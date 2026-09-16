"""Post-publication competency checks scoped to the fixed named graphs."""
from importlib.resources import files
from .loader import FusekiSparqlClient

QUERIES = files("oireachtas_etl.validation.resources")
EXPECTED = {
    "current-dail.rq": [{"term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"}],
    "current-seanad.rq": [{"term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/27"}],
    "term-details.rq": [{"number": "33", "house": "https://data.oireachtas.ie/house/dail", "start": "2020-02-08T00:00:00", "end": "2024-11-08T00:00:00"}],
}

def verify_houses_competency(client: FusekiSparqlClient) -> None:
    for filename, expected in EXPECTED.items():
        actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(QUERIES.joinpath(filename).read_text())]
        if actual != expected:
            raise ValueError(f"post-load competency check {filename} failed: expected {expected!r}, got {actual!r}")


PARTIES_EXPECTED = {
    "party-details.rq": [
        {"party": "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael", "code": "Fine_Gael", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"},
        {"party": "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent", "code": "Independent", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"},
    ],
}
CONSTITUENCIES_EXPECTED = {
    "representation-details.rq": [
        {"representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Mid-West", "kind": "DailConstituency", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"},
        {"representation": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/9/panel/Agricultural-Panel", "kind": "SeanadPanel", "term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/9"},
    ],
}


def _verify(client: FusekiSparqlClient, expected_queries: dict[str, list[dict]]) -> None:
    for filename, expected in expected_queries.items():
        actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(QUERIES.joinpath(filename).read_text())]
        if actual != expected:
            raise ValueError(f"post-load competency check {filename} failed: expected {expected!r}, got {actual!r}")


def verify_parties_competency(client: FusekiSparqlClient) -> None:
    _verify(client, PARTIES_EXPECTED)


def verify_constituencies_competency(client: FusekiSparqlClient) -> None:
    _verify(client, CONSTITUENCIES_EXPECTED)
