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
AKN committee author uses `/committee/dail/34/{slug}`, while the agents
ontology comment describes `/committee/{slug}/{term-no}`; treat this as an
owner-identity documentation discrepancy for separate review, not an alias
rule. The approved Tranche 2 exclusion of the `rollCall`-nested `sum_2`
Summary/ordinal is recorded in `phase-7-debates.md`; the broader active CSV
selector needs a separately approved correction. No broad production ingestion,
publication mechanics or corpus-scope selection was done in Tranche 2.

The Tranche 2 acceptance commands are
`mise exec -- .venv/bin/python tests/validate.py`,
`mise exec -- .venv/bin/python -m tools.validation`,
`mise exec -- .venv/bin/python -m pytest -q tests/test_debates*.py`, and
`mise exec -- .venv/bin/python -m pytest -q tests`. Repeated transformations
are checked against sorted named-graph N-Quads and source-hash-linked JSON;
manual expected-RDF subsets and source-derived structure checks remain
independent of the production transformer.
At Tranche 2 acceptance, ontology/HermiT and active mapping-term validation
passed; the focused Debates suite had 78 passing tests (23 subtests), and the
full repository suite had 503 passing tests, 9 skips (23 subtests). These
results verify representative output, not a production-corpus resource gate.
