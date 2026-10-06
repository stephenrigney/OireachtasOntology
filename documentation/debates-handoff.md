# Debates implementation handoff

- Status snapshot: `master` at `e8b728a1855a1f3c06ae9fdbb031f0d990ec8472`
  (Phase 7 Tranche 3 documentation/status update; based on implementation
  commit `8d53797`).
- Ministerial Phase 7: Tranches 1–3 complete; Tranches 4–6 pending.
- Available semantic boundary: `NamedOffice`, Member-owned `OfficeHolding`, and
  derived `CabinetMembership`. Debates must consume this model rather than
  introduce separate ministerial office or holder identity machinery.
- Limited baseline passed: ontology validation, mapping-integrity validation,
  and focused Member/Phase 7 tests (`93 passed`); `git diff --check` clean.
  Commands: `mise exec -- .venv/bin/python tests/validate.py`,
  `mise exec -- .venv/bin/python -m tools.validation`, and
  `mise exec -- .venv/bin/python -m pytest tests/test_members_etl.py
  tests/test_member_office_publication.py`.
- Retained limitation: if an accepted holding loses its entire containing House
  membership, the prior Member graph is retained and publication for that
  Member is blocked pending review. Production graphs were not mutated during
  Tranche 3 verification.
- Debates implementation has not started from this handoff state; the approved
  Tranche 1 source/semantic contract exists, but no runtime transformer does.

## Debates Tranche 2 handoff (2026-10-04)

The paragraph above is the historical ministerial handoff snapshot. Debates
Tranche 2 now provides `transform_debate(source_xml, resolver=...)` for exact
AKN bytes, a Work-keyed named-graph IRI, deterministic RDF and a sorted,
source-SHA-256-linked non-RDF reference-outcome report. It does not ingest,
publish, enumerate Expressions or claim one fetched file is a complete Work.
Use `validate_debates(result)` for focused RDF-visible checks; source-aware
fixture goldens prove the exclusions RDF alone cannot establish. The resolver
interface requires exact, existing Member, HouseTerm, House or Committee owner
identities; the small fixture tests supply checked-in owner examples, not a
complete authoritative registry. No question-recipient or `@as` office/
ParticipationRole crosswalk is activated: the existing `NamedOffice`,
Member-owned `OfficeHolding` and derived `CabinetMembership` model remains
authoritative, with no parallel Debates office/holder resources.

For Tranche 3, connect authoritative validated owner datasets, preserve the
source-hash outcome/evidence boundary, add SHACL and semantic-quality checks,
competency queries and graph-boundary tests. Historical HouseTerms and the
Committee owner are not established by the small checked-in owner examples;
do not normalize Committee URI patterns or guess identities from slugs. The
AKN committee author uses `/committee/dail/34/{slug}`. The consolidated
Members Committee owner uses `/committee/{houseCode}/{houseNo}/{slug}`;
the old `/committee/{slug}/{term-no}` template was a wiki documentation
error, not an owner alias. Link only after exact validated owner resolution.
The approved Tranche 2 exclusion of the `rollCall`-nested `sum_2`
Summary/ordinal is recorded in `phase-7-debates.md`, and the active CSV selector
now matches it (`debateBody//summary[not(ancestor::rollCall)]`, also applied to
the eId selector and the ordinal rule). No broad production ingestion,
publication mechanics or corpus-scope selection was done in Tranche 2.

Each Work and Expression IRI comes from its own FRBR URI; the Expression path
need not nest under the Work path. A present but valueless `FRBRWork/FRBRname`
fails source validation with hash-linked evidence instead of being mistaken
for an absent name and assigned a sitting. An absent `FRBRname` remains eligible
under the approved non-written Work rule.

The Tranche 2 acceptance commands are
`mise exec -- .venv/bin/python tests/validate.py`,
`mise exec -- .venv/bin/python -m tools.validation`,
`mise exec -- .venv/bin/python -m pytest -q tests/test_debates*.py`, and
`mise exec -- .venv/bin/python -m pytest -q tests`. Repeated transformations
are checked against sorted named-graph N-Quads and source-hash-linked JSON;
manual expected-RDF subsets and source-derived structure checks remain
independent of the production transformer.
At Tranche 2 acceptance, ontology/HermiT and active mapping-term validation
passed; the focused Debates suite had 87 passing tests (23 subtests), and the
full repository suite had 512 passing tests, 9 skips (23 subtests). These
results verify representative output, not a production-corpus resource gate.

## Tranche 3 bounded closure (2026-10-05)

