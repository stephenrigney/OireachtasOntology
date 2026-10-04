# Phase 7 office observation review and occurrence ledger

`oir-etl reconcile offices` is the local-only Tranche 2 workflow. It extracts
every `member.memberships[].membership.offices[].office` report from a fixture
or a complete Members API scan, persists each response through the immutable
raw-response store, validates Member/House-membership context and raw dates,
generates candidates only from the reviewed local registry, and records the
result in its own SQLite occurrence ledger. A malformed item inside
`membership.offices[]` (including an invalid or reversed office date range) is
quarantined as `review_required` with its exact raw pointer and validation
reason; it receives no candidates and cannot be accepted. Its source JSON is
never repaired. Member identity, membership/House context, a non-array
`offices` field, and raw-page integrity remain fail-closed. The occurrence
ledger keeps any prior `last_accepted_resolution` when current office evidence
is malformed. It does not transform/publish
Member RDF, allocate office identities, create holdings, or contact external
identity services.

Typical offline review scan:

```text
oir-etl reconcile offices --fixture data/api_examples/member.json --offline
```

Useful options are `--registry-file`, `--review-file`, `--office-state-file`
and `--raw-dir`. The command prints occurrence keys, source labels and dates,
registered candidates, review-required conflicts, and immutable raw pointers.
Exit status 1 means one or more reports need review or remain explicitly
unresolved. Unsafe Member context, registry, review, or SQLite errors still
fail closed. Raw responses are persisted before source validation; the
occurrence ledger uses one SQLite transaction per completed source scan. The
CLI never writes the review file.

## Member publication integration

The approved Phase 7 Tranche 3 contract migration updates the Member RDF golden
for `data/api_examples/member.json` to the exact graph emitted from that source
without office resolutions. The fixture's office observations remain unresolved
and therefore have no local office identity or legacy office RDF until accepted
through review. This golden intentionally removes the two legacy occurrence
records and their Member links, role assertions and date ranges; the exact graph
assertion preserves all other fixture triples. Dedicated approved-resolution
tests continue to pin OfficeHolding and derived Cabinet output.

Tranche 3 verification on 2026-10-04 used the complete hash-verified captured
Members fixture (1,928 unique Members). The offline run processed 1,142 office
observations: 22 accepted, two explicitly unresolved and 1,118 requiring
review (including two malformed, quarantined ranges); it emitted 22
OfficeHoldings and 22 derived CabinetMembership episodes. Twelve malformed
party ranges remained explicitly quarantined. A second run produced byte-for-
byte identical N-Quads (SHA-256
`345899ca9f8494799b1b8d8fce593aca24b96290ba1058b867d56862b0995be2`).
The pinned-Java ontology reasoner, mapping-integrity validator, and focused
Member/office tests passed. The full suite, including nine tests against an
isolated, disposable Fuseki 5.1.0 dataset, passed (462 tests and 23 subtests).
The isolated migration test confirmed validated whole-graph replacement
removes legacy office triples, preserves another graph, and retains exact
published graph equality on a deterministic rerun. These results exercise
Tranche 3, not external office or Bill-local reconciliation or the deferred
final Tranche 6 acceptance.

`oir-etl run members` performs the same registry/decision reconciliation before
transforming a complete current Member scan. Each office observation is linked
to its immutable raw response path, response SHA-256 and JSON pointer. The
effective accepted local office IRIs and their registered OfficeType concepts
are passed to both the Member transformer and its independent validator.
Unresolved or malformed office reports create no OfficeHolding.

Only a complete live scan, or a fixture envelope whose advertised
`memberCount` matches the deduplicated records, updates the durable occurrence
ledger. An offline run uses a fresh in-memory ledger and the supplied reviewed
registry/decisions only; it can exercise an initial reviewed bootstrap without
creating persistent occurrence state. An incomplete online fixture reads
existing accepted evidence without marking any observation absent or updating
the durable ledger.

Missing or conflicted observations do not revoke an accepted holding. For
contract-3 Member graphs, the ETL composes only holding records that can be
matched exactly to the hash-verified last accepted Member payload. If an
accepted ledger record requires retention but that payload is unavailable,
unparseable or inconsistent, the Member graph is left untouched. Contract-2
graphs predate OfficeHolding publication and are rebuilt under the new Member
contract rather than being treated as prior accepted holdings.

An unchanged Member source hash is not sufficient to skip an office-related
Member. When the ledger has accepted office evidence, the CLI builds and
independently validates the effective graph, then compares its triples with
the hash-verified last published payload. This detects reviewed outcomes
already reconciled by a separate `reconcile offices` invocation (including a
retry after an aborted publication) without relying on an in-process ledger
change marker. An equal validated graph can still skip its PUT; a changed
outcome is published through the ordinary dirty-state and exact-verification
path.

