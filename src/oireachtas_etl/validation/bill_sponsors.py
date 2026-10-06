"""Independent acceptance checks for complete Bill-local sponsor graphs."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta

from rdflib import Graph, URIRef

from ..bill_sponsor_reconciliation import (
    FINGERPRINT_RE,
    _DATE_ONLY_RE,
    extract_bill_sponsor_observations,
    normalize_accepted_member_holdings,
    sponsor_input_fingerprint,
)
from ..office_observations import normalize_label
from ..transforms.common import MEMBERS, datetime_literal
from ..transforms.offices import office_iri
from .offices import validate_registry_source


_ALLOWED_PREDICATES = {MEMBERS.reconciledSponsorOffice,
                       MEMBERS.reconciledSponsorHolding}
_DATE_ONLY = _DATE_ONLY_RE


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _participation_for_source(bill_iri: str, sponsor: dict) -> str:
    """Reconstruct the unchanged Bill transformer identity independently."""
    role, by = sponsor.get("as", {}), sponsor.get("by", {})
    identity = {
        "member": by.get("uri"),
        "role": role.get("uri") or role.get("showAs"),
        "primary": sponsor.get("isPrimary"),
    }
    digest = hashlib.sha256(_canonical(identity)).hexdigest()
    return f"{bill_iri}#process#sponsor-{digest}"


def _active_on_source_date(holding: dict, event_date: str) -> bool:
    dates = holding["date_range"]
    if (not isinstance(dates.get("start"), str) or not _DATE_ONLY.fullmatch(dates["start"])
            or (dates.get("end") is not None
                and (not isinstance(dates["end"], str) or not _DATE_ONLY.fullmatch(dates["end"])) )):
        return False
    observed = date.fromisoformat(event_date)
    start = date.fromisoformat(dates["start"])
    end = date.fromisoformat(dates["end"]) if dates.get("end") is not None else None
    return observed >= start and (end is None or observed <= end)


def _has_ambiguous_precision_overlap(holding: dict, event_date: str) -> bool:
    dates = holding["date_range"]
    if (_DATE_ONLY.fullmatch(dates["start"])
            and (dates.get("end") is None or _DATE_ONLY.fullmatch(dates["end"]))):
        return False
    day_start = datetime.combine(date.fromisoformat(event_date), datetime.min.time())
    day_end = day_start + timedelta(days=1)
    start = datetime_literal(dates["start"]).toPython()
    end = datetime_literal(dates["end"]).toPython() if dates.get("end") is not None else None
    return start < day_end and (end is None or end >= day_start)


def _independent_office_matches(observation: dict, registry: dict,
                                time_context: dict | None) -> list[str]:
    """Reconstruct the unambiguous auto-alias rule without the graph builder."""
    role_text = observation.get("role_text")
    if not isinstance(role_text, str):
        return []
    wanted = normalize_label(role_text)
    matches = []
    for office in registry["offices"]:
        labels = [office["label_en"]]
        if office.get("label_ga"):
            labels.append(office["label_ga"])
        for alias in office["aliases"]:
            if normalize_label(alias["label"]) != wanted:
                continue
            contexts = set(alias.get("contexts", []))
            if contexts and not ({observation.get("origin_house_code"),
                                 observation.get("origin_house_uri")} & contexts):
                continue
            validity = alias.get("validity")
            if validity is not None:
                if (time_context is None or not _DATE_ONLY.fullmatch(validity["start"])
                        or (validity.get("end") is not None
                            and not _DATE_ONLY.fullmatch(validity["end"]))):
                    continue
                current = date.fromisoformat(time_context["date"])
                start = date.fromisoformat(validity["start"])
                end = date.fromisoformat(validity["end"]) if validity.get("end") else None
                if current < start or (end is not None and current > end):
                    continue
            if alias.get("unit_keys"):
                continue
            labels.append(alias["label"])
        if any(normalize_label(label) == wanted for label in labels):
            matches.append(str(office_iri(office["key"])))
    return sorted(set(matches))


def _assert_exact_graph(graph: Graph, expected: set[tuple]) -> None:
    if not isinstance(graph, Graph):
        raise ValueError("Bill sponsor RDF graph is required")
    unexpected_predicates = {triple[1] for triple in graph} - _ALLOWED_PREDICATES
    if unexpected_predicates:
        raise ValueError("Bill sponsor graph contains predicates outside the local-link contract")
    missing, unexpected = expected.difference(graph), set(graph).difference(expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing " + "; ".join(
                " ".join(term.n3() for term in triple)
                for triple in sorted(missing, key=str)))
        if unexpected:
            details.append("unexpected " + "; ".join(
                " ".join(term.n3() for term in triple)
                for triple in sorted(unexpected, key=str)))
        raise ValueError("Bill sponsor source-to-RDF correspondence failed: " + " | ".join(details))


def validate_bill_sponsor_graph(
    wrapper: dict,
    graph: Graph,
    resolutions: list[dict],
    office_registry: dict,
    accepted_member_holdings: list[dict],
) -> None:
    """Validate exact current Participation links, targets, and graph isolation.

    Expected triples are reconstructed here rather than by calling the graph
    transformer.  The input resolutions are checked against current source and
    evidence, registered offices, and accepted person+time-qualified holdings.
    """
    registry = validate_registry_source(office_registry)
    office_iris = {str(office_iri(item["key"])) for item in registry["offices"]}
    holdings = normalize_accepted_member_holdings(accepted_member_holdings, registry)
    holdings_by_iri = {item["holding_iri"]: item for item in holdings}
    observations = extract_bill_sponsor_observations(wrapper)
    bill_iri = observations[0]["bill_iri"] if observations else wrapper["bill"]["uri"]

    if not isinstance(resolutions, list):
        raise ValueError("Bill sponsor resolutions must be a list")
    by_key: dict[str, dict] = {}
    for record in resolutions:
        if not isinstance(record, dict):
            raise ValueError("each Bill sponsor resolution must be an object")
        if record.get("bill_iri") != bill_iri:
            raise ValueError("Bill sponsor resolution belongs to a different Bill")
        key = record.get("observation_key")
        if not isinstance(key, str) or key in by_key:
            raise ValueError("Bill sponsor resolutions must have unique observation keys")
        by_key[key] = record

    current_keys = {item["observation_key"] for item in observations}
    if any(record.get("source_presence") == "present" and key not in current_keys
           for key, record in by_key.items()):
        raise ValueError("present Bill sponsor resolution has no current source observation")

    expected: set[tuple] = set()
    participation_targets: dict[tuple[str, object], set[str]] = {}
    for observation in observations:
        key = observation["observation_key"]
        record = by_key.get(key)
        if record is None or record.get("source_presence") != "present":
            raise ValueError(f"current Bill sponsor {key} has no present reconciliation record")
        source_sponsor = wrapper["bill"]["sponsors"][observation["source_index"]]["sponsor"]
        independent_participation = _participation_for_source(bill_iri, source_sponsor)
        if (record.get("participation_iri") != independent_participation
                or observation["participation_iri"] != independent_participation):
            raise ValueError(f"Bill sponsor {key} does not identify its current Participation")
        if record.get("input_fingerprint") != sponsor_input_fingerprint(
                observation, registry, holdings, record.get("time_context")):
            raise ValueError(f"Bill sponsor {key} resolution is stale for current evidence")
        status = record.get("status")
        if status not in {"accepted", "rejected", "unresolved", "review_required"}:
            raise ValueError(f"Bill sponsor {key} has an unsupported reconciliation status")
        office_target, holding_target = record.get("office_iri"), record.get("holding_iri")
        if status != "accepted":
            if office_target is not None or holding_target is not None:
                raise ValueError(f"non-accepted Bill sponsor {key} must not retain RDF targets")
            continue
        if office_target is None and holding_target is None:
            raise ValueError(f"accepted Bill sponsor {key} has no target")
        if office_target is not None and office_target not in office_iris:
            raise ValueError(f"Bill sponsor {key} targets an unregistered NamedOffice")
        if holding_target is not None:
            holding = holdings_by_iri.get(holding_target)
            if holding is None:
                raise ValueError(f"Bill sponsor {key} holding target is not an accepted Member holding")
            if observation.get("person_iri") is None or holding["member_iri"] != observation["person_iri"]:
                raise ValueError(f"Bill sponsor {key} holding target does not match its explicit source person")
            time_context = record.get("time_context")
            if not isinstance(time_context, dict) or time_context not in observation["bill_time_contexts"]:
                raise ValueError(f"Bill sponsor {key} holding target has no source-backed Bill time context")
            if not _active_on_source_date(holding, time_context["date"]):
                raise ValueError(f"Bill sponsor {key} holding is not date-qualified at the selected Bill event")
            qualifying = [item for item in holdings
                          if item["member_iri"] == observation["person_iri"]
                          and _active_on_source_date(item, time_context["date"])]
            precision_ambiguous = any(
                item["member_iri"] == observation["person_iri"]
                and _has_ambiguous_precision_overlap(item, time_context["date"])
                for item in holdings)
            if (len(qualifying) != 1 or qualifying[0]["holding_iri"] != holding_target
                    or precision_ambiguous):
                raise ValueError(f"Bill sponsor {key} holding is not uniquely person+time qualified")
            if office_target is not None and holding["office_iri"] != office_target:
                raise ValueError(f"Bill sponsor {key} office and holding targets disagree")
        if not isinstance(record.get("evidence"), list) or not record["evidence"]:
            raise ValueError(f"accepted Bill sponsor {key} requires preserved evidence")
        method = record.get("resolution_method")
        if method == "unique-reviewed-office-label":
            matches = _independent_office_matches(observation, registry,
                                                  record.get("time_context"))
            if matches != [office_target] or holding_target is not None:
                raise ValueError(f"Bill sponsor {key} automatic office acceptance is not uniquely justified")
            if record.get("decision_hash") is not None:
                raise ValueError(f"Bill sponsor {key} automatic acceptance must not claim a review decision")
        elif method == "review-file":
            decisions = [item.get("decision") for item in record["evidence"]
                         if isinstance(item, dict) and item.get("kind") == "review-decision"]
            if len(decisions) != 1 or not isinstance(decisions[0], dict):
                raise ValueError(f"Bill sponsor {key} accepted review decision evidence is incomplete")
            decision = decisions[0]
            digest = hashlib.sha256(_canonical(decision)).hexdigest()
            if (not isinstance(record.get("decision_hash"), str)
                    or not FINGERPRINT_RE.fullmatch(record["decision_hash"])
                    or digest != record["decision_hash"]
                    or decision.get("status") != "accepted"
                    or decision.get("input_fingerprint") != record.get("input_fingerprint")
                    or decision.get("office_iri") != office_target
                    or decision.get("holding_iri") != holding_target
                    or decision.get("time_context") != record.get("time_context")):
                raise ValueError(f"Bill sponsor {key} accepted targets do not match its reviewed decision")
        else:
            raise ValueError(f"Bill sponsor {key} has an unsupported accepted resolution method")

        participation = independent_participation
        if office_target is not None:
            expected.add((URIRef(participation), MEMBERS.reconciledSponsorOffice,
                          URIRef(office_target)))
            participation_targets.setdefault((participation, MEMBERS.reconciledSponsorOffice), set()).add(office_target)
        if holding_target is not None:
            expected.add((URIRef(participation), MEMBERS.reconciledSponsorHolding,
                          URIRef(holding_target)))
            participation_targets.setdefault((participation, MEMBERS.reconciledSponsorHolding), set()).add(holding_target)

    if any(len(targets) > 1 for targets in participation_targets.values()):
        raise ValueError("one Participation cannot have multiple reconciled sponsor targets of the same kind")
    for participation, predicate in set((triple[0], triple[1]) for triple in graph):
        if len(list(graph.objects(participation, predicate))) > 1:
            raise ValueError("one Participation cannot have multiple reconciled sponsor targets of the same kind")
    _assert_exact_graph(graph, expected)