Exact owner-RDF resolution for Member, House/HouseTerm and Committee identities,
joined SHACL/quality and source-hash report validation, executable competency
queries, and disposable graph-boundary tests are implemented. See the Tranche 3
evidence review and bounded closure in `phase-7-debates.md` for exact outcomes.
All links supported by reviewed source/owner evidence are validated; the two
unsupported competencies remain explicitly deferred, not marked as successful
query results.

The section-reference review found 16 `@refersTo` values across the five
preserved AKNs: eight target only a local `TLCEvent`, and eight 2026 Dáil
fragments have no local eId target. The local AKN targets are not Bill-owned
owners. Six distinct source `@href` strings contain Bill year/number path text
for 2013/23, 2014/86, 2015/1, 2015/67, 2024/25 and 2026/6; this inventory is
not an accepted identity crosswalk. Of the eight locally unmatched fragments,
six are `#bill.2026.6.dail.` and two are `#bill.2024.25.dail.`. The only
checked-in Bill owner is 2025/60. The per-section
hash-linked unresolved outcomes are checked against
the joined owner graphs; there is no exact reviewed AKN `TLCEvent`-to-Bill owner
crosswalk. The bill-event query contract is preserved and its no-row result is
not treated as positive competency acceptance.

The question-recipient review found 239 `@to` values, all resolving only to
source-local `TLCRole`s: ten in the Dáil 2015 record and 229 in written answers.
The checked-in office registry has three `NamedOffice` identities (Taoiseach,
Tánaiste, Minister for Finance) and the joined owner examples provide no typed
`eli-dl:ParticipationRole` individuals. In particular, the source references
`akn/ontology/role/ie/oireachtas/minister/public`,
`/ie/oireachtas/role/office/public` and
`/ie/oireachtas/role/office/social` and
`/ie/oireachtas/role/office/finance` have no reviewed crosswalk. All 239
reports remain unresolved and neither recipient predicate is emitted; the
query contract remains intact and unanswered.

The limited checked-in Committee owner example still does not establish the
Dáil 34 Public Accounts author; do not create that owner from the AKN href.
Committee rollCall attendance and its nested `sum_2` remain source-only and are
excluded by the transformer and golden. The active CSV selector now expresses
that exclusion (`debateBody//summary[not(ancestor::rollCall)]`, also applied to
the eId selector and the ordinal rule), so the protected mapping mismatch is
closed. No ontology, source fixture or golden was changed. Tranche 3 is closed
only under this evidence-backed deferral rule; this is not full Phase 7
completion or production-corpus acceptance.

At Tranche 3 closure, no Tranche 4 ingestion, state, graph-replacement or
publication work had started. The Tranche 4 implementation record below
supersedes that historical status. The production resource/scope gate,
historical duplicate-eId and written-answer fragmentation dispositions, and
eventual positive acceptance of the two deferred competencies remain open
separately.

## Debates Tranche 4 handoff (2026-10-06)

The implementation accepts explicit official AKN `main.xml` URLs or exact
preserved-object SHA-256 replay keys through `oir-etl run debates`. It does not
enumerate `/v1/debates`, infer expression completeness, or accept a section
object as its Work source: after transformation, the official source object
path must match the exact FRBR Expression path plus `/main.xml`. Exact XML bytes
are immutable content-addressed files under `{raw-root}/debates/sha256/`; Core
State schema v5 stores their source hash/path/URL reference with Work-keyed
publication state and the Expression IRI. Each validated resolution also keeps
an immutable source-/resolver-/owner-snapshot-linked reference-outcome JSON
sidecar; Core State tracks its pending/published path and hash and verifies it
before a clean skip or publication completion.

Publication is opt-in with `--publish`; a default run cannot construct/use a
Fuseki publisher. Opt-in publication uses the existing deterministic Debates
transform, exact owner resolver and source-aware integration validation. Core
State stays dirty until complete Work-graph PUT and exact post-PUT graph
verification succeed. A skip additionally requires unchanged source and
transform contract, resolver version, owner snapshot fingerprint, and a
verified remote graph; owner changes trigger re-resolution. Dirty/failure
records remain replayable through `--replay <sha256> --publish`.

No ontology, mapping, golden or source fixture was changed. The production
resource/scope gate, corpus quarantine/fragmentation dispositions, production
scanning/scheduling, and the two evidence-deferred positive competencies remain
open. The bounded test run passed Core State/Debates focused checks, including
the dedicated disposable Fuseki acceptance on loopback port 13035; production
graphs were not accessed or mutated. See `phase-7-debates.md` for the exact
acceptance record and run commands.
