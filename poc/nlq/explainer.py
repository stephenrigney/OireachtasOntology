"""Read-only presentation of composable v2 evidence, never a compiler trace.

Field mapping and known evidence gaps are documented in query-explainer-evidence.md.
This module deliberately does not validate, resolve or execute a plan.
"""

from __future__ import annotations

from datetime import date

from .interpretation import current_scope_explanation


# Singular parliamentary roles, not RDF vocabulary in the default view.
TYPES = {
    "Member": "Member", "DailTerm": "Dáil term", "SeanadTerm": "Seanad term",
    "DailMembership": "Dáil membership", "SeanadMembership": "Seanad membership",
    "DailConstituency": "Dáil constituency", "SeanadPanel": "Seanad panel",
    "SeanadRepresentation": "Seanad representation", "Committee": "committee",
    "CommitteeMembership": "committee membership", "NamedOffice": "office",
    "OfficeHolding": "office-holding period", "PartyMembershipEpisode": "party-affiliation period",
    "ParliamentaryParty": "term-specific parliamentary party",
    "PoliticalAffiliationIdentity": "political affiliation",
    "ParliamentaryCollectionMembership": "parliamentary collection membership",
    "ParliamentaryMemberCollection": "parliamentary collection",
    "IndependentMemberCollection": "Independent status",
    "CabinetMembership": "Cabinet membership", "Government": "Government",
    "Bill": "Bill", "BillProcess": "Bill process", "BillActivity": "Bill activity",
    "BillParticipation": "sponsorship record", "ExplanatoryMemoWork": "explanatory memorandum",
    "DebateSitting": "debate sitting", "DebateRecord": "official debate record",
}

# Reviewed against composable-query-plan-contract.json and the family executors.
# These describe edges, not operations that supposedly happened.
RELATIONS = {
    "member_has_membership": "{a} has a recorded Dáil membership: {b}.",
    "membership_in_term": "{a} belongs to {b}.",
    "membership_represents": "{a} represents {b}.",
    "constituency_in_term": "{a} is the constituency occurrence for {b}.",
    "member_has_seanad_membership": "{a} has a recorded Seanad membership: {b}.",
    "seanad_membership_in_term": "{a} belongs to {b}.",
    "seanad_membership_represents": "{a} represents {b}.",
    "seanad_membership_represents_resource": "{a} has the recorded representation {b}.",
    "member_party_membership": "{a} has a party-affiliation period: {b}.",
    "party_episode_in_membership": "{a} is linked to the same exact Dáil membership, {b}.",
    "party_episode_in_seanad_membership": "{a} is linked to the same exact Seanad membership, {b}.",
    "episode_in_parliamentary_party": "{a} is affiliated with {b}.",
    "parliamentary_party_has_affiliation_identity": "{a} is linked to the political identity {b}.",
    "party_active_during_term": "{a} is associated with {b}.",
    "party_active_during_seanad_term": "{a} is associated with {b}.",
    "member_has_office_holding": "{a} has a recorded office-holding period: {b}.",
    "office_holding_of_office": "{a} is a holding of {b}.",
    "member_has_cabinet_membership": "{a} has a Cabinet membership: {b}.",
    "cabinet_membership_of_government": "{a} is membership of the constitutional {b}.",
    "member_has_committee_membership": "{a} has a committee membership: {b}.",
    "committee_membership_of_committee": "{a} is membership of {b}.",
    "committee_in_term": "{a} is associated with {b}.",
    "committee_in_seanad_term": "{a} is associated with {b}.",
    "member_has_collection_membership": "{a} has a parliamentary collection membership: {b}.",
    "collection_membership_of_collection": "{a} is membership of {b}.",
    "sitting_produced_record": "{a} produced {b}.",
    "bill_has_sponsor_participation": "{a} is linked through its delivery and legislative process to {b}.",
    "participation_has_participant": "{a} names {b} by exact person identity.",
    "bill_process_cocontained": "{a} is linked through its delivery to {b}; sharing a source graph alone is not enough.",
    "activity_forms_part_of_process": "{a} forms part of {b}.",
    "process_has_participation": "{a} contains {b}.",
    "bill_has_explanatory_memo_work": "{a} may supply {b} through its recorded document links.",
}

