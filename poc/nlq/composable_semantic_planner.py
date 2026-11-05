"""Strict semantic interpretation for the bounded composable v2 slice.

The model proposes only v2 referents, reviewed relation IDs, and an answer
role. Local validation owns relation authority, identity resolution, graph
ownership, SPARQL generation, and execution.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from .config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL
from .structured_planner import (
    ResponsesPlanGenerator,
    _label_position,
    _reject_model_ir_is,
    parse_draft_json,
)


_ROOT = Path(__file__).resolve().parents[1]
DRAFT_SCHEMA_PATH = _ROOT / "specs" / "composable-query-plan-draft.schema.json"
_PLAN_CONTRACT_PATH = _ROOT / "specs" / "composable-query-plan-contract.json"
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_DAIL_ORDINAL = re.compile(r"\b(?P<number>[0-9]{1,3})(?P<suffix>st|nd|rd|th)\b", re.IGNORECASE)
_LATEST_TERM_REFERENCE = re.compile(
    r"\b(?:latest\s+recorded|most\s+recent)\b|\blast(?:\s+recorded)?\s+(?:dáil\s+)?term\b",
    re.IGNORECASE,
)


class InvalidComposableDraft(ValueError):
    """A model proposal is incomplete, malformed, or internally inconsistent."""


class InvalidComposableOutput(ValueError):
    """The planner did not return one parseable strict-JSON document."""


class UnsupportedComposableRequest(ValueError):
    """The requested semantics are outside the reviewed v2 slice."""


def _plan_contract() -> dict[str, Any]:
    return json.loads(_PLAN_CONTRACT_PATH.read_text(encoding="utf-8"))


def load_composable_draft_schema() -> dict[str, Any]:
    return json.loads(DRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _explicit_latest_term_reference(question: str) -> bool:
    """Recognize explicit wording for the existing latest-recorded selector."""
    return _LATEST_TERM_REFERENCE.search(question) is not None


def build_composable_planner_instructions() -> str:
    """Render planner context from the existing v2 semantic contract."""
    contract = _plan_contract()
    shared_terms = next(
        item for item in contract["questionFamilies"]
        if item["id"] == "shared_dail_terms"
    )
    member_composition = next(
        item for item in contract["questionFamilies"]
        if item["id"] == "member_relationship_composition"
    )
    relations = {item["id"]: item for item in contract["relations"]}
    dispatch_capabilities = contract.get("semanticDispatch", {}).get("capabilities", [])
    dispatch_guidance = "\n".join(
        f'- Existing capability "{item["id"]}" ({item["handler"]}; input {item["input"]}): {item["semantics"]}'
        for item in dispatch_capabilities
    )
    relation_guidance = "\n".join(
        f"- {fact}: {relations[fact]['subjectType']} to {relations[fact]['objectType']}"
        for fact in (
            "member_has_membership", "membership_in_term",
            "membership_represents", "constituency_in_term",
            "member_party_membership", "party_episode_in_membership",
            "episode_in_parliamentary_party", "party_active_during_term",
            "parliamentary_party_has_affiliation_identity",
        )
    )
    return f"""Interpret one user question as a semantic proposal for composable query plan v2.

Interpretation contract: for the one-term, one-constituency Member list/count, the explicit phrase "in this Dáil" selects the exact House-date-resolved current term and is term-wide, regardless of whether the question says "represent" or "represented". It overrides only the implicit present-tense-as-of default: do not require an asOf membership interval unless the user explicitly asks for current representation (for example, "currently", "now", "today", or "as of now/today"). A literal calendar date remains its exact membership-date point. Without the explicit "this Dáil" scope, an unqualified present-tense constituency request defaults to representation at the query date; an explicit current-point request also requires the DailMembership interval to contain asOf. Dated party/representation composition retains its separate rule that currentTerm requires both party and DailMembership intervals to contain asOf. Never default numbered-term, other dated, historical, or election questions. The plain term-scoped constituency Member projection supports one explicit membership calendar-date point; preserve it as a membershipInterval constraint, never as a HouseTerm date or election event. For a Member's latest recorded Dáil term and constituency, use the constituency_representation family with selector "latestRecorded" when the question explicitly asks for the latest recorded term, the most recent term, or the last term (including "last term in the Dáil"). Local code selects from that Member's accepted DailMembership identities and House-owned chronology, and fails closed on missing/tied/conflicting dates or representation evidence. This is not an election-date answer.
For partial-name person lookup use capability_selection member_lookup with parameters {{"member":"exact name mention","house":"Dail"}} for Deputy/TD, "Seanad" for Senator, or null for unqualified Member. Local code offers grounded alternatives; never expand a surname to an assumed full name.
For a numbered-Dáil party listing use capability_selection dail_parties_and_groups with parameters {{"termNumber":N,"includeGroups":false}}; true only if groups are also requested. This reuses the existing party compiler, not the constituency composition.
For a named person's office tenure use capability_selection office_holding_evidence with parameters {{"member":"exact mention","office":"exact office mention"}}. This checks accepted local OfficeHolding evidence only; unreviewed observations cannot answer tenure. A first-election date is unsupported: election-event evidence is not queryable, and a membership start is not an election date. Never substitute service entry for election.

For who held a named office on a calendar date, during a complete month/year, or over an explicit month-to-month window, use capability_selection office_holding_window with exactly one of {{"office":"exact mention","date":"1994-06-01"}}, {{"office":"exact mention","year":1994}}, or {{"office":"exact mention","startMonth":6,"startYear":1994,"endMonth":6,"endYear":1994}}. Preserve date-point vs full-window semantics. Local code reuses the accepted dated OfficeHolding compiler and incomplete-coverage qualification; an overlap does not mean service throughout the window.

Bounded operators extend the SAME member_relationship_composition graph below, not new families. Dispatch priority: when the question asks for other/another named-party TDs or Deputies sharing the same constituency as a named Member while/when/during that Member held a named office, use the independent anchor/answer shared-constituency operator below, not the ordinary single-member party/representation shape. Keep separate membership paths for the anchor and answer Member and join them to the same exact constituency and term identities. Preserve all nine edges in the base party/representation graph below, including constituency_in_term, then append the five anchor/office edges in the anchor operator for fourteen relations total; do not drop or replace any base edge. The named office episode anchors the common time intersection; do not invent or require a numbered-term selector.
- For one explicitly numbered or House-date-resolved current Dáil and one named constituency, a distinct-Member count uses the exact same referents, relationships and optional membership-date point as the entity-list projection. Use answer {{"kind":"count","referent":"member","distinctBy":"identity"}} only when asked for a count; count recorded Member RDF identities, not seats or election events. In this non-party projection, unqualified "in this Dáil" means term-wide membership regardless of "represent"/"represented"; it overrides the implicit present-tense asOf default. Explicit "currently"/"now"/"today" or "as of now/today" requests additionally require the DailMembership interval to contain asOf. A literal date remains its exact date constraint. Never count a partial/truncated page or drop a date/constituency/term condition to return a number.
- For any one-term, one-constituency non-party Member list or count—including "this Dáil"—prefer family "member_relationship_composition" with referents member, membership, term, constituency and the four exact representation edges, rather than family "constituency_representation". The list answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}; only an explicit count uses {{"kind":"count","referent":"member","distinctBy":"identity"}}. This keeps the list and count on the same bounded selection. Select the exact House-date current Dáil for "this Dáil"; add the asOf membership interval only for an explicit current-point request or the ordinary unqualified present-tense default without "this Dáil". Do not use this exception for numbered, explicitly dated, election, or party-filtered requests.
- For an explicitly named OR set of two to four constituencies, replace constituency with {{"type":"DailConstituency","members":[{{"type":"DailConstituency","mention":"exact first mention"}},{{"type":"DailConstituency","mention":"exact second mention"}}]}}. All existing edges and the party/membership overlap constraint and Member evidence answer remain unchanged. Local code resolves each occurrence in the same selected term and compiles one VALUES identity set; never merge string results. Never infer a set from 'the two Galway constituencies'; that is ambiguous (Roscommon-Galway may also be relevant).
- For other named-party TDs sharing a constituency with a named anchor Member while that anchor held a named office, keep member, membership, episode, party, affiliation and their edges as below; term is {{"type":"DailTerm","mention":null}} and constituency is {{"type":"DailConstituency","mention":null}} (unselected shared resource identities). Add anchor (Member, exact named mention), anchor_membership (DailMembership, null mention), holding (OfficeHolding, null mention), office (NamedOffice, exact office mention). Add edges member_has_membership anchor→anchor_membership, membership_in_term anchor_membership→term, membership_represents anchor_membership→constituency, member_has_office_holding anchor→holding, office_holding_of_office holding→office. Keep both independent membership paths to the SAME exact constituency and term. No numbered-term clarification is needed: the accepted office episode anchors time. Constraints are exactly [{{"referent":"episode","field":"partyEpisodeInterval","operator":"overlaps","value":"membership"}},{{"referent":"member","field":"identity","operator":"distinctFrom","value":"anchor"}},{{"referent":"holding","field":"interval","operator":"commonIntersection","value":["holding","anchor_membership","membership","episode"]}}]. The answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}},{{"referent":"holding","display":["start","end"]}},{{"referent":"anchor_membership","display":["start","end"]}},{{"referent":"constituency","display":["label"]}}],"preserveEvidence":true}}. Local code requires one common inclusive intersection of ALL four independently owned intervals, not merely pairwise overlaps, and reports partial accepted-evidence coverage, never a complete roster. Additional filters or projections remain unsupported as a whole.

