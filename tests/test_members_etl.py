import json
import fcntl
import multiprocessing
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF, SKOS

from oireachtas_etl.api import ApiClient, ApiPage
from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.members import member_graph_iri, source_hash, transform_member_with_report
from oireachtas_etl.validation import validate_member
from oireachtas_etl.competency import MEMBERS_COMPETENCY_EXPECTED, render_member_competency_query, verify_member_competency, verify_members_competency

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = json.loads((ROOT / "data/api_examples/member.json").read_text())


def copied():
    return json.loads(json.dumps(WRAPPER))


def test_member_graph_is_deterministic_owned_and_valid():
    graph, report = transform_member_with_report(WRAPPER)
    golden = Graph().parse(ROOT / "tests/expected/members.ttl")
    assert set(graph) == set(golden)
    assert member_graph_iri(WRAPPER["member"]).endswith("Timmy-Dooley.S.2002-09-12")
    assert nquads(graph, member_graph_iri(WRAPPER["member"])) == nquads(transform_member_with_report(WRAPPER)[0], member_graph_iri(WRAPPER["member"]))
    assert validate_member(WRAPPER, graph) == report
    committee = URIRef(WRAPPER["member"]["memberships"][0]["membership"]["committees"][0]["uri"])
    assert not list(graph.triples((committee, None, None)))
    assert any(item["path"].endswith("committeeName[].nameEn") for item in report)


def test_member_golden_pins_full_sha_generated_iri_hierarchy():
    graph, _ = transform_member_with_report(WRAPPER)
    root = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12/house/dail/34"
    assert URIRef(root + "#minister-of-state-membership-681ed4c802b1acbb81a375404a6e076cd53901371313c501a8f7e77c9422b1a3#role") in set(graph.subjects())
    assert URIRef(root + "#party-membership-a0db44ca23cb7ed5129ed071ca4d545fee362c5137db08325cfebf43b296d273#date-range") in set(graph.subjects())


def test_party_membership_requires_date_even_without_explicit_collection_membership_type():
    from pyshacl import validate as validate_shacl

    graph, _ = transform_member_with_report(WRAPPER)
    party_membership = next(graph.subjects(RDF.type, MEMBERS.PartyMembership))
    graph.remove((party_membership, RDF.type, MEMBERS.ParliamentaryCollectionMembership))
    graph.remove((party_membership, MEMBERS.hasMembershipDateRange, None))

    conforms, _, report = validate_shacl(
        graph,
        shacl_graph=(ROOT / "src/oireachtas_etl/validation/resources/members.ttl").read_text(),
        shacl_graph_format="turtle",
        inference="none",
        abort_on_first=False,
    )
    assert not conforms
    assert "hasMembershipDateRange" in str(report)


def test_independent_member_record_uses_contextual_general_collection_membership_and_fails_closed():
    changed = copied()
    wrapped_membership = next(
        value for value in changed["member"]["memberships"]
        if value["membership"]["house"]["houseCode"] == "dail"
        and value["membership"]["house"]["houseNo"] == "34"
    )
    membership = wrapped_membership["membership"]
    party = membership["parties"][0]["party"]
    party["uri"] = "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Independent"
    party["partyCode"] = "Independent"
    party["showAs"] = "Independent"

    graph, _ = transform_member_with_report(changed)
    collection = URIRef(party["uri"])
    member = URIRef(changed["member"]["uri"])
    oireachtas_membership = URIRef(membership["uri"])
    collection_memberships = list(graph.subjects(MEMBERS.memberOfCollection, collection))
    assert len(collection_memberships) == 1
    collection_membership = collection_memberships[0]
    assert (collection_membership, RDF.type, MEMBERS.ParliamentaryCollectionMembership) in graph
    assert (collection_membership, RDF.type, MEMBERS.PartyMembership) not in graph
    assert (collection_membership, MEMBERS.memberOfCollection, collection) in graph
    assert (collection_membership, MEMBERS.inOireachtasMembership, oireachtas_membership) in graph
    assert (member, MEMBERS.hasMembersMembership, collection_membership) in graph
    assert not list(graph.triples((collection_membership, MEMBERS.isPartyMembershipOf, None)))
    validate_member(changed, graph)

    invalid_graphs = []
    missing_context = Graph(); [missing_context.add(triple) for triple in graph]
    missing_context.remove((collection_membership, MEMBERS.inOireachtasMembership, oireachtas_membership))
    invalid_graphs.append((missing_context, "missing"))
    missing_collection = Graph(); [missing_collection.add(triple) for triple in graph]
    missing_collection.remove((collection_membership, MEMBERS.memberOfCollection, collection))
    invalid_graphs.append((missing_collection, "missing"))
    wrong_party_type = Graph(); [wrong_party_type.add(triple) for triple in graph]
    wrong_party_type.add((collection_membership, RDF.type, MEMBERS.PartyMembership))
    invalid_graphs.append((wrong_party_type, "unexpected"))
    party_specific_link = Graph(); [party_specific_link.add(triple) for triple in graph]
    party_specific_link.add((collection_membership, MEMBERS.isPartyMembershipOf, collection))
    invalid_graphs.append((party_specific_link, "unexpected"))
    for invalid, failure in invalid_graphs:
        with pytest.raises(ValueError, match=f"source-to-RDF correspondence failed: {failure}"):
            validate_member(changed, invalid)


