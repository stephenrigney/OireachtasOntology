"""Validated candidate reference graphs with non-destructive carry-forward."""
from __future__ import annotations

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from .reference_closure import validate_reference_closure
from .transforms.common import MEMBERS
from .transforms.committees import transform_committees
from .transforms.constituencies import transform_constituencies
from .transforms.parties import transform_parties
from .validation.committees import (validate_committees, validate_quality as validate_committee_quality,
                                    validate_shacl as validate_committee_shacl)
from .validation.constituencies import validate_constituencies
from .validation.houses import validate_rdf
from .validation.parties import validate_parties
from .validation.reference import assert_expected


GRAPH_CLASSES = {
    "parties": (MEMBERS.ParliamentaryMemberCollection,
                MEMBERS.ParliamentaryParty,
                MEMBERS.IndependentMemberCollection),
    "constituencies": (MEMBERS.Constituencies,
                       MEMBERS.DailConstituency, MEMBERS.SeanadPanel),
    "committees": (MEMBERS.Committee,),
}
TRANSFORMS = {
    "parties": transform_parties,
    "constituencies": transform_constituencies,
    "committees": transform_committees,
}
VALIDATORS = {
    "parties": validate_parties,
    "constituencies": validate_constituencies,
    "committees": validate_committees,
}


class ReferencePublicationError(ValueError):
    """Candidate reference graphs cannot safely replace their current owners."""


def _records_for(census_records: dict, endpoint: str) -> list[dict]:
    key = {"parties": "parties", "constituencies": "constituencies",
           "committees": "committees"}[endpoint]
    return census_records[key]


def _subjects(graph: Graph, endpoint: str) -> set[URIRef]:
    return {subject for class_ in GRAPH_CLASSES[endpoint]
            for subject in graph.subjects(RDF.type, class_)
            if isinstance(subject, URIRef)}


def _record_iris(records: list[dict], endpoint: str) -> set[URIRef]:
    if endpoint == "parties":
        key = "party"
    elif endpoint == "constituencies":
        key = "constituencyOrPanel"
    else:
        key = None
    return {URIRef(record[key]["uri"] if key else record["uri"])
            for record in records}


def _retained_graph(previous: Graph, endpoint: str,
                    replaced_subjects: set[URIRef]) -> Graph:
    """Carry forward absent owners; refresh whole descriptions for current IRIs."""
    retained = Graph()
    old_subjects = _subjects(previous, endpoint)
    kept_subjects = old_subjects - replaced_subjects
    dependent_subjects: set = set()
    replaced_dependents: set = set()
    if endpoint == "committees":
        dependent_subjects = {
            period for subject in kept_subjects
            for period in previous.objects(subject, MEMBERS.hasCommitteeDateRange)
        }
        replaced_dependents = {
            period for subject in old_subjects & replaced_subjects
            for period in previous.objects(subject, MEMBERS.hasCommitteeDateRange)
        }
    for triple in previous:
        subject, _predicate, _object = triple
        if subject in kept_subjects or subject in dependent_subjects:
            retained.add(triple)
    # A previously accepted graph consists only of owner descriptions and
    # their Committee DateRange nodes. Do not silently drop unknown content.
    unowned = set(previous) - set(retained)
    replaced_triples = {
        triple for subject in replaced_subjects
        for triple in previous.triples((subject, None, None))
    }
    replaced_triples.update(
        triple for subject in replaced_dependents
        for triple in previous.triples((subject, None, None)))
    if unowned - replaced_triples:
        raise ReferencePublicationError(
            f"previous {endpoint} graph contains triples outside its owner contract")
    return retained


def _validate_retained_only(endpoint: str, graph: Graph, retained: Graph) -> None:
    assert_expected(graph, set(retained))
    validate_rdf(graph)
    if endpoint == "committees":
        validate_committee_shacl(graph)
        validate_committee_quality(graph)
    else:
        from .validation.constituencies import validate_quality as validate_constituency_quality
        from .validation.constituencies import validate_shacl as validate_constituency_shacl
        from .validation.parties import validate_quality as validate_party_quality
        from .validation.parties import validate_shacl as validate_party_shacl
        if endpoint == "parties":
            validate_party_shacl(graph)
            validate_party_quality(graph)
        else:
            validate_constituency_shacl(graph)
            validate_constituency_quality(graph)