# Closed family_result projections do not express their shape in answer.kind.
# Family-specific wording is limited to their reviewed, different semantics.
PROJECTIONS = {
    "member_lookup": "Matching local Member identity information.",
    "previous_service": "Whether the Member has recorded service in the previous Dáil selected from House dates at the reference date {as_of}.",
    "dail_duration": "Total dated Dáil service, combining overlapping periods without filling gaps, through the reference date {as_of}.",
    "term_count": "A count of distinct recorded Dáil terms, not membership rows.",
    "seanad_entry": "The earliest recorded dated Seanad entry and separate later membership periods.",
    "seanad_representation": "The recorded Seanad representation designation, where available.",
    "current_collection": "Parliamentary collection membership at the reference date {as_of}; Independent is a status, not a party.",
    "committee_boolean": "Whether local records establish service on the uniquely dated current committee at the reference date {as_of}.",
    "committee_count": "A count of distinct committee identities, not membership records.",
    "dail_all": "All matching distinct Member identities with recorded Dáil service.",
    "bill_lookup": "The selected Bill's title, recorded status, dated history and memorandum link where available.",
    "bill_title_search": "Distinct official Bill candidates matching the title mention; ambiguity is not resolved by guessing.",
    "bill_status_history": "The selected Bill's recorded status and dated history, not a prediction of its next stage.",
    "bill_sponsors": "Recorded sponsorships, including primary, supporting or unknown status where available.",
    "bills_published": "Bills with a dated Published activity in the selected calendar year.",
    "non_enacted_bills": "Bills classified and counted by known status other than Enacted. Unclassified records may also be shown; missing or conflicting status is not counted as non-enacted.",
    "office_overlap": "Whether accepted office-holding evidence overlaps any part of the requested period, with recorded dates.",
    "office_point": "Locally evidenced officeholders on the requested date, with recorded holding dates.",
    "office_current_coverage": "A current officeholder only if sufficiently complete accepted roster evidence is available.",
    "committee_chair": "Committee identity and the available chair-evidence limitation; membership does not establish chairmanship.",
    "committee_conflict": "The source-coverage conflict, not a verified committee roster.",
    "dail_seats": "The selected Dáil term's recorded seat allocation, not a count of Member records.",
    "dail_parties_and_groups": "Recorded term-specific parliamentary parties and any requested group-coverage limitation.",
    "bill_quarantine": "The selected Bill's local source-availability evidence, not proof of nonexistence.",
    "debate_lookup": "The actual sitting date and official debate record link, where locally recorded.",
    "committee_topic_latest": "The available topic and coverage limitation; metadata does not establish substantive examination or latest coverage.",
    "bill_votes": "The voting-evidence limitation; sponsorship is not voting evidence.",
    "debate_transcript": "The transcript-content limitation; record metadata is not speech text.",
}


def _ordinal(number):
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _label(ref, as_of):
    selector = ref.get("selector") or {}
    kind = selector.get("kind")
    house = "Seanad" if ref.get("type") == "SeanadTerm" else "Dáil"
    if ref.get("label") or ref.get("mention"):
        return ref.get("label") or ref["mention"]
    if kind == "termNumber":
        return f"the {_ordinal(selector['number'])} {house}"
    if kind == "numberYear":
        return f"Bill {selector.get('number')} of {selector.get('year')}"
    if kind == "currentTerm":
        return f"the current {house} term at {as_of}"
    if kind == "previousTerm":
        return f"the previous {house} term relative to {as_of}"
    if kind == "latestRecorded":
        return f"the latest recorded {house} term (not necessarily current)"
    return TYPES.get(ref.get("type"), "entity")


