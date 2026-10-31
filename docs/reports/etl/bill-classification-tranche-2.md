# Bill Classification and Integration — Tranche 2

## Approved decision and boundaries

The owner approved retaining Bill-level metadata on the Bill Work, rather than
distributing it across source versions. The final Bill is an
`eli-dl:DraftLegislationWork` with `eli:work_type oir:Bill`, `dct:title`,
`dct:alternative` and `dct:identifier`. The established `oir:Bill` concept is an
`eli:WorkType` in `eli:WorkTypeTable`; it is no longer a ResourceType-table member.
Source values (including long-title HTML), language tags and all resource/graph
IRIs remain unchanged. Expressions retain their source-backed labels, dates,
languages, versions and renditions; no Bill-level titles are invented on them.

The pinned ELI 1.5 axioms were examined, not modified:

| Property | Domain | Range | Bill Work treatment |
|---|---|---|---|
| `eli:type_document` | `eli:LegalResource` | `eli:ResourceType` | Replace with `eli:work_type` to avoid inferred LegalResource classification |
| `eli:work_type` | `eli:Work` | `eli:WorkType` | Use on Bill Work |
| `eli:title`, `eli:title_alternative` | `eli:Expression` | `rdfs:Literal` | Use Dublin Core titles on the Work instead |
| `eli:id_local` | `eli:Format ∪ eli:LegalExpression ∪ eli:LegalResource` | `xsd:anyURI ∪ xsd:string` | Use Dublin Core identifier on the Work instead |

The Tranche 1 BillDelivery path remains the explicit Work/process connection:
`delivery created_a_realization_of bill; forms_part_of process`. Introduction,
presentation and both application aliases retain their deterministic identities;
neither a delivery date nor a First Stage occurrence is inferred. There is no
direct Bill-to-process property or named-graph-co-ownership fallback.

Enacted Acts remain separate LegalResources. Bills still emit only an Act
reference through `eli:basis_for`; Act descriptions and Expressions remain owned
by the deferred Acts ETL. No source fixtures or external vocabulary pins changed.

## Integration and publication

Query-schema contract 2.10.0, deterministic plan compilation, label resolution
and lookup, composable sponsorship, Stage B queries and Stage C Bill existence
checks use the final metadata. The existing explanatory-memorandum chain is
unchanged. Query Service has no fallback to the obsolete Bill metadata model.
Composable plan contract 2.12.0 combines this Bill path with the temporal
party/constituency composition integrated from PR #13; the query-schema contract
remains independently versioned at 2.10.0.

Bills publication contract 2 invalidates the old source-hash skip gate. Observed
contract-1 Bills are transformed and validated even with unchanged hashes, then
their same named graphs are replaced and verified. Contract-2 clean Bills are
skipped only after whole-graph verification. Failed PUT/verification remains
dirty even when the pending and previously published source hashes match.
Older-contract dirty Bills absent from the current source selection are reported
as deferred, not replayed or declared migrated. This follows the existing
Members contract-upgrade precedent and leaves their saved recovery evidence
intact. Current-contract durable replay is retained.

## Verification evidence

- Final `.venv/bin/python tests/validate.py`: passed, including HermiT local
  ontology consistency/unsatisfiability checks (2,586 parsed triples).
- Final `.venv/bin/python -m pytest tests -q --disable-warnings`: **1,824 passed,
  25 skipped, 23 subtests passed**. Skipped environment/opt-in integration checks
  are not claimed as acceptance. Earlier stale version/allowlist test expectations
  were corrected to the approved model; the final full run is green.
- Mapping-integrity checks: **5 passed**. Both Bill cookbook queries parse with
  resolved prefixes, and `git diff --check` passes.
- Independent read-only architecture/semantic integration review found no
  concrete blockers; no new semantic decision was required.
- The complete preceding Tranche 1 golden N-Quads hash is pinned by the new
  regression. The final golden delta is exactly seven removed and six added
  triples, all on the Bill Work: one removed type and six predicate replacements.
  Every other triple, subject IRI and Work–Expression link is preserved.
- Regression tests inspect pinned property domains/ranges and run OWL-RL closure
  over final RDF plus the vendored ELI/ELI-DL and local ontology. The Bill remains
  a Work without inferred LegalResource, Expression or Format classification.
- Python validation, SHACL and post-load competency reject obsolete Bill metadata.
- Temporary SQLite and in-memory named-graph tests migrate unchanged-source
  contract-1 Bills both with and without the Tranche 1 relationship. They verify
  replacement, obsolete-triple removal, durable dirty ordering, PUT/verification
  failure retries, idempotent skipping and preservation of an unrelated Act graph.
