from __future__ import annotations

import copy
import json

from oireachtas_etl.reference_coverage import build_reference_census, summary


MEMBER_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/Example.Member"
HOUSE_SEANAD = {
    "uri": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26",
    "houseCode": "seanad", "houseNo": "26",
}
HOUSE_DAIL = {
    "uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35",
    "houseCode": "dail", "houseNo": "35",
}
PARTY_IRI = "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/Independent"
REPRESENTATION_IRI = (
    "https://data.oireachtas.ie/ie/oireachtas/house/dail/35/constituency/Example"
)
COMMITTEE_IRI = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_example"
)


def _member(committee: dict | None = None) -> dict:
    committee = committee or {
        "uri": COMMITTEE_IRI,
        "houseCode": "dail",
        "houseNo": 33,
        "committeeCode": " C1 ",
        "committeeID": "001",
        "committeeType": ["Select", "Policy", "unmapped-value"],
        "committeeDateRange": {"start": "2020-01-01", "end": None},
        "committeeName": [{
            "dateRange": {"start": "2021-05-01", "end": None},
            "nameEn": "Example Select Committee",
            "nameGa": "Roghchoiste Samplach",
        }],
        # These relationship fields are not owner data.
        "memberDateRange": {"start": "2022-03-01", "end": None},
        "role": [{"role": "Chair"}],
    }
    membership = {
        "uri": MEMBER_IRI + "/memberships/example",
        "house": copy.deepcopy(HOUSE_DAIL),
        "parties": [{"party": {
            "uri": PARTY_IRI, "partyCode": "Independent", "showAs": "Independent"
        }}],
        "represents": [{"represent": {
            "uri": REPRESENTATION_IRI,
            "representType": "constituency",
            "representCode": "Example",
            "showAs": "Example constituency",
        }}],
        "committees": [committee],
    }
    return {"member": {"uri": MEMBER_IRI, "memberships": [{"membership": membership}]}}


def _endpoint_party(*, label: str = "Independent") -> dict:
    return {"party": {"uri": PARTY_IRI, "partyCode": "Independent", "showAs": label},
            "house": copy.deepcopy(HOUSE_DAIL)}


def _endpoint_representation() -> dict:
    return {
        "constituencyOrPanel": {
            "uri": REPRESENTATION_IRI, "representType": "constituency",
            "representCode": "Example", "showAs": "Example constituency",
        },
        "house": copy.deepcopy(HOUSE_DAIL),
    }


def test_census_is_stable_consolidates_by_exact_iri_and_tracks_provenance():
    member = _member()
    result = build_reference_census(
        member_records=[member, copy.deepcopy(member)],
        party_records=[_endpoint_party(label=" Independent ")],
        constituency_records=[_endpoint_representation()],
        member_capture_complete=True,
        party_capture_complete=True,
        constituency_capture_complete=True,
    )
    repeated = build_reference_census(
        member_records=[member, copy.deepcopy(member)],
        party_records=[_endpoint_party(label=" Independent ")],
        constituency_records=[_endpoint_representation()],
        member_capture_complete=True,
        party_capture_complete=True,
        constituency_capture_complete=True,
    )

    assert result == repeated
    report, records = result["report"], result["records"]
    assert report["totals"]["identities_by_kind"] == {
        "party": 1, "representation": 1, "committee": 1,
    }
    assert report["coverage_counts_by_kind"]["party"]["overlap/concordant"] == 1
    assert report["coverage_counts_by_kind"]["representation"]["overlap/concordant"] == 1
    assert report["coverage_counts_by_kind"]["committee"]["members-only"] == 1
    assert len(records["parties"]) == len(records["constituencies"]) == 1
    assert len(records["committees"]) == 1
    assert records["parties"][0]["party"]["showAs"] == " Independent "
    committee = records["committees"][0]
    assert committee["uri"] == COMMITTEE_IRI
    assert committee["committeeCode"] == " C1 "
    assert committee["committeeID"] == "001"
    assert committee["committeeType"] == ["Policy", "Select"]
    assert committee["committeeName"] == [{
        "nameEn": "Example Select Committee", "nameGa": "Roghchoiste Samplach",
    }]
    assert committee["uri"].startswith("https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/")
    assert records["committees"][0]["committeeDateRange"] == {
        "start": "2020-01-01T00:00:00", "end": None,
    }
    observation = next(item for item in report["observations"]
                       if item["reference_kind"] == "committee")
    assert observation["house_term_context"] == HOUSE_DAIL["uri"]
    assert observation["normalized_comparison_values"]["houseTerm"] == (
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/33"
    )
    assert observation["source_fields"]["memberDateRange"] == {
        "start": "2022-03-01", "end": None,
    }
    assert records["committees"][0]["committeeDateRange"]["start"] != "2022-03-01"
    assert summary(report)["capture_completeness"]["members"] is True


