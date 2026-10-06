"""Build model grounding from the query contract and repository ontology."""

from __future__ import annotations

import csv
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .contract import QueryContractError, load_query_contract
from .vocabulary import supported_predicates


SCHEMA_TYPE_URIS = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty)
MAX_SCHEMA_CONTEXT_CHARS = 48_000
COMMENT_CHARS = 120


def _one_line(graph: Graph, subject: URIRef, predicate: URIRef,
              limit: int = COMMENT_CHARS) -> str:
    values = sorted(
        (" ".join(str(value).split()) for value in graph.objects(subject, predicate)),
        key=str.casefold,
    )
    if not values:
        return ""
    value = values[0]
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _qname(value, prefixes: dict[str, str]) -> str:
    if not isinstance(value, URIRef):
        return str(value)
    candidates = [
        (namespace, prefix)
        for prefix, namespace in prefixes.items()
        if prefix and str(value).startswith(namespace)
    ]
    if candidates:
        namespace, prefix = max(candidates, key=lambda item: len(item[0]))
        return f"{prefix}:{str(value)[len(namespace):]}"
    return f"<{value}>"


def _contract_iri(term: str, prefixes: dict[str, str]) -> URIRef:
    prefix, local_name = term.split(":", 1)
    return URIRef(prefixes[prefix] + local_name)


