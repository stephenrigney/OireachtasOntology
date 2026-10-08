from __future__ import annotations

import ast
import builtins
import json
from pathlib import Path

import pytest
from rdflib import URIRef

from poc.nlq.contract import (
    CONTRACT_PATH,
    QueryContractError,
    load_query_contract,
)
from poc.nlq.errors import NLQError
from poc.nlq.fuseki import (
    DEFAULT_FUSEKI_QUERY_URL,
    FUSEKI_QUERY_PATH,
    FUSEKI_QUERY_URL_ENV,
    FUSEKI_TIMEOUT_SECONDS,
    READINESS_SOURCES_QUERY,
)
from poc.nlq.safety import (
    ALLOWED_QUERY_OPERATIONS,
    DEFAULT_SELECT_LIMIT,
    MAX_QUERY_CHARS,
    MAX_RESULT_OFFSET,
    MAX_RESULT_ROWS,
    validate_sparql,
)
from poc.nlq.schema import build_schema_context
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]


def _write_contract(tmp_path: Path, mutate) -> Path:
    document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    mutate(document)
    path = tmp_path / "query-schema-contract.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_contract_artifact_loads_and_validates_its_versioned_shape():
    contract = load_query_contract()
    schema = json.loads(
        (ROOT / "poc/specs/query-schema-contract.schema.json").read_text(encoding="utf-8")
    )

    assert contract["contractVersion"] == "1.1.0"
    assert contract["schemaVersion"] == schema["properties"]["schemaVersion"]["const"] == 1
    assert contract["contractId"] == "https://data.oireachtas.ie/specs/query-schema-contract"
    assert contract["contractSchema"] == "poc/specs/query-schema-contract.schema.json"
    assert schema["$schema"] == contract["$schema"]
    assert {
        "graphFamilies", "emittedRdfPatterns", "externalIdentityPredicates", "localSafety",
    }.issubset(schema["required"])
    assert contract["namespaces"]["agents"] == "https://data.oireachtas.ie/ontology#"


def test_contract_minor_additions_are_compatible_and_unknown_fields_are_ignored(tmp_path):
    def add_compatible_pattern(document):
        document["contractVersion"] = "1.4.2"
        document["informationalExtension"] = {"owner": "consumer"}
        document["emittedRdfPatterns"].append({
            "id": "additional-compatible-member-pattern",
            "graphFamily": "member-records",
            "availability": "emitted",
            "triples": [["?member", "rdf:type", "agents:Member"]],
        })

    path = _write_contract(tmp_path, add_compatible_pattern)

    contract = load_query_contract(path)

    assert contract["contractVersion"] == "1.4.2"
    assert "additional-compatible-member-pattern" in {
        pattern["id"] for pattern in contract["emittedRdfPatterns"]
    }


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda document: document.update(schemaVersion=2), "Unsupported query contract schema version 2"),
        (lambda document: document.update(contractVersion="2.0.0"), "Unsupported query contract major version 2"),
        (lambda document: document["localSafety"].update(version="2.0.0"), "Unsupported local query safety major version 2"),
        (lambda document: document["emittedRdfPatterns"][0].update(graphFamily="unknown"), "unknown graph family"),
        (lambda document: document["namespaces"].pop("agents"), "unknown or invalid QName"),
    ],
)
def test_contract_rejects_unsupported_versions_and_invalid_references(tmp_path, mutate, message):
    path = _write_contract(tmp_path, mutate)

    with pytest.raises(QueryContractError, match=message):
        load_query_contract(path)


