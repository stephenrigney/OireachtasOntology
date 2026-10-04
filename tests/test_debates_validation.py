from pathlib import Path
from types import SimpleNamespace

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from oireachtas_etl.transforms.common import ELIDL, OIR
from oireachtas_etl.transforms.debates import transform_debate
from oireachtas_etl.validation.debates import (
    DEFERRED_PREDICATES,
    RDF_ONLY_LIMITATIONS,
    validate_debates,
)


WORK_PATH = "/akn/ie/debateRecord/dail/2026-02-26/debate"
WORK = URIRef("https://data.oireachtas.ie" + WORK_PATH)
EXPRESSION = URIRef(str(WORK) + "/mul%40")
GRAPH_IRI = "https://data.oireachtas.ie/graph/debate/dail/2026-02-26/debate"
ELI_ACTIVITY_DATE = ELIDL.activity_date
DATE = Literal("2026-02-25T00:00:00", datatype=XSD.dateTime)
ROOT = Path(__file__).resolve().parents[1]
DEBATE_FIXTURES = (
    "dail_2015-07-02.akn.xml",
    "dail_2026-02-26.akn.xml",
    "seanad_2015-07-02.akn.xml",
    "committee_public_accounts_2026-09-24.akn.xml",
    "dail_written_answers_2015-07-02.akn.xml",
)


def make_result(*, written=False):
    work = URIRef("https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens" if written else WORK)
    expression = URIRef(str(work) + "/eng%40")
    graph_path = str(work).replace("https://data.oireachtas.ie/akn/ie/debateRecord/",
                                   "https://data.oireachtas.ie/graph/debate/", 1)
    graph = Graph()
    graph.add((work, RDF.type, OIR.DebateRecord))
    graph.add((work, OIR.debateDate, DATE))
    graph.add((work, OIR.debateType, Literal("writtens" if written else "debate")))
    graph.add((work, OIR.hasExpression, expression))
    graph.add((expression, RDF.type, OIR.DebateExpression))
    graph.add((expression, OIR.expressionLanguageCode, Literal("eng")))
    if not written:
        sitting = URIRef(str(work) + "#sitting")
        graph.add((sitting, RDF.type, OIR.DebateSitting))
        graph.add((sitting, OIR.producedRecord, work))
        graph.add((sitting, ELI_ACTIVITY_DATE, DATE))

    top = URIRef(str(expression) + "/eid/e-top")
    nested = URIRef(str(expression) + "/eid/e-nested")
    speech = URIRef(str(expression) + "/eid/e-speech")
    summary = URIRef(str(expression) + "/eid/e-summary")
    question = URIRef(str(expression) + "/eid/e-question")
    division = URIRef(str(expression) + "/eid/e-division")
    ta_group = URIRef(str(expression) + "/eid/e-ta")
    nested_summary = URIRef(str(expression) + "/eid/e-nested-summary")

    graph.add((expression, OIR.expressionHasSection, top))
    graph.add((work, OIR.hasSection, top))
    graph.add((top, RDF.type, OIR.DebateSection))
    graph.add((top, OIR.sectionName, Literal("debate")))
    graph.add((top, OIR.sourceOrdinal, Literal(1, datatype=XSD.integer)))

    for resource, class_iri, ordinal in (
        (speech, OIR.Speech, 1),
        (summary, OIR.Summary, 2),
        (question, OIR.ParliamentaryQuestion, 3),
        (nested, OIR.DebateSection, 4),
    ):
        graph.add((resource, RDF.type, class_iri))
        graph.add((resource, OIR.sourceOrdinal, Literal(ordinal, datatype=XSD.integer)))
    graph.add((top, OIR.hasSpeech, speech))
    graph.add((top, OIR.hasSummary, summary))
    graph.add((top, OIR.hasQuestion, question))
    graph.add((top, OIR.hasSubSection, nested))
    graph.add((nested, OIR.sectionName, Literal("question")))
    graph.add((nested, OIR.hasSummary, nested_summary))
    graph.add((nested_summary, RDF.type, OIR.Summary))
    graph.add((nested_summary, OIR.sourceOrdinal, Literal(1, datatype=XSD.integer)))

    graph.add((division, RDF.type, OIR.DebateSection))
    graph.add((division, RDF.type, OIR.Division))
    graph.add((division, OIR.sectionName, Literal("division")))
    graph.add((division, OIR.sourceOrdinal, Literal(5, datatype=XSD.integer)))
    graph.add((top, OIR.hasDivision, division))
    graph.add((ta_group, RDF.type, OIR.DebateSection))
    graph.add((ta_group, OIR.sectionName, Literal("ta")))
    graph.add((ta_group, OIR.sourceOrdinal, Literal(1, datatype=XSD.integer)))
    graph.add((division, OIR.hasSubSection, ta_group))
    graph.add((division, OIR.taCount, Literal(0, datatype=XSD.integer)))
    graph.add((division, OIR.nilCount, Literal(2, datatype=XSD.integer)))
    graph.add((division, OIR.staonCount, Literal(0, datatype=XSD.integer)))
    graph.add((division, OIR.divisionOutcome, OIR.DeclaredCarried))

    member = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/123")
    graph.add((speech, OIR.speaker, member))
    graph.add((question, OIR.askedBy, member))
    graph.add((division, OIR.votedFor, member))
    part = URIRef(str(speech) + "#participation")
    graph.add((speech, OIR.hasSpeechParticipation, part))
    graph.add((part, RDF.type, ELIDL.Participation))
    graph.add((part, ELIDL.had_participant_person, member))

    return SimpleNamespace(graph=graph, graph_iri=graph_path,
                           work_iri=work, expression_iri=expression)


