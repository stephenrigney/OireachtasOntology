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
_HISTORICAL_CURRENT_CONTRAST = re.compile(
    r"\b(?:past|formerly|former)\b|\bused\s+to\b|\bno\s+longer\b",
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
    # The inventory also describes separately routed semantic families. Only
    # schema-admissible generic selectors belong in capability_selection guidance.
    selection_shape = next(
        shape for shape in load_composable_draft_schema()["properties"]["referents"]["anyOf"]
        if "capability" in shape.get("properties", {})
    )
    selection_ids = set(selection_shape["properties"]["capability"]["enum"])
    dispatch_guidance = "\n".join(
        f'- Existing capability "{item["id"]}" ({item["handler"]}; input {item["input"]}): {item["semantics"]}'
        for item in dispatch_capabilities
        if item["id"] in selection_ids
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

PRIORITY for present/current two-relationship Member questions: use family
"current_member_composition" for any TWO DISTINCT selections among R (Dáil
constituency representation), P (named party membership), K (named committee
membership). This is the reusable typed composition kernel, not a sentence
recognizer. Interpret paraphrases, reversed clauses and implicit party adjectives
semantically. referents is exactly {{"selections":[{{"role":"R|P|K","mention":"exact full name text from question"}},{{"role":"R|P|K","mention":"exact full name text from question"}}],"shape":"list|count|boolean","temporal":"current"}}.
relations=[], constraints=[], answer=null. Mentions must be verbatim; preserve
short committee mentions such as Public Accounts or PAC, never expand them or
invent IRIs. Code resolves grounded names and reports ambiguity. R+P supports
Member lists and distinct-Member counts; K-containing pairs support lists only.
Boolean questions (e.g. Are there...?) must retain shape=boolean, which code will
explain as unsupported; NEVER substitute a list. Ordinary present tense defaults
to backend asOf; code checks all independent intervals and exact identities.
All requested conditions and answer fields remain obligatory. If a third role,
negation, historic/explicit date, office, election or another condition is requested,
do NOT omit it to propose this current-only family. Use an existing supported
historical/anchored family below if it preserves the whole question; otherwise
return unsupported for the entire request. Single relationships and existing
capabilities still use their existing families below. This priority supersedes
the older current named-party/constituency Member-list guidance only for this
two-role current selection; it does not replace historical or anchored queries.

Approved present-time policy: ordinary unqualified present-tense requests for an existing current-time parliamentary relationship mean current at configured asOf. This applies to both Dáil and Seanad named-party membership, current Dáil representation, current named-committee membership, current named-office holders, officeholder-to-constituency and constitutional Government/party membership. Use the existing current selector/operation without inventing a date; local code supplies asOf and validates each relationship's own temporal evidence. Explicit dates, numbered terms, past/future expressions, negation and additional requirements cannot be replaced by a default. latestRecorded is NOT current. This does not add standalone House rosters, generic current Senator representation, current cross-House simultaneous service, chairs or other unsupported operations. Family-specific completeness guards remain mandatory.

Interpretation contract: for the one-term, one-constituency Member list/count, the explicit phrase "in this Dáil" selects the exact House-date-resolved current term and is term-wide, regardless of whether the question says "represent" or "represented". It overrides only the implicit present-tense-as-of default: do not require an asOf membership interval unless the user explicitly asks for current representation (for example, "currently", "now", "today", or "as of now/today"). A literal calendar date remains its exact membership-date point. Without the explicit "this Dáil" scope, an unqualified present-tense constituency request defaults to representation at the query date; an explicit current-point request also requires the DailMembership interval to contain asOf. Dated party/representation composition retains its separate rule that currentTerm requires both party and DailMembership intervals to contain asOf. Never default numbered-term, other dated, historical, or election questions. The plain term-scoped constituency Member projection supports one explicit membership calendar-date point; preserve it as a membershipInterval constraint, never as a HouseTerm date or election event. For a Member's latest recorded Dáil term and constituency, use the constituency_representation family with selector "latestRecorded" when the question explicitly asks for the latest recorded term, the most recent term, or the last term (including "last term in the Dáil"). Local code selects from that Member's accepted DailMembership identities and House-owned chronology, and fails closed on missing/tied/conflicting dates or representation evidence. This is not an election-date answer.
For partial-name person lookup use capability_selection member_lookup with parameters {{"member":"exact name mention","house":"Dail"}} for Deputy/TD, "Seanad" for Senator, or null for unqualified Member. Local code offers grounded alternatives; never expand a surname to an assumed full name.
For a numbered-Dáil party listing use capability_selection dail_parties_and_groups with parameters {{"termNumber":N,"includeGroups":false}}; true only if groups are also requested. This reuses the existing party compiler, not the constituency composition.

For a present/current list of the members of one named committee, use capability_selection current_committee_members with parameters exactly {{"committee":"the exact committee name mention"}}. This includes "Who are the members of the Committee on Public Accounts?" and "Which members serve on the Committee of Public Accounts?". Do not supply a term, date, person, chair or inferred committee identity. Local code selects one current Committee incarnation using accepted owner and HouseTerm date evidence at configured asOf, then tests each exact CommitteeMembership interval independently. Preserve the whole user-mentioned committee name; only the initial generic Committee on/of connector may vary in source-label matching. Results are distinct local Member identities with separate dated membership evidence, not a certified complete current roster, attendance or chairmanship. Historical scope, counts, party filters, additional conditions or answer fields remain unsupported as a whole.

For the current constituency of a named officeholder, e.g. "What constituency does the Tánaiste represent?", use capability_selection current_office_constituency with parameters exactly {{"office":"the exact office name mention"}}. An office title is a NamedOffice, NEVER a Member name. Do not name an assumed holder or invent a date. Code resolves one reviewed office and requires one accepted current OfficeHolding at configured asOf, then uses its exact Member identity for the independently dated current Dáil representation capability. Preserve both relationships and all identity/date evidence. Do not assume the holder is a TD or substitute former officeholders/historical constituencies. Missing, conflicting or ambiguous accepted evidence fails closed; neither local office nor government roster completeness is certified. Historical dates, extra conditions, counts and additional answer fields are unsupported as a whole.
For an unfiltered question asking when/for what dates or periods one named person held one named office, also accepting "When did [member] serve as [office]?" and "During what period was [member] [office]?", use capability_selection office_holding_evidence with parameters {{"member":"exact mention","office":"exact office mention"}}. This returns each separately recorded accepted local OfficeHolding episode for the exact identities with its validated interval, explicitly labeled incomplete local-recorded evidence—not a complete career timeline. Do not merge episodes or infer first start, final end, total duration, election events, or absence from gaps; unreviewed observations cannot answer. Election, first-event, duration, and extra-filter requests remain unsupported.

For the same named-person/office period request qualified by "last" or "most recently" (including "When was [member] last [office]?" and "When did [member] last serve as [office]?"), reuse office_holding_evidence with parameters {{"member":"exact mention","office":"exact office mention","selection":"latestRecorded"}}. Do not reject this as an election-event request or claim complete career history. Local code reads every accepted episode and may return only a uniquely latest recorded episode by validated StartDate, with an explicit NOT proven historically last tenure qualification. Tied latest starts, earlier open/overlapping intervals, future starts or any uncertain interval fail closed; no IRI tie-break determines chronology. A missing end remains open-ended, not a completed tenure. Do not omit selection for last/most-recently wording or add it to an all-episodes request. Extra dates, parties, election events and relationships remain unsupported as a whole.

For who held a named office on a calendar date, during a complete month/year, or over an explicit month-to-month window, use capability_selection office_holding_window with exactly one of {{"office":"exact mention","date":"1994-06-01"}}, {{"office":"exact mention","year":1994}}, or {{"office":"exact mention","startMonth":6,"startYear":1994,"endMonth":6,"endYear":1994}}. Preserve date-point vs full-window semantics. Local code reuses the accepted dated OfficeHolding compiler and incomplete-coverage qualification; an overlap does not mean service throughout the window.

For a date-less present/current question asking who is a named office-holder (for example, "Who is the Taoiseach?" or "Who is the current Taoiseach?"), use capability_selection office_holding_window with parameters exactly {{"office":"exact office mention from the question"}}. Do not put a date or period in the proposal: local code injects the configured asOf as an inclusive one-day point and reuses the accepted OfficeHolding interval evaluator. Resolve any generic office only through its existing reviewed NamedOffice identity; do not hardcode an office or infer a holder from its alias. Return only locally evidenced accepted holdings, preserve their exact start/end dates, and state that current-office coverage is not certified. Missing, conflicting, uncertain or absent holding evidence fails closed; an empty result is not evidence that the office has no holder. A date-less past-tense question is not current and must not be defaulted to asOf. This point lookup is not a complete current roster or office-tenure duration/election query.

Bounded operators extend the SAME member_relationship_composition graph below, not new families. Dispatch priority: when the question asks for other/another named-party TDs or Deputies sharing the same constituency as a named Member while/when/during that Member held a named office, use the independent anchor/answer shared-constituency operator below, not the ordinary single-member party/representation shape. Keep separate membership paths for the anchor and answer Member and join them to the same exact constituency and term identities. Preserve all nine edges in the base party/representation graph below, including constituency_in_term, then append the five anchor/office edges in the anchor operator for fourteen relations total; do not drop or replace any base edge. The named office episode anchors the common time intersection; do not invent or require a numbered-term selector.
- For one explicitly numbered or House-date-resolved current Dáil and one named constituency, a distinct-Member count uses the exact same referents, relationships and optional membership-date point as the entity-list projection. Use answer {{"kind":"count","referent":"member","distinctBy":"identity"}} only when asked for a count; count recorded Member RDF identities, not seats or election events. In this non-party projection, unqualified "in this Dáil" means term-wide membership regardless of "represent"/"represented"; it overrides the implicit present-tense asOf default. Explicit "currently"/"now"/"today" or "as of now/today" requests additionally require the DailMembership interval to contain asOf. A literal date remains its exact date constraint. Never count a partial/truncated page or drop a date/constituency/term condition to return a number.
- For any one-term, one-constituency non-party Member list or count—including "this Dáil"—prefer family "member_relationship_composition" with referents member, membership, term, constituency and the four exact representation edges, rather than family "constituency_representation". The list answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}; only an explicit count uses {{"kind":"count","referent":"member","distinctBy":"identity"}}. This keeps the list and count on the same bounded selection. Select the exact House-date current Dáil for "this Dáil"; add the asOf membership interval only for an explicit current-point request or the ordinary unqualified present-tense default without "this Dáil". Do not use this exception for numbered, explicitly dated, election, or party-filtered requests.
- For an explicitly named OR set of two to four constituencies, replace constituency with {{"type":"DailConstituency","members":[{{"type":"DailConstituency","mention":"exact first mention"}},{{"type":"DailConstituency","mention":"exact second mention"}}]}}. All existing edges and the party/membership overlap constraint and Member evidence answer remain unchanged. Local code resolves each occurrence in the same selected term and compiles one VALUES identity set; never merge string results. Never infer a set from 'the two Galway constituencies'; that is ambiguous (Roscommon-Galway may also be relevant).
- For other named-party TDs sharing a constituency with a named anchor Member while that anchor held a named office, keep member, membership, episode, party, affiliation and their edges as below; term is {{"type":"DailTerm","mention":null}} and constituency is {{"type":"DailConstituency","mention":null}} (unselected shared resource identities). Add anchor (Member, exact named mention), anchor_membership (DailMembership, null mention), holding (OfficeHolding, null mention), office (NamedOffice, exact office mention). Add edges member_has_membership anchor→anchor_membership, membership_in_term anchor_membership→term, membership_represents anchor_membership→constituency, member_has_office_holding anchor→holding, office_holding_of_office holding→office. Keep both independent membership paths to the SAME exact constituency and term. No numbered-term clarification is needed: the accepted office episode anchors time. Constraints are exactly [{{"referent":"episode","field":"partyEpisodeInterval","operator":"overlaps","value":"membership"}},{{"referent":"member","field":"identity","operator":"distinctFrom","value":"anchor"}},{{"referent":"holding","field":"interval","operator":"commonIntersection","value":["holding","anchor_membership","membership","episode"]}}]. The answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}},{{"referent":"holding","display":["start","end"]}},{{"referent":"anchor_membership","display":["start","end"]}},{{"referent":"constituency","display":["label"]}}],"preserveEvidence":true}}. Local code requires one common inclusive intersection of ALL four independently owned intervals, not merely pairwise overlaps, and reports partial accepted-evidence coverage, never a complete roster. Additional filters or projections remain unsupported as a whole.

