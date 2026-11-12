"""Evaluation-only assertion scorer over independent live captures and saved output.

Never imports/executes the kernel, supplies transport data, or modifies evidence.
Role-specific expected RDF assertions are scoring logic, not an application
validator/projector. All expected object values come from independent raw pages.
"""

import argparse
from datetime import date, datetime
import json
from pathlib import Path

if not __debug__:
    raise SystemExit("Independent assertion scoring must not run with Python -O")

A = "https://data.oireachtas.ie/ontology#"
M = "https://data.oireachtas.ie/ontology/members#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
DCT = "http://purl.org/dc/terms/temporal"
DCAT = "http://www.w3.org/ns/dcat#"
SKOS = "http://www.w3.org/2004/02/skos/core#prefLabel"
HOUSES = "https://data.oireachtas.ie/graph/houses"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def uri(value):
    return {"type": "uri", "value": value}


def raw_quads(oracle):
    facts = {}
    def add(s, p, o, g):
        fact = {"subject": s, "predicate": uri(p), "object": o, "graph": g}
        facts[canonical(fact)] = fact
    for section in oracle["sections"].values():
        assert section["complete"] is True
        for page in section["pages"]:
            for row in page["raw_typed_response"]["results"]["bindings"]:
                if "predicate" in row and "object" in row:
                    for subject, graph in [("resource", "graph"), ("term", "graph"),
                                           ("membership", "graph"), ("member", "graph"),
                                           ("range", "rangeGraph"), ("range", "graph"),
                                           ("period", "graph")]:
                        if subject in row and graph in row:
                            add(row[subject], row["predicate"]["value"], row["object"], row[graph])
                            break
                    else:
                        if "committee" in row and "range" not in row:
                            # Resolver discovery pins this owner GRAPH in its query;
                            # the separate full audit also returns explicit graph bindings.
                            owner_graph = "https://data.oireachtas.ie/graph/committees"
                            assert "GRAPH <" + owner_graph + ">" in section["query_without_page_clause"]
                            add(row["committee"], row["predicate"]["value"], row["object"], uri(owner_graph))
                        else:
                            raise AssertionError(f"Unrecognised independent quad projection: {row.keys()}")
                if {"member", "membership", "memberGraph"} <= row.keys():
                    add(row["member"], M + "hasMembersMembership", row["membership"], row["memberGraph"])
                if {"membership", "range", "rangeLinkGraph"} <= row.keys():
                    add(row["membership"], M + "hasMembershipDateRange", row["range"], row["rangeLinkGraph"])
    return list(facts.values())


