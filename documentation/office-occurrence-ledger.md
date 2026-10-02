# Office occurrence ledger: accepted resolution evidence

The Tranche 2 `OfficeOccurrenceStore` keeps current review state separate from
the latest accepted local office resolution. Each occurrence row and each
immutable attempt row stores `last_accepted_resolution_json`, exposed by the
Python API as `last_accepted_resolution`.

That value records the accepted office IRI target set, source fingerprint and
snapshot, immutable raw-response pointers, generated candidate evidence,
review and registry hashes, resolution method, acceptance time, and—when the
acceptance was explicit—the complete accepted decision including its evidence
references and reason. Automatic acceptance records the unique reviewed
candidate as its evidence. An accepted re-review replaces the occurrence's
latest accepted resolution; previous attempt rows retain the accepted
resolution that was known at the time of each attempt.

Source corrections, registry or decision changes, absence, reappearance,
rejection, and unresolved/review-required outcomes update current operational
status but do not clear or rewrite the accepted resolution. This is evidence
retention only: Tranche 2 does not publish holdings or implement a revocation
action. Tranche 3 must use the retained acceptance evidence when composing
effective holdings and must not infer revocation from absence or rejection.

The ledger schema is version 2. Opening a version-1 database migrates it in a
SQLite transaction. A version-1 automatic acceptance is recoverable only when
its method and single stored candidate uniquely identify the target; that
target is backfilled together with the stored snapshot, raw pointers, hashes
and candidate evidence. Version 1 did not persist reviewed decision contents
or targets, so a review-file acceptance (or a prior acceptance already
overwritten by later operational status) cannot be reconstructed safely and
is left without a fabricated `last_accepted_resolution`. A subsequent reviewed
acceptance can establish this evidence going forward.

This ledger is operational state only. It does not emit or alter Member RDF,
OfficeHolding resources, Cabinet membership, ontology terms, mappings, source
fixtures, or the Member contract.
