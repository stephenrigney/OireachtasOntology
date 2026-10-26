import json

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF, SKOS

from oireachtas_etl.political_affiliations import (
    GRAPH_IRI, MEMBERS, PoliticalAffiliationError, build_graph, serialize,
)


def test_registry_builds_exact_deterministic_graph_and_distinct_sinn_fein_identities():
    ds = build_graph()
    graph = ds.graph(URIRef(GRAPH_IRI))
    assert len(set(graph.subjects(RDF.type, MEMBERS.PoliticalAffiliationIdentity))) == 33
    assert len(list(graph.triples((None, MEMBERS.hasPoliticalAffiliationIdentity, None)))) == 314
    assert serialize() == serialize()
    sinn = list(graph.subjects(SKOS.altLabel, __import__("rdflib").Literal("Sinn Féin", lang="en")))
    assert len(sinn) == 3


@pytest.mark.parametrize("change", ["duplicate", "unknown", "unresolved"])
def test_bad_decision_register_fails_closed(tmp_path, change):
    from oireachtas_etl.political_affiliations import DECISIONS
    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    if change == "duplicate":
        data["records"].append(data["records"][0])
    elif change == "unknown":
        data["records"][0]["identity"] = "not-reviewed"
    else:
        data["records"][0]["outcome"] = "unresolved"
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PoliticalAffiliationError):
        build_graph(path)


def test_same_counts_with_wrong_accepted_identity_fails_closed(tmp_path):
    from oireachtas_etl.political_affiliations import DECISIONS
    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    accepted = [row for row in data["records"] if row["outcome"] == "accepted"]
    accepted[0]["identity"], accepted[1]["identity"] = accepted[1]["identity"], accepted[0]["identity"]
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PoliticalAffiliationError, match="approved reviewed register"):
        build_graph(path)


def test_wrong_office_exclusion_fails_closed(tmp_path):
    from oireachtas_etl.political_affiliations import DECISIONS
    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    excluded = next(row for row in data["records"] if row["outcome"] == "excluded")
    excluded["source_label"] = "Independent"
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PoliticalAffiliationError):
        build_graph(path)


def test_publication_replaces_and_verifies_only_the_owned_graph(monkeypatch):
    from oireachtas_etl import loader, political_affiliations
    calls = []
    expected = build_graph().graph(URIRef(GRAPH_IRI))

    class Store:
        def __init__(self, endpoint, **kwargs):
            pass

        def replace(self, graph, payload, **kwargs):
            calls.append((graph, payload))
            assert kwargs["content_type"] == "application/n-triples"
            assert payload.splitlines()[0].count("<") >= 2

    class Query:
        def __init__(self, endpoint, **kwargs):
            pass

        def construct_graph(self, graph):
            calls.append(("verified", graph))
            return expected

    monkeypatch.setattr(loader, "FusekiGraphStoreLoader", Store)
    monkeypatch.setattr(loader, "FusekiSparqlClient", Query)
    political_affiliations.publish("http://isolated/data", "http://isolated/query")
    assert calls[0][0] == GRAPH_IRI
    assert calls[1] == ("verified", GRAPH_IRI)