def expected_witness(role, witness, quads, selection):
    used = {}
    intervals = []
    def pick(s, p, graph, object_=None):
        found = [f for f in quads if f["subject"] == uri(s) and f["predicate"] == uri(p)
                 and f["graph"] == uri(graph) and (object_ is None or f["object"] == object_)]
        for f in found:
            used[canonical(f)] = f
        return [f["object"] for f in found]
    def one(s, p, graph):
        found = pick(s, p, graph)
        assert len(found) == 1, (s, p, graph, found)
        return found[0]["value"]
    def type_(s, type_, graph):
        assert pick(s, RDF, graph, uri(type_)) == [uri(type_)]
    def interval(resource, graph, label, *, house=False, committee=False):
        range_ = one(resource, DCT if house else M + ("hasCommitteeDateRange" if committee else "hasMembershipDateRange"), graph)
        type_(range_, "http://purl.org/dc/terms/PeriodOfTime" if house else M + "DateRange", graph)
        starts = pick(range_, DCAT + "startDate" if house else M + "StartDate", graph)
        ends = pick(range_, DCAT + "endDate" if house else M + "EndDate", graph)
        assert len(starts) == 1 and len(ends) <= 1
        start, end = starts[0], ends[0] if ends else None
        def day(term):
            return datetime.fromisoformat(term["value"].replace("Z", "+00:00")).date()
        active = day(start) <= date(2026, 11, 11) and (end is None or date(2026, 11, 11) <= day(end))
        intervals.append({"role": label, "resource": resource, "range": range_,
                          "start": start, "end": end, "graph": graph, "currentAtAsOf": active})
        return active
    bindings = witness["bindings"]
    member = bindings["Member"]["iri"]
    membership = bindings["membership" if role == "K" else "parliamentaryMembership"]["iri"]
    # Discover the authoritative graph via asserted Member code, not result metadata.
    code_facts = [f for f in quads if f["subject"] == uri(member) and f["predicate"] == uri(A + "memberCode")]
    assert len(code_facts) == 1
    graph = code_facts[0]["graph"]["value"]
    from urllib.parse import quote
    assert graph == "https://data.oireachtas.ie/graph/member/" + quote(code_facts[0]["object"]["value"], safe="")
    type_(member, A + "Member", graph)
    one(member, A + "memberCode", graph)
    assert pick(member, M + "hasMembersMembership", graph, uri(membership)) == [uri(membership)]
    type_(membership, M + ("CommitteeMembership" if role == "K" else "DailMembership"), graph)
    active = interval(membership, graph, "membership" if role == "K" else "parliamentaryMembership")
    target = one(membership, M + ("isCommitteeMembershipOf" if role == "K" else "isRepresentativeFrom"), graph)
    assert target == selection["committee" if role == "K" else "constituency"]
    owner_graph = "https://data.oireachtas.ie/graph/" + ("committees" if role == "K" else "constituencies")
    type_(target, M + ("Committee" if role == "K" else "DailConstituency"), owner_graph)
    assert pick(target, SKOS, owner_graph)
    term = one(target, M + ("committeeInHouseTerm" if role == "K" else "constituencyInHouseTerm"), owner_graph)
    assert witness["role"] == role
    assert bindings == {
        "Member": {"kind": "Member", "iri": member},
        "membership" if role == "K" else "parliamentaryMembership": {
            "kind": "CommitteeMembership" if role == "K" else "ParliamentaryMembership", "iri": membership},
        "term": {"kind": "HouseTerm", "iri": term},
        "committee" if role == "K" else "constituency": {
            "kind": "Committee" if role == "K" else "DailConstituency", "iri": target}}
    if role == "K":
        active = interval(target, owner_graph, "owner", committee=True) and active
    else:
        assert one(membership, M + "inHouseTerm", graph) == term
    houses = [house for house in ("Dail", "Seanad") if any(
        f["subject"] == uri(term) and f["predicate"] == uri(RDF)
        and f["object"] == uri(A + house + "Term") and f["graph"] == uri(HOUSES) for f in quads)]
    assert len(houses) == 1 and (role != "R" or houses == ["Dail"])
    type_(term, A + houses[0] + "Term", HOUSES)
    assert one(term, A + "termOf", HOUSES) == "https://data.oireachtas.ie/house/" + houses[0].lower()
    active = interval(term, HOUSES, "term", house=True) and active
    return set(used), intervals, active, member, membership


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text())
    baseline = json.loads(args.baseline.read_text())
    report = baseline["report"]
    assert oracle["completion"]["positive_evidence_gate_satisfied"] is True
    assert report["status"] == "answer", report.get("error")
    assert oracle["endpoint"] == baseline["endpoint"]
    selections = {s["role"]: s for s in baseline["original"]["requiredSelections"]}
    assert selections["K"]["committee"] == oracle["parameters"]["committee_resource"]
    assert selections["R"]["constituency"] == oracle["parameters"]["constituency_resource"]
    quads = raw_quads(oracle)
    scores = []
    qualifying = {}
    expected_relationships = {}
    for role in ("K", "R"):
        candidates = oracle["candidates"][role + "_all_exact_path_candidates"]
        # Oracle explicitly enumerates all candidate relationship resources first.
        expected_relationships[role] = {item["membership_iri"] for item in candidates}
        actual_relationships = set()
        qualifying[role] = set()
        for witness in report["validatedWitnesses"][role]:
            expected, intervals, active, member, membership = expected_witness(role, witness, quads, selections[role])
            actual_relationships.add(membership)
            actual = {canonical(f) for f in witness["facts"]}
            entry = {"role": role, "member": member, "membership": membership,
                     "facts": len(expected), "factsExact": actual == expected,
                     "intervals": len(intervals), "intervalsExact": witness["intervals"] == intervals,
                     "active": active}
            scores.append(entry)
            if active:
                qualifying[role].add((member, membership))
        assert actual_relationships == expected_relationships[role]
    expected_members = sorted({m for m, _ in qualifying["K"]} & {m for m, _ in qualifying["R"]})
    expected_pairs = {(m, k, r) for m, k in qualifying["K"] for n, r in qualifying["R"] if m == n}
    actual_pairs = set()
    for pair in report["answer"]["witnesses"]:
        by_role = {w["role"]: w for w in pair}
        assert set(by_role) == {"K", "R"}
        k, r = by_role["K"], by_role["R"]
        assert k in report["validatedWitnesses"]["K"] and r in report["validatedWitnesses"]["R"]
        assert k["bindings"]["Member"] == r["bindings"]["Member"]
        actual_pairs.add((k["bindings"]["Member"]["iri"], k["bindings"]["membership"]["iri"], r["bindings"]["parliamentaryMembership"]["iri"]))
    result = {"expectedMembers": expected_members, "actualMembers": report["answer"]["members"],
              "oracleMembersExact": expected_members == oracle["candidates"]["expected_members_intersection"],
              "membersExact": expected_members == report["answer"]["members"],
              "allValidatedRelationshipsCovered": True,
              "witnessPairsExact": actual_pairs == expected_pairs and len(report["answer"]["witnesses"]) == len(expected_pairs),
              "expectedWitnessPairs": [list(x) for x in sorted(expected_pairs)],
              "assertions": scores,
              "scopeExact": all(report["answer"][key] == baseline["original"]["answer"][key] for key in ("shape", "unit", "scope")),
              "asOfExact": report["answer"]["asOf"] == "2026-11-11"}
    result["passed"] = (all(result[key] for key in ("oracleMembersExact", "membersExact", "witnessPairsExact", "scopeExact", "asOfExact"))
                        and all(x["factsExact"] and x["intervalsExact"] for x in scores))
    with args.output.open("x") as saved:
        json.dump(result, saved, indent=2, ensure_ascii=False)
        saved.write("\n")
    print(json.dumps({"passed": result["passed"], "validatedWitnessesScored": len(scores),
                      "factsScored": sum(x["facts"] for x in scores),
                      "intervalsScored": sum(x["intervals"] for x in scores)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