def _build_reference_candidates(census: dict, *, member_graph: Graph,
                                previous_graphs: dict[str, Graph] | None,
                                allow_quarantined_conflicts: bool) -> dict:
    """Shared pure construction path for authoritative and development runs."""
    report = census.get("report")
    records = census.get("records")
    if not isinstance(report, dict) or not isinstance(records, dict):
        raise ReferencePublicationError("reference census result is malformed")
    conflicts = report.get("conflicts", [])
    if conflicts and not allow_quarantined_conflicts:
        conflict_summary = "; ".join(
            f"{item.get('reference_kind')} {item.get('canonical_iri')}"
            for item in report["conflicts"])
        raise ReferencePublicationError(
            "reference census conflicts block publication: " + conflict_summary)

    quarantined_iris: dict[str, set[URIRef]] = {
        "parties": set(), "constituencies": set(), "committees": set(),
    }
    if allow_quarantined_conflicts:
        endpoint_by_kind = {
            "party": "parties", "representation": "constituencies",
            "committee": "committees",
        }
        for conflict in conflicts:
            endpoint = endpoint_by_kind.get(conflict.get("reference_kind"))
            identity = conflict.get("canonical_iri")
            if endpoint and isinstance(identity, str):
                quarantined_iris[endpoint].add(URIRef(identity))

    previous_graphs = previous_graphs or {}
    candidate_graphs: dict[str, Graph] = {}
    retained_graphs: dict[str, Graph] = {}
    for endpoint in ("parties", "constituencies", "committees"):
        source_records = _records_for(records, endpoint)
        if quarantined_iris[endpoint]:
            source_records = [
                record for record in source_records
                if not _record_iris([record], endpoint).intersection(
                    quarantined_iris[endpoint])
            ]
        current = TRANSFORMS[endpoint](source_records) if source_records else Graph()
        retained = _retained_graph(
            previous_graphs.get(endpoint, Graph()), endpoint,
            _record_iris(source_records, endpoint))
        candidate = Graph()
        candidate += current
        candidate += retained
        retained_graphs[endpoint] = retained
        candidate_graphs[endpoint] = candidate
        if source_records:
            VALIDATORS[endpoint](source_records, candidate,
                                 retained_graph=retained)
        elif len(candidate):
            _validate_retained_only(endpoint, candidate, retained)
        elif endpoint == "committees":
            # An empty first Committee owner graph is valid when the complete
            # Members source contains no Committee references.
            validate_rdf(candidate)

    # The authoritative closure validator deliberately rejects every material
    # conflict. Development uses the same edge/owner checks for all other
    # identities after ensuring the census has already omitted conflicting
    # owner records. The original report and conflicts remain untouched and are
    # returned as explicit development diagnostics below.
    closure_report = ({**report, "conflicts": []}
                      if allow_quarantined_conflicts and conflicts else report)
    closure = validate_reference_closure(member_graph, candidate_graphs, closure_report)
    if closure["unresolved_closable"]:
        raise ReferencePublicationError("candidate reference closure has unresolved closable references")
    result = {
        "graphs": candidate_graphs,
        "retained_graphs": retained_graphs,
        "closure": closure,
        "coverage_report": report,
    }
    if allow_quarantined_conflicts:
        conflict_diagnostics = []
        conflicts_by_identity = {}
        for conflict in report.get("conflicts", []):
            fields = sorted({item.get("field") for item in conflict.get("conflicts", [])
                             if item.get("field")})
            reason = "materially conflicting source observations"
            if fields:
                reason += " disagree on " + ", ".join(fields)
            diagnostic = {
                "reference_kind": conflict.get("reference_kind"),
                "canonical_iri": conflict.get("canonical_iri"),
                "reason": reason,
                "fields": fields,
            }
            conflict_diagnostics.append(diagnostic)
            conflicts_by_identity[(diagnostic["reference_kind"],
                                   diagnostic["canonical_iri"])] = diagnostic

        # Closure findings are edge-oriented. Consolidate them by referenced
        # identity for the local status report while preserving all source
        # paths. Conflicted identities are called quarantined, not incomplete
        # evidence, because their source evidence is contradictory.
        unresolved_by_identity = {}
        for item in closure["insufficient_evidence"]:
            key = (item["reference_kind"], item["target"])
            diagnostic = unresolved_by_identity.setdefault(key, {
                "reference_kind": key[0], "canonical_iri": key[1],
                "paths": [], "reason": item["reason"],
            })
            diagnostic["paths"].extend(item.get("paths", []))
            conflict = conflicts_by_identity.get(key)
            if conflict:
                diagnostic["reason"] = "owner identity quarantined: " + conflict["reason"]
        unresolved_references = sorted(
            ({**item, "paths": sorted(set(item["paths"]))}
             for item in unresolved_by_identity.values()),
            key=lambda item: (item["reference_kind"], item["canonical_iri"]),
        )
        result["development_status"] = {
            "authoritative": False,
            "reference_closure": "NOT authoritative / not complete",
            "quarantined_conflicts": conflict_diagnostics,
            "quarantined_conflict_count": len(conflict_diagnostics),
            "unresolved_references": unresolved_references,
            "unresolved_reference_count": len(unresolved_references),
        }
    return result


def build_reference_candidates(census: dict, *, member_graph: Graph,
                               previous_graphs: dict[str, Graph] | None = None) -> dict:
    """Transform, carry forward and validate every authoritative owner graph.

    ``previous_graphs`` must contain only locally hash-verified clean payloads.
    Current identities are replaced as a whole; absent historical identities
    are retained so endpoint omissions cannot erase owner descriptions. Any
    material census conflict continues to block the entire candidate set.
    """
    return _build_reference_candidates(
        census, member_graph=member_graph, previous_graphs=previous_graphs,
        allow_quarantined_conflicts=False,
    )


def build_development_reference_candidates(census: dict, *, member_graph: Graph) -> dict:
    """Build local candidates while omitting every materially conflicted owner.

    This API is only for disposable local development. It deliberately carries
    no previous owner descriptions, so an earlier local graph cannot preserve
    an owner description for a newly quarantined identity.
    """
    return _build_reference_candidates(
        census, member_graph=member_graph, previous_graphs=None,
        allow_quarantined_conflicts=True,
    )