def test_material_committee_identity_conflict_is_reported_and_not_consolidated():
    first = _member()
    second = copy.deepcopy(first)
    second["member"]["memberships"][0]["membership"]["committees"][0]["committeeCode"] = "C2"
    second["member"]["memberships"][0]["membership"]["committees"][0]["committeeID"] = 2

    result = build_reference_census(
        member_records=[first, second], member_capture_complete=True,
    )
    assert result["records"]["committees"] == []
    conflict = result["report"]["conflicts"][0]
    assert conflict["canonical_iri"] == COMMITTEE_IRI
    assert conflict["coverage_class"] == "members-conflicting"
    assert {item["field"] for item in conflict["conflicts"]} >= {
        "committeeCode", "committeeID",
    }
    assert all(len(field["evidence"]) == 2 for field in conflict["conflicts"])


def test_fatal_committee_observation_keeps_independently_comparable_conflicts():
    first = _member()
    second = copy.deepcopy(first)
    committee = second["member"]["memberships"][0]["membership"]["committees"][0]
    committee["committeeCode"] = "C2"
    committee["committeeID"] = 2
    committee["houseCode"] = "seanad"  # independently invalid against the IRI

    result = build_reference_census(
        member_records=[first, second], member_capture_complete=True)
    assert result["records"]["committees"] == []
    conflict = result["report"]["conflicts"][0]
    assert {item["field"] for item in conflict["conflicts"]} >= {
        "committeeCode", "committeeID", "houseCode",
    }
    code_evidence = next(item for item in conflict["conflicts"]
                         if item["field"] == "committeeCode")["evidence"]
    assert {item["normalized_value"] for item in code_evidence} == {"C1", "C2"}


def test_uncomparable_optional_committee_field_cannot_override_valid_evidence():
    first = _member()
    second = copy.deepcopy(first)
    committee = second["member"]["memberships"][0]["membership"]["committees"][0]
    committee["committeeID"] = "not-an-integer"

    result = build_reference_census(
        member_records=[first, second], member_capture_complete=True)
    assert result["records"]["committees"] == []
    conflict = result["report"]["conflicts"][0]
    id_conflict = next(item for item in conflict["conflicts"]
                       if item["field"] == "committeeID")
    assert any(item["normalized_value"] == {"uncomparable": True}
               for item in id_conflict["evidence"])


def test_malformed_optional_committee_code_does_not_drop_a_closable_identity():
    member = _member()
    member["member"]["memberships"][0]["membership"]["committees"][0][
        "committeeCode"] = 156

    result = build_reference_census(
        member_records=[member], member_capture_complete=True)
    assert result["report"]["conflicts"] == []
    assert len(result["records"]["committees"]) == 1
    assert "committeeCode" not in result["records"]["committees"][0]
    identity = next(item for item in result["report"]["identities"]
                    if item["canonical_iri"] == COMMITTEE_IRI)
    assert identity["closable"] is True
    assert any(item["reason"] == "value must be a non-empty string"
               for item in result["report"]["malformed_observations"])


def test_missing_owner_fields_and_malformed_identity_are_not_placeholder_records():
    member = _member()
    membership = member["member"]["memberships"][0]["membership"]
    membership["parties"][0]["party"]["showAs"] = None
    membership["represents"][0]["represent"]["representCode"] = None
    membership["committees"][0]["uri"] = "https://example.test/committee/not-oireachtas"

    result = build_reference_census(
        member_records=[member], member_capture_complete=True,
    )
    assert result["records"] == {"parties": [], "constituencies": [], "committees": []}
    assert result["report"]["insufficient_evidence_identities"] == 2
    assert result["report"]["malformed_observation_count"] == 2
    assert result["report"]["insufficient_evidence"]
    malformed_paths = {item.get("path", item.get("json_pointer"))
                       for item in result["report"]["malformed_observations"]}
    assert any(path.endswith("/committees/0") for path in malformed_paths)