For another/other TDs sharing a named Member's constituency in one exact Dáil, use the bounded shared-constituency form of "member_relationship_composition": referents member (answer Member), membership, term, constituency, anchorMember (exact name), and anchorMembership. The anchor and answer have independent DailMembership paths to the exact same DailTerm and DailConstituency identities, and that constituency occurrence links to the selected term. Use a termNumber selector only for the exact numbered Dáil, or previousTerm for a globally previous/last Dáil relative to asOf; never substitute the anchor's latestRecorded term or a fixed ordinal. Set constraints to [] and use the exact entity-list answer, or the distinct Member-IRI count only for an explicit count. Local execution resolves the anchor uniquely, validates one accepted constituency identity in the selected term, excludes the anchor by Member IRI, and paginates the complete shared selection before count/list output. Meaning is term-wide recorded co-membership, not simultaneous service. Do not drop party, office, election, explicit-date, simultaneity or any other requested condition; those requests remain unsupported.

Existing shared-term capability: {shared_terms['semantics']}

Reusable Member relationship capability: {member_composition['semantics']}

For the exact question shape asking who was a Senator in the current Seanad and a Deputy in the current Dáil, use family "member_relationship_composition" with referents member, seanad_membership, seanad_term, dail_membership, and dail_term. Use independent Member→SeanadMembership→SeanadTerm and Member→DailMembership→DailTerm paths, with facts member_has_seanad_membership, seanad_membership_in_term, member_has_membership, and membership_in_term. Both term selectors are {{"kind":"currentTerm"}}; local code resolves each exact term independently from House-owned date evidence. Set constraints to [] and answer exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}. This means term-wide recorded membership in both terms. Do not require intervals to overlap, do not describe a Member as currently serving in either House, and do not claim simultaneous service; the executor displays each House's separate mapped membership intervals. If the user asks for simultaneous/concurrent/current-point service, a historical period, a date, a party, or any additional filter, return unsupported for the whole request rather than dropping it.

The Seanad party-only shape below also supports one explicitly numbered Seanad with term selector {{"kind":"termNumber","number":N}}. Keep the SAME seven typed edges and partySeanadEpisodeInterval overlap constraint; local code resolves the exact SeanadTerm and validates inclusive party/membership interval overlap, without imposing today's party or membership. Preserve all matching separate episodes, including changes of party during the term. An unqualified present-tense named-party Senator request ("Who are the [party] Senators?", "Which [party] Senators are there?", or "How many [party] Senators are there?") instead uses currentTerm: local code records the scoped asOf default and enforces both active intervals. Never default a past-tense, explicitly numbered, dated or additionally filtered request. A numbered Seanad and current Seanad are distinct temporal meanings; unsupported extra dates/relationships must not be dropped.

For a request for current Senators who previously served in the Dáil (Q20), use the same five typed roles and four exact Member→membership→HouseTerm edges, but select only seanad_term with selector {{"kind":"currentTerm"}}; dail_term is an unselected DailTerm because the Dáil is selected by its exact membership path, not by a guessed prior ordinal. An ordinary unqualified present-tense Senator head in this same bounded request also defaults to current: the separate explicitly prior Dáil clause remains historical and must NEVER be replaced by current Dáil service. Require the current SeanadMembership's own accepted interval to contain the configured asOf inclusively, and return a Member only when a finite accepted DailMembership EndDate is strictly earlier than that same SeanadMembership StartDate. Equal endpoints do not qualify; an open-ended DailMembership is not prior-service evidence. Use the evidence-preserving Member list answer with details for both membership intervals and both HouseTerm identities, or the distinct Member count only when explicitly requested. Count/list share the same complete bounded pagination and exact Member-identity join. Unknown, missing, conflicting, malformed or capped identity/date evidence fails closed. This is a positive local-record result only: do not claim complete career/history coverage or infer that anyone never served from an absent path. Refuse party, panel, office, election, simultaneity, dated/ordinal or other additional conditions as a whole.

