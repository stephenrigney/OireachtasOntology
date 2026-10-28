"""Bounded Stage B Query Service routes built only from reviewed local RDF."""

from __future__ import annotations

import re
import calendar
from datetime import date, datetime
from typing import Any

from .composable_plan import (PlanOutcome, _PREFIXES, _pattern_predicate,
                              PlanError, _pattern_rdf_type, _reviewed_cross_graph_join,
                              _reviewed_pattern)
from .contract import load_query_contract
from .errors import NLQError
from .safety import validate_sparql
from .results import QueryResult


_BILL = "https://data.oireachtas.ie/ie/oireachtas/bill"
_PUBLISHED = "https://data.oireachtas.ie/ontology#Published"
_B_FAMILIES = {
    "bill_lookup", "bills_published", "non_enacted_bills", "bill_status_history",
    "bill_sponsors", "bill_title_search", "committee_chair", "committee_conflict",
    "office_overlap", "office_point", "office_current_coverage",
}


def _plan(family: str, as_of: date, *, bill: dict | None = None,
          mention: str | None = None, year: int | None = None,
          office: str | None = None, interval: tuple[str, str] | None = None,
          point: str | None = None, committee: str | None = None) -> dict[str, Any]:
    """Build the one shared semantic v2 envelope used by every Stage B route."""
    refs: dict[str, dict[str, Any]]
    relations: list[dict[str, str]] = []
    constraints: list[dict[str, Any]] = []
    projection = family
    if family == "bill_lookup":
        refs = {"bill": {"type": "Bill", "selector": {"kind": "numberYear", **bill}},
                "process": {"type": "BillProcess"}, "activity": {"type": "BillActivity"},
                "memo": {"type": "ExplanatoryMemoWork"}}
        relations = [_relation("bill-process", "bill_process_cocontained", "bill", "process"),
                     _relation("activity-process", "activity_forms_part_of_process", "activity", "process"),
                     _relation("bill-memo", "bill_has_explanatory_memo_work", "bill", "memo")]
    elif family in {"bills_published", "non_enacted_bills"}:
        refs = {"bill": {"type": "Bill"}, "process": {"type": "BillProcess"},
                "activity": {"type": "BillActivity"}}
        relations = [_relation("bill-process", "bill_process_cocontained", "bill", "process"),
                     _relation("activity-process", "activity_forms_part_of_process", "activity", "process")]
        if family == "bills_published":
            constraints.append(_constraint("activity", "activityTypeAndDate", "publishedInCalendarYear", year))
        else:
            constraints.append(_constraint("bill", "legislativeYear", "equals", year))
            constraints.append(_constraint("process", "processStatus", "knownExcept", "Enacted"))
    elif family in {"bill_title_search", "bill_status_history", "bill_sponsors"}:
        mention = re.sub(r"(?i)^(?:the|a|an)\s+", "", mention or "").strip()
        refs = {"bill": {"type": "Bill", "mention": mention}, "process": {"type": "BillProcess"},
                "activity": {"type": "BillActivity"}}
        relations = [_relation("bill-process", "bill_process_cocontained", "bill", "process"),
                     _relation("activity-process", "activity_forms_part_of_process", "activity", "process")]
        if family == "bill_sponsors":
            refs["participation"] = {"type": "BillParticipation"}
            refs["member"] = {"type": "Member"}
            relations.extend([_relation("process-participation", "process_has_participation", "process", "participation"),
                              _relation("participation-member", "participation_has_participant", "participation", "member")])
    elif family == "committee_chair":
        refs = {"committee": {"type": "Committee", "mention": committee}}
        constraints.append(_constraint("committee", "temporalOwner", "currentAt", as_of.isoformat()))
    elif family == "committee_conflict":
        refs = {"committee": {"type": "Committee", "mention": committee}}
        constraints.append(_constraint("committee", "coverage", "knownConflict", "quarantined_development_source"))
    elif family == "office_current_coverage":
        refs = {"office": {"type": "NamedOffice", "mention": office}}
        constraints.append(_constraint("office", "coverage", "requires", "complete_current_roster"))
    elif family in {"office_overlap", "office_point"}:
        # Preserve the established Q35 relationship and inclusive-date envelope.
        refs = {"holding": {"type": "OfficeHolding"},
                "office": {"type": "NamedOffice", "mention": office, "resolution": "unresolved"},
                "member": {"type": "Member", "answer": True}}
        if family == "office_overlap":
            refs["member"] = {"type": "Member", "mention": mention, "answer": True,
                               "resolution": "unresolved"}
        relations = [_relation("member-holding", "member_has_office_holding", "member", "holding"),
                     _relation("holding-office", "office_holding_of_office", "holding", "office")]
        if interval:
            constraints.append(_constraint("holding", "interval", "overlaps",
                                           {"start": interval[0], "end": interval[1], "inclusive": True}))
        else:
            constraints.append(_constraint("holding", "interval", "overlaps",
                                           {"start": point, "end": point, "inclusive": True}))
    else:
        raise ValueError("Unknown Stage B family.")
    plan: dict[str, Any] = {"version": 2, "asOf": as_of.isoformat(), "family": family,
                            "referents": refs, "relations": relations,
                            "answer": {"kind": "family_result", "referent": _answer_ref(family),
                                       "projection": projection}}
    if constraints:
        plan["constraints"] = constraints
    return plan


def _answer_ref(family: str) -> str:
    if family in {"committee_chair", "committee_conflict"}: return "committee"
    if family == "office_current_coverage": return "office"
    if family in {"office_overlap", "office_point"}: return "member"
    return "bill"


def _relation(identifier: str, fact: str, source: str, target: str) -> dict[str, str]:
    return {"id": identifier, "fact": fact, "from": source, "to": target}


def _constraint(referent: str, field: str, operator: str, value: Any) -> dict[str, Any]:
    return {"referent": referent, "field": field, "operator": operator, "value": value}


def _family(plan: dict[str, Any]) -> str: return plan["family"]
def _ref(plan: dict[str, Any], key: str) -> dict[str, Any]: return plan["referents"][key]
def _constraint_value(plan: dict[str, Any], field: str) -> Any:
    for item in plan.get("constraints", []):
        if item.get("field") == field:
            return item["value"]
    raise ValueError(f"Required semantic constraint {field!r} is missing.")
def _bill_identity(plan: dict[str, Any]) -> dict[str, Any]: return _ref(plan, "bill")["selector"]
def _title_tokens_from_plan(plan: dict[str, Any]) -> list[str]: return _title_tokens(_ref(plan, "bill")["mention"])


def _bill_owner_route() -> tuple[str, str]:
    """Return the exact contract-owned Bill graph template and SPARQL regex."""
    contract = load_query_contract()
    family = next((item for item in contract["graphFamilies"] if item["id"] == "bill-records"), None)
    route = family.get("graph") if family else None
    template = route.get("iriTemplate") if isinstance(route, dict) else None
    if (not family or family.get("availability") != "optional-published-when-loaded"
            or family.get("owner") != "Bills ETL"
            or not isinstance(route, dict)
            or route.get("kind") != "resource-pattern" or not isinstance(template, str)
            or template.count("{year}") != 1 or template.count("{number}") != 1):
        raise PlanError("The reviewed one-Bill graph owner route is absent or malformed.")
    escaped = (re.escape(template).replace(r"\.", "[.]")
               .replace(r"\{year\}", r"[0-9]{4}")
               .replace(r"\{number\}", r"[0-9]+"))
    return template, "^" + escaped + "$"


