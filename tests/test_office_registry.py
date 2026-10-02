from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from oireachtas_etl.cli import main
from oireachtas_etl.config import ADMINISTRATIVE_UNITS_GRAPH, OFFICES_GRAPH
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.offices import (
    OFFICE_TYPE_CABINET_QUALIFICATION,
    OFFICE_TYPE_POLICY_VERSION,
    administrative_unit_iri,
    office_iri,
    transform_administrative_units,
    transform_offices,
)
from oireachtas_etl.validation.offices import (
    validate_administrative_units,
    validate_offices,
    validate_registry_source,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "registries/ministerial-office-registry.json"


def sample_registry() -> dict:
    return {
        "version": 1,
        "administrative_units": [{
            "key": "u-000001",
            "label_en": "Synthetic unit",
            "label_ga": "Aonad samplach",
            "aliases": [{"language": "en", "label": "Synthetic unit alias"}],
            "reviewer_notes": "Synthetic test identity only; not registry evidence.",
            "evidence": ["tests/test_office_registry.py#synthetic-unit"],
        }],
        "offices": [{
            "key": "o-000001",
            "label_en": "Synthetic ministerial office",
            "aliases": [{"language": "ga", "label": "Oifig shamplach"}],
            "office_type": "MinisterOfficeType",
            "unit_relationships": [{"relationship": "headsAdministrativeUnit", "unit_key": "u-000001"}],
            "reviewer_notes": "Synthetic test identity only; not registry evidence.",
            "evidence": ["tests/test_office_registry.py#synthetic-office"],
        }, {
            "key": "o-000002",
            "label_en": "Synthetic Minister of State office",
            "aliases": [],
            "office_type": "MinisterOfStateOfficeType",
            "unit_relationships": [{"relationship": "assignedToAdministrativeUnit", "unit_key": "u-000001"}],
            "reviewer_notes": "Synthetic test identity only; not registry evidence.",
            "evidence": ["tests/test_office_registry.py#synthetic-minister-of-state"],
        }],
    }


def test_initial_reviewed_registry_is_independently_valid_and_minimal():
    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    units = transform_administrative_units(registry)
    offices = transform_offices(registry)
    validate_administrative_units(registry, units)
    validate_offices(registry, offices)

    assert [unit["key"] for unit in registry["administrative_units"]] == ["u-000001"]
    assert [office["key"] for office in registry["offices"]] == [
        "o-000001", "o-000002", "o-000003"
    ]
    finance_unit = administrative_unit_iri("u-000001")
    taoiseach = office_iri("o-000001")
    tanaiste = office_iri("o-000002")
    finance = office_iri("o-000003")
    assert len(list(units.triples((None, RDF.type, MEMBERS.AdministrativeUnit)))) == 1
    assert (taoiseach, MEMBERS.hasRoleType, MEMBERS.TaoiseachOfficeType) in offices
    assert (tanaiste, MEMBERS.hasRoleType, MEMBERS.TanaisteOfficeType) in offices
    assert (finance, MEMBERS.hasRoleType, MEMBERS.MinisterOfficeType) in offices
    assert (finance, MEMBERS.headsAdministrativeUnit, finance_unit) in offices
    assert not list(offices.triples((taoiseach, MEMBERS.headsAdministrativeUnit, None)))
    assert not list(offices.triples((tanaiste, MEMBERS.headsAdministrativeUnit, None)))


def test_transformers_emit_only_registry_identities_and_unit_relationships():
    registry = sample_registry()
    units = transform_administrative_units(registry)
    offices = transform_offices(registry)
    validate_administrative_units(registry, units)
    validate_offices(registry, offices)

    unit = administrative_unit_iri("u-000001")
    office = office_iri("o-000001")
    mos_office = office_iri("o-000002")
    assert set(units) == {
        (unit, RDF.type, MEMBERS.AdministrativeUnit),
        (unit, SKOS.prefLabel, Literal("Synthetic unit", lang="en")),
        (unit, SKOS.prefLabel, Literal("Aonad samplach", lang="ga")),
        (unit, SKOS.altLabel, Literal("Synthetic unit alias", lang="en")),
    }
    assert (office, RDF.type, MEMBERS.NamedOffice) in offices
    assert (office, MEMBERS.hasRoleType, MEMBERS.MinisterOfficeType) in offices
    assert (office, MEMBERS.headsAdministrativeUnit, unit) in offices
    assert (mos_office, MEMBERS.assignedToAdministrativeUnit, unit) in offices
    assert (mos_office, MEMBERS.headsAdministrativeUnit, unit) not in offices
    assert not list(units.triples((office, None, None)))
    assert not list(offices.triples((unit, None, None)))


@pytest.mark.parametrize("mutate", [
    lambda graph: graph.remove((office_iri("o-000001"), MEMBERS.hasRoleType, None)),
    lambda graph: graph.add((office_iri("o-000001"), MEMBERS.assignedToAdministrativeUnit,
                             administrative_unit_iri("u-000001"))),
])
def test_office_graph_acceptance_detects_missing_or_rogue_assertions(mutate):
    registry = sample_registry()
    graph = transform_offices(registry)
    mutate(graph)
    with pytest.raises(ValueError, match="NamedOffice source-to-RDF correspondence failed"):
        validate_offices(registry, graph)


def test_administrative_unit_graph_rejects_unsourced_descriptions():
    registry = sample_registry()
    graph = transform_administrative_units(registry)
    graph.add((URIRef("https://data.oireachtas.ie/administrative-unit/not-registered"),
               RDF.type, MEMBERS.AdministrativeUnit))
    with pytest.raises(ValueError, match="AdministrativeUnit source-to-RDF correspondence failed: unexpected"):
        validate_administrative_units(registry, graph)


@pytest.mark.parametrize("mutation, message", [
    (lambda registry: registry["offices"][0].update(office_type="MinisterRole"), "unsupported OfficeType"),
    (lambda registry: registry["offices"][0]["unit_relationships"][0].update(
        relationship="assignedToAdministrativeUnit"), "incompatible"),
    (lambda registry: registry["offices"][0]["unit_relationships"][0].update(
        unit_key="u-999999"), "unregistered AdministrativeUnit"),
    (lambda registry: registry["offices"][0].update(key="Synthetic ministerial office"), "opaque o-NNNNNN key"),
    (lambda registry: registry["offices"][0].update(evidence=[]), "non-empty list"),
])
def test_registry_review_contract_fails_closed(mutation, message):
    registry = sample_registry()
    mutation(registry)
    with pytest.raises(ValueError, match=message):
        validate_registry_source(registry)


def test_office_type_concepts_do_not_pun_with_legacy_role_classes():
    graph = Graph().parse(ROOT / "ontology/members.owl.ttl", format="turtle")
    concepts = {
        MEMBERS.TaoiseachOfficeType, MEMBERS.TanaisteOfficeType,
        MEMBERS.MinisterOfficeType, MEMBERS.MinisterOfStateOfficeType,
        MEMBERS.CeannComhairleOfficeType, MEMBERS.CathaoirleachOfficeType,
        MEMBERS.AttorneyGeneralOfficeType,
    }
    for concept in concepts:
        assert (concept, RDF.type, MEMBERS.OfficeType) in graph
        assert (concept, SKOS.inScheme, MEMBERS.OfficeTypeTable) in graph
    assert (MEMBERS.hasRoleType, RDFS.domain, MEMBERS.NamedOffice) in graph
    assert (MEMBERS.hasRoleType, RDFS.range, MEMBERS.OfficeType) in graph
    assert (MEMBERS.MinisterOfficeType, RDF.type, MEMBERS.MinisterRole) not in graph
    assert (MEMBERS.MinisterRole, RDF.type, OWL.Class) in graph
    assert (MEMBERS.MinisterRole, RDF.type, MEMBERS.OfficeType) not in graph
    assert (MEMBERS.MinisterOfStateMembership, OWL.deprecated, Literal(True)) in graph
    assert (MEMBERS.hasMinisterOfStateRole, OWL.deprecated, Literal(True)) in graph
    assert (MEMBERS.officeNameUri, OWL.deprecated, Literal(True)) in graph
    assert (MEMBERS.GovernmentExecutive, RDFS.subClassOf, MEMBERS.MinisterOfStateMembership) not in graph
    restrictions = [item for item in graph.objects(MEMBERS.GovernmentExecutive, RDFS.subClassOf)
                    if (item, RDF.type, OWL.Restriction) in graph]
    assert not any(graph.value(item, OWL.onProperty) == MEMBERS.hasMembers for item in restrictions)


def test_versioned_office_type_policy_is_exact_and_does_not_classify_other_types():
    assert OFFICE_TYPE_POLICY_VERSION == 1
    assert OFFICE_TYPE_CABINET_QUALIFICATION == {
        "TaoiseachOfficeType": True,
        "TanaisteOfficeType": True,
        "MinisterOfficeType": True,
        "MinisterOfStateOfficeType": False,
    }
    assert "CeannComhairleOfficeType" not in OFFICE_TYPE_CABINET_QUALIFICATION


def test_registry_cli_offline_serializes_only_requested_graph(tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
    for endpoint, graph_iri in (("administrative-units", ADMINISTRATIVE_UNITS_GRAPH), ("offices", OFFICES_GRAPH)):
        output = tmp_path / f"{endpoint}.nq"
        assert main(["run", endpoint, "--registry-file", str(registry_path), "--offline",
                     "--output-nq", str(output), "--raw-dir", str(tmp_path / "raw")]) == 0
        assert output.exists()
        assert graph_iri in output.read_text(encoding="utf-8")


def test_registry_publication_is_graph_scoped_verified_and_stateful(tmp_path, monkeypatch):
    from oireachtas_etl import cli

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
    calls = []

    class Loader:
        def __init__(self, *args, **kwargs):
            pass

        def replace(self, graph_iri, payload, *, content_type):
            calls.append(("put", graph_iri, payload, content_type))

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "verify_core_graph", lambda client, graph, payload:
                        calls.append(("verify", graph, payload)))
    state_db = tmp_path / "state.sqlite"
    for endpoint, graph_iri in (("administrative-units", ADMINISTRATIVE_UNITS_GRAPH), ("offices", OFFICES_GRAPH)):
        assert main(["run", endpoint, "--registry-file", str(registry_path), "--state-db", str(state_db),
                     "--fuseki-gsp-url", "http://fuseki.test/data", "--fuseki-sparql-url", "http://fuseki.test/query"]) == 0
        puts = [call for call in calls if call[0] == "put"]
        assert puts[-1][1] == graph_iri
        assert calls[-1][0] == "verify"

    assert [call[1] for call in calls if call[0] == "put"] == [ADMINISTRATIVE_UNITS_GRAPH, OFFICES_GRAPH]
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("administrative-units")["publication_state"] == "clean"
        assert state.endpoint_publication("offices")["publication_state"] == "clean"


def test_office_publication_requires_current_units_first_and_never_constructs_loader(tmp_path, monkeypatch):
    from oireachtas_etl import cli

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
    state_db = tmp_path / "state.sqlite"
    constructed = []

    class Loader:
        def __init__(self, *args, **kwargs):
            constructed.append(True)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    with pytest.raises(ValueError, match="publish the current validated AdministrativeUnit graph"):
        main(["run", "offices", "--registry-file", str(registry_path), "--state-db", str(state_db),
              "--fuseki-gsp-url", "http://fuseki.test/data", "--fuseki-sparql-url", "http://fuseki.test/query"])
    assert not constructed


def test_online_registry_output_uses_exact_graph_payload(tmp_path, monkeypatch):
    from oireachtas_etl import cli

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
    captured = []

    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, graph_iri, payload, *, content_type): captured.append((graph_iri, payload))

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *_args: None)
    state_db = tmp_path / "state.sqlite"
    main(["run", "administrative-units", "--registry-file", str(registry_path), "--state-db", str(state_db),
          "--fuseki-gsp-url", "http://fuseki.test/data", "--fuseki-sparql-url", "http://fuseki.test/query"])
    expected = ntriples(transform_administrative_units(sample_registry()))
    assert captured == [(ADMINISTRATIVE_UNITS_GRAPH, expected)]
