# Natural-language query POC

This proof of concept lets you ask questions about the Oireachtas RDF dataset in plain English. Its default Phase 2 route first retains the reviewed Stage A/B/C and deterministic composable families. When those do not recognize a question, a Responses-compatible planner may propose a semantic composable-v2 plan; local code resolves exact entity labels and validates the complete plan before the deterministic compiler generates safety-validated SPARQL. The model does not generate executable SPARQL on this path.

The Stage 1 human-readable UI is available at `/` and its capability catalogue at
`/capabilities`. The catalogue is generated from the query-plan contract and
compiler mappings. It describes semantic expressibility and compiler coverage,
not whether the required records are present in a particular Fuseki dataset.
Temporal semantics remain fact-specific; the catalogue lists contract temporal
forms but does not claim every form compiles for every fact. A planner draft may
be shown for diagnosis but is explicitly marked unvalidated and is not an
accepted relationship.

The development form also retains the Phase 1 direct NL→SPARQL path as an optional comparison/debug mode. Phase 2 ambiguity, unresolved entities, unsupported requests, planner/validation failures, and Fuseki execution failures are reported as distinct, controlled outcomes; no failed or unresolved plan is executed.

This is an experimental query interface. It is separate from the deterministic ETL pipeline and never writes to Fuseki.

## Quick start

Run all commands from the repository root. The launcher needs `uv`, Docker with
the `docker compose` plugin, and `curl`.

### 1. Configure the LLM key

```bash
cp .env.local.example .env.local
# edit .env.local and set NLQ_LLM_API_KEY
```

`.env.local` is git-ignored. `NLQ_LLM_API_KEY` is required and has no default.

The endpoint and model are optional overrides. When they are omitted, the
launcher uses these local-development defaults:

```dotenv
NLQ_LLM_BASE_URL=https://opencode.ai/inference/openai/v1
NLQ_LLM_MODEL=gpt-6-luna
NLQ_FUSEKI_QUERY_URL=http://localhost:3030/houses/query
```

Do **not** add `/responses` to `NLQ_LLM_BASE_URL`; the application adds it. The
endpoint and model are not hard-coded into the application; the launcher only
supplies development defaults.

### 2. Start the POC

```bash
scripts/dev-nlq.sh
```

The launcher resolves configuration, installs the NLQ dependencies from the
committed `uv.lock`, starts or reuses the local Docker Compose Fuseki service,
waits until Fuseki is reachable, applies the local Fuseki credentials, and
starts the FastAPI application under Uvicorn with auto-reload enabled.

### 3. Open the browser interface

Open:

<http://127.0.0.1:8000/>

The home page performs a read-only, presence-only readiness check for Houses,
Parties, Constituencies and Members. Committees, Bills, the reviewed office and
administrative-unit registries, and accepted OfficeHolding/CabinetMembership
data are reported as optional domains; their absence does not make the basic
dataset unready. This check does not identify source captures or establish
reference closure.

Try questions such as:

- Who were the Fine Gael members of the 33rd Dáil?
- Which TDs represented Dublin constituencies in the 32nd Dáil?
- Which parliamentary member collection did Micheál Martin belong to in the 33rd Dáil?
- How many members were in each parliamentary member collection in the 33rd Dáil?
- Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?

On success, the application shows the result. In the default Phase 2 path, expand **Validated query plan** and **Generated SPARQL** to inspect the interpretation and executable query. Phase 1 continues to show its direct-generated query using the existing display.

The application also reports:

- ambiguous local identity without selecting a candidate;
- unresolved local identity without running an answer query;
- unsupported question/semantic combinations without generating an answer query;
- planner or validation failures separately from Fuseki execution failures.

Detailed diagnostics and the raw endpoint payload, when available, are in the expandable query debugger. Internal exceptions are not used as the primary user-facing message.

Phase 2 is complete. The accepted structured local-query path is:

```text
question → reviewed Stage A/B/C or deterministic composable family
         → (unrecognized: semantic composable-v2 planner for supported slices)
         → deterministic resolution and validation → deterministic SPARQL
         → local Fuseki → rendered result
```

It is the default browser development path. The accepted realistic benchmark is
**32 passed, 2 failed, 3 not scored**; the Phase 1 comparison was **14/30**, and
deterministic regression was **10/10**. Phase 2 substantially outperformed the
retained Phase 1 comparison. The remaining failures are bounded planner defects,
not evidence of architectural failure: `aggregate.dail-term-count` can produce
an invalid count draft, and `debate.committee-sep24` selects a date fact rather
than the expected DebateRecord answer.

