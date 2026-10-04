"""Exercise the documented fallback vector through the public transform API."""

from __future__ import annotations

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF

from oireachtas_etl.transforms.common import OIR
from oireachtas_etl.transforms.debates import DebateTransformError, transform_debate


AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
WORK_PATH = "/akn/ie/debateRecord/dail/2015-07-02/debate"
EXPRESSION_PATH = WORK_PATH + "/mul@"
CONTAINER_IRI = (
    "https://data.oireachtas.ie/akn/ie/debateRecord/"
    "dail/2015-07-02/debate/mul%40"
)
EXPECTED_DIGEST = "646242b40e1062e09f7d3cfbcb6d5506ecb032b190ec264e23f52940ad9749a2"
EXPECTED_FALLBACK_IRI = (
    "https://data.oireachtas.ie/akn/ie/debateRecord/"
    "dail/2015-07-02/debate/mul%40/fallback/fb-"
    "646242b40e1062e09f7d3cfbcb6d5506ecb032b190ec264e23f52940ad9749a2"
)
SPEECH_SUBTREE = (
    '<speech xmlns="urn:akn:test"><p>Vote &amp; return</p></speech>'
)


def _source(body_xml: str) -> bytes:
    """Build an in-memory source whose expression is the fixed contract vector."""

    return (
        f'<akomaNtoso xmlns="{AKN}"><debate><meta><identification>'
        f'<FRBRWork><FRBRuri value="{WORK_PATH}"/>'
        '<FRBRdate name="#generation" date="2015-07-02"/>'
        "</FRBRWork>"
        f'<FRBRExpression><FRBRuri value="{EXPRESSION_PATH}"/></FRBRExpression>'
        f"</identification></meta><debateBody>{body_xml}</debateBody>"
        "</debate></akomaNtoso>"
    ).encode("utf-8")


def _fallback_resource_iris(result) -> set[str]:
    return {
        identity["source_node_iri"]
        for identity in result.reference_report["resource_identities"]
        if identity["identity_kind"] == "fallback"
    }


def test_production_transform_matches_the_fixed_c14n_fallback_vector():
    result = transform_debate(_source(SPEECH_SUBTREE))

    assert result.expression_iri == CONTAINER_IRI
    expected_resource = URIRef(EXPECTED_FALLBACK_IRI)
    assert (expected_resource, RDF.type, OIR.Speech) in result.graph
    assert _fallback_resource_iris(result) == {EXPECTED_FALLBACK_IRI}

    identities = [
        identity
        for identity in result.reference_report["resource_identities"]
        if identity["source_node_iri"] == EXPECTED_FALLBACK_IRI
    ]
    assert len(identities) == 1
    identity = identities[0]
    assert identity["expanded_qname"] == "{urn:akn:test}speech"
    assert identity["fallback_evidence"]["container_iri"] == CONTAINER_IRI
    assert identity["fallback_evidence"]["fallback_digest"] == EXPECTED_DIGEST


def test_unrelated_sibling_reordering_preserves_runtime_fallback():
    before = transform_debate(
        _source(f"<marker>before</marker>{SPEECH_SUBTREE}<marker>after</marker>")
    )
    after = transform_debate(
        _source(f"<marker>after</marker>{SPEECH_SUBTREE}<marker>before</marker>")
    )

    assert _fallback_resource_iris(before) == {EXPECTED_FALLBACK_IRI}
    assert _fallback_resource_iris(after) == {EXPECTED_FALLBACK_IRI}


def test_identical_runtime_fallback_siblings_fail_closed():
    with pytest.raises(
        DebateTransformError, match="duplicate proposed Debate resource IRI"
    ) as error:
        transform_debate(_source(SPEECH_SUBTREE + SPEECH_SUBTREE))

    assert error.value.reference_report["diagnostics"][0]["code"] == (
        "duplicate-proposed-resource-iri"
    )
