"""Transport-only controls: no live endpoint or frozen kernel execution."""

import httpx
import pytest
from rdflib import Literal, URIRef

from poc.nlq.errors import NLQError
from tools.nlq_composition_live import LiveTransport, decode_select, typed_json


def test_typed_lexical_roundtrip():
    payload = {"head": {"vars": ["i", "d", "s"]}, "results": {"bindings": [{
        "i": {"type": "uri", "value": "https://data.oireachtas.ie/test"},
        "d": {"type": "literal", "value": "2026-11-11T00:00:00.000", "datatype": "http://www.w3.org/2001/XMLSchema#dateTime"},
        "s": {"type": "literal", "value": "téacs", "xml:lang": "ga"}}]}}
    columns, rows = decode_select(payload)
    assert columns == payload["head"]["vars"]
    assert isinstance(rows[0]["i"], URIRef)
    assert isinstance(rows[0]["d"], Literal)
    assert typed_json(rows) == payload["results"]["bindings"]


@pytest.mark.parametrize("payload", [
    {}, {"head": {"vars": ["x", "x"]}, "results": {"bindings": []}},
    {"head": {"vars": ["x"]}, "results": {"bindings": [{"y": {"type": "uri", "value": "urn:x"}}]}},
    {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "bnode", "value": "b1"}}]}},
    {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "literal", "value": "x", "datatype": "urn:d", "xml:lang": "en"}}]}},
])
def test_malformed_bindings_fail_closed(payload):
    with pytest.raises(NLQError):
        decode_select(payload)


def test_http_query_and_page_are_unmodified():
    query = "SELECT ?x WHERE { VALUES ?x { 1 } } LIMIT 100"
    body = {"head": {"vars": ["x"]}, "results": {"bindings": [
        {"x": {"type": "literal", "value": "01", "datatype": "http://www.w3.org/2001/XMLSchema#integer"}}] * 100}}
    def handler(request):
        assert request.url.path == "/houses/query"
        assert request.method == "POST"
        assert request.extensions["timeout"] == {"connect": 15, "read": 15, "write": 15, "pool": 15}
        from urllib.parse import parse_qs
        assert parse_qs(request.content.decode()) == {"query": [query]}
        return httpx.Response(200, json=body, headers={"Content-Type": "application/sparql-results+json"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = LiveTransport(client=client)
        result = transport.select(None, query, 0)
    assert len(result["rows"]) == 100
    assert typed_json(result["rows"]) == body["results"]["bindings"]
    assert result["complete"] is True  # Page only; does not suppress kernel lookahead.


@pytest.mark.parametrize("status,body,ctype", [(503, "busy", "text/plain"),
    (200, '{"head":', "application/sparql-results+json"), (200, "{}", "text/plain")])
def test_invalid_http_page_fails(status, body, ctype):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            status, text=body, headers={"Content-Type": ctype}))) as client:
        transport = LiveTransport(client=client)
        with pytest.raises(NLQError):
            transport.select(None, "SELECT ?x WHERE {} LIMIT 100", 0)
        assert len(transport.exchanges) == 1


def test_http_timeout_is_nonanswer_error():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(NLQError):
            LiveTransport(client=client).select(None, "SELECT ?x WHERE {} LIMIT 100", 0)


def test_adapter_does_not_hide_malformed_or_oversized_evidence():
    # Semantic invalidity and raw budgets belong to the frozen executor, not HTTP.
    payload = {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {
        "type": "literal", "value": "not-a-date", "datatype": "http://www.w3.org/2001/XMLSchema#date"
    }}] * 101}}
    columns, rows = decode_select(payload)
    assert columns == ["x"]
    assert len(rows) == 101
    assert typed_json(rows) == payload["results"]["bindings"]
