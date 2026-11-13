"""Query Service accepted factual evidence v1.

Only validated executors/projectors construct this contract. It is not an
admission API: schema validity alone cannot authorise a fact. Display fields are
a lossless *view* of a proposition, never its evidence. Unknown shapes stay out.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Entity(Closed):
    iri: str = Field(min_length=1)
    type: str = Field(min_length=1)
    label: str = Field(min_length=1)


class Interval(Closed):
    resourceIri: str | None
    rangeIri: str | None
    start: str | None
    end: str | None
    endMeaning: Literal["recorded", "not_recorded", "open_ended"]
    meaning: str = Field(min_length=1)

    @model_validator(mode="after")
    def dates(self):
        from datetime import datetime
        for value in (self.start, self.end):
            if value is not None:
                datetime.fromisoformat(value)
        if self.start and self.end:
            try:
                if datetime.fromisoformat(self.end) < datetime.fromisoformat(self.start):
                    raise ValueError("Reversed evidence interval.")
            except TypeError as error:
                raise ValueError("Incompatible interval date precision/timezones.") from error
        if (self.end is not None) != (self.endMeaning == "recorded"):
            raise ValueError("Missing and recorded ends must remain distinguishable.")
        return self


class DisplayField(Closed):
    label: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Fact(Closed):
    predicate: str = Field(min_length=1)
    text: str = Field(min_length=1)
    fields: dict[str, DisplayField]
    scope: dict
    witnesses: list[dict] = Field(min_length=1)
    qualifications: list[str] = Field(min_length=1)


class EntityFact(Fact):
    kind: Literal["entity"] = "entity"
    entity: Entity


class RelationshipFact(Fact):
    kind: Literal["relationship"] = "relationship"
    participants: dict[str, Entity] = Field(min_length=2)


class EpisodeFact(Fact):
    kind: Literal["episode"] = "episode"
    participants: dict[str, Entity] = Field(min_length=1)
    intervals: list[Interval] = Field(min_length=1)


class MeasureFact(Fact):
    kind: Literal["measure"] = "measure"
    value: int
    unit: str = Field(min_length=1)
    method: Literal["accepted_selection_cardinality"]
    identities: list[str]

    @model_validator(mode="after")
    def cardinality(self):
        if self.value != len(set(self.identities)) or self.value < 0:
            raise ValueError("Measure does not match the accepted distinct identity set.")
        return self


Proposition = Annotated[EntityFact | RelationshipFact | EpisodeFact | MeasureFact, Field(discriminator="kind")]


class AcceptedEvidence(Closed):
    version: Literal[1] = 1
    facts: list[Proposition] = Field(min_length=1)
    plan: dict
    answerQuery: str = Field(min_length=1)
    resultDigest: str = Field(min_length=1)
    sourceCoverage: Literal["uncertified"] = "uncertified"
    freshness: Literal["unknown"] = "unknown"


QUALIFICATIONS = [
    "Findings describe available source records, not a certified complete account.",
    "Source freshness is unknown; separate reads do not establish a common snapshot.",
]


def entity(iri, label, type):
    return {"iri": iri, "label": label, "type": type}


def fields(**values):
    return {key: {"label": label, "text": str(text)} for key, (label, text) in values.items()}


def date_text(value):
    """Editorial calendar view; exact precision/lexical evidence stays retained.

    Non-midnight times are not silently discarded. This formats an already
    validated temporal value, never extracts a date from a display string.
    """
    from datetime import datetime, time
    if value is None:
        return "not recorded"
    parsed = datetime.fromisoformat(value)
    label = f"{parsed.day} {parsed.strftime('%B %Y')}"
    if parsed.time() != time():
        label += " · " + parsed.timetz().isoformat()
    elif parsed.tzinfo is not None:
        label += " · " + parsed.timetz().isoformat()
    return label


def result_digest(result):
    import hashlib
    import json
    return hashlib.sha256(json.dumps([result.kind, result.columns, result.rows, result.boolean],
                                    ensure_ascii=False).encode()).hexdigest()


def bundle(plan, query, facts, result):
    return AcceptedEvidence.model_validate({"plan": plan, "answerQuery": query, "facts": facts,
                                           "resultDigest": result_digest(result)}).model_dump()


def base(predicate, text, display, scope, witnesses, qualifications=()):
    return {"predicate": predicate, "text": text, "fields": display, "scope": scope,
            "witnesses": witnesses, "qualifications": QUALIFICATIONS + list(qualifications)}


def project_legacy(outcome):
    """Service-side migration of already accepted payloads; never display rows.

    Legacy payloads remain on PlanOutcome for existing consumers. No research
    code participates in authorising these propositions.
    """
    data, plan = outcome.accepted_evidence, outcome.plan
    if not data or not plan or outcome.status != "success":
        return None
    refs, facts = plan["referents"], []
    if set(data) == {"representation"}:
        for r in data["representation"]:
            participants = {"member": entity(r["member"], r["name"], "Member"),
                            "constituency": entity(r["constituency"], r["label"], "DailConstituency"),
                            "term": entity(r["term"], r["termLabel"], "DailTerm")}
            scope = {"meaning": "recorded_term_representation", "selector": refs["term"].get("selector"),
                     "asOf": plan["asOf"] if refs["term"].get("selector", {}).get("kind") == "currentTerm" else None}
            display = fields(member=("Member", r["name"]), constituency=("Constituency", r["label"]), term=("Dáil term", r["termLabel"]))
            text = f"The available records identify {r['name']} as representing {r['label']} in the {r['termLabel']}"
            intervals = []
            if scope["asOf"]:
                from .composable_plan import _rdf_literal_parts
                scope["meaning"] = "membership_contains_as_of"
                display.update(fields(as_of=("Reporting date", date_text(scope["asOf"]))))
                text += f" on {scope['asOf']}"
                intervals = [Interval(resourceIri=r["membership"], rangeIri=r["range"],
                    start=_rdf_literal_parts(r["start"])[0],
                    end=None if r["end"] in {"—", ""} else _rdf_literal_parts(r["end"])[0],
                    endMeaning="open_ended" if r["end"] in {"—", ""} else "recorded", meaning="membership")]
            common = base("representation", text + ".", display, scope, [r],
                          ["Separate term records do not establish uninterrupted tenure or other parliamentary roles."])
            facts.append((EpisodeFact(**common, participants=participants, intervals=intervals) if intervals
                          else RelationshipFact(**common, participants=participants)).model_dump())
    elif set(data) == {"members"}:
        # Projection only for the executor's reviewed current Dáil party shape.
        term, affiliation, as_of = refs["term"]["iri"], refs["affiliation"]["iri"], plan["asOf"]
        name = refs["affiliation"]["label"]
        identities = []
        for m in data["members"]:
            identities.append(m["memberIri"])
            for w in m["witnesses"]:
                if w["termIri"] != term or w["affiliationIri"] != affiliation:
                    raise ValueError("Accepted Member witness scope mismatch.")
                intervals = []
                for key in ("membership", "episode"):
                    i = w[key]
                    interval = Interval(resourceIri=i["resourceIri"], rangeIri=i["rangeIri"], start=i["start"], end=i["end"],
                        endMeaning="recorded" if i["end"] else "open_ended", meaning=key)
                    if not interval.start or not (interval.start[:10] <= as_of and (not interval.end or as_of <= interval.end[:10])):
                        raise ValueError("Both independent intervals must contain asOf.")
                    intervals.append(interval)
                facts.append(EpisodeFact(**base("dated_party_membership",
                    f"The available records identify {m['displayName']} as a {name} TD on {as_of}.",
                    fields(member=("Member", m["displayName"]), affiliation=("Party", name), as_of=("Reporting date", date_text(as_of))),
                    {"meaning": "both_intervals_contain_as_of", "asOf": as_of, "termIri": term}, [w],
                    ["Both separate intervals contain the reporting date; this is not a certified complete roster."]),
                    participants={"member": entity(m["memberIri"], m["displayName"], "Member"),
                                  "affiliation": entity(affiliation, name, "PoliticalAffiliationIdentity")}, intervals=intervals).model_dump())
        if plan["answer"]["kind"] == "count":
            if outcome.result.rows != ((str(len(set(identities))),),):
                raise ValueError("Count/witness mismatch.")
            facts.append(MeasureFact(**base("distinct_member_count",
                f"The accepted {name} selection on {as_of} contains {len(set(identities))} distinct recorded Members.",
                fields(affiliation=("Party", name), value=("Recorded Members", len(set(identities))), as_of=("Reporting date", date_text(as_of))),
                {"meaning": "both_intervals_contain_as_of", "asOf": as_of, "termIri": term}, data["members"]),
                value=len(set(identities)), unit="distinct_recorded_member_identities", method="accepted_selection_cardinality", identities=identities).model_dump())
        elif {r[1]: r[0] for r in outcome.result.rows} != {m["memberIri"]: m["displayName"] for m in data["members"]}:
            raise ValueError("List/witness mismatch.")
    elif set(data) == {"memberIri", "bills"}:
        member = refs["member"]
        if data["memberIri"] != member["iri"]:
            raise ValueError("Sponsorship Member identity mismatch.")
        for b in data["bills"]:
            for p in b["participations"]:
                title, role, primary = " / ".join(b["titles"]), ", ".join(p["roles"]) or "not recorded", ", ".join(p["primaryStatus"])
                facts.append(RelationshipFact(**base("sponsorship",
                    f"The available records identify {member['label']} as a sponsor of {title} (Bill {'/'.join(b['numbers'])}/{'/'.join(b['years'])}); recorded classification: {primary}; recorded sponsor role: {role}.",
                    fields(member=("Member", member["label"]), bill=("Bill", title), classification=("Recorded classification", primary), role=("Recorded role", role)),
                    {"meaning": "recorded_sponsorship", "constraints": plan.get("constraints", [])}, [b, p]),
                    participants={"member": entity(member["iri"], member["label"], "Member"), "bill": entity(b["billIri"], title, "Bill")}).model_dump())
        ids = sorted({b["billIri"] for b in data["bills"]})
        facts.append(MeasureFact(**base("distinct_bill_count", f"The sponsorship results retrieved here contain {len(ids)} distinct Bills.",
            fields(value=("Recorded Bills", len(ids))), {"meaning": "accepted_sponsorship_enumeration"}, data["bills"]),
            value=len(ids), unit="distinct_recorded_bill_identities", method="accepted_selection_cardinality", identities=ids).model_dump())
    elif set(data) == {"lifecycle"}:
        for b in data["lifecycle"]:
            bill = entity(b["billIri"], b["title"], "Bill")
            facts.append(RelationshipFact(**base("recorded_status",
                f"{b['title']} has the recorded process status ‘{b['recordedStatus']}’ in the available records. This is not a certified final outcome.",
                fields(bill=("Bill", b["title"]), status=("Recorded status", b["recordedStatus"])),
                {"meaning": "recorded_process_status"}, [b], ["Recorded status is not a certified final outcome."]),
                participants={"bill": bill, "status": entity(b["statusIri"], b["recordedStatus"], "BillStatus")}).model_dump())
            for e in b["events"]:
                facts.append(EpisodeFact(**base("recorded_activity",
                    f"The records for {b['title']} include {e['label']} dated {e['date']}.",
                    fields(bill=("Bill", b["title"]), activity=("Recorded activity", e["label"]), date=("Recorded date", date_text(e["date"]))),
                    {"meaning": "recorded_activity_not_latest_or_final"}, [b, e],
                    ["Not necessarily the latest development or final outcome.",
                     "The legacy lifecycle projection retains activity type/date observations, not individual activity resource identities."]),
                    participants={"bill": bill}, intervals=[Interval(resourceIri=None, rangeIri=None,
                        start=e["date"], end=e["date"], endMeaning="recorded", meaning="recorded_activity_date")]).model_dump())
    return bundle(plan, outcome.sparql, facts, outcome.result) if facts else None


def affiliation_evidence(plan, query, raw, result):
    """Validate exact source episodes before projecting, never parse display prose.

    Unknown dates remain unknown. Conflicting identities/ranges/dates are not
    resolved by choosing the last row; no parliamentary dates substitute for them.
    """
    from .composable_plan import _require_local_iri, _date_binding, _rdf_literal_parts
    required = {"member", "episode", "identity", "affiliationLabel", "start", "end",
                "party", "membership", "term", "dateRange", "memberGraph"}
    if raw.kind != "select" or not required.issubset(raw.columns):
        raise ValueError("Incomplete party episode evidence projection.")
    episodes = {}
    for row in raw.rows:
        if len(row) != len(raw.columns):
            raise ValueError("Truncated party episode evidence.")
        r = dict(zip(raw.columns, row))
        if r["member"] != plan["referents"]["member"]["iri"]:
            raise ValueError("Party episode escaped exact Member identity.")
        for key in ("member", "episode", "identity", "party", "membership", "term", "memberGraph"):
            _require_local_iri(r[key], key)
        if r["dateRange"] not in {"—", ""}:
            _require_local_iri(r["dateRange"], "DateRange")
        r["affiliationLabel"] = r["affiliationLabel"].removesuffix("@en")
        canonical = dict(r)
        for key in ("start", "end"):
            if r[key] in {"—", ""}:
                canonical[key] = None
            else:
                _date_binding(r[key])  # reviewed datatype/lexical validation
                canonical[key] = _rdf_literal_parts(r[key])[0]
        if r["episode"] in episodes and episodes[r["episode"]][0] != canonical:
            raise ValueError("Conflicting party episode identity, label or dates.")
        episodes[r["episode"]] = canonical, r
    facts = []
    member = plan["referents"]["member"]
    for r, source in episodes.values():
        interval = Interval(resourceIri=r["episode"], rangeIri=None if r["dateRange"] in {"—", ""} else r["dateRange"],
            start=r["start"], end=r["end"], endMeaning="recorded" if r["end"] else "not_recorded",
            meaning="recorded_party_membership_episode")
        start, end = interval.start or "not recorded", interval.end or "not recorded"
        facts.append(EpisodeFact(**base("party_membership_episode",
            f"The records identify a {r['affiliationLabel']} membership episode for {member['label']}; recorded start: {start}; recorded end: {end}.",
            fields(member=("Member", member["label"]), affiliation=("Party", r["affiliationLabel"]),
                   start=("Recorded start", date_text(interval.start)), end=("Recorded end", date_text(interval.end))),
            {"meaning": "separate_recorded_episodes_not_continuous_history"}, [source],
            ["Separate episodes preserve gaps in the records, not proven periods of non-membership. Missing dates are not inferred from parliamentary terms; an unrecorded end is not a current-membership claim."]),
            participants={"member": entity(member["iri"], member["label"], "Member"),
                          "affiliation": entity(r["identity"], r["affiliationLabel"], "PoliticalAffiliationIdentity")},
            intervals=[interval]).model_dump())
    return bundle(plan, query, facts, result)
