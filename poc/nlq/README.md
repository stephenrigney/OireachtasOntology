# Natural-language query POC

This proof of concept lets you ask questions about the Oireachtas RDF dataset in plain English.

The application first checks exact local Member-name references against Member `foaf:name` labels in Fuseki. If multiple local Member records remain without distinguishing context, it returns a clarification outcome and does not send an answer query. Otherwise, it sends the question with schema context derived from the repository ontology to an OpenAI Responses-compatible LLM; the application validates the model's read-only SPARQL, runs it against Fuseki, and shows both the result and the generated SPARQL.

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
Parties, Constituencies and Members; Bills are detected as optional. This check
does not identify the source captures or establish reference closure, and it
does not currently probe the Committee graph family.

Try questions such as:

- Who were the Fine Gael members of the 33rd Dáil?
- Which TDs represented Dublin constituencies in the 32nd Dáil?
- Which parliamentary member collection did Micheál Martin belong to in the 33rd Dáil?
- How many members were in each parliamentary member collection in the 33rd Dáil?

The application shows:

- the model's interpretation of the question;
- the exact SPARQL submitted to Fuseki;
- the SELECT result table or ASK result;
- debugging information when translation, validation, or Fuseki execution fails.

### Other launcher commands

```bash
scripts/dev-nlq.sh --load-data   # bootstrap local data from preserved API captures
scripts/dev-nlq.sh --no-reload   # start without the Uvicorn autoreload watcher
```

Ordinary startup never loads source data. `--load-data` explicitly invokes
`oir-etl dev bootstrap`, which reads the latest successful complete API captures
already preserved and indexed in Core State, validates them, and loads the
non-authoritative local-development graphs into loopback Fuseki. It does not
fetch current API data, run the authoritative `oir-etl run` publication path,
or advance Core State coverage/publication or external-reconciliation state.
Materially conflicted reference identities remain quarantined, and the bootstrap
reports unresolved references and labels reference closure **NOT authoritative
/ not complete**. If the bootstrap fails, the POC is not started.

The bootstrap prints a stable dataset identity. To save its full machine-readable
baseline for later evaluation tooling, invoke the same development-only command
with an output path:

```bash
uv run --locked oir-etl dev bootstrap \
  --fuseki-gsp-url http://localhost:3030/houses/data \
  --fuseki-sparql-url http://localhost:3030/houses/query \
  --dataset-baseline-output /tmp/oireachtas-nlq-dataset-baseline.json
```

The baseline records the selected source capture run IDs, graph families and
resource counts, quarantined identities, unresolved references, and the
non-authoritative closure status. Its identity is derived from the source URLs
and run IDs, so reusing the same preserved captures produces the same identity.
It describes graph payloads written by the bootstrap; it is not a live census
of other or stale graphs already in a persistent Fuseki dataset.

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

Both automation tiers require Docker and the preserved complete API captures
and Core State index used by `oir-etl dev bootstrap`. Override their locations
with `--raw-dir` / `--state-db` or the existing `OIR_RAW_DIR` /
`OIR_ETL_STATE_DB` environment settings. The runner starts a new
`stain/jena-fuseki:5.1.0` container for each run, publishes a random port only
on loopback, attaches no host or named data volume, bootstraps that instance
from the preserved captures, and stops/removes it after evaluation. It never
targets the ordinary persistent Compose dataset. The runner defaults to
benchmark v0.3.0; use `--benchmark
poc/nlq/benchmarks/benchmark-v2.json` or `--benchmark
poc/nlq/benchmarks/benchmark-v1.json` to reproduce the historical v0.2.0 or
v0.1.0 case sets. Result JSON is written beneath the ignored
`var/nlq-benchmark/runs/` directory by default.

Every result embeds the exact Phase 0A dataset-baseline JSON and its stable
`sha256:` dataset ID, plus the disposable container ID for that particular run.
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

## How it works

