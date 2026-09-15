from __future__ import annotations

from rdflib import Graph, Namespace, OWL, RDF

import validate


def test_all_ontology_turtle_files_parse() -> None:
    assert validate.turtle_files()
    validate.load_ontology_graph()


def test_parse_failure_returns_nonzero(tmp_path) -> None:
    (tmp_path / "broken.owl.ttl").write_text(
        "@prefix : <https://example.test/> .\n:subject :predicate ; .",
        encoding="utf-8",
    )

    assert validate.main(["--ontology-dir", str(tmp_path)]) == 1


def test_reasoner_failure_raises_validation_error(monkeypatch) -> None:
    def fail_reasoner(*_args, **_kwargs) -> None:
        raise RuntimeError("HermiT unavailable")

    monkeypatch.setattr(validate.owlready2, "sync_reasoner", fail_reasoner)

    try:
        validate.run_consistency_check(Graph())
    except validate.OntologyValidationError as error:
        assert "reasoner failed" in str(error).lower()
    else:
        raise AssertionError("Reasoner failure must fail validation")


def test_inconsistent_ontology_raises_validation_error() -> None:
    graph = Graph()
    example = Namespace("https://example.test/")
    graph.add((example.ontology, RDF.type, OWL.Ontology))
    graph.add((example.A, RDF.type, OWL.Class))
    graph.add((example.B, RDF.type, OWL.Class))
    graph.add((example.A, OWL.disjointWith, example.B))
    graph.add((example.instance, RDF.type, example.A))
    graph.add((example.instance, RDF.type, example.B))

    try:
        validate.run_consistency_check(graph)
    except validate.OntologyValidationError as error:
        assert "inconsistent" in str(error).lower()
    else:
        raise AssertionError("Inconsistent ontology must fail validation")