- Query Service tests execute against actual final transformer output, including
  title resolution/lookup, status, sponsorship, existence and memorandum retrieval.
  Controlled source variants add a person reference solely to test sponsor joins;
  they are not claims about the captured Finance Bill's actual sponsors.

## Master integration — 31 October 2026

Integrated `origin/master` at `e44d61e` (PR #13) into
`feature/bill-classification-tranche-2`. At integration time remote PR #11 was
still open, contrary to the task premise; its BillDelivery commit `0b99f6b` was
already an ancestor of this branch and is retained. No PR was merged by this
task. PR #12 now targets `master` and includes both approved Bill
tranches.

The overlapping composable answer contract now preserves both PR #13's temporal
composition projection and the explicit BillDelivery sponsorship association.
The integrated composable version is 2.12.0; the separate query-schema 2.10.0 and
structured-plan 1.2.0 artifacts are unchanged from PR #12. A combined regression
pins the temporal membership join, inclusive date-time interval boundary,
separate evidence, fail-closed uncertainty, explicit Bill path and final Work
metadata together. The merged strict draft-schema acceptance and negative tests
are retained, not relaxed.

This integration introduces no further ontology, mapping, source-fixture,
golden-output or ETL publication-contract changes. Publication contract 2,
legacy-dirty deferral, exact current-contract recovery, Act ownership and the
separately authorized rollout boundary remain intact.

Integrated verification:

- Full suite (`.venv/bin/python -m pytest tests -q --disable-warnings -ra`):
  **1,850 passed, 25 skipped, 23 subtests passed**. Skips remain the explicitly
  gated disposable-Fuseki, capture-backed and production-release acceptance
  checks; they are not claimed as acceptance. Initial two-minute tool-limited
  runs were incomplete and are not counted; the successful reruns had no tool
  time limit.
- Focused temporal/composition, Bill classification/publication and Query
  Service regression selection: **519 passed**.
- All Query Service tests (`tests/test_nlq*.py`): **720 passed, 1 skipped**.
- Ontology validation: **passed**, including HermiT consistency and
  unsatisfiability checks over 2,586 local triples.
- Mapping integrity: **5 passed**.
- All **20** cookbook SPARQL queries translate successfully with their documented
  prefixes. The temporal evidence query returns both separate party episodes
  against the controlled named-graph fixture. The Bill relationship query runs
  against actual final transformer output and returns no rows after removing
  the explicit delivery-to-Work edge. No operational store was queried or changed.
- Deterministic contract conservation checks retain all temporal definitions and
  both explicit Bill associations; separate schema/plan artifacts are byte-identical
  to the pre-integration PR #12 versions. No new semantic decision was required.
- Independent read-only integration review found no material semantic regression
  or acceptance weakening. Its staging observation was resolved by staging the
  contract and both version-pin tests; the index was checked explicitly. A
  revision note distinguishes PR #13's historical version prose from the current
  integrated versions. Open-ended party/representation overlap remains distinct
  from the existing as-of-bounded cumulative-service calculation; neither
  behavior was changed.

## Residual issues and limitations (not expanded here)

- Related-document Works still use `eli:type_document`, whose domain entails
  LegalResource. Their classification was explicitly excluded from this tranche;
  no assertion, mapping or acceptance rule for them was changed.
- Older Debates vocabulary prose/source examples can call a Bill Work an
  `eli:LegalResource`. The unchanged legacy source markup is not the final Bill
  owner classification. Any separate Debates contract cleanup needs its own
  review; this tranche does not reinterpret source markup or change Bill references.
- Existing quarantines (`2024/48`, `1959/P3`, `1965/P1`, `1965/P3`) and unresolved
  amendment-reference diagnostics remain unchanged. Controlled tests are not a
  complete live-source acceptance or an operational dataset migration.
- The repository ontology validator runs HermiT over local ontology axioms, not
  the complete external import closure; pinned external inference is separately
  exercised by the OWL-RL Bill regression.

## Deployment requirement

No operational reload or production publication was performed. After review,
deploy the combined Tranche 1/2 ontology, mappings, ETL and Query Service, back up
state/evidence and authorize **one complete Bills source reconciliation** under
the existing operation lock. Do not clear hashes, delete graphs or treat an
incremental refresh as complete migration. Inspect per-Bill contract-2 clean
state, exact graph verification, run/catalog completion, quarantine, missing and
deferred dirty inventories and representative Query Service answers. Absent or
quarantined older Bills require separate resolution before claiming complete
coverage. See the [current rollout contract](../../reference/etl/legislation.md#contract-2-rollout-not-performed-here).
