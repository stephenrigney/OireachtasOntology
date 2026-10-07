from __future__ import annotations

import asyncio
from html import unescape
from pathlib import Path
import unicodedata

import httpx
from poc.nlq import app as app_module
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.llm import Translation
from poc.nlq.pipeline import process_question
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
PREDICATES = supported_predicates(ROOT / "ontology")


class CapturedMemberFuseki:
    """Small mock of captured local RDF for the exact identity examples."""

    MEMBERS = {
        "Michael Collins": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1919-01-21",
                "Michael-Collins.D.1919-01-21",
                ("1st Dáil", "2nd Dáil", "3rd Dáil"),
                ("Armagh", "Cork Mid, North, South, South East and West", "Cork South"),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26",
                "Michael-Collins.D.1997-06-26",
                ("28th Dáil", "29th Dáil"),
                ("Limerick West",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03",
                "Michael-Collins.D.2016-10-03",
                ("32nd Dáil", "33rd Dáil", "34th Dáil"),
                ("Cork South-West",),
            ),
        ),
        "Cathy Honan": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1965-06-23",
                "Cathy-Honan.S.1965-06-23",
                ("11th Seanad", "12th Seanad"),
                ("Industrial and Commercial Panel",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1982-05-13",
                "Cathy-Honan.S.1982-05-13",
                ("16th Seanad",),
                ("Administrative Panel",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1997-01-28",
                "Cathy-Honan.S.1997-01-28",
                ("20th Seanad",),
                ("Industrial and Commercial Panel",),
            ),
        ),
        "Micheál Martin": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Micheál-Martin.D.1989-06-29",
                "Micheál-Martin.D.1989-06-29",
                ("26th Dáil", "27th Dáil", "28th Dáil", "29th Dáil", "30th Dáil",
                 "31st Dáil", "32nd Dáil", "33rd Dáil", "34th Dáil"),
                ("Cork South-Central",),
            ),
        ),
        "Timmy Dooley": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12",
                "Timmy-Dooley.S.2002-09-12",
                ("22nd Seanad", "26th Seanad", "30th Dáil", "31st Dáil", "32nd Dáil", "34th Dáil"),
                ("Clare", "Nominated by the Taoiseach"),
            ),
        ),
    }

    def __init__(self):
        self.resolution_queries: list[str] = []
        self.context_queries: list[str] = []
        self.answer_queries: list[str] = []

    def readiness(self):
        return FusekiReadiness(
            "ready", True,
            (("Houses", True), ("Parties", True), ("Constituencies", True),
             ("Members", True), ("Bills", False)),
            "Required local graph families are present.",
        )

    def query(self, sparql: str) -> QueryResult:
        if "?question" in sparql and "foaf:name ?name" in sparql:
            self.resolution_queries.append(sparql)
            matches = [name for name in self.MEMBERS if name.casefold() in sparql.casefold()]
            return QueryResult(
                kind="select",
                columns=("member", "name", "memberCode"),
                rows=tuple((iri, name, code) for name in matches
                           for iri, code, _terms, _representations in self.MEMBERS[name]),
            )

        if "VALUES ?member" in sparql:
            self.context_queries.append(sparql)
            candidate = next(
                candidate
                for members in self.MEMBERS.values()
                for candidate in members
                if f"<{candidate[0]}>" in sparql
            )
            rows = tuple(
                ("house_term", label + "@en") for label in candidate[2]
            ) + tuple(
                ("representation", label + "@en") for label in candidate[3]
            )
            return QueryResult(
                kind="select", columns=("contextType", "contextLabel"), rows=rows,
            )

        self.answer_queries.append(sparql)
        if '"Michael Collins"' in sparql and '"28th Dáil"' in sparql:
            values = ("Michael Collins",)
        elif '"Michael Collins"' in sparql:
            values = ("Michael Collins", "Michael Collins", "Michael Collins")
        elif '"Cathy Honan"' in sparql:
            values = ("Cathy Honan", "Cathy Honan", "Cathy Honan")
        elif '"Micheál Martin"' in sparql:
            values = ("Micheál Martin",)
        elif '"Timmy Dooley"' in sparql:
            values = ("Timmy Dooley",)
        elif "Martin" in sparql:
            values = ("Martin Brady", "Martin Heydon")
        elif "FILTER(false)" in sparql:
            values = ()
        else:
            values = ("A local answer",)
        return QueryResult(
            kind="select", columns=("name",), rows=tuple((value,) for value in values),
        )

    def close(self):
        pass


class FixedTranslator:
    def __init__(self, query: str | None = None):
        self.query = query or (
            'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
            'SELECT ?name WHERE { ?member foaf:name ?name } LIMIT 10'
        )
        self.calls = 0

    def translate(self, question, _schema):
        self.calls += 1
        return Translation(f"Query for: {question}", self.query)

    def close(self):
        pass


def _run(question: str, fuseki: CapturedMemberFuseki, translator: FixedTranslator):
    return process_question(
        question,
        translator=translator,
        fuseki_factory=lambda: fuseki,
        schema_context="local test schema",
        supported_predicates=PREDICATES,
    )


def test_exact_member_name_that_resolves_uniquely_continues_normally():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
        'SELECT ?name WHERE { ?member foaf:name ?name . FILTER(?name = "Timmy Dooley") } LIMIT 10'
    )

    outcome = _run("Who is Timmy Dooley?", fuseki, translator)

    assert outcome.error is None
    assert outcome.ambiguity is None
    assert outcome.result.rows == (("Timmy Dooley",),)
    assert translator.calls == 1
    assert len(fuseki.resolution_queries) == 1
    assert len(fuseki.answer_queries) == 1