def copied(result):
    graph = Graph()
    for triple in result.graph:
        graph.add(triple)
    return SimpleNamespace(graph=graph, graph_iri=result.graph_iri,
                           work_iri=result.work_iri,
                           expression_iri=result.expression_iri)


def test_valid_debates_rdf_passes_and_rdf_only_limits_are_explicit():
    validate_debates(make_result())
    assert any("transcript" in limit and "source-aware" in limit for limit in RDF_ONLY_LIMITATIONS)
    assert any("rollCall" in limit and "source-aware" in limit for limit in RDF_ONLY_LIMITATIONS)


@pytest.mark.parametrize("filename", DEBATE_FIXTURES)
def test_preserved_fixture_transforms_pass_debates_validation(filename):
    source = (ROOT / "data" / "debates_examples" / filename).read_bytes()
    result = transform_debate(source, resolver=None)
    validate_debates(result)


def test_written_answer_work_keeps_record_and_date_but_has_no_sitting():
    result = make_result(written=True)
    validate_debates(result)
    sitting = URIRef(str(result.work_iri) + "#sitting")
    result.graph.add((sitting, RDF.type, OIR.DebateSitting))
    with pytest.raises(ValueError, match="must not receive a DebateSitting"):
        validate_debates(result)


def test_eligible_work_requires_deterministic_sitting_date_and_graph_identity():
    result = copied(make_result())
    result.graph.remove((URIRef(str(result.work_iri) + "#sitting"), RDF.type, OIR.DebateSitting))
    with pytest.raises(ValueError, match="requires its deterministic DebateSitting"):
        validate_debates(result)

    result = copied(make_result())
    sitting = URIRef(str(result.work_iri) + "#sitting")
    result.graph.set((sitting, ELI_ACTIVITY_DATE, Literal("2026-02-24T00:00:00", datatype=XSD.dateTime)))
    with pytest.raises(ValueError, match="must equal its Work debateDate"):
        validate_debates(result)

    result = copied(make_result())
    result.graph_iri = GRAPH_IRI + "/wrong"
    with pytest.raises(ValueError, match="graph_iri does not match"):
        validate_debates(result)


def test_sitting_activity_date_accepts_valid_xsd_date_and_rejects_bad_dates():
    result = copied(make_result())
    sitting = URIRef(str(result.work_iri) + "#sitting")
    result.graph.set((sitting, ELI_ACTIVITY_DATE,
                      Literal("2026-02-25", datatype=XSD.date)))
    validate_debates(result)

    result = copied(make_result())
    sitting = URIRef(str(result.work_iri) + "#sitting")
    result.graph.set((sitting, ELI_ACTIVITY_DATE,
                      Literal("2026-02-24", datatype=XSD.date)))
    with pytest.raises(ValueError, match="must equal the Work calendar date"):
        validate_debates(result)

    result = copied(make_result())
    sitting = URIRef(str(result.work_iri) + "#sitting")
    result.graph.set((sitting, ELI_ACTIVITY_DATE,
                      Literal("2026-02-30", datatype=XSD.date, normalize=False)))
    with pytest.raises(ValueError, match="valid xsd:date"):
        validate_debates(result)


