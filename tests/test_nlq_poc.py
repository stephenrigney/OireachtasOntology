"""Offline tests for the isolated natural-language query POC."""

from __future__ import annotations

import asyncio
from html import unescape
import json
import os
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from poc.nlq import app as app_module
from poc.nlq.config import load_local_environment
from poc.nlq.errors import NLQError
from poc.nlq.fuseki import FusekiQueryClient, FusekiReadiness
from poc.nlq.llm import ResponsesTranslator, Translation, parse_translation
from poc.nlq.results import QueryResult, parse_results
from poc.nlq.safety import MAX_RESULT_OFFSET, validate_sparql
from poc.nlq.schema import build_schema_context
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]


def test_local_dotenv_loads_nlq_settings_and_process_environment_wins(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "NLQ_LLM_API_KEY=file-key\nNLQ_LLM_BASE_URL=https://example.test/v1\nNLQ_LLM_MODEL=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("NLQ_LLM_API_KEY", raising=False)
    monkeypatch.delenv("NLQ_LLM_MODEL", raising=False)
    monkeypatch.setenv("NLQ_LLM_BASE_URL", "https://environment.test/v1")

    assert load_local_environment(tmp_path)
    assert os.environ["NLQ_LLM_API_KEY"] == "file-key"
    assert os.environ["NLQ_LLM_BASE_URL"] == "https://environment.test/v1"
    assert os.environ["NLQ_LLM_MODEL"] == "file-model"


def test_read_only_select_is_accepted_and_bounded():
    query = "SELECT ?member WHERE { ?member <urn:memberProperty> ?o }"
    assert validate_sparql(query) == query + "\nLIMIT 100"
    assert validate_sparql(query + " LIMIT 25") == query + " LIMIT 25"


def test_read_only_ask_is_accepted():
    query = "ASK { ?member <urn:memberProperty> ?o }"
    assert validate_sparql(query) == query


@pytest.mark.parametrize("query", [
    "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
    "DROP ALL",
    "CLEAR ALL",
    "LOAD <https://example.test/graph>",
])
def test_update_operations_are_rejected(query):
    with pytest.raises(NLQError):
        validate_sparql(query)


def test_other_read_query_forms_are_rejected():
    with pytest.raises(NLQError, match="SELECT and ASK"):
        validate_sparql("CONSTRUCT { ?s <urn:p> ?o } WHERE { ?s <urn:p> ?o }")


def test_service_and_dataset_overrides_are_rejected():
    with pytest.raises(NLQError, match="SERVICE"):
        validate_sparql("SELECT ?s WHERE { SERVICE <https://example.test/sparql> { ?s <urn:p> ?o } }")
    with pytest.raises(NLQError, match="FROM"):
        validate_sparql("SELECT ?s FROM <https://example.test/graph> WHERE { ?s <urn:p> ?o }")


def test_malformed_query_is_rejected():
    with pytest.raises(NLQError, match="malformed"):
        validate_sparql("SELECT ?s WHERE { ?s ?p")


def test_select_limits_over_the_cap_are_rejected():
    with pytest.raises(NLQError, match="100 rows"):
        validate_sparql("SELECT ?s WHERE { ?s <urn:p> ?o } LIMIT 101")


def test_select_without_limit_but_with_bounded_offset_gets_a_limit():
    assert validate_sparql("SELECT ?s WHERE { ?s <urn:p> ?o } OFFSET 25").endswith(
        "OFFSET 25\nLIMIT 100"
    )


def test_large_offsets_are_rejected_even_when_default_limit_would_be_added():
    with pytest.raises(NLQError, match=f"offsets may not exceed {MAX_RESULT_OFFSET}"):
        validate_sparql(f"SELECT ?s WHERE {{ ?s <urn:p> ?o }} OFFSET {MAX_RESULT_OFFSET + 1}")
    with pytest.raises(NLQError, match=f"offsets may not exceed {MAX_RESULT_OFFSET}"):
        validate_sparql(f"ASK {{ ?s <urn:p> ?o }} OFFSET {MAX_RESULT_OFFSET + 1}")


def test_subselects_are_rejected_to_prevent_hidden_intermediate_scans():
    query = "SELECT ?s WHERE { { SELECT ?s WHERE { ?s <urn:p> ?o } LIMIT 500 } } LIMIT 10"
    with pytest.raises(NLQError, match="subqueries are not allowed"):
        validate_sparql(query)


@pytest.mark.parametrize("path", [
    "<https://example.test/p>*",
    "<https://example.test/p>+",
    "<https://example.test/p>?",
    "^<https://example.test/p>",
    "!<https://example.test/p>",
    "<https://example.test/p>/<https://example.test/q>",
    "<https://example.test/p>|<https://example.test/q>",
])
def test_property_paths_are_rejected(path):
    with pytest.raises(NLQError, match="property path"):
        validate_sparql(f"SELECT ?s WHERE {{ ?s {path} ?o }}")


def test_direct_predicates_are_accepted():
    query = "SELECT ?name WHERE { ?member <http://xmlns.com/foaf/0.1/name> ?name } LIMIT 20"
    assert validate_sparql(query) == query


def test_predicates_are_checked_against_ontology_and_active_mappings():
    vocabulary = supported_predicates(ROOT / "ontology")
    assert URIRef("http://xmlns.com/foaf/0.1/name") in vocabulary
    assert URIRef("http://data.europa.eu/eli/ontology#title") in vocabulary
    assert URIRef("http://data.europa.eu/eli/eli-draft-legislation-ontology#forms_part_of") in vocabulary
    assert URIRef("http://www.w3.org/2002/07/owl#sameAs") in vocabulary
    query = "PREFIX members: <https://data.oireachtas.ie/ontology/members#> SELECT ?x WHERE { ?x members:memberOfCollection ?collection } LIMIT 10"
    assert validate_sparql(query, supported_predicates=vocabulary) == query
    invented = "SELECT ?x WHERE { ?x <https://data.oireachtas.ie/ontology/members#inventedPredicate> ?o }"
    with pytest.raises(NLQError, match="not declared by the ontology or active mappings"):
        validate_sparql(invented, supported_predicates=vocabulary)


def test_variable_predicates_are_rejected_as_unbounded_vocabulary_scans():
    with pytest.raises(NLQError, match="Variable predicates"):
        validate_sparql("SELECT ?s WHERE { ?s ?predicate ?o }")


def test_select_result_json_is_converted_with_columns_and_rdf_literal_hints():
    payload = {
        "head": {"vars": ["member", "name", "term"]},
        "results": {"bindings": [
            {
                "member": {"type": "uri", "value": "https://data.example/member/1"},
                "name": {"type": "literal", "xml:lang": "ga", "value": "Micheál"},
                "term": {"type": "literal", "datatype": "http://www.w3.org/2001/XMLSchema#integer", "value": "33"},
            },
            {"member": {"type": "bnode", "value": "record"}},
        ]},
    }
    result = parse_results(payload)
    assert result.kind == "select"
    assert result.columns == ("member", "name", "term")
    assert result.rows == (
        ("https://data.example/member/1", "Micheál@ga", "33^^<http://www.w3.org/2001/XMLSchema#integer>"),
        ("_:record", "—", "—"),
    )
    assert json.loads(result.raw_json) == payload


def test_ask_result_json_is_converted():
    yes = parse_results({"head": {}, "boolean": True})
    no = parse_results({"head": {}, "boolean": False})
    assert yes.kind == "ask" and yes.boolean is True
    assert no.boolean is False
    assert json.loads(yes.raw_json) == {"head": {}, "boolean": True}


def test_mocked_fuseki_select_and_ask_responses_are_handled():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert request.url.path == "/houses/query"
        assert request.headers["accept"] == "application/sparql-results+json"
        query = parse_qs(request.content.decode())["query"][0]
        if query.lstrip().startswith("ASK"):
            body = {"head": {}, "boolean": True}
        else:
            body = {"head": {"vars": ["member"]}, "results": {"bindings": [
                {"member": {"type": "uri", "value": "https://data.example/member/1"}},
            ]}}
        return httpx.Response(200, json=body)

    client = FusekiQueryClient(
        "http://fuseki.test/houses/query", transport=httpx.MockTransport(handler)
    )
    try:
        select = client.query("SELECT ?member WHERE { ?member <urn:memberProperty> ?o } LIMIT 10")
        ask = client.query("ASK { ?s <urn:memberProperty> ?o }")
    finally:
        client.close()
    assert select.columns == ("member",)
    assert select.rows == (("https://data.example/member/1",),)
    assert json.loads(select.raw_json)["results"]["bindings"][0]["member"]["value"] == "https://data.example/member/1"
    assert ask.kind == "ask" and ask.boolean is True
    assert len(calls) == 2


def test_fuseki_client_rejects_non_query_urls():
    with pytest.raises(NLQError, match="/query endpoint"):
        FusekiQueryClient("http://fuseki.test/houses/update")


def test_fuseki_http_error_exposes_json_payload_for_debugging():
    client = FusekiQueryClient(
        "http://fuseki.test/houses/query",
        transport=httpx.MockTransport(lambda _: httpx.Response(
            400, json={"error": "bad query", "detail": "syntax error"}
        )),
    )
    try:
        with pytest.raises(NLQError, match="HTTP 400") as error:
            client.query("SELECT ?x WHERE { broken }")
    finally:
        client.close()
    assert json.loads(error.value.debug_output) == {"error": "bad query", "detail": "syntax error"}


def test_fuseki_readiness_is_read_only_and_reports_partial_graphs():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert request.url.path == "/houses/query"
        query = parse_qs(request.content.decode())["query"][0]
        if query.lstrip().startswith("ASK"):
            return httpx.Response(200, json={"head": {}, "boolean": True})
        assert "SELECT DISTINCT ?source" in query
        assert "INSERT" not in query.upper() and "DROP" not in query.upper()
        return httpx.Response(200, json={
            "head": {"vars": ["source"]},
            "results": {"bindings": [
                {"source": {"type": "literal", "value": "Houses"}},
                {"source": {"type": "literal", "value": "Members"}},
            ]},
        })

    client = FusekiQueryClient(
        "http://fuseki.test/houses/query", transport=httpx.MockTransport(handler)
    )
    try:
        readiness = client.readiness()
    finally:
        client.close()
    assert readiness.state == "partial"
    assert readiness.has_triples is True
    assert dict(readiness.sources) == {
        "Houses": True, "Parties": False, "Constituencies": False, "Members": True, "Bills": False,
    }
    assert "missing: Parties, Constituencies" in readiness.message
    assert len(calls) == 2


def test_fuseki_readiness_recognizes_an_empty_named_dataset():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert request.url.path == "/houses/query"
        query = parse_qs(request.content.decode())["query"][0]
        assert query.lstrip().startswith("ASK")
        return httpx.Response(200, json={"head": {}, "boolean": False})

    client = FusekiQueryClient(
        "http://fuseki.test/houses/query", transport=httpx.MockTransport(handler)
    )
    try:
        readiness = client.readiness()
    finally:
        client.close()
    assert readiness.state == "empty"
    assert readiness.has_triples is False
    assert not any(present for _, present in readiness.sources)
    assert len(calls) == 1


def test_malformed_llm_output_has_a_controlled_error():
    with pytest.raises(NLQError, match="invalid JSON"):
        parse_translation("not JSON")
    with pytest.raises(NLQError, match="non-empty"):
        parse_translation(json.dumps({"interpretation": "Find members", "sparql": ""}))


def test_responses_translator_parses_mocked_structured_output():
    output = json.dumps({"interpretation": "Find Dáil members", "sparql": "SELECT ?m WHERE { ?m <urn:memberProperty> ?o }"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["user-agent"] == "oireachtas-nlq-poc/0.1"
        assert request.headers["x-opencode-session"]
        body = json.loads(request.content)
        assert body["text"]["format"]["type"] == "json_schema"
        assert "agents:Member" in body["instructions"]
        return httpx.Response(200, json={"status": "completed", "output_text": output})

    translator = ResponsesTranslator(
        "test-key", "https://llm.example/v1", "test-model", transport=httpx.MockTransport(handler)
    )
    try:
        assert translator.translate("Who were the members?", "agents:Member") == Translation(
            "Find Dáil members", "SELECT ?m WHERE { ?m <urn:memberProperty> ?o }"
        )
    finally:
        translator.close()


def test_responses_translator_reports_bad_model_json_as_controlled_error():
    translator = ResponsesTranslator(
        "test-key", "https://llm.example/v1", "test-model",
        transport=httpx.MockTransport(lambda _: httpx.Response(
            200, json={"status": "completed", "output_text": "not JSON"}
        )),
    )
    try:
        with pytest.raises(NLQError, match="invalid JSON") as error:
            translator.translate("question", "schema")
        assert error.value.debug_source == "LLM API"
        assert json.loads(error.value.debug_output) == {"status": "completed", "output_text": "not JSON"}
    finally:
        translator.close()


def test_responses_translator_gives_safe_actionable_401_error():
    translator = ResponsesTranslator(
        "test-key", "https://llm.example/v1", "test-model",
        transport=httpx.MockTransport(lambda _: httpx.Response(
            401, json={"error": {"message": "Invalid key: test-key"}}
        )),
    )
    try:
        with pytest.raises(NLQError, match="NLQ_LLM_API_KEY") as error:
            translator.translate("question", "schema")
        assert error.value.debug_source == "LLM API"
        debug = json.loads(error.value.debug_output)
        assert debug["error"]["message"] == "Invalid key: [REDACTED]"
        assert "test-key" not in error.value.debug_output
    finally:
        translator.close()


def test_home_page_displays_empty_readiness_and_says_loading_is_manual(monkeypatch):
    class EmptyFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness(
                "empty", False,
                (("Houses", False), ("Parties", False), ("Constituencies", False),
                 ("Members", False), ("Bills", False)),
                "Fuseki is reachable, but no triples were found in its named graphs. The POC does not load or rebuild data automatically.",
            )

        def close(self):
            pass

    monkeypatch.setattr(app_module, "FusekiQueryClient", EmptyFuseki)

    async def get_home():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/")

    response = asyncio.run(get_home())
    assert response.status_code == 200
    assert "Fuseki readiness" in response.text
    assert "Empty:" in response.text
    assert "The POC does not load or rebuild data automatically" in response.text
    assert "Houses: not detected" in response.text


def test_home_page_reports_unavailable_fuseki_without_claiming_graphs_are_missing(monkeypatch):
    class UnavailableFuseki:
        def __init__(self, *args, **kwargs):
            raise NLQError("Fuseki query timed out.")

    monkeypatch.setattr(app_module, "FusekiQueryClient", UnavailableFuseki)

    async def get_home():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/")

    response = asyncio.run(get_home())
    assert response.status_code == 200
    assert "Unavailable:" in response.text
    assert "Could not check Fuseki readiness: Fuseki query timed out." in response.text
    assert "Houses: unknown" in response.text


def test_schema_context_comes_from_real_member_and_agent_ontology():
    context = build_schema_context(ROOT / "ontology")
    assert "agents:Member" in context
    assert "agents:House" in context
    assert "members:OireachtasMembership" in context
    assert "members:ParliamentaryParty" in context
    assert "members:IndependentMemberCollection" in context
    assert "members:memberOfCollection" in context
    assert "members:inOireachtasMembership" in context
    assert "members:OfficeHolding" in context
    assert "office-type-vocabulary [ontology-only-not-queryable]" in context
    assert "members:hasMinisterOfStateRole (" not in context
    assert "members:officeNameUri (" not in context
    assert "foaf:name" in context and "skos:prefLabel" in context
    assert "Micheál Martin" not in context
    assert "eli-dl:LegislativeProcess" in context
    assert "agents:DailTerm" in context
    assert "agents:HouseTerm" in context
    assert "eli-dl:DraftLegislationWork" in context
    assert "eli:title (DatatypeProperty)" in context
    assert "eli-dl:process_status (ObjectProperty)" in context
    assert "eli-dl:forms_part_of" in context
    assert "foaf:firstName (AnnotationProperty)" in context
    assert "graph/houses" in context
    assert "graph/parties" in context
    assert "graph/constituencies" in context
    assert "graph/committees" in context
    assert "graph/administrative-units" in context and "graph/offices" in context
    assert "graph/member/{percent-encoded-memberCode}" in context
    assert "member-external-links" in context and "optional-reviewed-links" in context
    assert "OWL entailment=none" in context
    assert "DailTerm: skos:prefLabel (language: en)" in context
    assert "Independent records must use members:memberOfCollection" in context
    assert "older published Member graphs may omit that explicit type" in context
    assert "require accepted office resolution" in context
    assert "not executable through the current local NLQ predicate allowlist" in context
    assert "Reviewed Wikidata Q-item" in context
    assert "ns1:" not in context
    assert len(context) < 48_000

    house_fixture = Graph().parse(ROOT / "tests/expected/houses.ttl", format="turtle")
    dail_33 = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33")
    assert (dail_33, RDF.type, URIRef("https://data.oireachtas.ie/ontology#DailTerm")) in house_fixture
    assert (dail_33, RDF.type, URIRef("https://data.oireachtas.ie/ontology#HouseTerm")) not in house_fixture

    parties_fixture = Graph().parse(ROOT / "tests/expected/parties.ttl", format="turtle")
    independent = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent")
    assert (independent, RDF.type, URIRef("https://data.oireachtas.ie/ontology/members#IndependentMemberCollection")) in parties_fixture
    assert (independent, RDF.type, URIRef("https://data.oireachtas.ie/ontology/members#ParliamentaryParty")) not in parties_fixture


def test_browser_renders_result_and_exact_sparql(monkeypatch):
    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, question, schema):
            return Translation("Find the requested member", "SELECT ?name WHERE { ?m foaf:name ?name }")

        def close(self):
            pass

    class FakeFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("ready", True, (("Houses", True), ("Parties", True),
                                   ("Constituencies", True), ("Members", True), ("Bills", False)),
                                   "Required graph families present.")

        def query(self, sparql):
            assert sparql.startswith("PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n")
            assert sparql.endswith("LIMIT 100")
            return QueryResult(
                kind="select", columns=("name",), rows=(("A Member",),),
                raw_json=json.dumps({
                    "head": {"vars": ["name"]},
                    "results": {"bindings": [{"name": {"type": "literal", "value": "A Member"}}]},
                }, indent=2),
            )

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", FakeFuseki)
    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is the member?"})

    response = asyncio.run(post_question())
    assert response.status_code == 200
    assert "Interpreted as" in response.text
    assert "Find the requested member" in response.text
    assert "<th scope=\"col\">name</th>" in response.text
    assert "A Member" in response.text
    assert "Generated SPARQL" in response.text
    assert (
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
        "SELECT ?name WHERE { ?m foaf:name ?name }\nLIMIT 100"
    ) in unescape(response.text)
    assert "Raw Fuseki response payload" in response.text
    assert '"vars": [' in unescape(response.text)
    assert "Fuseki readiness" in response.text
    assert "Required graph families present." in response.text


def test_browser_shows_fuseki_error_payload_in_debug_output(monkeypatch):
    payload = json.dumps({"error": "bad query", "detail": "syntax error"}, indent=2)

    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, question, schema):
            return Translation("Run a query", "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT ?name WHERE { ?m foaf:name ?name }")

        def close(self):
            pass

    class FakeFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("partial", True, (("Houses", True), ("Parties", False),
                                     ("Constituencies", False), ("Members", True), ("Bills", False)),
                                   "Missing Parties and Constituencies.")

        def query(self, sparql):
            raise NLQError("Fuseki returned HTTP 400 while querying.", debug_output=payload)

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", FakeFuseki)

    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is the member?"})

    response = asyncio.run(post_question())
    assert response.status_code == 200
    assert "Fuseki returned HTTP 400" in response.text
    assert "Query debugger" in response.text
    assert "passed local validation" in response.text
    assert "<details open>" in response.text
    assert '"detail": "syntax error"' in unescape(response.text)


def test_browser_shows_llm_error_payload_when_translation_fails(monkeypatch):
    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, question, schema):
            raise NLQError(
                "The LLM rejected authentication (HTTP 401).",
                debug_output=json.dumps({"error": {"message": "invalid API key"}}, indent=2),
                debug_source="LLM API",
            )

        def close(self):
            pass

    class MustNotQueryFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("empty", False, (), "Fuseki is empty.")

        def query(self, sparql):
            raise AssertionError("Generated SPARQL must not be sent to Fuseki when the LLM request fails")

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", MustNotQueryFuseki)

    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is the member?"})

    response = asyncio.run(post_question())
    assert response.status_code == 200
    assert "LLM translation failed; no SPARQL query was sent" in response.text
    assert "Raw LLM API response payload" in response.text
    assert "invalid API key" in response.text
    assert "No response payload was received" not in response.text
    assert "Fuseki is empty." in response.text