The development UI distinguishes success, ambiguity, unresolved identity,
unsupported requests, planner/validation failures, and execution failures.
Failed or unresolved plans do not execute answer queries; the plan and generated
SPARQL are inspectable. Phase 1 direct NL→SPARQL remains available for
comparison/debugging. A live smoke test exercised real Fuseki with a fixed
planner test double. Carried-forward limitations, not reopened in Phase 2, are:
Debate coverage limited to the three pinned representative graphs;
quarantined/unavailable source cases as data-coverage limitations; planner/model
variability; no repair/retry loop; and broader source selection, federation,
and external querying deferred. See the [final benchmark and close-out
report](../reports/query-service/realistic-phase2-benchmark.md).

The first generalized semantic-composition slice answers questions about Dáil
terms shared by exactly two independently resolved Members. It intersects the
Members' recorded DailMembership paths by the same DailTerm RDF identity, not by
matching display labels. Ambiguity, missing Member identity, same-identity
aliases, unsupported relationships, and missing membership evidence fail closed.
Empty results reflect recorded local evidence only and do not certify complete
historical coverage. Seanad terms, extra filters/temporal constraints, and other
compositions remain unsupported. Unrecognized questions use one strict
Responses-compatible plan call with no repair/retry; planner failures are
reported separately from unsupported semantics and source-evidence limitations.

The reusable Member relationship composition also supports two bounded local
queries: Members with recorded membership in each of two explicitly numbered
Dáil terms, and Members whose recorded DailMembership represents an exact
constituency occurrence in one numbered Dáil term. The constituency occurrence
and membership must join to the same DailTerm RDF identity. Both use the same
validated relation-graph compiler; term and constituency identities are resolved
locally before an answer query runs. Results reflect recorded local evidence and
do not certify historical completeness. Additional filters, more/fewer terms,
Seanad terms, and unsupported relationships are refused rather than dropped.

### Other launcher commands

```bash
scripts/dev-nlq.sh --load-data   # bootstrap local data from preserved API captures
scripts/dev-nlq.sh --no-reload   # start without the Uvicorn autoreload watcher
```

Ordinary startup never loads source data. `--load-data` explicitly invokes
`oir-etl dev bootstrap` with the reviewed office-decision file, selecting Query
Service Phase 2 evaluation mode and its committed development-data and Debate
source selections. It verifies immutable raw-page evidence and office
registry/review inputs, derives holdings only from current explicitly accepted
office evidence, validates transformed RDF, checks the accepted graph/resource
counts, and loads the non-authoritative evaluation graphs into loopback Fuseki.
For the exact dataset ID already accepted for this benchmark, Member RDF
validation may be reused while source evidence and deterministic transforms are
rechecked. Bill validation reuse additionally requires the current Bills
publication contract and an exact per-graph RDF 1.1 semantic-hash inventory
matching the accepted contract-specific evidence. Bill transforms and source
checks still run on each bootstrap; changed RDF, a changed Bill contract, or a
different dataset identity requires full Bill validation. Aggregate graph and
triple counts are checked separately and cannot authorize reuse. Benchmark
candidate generation always performs full Member and Bill validation. The
bootstrap also checks serialized RDF and Fuseki per-graph counts.
It does not fetch current API data, run the authoritative publication path, or
advance Core State, office-occurrence, or external-reconciliation state.
Materially conflicted reference identities remain quarantined, and reference
closure is reported **NOT authoritative / not complete**. If bootstrap fails,
the POC is not started.

The conservative publication-backed `oir-etl dev bootstrap` mode remains the
default when neither `--review-file` nor benchmark-candidate output options are
supplied. It reads complete API captures and current clean Member/Bill
publications from Core State in read-only mode. Only exact-source-matching clean
contract-3 Member publications contribute OfficeHolding/CabinetMembership
output; other Members receive no office resolutions. Bill graphs are optional
and loaded only from current clean contract-2 Core State publications with
intact payloads. The NLQ launcher and Phase 2 benchmark runners pass
`reconciliation/office-decisions.json` explicitly when they require the pinned
Phase 2 evaluation dataset.

Development bootstrap and query-benchmark scratch artifacts default to the
ignored repository directory `var/nlq-scratch`. Set `OIR_NLQ_SCRATCH_DIR` to a
different non-`/tmp` location when needed.

The bootstrap prints a stable dataset identity. To save its full machine-readable
baseline for later evaluation tooling, invoke the same development-only command
with an output path:

