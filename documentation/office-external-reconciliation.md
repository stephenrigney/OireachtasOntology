# Phase 7 Tranche 4 — External office reconciliation CLI

`oir-etl reconcile offices` and `oir-etl reconcile office-external` are
separate workflows:

- `reconcile offices` reads Member source observations and reconciles them to
  reviewed **local** office identities. It uses the office-occurrence ledger
  and does not contact external identity services.
- `reconcile office-external` starts from the reviewed office registry and
  reconciles those enduring local `NamedOffice` identities to external
  identities. It does not read Member office observations, resolve Members,
  holdings, administrative units or source labels as local identities.

The external policy treats Wikidata/ISAD evidence as candidate or conflict
evidence, never as authority to change the local registry. A matching label,
office type, date or organisational relationship does not create an accepted
identity. Only an explicit version-controlled review decision can authorize a
same-enduring-office link. The CLI reads but never edits review decisions.
There are no review approvals supplied by this command.

The three existing local offices have explicit human-approved Wikidata decisions
in `reconciliation/office-external-decisions.json` (2026-10-05):

| Local office | Reviewed external office |
|---|---|
| Taoiseach (`o-000001`) | Wikidata Q191827 |
| Tánaiste (`o-000002`) | Wikidata Q1146214 |
| Minister for Finance (`o-000003`) | Wikidata Q4294945 |

Each item denotes a public office, not a current holder or appointment. Q191827's
predecessor relationship refers to the distinct pre-1937 office; it is not a
reason to conflate the two local identities. Q4294945 points to the distinct
Department of Finance item Q731336; that department item is not a sameAs target.
These are reviewed identities, not hard-coded lookup seeds or permission to
publish Wikidata's tenure, succession or department assertions locally. The
CLI never creates or edits a human decision.

The policy derives the replaceable graph from the registered stable office key:
`https://data.oireachtas.ie/graph/office/{office-key}/external-links`.
Only the office itself is the subject of its approved `owl:sameAs` assertion;
Wikidata labels, dates, succession facts, office holders and unit descriptions
are not copied into that graph.

## Scope fixture

The command normally considers all offices in the validated registry. `--fixture`
selects a strict subset by full local office IRI; every IRI must already be in
the registry. The fixture does not define or mint office identities:

```json
{
  "version": 1,
  "offices": [
    "https://data.oireachtas.ie/office/o-000003"
  ]
}
```

Duplicates, unknown IRIs and an empty scope fail closed. Scoped runs only
process their selected registry offices; `--all` forces reconciliation of all
offices in that selected scope, not offices outside it. Review decisions for
other offices in the same registry remain available for later runs.

## Offline fixture-backed operation

Offline mode requires both the scope fixture and a complete response fixture.
No network client is used, and `--publish` is forbidden:

```text
oir-etl reconcile office-external \
  --registry-file registries/ministerial-office-registry.json \
  --fixture data/fixtures/office-external-scope.json \
  --responses-file data/fixtures/office-external-responses.json \
  --review-file reconciliation/office-external-decisions.json \
  --reconciliation-state-file /tmp/oireachtasontology/office-external/reconciliation.sqlite \
  --output-nq /tmp/oireachtasontology/office-external/office-external-links.nq \
  --offline
```

The response fixture is a strict Wikidata fixture keyed by selected local office
IRI. `office_candidates` contains the policy's candidate-evidence arrays only
for selected offices with no review decision. `entities` contains only
accepted-QID verification responses needed by selected human decisions:

```json
{
  "wikidata": {
    "office_candidates": {
      "https://data.oireachtas.ie/office/o-000003": []
    },
    "entities": {}
  }
}
```

Every selected, undecided office needs a candidate entry, including an empty
array when there are no candidates. Unknown, out-of-scope or unrequested office
keys, malformed candidate evidence, duplicate candidate identities, missing
accepted-target responses, and unrequested entity responses fail before
reconciliation state is opened. The offline fixture is not a simulated service
outage. It must contain complete evidence for the requested operation.

The version-1 review file is keyed by full local office IRI and follows the
strict decision schema enforced by the external-office policy. A decision
records its review evidence and reason; an accepted decision names the full
canonical Wikidata entity IRI. The review file must exist and be supplied with
`--review-file` if it is not at the default path. No default acceptance is
inferred from the registry or fixture.

## Online operation and publication

Without `--offline`, the command uses the Wikidata client unless
`--responses-file` is supplied. Reconciliation state uses the same generic
`ReconciliationStore` and `--reconciliation-state-file` as the other external
reconciliation commands. `--all` requests a full pass over the selected office
scope.

Reconciliation without `--publish` updates only reconciliation operational
state and can write a deterministic N-Quads preview with `--output-nq`. Online
publication is explicitly opt-in:

```text
oir-etl reconcile office-external \
  --registry-file registries/ministerial-office-registry.json \
  --review-file reconciliation/office-external-decisions.json \
  --publish \
  --fuseki-gsp-url http://localhost:3030/oir/data \
  --fuseki-sparql-url http://localhost:3030/oir/query
```

`--publish` requires both Fuseki endpoints. The generic reconciliation engine
owns only each local office's external-link graph; it publishes approved
identity assertions, replaces that graph independently, and verifies the exact
whole graph after PUT. It does not write to the authoritative office,
administrative-unit, Member or Bill graphs. Store failure, candidate ambiguity
or external-service failure does not authorize clearing a previous accepted
graph. Only policy-validated explicit review decisions can drive reviewed
acceptance or revocation behavior.

The JSON summary reports the selected local office IRIs, reconciliation states,
unresolved offices, excluded-candidate count and number of graph replacements.
Exit status 1 indicates unresolved or retryable reconciliation results; input,
review, registry and state-integrity errors fail closed.
