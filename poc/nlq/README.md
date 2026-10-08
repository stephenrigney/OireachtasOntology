# Natural-language query POC

This app lets you ask questions about the Oireachtas RDF data in plain English.

For example:

- Who were the Fine Gael members of the 33rd Dáil?
- Which TDs represented Dublin constituencies in the 32nd Dáil?
- Which parliamentary collection did Micheál Martin belong to in the 33rd Dáil?
- How many members were in each parliamentary collection in the 33rd Dáil?

It is an experimental local application, not a production service.

## Get it running

Run these commands from the repository root.

### 1. Add an LLM API key

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set:

```dotenv
NLQ_LLM_API_KEY=...
```

The default development configuration uses the OpenCode Console-compatible
endpoint and `gpt-6-luna`. You can override the endpoint or model in the same
file if needed.

### 2. Start the app and load local data

```bash
scripts/dev-nlq.sh --load-data
```

The launcher will:

1. install the locked NLQ dependencies;
2. start or reuse the local Fuseki service;
3. load the preserved development dataset into Fuseki; and
4. start the web application.

The data load uses preserved Oireachtas API captures already held by the
project. It does **not** fetch current API data or publish anything
authoritatively.

If your local Fuseki already contains the data you want to query, start without
reloading it:

```bash
scripts/dev-nlq.sh
```

### 3. Open the app

Open <http://127.0.0.1:8000/>.

The page shows:

- how the question was interpreted;
- the generated SPARQL query;
- the query result; and
- useful diagnostics if translation or execution fails.

### Requirements

You need:

- `uv`;
- Docker with the `docker compose` plugin; and
- `curl`.

The launcher handles the Python environment and local Fuseki startup.

## How it works

The whole application can be understood as this pipeline:

```text
plain-English question
        ↓
LLM translates the question
        ↓
generated SPARQL is checked
        ↓
Fuseki runs the query against the RDF data
        ↓
result + generated SPARQL are shown in the browser
```

The LLM does **not** answer from its own knowledge. Its job is to translate the
question into SPARQL. Fuseki remains the source of the facts returned by the
application.

No RDF instance dataset is sent to the LLM.

## The three things to keep separate

| Part | What it does |
|---|---|
| **Ontology** | Defines what Oireachtas entities and relationships mean. |
| **Query contract** | Defines the subset of that model that this application is currently allowed to query. |
| **Fuseki dataset** | Contains the RDF facts that are actually available to answer a question. |

This distinction matters. A concept can exist in the ontology without being
available through the NLQ application, and a supported query can only return a
fact if the relevant RDF has actually been loaded into Fuseki.

The machine-readable query contract is
[`poc/specs/query-schema-contract.json`](../specs/query-schema-contract.json).

## What can I ask about?

The current query contract supports useful questions about:

- Members and their Dáil or Seanad service;
- Dáil and Seanad terms;
- parliamentary parties and Independent Member collections;
- Dáil constituencies and Seanad panels;
- committees and committee membership;
- Bills and their legislative lifecycle when Bill data has been loaded; and
- selected reviewed external links where they are present.

The application currently supports read-only `SELECT` and `ASK` queries.

Debate data is not currently exposed through the NLQ query contract.

## What the app does not do

The POC deliberately has a narrow scope.

It does not:

- write to Fuseki;
- provide a general SPARQL console;
- perform general OWL reasoning;
- infer missing historical facts;
- provide conversational follow-up state;
- resolve every ambiguous person or entity name automatically;
- query Wikidata or other remote services; or
- provide production authentication or hardening.

A query can be syntactically safe and still be semantically wrong. The browser
therefore shows the generated SPARQL so that results can be inspected.

## Data loading

Normal startup:

```bash
scripts/dev-nlq.sh
```

starts the application against whatever is already in the local Fuseki
dataset.

Development bootstrap:

```bash
scripts/dev-nlq.sh --load-data
```

loads the latest suitable preserved captures available to the project before
starting the application.

This bootstrap is deliberately **non-authoritative**. It is for local
development and evaluation. It does not update production publication state,
claim complete historical coverage, or resolve quarantined identity conflicts.

Bills are only queryable when Bill graphs are present in the local dataset.

## Configuration

For normal use, `.env.local` is the only configuration file you should need.

The most useful settings are:

```dotenv
NLQ_LLM_API_KEY=...
NLQ_LLM_BASE_URL=https://opencode.ai/inference/openai/v1
NLQ_LLM_MODEL=gpt-6-luna
NLQ_FUSEKI_QUERY_URL=http://localhost:3030/houses/query
```

Only the API key is required if the defaults are suitable.

Do not append `/responses` to `NLQ_LLM_BASE_URL`; the application adds the
Responses API path itself.

An explicit shell environment variable takes precedence over the same value in
`.env.local`.

## Common problems

### `NLQ_LLM_API_KEY is not set`

Add the key to `.env.local`, or export it in your shell:

```bash
export NLQ_LLM_API_KEY=...
```

### The app opens but the dataset is empty or incomplete

Starting Fuseki does not load RDF by itself. Run:

```bash
scripts/dev-nlq.sh --load-data
```

### LLM authentication or model errors

Check `NLQ_LLM_API_KEY`, `NLQ_LLM_BASE_URL`, and `NLQ_LLM_MODEL` in
`.env.local`.

### I want to reset Fuseki

Do not use `docker compose down -v` casually: it deletes the persistent local
Fuseki volume.

For more detailed Fuseki operation and recovery guidance, see the
[Fuseki user guide](../../documentation/fuseki-user-guide.md).

## For developers

The browser and automated benchmark use the same translation, validation and
execution pipeline.

Run the focused NLQ tests with:

```bash
uv run --locked --extra test --extra nlq pytest   tests/test_nlq_contract.py   tests/test_nlq_poc.py   tests/test_nlq_benchmark.py
```

Run the deterministic regression benchmark with:

```bash
uv run --locked --extra nlq python scripts/run-nlq-benchmark.py --tier regression
```

The measured benchmark uses the configured LLM:

```bash
uv run --locked --extra nlq python scripts/run-nlq-benchmark.py --tier measured
```

The benchmark definition is
[`benchmarks/benchmark-v1.json`](benchmarks/benchmark-v1.json).

Detailed contract structure, graph families, safety limits and compatibility
rules belong in the machine-readable contract and its specification rather than
in this user guide.

## Further reading

- [Current system overview](../../documentation/current-state.md)
- [Ontology conceptual guide](../../documentation/wiki/Home.md)
- [Query schema contract](../specs/query-schema-contract.json)
- [Query Service plan](../specs/query-service-plan.md)
- [Fuseki user guide](../../documentation/fuseki-user-guide.md)

## Scope

The POC is testing one idea:

> Can an LLM turn useful plain-English questions about OireachtasOntology into
> safe, inspectable SPARQL and return useful results from the local RDF store?

It does not redesign the ontology or the ETL, and it never writes to the RDF
store.