def test_exact_duplicate_name_returns_explicit_candidates_without_selecting_one():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator()

    outcome = _run("Who is Michael Collins?", fuseki, translator)

    assert outcome.error is None
    assert outcome.result is None
    assert outcome.validated_sparql is None
    assert outcome.ambiguity is not None
    assert outcome.ambiguity.entity_reference == "Michael Collins"
    assert len(outcome.ambiguity.candidates) == 3
    assert len({candidate.member_iri for candidate in outcome.ambiguity.candidates}) == 3
    assert all(candidate.name == "Michael Collins" for candidate in outcome.ambiguity.candidates)
    assert tuple(candidate.house_terms for candidate in outcome.ambiguity.candidates) == (
        ("1st Dáil", "2nd Dáil", "3rd Dáil"),
        ("28th Dáil", "29th Dáil"),
        ("32nd Dáil", "33rd Dáil", "34th Dáil"),
    )
    assert outcome.ambiguity.candidates[1].representations == ("Limerick West",)
    assert translator.calls == 0
    assert fuseki.answer_queries == []


def test_exact_duplicate_can_be_resolved_by_explicit_local_term_context():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
        'PREFIX skos: <http://www.w3.org/2004/02/skos/core#> '
        'SELECT ?name WHERE { GRAPH ?memberGraph { ?member foaf:name ?name } '
        'GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel '
        '. FILTER(STR(?termLabel) = "28th Dáil") } FILTER(?name = "Michael Collins") } LIMIT 10'
    )

    outcome = _run("What did Michael Collins do in the 28th Dáil?", fuseki, translator)

    assert outcome.error is None
    assert outcome.ambiguity is None
    assert outcome.result.rows == (("Michael Collins",),)
    assert len(fuseki.context_queries) == 3
    assert translator.calls == 1


def test_explicit_plural_name_question_is_not_mistaken_for_one_entity_ambiguity():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
        'SELECT ?name WHERE { ?member foaf:name ?name . FILTER(?name = "Michael Collins") } LIMIT 10'
    )

    outcome = _run("List all Members named Michael Collins.", fuseki, translator)

    assert outcome.error is None
    assert outcome.ambiguity is None
    assert outcome.result.rows == (("Michael Collins",),) * 3
    assert translator.calls == 1
    assert len(fuseki.answer_queries) == 1


def test_partial_set_valued_martin_question_continues_as_an_ordinary_query():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
        'SELECT ?name WHERE { ?member foaf:name ?name . FILTER(CONTAINS(STR(?name), "Martin")) } LIMIT 10'
    )

    outcome = _run("Which Martin served in the Dáil?", fuseki, translator)

    assert outcome.error is None
    assert outcome.ambiguity is None
    assert outcome.result.rows == (("Martin Brady",), ("Martin Heydon",))
    assert translator.calls == 1
    assert fuseki.context_queries == []


def test_diacritic_preserving_name_match_accepts_canonical_unicode_but_not_accent_folding():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        'PREFIX foaf: <http://xmlns.com/foaf/0.1/> '
        'SELECT ?name WHERE { ?member foaf:name ?name . FILTER(?name = "Micheál Martin") } LIMIT 10'
    )

    decomposed = unicodedata.normalize("NFD", "Who is Micheál Martin?")
    outcome = _run(decomposed, fuseki, translator)

    assert outcome.ambiguity is None
    assert outcome.result.rows == (("Micheál Martin",),)
    assert "Micheál Martin" in fuseki.resolution_queries[0]

    no_fada_fuseki = CapturedMemberFuseki()
    no_fada = _run("Who is Micheal Martin?", no_fada_fuseki, FixedTranslator())
    assert no_fada.ambiguity is None
    assert no_fada.result.rows == (("A local answer",),)
    assert "Micheál Martin" not in no_fada_fuseki.resolution_queries[0]


def test_zero_member_matches_remain_distinct_from_an_ambiguity():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator('SELECT ?name WHERE { FILTER(false) } LIMIT 10')

    outcome = _run("Who is Nobody Example?", fuseki, translator)

    assert outcome.error is None
    assert outcome.ambiguity is None
    assert outcome.result is not None and outcome.result.rows == ()
    assert translator.calls == 1


def test_query_safety_still_applies_after_a_unique_local_name_match():
    fuseki = CapturedMemberFuseki()
    translator = FixedTranslator(
        "SELECT ?name WHERE { SERVICE <https://example.test/sparql> "
        "{ ?member <urn:name> ?name } }"
    )

    outcome = _run("Who is Timmy Dooley?", fuseki, translator)

    assert outcome.ambiguity is None
    assert outcome.error is not None
    assert outcome.error_phase == "SPARQL validation"
    assert "SERVICE clauses are not allowed" in str(outcome.error)
    assert fuseki.answer_queries == []


def test_browser_uses_shared_ambiguity_outcome_and_exposes_only_local_context(monkeypatch):
    fuseki = CapturedMemberFuseki()

    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, *_args):
            raise AssertionError("ambiguous Member references must stop before translation")

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fuseki)

    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is Michael Collins?"})

    response = asyncio.run(post_question())
    page = unescape(response.text)

    assert response.status_code == 200
    assert "More than one local Member record matches" in page
    assert "I have not selected one" in page
    assert "28th Dáil" in page
    assert "Limerick West" in page
    assert "Generated SPARQL" not in page
    assert "Local Member resolution evidence" in page
    assert '"status": "ambiguous"' in page
    assert "Michael-Collins.D.1997-06-26" in page
    assert "No answer query was sent to Fuseki" in page
    assert "<p class=\"error\"" not in page