def test_name_history_uses_latest_unambiguous_current_name_without_order_dependence():
    member = _member()
    committee = member["member"]["memberships"][0]["membership"]["committees"][0]
    committee["committeeName"].insert(0, {
        "dateRange": {"start": "2020-01-01", "end": "2021-04-30"},
        "nameEn": "Earlier name", "nameGa": "Ainm níos luaithe",
    })
    reversed_member = copy.deepcopy(member)
    reversed_member["member"]["memberships"][0]["membership"]["committees"][0]["committeeName"].reverse()
    outputs = [build_reference_census(
        member_records=[record], member_capture_complete=True)["records"]["committees"]
        for record in (member, reversed_member)]
    assert outputs[0] == outputs[1]
    assert outputs[0][0]["committeeName"] == [{
        "nameEn": "Example Select Committee", "nameGa": "Roghchoiste Samplach",
    }]


def test_equal_latest_names_are_reported_as_ambiguous_but_not_falsely_selected():
    member = _member()
    names = member["member"]["memberships"][0]["membership"]["committees"][0]["committeeName"]
    names.append({
        "dateRange": {"start": "2021-05-01", "end": None},
        "nameEn": "Different current name", "nameGa": "Ainm eile",
    })
    result = build_reference_census(
        member_records=[member], member_capture_complete=True,
    )
    assert result["report"]["committee_name_ambiguity_count"] == 2
    assert result["records"]["committees"][0]["committeeName"] == []


def test_reference_closure_requires_owner_class_key_and_source_term_for_each_edge():
    from rdflib import Graph, URIRef

    from oireachtas_etl.reference_closure import validate_reference_closure
    from oireachtas_etl.transforms.common import MEMBERS
    from oireachtas_etl.transforms.committees import transform_committees
    from oireachtas_etl.transforms.constituencies import transform_constituencies
    from oireachtas_etl.transforms.parties import transform_parties

    member = _member()
    census = build_reference_census(
        member_records=[member], party_records=[_endpoint_party()],
        constituency_records=[_endpoint_representation()], member_capture_complete=True,
        party_capture_complete=True, constituency_capture_complete=True,
    )
    member_graph = Graph()
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.memberOfCollection, URIRef(PARTY_IRI)))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isRepresentativeFrom,
                      URIRef(REPRESENTATION_IRI)))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isCommitteeMembershipOf,
                      URIRef(COMMITTEE_IRI)))
    owners = {
        "parties": transform_parties(census["records"]["parties"]),
        "constituencies": transform_constituencies(census["records"]["constituencies"]),
        "committees": transform_committees(census["records"]["committees"]),
    }
    closure = validate_reference_closure(member_graph, owners, census["report"])
    assert closure["references"] == closure["closed"] == 3
    assert closure["unresolved_closable"] == []

    owners["committees"].remove((URIRef(COMMITTEE_IRI), MEMBERS.committeeInHouseTerm, None))
    with __import__("pytest").raises(ValueError, match="unresolved closable targets"):
        validate_reference_closure(member_graph, owners, census["report"])


def test_reference_closure_does_not_hide_conflicts_as_insufficient_evidence():
    from rdflib import Graph

    from oireachtas_etl.reference_closure import validate_reference_closure
    import pytest

    first = _member()
    second = copy.deepcopy(first)
    second["member"]["memberships"][0]["membership"]["committees"][0]["committeeID"] = 2
    census = build_reference_census(
        member_records=[first, second], member_capture_complete=True,
    )
    with pytest.raises(ValueError, match="material conflicts"):
        validate_reference_closure(Graph(), {"committees": Graph()}, census["report"])


