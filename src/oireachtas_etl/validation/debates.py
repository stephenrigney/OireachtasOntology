"""RDF-only Tranche 2 checks for one Work-owned Debates graph.

This is deliberately not a SHACL or Tranche 3 semantic validator. The RDF
alone cannot prove that transcript prose was not copied into an otherwise
permitted structural string, or that a Division/vote/participation was not
derived from a source ``rollCall``. Source-aware acceptance tests must compare
the output with the immutable AKN input for those negative guarantees.

Public API: :func:`validate_debates` accepts a transform result exposing
``graph``, ``graph_iri``, ``work_iri`` and ``expression_iri`` attributes and
raises :class:`ValueError` when an RDF-visible Tranche 2 invariant fails.
"""
from __future__ import annotations

from datetime import date, datetime
import re
from urllib.parse import urlsplit

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from ..transforms.common import ELIDL, OIR

SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
DC = "http://purl.org/dc/elements/1.1/"
FOAF = "http://xmlns.com/foaf/0.1/"
SCHEMA = "https://schema.org/"

DEFERRED_PREDICATES = frozenset({
    OIR.inHouse,
    OIR.directedTo,
    OIR.directedToOffice,
    OIR.refersToEvent,
    OIR.refersToProposal,
})
SPEECH_PARTICIPATION_FORBIDDEN = ELIDL.had_participation

_ALLOWED_PREDICATES = frozenset({
    RDF.type,
    OIR.hasExpression,
    OIR.debateDate,
    OIR.debateType,
    OIR.expressionLanguageCode,
    OIR.expressionHasSection,
    OIR.hasSection,
    OIR.hasSubSection,
    OIR.sectionName,
    OIR.hasSpeech,
    OIR.recordedTime,
    OIR.speaker,
    OIR.hasSpeechParticipation,
    OIR.hasSummary,
    OIR.hasQuestion,
    OIR.askedBy,
    OIR.recordOfBody,
    OIR.recordOfHouseTerm,
    OIR.producedRecord,
    ELIDL.activity_date,
    OIR.hasDivision,
    OIR.votedFor,
    OIR.votedAgainst,
    OIR.abstained,
    OIR.divisionOutcome,
    OIR.taCount,
    OIR.nilCount,
    OIR.staonCount,
    OIR.sourceOrdinal,
    ELIDL.had_participant_person,
    ELIDL.participation_role,
})
_LITERAL_PREDICATES = frozenset({
    OIR.debateDate,
    OIR.debateType,
    OIR.expressionLanguageCode,
    OIR.sectionName,
    OIR.recordedTime,
    ELIDL.activity_date,
    OIR.sourceOrdinal,
    OIR.taCount,
    OIR.nilCount,
    OIR.staonCount,
})
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\Z")
_MIDNIGHT = re.compile(r"\d{4}-\d{2}-\d{2}T00:00:00\Z")
_DATE_LITERAL = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})(?P<timezone>Z|[+-]\d{2}:\d{2})?\Z")
_INTEGER = re.compile(r"[+-]?\d+\Z")
_ENCODED_COMPONENT = re.compile(r"(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+\Z")
_KNOWN_OUTCOMES = frozenset({OIR.DeclaredCarried, OIR.DeclaredLost})

_PROSE_PREDICATES = frozenset(URIRef(value) for value in (
    str(RDFS.label), str(RDFS.comment), SKOS + "prefLabel", SKOS + "altLabel",
    SKOS + "definition", DCT + "title", DCT + "description", DC + "title",
    DC + "description", FOAF + "name", SCHEMA + "text", SCHEMA + "description",
))

RDF_ONLY_LIMITATIONS = (
    "RDF-only inspection cannot prove transcript prose was not copied into a permitted structural string; source-aware AKN/output tests are required.",
    "RDF-only inspection cannot prove that a Division, vote, or participation was not derived from source rollCall attendance; source-aware AKN/output tests are required.",
    "This Tranche 2 validator does not resolve or establish the owner/type of external target IRIs; that remains cross-dataset validation work.",
)