def _condition(item, labels):
    field, op, value = item.get("field"), item.get("operator"), item.get("value")
    subject = labels.get(item.get("referent"), "The selected record")
    if field in {"partyEpisodeInterval", "partySeanadEpisodeInterval"} and op == "overlaps":
        return f"The relevant periods must overlap, including their endpoints: {subject} and {labels.get(value, 'the linked membership')}."
    if field == "interval" and op == "commonIntersection" and isinstance(value, list):
        return "All these periods must share a common inclusive intersection: " + ", ".join(labels.get(v, "recorded period") for v in value) + "."
    if field in {"membershipInterval", "cabinetInterval", "partyEpisodeInterval", "partySeanadEpisodeInterval", "interval"} and op in {"on", "currentAt"}:
        return f"The period for {subject} must contain {value}, including endpoints."
    if field == "interval" and op == "overlaps" and isinstance(value, dict):
        if value.get("start") == value.get("end"):
            return f"The office-holding period must include the calendar date {value.get('start')}."
        return f"The office-holding period must overlap any part of {value.get('start')} to {value.get('end')}, including both dates; service throughout is not required."
    if field == "identity" and op == "distinctFrom":
        return f"Exclude {labels.get(value, 'the named anchor')} by exact Member identity."
    if field == "memberIdentity" and op == "equals":
        return "Match the exact resolved Member identity, not just a name."
    if (field, op) in {("publishedDate", "inCalendarYear"), ("activityTypeAndDate", "publishedInCalendarYear")}:
        return f"A recorded Published activity must be dated in calendar year {value}; legislative year alone is not enough."
    if field == "date" and op == "on":
        return f"The sitting date must be {value}."
    if field == "chamber" and op == "equals":
        return f"The debate record must be for {'Dáil' if value == 'dail' else 'Seanad' if value == 'seanad' else value}."
    if field == "legislativeYear" and op == "equals":
        return f"The Bill's legislative year must be {value}."
    if field == "processStatus" and op == "knownExcept":
        return f"Only known statuses other than {value} qualify for classification and counting. Records with missing or conflicting status may appear separately as unclassified evidence."
    if field == "temporalOwner" and op == "currentAt":
        return f"The committee's own dates must establish it as current at {value}."
    if field == "coverage" and op == "requires" and value == "complete_current_roster":
        return "A sufficiently complete accepted current-office roster is required."
    if field == "coverage" and op == "knownConflict":
        return "The plan records a known source-coverage conflict."
    return None


def _shared_constituency_anchor(plan):
    """Recognise the reviewed independent paths sharing both exact resources."""
    if plan.get("family") != "member_relationship_composition":
        return None
    refs, edges = plan.get("referents", {}), plan.get("relations", [])
    answer_id = plan.get("answer", {}).get("referent")
    if refs.get(answer_id, {}).get("type") != "Member":
        return None

    def targets(source, fact):
        return {e.get("to") for e in edges if e.get("from") == source and e.get("fact") == fact}

    for anchor, ref in refs.items():
        if anchor == answer_id or ref.get("type") != "Member":
            continue
        for member_path in targets(answer_id, "member_has_membership"):
            for anchor_path in targets(anchor, "member_has_membership"):
                places = targets(member_path, "membership_represents") & targets(anchor_path, "membership_represents")
                terms = targets(member_path, "membership_in_term") & targets(anchor_path, "membership_in_term")
                if member_path != anchor_path and len(places) == len(terms) == 1:
                    return anchor, next(iter(places)), next(iter(terms))
    return None


