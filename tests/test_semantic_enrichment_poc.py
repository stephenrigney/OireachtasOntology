"""Focused non-production tests for the bounded EuroVoc enrichment PoC."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS
from rdflib.plugins.sparql.parser import parseQuery

ROOT = Path(__file__).resolve().parents[1]
POC_DIR = ROOT / "poc" / "semantic-enrichment"
sys.path.insert(0, str(POC_DIR))

import run as poc_run
import semantic_enrichment as se


def _source_xml() -> bytes:
    return '''<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:skos="http://www.w3.org/2004/02/skos/core#"
  xmlns:skosxl="http://www.w3.org/2008/05/skos-xl#"
  xmlns:euvoc="http://publications.europa.eu/ontology/euvoc#"
  xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <rdf:Description rdf:about="http://eurovoc.europa.eu/100">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <euvoc:status rdf:resource="http://publications.europa.eu/resource/authority/concept-status/CURRENT"/>
    <skos:prefLabel xml:lang="en">Health policy</skos:prefLabel>
    <skos:prefLabel xml:lang="ga">Polasaí sláinte</skos:prefLabel>
    <skos:altLabel xml:lang="en">healthcare policy</skos:altLabel>
    <skos:narrower rdf:resource="http://eurovoc.europa.eu/101"/>
  </rdf:Description>
  <rdf:Description rdf:about="http://eurovoc.europa.eu/101">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <euvoc:status rdf:resource="http://publications.europa.eu/resource/authority/concept-status/CURRENT"/>
    <skosxl:prefLabel rdf:resource="http://eurovoc.europa.eu/xl_en_child"/>
    <skos:broader rdf:resource="http://eurovoc.europa.eu/100"/>
  </rdf:Description>
  <rdf:Description rdf:about="http://eurovoc.europa.eu/xl_en_child">
    <rdf:type rdf:resource="http://www.w3.org/2008/05/skos-xl#Label"/>
    <skosxl:literalForm xml:lang="en">community care</skosxl:literalForm>
  </rdf:Description>
  <rdf:Description rdf:about="http://eurovoc.europa.eu/102">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <euvoc:status rdf:resource="http://publications.europa.eu/resource/authority/concept-status/DEPRECATED"/>
    <skos:prefLabel xml:lang="en">obsolete healthcare</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>'''.encode("utf-8")


def test_taxonomy_projection_streams_english_labels_status_and_hierarchy(tmp_path):
    path = tmp_path / "mini.rdf"
    path.write_bytes(_source_xml())
    concepts, counts = se.parse_taxonomy(path)

    assert set(concepts) == {"http://eurovoc.europa.eu/100", "http://eurovoc.europa.eu/101"}
    assert concepts["http://eurovoc.europa.eu/100"].preferred_labels == ("Health policy",)
    assert concepts["http://eurovoc.europa.eu/100"].alternative_labels == ("healthcare policy",)
    assert concepts["http://eurovoc.europa.eu/101"].preferred_labels == ("community care",)
    assert concepts["http://eurovoc.europa.eu/100"].narrower == ("http://eurovoc.europa.eu/101",)
    assert counts["concepts_total"] == 3
    assert counts["concept_status_deprecated"] == 1
    assert counts["projected_current_concepts"] == 2


def test_label_baseline_uses_whole_unicode_word_phrases_and_abstains():
    concepts = {
        "http://eurovoc.europa.eu/100": se.Concept(
            "http://eurovoc.europa.eu/100",
            ("health policy",),
            ("healthcare policy",),
            (),
            (),
        ),
        "http://eurovoc.europa.eu/101": se.Concept(
            "http://eurovoc.europa.eu/101", ("clinic",), (), (), ()
        ),
    }
    records = [
        {"contribution_iri": "https://example.test/s1", "text": "Irish HEALTH POLICY matters."},
        {"contribution_iri": "https://example.test/s2", "text": "This is not a healthpolicy match."},
        {"contribution_iri": "https://example.test/s3", "text": "A short clinical update."},
        {"contribution_iri": "https://example.test/s4", "text": "The healthcare policy changed."},
    ]
    predictions = se.label_baseline(records, concepts)
    assert [item.concept_uri for item in predictions["https://example.test/s1"]] == [
        "http://eurovoc.europa.eu/100"
    ]
    assert predictions["https://example.test/s2"] == []
    assert predictions["https://example.test/s3"] == []
    assert predictions["https://example.test/s4"][0].evidence_label == "healthcare policy"


def test_hash_ranked_source_sample_is_reproducible_and_work_level_split_safe():
    rows = [
        {
            "contribution_iri": f"https://example.test/speech/{index}",
            "work_iri": f"https://example.test/work/{index // 5}",
            "source_sha256": "a" * 64,
            "split": "evaluation" if index // 5 == 1 else "development",
            "source_id": "s1" if index // 5 != 1 else "s2",
        }
        for index in range(15)
    ]
    source = {"id": "s1", "sample_count": 5}
    selected1 = se.deterministic_sample(rows[:5], source=source, seed="fixed")
    selected2 = se.deterministic_sample(rows[:5], source=source, seed="fixed")
    assert [row["contribution_iri"] for row in selected1] == [row["contribution_iri"] for row in selected2]
    se.validate_split(
        rows,
        [
            {"id": "s1", "sample_count": 10},
            {"id": "s2", "sample_count": 5},
        ],
    )
    leaked = [dict(row, split="development") for row in rows]
    leaked[5]["split"] = "evaluation"
    with pytest.raises(ValueError, match="leakage"):
        se.validate_split(
            leaked,
            [{"id": "s1", "sample_count": 10}, {"id": "s2", "sample_count": 5}],
        )


def test_enrichment_graph_records_only_provisional_source_linked_suggestions():
    record = {
        "contribution_iri": "https://data.oireachtas.ie/akn/example/speech/1",
        "source_sha256": "a" * 64,
        "source_pointer": "/debateBody/speech[1]",
        "text_sha256": "b" * 64,
        "text": "This long transcript must not be copied into RDF." * 2,
    }
    graph_iri = "https://data.oireachtas.ie/graph/poc/semantic-enrichment/semantic/evaluation/run"
    graph = se.build_enrichment_graph(
        [record],
        {
            record["contribution_iri"]: [
                se.Suggestion("http://eurovoc.europa.eu/100", "health policy", "preferred-label", 1, 0.71)
            ]
        },
        graph_iri=graph_iri,
        method="semantic",
        method_version="test-v1",
        taxonomy={"version": "4.24", "release_identifier": "20260708-0", "sha256": "c" * 64},
        input_hash="d" * 64,
        model_sha256="e" * 64,
        settings={"threshold": 0.54},
    )
    assert (URIRef(record["contribution_iri"]), None, None) not in graph
    assert Literal(record["text"]) not in set(graph.objects(None, None))
    assert any(graph.objects(None, se.POC.assignmentStatus))
    assert Literal("provisional-unreviewed") in set(graph.objects(None, se.POC.assignmentStatus))
    assert Literal("a" * 64) in set(graph.objects(None, se.POC.sourceChecksum))
    assert Literal("e" * 64) in set(graph.objects(None, se.POC.modelChecksum))


def test_generated_queries_keep_narrower_traversal_explicit_and_house_join_named():
    questions = poc_run.load_config()[2]["questions"]
    sources = {
        "seanad-2025-02-27": {
            "work_iri": "https://data.oireachtas.ie/akn/work/seanad/2025",
            "graph_iri": "https://data.oireachtas.ie/graph/debate/seanad/2025",
        }
    }
    exact = poc_run.build_query(
        questions[1], method_graph="https://example.test/enrichment", taxonomy_graph="https://example.test/taxonomy",
        source_rows=sources,
    )
    broader = poc_run.build_query(
        questions[2], method_graph="https://example.test/enrichment", taxonomy_graph="https://example.test/taxonomy",
        source_rows=sources,
    )
    assert "FILTER(?assigned = <http://eurovoc.europa.eu/2476>)" in exact
    assert "skos:broader* <http://eurovoc.europa.eu/1372>" in broader
    assert "GRAPH <https://data.oireachtas.ie/graph/debate/seanad/2025> { ?work oir:recordOfHouseTerm ?houseTerm }" in exact
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in exact


def test_every_frozen_query_is_valid_sparql_including_multi_source_union():
    _, sources, questions_doc = poc_run.load_config()
    source_rows = {
        source["id"]: {
            "work_iri": f"https://example.test/work/{source['id']}",
            "graph_iri": f"https://example.test/graph/{source['id']}",
        }
        for source in sources
    }
    for question in questions_doc["questions"]:
        query = poc_run.build_query(
            question,
            method_graph=None if question["mode"] == "structured-only" else "https://example.test/enrichment",
            taxonomy_graph="https://example.test/taxonomy",
            source_rows=source_rows,
        )
        parseQuery(query)


def test_fuseki_configuration_rejects_remote_or_unapproved_datasets():
    assert poc_run.local_fuseki_endpoints("http://127.0.0.1:13036/semantic_enrichment") == (
        "http://127.0.0.1:13036/semantic_enrichment/data",
        "http://127.0.0.1:13036/semantic_enrichment/query",
    )
    with pytest.raises(ValueError, match="loopback"):
        poc_run.local_fuseki_endpoints("https://example.com/semantic_enrichment")
    with pytest.raises(ValueError, match="loopback"):
        poc_run.local_fuseki_endpoints("http://127.0.0.1:3030/production")
    with pytest.raises(ValueError, match="loopback"):
        poc_run.local_fuseki_endpoints("http://127.0.0.1:3030/semantic_enrichment")
    with pytest.raises(ValueError, match="loopback"):
        poc_run.local_fuseki_endpoints("http://127.0.0.1/semantic_enrichment")


def test_frozen_corpus_and_questions_stay_within_approved_bounds():
    source_doc, sources, questions_doc = poc_run.load_config()
    assert source_doc["sample_size"] == 736
    assert sum(source["sample_count"] for source in sources) <= se.MAX_CONTRIBUTIONS
    assert {source["split"] for source in sources} == {"development", "evaluation"}
    assert questions_doc["frozen_before_method_comparison"] is True
    assert any(question["include_narrower"] for question in questions_doc["questions"])
    assert any(question["mode"] == "structured-only" for question in questions_doc["questions"])