```text
Question in browser / benchmark runner
  -> bounded local exact Member-label resolution
       - explicit ambiguity outcome for unresolved duplicate labels
       - local HouseTerm / constituency context for disambiguation
  -> OpenAI Responses-compatible LLM (when resolution is unique or set-valued)
       - query-contract-scoped schema context
       - dataset graph conventions from the contract
       - user question
  -> structured { interpretation, sparql }
  -> RDFLib SPARQL parsing and safety checks
  -> configured Fuseki /query endpoint
  -> SPARQL Results JSON
  -> result table / ASK answer in browser
```

The repository-owned machine-readable query contract is
`poc/specs/query-schema-contract.json` (contract version `1.0.0`, schema
version `1`). Its JSON Schema is `poc/specs/query-schema-contract.schema.json`.
The contract defines the queryable class/property scope, named-graph families
and owners, emitted RDF patterns, entity-specific label predicates,
cross-graph joins, optional reviewed external identity links, reasoning
assumptions, known unavailable patterns, and the local safety policy.

At startup, RDFLib reads the repository's `ontology/*.owl.ttl` modules and the
pinned ELI/ELI-DL vocabularies to add ontology descriptions, domains, ranges,
and comments for terms selected by the contract. Active mapping files still
provide the external-predicate definitions and safety allowlist entries. The
contract is not a dump of every OWL declaration: a term's ontology declaration
alone does not make it queryable. In particular, emitted `dct:temporal`,
`eli:has_part`, and `eli:is_realized_by` triples are recorded as not executable
through the current local NLQ predicate allowlist. The NLQ grounding path does
not import private `oireachtas_etl.config` constants.

The contract distinguishes emitted data from ontology-only or currently
unavailable patterns. For example, Dáil and Seanad terms are explicitly typed
as `agents:DailTerm` or `agents:SeanadTerm`, not as `agents:HouseTerm`; the
store does not infer superclass types. Member records and their membership
resources live in per-Member graphs, while HouseTerm, collection,
constituency/panel, and Committee descriptions are owned by other graph
families. Cross-graph joins use the same RDF resource IRI. The contract also
marks office holdings as conditional on reviewed office resolution and states
that Debate/Act descriptions are not currently published.

The `labelsByEntityType` entries are intentionally distinct: Member
`foaf:name` values are plain literals, HouseTerm/collection/constituency labels
use English `skos:prefLabel`, Committees may have English or Irish
`skos:prefLabel`, and Bill primary titles use language-tagged `eli:title`.
Those predicates are not interchangeable.

Reviewed external join identifiers are represented without enabling remote
execution: accepted Member-to-Wikidata links use `owl:sameAs` in the separately
owned Member external-links graph; Party-to-Wikidata links use
`members:recognisedAsParty` and do **not** assert identity; reviewed Wikipedia
links use `foaf:isPrimaryTopicOf`. These graph patterns are optional and no
Wikidata query or federation is performed.

### Contract compatibility

- `schemaVersion` identifies the JSON shape. This consumer supports schema
  version `1` and fails clearly on any other value.
- `contractVersion` is semantic versioning. Additive classes, properties,
  graph families, emitted patterns, or descriptive metadata that preserve all
  existing meanings may use a `1.x` minor/patch release. A removal, renamed
  term, changed graph owner or IRI pattern, changed label/pattern semantics,
  changed identity meaning, or incompatible entailment/safety change requires a
  new contract major. This consumer supports major `1` and rejects others.
- Consumers of a compatible minor version should ignore unknown optional
  fields while retaining the meaning of known fields. A new safety behavior is
  not an additive schema-only change: a change to accepted query capability or
  an enforced safety limit requires a `localSafety` major and contract major
  bump, plus a consumer implementation/test update. This consumer rejects
  unsupported local-safety major versions.
- The contract is consumed from this repository. Cross-repository packaging or
  distribution is deferred; no extraction mechanism is implied here.

No RDF instance dataset is sent to the LLM. Fuseki remains the factual source.

## Named graph expectations

The contract is the service-facing source for exact graph IRIs/templates,
owner names, availability and owned descriptions. It lists Houses, Parties,
Constituencies, Committees, per-Member and per-Bill graphs, currently empty
Office/Administrative-unit registries, and separately owned reviewed external
link graphs. Member and Bill graph families are per-resource patterns; the
external-link families are not part of the authoritative owner graphs.

