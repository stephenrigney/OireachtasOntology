# Natural-language query POC

This proof of concept lets you ask questions about the Oireachtas RDF dataset in plain English.

The application sends the question, together with schema context derived from the repository ontology, to an OpenAI Responses-compatible LLM. The model returns read-only SPARQL, the application validates it, runs it against Fuseki, and shows both the result and the generated SPARQL.

This is an experimental query interface. It is separate from the deterministic ETL pipeline and never writes to Fuseki.

## Quick start

Run all commands from the repository root.

### 1. Install the POC dependencies

The repository uses `uv` for the POC environment:

```bash
uv sync --extra nlq
```

At present the repository package itself is not installed by `uv sync`, so commands that import `oireachtas_etl` must include `PYTHONPATH=src`. This is a repository packaging limitation, not an NLQ configuration setting.

### 2. Start Fuseki

```bash
docker compose up -d fuseki
```

The default query endpoint is:

```text
http://localhost:3030/houses/query
```

Starting the container does **not** load RDF data. The POC only queries data that is already present.

### 3. Configure the LLM

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the repository-root `.env`.

For OpenCode Console inference with GPT-6 Luna:

```dotenv
NLQ_LLM_API_KEY=your-service-account-key
NLQ_LLM_BASE_URL=https://opencode.ai/inference/openai/v1
NLQ_LLM_MODEL=gpt-6-luna
NLQ_FUSEKI_QUERY_URL=http://localhost:3030/houses/query
```

Do **not** add `/responses` to `NLQ_LLM_BASE_URL`; the application adds it.

The application loads `.env` automatically when it starts. Existing process environment variables take precedence. Restart the application after changing `.env`.

For an authenticated local Fuseki instance, also set:

```dotenv
OIR_FUSEKI_USER=...
OIR_FUSEKI_PASSWORD=...
```

### 4. Start the application

```bash
PYTHONPATH=src uv run uvicorn poc.nlq.app:app --reload
```

### 5. Open the browser interface

Open:

<http://127.0.0.1:8000/>

The home page performs a read-only readiness check against Fuseki and reports whether the expected graph families are present.

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

## If the application does not start

### `ModuleNotFoundError: No module named 'oireachtas_etl'`

Run the application with the repository source directory on `PYTHONPATH`:

```bash
PYTHONPATH=src uv run uvicorn poc.nlq.app:app --reload
```

You can verify the ETL package is visible with:

```bash
PYTHONPATH=src uv run python - <<'PY'
import oireachtas_etl.config as c

print("Loaded from:", c.__file__)
print("HOUSES_GRAPH =", c.HOUSES_GRAPH)
print("PARTIES_GRAPH =", c.PARTIES_GRAPH)
print("CONSTITUENCIES_GRAPH =", c.CONSTITUENCIES_GRAPH)
print("OFFICES_GRAPH =", c.OFFICES_GRAPH)
print("ADMINISTRATIVE_UNITS_GRAPH =", c.ADMINISTRATIVE_UNITS_GRAPH)
PY
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

If this succeeds but the POC fails, check that the values in the repository-root `.env` exactly match the working endpoint and model.

### Fuseki is reachable but the readiness panel is empty or partial

Starting Fuseki does not populate it. Data loading is deliberately an ETL operation, not an application startup side effect.

See the next section if you intentionally want to refresh your local dataset.

## Loading data into local Fuseki

Only do this when you intend to fetch and publish current Oireachtas API data.

Set the ETL write and verification endpoints in the shell:

```bash
export OIR_FUSEKI_GSP_URL=http://localhost:3030/houses/data
export OIR_FUSEKI_SPARQL_URL=http://localhost:3030/houses/query
```

For authenticated Fuseki, also export `OIR_FUSEKI_USER` and `OIR_FUSEKI_PASSWORD`.

Under the repository's current packaging setup, run the ETL module with `PYTHONPATH=src`:

```bash
PYTHONPATH=src uv run python -m oireachtas_etl.cli run houses
PYTHONPATH=src uv run python -m oireachtas_etl.cli run parties
PYTHONPATH=src uv run python -m oireachtas_etl.cli run constituencies
PYTHONPATH=src uv run python -m oireachtas_etl.cli run members
```

Bills are optional for the member-oriented example queries:

```bash
PYTHONPATH=src uv run python -m oireachtas_etl.cli run bills
```

The POC never invokes these commands itself.

Do not use `docker compose down -v` as a refresh step: it deletes Fuseki's persistent volume.

## How it works

```text
Question in browser
  -> OpenAI Responses-compatible LLM
       - repository-derived schema context
       - dataset graph conventions
       - user question
  -> structured { interpretation, sparql }
  -> RDFLib SPARQL parsing and safety checks
  -> configured Fuseki /query endpoint
  -> SPARQL Results JSON
  -> result table / ASK answer in browser
