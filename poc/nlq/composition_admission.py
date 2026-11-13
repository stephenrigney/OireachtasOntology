"""Independent admission for semantic-planner-selected current Member operations.

The planner supplies typed mentions, scope and projection, not SPARQL. Admission
accounts for every residual word, checks person/projection/relationship cues and
rejects unrepresented operators. It is a bounded vocabulary, NOT a collection
of accepted sentence templates or an AI self-review. Exact resource grounding
and ambiguity remain the kernel's job; mentions cannot hide a clause unless the
whole mention also resolves to a reviewed local name.
"""

import re
import unicodedata

from .composable_plan import _normalise_label, _reviewed_affiliation_labels
from .composition_kernel import SIGNATURES, parse_semantics
from .interpretation import current_relationship_scope
from .errors import NLQError
from .structured_planner import _label_position


FAMILY = "current_member_composition"
MEMBERS = frozenset("member members td tds deputy deputies senator senators people persons representative representatives parliamentarians".split())
REPRESENT = frozenset("represent represents representing representation constituency constituencies".split())
COMMITTEE = frozenset("committee committees serve serves serving sit sits sitting".split())
PARTY = frozenset("party belong belongs belonging affiliation affiliated membership".split())
FUNCTION = frozenset("who whom which what how many count number total list show give name identify find tell can could you please me us they them the a an of on for from in at to among and also both that those these are is do does have has with s current currently now today present parliamentary political recorded local evidence there dail dáil seanad éireann".split())
ALLOWED = MEMBERS | REPRESENT | COMMITTEE | PARTY | FUNCTION


def routing_hint(question, *, current_only=False):
    """Only select semantic planning; this grants no execution authority."""
    # 'on <calendar date>' is not a committee cue. Keep legacy single-R date
    # questions on their existing date-preserving path, including recorded zero.
    from .composable_plan import _ISO_DATE, _TEXT_DATE
    surface = question
    spans = sorted({match.span() for pattern in (_ISO_DATE, _TEXT_DATE) for match in pattern.finditer(question)}, reverse=True)
    for start, end in spans:
        prefix = re.sub(r"\bon\s*$", " ", surface[:start], flags=re.I)
        surface = prefix + " " + surface[end:]
    words = set(re.findall(r"[^\W\d_]+", surface.casefold()))
    if current_only and (re.search(r"\d", question) or words & {
        "was", "were", "did", "had", "represented", "served", "belonged", "past", "previous", "last", "during", "before", "after", "since", "until", "between"}):
        return False
    text = " " + _normalise_label(question) + " "
    try:
        labels_by_iri = _reviewed_affiliation_labels()
    except NLQError:
        labels_by_iri = {}  # Other domains must not depend on the party register.
    normalized_labels = {_normalise_label(label) for labels in labels_by_iri.values() for label in labels}
    # Match the existing resolver's omission of only a terminal generic Party,
    # e.g. Labour, never a substring such as Labour for National Labour Party.
    normalized_labels |= {label.removesuffix(" party") for label in normalized_labels if label.endswith(" party")}
    party = any(" " + label + " " in text for label in normalized_labels)
    representation = bool(words & (REPRESENT | {"td", "tds", "deputy", "deputies", "representative", "representatives"}))
    committee = bool(words & COMMITTEE or "pac" in words or "on" in words or
                     ("members" in words and "of" in words and not words & {"dail", "dáil", "seanad"}))
    return (party and (representation or committee)) or (committee and representation)