def test_graph_family_ownership_patterns_and_cross_graph_joins_are_explicit():
    contract = load_query_contract()
    families = {family["id"]: family for family in contract["graphFamilies"]}
    patterns = {pattern["id"]: pattern for pattern in contract["emittedRdfPatterns"]}

    assert families["houses"]["graph"] == {
        "kind": "fixed", "iri": "https://data.oireachtas.ie/graph/houses",
    }
    assert families["committees"]["owner"] == "Committees ETL"
    assert families["member-records"]["graph"]["iriTemplate"].endswith("{percent-encoded-memberCode}")
    assert families["bill-records"]["availability"] == "optional-published-when-loaded"
    assert families["offices"]["availability"] == "published-when-loaded"
    assert families["administrative-units"]["availability"] == "published-when-loaded"
    assert patterns["member-house-membership"]["graphFamily"] == "member-records"
    assert patterns["member-collection-membership"]["availability"] == "emitted"
    assert patterns["registered-office-description"]["graphFamily"] == "offices"
    assert patterns["administrative-unit-description"]["graphFamily"] == "administrative-units"
    assert patterns["accepted-member-office-holding"]["queryableInLocalNlq"] is True
    assert patterns["accepted-cabinet-membership"]["queryableInLocalNlq"] is True
    assert {
        "members:NamedOffice", "members:AdministrativeUnit",
        "members:OfficeHolding", "members:CabinetMembership",
    }.issubset(contract["queryableClasses"])
    assert any(
        join["fromGraphFamily"] == "member-records"
        and join["predicate"] == "members:isCommitteeMembershipOf"
        and join["toGraphFamily"] == "committees"
        for join in contract["crossGraphJoins"]
    )
    assert any(
        join["fromGraphFamily"] == "member-records"
        and join["predicate"] == "members:heldOffice"
        and join["toGraphFamily"] == "offices"
        for join in contract["crossGraphJoins"]
    )
    assert any(
        join["fromGraphFamily"] == "offices"
        and join["predicate"] == "members:headsAdministrativeUnit"
        and join["toGraphFamily"] == "administrative-units"
        for join in contract["crossGraphJoins"]
    )
    assert contract["reasoning"]["owlEntailment"] == "none"
    assert "members:ParliamentaryGroup" not in contract["queryableClasses"]
    assert "members:OfficeType" not in contract["queryableClasses"]
    unsupported = {item["id"] for item in contract["unsupportedPatterns"]}
    assert "parliamentary-group-records" in unsupported
    assert "office-type-vocabulary" in unsupported
    assert "office-registry-data" not in unsupported


def test_supported_predicates_come_from_contract_policy_and_active_sources():
    contract = load_query_contract()
    predicates = supported_predicates(ROOT / "ontology")
    namespaces = contract["namespaces"]
    queryable = {
        URIRef(namespaces[prefix] + local_name)
        for prefix, local_name in (term.split(":", 1) for term in contract["queryableProperties"])
    }

    assert queryable.issubset(predicates)
    assert URIRef("http://data.europa.eu/eli/ontology#title") in predicates
    assert URIRef("http://data.europa.eu/eli/eli-draft-legislation-ontology#forms_part_of") in predicates
    assert URIRef("http://www.w3.org/2002/07/owl#sameAs") in predicates
    assert URIRef("https://data.oireachtas.ie/ontology/members#recognisedAsParty") in predicates
    assert URIRef("http://xmlns.com/foaf/0.1/isPrimaryTopicOf") in predicates
    assert "skos:altLabel" in contract["localSafety"]["predicateAllowlist"]["unconditionalPredicates"]
    assert "org:heldBy" in contract["localSafety"]["predicateAllowlist"]["unconditionalPredicates"]
    for property_name in (
        "members:hasOfficeHolding", "members:heldOffice", "members:officeHolder",
        "members:hasRoleType", "members:headsAdministrativeUnit",
        "members:isCabinetMembershipOf", "members:supportedByOfficeHolding",
    ):
        prefix, local = property_name.split(":", 1)
        assert URIRef(namespaces[prefix] + local) in queryable

    # These are real emitted triples but are deliberately not in the current
    # executable grounding allowlist; the contract calls that out explicitly.
    for excluded in ("dct:temporal", "eli:has_part", "eli:is_realized_by"):
        prefix, local_name = excluded.split(":", 1)
        assert URIRef(namespaces[prefix] + local_name) not in predicates
        assert excluded not in contract["queryableProperties"]


