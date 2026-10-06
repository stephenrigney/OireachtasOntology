"""Loader and compatibility checks for the repository-owned query contract."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "query-schema-contract.json"
SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_CONTRACT_MAJOR = 1
SUPPORTED_SAFETY_MAJOR = 1
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


class QueryContractError(ValueError):
    """The query contract is malformed or uses an unsupported version."""


def _version(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not (match := _SEMVER.fullmatch(value)):
        raise QueryContractError(f"Query contract {label} must be a semantic version (major.minor.patch).")
    return tuple(int(component) for component in match.groups())


def _required_object(document: dict[str, Any], name: str) -> dict[str, Any]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise QueryContractError(f"Query contract field {name!r} must be an object.")
    return value


def _required_list(document: dict[str, Any], name: str) -> list[Any]:
    value = document.get(name)
    if not isinstance(value, list):
        raise QueryContractError(f"Query contract field {name!r} must be an array.")
    return value


def _check_qname(value: Any, namespaces: dict[str, Any], where: str) -> None:
    if not isinstance(value, str) or ":" not in value:
        raise QueryContractError(f"Query contract {where} must be a prefixed name.")
    prefix, local_name = value.split(":", 1)
    if prefix not in namespaces or not local_name or any(character.isspace() for character in local_name):
        raise QueryContractError(f"Query contract {where} uses an unknown or invalid QName {value!r}.")


def _check_iri(value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise QueryContractError(f"Query contract {where} must be an absolute HTTP(S) IRI.")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise QueryContractError(f"Query contract {where} must be an absolute HTTP(S) IRI.")


def _validate_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise QueryContractError("Query contract root must be a JSON object.")
    if document.get("$schema") != _JSON_SCHEMA_DIALECT:
        raise QueryContractError(f"Query contract $schema must be {_JSON_SCHEMA_DIALECT!r}.")

    schema_version = document.get("schemaVersion")
    if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
        raise QueryContractError(
            f"Unsupported query contract schema version {schema_version!r}; "
            f"this consumer supports schema version {SUPPORTED_SCHEMA_VERSION}."
        )
    contract_major, _, _ = _version(document.get("contractVersion"), "contractVersion")
    if contract_major != SUPPORTED_CONTRACT_MAJOR:
        raise QueryContractError(
            f"Unsupported query contract major version {contract_major}; "
            f"this consumer supports major version {SUPPORTED_CONTRACT_MAJOR}."
        )

    required = (
        "contractId", "contractSchema", "namespaces", "queryableClasses", "queryableProperties",
        "graphFamilies", "labelsByEntityType", "emittedRdfPatterns",
        "crossGraphJoins", "externalIdentityPredicates", "reasoning",
        "unsupportedPatterns", "localSafety",
    )
    missing = [name for name in required if name not in document]
    if missing:
        raise QueryContractError("Query contract is missing required fields: " + ", ".join(missing) + ".")
    _check_iri(document.get("contractId"), "contractId")
    if not isinstance(document.get("contractSchema"), str) or not document["contractSchema"]:
        raise QueryContractError("Query contract contractSchema must name the repository's JSON Schema artifact.")

    namespaces = _required_object(document, "namespaces")
    if not namespaces or any(not isinstance(prefix, str) or not isinstance(iri, str) or not iri
                             for prefix, iri in namespaces.items()):
        raise QueryContractError("Query contract namespaces must map prefixes to non-empty namespace IRIs.")
    for prefix, iri in namespaces.items():
        _check_iri(iri, f"namespaces.{prefix}")

    for field in ("queryableClasses", "queryableProperties"):
        values = _required_list(document, field)
        if (not values or any(not isinstance(value, str) for value in values)
                or len(values) != len(set(values))):
            raise QueryContractError(f"Query contract {field} must be a non-empty array of unique QNames.")
        for value in values:
            _check_qname(value, namespaces, field)

    graph_families = _required_list(document, "graphFamilies")
    graph_ids: set[str] = set()
    for family in graph_families:
        if not isinstance(family, dict):
            raise QueryContractError("Every query contract graph family must be an object.")
        family_id = family.get("id")
        graph = family.get("graph")
        if not isinstance(family_id, str) or not family_id or family_id in graph_ids:
            raise QueryContractError(f"Query contract graph family has a missing or duplicate id: {family_id!r}.")
        graph_ids.add(family_id)
        if not isinstance(graph, dict) or graph.get("kind") not in {"fixed", "fixed-set", "resource-pattern"}:
            raise QueryContractError(f"Query contract graph family {family_id!r} has an unsupported graph pattern.")
        graph_key = {"fixed": "iri", "fixed-set": "iris", "resource-pattern": "iriTemplate"}[graph["kind"]]
        if graph_key not in graph:
            raise QueryContractError(f"Query contract graph family {family_id!r} is missing {graph_key!r}.")
        if graph["kind"] == "fixed":
            _check_iri(graph["iri"], f"graphFamilies.{family_id}.graph.iri")
        elif graph["kind"] == "fixed-set":
            iris = graph["iris"]
            if not isinstance(iris, list) or not iris:
                raise QueryContractError(f"Query contract graph family {family_id!r} requires a non-empty IRI set.")
            for iri in iris:
                _check_iri(iri, f"graphFamilies.{family_id}.graph.iris")
        elif not isinstance(graph["iriTemplate"], str) or not graph["iriTemplate"]:
            raise QueryContractError(f"Query contract graph family {family_id!r} has an invalid IRI template.")
        for field in ("owner", "availability", "owns"):
            if not isinstance(family.get(field), str) or not family[field]:
                raise QueryContractError(f"Query contract graph family {family_id!r} is missing {field!r}.")

    patterns = _required_list(document, "emittedRdfPatterns")
    pattern_ids: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, dict):
            raise QueryContractError("Every emitted RDF pattern must be an object.")
        pattern_id = pattern.get("id")
        if not isinstance(pattern_id, str) or not pattern_id or pattern_id in pattern_ids:
            raise QueryContractError(f"Query contract emitted pattern has a missing or duplicate id: {pattern_id!r}.")
        pattern_ids.add(pattern_id)
        if pattern.get("graphFamily") not in graph_ids:
            raise QueryContractError(f"Emitted pattern {pattern_id!r} refers to an unknown graph family.")
        if not isinstance(pattern.get("availability"), str) or not pattern["availability"]:
            raise QueryContractError(f"Emitted pattern {pattern_id!r} is missing an availability value.")
        if ("queryableInLocalNlq" in pattern
                and type(pattern["queryableInLocalNlq"]) is not bool):
            raise QueryContractError(f"Emitted pattern {pattern_id!r} queryableInLocalNlq must be boolean.")
        triples = pattern.get("triples")
        if (not isinstance(triples, list) or not triples
                or any(not isinstance(triple, list) or len(triple) != 3
                       or any(not isinstance(term, str) for term in triple)
                       for triple in triples)):
            raise QueryContractError(f"Emitted pattern {pattern_id!r} must contain three-term RDF patterns.")

    for field in ("crossGraphJoins", "externalIdentityPredicates"):
        for item in _required_list(document, field):
            if not isinstance(item, dict):
                raise QueryContractError(f"Every {field} entry must be an object.")
            references = ([item.get("fromGraphFamily"), item.get("toGraphFamily")]
                          if field == "crossGraphJoins" else [item.get("graphFamily")])
            if any(reference not in graph_ids for reference in references):
                raise QueryContractError(f"A query contract {field} entry refers to an unknown graph family.")
            required_strings = (
                ("fromGraphFamily", "predicate", "toGraphFamily", "joinKey")
                if field == "crossGraphJoins" else ("entityType", "predicate", "target", "graphFamily")
            )
            if any(not isinstance(item.get(name), str) or not item[name] for name in required_strings):
                raise QueryContractError(f"Query contract {field} entries have missing string fields.")
            if field == "externalIdentityPredicates" and any(
                    type(item.get(name)) is not bool for name in ("wikidataJoin", "identityAssertion")):
                raise QueryContractError("Query contract external identity flags must be boolean.")

    labels = _required_object(document, "labelsByEntityType")
    for entity_type, label in labels.items():
        if not isinstance(entity_type, str) or not isinstance(label, dict):
            raise QueryContractError("Query contract labelsByEntityType entries must map entity names to objects.")
        _check_qname(label.get("predicate"), namespaces, f"labelsByEntityType.{entity_type}.predicate")
        language = label.get("language")
        languages = label.get("languages")
        if (language is not None and not isinstance(language, str)
                or languages is not None and (not isinstance(languages, list)
                                               or not all(isinstance(item, str) for item in languages))):
            raise QueryContractError(f"Query contract label languages for {entity_type!r} are malformed.")

    reasoning = _required_object(document, "reasoning")
    for field in ("owlEntailment", "queryRule"):
        if not isinstance(reasoning.get(field), str) or not reasoning[field]:
            raise QueryContractError(f"Query contract reasoning.{field} must be a non-empty string.")
    for field in ("rdfsSubclassInference", "owlSameAsExpansion"):
        if type(reasoning.get(field)) is not bool:
            raise QueryContractError(f"Query contract reasoning.{field} must be boolean.")

    unsupported = _required_list(document, "unsupportedPatterns")
    for item in unsupported:
        if (not isinstance(item, dict)
                or any(not isinstance(item.get(field), str) or not item[field]
                       for field in ("id", "status", "detail"))):
            raise QueryContractError("Query contract unsupportedPatterns entries require id, status, and detail strings.")

    safety = _required_object(document, "localSafety")
    safety_major, _, _ = _version(safety.get("version"), "localSafety.version")
    if safety_major != SUPPORTED_SAFETY_MAJOR:
        raise QueryContractError(
            f"Unsupported local query safety major version {safety_major}; "
            f"this consumer supports major version {SUPPORTED_SAFETY_MAJOR}."
        )
    if safety.get("allowedOperations") != ["SELECT", "ASK"]:
        raise QueryContractError("Unsupported local query safety operation policy; only SELECT and ASK are supported.")
    rejected = safety.get("rejectedFeatures")
    if not isinstance(rejected, list) or not all(isinstance(value, str) and value for value in rejected):
        raise QueryContractError("Query contract localSafety.rejectedFeatures must be an array of strings.")
    if safety.get("propertyPaths") != "direct-predicates-only":
        raise QueryContractError("Unsupported local query safety property-path policy.")
    federation = _required_object(safety, "federation")
    if federation.get("enabled") is not False:
        raise QueryContractError("This query consumer does not support a contract that enables federation.")
    for field in ("requiresExplicitSafetyVersionChange", "requiresExplicitContractVersionChange"):
        if type(federation.get(field)) is not bool:
            raise QueryContractError(f"Query contract localSafety.federation.{field} must be boolean.")

    limits = _required_object(safety, "limits")
    for field in ("maxQueryCharacters", "defaultSelectLimit", "maxExplicitLimit", "maxOffset", "fusekiTimeoutSeconds"):
        if type(limits.get(field)) is not int or limits[field] < 1:
            raise QueryContractError(f"Query contract localSafety.limits.{field} must be a positive integer.")

    predicate_policy = _required_object(safety, "predicateAllowlist")
    for field in ("includeLocalOntologyDeclarations", "includeLocallyAnnotatedExternalProperties",
                  "enforcedBySharedNlqPipeline"):
        if type(predicate_policy.get(field)) is not bool:
            raise QueryContractError(f"Query contract localSafety.predicateAllowlist.{field} must be boolean.")
    for field in ("localOntologyPrefixes", "activeMappingStatuses",
                  "activeMappingTermTypes", "unconditionalPredicates"):
        values = predicate_policy.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            raise QueryContractError(f"Query contract localSafety.predicateAllowlist.{field} must be an array of strings.")
    for prefix in predicate_policy["localOntologyPrefixes"]:
        if prefix not in namespaces:
            raise QueryContractError(f"Unknown local ontology prefix in predicate allowlist: {prefix!r}.")
    for term in predicate_policy["unconditionalPredicates"]:
        _check_qname(term, namespaces, "localSafety.predicateAllowlist.unconditionalPredicates")

    endpoint = _required_object(safety, "endpoint")
    for field in ("configuration", "defaultUrl", "requiredEndpointPath"):
        if not isinstance(endpoint.get(field), str) or not endpoint[field]:
            raise QueryContractError(f"Query contract localSafety.endpoint.{field} must be a non-empty string.")
    _check_iri(endpoint["defaultUrl"], "localSafety.endpoint.defaultUrl")
    if not endpoint["requiredEndpointPath"].startswith("/"):
        raise QueryContractError("Query contract localSafety.endpoint.requiredEndpointPath must be an absolute path.")
    for field in ("localDeploymentExpected", "hostLocalityEnforced"):
        if type(endpoint.get(field)) is not bool:
            raise QueryContractError(f"Query contract localSafety.endpoint.{field} must be boolean.")

    return document


@lru_cache(maxsize=8)
def _load_cached(path: str) -> dict[str, Any]:
    contract_path = Path(path)
    try:
        document = json.loads(contract_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise QueryContractError(f"Could not read the query contract at {contract_path}.") from error
    except json.JSONDecodeError as error:
        raise QueryContractError(f"The query contract at {contract_path} is not valid JSON: {error.msg}.") from error
    return _validate_document(document)


def load_query_contract(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the contract; reject schema/contract majors we do not support."""
    contract_path = Path(path) if path is not None else CONTRACT_PATH
    return _load_cached(str(contract_path.resolve()))