def _value_iri(value: object, name: str) -> URIRef:
    if isinstance(value, URIRef):
        result = value
    elif isinstance(value, str) and value:
        result = URIRef(value)
    else:
        raise ValueError(f"Debates result {name} must be an absolute IRI")
    parsed = urlsplit(str(result))
    if parsed.scheme != "https" or not parsed.netloc or any(c.isspace() for c in str(result)):
        raise ValueError(f"Debates result {name} must be an absolute HTTPS IRI")
    return result


def _expected_graph_iri(work: URIRef) -> str:
    parsed = urlsplit(str(work))
    prefix = "/akn/ie/debateRecord/"
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.query or parsed.fragment or not parsed.path.startswith(prefix)
            or parsed.path == prefix):
        raise ValueError("work_iri must use the approved canonical debateRecord Work path")
    _check_encoded_path(parsed.path, "work_iri")
    return "https://data.oireachtas.ie/graph/debate/" + parsed.path[len(prefix):]


def _check_encoded_path(path: str, label: str) -> None:
    if not path.startswith("/"):
        raise ValueError(f"{label} must have an absolute canonical path")
    components = path[1:].split("/")
    if any(component in ("", ".", "..") or not _ENCODED_COMPONENT.fullmatch(component)
           for component in components):
        raise ValueError(f"{label} path must use non-empty RFC 3986 encoded components")


def _objects(graph: Graph, subject: URIRef, predicate: URIRef, label: str,
             *, required: bool = False, maximum: int = 1) -> list:
    values = list(graph.objects(subject, predicate))
    if len(values) > maximum or (required and not values):
        requirement = "exactly one" if maximum == 1 else f"at most {maximum}"
        if required and maximum == 1:
            requirement = "exactly one"
        raise ValueError(f"{label} requires {requirement} value(s)")
    return values


def _one_literal(graph: Graph, subject: URIRef, predicate: URIRef, label: str,
                 datatype: URIRef, *, required: bool = False) -> Literal | None:
    values = _objects(graph, subject, predicate, label, required=required)
    if not values:
        return None
    value = values[0]
    valid_datatypes = {datatype}
    if datatype == XSD.string:
        # RDF 1.1 simple literals are xsd:string values, even though RDFLib
        # retains the compact no-datatype syntax on the Literal object.
        valid_datatypes.add(None)
    if (not isinstance(value, Literal) or value.datatype not in valid_datatypes
            or value.language is not None):
        raise ValueError(f"{label} must be an untagged {datatype} literal")
    return value