def test_grounding_is_generated_from_contract_scope_without_private_etl_imports(monkeypatch):
    contract = load_query_contract()
    original_import = builtins.__import__

    def reject_etl_import(name, *args, **kwargs):
        if name == "oireachtas_etl" or name.startswith("oireachtas_etl."):
            raise AssertionError(f"query grounding attempted private ETL import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_etl_import)
    context = build_schema_context(ROOT / "ontology")

    for term in ("agents:Member", "members:PartyMembership", "eli-dl:DraftLegislationWork"):
        assert term in context
    assert "contract 1.1.0 (schema version 1)" in context
    assert "https://data.oireachtas.ie/graph/committees" in context
    assert "https://data.oireachtas.ie/graph/offices" in context
    assert "members:CabinetMembership" in context
    assert "same RDF resource IRI" in context
    assert "Reviewed Wikidata political-party item" in context
    assert "not executable through the current local NLQ predicate allowlist" in context
    assert "members:ParliamentaryGroup (" not in context
    assert "Queryable classes" in context
    assert "brick:" not in context  # unrelated ontology namespaces are not prompt grounding

    nlq_root = ROOT / "poc/nlq"
    for source_path in nlq_root.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith("oireachtas_etl") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("oireachtas_etl")


def test_safety_contract_values_match_validate_sparql_and_local_fuseki_boundary():
    contract = load_query_contract()
    safety = contract["localSafety"]
    limits = safety["limits"]

    assert ALLOWED_QUERY_OPERATIONS == frozenset(safety["allowedOperations"]) == {"SELECT", "ASK"}
    assert MAX_QUERY_CHARS == limits["maxQueryCharacters"] == 32_000
    assert DEFAULT_SELECT_LIMIT == limits["defaultSelectLimit"] == 100
    assert MAX_RESULT_ROWS == limits["maxExplicitLimit"] == 100
    assert MAX_RESULT_OFFSET == limits["maxOffset"] == 10_000
    assert FUSEKI_TIMEOUT_SECONDS == limits["fusekiTimeoutSeconds"] == 15
    assert FUSEKI_QUERY_URL_ENV == safety["endpoint"]["configuration"] == "NLQ_FUSEKI_QUERY_URL"
    assert DEFAULT_FUSEKI_QUERY_URL == safety["endpoint"]["defaultUrl"]
    assert FUSEKI_QUERY_PATH == safety["endpoint"]["requiredEndpointPath"].strip("/") == "query"
    assert safety["endpoint"]["localDeploymentExpected"] is True
    assert safety["endpoint"]["hostLocalityEnforced"] is False
    assert safety["federation"]["enabled"] is False
    assert set(safety["rejectedFeatures"]) == {
        "SPARQL Update", "SERVICE", "FROM", "FROM NAMED", "subqueries",
        "variable predicates", "property paths",
    }
    assert "__" not in READINESS_SOURCES_QUERY
    assert "https://data.oireachtas.ie/graph/houses" in READINESS_SOURCES_QUERY
    assert "https://data.oireachtas.ie/graph/member/" in READINESS_SOURCES_QUERY

    with pytest.raises(NLQError, match="too long"):
        validate_sparql("SELECT ?s WHERE { ?s <urn:p> ?o }" + " " * MAX_QUERY_CHARS)

    forbidden = (
        "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
        "SELECT ?s WHERE { SERVICE <https://example.test/sparql> { ?s <urn:p> ?o } }",
        "SELECT ?s FROM NAMED <https://example.test/graph> WHERE { ?s <urn:p> ?o }",
        "SELECT ?s WHERE { { SELECT ?s WHERE { ?s <urn:p> ?o } } }",
        "SELECT ?s WHERE { ?s ?p ?o }",
        "SELECT ?s WHERE { ?s <urn:p>* ?o }",
    )
    for query in forbidden:
        with pytest.raises(NLQError):
            validate_sparql(query)


def test_emitted_but_unallowlisted_patterns_are_not_mislabeled_queryable():
    contract = load_query_contract()
    patterns = {pattern["id"]: pattern for pattern in contract["emittedRdfPatterns"]}

    for pattern_id in (
        "house-term-temporal-reference", "bill-document-work-links",
    ):
        assert patterns[pattern_id]["queryableInLocalNlq"] is False
    for pattern_id in ("house-term-temporal-reference", "bill-document-work-links"):
        assert "not-queryable" in patterns[pattern_id]["availability"]