def _relationship_summary(plan, labels):
    """A short sentence from reviewed connected paths, not question matching."""
    refs, answer = plan.get("referents", {}), plan.get("answer", {})
    edges = plan.get("relations", [])

    def targets(source, fact):
        return [e.get("to") for e in edges if e.get("from") == source and e.get("fact") == fact]

    def named(key):
        ref = refs.get(key, {})
        return bool(ref.get("mention") or ref.get("label") or ref.get("selector"))

    target_id = answer.get("referent")
    target_type = refs.get(target_id, {}).get("type")
    action = "Count distinct" if answer.get("kind") == "count" and answer.get("distinctBy") == "identity" else "Count" if answer.get("kind") == "count" else "Find"
    if target_type == "Member":
        clauses = []
        shared = _shared_constituency_anchor(plan)
        for membership in targets(target_id, "member_has_membership") + targets(target_id, "member_has_seanad_membership"):
            terms = [labels[k] for fact in ("membership_in_term", "seanad_membership_in_term") for k in targets(membership, fact) if named(k)]
            places = [labels[k] for k in targets(membership, "membership_represents") if named(k)]
            if places:
                clauses.append("recorded representation of " + " or ".join(places) + (" in " + " and ".join(terms) if terms else ""))
            elif terms:
                clauses.append("recorded membership in " + " and ".join(terms))
        affiliations = [labels[affiliation] for episode in targets(target_id, "member_party_membership")
                        for party in targets(episode, "episode_in_parliamentary_party")
                        for affiliation in targets(party, "parliamentary_party_has_affiliation_identity") if named(affiliation)]
        if affiliations:
            clauses.append("party affiliation with " + " or ".join(affiliations))
        if shared:
            anchor, place, term = shared
            summary = f"{action} other Members sharing {labels[anchor]}'s constituency, {labels[place]}, in {labels[term]}"
            if affiliations:
                summary += " and with party affiliation with " + " or ".join(affiliations)
            return summary + ". The anchor Member is excluded by exact identity."
        if clauses:
            return f"{action} Members with " + " and ".join(clauses) + "."
    if target_type == "Bill":
        members = [labels[member] for participation in targets(target_id, "bill_has_sponsor_participation")
                   for member in targets(participation, "participation_has_participant") if named(member)]
        if members:
            return f"{action} Bills with recorded sponsorship by " + " and ".join(members) + "."
    return None


