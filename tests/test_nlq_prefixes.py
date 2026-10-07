from __future__ import annotations

from pathlib import Path

import pytest
from pyparsing import ParseResults
from rdflib import URIRef
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue

from poc.nlq.contract import load_query_contract
from poc.nlq.errors import NLQError
from poc.nlq.llm import Translation
from poc.nlq.results import QueryResult
from poc.nlq.pipeline import process_question
from poc.nlq import pipeline as pipeline_module
from poc.nlq.safety import complete_known_prefixes, validate_sparql
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_query_contract()
NAMESPACES = CONTRACT["namespaces"]
PREDICATES = supported_predicates(ROOT / "ontology")


def _walk(value):
    if isinstance(value, CompValue):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, (list, tuple, ParseResults)):
        for child in value:
            yield from _walk(child)


def test_one_missing_known_prefix_is_completed_from_contract():
    query = "SELECT ?membership WHERE { ?member members:hasMembersMembership ?membership }"

    completed = complete_known_prefixes(query)

    assert completed == (
        f"PREFIX members: <{NAMESPACES['members']}>\n" + query
    )
    assert validate_sparql(completed, supported_predicates=PREDICATES).endswith("LIMIT 100")


def test_several_missing_known_prefixes_are_completed_once_and_deterministically():
    query = (
        "SELECT ?label WHERE { ?term a agents:DailTerm ; agents:termOf ?house ; "
        "skos:prefLabel ?label . ?member members:hasMembersMembership ?membership }"
    )

    completed = complete_known_prefixes(query)

    declarations = [line for line in completed.splitlines() if line.startswith("PREFIX ")]
    assert [line.split()[1].removesuffix(":") for line in declarations] == [
        "agents", "members", "skos",
    ]
    assert validate_sparql(completed, supported_predicates=PREDICATES)


def test_declared_and_missing_prefixes_are_mixed_without_duplicate_declarations():
    query = (
        f"PREFIX members: <{NAMESPACES['members']}>\n"
        "SELECT ?label WHERE { ?collection members:memberOfCollection ?member ; "
        "skos:prefLabel ?label }"
    )

    completed = complete_known_prefixes(query)

    assert completed.startswith(
        f"PREFIX skos: <{NAMESPACES['skos']}>\nPREFIX members: <{NAMESPACES['members']}>\n"
    )
    assert completed.count("PREFIX members:") == 1
    assert validate_sparql(completed, supported_predicates=PREDICATES)


def test_existing_prefix_binding_is_never_rewritten_from_the_contract():
    query = (
        "PREFIX members: <urn:model-supplied:>\n"
        "SELECT ?value WHERE { ?subject members:someProperty ?value }"
    )

    assert complete_known_prefixes(query) == query
    with pytest.raises(NLQError, match="not declared by the ontology or active mappings"):
        validate_sparql(query, supported_predicates=PREDICATES)


def test_query_with_all_required_prefixes_is_left_unchanged():
    query = (
        f"PREFIX agents: <{NAMESPACES['agents']}>\n"
        f"PREFIX members: <{NAMESPACES['members']}>\n"
        f"PREFIX skos: <{NAMESPACES['skos']}>\n"
        "SELECT ?label WHERE { ?member a agents:Member ; "
        "members:hasMembersMembership ?membership . ?membership skos:prefLabel ?label }"
    )

    assert complete_known_prefixes(query) == query
    assert validate_sparql(query, supported_predicates=PREDICATES).startswith(query)


def test_unknown_undeclared_prefix_is_not_completed_and_still_fails_closed():
    query = "SELECT ?value WHERE { ?subject mystery:unsupportedProperty ?value }"

    assert complete_known_prefixes(query) == query
    with pytest.raises(NLQError, match="prefix 'mystery' is undeclared"):
        validate_sparql(complete_known_prefixes(query), supported_predicates=PREDICATES)


def test_unknown_undeclared_prefix_in_a_non_predicate_position_still_fails_closed():
    query = "SELECT ?subject WHERE { ?subject rdf:type mystery:UnsupportedClass }"

    completed = complete_known_prefixes(query)

    assert f"PREFIX rdf: <{NAMESPACES['rdf']}>" in completed
    assert "PREFIX mystery:" not in completed
    with pytest.raises(NLQError, match="prefix 'mystery' is undeclared"):
        validate_sparql(completed, supported_predicates=PREDICATES)


def test_prefix_like_text_in_literals_comments_and_absolute_iris_is_not_completed():
    query = (
        'SELECT ?member WHERE { ?member <urn:agents:Member> '
        '"agents:Member members:hasMembersMembership skos:prefLabel" } '
        '# foaf:name members:inHouseTerm\n'
    )

    assert complete_known_prefixes(query) == query
    assert validate_sparql(query)