def _external_property_context(
        repository_root: Path, prefixes: dict[str, str], locally_declared: set[URIRef],
        graph: Graph, externally_annotated: set[URIRef],
        queryable_properties: set[URIRef], mapping_policy: dict) -> list[str]:
    """Describe only contract-queryable external predicates."""
    mapping_directory = repository_root / "mappings"
    descriptions: dict[URIRef, set[str]] = {}
    kinds: dict[URIRef, set[str]] = {}
    if mapping_directory.is_dir():
        for path in sorted(mapping_directory.glob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    if row.get("mapping_status") not in mapping_policy["activeMappingStatuses"]:
                        continue
                    if row.get("term_type") not in mapping_policy["activeMappingTermTypes"]:
                        continue
                    term = row.get("ontology_term", "").strip()
                    if ":" not in term:
                        continue
                    prefix, local_name = term.split(":", 1)
                    namespace = prefixes.get(prefix)
                    if not namespace or not local_name or any(char.isspace() for char in local_name):
                        continue
                    iri = URIRef(namespace + local_name)
                    if iri not in queryable_properties or iri in locally_declared:
                        continue
                    kinds.setdefault(iri, set()).add(row["term_type"])
                    note = " ".join((row.get("notes") or "").split())
                    if note:
                        descriptions.setdefault(iri, set()).add(note)

    if mapping_policy["includeLocallyAnnotatedExternalProperties"]:
        for iri in externally_annotated:
            if iri not in queryable_properties or iri in locally_declared:
                continue
            for property_type, kind in (
                (OWL.ObjectProperty, "ObjectProperty"),
                (OWL.DatatypeProperty, "DatatypeProperty"),
                (OWL.AnnotationProperty, "AnnotationProperty"),
            ):
                if (iri, RDF.type, property_type) in graph:
                    kinds.setdefault(iri, set()).add(kind)
                    comment = _one_line(graph, iri, RDFS.comment)
                    if comment:
                        descriptions.setdefault(iri, set()).add(comment)

    if not kinds:
        return []

    lines = ["\nQueryable external-vocabulary predicates from the contract:"]
    for iri in sorted(kinds, key=str):
        domains = sorted(
            (_qname(value, prefixes) for value in graph.objects(iri, RDFS.domain)
             if isinstance(value, URIRef)), key=str.casefold
        )
        ranges = sorted(
            (_qname(value, prefixes) for value in graph.objects(iri, RDFS.range)
             if isinstance(value, URIRef)), key=str.casefold
        )
        details = f"  {_qname(iri, prefixes)} ({', '.join(sorted(kinds[iri]))})"
        if domains or ranges:
            details += f" ({', '.join(domains) or '?'} → {', '.join(ranges) or '?'})"
        label = _one_line(graph, iri, RDFS.label)
        if label:
            details += f"; label={label!r}"
        notes = sorted(descriptions.get(iri, ()), key=str.casefold)
        if notes:
            note = notes[0]
            if len(note) > COMMENT_CHARS:
                note = note[: COMMENT_CHARS - 1].rstrip() + "…"
            details += f"; mapping: {note}"
        lines.append(details)
    return lines


def _contract_context(contract: dict) -> list[str]:
    """Render ownership, emitted patterns and safety notes from the contract."""
    lines = [
        f"\nOireachtas query/schema contract {contract['contractVersion']} "
        f"(schema version {contract['schemaVersion']}):",
        "Named graph families (graph IRIs are dataset identifiers, not ontology terms):",
    ]
    for family in contract["graphFamilies"]:
        graph = family["graph"]
        if graph["kind"] == "fixed":
            identifier = f"<{graph['iri']}>"
        elif graph["kind"] == "fixed-set":
            identifier = ", ".join(f"<{iri}>" for iri in graph["iris"])
        else:
            identifier = f"<{graph['iriTemplate']}>"
        lines.append(
            f"  {family['id']}: {identifier}; owner={family['owner']}; "
            f"availability={family['availability']}; {family['owns']}"
        )

    lines.append("Current emitted RDF patterns (each entry declares availability and local-NLQ queryability):")
    for pattern in contract["emittedRdfPatterns"]:
        triples = "; ".join(" ".join(triple) for triple in pattern["triples"])
        queryability = (
            "queryable in local NLQ" if pattern.get("queryableInLocalNlq", True)
            else "not executable through the current local NLQ predicate allowlist"
        )
        detail = (
            f"  {pattern['id']} [{pattern['graphFamily']}; {pattern['availability']}; "
            f"{queryability}]: {triples}"
        )
        if pattern.get("note"):
            detail += f". {pattern['note']}"
        lines.append(detail)

    lines.append("Cross-graph joins use the same RDF resource IRI; descriptions need not be co-located:")
    for join in contract["crossGraphJoins"]:
        detail = (
            f"  {join['fromGraphFamily']} --{join['predicate']}--> "
            f"{join['toGraphFamily']} ({join['joinKey']})"
        )
        if join.get("appliesTo"):
            detail += f"; {join['appliesTo']}"
        lines.append(detail)

    lines.append("Entity label predicates (literal language tags are significant):")
    for entity_type, label in contract["labelsByEntityType"].items():
        languages = label.get("languages", [label.get("language", "unspecified")])
        detail = f"  {entity_type}: {label['predicate']} (language: {', '.join(languages)})"
        if label.get("note"):
            detail += f"; {label['note']}"
        lines.append(detail)

    lines.append("Reviewed external identity/link predicates (links are optional; no remote query is performed):")
    for identity in contract["externalIdentityPredicates"]:
        detail = (
            f"  {identity['entityType']}: {identity['predicate']} -> {identity['target']} "
            f"[{identity['graphFamily']}; Wikidata join={str(identity['wikidataJoin']).lower()}; "
            f"identity assertion={str(identity['identityAssertion']).lower()}]"
        )
        if identity.get("note"):
            detail += f"; {identity['note']}"
        lines.append(detail)

    reasoning = contract["reasoning"]
    lines.append(
        "Reasoning: " + reasoning["queryRule"] +
        f" OWL entailment={reasoning['owlEntailment']}."
    )
    lines.append("Unsupported or not-currently-populated patterns:")
    lines.extend(
        f"  {item['id']} [{item['status']}]: {item['detail']}"
        for item in contract["unsupportedPatterns"]
    )
    safety = contract["localSafety"]
    lines.append(
        "Local query boundary: " + ", ".join(safety["allowedOperations"]) +
        " only; rejected features: " + ", ".join(safety["rejectedFeatures"]) + ". " +
        safety["endpoint"]["note"]
    )
    return lines


def build_schema_context(ontology_dir: str | Path) -> str:
    """Ground in the contract's queryable terms and derive their axioms from source ontologies.

    The contract defines scope; ontology and pinned-vocabulary files provide
    descriptions and structural detail. No RDF instance data is sent to the model.
    """
    directory = Path(ontology_dir)
    contract = load_query_contract()
    graph = Graph()
    externally_annotated: set[URIRef] = set()
    prefixes: dict[str, str] = dict(contract["namespaces"])
    files = sorted(directory.glob("*.owl.ttl"))
    if not files:
        raise FileNotFoundError(f"No Turtle ontology modules found in {directory}")
    for path in files:
        module = Graph().parse(path, format="turtle")
        for term in module.subjects(RDFS.comment):
            if isinstance(term, URIRef) and not str(term).startswith((
                "https://data.oireachtas.ie/ontology#",
                "https://data.oireachtas.ie/ontology/members#",
            )):
                externally_annotated.add(term)
        graph += module
    for path, format_ in (
        (directory / "ELI-OWL" / "eli-1.5.rdf", "xml"),
        (directory / "ELI-DL-OWL" / "eli-dl.ttl", "turtle"),
    ):
        if path.is_file():
            vocabulary = Graph().parse(path, format=format_)
            graph += vocabulary

    queryable_class_uris = {
        _contract_iri(value, prefixes) for value in contract["queryableClasses"]
    }
    queryable_property_uris = {
        _contract_iri(value, prefixes) for value in contract["queryableProperties"]
    }
    property_allowlist = supported_predicates(directory)
    unqueryable_contract_terms = sorted(
        _qname(value, prefixes) for value in queryable_property_uris
        if value not in property_allowlist
    )
    if unqueryable_contract_terms:
        raise QueryContractError(
            "Query contract marks predicates queryable that are absent from the "
            "current local predicate allowlist: " + ", ".join(unqueryable_contract_terms)
        )
    undeclared_contract_classes = sorted(
        value for value in queryable_class_uris
        if (value, RDF.type, OWL.Class) not in graph and (value, RDF.type, RDFS.Class) not in graph
    )
    if undeclared_contract_classes:
        raise QueryContractError(
            "Query contract lists classes that are not declared by repository or pinned ontology files: "
            + ", ".join(_qname(value, prefixes) for value in undeclared_contract_classes)
        )
    local_namespaces = tuple(prefixes[prefix] for prefix in ("agents", "members"))

    def local(term) -> bool:
        return isinstance(term, URIRef) and str(term).startswith(local_namespaces)

    schema_terms = {
        type_: sorted(
            {term for term in graph.subjects(RDF.type, type_)
             if term in (queryable_class_uris if type_ == OWL.Class else queryable_property_uris)
             if local(term) and not any(str(value).lower() == "true"
                                        for value in graph.objects(term, OWL.deprecated))},
            key=str,
        )
        for type_ in SCHEMA_TYPE_URIS
    }
    locally_declared = {
        term for type_ in SCHEMA_TYPE_URIS for term in graph.subjects(RDF.type, type_)
        if local(term)
    }

    lines = [
        "Queryable vocabulary (scope comes from the versioned repository query contract; "
        "axioms/descriptions are read from ontology and pinned vocabulary files):",
        "Namespaces:",
    ]
    for prefix, namespace in sorted(prefixes.items()):
        lines.append(f"  {prefix}: <{namespace}>")

    for type_, heading in zip(SCHEMA_TYPE_URIS, (
            "Queryable classes", "Queryable object properties", "Queryable datatype properties")):
        lines.append(f"\n{heading}:")
        for term in schema_terms[type_]:
            if type_ == OWL.Class:
                parents = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.subClassOf)
                     if isinstance(value, URIRef)), key=str.casefold,
                )
                structural = f" subClassOf {', '.join(parents)}" if parents else ""
            else:
                domains = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.domain)
                     if isinstance(value, URIRef)), key=str.casefold,
                )
                ranges = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.range)
                     if isinstance(value, URIRef)), key=str.casefold,
                )
                parents = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.subPropertyOf)
                     if isinstance(value, URIRef)), key=str.casefold,
                )
                structural = ""
                if domains or ranges:
                    structural = f" ({', '.join(domains) or '?'} → {', '.join(ranges) or '?'})"
                if parents:
                    structural += f" subPropertyOf {', '.join(parents)}"
            label = _one_line(graph, term, SKOS.prefLabel) or _one_line(graph, term, RDFS.label)
            comment = _one_line(graph, term, RDFS.comment)
            detail = f"  {_qname(term, prefixes)}{structural}"
            if label:
                detail += f"; label={label!r}"
            if comment:
                detail += f"; note={comment}"
            lines.append(detail)

    mapping_policy = contract["localSafety"]["predicateAllowlist"]
    lines.extend(_external_property_context(
        directory.parent, prefixes, locally_declared, graph, externally_annotated,
        queryable_property_uris, mapping_policy,
    ))
    lines.extend(_contract_context(contract))

    context = "\n".join(lines)
    if len(context) > MAX_SCHEMA_CONTEXT_CHARS:
        raise ValueError(
            f"Generated schema context is {len(context)} characters; exceeds the {MAX_SCHEMA_CONTEXT_CHARS}-character cap."
        )
    return context