def explain_validated_plan(plan: dict, *, question: str = "") -> dict:
    """Only call with the actual plan already accepted by validate_plan."""
    refs, answer = plan.get("referents", {}), plan.get("answer", {})
    as_of = plan.get("asOf", "the configured reference date")
    labels = {key: _label(ref, as_of) for key, ref in refs.items()}
    # Different unbound evidence roles must not look like one shared resource.
    for key, ref in refs.items():
        peers = [k for k, r in refs.items() if r.get("type") == ref.get("type") and labels[k] == labels[key]]
        if len(peers) > 1:
            for index, peer in enumerate(peers, 1):
                labels[peer] = f"{labels[peer]} ({index})"
    entities, conditions, gaps = [], [], []
    if set(plan) - {"version", "asOf", "family", "referents", "relations", "constraints", "answer", "interpretation"}:
        gaps.append("Additional plan settings are not translated here; consult the technical query plan.")
    if set(answer) - {"kind", "referent", "projection", "distinctBy", "display", "details", "preserveEvidence", "preserveGaps", "includeGroups"}:
        gaps.append("Additional result settings are not translated here; consult the technical query plan.")
    for key, ref in refs.items():
        selector = ref.get("selector") or {}
        state = ref.get("resolution")
        if ref.get("mention") or selector or state or ref.get("iri") or ref.get("members"):
            resolution = {
                "resolved": "Matched to an ontology identity" if ref.get("iri") else "Recorded match set; see technical evidence",
                "ambiguous": "Several matches; no single identity selected",
                "unresolved": "Identity not yet resolved", "not_found": "No matching local identity found",
                "source_data_unavailable": "Identity evidence unavailable", "unsupported_mapping": "Identity mapping unsupported",
            }.get(state, "Selector or mention specified; no resolved identity supplied")
            entities.append({"label": labels[key], "resolution": resolution})
        if ref.get("members"):
            conditions.append("Match any one of these constituency identities: " + " OR ".join(_label(r, as_of) for r in ref["members"]) + ".")
        kind = selector.get("kind")
        if kind in {"termNumber", "numberYear", "currentTerm", "previousTerm", "latestRecorded"}:
            conditions.append(f"Select {labels[key]}." if not ref.get("mention") else f"Selector for {labels[key]}: {_label({**ref, 'label': None, 'mention': None}, as_of)}.")
        elif kind == "onDate":
            conditions.append(f"Select House terms containing {selector.get('date')}; this does not establish an actual sitting.")
        elif kind == "duringMonth":
            conditions.append(f"Select House terms overlapping the full calendar month {selector.get('year')}-{selector.get('month'):02d}.")
        elif kind == "sittingDate":
            conditions.append(f"Select the {selector.get('chamber')} sitting on {selector.get('date')}.")
        elif selector:
            gaps.append("A selector has no plain-language translation; consult the technical query plan.")
    relationships = []
    for relation in plan.get("relations", []):
        wording = RELATIONS.get(relation.get("fact"))
        if wording:
            relationships.append(wording.format(a=labels.get(relation.get("from"), "entity"), b=labels.get(relation.get("to"), "entity")))
        else:
            gaps.append("A relationship has no plain-language translation; consult the technical query plan.")
    for item in plan.get("constraints", []):
        text = _condition(item, labels)
        if text:
            conditions.append(text)
        else:
            gaps.append("An additional condition has no plain-language translation; consult the technical query plan.")
    family = plan.get("family")
    shared = _shared_constituency_anchor(plan)
    if shared:
        anchor, _, _ = shared
        if not any(c.get("field") == "identity" and c.get("operator") == "distinctFrom" for c in plan.get("constraints", [])):
            conditions.append(f"Exclude {labels[anchor]} by exact Member identity.")
        if not plan.get("constraints"):
            conditions.append("This is term-wide recorded co-membership, not evidence of simultaneous service.")
    if (family == "constituency_representation"
            and refs.get("term", {}).get("selector", {}).get("kind") == "currentTerm"):
        conditions.append(f"The representation membership's own period must contain {as_of}; being linked to the current term alone is not enough.")
    current_party = family == "member_relationship_composition" and any(r.get("type") == "PartyMembershipEpisode" for r in refs.values()) and any(r.get("selector", {}).get("kind") == "currentTerm" for r in refs.values())
    if current_party:
        conditions.append(f"Both the parliamentary membership and party-affiliation periods must independently contain {as_of}; overlap alone is not enough.")
    if family == "member_relationship_composition" and {"seanad_term", "dail_term"}.issubset(refs):
        if refs["dail_term"].get("selector", {}).get("kind") == "currentTerm":
            conditions.append("Membership in both selected terms is required, not simultaneous or current service in both Houses.")
        else:
            conditions.append(f"The Seanad membership must contain {as_of}. The Dáil membership must have a finite end strictly before that same Seanad membership starts.")
    if (family == "member_relationship_composition" and not current_party
            and any(r.get("selector", {}).get("kind") == "currentTerm" for r in refs.values())
            and not plan.get("constraints") and "seanad_term" not in refs):
        conditions.append("This is term-wide membership; service on the reference date is not required.")
    assumptions = []
    evidence = plan.get("interpretation")
    if evidence:
        assumptions.append(f"Present-time default applied: no time was specified; interpreted as current at configured asOf {evidence.get('date', as_of)}.")
    elif question and plan.get("asOf"):
        note = current_scope_explanation(question, plan, date.fromisoformat(plan["asOf"]))
        if note:
            assumptions.append(note)
    target = TYPES.get(refs.get(answer.get("referent"), {}).get("type"), "requested result")
    kind = answer.get("kind")
    projection = PROJECTIONS.get(answer.get("projection", family)) if kind == "family_result" else None
    if projection:
        projection = projection.format(as_of=as_of)
    if kind == "family_result" and not projection:
        gaps.append("This family-specific result projection has no plain-language translation; consult the technical query plan.")
    construction = []
    distinct = "distinct " if answer.get("distinctBy") == "identity" else ""
    if kind == "count":
        answer_text = f"A count of {distinct}matching {target} identities."
    elif kind == "boolean":
        answer_text = "A yes-or-no result based on the queried local records."
    elif kind == "entities":
        answer_text = f"A list of {distinct}matching {target} identities."
    elif kind == "values":
        answer_text = f"Recorded values for each matching {target}."
    else:
        answer_text = projection or "The result shape is not available from this plan."
    construction.append(answer_text)
    if answer.get("distinctBy") == "identity":
        construction.append("Repeated matches are combined by exact identity, not by matching names.")
    if answer.get("display"):
        display = {"name": "name", "label": "label", "date": "date", "officialLink": "official record link", "start": "start date", "end": "end date", "englishTitle": "English title", "billNumber": "Bill number", "year": "year"}
        construction.append("Requested display fields: " + ", ".join(display.get(v, "additional field (see technical plan)") for v in answer["display"]) + ".")
    if answer.get("details") or answer.get("preserveEvidence") or answer.get("preserveGaps"):
        construction.append("The plan requests separate supporting records where available; actual evidence is described under Executed.")
    names = [e["label"] for e in entities]
    action = "Count" if kind == "count" else "Check for" if kind == "boolean" else "Find"
    summary = f"{action} matching {target} records."
    if names:
        summary += " The selection concerns " + ", ".join(names) + "."
    if projection:
        summary = projection
    else:
        summary = _relationship_summary(plan, labels) or summary
    return {"summary": summary, "target": projection or f"{action} matching {target} records.",
            "entities": entities, "relationships": relationships, "conditions": conditions,
            "assumptions": assumptions, "construction": construction,
            "gaps": list(dict.fromkeys(gaps)), "answer_text": answer_text,
            "unresolved": any(r.get("resolution") in {"ambiguous", "not_found", "unresolved", "source_data_unavailable", "unsupported_mapping"} for r in refs.values())}


