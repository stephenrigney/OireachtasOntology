# Phase 2 — Controlled semantic capability expansion

**Historical report:** Bill status and sponsorship associations below originally
used graph co-ownership. The subsequent Bill–LegislativeProcess Tranche 1
correction replaces that association with the explicit BillDelivery
`created_a_realization_of` / `forms_part_of` path; see the
[current legislation contract](../../reference/etl/legislation.md).

## Scope

This tranche extends the separate validated-plan compiler, not the Phase 1
browser/query route. It adds a small, evidence-backed query slice over the
accepted non-authoritative development bootstrap. It does not change ontology
or mapping meaning, ETL ownership, identifiers, bootstrap selection, or
publication behavior.

The query/schema contract is now `2.0.0`. That major bump corrects a stale Bill
lifecycle statement: the ETL emits
`?process eli-dl:latest_activity ?activity`, not
`?bill eli-dl:latest_activity ?activity`. The Bill and its process are
co-owned in the Bill's one named graph; there is no direct Bill-to-process RDF
edge. The plan semantic vocabulary is an additive `1.1.0` extension under its
existing major version `1`.

## Supported patterns

### Bills

- Bill identity is a resolved local Bill IRI; Bill lookup uses the reviewed
  `eli:work_type agents:Bill` designation and the Bill graph family (updated by
  Bill Classification Tranche 2; query/schema contract 2.10.0).
- `bill_title` returns the emitted English and/or Irish Bill Work `dct:title` values.
- `bill_year` uses the explicitly emitted `agents:legislativeYear` value.
- `bill_status` follows the co-owned `eli-dl:LegislativeProcess` and
  `eli-dl:process_status` path. It returns one of the reviewed English labels
  in the controlled process-status vocabulary; filters use the exact
  controlled value ID and resource IRI.
- `bill_sponsor` follows `had_participation` and
  `had_participant_person` in the Bill-owned graph. The single Bill cross-family
  evaluation case joins that exact Member IRI to the Member-owned graph by the
  documented same-resource-IRI rule.
- Bill graph patterns are usable only when the optional Bill graph is loaded.
  Graph scoping is restricted to the contract's local Bill graph route.

### Accepted Member OfficeHoldings

- The query reads only asserted `members:OfficeHolding` records in a
  Member-owned graph and requires their accepted `members:heldOffice` identity.
- A named-office filter binds one exact IRI resolved from the reviewed local
  NamedOffice registry. The answer query compares that IRI to `members:heldOffice`;
  it does not infer an office from raw observations or issue a second graph
  family join.
- `on` uses the emitted DateRange: `StartDate <= date` and, when present,
  `EndDate >= date`. Both boundaries are inclusive; an absent EndDate is
  open-ended. The date is normalized to midnight as a timezone-less
  `xsd:dateTime`, matching the accepted Member transformation.
- A holding is not a Cabinet membership, executive role, or proof of general
  office coverage. Unresolved office observations do not produce queryable
  holdings.

### Debate identity and date

- The bootstrap contains the three exact Debates sources pinned in
  `development-source-selection.json`: one Dáil, one Seanad, and one committee
  record. This is a development evaluation slice, not corpus coverage.
- `DebateRecord` identity and `agents:debateDate` are queried from their
  Debate-owned graphs. An `on` date is exact equality to the source date
  normalized as timezone-less `xsd:dateTime` at midnight.
- No chamber predicate is emitted. The Dáil/Seanad chamber filter is grounded
  only in the canonical named-graph route segment and is restricted to `dail`
  or `seanad`; it does not infer a House relationship. Committee is not an
  allowed chamber-filter value.
- Transcript speech text, debate search, owner references and general
  Debate-corpus completeness remain unsupported.

## Evaluation and boundaries

`query-service-phase-2-v1.json` contains eleven deterministic semantic-plan cases
and their expected result invariants, tied to the accepted dataset ID recorded
in `development-data-evidence.md`. Exactly one case exercises a cross-family
join (Bill sponsor to Member). Office tests use Member-owned facts plus a
resolved NamedOffice IRI; Debate tests remain within the Debate graph family.

Offline contract, determinism and generated-query checks:

```text
.venv/bin/python -m pytest tests/test_nlq_plan_phase2_evaluation.py
```

The opt-in test executes these cases against a fresh disposable Fuseki dataset
bootstrapped from the accepted local inputs:

```text
OIR_RUN_NLQ_PLAN_FUSEKI_TESTS=1 \
OIR_NLQ_CAPTURE_RAW_DIR=/path/to/preserved/raw-captures \
OIR_ETL_STATE_DB=/path/to/accepted/capture-index.sqlite \
.venv/bin/python -m pytest tests/test_nlq_plan_sparql_fuseki.py
```

The supplied Core State database is read-only capture-selection evidence; the
test publishes only to its disposable loopback Fuseki instance. No live model,
remote endpoint, production store, or user-directed source selection is used.
Direct natural-language-to-SPARQL generation, visible `/ask` planner
integration, transcript search, broad temporal operators, unsupported office
or Bill inferences, and production/authoritative coverage remain deferred.
