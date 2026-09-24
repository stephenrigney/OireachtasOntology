import json
import fcntl
import multiprocessing
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF

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
                     output_nq=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query", state_file=str(tmp_path / "state.json"))
    with pytest.raises(RuntimeError, match="PUT failed"):
        cli.run_members(args)
    state = json.loads((tmp_path / "state.json").read_text())
    entry = state["members"][WRAPPER["member"]["uri"]]
    assert entry["status"] == "dirty"
    assert "published_hash" not in entry


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
                     state_file=str(tmp_path / "state.json"))


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
    from oireachtas_etl.state import manifest_lock
    with manifest_lock(Path(path)):
        ready.set()
        release.wait(5)


def _manifest_lock_contender(path, entered):
    from oireachtas_etl.state import manifest_lock
    with manifest_lock(Path(path)):
        entered.set()


def test_manifest_lock_blocks_second_process_until_first_releases(tmp_path):
    context = multiprocessing.get_context("fork")
    state_path = tmp_path / "state.json"
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
            lock_path = Path(_online_args(tmp_path).state_file).with_name("state.json.lock")
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
    assert cli.run_members(_online_args(tmp_path)) == 0
    assert lock_seen == [True]


def test_offline_members_run_does_not_acquire_lock_or_publish_state(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    monkeypatch.setattr(cli, "manifest_lock", lambda path: (_ for _ in ()).throw(AssertionError("offline run acquired lock")))
    args = _online_args(tmp_path)
    args.offline = True
    assert cli.run_members(args) == 0
    assert not Path(args.state_file).exists()


def test_members_online_first_run_is_new_and_writes_published_state(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    assert cli.run_members(_online_args(tmp_path)) == 0
    result, identity = _report(capsys), WRAPPER["member"]["uri"]
    state = json.loads((tmp_path / "state.json").read_text())
    assert result["new"] == [identity] and result["changed"] == [] and result["skipped_identities"] == []
    assert result["published"] == 1 and len(calls) == 1
    assert state["members"][identity]["published_hash"] == source_hash(WRAPPER["member"])


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
    before = json.loads((tmp_path / "state.json").read_text())
    changed = copied(); changed["member"]["fullName"] = "Timmy Dooley changed"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    calls = []; _mock_online(monkeypatch, calls, competency=lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    with pytest.raises(ValueError, match="competency failed"):
        args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-changed")
        cli.run_members(args)
    assert len(calls) == 1
    after = json.loads((tmp_path / "state.json").read_text())
    assert after["members"][WRAPPER["member"]["uri"]]["published_hash"] == before["members"][WRAPPER["member"]["uri"]]["published_hash"]


def test_members_competency_failure_after_put_persists_dirty_pending_hash(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    calls = []; _mock_online(monkeypatch, calls)
    cli.run_members(_online_args(tmp_path)); capsys.readouterr()
    prior = json.loads((tmp_path / "state.json").read_text())["members"][WRAPPER["member"]["uri"]]
    changed = copied(); changed["member"]["fullName"] = "A failed publication"
    fixture = tmp_path / "changed.json"; fixture.write_text(json.dumps(changed))
    _mock_online(monkeypatch, calls, competency=lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    args = _online_args(tmp_path, fixture); args.raw_dir = str(tmp_path / "raw-changed")
    with pytest.raises(ValueError, match="competency failed"):
        cli.run_members(args)
    entry = json.loads((tmp_path / "state.json").read_text())["members"][WRAPPER["member"]["uri"]]
    assert entry["status"] in {"dirty", "in_progress"}
    assert entry["pending_hash"] == source_hash(changed["member"])
    assert entry["published_hash"] == prior["published_hash"]


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
    entry = json.loads((tmp_path / "state.json").read_text())["members"][WRAPPER["member"]["uri"]]
    identity = WRAPPER["member"]["uri"]
    assert result == 0 and len(calls) == 1
    assert output["changed"] == [identity] and output["skipped_identities"] == []
    assert entry["status"] == "clean" and "pending_hash" not in entry
    assert entry["published_hash"] == source_hash(WRAPPER["member"])


def test_members_put_failure_is_dirty_and_retry_publishes_clean_current_state(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    class FailingLoader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", FailingLoader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_member_competency", lambda *args, **kwargs: None)
    args = _online_args(tmp_path)
    with pytest.raises(RuntimeError, match="PUT failed"): cli.run_members(args)
    dirty = json.loads((tmp_path / "state.json").read_text())["members"][WRAPPER["member"]["uri"]]
    assert dirty["status"] in {"dirty", "in_progress"} and dirty["pending_hash"] == source_hash(WRAPPER["member"])
    calls = []; _mock_online(monkeypatch, calls)
    assert cli.run_members(args) == 0 and len(calls) == 1
    clean = json.loads((tmp_path / "state.json").read_text())["members"][WRAPPER["member"]["uri"]]
    assert clean["status"] == "clean" and "pending_hash" not in clean
    assert clean["published_hash"] == source_hash(WRAPPER["member"])
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
    (tmp_path / "state.json").write_text(json.dumps(state))
    calls = []; _mock_online(monkeypatch, calls)
    assert cli.run_members(_online_args(tmp_path)) == 0
    result = _report(capsys)
    persisted = json.loads((tmp_path / "state.json").read_text())
    assert result["missing_retained"] == [absent]
    assert absent in persisted["members"]