def explain_execution(*, attempted, result, status=None, error=None, plan=None):
    """Use explicit attempt evidence; SPARQL availability is never an attempt."""
    if not attempted:
        return {"status": "Execution was not reached.", "summary": "No execution outcome is available."}
    if status in {"execution_failure", "query_execution_failed"}:
        return {"status": "Execution was attempted but failed.", "summary": error or "No successful result is available."}
    if result is None:
        return {"status": "Execution was attempted; no result is available.", "summary": "Successful execution is not established by the available evidence."}
    state = "Execution was attempted and completed successfully." if not error else "Execution was attempted; results were returned with qualifications."
    if result.kind == "ask":
        summary = f"The returned result is {'true (Yes)' if result.boolean is True else 'false (No)' if result.boolean is False else 'not a supplied boolean value'}. This applies to the queried records, not all historical evidence."
    elif not result.rows:
        summary = "No matching records found in the queried data. This does not prove that no historical matches exist."
    elif (plan and (plan.get("answer", {}).get("kind") == "count"
                   or plan.get("answer", {}).get("kind") == "family_result"
                   and plan.get("family") in {"term_count", "committee_count"})
          and len(result.rows) == 1 and len(result.rows[0]) == 1):
        summary = f"Returned count: {result.rows[0][0]}. This counts matching local identities, not a certified complete historical total."
    else:
        summary = f"Returned {len(result.rows)} result {'row' if len(result.rows) == 1 else 'rows'}. Rows are not necessarily distinct people or a complete historical answer."
    return {"status": state, "summary": summary}