def test_browser_opens_debugger_for_empty_select_results(monkeypatch):
    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, question, schema):
            return Translation("Find the named member", "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT ?name WHERE { ?m foaf:name ?name }")

        def close(self):
            pass

    class FakeFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("ready", True, (("Houses", True), ("Parties", True),
                                     ("Constituencies", True), ("Members", True), ("Bills", False)),
                                   "Ready.")

        def query(self, sparql):
            return parse_results({"head": {"vars": ["name"]}, "results": {"bindings": []}})

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", FakeFuseki)

    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is the named member?"})

    response = asyncio.run(post_question())
    assert response.status_code == 200
    assert "Fuseki accepted the SELECT query but returned zero bindings" in response.text
    assert "<details open>" in response.text
    assert '"bindings": []' in unescape(response.text)


def test_browser_identifies_safety_rejection_as_not_sent_to_fuseki(monkeypatch):
    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, question, schema):
            return Translation("This query uses a forbidden service", "SELECT ?s WHERE { SERVICE <http://example.test> {?s <urn:p> ?o} }")

        def close(self):
            pass

    class MustNotQueryFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("ready", True, (), "Ready.")

        def query(self, sparql):
            raise AssertionError("Unsafe SPARQL must not be sent to Fuseki")

        def close(self):
            pass

    monkeypatch.setattr(app_module, "ResponsesTranslator", FakeTranslator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", MustNotQueryFuseki)

    async def post_question():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/ask", data={"question": "Who is the member?"})

    response = asyncio.run(post_question())
    assert response.status_code == 200
    assert "SERVICE clauses are not allowed" in response.text
    assert "was not sent to Fuseki" in response.text
    assert "SELECT ?s WHERE { SERVICE" in response.text
