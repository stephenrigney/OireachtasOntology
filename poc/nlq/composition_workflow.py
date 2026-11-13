"""Opt-in, human-confirmed K/R interpretation and readable evidence adaptation.

The model proposes mentions only. Independent closed-scope checks do not use a
second model or the proposal's self-assessment to certify semantic completeness.
Confirmation is an attended workflow, not unattended natural-language admission.
"""

import os
import re
import unicodedata

from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

from .composition_kernel import (
    Budget, Evidence, Fact, Lookup, Read, SIGNATURES, execute, parse_semantics, retrieve,
    validate_as_of,
)
from .config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL
from .errors import NLQError
from .interpretation import current_relationship_scope
from .results import QueryResult
from .structured_planner import ResponsesPlanGenerator, _label_position, parse_draft_json


PROPOSAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"supported": {"type": "boolean"},
                   "committee": {"type": ["string", "null"]},
                   "constituency": {"type": ["string", "null"]},
                   "reason": {"type": ["string", "null"]}},
    "required": ["supported", "committee", "constituency", "reason"],
}


def create_composition_proposer():
    return ResponsesPlanGenerator(
        os.getenv("NLQ_LLM_API_KEY", ""), os.getenv("NLQ_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        os.getenv("NLQ_LLM_MODEL", DEFAULT_LLM_MODEL), output_schema=PROPOSAL_SCHEMA,
        schema_name="confirmed_composition_mentions",
        instructions=(
            "Propose the exact user-supplied committee and constituency name mentions for a "
            "current committee membership AND current Dáil constituency representation Member list. "
            "Preserve the whole names, including Committee on/of when supplied. No IRIs, names "
            "of assumed Members, dates, SPARQL, resolution or factual answers. Only those two "
            "relationships and a distinct Member list are supported. Never discard another "
            "condition, historical scope, count or requested answer field. If unsupported, "
            "supported=false, mentions=null, reason explains the limitation; otherwise "
            "supported=true, both mentions non-null, reason=null. Return strict JSON. "
            "These are proposals for human review, not validated interpretations."
        ),
    )


def validate_scope(question, committee, constituency):
    """Consume the WHOLE question outside exact, independently grounded mentions.

    A deliberately bounded wording language: unknown words, extra clauses,
    operators, dates, projections and negation fail closed even if the LLM drops
    them. Mention text must later match full owner labels, not substring search.
    """
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
        raise ValueError("Enter a question of 1–2,000 characters.")
    # Canonical Unicode equivalence is already accepted by _label_position.
    # Keep the original question in server state; normalize only matching text.
    matching_question = unicodedata.normalize("NFC", question)
    spans = []
    for key, mention in (("K", committee), ("R", constituency)):
        if (not isinstance(mention, str) or not 1 <= len(mention.strip()) <= 200
                or mention != mention.strip() or _label_position(question, mention) is None):
            raise ValueError("Both resource names must be exact mentions in the original question.")
        matches = list(re.finditer(re.escape(unicodedata.normalize("NFC", mention)), matching_question, re.I))
        if len(matches) != 1:
            raise ValueError("Name each committee and constituency exactly once; clarify repeated names.")
        spans.append((matches[0].start(), matches[0].end(), key))
    spans.sort()
    if spans[0][1] > spans[1][0]:
        raise ValueError("Committee and constituency names must be separate mentions.")
    text = matching_question
    for start, end, key in reversed(spans):
        text = text[:start] + key + text[end:]
    current = r"(?:(?:currently|now|today)\s+)?"
    members = r"(?:members|TDs|deputies)"
    patterns = (
        rf"(?:which|what)\s+(?:current\s+)?{members}\s+(?:of|on)\s+(?:the\s+)?K\s+(?:who\s+)?{current}(?:represent|are\s+representing)\s+R",
        rf"who\s+{current}(?:represents|is\s+representing)\s+R\s+and\s+{current}(?:serves|sits)\s+on\s+(?:the\s+)?K",
        rf"(?:which|what)\s+(?:current\s+)?(?:TDs|deputies)\s+for\s+R\s+are\s+(?:current\s+)?members\s+of\s+(?:the\s+)?K",
        rf"(?:list|show)(?:\s+me)?\s+(?:the\s+)?(?:current\s+)?members\s+of\s+(?:the\s+)?K\s+who\s+{current}represent\s+R",
        rf"who\s+{current}(?:serves|sits)\s+on\s+(?:the\s+)?K\s+and\s+{current}represents\s+R",
        rf"(?:which|what)\s+{members}\s+{current}(?:serve|sit)\s+on\s+(?:the\s+)?K\s+and\s+{current}represent\s+R",
    )
    if (not any(re.fullmatch(r"\s*" + p + r"(?:\s+(?:currently|now|today))?\s*[?.!]?\s*", text, re.I) for p in patterns)
            or current_relationship_scope(matching_question, unicodedata.normalize("NFC", committee), unicodedata.normalize("NFC", constituency)) is None):
        raise ValueError("Clarify the whole question: this experiment supports only a current committee AND current Dáil constituency Member list. Additional conditions, dates, counts and answer fields cannot be discarded.")


def propose(question, as_of, factory=None):
    validate_as_of(as_of)
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
        raise ValueError("Enter a question of 1–2,000 characters.")
    generator = (factory or create_composition_proposer)()
    try:
        proposal = parse_draft_json(generator.generate(question))
    finally:
        generator.close()
    if (not isinstance(proposal, dict) or set(proposal) != set(PROPOSAL_SCHEMA["required"])
            or type(proposal["supported"]) is not bool):
        raise ValueError("The semantic proposal has an invalid structure; no interpretation accepted.")
    if proposal["supported"] is False:
        if proposal["committee"] is not None or proposal["constituency"] is not None or not isinstance(proposal["reason"], str):
            raise ValueError("Malformed unsupported semantic proposal.")
        raise ValueError("Unsupported experimental request. " + proposal["reason"][:500])
    if proposal["reason"] is not None:
        raise ValueError("Conflicting semantic proposal support state.")
    validate_scope(question, proposal["committee"], proposal["constituency"])
    request = {
        "id": "confirmed-interpretation", "asOf": as_of,
        "requiredSelections": [
            {"role": "K", "relationship": SIGNATURES["K"][0], "committee": {"mention": proposal["committee"]}},
            {"role": "R", "relationship": SIGNATURES["R"][0], "constituency": {"mention": proposal["constituency"]}, "house": "Dail"},
        ],
        "exactSharedBindings": ["Member"],
        "currentAtRoles": ["K.owner", "K.term", "K.membership", "R.parliamentaryMembership", "R.term"],
        "answer": {"shape": "list", "unit": "distinct Member IRI", "scope": "positive local recorded evidence; not a certified complete roster"},
        "retainAllWitnesses": True,
    }
    parse_semantics(request)
    return request


def interpretation(request):
    selections = {s["role"]: s for s in request["requiredSelections"]}
    return (
        f"List distinct Members who, on {request['asOf']}, both serve on "
        f"{selections['K']['committee']['mention']} and represent "
        f"{selections['R']['constituency']['mention']} in the Dáil. "
        "Check each CommitteeMembership, committee incarnation and its own House term, "
        "and each Dáil representation membership and its own term independently at that date "
        "(inclusive endpoints; absent ends remain open-ended). Join only the exact Member identity. "
        "Return readable names with both supporting relationships and source evidence. "
        "This is positive local recorded evidence, not a certified complete roster."
    )


def execute_confirmed(request, transport, *, budget=None):
    budget = budget if budget is not None else Budget()
    report = execute(request, transport, budget=budget)
    result = None
    if report["status"] != "answer":
        return report, result
    try:
        # Presentation evidence is another bounded lookup, never an IRI suffix or
        # a model-generated Member name. It shares the plan's request/page budget.
        members = report["answer"]["members"]
        r = Read()
        lookup = Lookup("display", (r.p("member", "foaf:name", "name"),),
                        "VALUES ?member { " + " ".join(URIRef(m).n3() for m in members) + " }",
                        {"anchor": "Member names", "members": members})
        facts, _ = retrieve(lookup, transport, budget)
        witness_facts = set()
        # Retain the typed facts internally from the actual evidence JSON, without
        # reparsing display strings or capped debug output.
        from .composition_transport import decode_select
        for pair in report["answer"]["witnesses"]:
            for witness in pair:
                for fact in witness["facts"]:
                    _, rows = decode_select({"head": {"vars": list(fact)}, "results": {"bindings": [fact]}})
                    witness_facts.add(Fact(**rows[0]))
        names = {}
        recorded_names = {}
        display = []
        for member in members:
            e = Evidence(witness_facts | facts, validate_as_of(request["asOf"]))
            owner = e.member(URIRef(member))
            values = e.values(URIRef(member), "foaf:name", owner)
            if not values or any(not isinstance(name, Literal) or not str(name).strip()
                                 or name.datatype not in {None, XSD.string, RDF.langString} for name in values):
                raise NLQError("Missing/invalid Member display name evidence.")
            # member.showAs AND member.fullName both map to foaf:name. Preserve
            # the entire source name set; neither choose a winner nor merge
            # distinct Member identities because their names happen to agree.
            recorded_names[member] = sorted({str(name) for name in values})
            names[member] = " / ".join(recorded_names[member])
            display.extend(f.json() for f in e.used if f in facts)
        report["displayEvidence"] = display
        report["names"] = names
        report["recordedNames"] = recorded_names
        result = QueryResult("select", ("Member", "Member identity", "As of"),
                             tuple(sorted((names[m], m, request["asOf"]) for m in members)))
    except NLQError as error:
        report.update(status="nonanswer", error=str(error))
        # No projected answer may escape a presentation/evidence failure.
        report.pop("answer", None)
    return report, result
