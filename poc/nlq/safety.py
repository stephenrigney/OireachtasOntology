"""Small, conservative SPARQL query gate for untrusted generated text."""

from __future__ import annotations

from collections.abc import Iterator

from pyparsing import ParseResults
from rdflib import URIRef, Variable
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue

from .contract import QueryContractError, load_query_contract
from .errors import NLQError


_LOCAL_SAFETY = load_query_contract()["localSafety"]
_ENFORCED_REJECTIONS = frozenset({
    "SPARQL Update", "SERVICE", "FROM", "FROM NAMED", "subqueries",
    "variable predicates", "property paths",
})
if frozenset(_LOCAL_SAFETY["rejectedFeatures"]) != _ENFORCED_REJECTIONS:
    raise QueryContractError(
        "The local safety contract's rejected-feature list does not match validate_sparql enforcement."
    )
if _LOCAL_SAFETY["propertyPaths"] != "direct-predicates-only":
    raise QueryContractError("The local safety contract's property-path policy is unsupported.")
MAX_QUERY_CHARS = _LOCAL_SAFETY["limits"]["maxQueryCharacters"]
MAX_RESULT_ROWS = _LOCAL_SAFETY["limits"]["maxExplicitLimit"]
MAX_RESULT_OFFSET = _LOCAL_SAFETY["limits"]["maxOffset"]
ALLOWED_QUERY_OPERATIONS = frozenset(_LOCAL_SAFETY["allowedOperations"])
DEFAULT_SELECT_LIMIT = _LOCAL_SAFETY["limits"]["defaultSelectLimit"]
_CONTRACT_NAMESPACES = load_query_contract()["namespaces"]


def _walk(value) -> Iterator[CompValue]:
    if isinstance(value, CompValue):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, (list, tuple, ParseResults)):
        for child in value:
            yield from _walk(child)


def complete_known_prefixes(sparql: str) -> str:
    """Declare used, undeclared QNames only from the versioned query contract.

    RDFLib's SPARQL parser distinguishes QName nodes from literals, comments,
    variables, and absolute IRIs. If parsing fails, or a used prefix is not in
    the contract, leave the query untouched so normal safety validation fails
    closed. Oversized input is likewise left for the existing length check.
    """
    if not isinstance(sparql, str) or len(sparql) > MAX_QUERY_CHARS:
        return sparql

    try:
        parsed = parseQuery(sparql)
    except Exception:
        return sparql

    nodes = tuple(_walk(parsed))
    declared_prefixes = {
        str(node["prefix"] if "prefix" in node else "")
        for node in nodes if node.name == "PrefixDecl"
    }
    used_prefixes = {
        str(node["prefix"] if "prefix" in node else "")
        for node in nodes if node.name == "pname"
    }
    missing_prefixes = sorted(
        (used_prefixes - declared_prefixes) & _CONTRACT_NAMESPACES.keys()
    )
    if not missing_prefixes:
        return sparql

    declarations = "\n".join(
        f"PREFIX {prefix}: <{_CONTRACT_NAMESPACES[prefix]}>"
        for prefix in missing_prefixes
    )
    return declarations + "\n" + sparql