def validate_requirements(question, selections, shape, temporal, *, expected_selections=2):
    if (not isinstance(selections, list) or len(selections) != expected_selections
            or shape not in {"list", "count", "boolean"} or temporal != "current"):
        raise ValueError("Choose exactly two existing current relationships and a supported Member projection; historical scope cannot be defaulted to current.")
    roles, spans = set(), []
    text = unicodedata.normalize("NFC", question)
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != {"role", "mention"}:
            raise ValueError("Each selection requires only a typed role and exact question mention.")
        role, mention = selection["role"], selection["mention"]
        if (role not in SIGNATURES or role in roles or not isinstance(mention, str)
                or not 1 <= len(mention) <= 200 or mention != mention.strip()
                or _label_position(question, mention) is None):
            raise ValueError("Relationships must have distinct roles and complete, exact user-mentioned names.")
        matches = list(re.finditer(re.escape(unicodedata.normalize("NFC", mention)), text, re.I))
        if len(matches) != 1:
            raise ValueError("Clarify repeated or overlapping resource names; no identity set was inferred.")
        spans.append((matches[0].start(), matches[0].end(), role))
        roles.add(role)
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise ValueError("Relationship names must be independently mentioned.")
    marked = text
    for start, end, role in reversed(spans):
        marked = marked[:start] + " entity" + role + " " + marked[end:]
        text = text[:start] + " " + text[end:]
    context = re.findall(r"[^\W\d_]+", marked.casefold())
    if "K" in roles:
        before = context[:context.index("entityk")]
        governor = next((w for w in reversed(before) if w not in {"the", "a", "an", "current", "currently"}), None)
        if governor in {"represent", "represents", "representing", "representation"}:
            raise ValueError("Representing a committee is not committee membership; that relationship cannot be substituted.")
    words = re.findall(r"[^\W\d_]+", text.casefold())
    vocabulary = set(words)
    unknown = vocabulary - ALLOWED
    if re.search(r"\d|[^\w\s,:?.!'’\-]", text) or unknown:
        detail = ", ".join(sorted(unknown))[:180]
        raise ValueError("The complete question includes an unsupported condition, date, negation or answer field; nothing was discarded" + (": " + detail if detail else "."))
    for index, word in enumerate(words):
        if word in {"can", "could"} and (words[index + 1:index + 2] != ["you"] or
                not any(w in {"show", "list", "name", "identify", "find", "tell", "give"} for w in words[index + 2:])):
            raise ValueError("A hypothetical/modal relationship cannot be replaced by current membership evidence.")
    present_cues = vocabulary & (MEMBERS | {"belong", "belongs", "affiliated", "serve", "serves", "sit", "sits", "list", "show", "identify", "find", "represent", "represents"})
    if current_relationship_scope(question, *(s["mention"] for s in selections)) is None and not present_cues:
        raise ValueError("Only present/current relationship scope can use the backend asOf default.")
    count = bool(vocabulary & {"count", "number", "total"} or {"how", "many"} <= vocabulary)
    if count:
        aggregate_index = next(i for i, word in enumerate(words) if word in {"count", "number", "total", "how"})
        member_index = next((i for i, word in enumerate(words) if word in MEMBERS), len(words))
        if aggregate_index > member_index:
            raise ValueError("Clarify the requested aggregate; a predicate or extra answer field cannot replace a distinct-Member count.")
    # A Boolean request is not interchangeable with a positive list or count.
    projection_cues = {"who", "whom", "which", "what", "list", "show", "name", "identify", "find", "count", "how", "number", "total"}
    auxiliaries = {"are", "is", "do", "does", "can", "could", "have", "has"}
    first = next((i for i, word in enumerate(words) if word in projection_cues | auxiliaries), None)
    boolean = "whether" in vocabulary
    if first is not None and words[first] in auxiliaries:
        # "Can you show/list..." is a polite request, whereas "Can Members..."
        # and "Tell me, are there Members who..." request a Boolean/modal answer.
        polite = words[first] in {"can", "could"} and words[first + 1:first + 2] == ["you"]
        following = next((w for w in words[first + 2:] if w in projection_cues | auxiliaries), None)
        implicit_list = following is None and bool(set(words[first + 2:]) & {"tell", "give"})
        boolean = boolean or not (polite and (following in projection_cues or implicit_list))
    if shape == "boolean" or boolean:
        raise ValueError("Yes/no composition is not supported by the kernel. Ask for a Member list instead; no Boolean or partial list was substituted.")
    if (shape == "count") != count:
        raise ValueError("Preserve the requested distinct-Member count versus list projection.")
    if shape == "count" and "K" in roles:
        raise ValueError("Committee-containing compositions support Member lists only, not counts.")
    # Inspect the answer head independently of the model's Member declaration.
    noun_index = next((i for i, w in enumerate(words) if w in MEMBERS | {"party", "constituency", "constituencies", "committee", "committees"}), None)
    member_head = noun_index is not None and (words[noun_index] in MEMBERS or
                  (words[noun_index] in {"party", "committee"} and words[noun_index + 1:noun_index + 2] and words[noun_index + 1] in MEMBERS))
    person_head = first is not None and words[first] in {"who", "whom"}
    if not (person_head or member_head):
        raise ValueError("The supported answer target is Members, not parties, constituencies or other fields.")
    if "R" in roles and not (vocabulary & REPRESENT or vocabulary & {"td", "tds", "deputy", "deputies", "representative", "representatives"}):
        raise ValueError("Constituency representation is not independently expressed in the question.")
    if "K" in roles and not (vocabulary & COMMITTEE or vocabulary & PARTY or vocabulary & {"member", "members", "on"}):
        raise ValueError("Committee membership is not independently expressed in the question.")
    if "P" in roles and not (vocabulary & PARTY or vocabulary & MEMBERS):
        raise ValueError("Party membership is not independently expressed in the question.")
    if "R" not in roles and vocabulary & REPRESENT:
        raise ValueError("The question's constituency representation requirement is absent from the proposal.")
    if "K" not in roles and vocabulary & {"committee", "committees"}:
        raise ValueError("The question's committee requirement is absent from the proposal.")
    if "P" not in roles and vocabulary & (PARTY - {"membership"}):
        raise ValueError("The question's party membership requirement is absent from the proposal.")
    if "R" in roles and vocabulary & {"senator", "senators", "seanad"}:
        raise ValueError("Dáil representation cannot replace a Senator/Seanad condition.")
    houses = ["Dail"] if vocabulary & {"td", "tds", "deputy", "deputies", "dail", "dáil"} or "R" in roles else ["Seanad"] if vocabulary & {"senator", "senators", "seanad"} else ["Dail", "Seanad"]
    if vocabulary & {"td", "tds", "deputy", "deputies", "dail", "dáil"} and vocabulary & {"senator", "senators", "seanad"}:
        raise ValueError("Clarify the House requirement; simultaneous cross-House membership was not inferred.")
    return houses


