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
