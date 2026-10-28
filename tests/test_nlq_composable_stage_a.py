"""Stage A family routes tested against a small synthetic, owner-scoped RDF dataset."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from poc.nlq.composable_plan import execute_question
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.stage_a import merge_service_intervals, parse_stage_a_question
from poc.nlq.composable_plan import PlanError, validate_plan
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 25)
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
FOAF_NAME = URIRef("http://xmlns.com/foaf/0.1/name")


class StageAFixture:
    """Artificial RDF for route mechanics; dates/relations are not factual coverage claims."""
    def __init__(self):
        self.dataset = Dataset()
        self.queries = []
        self.houses = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
        self.parties = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
        self.constituencies = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/constituencies"))
        self.committees = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/committees"))
        self.dail33 = self.add_term("Dail", 33, "2020-02-08T00:00:00", "2024-11-08T00:00:00")
        self.dail34 = self.add_term("Dail", 34, "2024-11-29T00:00:00", None)
        self.dail32 = self.add_term("Dail", 32, "2016-02-03T00:00:00", "2020-02-07T00:00:00")
        self.seanad26 = self.add_term("Seanad", 26, "2020-06-29T00:00:00", "2025-01-01T00:00:00")
        self.seanad27 = self.add_term("Seanad", 27, "2025-01-02T00:00:00", None)
        self.add_member("aengus", "Aengus Ó Snodaigh")
        self.add_membership("aengus", "Dail", self.dail33, "2011-03-09T00:00:00", "2024-11-08T00:00:00")
        self.add_member("micheal", "Micheál Martin")
        self.add_membership("micheal", "Dail", self.dail32, "2016-02-05T00:00:00", "2017-01-10T00:00:00")
        self.add_membership("micheal", "Dail", self.dail33, "2020-02-10T00:00:00", "2021-01-01T00:00:00")
        self.add_membership("micheal", "Dail", self.dail34, "2024-11-29T00:00:00", None)
        self.add_member("timmy", "Timmy Dooley")
        self.add_membership("timmy", "Seanad", self.seanad26, "2020-06-29T00:00:00", "2024-11-29T00:00:00",
                            None)
        self.add_membership("timmy", "Seanad", self.seanad27, "2025-01-02T00:00:00", None,
                            "Agricultural Panel")
        self.add_member("mcdowell", "Michael McDowell")
        self.add_membership("mcdowell", "Seanad", self.seanad26, "2020-06-29T00:00:00", "2025-01-01T00:00:00",
                            "National University of Ireland constituency")
        self.add_member("panel-member", "Bríd Example")
        self.add_membership("panel-member", "Seanad", self.seanad26, "2020-06-29T00:00:00", "2025-01-01T00:00:00",
                            "Agricultural Panel")
        self.add_member("chris", "Chris Andrews")
        self.add_collection("chris", "ParliamentaryParty", "Fianna Fáil", "2025-01-01T00:00:00", None)
        self.add_member("lowry", "Michael Lowry")
        self.add_collection("lowry", "IndependentMemberCollection", "Independent", "2024-11-29T00:00:00", None)
        self.add_member("collins-d", "Michael Collins")
        self.add_membership("collins-d", "Dail", self.dail33, "2016-02-26T00:00:00", "2020-02-08T00:00:00")
        self.add_member("collins-s", "Michael Collins")
        self.add_membership("collins-s", "Seanad", self.seanad26, "2020-06-29T00:00:00", "2025-01-01T00:00:00")
        self._add_committee_member()

    def add_term(self, house: str, number: int, start: str, end: str | None):
        house_lower = house.casefold()
        term = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/{house_lower}/{number}")
        period = URIRef(f"{term}#period")
        self.houses.add((term, RDF.type, URIRef(AGENTS + house + "Term")))
        suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        self.houses.add((term, SKOS.prefLabel, Literal(f"{number}{suffix} {house}".replace("Dail", "Dáil"), lang="en")))
        self.houses.add((term, URIRef(AGENTS + "termNo"), Literal(number, datatype=XSD.integer)))
        self.houses.add((term, URIRef(AGENTS + "termOf"), URIRef(f"https://data.oireachtas.ie/house/{house_lower}")))
        self.houses.add((term, URIRef("http://purl.org/dc/terms/temporal"), period))
        self.houses.add((period, RDF.type, URIRef("http://purl.org/dc/terms/PeriodOfTime")))
        self.houses.add((period, URIRef("http://www.w3.org/ns/dcat#startDate"), Literal(start, datatype=XSD.dateTime)))
        if end:
            self.houses.add((period, URIRef("http://www.w3.org/ns/dcat#endDate"), Literal(end, datatype=XSD.dateTime)))
        return term

    def add_member(self, code: str, name: str):
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{code}"))
        self.members_graphs = getattr(self, "members_graphs", {})
        member = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/member/id/{code}")
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, FOAF_NAME, Literal(name)))
        self.members_graphs[code] = graph
        return member

    def add_membership(self, code: str, house: str, term, start: str, end: str | None, representation: str | None = None):
        graph = self.members_graphs[code]
        member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
        counters = getattr(self, "membership_counters", {})
        index = counters.get(code, 0) + 1
        counters[code] = index
        self.membership_counters = counters
        membership = URIRef(f"{member}/house/{house.casefold()}/{term.rsplit('/', 1)[-1]}-{index}")
        date_range = URIRef(str(membership) + "#date-range")
        graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), membership))
        graph.add((membership, RDF.type, URIRef(MEMBERS + house + "Membership")))
        graph.add((membership, URIRef(MEMBERS + "inHouseTerm"), term))
        graph.add((membership, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
        graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
        graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
        if end:
            graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        if representation:
            representation_iri = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/seanad/{term.rsplit('/', 1)[-1]}/panel/{representation.replace(' ', '-')}")
            self.constituencies.add((representation_iri, RDF.type, URIRef(MEMBERS + "SeanadPanel")))
            self.constituencies.add((representation_iri, RDF.type, URIRef(MEMBERS + "Constituencies")))
            self.constituencies.add((representation_iri, SKOS.prefLabel, Literal(representation, lang="en")))
            self.constituencies.add((representation_iri, URIRef(MEMBERS + "constituencyInHouseTerm"), term))
            graph.add((membership, URIRef(MEMBERS + "isRepresentativeFrom"), representation_iri))
        return membership

    def add_collection(self, code: str, collection_class: str, label: str, start: str, end: str | None):
        graph = self.members_graphs[code]
        member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
        collection = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/party/dail/34/{label.replace(' ', '_')}")
        record = URIRef(str(member) + "#collection-record")
        date_range = URIRef(str(record) + "#date-range")
        graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), record))
        graph.add((record, RDF.type, URIRef(MEMBERS + "ParliamentaryCollectionMembership")))
        graph.add((record, URIRef(MEMBERS + "memberOfCollection"), collection))
        owner_membership = URIRef(str(member) + "#synthetic-collection-owner")
        graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), owner_membership))
        graph.add((owner_membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
        graph.add((owner_membership, URIRef(MEMBERS + "inHouseTerm"), self.dail34))
        graph.add((record, URIRef(MEMBERS + "inOireachtasMembership"), owner_membership))
        graph.add((record, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
        graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
        graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
        if end:
            graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        self.parties.add((collection, RDF.type, URIRef(MEMBERS + collection_class)))
        self.parties.add((collection, SKOS.prefLabel, Literal(label, lang="en")))

    def _add_committee_member(self):
        member = next(self.members_graphs["timmy"].subjects(RDF.type, URIRef(AGENTS + "Member")))
        graph = self.members_graphs["timmy"]
        committee = URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/select_committee_on_transport")
        self.committees.add((committee, RDF.type, URIRef(MEMBERS + "Committee")))
        self.committees.add((committee, URIRef(MEMBERS + "committeeInHouseTerm"), self.dail34))
        self.committees.add((committee, SKOS.prefLabel, Literal("Select Committee on Transport and Communications", lang="en")))
        committee_range = URIRef(str(committee) + "#dates")
        self.committees.add((committee, URIRef(MEMBERS + "hasCommitteeDateRange"), committee_range))
        self.committees.add((committee_range, RDF.type, URIRef(MEMBERS + "DateRange")))
        self.committees.add((committee_range, URIRef(MEMBERS + "StartDate"), Literal("2024-12-01T00:00:00", datatype=XSD.dateTime)))
        cm1 = URIRef(str(member) + "#committee-membership-1")
        cm2 = URIRef(str(member) + "#committee-membership-2")
        for cm in (cm1, cm2):
            graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), cm))
            graph.add((cm, RDF.type, URIRef(MEMBERS + "CommitteeMembership")))
            graph.add((cm, URIRef(MEMBERS + "isCommitteeMembershipOf"), committee))

    def readiness(self):
        return FusekiReadiness("ready", True, (), "synthetic Stage A evidence")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type == "ASK":
            return QueryResult("ask", boolean=bool(result.askAnswer))
        columns = tuple(str(variable) for variable in result.vars)
        rows = []
        for row in result:
            values = []
            for value in row:
                if value is None:
                    values.append("—")
                elif isinstance(value, Literal) and value.datatype:
                    values.append(f"{value}^^<{value.datatype}>")
                elif isinstance(value, Literal) and value.language:
                    values.append(f"{value}@{value.language}")
                else:
                    values.append(str(value))
            rows.append(tuple(values))
        return QueryResult("select", columns, tuple(rows))


def _run(question: str, fixture: StageAFixture | None = None):
    fixture = fixture or StageAFixture()
    return execute_question(question, as_of=AS_OF, fuseki=fixture,
                            supported_predicates=supported_predicates(ROOT / "ontology")), fixture


@pytest.mark.parametrize("question,family", [
    ("Find Deputy Ó Snodaigh's full name for me.", "member_lookup"),
    ("Was Aengus Ó Snodaigh a TD in the previous Dáil term?", "previous_service"),
    ("How long was Micheál Martin a Deputy?", "dail_duration"),
    ("How many Dáil terms has Micheál Martin served in?", "term_count"),
    ("When did Timmy Dooley become a Senator?", "seanad_entry"),
    ("What party is Senator Chris Andrews a member of?", "current_collection"),
    ("What party does Michael Lowry belong to now?", "current_collection"),
    ("Which panel did Timmy Dooley represent in the 26th Seanad?", "seanad_representation"),
    ("Was Timmy Dooley a member of the Select Committee on Transport and Communications?", "committee_boolean"),
    ("How many committees was Timmy Dooley a member of?", "committee_count"),
    ("When did each Dáil start and finish?", "house_terms"),
    ("Who is Michael Collins?", "member_lookup"),
    ("Which Members named Michael Collins served in the Dáil?", "dail_all"),
    ("What is the full name of Niamh Example?", "member_lookup"),
    ("How many Dáil terms are listed in the Houses data?", "term_count"),
])
def test_approved_stage_a_questions_map_to_general_family_primitives(question, family):
    request = parse_stage_a_question(question)
    assert request is not None and request.family == family


def test_q01_partial_qualified_member_name_resolves_to_full_local_name():
    outcome, _ = _run("Find Deputy Ó Snodaigh's full name for me.")
    assert outcome.status == "success"
    assert outcome.result.rows == (("Aengus Ó Snodaigh",),)
    assert "external identity" in outcome.diagnostic


def test_q02_previous_term_is_as_of_selected_and_membership_is_boolean():
    outcome, _ = _run("Was Aengus Ó Snodaigh a TD in the previous Dáil term?")
    assert outcome.status == "success"
    assert outcome.result.kind == "ask" and outcome.result.boolean is True
    assert "2026-10-25" in outcome.diagnostic


def test_q02_absent_membership_rows_are_not_a_confirmed_no():
    fixture = StageAFixture()
    graph = fixture.members_graphs["aengus"]
    graph.remove((None, None, None))
    fixture.add_member("aengus-empty", "Aengus Ó Snodaigh")
    outcome = execute_question("Was Aengus Ó Snodaigh a TD in the previous Dáil term?", as_of=AS_OF,
                               fuseki=fixture, supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "source_data_unavailable"
    assert "not a reliable negative" in outcome.diagnostic


def test_q03_cumulative_service_unions_overlaps_and_preserves_gaps():
    outcome, _ = _run("How long was Micheál Martin a Deputy?")
    assert outcome.status == "success"
    assert outcome.result.columns == ("Member", "Cumulative service (days)", "Service intervals", "Gaps")
    assert "2020-02-10" in outcome.result.rows[0][2]
    assert "2017-01-11" in outcome.result.rows[0][3]
    assert "2024-11-29" in outcome.result.rows[0][2]
    assert "not certify complete lifetime history" in outcome.diagnostic


def test_q03_missing_end_in_historical_membership_is_not_extended_to_asof():
    fixture = StageAFixture()
    member = fixture.members_graphs["micheal"]
    for membership in list(member.objects(None, URIRef(MEMBERS + "hasMembershipDateRange"))):
        pass
    # Remove the end date from an episode attached to an ended HouseTerm.
    old_term = fixture.dail32
    old_term_membership = next(member.subjects(URIRef(MEMBERS + "inHouseTerm"), old_term))
    old_range = next(member.objects(old_term_membership, URIRef(MEMBERS + "hasMembershipDateRange")))
    member.remove((old_range, URIRef(MEMBERS + "EndDate"), None))
    outcome = execute_question("How long was Micheál Martin a Deputy?", as_of=AS_OF, fuseki=fixture,
                               supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "source_data_unavailable"
    assert "not extended to today" in outcome.diagnostic


def test_service_interval_union_does_not_double_count_overlaps():
    from datetime import date
    merged, days, gaps = merge_service_intervals([
        (date(2020, 1, 1), date(2020, 1, 10)),
        (date(2020, 1, 5), date(2020, 1, 15)),
        (date(2020, 1, 20), date(2020, 1, 25)),
    ], date(2020, 1, 25))
    assert merged == [(date(2020, 1, 1), date(2020, 1, 15)), (date(2020, 1, 20), date(2020, 1, 25))]
    assert days == 21
    assert gaps == [(date(2020, 1, 16), date(2020, 1, 19))]


def test_q04_and_t01_count_distinct_house_term_identities():
    member, _ = _run("How many Dáil terms has Micheál Martin served in?")
    total, fixture = _run("How many Dáil terms are listed in the Houses data?")
    assert member.result.rows == (("3",),)
    assert total.result.rows == (("3",),)
    assert "distinct Dáil-term resources" in total.diagnostic
    assert "COUNT(DISTINCT ?term)" in fixture.queries[-1]
    assert "skos:prefLabel" not in fixture.queries[-1] and "termNo" not in fixture.queries[-1]


def test_q04_and_t01_count_links_without_optional_term_description():
    fixture = StageAFixture()
    term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/31-unlabelled")
    fixture.houses.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
    aengus = next(fixture.members_graphs["aengus"].subjects(RDF.type, URIRef(AGENTS + "Member")))
    membership = URIRef(str(aengus) + "#metadata-free-term")
    graph = fixture.members_graphs["aengus"]
    graph.add((aengus, URIRef(MEMBERS + "hasMembersMembership"), membership))
    graph.add((membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
    graph.add((membership, URIRef(MEMBERS + "inHouseTerm"), term))
    by_member, _ = _run("How many Dáil terms has Aengus Ó Snodaigh served in?", fixture)
    total, _ = _run("How many Dáil terms are listed in the Houses data?", fixture)
    assert by_member.status == "success" and by_member.result.rows == (("2",),)
    assert total.status == "success" and total.result.rows == (("4",),)


def test_q05_first_seanad_membership_has_date_and_keeps_later_episode():
    outcome, _ = _run("When did Timmy Dooley become a Senator?")
    assert outcome.status == "success"
    assert outcome.result.rows[0][1:3] == ("2020-06-29", "26th Seanad")
    assert "No designation recorded" in outcome.result.rows[0][3]
    assert "27th Seanad" in outcome.result.rows[0][4]


def test_q05_does_not_ignore_missing_or_conflicting_episode_starts():
    fixture = StageAFixture()
    graph = fixture.members_graphs["timmy"]
    member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
    first_membership = next(membership for membership in graph.objects(member, URIRef(MEMBERS + "hasMembersMembership"))
                            if (membership, RDF.type, URIRef(MEMBERS + "SeanadMembership")) in graph)
    date_range = next(graph.objects(first_membership, URIRef(MEMBERS + "hasMembershipDateRange")))
    graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal("2021-01-01T00:00:00", datatype=XSD.dateTime)))
    outcome, _ = _run("When did Timmy Dooley become a Senator?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "Conflicting Seanad membership date-range" in outcome.diagnostic

    fixture = StageAFixture()
    graph = fixture.members_graphs["timmy"]
    member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
    membership = next(membership for membership in graph.objects(member, URIRef(MEMBERS + "hasMembersMembership"))
                      if (membership, RDF.type, URIRef(MEMBERS + "SeanadMembership")) in graph)
    date_range = next(graph.objects(membership, URIRef(MEMBERS + "hasMembershipDateRange")))
    graph.remove((date_range, URIRef(MEMBERS + "StartDate"), None))
    missing, _ = _run("When did Timmy Dooley become a Senator?", fixture)
    assert missing.status == "source_data_unavailable"
    assert "earliest entry cannot be established" in missing.diagnostic

    fixture = StageAFixture()
    graph = fixture.members_graphs["timmy"]
    member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
    membership = next(membership for membership in graph.objects(member, URIRef(MEMBERS + "hasMembersMembership"))
                      if (membership, RDF.type, URIRef(MEMBERS + "SeanadMembership")) in graph)
    date_range = next(graph.objects(membership, URIRef(MEMBERS + "hasMembershipDateRange")))
    graph.remove((date_range, URIRef(MEMBERS + "StartDate"), None))
    graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal("2020-06-29T00:00:00", datatype=XSD.string)))
    wrong_datatype, _ = _run("When did Timmy Dooley become a Senator?", fixture)
    assert wrong_datatype.status == "source_data_unavailable"
    assert "no reviewed xsd:date/dateTime datatype" in wrong_datatype.diagnostic


@pytest.mark.parametrize("question,expected", [
    ("What party is Senator Chris Andrews a member of?", "Fianna Fáil"),
    ("What party does Michael Lowry belong to now?", "Independent"),
])
def test_q07_q08_use_injectable_asof_and_distinguish_independent(question, expected):
    outcome, _ = _run(question)
    assert outcome.status == "success"
    assert expected in outcome.result.rows[0][0]
    assert "2026-10-25" in outcome.diagnostic


def test_open_collection_record_in_ended_containing_term_is_not_current():
    fixture = StageAFixture()
    graph = fixture.members_graphs["chris"]
    member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
    record = next(graph.subjects(RDF.type, URIRef(MEMBERS + "ParliamentaryCollectionMembership")))
    synthetic_owner = URIRef(str(member) + "#synthetic-collection-owner")
    graph.remove((record, URIRef(MEMBERS + "inOireachtasMembership"), synthetic_owner))
    graph.remove((member, URIRef(MEMBERS + "hasMembersMembership"), synthetic_owner))
    owner = URIRef(str(member) + "#ended-owner")
    graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), owner))
    graph.add((owner, RDF.type, URIRef(MEMBERS + "DailMembership")))
    graph.add((owner, URIRef(MEMBERS + "inHouseTerm"), fixture.dail33))
    graph.add((record, URIRef(MEMBERS + "inOireachtasMembership"), owner))
    outcome, _ = _run("What party is Chris Andrews a member of?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "not evidence of no affiliation" in outcome.diagnostic or "not inferred" in outcome.diagnostic


@pytest.mark.parametrize("member,representation", [
    ("Michael McDowell", "National University of Ireland constituency"),
    ("Bríd Example", "Agricultural Panel"),
])
def test_q10_reports_source_designations_without_coercing_seanad_routes(member, representation):
    outcome, _ = _run(f"Which panel did {member} represent in the 26th Seanad?")
    assert outcome.status == "success"
    assert representation in repr(outcome.result.rows)


def test_q10_does_not_infer_taoiseach_nomination_when_mapping_has_no_entry_route():
    outcome, _ = _run("Which panel did Timmy Dooley represent in the 26th Seanad?")
    assert outcome.status == "source_data_unavailable"
    assert "cannot be inferred" in outcome.diagnostic


def test_q11_requires_unique_current_committee_date_evidence():
    outcome, _ = _run("Was Timmy Dooley a member of the Select Committee on Transport and Communications?")
    assert outcome.status == "success"
    assert outcome.result.kind == "ask" and outcome.result.boolean is True
    assert "current committee incarnation" in outcome.diagnostic.casefold()
    assert "2026-10-25" in outcome.diagnostic
    fixture = StageAFixture()
    for triple in list(fixture.committees):
        if triple[1] == URIRef(MEMBERS + "hasCommitteeDateRange"):
            fixture.committees.remove(triple)
    missing, _ = _run("Was Timmy Dooley a member of the Select Committee on Transport and Communications?", fixture)
    assert missing.status == "source_data_unavailable"
    assert "Member identities were not queried" in missing.diagnostic


def test_q11_matches_membership_to_selected_committee_iri_and_returns_name():
    fixture = StageAFixture()
    member = next(fixture.members_graphs["timmy"].subjects(RDF.type, URIRef(AGENTS + "Member")))
    other = URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/unrelated")
    fixture.committees.add((other, RDF.type, URIRef(MEMBERS + "Committee")))
    fixture.committees.add((other, URIRef(MEMBERS + "committeeInHouseTerm"), fixture.dail34))
    fixture.committees.add((other, SKOS.prefLabel, Literal("Unrelated Committee", lang="en")))
    cm = URIRef(str(member) + "#committee-membership-unrelated")
    graph = fixture.members_graphs["timmy"]
    graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), cm))
    graph.add((cm, RDF.type, URIRef(MEMBERS + "CommitteeMembership")))
    graph.add((cm, URIRef(MEMBERS + "isCommitteeMembershipOf"), other))
    outcome, _ = _run("Was Timmy Dooley a member of the Select Committee on Transport and Communications?", fixture)
    assert outcome.status == "success" and outcome.result.boolean is True
    assert "Select Committee on Transport and Communications" in outcome.diagnostic
    assert str(other) not in outcome.diagnostic


def test_q11_selected_committee_and_asof_qualification_are_visible_in_ask(monkeypatch):
    from poc.nlq import app as app_module
    fixture = StageAFixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Was Timmy Dooley a member of the Select Committee on Transport and Communications?",
        "mode": "phase2",
    })
    assert "Select Committee on Transport and Communications" in response.text
    assert AS_OF.isoformat() in response.text


def test_q13_counts_distinct_committee_iris_not_repeated_membership_rows():
    outcome, _ = _run("How many committees was Timmy Dooley a member of?")
    assert outcome.status == "success"
    assert outcome.result.rows == (("1",),)
    assert "distinct membership-linked Committee IRIs" in outcome.diagnostic


def test_q13_counts_membership_linked_committee_without_owner_metadata():
    fixture = StageAFixture()
    hidden = URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/unknown-owner")
    member = next(fixture.members_graphs["timmy"].subjects(RDF.type, URIRef(AGENTS + "Member")))
    membership = URIRef(str(member) + "#committee-membership-unlabelled")
    graph = fixture.members_graphs["timmy"]
    graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), membership))
    graph.add((membership, RDF.type, URIRef(MEMBERS + "CommitteeMembership")))
    graph.add((membership, URIRef(MEMBERS + "isCommitteeMembershipOf"), hidden))
    outcome, _ = _run("How many committees was Timmy Dooley a member of?", fixture)
    assert outcome.status == "success" and outcome.result.rows == (("2",),)


def test_q03_rejects_open_historical_house_term_despite_member_context_rows():
    fixture = StageAFixture()
    old = fixture.add_term("Dail", 31, "2011-02-25T00:00:00", None)
    fixture.add_membership("micheal", "Dail", old, "2011-02-25T00:00:00", None)
    outcome, _ = _run("How long was Micheál Martin a Deputy?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "historical HouseTerm has no end date" in outcome.diagnostic


def test_q03_does_not_clip_inconsistent_membership_interval_to_house_term():
    fixture = StageAFixture()
    graph = fixture.members_graphs["micheal"]
    member = next(graph.subjects(RDF.type, URIRef(AGENTS + "Member")))
    membership = next(graph.subjects(URIRef(MEMBERS + "inHouseTerm"), fixture.dail32))
    date_range = next(graph.objects(membership, URIRef(MEMBERS + "hasMembershipDateRange")))
    graph.remove((date_range, URIRef(MEMBERS + "StartDate"), None))
    graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal("2015-01-01T00:00:00", datatype=XSD.dateTime)))
    outcome, _ = _run("How long was Micheál Martin a Deputy?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "not silently clipped or intersected" in outcome.diagnostic


def test_q13_absent_local_committee_records_are_not_an_exact_zero():
    fixture = StageAFixture()
    member = next(fixture.members_graphs["timmy"].subjects(RDF.type, URIRef(AGENTS + "Member")))
    graph = fixture.members_graphs["timmy"]
    for membership in list(graph.objects(member, URIRef(MEMBERS + "hasMembersMembership"))):
        if (membership, RDF.type, URIRef(MEMBERS + "CommitteeMembership")) in graph:
            graph.remove((member, URIRef(MEMBERS + "hasMembersMembership"), membership))
    outcome = execute_question("How many committees was Timmy Dooley a member of?", as_of=AS_OF,
                               fuseki=fixture, supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "source_data_unavailable"
    assert "exact zero" in outcome.diagnostic


def test_q15_distinguishes_current_open_term_from_missing_end_dates():
    outcome, _ = _run("When did each Dáil start and finish?")
    assert outcome.status == "success"
    assert outcome.result.rows == (
        ("32nd Dáil", "2016-02-03", "2020-02-07"),
        ("33rd Dáil", "2020-02-08", "2024-11-08"),
        ("34th Dáil", "2024-11-29", "Current term (open end)"),
    )


def test_q32_candidates_have_distinct_house_and_membership_date_context():
    outcome, _ = _run("Who is Michael Collins?")
    assert outcome.status == "ambiguous"
    assert len(outcome.candidates) == 2
    assert "203" not in repr(outcome.candidates)
    assert "2020-02-08" in repr(outcome.result.rows) and "2020-06-29" in repr(outcome.result.rows)


def test_q32_and_q33_full_names_do_not_use_loose_substring_identity():
    fixture = StageAFixture()
    fixture.add_member("collins-junior", "Michael Collins Junior")
    exact, _ = _run("Who is Michael Collins?", fixture)
    listed, _ = _run("Which Members named Michael Collins served in the Dáil?", fixture)
    assert exact.status == "ambiguous" and len(exact.candidates) == 2
    assert listed.status == "success" and len(listed.result.rows) == 1


def test_q33_returns_all_matching_dail_member_identities_and_q34_is_not_found():
    listed, _ = _run("Which Members named Michael Collins served in the Dáil?")
    missing, _ = _run("What is the full name of Niamh Example?")
    assert listed.status == "success"
    assert listed.result.rows == (("Michael Collins", "33rd Dáil"),)
    assert missing.status == "not_found"


@pytest.mark.parametrize("question", [
    "Find Deputy Ó Snodaigh's full name for me.",
    "Was Aengus Ó Snodaigh a TD in the previous Dáil term?",
    "How long was Micheál Martin a Deputy?",
    "How many Dáil terms has Micheál Martin served in?",
    "When did Timmy Dooley become a Senator?",
    "What party is Senator Chris Andrews a member of?",
    "What party does Michael Lowry belong to now?",
    "Which panel did Timmy Dooley represent in the 26th Seanad?",
    "Was Timmy Dooley a member of the Select Committee on Transport and Communications?",
    "How many committees was Timmy Dooley a member of?",
    "When did each Dáil start and finish?",
    "How many Dáil terms are listed in the Houses data?",
    "Who is Michael Collins?",
    "Which Members named Michael Collins served in the Dáil?",
    "What is the full name of Niamh Example?",
])
def test_stage_a_questions_run_through_version_two_ask_route(monkeypatch, question):
    from poc.nlq import app as app_module

    fixture = StageAFixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": question, "mode": "phase2"})
    assert response.status_code == 200
    assert fixture.queries
    assert all(query.startswith("PREFIX") for query in fixture.queries)
    assert "previous Dáil" not in response.text or "previous Dáil" in question


@pytest.mark.parametrize("question,remove_committee_dates", [
    ("Was Timmy Dooley a member of the Unknown Committee?", False),
    ("Was Timmy Dooley a member of the Select Committee on Transport and Communications?", True),
])
def test_early_q11_diagnostics_render_without_false_summary_or_validated_plan(monkeypatch, question, remove_committee_dates):
    from poc.nlq import app as app_module
    fixture = StageAFixture()
    if remove_committee_dates:
        for triple in list(fixture.committees):
            if triple[1] == URIRef(MEMBERS + "hasCommitteeDateRange"):
                fixture.committees.remove(triple)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": question, "mode": "phase2"})
    assert response.status_code == 200
    assert "previous Dáil" not in response.text
    assert "No Committee owner resource" in response.text or "no complete date evidence" in response.text
    assert "Validated composable query plan" not in response.text
    assert "Draft plan — not validated" not in response.text


def test_q11_owner_catalogue_cap_is_visible_and_does_not_claim_plan_validation(monkeypatch):
    from poc.nlq import app as app_module
    fixture = StageAFixture()
    original_query = fixture.query
    def capped_query(query):
        if "SELECT DISTINCT ?committee ?label ?term ?start" in query:
            fixture.queries.append(query)
            return QueryResult("select", ("committee", "label", "term", "start", "end", "termStart", "termEnd"),
                               tuple((f"https://data.oireachtas.ie/ie/oireachtas/committee/{i}", "A Committee", "https://data.oireachtas.ie/ie/oireachtas/house/dail/34", "2024-01-01T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>", "—", "2024-01-01T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>", "—") for i in range(100)))
        return original_query(query)
    monkeypatch.setattr(fixture, "query", capped_query)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": "Was Timmy Dooley a member of the Select Committee on Transport and Communications?", "mode": "phase2"})
    assert "100-row cap" in response.text
    assert "previous Dáil" not in response.text
    assert "Validated composable query plan" not in response.text


def test_single_token_member_lookup_error_is_not_rendered_as_another_family(monkeypatch):
    from poc.nlq import app as app_module
    fixture = StageAFixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": "Who is Pat?", "mode": "phase2"})
    assert "single unqualified token is insufficient" in response.text
    assert "previous Dáil" not in response.text and "No constituency" not in response.text
    assert "Validated composable query plan" not in response.text


def test_stage_a_success_qualification_is_visible_in_ask_result_notice(monkeypatch):
    from poc.nlq import app as app_module
    fixture = StageAFixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": "How long was Micheál Martin a Deputy?", "mode": "phase2"})
    assert "does not certify complete lifetime history" in response.text


def test_stage_a_plans_validate_against_the_closed_v2_instance_schema():
    schema = __import__("json").loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for question in (
        "When did each Dáil start and finish?", "How many Dáil terms are listed in the Houses data?",
        "Find Deputy Ó Snodaigh's full name for me.", "Who is Michael Collins?",
        "What is the full name of Niamh Example?", "How long was Micheál Martin a Deputy?",
    ):
        outcome, _ = _run(question)
        assert validator.is_valid(outcome.plan), list(validator.iter_errors(outcome.plan))


def test_closed_family_validator_rejects_mutated_stage_a_referents_relations_and_answers():
    outcome, _ = _run("Was Aengus Ó Snodaigh a TD in the previous Dáil term?")
    plan = outcome.plan
    validate_plan(plan)
    for mutation in (
        lambda item: item["referents"].update(unrelated={"type": "Member"}),
        lambda item: item["relations"].append({"id": "r3", "fact": "member_has_membership", "from": "member", "to": "member"}),
        lambda item: item["answer"].update(display=["arbitrary"]),
        lambda item: item.update(constraints=[]),
    ):
        altered = __import__("copy").deepcopy(plan)
        mutation(altered)
        with pytest.raises(PlanError):
            validate_plan(altered)


def test_stage_a_validation_rejects_auxiliary_types_or_orphan_same_type_referents():
    import copy
    outcome, _ = _run("How many Dáil terms has Micheál Martin served in?")
    wrong_type = copy.deepcopy(outcome.plan)
    wrong_type["referents"]["membership"]["type"] = "SeanadMembership"
    orphan = copy.deepcopy(outcome.plan)
    orphan["referents"]["extraTerm"] = {"type": "DailTerm"}
    wrong_endpoint = copy.deepcopy(outcome.plan)
    wrong_endpoint["relations"][0]["from"], wrong_endpoint["relations"][0]["to"] = "term", "member"
    for altered in (wrong_type, orphan, wrong_endpoint):
        with pytest.raises(PlanError):
            validate_plan(altered)


def test_unresolved_stage_a_identity_cannot_retain_a_selected_iri():
    import copy
    outcome, _ = _run("What is the full name of Niamh Example?")
    altered = copy.deepcopy(outcome.plan)
    altered["referents"]["member"]["iri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/other"
    with pytest.raises(PlanError):
        validate_plan(altered)


@pytest.mark.parametrize("mutation", ["unqueryable", "predicate", "cross_join"])
def test_stage_a_required_pattern_contract_removal_fails_before_query(monkeypatch, mutation):
    import copy
    import poc.nlq.stage_a as stage_a

    contract = copy.deepcopy(stage_a.load_query_contract())
    if mutation == "unqueryable":
        next(item for item in contract["emittedRdfPatterns"] if item["id"] == "member-house-membership")["queryableInLocalNlq"] = False
    elif mutation == "predicate":
        contract["queryableProperties"].remove("members:inHouseTerm")
    else:
        contract["crossGraphJoins"] = [item for item in contract["crossGraphJoins"] if item.get("predicate") != "members:inHouseTerm"]
    monkeypatch.setattr(stage_a, "load_query_contract", lambda: contract)
    fixture = StageAFixture()
    outcome, _ = _run("How long was Micheál Martin a Deputy?", fixture)
    assert outcome.status == "unsupported_mapping"
    assert not fixture.queries


def test_domain_role_question_is_not_misrouted_to_member_lookup():
    assert parse_stage_a_question("Who is the current Taoiseach?") is None