For a named-party Member count/list in the explicitly current Seanad, use the party-only shape with member, membership (SeanadMembership), term (SeanadTerm selector {{"kind":"currentTerm"}}), episode, party, and affiliation. Use member_has_seanad_membership, seanad_membership_in_term, member_party_membership, party_episode_in_seanad_membership, episode_in_parliamentary_party, party_active_during_seanad_term, and parliamentary_party_has_affiliation_identity. Preserve the exact party mention as the PoliticalAffiliationIdentity filter and require constraints exactly [{{"referent":"episode","field":"partySeanadEpisodeInterval","operator":"overlaps","value":"membership"}}]. Local code resolves the unique current SeanadTerm by Houses-owned dates and requires both each SeanadMembership interval and its PartyMembership interval independently to contain asOf; the overlap does not replace either active-point test. A count answer is {{"kind":"count","referent":"member","distinctBy":"identity"}}; a list uses the same Member selection and preserves separate identity/episode/membership evidence. Exact identities, typed PartyMembership records, and complete pagination are mandatory; missing/conflicting dates or identity evidence fail closed. State that results reflect local records and do not certify a complete current Seanad roster. Do not use current Seanad membership alone as a substitute for active party evidence or answer a generic unfiltered Senator count.

Existing validated capabilities available through capability_selection:
{dispatch_guidance}

When one of those existing capabilities directly answers the request, use family "capability_selection", put its exact ID in referents.capability, and provide only the matching semantic inputs in referents.parameters. For seanad_entry use {{"member":"the exact grounded Member name"}}. For bill_lookup use {{"billNumber":"the explicitly supplied Bill number","billYear":2025}}. Set relations to [], constraints to [], and answer to null. Local code checks the inputs against the question, then invokes the same validated Stage A/B/C plan builder and executor used by deterministic recognition, or the named evidence-boundary resolver. Never use this route to answer another relationship or drop a requested condition.

Use the existing semantic relationship identifiers below; these are proposals, not authority decisions:
{relation_guidance}

For the existing shared-term capability, use family "shared_dail_terms" and fixed referent keys member_a, membership_a, member_b, membership_b, and shared_term. Member entries use exact user-supplied labels. Each Member has an independent DailMembership path to the same shared DailTerm identity; set "constraints": [] and set "answer" to exactly {{"kind":"entities","referent":"shared_term","distinctBy":"identity","display":["label"],"details":[],"preserveEvidence":false}}.

For the reusable Member relationship capability, use family "member_relationship_composition" and one Member answer referent with a null mention for ordinary projections. Every ordinary DailTerm referent must carry selector {{"kind":"termNumber","number":N}} for an explicitly requested numeric Dáil ordinal. The separately described anchored shared-constituency operator may use previousTerm for the globally previous Dáil. For a one-term, one-constituency non-party Member selection, use selector {{"kind":"currentTerm"}} for an explicit current/now request, the approved unqualified present-tense default, or "this Dáil"; local code selects one exact House-dated term. In this exact shape, unqualified "in this Dáil" is term-wide regardless of represent/represented and overrides the implicit present-tense asOf condition. Explicit currently/now/today/as-of-current requests still preserve the appropriate membership interval; explicit calendar dates remain exact date points. This does not change numbered or election questions. In this family, selector is always an object: never use the string "currentTerm" or "latestRecorded". Use selector {{"kind":"currentTerm"}} in the dated party/representation shape only for explicit current/now or the approved unqualified present-tense default; there, both episode and representation intervals must contain asOf. Use one of these complete typed graph shapes only:
- keys member, membership_a, term_a, membership_b, and term_b: two distinct selected DailTerms, each reached from the same answer Member through a separate DailMembership; this returns Members with recorded membership in both exact term identities;
- keys member, membership, term, and constituency: one selected DailTerm and one exact user-mentioned DailConstituency, where the same DailMembership links the Member to that term and constituency, and the constituency occurrence links to that same term identity.
- keys member, membership, term, constituency, anchorMember, and anchorMembership: one exact named anchor plus a separate answer Member path, with both DailMemberships linked to the same selected DailTerm and exact DailConstituency identity, and that constituency occurrence linked to the same term. The term is a numbered term or previousTerm only. This term-wide shape returns other Members only; local execution excludes the anchor by Member IRI and does not claim simultaneous service.
Use distinct referent IDs for separate membership/term resources. Do not substitute matching labels for RDF identity joins. Preserve every selected term and the constituency when required. For the two-term intersection, use "constraints": [] and the exact entity-list answer. For one term-scoped constituency selection, preserve an explicit date point with exactly one constraint {{"referent":"membership","field":"membershipInterval","operator":"on","value":"1994-06-01"}}; otherwise use an empty constraints list. Local code supplies the asOf date point for an approved current-representation request; do not invent a date in the draft. Return an entity list with the exact answer value {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}, or, only for an explicit how-many/count request, use {{"kind":"count","referent":"member","distinctBy":"identity"}}. Counts are distinct recorded Member IRIs from the same selection as the list, not seats or election events; never count a truncated or uncertain result.

