"""Post-publication competency checks scoped to the fixed Houses named graph."""
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