Descriptions and references may live in different named graphs. Queries join
them using the same RDF resource IRI rather than assuming that all related
triples are co-located. The contract's `crossGraphJoins` enumerates the current
supported joins.

## Query safety

Model-generated SPARQL is treated as untrusted input.

The versioned `localSafety` section records and supplies the current local
policy. The shared browser/benchmark pipeline:

- accepts RDFLib-parseable `SELECT` and `ASK` queries only; SPARQL Update and
  other query forms are rejected;
- rejects `SERVICE`, `FROM`, and `FROM NAMED`;
- rejects subqueries and variable predicates;
- permits only direct predicates, not SPARQL property paths;
- checks predicates against the contract-defined allowlist policy, whose terms
  are resolved from local ontology declarations, locally annotated external
  properties, active (`mapped`/`new`) property mappings, and the listed
  unconditional predicates;
- rejects query strings longer than 32,000 characters;
- appends `LIMIT 100` to a `SELECT` without a limit and rejects explicit limits
  over 100 (also when an explicit ASK limit is present);
- rejects offsets over 10,000; and
- uses a 15-second Fuseki request timeout.

Execution uses only the configured `NLQ_FUSEKI_QUERY_URL` Fuseki query endpoint
(default `http://localhost:3030/houses/query`), with a `/query` path. The
contract records local deployment as the expectation, but the current client
does not enforce a loopback hostname; deployment configuration must keep this
endpoint local. The POC has no federation mode. Any later controlled federation
must deliberately extend and version the safety contract, configure allowed
remote endpoints, and add remote-pattern, timeout, and complexity controls; it
must not bypass this local boundary silently.

The fixed readiness probes are also read-only.

This is still not a complete SPARQL sandbox. Expensive graph patterns can exist even in read-only queries, so the POC should remain local or otherwise isolated from untrusted public use.

## Limitations

A syntactically valid and safe SPARQL query can still be semantically wrong.

In particular:

- the store does not provide general OWL entailment;
- a few current ETL-emitted predicates (`dct:temporal`, `eli:has_part`, and
  `eli:is_realized_by`) are not in the current active property mappings or
  predicate allowlist, so the contract marks those patterns as emitted but not
  executable in local NLQ rather than expanding the safety policy implicitly;
- people, memberships, House terms and parliamentary collections are distinct resources;
- party and independent collection membership use related but not identical graph patterns;
- some ontology vocabulary is defined before corresponding instance data is populated;
- historic facts can only be returned when the required source data has been loaded;
- exact local Member-label ambiguity handling is bounded to the shared NLQ
  pipeline; it does not provide general fuzzy search or same-person merging;
- a matching local HouseTerm or constituency/panel label can narrow duplicate
  Member candidates enough to continue, but the selected Member IRI is not
  mechanically bound into the later LLM-generated answer query. That query must
  still apply the context correctly; inspect its generated SPARQL before relying
  on a context-disambiguated answer;
- there is no conversational follow-up state;
- there is no authentication or production hardening;
- the schema grounding is not a full reasoner or query planner.

Always inspect the generated SPARQL when evaluating the POC.

## Development checks

Install the test dependencies:

```bash
uv sync --locked --extra test --extra nlq
```

Run the tests:

```bash
uv run --locked pytest tests
```

Focused contract, safety, NLQ grounding, and Phase 0B benchmark-path tests:

```bash
uv run --locked pytest tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_benchmark.py
```

Run ontology validation, with the repository's pinned Java runtime available through `mise`:

```bash
mise install
mise exec -- uv run --locked python tests/validate.py
```

## Scope

This POC exists to answer one question:

> Can a schema-grounded LLM translate useful natural-language questions about the current OireachtasOntology graph into safe, inspectable SPARQL and return useful Fuseki results?

It does not redesign the ontology, modify ETL semantics, use a vector database, provide a general agent framework, or write to Fuseki.