def validate_draft(value, question):
    refs = value["referents"]
    if (not isinstance(refs, dict) or set(refs) != {"selections", "shape", "temporal"}
            or value["relations"] or value["constraints"] or value["answer"] is not None):
        raise ValueError("Current composition requires only its typed selections, scope and projection; no hidden extra plan fields.")
    houses = validate_requirements(question, refs["selections"], refs["shape"], refs["temporal"])
    return {"family": FAMILY, **refs, "partyHouses": houses}


def validate_legacy_current_requirements(question, selections, shape):
    # Preserve the already-approved legacy party/current-Dáil rule: even a
    # past-tense 'represented ... in the current Dáil' uses both asOf intervals.
    # Only that independently expressed scope is accounted for here; all other
    # words/conditions still go through the same complete-question checks.
    if re.search(r"\bcurrent\s+d[áa]il\b", question, re.I):
        # An answer asking WHICH term is not a Member projection.
        head = re.findall(r"[^\W\d_]+", question.casefold())
        noun = next((w for w in head if w in MEMBERS | {"term", "terms"}), None)
        if noun in {"term", "terms"}:
            raise ValueError("A House-term answer cannot be replaced by Members.")
        question = re.sub(r"\bcurrent\s+d[áa]il(?:\s+term)?\b", "today", question, flags=re.I)
        question = re.sub(r"\brepresented\b", "represent", question, flags=re.I)
        question = re.sub(r"\bwere\b", "are", question, flags=re.I)
    return validate_requirements(question, selections, shape, "current")


def make_request(plan, question, as_of):
    houses = validate_requirements(question, plan["selections"], plan["shape"], plan["temporal"])
    selections = []
    for item in sorted(plan["selections"], key=lambda s: s["role"]):
        role = item["role"]
        relationship, parameter, _ = SIGNATURES[role]
        selection = {"role": role, "relationship": relationship, parameter: {"mention": item["mention"]}}
        if role == "R": selection["house"] = "Dail"
        if role == "P": selection["houses"] = houses
        selections.append(selection)
    roles = {s["role"] for s in selections}
    shared = ["Member"]
    if {"R", "P"} <= roles:
        shared += ["R.parliamentaryMembership=P.containingMembership", "R.term=P.term"]
    request = {"id": "validated-natural-language-composition", "asOf": as_of.isoformat(),
               "requiredSelections": selections, "exactSharedBindings": shared,
               "currentAtRoles": [f"{s['role']}.{name}" for s in selections for name in SIGNATURES[s["role"]][2]],
               "answer": {"shape": plan["shape"], "unit": "distinct Member IRI", "scope": "positive local recorded evidence; not a certified complete roster"},
               "retainAllWitnesses": True}
    parse_semantics(request)
    return request


def execute_plan(plan, *, question, as_of, transport):
    from .composable_plan import PlanOutcome
    from .composition_workflow import execute_request, interpretation
    request = make_request(plan, question, as_of)
    report, result = execute_request(request, transport)
    status = "success" if result is not None else "ambiguous" if report["status"] == "ambiguous" else "source_data_unavailable"
    return PlanOutcome(status, diagnostic=report.get("error") or interpretation(request),
                       result=result, request_family=FAMILY,
                       composition_request=request, composition_report=report)