def test_postpublication_sparql_closure_checks_owner_terms_against_source_iris():
    from rdflib import Dataset, Literal, URIRef

    from oireachtas_etl.reference_closure import reference_closure_query
    from oireachtas_etl.transforms.common import MEMBERS
    from oireachtas_etl.transforms.committees import transform_committees
    from oireachtas_etl.transforms.constituencies import transform_constituencies
    from oireachtas_etl.transforms.parties import transform_parties

    party = _endpoint_party()
    representation = _endpoint_representation()
    committee = {
        "uri": COMMITTEE_IRI, "committeeCode": "C1", "committeeID": 1,
    }
    dataset = Dataset()
    for graph_iri, graph in (
        ("https://data.oireachtas.ie/graph/parties", transform_parties([party])),
        ("https://data.oireachtas.ie/graph/constituencies",
         transform_constituencies([representation])),
        ("https://data.oireachtas.ie/graph/committees",
         transform_committees([committee])),
    ):
        target = dataset.graph(URIRef(graph_iri))
        for triple in graph:
            target.add(triple)
    member = dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Example"))
    subject = URIRef(MEMBER_IRI)
    member.add((subject, MEMBERS.memberOfCollection, URIRef(PARTY_IRI)))
    member.add((subject, MEMBERS.isRepresentativeFrom, URIRef(REPRESENTATION_IRI)))
    member.add((subject, MEMBERS.isCommitteeMembershipOf, URIRef(COMMITTEE_IRI)))
    kinds = ("party-collection", "party-membership", "representation-dail",
             "representation-seanad", "committee")
    assert all(list(dataset.query(reference_closure_query(kind))) == [] for kind in kinds)

    parties_graph = dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
    parties_graph.remove((URIRef(PARTY_IRI), MEMBERS.partyCode, None))
    parties_graph.add((URIRef(PARTY_IRI), MEMBERS.partyCode, Literal("Wrong")))
    failures = list(dataset.query(reference_closure_query("party-collection")))
    assert any(str(row.target) == PARTY_IRI for row in failures)
    parties_graph.remove((URIRef(PARTY_IRI), MEMBERS.partyCode, None))
    parties_graph.add((URIRef(PARTY_IRI), MEMBERS.partyCode, Literal("Independent")))
    parties_graph.remove((URIRef(PARTY_IRI), MEMBERS.activeDuringTerm, None))
    parties_graph.add((URIRef(PARTY_IRI), MEMBERS.activeDuringTerm,
                       URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")))
    failures = [row for kind in kinds
                for row in dataset.query(reference_closure_query(kind))]
    assert any(str(row.target) == PARTY_IRI for row in failures)

    parties_graph.remove((URIRef(PARTY_IRI), MEMBERS.activeDuringTerm, None))
    parties_graph.add((URIRef(PARTY_IRI), MEMBERS.activeDuringTerm,
                       URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/35")))
    committees_graph = dataset.graph(URIRef("https://data.oireachtas.ie/graph/committees"))
    committees_graph.remove((URIRef(COMMITTEE_IRI), MEMBERS.committeeInHouseTerm, None))
    committees_graph.add((URIRef(COMMITTEE_IRI), MEMBERS.committeeInHouseTerm,
                          URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/32")))
    failures = list(dataset.query(reference_closure_query("committee")))
    assert any(str(row.target) == COMMITTEE_IRI for row in failures)


def test_postpublication_party_closure_accepts_percent_encoded_unicode_slug():
    from rdflib import Dataset, URIRef

    from oireachtas_etl.reference_closure import reference_closure_query
    from oireachtas_etl.transforms.common import MEMBERS
    from oireachtas_etl.transforms.parties import transform_parties
    from oireachtas_etl.validation.parties import validate_parties

    party = _endpoint_party()
    party["party"]["uri"] = (
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/Sinn_F%C3%A9in")
    party["party"]["partyCode"] = "Sinn_Féin"
    party["party"]["showAs"] = "Sinn Féin"
    graph = transform_parties([party])
    validate_parties([party], graph)

    dataset = Dataset()
    owner = dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
    for triple in graph:
        owner.add(triple)
    member = dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Example"))
    member.add((URIRef(MEMBER_IRI), MEMBERS.memberOfCollection,
                URIRef(party["party"]["uri"])))
    assert list(dataset.query(reference_closure_query("party-collection"))) == []
