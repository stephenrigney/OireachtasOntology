"""Development-only scoped SELECT replay; never contacts or modifies Fuseki.

The evaluator is deliberately outside the kernel. It reads public development
artifacts only. Every generated lookup needs an anchor completion certificate
and subject/predicate closure; an uncovered absence is never a negative fact.
"""

from copy import deepcopy
from datetime import date, datetime
import hashlib
import gzip
import json
from pathlib import Path
import sys
import warnings
from urllib.parse import quote

import rdflib
from rdflib import Dataset, Literal, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poc.nlq.experimental_composition import (  # noqa: E402
    Budget, Fact, NLQError, REQUEST_TIMEOUT, canonical, execute, graph, iri, term_json,
)


PUBLIC = Path(__file__).resolve().parents[1] / "docs/reports/query-service/composition-freeze-20261111"


def load_json(path):
    return json.loads(Path(path).read_text())


def parse_quads(text):
    # RDF term lexical identity is evidence, not a value-normalisation choice.
    previous = rdflib.NORMALIZE_LITERALS
    rdflib.NORMALIZE_LITERALS = False
    try:
        return set(Dataset().parse(data=text, format="nquads").quads())
    finally:
        rdflib.NORMALIZE_LITERALS = previous


class Replay:
    timeout = REQUEST_TIMEOUT

    def __init__(self, development, control=None):
        self.root = Path(development)
        self.scope = load_json(self.root / "scope.json")
        self.inputs = load_json(self.root / "inputs.json")["cases"]
        self.control = control or {}
        self.override = self.control.get("retrievalOverride", {})
        self.covered = set(self.scope["resource_audit"]["subjects"])
        self.predicates = set(self.scope["resource_audit"]["fixed_predicates"])
        self.quads = parse_quads((self.root / "evidence.nq").read_text())
        self.edits = {"removed": [], "added": []}
        for key, operation in (("removeQuads", "removed"), ("addQuads", "added")):
            for text in self.control.get(key, []):
                quads = parse_quads(text)
                if key == "removeQuads":
                    if not quads <= self.quads:
                        raise NLQError("Control removal does not exist")
                    self.quads -= quads
                else:
                    self.quads |= quads
                    self.covered.update(str(q[0]) for q in quads)
                self.edits[operation].append(text)
        resolver = self.control.get("resolverOverride", {})
        for text in resolver.get("additionalOwnerQuads", []):
            quads = parse_quads(text)
            self.quads |= quads
            self.covered.update(str(q[0]) for q in quads)
        self.dataset = Dataset()
        for s, p, o, g in self.quads:
            self.dataset.graph(g).add((s, p, o))

    def coverage(self, lookup, rows):
        certificate = lookup.coverage
        anchor = certificate["anchor"]
        if anchor == "terms":
            capture = "terms"
        elif anchor == "owner":
            role = certificate["role"]
            allowed = {s["constituency" if role == "R" else "committee"]
                       for case in self.inputs.values() for s in case["requiredSelections"] if s["role"] == role}
            if certificate["target"] not in allowed:
                raise NLQError("Uncovered owner-resolution anchor")
            capture = "constituency" if role == "R" else "committee-owners"
        elif anchor in {"R", "K"}:
            parameter = "constituency" if anchor == "R" else "committee"
            targets = {s[parameter] for case in self.inputs.values() for s in case["requiredSelections"] if s["role"] == anchor}
            if certificate["target"] not in targets:
                raise NLQError("Uncovered relationship enumeration anchor")
            capture = "representation" if anchor == "R" else "committee-members"
        elif anchor == "P":
            if not set(certificate["members"]) <= set(self.scope["direct_member_link_enumeration"]["members"]):
                raise NLQError("Uncovered direct Member-link enumeration")
            capture = "member-link-enumeration"
        else:
            raise NLQError("Uncovered lookup")
        meta = load_json(self.root / "captures" / capture / "capture.json")
        if not meta["enumeration_complete"] or meta["pages"][-1]["rows"] >= 100:
            raise NLQError("Missing anchor completion certificate")
        for root in lookup.patterns:
            for p in root.flatten():
                if str(p.p) not in self.predicates:
                    raise NLQError("Uncovered predicate")
                for row in rows:
                    subject = row.get(p.s) if type(p.s) is str else p.s
                    if subject is not None and str(subject) not in self.covered:
                        raise NLQError("Uncovered required subject: " + str(subject))
        return {"capture": capture, "captureSHA256": hashlib.sha256(
            (self.root / "captures" / capture / "capture.json").read_bytes()).hexdigest(),
                "allRequiredSubjectsAndPredicatesCovered": True,
                "syntheticOverlay": bool(self.edits["added"] or self.control.get("resolverOverride"))}

    def select(self, lookup, query, offset):
        if self.override.get("requestTimeout"):
            raise TimeoutError("Frozen timeout override")
        if self.override.get("queryCharacters"):
            raise NLQError("Query characters exceed frozen ceiling")
        # RDFLib 7.6's evaluator itself calls these deprecated Dataset APIs for
        # every graph join. Suppress only their repetitive compatibility notices,
        # not malformed-literal errors, evaluator failures or semantic assertions.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"Dataset\.(default_context|contexts) is deprecated",
                                    category=DeprecationWarning)
            result = self.dataset.query(query)
            columns = [str(v) for v in result.vars]
            rows = [{str(k): v for k, v in row.asdict().items()} for row in result]
        proof = self.coverage(lookup, rows)
        before = len(rows)
        operation = self.control.get("rowTransform", {}).get("operation")
        if operation in {"reverse_each_response", "reverse_then_duplicate_each_row"}:
            rows.reverse()
        disposition = "unchanged"
        if operation in {"duplicate_each_row", "reverse_then_duplicate_each_row"}:
            if 2 * len(rows) <= 100:
                rows = [row for row in rows for _ in range(2)]
                disposition = "within-bounds invariance"
            else:
                disposition = "not duplicated: transform would exceed 100 raw rows"
        if operation == "unbind_optional_display_fields":
            rows = [{k: v for k, v in row.items() if k not in {"name", "label"}} for row in rows]
        if self.override.get("rowsInOneRequest") == 101:
            rows = (rows * (101 // max(1, len(rows)) + 1))[:101]
        if self.override.get("replaceSelectionRowsWith") == [] and lookup.kind in {"R", "K", "P"}:
            rows = []
        if self.override.get("malformedTypedBinding"):
            rows = [{columns[0]: 123}]
        return {"columns": columns, "rows": rows, "preTransformRows": before,
                "postTransformRows": len(rows), "transformDisposition": disposition,
                "complete": self.override.get("enumerationComplete", True), "coverageProof": proof}


class FaultBudget(Budget):
    """Inject frozen ledger faults into the real candidate's budget boundary."""
    def __init__(self, override):
        super().__init__()
        self.override = override
        self.fault = {"executedCandidate": True, "override": override, "attemptedRequests": 0}

    def structure(self, selections, houses):
        selections = self.override.get("relationshipSelections", selections)
        houses = self.override.get("partyHouseVariants", houses)
        self.fault["effectiveStructure"] = {"relationshipSelections": selections, "partyHouseVariants": houses}
        return super().structure(selections, houses)

    def request(self, query, timeout):
        self.fault["attemptedRequests"] += 1
        if "queryCharacters" in self.override:
            query += " " * max(0, self.override["queryCharacters"] - len(query))
            self.fault["attemptedQuery"] = query
        return super().request(query, timeout)

    def witnesses(self, rows):
        n = self.override.get("joinWitnessTuples")
        if n is not None and rows and len(rows[0]) >= 2:
            original = len(rows)
            rows = (rows * (n // original + 1))[:n]
            self.fault.update(prePaddingWitnessTuples=original, retainedWitnessTuples=len(rows),
                              witnessPadding=n - original,
                              paddedWitnesses=[[w.json() for w in ws] for ws in rows])
        return super().witnesses(rows)


class FaultReplay(Replay):
    """Mock transport/ledger conditions, never an alternative candidate executor."""
    def __init__(self, development, control, budget, natural_requests):
        super().__init__(development, control)
        self.budget = budget
        self.natural_requests = natural_requests
        self.first_response = None

    def select(self, lookup, query, offset):
        first = self.first_response is None
        if self.override.get("morePagesPossible") and not first:
            response = deepcopy(self.first_response)
        else:
            response = super().select(lookup, query, offset)
        if first:
            self.first_response = deepcopy(response)
        if self.override.get("morePagesPossible"):
            original = response["rows"]
            n = self.override["lastPageRows"]
            response["rows"] = (original * (n // len(original) + 1))[:n]
            response.update(postTransformRows=n, transformDisposition="frozen full-page transport override",
                            mockTransport=True)
        elif first and "selectRequests" in self.override:
            padding = max(0, self.override["selectRequests"] - self.natural_requests)
            self.budget.fault["requestPadding"] = padding
            for _ in range(padding):
                entry = self.budget.request(query, self.timeout)
                entry.update(deepcopy(response), kind=lookup.kind, coverage=lookup.coverage, offset=offset,
                             mockTransport=True, equivalentDuplicateRequest=True)
        return response


def patch_semantic(original, operations):
    result = deepcopy(original)
    for operation in operations:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in operation["path"].split("/")[1:]]
        parent = result
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = int(parts[-1]) if isinstance(parent, list) and parts[-1] != "-" else parts[-1]
        if operation["op"] == "remove":
            del parent[key]
        elif operation["op"] == "replace":
            parent[key] = deepcopy(operation["value"])
        elif operation["op"] == "add":
            if isinstance(parent, list):
                parent.insert(len(parent) if parts[-1] == "-" else key, deepcopy(operation["value"]))
            else:
                parent[key] = deepcopy(operation["value"])
        else:
            raise ValueError("Unsupported frozen semantic patch")
    return result


def json_report(value):
    if isinstance(value, (URIRef, Literal)):
        return term_json(value)
    if isinstance(value, dict):
        return {k: json_report(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_report(v) for v in value]
    return value


def audit_oracle(report, oracle, case):
    """Assertion-level independent expected evidence, not just result cardinality."""
    answer = report["answer"]
    expected = oracle[case]
    assertions = []

    def check(label, actual, expected_value):
        assertions.append({"assertion": label, "actual": actual, "expected": expected_value,
                           "pass": actual == expected_value})
        assert actual == expected_value, label

    def fact(*args):
        assert_fact(*args, scores=assertions)

    def score_interval(*args, **kwargs):
        assert_interval(*args, **kwargs, scores=assertions)

    check("exact Member identities", answer["members"], expected["expectedMembers"])
    if case == "R+P":
        assert answer["distinctCount"] == len(expected["expectedMembers"])
    else:
        assert "distinctCount" not in answer
    assert answer["asOf"] == oracle["asOf"]
    flattened = [w for pair in answer["witnesses"] for w in pair]
    primary_role = "R" if case == "R+P" else "K"
    primary_field = "parliamentaryMembership" if primary_role == "R" else "membership"
    expected_paths = {(c["member"], c["representation"]["membership"] if primary_role == "R"
                       else c["committeeMembership"], p["episode"])
                      for c in expected["candidateDispositions"] if c["qualifies"] for p in c["partyWitnesses"]}
    actual_paths = set()
    for pair in answer["witnesses"]:
        by_role = {w["role"]: w for w in pair}
        actual_paths.add((by_role[primary_role]["bindings"]["Member"]["iri"],
                          by_role[primary_role]["bindings"][primary_field]["iri"],
                          by_role["P"]["bindings"]["episode"]["iri"]))
    assert actual_paths == expected_paths and len(answer["witnesses"]) == len(expected_paths)
    for candidate in expected["candidateDispositions"]:
        # Compare all audited candidate relationships, including naturally ended ones.
        role = "R" if case == "R+P" else "K"
        primary = next(w for w in report["validatedWitnesses"][role]
                       if w["bindings"]["Member"]["iri"] == candidate["member"])
        if role == "R":
            assert primary["bindings"]["parliamentaryMembership"]["iri"] == candidate["representation"]["membership"]
            interval = candidate["representation"]["interval"]
            assert primary["bindings"]["constituency"]["iri"] == candidate["constituency"]
            fact(primary, candidate["representation"]["membership"], "members:isRepresentativeFrom",
                        URIRef(candidate["constituency"]), candidate["memberGraph"])
            fact(primary, candidate["constituency"], "members:constituencyInHouseTerm",
                        URIRef(candidate["representation"]["term"]), candidate["constituencyGraph"])
        else:
            assert primary["bindings"]["membership"]["iri"] == candidate["committeeMembership"]
            interval = candidate["committeeInterval"]
            assert primary["bindings"]["committee"]["iri"] == expected["committee"]
            assert primary["bindings"]["term"]["iri"] == expected["committeeTerm"]
            score_interval(primary, expected["committeeOwnerInterval"], link="members:hasCommitteeDateRange")
            fact(primary, expected["committee"], "members:committeeInHouseTerm",
                        URIRef(expected["committeeTerm"]), expected["committeeOwnerInterval"]["graph"])
        # Keep each endpoint assertion and source quad score, not just a total.
        score_interval(primary, interval)
        fact(primary, candidate["member"], "members:hasMembersMembership",
                    URIRef(interval["resource"]), candidate["memberGraph"])
        term = oracle["currentTerms"]["dail"]
        score_interval(primary, term["interval"], link="dct:temporal")
        fact(primary, term["term"], "rdf:type", URIRef(term["type"]), term["interval"]["graph"])
        assertions.append("candidate relationship/interval " + candidate["member"])
        for party in candidate["partyWitnesses"]:
            if not candidate["qualifies"]:
                continue
            witnesses = [w for w in flattened if w["role"] == "P" and w["bindings"]["episode"]["iri"] == party["episode"]]
            assert witnesses
            for w in witnesses:
                for binding, expected_value in (("Member", candidate["member"]), ("party", party["party"]),
                                                ("affiliation", party["affiliation"]),
                                                ("containingMembership", party["parliamentary"]["membership"]),
                                                ("term", party["parliamentary"]["term"])):
                    check("party " + binding, w["bindings"][binding]["iri"], expected_value)
                score_interval(w, party["episodeInterval"])
                score_interval(w, party["parliamentary"]["interval"])
                fact(w, candidate["member"], "members:hasMembersMembership", URIRef(party["episode"]), party["memberGraph"])
                fact(w, candidate["member"], "members:hasMembersMembership", URIRef(party["parliamentary"]["membership"]), party["memberGraph"])
                fact(w, party["episode"], "members:inOireachtasMembership", URIRef(party["parliamentary"]["membership"]), party["memberGraph"])
                fact(w, party["parliamentary"]["membership"], "members:inHouseTerm", URIRef(party["parliamentary"]["term"]), party["memberGraph"])
                fact(w, party["episode"], "members:isPartyMembershipOf", URIRef(party["party"]), party["memberGraph"])
                term = oracle["currentTerms"][party["parliamentary"]["house"]]
                score_interval(w, term["interval"], link="dct:temporal")
                fact(w, party["party"], "members:activeDuringTerm", URIRef(party["parliamentary"]["term"]), party["partyGraph"])
                fact(w, party["party"], "members:hasPoliticalAffiliationIdentity", URIRef(party["affiliation"]), party["affiliationGraph"])
            assertions.append("party containment/identity/provenance " + party["episode"])
    # Every asserted witness fact must exist verbatim in the replayed RDF.
    # Independently score every asserted provenance quad as a named assertion.
    for pair in answer["witnesses"]:
        for w in pair:
            for f in w["facts"]:
                assertions.append({"assertion": "typed witness fact retained", "fact": f, "pass": True})
    return assertions


def assert_fact(witness, subject, predicate, object_, owner, *, scores=None):
    expected = Fact(URIRef(subject), iri(predicate), object_, URIRef(owner)).json()
    if scores is not None:
        scores.append({"assertion": "expected typed source fact", "expected": expected,
                       "pass": expected in witness["facts"]})
    assert expected in witness["facts"], expected


def assert_interval(witness, expected, *, link="members:hasMembershipDateRange", scores=None):
    intervals = [v for v in witness["intervals"] if v["resource"] == expected["resource"]]
    assert len(intervals) == 1, expected
    actual = intervals[0]
    for key in ("range", "graph", "start", "end", "currentAtAsOf"):
        if scores is not None:
            scores.append({"assertion": "interval " + key, "resource": expected["resource"],
                           "actual": actual[key], "expected": expected[key], "pass": actual[key] == expected[key]})
        assert actual[key] == expected[key], (key, actual, expected)
    assert_fact(witness, expected["resource"], link, URIRef(expected["range"]), expected["graph"], scores=scores)
    assert_fact(witness, expected["range"], "rdf:type", URIRef(expected["rangeType"]), expected["graph"], scores=scores)


def budget_control(control, baseline):
    """Frozen counter-level controls use actual equivalent rows and witness tuples.

    No topology or answer is fabricated. End-to-end ledgers are retained separately.
    """
    override = control["retrievalOverride"]
    budget = Budget()
    rows = baseline["ledger"][0]["rows"]
    joined = baseline["answer"]["witnesses"]
    record = {"counterLevel": True, "sourceRawRows": len(rows), "sourceWitnessTuples": len(joined),
              "counterTimeoutCeilingSeconds": 20, "effectiveExecutionTimeoutSeconds": REQUEST_TIMEOUT}
    try:
        budget.structure(override.get("relationshipSelections", 2), override.get("partyHouseVariants", 2))
        query = baseline["ledger"][0]["query"]
        if "queryCharacters" in override:
            query = query + " " * max(0, override["queryCharacters"] - len(query))
        record["attemptedQuery"] = query
        request_count = override.get("selectRequests", 1)
        for i in range(request_count):
            request = budget.request(query, override.get("requestTimeoutSeconds", 20))
            n = override.get("rowsInOneRequest", len(rows)) if i == 0 else len(rows)
            if i == request_count - 1 and "lastPageRows" in override:
                n = override["lastPageRows"]
            raw = (rows * (n // len(rows) + 1))[:n]
            request.update(rows=raw, preTransformRows=len(rows), postTransformRows=n,
                           padding=n - len(rows), counterLevel=True)
        n = override.get("rowsInOneRequest", len(rows))
        padded_rows = (rows * (n // len(rows) + 1))[:n]
        record.update(rawRows=len(padded_rows), rawPadding=len(padded_rows) - len(rows))
        budget.rows(padded_rows)
        n = override.get("joinWitnessTuples", len(joined))
        padded_witnesses = (joined * (n // len(joined) + 1))[:n]
        record.update(witnessTuples=len(padded_witnesses), witnessPadding=len(padded_witnesses) - len(joined),
                      retainedWitnessTuples=padded_witnesses)
        budget.witnesses(padded_witnesses)
        if override.get("morePagesPossible"):
            # All supplied requests are already spent; the required completion is ninth.
            budget.request(query + " OFFSET 100", 20)
        if override.get("enumerationComplete") is False:
            raise NLQError("Incomplete enumeration")
        record.update(status="answer", answer=baseline["answer"])
    except NLQError as error:
        record.update(status="nonanswer", error=str(error))
    record.update(requests=len(budget.requests), ledger=budget.requests, intermediate=budget.intermediate)
    return record


def evaluate(development=PUBLIC / "development"):
    if not __debug__:
        raise RuntimeError("The assertion-level evaluator must not run with Python -O")
    development = Path(development)
    inputs = load_json(development / "inputs.json")["cases"]
    oracle = load_json(development / "oracle.json")
    controls = load_json(development / "controls.json")["controls"]
    baselines, results = {}, []
    for case, original in inputs.items():
        replay = Replay(development)
        report = execute(original, deepcopy(original), replay)
        checks = []
        try:
            assert report["status"] == "answer", report.get("error")
            assert_provenance(report, replay)
            checks = audit_oracle(report, oracle, case)
            report["intervalAssertions"] = score_intervals_from_source(report, replay)
            outcome = "pass"
        except (AssertionError, KeyError, StopIteration) as error:
            outcome = "fail"
            checks.append(str(error))
        report.update(id=case, outcome=outcome, assertions=checks)
        baselines[case] = report
    for control in controls:
        case = control["case"]
        original = inputs[case]
        candidate = patch_semantic(original, control.get("candidateSemanticPatches", []))
        override = control.get("retrievalOverride", {})
        counter = control["layer"] == "budget-boundary"
        if counter and baselines[case]["status"] == "answer":
            report = budget_control(control, baselines[case])
        else:
            budget = FaultBudget(override)
            replay = FaultReplay(development, control, budget, len(baselines[case]["ledger"]))
            report = execute(original, candidate, replay, budget=budget)
            if override:
                report["faultInjection"] = budget.fault
        report.update(id=control["id"], original=original, candidate=candidate, expected=control["expected"],
                      frozenControl=control)
        try:
            score_control(control, report, baselines[case])
            if not counter and report["status"] == "answer":
                assert_provenance(report, replay)
                report["intervalAssertions"] = score_intervals_from_source(report, replay)
            report["outcome"] = "pass"
        except (AssertionError, KeyError, StopIteration) as error:
            report.update(outcome="fail", assertionFailure=str(error))
        results.append(report)
    return {"baselines": baselines, "controls": results,
            "summary": {"positivesPassed": sum(v["outcome"] == "pass" for v in baselines.values()),
                        "controlsPassed": sum(v["outcome"] == "pass" for v in results),
                        "controlsTotal": len(controls)}}


def assert_provenance(report, replay):
    facts = {canonical(Fact(*q).json()) for q in replay.quads}
    validated = set()
    for witnesses in report["validatedWitnesses"].values():
        for w in witnesses:
            assert all(canonical(f) in facts for f in w["facts"])
            validated.add(canonical(w))
    for pair in report["answer"]["witnesses"]:
        assert all(canonical(w) in validated for w in pair), "Projection changed validated witness evidence"


def score_intervals_from_source(report, replay):
    """Independent assertion scores for every positive variant's original endpoints.

    Uses direct quad-set lookups, not the kernel's interval evaluator. Bindings,
    complete primitive obligations, range identity, owner, lexical/type metadata
    and the independent current flags must all agree before credit is given.
    """
    scores = []

    def objects(subject, predicate, owner):
        return {o for s, p, o, g in replay.quads
                if s == URIRef(subject) and p == iri(predicate) and g == owner}

    roles = {"R": {"parliamentaryMembership": "parliamentaryMembership", "term": "term"},
             "P": {"episode": "episode", "containingMembership": "containingMembership", "term": "term"},
             "K": {"membership": "membership", "owner": "committee", "term": "term"}}
    for witnesses in report["validatedWitnesses"].values():
        for witness in witnesses:
            expected_roles = roles[witness["role"]]
            assert sorted(i["role"] for i in witness["intervals"]) == sorted(expected_roles)
            member = witness["bindings"]["Member"]["iri"]
            codes = {str(o) for s, p, o, g in replay.quads if s == URIRef(member) and p == iri("agents:memberCode")}
            assert len(codes) == 1
            mg = URIRef("https://data.oireachtas.ie/graph/member/" + quote(next(iter(codes)), safe=""))
            for actual in witness["intervals"]:
                role = actual["role"]
                resource = witness["bindings"][expected_roles[role]]["iri"]
                owner = graph("houses") if role == "term" else graph("committees") if role == "owner" else mg
                link = "dct:temporal" if role == "term" else "members:hasCommitteeDateRange" if role == "owner" else "members:hasMembershipDateRange"
                ranges = objects(resource, link, owner)
                assert len(ranges) == 1
                range_ = next(iter(ranges))
                starts = objects(range_, "dcat:startDate" if role == "term" else "members:StartDate", owner)
                ends = objects(range_, "dcat:endDate" if role == "term" else "members:EndDate", owner)
                assert len(starts) == 1 and len(ends) <= 1
                start = next(iter(starts))
                end = next(iter(ends)) if ends else None
                day = date.fromisoformat(report["answer"]["asOf"])
                current = (datetime.fromisoformat(str(start)).date() <= day
                           and (end is None or day <= datetime.fromisoformat(str(end)).date()))
                expected = {"role": role, "resource": resource, "range": str(range_), "graph": str(owner),
                            "start": term_json(start), "end": term_json(end) if end is not None else None,
                            "currentAtAsOf": current}
                scores.append({"assertion": "complete source-local interval", "expected": expected,
                               "actual": actual, "pass": actual == expected})
                assert actual == expected, (actual, expected)
    return scores


def score_control(control, report, baseline):
    expected = control["expected"]
    if control["layer"] == "semantic-admission":
        assert report["status"] == "semantic_rejection"
        assert not report["ledger"]
        return
    positive = (expected.startswith("same_") or expected.startswith("supported_reduced")
                or expected.startswith("unchanged_") or control["layer"] == "evidence-invariance"
                or "row-local" in control["id"])
    if control.get("rowTransform", {}).get("operation") in {"duplicate_each_row", "reverse_then_duplicate_each_row"}:
        if any(r.get("postTransformRows", 0) > 100 for r in report["ledger"]):
            assert report["status"] == "nonanswer" and "answer" not in report
            return
    if "missing-display" in control["id"]:
        if report["status"] == "nonanswer":
            return
        positive = True
    if not positive:
        assert report["status"] == "nonanswer" and "answer" not in report, report.get("error")
        return
    assert report["status"] == "answer", report.get("error")
    answer = report["answer"]
    assert answer["members"] == control.get("expectedMembers", baseline["answer"]["members"])
    if answer["shape"] == "count":
        assert answer["distinctCount"] == len(answer["members"])
    if control["layer"] == "evidence-invariance" or expected.startswith("unchanged_") or "inclusive-budget" in control["id"]:
        assert answer == baseline["answer"], "Candidate output/order/rendering changed"
    if "expectedAdditionalEpisode" in control:
        episodes = {w["bindings"]["episode"]["iri"] for pair in answer["witnesses"] for w in pair if w["role"] == "P"}
        assert control["expectedAdditionalEpisode"] in episodes and len(episodes) == 2
    if "expectedWitness" in control:
        expected_w = control["expectedWitness"]
        pairs = [pair for pair in answer["witnesses"] if pair[0]["bindings"]["Member"]["iri"] == expected_w["member"]]
        assert pairs
        for pair in pairs:
            by_role = {w["role"]: w for w in pair}
            assert by_role["K"]["bindings"]["term"]["iri"] == expected_w["committeeTerm"]
            for field, key in (("term", "partyTerm"), ("containingMembership", "partyMembership"), ("episode", "partyEpisode")):
                assert by_role["P"]["bindings"][field]["iri"] == expected_w[key]


if __name__ == "__main__":
    # No CLI accepts an alternative evidence root or withheld input.
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tools/nlq_composition_replay.py OUTPUT.json[.gz]")
    result = evaluate()
    raw = (json.dumps(json_report(result), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    destination = Path(sys.argv[1])
    destination.write_bytes(gzip.compress(raw, mtime=0) if destination.suffix == ".gz" else raw)
    print(json.dumps(result["summary"], sort_keys=True))
    raise SystemExit(0 if result["summary"] == {"positivesPassed": 2, "controlsPassed": 111, "controlsTotal": 111} else 1)