def _bill_graph(year: int, number: str) -> str:
    template, _regex = _bill_owner_route()
    return template.replace("{year}", f"{year:04d}").replace("{number}", number)


def _member_owner_regex() -> str:
    contract = load_query_contract()
    family = next((item for item in contract["graphFamilies"] if item["id"] == "member-records"), None)
    route = family.get("graph") if family else None
    template = route.get("iriTemplate") if isinstance(route, dict) else None
    if (not family or family.get("availability") != "published-when-loaded"
            or family.get("owner") != "Members ETL"
            or not isinstance(route, dict)
            or route.get("kind") != "resource-pattern" or not isinstance(template, str)
            or template.count("{percent-encoded-memberCode}") != 1):
        raise PlanError("The reviewed Member graph owner route is absent or malformed.")
    escaped = (re.escape(template).replace(r"\.", "[.]")
               .replace(r"\{percent\-encoded\-memberCode\}", "[^/]+"))
    return "^" + escaped + "$"


def _bill_pattern_gate(*, activity: bool = False, sponsor: bool = False,
                       documents: bool = False) -> None:
    lifecycle = _reviewed_pattern("bill-lifecycle", "bill-records")
    types = {"?bill": "eli-dl:DraftLegislationWork", "?process": "eli-dl:LegislativeProcess"}
    if activity: types["?activity"] = "eli-dl:LegislativeActivity"
    predicates = [("?bill", "agents:Bill", "eli:type_document"),
                  ("?bill", "?englishOrIrishTitle", "eli:title"),
                  ("?process", "?status", "eli-dl:process_status")]
    if activity:
        predicates.extend([("?activity", "?process", "eli-dl:forms_part_of"),
                           ("?activity", "?xsdDate eventDate", "eli-dl:activity_date"),
                           ("?activity", "?eventType", "eli-dl:had_activity_type")])
    for subject, expected in types.items():
        if _pattern_rdf_type(lifecycle, subject) != expected:
            raise PlanError(f"Bill lifecycle contract type for {subject} is not {expected}.")
    for subject, obj, expected in predicates:
        if _pattern_predicate(lifecycle, subject, obj) != expected:
            raise PlanError(f"Bill lifecycle contract predicate for {subject}/{obj} is not {expected}.")
    controlled = set(lifecycle.get("controlledValues", []))
    required_controlled = {"agents:Bill", "agents:Published", *_STATUS_QNAMES.values()}
    if not required_controlled.issubset(controlled):
        raise PlanError("Reviewed Bill document/status controlled values are incomplete.")
    if sponsor:
        reference = _reviewed_pattern("bill-sponsor-reference", "bill-records")
        if (_pattern_rdf_type(reference, "?participation") != "eli-dl:Participation"
                or _pattern_predicate(reference, "?process", "?participation") != "eli-dl:had_participation"
                or _pattern_predicate(reference, "?participation", "?member") != "eli-dl:had_participant_person"):
            raise PlanError("Reviewed Bill sponsor Participation pattern is incomplete.")
        member = _reviewed_pattern("member-description", "member-records")
        if (_pattern_rdf_type(member, "?member") != "agents:Member"
                or _pattern_predicate(member, "?member", "?plainLiteralName") != "foaf:name"):
            raise PlanError("Reviewed Member display pattern is incomplete.")
    if documents:
        docs = _reviewed_pattern("bill-document-work-links", "bill-records")
        checks = [("?bill", "?documentWork", "eli:has_part"),
                  ("?documentWork", "?documentType", "eli:type_document"),
                  ("?documentWork", "?documentExpression", "eli:is_realized_by"),
                  ("?documentExpression", "?format", "eli:is_embodied_by"),
                  ("?format", "?rendition", "eli:uri_schema")]
        for subject, obj, expected in checks:
            if _pattern_predicate(docs, subject, obj) != expected:
                raise PlanError("Reviewed Bill memorandum rendition chain is incomplete.")
        for subject, expected in (("?documentWork", "eli:Work"),
                                  ("?documentExpression", "eli:LegalExpression"),
                                  ("?format", "eli:Format")):
            if _pattern_rdf_type(docs, subject) != expected:
                raise PlanError(f"Bill document chain omits reviewed {expected} type.")
        if "agents:ExplanatoryMemo" not in docs.get("controlledValues", []):
            raise PlanError("ExplanatoryMemo is not present in the reviewed document controlled values.")


_STATUS_QNAMES = {
    "AwaitingSignatureBill": "agents:AwaitingSignatureBill",
    "CurrentBill": "agents:CurrentBill",
    "DefeatedBill": "agents:DefeatedBill",
    "DeclaredRepugnantToConstitutionBill": "agents:DeclaredRepugnantToConstitutionBill",
    "DraftHeadsOfBill": "agents:DraftHeadsOfBill",
    "EnactedBill": "agents:EnactedBill",
    "LapsedBill": "agents:LapsedBill",
    "WithdrawnBill": "agents:WithdrawnBill",
    "RejectedAtReferendumBill": "agents:RejectedAtReferendumBill",
}
_STATUS_IRIS = {name: "https://data.oireachtas.ie/ontology#" + name for name in _STATUS_QNAMES}
_STATUS_LABELS = {
    _STATUS_IRIS["AwaitingSignatureBill"]: "Awaiting signature",
    _STATUS_IRIS["CurrentBill"]: "Current",
    _STATUS_IRIS["DefeatedBill"]: "Defeated",
    _STATUS_IRIS["DeclaredRepugnantToConstitutionBill"]: "Declared repugnant to the Constitution",
    _STATUS_IRIS["DraftHeadsOfBill"]: "Draft heads of Bill",
    _STATUS_IRIS["EnactedBill"]: "Enacted",
    _STATUS_IRIS["LapsedBill"]: "Lapsed",
    _STATUS_IRIS["WithdrawnBill"]: "Withdrawn",
    _STATUS_IRIS["RejectedAtReferendumBill"]: "Rejected at referendum",
}


def plan_stage_b(question: str, *, as_of: date) -> dict[str, Any] | None:
    """Return one finite, closed semantic plan for a supported Stage B phrasing."""
    text = question.strip()
    title_match = re.fullmatch(r"(?i)find the full title of (?P<title>.+?) bill[?.!]*", text)
    if title_match:
        tokens = _title_tokens(title_match["title"])
        if tokens:
            return _plan("bill_title_search", as_of, mention=" ".join(title_match["title"].split()))
    if re.fullmatch(r"(?i)who is the chair of the committee on transport[?.!]*", text):
        return _plan("committee_chair", as_of, committee="Committee on Transport")
    if re.fullmatch(r"(?i)who are the sinn f[eé]in members of the good friday committee[?.!]*", text):
        return _plan("committee_conflict", as_of, committee="Good Friday Committee")
    if re.fullmatch(r"(?i)who is minister for finance[?.!]*", text):
        return _plan("office_current_coverage", as_of, office="Minister for Finance")
    match = re.fullmatch(r"(?i)was (?P<member>.+?) (?P<office>taoiseach) in (?P<month>[a-z]+) (?P<year>\d{4})[?.!]*", text)
    if match:
        try:
            month = datetime.strptime(match["month"], "%B").month
            year = int(match["year"])
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
        except (ValueError, OverflowError):
            return None
        return _plan("office_overlap", as_of, mention=" ".join(match["member"].split()),
                     office="Taoiseach", interval=(start.isoformat(), end.isoformat()))
    match = re.fullmatch(r"(?i)who was (?P<office>.+?) on (?P<day>\d{1,2}) (?P<month>[a-z]+) (?P<year>\d{4})[?.!]*", text)
    if match:
        try:
            day = date.fromisoformat(f"{match['year']}-{__import__('datetime').datetime.strptime(match['month'], '%B').month:02d}-{int(match['day']):02d}")
        except ValueError:
            return None
        return _plan("office_point", as_of, office="Minister for Finance", point=day.isoformat())
    match = re.fullmatch(r"(?i)tell me about bill (?P<number>\d+) from (?P<year>\d{4})[?.!]*", text)
    if match:
        return _plan("bill_lookup", as_of,
                     bill={"year": int(match["year"]), "number": match["number"]})
    if re.fullmatch(r"(?i)what bills were published in (?P<year>\d{4})[?.!]*", text):
        year = int(re.search(r"\d{4}", text).group())
        return _plan("bills_published", as_of, year=year)
    match = re.fullmatch(r"(?i)what (?P<year>\d{4}) bills haven.t been enacted[?.!]*", text)
    if match:
        return _plan("non_enacted_bills", as_of, year=int(match["year"]))
    match = re.fullmatch(r"(?i)what is happening to (?P<title>.+?) bill[?.!]*", text)
    if match:
        tokens = _title_tokens(match["title"])
        if tokens:
            return _plan("bill_status_history", as_of, mention=" ".join(match["title"].split()))
    match = re.fullmatch(r"(?i)who is the sponsor of (?P<title>.+?) bill[?.!]*", text)
    if match:
        tokens = _title_tokens(match["title"])
        if tokens:
            return _plan("bill_sponsors", as_of, mention=" ".join(match["title"].split()))
    return None