def explain_validated_composition(request: dict, report: dict, *, question: str = "") -> dict:
    """Present an admitted composition request and only its recorded query evidence."""
    roles = {"R": "represent", "P": "belong to", "K": "serve on"}
    kinds = {"R": "Constituency", "P": "Political party", "K": "Committee"}
    mentioned = {"R": "Constituency mentioned", "P": "Party mentioned", "K": "Committee mentioned"}
    selections = request.get("requiredSelections", [])
    entities = []
    named = {}
    for selection in selections:
        role = selection.get("role")
        target = selection.get("constituency", selection.get("affiliation", selection.get("committee", {})))
        label = target.get("mention", "the requested entity") if isinstance(target, dict) else str(target)
        named[role] = label
        entities.append({"kind": (kinds if report.get("status") == "answer" else mentioned).get(role, "Entity"),
                         "label": label})
    answer = request.get("answer", {})
    subject = "TDs" if "R" in named else "Members"
    relationship_text = " and ".join(f"{roles[role]} {named[role]}" for role in ("R", "P", "K") if role in named)
    verb = "Count" if answer.get("shape") == "count" else "Find"
    projection = (f"A count of distinct matching {subject}." if answer.get("shape") == "count"
                  else f"A list of matching {subject}.")
    summary = f"{verb} {subject} who {relationship_text}."
    as_of = request.get("asOf", "the configured reference date")
    conditions = [f"The requested relationships must belong to the same person and be current on {as_of}."]
    evidence_links = [phrase for role, phrase in (
        ("R", f"representation for {named.get('R')}"),
        ("P", f"party membership with {named.get('P')}"),
        ("K", f"committee membership of {named.get('K')}"),
    ) if role in named]
    answer_relationship = (f"The returned {subject} have recorded "
                          + " and ".join(evidence_links) + f" as of {as_of}.")
    ledger = report.get("ledger", [])
    queries = [entry.get("query") for entry in ledger if isinstance(entry, dict) and entry.get("query")]
    exact_bindings = request.get("exactSharedBindings", [])
    technical_requirements = ["Exact identity bindings: " + "; ".join(exact_bindings)] if exact_bindings else []
    temporal_roles = request.get("currentAtRoles", [])
    if temporal_roles:
        technical_requirements.append("Independently checked current-date roles: " + "; ".join(temporal_roles))
    return {"summary": summary, "entities": entities, "relationships": [], "conditions": conditions,
            "assumptions": [], "answer_text": projection, "target": projection,
            "construction": [], "gaps": [], "unresolved": False, "queries": queries,
            "compiled_summary": (f"The application prepared a query to find {subject.lower()} who {relationship_text}. "
                                 "It matches the results to the same person and checks the recorded dates for the requested current status."),
            "answer_relationship": answer_relationship,
            "technical_requirements": technical_requirements,
            "specification": "This describes the validated request; the individual SELECT queries below are the requests recorded during execution."}


def explain_composition_execution(*, attempted: bool, request: dict, report: dict | None,
                                  result=None, status=None, error=None) -> dict:
    """Describe only the composition report and execution evidence actually supplied."""
    if not attempted:
        return {"status": "The query was not run.", "summary": "No execution result is available."}
    if status in {"execution_failure", "query_execution_failed"} or error:
        return {"status": "The query could not be completed.",
                "summary": error or "Execution failed; no answer is available."}
    if not report or result is None:
        return {"status": "The query ran, but no answer was returned.",
                "summary": (report or {}).get("error", "The available evidence does not establish a successful result.")}
    if report.get("status") != "answer":
        return {"status": "The query ran, but the available records did not support an answer.",
                "summary": report.get("error", "No complete matching result could be established.")}
    shape = request.get("answer", {}).get("shape")
    subject = "TDs" if any(s.get("role") == "R" for s in request.get("requiredSelections", [])) else "Members"
    if shape == "count":
        count = report.get("answer", {}).get("distinctCount")
        return {"status": "The query completed successfully.",
                "summary": f"The records returned a count of {count} distinct {subject}."}
    count = len(report.get("answer", {}).get("members", []))
    return {"status": "The query completed successfully.",
            "summary": f"The records returned {count} matching {subject}; the readable answer is shown above."}


def composition_answer_display(*, request: dict, report: dict, explanation: dict,
                                result=None, status=None, error=None) -> dict:
    """Shared, user-facing answer fields and exact feedback text for /ask compositions."""
    qualification = "These results reflect locally recorded evidence; the available records may not be complete."
    answerable = (report.get("status") == "answer" and result is not None and not error
                  and status not in {"execution_failure", "query_execution_failed"})
    if not answerable:
        refusal = error or report.get("error") or "No answer was established from the available records."
        return {"answerable": False, "actual": str(refusal)}

    is_td_answer = any(selection.get("role") == "R"
                       for selection in request.get("requiredSelections", []))
    noun = "TD" if is_td_answer else "Member"
    if request.get("answer", {}).get("shape") == "count":
        count = report.get("answer", {}).get("distinctCount")
        count_label = f"{count} matching {noun if count == 1 else noun + 's'}"
        names = ()
        answer_lines = [count_label]
    else:
        count_label = None
        names = tuple(sorted(report.get("names", {}).values()))
        answer_lines = list(names)

    relationship = explanation["answer_relationship"]
    actual = "\n".join(("Answer", *answer_lines, relationship, qualification))
    return {"answerable": True, "count_label": count_label, "names": names,
            "relationship": relationship, "qualification": qualification,
            "actual": actual}
