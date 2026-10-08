# Phase 6 Tranche A — operational ETL foundation

This note describes the implemented Core State, failure handling, provenance,
and recovery behavior. It is not a production deployment or Debates-readiness
claim.

## State and legacy provenance

The authoritative operational database is SQLite Core State (default:
`~/.local/share/oireachtas-etl/core-state.sqlite`; override with `--state-db` or
`OIR_ETL_STATE_DB`). Opening it applies supported migrations transactionally
through schema version 8; unsupported schema versions fail closed. Schema 8
adds the immutable `entity_version` and `entity_version_source` associations,
keyed by owner graph, payload hash, and entity IRI. The v6-to-v7
migration adds catalog-finalization/publication-attempt records and the
`provenance_incomplete` inventory. The additive v7-to-v8 migration adds
shared-entity lineage without rebuilding existing resource publication state or
rewriting dirty candidates. On every open, clean shared snapshots are checked
against their entity-version associations; an older `resolved` inventory item
is reopened as `pending` if a non-empty owner payload lacks complete entity
lineage. Earlier
supported schemas migrate through the intervening versions.

Migration backfills old clean graph provenance only when the retained graph,
source, run, time, raw-evidence, request, and version facts can all be verified.
It does not infer missing history. A legacy clean publication that cannot be
proved is listed in `state status` as `provenance_incomplete`, with its reason
and required action `validated_reobservation_and_republish`. A later successful
publication resolves that inventory item only when the new observation has a
raw evidence pointer and complete ETL/ontology/mapping version metadata. This is
an explicit migration-reconciliation gate, not a command that repairs history;
it surfaces the gaps but does not globally stop unrelated ETL runs. There is no
dedicated CLI to dismiss an item or invent its missing evidence. Existing dirty
publications remain dirty and recoverable, rather than being misclassified as
clean provenance gaps. Legacy Member/Bill JSON manifests are a separate,
explicit one-time import via `--legacy-state-file` (deprecated alias
`--state-file`).

`oir-etl state status [--state-db PATH]` reports the schema version, endpoint
cursors and publication state, dirty and missing resources, recent run
summaries, unresolved quarantines, provenance-catalog publication state, and
pending legacy provenance gaps.

## Publication boundary

The approved remote atomicity unit is one named graph. Each graph candidate is
transformed and validated before replacement. Core State durably stores that
graph's exact pending payload and SHA-256 as `dirty`; the loader replaces the
whole named graph with a Graph Store Protocol `PUT`; the ETL verifies the
resulting whole graph; only then is that graph marked `clean`. A failed PUT or
verification leaves its pending payload available for recovery.

This is **not** a transaction across every graph in a multi-graph ETL run.
Each already-verified graph replacement remains durable if a later graph or
the provenance catalog fails; there is no cross-graph rollback. Run completion
and authority updates are separately guarded by publication of the exact,
validated catalog candidate. For catalog-backed online runs, SQLite stages the
planned outcome and catalog payload before the PUT; the run becomes terminal
and a legislation cursor/complete-scan evidence can advance only after exact
catalog verification. A catalog PUT/verification failure is recorded as a failed
run and leaves hash-identified pending catalog state for replay; candidate
construction or staging failures fail before a new catalog PUT.

## Outcomes and failure classification

Runs have `success`, `degraded`, or `failed` outcomes. Non-success runs record a
failure scope (`record`, `source`, `run`, or `system`) and a non-empty
classification identifying the cause. Record failures that can be isolated
(Members, Legislation/Bills, and explicit Debates Work inputs) retain immutable
quarantine evidence and can leave unaffected validated graphs publishable. The
Debates publisher still validates all publishable Work graphs before the first
PUT; it omits quarantined Works while preserving the one-graph-per-Work
ownership boundary. A known multi-Expression Work is quarantined as a Work-level
conflict, never partially published. If processing otherwise reaches
finalization, unresolved quarantine prevents a `success` outcome and makes the
run degraded. Incompatible records on the shared-source Houses, Parties, and
Constituencies paths, source-envelope/completeness failures, and fatal state,
validation, publication, or verification errors fail the run rather than
claiming a complete successful view. JSON Lines operational events go to
stderr; persisted run summaries contain endpoint-applicable counters and
timings.

