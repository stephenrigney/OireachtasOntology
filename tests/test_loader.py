from urllib.parse import parse_qs, urlparse
from oireachtas_etl.loader import FusekiGraphStoreLoader

class Response:
    status = 201
    def __enter__(self): return self
    def __exit__(self, *args): return False

def test_loader_uses_single_gsp_put_with_graph_parameter(monkeypatch):
    seen = []
    def fake_open(request, timeout): seen.append((request, timeout)); return Response()
    monkeypatch.setattr("oireachtas_etl.loader.urlopen", fake_open)
    loader = FusekiGraphStoreLoader("http://localhost:3030/ds/data", user="user", password="pass")
    loader.replace("https://data.oireachtas.ie/graph/houses", "@prefix : <x:> .", content_type="text/turtle")
    request, _ = seen[0]
    assert request.get_method() == "PUT"
    assert parse_qs(urlparse(request.full_url).query)["graph"] == ["https://data.oireachtas.ie/graph/houses"]
    assert request.get_header("Content-type") == "text/turtle"
    assert request.get_header("Authorization").startswith("Basic ")


def test_loader_deletes_only_the_requested_graph_with_gsp_delete(monkeypatch):
    seen = []

    def fake_open(request, timeout):
        seen.append((request, timeout))
        return Response()

    monkeypatch.setattr("oireachtas_etl.loader.urlopen", fake_open)
    graph_iri = "https://data.oireachtas.ie/graph/bill/2025/60"
    FusekiGraphStoreLoader("http://localhost:3030/ds/data").delete(graph_iri)
    request, _ = seen[0]
    assert request.get_method() == "DELETE"
    assert parse_qs(urlparse(request.full_url).query)["graph"] == [graph_iri]
