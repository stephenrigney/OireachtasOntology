# Natural-language query POC

This proof of concept lets you ask questions about the Oireachtas RDF dataset in plain English. Its normal development path is the structured Phase 2 flow: a Responses-compatible planner proposes a semantic plan, local code resolves exact entity labels and validates the plan, a deterministic compiler generates safety-validated SPARQL, and Fuseki executes it. The model does not generate executable SPARQL on this path.

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

On success, the application shows the result. In the default Phase 2 path, expand **Validated query plan** and **Generated SPARQL** to inspect the interpretation and executable query. Phase 1 continues to show its direct-generated query using the existing display.

The application also reports:

- ambiguous local identity without selecting a candidate;
- unresolved local identity without running an answer query;
- unsupported question/semantic combinations without generating an answer query;
- planner or validation failures separately from Fuseki execution failures.

Detailed diagnostics and the raw endpoint payload, when available, are in the expandable query debugger. Internal exceptions are not used as the primary user-facing message.

Phase 2 is complete. The accepted structured local-query path is:

```text
question → semantic planner → deterministic resolution → validated query plan
         → deterministic SPARQL → local Fuseki → rendered result
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
report](benchmarks/realistic-phase2-report.md).

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
For the exact dataset ID already accepted for this benchmark, it reuses the
recorded full Member/Bill RDF acceptance while rechecking source evidence,
deterministic transforms, RDF syntax, output counts, and Fuseki's per-graph
counts. A different input identity takes the full per-resource validation path.
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
and loaded only from current clean contract-1 Core State publications with
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

## How it works

```text
Question in browser
  -> composable semantic plan v2 (default browser path)
  -> date-grounded term resolution and term-scoped entity resolution
  -> typed relation validation
  -> deterministic SPARQL compilation and safety checks
  -> configured local Fuseki /query endpoint
  -> SPARQL Results JSON
  -> result table / ASK answer in browser