```bash
uv run --locked oir-etl dev bootstrap \
  --review-file reconciliation/office-decisions.json \
  --fuseki-gsp-url http://localhost:3030/houses/data \
  --fuseki-sparql-url http://localhost:3030/houses/query \
  --dataset-baseline-output /tmp/oireachtas-nlq-dataset-baseline.json
```

The schema-version-1 baseline records source capture run IDs, graph families and
resource counts, quarantines, unresolved references, and source/publication
evidence. In Phase 2 evaluation mode it additionally fingerprints raw-page
hashes, office registry/review inputs and accepted holdings, and the pinned
three-Debate evaluation slice. In publication-backed mode it records eligible
Bill evidence and the exact-current Member publication inventory. Its stable
identity is derived from the relevant preserved inputs. It describes only graph
payloads written by the bootstrap, not a live census of unrelated or stale
graphs in persistent Fuseki. The Debate slice is non-authoritative and does not
imply complete Debate or cross-dataset owner-reference coverage.

## NLQ evaluation benchmark

The current question set is benchmark v0.3.0 at
`poc/nlq/benchmarks/benchmark-v3.json`; historical v0.1.0 and v0.2.0 sets are
preserved as `poc/nlq/benchmarks/benchmark-v1.json` and
`poc/nlq/benchmarks/benchmark-v2.json`. All use the format defined by
`poc/specs/nlq-benchmark.schema.json`. Each case records its
category, support expectation, interpretation target, semantic result
invariants, graph/resource prerequisites, and optional independent coverage
probes. Exact duplicate Member-name cases use a deterministic
`ambiguity_handling` evaluation mode; broad set-valued Member questions remain
manual review when their precise answer set is not yet stable enough to score.

Run the deterministic ten-case subset without an external LLM:

```bash
uv run --locked --extra nlq python scripts/run-nlq-benchmark.py --tier regression
```

Run all 42 v0.3.0 cases using the configured Responses-compatible LLM where
translation is required:

```bash
uv run --locked --extra nlq python scripts/run-nlq-benchmark.py --tier measured
```

Both automation tiers require Docker, the preserved API captures, and the
committed API/Debate selection manifests; no Core State capture-index snapshot
is required. Override the raw-capture location with `--raw-dir` or
`OIR_RAW_DIR`. The optional `--state-db` argument only supplies a path protected
against baseline-output overwrite; it is not opened for capture selection.
The runner starts a new
`stain/jena-fuseki:5.1.0` container for each run, publishes a random port only
on loopback, attaches no host or named data volume, bootstraps that instance
from the preserved captures, and stops/removes it after evaluation. It never
targets the ordinary persistent Compose dataset. The runner defaults to
benchmark v0.3.0; use `--benchmark
poc/nlq/benchmarks/benchmark-v2.json` or `--benchmark
poc/nlq/benchmarks/benchmark-v1.json` to reproduce the historical v0.2.0 or
v0.1.0 case sets. Result JSON is written beneath the ignored
`var/nlq-benchmark/runs/` directory by default.

Every result embeds the exact schema-version-1 development dataset-baseline
JSON and its stable `sha256:` dataset ID, plus the disposable container ID for
that particular run.
Measured results also record the resolved non-secret translator model, base
endpoint, request timeout, output-token cap, and whether configurable
model/endpoint values came from
the process environment, repository `.env`, or defaults. API keys and
authorization material are never recorded. This is provenance for that run,
not a repeatability guarantee for model output.
Before an NLQ case is scored, the runner checks its required graph families,
known quarantined/unresolved resources, and (where defined) curated read-only
coverage probes. A missing prerequisite is recorded as
`source_data_coverage` / `coverage_unavailable`, not as an NLQ failure. Once
coverage is established, the shared browser/benchmark pipeline translates,
validates and executes the question. Scoring inspects result kinds, row counts,
literal values, row-level co-occurrence and aggregate invariants; it does not
compare generated SPARQL strings. Translation, validation, execution and
semantic mismatches retain their failure class and diagnostic candidates.

The Phase 0A bootstrap remains explicitly non-authoritative and labels reference
closure **NOT authoritative / not complete**. A passing case-level probe only
establishes the exact prerequisite facts for that case; it does not promote the
whole development dataset to complete or authoritative coverage.

