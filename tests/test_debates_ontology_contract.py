"""Focused contract checks for the approved Debates ontology additions."""

from pathlib import Path

from rdflib import Graph, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.collection import Collection


ROOT = Path(__file__).resolve().parents[1]
DEBATES = Namespace("https://data.oireachtas.ie/ontology#")
MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
ELI_DL = Namespace("http://data.europa.eu/eli/eli-draft-legislation-ontology#")
ORG = Namespace("http://www.w3.org/ns/org#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")


def debates_graph() -> Graph:
    return Graph().parse(ROOT / "ontology/debates.owl.ttl", format="turtle")


def test_approved_debates_object_property_contracts() -> None:
    graph = debates_graph()
    properties = {
        DEBATES.hasExpression: (DEBATES.DebateRecord, DEBATES.DebateExpression),
        DEBATES.expressionHasSection: (DEBATES.DebateExpression, DEBATES.DebateSection),
        DEBATES.hasQuestion: (DEBATES.DebateSection, DEBATES.ParliamentaryQuestion),
        DEBATES.recordOfBody: (DEBATES.DebateRecord, ORG.Organization),
        DEBATES.recordOfHouseTerm: (DEBATES.DebateRecord, DEBATES.HouseTerm),
        DEBATES.hasSpeechParticipation: (DEBATES.Speech, ELI_DL.Participation),
        DEBATES.directedToOffice: (DEBATES.ParliamentaryQuestion, MEMBERS.NamedOffice),
    }

    for prop, (domain, range_) in properties.items():
        assert (prop, RDF.type, OWL.ObjectProperty) in graph
        assert set(graph.objects(prop, RDFS.domain)) == {domain}
        assert set(graph.objects(prop, RDFS.range)) == {range_}

    assert (DEBATES.hasSpeechParticipation, RDFS.subPropertyOf, ELI_DL.had_participation) not in graph
    assert (DEBATES.directedTo, RDFS.range, ELI_DL.ParticipationRole) in graph
    assert (DEBATES.directedToOffice, OWL.equivalentProperty, DEBATES.directedTo) not in graph
    assert (
        URIRef("https://data.oireachtas.ie/ontology/debates"),
        OWL.imports,
        URIRef("https://data.oireachtas.ie/ontology/members"),
    ) in graph


def test_source_ordinal_and_expression_language_datatype_contracts() -> None:
    graph = debates_graph()

    assert (DEBATES.sourceOrdinal, RDF.type, OWL.DatatypeProperty) in graph
    assert set(graph.objects(DEBATES.sourceOrdinal, RDFS.range)) == {XSD.integer}
    assert not list(graph.objects(DEBATES.sourceOrdinal, RDFS.domain))
    assert (DEBATES.sourceOrdinal, RDF.type, OWL.FunctionalProperty) not in graph

    for _, key in graph.subject_objects(OWL.hasKey):
        assert DEBATES.sourceOrdinal not in Collection(graph, key)

    assert (DEBATES.expressionLanguageCode, RDF.type, OWL.DatatypeProperty) in graph
    assert set(graph.objects(DEBATES.expressionLanguageCode, RDFS.domain)) == {DEBATES.DebateExpression}
    assert set(graph.objects(DEBATES.expressionLanguageCode, RDFS.range)) == {XSD.string}


def test_comments_preserve_written_response_and_vote_boundaries() -> None:
    graph = debates_graph()
    ontology = URIRef("https://data.oireachtas.ie/ontology/debates")
    ontology_comment = " ".join(str(value) for value in graph.objects(ontology, RDFS.comment))
    speech_comment = " ".join(str(value) for value in graph.objects(DEBATES.Speech, RDFS.comment))
    has_speech_comment = " ".join(str(value) for value in graph.objects(DEBATES.hasSpeech, RDFS.comment))
    has_question_comment = " ".join(str(value) for value in graph.objects(DEBATES.hasQuestion, RDFS.comment))
    outcome_comment = " ".join(str(value) for value in graph.objects(DEBATES.divisionOutcome, RDFS.comment))
    staon_comments = " ".join(
        str(value)
        for subject in (DEBATES.abstained, DEBATES.staonCount, DEBATES.StaonVote, DEBATES.Division)
        for value in graph.objects(subject, RDFS.comment)
    )

    assert "writtenAnswer" in speech_comment and "written responses" in speech_comment
    assert "writtenAnswer" in has_speech_comment
    assert "one-to-one" in has_question_comment
    assert "rollCall attendance remains source-only" in ontology_comment
    assert "#declared marker alone does not entail" in outcome_comment
    assert "2026 onwards" not in staon_comments
    assert "when supplied" in staon_comments


def test_existing_debate_classes_remain_and_speech_is_not_an_activity() -> None:
    graph = debates_graph()

    for class_ in (
        DEBATES.DebateRecord,
        DEBATES.DebateExpression,
        DEBATES.DebateSitting,
        DEBATES.DebateSection,
        DEBATES.Speech,
        DEBATES.Summary,
        DEBATES.ParliamentaryQuestion,
        DEBATES.Division,
    ):
        assert (class_, RDF.type, OWL.Class) in graph

    assert (DEBATES.DebateSitting, RDFS.subClassOf, ELI_DL.Activity) in graph
    assert (DEBATES.Division, RDFS.subClassOf, ELI_DL.Vote) in graph
    assert (DEBATES.Speech, RDFS.subClassOf, ELI_DL.Activity) not in graph
    assert (DEBATES.DebateTranscript, RDF.type, OWL.Class) not in graph