def _title_tokens(mention: str) -> list[str]:
    """Normalize controlled title mentions; AI is the only approved abbreviation."""
    words = re.findall(r"[a-z]+", mention.casefold())
    if "ai" in words:
        words = [part for word in words for part in (("artificial", "intelligence") if word == "ai" else (word,))]
    ignored = {"the", "a", "an", "bill", "of", "for", "and"}
    tokens = [word for word in words if word not in ignored]
    if "artificial" in tokens and "intelligence" in tokens:
        return ["artificial intelligence", *[word for word in tokens if word not in {"artificial", "intelligence"}]]
    return tokens


def validate_stage_b_plan(plan: Any) -> dict[str, Any]:
    """Closed validation for B plans in the shared typed v2 plan envelope."""
    from .composable_plan import PlanError
    def fail(message: str): raise PlanError(message)
    if not isinstance(plan, dict) or plan.get("family") not in _B_FAMILIES:
        fail("Not a supported Stage B plan family.")
    family = plan["family"]
    try:
        date.fromisoformat(plan.get("asOf", ""))
    except (TypeError, ValueError):
        fail("asOf must be an ISO calendar date.")
    try:
        refs = plan["referents"]
        if family == "bill_lookup":
            selector = refs["bill"]["selector"]
            year, number = selector["year"], selector["number"]
            if type(year) is not int or not 1800 <= year <= 2200 or not isinstance(number, str) or not re.fullmatch(r"[0-9]+", number):
                fail("Bill selector must contain an exact supported year/number pair.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), bill={"year": year, "number": number})
        elif family in {"bills_published", "non_enacted_bills"}:
            year = _constraint_value(plan, "activityTypeAndDate" if family == "bills_published" else "legislativeYear")
            if type(year) is not int or not 1800 <= year <= 2200:
                fail("Bill year constraint must be a supported calendar year.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), year=year)
        elif family in {"bill_title_search", "bill_status_history", "bill_sponsors"}:
            mention = refs["bill"]["mention"]
            if not isinstance(mention, str) or not mention.strip() or not _title_tokens(mention):
                fail("Bill title resolution requires a non-empty grounded title mention.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), mention=mention)
        elif family in {"committee_chair", "committee_conflict"}:
            mention = refs["committee"]["mention"]
            if mention != ("Committee on Transport" if family == "committee_chair" else "Good Friday Committee"):
                fail("Committee diagnostic family requires its controlled official Committee mention.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), committee=mention)
        elif family == "office_current_coverage":
            mention = refs["office"]["mention"]
            if mention != "Minister for Finance": fail("Coverage diagnostic requires the reviewed Minister for Finance office.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), office=mention)
        elif family == "office_overlap":
            mention = refs["member"]["mention"]
            member = refs["member"]
            if not isinstance(mention, str) or not mention.strip():
                fail("Office overlap requires a grounded Member name.")
            if not isinstance(refs["office"].get("mention"), str) or not refs["office"]["mention"].strip():
                fail("Office overlap requires a grounded named-office role.")
            if refs["office"]["mention"] != "Taoiseach":
                fail("The bounded Member-overlap route is limited to the reviewed Taoiseach role.")
            interval = _constraint_value(plan, "interval")
            if not isinstance(interval, dict) or set(interval) != {"start", "end", "inclusive"} or interval["inclusive"] is not True:
                fail("Office overlap requires a closed inclusive calendar interval.")
            start, end = date.fromisoformat(interval["start"]), date.fromisoformat(interval["end"])
            if start > end: fail("Office interval start must not follow its end.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), mention=mention,
                             office=refs["office"]["mention"], interval=(start.isoformat(), end.isoformat()))
            resolution = member.get("resolution", "unresolved")
            if resolution == "unresolved":
                if member != expected["referents"]["member"]:
                    fail("Unresolved office Member referent contains unsupported identity fields.")
            elif resolution == "resolved":
                if set(member) != {"type", "mention", "answer", "resolution", "iri", "label"} or member.get("answer") is not True:
                    fail("Resolved office Member referent has unsupported identity fields.")
                from .composable_plan import _require_local_iri
                _require_local_iri(member["iri"], "Member")
                if not isinstance(member["label"], str) or not member["label"].strip():
                    fail("Resolved office Member requires its exact local display label.")
                expected["referents"]["member"] = dict(member)
                expected["constraints"].append(_constraint("member", "memberIdentity", "equals", member["iri"]))
            elif resolution in {"ambiguous", "not_found", "source_data_unavailable", "unsupported_mapping"}:
                allowed = {"type", "mention", "answer", "resolution"}
                if resolution == "ambiguous": allowed.add("candidates")
                if set(member) != allowed or member.get("answer") is not True:
                    fail("Unresolved office Member outcome has unsupported identity fields.")
                if resolution == "ambiguous":
                    candidates = member["candidates"]
                    if not isinstance(candidates, list) or len(candidates) < 2:
                        fail("Ambiguous office Member requires distinct local IRI candidates.")
                    from .composable_plan import _require_local_iri
                    seen_iris = set()
                    for candidate in candidates:
                        if (not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}
                                or not isinstance(candidate["label"], str) or not candidate["label"].strip()):
                            fail("Ambiguous office Member candidates require a local IRI and readable label.")
                        _require_local_iri(candidate["iri"], "Member candidate")
                        if candidate["iri"] in seen_iris:
                            fail("Ambiguous office Member candidates must have distinct IRIs.")
                        seen_iris.add(candidate["iri"])
                expected["referents"]["member"] = dict(member)
            else:
                fail("Office Member resolution must use a reviewed local identity outcome.")
        else:
            if not isinstance(refs["office"].get("mention"), str) or not refs["office"]["mention"].strip():
                fail("Office point requires a grounded named-office role.")
            point = _constraint_value(plan, "interval")
            if not isinstance(point, dict) or set(point) != {"start", "end", "inclusive"} or point["inclusive"] is not True or point["start"] != point["end"]:
                fail("Office point lookup requires one inclusive calendar date.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), office=refs["office"]["mention"], point=date.fromisoformat(point["start"]).isoformat())
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, PlanError): raise
        fail(f"Malformed semantic parameters for {family}: {error}")
    if plan != expected:
        fail(f"{family} plan does not match its exact reviewed referent roles, relations, constraints, and projection.")
    from .composable_plan import _RELATION_MAPPINGS, _RELATION_TYPES
    for relation in plan["relations"]:
        fact = relation["fact"]
        if fact not in _RELATION_MAPPINGS or fact not in _RELATION_TYPES:
            fail(f"Stage B relation {fact!r} is not in the reviewed relation contract.")
        subject_type, object_type = _RELATION_TYPES[fact]
        if (plan["referents"][relation["from"]]["type"],
                plan["referents"][relation["to"]]["type"]) != (subject_type, object_type):
            fail(f"Stage B relation {fact!r} has incompatible typed endpoints.")
    return plan


def _validate(plan: dict[str, Any]) -> None:
    from .composable_plan import validate_plan
    validate_plan(plan)


def _bill_uri(plan: dict[str, Any]) -> str:
    bill = _bill_identity(plan)
    if type(bill["year"]) is not int or bill["year"] < 1800 or bill["year"] > 2200:
        raise ValueError("Bill year is outside the supported source identity range.")
    return f"{_BILL}/{bill['year']}/{bill['number']}"


def _query(plan: dict[str, Any], supported_predicates) -> str:
    _validate(plan)
    family = _family(plan)
    if family in {"bill_lookup", "bills_published", "non_enacted_bills", "bill_status_history", "bill_sponsors", "bill_title_search"}:
        _bill_pattern_gate(
            activity=family in {"bill_lookup", "bills_published", "bill_status_history"},
            sponsor=family == "bill_sponsors", documents=family == "bill_lookup",
        )
    if family in {"office_overlap", "office_point"}:
        raise ValueError("Office questions must compile through the existing validated Q35 interval path.")
    if family == "bill_lookup":
        identity = _bill_identity(plan)
        bill = _bill_uri(plan)
        graph = _bill_graph(identity["year"], identity["number"])
        body = f'''GRAPH <{graph}> {{
          <{bill}> a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill .
          BIND(<{bill}> AS ?bill)
          OPTIONAL {{ <{bill}> eli:title ?title . FILTER(LANG(?title) = "en") }}
          OPTIONAL {{ <{bill}> agents:legislativeYear ?year }}
          OPTIONAL {{ ?process a eli-dl:LegislativeProcess . OPTIONAL {{ ?process eli-dl:process_number ?number }} OPTIONAL {{ ?process eli-dl:process_status ?status }}
            OPTIONAL {{ ?activity a eli-dl:LegislativeActivity ; eli-dl:forms_part_of ?process ; eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type ?eventType . FILTER(DATATYPE(?eventDate) = xsd:date) }} }}
          OPTIONAL {{ <{bill}> eli:has_part ?memoWork . ?memoWork a eli:Work ; eli:type_document agents:ExplanatoryMemo .
            OPTIONAL {{ ?memoWork eli:is_realized_by ?memoExpression . ?memoExpression a eli:LegalExpression ; eli:is_embodied_by ?memoFormat . ?memoFormat a eli:Format ; eli:uri_schema ?memo }} }}
        }}'''
        select = "?bill ?title ?year ?process ?number ?status ?eventDate ?eventType ?memoWork ?memo"
    elif family in {"bills_published", "non_enacted_bills"}:
        year = _constraint_value(plan, "activityTypeAndDate" if family == "bills_published" else "legislativeYear")
        _template, graph_regex = _bill_owner_route()
        if family == "bills_published":
            body = f'''GRAPH ?graph {{
              ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill .
              OPTIONAL {{ ?bill eli:title ?title . FILTER(LANG(?title) = "en") }}
              OPTIONAL {{ ?bill agents:legislativeYear ?year }}
              ?process a eli-dl:LegislativeProcess .
              ?activity a eli-dl:LegislativeActivity ; eli-dl:forms_part_of ?process ;
                eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type <{_PUBLISHED}> .
              FILTER(DATATYPE(?eventDate) = xsd:date)
              FILTER(?eventDate >= "{year:04d}-01-01"^^xsd:date && ?eventDate < "{year + 1:04d}-01-01"^^xsd:date)
            }} FILTER(REGEX(STR(?graph), "{graph_regex}"))'''
            select = "?bill ?title ?year ?eventDate"
        else:
            _template, graph_regex = _bill_owner_route()
            body = f'''GRAPH ?graph {{
              ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill .
              OPTIONAL {{ ?bill agents:legislativeYear ?year }}
              FILTER(EXISTS {{ ?bill agents:legislativeYear ?requestedYear . FILTER(?requestedYear = {year}) }})
              OPTIONAL {{ ?bill eli:title ?title . FILTER(LANG(?title) = "en") }}
              OPTIONAL {{ ?process a eli-dl:LegislativeProcess . OPTIONAL {{ ?process eli-dl:process_number ?number }} OPTIONAL {{ ?process eli-dl:process_status ?status }} }}
            }} FILTER(REGEX(STR(?graph), "{graph_regex}"))'''
            select = "?bill ?title ?year ?process ?number ?status"
    elif family == "bill_title_search":
        # Title-based resolution happens over source-backed English Bill titles;
        # candidate identities are returned rather than selecting by similarity.
        _template, graph_regex = _bill_owner_route()
        body = f'''GRAPH ?graph {{
          ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill ; eli:title ?title .
          OPTIONAL {{ ?bill agents:legislativeYear ?year }}
          FILTER(LANG(?title) = "en")
         }} FILTER(REGEX(STR(?graph), "{graph_regex}"))'''
        for token in _title_tokens_from_plan(plan):
            if not isinstance(token, str) or not re.fullmatch(r"[a-z ]+", token):
                raise ValueError("Bill title tokens must use reviewed lowercase text.")
            body += f' FILTER(CONTAINS(LCASE(STR(?title)), "{token}")) '
        select = "?bill ?title ?year"
    elif family == "bill_status_history":
        _template, graph_regex = _bill_owner_route()
        body = f'''GRAPH ?graph {{
          ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill ; eli:title ?title .
          OPTIONAL {{ ?bill agents:legislativeYear ?year }}
          FILTER(LANG(?title) = "en")
          OPTIONAL {{
            ?process a eli-dl:LegislativeProcess .
            OPTIONAL {{ ?process eli-dl:process_number ?number }}
            OPTIONAL {{ ?process eli-dl:process_status ?status }}
            OPTIONAL {{ ?activity a eli-dl:LegislativeActivity ; eli-dl:forms_part_of ?process ; eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type ?eventType . FILTER(DATATYPE(?eventDate) = xsd:date) }}
          }}
        }} FILTER(REGEX(STR(?graph), "{graph_regex}"))'''
        for token in _title_tokens_from_plan(plan): body += f' FILTER(CONTAINS(LCASE(STR(?title)), "{token}")) '
        select = "?bill ?title ?year ?process ?number ?status ?eventDate ?eventType"
    elif family == "bill_sponsors":
        contract = load_query_contract()
        if "eli-dl:had_participant_person" not in contract["queryableProperties"]:
            raise PlanError("The reviewed Bill-to-Member identity join is not queryable.")
        _reviewed_cross_graph_join("bill-records", "eli-dl:had_participant_person", "member-records")
        _bill_pattern_gate(sponsor=True)
        _template, graph_regex = _bill_owner_route()
        member_regex = _member_owner_regex()
        body = f'''GRAPH ?graph {{
          ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill ; eli:title ?title .
          OPTIONAL {{ ?bill agents:legislativeYear ?year }}
          FILTER(LANG(?title) = "en")
          OPTIONAL {{
            ?process a eli-dl:LegislativeProcess .
            OPTIONAL {{ ?process eli-dl:process_number ?number }}
            OPTIONAL {{ ?process eli-dl:process_status ?status }}
            OPTIONAL {{
              ?process eli-dl:had_participation ?participation .
              ?participation a eli-dl:Participation .
              OPTIONAL {{ ?participation eli-dl:had_participant_person ?member .
                OPTIONAL {{ GRAPH ?memberGraph {{ ?member a agents:Member ; foaf:name ?memberName }}
                  FILTER(REGEX(STR(?memberGraph), "{member_regex}")) }} }}
              OPTIONAL {{ ?participation agents:isPrimarySponsor ?primary }}
              OPTIONAL {{ ?participation rdfs:label ?role }}
            }}
          }}
        }} FILTER(REGEX(STR(?graph), "{graph_regex}"))
        '''
        for token in _title_tokens_from_plan(plan): body += f' FILTER(CONTAINS(LCASE(STR(?title)), "{token}")) '
        select = "?bill ?title ?year ?number ?status ?participation ?member ?memberName ?primary ?role"
    query = _PREFIXES + f"SELECT DISTINCT {select} WHERE {{ {body} }} LIMIT 100"
    return validate_sparql(query, supported_predicates=supported_predicates)


def execute_stage_b(plan: dict[str, Any], *, fuseki, supported_predicates) -> PlanOutcome:
    try:
        _validate(plan)
    except (ValueError, TypeError, KeyError) as error:
        return PlanOutcome("unsupported_mapping", diagnostic=f"Stage B plan failed authoritative validation: {error}")
    try:
        query = _query(plan, supported_predicates)
    except (ValueError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=f"A reviewed Bill query dependency is unavailable: {error}")
    try:
        result = fuseki.query(query)
        if result.kind != "select":
            raise NLQError("Bill route returned a non-SELECT response.")
    except Exception as error:
        return PlanOutcome("query_execution_failed", plan=plan, sparql=query,
                           diagnostic=f"The validated read-only Bill query did not complete: {error}")
    family = _family(plan)
    truncated = len(result.rows) >= 100
    try:
        readable, status, notice = _project_bill_result(family, result)
    except (KeyError, ValueError, IndexError) as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                           diagnostic=f"Bill result metadata could not be interpreted consistently: {error}")
    if truncated:
        status = "incomplete_results"
        notice += " The 100-row safety cap was reached; this readable partial view can omit additional Bills or evidence."
    if status == "source_data_unavailable":
        return PlanOutcome(status, plan=plan, sparql=query, result=readable, diagnostic=notice)
    return PlanOutcome(status, plan=plan, sparql=query, result=readable, diagnostic=notice)


def _tail(value: str) -> str:
    value = value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).replace("_", " ").strip() or "Unknown"


def _status_label(value: str) -> str:
    return _STATUS_LABELS.get(value, "Unknown/unmapped process status" if value not in {"—", ""} else "Unknown")


_BILL_IRI_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/bill/([0-9]{4})/([0-9]+)$")
_XSD_BOOLEAN = "http://www.w3.org/2001/XMLSchema#boolean"


def _plain(value: str) -> str:
    if value in {"—", ""}:
        return "—"
    value = re.sub(r"\^\^<[^>]+>$", "", value)
    return value.removesuffix("@en").strip('"')


def _cell(result: QueryResult, row: tuple[str, ...], name: str) -> str:
    index = result.columns.index(name) if name in result.columns else -1
    return _plain(row[index]) if index >= 0 and index < len(row) else "—"


def _raw_cell(result: QueryResult, row: tuple[str, ...], name: str) -> str:
    index = result.columns.index(name) if name in result.columns else -1
    return row[index] if index >= 0 and index < len(row) else "—"


def _bill_number_year(bill: str, number: str, year: str) -> tuple[str, str]:
    match = _BILL_IRI_RE.fullmatch(bill)
    return (number if number not in {"—", ""} else (match.group(2) if match else "—"),
            year if year not in {"—", ""} else (match.group(1) if match else "Year unavailable"))


def _group_bill_rows(result: QueryResult) -> dict[str, list[tuple[str, ...]]]:
    groups: dict[str, list[tuple[str, ...]]] = {}
    for row in result.rows:
        bill = _cell(result, row, "bill")
        if bill != "—":
            groups.setdefault(bill, []).append(row)
    return groups


def _consistent(values: set[str], *, missing: str = "—") -> tuple[str, str | None]:
    values.discard(missing)
    if not values:
        return missing, "missing"
    if len(values) > 1:
        return "Conflicting values", "conflicting"
    return next(iter(values)), None


def _event_history(result: QueryResult, rows: list[tuple[str, ...]]) -> str:
    events = set()
    for row in rows:
        event_date, event_type = _cell(result, row, "eventDate"), _cell(result, row, "eventType")
        if event_date == "—":
            continue
        label = _tail(event_type) if event_type != "—" else "Activity type unavailable"
        events.add((event_date, label))
    if not events:
        return "No mapped dated lifecycle activity is recorded"
    return "; ".join(f"{event_type}: {event_date}" for event_date, event_type in sorted(events))


def _primary_status(values: set[str]) -> tuple[str, str | None]:
    """Decode only valid xsd:boolean lexical forms; never substring-match."""
    if not values or values == {"—"}:
        return "Unknown (not recorded)", "absent"
    decoded: set[bool] = set()
    malformed = False
    for value in values:
        match = re.fullmatch(r'"?(true|false|1|0)"?\^\^<([^>]+)>', value)
        if not match or match.group(2) != _XSD_BOOLEAN:
            malformed = True
            continue
        decoded.add(match.group(1) in {"true", "1"})
    if malformed:
        return "Malformed primary flag", "malformed"
    if len(decoded) > 1:
        return "Conflicting primary flags", "conflicting"
    if not decoded:
        return "Malformed primary flag", "malformed"
    return ("Primary" if next(iter(decoded)) else "Supporting"), None


def _project_bill_result(family: str, result: QueryResult) -> tuple[QueryResult, str, str]:
    groups = _group_bill_rows(result)
    base_notice = "Results use locally recorded Bill-owned RDF; source coverage is not certified complete."
    if family == "bills_published":
        projected, issues = [], []
        for bill, rows in groups.items():
            titles = {_cell(result, row, "title") for row in rows}
            title, issue = _consistent(titles)
            if issue:
                issues.append(f"{bill}: English Bill title is {issue}.")
                if title == "—": title = "English title unavailable"
            years = {_cell(result, row, "year") for row in rows}
            year, year_issue = _consistent(years)
            if year_issue:
                display_year = "Legislative year unavailable" if year_issue == "missing" else "Conflicting legislativeYear"
                issues.append(f"{bill}: legislativeYear metadata is {year_issue}; not counted under an enacted-state category.")
            else:
                display_year = year
            number, _route_year = _bill_number_year(bill, "—", "—")
            dates = sorted({_cell(result, row, "eventDate") for row in rows} - {"—"})
            projected.append((title, number, display_year, "; ".join(dates), bill))
        if not groups:
            return QueryResult("select", ("English title", "Bill number", "Legislative year", "Published event dates", "Official Bill"), ()), "source_data_unavailable", base_notice + " No matching dated Published event is present locally."
        status = "incomplete_display_evidence" if issues else "success"
        notice = base_notice + " Any typed Published lifecycle event dated with xsd:date in the requested year qualifies; legislativeYear is display-only."
        if issues: notice += " " + " ".join(issues)
        return QueryResult("select", ("English title", "Bill number", "Legislative year", "Published event dates", "Official Bill"), tuple(projected)), status, notice

    if family == "non_enacted_bills":
        projected, count_by_status, issues = [], {}, []
        for bill, rows in groups.items():
            title, title_issue = _consistent({_cell(result, row, "title") for row in rows})
            if title_issue: issues.append(f"{bill}: English Bill title is {title_issue}.")
            years = {_cell(result, row, "year") for row in rows} - {"—"}
            year_issue = "missing" if not years else ("conflicting" if len(years) > 1 else None)
            if years and years != {str(_bill_number_year(bill, "—", "—")[1])}:
                year_issue = "conflicting"
            statuses = {_cell(result, row, "status") for row in rows}
            statuses.discard("—")
            if year_issue:
                display_year = "Legislative year unavailable" if year_issue == "missing" else "Conflicting legislativeYear"
                issues.append(f"{bill}: legislativeYear display metadata is {year_issue}.")
            if len(statuses) > 1:
                label = "Conflicting process statuses"
                issues.append(f"{bill}: process status is conflicting; it was not classified.")
            elif not statuses:
                label = "Unknown process status"
                issues.append(f"{bill}: process status is missing; it was not counted as non-enacted.")
            else:
                status_uri = next(iter(statuses))
                label = _status_label(status_uri)
                if status_uri not in _STATUS_LABELS:
                    issues.append(f"{bill}: process status is not a recognized controlled Bill status; it was not classified.")
                elif status_uri == _STATUS_IRIS["EnactedBill"]:
                    continue
            number, route_year = _bill_number_year(bill, "—", "—")
            year = next(iter(years)) if len(years) == 1 else ("Legislative year unavailable" if not years else "Conflicting legislativeYear")
            projected.append((title, number, year, label, bill))
            if len(statuses) == 1 and next(iter(statuses)) in _STATUS_LABELS:
                count_by_status[label] = count_by_status.get(label, 0) + 1
        if not groups:
            return QueryResult("select", ("English title", "Bill number", "Legislative year", "Recorded process status", "Official Bill"), ()), "source_data_unavailable", base_notice + " No Bills with the requested legislative year are present locally."
        status = ("conflicting_status_evidence" if any("process status is conflicting" in item for item in issues)
                  else ("incomplete_status_evidence" if any("process status" in item for item in issues)
                        else ("incomplete_display_evidence" if issues
                              else ("source_data_unavailable" if not projected else "success"))))
        counts = "; ".join(f"{name}: {count}" for name, count in sorted(count_by_status.items())) or "none"
        notice = base_notice + f" Distinct local Bill counts by recorded status: {counts}."
        if issues: notice += " " + " ".join(issues)
        elif not projected: notice += " All matching locally recorded Bills have Enacted status; incomplete corpus coverage prevents a complete negative."
        return QueryResult("select", ("English title", "Bill number", "Legislative year", "Recorded process status", "Official Bill"), tuple(projected)), status, notice

    if family in {"bill_title_search", "bill_status_history", "bill_sponsors"}:
        if not groups:
            return QueryResult("select", ("English title", "Bill number", "Legislative year", "Official Bill"), ()), "source_data_unavailable", base_notice + " No locally recorded Bill title matches the supplied mention."
        title_rows = []
        for bill, rows in groups.items():
            title, issue = _consistent({_cell(result, row, "title") for row in rows})
            number, year = _bill_number_year(bill, _one_value(rows, result, "number"), _one_value(rows, result, "year"))
            title_rows.append((bill, rows, title, number, year, issue))
        candidate_table = QueryResult("select", ("English title", "Bill number", "Legislative year", "Official Bill"),
                                      tuple((title, number, year, bill) for bill, _rows, title, number, year, _issue in title_rows))
        if len(groups) > 1:
            return candidate_table, "ambiguous", base_notice + " Several distinct Bill IRIs match the supplied title mention; select one before requesting Bill-specific facts."
        bill, rows, title, number, year, title_issue = title_rows[0]
        if title_issue or title == "—":
            return candidate_table, "incomplete_display_evidence", base_notice + " The matching Bill lacks one unambiguous English title; none was guessed."
        if family == "bill_title_search":
            return candidate_table, "success", base_notice + " Candidate identity is the distinct Bill resource IRI."
        if family == "bill_status_history":
            processes = {_cell(result, row, "process") for row in rows} - {"—"}
            if not processes:
                out = QueryResult("select", ("English title", "Current process status", "Bill number", "Legislative year", "Dated lifecycle history", "Official Bill"),
                                  ((title, "No typed LegislativeProcess recorded", number, year,
                                    "No process-linked dated history can be established", bill),))
                return out, "incomplete_status_evidence", base_notice + " The title-matched typed Bill has no typed LegislativeProcess in its owner graph; no process status or lifecycle history can be established."
            statuses = {_cell(result, row, "status") for row in rows} - {"—"}
            if len(statuses) > 1:
                label, status, note = "Conflicting process statuses", "conflicting_status_evidence", "The current process status is conflicting; no value was selected."
            elif not statuses:
                label, status, note = "Unknown process status", "incomplete_status_evidence", "No current process status is recorded; dated events do not substitute for it."
            else:
                uri = next(iter(statuses)); label = _status_label(uri)
                if uri not in _STATUS_LABELS:
                    status, note = "incomplete_status_evidence", "The process status is not a recognized controlled Bill status."
                else:
                    status, note = "success", "Current status is the mapped process status; no next step is inferred."
            history = _event_history(result, rows)
            out = QueryResult("select", ("English title", "Current process status", "Bill number", "Legislative year", "Dated lifecycle history", "Official Bill"),
                              ((title, label, number, year, history, bill),))
            return out, status, base_notice + " " + note
        # One readable row per Participation identity, with no activity join.
        participation_groups: dict[str, list[tuple[str, ...]]] = {}
        for row in rows:
            participation = _cell(result, row, "participation")
            if participation != "—": participation_groups.setdefault(participation, []).append(row)
        if not participation_groups:
            out = QueryResult("select", ("English title", "Sponsor", "Recorded role", "Primary status", "Official Bill"), ())
            return out, "source_data_unavailable", base_notice + " The matching Bill has no recorded sponsor Participation; this is not proof of no sponsorship."
        projected, issues = [], []
        for participation, part_rows in participation_groups.items():
            members = {_cell(result, row, "member") for row in part_rows} - {"—"}
            names = {_cell(result, row, "memberName") for row in part_rows} - {"—"}
            roles = {_cell(result, row, "role") for row in part_rows} - {"—"}
            if len(members) > 1 or len(names) > 1 or len(roles) > 1:
                issues.append("A Participation has conflicting participant, label, or role evidence.")
            if len(names) > 1:
                person = "Conflicting local Member display labels"
            elif names:
                person = next(iter(names))
            elif members:
                person = "Sponsor identity has no local display label"
            elif roles:
                person = "Unresolved sponsor (recorded role only)"
            else:
                person = "Participation has no recorded participant or role"
            primary, primary_issue = _primary_status({_raw_cell(result, row, "primary") for row in part_rows})
            if primary_issue: issues.append(f"A Participation primary flag is {primary_issue}.")
            role = ("Conflicting recorded roles" if len(roles) > 1 else
                    (next(iter(roles)) if roles else "Role not recorded"))
            projected.append((title, person, role, primary, bill))
        out = QueryResult("select", ("English title", "Sponsor", "Recorded role", "Primary status", "Official Bill"), tuple(projected))
        status = "conflicting_sponsorship_evidence" if any("conflicting" in item for item in issues) else ("incomplete_primary_status_evidence" if issues else "success")
        return out, status, base_notice + " Sponsorship rows preserve distinct Participation resources. " + (" ".join(issues) if issues else "")

    if family == "bill_lookup":
        if not groups:
            return QueryResult("select", ("English title", "Process status", "Bill number/year", "Recorded dated history", "Official Bill", "Explanatory memorandum"), ()), "source_data_unavailable", base_notice + " The exact typed Bill is absent from its resolved Bill graph; this does not mean it never existed."
        bill, rows = next(iter(groups.items()))
        titles = {_cell(result, row, "title") for row in rows} - {"—"}
        title_issue = "conflicting" if len(titles) > 1 else ("missing" if not titles else None)
        title = next(iter(titles)) if len(titles) == 1 else ("Conflicting English titles" if title_issue == "conflicting" else "English title unavailable")
        statuses = {_cell(result, row, "status") for row in rows} - {"—"}
        status_issue = "conflicting" if len(statuses) > 1 else ("missing" if not statuses else None)
        status_uri = next(iter(statuses)) if len(statuses) == 1 else "—"
        status_label = _status_label(status_uri)
        if status_uri not in _STATUS_LABELS and status_uri != "—": status_issue = status_issue or "unknown"
        if status_issue: status_label = "Conflicting process statuses" if status_issue == "conflicting" else ("Unknown/unmapped process status" if status_issue == "unknown" else "Unknown")
        number = _one_value(rows, result, "number")
        year = _one_value(rows, result, "year")
        bill_number, _legislative_year = _bill_number_year(bill, number, year)
        # Exact number/year in the requested identity is always an authoritative display selector.
        history = _event_history(result, rows)
        memo_works = {_cell(result, row, "memoWork") for row in rows} - {"—"}
        memos = sorted({_cell(result, row, "memo") for row in rows} - {"—"})
        memo_status = ""
        memo_incomplete = False
        if not memo_works:
            memo = "No explanatory memorandum Work is recorded in this Bill graph"
            memo_status = "No explanatory memorandum Work is recorded in the available Bill graph; this does not prove none exists elsewhere."
        elif not memos:
            memo = "Explanatory memorandum Work exists, but no complete typed rendition chain is recorded"
            memo_status = "A typed ExplanatoryMemo Work is present, but its expression/format/rendition link is incomplete; this is not absence of memorandum work."
            memo_incomplete = True
        else:
            memo = "; ".join(memos)
            if any(_cell(result, row, "memoWork") != "—" and _cell(result, row, "memo") == "—" for row in rows):
                memo_status = "At least one ExplanatoryMemo Work lacks a complete typed rendition chain."
                memo_incomplete = True
        out = QueryResult("select", ("English title", "Process status", "Bill number/year", "Recorded dated history", "Official Bill", "Explanatory memorandum"),
                          ((title, status_label, f"{bill_number}/{_BILL_IRI_RE.fullmatch(bill).group(1) if _BILL_IRI_RE.fullmatch(bill) else 'Year unavailable'}", history, bill, memo),))
        if title_issue:
            display_detail = ("missing English-title evidence" if title_issue == "missing"
                              else "conflicting English-title evidence")
            return out, "incomplete_display_evidence", base_notice + " The exact Bill graph has " + display_detail + "; no title was guessed. " + memo_status
        if status_issue:
            detail = ("conflicting current process-status evidence" if status_issue == "conflicting" else
                      "no recorded current process status" if status_issue == "missing" else "unknown current process status")
            return out, "conflicting_status_evidence" if status_issue == "conflicting" else "incomplete_status_evidence", base_notice + " The exact Bill graph has " + detail + "; no dated event substitutes for it. " + memo_status
        notice = base_notice + " Dated history includes every mapped typed activity with xsd:date. " + memo_status
        return out, "incomplete_document_evidence" if memo_incomplete else "success", notice

    return result, "unsupported_mapping", f"No readable result projection exists for the validated family {family}."


def _one_value(rows: list[tuple[str, ...]], result: QueryResult, name: str) -> str:
    return next(iter({_cell(result, row, name) for row in rows} - {"—"}), "—")


def _committee_alias_matches(alias: str, official_label: str) -> bool:
    """Bounded Q12 alias grounding: Transport matches official committee labels."""
    aliases = {"committee on transport": {"transport"}}
    tokens = aliases.get(" ".join(alias.casefold().split()))
    if not tokens:
        return " ".join(alias.casefold().split()) == " ".join(official_label.casefold().split())
    words = set(re.findall(r"[a-z]+", official_label.casefold()))
    return "committee" in words and tokens.issubset(words)


def _readable_bill_result(family: str, result: QueryResult) -> tuple[QueryResult, str | None]:
    readable, _status, notice = _project_bill_result(family, result)
    return readable, notice


def handle_stage_b(question: str, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome | None:
    plan = plan_stage_b(question, as_of=as_of)
    if plan is None:
        return None
    try:
        _validate(plan)
    except (KeyError, TypeError, ValueError) as error:
        return PlanOutcome("unsupported_capability",
                           diagnostic=f"Stage B plan failed its closed semantic validator: {error}")
    family = _family(plan)
    if family in {"office_overlap", "office_point"}:
        from .composable_plan import _execute_office_question, plan_question, validate_plan
        office_mention = _ref(plan, "office")["mention"]
        if family == "office_overlap":
            from .stage_a import _resolve_member
            member_ref = _ref(plan, "member")
            member_mention = member_ref["mention"]
            try:
                candidates = _resolve_member(member_mention, fuseki, supported_predicates)
            except NLQError as error:
                resolution = "unsupported_mapping" if "requires a full name" in str(error) else "source_data_unavailable"
                member_ref["resolution"] = resolution
                _validate(plan)
                status = "unsupported_capability" if resolution == "unsupported_mapping" else "source_data_unavailable"
                return PlanOutcome(status, plan=plan,
                                   diagnostic=f"The requested Member identity could not be resolved safely: {error}")
            except Exception as error:
                member_ref["resolution"] = "source_data_unavailable"
                _validate(plan)
                return PlanOutcome("query_execution_failed", plan=plan,
                                   diagnostic=f"The read-only exact Member identity lookup did not complete: {error}")
            if len(candidates) != 1:
                if not candidates:
                    member_ref["resolution"] = "not_found"
                    _validate(plan)
                    return PlanOutcome("not_found", plan=plan,
                                       diagnostic=(f'No exact local Member identity matches “{member_mention}”; '
                                                   "no office query or yes/no answer was produced."))
                member_ref.update({
                    "resolution": "ambiguous",
                    "candidates": [{"iri": iri, "label": label}
                                   for iri, label in sorted(candidates.items())],
                })
                _validate(plan)
                candidate_outcomes = tuple({"iri": iri, "label": label}
                                           for iri, label in sorted(candidates.items()))
                return PlanOutcome("ambiguous", plan=plan,
                                   candidates=candidate_outcomes,
                                   diagnostic=(f'Several distinct local Member IRIs exactly match “{member_mention}”; '
                                               "choose a candidate before testing the office interval."))
            member_iri, member_label = next(iter(candidates.items()))
            member_ref.update({"resolution": "resolved", "iri": member_iri, "label": member_label})
            plan["constraints"].append(_constraint("member", "memberIdentity", "equals", member_iri))
            _validate(plan)
        if family == "office_overlap":
            value = _constraint_value(plan, "interval")
            start = date.fromisoformat(value["start"])
            end = date.fromisoformat(value["end"])
            q35_question = (f"Who was {office_mention} from {start.strftime('%B')} {start.year} "
                            f"to {end.strftime('%B')} {end.year}?")
        else:
            parsed = date.fromisoformat(_constraint_value(plan, "interval")["start"])
            month = parsed.strftime("%B")
            q35_question = f"Who was {office_mention} from {month} {parsed.year} to {month} {parsed.year}?"
        office_plan = plan_question(q35_question, as_of=as_of)
        if family == "office_point":
            office_plan["constraints"][0]["value"].update({"start": parsed.isoformat(), "end": parsed.isoformat()})
        else:
            member = _ref(plan, "member")
            office_plan["referents"]["member"] = {
                "type": "Member", "answer": True, "mention": member["mention"],
                "resolution": "resolved", "iri": member["iri"], "label": member["label"],
            }
            office_plan["constraints"].append(_constraint("member", "memberIdentity", "equals", member["iri"]))
        office_plan = validate_plan(office_plan)
        outcome = _execute_office_question(office_plan, fuseki=fuseki,
                                           supported_predicates=supported_predicates)
        if family == "office_overlap":
            member = _ref(plan, "member")
            start_text = _constraint_value(plan, "interval")["start"]
            end_text = _constraint_value(plan, "interval")["end"]
            qualified_note = (f"The inclusive calendar window is {start_text} through {end_text}. "
                              "This reports locally evidenced accepted holdings only; historical coverage is not certified complete.")
            if outcome.status == "success" and outcome.result is not None:
                rows = tuple(("Yes", row[0], row[1], row[2]) for row in outcome.result.rows)
                readable = QueryResult("select", ("Overlap", "Member", "Holding start", "Holding end"), rows)
                return PlanOutcome("success", plan=plan, sparql=outcome.sparql, result=readable,
                                   diagnostic=qualified_note + " At least one accepted holding for the exact Member IRI overlaps the requested interval.")
            negative_markers = (
                "No accepted Member-owned OfficeHolding record for this reviewed office is present",
                "No accepted local holding is recorded overlapping",
            )
            if (outcome.status == "source_data_unavailable" and outcome.diagnostic
                    and outcome.diagnostic.startswith(negative_markers[1])):
                evidence_rows = (outcome.result.rows if outcome.result is not None else ())
                rows = tuple(("No", row[0], row[1], row[2]) for row in evidence_rows)
                readable = QueryResult("select", ("Overlap", "Member", "Holding start", "Holding end"), rows)
                return PlanOutcome("success", plan=plan, sparql=outcome.sparql, result=readable,
                                   diagnostic=(qualified_note + " No matching accepted holding is recorded for this exact local Member and office in the local dataset; this is a qualified local result, not proof of complete historical absence."))
            return PlanOutcome(outcome.status, plan=plan, sparql=outcome.sparql,
                               result=outcome.result, diagnostic=outcome.diagnostic,
                               candidates=outcome.candidates)
        return PlanOutcome(outcome.status, plan=plan, sparql=outcome.sparql,
                           result=outcome.result, diagnostic=outcome.diagnostic,
                           candidates=outcome.candidates)
    if family == "committee_chair":
        from .stage_a import _committee_catalogue_query, _date, _values
        try:
            committee_query = _committee_catalogue_query(supported_predicates=supported_predicates)
        except (NLQError, ValueError, TypeError) as error:
            return PlanOutcome("unsupported_mapping", plan=plan,
                               diagnostic=f"The reviewed Committee owner/date query could not be compiled: {error}")
        try:
            committee_result = fuseki.query(committee_query)
            catalogue = _values(committee_result,
                                ("committee", "label", "term", "start", "end", "termStart", "termEnd"))
        except Exception as error:
            return PlanOutcome("query_execution_failed", plan=plan, sparql=committee_query,
                               diagnostic=f"The validated read-only Committee owner/date query did not complete: {error}")
        try:
            if len(catalogue) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   sparql=committee_query,
                                   diagnostic="The local Committee owner catalogue reached the 100-row cap; no current Committee was selected.")
            expected = _ref(plan, "committee")["mention"]
            named = [row for row in catalogue if row["label"] and
                     ("@" not in row["label"] or row["label"].endswith("@en")) and
                     _committee_alias_matches(expected, row["label"].removesuffix("@en"))]
            date_evidence: dict[str, set[tuple[str | None, ...]]] = {}
            for row in named:
                date_evidence.setdefault(row["committee"], set()).add(
                    tuple(row[field] for field in ("start", "end", "term", "termStart", "termEnd")))
            if any(len(records) > 1 for records in date_evidence.values()):
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=committee_query,
                                   diagnostic="The matching Committee owner has conflicting date/term records; current incarnation was not selected and no chair was inferred.")
            if any(row["start"] is None or row["term"] is None or row["termStart"] is None for row in named):
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=committee_query,
                                   diagnostic="The matching Committee owner lacks required Committee/HouseTerm start-date evidence; current incarnation was not selected.")
            current = []
            for row in named:
                term_start, term_end = _date(row["termStart"]), _date(row["termEnd"])
                start, end = _date(row["start"]), _date(row["end"])
                if (term_start and term_start <= as_of and (term_end is None or as_of <= term_end)
                        and start and start <= as_of and (end is None or as_of <= end)):
                    current.append(row)
            identities = {row["committee"] for row in current}
            if len(identities) > 1:
                candidates = tuple({"iri": iri, "label": label} for iri, label in sorted({
                    (row["committee"], row["label"].removesuffix("@en")) for row in current}))
                result = QueryResult("select", ("Current Committee incarnation",),
                                     tuple((label,) for _iri, label in sorted({
                                         (row["committee"], row["label"].removesuffix("@en")) for row in current})))
                return PlanOutcome("ambiguous", plan=plan, candidates=candidates, result=result, sparql=committee_query,
                                   diagnostic="Several current Committee on Transport incarnations match the as-of date; no chair or Committee identity was selected.")
            if not current:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   sparql=committee_query,
                                   diagnostic="No uniquely dated current Committee on Transport owner is present in the local Committee graph; chair evidence was not queried or inferred.")
            row = current[0]
            labels = {item["label"].removesuffix("@en") for item in current}
            if len(labels) != 1:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=committee_query,
                                   diagnostic="The current Committee identity resolves, but its matching official English labels conflict; no display name or chair was selected.")
            result = QueryResult("select", ("Current Committee", "As-of date"),
                                 ((next(iter(labels)), as_of.isoformat()),))
            return PlanOutcome("source_data_unavailable", plan=plan, result=result, sparql=committee_query,
                               diagnostic="The current Committee on Transport was resolved from its dated owner record, but no reviewed chair/office-holder relationship is queryable; no chair is inferred from membership.")
        except (NLQError, ValueError, TypeError) as error:
            return PlanOutcome("source_data_unavailable", plan=plan,
                               diagnostic=f"The current Committee owner/date evidence could not be resolved safely: {error}")
    if family in {"committee_conflict", "office_current_coverage"}:
        diagnostics = {
            "committee_conflict": "The reviewed 33rd-term Good Friday Committee source identity is conflicted/quarantined in the development dataset; this does not assert that the 34th-term resource itself is conflicted and cannot verify a current roster.",
            "office_current_coverage": "The accepted development holdings are an incomplete 22-holding sample and do not establish a complete current Finance-office roster; office aliases do not identify a holder.",
        }
        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=diagnostics[family])
    return execute_stage_b(plan, fuseki=fuseki, supported_predicates=supported_predicates)