The automated regression tests use deterministic translation inputs and
mocked Fuseki responses, so they run offline. Running the script against the
capture-backed disposable dataset remains a separate integration/baseline run.
For ordinary CI, run the repository test suite (including
`tests/test_nlq_benchmark.py`, `tests/test_nlq_prefixes.py`,
`tests/test_nlq_ambiguity.py`, and the NLQ safety/pipeline tests); this tier needs
no live LLM. The ten-case `--tier regression` runner additionally replays the
same frozen benchmark translations against disposable Fuseki and capture-backed
data. The `--tier measured` run invokes the configured LLM and is
nondeterministic: retain and inspect its run artifact, but do not use generated
SPARQL or measured JSON bytes as a byte-for-byte CI gate. Future planner or
federation work must preserve the deterministic local behaviours, fail-closed
safety, exact duplicate-name ambiguity handling, and source-coverage/NLQ
failure separation documented in the Phase 1 completion report.

## Configuration precedence

The launcher applies one precedence to every value:

```text
explicit process environment
    > .env.local
    > launcher development defaults
```

Only `scripts/dev-nlq.sh` reads `.env.local`; the launcher parses it as data and
does not `source` it. The application itself loads the repository-root `.env`
with `override=False`, so the values the launcher exports always win over
`.env`. A per-value override in `.env.local` is optional.

## Fuseki and credentials

The launcher uses the bundled `docker-compose.yml` Fuseki service. It:

- verifies Docker and the Compose plugin are available;
- runs `docker compose up -d fuseki`, recreating the container when the Compose
  configuration changed but never deleting the persistent `fuseki-data` volume;
- waits for the anonymous `/$/ping` endpoint with a bounded retry loop before
  starting Uvicorn;
- applies the configured local admin password in place if an existing volume has
  a different stored credential, then restarts the service.

The local-development admin password default is `oireachtas-dev`, which is also
the non-production fallback in `docker-compose.yml`. Override it with
`FUSEKI_ADMIN_PASSWORD` in the process environment or `.env.local`. An
`OIR_FUSEKI_PASSWORD` supplied by either source is reused as the local admin
password so an existing Fuseki volume keeps working. The launcher populates
`OIR_FUSEKI_USER` (default `admin`) and `OIR_FUSEKI_PASSWORD` for the
application and does not print credentials.

For `--load-data`, the launcher also exports `OIR_FUSEKI_GSP_URL` and
`OIR_FUSEKI_SPARQL_URL` so the development bootstrap can load and verify each
graph.
`OIR_FUSEKI_SPARQL_URL` defaults to the resolved `NLQ_FUSEKI_QUERY_URL`, so no
manual export is needed.

These credentials are for local development only and must not be treated as
production credentials. Do not use `docker compose down -v` as a refresh step:
it deletes the persistent local Fuseki volume.

## If the application does not start

### `NLQ_LLM_API_KEY is not set`

The launcher fails immediately when no key is available. Copy
`.env.local.example` to `.env.local` and set `NLQ_LLM_API_KEY`, or export it:

```bash
export NLQ_LLM_API_KEY=...
```

### LLM authentication or model errors

First test the provider independently.

For OpenCode Console inference:

```bash
curl --fail-with-body \
  https://opencode.ai/inference/openai/v1/responses \
  -H "Authorization: Bearer $NLQ_LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-6-luna",
    "input": "Return only the word OK"
  }'
```

If this succeeds but the POC fails, check that `NLQ_LLM_BASE_URL`,
`NLQ_LLM_MODEL` and `NLQ_LLM_API_KEY` resolve to the working endpoint. Remember
that an explicit process environment value wins over `.env.local`.

### Fuseki is reachable but the readiness panel is empty or partial

Starting Fuseki does not populate it. Data loading is deliberately an ETL
operation, not an application startup side effect. Run
`scripts/dev-nlq.sh --load-data` when you intentionally want the local
development bootstrap to load preserved complete API captures for the
reference and Member graphs.

## Manual commands (advanced / troubleshooting)

These are the operations the launcher performs. Use them only when diagnosing
launcher behaviour; normal development should use `scripts/dev-nlq.sh`.

### Dependencies

```bash
uv sync --locked --extra nlq
```

The local `oireachtas_etl` package is installed by `uv sync` from the committed
lockfile; no `PYTHONPATH` override is needed.

### Fuseki endpoints

```bash
docker compose up -d fuseki
```

```text
Query endpoint: http://localhost:3030/houses/query
Write endpoint: http://localhost:3030/houses/data
```

### Start Uvicorn directly

```bash
uv run --locked uvicorn poc.nlq.app:app --reload
```

### Run the local NLQ development bootstrap