```

The old structured v1 plan pipeline is retired from the application and
capabilities UI; it is not a parallel runtime. The Phase 1 direct NL→SPARQL
comparison mode remains selectable for development only. The current v2
composable contract is `poc/specs/composable-query-plan-contract.json`, with
instance shape in `poc/specs/composable-query-plan.schema.json`. The bounded
running slices include previous-Dáil constituency representation and the Q35
Minister-for-Finance office-holding interval.
The default `OIR_NLQ_AS_OF_DATE` is today; pin it (for example,
`2026-10-25`) for reproducible evaluation. Previous-term selection uses
asserted HouseTerm types and reviewed start/end dates reached through the
HouseTerm's `dct:temporal` period link, never term labels or ordinal numbers.
Constituency identity is resolved by its label together with
`members:constituencyInHouseTerm` for that selected term. The Member query joins
membership, term and representation records using reviewed mappings,
deduplicates by Member resource identity, and renders names rather than IRIs.

The only added House-term query grounding is the already-emitted and mapped
`dct:temporal` relationship plus its existing `dcat:startDate`/`dcat:endDate`
values; the query/schema contract is now `2.1.0`. The committed
`tests/expected/constituencies.ttl` fixture contains Dublin Mid-West only in
the 34th Dáil, so it is not a previous-Dáil acceptance fixture. Focused Q09
tests use explicitly synthetic constituency/member records with source-backed
term-date values to verify replacements and identity deduplication. This
proves the planner/compiler/UI path, not the complete real-world answer for
Dublin South-Central. That historical acceptance check still needs a
reviewed, sufficiently complete fixture of 33rd-Dáil South-Central
representation and replacement records.

Q35 resolves the office mention through exact labels on reviewed local
`NamedOffice` resources, then follows only accepted Member-owned
`OfficeHolding` records and their `members:heldOffice` references. Its
inclusive calendar-date overlap is compiled against the mapped `xsd:dateTime`
`StartDate`/`EndDate` range; a missing mapped end is open-ended, while a missing
or invalid start cannot establish tenure. Every matching holding remains a
separate result row, including repeated episodes for one Member. The local
development capture is partial and does not establish historical completeness.

The repository-owned machine-readable query contract is
`poc/specs/query-schema-contract.json` (contract version `2.4.0`, schema
version `1`). Its JSON Schema is `poc/specs/query-schema-contract.schema.json`.
The contract defines the queryable class/property scope, named-graph families
and owners, emitted RDF patterns, entity-specific label predicates,
cross-graph joins, optional reviewed external identity links, reasoning
assumptions, known unavailable patterns, and the local safety policy.

### Structured query-plan contract (Phase 2A)

The following Phase 2A/2B/2C sections are historical implementation context.
Their version-1 plan format and browser runtime have been retired; the current
application consumes the composable plan contract described above.

The semantic plan contract is `poc/specs/query-plan-contract.json` (contract
version `1.2.0`, schema version `1`). Its manifest schema is
`poc/specs/query-plan-contract.schema.json`; the plan-instance schema is
`poc/specs/query-plan.schema.json`. Seven representative plans are under
`poc/specs/query-plan-examples/`. Plans include intent, local Oireachtas source,
referenced entities, requested facts/relations, semantic filters, temporal
constraints, optional aggregation, and answer shape. They contain no SPARQL,
named graph identifiers, or SPARQL variable names.

Entity references retain their type and user label. `resolved` entities carry
one local Oireachtas IRI; `ambiguous` entities carry multiple distinct local
candidates and no selected IRI; `unresolved` entities carry neither an IRI nor
candidates. A HouseTerm reference uses its concrete `DailTerm` or `SeanadTerm`
type; the contract does not introduce a generic HouseTerm RDF type. Temporal
constraints distinguish `on`, `before`, `after`, `during`, `interval`, and
`current`. The initial aggregation operation is `count`, with
explicit target and optional grouping; answer shapes include boolean, entity,
entities, label, fact, list, count, and grouped result. Source scope is fixed to
local Oireachtas data; source selection and federation are not part of this
contract.

The manifest's `semanticVocabulary` is the source of truth for the currently
supported entity types, semantic fact IDs, and filter-field IDs. The fact IDs
cover the queryable House, Member, parliamentary-term, collection,
constituency/panel, Committee, Bill, accepted Member OfficeHolding, and selected
Debate patterns recorded by the query/schema contract; their manifest
descriptions are for people, while the IDs drive consumer dispatch. Fact IDs
and filter fields are controlled values, not natural-language descriptions or
RDF/SPARQL names. Filter fields also declare their applicable facts, value kind,
and supported operators; for example, `parliamentary_collection` is valid for
`member_collection_membership`, not for an unrelated fact. Unknown facts and
fields are rejected. The plan-schema enum and field-specific rules mirror the
manifest vocabulary, with exact parity checked by the focused contract tests.

Entity types remain a controlled set: the validator accepts only the types in
the current manifest and the plan schema. Adding a **reviewed, supported** entity
type is an additive compatible extension within contract major version `1`,
provided existing meanings and validation behavior are unchanged. The manifest,
schema enum, and focused vocabulary-parity test must be updated together;
consumers that do not yet support an added type reject it. The current extension
adds Bill and NamedOffice resolution from reviewed local labels, plus DebateRecord
as a type-only result role. Bill resolution permits only exact canonical-title
equality after removing parenthetical qualifiers and a trailing legislative
year. If a user-supplied Bill title includes a trailing year, a candidate must
carry that same year; a candidate with a different or absent title year does not
match. Without a supplied year, multiple resources with the same canonical title
remain ambiguous.
DebateRecord has no entity-label resolver because the accepted Debate slice has
no reviewed local label mapping. Its optional `debate_body` filter is restricted
to the one pinned Committee of Public Accounts route and does not enable general
Debate or transcript search.

Requirements, filters, and temporal constraints are conjunctive. Repeated
references to one entity ID denote that same entity; repeated type-only
participants of one type denote one result role (schema v1 does not express two
independent unbound roles of the same type). Ambiguous or unresolved references
are valid plan states, not executable identity bindings: a later consumer must
clarify or resolve them and must not choose a candidate or drop a dependent
constraint. Filter field IDs are controlled and fact-specific; values are
typed by the selected field. Equality is exact, with no implied fuzzy or
label-matching behavior; Bill-title canonicalization above is limited to named
entity resolution. The validator checks that IRIs use the Oireachtas
namespace but does not manufacture IRIs or independently check the resolver's
entity-type/IRI assignment. Unknown compatible optional fields may be ignored
and must not be treated as query, graph, variable, source, or endpoint
instructions.

### Structured planner path (Phase 2B)

`poc/specs/query-plan-draft.schema.json` defines the strict model-output shape
used by `poc.nlq.structured_planner.StructuredPlanner`. It contains the same
controlled facts, filters, temporal constraints, aggregation and answer shapes
as the Phase 2A contract, but its entities are only `{id, type, label}` user
mentions. It has no final-plan metadata, source override, resolution state,
candidate list or entity IRI. Required `null` slots are the strict Responses
schema's encoding for omitted optional values; the planner removes only those
documented nulls before semantic validation.

The planner uses the configured Responses-compatible endpoint's strict
`json_schema` output mode. Its prompt is built narrowly from the Phase 2A
semantic vocabulary and type/fact/filter descriptions; it contains no RDF
predicates, graph patterns or query-schema dump. Invalid JSON, invalid draft
structure, unsupported vocabulary and inconsistent semantics fail visibly.
There is one model request only: no automatic repair, regeneration or retry.

After draft validation, deterministic local exact-label resolution reuses the
Phase 1 NFC-normalised, case-insensitive, diacritic-preserving behavior. It
supports the current controlled entity types and returns exactly one local IRI,
distinct ambiguous candidates, or unresolved state. It does not fuzzy-match,
merge same-name resources, manufacture identifiers or use external services.
For duplicate Member labels, exact local HouseTerm/constituency context reuses
Phase 1 narrowing: one contextual match resolves, multiple matches remain
ambiguous, and no match preserves all original candidates. The planner also
applies Phase 1's explicit set-valued Member-reference gate before accepting a
final plan. If a plural request is drafted as a named Member
entity, it returns `set_valued_member_identity` without selecting an IRI. For
duplicate Member labels, application-generated `binding_evidence` records the
initial candidates, matched local context labels, deterministic narrowing rule
and decision, and the selected IRI only when exactly one candidate matches.
This evidence is separate from the semantic plan.
The planner inserts those results into a final plan and always calls the
authoritative Phase 2A validator before accepting it. Ambiguity returns
`clarification_required`; an absent local label returns `unresolved_entity`.
Resolver/data unavailability, unsupported resolver types, draft failures and
final-plan failures have separate result classes.

The structured planner and deterministic compiler are now connected to the
default `/ask` browser path. The compiler accepts only a `validated_plan`
`PlannerResult`, revalidates the final plan, and either returns safety-validated
local SPARQL with a mapping trace or a fail-closed outcome. The Phase 1
direct-generation path remains an optional comparison/debug mode.

Phase 2B planner-only evaluation uses selected Phase 1 controlled cases and
semantic plan invariants from `poc/nlq/benchmarks/planner-benchmark-v1.json`. It
checks source prerequisites with the existing Phase 1 coverage contract before
scoring; an unavailable prerequisite is recorded separately as source-data
coverage. This path scores planning only. Run a measured, capture-backed
planner-only evaluation with:

```bash
uv run --locked --extra nlq python scripts/run-nlq-planner-benchmark.py
```

The runner uses disposable loopback Fuseki and records run/dataset identity and
resolved non-secret model/endpoint configuration beneath the ignored
`var/nlq-planner-benchmark/runs/` directory. Ordinary automated tests use fake
model output and do not require an LLM. Unsupported requests remain manual
review because Phase 2A does not define an explicit unsupported-question plan
state. The deterministic test for the unsupported manual-review case injects a
supported draft and checks only the not-scored accounting path; it does not test
whether a model recognizes unsupported wording. The final realistic-question
benchmark was completed for the Phase 2 exit gate; the full result and close-out
are recorded in [`benchmarks/realistic-phase2-report.md`](benchmarks/realistic-phase2-report.md).

### Deterministic plan generation (Phase 2C)

`poc.nlq.plan_sparql.PlanSparqlGenerator` compiles only accepted, validated
plans. Its explicit semantic-fact dispatch maps to emitted query-schema patterns,
contract-owned graph families and allowlisted predicates; unsupported facts,
entity bindings, temporal translations, answer shapes and aggregations fail
closed. The supported `during` translation is restricted to a referenced
Dáil/Seanad term for reviewed Member membership, collection-membership and
representation paths. The additive Phase 2 expansion also supports `on` for
accepted Member-owned OfficeHolding ranges (inclusive start/end containment; a
missing end is open) and exact DebateRecord source dates normalized to midnight
without a timezone. Other date windows, `before`/`after`, `current`, HouseTerm-
owned temporal references and Committee-membership temporal joins are not
inferred. Generated entity answers remain resource IRIs; separate
contract-grounded label lookups are used only by the evaluator when comparing
resource results against label-valued expectations.

The evaluation path is `poc.nlq.plan_benchmark.run_plan_cases`; it keeps
planner, validation, binding, generation, safety, Fuseki execution and result
scoring outcomes separate. A result oracle must match the generated query form:
the runner does not borrow a coverage probe as an answer oracle. The controlled
Boolean plan has its own explicit ASK result oracle. Run measured planner →
generator → Fuseki evaluation, optionally alongside the Phase 1 direct
generation comparison, against a disposable capture-backed dataset with:

```bash
uv run --locked --extra nlq python scripts/run-nlq-plan-benchmark.py \
  --raw-dir /path/to/preserved/complete-captures --compare-phase1
