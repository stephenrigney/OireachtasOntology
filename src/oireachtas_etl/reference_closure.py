"""Pre-publication and Fuseki closure checks for shared reference owners."""
from __future__ import annotations

from collections import defaultdict
import re
from urllib.parse import unquote

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from .config import COMMITTEES_GRAPH, CONSTITUENCIES_GRAPH, PARTIES_GRAPH
from .reference_coverage import MEMBER_REFERENCE_KINDS
from .transforms.common import MEMBERS
from .transforms.members import transform_member


MEMBER_GRAPH_PREFIX = "https://data.oireachtas.ie/graph/member/"
OWNER_SPEC = {
    "party": {
        "graph": "parties",
        "predicates": (MEMBERS.memberOfCollection, MEMBERS.isPartyMembershipOf),
        "classes": (MEMBERS.ParliamentaryParty,
                    MEMBERS.IndependentMemberCollection),
        "key": MEMBERS.partyCode,
        "term": MEMBERS.activeDuringTerm,
        "pattern": re.compile(
            r"^https://data\.oireachtas\.ie/ie/oireachtas/party/"
            r"(dail|seanad)/([1-9][0-9]*)/[^/]+$"),
    },
    "representation": {
        "graph": "constituencies",
        "predicates": (MEMBERS.isRepresentativeFrom,),
        "classes": (MEMBERS.DailConstituency, MEMBERS.SeanadPanel),
        "key": MEMBERS.representCode,
        "term": MEMBERS.constituencyInHouseTerm,
        "pattern": re.compile(
            r"^https://data\.oireachtas\.ie/ie/oireachtas/house/"
            r"(dail|seanad)/([1-9][0-9]*)/(constituency|panel)/[^/]+$"),
    },
    "committee": {
        "graph": "committees",
        "predicates": (MEMBERS.isCommitteeMembershipOf,),
        "classes": (MEMBERS.Committee,),
        "key": None,
        "term": MEMBERS.committeeInHouseTerm,
        "pattern": re.compile(
            r"^https://data\.oireachtas\.ie/ie/oireachtas/committee/"
            r"(dail|seanad)/([1-9][0-9]*)/[^/]+$"),
    },
}


def candidate_member_dataset(records: list[dict]) -> Graph:
    """Build the complete Member candidate dataset used by closure validation."""
    result = Graph()
    for wrapper in records:
        result += transform_member(wrapper)
    return result


def _source_paths(census_report: dict) -> dict[tuple[str, str], list[str]]:
    result: dict[tuple[str, str], list[str]] = defaultdict(list)
    for observation in census_report.get("observations", []):
        key = (observation.get("reference_kind"), observation.get("canonical_iri"))
        if key[1]:
            result[key].append(observation.get("json_pointer", ""))
    return result


def validate_reference_closure(member_graph: Graph,
                               owner_graphs: dict[str, Graph],
                               census_report: dict) -> dict:
    """Require every closable Member edge to resolve to a correct owner."""
    conflicts = census_report.get("conflicts", [])
    if conflicts:
        details = "; ".join(
            f"{item.get('reference_kind')} {item.get('canonical_iri')}"
            for item in conflicts)
        raise ValueError("reference census contains material conflicts: " + details)
    by_identity = {(item["reference_kind"], item["canonical_iri"]): item
                   for item in census_report.get("identities", [])}
    source_paths = _source_paths(census_report)
    report = {
        "references": 0,
        "closed": 0,
        "unresolved_closable": [],
        "insufficient_evidence": [],
        "malformed_observations": [],
        "member_owner_description_leaks": [],
    }
    seen: set[tuple[str, str, str]] = set()
    referenced_iris: set[str] = set()
    for kind in MEMBER_REFERENCE_KINDS:
        spec = OWNER_SPEC[kind]
        for predicate in spec["predicates"]:
            for subject, _predicate, target in member_graph.triples((None, predicate, None)):
                if not isinstance(target, URIRef):
                    report["unresolved_closable"].append({
                        "reference_kind": kind, "source": str(subject),
                        "target": str(target), "reason": "reference target is not an IRI"})
                    continue
                key = (kind, str(target), str(predicate))
                if key in seen:
                    continue
                seen.add(key)
                referenced_iris.add(str(target))
                report["references"] += 1
                identity = by_identity.get((kind, str(target)))
                for malformed in census_report.get("malformed_observations", []):
                    if (malformed.get("reference_kind") == kind
                            and malformed.get("canonical_iri") == str(target)):
                        report["malformed_observations"].append({
                            "reference_kind": kind, "source": str(subject),
                            "target": str(target),
                            "path": malformed.get("path"),
                            "reason": malformed.get("reason"),
                        })
                if identity is None or not identity.get("closable"):
                    reason = ("reference was not present in census evidence"
                              if identity is None else
                              "required owner fields are absent: "
                              + ", ".join(identity.get("missing_owner_fields", [])))
                    report["insufficient_evidence"].append({
                        "reference_kind": kind, "source": str(subject),
                        "target": str(target),
                        "paths": sorted(source_paths.get((kind, str(target)), [])),
                        "reason": reason,
                    })
                    continue

                owner = owner_graphs[spec["graph"]]
                if not _owner_description_is_valid(kind, target, owner,
                                                   predicate=predicate):
                    report["unresolved_closable"].append({
                        "reference_kind": kind, "source": str(subject),
                        "target": str(target),
                        "paths": sorted(source_paths.get((kind, str(target)), [])),
                        "reason": "candidate owner graph lacks the expected class, key or HouseTerm relation",
                    })
                    continue
                report["closed"] += 1

    owner_classes = {class_ for spec in OWNER_SPEC.values()
                     for class_ in spec["classes"]}
    owner_subjects = set(referenced_iris)
    owner_subjects.update(str(subject) for class_ in owner_classes
                          for subject in member_graph.subjects(RDF.type, class_))
    for owner_iri in sorted(owner_subjects):
        subject = URIRef(owner_iri)
        if next(member_graph.triples((subject, None, None)), None) is not None:
            report["member_owner_description_leaks"].append(owner_iri)

    if report["member_owner_description_leaks"]:
        raise ValueError("Member candidate graph contains owner descriptions: "
                         + ", ".join(report["member_owner_description_leaks"]))
    if report["unresolved_closable"]:
        raise ValueError("reference closure has unresolved closable targets: "
                         + "; ".join(
                             f"{item['reference_kind']} {item['target']} ({item['reason']})"
                             for item in report["unresolved_closable"]))
    return report