The launcher sets these endpoints automatically. To invoke the same local,
non-authoritative bootstrap manually (including writing a dataset baseline),
set the loopback Fuseki write and verification endpoints:

```bash
export OIR_FUSEKI_GSP_URL=http://localhost:3030/houses/data
export OIR_FUSEKI_SPARQL_URL=http://localhost:3030/houses/query
```

For authenticated Fuseki, also export `OIR_FUSEKI_USER` and
`OIR_FUSEKI_PASSWORD`.

```bash
uv run --locked oir-etl dev bootstrap \
  --dataset-baseline-output /tmp/oireachtas-nlq-dataset-baseline.json
```

This selects preserved captures; it does not fetch source data. The separate
`oir-etl run <endpoint>` commands are authoritative ETL operations and are not
the workflow used by `scripts/dev-nlq.sh --load-data`.

For independent authoritative ETL operation, the following commands remain
available:

```bash
uv run --locked oir-etl run houses
uv run --locked oir-etl run parties
uv run --locked oir-etl run constituencies
uv run --locked oir-etl run members
uv run --locked oir-etl run bills
```

The POC launcher does not invoke these authoritative commands.

Do not use `docker compose down -v` as a refresh step: it deletes Fuseki's persistent volume.

## Query behavior and technical authority

The default browser path is the implemented structured Phase 2 local flow:
question → semantic plan → deterministic entity resolution and validation →
deterministic SPARQL compilation → local Fuseki. The optional Phase 1 direct
NL→SPARQL path is retained for comparison/debugging, not as the default. Failed,
ambiguous, unresolved or unsupported plans do not execute an answer query. The
model does not generate executable SPARQL on the default path.

The `/capabilities` catalogue reports semantic expressibility and compiler
coverage, not data availability in a particular Fuseki dataset. Temporal forms
are fact-specific; not every listed form compiles for every fact. The accepted
question and answer requirements remain in
[`poc/specs/query-service-questions-approved.md`](../../poc/specs/query-service-questions-approved.md).
The authoritative technical specification—including query-plan, safety,
compatibility and supported relationship contracts—is
[`poc/specs/query-service-plan.md`](../../poc/specs/query-service-plan.md).
This user guide does not create a parallel semantic contract.

The older Phase 2 contract permits an additive **reviewed, supported** entity
type within contract major version `1` only when existing meanings and
validation behavior remain unchanged; the manifest, schema and parity tests
must be updated together. The current composable contract has its own version
and compatibility rules in the technical specification.

## Benchmark evidence and limitations

The current realistic Phase 2 benchmark recorded **32 passed, 2 failed and 3
not scored**; Phase 1 comparison recorded **14/30**, and deterministic
regression **10/10**. These are results for the documented development dataset
and benchmark run, not a production-readiness or data-coverage claim. The two
carried failures were an invalid aggregate draft for `aggregate.dail-term-count`
and a wrong answer kind for `debate.committee-sep24`. See the
[realistic Phase 2 benchmark and close-out](../reports/query-service/realistic-phase2-benchmark.md)
and the [completion evidence](../reports/query-service/completion-evidence.md).
The exact benchmark cases and machine-readable results remain under `poc/`;
prior Phase 1 comparisons and supporting evidence are in the
[report archive](../reports/query-service/).

Important limits:

- Historical answers depend on the specific Member, Parties, Bills, office and
  Debate graphs loaded. Presence/readiness checks do not establish complete
  source coverage, reference closure or authoritative data.
- The Debate benchmark slice contains three pinned representative graphs; it is
  not complete Debate coverage. Source quarantine and unavailable source cases
  remain data-coverage limits, not query-planner successes or failures.
- Read-only SPARQL safety checks do not constitute a complete sandbox; this POC
  is for local/isolated development, has no authentication or production
  hardening, and has no federation or external-query mode.
- Safe, valid SPARQL may still be semantically wrong. There is no general OWL
  entailment, fuzzy identity matching, person merging or conversational
  follow-up state.
- Q06 uses reviewed local political-affiliation identity evidence, not name
  matching or external `recognisedAsParty` links. Synthetic tests cover its
  query path; completeness depends on the relevant graphs being loaded. See the
  [Q06 evidence report](../reports/query-service/q06-political-affiliation-evidence.md).

Use the linked benchmark and development-data reports for reproducibility,
exact dataset provenance and evaluation methods. Use the technical specification
for current contracts; reports describe measured evidence at their stated
revision/date and are not active implementation plans.
