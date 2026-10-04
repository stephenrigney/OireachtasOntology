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
