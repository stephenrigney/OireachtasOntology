# Query Service — Q23 and Bounded Bill Temporal Aggregation

## Outcome and route ownership

Q23 is owned by the integrated composable Query Service route (`/ask`, phase2),
not by Stage B's named-Bill sponsor lookup. The existing typed Q23 sponsorship
plan, exact Member IRI join, Bill graph route, compiler, evidence projection,
and result presentation remain the single path for reverse sponsorship. The
Stage B `bill_sponsors` capability remains the separate Q22 named-Bill
direction; it was not extended or duplicated for Q23.

The bounded temporal aggregate uses that same sponsorship plan with explicit
Bill, BillProcess, BillParticipation, Member and BillActivity referents. Its
extra edges retain the reviewed BillDelivery/process path and attach only typed
BillActivity dates to that exact process. One calendar-year constraint selects
source-backed Published events. The compiler reads all records for the selected
Member and the shared evaluator counts distinct Bill IRIs after validating the
Published activity evidence. Legislative year and document/version dates are
not used.

Primary, supporting, unknown, role-only, repeated-participation, and repeated
publication-record evidence are retained or interpreted without inferring
sponsorship/publication. Exact Member ambiguity, missing local Bill evidence,
malformed/missing publication dates, query/pagination errors and the bounded
page cap do not produce a guessed or partial count. A verified zero is returned
only when recorded sponsorship evidence and valid dated Published activities
establish a local zero; it is not a complete-corpus claim.

## Verification

- Controlled named-graph tests cover Q23 through `/ask`, English short titles,
  primary/supporting/unknown evidence, duplicate participation and event rows,
  exact Member ambiguity, unavailable Bill graphs, missing/malformed dates,
  year and Member parameter variation, same-query count/list identity parity,
  count zero versus unavailable evidence, and pagination-cap failure.
- Deterministic SPARQL compilation is checked for repeatability, the explicit
  ownership/process path, `Published`/`activity_date`, and read-only query safety.
- The semantic draft validator and JSON Schema cover the bounded five-referent
  graph and reject a dropped date constraint. `/ask` count presentation is
  exercised with a controlled graph fixture.
- Minimal planner endpoint check: one structured request returned HTTP success.
  Runtime health was checked separately from semantic capability results.
- Read-only Fuseki readiness was `ready` with Bill graphs present. Live
  integrated `/ask` Q23 returned a successful answer with 20 Bill rows and
  primary/supporting evidence. Live Q23 count for Malcolm Byrne/2024 failed
  closed with `source_data_unavailable`: at least one locally recorded
  sponsored Bill lacks a valid dated Published activity. The local evidence
  does not establish a count; this is a data-evidence limitation, not a planner
  runtime failure. The controlled positive count cases passed.
- Focused regression commands and ontology/contract validation are recorded in
  the implementation handoff/commit verification. The focused regression set
  passed **143 tests**; `.venv/bin/python tests/validate.py` passed with HermiT
  (2,586 ontology triples). No full benchmark, corpus
  scan, data refresh or production acceptance was performed.

## Implementation cost

Changed files: `poc/nlq/app.py`, `poc/nlq/composable_plan.py`,
`poc/nlq/composable_semantic_planner.py`,
`poc/specs/composable-query-plan-contract.json`,
`poc/specs/composable-query-plan-draft.schema.json`,
`tests/test_nlq_composable_q23.py`,
`tests/test_nlq_composable_semantic_capability_discovery.py`,
`tests/test_nlq_contract.py`,
`tests/test_nlq_composable_shared_dail_terms.py`,
`tests/test_nlq_composable_member_relationship_composition.py`, and this
report: **11 files**.

Approximate cost is **~480 added LOC and ~30 removed LOC** across runtime code,
contract/schema, tests, and this report; about 200 lines are runtime code, 22
contract/schema, 172 tests, and 92 report. Reused components: existing Q23 exact Member
resolution and sponsor compiler/evidence projection, validated plan validator,
Bill owner route and typed RDF path mappings, SPARQL read-only validation,
ordered pagination/truncation handling, `Published` lifecycle contract,
`QueryResult`, and `/ask` presentation. The only new evaluator is a narrow
calendar-year/xsd:date evaluator over the explicit Published event rows; the
existing Member interval evaluator is not equivalent to Bill activity-date
selection. No generic Bills framework or alternate compiler path was added.

## Limits and next human review gate

Live sponsorship is limited by optional Bill graphs and incomplete historical
coverage. The bounded aggregate deliberately fails closed when a sponsored
Bill's publication evidence is missing or malformed, so source availability can
prevent an otherwise plausible count. Human review should first accept the
Q23 route/contract changes and assess whether the local source capture provides
adequate dated Published evidence for this aggregate. **Do not expand Bills
capabilities until that review gate confirms evidence and completeness
expectations for dated Bill lifecycle selection and zero/count presentation.**

No ontology relationship, IRI, graph ownership, ETL, source fixture, or
publication behavior changed. Further Bills expansion still requires its own
approved bounded question and evidence review; this work does not authorize
votes, amendments, Bill/debate links, inferred steps, or corpus-wide
completeness claims.