def _valid_datetime(value: Literal, label: str) -> None:
    lexical = str(value)
    if not _DATETIME.fullmatch(lexical):
        raise ValueError(f"{label} must be a valid xsd:dateTime")
    try:
        datetime.fromisoformat(lexical.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be a valid xsd:dateTime") from error


def _validate_activity_date(value: object, work_date_time: Literal) -> None:
    """Accept the pinned ELI-DL date/dateTime range without losing Work date."""
    if not isinstance(value, Literal) or value.language is not None:
        raise ValueError("activity_date must be an untagged xsd:date or xsd:dateTime literal")
    if value.datatype == XSD.dateTime:
        if str(value) != str(work_date_time):
            raise ValueError("activity_date must equal its Work debateDate")
        return
    if value.datatype != XSD.date:
        raise ValueError("activity_date must use xsd:date or xsd:dateTime")
    match = _DATE_LITERAL.fullmatch(str(value))
    if match is None:
        raise ValueError("activity_date must be a valid xsd:date")
    try:
        date.fromisoformat(match.group("date"))
    except ValueError as error:
        raise ValueError("activity_date must be a valid xsd:date") from error
    timezone = match.group("timezone")
    if timezone and timezone != "Z":
        hours, minutes = map(int, timezone[1:].split(":"))
        if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
            raise ValueError("activity_date must be a valid xsd:date")
    if match.group("date") != str(work_date_time)[:10]:
        raise ValueError("activity_date xsd:date must equal the Work calendar date")


def _ordinal(value: object, label: str) -> int:
    if (not isinstance(value, Literal) or value.datatype != XSD.integer
            or value.language is not None or not _INTEGER.fullmatch(str(value))):
        raise ValueError(f"{label} must be an xsd:integer")
    parsed = int(str(value))
    if parsed < 1:
        raise ValueError(f"{label} must be positive")
    return parsed


def _count(value: object, label: str) -> int:
    if (not isinstance(value, Literal) or value.datatype != XSD.integer
            or value.language is not None or not _INTEGER.fullmatch(str(value))):
        raise ValueError(f"{label} must be an xsd:integer")
    parsed = int(str(value))
    if parsed < 0:
        raise ValueError(f"{label} must not be negative")
    return parsed


def _targets(graph: Graph, subject: URIRef, predicate: URIRef, label: str) -> set[URIRef]:
    values = set(graph.objects(subject, predicate))
    if any(not isinstance(value, URIRef) for value in values):
        raise ValueError(f"{label} targets must be IRIs")
    return values


def _check_ordinals(graph: Graph, expression: URIRef,
                    sections: set[URIRef], speeches: set[URIRef],
                    summaries: set[URIRef], questions: set[URIRef]) -> None:
    addressable = sections | speeches | summaries | questions
    ordinal_subjects = set(graph.subjects(OIR.sourceOrdinal, None))
    if ordinal_subjects != addressable:
        raise ValueError("every addressable section/contribution must have exactly one sourceOrdinal, and no other resource may have one")

    scopes: dict[URIRef, set[URIRef]] = {expression: set(graph.objects(expression, OIR.expressionHasSection))}
    for section in sections:
        children = set()
        for predicate in (OIR.hasSubSection, OIR.hasDivision, OIR.hasSpeech,
                          OIR.hasSummary, OIR.hasQuestion):
            children.update(graph.objects(section, predicate))
        scopes[section] = children

    for container, children in scopes.items():
        values = []
        for child in children:
            if not isinstance(child, URIRef):
                raise ValueError("addressable containment targets must be IRIs")
            value = _one_literal(graph, child, OIR.sourceOrdinal, "sourceOrdinal", XSD.integer, required=True)
            values.append(_ordinal(value, "sourceOrdinal"))
        if sorted(values) != list(range(1, len(values) + 1)):
            raise ValueError(f"sourceOrdinal values must be consecutive 1-based ordinals within {container}")

    for subject in addressable:
        value = _one_literal(graph, subject, OIR.sourceOrdinal, "sourceOrdinal", XSD.integer, required=True)
        _ordinal(value, "sourceOrdinal")


def _check_graph_terms(graph: Graph, speeches: set[URIRef]) -> None:
    for subject, predicate, obj in graph:
        if predicate == SPEECH_PARTICIPATION_FORBIDDEN and subject in speeches:
            raise ValueError("eli-dl:had_participation is forbidden on Speech; use hasSpeechParticipation")
        if predicate in DEFERRED_PREDICATES:
            raise ValueError(f"deferred Debates predicate is forbidden: {predicate}")
        if predicate in _PROSE_PREDICATES:
            raise ValueError(f"prose/description predicate is forbidden in the Debates graph: {predicate}")
        if predicate == RDF.type and isinstance(obj, URIRef):
            local_name = str(obj).rsplit("#", 1)[-1].rsplit("/", 1)[-1].lower()
            if "rollcall" in local_name or "attendance" in local_name:
                raise ValueError(f"rollCall/attendance type is forbidden in the Debates graph: {obj}")
        if predicate != RDF.type and ("rollcall" in str(predicate).rsplit("#", 1)[-1].rsplit("/", 1)[-1].lower()
                                      or "attendance" in str(predicate).rsplit("#", 1)[-1].rsplit("/", 1)[-1].lower()):
            raise ValueError(f"rollCall/attendance predicate is forbidden in the Debates graph: {predicate}")
        if predicate not in _ALLOWED_PREDICATES:
            raise ValueError(f"unmapped predicate is forbidden in the Tranche 2 Debates graph: {predicate}")
        if isinstance(subject, BNode) or isinstance(obj, BNode):
            raise ValueError("blank nodes are not permitted in deterministic Debates RDF")
        if isinstance(obj, Literal) and predicate not in _LITERAL_PREDICATES:
            raise ValueError(f"literal/prose value is not permitted on {predicate}")


def validate_debates(result: object) -> None:
    """Validate the RDF-visible Tranche 2 invariants of a transform result.

    ``result`` must expose ``graph``, ``graph_iri``, ``work_iri`` and
    ``expression_iri``. It is intentionally not a source validator: immutable
    AKN/output comparison remains necessary for transcript and rollCall
    non-emission guarantees (see :data:`RDF_ONLY_LIMITATIONS`).
    """
    try:
        graph = result.graph
        graph_iri = _value_iri(result.graph_iri, "graph_iri")
        work = _value_iri(result.work_iri, "work_iri")
        expression = _value_iri(result.expression_iri, "expression_iri")
    except AttributeError as error:
        raise ValueError("Debates transform result must expose graph, graph_iri, work_iri and expression_iri") from error
    if not isinstance(graph, Graph):
        raise ValueError("Debates result graph must be an RDFLib Graph")
    expected_graph = _expected_graph_iri(work)
    if str(graph_iri) != expected_graph:
        raise ValueError("graph_iri does not match the approved Work-owned Debates graph identity")
    expression_parts = urlsplit(str(expression))
    expression_path = expression_parts.path
    if (expression_parts.scheme != "https" or expression_parts.netloc != "data.oireachtas.ie"
            or expression_parts.query or expression_parts.fragment
            or not expression_path.startswith("/akn/ie/debateRecord/")
            or expression_path == "/akn/ie/debateRecord/"):
        raise ValueError("expression_iri must use the approved canonical debateRecord path")
    _check_encoded_path(expression_path, "expression_iri")

    _check_graph_terms(graph, set(graph.subjects(RDF.type, OIR.Speech)))

    if set(graph.subjects(RDF.type, OIR.DebateRecord)) != {work}:
        raise ValueError("graph must contain exactly its result Work as a DebateRecord")
    if set(graph.subjects(RDF.type, OIR.DebateExpression)) != {expression}:
        raise ValueError("graph must contain exactly its result Expression as a DebateExpression")
    if set(graph.subjects(OIR.hasExpression, None)) - {work}:
        raise ValueError("hasExpression is permitted only on the DebateRecord Work")
    if _targets(graph, work, OIR.hasExpression, "hasExpression") != {expression}:
        raise ValueError("DebateRecord must link to exactly its result DebateExpression")

    date_value = _one_literal(graph, work, OIR.debateDate, "debateDate", XSD.dateTime, required=True)
    if not _MIDNIGHT.fullmatch(str(date_value)):
        raise ValueError("debateDate must preserve the Work date at midnight without a timezone")
    try:
        datetime.fromisoformat(str(date_value))
    except ValueError as error:
        raise ValueError("debateDate must be a valid xsd:dateTime") from error
    if set(graph.subjects(OIR.debateDate, None)) != {work}:
        raise ValueError("debateDate is permitted only on the DebateRecord Work")

    debate_type = _one_literal(graph, work, OIR.debateType, "debateType", XSD.string)
    if set(graph.subjects(OIR.debateType, None)) - {work}:
        raise ValueError("debateType is permitted only on the DebateRecord Work")
    language = _one_literal(graph, expression, OIR.expressionLanguageCode,
                            "expressionLanguageCode", XSD.string)
    if language is not None and not str(language):
        raise ValueError("expressionLanguageCode must not be empty when emitted")
    if set(graph.subjects(OIR.expressionLanguageCode, None)) - {expression}:
        raise ValueError("expressionLanguageCode is permitted only on the DebateExpression")
    recorded_subjects = set(graph.subjects(OIR.recordedTime, None))
    if recorded_subjects - set(graph.subjects(RDF.type, OIR.Speech)):
        raise ValueError("recordedTime is permitted only on Speech")
    for subject in recorded_subjects:
        recorded = _one_literal(graph, subject, OIR.recordedTime, "recordedTime", XSD.dateTime)
        if recorded is not None:
            _valid_datetime(recorded, "recordedTime")

    work_segments = urlsplit(str(work)).path.split("/")
    work_is_written = "writtens" in work_segments
    type_value = str(debate_type) if debate_type is not None else None
    sitting_eligible = not work_is_written and type_value in (None, "debate")
    if type_value == "writtens":
        sitting_eligible = False
    sittings = set(graph.subjects(RDF.type, OIR.DebateSitting))
    sitting = URIRef(str(work) + "#sitting")
    if sitting_eligible:
        if sittings != {sitting}:
            raise ValueError("eligible non-written Work requires its deterministic DebateSitting")
        if _targets(graph, sitting, OIR.producedRecord, "producedRecord") != {work}:
            raise ValueError("eligible DebateSitting must produce its DebateRecord")
        activity_dates = _objects(graph, sitting, ELIDL.activity_date,
                                  "activity_date", required=True)
        _validate_activity_date(activity_dates[0], date_value)
        if set(graph.subjects(OIR.producedRecord, None)) != {sitting}:
            raise ValueError("producedRecord is permitted only on the deterministic DebateSitting")
        if set(graph.subjects(ELIDL.activity_date, None)) != {sitting}:
            raise ValueError("activity_date is permitted only on the eligible DebateSitting")
    else:
        if sittings:
            raise ValueError("written or unreviewed Work type must not receive a DebateSitting")
        if list(graph.triples((None, OIR.producedRecord, None))) or list(graph.triples((None, ELIDL.activity_date, None))):
            raise ValueError("written or unreviewed Work must not emit sitting activity assertions")

    top_sections = _targets(graph, expression, OIR.expressionHasSection, "expressionHasSection")
    if _targets(graph, work, OIR.hasSection, "hasSection") != top_sections:
        raise ValueError("Work hasSection convenience links must equal its Expression's top-level sections")
    if set(graph.subjects(OIR.expressionHasSection, None)) - {expression}:
        raise ValueError("expressionHasSection is permitted only on the result Expression")
    if set(graph.subjects(OIR.hasSection, None)) - {work}:
        raise ValueError("hasSection is permitted only on the result Work")

    sections = set(graph.subjects(RDF.type, OIR.DebateSection))
    divisions = set(graph.subjects(RDF.type, OIR.Division))
    speeches = set(graph.subjects(RDF.type, OIR.Speech))
    summaries = set(graph.subjects(RDF.type, OIR.Summary))
    questions = set(graph.subjects(RDF.type, OIR.ParliamentaryQuestion))
    participations = set(graph.subjects(RDF.type, ELIDL.Participation))
    if not divisions <= sections:
        raise ValueError("every Division must also be typed DebateSection")

    expected_types: dict[URIRef, set[URIRef]] = {
        work: {OIR.DebateRecord},
        expression: {OIR.DebateExpression},
    }
    expected_types.update({item: {OIR.DebateSitting} for item in sittings})
    expected_types.update({item: {OIR.DebateSection} | ({OIR.Division} if item in divisions else set())
                           for item in sections})
    expected_types.update({item: {OIR.Speech} for item in speeches})
    expected_types.update({item: {OIR.Summary} for item in summaries})
    expected_types.update({item: {OIR.ParliamentaryQuestion} for item in questions})
    expected_types.update({item: {ELIDL.Participation} for item in participations})
    if set(graph.subjects(RDF.type, None)) != set(expected_types):
        raise ValueError("RDF types may describe only the result Work, Expression, Sitting, contained resources, and Participation")
    for resource, allowed_types in expected_types.items():
        if set(graph.objects(resource, RDF.type)) != allowed_types:
            raise ValueError(f"unexpected RDF class typing on Debates-owned resource {resource}")
    if (set(graph.subjects(OIR.speaker, None)) - speeches
            or set(graph.subjects(OIR.askedBy, None)) - questions):
        raise ValueError("speaker and askedBy are permitted only on Speech and ParliamentaryQuestion")

    # Every containment target must have the structural class required by its
    # predicate. The same division node is both a section and a Division.
    for parent, child in graph.subject_objects(OIR.hasSubSection):
        if parent not in sections or child not in sections:
            raise ValueError("hasSubSection must connect DebateSection resources")
    for parent, child in graph.subject_objects(OIR.hasDivision):
        if parent not in sections or child not in divisions:
            raise ValueError("hasDivision must connect a DebateSection to a DebateSection/Division")
    for predicate, expected, label in (
        (OIR.hasSpeech, speeches, "hasSpeech"),
        (OIR.hasSummary, summaries, "hasSummary"),
        (OIR.hasQuestion, questions, "hasQuestion"),
    ):
        for parent, child in graph.subject_objects(predicate):
            if parent not in sections or child not in expected:
                raise ValueError(f"{label} must connect a DebateSection to its contained structural resource")

    for division in divisions:
        names = _objects(graph, division, OIR.sectionName, "Division sectionName", required=True)
        if len(names) != 1 or not isinstance(names[0], Literal) or str(names[0]) != "division":
            raise ValueError("Division must retain sectionName 'division'")
    for section in sections - divisions:
        names = list(graph.objects(section, OIR.sectionName))
        if any(isinstance(name, Literal) and str(name) == "division" for name in names):
            raise ValueError("sectionName 'division' requires the same resource to be typed Division")
    for section in sections:
        name = _one_literal(graph, section, OIR.sectionName, "sectionName", XSD.string)
        if name is not None and not str(name):
            raise ValueError("sectionName must not be empty when emitted")
    if set(graph.subjects(OIR.sectionName, None)) - sections:
        raise ValueError("sectionName is permitted only on DebateSection")

    # Sections have one source parent: either the expression's top-level list,
    # or a nested hasSubSection/hasDivision relation. Contribution nodes have
    # exactly one immediate DebateSection parent.
    nested_parents: dict[URIRef, set[URIRef]] = {section: set() for section in sections}
    for predicate in (OIR.hasSubSection, OIR.hasDivision):
        for parent, child in graph.subject_objects(predicate):
            nested_parents[child].add(parent)
    if divisions & set(graph.objects(None, OIR.hasSubSection)):
        raise ValueError("Division must be contained with hasDivision, not hasSubSection")
    if divisions != set(graph.objects(None, OIR.hasDivision)):
        raise ValueError("every Division must have exactly one hasDivision containment link")
    if top_sections & {section for section, parents in nested_parents.items() if parents}:
        raise ValueError("top-level DebateSection must not also have a nested section parent")
    for section in sections:
        parent_count = len(nested_parents[section]) + (1 if section in top_sections else 0)
        if parent_count != 1:
            raise ValueError("every DebateSection must have exactly one Expression/section containment parent")
    if top_sections | {section for section, parents in nested_parents.items() if parents} != sections:
        raise ValueError("every DebateSection must be contained by the result Expression or another DebateSection")

    reachable: set[URIRef] = set()
    pending = list(top_sections)
    while pending:
        section = pending.pop()
        if section in reachable:
            raise ValueError("DebateSection containment must be an acyclic source tree")
        reachable.add(section)
        pending.extend(graph.objects(section, OIR.hasSubSection))
        pending.extend(graph.objects(section, OIR.hasDivision))
    if reachable != sections:
        raise ValueError("every DebateSection must be reachable from the result Expression")

    for resources, predicate, label in (
        (speeches, OIR.hasSpeech, "Speech"),
        (summaries, OIR.hasSummary, "Summary"),
        (questions, OIR.hasQuestion, "ParliamentaryQuestion"),
    ):
        parents: dict[URIRef, set[URIRef]] = {resource: set() for resource in resources}
        for parent, child in graph.subject_objects(predicate):
            if child in parents:
                parents[child].add(parent)
        if any(len(found) != 1 for found in parents.values()):
            raise ValueError(f"every {label} must have exactly one containing DebateSection")

    _check_ordinals(graph, expression, sections, speeches, summaries, questions)

    for speech in speeches:
        if set(graph.objects(speech, OIR.hasSpeechParticipation)):
            linked = _targets(graph, speech, OIR.hasSpeechParticipation, "hasSpeechParticipation")
            if len(linked) != 1:
                raise ValueError("Speech may link to at most one Participation")
            participation = next(iter(linked))
            if participation not in participations or str(participation) != str(speech) + "#participation":
                raise ValueError("Speech Participation must use its deterministic owned IRI and type")
    linked_participations = set(graph.objects(None, OIR.hasSpeechParticipation))
    if linked_participations != participations:
        raise ValueError("every Debate-owned Participation must be linked from exactly one Speech")
    for participation in participations:
        parents = set(graph.subjects(OIR.hasSpeechParticipation, participation))
        if len(parents) != 1 or next(iter(parents)) not in speeches:
            raise ValueError("Participation must belong to exactly one Speech")
        if not (list(graph.objects(participation, ELIDL.had_participant_person))
                or list(graph.objects(participation, ELIDL.participation_role))):
            raise ValueError("Participation requires at least one resolved person or reviewed role target")
        _objects(graph, participation, ELIDL.had_participant_person,
                 "had_participant_person")
        _objects(graph, participation, ELIDL.participation_role,
                 "participation_role")

    for predicate in (OIR.speaker, OIR.askedBy, OIR.votedFor, OIR.votedAgainst,
                      OIR.abstained, OIR.recordOfBody, OIR.recordOfHouseTerm,
                      ELIDL.had_participant_person, ELIDL.participation_role,
                      OIR.divisionOutcome):
        for target in graph.objects(None, predicate):
            if not isinstance(target, URIRef):
                raise ValueError(f"reference target of {predicate} must be an IRI")
            if list(graph.predicate_objects(target)):
                raise ValueError(f"Debates graph must not copy descriptive triples for foreign target {target}")

    for speech in speeches:
        _objects(graph, speech, OIR.speaker, "speaker")
    for question in questions:
        _objects(graph, question, OIR.askedBy, "askedBy")
    vote_subjects = (set(graph.subjects(OIR.votedFor, None))
                     | set(graph.subjects(OIR.votedAgainst, None))
                     | set(graph.subjects(OIR.abstained, None)))
    if vote_subjects - divisions:
        raise ValueError("individual vote links are permitted only on Division")
    participation_subjects = (set(graph.subjects(ELIDL.had_participant_person, None))
                              | set(graph.subjects(ELIDL.participation_role, None)))
    if participation_subjects - participations:
        raise ValueError("participation target links are permitted only on Participation")
    _objects(graph, work, OIR.recordOfBody, "recordOfBody")
    _objects(graph, work, OIR.recordOfHouseTerm, "recordOfHouseTerm")
    if (set(graph.subjects(OIR.recordOfBody, None)) - {work}
            or set(graph.subjects(OIR.recordOfHouseTerm, None)) - {work}):
        raise ValueError("recordOfBody and recordOfHouseTerm are permitted only on the DebateRecord Work")

    for division in divisions:
        outcomes = _objects(graph, division, OIR.divisionOutcome, "divisionOutcome")
        if outcomes and outcomes[0] not in _KNOWN_OUTCOMES:
            raise ValueError("divisionOutcome must be a known controlled #carried or #lost value")
        for predicate, label in ((OIR.taCount, "taCount"), (OIR.nilCount, "nilCount"),
                                 (OIR.staonCount, "staonCount")):
            values = _objects(graph, division, predicate, label)
            if values:
                _count(values[0], label)
    count_subjects = set().union(*(set(graph.subjects(predicate, None)) for predicate in
                                   (OIR.taCount, OIR.nilCount, OIR.staonCount)))
    if count_subjects - divisions:
        raise ValueError("vote counts are permitted only on Division")
    if set(graph.subjects(OIR.divisionOutcome, None)) - divisions:
        raise ValueError("divisionOutcome is permitted only on Division")

    # Exact Tranche 2 ownership: all graph subjects are resources owned by this
    # Work (the externally-owned targets above may occur only as objects).
    owned_subjects = ({work, expression} | sittings | sections | speeches |
                      summaries | questions | divisions | participations)
    subjects = set(graph.subjects())
    if subjects - owned_subjects:
        leaked = sorted(map(str, subjects - owned_subjects))
        raise ValueError("Debates graph contains an unowned subject/resource: " + ", ".join(leaked))
