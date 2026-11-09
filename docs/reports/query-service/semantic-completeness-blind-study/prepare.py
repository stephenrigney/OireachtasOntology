"""Pre-inference evidence and fixed semantic references/faults. No inference calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from run import HERE, ROOT, all_clear, compatibility, configuration, norm, save


def requirement(question, role, value, binding, phrase=None, polarity="positive", argument=None):
    def span(text):
        start = question.index(text)
        return {"start": start, "end": start + len(text)}
    return {"role": role, "value": value, "binding": binding, "polarity": polarity,
            "origin": "explicit" if phrase else "default", "evidence": [span(phrase)] if phrase else [],
            "argument": span(argument) if argument else None, "explanation": "Pre-model reference from independent expected semantics."}


def reference(case, catalogue=False):
    q, member = case["question"], None if catalogue else case["member"]
    r = lambda role, value, binding, **kw: requirement(q, role, value, binding, **kw)
    # Broad evidence boundaries are deliberate: references specify meaning, not segmentation.
    whole = q.rstrip("?.!")
    requirements = [r("operation", "count", "query", phrase=whole), r("target", "DailTerm", "count", phrase=whole),
        r("relationship", "member_recorded_dail_service" if member else "houses_typed_dail_terms", "member" if member else "source", phrase=whole),
        r("scope", "member_service" if member else "houses_catalogue", "query", phrase=whole),
        r("temporal", "unfiltered", "service" if member else "term"), r("aggregation", "count_distinct", "count", phrase=whole),
        r("coverage", "local_recorded", "source"), r("output", "count", "answer", phrase=whole)]
    if member:
        requirements.append(r("identity", "Member", "member", phrase=member, argument=member))
    if case["id"] == "S4":
        requirements.append(r("exclusion", "measure_membership_records", "count", phrase="I'm not asking how many membership rows there are", polarity="negative"))
    return {"requirements": requirements}


def main(pid):
    from poc.nlq.fuseki import FusekiQueryClient
    from poc.nlq.member_resolution import resolve_local_entity_label
    from copy import deepcopy
    config = configuration(pid)
    client = FusekiQueryClient(config["NLQ_FUSEKI_QUERY_URL"])
    evidence = {"observed_at": datetime.now(timezone.utc).isoformat(), "endpoint": config["NLQ_FUSEKI_QUERY_URL"],
                "candidates": {}, "queries": [], "purpose": "Independent read-only names, unfiltered term identities and catalogue; not model answers."}
    class Recorder:
        def query(self, query):
            result = client.query(query)
            evidence["queries"].append({"query": query, "result": result.raw_json})
            return result
    recorder = Recorder()
    for name in ["Mary Lou McDonald", "Simon Harris"]:
        resolution = resolve_local_entity_label("Member", name, recorder)
        evidence["candidates"][norm(name)] = {c.iri: c.label for c in resolution.candidates}
        assert len(resolution.candidates) == 1
        iri = resolution.candidates[0].iri
        recorder.query(f'''PREFIX members: <https://data.oireachtas.ie/ontology/members#>
SELECT DISTINCT ?term WHERE {{
 GRAPH ?g {{ <{iri}> members:hasMembersMembership ?membership .
 ?membership a members:DailMembership ; members:inHouseTerm ?term . }}
 FILTER(STRSTARTS(STR(?g), "https://data.oireachtas.ie/graph/member/"))
}} ORDER BY ?term''')
    # Discover the published Houses graph from the authoritative local query contract.
    from poc.nlq.stage_a import _contract_parts
    _, families = _contract_parts()
    houses = families["houses"]["iri"]
    recorder.query(f'''PREFIX agents: <https://data.oireachtas.ie/ontology#>
SELECT DISTINCT ?term WHERE {{ GRAPH <{houses}> {{ ?term a agents:DailTerm . }} }} ORDER BY ?term''')
    recorder.query('SELECT (COUNT(*) AS ?triples) (COUNT(DISTINCT ?g) AS ?graphs) WHERE { GRAPH ?g { ?s ?p ?o } }')
    client.close()
    save(HERE / "evidence.json", evidence)

    cases = json.loads((HERE / "cases.json").read_text())["cases"]
    references, faults = {}, []
    for case in cases:
        ref = reference(case, catalogue=case["member"] is None or case["id"] == "U5")
        assert compatibility(case["question"], ref, evidence["candidates"])["status"] == "admit"
        if case["expected"] == "supported":
            references[case["id"]] = ref
            for kind in ["target", "relationship", "attachment", "negation", "extra_output"]:
                bad = deepcopy(ref)
                if kind == "target":
                    next(r for r in bad["requirements"] if r["role"] == "target")["value"] = "membership_records"
                elif kind == "relationship":
                    next(r for r in bad["requirements"] if r["role"] == "relationship")["value"] = "shared_service"
                elif kind == "attachment":
                    next(r for r in bad["requirements"] if r["role"] == "relationship")["binding"] = "term"
                elif kind == "negation":
                    next(r for r in bad["requirements"] if r["role"] == "relationship")["polarity"] = "negative"
                else:
                    bad["requirements"].append(requirement(case["question"], "output", "identity", "answer"))
                faults.append({"id": case["id"] + "-" + kind, "case": case["id"], "kind": kind,
                               "candidate": {"interpretation": bad, "self_check": all_clear()}})
        else:
            faults.append({"id": case["id"] + "-omission", "case": case["id"], "kind": "omission",
                           "candidate": {"interpretation": ref, "self_check": all_clear()}})
    # Actual condition-attachment probe: same service-before-2020 condition attached to term.
    case = next(c for c in cases if c["id"] == "U3")
    bad = reference(case)
    temporal = next(r for r in bad["requirements"] if r["role"] == "temporal")
    temporal.update(requirement(case["question"], "temporal", "date_before", "term", phrase="began before 2020", argument="2020"))
    faults.append({"id": "U3-condition-attachment", "case": "U3", "kind": "condition_attachment",
                   "candidate": {"interpretation": bad, "self_check": all_clear()}})
    save(HERE / "references.json", {"purpose": "Pre-model expected supported semantics; not live interpretations", "references": references})
    save(HERE / "faults.json", {"purpose": "Frozen deliberate corruptions; not natural model outputs", "faults": faults})

    historical = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines()
    matches = {}
    for case in cases:
        matches[case["id"]] = [p for p in historical if p.endswith((".json", ".md", ".jsonl", ".py"))
            and (case["question"] in (ROOT/p).read_text(errors="replace")
                 or json.dumps(case["question"], ensure_ascii=True)[1:-1] in (ROOT/p).read_text(errors="replace"))]
    assert not any(matches.values()), matches
    save(HERE / "novelty.json", {"method": "Exact question text and JSON Unicode-escaped spelling against all baseline tracked JSON/JSONL/Markdown/Python; after authorship only",
        "files_considered": len(historical), "matches": matches,
        "limitations": "Does not prove conceptual novelty; author received no historical questions.",
        "cases_sha256": hashlib.sha256((HERE/"cases.json").read_bytes()).hexdigest()})


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]))