Existing shared-term capability: {shared_terms['semantics']}

Reusable Member relationship capability: {member_composition['semantics']}

Existing validated single-family capabilities:
{dispatch_guidance}

When one of those existing capabilities directly answers the request, use family "capability_selection", put its exact ID in referents.capability, and provide only the matching semantic inputs in referents.parameters. For seanad_entry use {{"member":"the exact grounded Member name"}}. For bill_lookup use {{"billNumber":"the explicitly supplied Bill number","billYear":2025}}. Set relations to [], constraints to [], and answer to null. Local code checks the inputs against the question, then invokes the same validated Stage A/B/C plan builder and executor used by deterministic recognition, or the named evidence-boundary resolver. Never use this route to answer another relationship or drop a requested condition.

Use the existing semantic relationship identifiers below; these are proposals, not authority decisions:
{relation_guidance}

For the existing shared-term capability, use family "shared_dail_terms" and fixed referent keys member_a, membership_a, member_b, membership_b, and shared_term. Member entries use exact user-supplied labels. Each Member has an independent DailMembership path to the same shared DailTerm identity; set "constraints": [] and set "answer" to exactly {{"kind":"entities","referent":"shared_term","distinctBy":"identity","display":["label"],"details":[],"preserveEvidence":false}}.

For the reusable Member relationship capability, use family "member_relationship_composition" and one Member answer referent with a null mention. Every DailTerm referent must carry selector {{"kind":"termNumber","number":N}} for an explicitly requested numeric Dáil ordinal. For a one-term, one-constituency non-party Member selection, use selector {{"kind":"currentTerm"}} for an explicit current/now request, the approved unqualified present-tense default, or "this Dáil"; local code selects one exact House-dated term. In this exact shape, unqualified "in this Dáil" is term-wide regardless of represent/represented and overrides the implicit present-tense asOf condition. Explicit currently/now/today/as-of-current requests still preserve the appropriate membership interval; explicit calendar dates remain exact date points. This does not change numbered or election questions. In this family, selector is always an object: never use the string "currentTerm" or "latestRecorded". Use selector {{"kind":"currentTerm"}} in the dated party/representation shape only for explicit current/now or the approved unqualified present-tense default; there, both episode and representation intervals must contain asOf. Use one of these complete typed graph shapes only:
- keys member, membership_a, term_a, membership_b, and term_b: two distinct selected DailTerms, each reached from the same answer Member through a separate DailMembership; this returns Members with recorded membership in both exact term identities;
- keys member, membership, term, and constituency: one selected DailTerm and one exact user-mentioned DailConstituency, where the same DailMembership links the Member to that term and constituency, and the constituency occurrence links to that same term identity.
Use distinct referent IDs for separate membership/term resources. Do not substitute matching labels for RDF identity joins. Preserve every selected term and the constituency when required. For the two-term intersection, use "constraints": [] and the exact entity-list answer. For one term-scoped constituency selection, preserve an explicit date point with exactly one constraint {{"referent":"membership","field":"membershipInterval","operator":"on","value":"1994-06-01"}}; otherwise use an empty constraints list. Local code supplies the asOf date point for an approved current-representation request; do not invent a date in the draft. Return an entity list with the exact answer value {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}, or, only for an explicit how-many/count request, use {{"kind":"count","referent":"member","distinctBy":"identity"}}. Counts are distinct recorded Member IRIs from the same selection as the list, not seats or election events; never count a truncated or uncertain result.

