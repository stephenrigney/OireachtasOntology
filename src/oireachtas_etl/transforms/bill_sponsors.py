"""Transform accepted Bill-local sponsor links into a separate graph."""
from __future__ import annotations

from rdflib import Graph, URIRef

from ..bill_sponsor_reconciliation import (
    extract_bill_sponsor_observations,
    generate_bill_sponsor_candidates,
    normalize_accepted_member_holdings,
    sponsor_input_fingerprint,
)
from ..transforms.common import ELIDL, MEMBERS
from ..validation.offices import validate_registry_source


def build_bill_sponsor_graph(
    wrapper: dict,
    resolutions: list[dict],
    office_registry: dict,
    accepted_member_holdings: list[dict],
) -> Graph:
    """Build the complete current per-Bill graph from validated resolutions.

    This graph contains only ``reconciledSponsorOffice`` and
    ``reconciledSponsorHolding`` triples.  It intentionally contains no Bill
    core triples, Participation descriptions, labels, or external links.
    """
    if not isinstance(resolutions, list):
        raise ValueError("Bill sponsor resolutions must be a list")
    registry = validate_registry_source(office_registry)
    registered_offices = {
        f"https://data.oireachtas.ie/office/{entry['key']}"
        for entry in registry["offices"]
    }
    holdings = normalize_accepted_member_holdings(accepted_member_holdings, registry)
    holding_by_iri = {item["holding_iri"]: item for item in holdings}
    observations = extract_bill_sponsor_observations(wrapper)
    bill_iri = observations[0]["bill_iri"] if observations else wrapper["bill"]["uri"]
    current = {item["observation_key"]: item for item in observations}
    by_key: dict[str, dict] = {}
    for record in resolutions:
        if not isinstance(record, dict):
            raise ValueError("each Bill sponsor resolution must be an object")
        if record.get("bill_iri") != bill_iri:
            raise ValueError("Bill sponsor resolution belongs to a different Bill")
        key = record.get("observation_key")
        if not isinstance(key, str) or key in by_key:
            raise ValueError("Bill sponsor resolutions must have unique observation keys")
        if record.get("source_presence") == "present" and key not in current:
            raise ValueError("present Bill sponsor resolution has no current source observation")
        by_key[key] = record

    graph = Graph()
    graph.bind("members", MEMBERS)
    graph.bind("eli-dl", str(ELIDL))
    participation_targets: dict[tuple[str, object], set[str]] = {}
    for key, observation in current.items():
        record = by_key.get(key)
        if record is None or record.get("source_presence") != "present":
            raise ValueError(f"current Bill sponsor {key} has no present reconciliation record")
        if record.get("participation_iri") != observation["participation_iri"]:
            raise ValueError(f"Bill sponsor {key} Participation IRI is stale")
        expected_fingerprint = sponsor_input_fingerprint(
            observation, registry, holdings, record.get("time_context"))
        if record.get("input_fingerprint") != expected_fingerprint:
            raise ValueError(f"Bill sponsor {key} resolution is stale for current evidence")
        if record.get("status") not in {"accepted", "rejected", "unresolved", "review_required"}:
            raise ValueError(f"Bill sponsor {key} has an unsupported reconciliation status")
        office_target, holding_target = record.get("office_iri"), record.get("holding_iri")
        if record["status"] != "accepted":
            if office_target is not None or holding_target is not None:
                raise ValueError(f"non-accepted Bill sponsor {key} must not have RDF targets")
            continue
        if office_target is None and holding_target is None:
            raise ValueError(f"accepted Bill sponsor {key} has no RDF target")
        if office_target is not None and office_target not in registered_offices:
            raise ValueError(f"Bill sponsor {key} targets an unregistered NamedOffice")
        if holding_target is not None:
            if holding_target not in holding_by_iri:
                raise ValueError(f"Bill sponsor {key} targets no current accepted Member holding")
            time_context = record.get("time_context")
            candidates = generate_bill_sponsor_candidates(
                observation, registry, holdings, time_context)
            precision_ambiguous = any(
                item.get("kind") == "holding-time-precision-ambiguous"
                for item in candidates["conflicts"])
            if (len(candidates["holding_candidates"]) != 1
                    or candidates["holding_candidates"][0]["holding_iri"] != holding_target
                    or precision_ambiguous):
                raise ValueError(f"Bill sponsor {key} holding is not uniquely person+time qualified")
            selected = holding_by_iri[holding_target]
            if selected["member_iri"] != observation.get("person_iri"):
                raise ValueError(f"Bill sponsor {key} holding belongs to a different person")
            if office_target is not None and selected["office_iri"] != office_target:
                raise ValueError(f"Bill sponsor {key} office and holding targets disagree")
        participation = URIRef(observation["participation_iri"])
        if office_target is not None:
            targets = participation_targets.setdefault(
                (str(participation), MEMBERS.reconciledSponsorOffice), set())
            targets.add(office_target)
            if len(targets) > 1:
                raise ValueError("one Participation cannot have multiple reconciled sponsor offices")
            graph.add((participation, MEMBERS.reconciledSponsorOffice, URIRef(office_target)))
        if holding_target is not None:
            targets = participation_targets.setdefault(
                (str(participation), MEMBERS.reconciledSponsorHolding), set())
            targets.add(holding_target)
            if len(targets) > 1:
                raise ValueError("one Participation cannot have multiple reconciled sponsor holdings")
            graph.add((participation, MEMBERS.reconciledSponsorHolding, URIRef(holding_target)))

    return graph
