"""Bounded Stage B Query Service routes built only from reviewed local RDF."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .composable_plan import PlanOutcome, _PREFIXES, _reviewed_cross_graph_join, _reviewed_pattern
from .contract import load_query_contract
from .errors import NLQError
from .safety import validate_sparql
from .results import QueryResult


_BILL = "https://data.oireachtas.ie/ie/oireachtas/bill"
_GRAPH = "https://data.oireachtas.ie/graph/bill/"
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
            refs["member"] = {"type": "Member", "mention": mention, "answer": True}
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
    match = re.fullmatch(r"(?i)was (?P<member>.+?) (?P<office>taoiseach) in september (?P<year>\d{4})[?.!]*", text)
    if match:
        return _plan("office_overlap", as_of, mention=" ".join(match["member"].split()),
                     office="Taoiseach", interval=(f"{match['year']}-09-01", f"{match['year']}-09-30"))
    match = re.fullmatch(r"(?i)who was (?P<office>minister for finance) on (?P<day>\d{1,2}) (?P<month>[a-z]+) (?P<year>\d{4})[?.!]*", text)
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
            if refs["office"].get("mention") != "Taoiseach": fail("Office overlap requires the reviewed Taoiseach role.")
            interval = _constraint_value(plan, "interval")
            if not isinstance(interval, dict) or set(interval) != {"start", "end", "inclusive"} or interval["inclusive"] is not True:
                fail("Office overlap requires a closed inclusive calendar interval.")
            start, end = date.fromisoformat(interval["start"]), date.fromisoformat(interval["end"])
            if start > end: fail("Office interval start must not follow its end.")
            expected = _plan(family, date.fromisoformat(plan["asOf"]), mention=mention,
                             office=refs["office"]["mention"], interval=(start.isoformat(), end.isoformat()))
        else:
            if refs["office"].get("mention") != "Minister for Finance": fail("Office point requires the reviewed Minister for Finance role.")
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
        _reviewed_pattern("bill-lifecycle", "bill-records")
    if family == "bill_lookup":
        _reviewed_pattern("bill-document-work-links", "bill-records")
    if family in {"office_overlap", "office_point"}:
        raise ValueError("Office questions must compile through the existing validated Q35 interval path.")
    if family == "bill_lookup":
        identity = _bill_identity(plan)
        bill = _bill_uri(plan)
        graph = f"{_GRAPH}{identity['year']}/{identity['number']}"
        body = f'''GRAPH <{graph}> {{
          <{bill}> a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill .
          BIND(<{bill}> AS ?bill)
          OPTIONAL {{ <{bill}> eli:title ?title . FILTER(LANG(?title) = "en") }}
          OPTIONAL {{ <{bill}> agents:legislativeYear ?year }}
          OPTIONAL {{ ?process a eli-dl:LegislativeProcess ; eli-dl:process_number ?number . OPTIONAL {{ ?process eli-dl:process_status ?status }} }}
          OPTIONAL {{ ?process eli-dl:latest_activity ?latest . ?latest eli-dl:forms_part_of ?process }}
          OPTIONAL {{ ?activity eli-dl:forms_part_of ?process ; eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type ?eventType }}
          OPTIONAL {{ <{bill}> eli:has_part ?work . ?work a eli:Work ; eli:type_document agents:ExplanatoryMemo ; eli:is_realized_by ?expression . ?expression a eli:LegalExpression ; eli:is_embodied_by ?format . ?format a eli:Format ; eli:uri_schema ?memo }}
        }}'''
        select = "?bill ?title ?year ?number ?status ?eventDate ?eventType ?memo"
    elif family in {"bills_published", "non_enacted_bills"}:
        year = _constraint_value(plan, "activityTypeAndDate" if family == "bills_published" else "legislativeYear")
        year_pattern = (f"agents:legislativeYear {year} ; " if family == "non_enacted_bills" else "")
        graph_route = f"{_GRAPH}{year}/" if family == "non_enacted_bills" else _GRAPH
        body = f'''GRAPH ?graph {{
          ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill ; {year_pattern}eli:title ?title .
          FILTER(LANG(?title) = "en")
           OPTIONAL {{ ?process a eli-dl:LegislativeProcess . OPTIONAL {{ ?process eli-dl:process_number ?number }} OPTIONAL {{ ?process eli-dl:process_status ?status }}
             OPTIONAL {{ ?activity eli-dl:forms_part_of ?process ; eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type ?eventType }} }}
           FILTER(REGEX(STR(?graph), "^{graph_route.replace('.', '[.]')}[0-9]+$"))
        }}'''
        if family == "bills_published":
            year_start = f'{year:04d}-01-01T00:00:00'
            next_year = f'{year + 1:04d}-01-01T00:00:00'
            year_start = f'{year:04d}-01-01'
            next_year = f'{year + 1:04d}-01-01'
            body += (f' FILTER(?eventType = <{_PUBLISHED}> '
                     f'&& DATATYPE(?eventDate) = xsd:date '
                     f'&& ?eventDate >= "{year_start}"^^xsd:date '
                     f'&& ?eventDate < "{next_year}"^^xsd:date) ')
            select = "?bill ?title ?number ?status ?eventDate"
        else:
            select = "?bill ?title ?number ?status"
    else:
        # Title-based resolution happens over source-backed English Bill titles;
        # candidate identities are returned rather than selecting by similarity.
        body = f'''GRAPH ?graph {{
          ?bill a eli-dl:DraftLegislationWork ; eli:type_document agents:Bill ; eli:title ?title .
          OPTIONAL {{ ?bill agents:legislativeYear ?year }}
          FILTER(LANG(?title) = "en")
           OPTIONAL {{ ?process a eli-dl:LegislativeProcess . OPTIONAL {{ ?process eli-dl:process_number ?number }} OPTIONAL {{ ?process eli-dl:process_status ?status }}
             OPTIONAL {{ ?activity eli-dl:forms_part_of ?process ; eli-dl:activity_date ?eventDate ; eli-dl:had_activity_type ?eventType }}
            OPTIONAL {{ ?process eli-dl:had_participation ?participation . ?participation a eli-dl:Participation . OPTIONAL {{ ?participation eli-dl:had_participant_person ?member }} OPTIONAL {{ ?participation agents:isPrimarySponsor ?primary }} OPTIONAL {{ ?participation rdfs:label ?role }} }} }}
           FILTER(REGEX(STR(?graph), "^https://data[.]oireachtas[.]ie/graph/bill/[0-9]{{4}}/[0-9]+$"))
        }}'''
        if family == "bill_sponsors":
            contract = load_query_contract()
            if "eli-dl:had_participant_person" not in contract["queryableProperties"]:
                raise ValueError("The reviewed Bill-to-Member identity join is not queryable.")
            _reviewed_cross_graph_join("bill-records", "eli-dl:had_participant_person", "member-records")
            _reviewed_pattern("bill-sponsor-reference", "bill-records")
            _reviewed_pattern("member-description", "member-records")
            body += ''' OPTIONAL { FILTER(BOUND(?member)) GRAPH ?memberGraph { ?member a agents:Member ; foaf:name ?memberName . }
              FILTER(STRSTARTS(STR(?memberGraph), "https://data.oireachtas.ie/graph/member/")) } '''
        for token in _title_tokens_from_plan(plan):
            if not isinstance(token, str) or not re.fullmatch(r"[a-z ]+", token):
                raise ValueError("Bill title tokens must use reviewed lowercase text.")
            body += f' FILTER(CONTAINS(LCASE(STR(?title)), "{token}")) '
        select = ("?bill ?title ?year ?number ?status ?eventDate ?eventType ?participation ?member ?memberName ?primary ?role"
                  if family != "bill_title_search" else "?bill ?title ?year ?number ?status")
    query = _PREFIXES + f"SELECT DISTINCT {select} WHERE {{ {body} }} LIMIT 100"
    return validate_sparql(query, supported_predicates=supported_predicates)


def execute_stage_b(plan: dict[str, Any], *, fuseki, supported_predicates) -> PlanOutcome:
    try:
        _validate(plan)
    except (ValueError, TypeError, KeyError) as error:
        return PlanOutcome("unsupported_mapping", diagnostic=f"Stage B plan failed authoritative validation: {error}")
    try:
        query = _query(plan, supported_predicates)
        result = fuseki.query(query)
    except (ValueError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    if len(result.rows) >= 100:
        return PlanOutcome("incomplete_results", plan=plan, sparql=query, result=result,
                           diagnostic="The local safety cap was reached; additional Bills may be omitted.")
    family = _family(plan)
    if family == "bill_lookup" and not result.rows:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                           diagnostic="Bill graph is not present in the local dataset; this does not mean the Bill never existed.")
    if family == "bill_lookup":
        title_index = result.columns.index("title")
        status_index = result.columns.index("status")
        if any(len(row) <= title_index or row[title_index] in {"—", ""} for row in result.rows):
            readable, _ = _readable_bill_result(family, result)
            return PlanOutcome("incomplete_display_evidence", plan=plan, sparql=query, result=readable,
                               diagnostic="The exact Bill graph has no English-title evidence in the queryable record; the title was not guessed.")
        if any(len(row) <= status_index or row[status_index] in {"—", ""} for row in result.rows):
            readable, _ = _readable_bill_result(family, result)
            return PlanOutcome("incomplete_status_evidence", plan=plan, sparql=query, result=readable,
                               diagnostic="The exact Bill graph has no recorded current process status; no status was inferred from a dated event.")
    if family in {"office_overlap", "office_point"} and not result.rows:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, result=result,
                           diagnostic="No accepted Member-owned OfficeHolding with matching reviewed office and dated overlap was found; local office coverage is not certified complete.")
    if family == "bills_published":
        rows = tuple(row for row in result.rows if len(row) > 4 and row[4] not in {"—", ""})
        result = result.__class__(result.kind, result.columns, rows, result.boolean, result.raw_json)
    if not result.rows:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, result=result,
                           diagnostic="No matching source-backed Bill evidence is present in the local dataset; coverage is not certified complete.")
    if family == "bill_status_history":
        status_index = result.columns.index("status")
        if any(len(row) <= status_index or row[status_index] in {"—", ""} for row in result.rows):
            readable, _ = _readable_bill_result(family, result)
            return PlanOutcome("incomplete_status_evidence", plan=plan, sparql=query, result=readable,
                               diagnostic="The matching Bill has no recorded current process status; its dated history is not substituted for status.")
    if family == "bill_title_search":
        bill_column = result.columns.index("bill")
        identities = {row[bill_column] for row in result.rows if len(row) > bill_column}
        if len(identities) > 1:
            return PlanOutcome("ambiguous", plan=plan, sparql=query, result=result,
                               diagnostic="Several locally recorded Bills match the abbreviation; choose among these official English titles rather than selecting one by guess.")
    if family == "non_enacted_bills":
        status_index = result.columns.index("status")
        bill_index = result.columns.index("bill")
        if any(len(row) <= status_index or row[status_index] in {"—", ""} for row in result.rows):
            return PlanOutcome("incomplete_status_evidence", plan=plan, sparql=query, result=result,
                               diagnostic="Some matching Bill processes have no recorded status; they are included as unknown, not silently classified as non-enacted.")
        by_bill: dict[str, set[str]] = {}
        for row in result.rows:
            by_bill.setdefault(row[bill_index], set()).add(row[status_index])
        if any(len(statuses) > 1 for statuses in by_bill.values()):
            return PlanOutcome("conflicting_status_evidence", plan=plan, sparql=query, result=result,
                               diagnostic="Conflicting process statuses are present; no single status was selected silently.")
        rows = tuple(row for row in result.rows if not _tail(row[status_index]).casefold().startswith("enacted"))
        if not rows:
            return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                               diagnostic="No matching locally recorded non-enacted Bill was found; the development dataset does not prove a complete negative for the year.")
        result = QueryResult(result.kind, result.columns, rows, result.boolean, result.raw_json)
    notice = "Results use locally recorded Bill-owned RDF; this development dataset does not certify complete Bill coverage."
    if family == "bills_published":
        notice += " Selection uses any mapped, queryable Published lifecycle event with an xsd:date in the requested calendar year. Legislative year is displayed only and is not used as a publication-date fallback."
    result, extra_notice = _readable_bill_result(family, result)
    if extra_notice:
        notice += " " + extra_notice
    return PlanOutcome("success", plan=plan, sparql=query, result=result,
                       diagnostic=notice)


def _tail(value: str) -> str:
    value = value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).replace("_", " ").strip() or "Unknown"


def _status_label(value: str) -> str:
    if value in {"—", ""}:
        return "Unknown"
    tail = _tail(value)
    return "Current" if tail.casefold() in {"published", "current", "current bill"} else tail


def _readable_bill_result(family: str, result: QueryResult) -> tuple[QueryResult, str | None]:
    if family in {"office_overlap", "office_point"}:
        return result, "Tenure dates are recorded inclusive calendar-date evidence; local office coverage is not certified complete."
    indices = {name: index for index, name in enumerate(result.columns)}
    def cell(row, name):
        index = indices.get(name)
        if index is None or len(row) <= index:
            return "—"
        return re.sub(r"\^\^<[^>]+>$", "", row[index]).removesuffix("@en")
    rows = []
    for row in result.rows:
        bill = cell(row, "bill")
        title = cell(row, "title")
        status = _status_label(cell(row, "status"))
        link = bill if bill.startswith(_BILL + "/") else "—"
        if family == "bill_lookup":
            dates = cell(row, "eventDate")
            event = _tail(cell(row, "eventType")) if cell(row, "eventType") not in {"—", ""} else "—"
            memo = cell(row, "memo")
            rows.append((title, status, cell(row, "number") + "/" + cell(row, "year"),
                         (event + " " + dates) if dates not in {"—", ""} else "—", link,
                         memo if memo not in {"—", ""} else "No explanatory memorandum is recorded in this Bill graph"))
        elif family == "bill_title_search":
            rows.append((title, cell(row, "number"), cell(row, "year"), link))
        elif family in {"bills_published", "non_enacted_bills"}:
            status_label = _status_label(status)
            if family == "bills_published":
                identity = re.fullmatch(r"https://data\.oireachtas\.ie/ie/oireachtas/bill/(\d{4})/(\d+)", bill)
                year = identity.group(1) if identity else "Year unavailable from Bill identity"
                number = cell(row, "number") if cell(row, "number") not in {"—", ""} else (identity.group(2) if identity else "—")
                rows.append((title, number, year, status_label, cell(row, "eventDate"), link))
            else:
                rows.append((title, cell(row, "number"), status_label, cell(row, "eventDate"), link))
        elif family == "bill_sponsors":
            primary = cell(row, "primary")
            primary = ("Unknown" if primary in {"—", ""} else
                       "Primary" if "true" in primary.casefold() else "Supporting" if "false" in primary.casefold() else "Conflicting/unknown")
            person = cell(row, "memberName")
            if person == "—":
                if cell(row, "member") != "—":
                    person = "Sponsor identity has no local display label"
                elif cell(row, "role") not in {"—", ""}:
                    person = "Unresolved sponsor (recorded role only)"
                else:
                    person = "No sponsor Participation is recorded in this Bill graph"
            rows.append((title, person if person != "—" else "Unresolved sponsor (recorded role only)",
                         cell(row, "role"), primary, link))
        else:
            rows.append((title, status, cell(row, "number"), cell(row, "eventDate"), link))
    columns = {
        "bill_lookup": ("English title", "Process status", "Bill number/year", "Latest recorded event", "Official Bill", "Explanatory memorandum"),
        "bill_title_search": ("English official short title", "Bill number", "Year", "Official Bill"),
        "bills_published": ("English short title", "Bill number", "Year", "Recorded status", "Published event date", "Official Bill"),
        "non_enacted_bills": ("English short title", "Bill number", "Recorded status", "Dated event", "Official Bill"),
        "bill_status_history": ("English short title", "Process status", "Bill number", "Dated event", "Official Bill"),
        "bill_sponsors": ("English short title", "Sponsor", "Recorded role", "Primary status", "Official Bill"),
    }.get(family)
    if not columns:
        return result, None
    extra = None
    if family == "non_enacted_bills":
        counts: dict[str, int] = {}
        for row in rows:
            counts[row[2]] = counts.get(row[2], 0) + 1
        extra = "Local recorded Bill counts by status: " + "; ".join(f"{status}: {count}" for status, count in sorted(counts.items())) + "."
    if family == "bill_lookup" and rows and all(row[-1] == "No explanatory memorandum is recorded in this Bill graph" for row in rows):
        extra = "No explanatory memorandum is recorded in the available Bill graph; this does not prove none exists elsewhere."
    return QueryResult("select", columns, tuple(rows), raw_json=result.raw_json), extra


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
        office_plan = validate_plan(office_plan)
        outcome = _execute_office_question(office_plan, fuseki=fuseki,
                                           supported_predicates=supported_predicates)
        if family == "office_overlap" and outcome.status == "success":
            # Q25 must be restricted to the resolved Member IRI, not a display
            # label. Until the office-plan contract carries that identity into
            # the compiled path, do not turn an unfiltered holder list into Yes.
            return PlanOutcome("source_data_unavailable", plan=plan,
                               sparql=outcome.sparql,
                               diagnostic=(f"Dated {office_mention} holdings were found, but this bounded Q35 path cannot yet bind "
                                           f"{_ref(plan, 'member')['mention']} to an exact local Member IRI; no yes/no answer is inferred."))
        return PlanOutcome(outcome.status, plan=plan, sparql=outcome.sparql,
                           result=outcome.result, diagnostic=outcome.diagnostic,
                           candidates=outcome.candidates)
    if family == "committee_chair":
        from .stage_a import _committee_catalogue_query, _date, _values
        try:
            committee_query = _committee_catalogue_query(supported_predicates=supported_predicates)
            catalogue = _values(fuseki.query(committee_query),
                                ("committee", "label", "term", "start", "end", "termStart", "termEnd"))
            if len(catalogue) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   sparql=committee_query,
                                   diagnostic="The local Committee owner catalogue reached the 100-row cap; no current Committee was selected.")
            expected = " ".join(_ref(plan, "committee")["mention"].casefold().split())
            named = [row for row in catalogue if row["label"] and
                     " ".join(row["label"].removesuffix("@en").casefold().split()) == expected]
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
                candidates = tuple({"iri": row["committee"], "label": row["label"].removesuffix("@en")} for row in current)
                result = QueryResult("select", ("Current Committee incarnation",),
                                     tuple((row["label"].removesuffix("@en"),) for row in current))
                return PlanOutcome("ambiguous", plan=plan, candidates=candidates, result=result, sparql=committee_query,
                                   diagnostic="Several current Committee on Transport incarnations match the as-of date; no chair or Committee identity was selected.")
            if not current:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   sparql=committee_query,
                                   diagnostic="No uniquely dated current Committee on Transport owner is present in the local Committee graph; chair evidence was not queried or inferred.")
            row = current[0]
            result = QueryResult("select", ("Current Committee", "As-of date"),
                                 ((row["label"].removesuffix("@en"), as_of.isoformat()),))
            return PlanOutcome("source_data_unavailable", plan=plan, result=result, sparql=committee_query,
                               diagnostic="The current Committee on Transport was resolved from its dated owner record, but no reviewed chair/office-holder relationship is queryable; no chair is inferred from membership.")
        except (NLQError, ValueError, TypeError) as error:
            return PlanOutcome("source_data_unavailable", plan=plan,
                               diagnostic=f"The current Committee owner/date evidence could not be resolved safely: {error}")
    if family in {"committee_conflict", "office_current_coverage"}:
        diagnostics = {
            "committee_conflict": "The reviewed 33rd-term Good Friday Committee identity is conflicted/quarantined in the development dataset; it cannot verify a current membership roster.",
            "office_current_coverage": "The accepted development holdings are an incomplete 22-holding sample and do not establish a complete current Finance-office roster; office aliases do not identify a holder.",
        }
        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=diagnostics[family])
    return execute_stage_b(plan, fuseki=fuseki, supported_predicates=supported_predicates)