A degraded or failed run cannot advance the Bills incremental cursor or create
complete-scan missing-resource evidence. An incomplete source view is never
used as absence evidence. A process interruption is recorded as a failed run
(`process_interruption`) when the next run starts, unless a catalog finalization
is pending and must first be recovered.

## Quarantine and reobservation

The operator commands are:

```text
oir-etl quarantine list [--state-db PATH] [--endpoint ENDPOINT] [--status quarantined|resolved]
oir-etl quarantine show QUARANTINE_ID [--state-db PATH]
oir-etl quarantine retry QUARANTINE_ID --requested-by OPERATOR [--reason TEXT] [--state-db PATH]
```

`list` returns stored records (optionally filtered); its endpoint filter accepts
`houses`, `parties`, `constituencies`, `members`, `legislation`, and `debates`.
`show` returns the record and its append-only history. `retry` records an
operator request; it does not run the transformation immediately. Automatic
retry processing is wired to Members, Bills/Legislation, and explicit Debates
source runs. It selects unresolved records only when the corresponding source
record is reobserved: identified records match their resource IRI; identity-less
records may match by exact source hash only in an applicable live full scan (for
Bills, `run bills --full`) or the exact Debates content-addressed replay. A
Debates retry can be driven deterministically with
`oir-etl run debates --publish --replay SHA256`; the original AKN bytes and
source identity are revalidated before retry state can resolve. A successful
attempt marks the record resolved but retains its original evidence and
history; a failed attempt leaves it quarantined with the failure recorded.
Thus retry never republishes a stale quarantined snapshot merely because an
operator requested it.

## Source drift reports

The consumed-field source contracts currently cover Houses, Parties,
Constituencies, Members, and Legislation. They are not a full schema for every
API property. Unused additive properties are reported as warnings; malformed,
missing, or incompatible consumed fields are classified at record or source
level. Envelope shape and advertised-count failures are source failures. For
stateful runs, the per-run `source-drift.json` report and any page-level
`*.source-envelope-drift.json` sidecars are immutable JSON stored beside the
preserved raw capture. Findings identify endpoint, severity, JSON pointer, run,
source-page hash, and evidence path; reports describe observed JSON types rather
than copying field values. Reports and counters do not change or rewrite raw
source bytes.

## Provenance catalog and replay

The replaceable catalog is the named graph
`https://data.oireachtas.ie/graph/provenance`; SQLite remains canonical state.
The projection uses PROV-O and the `https://data.oireachtas.ie/etl/` namespace:

- A run is a `prov:Activity` at `.../etl/run/{escaped-run-id}`, with endpoint,
  run kind/completeness, outcome/status, times, and ETL/ontology/mapping
  versions.
- A source observation is a `prov:Entity` at
  `.../etl/source/{sha256}/observed/{escaped-time}`. It records the source hash,
  observation time, endpoint, canonical request parameters, available source
  URL/evidence pointer, and versions. Its run `prov:used` the observation.
- A published graph version is a `prov:Entity` at
  `{graph-iri}#sha256={payload-sha256}`, with `prov:specializationOf` the named
  graph, `prov:wasGeneratedBy` its actual publishing run, and (when evidenced)
  `prov:wasDerivedFrom` its source observation(s).
- A shared-graph entity version is keyed by graph IRI, payload hash, and entity
  IRI. Houses/HouseTerms and the Parties, Constituency/Panel, and Committee
  owner graphs retain the actual publishing run. A non-empty owner snapshot has
  exactly one association for every owned entity; each association derives from
  its exact source-page observation and record JSON pointer, or from the prior
  immutable entity version when that description is carried forward. It is not
  attributed to an unrelated current record. An empty owner payload has no
  synthetic entity-version rows.

  An empty Committees owner graph is derived at graph level from the exact page
  observations in the complete Members API capture identified by the immutable
  publication event's `member_source_run_id`. For a Committee command this is
  the successful capture named by the run's `source_run_id`; a Members publisher
  identifies its own current complete API capture. Those preserved Members
  observations are the source evidence; the ETL does not invent a Committee
  retrieval or a Committee record pointer. A new empty Committee publication
  fails closed unless the identified Members capture and its immutable raw-page
  evidence are available.