def test_member_source_validator_rejects_independent_code_with_party_source_iri():
    from oireachtas_etl.validation.members import validate_member_source
    changed = copied()
    party = changed["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["partyCode"] = "Independent"
    with pytest.raises(ValueError, match="party.uri must be the term-scoped Party source IRI"):
        validate_member_source(changed)


def test_member_synthetic_roles_and_office_uri_are_member_terms():
    changed = copied()
    committee = changed["member"]["memberships"][0]["membership"]["committees"][0]
    committee["role"] = ["Chair", "Deputy Chair"]
    office = changed["member"]["memberships"][3]["membership"]["offices"][0]["office"]
    office["officeName"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/office/example"
    graph, _ = transform_member_with_report(changed)
    from oireachtas_etl.transforms.common import MEMBERS
    assert len(list(graph.subjects(RDF.type, MEMBERS.Chair))) == 1
    assert len(list(graph.subjects(RDF.type, MEMBERS.DeputyChair))) == 1
    assert (None, MEMBERS.officeNameUri, URIRef(office["officeName"]["uri"])) in graph
    validate_member(changed, graph)


def _garret_ahearn_role_case() -> dict:
    """Minimal Member record retaining Garret's captured committee role form.

    Source: Members API skip=0, result 4, pointer
    /results/4/member/memberships/0/membership/committees/1/role.
    """
    member_code = "Garret-Ahearn.S.2020-03-30"
    member_uri = f"https://data.oireachtas.ie/ie/oireachtas/member/id/{member_code}"
    membership_uri = f"{member_uri}/house/seanad/26"
    committee_uri = (
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
        "joint_committee_on_enterprise_trade_and_employment")
    return {"member": {
        "memberCode": member_code,
        "uri": member_uri,
        "image": False,
        "memberships": [{"membership": {
            "uri": membership_uri,
            "house": {"houseCode": "seanad", "houseNo": "26",
                      "uri": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26"},
            "dateRange": {"start": "2020-03-30", "end": "2025-01-29"},
            "committees": [
                {"uri": "https://data.oireachtas.ie/ie/oireachtas/committee/seanad/26/"
                         "committee_of_selection",
                 "memberDateRange": {"start": "2020-09-25 00:00:00+00:00",
                                     "end": "2024-11-08 00:00:00+00:00"},
                 "role": []},
                {"committeeCode": "BUJ",
                 "memberDateRange": {"start": "2020-09-25 00:00:00+00:00",
                                     "end": "2024-11-08 00:00:00+00:00"},
                 "uri": committee_uri,
                 "role": {"title": "Leas-Chathaoirleach",
                          "dateRange": {"start": "2023-05-03 00:00:00+00:00",
                                        "end": None}}},
            ],
            "parties": [], "represents": [], "offices": [],
        }}],
    }}


def test_garret_ahearn_committee_role_object_maps_without_changing_existing_rdf_semantics():
    from oireachtas_etl.validation.members import validate_member_source

    changed = _garret_ahearn_role_case()
    source_before = json.dumps(changed, ensure_ascii=False, sort_keys=True)
    graph, report = transform_member_with_report(changed)
    assert json.dumps(changed, ensure_ascii=False, sort_keys=True) == source_before
    assert validate_member_source(changed) == report
    assert validate_member(changed, graph) == report

    member = URIRef(changed["member"]["uri"])
    committee_memberships = set(graph.subjects(RDF.type, MEMBERS.CommitteeMembership))
    assert len(committee_memberships) == 2
    assert all((member, MEMBERS.hasMembersMembership, cm) in graph
               for cm in committee_memberships)
    deputy_roles = set(graph.subjects(RDF.type, MEMBERS.DeputyChair))
    assert len(deputy_roles) == 1
    assert (next(cm for cm in committee_memberships
                 if (cm, MEMBERS.isCommitteeMembershipOf,
                     URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
                            "joint_committee_on_enterprise_trade_and_employment")) in graph),
            MEMBERS.hasCommitteeRole, next(iter(deputy_roles))) in graph
    assert not list(graph.subjects(RDF.type, MEMBERS.Chair))

    # The role object's source interval is validated and reported, not silently
    # conflated with the committee membership interval or emitted as new RDF.
    role_date_omissions = [item for item in report
                           if item["path"].endswith("role.dateRange.start")]
    assert len(role_date_omissions) == 1
    assert role_date_omissions[0]["category"] == "future_work"
    assert "no property in the current Member mapping" in role_date_omissions[0]["reason"]

    # Equivalent mapped array input yields exactly the same RDF as the object
    # title, keeping existing deterministic committee-role semantics intact.
    array_form = json.loads(json.dumps(changed))
    array_form["member"]["memberships"][0]["membership"]["committees"][1]["role"] = ["Deputy Chair"]
    array_graph, _ = transform_member_with_report(array_form)
    assert set(array_graph) == set(graph)


@pytest.mark.parametrize(("title", "expected_role"), [
    ("Cathaoirleach", MEMBERS.Chair),
    ("Leas-Chathaoirleach", MEMBERS.DeputyChair),
])
def test_committee_role_object_maps_each_observed_irish_title(title, expected_role):
    from oireachtas_etl.validation.members import validate_member_source

    changed = _garret_ahearn_role_case()
    committee = changed["member"]["memberships"][0]["membership"]["committees"][1]
    committee["role"]["title"] = title
    graph, _ = transform_member_with_report(changed)
    validate_member_source(changed)
    validate_member(changed, graph)
    assert len(list(graph.subjects(RDF.type, expected_role))) == 1


def test_existing_empty_committee_role_array_remains_no_special_role():
    graph, _ = transform_member_with_report(WRAPPER)
    assert not list(graph.subjects(RDF.type, MEMBERS.Chair))
    assert not list(graph.subjects(RDF.type, MEMBERS.DeputyChair))


@pytest.mark.parametrize(("role", "message"), [
    ("Chair", "committee role must be an array or a supported role object"),
    ({"title": "Unknown role", "dateRange": {"start": "2024-01-01", "end": None}},
     "unsupported committee role title"),
    ({"title": "Leas-Chathaoirleach", "dateRange": {"start": "2025-01-01", "end": "2024-01-01"}},
     "reverse committee role date range"),
    ({"title": "Leas-Chathaoirleach", "dateRange": {"start": "2024-01-01", "end": None},
      "unexpected": True}, "only title and dateRange"),
])
def test_unsafe_committee_role_shapes_fail_closed(role, message):
    from oireachtas_etl.validation.members import validate_member_source

    changed = _garret_ahearn_role_case()
    changed["member"]["memberships"][0]["membership"]["committees"][1]["role"] = role
    with pytest.raises(ValueError, match=message):
        validate_member_source(changed)
    with pytest.raises(ValueError, match=message):
        transform_member_with_report(changed)


@pytest.mark.parametrize(("committee_value", "message"), [
    ("not-an-array", "membership.committees must be an array"),
    (["not-an-object"], "committee record must be an object"),
])
def test_unsafe_committee_containers_remain_fail_closed(committee_value, message):
    from oireachtas_etl.validation.members import validate_member_source

    changed = _garret_ahearn_role_case()
    changed["member"]["memberships"][0]["membership"]["committees"] = committee_value
    with pytest.raises(ValueError, match=message):
        validate_member_source(changed)
    with pytest.raises(ValueError, match=message):
        transform_member_with_report(changed)


def test_member_hash_known_nested_arrays_are_unordered_but_unknown_arrays_are_not():
    changed = copied()
    membership = changed["member"]["memberships"][0]["membership"]
    membership["committees"].reverse()
    membership["parties"].reverse()
    assert source_hash(WRAPPER["member"]) == source_hash(changed["member"])
    changed = copied(); changed["member"]["unknownArray"] = ["a", "b"]
    reordered = copied(); reordered["member"]["unknownArray"] = ["b", "a"]
    assert source_hash(changed["member"]) != source_hash(reordered["member"])


def test_canonical_hash_ignores_object_keys_and_source_array_order():
    changed = copied()
    changed["member"]["memberships"].reverse()
    changed["member"]["memberships"][0]["membership"]["committees"].reverse()
    assert source_hash(WRAPPER["member"]) == source_hash(changed["member"])


def test_member_identity_and_temporal_fail_closed():
    changed = copied(); changed["member"]["memberCode"] = "different"
    with pytest.raises(ValueError, match="memberCode"):
        transform_member_with_report(changed)
    changed = copied(); changed["member"]["memberships"][0]["membership"]["dateRange"] = {"start": "2025-01-01", "end": "2024-01-01"}
    with pytest.raises(ValueError, match="reverse membership date range"):
        transform_member_with_report(changed)


def test_malformed_nested_office_is_quarantined_while_valid_sibling_and_member_continue():
    from oireachtas_etl.validation.members import validate_member_source

    changed = copied()
    offices = changed["member"]["memberships"][3]["membership"]["offices"]
    assert len(offices) == 2
    invalid = offices[0]["office"]
    invalid["dateRange"]["end"] = "2025-01-01"
    source_before = json.dumps(changed, sort_keys=True)
    graph, transform_report = transform_member_with_report(changed)
    source_report = validate_member_source(changed)

    assert source_before == json.dumps(changed, sort_keys=True)
    assert len(list(graph.subjects(RDF.type, MEMBERS.MinisterOfStateMembership))) == 1
    valid_label = offices[1]["office"]["officeName"]["showAs"]
    valid_office = next(graph.subjects(RDF.type, MEMBERS.MinisterOfStateMembership))
    role = next(graph.objects(valid_office, MEMBERS.hasMinisterOfStateRole), None)
    # The office-membership has a generated role carrying the valid source label.
    assert role is not None
    assert str(next(graph.objects(role, SKOS.prefLabel))) == valid_label
    malformed = [item for item in transform_report if item["category"] == "source_quarantine"]
    assert len(malformed) == 1
    assert malformed[0]["path"] == "member.memberships[3].membership.offices[0]"
    assert malformed[0]["reason"] == "office.dateRange has reverse dates"
    assert malformed[0]["status"] == "review_required"
    assert source_report == transform_report
    assert validate_member(changed, graph) == transform_report


def test_unsafe_member_level_source_errors_remain_fail_closed():
    from oireachtas_etl.validation.members import validate_member_source

    changed = copied()
    changed["member"]["memberships"][0]["membership"]["dateRange"] = {
        "start": "2025-01-01", "end": "2024-01-01"}
    with pytest.raises(ValueError, match="reverse membership date range"):
        validate_member_source(changed)


@pytest.mark.parametrize(("date_range", "reason"), [
    ({"start": "2016-03-10", "end": "2016-03-09"}, "party.dateRange has reverse dates"),
    ({"start": "not-a-date", "end": None}, "party.dateRange contains invalid date evidence"),
    ({"end": "2016-03-09"}, "party.dateRange.start is required"),
    (None, "party.dateRange must be an object with a required start"),
])
def test_invalid_nested_party_range_is_quarantined_without_losing_valid_member_data(date_range, reason):
    from oireachtas_etl.validation.members import validate_member_source

    changed = copied()
    party = changed["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["dateRange"] = date_range
    source_before = json.dumps(changed, ensure_ascii=False, sort_keys=True)

    graph, report = transform_member_with_report(changed)
    assert json.dumps(changed, ensure_ascii=False, sort_keys=True) == source_before
    assert validate_member_source(changed) == report
    assert validate_member(changed, graph) == report

    malformed = [item for item in report if item.get("category") == "source_quarantine"
                 and ".parties[" in item.get("path", "")]
    assert len(malformed) == 1
    item = malformed[0]
    assert item["path"] == "member.memberships[0].membership.parties[0].party.dateRange"
    assert item["json_pointer"] == "/member/memberships/0/membership/parties/0/party/dateRange"
    assert item["party_uri"] == party["uri"]
    assert item["party_code"] == party["partyCode"]
    assert item["date_range"] == date_range
    assert item["raw_observation"] == changed["member"]["memberships"][0]["membership"]["parties"][0]
    assert item["reason"].startswith(reason)
    assert item["status"] == "review_required"

    # The malformed observation creates no party membership, while valid
    # party and Member content in other HouseTerms is retained.
    assert len(list(graph.subjects(RDF.type, MEMBERS.ParliamentaryCollectionMembership))) == 5
    assert len(list(graph.subjects(RDF.type, MEMBERS.OireachtasMembership))) == 6
    assert (URIRef(changed["member"]["uri"]), RDF.type, OIR.Member) in graph


@pytest.mark.parametrize(("parties", "message"), [
    ("not-an-array", "membership.parties must be an array"),
    (["not-a-party-wrapper"], "party wrapper must contain a party object"),
])
def test_unsafe_party_containers_remain_fail_closed(parties, message):
    from oireachtas_etl.validation.members import validate_member_source

    changed = copied()
    changed["member"]["memberships"][0]["membership"]["parties"] = parties
    with pytest.raises(ValueError, match=message):
        validate_member_source(changed)
    with pytest.raises(ValueError, match=message):
        transform_member_with_report(changed)


def test_malformed_party_identity_remains_fail_closed():
    from oireachtas_etl.validation.members import validate_member_source

    changed = copied()
    party = changed["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["uri"] = "https://data.oireachtas.ie/ie/oireachtas/party/dail/25/Other-Party"
    with pytest.raises(ValueError, match="party.uri must be the term-scoped Party source IRI"):
        validate_member_source(changed)
    with pytest.raises(ValueError, match="party.uri must be the term-scoped Party source IRI"):
        transform_member_with_report(changed)


def test_offline_members_cli_surfaces_quarantined_party_and_keeps_valid_siblings(tmp_path, capsys):
    from oireachtas_etl.cli import run_members

    changed = copied()
    bad_party = changed["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    raw_start, raw_end = "2016-03-10", "2016-03-09"
    bad_party["dateRange"] = {"start": raw_start, "end": raw_end}
    fixture = tmp_path / "malformed-party-member.json"
    fixture.write_text(json.dumps([changed], ensure_ascii=False), encoding="utf-8")
    fixture_before = fixture.read_bytes()
    output = tmp_path / "members.nq"
    args = Namespace(fixture=str(fixture), offline=True, raw_dir=str(tmp_path / "raw"),
                     output_nq=str(output), output_ttl=None, fuseki_gsp_url=None,
                     fuseki_sparql_url=None, state_file=None)

    assert run_members(args) == 0
    first_report = json.loads(capsys.readouterr().out)
    first_payload = output.read_bytes()
    assert fixture.read_bytes() == fixture_before
    assert len(first_report["malformed_parties"]) == 1
    malformed = first_report["malformed_parties"][0]
    assert malformed["reason"] == "party.dateRange has reverse dates"
    assert malformed["date_range"] == {"start": raw_start, "end": raw_end}
    assert malformed["preservation_status"] == "not_applicable_offline"
    bad_ranges = []
    generated_graph, _ = transform_member_with_report(changed)
    for party_membership in generated_graph.subjects(
            RDF.type, MEMBERS.ParliamentaryCollectionMembership):
        periods = generated_graph.objects(party_membership, MEMBERS.hasMembershipDateRange)
        values = {(str(start), str(end)) for period in periods
                  for start in generated_graph.objects(period, MEMBERS.StartDate)
                  for end in generated_graph.objects(period, MEMBERS.EndDate)}
        if (raw_start, raw_end) in values:
            bad_ranges.append(party_membership)
    assert not bad_ranges

    # Repeated offline runs must produce byte-identical RDF and the same
    # source-quarantine report independent of generated run metadata.
    assert run_members(args) == 0
    second_report = json.loads(capsys.readouterr().out)
    assert output.read_bytes() == first_payload
    assert second_report["malformed_parties"] == first_report["malformed_parties"]


def test_online_member_change_composes_previously_accepted_party_evidence(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.transforms.members import prior_party_membership_evidence
    from oireachtas_etl.state import CoreStateStore

    original = copied()
    first_fixture = tmp_path / "accepted-member.json"
    first_fixture.write_text(json.dumps([original], ensure_ascii=False), encoding="utf-8")
    first_calls = []
    _mock_online(monkeypatch, first_calls)
    assert cli.run_members(_online_args(tmp_path, first_fixture)) == 0
    capsys.readouterr()
    assert len(first_calls) == 1

    identity = original["member"]["uri"]
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        accepted = state.get_resource("members", identity)
        old_payload = accepted["published_payload"]
    previous_graph = Graph()
    previous_graph.parse(data=old_payload, format="nt")
    affected_membership = original["member"]["memberships"][0]["membership"]["uri"]
    prior_party_graph = prior_party_membership_evidence(
        previous_graph, URIRef(identity), {affected_membership})
    assert prior_party_graph

    current = copied()
    current["member"]["fullName"] = "Current Member Name"
    party = current["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["dateRange"] = {"start": "2016-03-10", "end": "2016-03-09"}
    second_fixture = tmp_path / "malformed-current-member.json"
    second_fixture.write_text(json.dumps([current], ensure_ascii=False), encoding="utf-8")
    second_args = _online_args(tmp_path, second_fixture)
    second_calls = []
    _mock_online(monkeypatch, second_calls)
    assert cli.run_members(second_args) == 0
    second_report = _report(capsys)
    assert second_report["published"] == 1
    assert len(second_calls) == 1
    quarantine = second_report["malformed_parties"]
    assert len(quarantine) == 1
    assert quarantine[0]["preservation_status"] == "previous_accepted_party_evidence_composed"

    published_graph = Graph()
    published_graph.parse(data=second_calls[0][1], format="nt")
    assert set(prior_party_graph).issubset(set(published_graph))
    assert "Current Member Name" in second_calls[0][1]
    assert validate_member(current, published_graph, preserved_party_graph=prior_party_graph)

    # If the remote graph has drifted, an unchanged-source repair replays the
    # exact last accepted Member graph rather than rebuilding without its
    # retained party evidence.
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        published_payload = state.get_resource("members", identity)["published_payload"]
    third_calls = []
    _mock_online(monkeypatch, third_calls)
    verify_calls = []

    def mismatch_then_repair(*args):
        verify_calls.append(args)
        if len(verify_calls) == 1:
            raise ValueError("remote graph mismatch")

    monkeypatch.setattr(cli, "verify_core_graph", mismatch_then_repair)
    assert cli.run_members(second_args) == 0
    third_report = _report(capsys)
    assert third_report["published"] == 1 and third_report["skipped"] == 0
    assert len(third_calls) == 1 and len(verify_calls) == 2
    assert third_report["malformed_parties"][0]["preservation_status"] == "unchanged_published_graph_replayed"
    assert third_calls[0][1] == published_payload
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        assert state.get_resource("members", identity)["published_payload"] == published_payload

    # A subsequent unchanged run is a clean skip and leaves the accepted
    # composite payload unchanged.
    fourth_calls = []
    _mock_online(monkeypatch, fourth_calls)
    assert cli.run_members(second_args) == 0
    fourth_report = _report(capsys)
    assert fourth_report["published"] == 0 and fourth_report["skipped"] == 1
    assert fourth_calls == []
    assert fourth_report["malformed_parties"][0]["preservation_status"] == "unchanged_published_graph_retained"
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        assert state.get_resource("members", identity)["published_payload"] == published_payload


def test_online_member_change_does_not_replace_prior_graph_without_retrievable_payload(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.state import CoreStateStore

    original = copied()
    accepted_fixture = tmp_path / "accepted-member.json"
    accepted_fixture.write_text(json.dumps([original], ensure_ascii=False), encoding="utf-8")
    first_calls = []
    _mock_online(monkeypatch, first_calls)
    assert cli.run_members(_online_args(tmp_path, accepted_fixture)) == 0
    capsys.readouterr()

    identity = original["member"]["uri"]
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        state.connection.execute(
            "UPDATE resource_state SET published_payload=NULL WHERE endpoint='members' AND resource_iri=?",
            (identity,))

    current = copied()
    current["member"]["fullName"] = "Must Not Replace Prior Graph"
    party = current["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["dateRange"] = {"start": "2016-03-10", "end": "2016-03-09"}
    fixture = tmp_path / "malformed-current-member.json"
    fixture.write_text(json.dumps([current], ensure_ascii=False), encoding="utf-8")
    calls = []
    _mock_online(monkeypatch, calls)
    assert cli.run_members(_online_args(tmp_path, fixture)) == 0
    report = _report(capsys)
    assert report["published"] == 0 and report["skipped"] == 1
    assert report["malformed_parties"][0]["preservation_status"] == "blocked_previous_graph_retained"
    assert "previous accepted Member payload is unavailable" in report["malformed_parties"][0]["preservation_reason"]
    assert calls == []


def test_unchanged_malformed_party_source_blocks_repair_when_accepted_payload_is_missing(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.state import CoreStateStore

    current = copied()
    party = current["member"]["memberships"][0]["membership"]["parties"][0]["party"]
    party["dateRange"] = {"start": "2016-03-10", "end": "2016-03-09"}
    fixture = tmp_path / "malformed-member.json"
    fixture.write_text(json.dumps([current], ensure_ascii=False), encoding="utf-8")
    initial_calls = []
    _mock_online(monkeypatch, initial_calls)
    assert cli.run_members(_online_args(tmp_path, fixture)) == 0
    initial_report = _report(capsys)
    assert initial_report["published"] == 1
    assert initial_report["malformed_parties"][0]["preservation_status"] == "no_previous_accepted_member_graph"

    identity = current["member"]["uri"]
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        state.connection.execute(
            "UPDATE resource_state SET published_payload=NULL WHERE endpoint='members' AND resource_iri=?",
            (identity,))

    repair_calls = []
    _mock_online(monkeypatch, repair_calls)
    assert cli.run_members(_online_args(tmp_path, fixture)) == 0
    report = _report(capsys)
    assert report["published"] == 0 and report["skipped"] == 1
    assert report["malformed_parties"][0]["preservation_status"] == "blocked_previous_graph_retained"
    assert "previous accepted Member payload is unavailable" in report["malformed_parties"][0]["preservation_reason"]
    assert repair_calls == []


@pytest.mark.parametrize("uri", [
    "http://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12",
    "https://evil.example/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12",
    "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12?x=1",
    "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12#x",
])
def test_member_source_identity_rejects_hostile_origins_and_suffixes(uri):
    changed = copied(); changed["member"]["uri"] = uri
    with pytest.raises(ValueError): transform_member_with_report(changed)


def test_member_graph_percent_encodes_member_code():
    changed = copied(); code = "A B/é"
    changed["member"]["memberCode"] = code
    changed["member"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/A%20B%2F%C3%A9"
    assert member_graph_iri(changed["member"]).endswith("A%20B%2F%C3%A9")


def test_exact_correspondence_rejects_ownership_or_missing_triples():
    graph, _ = transform_member_with_report(WRAPPER)
    graph.remove((URIRef(WRAPPER["member"]["uri"]), RDF.type, OIR.Member))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: missing"):
        validate_member(WRAPPER, graph)
    graph, _ = transform_member_with_report(WRAPPER)
    committee = URIRef(WRAPPER["member"]["memberships"][0]["membership"]["committees"][0]["uri"])
    graph.add((committee, RDF.type, OIR.Committee))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_member(WRAPPER, graph)


def test_members_cli_offline_never_marks_publication_state(tmp_path):
    from oireachtas_etl.cli import run_members
    state = tmp_path / "state.json"
    args = Namespace(fixture=str(ROOT / "data/api_examples/member.json"), offline=True, raw_dir=str(tmp_path / "raw"),
                     output_nq=str(tmp_path / "members.nq"), fuseki_gsp_url=None, fuseki_sparql_url=None, state_file=str(state))
    assert run_members(args) == 0
    assert not state.exists()
    assert (tmp_path / "members.nq").exists()


def test_members_cli_surfaces_malformed_office_and_serializes_valid_member_content(tmp_path, capsys):
    from oireachtas_etl.cli import run_members

    changed = copied()
    offices = changed["member"]["memberships"][3]["membership"]["offices"]
    invalid_label = offices[0]["office"]["officeName"]["showAs"]
    valid_label = offices[1]["office"]["officeName"]["showAs"]
    offices[0]["office"]["dateRange"]["end"] = "2025-01-01"
    fixture = tmp_path / "malformed-office-member.json"
    fixture.write_text(json.dumps([changed]), encoding="utf-8")
    output = tmp_path / "members.nq"
    args = Namespace(fixture=str(fixture), offline=True, raw_dir=str(tmp_path / "raw"),
                     output_nq=str(output), output_ttl=None, fuseki_gsp_url=None,
                     fuseki_sparql_url=None, state_file=None)

    assert run_members(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["malformed_offices"]) == 1
    assert report["malformed_offices"][0]["reason"] == "office.dateRange has reverse dates"
    assert report["malformed_offices"][0]["status"] == "review_required"
    serialized = output.read_text(encoding="utf-8")
    assert valid_label in serialized
    assert invalid_label not in serialized


def test_online_member_publication_continues_with_valid_sibling_office(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    changed = copied()
    offices = changed["member"]["memberships"][3]["membership"]["offices"]
    invalid_label = offices[0]["office"]["officeName"]["showAs"]
    valid_label = offices[1]["office"]["officeName"]["showAs"]
    offices[0]["office"]["dateRange"]["end"] = "2025-01-01"
    fixture = tmp_path / "malformed-office-member.json"
    fixture.write_text(json.dumps([changed]), encoding="utf-8")
    calls = []
    _mock_online(monkeypatch, calls)
    args = _online_args(tmp_path, fixture)

    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert report["published"] == 1
    assert len(report["malformed_offices"]) == 1
    assert len(calls) == 1
    published_payload = calls[0][1]
    assert valid_label in published_payload
    assert invalid_label not in published_payload


def test_members_scan_deduplicates_identical_and_rejects_conflicts():
    from oireachtas_etl.cli import _deduplicate_members
    assert len(_deduplicate_members([WRAPPER, copied()], None)) == 1
    changed = copied(); changed["member"]["fullName"] = "Different"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        _deduplicate_members([WRAPPER, changed], None)
    with pytest.raises(ValueError, match="advertised"):
        _deduplicate_members([WRAPPER], 2)


def test_failed_member_publication_never_writes_published_state(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    args = Namespace(fixture=str(ROOT / "data/api_examples/member.json"), offline=False, raw_dir=str(tmp_path / "raw"),
                     output_nq=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query", state_db=str(tmp_path / "state.sqlite"),
                     reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"))
    with pytest.raises(RuntimeError, match="PUT failed"):
        cli.run_members(args)
    from oireachtas_etl.state import CoreStateStore
    with CoreStateStore(tmp_path / "state.sqlite") as state:
        entry = state.get_resource("members", WRAPPER["member"]["uri"])
        assert entry["publication_state"] == "dirty"
        assert entry["published_source_hash"] is None


def test_member_competency_resources_execute_against_fixture_named_graph():
    dataset = Dataset()
    graph = dataset.graph(URIRef(member_graph_iri(WRAPPER["member"])))
    for triple in transform_member_with_report(WRAPPER)[0]:
        graph.add(triple)
    for filename, expected in MEMBERS_COMPETENCY_EXPECTED.items():
        actual = [{str(name): str(value) for name, value in row.asdict().items()}
                  for row in dataset.query(render_member_competency_query(filename))]
        assert actual == expected

    class DatasetClient:
        def query(self, sparql):
            return [{str(name): {"value": str(value)} for name, value in row.asdict().items()}
                    for row in dataset.query(sparql)]
    verify_member_competency(DatasetClient(), str(graph.identifier), WRAPPER["member"]["uri"], len(graph))
    verify_members_competency(DatasetClient())


def _online_args(tmp_path, fixture=ROOT / "data/api_examples/member.json"):
    return Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), output_nq=None,
                     output_ttl=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query",
                     state_db=str(tmp_path / "state.sqlite"),
                     reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"))


def _member_state(tmp_path, identity=WRAPPER["member"]["uri"]):
    from oireachtas_etl.state import CoreStateStore
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        return store.get_resource("members", identity)


def _mock_online(monkeypatch, calls, *, competency=None):
    from oireachtas_etl import cli
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): calls.append(args)
    class Client:
        def __init__(self, *args, **kwargs): pass
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_member_competency", competency or (lambda *args: None))
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)


def _report(capsys):
    return json.loads(capsys.readouterr().out)


def _members_page(records, count, *, include_count=True):
    envelope = {"results": records, "head": {"counts": {}}}
    if include_count:
        envelope["head"]["counts"]["memberCount"] = count
    return envelope


def _run_mocked_live_pages(tmp_path, monkeypatch, pages, *, limit, construction_sink=None):
    """Run the live path while retaining ApiClient.harvest pagination logic."""
    from oireachtas_etl import cli

    constructed = []

    class Loader:
        def __init__(self, *args, **kwargs):
            constructed.append(True)
            if construction_sink is not None:
                construction_sink.append(True)

        def replace(self, *args, **kwargs):
            pass

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_member_competency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    monkeypatch.setenv("OIR_API_LIMIT", str(limit))

    client = ApiClient("https://example.test/members")
    remaining = list(pages)

    def page(*, skip, limit):
        payload = remaining.pop(0)
        records = payload["results"]
        return ApiPage(json.dumps(payload).encode(), 200, {"skip": skip, "limit": limit})

    monkeypatch.setattr(client, "page", page)
    monkeypatch.setattr(cli, "ApiClient", lambda *args, **kwargs: client)
    args = _online_args(tmp_path)
    args.fixture = None
    return cli.run_members(args), constructed


@pytest.mark.parametrize("count", [None, True, 1.0, "1", -1])
def test_members_live_scan_requires_non_boolean_nonnegative_integer_count(tmp_path, monkeypatch, count):
    page = _members_page([WRAPPER], count)
    with pytest.raises(ValueError, match="nonnegative integer"):
        _run_mocked_live_pages(tmp_path, monkeypatch, [page], limit=2)


def test_members_live_scan_rejects_missing_count_on_later_page(tmp_path, monkeypatch):
    pages = [_members_page([WRAPPER], 1), _members_page([], None, include_count=False)]
    with pytest.raises(ValueError, match="nonnegative integer"):
        _run_mocked_live_pages(tmp_path, monkeypatch, pages, limit=1)


def test_members_live_scan_rejects_count_change_between_pages(tmp_path, monkeypatch):
    pages = [_members_page([WRAPPER], 2), _members_page([WRAPPER], 3)]
    with pytest.raises(ValueError, match="advertised count changed"):
        _run_mocked_live_pages(tmp_path, monkeypatch, pages, limit=1)


def test_members_live_scan_rejects_premature_short_scan_against_advertised_count(tmp_path, monkeypatch):
    pages = [_members_page([WRAPPER], 2)]
    with pytest.raises(ValueError, match="advertised count"):
        _run_mocked_live_pages(tmp_path, monkeypatch, pages, limit=2)


def test_members_live_scan_exact_boundary_consumes_terminal_page_and_succeeds(tmp_path, monkeypatch):
    # With one record and limit one, harvest must request and consume the
    # empty terminal page before run_members can publish successfully.
    pages = [_members_page([WRAPPER], 1), _members_page([], 1)]
    result, constructed = _run_mocked_live_pages(tmp_path, monkeypatch, pages, limit=1)
    assert result == 0 and constructed == [True] and pages[1]["results"] == []


def test_members_live_scan_rejects_lexical_uri_alias_collision_before_loader(tmp_path, monkeypatch):
    aliased = copied()
    aliased["member"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
    # Percent-encoding is a lexical alias of the same decoded memberCode and
    # therefore maps to the same deterministic member graph IRI.
    aliased["member"]["uri"] = aliased["member"]["uri"].replace("Timmy-Dooley", "Timmy%2DDooley")
    pages = [_members_page([WRAPPER, aliased], 2), _members_page([], 2)]
    constructed = []
    with pytest.raises(ValueError, match="collision"):
        _run_mocked_live_pages(tmp_path, monkeypatch, pages, limit=2, construction_sink=constructed)
    assert constructed == []


def _manifest_lock_holder(path, ready, release):
    from oireachtas_etl.state import state_lock
    with state_lock(Path(path)):
        ready.set()
        release.wait(5)


def _manifest_lock_contender(path, entered):
    from oireachtas_etl.state import state_lock
    with state_lock(Path(path)):
        entered.set()


def test_manifest_lock_blocks_second_process_until_first_releases(tmp_path):
    context = multiprocessing.get_context("fork")
    state_path = tmp_path / "state.sqlite"
    held = context.Event(); release = context.Event(); entered = context.Event()
    holder = context.Process(target=_manifest_lock_holder, args=(str(state_path), held, release))
    contender = None
    holder.start()
    try:
        assert held.wait(3), "lock holder did not acquire manifest lock"
        contender = context.Process(target=_manifest_lock_contender, args=(str(state_path), entered))
        contender.start()
        assert not entered.wait(0.25), "second process entered while manifest lock was held"
        release.set()
        assert entered.wait(3), "second process did not enter after manifest lock release"
        contender.join(3); holder.join(3)
        assert contender.exitcode == 0 and holder.exitcode == 0
    finally:
        release.set()
        for process in (contender, holder):
            if process is not None:
                process.join(3)
                if process.is_alive(): process.terminate(); process.join(3)


def test_online_members_run_holds_manifest_lock_during_loader_publication(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    lock_seen = []

    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs):
            lock_path = Path(_online_args(tmp_path).state_db).with_name("state.sqlite.lock")
            with lock_path.open("a+") as handle:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lock_seen.append(True)
                else:
                    lock_seen.append(False)
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_member_competency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    assert cli.run_members(_online_args(tmp_path)) == 0
    assert lock_seen == [True]


def test_offline_members_run_does_not_acquire_lock_or_publish_state(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    monkeypatch.setattr(cli, "state_lock", lambda path: (_ for _ in ()).throw(AssertionError("offline run acquired lock")))
    args = _online_args(tmp_path)
    args.offline = True
    assert cli.run_members(args) == 0
    assert not Path(args.state_db).exists()


def test_members_online_first_run_is_new_and_writes_published_state(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    assert cli.run_members(_online_args(tmp_path)) == 0
    result, identity = _report(capsys), WRAPPER["member"]["uri"]
    assert result["new"] == [identity] and result["changed"] == [] and result["skipped_identities"] == []
    assert result["published"] == 1 and len(calls) == 1
    assert _member_state(tmp_path, identity)["published_source_hash"] == source_hash(WRAPPER["member"])


def test_members_online_unchanged_skips_before_transform_and_put_but_reports_omissions(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    first_calls = []; _mock_online(monkeypatch, first_calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    calls = []; _mock_online(monkeypatch, calls)
    monkeypatch.setattr(cli, "transform_member_with_report", lambda value: (_ for _ in ()).throw(AssertionError("must skip transform")))
    assert cli.run_members(_online_args(tmp_path)) == 0
    result, identity = _report(capsys), WRAPPER["member"]["uri"]
    assert result["new"] == [] and result["changed"] == [] and result["skipped_identities"] == [identity]
    assert result["published"] == 0 and result["skipped"] == 1 and calls == []
    assert result["future_work_omitted"]


def test_members_online_changed_mapped_source_is_changed_and_put(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    changed = copied(); changed["member"]["fullName"] = "Timmy Dooley changed"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    calls = []; _mock_online(monkeypatch, calls)
    args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-changed")
    assert cli.run_members(args) == 0
    result, identity = _report(capsys), WRAPPER["member"]["uri"]
    assert result["new"] == [] and result["changed"] == [identity] and result["skipped_identities"] == []
    assert result["published"] == 1 and len(calls) == 1


def test_members_online_competency_failure_after_put_keeps_previous_published_hash(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    before = _member_state(tmp_path)
    changed = copied(); changed["member"]["fullName"] = "Timmy Dooley changed"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    calls = []; _mock_online(monkeypatch, calls, competency=lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    with pytest.raises(ValueError, match="competency failed"):
        args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-changed")
        cli.run_members(args)
    assert len(calls) == 1
    after = _member_state(tmp_path)
    assert after["published_source_hash"] == before["published_source_hash"]


def test_members_competency_failure_after_put_persists_dirty_pending_hash(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    prior = _member_state(tmp_path)
    changed = copied(); changed["member"]["fullName"] = "A failed publication"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    _mock_online(monkeypatch, calls, competency=lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-changed")
    with pytest.raises(ValueError, match="competency failed"):
        cli.run_members(args)
    entry = _member_state(tmp_path)
    assert entry["publication_state"] == "dirty"
    assert entry["pending_source_hash"] == source_hash(changed["member"])
    assert entry["published_source_hash"] == prior["published_source_hash"]


def test_members_reverted_source_republishes_dirty_entry_and_clears_pending(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    changed = copied(); changed["member"]["fullName"] = "B failed publication"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    _mock_online(monkeypatch, calls, competency=lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-b")
    with pytest.raises(ValueError): cli.run_members(args)
    calls.clear(); _mock_online(monkeypatch, calls)
    result = cli.run_members(_online_args(tmp_path)); output = _report(capsys)
    entry = _member_state(tmp_path)
    identity = WRAPPER["member"]["uri"]
    assert result == 0 and len(calls) == 1
    assert output["changed"] == [identity] and output["skipped_identities"] == []
    assert entry["publication_state"] == "clean" and entry["pending_source_hash"] is None
    assert entry["published_source_hash"] == source_hash(WRAPPER["member"])


def test_members_put_failure_is_dirty_and_retry_publishes_clean_current_state(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    class FailingLoader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", FailingLoader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_member_competency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    args = _online_args(tmp_path)
    with pytest.raises(RuntimeError, match="PUT failed"): cli.run_members(args)
    dirty = _member_state(tmp_path)
    assert dirty["publication_state"] == "dirty" and dirty["pending_source_hash"] == source_hash(WRAPPER["member"])
    calls = []; _mock_online(monkeypatch, calls)
    assert cli.run_members(args) == 0 and len(calls) == 1
    clean = _member_state(tmp_path)
    assert clean["publication_state"] == "clean" and clean["pending_source_hash"] is None
    assert clean["published_source_hash"] == source_hash(WRAPPER["member"])
    assert _report(capsys)["changed"] == [WRAPPER["member"]["uri"]]


def test_members_true_skip_calls_source_validation_only_and_reports_omissions(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.validation import members as member_validation
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    source_calls = []
    original_source_validation = cli.validate_member_source
    monkeypatch.setattr(cli, "validate_member_source", lambda value: (source_calls.append(value) or original_source_validation(value)))
    monkeypatch.setattr(cli, "transform_member_with_report", lambda value: (_ for _ in ()).throw(AssertionError("production transformer called")))
    monkeypatch.setattr(member_validation, "expected_member_graph", lambda value: (_ for _ in ()).throw(AssertionError("independent builder called")))
    calls.clear()
    assert cli.run_members(_online_args(tmp_path)) == 0
    output = _report(capsys)
    identity = WRAPPER["member"]["uri"]
    assert source_calls and calls == []
    assert output["new"] == [] and output["changed"] == [] and output["skipped_identities"] == [identity]
    assert output["published"] == 0 and output["skipped"] == 1 and output["future_work_omitted"]


def test_members_online_retains_manifest_only_absent_member(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    absent = "https://data.oireachtas.ie/ie/oireachtas/member/id/Absent"
    state = {"version": 1, "members": {absent: {"published_hash": "old", "graph_iri": "https://data.oireachtas.ie/graph/member/Absent", "contract_version": 1}}}
    legacy = tmp_path / "members-state.json"
    legacy.write_text(json.dumps(state))
    calls = []; _mock_online(monkeypatch, calls)
    args = _online_args(tmp_path); args.legacy_state_file = str(legacy)
    assert cli.run_members(args) == 0
    result = _report(capsys)
    from oireachtas_etl.state import CoreStateStore
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        persisted = store.get_resource("members", absent)
    assert result["missing_retained"] == [absent]
    assert persisted["published_source_hash"] == "old"
    assert json.loads(legacy.read_text()) == state


def test_members_full_scan_replays_durable_dirty_payload_when_source_omits_resource(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    absent = "https://data.oireachtas.ie/ie/oireachtas/member/id/PreviouslyObserved"
    graph_iri = "https://data.oireachtas.ie/graph/member/PreviouslyObserved"
    graph = Graph()
    graph.add((URIRef(absent), RDF.type, OIR.Member))
    payload = ntriples(graph)
    database = tmp_path / "state.sqlite"
    with CoreStateStore(database) as store:
        run_id = store.start_run("members", "full_refresh", is_complete=True, parameters={"seed": True})
        store.observe_resource("members", absent, graph_iri, "a" * 64, run_id)
        store.mark_publication_dirty("members", absent, source_hash="a" * 64,
                                     graph_iri=graph_iri, payload=payload, contract_version=2)
        store.finish_run(run_id, success=False, error="interrupted after pending state")

    calls = []; _mock_online(monkeypatch, calls)
    args = _online_args(tmp_path)
    assert cli.run_members(args) == 0
    result = _report(capsys)
    assert result["missing_retained"] == [absent]
    assert result["published"] == 2  # current Member plus recovered prior payload
    assert (graph_iri, payload) in calls
    with CoreStateStore(database) as store:
        recovered = store.get_resource("members", absent)
        assert recovered["publication_state"] == "clean"
        assert recovered["published_payload_hash"] == __import__("hashlib").sha256(payload.encode()).hexdigest()
        assert recovered["pending_payload"] is None