```

For the accepted 37-case realistic dataset, this runner makes two independent
offline candidates from the pinned captures and runs the full per-resource
Member/Bill RDF acceptance checks on each. Each complete candidate is emitted as
deterministically ordered N-Quads and parsed before any data load. The runner
then creates a fresh disposable Fuseki container bound only to loopback, verifies
that its sole dataset has no named or default-graph data, and performs one
dataset-level N-Quads POST. It checks the exact graph inventory and per-graph
triple counts, accepted family/resource totals, representative typed resources,
quarantined Bill-graph absence, and a full N-Quads readback against every
candidate per-graph RDF 1.1 semantic hash (including simple/`xsd:string`
equivalence). Both candidates must reproduce the accepted
dataset identity, inventory and hashes before the benchmark runs on the second
verified disposable dataset. Generated N-Quads and readback files are temporary.

This is a benchmark-harness-only load path for fresh, empty disposable datasets.
It does not change the normal `oir-etl dev bootstrap` whole-graph replacement
path or the atomic whole-graph publication rule for authoritative ETL.

The measured report and known limitation are recorded in
[`benchmarks/phase-2c-report.md`](benchmarks/phase-2c-report.md). Ordinary
compiler/evaluator tests use deterministic plans and a fake Fuseki client. The
opt-in capture-backed Fuseki acceptance is:

```bash
OIR_NLQ_CAPTURE_RAW_DIR=/path/to/preserved/complete-captures \
OIR_RUN_NLQ_PLAN_FUSEKI_TESTS=1 \
uv run --locked --extra test --extra nlq pytest tests/test_nlq_plan_sparql_fuseki.py
```

The compiler is used by the default browser pipeline; the benchmark evaluator
remains separate. The final 37-case realistic benchmark, UI evidence, and
Phase 2 close-out are recorded in
[`benchmarks/realistic-phase2-report.md`](benchmarks/realistic-phase2-report.md).

### Controlled capability expansion (Phase 2)

The bounded expansion and its deferred boundaries are recorded in
[`benchmarks/phase-2-controlled-capability-expansion.md`](benchmarks/phase-2-controlled-capability-expansion.md).
It updated the query/schema contract to major version `2.0.0` because the prior
Bill lifecycle pattern incorrectly attached `eli-dl:latest_activity` to the
Bill rather than its process. Additive semantic-plan vocabulary support uses
contract version `1.2.0`; plan-contract consumers still support major `1`.
Eleven deterministic semantic-plan evaluation cases are pinned in
`benchmarks/query-service-phase-2-v1.json`. Offline generation checks run with:

```bash
uv run --locked --extra test python -m pytest tests/test_nlq_plan_phase2_evaluation.py
```

The opt-in Fuseki acceptance runs those cases against the accepted
non-authoritative development bootstrap. It requires the preserved raw captures
and committed API/Debate selection evidence to be available locally; no Core
State capture-index snapshot is needed. The bootstrap writes only to its
disposable loopback Fuseki dataset.

`poc.nlq.plan_contract` exposes `load_query_plan_contract`,
`validate_query_plan`, and `load_query_plan`. The structured Phase 2 browser path
calls this authoritative validator before compilation; the optional Phase 1
direct NL-to-SPARQL path remains separate. To test the contract artifacts,
examples, and validator:

```bash
uv run --locked --extra test python -m pytest tests/test_nlq_query_plan.py
```

The composable Query Service contract uses major version `2`; additive queryability
extensions that preserve existing meanings use a minor bump. The older Phase 2
plan contract uses major version `1` and allows additive optional extensions and additive
reviewed entity types, semantic facts, or filter fields when existing meanings
and validation behavior are unchanged. A breaking change to an existing field's
meaning, supported resolution states, or validation expectations requires a
major bump. Consumers reject unsupported schema versions, contract majors, and
semantic vocabulary values. The realistic-question benchmark has been completed
and accepted as part of the Phase 2 exit gate; the controlled Phase 1 benchmark
remains the capability/regression suite. Source selection and provenance are
the Phase 3 handoff; broader federation and external querying remain deferred.

At startup, RDFLib reads the repository's `ontology/*.owl.ttl` modules and the
pinned ELI/ELI-DL vocabularies to add ontology descriptions, domains, ranges,
and comments for terms selected by the contract. Active mapping files still
provide the external-predicate definitions and safety allowlist entries. The
contract is not a dump of every OWL declaration: a term's ontology declaration
alone does not make it queryable. Emitted `dct:temporal` triples remain outside
the active local NLQ predicate allowlist. The reviewed finite Bill-document
chain, whose connectors were initially recorded as unavailable, is now
queryable within its Bill-owned graph. The NLQ grounding path does
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
- `contractVersion` is semantic versioning. For the composable Query Service
  contract (major `2`), additive classes, properties,
  graph families, emitted patterns, or descriptive metadata that preserve all
  existing meanings may use a `2.x` minor/patch release. A removal, renamed
  term, changed graph owner or IRI pattern, changed label/pattern semantics,
  changed identity meaning, or incompatible entailment/safety change requires a
  new contract major. This consumer supports major `2` and rejects others.
- Consumers of a compatible minor version should ignore unknown optional
  fields while retaining the meaning of known fields. A new safety behavior is
  not an additive schema-only change: enforced safety-limit changes require an
  explicit compatibility decision. The finite reviewed Bill-document connector
  extension is additive, versioned as query contract `2.7.0` and local safety
  `1.1.0`, and leaves limits and rejected features unchanged. The Stage C
  HouseTerm seat-complement pattern is additive in query contract `2.8.0`; its
  authority is the active Houses mapping, transform and expected RDF, and it
  does not count Member records. Consumers reject
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
- the Phase 1 direct-generation path does not mechanically bind the local
  Member IRI selected by contextual narrowing; that live path remains unchanged.
  The separate Phase 2C path binds only the singular IRI in a validated plan and
  rejects ambiguous, unresolved and set-valued Member identity outcomes;
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