Before any contract-3 PUT that migrates a previously published legacy Member,
the CLI writes a JSON inventory beside the core state file named
`<state-db>.member-migration-<run-id>.json`. Override the destination with
`--migration-inventory-file`. The artifact counts legacy
`MinisterOfStateMembership`, `MinisterOfStateRole`, `hasMinisterOfStateRole`
and `officeNameUri` triples from verified local publication payloads and lists
ledger observations marked missing, including exact prior OfficeHolding matches
where applicable. Its SHA-256 and path are included in the run report. This
inventory uses only CoreStateStore's last verified payload and the local office
ledger; it never queries a live triple store. If an imported legacy manifest
did not retain the RDF payload, the artifact records that inventory gap and the
run reports it in `inventory_gaps`; no production query is attempted. The
contract-bump republish still follows the approved current-source validation
path. A payload that is present but fails its stored hash or parsing checks
blocks only that Member as `migration_inventory_blocked`.

Two conservative publication limits are explicit. If an accepted holding's
containing House membership disappears from the current Member source, the CLI
does not try to synthesize missing membership RDF: it retains that Member's
last published graph, reports `office_preservation_blocked` with the missing
membership IRI, and continues with other Members. This can also defer unrelated
changes to that Member until the accepted context returns or a separately
reviewed implementation supplies safe composition and independent validation.
Likewise, if a retained accepted office target has been removed from the current
registry, the Member graph is not republished with a dangling target; restore or
review the registry entry before retrying. Neither condition aborts the full
Member scan.

An absent dirty contract-3 Member can be replayed only from its exact validated
pending payload. An absent dirty Member from an older contract is instead
reported in `legacy_dirty_deferred` and left dirty with its current graph
untouched; it must reappear in a Member source scan so the current contract can
be transformed and independently validated before replacement. Member and
office-observation raw-response metadata both identify the active mapping as
`member_mapping.csv@phase-7-ministerial-offices-2026`.

### Explicit reviewed revocation

An ordinary `rejected` decision never clears a prior accepted resolution. To
remove a previously published holding as an erroneous/revoked assertion, a
reviewer may use the following explicit extension to a version-1 decision:

```json
{
  "status": "rejected",
  "action": "revoke",
  "observation_fingerprint": "<exact-current-sha256>",
  "office_iris": [],
  "evidence": ["<reviewed evidence reference>"],
  "reason": "<why the prior assertion must be removed>"
}
```

The current source fingerprint is mandatory for revocation, and the action is
applied only to that present observation. Absence, a stale fingerprint, a
plain rejection, or a removed review entry retains the last accepted holding
when it was previously published. The ledger keeps historical acceptance
evidence even after a reviewed revocation; only the Member-owned graph is
replaced without the explicitly revoked holding.

## Reviewed alias scope

The Tranche 1 registry remains version 1 and existing `{language, label}` aliases
remain valid. A reviewed alias may optionally include candidate-only scope:

```json
{
  "language": "en",
  "label": "Reviewed source wording",
  "source_uris": ["https://data.oireachtas.ie/ie/oireachtas/office/source-id"],
  "contexts": ["dail", "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"],
  "validity": {"start": "2024-01-01", "end": null},
  "unit_keys": ["u-000001"]
}
```

All fields other than `language` and `label` are optional. Contexts are House
codes or canonical local Oireachtas source IRIs; validity is an ISO date or
date-time interval; unit keys must refer to registered units; source URIs are
candidate evidence only. These annotations do not add RDF, assert office
existence dates, or confer identity on an unregistered resource. Registry unit
aliases are used only as contextual candidate evidence.

## Review file

`reconciliation/office-decisions.json` is version 1 and keyed by opaque
`occ-{sha256}` occurrence keys. A decision has `status` (`accepted`, `rejected`
or `unresolved`), `office_iris`, non-empty evidence references and a reason.
Accepted decisions require one or more complete IRIs already present in the
reviewed registry; rejected and unresolved decisions require an empty target
list. The optional `observation_fingerprint` binds a decision to the exact
source snapshot. No local key is generated from a label, category, holder,
department, source URI or external identifier.

The SQLite ledger retains current and previous source snapshots/fingerprints,
registry-only candidate sets, source pointers, decision/registry hashes,
conflicts, review status and every scan attempt. Exact duplicate reports share
one occurrence and retain each raw pointer. A unique date correction under the
same Member + House membership + source-office URI (or, if absent, exact
normalized source label) retains its occurrence key; it is flagged for review
because the source snapshot changed. If several distinct reports share that
identity or correspondence is not one-to-one, their association remains
review-required. Disappeared observations and stale decisions are retained and
flagged; no holding deletion is implied.

Exact reviewed aliases and reviewed source-URI rules can provide a unique
automatic candidate only when context, unit, date and wording checks are
compatible. Taoiseach, Tánaiste, Minister, Minister of State/MoS, Ceann
Comhairle, Cathaoirleach, Attorney General/AG and historical wording are candidate hints,
not classifiers. Multi-department records remain review-required; the candidate
set may include multiple already-registered offices for an explicit reviewed
multi-office decision. Pattern matches never mint office IRIs.