def test_malformed_or_incomplete_qname_is_left_for_normal_parser_rejection():
    query = "SELECT ?membership WHERE { ?member members:hasMembersMembership"

    assert complete_known_prefixes(query) == query
    with pytest.raises(NLQError, match="malformed"):
        validate_sparql(complete_known_prefixes(query))


@pytest.mark.parametrize(("query", "message"), [
    (
        "SELECT ?member WHERE { SERVICE <https://example.test/sparql> "
        "{ ?member members:hasMembersMembership ?membership } }",
        "SERVICE clauses are not allowed",
    ),
    (
        "SELECT ?membership WHERE { ?member members:hasMembersMembership+ ?membership }",
        "property paths are not",
    ),
])
def test_completed_query_still_goes_through_normal_safety_rejections(
        monkeypatch, query, message):
    validation_inputs = []
    actual_validate = pipeline_module.validate_sparql

    def record_validation(sparql, **kwargs):
        validation_inputs.append(sparql)
        return actual_validate(sparql, **kwargs)

    monkeypatch.setattr(pipeline_module, "validate_sparql", record_validation)

    class Translator:
        def translate(self, _question, _schema):
            return Translation("Run a local query", query)

    class ResolutionOnlyFuseki:
        def query(self, sparql):
            assert "?question" in sparql
            return QueryResult(
                kind="select", columns=("member", "name", "memberCode"), rows=(),
            )

    outcome = process_question(
        "question", translator=Translator(), fuseki_factory=ResolutionOnlyFuseki,
        schema_context="schema", supported_predicates=PREDICATES,
    )

    assert validation_inputs[0].startswith(f"PREFIX members: <{NAMESPACES['members']}>\n")
    assert outcome.error_phase == "SPARQL validation"
    assert outcome.error is not None and message in str(outcome.error)
    assert outcome.result is None