For a dated political-party/constituency composition, use family "member_relationship_composition" and exactly the referents member, membership, term, constituency, episode, party, and affiliation. Connect member→membership→term, membership→constituency, constituency→term, member→episode, episode→membership, episode→party, party→term, and party→affiliation using their exact reviewed fact IDs. The episode must point to the exact same DailMembership that represents the constituency in the selected term. Set "constraints" to exactly [{{"referent":"episode","field":"partyEpisodeInterval","operator":"overlaps","value":"membership"}}] (inclusive xsd:dateTime endpoints; an absent end is open-ended; missing interval/start means uncertain, never a positive or negative match). When selector is "currentTerm", the local executor additionally requires both the DailMembership and PartyMembership intervals independently to contain the supplied asOf date; the model must not substitute only term membership for current service. Only typed PartyMembership records count; Independent is not a party. For "which parties" questions, use a null affiliation mention and set "answer" to exactly {{"kind":"entities","referent":"affiliation","distinctBy":"identity","display":["label"],"details":[{{"referent":"member","display":["name"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. For every named-party TD list, keep the exact named affiliation mention as a required identity filter and set "answer" to exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. Never use party-label equality or term context as a substitute for the dated episode and exact identity links.

For a named-party TD list or count with no constituency requested, use the Dáil-only party shape with exactly member, membership, term, episode, party, and affiliation referents and these seven edges: member→membership→term; member→episode→membership; episode→party→term; party→affiliation. Omit constituency and representation edges because they were not requested. Require the same exact PartyMembership/DailMembership identity join and inclusive interval-overlap constraint above. Resolve the named PoliticalAffiliationIdentity only among ParliamentaryParty identities active in the exact selected term, using the existing term-scoped party listing path; count distinct Member IRIs only after the exact party filter and temporal validation. Select an explicitly numbered term for a numbered request. For an explicitly current/as-of request OR an ordinary unqualified present-tense named-party TD/Deputy request, select currentTerm; local code resolves one exact DailTerm from House-owned dates and additionally requires both DailMembership and PartyMembership intervals independently to contain asOf. The same present-time default applies to named-party Senators. The list answer is exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}; only an explicit count uses {{"kind":"count","referent":"member","distinctBy":"identity"}}. Do not count ParliamentaryParty records, seats, or elections; missing/conflicting intervals, identity links, or truncated evidence fail closed, and recorded counts do not imply a complete roster.

Additional implemented capabilities (do not declare these unsupported):
Bill sponsorship uses the separate family "member_bill_sponsorship", never capability_selection. Its supported graph and bounded Published-year count are described below.
- Party history, including ordinary 'join', 'belonged to' and 'member of' paraphrases, uses family "member_party_history", referents member (named Member), episode (PartyMembershipEpisode), party (ParliamentaryParty), affiliation (PoliticalAffiliationIdentity). Only member has a non-null mention. Edges are member_party_membership member→episode, episode_in_parliamentary_party episode→party, parliamentary_party_has_affiliation_identity party→affiliation. Answer affiliation with display ["label"], details [], preserveEvidence true. This asks about recorded party membership, not joining events; Independent is not a party.
- Bills sponsored by a named Member uses family "member_bill_sponsorship", referents member (named Member), bill (Bill), participation (BillParticipation). Only member has a non-null mention. Edges are bill_has_sponsor_participation bill→participation and participation_has_participant participation→member. Answer bill with display ["label"], details [], preserveEvidence true. Local projection supplies Bill titles/numbers/links and primary, supporting or unknown-primary evidence; never restrict to primary sponsorship. For the exact bounded request "How many Bills did [Member] sponsor that were published in [calendar year]?", use referents member, bill, participation, process, activity; edges bill_process_cocontained bill→process, process_has_participation process→participation, participation_has_participant participation→member, and activity_forms_part_of_process activity→process. Add exactly one constraint {{"referent":"activity","field":"publishedDate","operator":"inCalendarYear","value":YEAR}}, answer {{"kind":"count","referent":"bill","distinctBy":"identity"}}. Never use legislative year or document/version dates; missing or malformed Published dates make the aggregate unavailable, not zero.
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
    if value["family"] == "current_member_composition":
        from .composition_admission import validate_draft
        try:
            return validate_draft(value, question), None
        except ValueError as error:
            raise UnsupportedComposableRequest(str(error)) from error
    count_intent = bool(re.search(r"\b(?:how many|count|number of|total of)\b", question, re.I))
    if (count_intent and re.search(r"\bseats?\b", question, re.I)
            and value["family"] == "member_relationship_composition"):
        raise UnsupportedComposableRequest(
            "Seat allocations are not recorded Member identities; no seat or election-event count was substituted."
        )
    if count_intent and (value["family"] not in {"member_relationship_composition", "member_bill_sponsorship"}
                         or not isinstance(value.get("answer"), dict)
                         or value["answer"].get("kind") != "count"):
        raise UnsupportedComposableRequest(
            "The requested count cannot be converted to a list or another aggregate; use only the validated Member identity count projection."
        )

    if re.search(r"\b(?:same|shared)\s+constituency\b", question, re.I):
        if (value["family"] != "member_relationship_composition"
                or not isinstance(value["referents"], dict)
                or not ({"anchor", "anchorMember"} & set(value["referents"]))):
            raise InvalidComposableDraft("The requested independent Member/shared-constituency operator is absent; no simplified plan is accepted.")

    if value["family"] == "capability_selection":
        return _validate_capability_selection_draft(value, question=question), None

    if value["family"] in {"constituency_representation", "member_party_history", "member_bill_sponsorship", "government_party_members"}:
        if value["family"] == "constituency_representation":
            refs = value.get("referents")
            if (isinstance(refs, dict) and isinstance(refs.get("constituency"), dict)
                    and isinstance(refs["constituency"].get("mention"), str)
                    and isinstance(refs.get("term"), dict) and refs["term"].get("selector") == "currentTerm"):
                from .composition_admission import routing_hint, validate_requirements
                if routing_hint(question):
                    try:
                        validate_requirements(question, [{"role": "R", "mention": refs["constituency"]["mention"]}],
                                              "list", "current", expected_selections=1)
                    except ValueError as error:
                        raise UnsupportedComposableRequest(str(error)) from error
        return _validate_existing_capability_draft(value, question=question), None

    if value["family"] == "member_relationship_composition":
        refs = value.get("referents")
        if isinstance(refs, dict) and "anchorMember" in refs:
            return _validate_anchored_shared_constituency_draft(value, question=question), None
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
    """Validate a narrow semantic draft, then return its complete canonical plan."""
    from .composable_plan import plan_question
    from .representation import representation_plan

    refs = value["referents"]
    bill_temporal = (value["family"] == "member_bill_sponsorship"
                     and bool(re.fullmatch(
                         r"(?is)\s*how\s+many\s+bills?\s+did\s+.+?\s+sponsor\s+(?:that\s+were\s+)?published\s+in\s+[0-9]{4}\s*[?.!]*\s*",
                         question,
                     )))
    if not isinstance(refs, dict) or value["constraints"] and not bill_temporal:
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
    if re.search(r"\b(?:not|never|except|excluding|only|before|after|since|until|between|while|count|how many|primary|supporting|elected|election|tenure)\b|[0-9]{4}", condition_text, re.I) and not bill_temporal:
        raise UnsupportedComposableRequest("This slice cannot preserve the question's additional constraint.")
    placeholder = date(2000, 1, 1)  # discarded; complete_v2_plan supplies the actual reference date
    family = value["family"]
    if family == "government_party_members":
        from .government import government_plan
        mention = refs.get("affiliation", {}).get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise InvalidComposableDraft("A named party identity is required.")
        from .interpretation import current_relationship_scope
        if current_relationship_scope(question, mention) is None:
            raise UnsupportedComposableRequest("Government membership requires present-time or explicit-current scope; historical scope cannot be defaulted.")
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
    elif family == "member_bill_sponsorship":
        mention = refs.get("member", {}).get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise InvalidComposableDraft("A Member name is required.")
        if bill_temporal:
            from .composable_plan import plan_question
            plan = plan_question(question, as_of=placeholder)
        else:
            canonical = f"Which Bills did {mention} sponsor?"
            plan = plan_question(canonical, as_of=placeholder)
        expected_answer = plan["answer"]
    else:
        mention = refs.get("member", {}).get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise InvalidComposableDraft("A Member name is required.")
        if family == "member_party_history":
            from .interpretation import current_relationship_scope
            if current_relationship_scope(question, mention) is not None:
                raise UnsupportedComposableRequest("A present/current party question requires dated current collection evidence; career-wide party history cannot substitute for current membership.")
        if re.search(r"\b(?:current|currently|now|government|minister|constituenc(?:y|ies))\b", condition_text, re.I):
            raise UnsupportedComposableRequest("This history slice cannot preserve an additional current or relationship condition.")
        canonical = (f"What parties was {mention} a member of?" if family == "member_party_history"
                     else f"Which Bills did {mention} sponsor?")
        plan = plan_question(canonical, as_of=placeholder)
        expected_answer = {"kind": "entities", "referent": "affiliation" if family == "member_party_history" else "bill",
                           "distinctBy": "identity", "display": ["label"], "details": [], "preserveEvidence": True}
    # Drafts express answer intent, not the compiler's display/evidence
    # projection. Compare against this explicit schema-compatible view while
    # retaining ``plan`` unchanged for execution.
    expected_refs = {
        key: {"type": ref["type"], "mention": ref.get("mention")}
        for key, ref in plan["referents"].items()
    }
    if "term" in expected_refs:
        expected_refs["term"]["selector"] = refs["term"].get("selector")
    expected_constraints = [] if family == "government_party_members" else plan.get("constraints", [])
    expected_draft_answer = _semantic_draft_answer(expected_answer, family=family)
    if refs != expected_refs or value["answer"] != expected_draft_answer or value["constraints"] != expected_constraints:
        raise InvalidComposableDraft("The proposed referents, constraints or answer intent differ from the supported draft projection.")
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


def _semantic_draft_answer(answer, *, family):
    """Project an executable answer to the model-authorised intent fields."""
    if family in {"government_party_members", "constituency_representation"}:
        return answer
    kind = answer.get("kind")
    if kind == "entities":
        return {"kind": kind, "referent": answer["referent"],
                "distinctBy": answer["distinctBy"], "display": ["label"],
                "details": [], "preserveEvidence": True}
    if kind in {"boolean", "count", "values", "family_result"}:
        return {key: answer[key] for key in ("kind", "referent", "distinctBy") if key in answer}
    raise InvalidComposableDraft("The canonical answer has no supported semantic draft projection.")


def _ordinal_suffix(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _validate_member_party_composition_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate the shared dated party graph for Dáil and bounded Seanad party-only selection."""
    if re.search(r"\b(?:senators?|seanad|panels?)\b", question, re.I) and not (
        isinstance(value.get("referents"), dict)
        and set(value["referents"]) == {"member", "membership", "term", "episode", "party", "affiliation"}
        and isinstance(value["referents"].get("membership"), dict)
        and value["referents"]["membership"].get("type") == "SeanadMembership"
    ):
        raise UnsupportedComposableRequest("Dáil representation cannot substitute for a Seanad/panel relationship.")
    referents = value["referents"]
    seanad_party_only = (
        isinstance(referents, dict)
        and set(referents) == {"member", "membership", "term", "episode", "party", "affiliation"}
        and isinstance(referents.get("membership"), dict)
        and referents["membership"].get("type") == "SeanadMembership"
    )
    membership_type = "SeanadMembership" if seanad_party_only else "DailMembership"
    term_type = "SeanadTerm" if seanad_party_only else "DailTerm"
    core_types = {
        "member": "Member",
        "membership": membership_type,
        "term": term_type,
        "episode": "PartyMembershipEpisode",
        "party": "ParliamentaryParty",
        "affiliation": "PoliticalAffiliationIdentity",
    }
    party_only = isinstance(referents, dict) and set(referents) == set(core_types)
    if (not seanad_party_only and isinstance(referents, dict)
            and isinstance(referents.get("membership"), dict)
            and referents["membership"].get("type") == "SeanadMembership"):
        raise UnsupportedComposableRequest("Seanad party selection requires the bounded party-only shape.")
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
                raise InvalidComposableDraft(f"The term must be one reviewed {term_type} selector.")
            if (isinstance(selector, dict) and set(selector) == {"kind", "number"}
                    and selector.get("kind") == "termNumber"
                    and type(selector.get("number")) is int
                    and 1 <= selector["number"] <= 999):
                normalized[key] = {"type": semantic_type, "selector": selector}
            elif isinstance(selector, dict) and selector == {"kind": "currentTerm"}:
                if seanad_party_only:
                    normalized[key] = {"type": semantic_type,
                                       "selector": {"kind": "currentTerm", "house": "Seanad"}}
                    continue
                from .interpretation import present_constituency_default
                constituency = referents.get("constituency", {}).get("mention")
                inferred = isinstance(constituency, str) and present_constituency_default(question, constituency)
                if party_only:
                    from .interpretation import present_party_default
                    inferred = present_party_default(question, referents["affiliation"].get("mention"), "Dail")
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
    if party_only and not seanad_party_only and term_selector["kind"] == "currentTerm" and re.search(
        r"\b(?:committee|committees|panel|panels|constituenc(?:y|ies)|represent(?:ed|s|ing)?|"
        r"office(?:holder)?s?|election|elected|before|after|between|while|and|or)\b", residual, re.I,
    ):
        raise UnsupportedComposableRequest(
            "The current Dáil party-only selection cannot drop an additional relationship, identity, or temporal condition."
        )
    if re.search(r"\b(?:and|or|while|same|shared|other|another|election|elected)\b", residual, re.I):
        raise InvalidComposableDraft("The proposed single-constituency graph omits a requested operator or projection.")
    term_numbers = ([int(number) for number in re.findall(r"\b([0-9]{1,3})(?:st|nd|rd|th)\s+seanad\b", question, re.I)]
                    if seanad_party_only else _question_dail_ordinals(question))
    if term_selector["kind"] == "termNumber":
        if len(term_numbers) != 1 or term_numbers[0] != term_selector["number"]:
            raise InvalidComposableDraft("The plan must preserve exactly one explicitly requested numeric House term.")
    elif term_numbers:
        raise InvalidComposableDraft("A currentTerm selector cannot replace an explicitly numbered Dáil term.")
    if party_only and not seanad_party_only and term_selector["kind"] == "currentTerm":
        from .interpretation import present_party_default
        if not re.search(r"\b(?:current|currently|now|today|present)\b", question, re.I) and not present_party_default(question, normalized["affiliation"]["mention"], "Dail"):
            raise UnsupportedComposableRequest("Current Dáil party selection requires an explicit current/as-of request.")
        # currentTerm means the exact House-date-selected term plus the configured
        # asOf point; it cannot silently stand in for a separately stated date.
        from .composable_plan import _question_calendar_dates
        dates, invalid_date = _question_calendar_dates(question)
        if invalid_date is not None:
            raise InvalidComposableDraft(f"{invalid_date} is not a valid calendar date; no party selection was run.")
        if dates:
            raise UnsupportedComposableRequest(
                "Current Dáil party selection cannot drop an additional calendar-date condition."
            )
    if party_only:
        from .interpretation import validate_party_scope
        try:
            validate_party_scope(question, normalized["affiliation"]["mention"], term_selector, "Seanad" if seanad_party_only else "Dail")
        except ValueError as error:
            raise UnsupportedComposableRequest(str(error)) from error

    party_list_question = bool(re.search(
        r"\b(?:which|what)\s+(?:political\s+)?part(?:y|ies)\b", question, re.IGNORECASE,
    ))
    affiliation_mention = normalized["affiliation"]["mention"]
    if not party_only and term_selector["kind"] == "currentTerm" and affiliation_mention is not None and not party_list_question:
        # An older schema family must not provide a side door around the new
        # whole-question checks when the model chooses that representation.
        from .composition_admission import validate_legacy_current_requirements
        try:
            validate_legacy_current_requirements(question, [
                {"role": "R", "mention": normalized["constituency"]["mention"]},
                {"role": "P", "mention": affiliation_mention}],
                "count" if count_intent else "list")
        except ValueError as error:
            raise UnsupportedComposableRequest(str(error)) from error
    if party_only and party_list_question:
        raise UnsupportedComposableRequest("The party-only term shape requires one named party and a Member answer.")
    if party_list_question and affiliation_mention is not None:
        raise InvalidComposableDraft("An all-parties answer cannot silently add a named affiliation filter.")
    if not party_list_question and affiliation_mention is None:
        raise InvalidComposableDraft("A named-party Member answer must retain its party identity filter.")

    contract = _plan_contract()
    relation_defs = {item["id"]: item for item in contract["relations"]}
    member_membership_fact = "member_has_seanad_membership" if seanad_party_only else "member_has_membership"
    membership_term_fact = "seanad_membership_in_term" if seanad_party_only else "membership_in_term"
    episode_membership_fact = "party_episode_in_seanad_membership" if seanad_party_only else "party_episode_in_membership"
    party_term_fact = "party_active_during_seanad_term" if seanad_party_only else "party_active_during_term"
    expected_edges = {
        member_membership_fact: ("member", "membership"),
        membership_term_fact: ("membership", "term"),
        "member_party_membership": ("member", "episode"),
        episode_membership_fact: ("episode", "membership"),
        "episode_in_parliamentary_party": ("episode", "party"),
        party_term_fact: ("party", "term"),
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

    interval_field = "partySeanadEpisodeInterval" if seanad_party_only else "partyEpisodeInterval"
    interval_constraint = {
        "referent": "episode", "field": interval_field, "operator": "overlaps", "value": "membership",
    }
    if value["constraints"] != [interval_constraint]:
        raise InvalidComposableDraft(
            f"The plan must preserve the required PartyMembershipEpisode/{membership_type} interval-overlap constraint and no extra constraints."
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
            "Named-party counts are only supported for the bounded party-only term selection; no list or simplified count was returned."
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
    if party_only:
        from .interpretation import present_party_default, RELATIONSHIP_POLICY
        if present_party_default(question, affiliation_mention, "Seanad" if seanad_party_only else "Dail"):
            final["interpretation"] = {"policy": RELATIONSHIP_POLICY, "question": question}
    elif term_selector["kind"] == "currentTerm" and not re.search(r"\b(?:current|currently|now|today)\b", question, re.I):
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

    if capability == "current_office_constituency":
        if (entry.get("handler") != "composable_office_representation" or entry.get("input") != "office_mention"
                or not isinstance(parameters, dict) or set(parameters) != {"office"}
                or not isinstance(parameters.get("office"), str) or not parameters["office"].strip()
                or _label_position(question, parameters["office"]) is None):
            raise InvalidComposableDraft("Current officeholder constituency requires one grounded NamedOffice mention.")
        from .office_representation import validate_request
        try:
            validate_request(question, parameters["office"])
        except ValueError as error:
            raise UnsupportedComposableRequest(str(error)) from error
        normalized_parameters = {"office": parameters["office"].strip()}
    elif capability == "current_committee_members":
        if (entry.get("handler") != "composable_committee_members" or entry.get("input") != "committee_mention"
                or not isinstance(parameters, dict) or set(parameters) != {"committee"}
                or not isinstance(parameters.get("committee"), str) or not parameters["committee"].strip()
                or _label_position(question, parameters["committee"]) is None):
            raise InvalidComposableDraft("Current committee listing requires one grounded Committee name.")
        from .committee_members import validate_request
        try:
            validate_request(question, parameters["committee"])
        except ValueError as error:
            raise UnsupportedComposableRequest(str(error)) from error
        normalized_parameters = {"committee": parameters["committee"].strip()}
    elif capability == "member_lookup":
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
        if keys == {"office"}:
            from .interpretation import current_office_point_request
            if not current_office_point_request(question):
                raise InvalidComposableDraft(
                    "An as-of OfficeHolding point is allowed only for a date-less present/current named-office question."
                )
            normalized_parameters = {"office": parameters["office"].strip()}
        elif keys == {"office", "startMonth", "startYear", "endMonth", "endYear"}:
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
        if (entry.get("handler") != "composable_office_evidence"
                or entry.get("input") != "member_and_office"):
            raise InvalidComposableDraft(
                "Office evidence dispatch metadata must match the reviewed composable_office_evidence handler and member_and_office input."
            )
        if (not isinstance(parameters, dict) or set(parameters) not in ({"member", "office"}, {"member", "office", "selection"})
                or ("selection" in parameters and parameters["selection"] != "latestRecorded")
                or any(not isinstance(parameters.get(key), str) or not parameters[key].strip()
                       or _label_position(question, parameters[key]) is None for key in ("member", "office"))):
            raise InvalidComposableDraft("Office evidence lookup requires grounded Member and office mentions.")
        reduced_question = question
        for mention, marker in sorted(
            ((parameters["member"], "member"), (parameters["office"], "office")),
            key=lambda item: len(item[0]), reverse=True,
        ):
            reduced_question = re.sub(re.escape(mention), f" {marker} ", reduced_question, flags=re.I)
        words = tuple(re.findall(r"[^\W_]+", reduced_question.casefold(), flags=re.UNICODE))
        accepted_shapes = {
            (*prefix, *tail)
            for prefix in (
                ("when", "was"), ("what", "date", "was"), ("what", "dates", "was"),
                ("what", "period", "was"), ("what", "periods", "was"),
                ("for", "what", "period", "was"), ("for", "what", "periods", "was"),
            )
            for tail in (("member", "office"), ("member", "the", "office"))
        }
        accepted_shapes.update({
            ("when", "did", "member", "serve", "as", "office"),
            ("when", "did", "member", "serve", "as", "the", "office"),
            ("during", "what", "period", "was", "member", "office"),
            ("during", "what", "period", "was", "member", "the", "office"),
        })
        # Apply the bounded latest-recorded operator to the same period question,
        # not to election events, durations, or an additional filtered timeline.
        latest_shapes = set()
        for shape in accepted_shapes:
            member_position = shape.index("member") + 1
            for qualifier in (("last",), ("most", "recently")):
                latest_shapes.add(shape[:member_position] + qualifier + shape[member_position:])
                latest_shapes.add(shape + qualifier)
        latest = words in latest_shapes
        if words not in accepted_shapes and not latest:
            raise UnsupportedComposableRequest(
                "Office evidence can answer only an unfiltered question asking when or for what dates/periods "
                "the named Member held the reviewed office, optionally selecting the latest recorded episode. Election dates, first-event claims, duration, "
                "and additional filters remain unsupported."
            )
        if latest != (parameters.get("selection") == "latestRecorded"):
            raise InvalidComposableDraft("Preserve the requested all-episodes versus latest-recorded office projection.")
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


def _validate_anchored_shared_constituency_draft(value, *, question):
    """Normalize the closed, term-wide shared-constituency operator."""
    from .composable_plan import _question_calendar_dates, validate_plan, PlanError
    from .structured_planner import _label_position

    referents = value["referents"]
    roles = {"member", "membership", "term", "constituency", "anchorMember", "anchorMembership"}
    if not isinstance(referents, dict) or set(referents) != roles:
        raise InvalidComposableDraft(
            "Shared-constituency selection requires one named anchor and independent anchor/answer membership paths."
        )
    if value["constraints"]:
        raise UnsupportedComposableRequest(
            "Term-wide shared-constituency co-membership does not support additional temporal or semantic filters."
        )
    if (not re.search(r"\bconstituenc(?:y|ies)\b", question, re.I)
            or not re.search(r"\b(?:same|shared|share|shares|sharing)\b", question, re.I)):
        raise InvalidComposableDraft("The question must explicitly ask for a shared or same constituency.")
    if not re.search(r"\b(?:other|another|others|fellow)\b", question, re.I):
        raise InvalidComposableDraft("The question must request other Members, excluding the named anchor.")

    anchor = referents["anchorMember"]
    if (not isinstance(anchor, dict) or set(anchor) != {"type", "mention"}
            or anchor.get("type") != "Member"
            or not isinstance(anchor.get("mention"), str) or not anchor["mention"].strip()
            or _label_position(question, anchor["mention"]) is None):
        raise InvalidComposableDraft("The anchorMember must preserve one exact user-supplied Member name.")
    for key, semantic_type in (("member", "Member"), ("membership", "DailMembership"),
                               ("anchorMembership", "DailMembership"), ("constituency", "DailConstituency")):
        item = referents[key]
        if (not isinstance(item, dict) or set(item) != {"type", "mention"}
                or item.get("type") != semantic_type or item.get("mention") is not None):
            raise InvalidComposableDraft(f"Referent {key!r} must be an unmentioned typed relationship role.")

    term = referents["term"]
    if (not isinstance(term, dict) or set(term) != {"type", "mention", "selector"}
            or term.get("type") != "DailTerm" or term.get("mention") is not None
            or not isinstance(term.get("selector"), dict)):
        raise InvalidComposableDraft("The DailTerm must use one exact numbered or globally previous-Dáil selector.")
    selector = term["selector"]
    if (set(selector) == {"kind", "number"} and selector.get("kind") == "termNumber"
            and type(selector.get("number")) is int and 1 <= selector["number"] <= 999):
        normalized_selector = dict(selector)
        ordinal_numbers = _question_dail_ordinals(question)
        if (ordinal_numbers != [selector["number"]]
                or not re.search(r"\bd[áa]il\b", question, re.I)):
            raise InvalidComposableDraft("The numbered selector must preserve exactly one explicitly requested Dáil ordinal.")
        selector_scope = "numbered"
    elif selector == {"kind": "previousTerm"}:
        if not re.search(r"\b(?:last|previous)\s+d[áa]il\b", question, re.I):
            raise InvalidComposableDraft("previousTerm is allowed only for an explicit globally previous/last Dáil request.")
        if _question_dail_ordinals(question):
            raise InvalidComposableDraft("A globally previous Dáil selector cannot replace an explicit numbered term.")
        normalized_selector = {"kind": "previousTerm", "house": "Dail"}
        selector_scope = "previous"
    else:
        raise InvalidComposableDraft("Use only a numeric termNumber or the global previousTerm Dáil selector.")
    if selector_scope == "previous" and _question_dail_ordinals(question):
        raise InvalidComposableDraft("Do not combine the previous Dáil selector with a numbered term.")

    dates, invalid_date = _question_calendar_dates(question)
    if invalid_date is not None or dates:
        raise UnsupportedComposableRequest("This term-wide co-membership projection does not support explicit calendar dates.")

    count_intent = bool(re.search(r"\b(?:how\s+many|count|number\s+of|total\s+of)\b", question, re.I))
    count_answer = {"kind": "count", "referent": "member", "distinctBy": "identity"}
    list_answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [], "preserveEvidence": False,
    }
    expected_answer = count_answer if count_intent else list_answer
    if value["answer"] != expected_answer:
        raise InvalidComposableDraft("Use a distinct Member count only for count intent; otherwise return the exact Member list.")

    residual = question
    residual = re.sub(re.escape(anchor["mention"]), " ", residual, flags=re.I)
    residual = re.sub(r"\b[0-9]{1,3}(?:st|nd|rd|th)\b", " ", residual, flags=re.I)
    allowed = set("""
        who what which how many count number total of the a an other another others fellow
        td tds deputy deputies member members in during for from with as same shared share shares
        constituency constituencies were was are is did do does have has had represent represents sharing
        represented representing serve served serving service term dáil dail previous last
        there also list show name give me records local evidence evidenced identify find tell
        can could you that those these whom alongside parliamentary
    """.split())
    words = set(re.findall(r"[^\W\d_]+", residual.casefold()))
    if re.search(r"\d", residual) or words - allowed:
        raise UnsupportedComposableRequest(
            "The anchored co-membership projection cannot preserve an additional filter, temporal condition, or answer request."
        )
    if re.search(r"\b(?:party|parties|office|minister|taoiseach|election|elected|simultaneous|simultaneously|while|when|current|currently|now|today|before|after|since|until|between|except|excluding|only|seats?)\b", question, re.I):
        raise UnsupportedComposableRequest(
            "Party, office, election, simultaneity, current-point, and additional temporal filters are not supported by this term-wide projection."
        )

    expected_edges = {
        ("member_has_membership", "anchorMember", "anchorMembership"),
        ("membership_in_term", "anchorMembership", "term"),
        ("membership_represents", "anchorMembership", "constituency"),
        ("member_has_membership", "member", "membership"),
        ("membership_in_term", "membership", "term"),
        ("membership_represents", "membership", "constituency"),
        ("constituency_in_term", "constituency", "term"),
    }
    if not isinstance(value["relations"], list) or len(value["relations"]) != len(expected_edges):
        raise InvalidComposableDraft("Both independent Member paths and the term-scoped constituency occurrence are required.")
    edges = []
    relation_ids = set()
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Relation IDs must be unique.")
        relation_ids.add(relation_id)
        edges.append((relation["fact"], relation["from"], relation["to"]))
    if set(edges) != expected_edges or len(edges) != len(expected_edges):
        raise InvalidComposableDraft("The proposal must preserve both exact term/constituency identity paths and no extra edge.")

    plan = {
        "version": 2, "asOf": "2000-01-01", "family": "member_relationship_composition",
        "referents": {
            "member": {"type": "Member", "answer": True},
            "membership": {"type": "DailMembership"},
            "term": {"type": "DailTerm", "selector": normalized_selector},
            "constituency": {"type": "DailConstituency"},
            "anchorMember": {"type": "Member", "mention": anchor["mention"].strip(), "resolution": "unresolved"},
            "anchorMembership": {"type": "DailMembership"},
        },
        "relations": [dict(item) for item in value["relations"]],
        "constraints": [],
        "answer": expected_answer,
    }
    try:
        validate_plan(plan)
    except (PlanError, KeyError, TypeError) as error:
        raise InvalidComposableDraft(str(error)) from error
    return {key: item for key, item in plan.items() if key not in {"version", "asOf"}}


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


def _validate_current_cross_house_membership_draft(value: dict[str, Any], *, question: str) -> dict[str, Any]:
    """Validate only term-wide recorded membership in the current Dáil and Seanad."""
    from .composable_plan import PlanError, _question_calendar_dates, validate_plan

    if value["constraints"]:
        raise UnsupportedComposableRequest(
            "The current cross-house intersection is term-wide; no simultaneity or extra temporal filter was dropped."
        )
    roles = {"member", "seanad_membership", "seanad_term", "dail_membership", "dail_term"}
    referents = value["referents"]
    if not isinstance(referents, dict) or set(referents) != roles:
        raise InvalidComposableDraft("The cross-house intersection requires independent Seanad and Dáil membership paths.")
    if referents["member"] != {"type": "Member", "mention": None}:
        raise InvalidComposableDraft("The cross-house selection returns a set-valued Member identity answer.")
    for key, semantic_type in (("seanad_membership", "SeanadMembership"),
                               ("dail_membership", "DailMembership")):
        if referents[key] != {"type": semantic_type, "mention": None}:
            raise InvalidComposableDraft(f"Referent {key!r} must be a plain typed {semantic_type} path.")
    for key, semantic_type in (("seanad_term", "SeanadTerm"), ("dail_term", "DailTerm")):
        if referents[key] != {"type": semantic_type, "mention": None, "selector": {"kind": "currentTerm"}}:
            raise InvalidComposableDraft(f"Referent {key!r} must preserve its current HouseTerm selector.")
    if not (re.search(r"\b(?:seanad|senators?)\b", question, re.I)
            and re.search(r"\b(?:d[áa]il|deput(?:y|ies)|tds?)\b", question, re.I)
            and re.search(r"\b(?:current|this)\s+seanad\b", question, re.I)
            and re.search(r"\b(?:current|this)\s+d[áa]il\b", question, re.I)):
        raise UnsupportedComposableRequest(
            "Cross-house history is not substituted for an intersection of both explicitly current House terms."
        )
    if _HISTORICAL_CURRENT_CONTRAST.search(question) or re.search(
        r"\b(?:simultaneous(?:ly)?|concurrent(?:ly)?|overlap(?:ping)?|currently|now|today|still|at\s+the\s+same\s+time|"
        r"same\s+period|while\s+(?:serving|a\s+member)|previous(?:ly)?|historical|history|before|after|since|until|during|between|"
        r"party|parties|constituenc(?:y|ies)|panels?|offices?|minister|election|elected|committees?|bills?|votes?|"
        r"how\s+many|count|number\s+of|seats?)\b",
        question, re.I,
    ):
        raise UnsupportedComposableRequest(
            "Simultaneity, historical-period and additional-filter requests are outside the term-wide cross-house intersection."
        )
    dates, invalid_date = _question_calendar_dates(question)
    if invalid_date is not None or dates or _question_dail_ordinals(question):
        raise UnsupportedComposableRequest("The current cross-house intersection accepts no extra date or ordinal filter.")
    answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [], "preserveEvidence": False,
    }
    if value["answer"] != answer:
        raise InvalidComposableDraft("The current cross-house intersection returns distinct Member identities only.")

    expected_edges = {
        ("member_has_seanad_membership", "member", "seanad_membership"),
        ("seanad_membership_in_term", "seanad_membership", "seanad_term"),
        ("member_has_membership", "member", "dail_membership"),
        ("membership_in_term", "dail_membership", "dail_term"),
    }
    relation_defs = {item["id"]: item for item in _plan_contract()["relations"]}
    actual_edges = []
    relation_ids = set()
    if not isinstance(value["relations"], list) or len(value["relations"]) != len(expected_edges):
        raise InvalidComposableDraft("Every exact current cross-house membership edge is required.")
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Cross-house relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Cross-house relation IDs must be unique.")
        relation_ids.add(relation_id)
        fact = _identifier(relation["fact"], f"relations[{index}].fact")
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        edge = (fact, source, target)
        definition = relation_defs.get(fact)
        if edge not in expected_edges or definition is None:
            raise UnsupportedComposableRequest(f"Relationship {fact!r} is outside the exact current cross-house graph.")
        if ((referents[source]["type"], referents[target]["type"])
                != (definition["subjectType"], definition["objectType"])):
            raise UnsupportedComposableRequest(f"Reviewed relation {fact!r} has incompatible cross-house types.")
        actual_edges.append(edge)
    if set(actual_edges) != expected_edges:
        raise InvalidComposableDraft("Both independent exact membership/term paths are required exactly once.")

    plan = {
        "version": 2, "asOf": "2000-01-01", "family": "member_relationship_composition",
        "referents": {
            "member": {"type": "Member", "answer": True},
            "seanad_membership": {"type": "SeanadMembership"},
            "seanad_term": {"type": "SeanadTerm", "selector": {"kind": "currentTerm", "house": "Seanad"}},
            "dail_membership": {"type": "DailMembership"},
            "dail_term": {"type": "DailTerm", "selector": {"kind": "currentTerm", "house": "Dail"}},
        },
        "relations": [dict(item) for item in value["relations"]],
        "answer": answer,
    }
    try:
        validate_plan(plan)
    except (PlanError, KeyError, TypeError) as error:
        raise InvalidComposableDraft(str(error)) from error
    return {key: item for key, item in plan.items() if key not in {"version", "asOf"}}


def _validate_current_seanad_prior_dail_membership_draft(
    value: dict[str, Any], *, question: str,
) -> dict[str, Any]:
    """Accept only the positive current-Seanad/strictly-prior-Dáil projection."""
    from .composable_plan import PlanError, _question_calendar_dates, validate_plan

    if value["constraints"]:
        raise UnsupportedComposableRequest(
            "Current Seanad/prior Dáil membership accepts no additional temporal or relationship filters."
        )
    roles = {"member", "seanad_membership", "seanad_term", "dail_membership", "dail_term"}
    referents = value["referents"]
    if not isinstance(referents, dict) or set(referents) != roles:
        raise InvalidComposableDraft("Prior-service selection requires independent Seanad and Dáil membership paths.")
    if referents["member"] != {"type": "Member", "mention": None}:
        raise InvalidComposableDraft("Prior-service selection returns a set-valued Member identity answer.")
    for key, semantic_type in (
        ("seanad_membership", "SeanadMembership"),
        ("dail_membership", "DailMembership"),
    ):
        if referents[key] != {"type": semantic_type, "mention": None}:
            raise InvalidComposableDraft(f"Referent {key!r} must be a plain typed {semantic_type} path.")
    if referents["seanad_term"] != {
        "type": "SeanadTerm", "mention": None, "selector": {"kind": "currentTerm"},
    }:
        raise InvalidComposableDraft("Prior-service selection must resolve the current SeanadTerm from House-owned dates.")
    if referents["dail_term"] != {"type": "DailTerm", "mention": None}:
        raise InvalidComposableDraft("Prior Dáil service is determined by accepted membership dates, not a selected ordinal.")

    current_seanad = bool(re.search(
        r"\b(?:current|currently|present|now|sitting)\b.{0,35}\b(?:seanad|senators?)\b|"
        r"\b(?:seanad|senators?)\b.{0,35}\b(?:current|currently|present|now)\b",
        question, re.I,
    ))
    dail_service = bool(re.search(r"\b(?:d[áa]il|deput(?:y|ies)|tds?)\b", question, re.I))
    prior_service = bool(re.search(
        r"\b(?:previously|previous|prior|earlier|former|formerly|used\s+to|past|before)\b",
        question, re.I,
    ))
    from .interpretation import prior_service_present_default
    current_seanad = current_seanad or prior_service_present_default(question)
    if not (current_seanad and dail_service and prior_service):
        raise UnsupportedComposableRequest(
            "This projection requires current Seanad membership and an explicitly requested prior Dáil service path."
        )

    extra_filter = re.search(
        r"\b(?:simultaneous(?:ly)?|concurrent(?:ly)?|overlap(?:ping)?|at\s+the\s+same\s+time|"
        r"party|parties|political\s+affiliation|constituenc(?:y|ies)|panels?|offices?|minister|"
        r"elections?|elected|committees?|bills?|votes?|seats?|sittings?|during|between|since|until|after)\b|"
        r"\b(?:current|this|present)\s+d[áa]il\b|"
        r"\b(?:fine\s+gael|fianna\s+f[áa]il|sinn\s+f[ée]in|labour(?:\s+party)?|green\s+party)\b",
        question, re.I,
    )
    dates, invalid_date = _question_calendar_dates(question)
    year_or_window = re.search(
        r"\b(?:during|between|since|until|after|on|in|for|from|throughout)\s+(?:the\s+)?"
        r"(?:(?:18|19|20|21)[0-9]{2}|January|February|March|April|May|June|July|August|September|October|November|December)\b",
        question, re.I,
    )
    non_member_count = re.search(
        r"\b(?:how many|number of|count(?:\s+of)?)\s+(?:(?:prior|previous|recorded|distinct)\s+)?"
        r"(?:d[áa]il\s+)?(?:terms?|episodes?|times|stints?|paths?|memberships)\b",
        question, re.I,
    )
    if (extra_filter or invalid_date is not None or dates or year_or_window
            or re.search(r"\b(?:18|19|20|21)[0-9]{2}\b", question)
            or _question_dail_ordinals(question) or non_member_count):
        raise UnsupportedComposableRequest(
            "Current Seanad/prior Dáil selection cannot drop an additional filter, date, term ordinal or simultaneity condition."
        )

    list_answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [
            {"referent": "seanad_membership", "display": ["start", "end"]},
            {"referent": "seanad_term", "display": ["label"]},
            {"referent": "dail_membership", "display": ["start", "end"]},
            {"referent": "dail_term", "display": ["label"]},
        ],
        "preserveEvidence": True,
    }
    count_answer = {"kind": "count", "referent": "member", "distinctBy": "identity"}
    proposed_answer = value["answer"]
    canonical_answer = None
    if proposed_answer == count_answer:
        canonical_answer = count_answer
    elif isinstance(proposed_answer, dict) and set(proposed_answer) == {
        "kind", "referent", "distinctBy", "display", "details", "preserveEvidence",
    }:
        expected_details = {
            "seanad_membership": {"start", "end"},
            "seanad_term": {"label"},
            "dail_membership": {"start", "end"},
            "dail_term": {"label"},
        }
        detail_map = {}
        details = proposed_answer.get("details")
        if isinstance(details, list):
            for detail in details:
                if (not isinstance(detail, dict) or set(detail) != {"referent", "display"}
                        or not isinstance(detail.get("referent"), str)
                        or detail["referent"] in detail_map
                        or not isinstance(detail.get("display"), list)):
                    detail_map = {}
                    break
                detail_map[detail["referent"]] = set(detail["display"])
        if (proposed_answer.get("kind") == "entities"
                and proposed_answer.get("referent") == "member"
                and proposed_answer.get("distinctBy") == "identity"
                and proposed_answer.get("display") == ["name"]
                and proposed_answer.get("preserveEvidence") is True
                and detail_map == expected_details):
            canonical_answer = list_answer
    if canonical_answer is None:
        raise InvalidComposableDraft("Prior-service selection returns Member identities with both House paths or their distinct count.")

    expected_edges = {
        ("member_has_seanad_membership", "member", "seanad_membership"),
        ("seanad_membership_in_term", "seanad_membership", "seanad_term"),
        ("member_has_membership", "member", "dail_membership"),
        ("membership_in_term", "dail_membership", "dail_term"),
    }
    relation_defs = {item["id"]: item for item in _plan_contract()["relations"]}
    actual_edges = []
    relation_ids = set()
    if not isinstance(value["relations"], list) or len(value["relations"]) != len(expected_edges):
        raise InvalidComposableDraft("Every exact current Seanad/prior Dáil membership edge is required.")
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Prior-service relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Prior-service relation IDs must be unique.")
        relation_ids.add(relation_id)
        fact = _identifier(relation["fact"], f"relations[{index}].fact")
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        edge = (fact, source, target)
        definition = relation_defs.get(fact)
        if edge not in expected_edges or definition is None:
            raise UnsupportedComposableRequest(f"Relationship {fact!r} is outside the reviewed prior-service graph.")
        if (referents[source]["type"], referents[target]["type"]) != (
            definition["subjectType"], definition["objectType"],
        ):
            raise UnsupportedComposableRequest(f"Reviewed relation {fact!r} has incompatible prior-service types.")
        actual_edges.append(edge)
    if set(actual_edges) != expected_edges:
        raise InvalidComposableDraft("Both independent Member-to-HouseTerm paths are required exactly once.")

    plan = {
        "version": 2, "asOf": "2000-01-01", "family": "member_relationship_composition",
        "referents": {
            "member": {"type": "Member", "answer": True},
            "seanad_membership": {"type": "SeanadMembership"},
            "seanad_term": {"type": "SeanadTerm", "selector": {"kind": "currentTerm", "house": "Seanad"}},
            "dail_membership": {"type": "DailMembership"},
            "dail_term": {"type": "DailTerm"},
        },
        "relations": [dict(item) for item in value["relations"]],
        "answer": canonical_answer,
    }
    try:
        validate_plan(plan)
    except (PlanError, KeyError, TypeError) as error:
        raise InvalidComposableDraft(str(error)) from error
    return {key: item for key, item in plan.items() if key not in {"version", "asOf"}}


def _validate_member_relationship_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate only the two closed relationship projections using v2 edges."""
    referents = value["referents"]
    if isinstance(referents, dict) and any(
        isinstance(item, dict) and item.get("type") == "PartyMembershipEpisode"
    for item in referents.values()
    ):
        return _validate_member_party_composition_draft(value, question=question)
    if isinstance(referents, dict) and any(
        isinstance(item, dict) and item.get("type") in {"SeanadMembership", "SeanadTerm"}
        for item in referents.values()
    ):
        dail_term = referents.get("dail_term")
        if isinstance(dail_term, dict) and dail_term.get("type") == "DailTerm" and "selector" not in dail_term:
            return _validate_current_seanad_prior_dail_membership_draft(value, question=question)
        return _validate_current_cross_house_membership_draft(value, question=question)
    if re.search(r"\b(?:senators?|seanad|panels?)\b", question, re.I):
        raise UnsupportedComposableRequest("The Dáil relationship compiler cannot substitute for a Seanad relationship.")
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

    if current_terms and len(constituency_mentions) == 1:
        from .composition_admission import routing_hint, validate_requirements
        if routing_hint(question):
            try:
                validate_requirements(question, [{"role": "R", "mention": next(iter(constituency_mentions.values()))}],
                                      "count" if count_intent else "list", "current", expected_selections=1)
            except ValueError as error:
                raise UnsupportedComposableRequest(str(error)) from error

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