def test_required_work_expression_and_date_invariants_fail_closed():
    result = copied(make_result())
    result.graph.remove((result.work_iri, OIR.debateDate, None))
    with pytest.raises(ValueError, match="debateDate requires exactly one"):
        validate_debates(result)

    result = copied(make_result())
    result.graph.remove((result.work_iri, OIR.hasExpression, None))
    with pytest.raises(ValueError, match="must link to exactly its result DebateExpression"):
        validate_debates(result)


def test_containment_requires_structural_classes_and_mixed_kind_ordinals():
    result = copied(make_result())
    speech = next(result.graph.objects(None, OIR.hasSpeech))
    result.graph.remove((speech, RDF.type, OIR.Speech))
    with pytest.raises(ValueError, match="hasSpeech must connect|speaker and askedBy"):
        validate_debates(result)

    result = copied(make_result())
    summary = URIRef(str(result.expression_iri) + "/eid/e-summary")
    result.graph.set((summary, OIR.sourceOrdinal, Literal(1, datatype=XSD.integer)))
    with pytest.raises(ValueError, match="consecutive 1-based ordinals"):
        validate_debates(result)

    result = copied(make_result())
    nested_summary = URIRef(str(result.expression_iri) + "/eid/e-nested-summary")
    # The nested summary's scope restarts at one; moving it to two must fail.
    result.graph.set((nested_summary, OIR.sourceOrdinal, Literal(2, datatype=XSD.integer)))
    with pytest.raises(ValueError, match="consecutive 1-based ordinals"):
        validate_debates(result)


@pytest.mark.parametrize("predicate", sorted(DEFERRED_PREDICATES, key=str))
def test_deferred_mapping_predicates_are_forbidden(predicate):
    result = copied(make_result())
    result.graph.add((result.work_iri, predicate, URIRef("https://example.test/target")))
    with pytest.raises(ValueError, match="deferred Debates predicate"):
        validate_debates(result)


def test_speech_cannot_use_eli_dl_had_participation():
    result = copied(make_result())
    speech = next(result.graph.subjects(OIR.hasSpeechParticipation, None))
    result.graph.add((speech, ELIDL.had_participation, URIRef("https://example.test/participation")))
    with pytest.raises(ValueError, match="forbidden on Speech"):
        validate_debates(result)


def test_foreign_target_descriptions_are_rejected():
    result = copied(make_result())
    member = next(result.graph.objects(None, OIR.speaker))
    result.graph.add((member, RDF.type, OIR.Member))
    with pytest.raises(ValueError):
        validate_debates(result)


def test_text_predicates_and_unmapped_prose_literals_are_rejected():
    result = copied(make_result())
    summary = next(result.graph.subjects(RDF.type, OIR.Summary))
    result.graph.add((summary, RDFS.label, Literal("copied transcript prose", lang="en")))
    with pytest.raises(ValueError, match="prose/description predicate"):
        validate_debates(result)

    result = copied(make_result())
    summary = next(result.graph.subjects(RDF.type, OIR.Summary))
    result.graph.add((summary, URIRef("https://example.test/text"), Literal("copied prose")))
    with pytest.raises(ValueError, match="unmapped predicate"):
        validate_debates(result)


def test_only_known_outcomes_and_nonnegative_integer_counts_are_valid():
    result = copied(make_result())
    division = next(result.graph.subjects(RDF.type, OIR.Division))
    result.graph.set((division, OIR.divisionOutcome, URIRef("https://data.oireachtas.ie/ontology#Declared")))
    with pytest.raises(ValueError, match="known controlled #carried or #lost"):
        validate_debates(result)

    result = copied(make_result())
    division = next(result.graph.subjects(RDF.type, OIR.Division))
    result.graph.set((division, OIR.taCount, Literal(-1, datatype=XSD.integer)))
    with pytest.raises(ValueError, match="must not be negative"):
        validate_debates(result)

    result = copied(make_result())
    division = next(result.graph.subjects(RDF.type, OIR.Division))
    result.graph.set((division, OIR.taCount, Literal("1.5", datatype=XSD.decimal)))
    with pytest.raises(ValueError, match="taCount must be an xsd:integer"):
        validate_debates(result)


def test_detectable_rollcall_and_attendance_terms_are_rejected():
    result = copied(make_result())
    result.graph.add((result.work_iri, URIRef("https://example.test/rollCallAttendance"),
                      URIRef("https://example.test/person")))
    with pytest.raises(ValueError, match="rollCall/attendance predicate"):
        validate_debates(result)

    result = copied(make_result())
    result.graph.add((result.work_iri, RDF.type,
                      URIRef("https://example.test/RollCallAttendance")))
    with pytest.raises(ValueError, match="rollCall/attendance type"):
        validate_debates(result)