def _owner_description_is_valid(kind: str, target: URIRef, graph: Graph,
                                *, predicate) -> bool:
    target_text = str(target)
    spec = OWNER_SPEC[kind]
    match = spec["pattern"].fullmatch(target_text)
    if not match:
        return False
    term = URIRef(
        f"https://data.oireachtas.ie/ie/oireachtas/house/{match.group(1)}/{match.group(2)}")
    if (target, spec["term"], term) not in graph:
        return False
    if kind == "party":
        expected_types = ((MEMBERS.ParliamentaryParty,)
                          if predicate == MEMBERS.isPartyMembershipOf else
                          (MEMBERS.ParliamentaryParty,
                           MEMBERS.IndependentMemberCollection))
        if not any((target, RDF.type, class_) in graph for class_ in expected_types):
            return False
        codes = list(graph.objects(target, MEMBERS.partyCode))
        return (len(codes) == 1 and bool(str(codes[0]).strip())
                and unquote(target_text.rsplit("/", 1)[-1]) == str(codes[0]))
    if kind == "representation":
        expected_class = (MEMBERS.DailConstituency if match.group(3) == "constituency"
                          else MEMBERS.SeanadPanel)
        if (target, RDF.type, MEMBERS.Constituencies) not in graph:
            return False
        if (target, RDF.type, expected_class) not in graph:
            return False
        codes = list(graph.objects(target, MEMBERS.representCode))
        return (len(codes) == 1 and bool(str(codes[0]).strip())
                and unquote(target_text.rsplit("/", 1)[-1]) == str(codes[0]))
    return (target, RDF.type, MEMBERS.Committee) in graph


_SOURCE_TERM_EXPRESSION = {
    "party": (
        'CONCAT("https://data.oireachtas.ie/ie/oireachtas/house/", '
        'STRBEFORE(STRAFTER(STR(?target), "/ie/oireachtas/party/"), "/"), "/", '
        'STRBEFORE(STRAFTER(STRAFTER(STR(?target), "/ie/oireachtas/party/"), "/"), "/"))'
    ),
    "representation": (
        'CONCAT("https://data.oireachtas.ie/ie/oireachtas/house/", '
        'STRBEFORE(STRAFTER(STR(?target), "/ie/oireachtas/house/"), "/"), "/", '
        'STRBEFORE(STRAFTER(STRAFTER(STR(?target), "/ie/oireachtas/house/"), "/"), "/"))'
    ),
    "committee": (
        'CONCAT("https://data.oireachtas.ie/ie/oireachtas/house/", '
        'STRBEFORE(STRAFTER(STR(?target), "/ie/oireachtas/committee/"), "/"), "/", '
        'STRBEFORE(STRAFTER(STRAFTER(STR(?target), "/ie/oireachtas/committee/"), "/"), "/"))'
    ),
}