For a dated political-party/constituency composition, use family "member_relationship_composition" and exactly the referents member, membership, term, constituency, episode, party, and affiliation. Connect member→membership→term, membership→constituency, constituency→term, member→episode, episode→membership, episode→party, party→term, and party→affiliation using their exact reviewed fact IDs. The episode must point to the exact same DailMembership that represents the constituency in the selected term. Set "constraints" to exactly [{{"referent":"episode","field":"partyEpisodeInterval","operator":"overlaps","value":"membership"}}] (inclusive xsd:dateTime endpoints; an absent end is open-ended; missing interval/start means uncertain, never a positive or negative match). When selector is "currentTerm", the local executor additionally requires both the DailMembership and PartyMembership intervals independently to contain the supplied asOf date; the model must not substitute only term membership for current service. Only typed PartyMembership records count; Independent is not a party. For "which parties" questions, use a null affiliation mention and set "answer" to exactly {{"kind":"entities","referent":"affiliation","distinctBy":"identity","display":["label"],"details":[{{"referent":"member","display":["name"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. For every named-party TD list, keep the exact named affiliation mention as a required identity filter and set "answer" to exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. Never use party-label equality or term context as a substitute for the dated episode and exact identity links.

For a named-party TD list or count in one explicitly numbered Dáil when no constituency is requested, use the party-only term shape with exactly member, membership, term, episode, party, and affiliation referents and these seven edges: member→membership→term; member→episode→membership; episode→party→term; party→affiliation. Omit constituency and representation edges because they were not requested. Require the same exact PartyMembership/DailMembership identity join and inclusive interval-overlap constraint above. Resolve the named PoliticalAffiliationIdentity only among ParliamentaryParty identities active in the exact numbered term, using the existing term-scoped party listing path; count distinct Member IRIs only after the exact party filter and temporal validation. The list answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}; only an explicit count uses {{"kind":"count","referent":"member","distinctBy":"identity"}}. Do not count ParliamentaryParty records, seats, or elections; missing/conflicting intervals, identity links, or truncated evidence fail closed, and recorded counts do not imply a complete roster. This party-only shape does not support currentTerm, extra filters, or additional relationships.

Additional implemented capabilities (do not declare these unsupported):
- Party history, including ordinary 'join', 'belonged to' and 'member of' paraphrases, uses family "member_party_history", referents member (named Member), episode (PartyMembershipEpisode), party (ParliamentaryParty), affiliation (PoliticalAffiliationIdentity). Only member has a non-null mention. Edges are member_party_membership member→episode, episode_in_parliamentary_party episode→party, parliamentary_party_has_affiliation_identity party→affiliation. Answer affiliation with display ["label"], details [], preserveEvidence true. This asks about recorded party membership, not joining events; Independent is not a party.
- Bills sponsored by a named Member uses family "member_bill_sponsorship", referents member (named Member), bill (Bill), participation (BillParticipation). Only member has a non-null mention. Edges are bill_has_sponsor_participation bill→participation and participation_has_participant participation→member. Answer bill with display ["label"], details [], preserveEvidence true. Local projection supplies Bill titles/numbers/links and primary, supporting or unknown-primary evidence; never restrict to primary sponsorship.
 - Constituency representation uses family "constituency_representation", referents member, membership (DailMembership), term (DailTerm), constituency (DailConstituency). Exactly one of member/constituency has a user-mentioned label; all others have null mentions. term may use selector "currentTerm" for present-tense/current questions, "latestRecorded" only for a named Member's latest House-dated Dáil term, or null for a named Member's career-wide/historical constituencies. Connect member_has_membership member→membership, membership_in_term membership→term, membership_represents membership→constituency, constituency_in_term constituency→term. Answer the unmentioned member (display ["name"]) or constituency (display ["label"]), details [{{"referent":"term","display":["label"]}}], preserveEvidence true. Current is date-relative, never a guessed ordinal.
For the three additional entity-history capabilities, constraints is []. Constituency representation supports only the explicit membership date point stated above; the bounded Member count is the only aggregate allowed for that same one-term, one-constituency selection. Preserve all other conditions; extra party, office, temporal-window or aggregate projections are not supported by these slices.

Constitutional Government members of a named party at the reference date are also implemented: family "government_party_members"; referents member (Member), cabinet (CabinetMembership), government (Government), episode (PartyMembershipEpisode), party (ParliamentaryParty), affiliation (PoliticalAffiliationIdentity). Only affiliation has a non-null user-mentioned label. Use member_has_cabinet_membership member→cabinet, cabinet_membership_of_government cabinet→government, member_party_membership member→episode, episode_in_parliamentary_party episode→party, parliamentary_party_has_affiliation_identity party→affiliation. Use constraints []; local code supplies the reference-date point constraints. Answer member, display ["name"], details [{{"referent":"affiliation","display":["label"]}},{{"referent":"cabinet","display":["start","end"]}},{{"referent":"episode","display":["start","end"]}}], preserveEvidence true. This is constitutional Cabinet membership, not the wider GovernmentExecutive or Government benches; Ministers of State alone do not qualify. Completeness cannot be inferred from the optional office dataset. Requests for the wider executive or additional conditions remain unsupported.

If a question asks for any other relationship, more or fewer terms than the supported shapes, an extra filter, temporal restriction, different answer, or anything outside these capabilities, return supported=false with a concise unsupportedReason, null family, null referents, empty relations, "constraints": [], and null answer. The unsupportedReason must describe the missing capability actually requested (for example, voting evidence, or an unsupported Member relationship). Do not describe every unsupported question as a Member-relationship limitation, and do not mention Dáil or Member capabilities when they are unrelated to the question. For unrelated topics, state briefly that the question is outside the local parliamentary query scope. Never simplify an unsupported request by dropping an essential relation or constraint.

Semantic interpretation only. Never output SPARQL, predicates, graph names, variables, endpoints, URLs, IRIs, candidates, or resolution decisions. Do not decide whether a mapping is authoritative; local code checks all proposed relation IDs against the reviewed v2 and query-schema contracts. Do not add assumptions about source completeness.

Return only the JSON object required by the strict composable-plan-v2 draft schema. All schema fields are required; family, unsupportedReason, referents, and answer are null when not applicable."""


def create_composable_plan_generator() -> ResponsesPlanGenerator:
    """Create the existing one-call Responses transport for a v2 draft schema."""
    return ResponsesPlanGenerator(
        os.getenv("NLQ_LLM_API_KEY", ""),
        os.getenv("NLQ_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        os.getenv("NLQ_LLM_MODEL", DEFAULT_LLM_MODEL),
        output_schema=load_composable_draft_schema(),
        schema_name="composable_query_plan_v2_draft",
        instructions=build_composable_planner_instructions(),
    )


def _identifier(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise InvalidComposableDraft(f"{where} must be a semantic identifier.")
    return value


def validate_composable_plan_draft(
    value: Any,
    *,
    question: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a model proposal and return a final-envelope-ready v2 plan.

    The supported projection is intentionally exact. This is what prevents a
    missing participant, relationship edge, or shared term identity from being
    silently simplified into a weaker query.
    """
    try:
        _reject_model_ir_is(value)
    except ValueError as error:
        raise InvalidComposableDraft(str(error)) from error

    required = {
        "version", "supported", "family", "unsupportedReason", "intent",
        "referents", "relations", "constraints", "answer",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise InvalidComposableDraft(
            "The composable v2 proposal must contain exactly version, support state, intent, referents, relations, and answer."
        )
    if type(value["version"]) is not int or value["version"] != 2:
        raise InvalidComposableDraft("The semantic proposal must use composable plan version 2.")
    if not isinstance(value["intent"], str) or not value["intent"].strip():
        raise InvalidComposableDraft("The semantic proposal requires a non-empty interpretation.")
    if type(value["supported"]) is not bool:
        raise InvalidComposableDraft("The semantic support state must be Boolean.")
    if not isinstance(value["relations"], list) or not isinstance(value["constraints"], list):
        raise InvalidComposableDraft("Relations and constraints must be arrays.")

    if value["supported"] is False:
        reason = value["unsupportedReason"]
        if (not isinstance(reason, str) or not reason.strip()
                or value["family"] is not None or value["referents"] is not None
                or value["relations"] or value["constraints"] or value["answer"] is not None):
            raise InvalidComposableDraft(
                "An unsupported proposal must provide a reason and no executable semantic plan."
            )
        return None, reason.strip()
    if value["unsupportedReason"] is not None:
        raise InvalidComposableDraft("A supported proposal cannot also carry an unsupported reason.")

    from .interpretation import unsupported_whole_intent
    reason = unsupported_whole_intent(question)
    if reason:
        raise InvalidComposableDraft(reason)
    count_intent = bool(re.search(r"\b(?:how many|count|number of|total of)\b", question, re.I))
    if (count_intent and re.search(r"\bseats?\b", question, re.I)
            and value["family"] == "member_relationship_composition"):
        raise UnsupportedComposableRequest(
            "Seat allocations are not recorded Member identities; no seat or election-event count was substituted."
        )
    if count_intent and (value["family"] != "member_relationship_composition"
                         or not isinstance(value.get("answer"), dict)
                         or value["answer"].get("kind") != "count"):
        raise UnsupportedComposableRequest(
            "The requested count cannot be converted to a list or another aggregate; use only the validated Member identity count projection."
        )

    if re.search(r"\b(?:same|shared)\s+constituency\b", question, re.I):
        if (value["family"] != "member_relationship_composition"
                or not isinstance(value["referents"], dict) or "anchor" not in value["referents"]):
            raise InvalidComposableDraft("The requested independent Member/shared-constituency operator is absent; no simplified plan is accepted.")

    if value["family"] == "capability_selection":
        return _validate_capability_selection_draft(value, question=question), None

    if value["family"] in {"constituency_representation", "member_party_history", "member_bill_sponsorship", "government_party_members"}:
        return _validate_existing_capability_draft(value, question=question), None

    if value["family"] == "member_relationship_composition":
        refs = value.get("referents")
        if isinstance(refs, dict) and ("anchor" in refs or "members" in refs.get("constituency", {})):
            return _validate_bounded_composition_draft(value, question=question), None
        return _validate_member_relationship_draft(value, question=question), None
    if value["family"] != "shared_dail_terms":
        raise UnsupportedComposableRequest(
            f"Composable semantic family {value['family']!r} is not supported."
        )

    referent_roles = {
        "member_a": "Member",
        "membership_a": "DailMembership",
        "member_b": "Member",
        "membership_b": "DailMembership",
        "shared_term": "DailTerm",
    }
    if value["constraints"]:
        raise InvalidComposableDraft("Shared-Dáil-term plans do not accept temporal or extra constraints.")
    if not isinstance(value["referents"], dict) or set(value["referents"]) != set(referent_roles):
        raise InvalidComposableDraft(
            "A supported shared-Dáil-term proposal requires the fixed member_a, membership_a, member_b, membership_b, and shared_term referents."
        )
    referents: dict[str, dict[str, Any]] = {}
    for referent_id, expected_type in referent_roles.items():
        item = value["referents"][referent_id]
        if not isinstance(item, dict) or set(item) != {"type", "mention"}:
            raise InvalidComposableDraft(
                f"Referent {referent_id!r} must contain exactly type and mention."
            )
        if not isinstance(item["type"], str) or item["type"] != expected_type:
            raise UnsupportedComposableRequest(
                f"Referent {referent_id!r} must have reviewed type {expected_type!r}."
            )
        mention = item["mention"]
        if referent_id in {"member_a", "member_b"}:
            if not isinstance(mention, str) or not mention.strip():
                raise InvalidComposableDraft("Member referents require non-empty user-supplied labels.")
            referents[referent_id] = {"type": expected_type, "mention": mention.strip()}
        else:
            if mention is not None:
                raise InvalidComposableDraft("Only the two Member referents may carry user-supplied labels.")
            referents[referent_id] = {"type": expected_type}

    member_ids = ["member_a", "member_b"]
    membership_ids = ["membership_a", "membership_b"]
    term_ids = ["shared_term"]
    for referent_id in member_ids:
        mention = referents[referent_id].get("mention")
        if not isinstance(mention, str) or _label_position(question, mention) is None:
            raise InvalidComposableDraft(
                f"Member referent {referent_id!r} must be an exact user-supplied name mention."
            )
    normalized_mentions = [
        unicodedata.normalize("NFC", referents[key]["mention"]).casefold()
        for key in member_ids
    ]
    if normalized_mentions[0] == normalized_mentions[1]:
        raise InvalidComposableDraft(
            "The two Member referents must be independently named, not repeated copies of one name."
        )
    if len(value["relations"]) != 4:
        raise InvalidComposableDraft(
            "Both Members require a complete Member → DailMembership → shared DailTerm path."
        )
    actual_edges: list[tuple[str, str, str]] = []
    relation_ids: set[str] = set()
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Relation IDs must be unique.")
        relation_ids.add(relation_id)
        fact = relation["fact"]
        if (not isinstance(fact, str)
                or fact not in {"member_has_membership", "membership_in_term"}):
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the reviewed shared-Dáil-term composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if source not in referents or target not in referents:
            raise InvalidComposableDraft("Every relationship endpoint must name a declared referent.")
        actual_edges.append((fact, source, target))

    term_id = term_ids[0]
    expected_edges: list[tuple[str, str, str]] = []
    seen_memberships: set[str] = set()
    for member_id in member_ids:
        linked = [
            edge for edge in actual_edges
            if edge[0] == "member_has_membership" and edge[1] == member_id
        ]
        if len(linked) != 1 or referents[linked[0][2]]["type"] != "DailMembership":
            raise InvalidComposableDraft(
                f"Member referent {member_id!r} must have exactly one typed DailMembership relationship."
            )
        membership_id = linked[0][2]
        if membership_id in seen_memberships:
            raise InvalidComposableDraft("Each Member requires an independent DailMembership referent.")
        seen_memberships.add(membership_id)
        expected_edges.extend([
            ("member_has_membership", member_id, membership_id),
            ("membership_in_term", membership_id, term_id),
        ])
    if sorted(actual_edges) != sorted(expected_edges):
        raise InvalidComposableDraft(
            "Every DailMembership must link to the same answer DailTerm identity; disconnected or extra edges are not supported."
        )

    expected_answer = {
        "kind": "entities", "referent": term_id,
        "distinctBy": "identity", "display": ["label"],
    }
    if value["answer"] != {
        **expected_answer, "details": [], "preserveEvidence": False,
    }:
        raise InvalidComposableDraft(
            "The answer must be the distinct shared DailTerm identity set with its mapped label."
        )

    plan_referents: dict[str, dict[str, Any]] = {}
    for referent_id, item in referents.items():
        final = {"type": item["type"]}
        if "mention" in item:
            final["mention"] = item["mention"]
            final["resolution"] = "unresolved"
        if referent_id == term_id:
            final["answer"] = True
        plan_referents[referent_id] = final

    return {
        "family": "shared_dail_terms",
        "referents": plan_referents,
        "relations": [dict(item) for item in value["relations"]],
        "answer": expected_answer,
    }, None


def _validate_existing_capability_draft(value, *, question):
    """Accept only exact, grounded graphs for already implemented compilers."""
    from .composable_plan import plan_question
    from .representation import representation_plan

    refs = value["referents"]
    if not isinstance(refs, dict) or value["constraints"]:
        raise InvalidComposableDraft("This capability does not support extra constraints.")
    for ref in refs.values():
        if not isinstance(ref, dict):
            raise InvalidComposableDraft("Every referent must be a typed object.")
        mention = ref.get("mention")
        if mention is not None and (not isinstance(mention, str) or _label_position(question, mention) is None):
            raise InvalidComposableDraft("Every named referent must be grounded in the user's question.")
    # These slices cannot preserve additional constraints or negation. Do not
    # let a model turn a restricted question into an unrestricted history list.
    condition_text = question
    for ref in refs.values():
        if ref.get("mention"):
            condition_text = re.sub(re.escape(ref["mention"]), " ", condition_text, flags=re.I)
    if re.search(r"\b(?:not|never|except|excluding|only|before|after|since|until|between|while|count|how many|primary|supporting|elected|election|tenure)\b|[0-9]{4}", condition_text, re.I):
        raise UnsupportedComposableRequest("This slice cannot preserve the question's additional constraint.")
    placeholder = date(2000, 1, 1)  # discarded; complete_v2_plan supplies the actual reference date
    family = value["family"]
    if family == "government_party_members":
        from .government import government_plan
        mention = refs.get("affiliation", {}).get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise InvalidComposableDraft("A named party identity is required.")
        if re.search(r"\b(?:executive|benches|ministers? of state|including|committee|constituenc(?:y|ies))\b", condition_text, re.I):
            raise UnsupportedComposableRequest("The constitutional Government slice cannot substitute for a wider executive or additional relationship.")
        plan = government_plan(mention, as_of=placeholder)
        expected_answer = plan["answer"]
    elif family == "constituency_representation":
        if re.search(r"\b(?:senators?|seanad|panels?)\b", condition_text, re.I):
            raise UnsupportedComposableRequest("Dáil constituency representation cannot substitute for Seanad service.")
        from .composable_plan import _reviewed_affiliation_mention_matches
        if (re.search(r"\b(?:party|parties|affiliation|independent|groups?)\b", condition_text, re.I)
                or _reviewed_affiliation_mention_matches(condition_text)):
            raise UnsupportedComposableRequest("A party-filtered representation request requires the dated affiliation graph; no party filter may be dropped.")
        term = refs.get("term", {})
        selector = term.get("selector")
        if selector not in (None, "currentTerm", "latestRecorded"):
            raise InvalidComposableDraft("Invalid relative Dáil selector.")
        member = refs.get("member", {}).get("mention")
        constituency = refs.get("constituency", {}).get("mention")
        if bool(member) == bool(constituency):
            raise InvalidComposableDraft("Exactly one representation participant must be named.")
        if selector is None and re.search(r"\b(?:current|currently|now|does|are|latest|most recent)\b", condition_text, re.I):
            raise InvalidComposableDraft("A current question cannot be converted into career-wide representation.")
        latest_requested = _explicit_latest_term_reference(question)
        if selector == "latestRecorded":
            if not member or constituency or not latest_requested:
                raise InvalidComposableDraft("Latest-recorded Dáil selection requires a named Member and an explicit latest-term reference.")
            if _question_dail_ordinals(question) or re.search(r"\b(?:current|currently|now|today)\b", question, re.I):
                raise InvalidComposableDraft("Latest-recorded selection cannot replace an explicit ordinal or current-date request.")
        elif latest_requested:
            raise InvalidComposableDraft("The explicit latest-recorded Dáil scope cannot be dropped.")
        plan = representation_plan(as_of=placeholder, member=member, constituency=constituency,
                                   current=selector == "currentTerm", latest_recorded=selector == "latestRecorded")
        from .interpretation import present_constituency_default
        explicit_current = bool(re.search(r"\b(?:current|currently|now|today)\b", question, re.I))
        inferred_current = bool(constituency and present_constituency_default(question, constituency))
        member_present = bool(member and re.search(r"\bdoes\b", condition_text, re.I))
        if selector == "currentTerm" and not explicit_current and not inferred_current and not member_present:
            raise InvalidComposableDraft("Current representation must preserve approved temporal scope.")
        if inferred_current and selector != "currentTerm":
            raise InvalidComposableDraft("Present constituency representation requires the approved query-date default.")
        if inferred_current and not explicit_current:
            plan["interpretation"] = {"policy": "present_constituency_as_of", "question": question}
        expected_answer = plan["answer"]
    else:
        mention = refs.get("member", {}).get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise InvalidComposableDraft("A Member name is required.")
        if re.search(r"\b(?:current|currently|now|government|minister|constituenc(?:y|ies))\b", condition_text, re.I):
            raise UnsupportedComposableRequest("This history slice cannot preserve an additional current or relationship condition.")
        canonical = (f"What parties was {mention} a member of?" if family == "member_party_history"
                     else f"Which Bills did {mention} sponsor?")
        plan = plan_question(canonical, as_of=placeholder)
        expected_answer = {"kind": "entities", "referent": "affiliation" if family == "member_party_history" else "bill",
                           "distinctBy": "identity", "display": ["label"], "details": [], "preserveEvidence": True}
    expected_refs = {}
    for key, ref in plan["referents"].items():
        expected_refs[key] = {"type": ref["type"], "mention": ref.get("mention")}
        if key == "term":
            expected_refs[key]["selector"] = selector
    if refs != expected_refs or value["answer"] != expected_answer:
        raise InvalidComposableDraft("The proposed referents or answer differ from the complete supported projection.")
    edges = lambda relations: sorted((item["fact"], item["from"], item["to"]) for item in relations)
    if (any(set(item) != {"id", "fact", "from", "to"} for item in value["relations"])
            or len({item["id"] for item in value["relations"]}) != len(value["relations"])
            or edges(value["relations"]) != edges(plan["relations"])):
        raise InvalidComposableDraft("Every relationship in the supported graph is required exactly once.")
    final = {key: item for key, item in plan.items() if key not in {"version", "asOf"}}
    if family == "government_party_members":
        # The real date is supplied only by complete_v2_plan, not the model.
        final.pop("constraints")
    return final


def _ordinal_suffix(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _validate_member_party_composition_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate the one shared graph and temporal operator used by U06/U16."""
    if re.search(r"\b(?:senators?|seanad|panels?)\b", question, re.I):
        raise UnsupportedComposableRequest("Dáil representation cannot substitute for a Seanad/panel relationship.")
    referents = value["referents"]
    core_types = {
        "member": "Member",
        "membership": "DailMembership",
        "term": "DailTerm",
        "episode": "PartyMembershipEpisode",
        "party": "ParliamentaryParty",
        "affiliation": "PoliticalAffiliationIdentity",
    }
    party_only = isinstance(referents, dict) and set(referents) == set(core_types)
    expected_types = {**core_types, **({} if party_only else {"constituency": "DailConstituency"})}
    if not isinstance(referents, dict) or set(referents) != set(expected_types):
        raise InvalidComposableDraft(
            "Dated party composition requires either the exact party-only term graph or the complete constituency/party graph."
        )

    normalized: dict[str, dict[str, Any]] = {}
    for key, semantic_type in expected_types.items():
        item = referents[key]
        if not isinstance(item, dict) or item.get("type") != semantic_type:
            raise InvalidComposableDraft(f"Referent {key!r} must have reviewed type {semantic_type!r}.")
        if key in {"member", "membership", "episode", "party"}:
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft(f"Referent {key!r} is a typed relationship role, not a name filter.")
            normalized[key] = {"type": semantic_type}
        elif key == "term":
            selector = item.get("selector")
            if set(item) != {"type", "mention", "selector"} or item["mention"] is not None:
                raise InvalidComposableDraft("The term must be one reviewed DailTerm selector.")
            if (isinstance(selector, dict) and set(selector) == {"kind", "number"}
                    and selector.get("kind") == "termNumber"
                    and type(selector.get("number")) is int
                    and 1 <= selector["number"] <= 999):
                normalized[key] = {"type": semantic_type, "selector": selector}
            elif isinstance(selector, dict) and selector == {"kind": "currentTerm"}:
                from .interpretation import present_constituency_default
                constituency = referents.get("constituency", {}).get("mention")
                inferred = isinstance(constituency, str) and present_constituency_default(question, constituency)
                if not re.search(r"\b(?:current|currently|now|today)\b", question, re.IGNORECASE) and not inferred:
                    raise InvalidComposableDraft("A currentTerm selector requires an explicit current/as-of request.")
                normalized[key] = {
                    "type": semantic_type,
                    "selector": {"kind": "currentTerm", "house": "Dail"},
                }
            else:
                raise InvalidComposableDraft("The term must use a numeric termNumber or reviewed currentTerm selector.")
        elif key == "constituency":
            mention = item.get("mention")
            if (set(item) != {"type", "mention"} or not isinstance(mention, str)
                    or not mention.strip() or _label_position(question, mention) is None):
                raise InvalidComposableDraft("The DailConstituency must preserve an exact user-supplied name mention.")
            normalized[key] = {"type": semantic_type, "mention": mention.strip()}
        else:
            mention = item.get("mention")
            if set(item) != {"type", "mention"} or (mention is not None and (
                not isinstance(mention, str) or not mention.strip()
                or _label_position(question, mention) is None
            )):
                raise InvalidComposableDraft("The affiliation must be either a null all-parties selector or an exact named-party mention.")
            normalized[key] = {"type": semantic_type, "mention": mention.strip() if isinstance(mention, str) else None}

    term_selector = normalized["term"]["selector"]
    residual = question
    for item in normalized.values():
        mention = item.get("mention")
        if mention:
            if re.search(r"\b(?:and|or|while|when|elected|election|before|after)\b", mention, re.I):
                raise InvalidComposableDraft("An entity mention cannot consume another requested clause or identity.")
            residual = re.sub(re.escape(mention), " ", residual, flags=re.I)
    count_intent = bool(re.search(r"\b(?:how many|count|number of|total of)\b", question, re.I))
    if count_intent:
        residual = re.sub(r"\b(?:how many|count|number of|total of)\b", " ", residual, flags=re.I)
    if re.search(r"\b(?:and|or|while|same|shared|other|another|election|elected)\b", residual, re.I):
        raise InvalidComposableDraft("The proposed single-constituency graph omits a requested operator or projection.")
    term_numbers = _question_dail_ordinals(question)
    if term_selector["kind"] == "termNumber":
        if len(term_numbers) != 1 or term_numbers[0] != term_selector["number"]:
            raise InvalidComposableDraft("The plan must preserve exactly one explicitly requested numeric Dáil term.")
    elif term_numbers:
        raise InvalidComposableDraft("A currentTerm selector cannot replace an explicitly numbered Dáil term.")
    if party_only and term_selector["kind"] != "termNumber":
        raise UnsupportedComposableRequest("Party-only Member selection is limited to one explicitly numbered Dáil term.")

    party_list_question = bool(re.search(
        r"\b(?:which|what)\s+(?:political\s+)?part(?:y|ies)\b", question, re.IGNORECASE,
    ))
    affiliation_mention = normalized["affiliation"]["mention"]
    if party_only and party_list_question:
        raise UnsupportedComposableRequest("The party-only term shape requires one named party and a Member answer.")
    if party_list_question and affiliation_mention is not None:
        raise InvalidComposableDraft("An all-parties answer cannot silently add a named affiliation filter.")
    if not party_list_question and affiliation_mention is None:
        raise InvalidComposableDraft("A named-party Member answer must retain its party identity filter.")

    contract = _plan_contract()
    relation_defs = {item["id"]: item for item in contract["relations"]}
    expected_edges = {
        "member_has_membership": ("member", "membership"),
        "membership_in_term": ("membership", "term"),
        "member_party_membership": ("member", "episode"),
        "party_episode_in_membership": ("episode", "membership"),
        "episode_in_parliamentary_party": ("episode", "party"),
        "party_active_during_term": ("party", "term"),
        "parliamentary_party_has_affiliation_identity": ("party", "affiliation"),
    }
    if not party_only:
        expected_edges.update({
            "membership_represents": ("membership", "constituency"),
            "constituency_in_term": ("constituency", "term"),
        })
    actual_edges: dict[str, tuple[str, str]] = {}
    relation_ids: set[str] = set()
    if not isinstance(value["relations"], list):
        raise InvalidComposableDraft("Dated party/representation relationships must be an array.")
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        fact = relation["fact"]
        if not isinstance(fact, str) or fact not in expected_edges:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the exact reviewed party/representation composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if relation_id in relation_ids or fact in actual_edges:
            raise InvalidComposableDraft("Dated composition relation IDs and facts must be unique.")
        relation_ids.add(relation_id)
        if (source, target) != expected_edges[fact]:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the exact reviewed party/representation composition."
            )
        if fact not in relation_defs:
            raise UnsupportedComposableRequest(f"Relationship {fact!r} has no reviewed v2 relation mapping.")
        actual_edges[fact] = (source, target)
    if len(value["relations"]) != len(expected_edges):
        raise InvalidComposableDraft("Every dated party/representation relationship edge is required exactly once.")
    if actual_edges != expected_edges:
        raise InvalidComposableDraft("The party episode, DailMembership, term, and affiliation paths must use exact referent identity.")
    for fact, (source, target) in expected_edges.items():
        definition = relation_defs[fact]
        if (expected_types[source], expected_types[target]) != (definition["subjectType"], definition["objectType"]):
            raise UnsupportedComposableRequest(f"Reviewed relationship {fact!r} has incompatible entity types.")

    interval_constraint = {
        "referent": "episode", "field": "partyEpisodeInterval", "operator": "overlaps", "value": "membership",
    }
    if value["constraints"] != [interval_constraint]:
        raise InvalidComposableDraft(
            "The plan must preserve the required PartyMembershipEpisode/DailMembership interval-overlap constraint and no extra constraints."
        )

    if party_list_question:
        answer = {
            "kind": "entities", "referent": "affiliation", "distinctBy": "identity", "display": ["label"],
            "details": [
                {"referent": "member", "display": ["name"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        }
        if value["answer"] != answer:
            raise InvalidComposableDraft("A party-list question must return distinct reviewed identity resources with separate Member/interval evidence.")
    elif count_intent and party_only:
        answer = {"kind": "count", "referent": "member", "distinctBy": "identity"}
        if value["answer"] != answer:
            raise InvalidComposableDraft("A party-only term count must count distinct Member identities after the complete temporal selection.")
    elif count_intent:
        raise UnsupportedComposableRequest(
            "Named-party counts are only supported for the bounded party-only numbered-term selection; no list or simplified count was returned."
        )
    else:
        answer = {
            "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
            "details": [
                {"referent": "affiliation", "display": ["label"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        }
        if value["answer"] != answer:
            raise InvalidComposableDraft("A named-party question must return distinct Member identities and preserve the affiliation/date evidence.")

    final_referents: dict[str, dict[str, Any]] = {}
    for key, semantic_type in expected_types.items():
        if key == "member":
            final_referents[key] = {"type": semantic_type, **({"answer": True} if not party_list_question else {})}
        elif key == "term":
            final_referents[key] = {"type": semantic_type, "selector": dict(normalized[key]["selector"])}
        elif key == "constituency":
            final_referents[key] = {"type": semantic_type, "mention": normalized[key]["mention"], "resolution": "unresolved"}
        elif key == "affiliation" and party_list_question:
            final_referents[key] = {"type": semantic_type, "answer": True}
        elif key == "affiliation":
            final_referents[key] = {"type": semantic_type, "mention": affiliation_mention, "resolution": "unresolved"}
        else:
            final_referents[key] = {"type": semantic_type}

    final = {
        "family": "member_relationship_composition",
        "referents": final_referents,
        "relations": [dict(item) for item in value["relations"]],
        "constraints": [dict(item) for item in value["constraints"]],
        "answer": answer,
    }
    if term_selector["kind"] == "currentTerm" and not re.search(r"\b(?:current|currently|now|today)\b", question, re.I):
        final["interpretation"] = {"policy": "present_constituency_as_of", "question": question}
    return final


def _bill_number_year_mentions(question: str) -> set[tuple[str, int]]:
    """Extract only explicit Bill number/year pairs; this does not classify intent."""
    patterns = (
        re.compile(
            r"\bbill\s*(?:(?:number|no\.?|#)\s*)?(?:numbered\s*)?"
            r"(?P<number>[0-9]+)\s*(?:/|of|from|in|,)\s*(?P<year>[0-9]{4})\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?P<year>[0-9]{4})\s+bill\s+(?:number|no\.?|#)\s*(?P<number>[0-9]+)\b",
            re.IGNORECASE,
        ),
    )
    pairs: set[tuple[str, int]] = set()
    for pattern in patterns:
        for match in pattern.finditer(question):
            pairs.add((match["number"], int(match["year"])))
    return pairs


def _validate_capability_selection_draft(value: dict[str, Any], *, question: str) -> dict[str, Any]:
    """Select an existing closed handler without translating it into new RDF logic."""
    referents = value["referents"]
    if (not isinstance(referents, dict)
            or set(referents) != {"capability", "parameters"}
            or value["relations"] != [] or value["constraints"] != []
            or value["answer"] is not None):
        raise InvalidComposableDraft(
            "Existing-capability selection requires one capability/input pair and no model-authored query graph or projection."
        )
    capability = referents["capability"]
    parameters = referents["parameters"]
    dispatch = _plan_contract().get("semanticDispatch", {})
    entries = {item.get("id"): item for item in dispatch.get("capabilities", [])
               if isinstance(item, dict)}
    entry = entries.get(capability)
    if not isinstance(entry, dict):
        raise UnsupportedComposableRequest(
            f"Existing semantic capability {capability!r} is not exposed for semantic selection."
        )

    if capability == "member_lookup":
        if (entry.get("handler") != "stage_a" or not isinstance(parameters, dict)
                or set(parameters) != {"member", "house"}
                or parameters.get("house") not in (None, "Dail", "Seanad")
                or not isinstance(parameters.get("member"), str)
                or not parameters["member"].strip()
                or _label_position(question, parameters["member"]) is None):
            raise InvalidComposableDraft("Member lookup requires a grounded name and explicit chamber restriction.")
        house = parameters["house"]
        if bool(re.search(r"\b(?:deputy|deputies|TDs?|D[áa]il)\b", question, re.I)) != (house == "Dail"):
            raise InvalidComposableDraft("Preserve the requested Dáil-service restriction.")
        if bool(re.search(r"\b(?:senators?|Seanad)\b", question, re.I)) != (house == "Seanad"):
            raise InvalidComposableDraft("Preserve the requested Seanad-service restriction.")
        condition_text = re.sub(re.escape(parameters["member"]), " ", question, flags=re.I)
        if re.search(r"\b(?:party|parties|constituenc(?:y|ies)|current|now|elected|election|minister|when|before|after|during|served|count|and|with|except|excluding|only|bills?|sponsor(?:ed|s|ing)?|committees?|votes?|voted)\b|[0-9]", condition_text, re.I):
            raise UnsupportedComposableRequest("Name lookup cannot replace another relationship or temporal question.")
        normalized_parameters = {"member": parameters["member"].strip(), "house": house}
    elif capability == "dail_parties_and_groups":
        if (entry.get("handler") != "stage_c" or not isinstance(parameters, dict)
                or set(parameters) != {"termNumber", "includeGroups"}
                or type(parameters.get("termNumber")) is not int
                or _question_dail_ordinals(question) != [parameters["termNumber"]]
                or type(parameters.get("includeGroups")) is not bool):
            raise InvalidComposableDraft("Party listing requires the exact numbered Dáil and requested group scope.")
        if parameters["includeGroups"] != bool(re.search(r"\bgroups?\b", question, re.I)):
            raise InvalidComposableDraft("Preserve party/group answer scope.")
        if re.search(r"\b(?:represent|constituenc(?:y|ies)|TDs|members|minister|current|now|before|after|count|how many|except|excluding|only|without|bills?|sponsor(?:ed|s|ing)?|votes?|voted|committees?)\b|[0-9]{4}", question, re.I):
            raise UnsupportedComposableRequest("Party listing cannot replace a Member relationship or additional condition.")
        normalized_parameters = dict(parameters)
    elif capability == "office_holding_window":
        if (not isinstance(parameters, dict) or "office" not in parameters
                or not isinstance(parameters.get("office"), str)
                or _label_position(question, parameters["office"]) is None):
            raise InvalidComposableDraft("Office time selection requires a grounded office mention.")
        if re.search(r"\b(?:throughout|the whole of|all of|the entire|for the full)\b", question, re.I):
            raise UnsupportedComposableRequest(
                "The accepted OfficeHolding compiler reports interval overlap, not uninterrupted service throughout a period."
            )
        keys = set(parameters)
        if keys == {"office", "startMonth", "startYear", "endMonth", "endYear"}:
            if (any(type(parameters[key]) is not int for key in ("startMonth", "endMonth", "startYear", "endYear"))
                    or any(not 1 <= parameters[key] <= 12 for key in ("startMonth", "endMonth"))
                    or any(not 1 <= parameters[key] <= 9998 for key in ("startYear", "endYear"))):
                raise InvalidComposableDraft("Office month/year boundaries must be bounded calendar integers.")
            bounds = _question_month_window(question)
            if tuple(parameters[key] for key in ("startYear", "startMonth", "endYear", "endMonth")) != bounds:
                raise InvalidComposableDraft("Preserve the complete requested calendar-month window; never replace it by a date point.")
            normalized_parameters = dict(parameters)
        elif keys == {"office", "date"}:
            from .composable_plan import _question_calendar_dates
            dates, invalid_date = _question_calendar_dates(question)
            try:
                selected_date = date.fromisoformat(parameters["date"])
            except (TypeError, ValueError) as error:
                raise InvalidComposableDraft("Office point selection requires one valid ISO calendar date.") from error
            if (selected_date.isoformat() != parameters["date"]
                    or invalid_date is not None or len(dates) != 1 or dates[0] != selected_date
                    or selected_date.year > 9998):
                raise InvalidComposableDraft("Preserve exactly one explicit calendar-date point for the office lookup.")
            normalized_parameters = {"office": parameters["office"].strip(), "date": selected_date.isoformat()}
        elif keys == {"office", "year"}:
            year_mentions = re.findall(r"(?<![0-9])([0-9]{4})(?![0-9])", question)
            year_match = re.search(r"\b(?:during|in|throughout)\s+(?P<year>[0-9]{4})\b", question, re.I)
            if (type(parameters["year"]) is not int or not 1 <= parameters["year"] <= 9998
                    or year_match is None or len(year_mentions) != 1
                    or int(year_match["year"]) != parameters["year"]):
                raise InvalidComposableDraft("Preserve one explicitly requested complete calendar year for the office lookup.")
            normalized_parameters = {"office": parameters["office"].strip(), "year": parameters["year"]}
        else:
            raise InvalidComposableDraft("Office time selection must be one date point, complete calendar year, or explicit month window.")
        residual = re.sub(re.escape(parameters["office"]), " ", question, flags=re.I)
        if re.search(r"\b(?:and|while|constituenc(?:y|ies)|party|parties|TDs?|members?|elected|election|count|how many|only|except|excluding|before|after|since|until|not)\b", residual, re.I):
            raise UnsupportedComposableRequest("A dated office window cannot drop an additional relationship, projection or condition.")
    elif capability == "office_holding_evidence":
        if (not isinstance(parameters, dict) or set(parameters) != {"member", "office"}
                or any(not isinstance(parameters.get(key), str) or not parameters[key].strip()
                       or _label_position(question, parameters[key]) is None for key in ("member", "office"))):
            raise InvalidComposableDraft("Office evidence lookup requires grounded Member and office mentions.")
        normalized_parameters = dict(parameters)
    elif capability == "seanad_entry":
        if (entry.get("handler") != "stage_a" or entry.get("input") != "member_mention"
                or not isinstance(parameters, dict) or set(parameters) != {"member"}
                or not isinstance(parameters.get("member"), str)
                or not parameters["member"].strip()
                or _label_position(question, parameters["member"]) is None):
            raise InvalidComposableDraft("Seanad-entry selection requires an exact grounded Member mention.")
        if re.search(
            r"\b(?:current|currently|now|Dáil|deputy|panel|constituenc(?:y|ies)|represent(?:s|ed)?|party|how many|count|between|until|elected|election)\b",
            question, re.IGNORECASE,
        ):
            raise UnsupportedComposableRequest(
                "The Seanad-entry capability cannot answer a current-status, representation, party, or additional temporal/count condition."
            )
        normalized_parameters = {"member": parameters["member"].strip()}
    elif capability == "bill_lookup":
        if (entry.get("handler") != "stage_b" or entry.get("input") != "bill_number_and_year"
                or not isinstance(parameters, dict)
                or set(parameters) != {"billNumber", "billYear"}
                or not isinstance(parameters.get("billNumber"), str)
                or not re.fullmatch(r"[0-9]+", parameters["billNumber"])
                or type(parameters.get("billYear")) is not int
                or not 1800 <= parameters["billYear"] <= 2200):
            raise InvalidComposableDraft("Bill lookup selection requires an exact Bill number/year pair.")
        mentioned = _bill_number_year_mentions(question)
        selected = (parameters["billNumber"], parameters["billYear"])
        if len(mentioned) != 1 or selected not in mentioned:
            raise InvalidComposableDraft(
                "The Bill number and year must be one unambiguous pair explicitly present in the question."
            )
        if re.search(
            r"\b(?:sponsor(?:ed|ship|s)?|vot(?:e|ed|ing)|division|constituenc(?:y|ies)|"
            r"represent(?:s|ed|ative)?|party|affiliation|member|senator|minister|officeholder)\b|"
            r"\b(?:as of|by|before|after|since|until|between|during)\b",
            question, re.IGNORECASE,
        ):
            raise UnsupportedComposableRequest(
                "Bill lookup cannot replace a sponsorship, voting, relationship, or additional temporal condition."
            )
        normalized_parameters = {"billNumber": parameters["billNumber"], "billYear": parameters["billYear"]}
    else:
        raise UnsupportedComposableRequest(
            f"Existing semantic capability {capability!r} has no reviewed dispatch adapter."
        )

    return {"family": "capability_selection", "capability": capability,
            "parameters": normalized_parameters}


def _question_month_window(question):
    """Ground only the already supported full-month window, not broad date NLQ."""
    import calendar
    months = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
    matches = re.findall(r"\b(" + "|".join(months) + r")\s+([0-9]{4})\b", question, re.I)
    if not 1 <= len(matches) <= 2:
        raise InvalidComposableDraft("Supply one calendar month or two explicit month/year boundaries.")
    bounds = [(int(year), months[month.casefold()]) for month, year in matches]
    if len(bounds) == 1:
        bounds *= 2
    if bounds[0] > bounds[1]:
        raise InvalidComposableDraft("The month window is reversed.")
    return (*bounds[0], *bounds[1])


def _validate_bounded_composition_draft(value, *, question):
    """Normalize operator inputs; the shared final validator owns graph meaning."""
    from .composable_plan import validate_plan, PlanError
    from .interpretation import present_constituency_default
    from .structured_planner import _label_position
    refs = value["referents"]
    anchored = "anchor" in refs
    normalized = {}
    mentions = []
    for key, ref in refs.items():
        if not isinstance(ref, dict):
            raise InvalidComposableDraft("Every referent must be a typed object.")
        if key == "constituency" and "members" in ref:
            if set(ref) != {"type", "members"} or not isinstance(ref["members"], list):
                raise InvalidComposableDraft("An identity set contains only typed, explicitly named alternatives.")
            items = ref["members"]
        else:
            items = [ref]
        converted = []
        for item in items:
            if not isinstance(item, dict) or set(item) - {"type", "mention", "selector"}:
                raise InvalidComposableDraft("The model may propose mentions/selectors, never identity resolution or arbitrary fields.")
            semantic_type = item.get("type")
            result = {"type": semantic_type}
            mention = item.get("mention")
            if mention is not None:
                if (not isinstance(mention, str) or not mention.strip() or _label_position(question, mention) is None
                        or re.search(r"\b(?:and|or|while|when|during|elected|election|first|before|after|except|excluding)\b", mention, re.I)):
                    raise InvalidComposableDraft("A referent must be an exact entity mention, not a consumed additional clause.")
                mentions.append(mention)
                result.update(mention=mention, resolution="unresolved")
            if "selector" in item:
                selector = item["selector"]
                if not isinstance(selector, dict):
                    raise InvalidComposableDraft("Invalid term selector.")
                if selector == {"kind": "currentTerm"}:
                    selector = {"kind": "currentTerm", "house": "Dail"}
                result["selector"] = selector
            converted.append(result)
        normalized[key] = {"type": ref["type"], "members": converted} if "members" in ref else converted[0]
    normalized["member"]["answer"] = True
    plan = {"version": 2, "asOf": "2000-01-01", "family": value["family"],
            "referents": normalized, "relations": value["relations"], "constraints": value["constraints"], "answer": value["answer"]}
    residual = question
    for mention in mentions:
        residual = re.sub(re.escape(mention), " ", residual, flags=re.I)
    if re.search(r"\b(?:not|never|except|excluding|only|before|after|since|until|between|count|how many|votes?|voted|bills?|committees?|elected|election|first|last)\b|[0-9]{4}", residual, re.I):
        raise UnsupportedComposableRequest("The bounded operators cannot preserve this additional constraint/projection; no partial answer is permitted.")
    # A bounded grammar is deliberately conservative. Unconsumed names/clauses
    # must not disappear merely because every proposed name occurs somewhere.
    scope_text = re.sub(r"\b[0-9]{1,3}(?:st|nd|rd|th)\b", " ", residual, flags=re.I)
    allowed = set("who what which were was are is did do does have has had the a an other another others td tds deputy deputies member members in for of from as same shared constituency constituencies with while when during he she they his her their s and or both either any represent represents represented representing representation serve served service held hold office term dáil dail current currently now today latest recorded most recent please list name show give me records local evidence evidenced identify find tell can could you that those these whom fellow alongside parliamentary".split())
    if set(re.findall(r"[^\W\d_]+", scope_text.casefold())) - allowed:
        raise UnsupportedComposableRequest("Unconsumed wording remains outside the bounded composition; no clause or identity was silently dropped.")
    if anchored:
        if not re.search(r"\b(?:same|shared)\s+constituency\b", residual, re.I) or not re.search(r"\b(?:while|when|during)\b", residual, re.I):
            raise InvalidComposableDraft("The shared-constituency and office temporal anchor must both be requested.")
        if _question_dail_ordinals(question) or re.search(r"\b(?:current|now|today)\b", residual, re.I):
            raise UnsupportedComposableRequest("Additional term/current scope cannot replace the office anchor.")
    else:
        scope = normalized["constituency"]
        selector = normalized["term"].get("selector")
        if selector == {"kind": "currentTerm", "house": "Dail"}:
            if not re.search(r"\b(?:current|currently|now|today)\b", question, re.I):
                if not all(present_constituency_default(question, item["mention"]) for item in scope["members"]):
                    raise InvalidComposableDraft("The OR set requires the same approved present-tense temporal default for every item.")
                plan["interpretation"] = {"policy": "present_constituency_as_of", "question": question, "date": plan["asOf"]}
            if _question_dail_ordinals(question):
                raise InvalidComposableDraft("Current selection cannot replace a numbered term.")
        elif not isinstance(selector, dict) or _question_dail_ordinals(question) != [selector.get("number")]:
            raise InvalidComposableDraft("Preserve the exact explicitly numbered term.")
        if not re.search(r"\b(?:and|or)\b", residual, re.I):
            raise InvalidComposableDraft("An identity OR set must be explicitly requested, not inferred from a geographic substring.")
    try:
        validate_plan(plan)
    except (PlanError, KeyError, TypeError) as error:
        raise InvalidComposableDraft(str(error)) from error
    return {key: item for key, item in plan.items() if key not in {"version", "asOf"}}


def _question_dail_ordinals(question: str) -> list[int]:
    values: list[int] = []
    for match in _DAIL_ORDINAL.finditer(question):
        number = int(match.group("number"))
        if match.group("suffix").casefold() != _ordinal_suffix(number):
            raise InvalidComposableDraft("A Dáil term ordinal in the question is malformed.")
        values.append(number)
    return values


def _validate_member_relationship_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate only the two closed relationship projections using v2 edges."""
    if re.search(r"\b(?:senators?|seanad|panels?)\b", question, re.I):
        raise UnsupportedComposableRequest("The Dáil relationship compiler cannot substitute for a Seanad relationship.")
    referents = value["referents"]
    if isinstance(referents, dict) and any(
        isinstance(item, dict) and item.get("type") == "PartyMembershipEpisode"
        for item in referents.values()
    ):
        return _validate_member_party_composition_draft(value, question=question)
    if not isinstance(value["constraints"], list) or len(value["constraints"]) > 1:
        raise InvalidComposableDraft("The non-party Member composition accepts at most one reviewed calendar-date constraint.")
    if re.search(r"\b(?:party|political affiliation|Sinn Féin|Fianna Fáil|Fine Gael|Labour|Green Party)\b", question, re.IGNORECASE):
        raise UnsupportedComposableRequest(
            "The question includes a party-affiliation condition that is absent from the proposed relationship graph."
        )
    if not isinstance(referents, dict) or not 4 <= len(referents) <= 5:
        raise InvalidComposableDraft(
            "Member relationship composition requires one Member and a complete supported membership graph."
        )

    typed: dict[str, str] = {}
    term_numbers: dict[str, int] = {}
    current_terms: set[str] = set()
    constituency_mentions: dict[str, str] = {}
    for referent_id, item in referents.items():
        _identifier(referent_id, "referent ID")
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise InvalidComposableDraft("Every composition referent requires a controlled type.")
        semantic_type = item["type"]
        if semantic_type == "Member":
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft(
                    "The Member referent is the set-valued answer and cannot bind a named person."
                )
        elif semantic_type == "DailMembership":
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft("DailMembership referents are relationship evidence, not named entities.")
        elif semantic_type == "DailTerm":
            selector = item.get("selector")
            if (set(item) != {"type", "mention", "selector"}
                    or item["mention"] is not None
                    or not isinstance(selector, dict)):
                raise InvalidComposableDraft(
                    "Each DailTerm requires one exact numeric or date-relative current-term selector."
                )
            if (set(selector) == {"kind", "number"}
                    and selector.get("kind") == "termNumber"
                    and type(selector.get("number")) is int
                    and 1 <= selector["number"] <= 999):
                term_numbers[referent_id] = selector["number"]
            elif selector == {"kind": "currentTerm"}:
                if not re.search(r"\b(?:current|currently|now|today|this\s+d[áa]il)\b", question, re.I):
                    raise InvalidComposableDraft(
                        "A currentTerm selector requires an explicit current-date or 'this Dáil' reference."
                    )
                current_terms.add(referent_id)
            else:
                raise InvalidComposableDraft(
                    "Each DailTerm requires an explicitly selected numeric ordinal or currentTerm."
                )
        elif semantic_type == "DailConstituency":
            mention = item.get("mention")
            if (set(item) != {"type", "mention"}
                    or not isinstance(mention, str) or not mention.strip()
                    or _label_position(question, mention) is None):
                raise InvalidComposableDraft(
                    "The DailConstituency must use an exact user-supplied name mention."
                )
            constituency_mentions[referent_id] = mention.strip()
        else:
            raise UnsupportedComposableRequest(
                f"Referent type {semantic_type!r} is outside the reviewed Member relationship composition."
            )
        typed[referent_id] = semantic_type

    members = [key for key, value_type in typed.items() if value_type == "Member"]
    memberships = [key for key, value_type in typed.items() if value_type == "DailMembership"]
    terms = [key for key, value_type in typed.items() if value_type == "DailTerm"]
    constituencies = [key for key, value_type in typed.items() if value_type == "DailConstituency"]
    if len(members) != 1:
        raise InvalidComposableDraft("The supported composition has exactly one set-valued Member answer.")
    mentioned_ordinals = _question_dail_ordinals(question)
    if (len(term_numbers) != len(mentioned_ordinals)
            or sorted(term_numbers.values()) != sorted(mentioned_ordinals)
            or len(set(term_numbers.values())) != len(term_numbers)):
        raise InvalidComposableDraft(
            "The plan must preserve every distinct numeric Dáil term explicitly requested in the question."
        )
    if current_terms and (len(current_terms) != 1 or term_numbers or mentioned_ordinals):
        raise InvalidComposableDraft(
            "A House-date-resolved currentTerm cannot replace or combine with an explicitly numbered Dáil."
        )
    from .composable_plan import _question_calendar_dates
    count_intent = bool(re.search(r"\b(?:how many|count|number of|total of)\b", question, re.I))
    selected_membership = next(iter(memberships), None)
    dates, invalid_date = _question_calendar_dates(question)
    if invalid_date is not None:
        raise InvalidComposableDraft(f"{invalid_date} is not a valid calendar date; no Member selection was run.")
    if len(dates) > 1:
        raise UnsupportedComposableRequest("The Member representation slice supports at most one explicit date point.")
    if value["constraints"]:
        constraint = value["constraints"][0]
        if (not isinstance(constraint, dict)
                or set(constraint) != {"referent", "field", "operator", "value"}
                or constraint.get("referent") != selected_membership
                or constraint.get("field") != "membershipInterval"
                or constraint.get("operator") != "on"
                or not isinstance(constraint.get("value"), str)):
            raise UnsupportedComposableRequest("Only one exact DailMembership calendar-date point is supported for this Member selection.")
        try:
            selected_date = date.fromisoformat(constraint["value"])
        except ValueError as error:
            raise InvalidComposableDraft("The membership calendar-date constraint must be a valid ISO date.") from error
        if len(dates) != 1 or selected_date != dates[0]:
            raise InvalidComposableDraft("The Member date selector must preserve the exact date stated in the question.")
    elif dates:
        raise InvalidComposableDraft("The explicit Member service date cannot be dropped from the plan.")
    elif re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+[0-9]{4}\b", question, re.I):
        raise UnsupportedComposableRequest("Member representation supports a calendar-date point, not an arbitrary month filter.")

    relation_defs = {item["id"]: item for item in _plan_contract()["relations"]}
    relation_types = {
        fact: (definition["subjectType"], definition["objectType"])
        for fact, definition in relation_defs.items()
    }
    if not isinstance(value["relations"], list):
        raise InvalidComposableDraft("Relations must be an array.")
    actual_edges: list[tuple[str, str, str]] = []
    relation_ids: set[str] = set()
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Relation IDs must be unique.")
        relation_ids.add(relation_id)
        fact = relation["fact"]
        if not isinstance(fact, str) or fact not in {
            "member_has_membership", "membership_in_term",
            "membership_represents", "constituency_in_term",
        }:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the reviewed Member relationship composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if source not in typed or target not in typed:
            raise InvalidComposableDraft("Every relationship endpoint must name a declared referent.")
        if (typed[source], typed[target]) != relation_types[fact]:
            raise InvalidComposableDraft(f"Relationship {fact!r} has incompatible typed referents.")
        actual_edges.append((fact, source, target))

    member_id = members[0]
    expected_edges: list[tuple[str, str, str]] = []
    if len(terms) == 2 and len(memberships) == 2 and not constituencies and not current_terms:
        expected_edges.extend(
            ("member_has_membership", member_id, membership_id)
            for membership_id in memberships
        )
        membership_to_term: dict[str, str] = {}
        for fact, source, target in actual_edges:
            if fact == "membership_in_term":
                if source in membership_to_term:
                    raise InvalidComposableDraft("Each DailMembership must identify exactly one requested term.")
                membership_to_term[source] = target
        if set(membership_to_term) != set(memberships) or set(membership_to_term.values()) != set(terms):
            raise InvalidComposableDraft(
                "Each independent membership must link to a different explicitly requested DailTerm."
            )
        expected_edges.extend(
            ("membership_in_term", membership_id, membership_to_term[membership_id])
            for membership_id in memberships
        )
    elif len(terms) == 1 and len(memberships) == 1 and len(constituencies) == 1:
        membership_id, term_id, constituency_id = memberships[0], terms[0], constituencies[0]
        expected_edges = [
            ("member_has_membership", member_id, membership_id),
            ("membership_in_term", membership_id, term_id),
            ("membership_represents", membership_id, constituency_id),
            ("constituency_in_term", constituency_id, term_id),
        ]
    else:
        raise InvalidComposableDraft(
            "The plan must be either one Member in two numbered Dáil terms or one term-scoped constituency representation path."
        )
    if sorted(actual_edges) != sorted(expected_edges):
        raise InvalidComposableDraft(
            "The relationship graph is disconnected, incomplete, or contains an extra semantic edge."
        )

    if (count_intent or value["constraints"]) and not (
        len(terms) == 1 and len(memberships) == 1 and len(constituencies) == 1
    ):
        raise UnsupportedComposableRequest(
            "Count and calendar-date projections are limited to one term-scoped constituency Member selection."
        )

    expected_answer = ({
        "kind": "count", "referent": member_id, "distinctBy": "identity",
    } if count_intent else {
        "kind": "entities", "referent": member_id,
        "distinctBy": "identity", "display": ["name"],
        "details": [], "preserveEvidence": False,
    })
    if value["answer"] != expected_answer:
        raise InvalidComposableDraft(
            "The answer must preserve the requested distinct Member count or matching identity list."
        )

    final_referents: dict[str, dict[str, Any]] = {}
    for referent_id, semantic_type in typed.items():
        if semantic_type == "Member":
            final_referents[referent_id] = {"type": semantic_type, "answer": True}
        elif semantic_type == "DailMembership":
            final_referents[referent_id] = {"type": semantic_type}
        elif semantic_type == "DailTerm":
            selector = ({"kind": "currentTerm", "house": "Dail"} if referent_id in current_terms else
                        {"kind": "termNumber", "number": term_numbers[referent_id]})
            final_referents[referent_id] = {"type": semantic_type, "selector": selector}
        else:
            final_referents[referent_id] = {
                "type": semantic_type,
                "mention": constituency_mentions[referent_id],
                "resolution": "unresolved",
            }
    final = {
        "family": "member_relationship_composition",
        "referents": final_referents,
        "relations": [dict(item) for item in value["relations"]],
        "constraints": [dict(item) for item in value["constraints"]],
        "answer": expected_answer,
    }
    from .interpretation import member_relationship_as_of_default
    if (current_terms and len(constituencies) == 1
            and member_relationship_as_of_default(question, next(iter(constituency_mentions.values())))):
        final["interpretation"] = {"policy": "present_constituency_as_of", "question": question}
    return final


def complete_v2_plan(draft_plan: dict[str, Any], *, as_of: date) -> dict[str, Any]:
    """Add only deterministic composable-v2 envelope metadata to a draft."""
    plan = {"version": 2, "asOf": as_of.isoformat(), **draft_plan}
    if "interpretation" in plan:
        plan["interpretation"] = {**plan["interpretation"], "date": as_of.isoformat()}
    if plan.get("family") == "government_party_members":
        from .government import government_plan
        plan["constraints"] = government_plan(plan["referents"]["affiliation"]["mention"], as_of=as_of)["constraints"]
    if (plan.get("family") == "member_relationship_composition"
            and "interpretation" in plan
            and not any(ref.get("type") == "PartyMembershipEpisode"
                        for ref in plan.get("referents", {}).values())
            and plan.get("referents", {}).get("term", {}).get("selector")
            == {"kind": "currentTerm", "house": "Dail"}):
        memberships = [key for key, ref in plan["referents"].items()
                       if ref.get("type") == "DailMembership"]
        if len(memberships) == 1 and not plan.get("constraints"):
            plan["constraints"] = [{
                "referent": memberships[0], "field": "membershipInterval",
                "operator": "on", "value": as_of.isoformat(),
            }]
    return plan


def parse_composable_plan_output(output: str) -> Any:
    """Use the shared strict JSON parser for duplicate-key/NaN rejection."""
    try:
        return parse_draft_json(output)
    except ValueError as error:
        raise InvalidComposableOutput(str(error)) from error