# These are the eight generated queries recorded in the Phase 1B v0.2.0 run.
# Keeping them as regression inputs proves both the original direct-pattern
# diagnosis and the post-completion safety result without changing benchmark
# expectations or model translations.
PHASE_1B_FAILURES = (
    ("term.micheal-dail-34-membership", '''SELECT DISTINCT ?termLabel WHERE {
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?membership .
    ?membership rdf:type members:DailMembership ;
                members:inHouseTerm ?term .
    FILTER(?name = "Micheál Martin")
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term rdf:type agents:DailTerm ;
          skos:prefLabel ?termLabel .
  }
}
LIMIT 100'''),
    ("collection.timmy-dail-34", '''SELECT DISTINCT ?collectionLabel
WHERE {
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?membership .
    ?membership rdf:type members:OireachtasMembership, members:DailMembership ;
                members:inHouseTerm ?term .
    ?collectionMembership members:inOireachtasMembership ?membership ;
                          members:memberOfCollection ?collection .
    FILTER(?name = "Timmy Dooley")
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?termLabel .
    FILTER(STR(?termLabel) = "34th Dáil")
  }
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?collection skos:prefLabel ?collectionLabel .
  }
}
LIMIT 100'''),
    ("representation.timmy-seanad-26-panel", '''SELECT DISTINCT ?panelLabel WHERE {
  BIND("Timmy Dooley" AS ?memberName)
  BIND("26th Seanad" AS ?termName)
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?membership .
    ?membership rdf:type members:SeanadMembership ;
                members:inHouseTerm ?term ;
                members:isRepresentativeFrom ?panel .
    FILTER(STR(?name) = ?memberName)
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?termLabel .
    FILTER(CONTAINS(LCASE(STR(?termLabel)), LCASE(?termName)))
  }
  GRAPH <https://data.oireachtas.ie/graph/constituencies> {
    ?panel skos:prefLabel ?panelLabel .
  }
}
LIMIT 100'''),
    ("representation.aidan-seanad-26-panel", '''SELECT DISTINCT ?panelLabel WHERE {
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?membership .
    ?membership rdf:type members:SeanadMembership ;
                members:inHouseTerm ?term ;
                members:isRepresentativeFrom ?panel .
    FILTER(?name = "Aidan Davitt")
  }
  FILTER(STRSTARTS(STR(?memberGraph), "https://data.oireachtas.ie/graph/member/"))
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term rdf:type agents:SeanadTerm ;
          skos:prefLabel ?termLabel .
    FILTER(STR(?termLabel) = "26th Seanad")
  }
  GRAPH <https://data.oireachtas.ie/graph/constituencies> {
    ?panel rdf:type members:SeanadPanel ;
           skos:prefLabel ?panelLabel ;
           members:constituencyInHouseTerm ?term .
  }
}
LIMIT 100'''),
    ("committee.timmy-committee-count", '''SELECT (COUNT(DISTINCT ?committee) AS ?committeeCount)
WHERE {
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?termMembership,
                                    ?committeeMembership .
    FILTER(?name = "Timmy Dooley")
    ?termMembership rdf:type members:SeanadMembership ;
                    members:inHouseTerm ?term .
    ?committeeMembership rdf:type members:CommitteeMembership ;
                         members:isCommitteeMembershipOf ?committee .
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?termLabel .
    FILTER(STR(?termLabel) = "26th Seanad")
  }
  GRAPH <https://data.oireachtas.ie/graph/committees> {
    ?committee rdf:type members:Committee ;
               members:committeeInHouseTerm ?term .
  }
}
LIMIT 100'''),
    ("date.timmy-seanad-26-start", '''SELECT DISTINCT ?startDate WHERE {
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            foaf:name ?name ;
            members:hasMembersMembership ?membership .
    FILTER(?name = "Timmy Dooley")
    ?membership rdf:type members:OireachtasMembership,
                         members:SeanadMembership ;
                members:inHouseTerm ?term ;
                members:hasMembershipDateRange ?dateRange .
    ?dateRange rdf:type members:DateRange ;
               members:StartDate ?startDate .
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?termLabel .
  }
  BIND("26th Seanad" AS ?requestedLabel)
  FILTER(STR(?termLabel) = ?requestedLabel)
}
LIMIT 100'''),
    ("date.timmy-seanad-26-end", '''SELECT DISTINCT ?endDate WHERE {
  GRAPH ?memberGraph {
    ?member a agents:Member ;
            foaf:name "Timmy Dooley" ;
            members:hasMembersMembership ?membership .
    ?membership a members:SeanadMembership ;
                members:inHouseTerm ?term ;
                members:hasMembershipDateRange ?dateRange .
    ?dateRange a members:DateRange ;
               members:EndDate ?endDate .
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term a agents:SeanadTerm ;
          skos:prefLabel ?termLabel .
  }
  BIND("26th Seanad" AS ?requestedTermLabel)
  FILTER(STR(?termLabel) = ?requestedTermLabel)
}
LIMIT 100'''),
    ("aggregate.dail-33-collection-counts", '''SELECT ?collection ?collectionLabel (COUNT(DISTINCT ?member) AS ?memberCount)
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term rdf:type agents:DailTerm ;
          skos:prefLabel ?termLabel .
    FILTER(STR(?termLabel) = "33rd Dáil")
  }
  GRAPH ?memberGraph {
    ?member rdf:type agents:Member ;
            members:hasMembersMembership ?membership .
    ?membership rdf:type members:DailMembership ;
                members:inHouseTerm ?term .
    ?collectionMembership members:inOireachtasMembership ?membership ;
                          members:memberOfCollection ?collection .
  }
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?collection skos:prefLabel ?collectionLabel .
  }
}
GROUP BY ?collection ?collectionLabel
ORDER BY ?collectionLabel
LIMIT 100'''),
)


@pytest.mark.parametrize(("case_id", "query"), PHASE_1B_FAILURES)
def test_phase_1b_missing_prefix_failures_are_direct_patterns_and_validate_after_completion(
        case_id, query):
    nodes = tuple(_walk(parseQuery(query)))
    path_elements = [node for node in nodes if node.name == "PathElt"]
    assert path_elements, case_id
    assert not any(
        node.name in {"PathEltOrInverse", "PathNegatedPropertySet"}
        for node in nodes
    ), case_id
    assert not any(
        node.name in {"PathSequence", "PathAlternative"} and len(node["part"]) > 1
        for node in nodes if "part" in node
    ), case_id
    assert all(
        (isinstance(node["part"], URIRef)
         or isinstance(node["part"], CompValue) and node["part"].name == "pname")
        and "mod" not in node
        for node in path_elements
    ), case_id

    with pytest.raises(NLQError, match="prefix .* is undeclared"):
        validate_sparql(query, supported_predicates=PREDICATES)

    completed = complete_known_prefixes(query)
    assert all(
        f"PREFIX {prefix}: <{NAMESPACES[prefix]}>" in completed
        for prefix in {"agents", "members", "skos"}
        if any(node.name == "pname" and node.get("prefix") == prefix for node in nodes)
    ), case_id
    assert validate_sparql(completed, supported_predicates=PREDICATES)


def test_phase_1b_failure_shapes_use_only_contract_known_prefixes():
    used_prefixes = {
        node.get("prefix")
        for _, query in PHASE_1B_FAILURES
        for node in _walk(parseQuery(query))
        if node.name == "pname"
    }

    assert {"agents", "members", "skos", "foaf", "rdf"} <= used_prefixes
    assert used_prefixes <= NAMESPACES.keys()