def reference_closure_query(kind: str) -> str:
    """Query one owner-edge kind independently for robust remote evaluation."""
    edge = {
        "party-collection": {
            "predicate": "members:memberOfCollection",
            "owner_graph": "parties",
            "owner_pattern": """?target rdf:type members:ParliamentaryMemberCollection ;
        members:partyCode ?code ; members:activeDuringTerm ?term .
        { ?target rdf:type members:ParliamentaryParty . FILTER (!STRENDS(STR(?target), "/Independent")) }
        UNION { ?target rdf:type members:IndependentMemberCollection . FILTER (STRENDS(STR(?target), "/Independent")) }""",
            "kind": "party",
            "key": True,
        },
        "party-membership": {
            "predicate": "members:isPartyMembershipOf",
            "owner_graph": "parties",
            "owner_pattern": """?target rdf:type members:ParliamentaryParty ;
        members:partyCode ?code ; members:activeDuringTerm ?term""",
            "kind": "party",
            "key": True,
        },
        "representation-dail": {
            "predicate": "members:isRepresentativeFrom",
            "owner_graph": "constituencies",
            "reference_filter": (
                '^https://data[.]oireachtas[.]ie/ie/oireachtas/house/'
                'dail/[1-9][0-9]*/constituency/[^/]+$'),
            "owner_pattern": """?target rdf:type members:Constituencies, members:DailConstituency ;
        members:representCode ?code ; members:constituencyInHouseTerm ?term""",
            "kind": "representation",
            "key": True,
        },
        "representation-seanad": {
            "predicate": "members:isRepresentativeFrom",
            "owner_graph": "constituencies",
            "reference_filter": (
                '^https://data[.]oireachtas[.]ie/ie/oireachtas/house/'
                'seanad/[1-9][0-9]*/panel/[^/]+$'),
            "owner_pattern": """?target rdf:type members:Constituencies, members:SeanadPanel ;
        members:representCode ?code ; members:constituencyInHouseTerm ?term""",
            "kind": "representation",
            "key": True,
        },
        "committee": {
            "predicate": "members:isCommitteeMembershipOf",
            "owner_graph": "committees",
            "owner_pattern": """?target rdf:type members:Committee ;
        members:committeeInHouseTerm ?term""",
            "kind": "committee",
            "key": False,
        },
    }
    try:
        spec = edge[kind]
    except KeyError as error:
        raise ValueError(f"unsupported reference closure kind: {kind}") from error

    kind_spec = OWNER_SPEC[spec["kind"]]
    pattern = kind_spec["pattern"].pattern.replace(r"\.", "[.]")
    # The expressions above mirror the path captures in each tested source-IRI
    # pattern. The owner graph must contain a matching HouseTerm, not just any IRI.
    owner_checks = [
        f'FILTER (REGEX(STR(?target), "{pattern}"))',
        f'FILTER (STR(?term) = {_SOURCE_TERM_EXPRESSION[spec["kind"]]})',
    ]
    if spec["key"]:
        owner_checks[0:0] = [
            'FILTER (isLiteral(?code) && STRLEN(STR(?code)) > 0)',
            'FILTER (STR(?code) = REPLACE(STR(?target), "^.*/", "") '
            '|| ENCODE_FOR_URI(STR(?code)) = REPLACE(STR(?target), "^.*/", ""))',
        ]
    else:
        owner_checks.insert(0, "FILTER (isIRI(?term))")
    return f"""PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?kind ?source ?target WHERE {{
  GRAPH ?memberGraph {{ ?source {spec['predicate']} ?target }}
  FILTER (STRSTARTS(STR(?memberGraph), "{MEMBER_GRAPH_PREFIX}")) .
  {f'FILTER (REGEX(STR(?target), "{spec["reference_filter"]}")) .' if spec.get("reference_filter") else ''}
  MINUS {{
    GRAPH <{REFERENCE_GRAPH_IRIS[spec['owner_graph']]}> {{
      {spec['owner_pattern']}
    }}
    {' '.join(owner_checks)}
  }}
  BIND("{kind}" AS ?kind)
}}"""


REFERENCE_GRAPH_IRIS = {
    "parties": PARTIES_GRAPH,
    "constituencies": CONSTITUENCIES_GRAPH,
    "committees": COMMITTEES_GRAPH,
}


def verify_reference_closure(client) -> None:
    kinds = ("party-collection", "party-membership", "representation-dail",
             "representation-seanad", "committee")
    failures = [row for kind in kinds
                for row in client.query(reference_closure_query(kind))]
    if failures:
        details = "; ".join(
            f"{row.get('kind', {}).get('value')} {row.get('target', {}).get('value')}"
            for row in failures)
        raise ValueError("post-publication graph-scoped reference closure failed: " + details)