The projection is validated before publication and excludes its own graph
version to avoid recursive self-description. Historical records lacking raw
pointers or required entity lineage remain without fabricated evidence.
Non-empty shared snapshots missing entity associations stay listed as
provenance-incomplete until a fully evidenced publication resolves the item.
Historical empty Committee snapshots without a source-run link remain without
graph-level derivation. New non-empty shared entities require immutable source
observations with exact record pointers, or a prior entity version. The empty
Committee case instead requires graph-level derivation from the preserved
Members capture observations described above. Credential-shaped
metadata and unsafe credential-bearing URLs are rejected at the durable state
and catalog boundaries.

Recovery is deterministic replay, not a mid-run resume engine. Applicable
shared-graph runs replay an intact dirty payload before considering a new
candidate. Resource publication reuses the durable, hash-checked payload when
eligible; legacy dirty Member payloads that do not meet the current publication
contract are deferred until that Member reappears for validation. A dirty
catalog payload is hash-checked and replayed before a different candidate may
be staged. Whole-graph verification is still required before any dirty marker
clears. `state status` exposes pending graph/catalog state; rerun the applicable
endpoint command to drive recovery. There is no generic `replay` subcommand
for Core State publications.

## Local verification

Install the project-pinned Temurin Java 8 used by HermiT via `mise.toml`, and
the Python test extra if they are not already available:

```bash
mise install
.venv/bin/python -m pip install -e '.[test]'
```

Run ontology validation (including HermiT), the focused operational tests, and
the full suite with the project Java on `PATH`:

```bash
mise exec -- .venv/bin/python tests/validate.py
mise exec -- .venv/bin/python -m pytest -q \
  tests/test_operational_state.py tests/test_cli_operations.py \
  tests/test_source_contract.py tests/test_provenance_catalog.py \
  tests/test_core_state.py
mise exec -- .venv/bin/python -m pytest tests
```

For a Fuseki smoke test, use a project-scoped Compose name, temporary Core
State/raw directories, and a fixture (no API fetch). Port 3030 must be free.
The unique project name gives this test its own named volume; the trap removes
only that disposable project and its volume.

```bash
set -eu
project="phase6-tranche-a-check-$$"
mkdir -p /tmp/oireachtasontology
scratch="$(mktemp -d /tmp/oireachtasontology/phase6-check.XXXXXX)"
export FUSEKI_ADMIN_PASSWORD='phase6-disposable-local-only'
cleanup() {
  docker compose -p "$project" down -v || true
  rm -rf "$scratch"
}
trap cleanup EXIT

docker compose -p "$project" up -d fuseki
curl --silent --show-error --fail --retry 30 --retry-connrefused \
  --retry-delay 1 -u "admin:${FUSEKI_ADMIN_PASSWORD}" \
  --data-urlencode 'query=ASK {}' \
  http://localhost:3030/houses/query >/dev/null
export OIR_ETL_STATE_DB="$scratch/core.sqlite"
export OIR_MEMBERS_STATE_FILE="$scratch/no-legacy-members.json"
export OIR_BILLS_STATE_FILE="$scratch/no-legacy-bills.json"
export OIR_RAW_DIR="$scratch/raw"
export OIR_FUSEKI_GSP_URL='http://localhost:3030/houses/data'
export OIR_FUSEKI_SPARQL_URL='http://localhost:3030/houses/query'
export OIR_FUSEKI_USER=admin
export OIR_FUSEKI_PASSWORD="$FUSEKI_ADMIN_PASSWORD"

mise exec -- .venv/bin/oir-etl run houses \
  --fixture data/api_examples/houses.json \
  --state-db "$OIR_ETL_STATE_DB" --raw-dir "$OIR_RAW_DIR"
mise exec -- .venv/bin/oir-etl state status --state-db "$OIR_ETL_STATE_DB"
```

Do not use `docker compose down -v` against the ordinary Compose project: its
`fuseki-data` volume is persistent. The disposable command above deliberately
uses a separate Compose project.

## Limits

Tranche A does not implement Tranche B production operations (deployment,
service-level caching/rate limits and resilience, backups/restore, scheduled
execution, or production monitoring). Debates remains an explicit bounded AKN
batch (`oir-etl run debates --source-url URL` or `--replay SHA256`) with opt-in
per-Work publication via `--publish`, not a complete-source run, broad
production-corpus loader, or scheduler. Approved initial corpus scope does not
close the separate Debates production gate: operational limits, the exact
in-scope quarantine inventory, and staged operational acceptance remain
deferred.