def validate_sparql(sparql: str, *, supported_predicates: frozenset[URIRef] | None = None) -> str:
    """Parse a read-only SELECT/ASK query and cap SELECT rows at 100."""
    if not isinstance(sparql, str) or not sparql.strip():
        raise NLQError("The model did not provide a SPARQL query.")
    if len(sparql) > MAX_QUERY_CHARS:
        raise NLQError(f"The generated SPARQL is too long (maximum {MAX_QUERY_CHARS} characters).")

    try:
        parsed = parseQuery(sparql)
    except Exception as error:
        reason = str(error).splitlines()[0][:160]
        raise NLQError(f"Generated SPARQL is malformed and was not sent to Fuseki: {reason}") from error

    query = parsed[1]
    operation = query.name
    operation_name = operation.split("Query", 1)[0].upper()
    if operation not in {"SelectQuery", "AskQuery"} or operation_name not in ALLOWED_QUERY_OPERATIONS:
        raise NLQError("Only read-only SPARQL SELECT and ASK queries are allowed.")

    nodes = tuple(_walk(parsed))
    query_prefixes = {}
    for node in nodes:
        if node.name == "PrefixDecl" and "iri" in node:
            prefix = node["prefix"] if "prefix" in node else ""
            query_prefixes[prefix] = node["iri"]
    for node in nodes:
        if node.name == "pname":
            prefix = node["prefix"] if "prefix" in node else ""
            if prefix not in query_prefixes:
                raise NLQError(f"SPARQL prefix {prefix!r} is undeclared.")
    if any(node.name == "ServiceGraphPattern" for node in nodes):
        raise NLQError("SPARQL SERVICE clauses are not allowed.")

    # Subqueries can hide unbounded intermediate work even when the outer
    # SELECT is limited. They are not needed for this POC's straightforward
    # graph-pattern/aggregate queries.
    if any(node.name == "SubSelect" for node in nodes):
        raise NLQError("SPARQL subqueries are not allowed; use one straightforward SELECT or ASK query.")

    # Reject property-path operators. A direct IRI predicate is represented as
    # one PathElt by RDFLib; repetition, inverses, alternatives and sequences
    # can cause expensive transitive graph traversal and are unnecessary here.
    for node in nodes:
        if node.name == "TriplesBlock" and "triples" in node:
            if any(len(triple) == 3 and isinstance(triple[1], Variable) for triple in node["triples"]):
                raise NLQError("Variable predicates are not allowed; use a property from the supplied schema.")
        if node.name == "PathElt":
            predicate = node["part"]
            if isinstance(predicate, CompValue) and predicate.name == "pname":
                prefix = predicate["prefix"] if "prefix" in predicate else ""
                local_name = predicate["localname"] if "localname" in predicate else ""
                namespace = query_prefixes.get(prefix)
                predicate = URIRef(str(namespace) + str(local_name)) if namespace is not None else predicate
            direct_predicate = isinstance(predicate, URIRef)
            if "mod" in node or not direct_predicate:
                raise NLQError("Only direct, single-property graph patterns are allowed; SPARQL property paths are not.")
            if supported_predicates is not None and predicate not in supported_predicates:
                raise NLQError(f"SPARQL predicate <{predicate}> is not declared by the ontology or active mappings.")
        if node.name in {"PathEltOrInverse", "PathNegatedPropertySet"}:
            raise NLQError("SPARQL inverse and negated property paths are not allowed.")
        if node.name in {"PathSequence", "PathAlternative"}:
            parts = node["part"] if "part" in node else []
            if isinstance(parts, (list, tuple, ParseResults)) and len(parts) > 1:
                raise NLQError("SPARQL property paths using sequences and alternatives are not allowed.")

    # FROM/FROM NAMED can override the Fuseki dataset and potentially fetch an
    # external graph. The POC only queries the dataset configured on Fuseki.
    if any(node.name == "DatasetClause" for node in nodes):
        raise NLQError("FROM and FROM NAMED are not allowed; query the configured Fuseki dataset.")

    limit_offset = query["limitoffset"] if "limitoffset" in query else None
    limit = limit_offset["limit"] if limit_offset is not None and "limit" in limit_offset else None
    offset = limit_offset["offset"] if limit_offset is not None and "offset" in limit_offset else None
    add_default_limit = operation == "SelectQuery" and limit is None
    if limit is not None:
        try:
            row_limit = int(str(limit))
        except (TypeError, ValueError) as error:
            raise NLQError("The SPARQL result limit must be an integer.") from error
        if row_limit > MAX_RESULT_ROWS:
            raise NLQError(f"Query result limits may not exceed {MAX_RESULT_ROWS} rows.")

    if offset is not None:
        try:
            row_offset = int(str(offset))
        except (TypeError, ValueError) as error:
            raise NLQError("The SPARQL result offset must be an integer.") from error
        if row_offset > MAX_RESULT_OFFSET:
            raise NLQError(f"Query result offsets may not exceed {MAX_RESULT_OFFSET} rows.")

    return sparql.rstrip() + f"\nLIMIT {DEFAULT_SELECT_LIMIT}" if add_default_limit else sparql