```

At startup, the POC reads the repository's `ontology/*.owl.ttl` modules with RDFLib.

It derives model-facing context from:

- local classes;
- object and datatype properties;
- direct named superclass relationships;
- asserted property domains and ranges;
- useful labels and comments;
- the repository-pinned ELI and ELI-DL schemas;
- active mapping CSV rows for reused external predicates;
- the ETL's actual named-graph conventions.

The prompt distinguishes important concepts such as:

- `agents:Member`;
- `members:OireachtasMembership`;
- `agents:HouseTerm`;
- `members:ParliamentaryParty`;
- `members:IndependentMemberCollection`.

No RDF instance dataset is sent to the LLM. Fuseki remains the factual source.

## Named graph expectations

The POC uses the same graph conventions as the ETL:

| Data | Named graph |
|---|---|
| Houses | `https://data.oireachtas.ie/graph/houses` |
| Parties | `https://data.oireachtas.ie/graph/parties` |
| Constituencies | `https://data.oireachtas.ie/graph/constituencies` |
| Offices | `https://data.oireachtas.ie/graph/offices` |
| Administrative units | `https://data.oireachtas.ie/graph/administrative-units` |
| Members | `https://data.oireachtas.ie/graph/member/{memberCode}` |
| Bills | `https://data.oireachtas.ie/graph/bill/{year}/{number}` |

Descriptions and references may live in different named graphs. Queries should join them using the same RDF resource IRI rather than assuming all related triples are co-located.

## Query safety

Model-generated SPARQL is treated as untrusted input.

The POC currently:

- accepts only RDFLib-parseable `SELECT` and `ASK` queries;
- rejects SPARQL Update operations;
- rejects `SERVICE`;
- rejects `FROM` and `FROM NAMED`;
- rejects subqueries;
- rejects property paths;
- rejects variable predicates;
- validates predicates against ontology declarations and active mappings;
- caps SELECT results at 100 rows;
- caps OFFSET at 10,000 rows;
- applies a 15-second Fuseki timeout;
- uses only the configured Fuseki `/query` endpoint.

The fixed readiness probes are also read-only.

This is still not a complete SPARQL sandbox. Expensive graph patterns can exist even in read-only queries, so the POC should remain local or otherwise isolated from untrusted public use.

## Limitations

A syntactically valid and safe SPARQL query can still be semantically wrong.

In particular:

- the store does not provide general OWL entailment;
- people, memberships, House terms and parliamentary collections are distinct resources;
- party and independent collection membership use related but not identical graph patterns;
- some ontology vocabulary is defined before corresponding instance data is populated;
- historic facts can only be returned when the required source data has been loaded;
- there is no dedicated entity-resolution subsystem;
- there is no conversational follow-up state;
- there is no authentication or production hardening;
- the schema grounding is not a full reasoner or query planner.

Always inspect the generated SPARQL when evaluating the POC.

## Development checks

Install the test dependencies:

```bash
uv sync --extra test --extra nlq
```

Run the tests:

```bash
PYTHONPATH=src uv run pytest tests
```

Run ontology validation, with the repository's pinned Java runtime available through `mise`:

```bash
mise install
PYTHONPATH=src mise exec -- uv run python tests/validate.py
```

## Scope

This POC exists to answer one question:

> Can a schema-grounded LLM translate useful natural-language questions about the current OireachtasOntology graph into safe, inspectable SPARQL and return useful Fuseki results?

It does not redesign the ontology, modify ETL semantics, use a vector database, provide a general agent framework, or write to Fuseki.
