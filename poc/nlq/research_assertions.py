"""Authority is attached to exact generated facts, never to arbitrary cited prose."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .research_adapter import ClosedModel


class Assertion(ClosedModel):
    id: str
    text: str
    level: Literal[1, 2, 3, 4]
    evidenceRefs: list[str]
    factRefs: list[str]
    reasoning: str
    assumptions: list[str]
    conflicts: list[str]
    limitations: list[str]
    confidence: Literal["high", "moderate", "low"] | None
    confidenceRationale: str | None
    reviewStatus: Literal["provisional", "reviewed by the researcher"] = "provisional"

    @model_validator(mode="after")
    def confidence_class(self):
        if self.level == 3:
            if not self.confidence or not self.confidenceRationale or not self.factRefs:
                raise ValueError("Interpretation requires facts and a reviewable qualitative rationale.")
        elif self.confidence is not None or self.confidenceRationale is not None:
            raise ValueError("Confidence belongs only to Level 3.")
        if self.level in (1, 2) and not self.evidenceRefs:
            raise ValueError("Established facts need accepted evidence.")
        return self


def stable_id(value):
    return "a-" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def facts_from(env):
    if env["outcome"] != "answer" or not env["validation"]["accepted"]:
        return []
    data, eid, facts = env["data"], env["evidenceId"], []

    if "evidence" in data:
        from .query_evidence import AcceptedEvidence
        evidence = AcceptedEvidence.model_validate(data["evidence"])
        for fact in evidence.facts:
            proposition = fact.model_dump()
            facts.append(Assertion(id=stable_id([eid, proposition]), text=fact.text,
                level=2 if fact.kind == "measure" else 1,
                evidenceRefs=[eid], factRefs=[], reasoning=(
                    "Approved calculation: cardinality of this accepted distinct identity selection."
                    if fact.kind == "measure" else "Exact Query Service accepted proposition."),
                assumptions=[], conflicts=[], limitations=list(dict.fromkeys(
                    env["completeness"]["limitations"] + fact.qualifications)),
                confidence=None, confidenceRationale=None).model_dump()
                | {"proposition": proposition, "display": {"fields": {k: v.model_dump() for k, v in fact.fields.items()}},
                   "queryRefs": data["queryRefs"]})
        return facts

    # Retained legacy sessions only. New general queries always use the shared
    # contract above; no additional family adapters belong in this consumer.

    def add(proposition, text, level=1, reasoning="Exact accepted compiler proposition.", display=None):
        facts.append(Assertion(id=stable_id([eid, proposition]), text=text, level=level,
            evidenceRefs=[eid], factRefs=[], reasoning=reasoning, assumptions=[], conflicts=[],
            limitations=env["completeness"]["limitations"], confidence=None, confidenceRationale=None).model_dump()
            | {"proposition": proposition, "display": display})

    member = env["request"]["factualRequest"]
    if "bills" in data:
        name = data.get("memberName") or member.removeprefix("Which Bills did ").removesuffix(" sponsor?")
        for b in data["bills"]:
            title = " / ".join(b["titles"])
            for p in b["participations"]:
                role = ", ".join(p["roles"]) or "not recorded"
                primary = ", ".join(p["primaryStatus"])
                add(["sponsorship", data["memberIri"], b, p],
                    f"The available records identify {name} as a sponsor of {title} (Bill {'/'.join(b['numbers'])}/{'/'.join(b['years'])}); recorded classification: {primary}; recorded sponsor role: {role}.")
        identities = sorted({b["billIri"] for b in data["bills"]})
        add(["distinct_bill_count", identities], f"The sponsorship results retrieved here contain {len(identities)} distinct Bills.", 2,
            "Approved calculation: cardinality of the distinct Bill IRI set in this one accepted sponsorship enumeration; no join or population estimate.")
    for b in data.get("lifecycle", []):
        add(["recorded_status", b["billIri"], b["statusIri"], b["processes"]],
            f"{b['title']} has the recorded process status ‘{b['recordedStatus']}’ in the available records. This is not a certified final outcome.", display={"status": b["recordedStatus"]})
        for e in b["events"]:
            add(["recorded_activity", b["billIri"], e],
                f"The records for {b['title']} include {e['label']} dated {e['date']}. This describes recorded activity, not necessarily the Bill's last development or final outcome.")
    seen = set()
    for r in data.get("representation", []):
        key = (r["member"], r["constituency"], r["term"])
        if key not in seen:
            add(["representation", key], f"The available records identify {r['name']} as representing {r['label']} in the {r['termLabel']}. This term-specific finding does not establish uninterrupted tenure or other parliamentary roles.",
                display={"name": r["name"], "constituency": r["label"], "term": r["termLabel"]})
            seen.add(key)
    if "partyScope" in data:
        scope = data["partyScope"]
        for m in data["members"]:
            for w in m["witnesses"]:
                add(["dated_party_membership", m["memberIri"], scope, w],
                    f"The available records identify {m['displayName']} as a {scope['label']} TD on {scope['asOf']}. "
                    f"The separately recorded parliamentary membership starts {w['membership']['start']} "
                    f"and has recorded end {w['membership']['end'] or 'not recorded (open-ended)'}; "
                    f"the party membership episode starts {w['episode']['start']} "
                    f"and has recorded end {w['episode']['end'] or 'not recorded (open-ended)'}. "
                    "Both intervals contain the reporting date. This is not a certified complete roster or continuous career history.")
    return facts


class Narrative(ClosedModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    text: str = Field(min_length=1, max_length=1800)
    level: Literal[3, 4]
    factRefs: list[str]
    reasoning: str = Field(min_length=1)
    assumptions: list[str]
    conflicts: list[str]
    limitations: list[str]
    confidence: Literal["high", "moderate", "low"] | None
    confidenceRationale: str | None


def accept_narrative(proposal, facts, section_kind, old=None):
    """Validate references/class, not the truth of free prose; always provisional."""
    p = Narrative.model_validate(proposal)
    if any(ref not in facts for ref in p.factRefs) or not p.factRefs:
        raise ValueError("Narrative must identify accepted facts, not invented citations.")
    if p.level == 4 and section_kind != "further_questions":
        raise ValueError("Hypotheses belong only in further questions.")
    if __import__("re").search(r"\d+(?:\.\d+)?\s*%", p.text + p.reasoning + (p.confidenceRationale or "")):
        raise ValueError("Numerical confidence is not permitted.")
    sources = sorted({e for ref in p.factRefs for e in facts[ref]["evidenceRefs"]})
    payload = p.model_dump(exclude={"key"}) | {"id": old["id"] if old else stable_id([p.key, p.text]), "evidenceRefs": sources}
    # Any change to wording/dependencies is a fresh provisional assessment.
    return Assertion.model_validate(payload).model_dump() | {"key": p.key}
