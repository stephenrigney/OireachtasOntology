# Natural-language query POC

This isolated experiment tests whether an ontology-grounded LLM can translate
plain-language questions into inspectable, read-only SPARQL for the current
Oireachtas RDF dataset in Fuseki. It is a small server-rendered FastAPI/Jinja
application; it is **not** part of the deterministic ETL pipeline and it does
not load, transform, validate, or publish RDF.

## Flow

```text
Question in browser
  -> OpenAI Responses-compatible LLM (schema context + question)
  -> structured { interpretation, sparql }
  -> RDFLib SPARQL parse and safety checks
  -> configured Fuseki /query endpoint
  -> SPARQL JSON converted to a result table / ASK answer
```

At startup, the POC reads every `ontology/*.owl.ttl` module with RDFLib. It
derives local classes, object/datatype properties, direct named superclass
links, asserted property domains/ranges, and useful labels/comments. It reads
the repository-pinned ELI/ELI-DL schemas and active mapping CSV rows to ground
external predicates such as `eli:title` and `eli-dl:process_status`. The query
gate rejects triple predicates not declared by this ontology or an active
mapping. It also includes the ETL's actual named-graph identifiers and ownership patterns, so
the prompt distinguishes `agents:Member`, `members:OireachtasMembership`,
`agents:HouseTerm`, `members:ParliamentaryParty`,
`members:IndependentMemberCollection`, and their separately owned graph
descriptions. It warns that Fuseki does not entail OWL subclass types, that
Independent collection memberships use the general relationship, and that the
current Members ETL does not emit Cabinet/Taoiseach role instances. No dataset
assertions are sent to the LLM.

## Install and run

From the repository root, install the optional POC dependencies:

```bash
./.venv/bin/python -m pip install -e '.[nlq]'
```

Start the repository's existing Fuseki service if it is not already running:

```bash
docker compose up -d fuseki
```

The default query URL is `http://localhost:3030/houses/query`, matching
`docker-compose.yml`. Starting Fuseki does not load RDF; use the already
published dataset. Do not set this app to a `/data`, `/update`, or admin URL.

When the home page opens, it runs a read-only readiness check against the
`/query` endpoint. It reports whether Fuseki is reachable and whether it finds
typed instance data in the Houses, Parties, Constituencies, Member, and optional
Bills graph families. For the example member questions, Houses, Parties,
Constituencies, and Member graphs are expected. “Ready” only means those graph
families have instances; it does not guarantee that a requested historic fact
is present. The check never creates, loads, replaces, or deletes a graph.

Copy the example configuration and edit `.env` with your own API key:

```bash
cp .env.example .env
# Edit .env and replace NLQ_LLM_API_KEY with your provider API key.
```

The app loads `.env` from the repository root when it starts. `.env` is
git-ignored; environment variables already set in the process take precedence.
Restart the app after editing `.env`. You can also configure these values
directly in the process environment.

Then launch the browser app:

```bash
./.venv/bin/uvicorn poc.nlq.app:app --reload
```

Open <http://127.0.0.1:8000/>. For an authenticated local Fuseki, the POC
also reads the repository's existing `OIR_FUSEKI_USER` and
`OIR_FUSEKI_PASSWORD` environment variables. The LLM endpoint must implement
the OpenAI Responses API, including structured JSON-schema output.
An HTTP 401 means the provider rejected the configured key: ensure the key and
base URL belong to the same provider (for example, an OpenCode Go key with the
OpenCode Go base URL).

### Deliberately loading data

If the readiness panel reports an empty or partial dataset, data loading stays
an explicit ETL operation—not an app-startup side effect. The ETL fetches source
records, preserves raw inputs, transforms and validates RDF, then replaces the
owned named graphs and runs competency checks before reporting success. To
publish current API data, configure the ETL's write and verification endpoints
in the shell that will run the commands:

```bash
export OIR_FUSEKI_GSP_URL='http://localhost:3030/houses/data'
export OIR_FUSEKI_SPARQL_URL='http://localhost:3030/houses/query'
```

The ETL CLI reads these from the process environment; unlike the NLQ web app, it
does not load `.env` automatically. For an authenticated Fuseki, also export
`OIR_FUSEKI_USER` and `OIR_FUSEKI_PASSWORD`. Then, from the repository root,
run only the data sources you intend to refresh:

```bash
./.venv/bin/oir-etl run houses
./.venv/bin/oir-etl run parties
./.venv/bin/oir-etl run constituencies
./.venv/bin/oir-etl run members
./.venv/bin/oir-etl run bills
```

These commands fetch from the configured Oireachtas APIs and publish validated
graphs. Review their output and source-data implications before running them.
They are not called by the NLQ app. Do not use `docker compose down -v` as a
readiness or refresh action: it deletes Fuseki's persistent volume.

### OpenCode Go / GPT-5.6 Luna

OpenCode Go's Responses-compatible endpoint can be configured as follows; use
the API key issued for your OpenCode Go account:

```bash
cp .env.example .env
```

Set these values in the root `.env` (without `export`) before launching Uvicorn:

```dotenv
NLQ_LLM_API_KEY=your-opencode-go-api-key
NLQ_LLM_BASE_URL=https://opencode.ai/zen/go/v1
NLQ_LLM_MODEL=gpt-5.6-luna
NLQ_FUSEKI_QUERY_URL=http://localhost:3030/houses/query
```

Then run `./.venv/bin/uvicorn poc.nlq.app:app --reload`.

The adapter calls `{NLQ_LLM_BASE_URL}/responses` and requests a strict JSON
schema containing `interpretation` and `sparql`. If a compatible provider does
not support Responses structured outputs, this POC intentionally reports an
error instead of guessing at response structure. It sends an application
User-Agent and a per-request `x-opencode-session` identifier as OpenCode Go
requests recommend.

## Example questions

- Who were the Fine Gael members of the 33rd Dáil?
- Which TDs represented Dublin constituencies in the 32nd Dáil?
- Which parliamentary member collection did Micheál Martin belong to in the 33rd Dáil?
- How many members were in each parliamentary member collection in the 33rd Dáil?

The exact SPARQL submitted to Fuseki is displayed with the answer, along with
the model's concise interpretation. The query debugger opens automatically for
LLM/validation/Fuseki failures and empty SELECT results. It shows the raw LLM
response when available (API-key text is redacted) and the Fuseki response JSON;
debug output is capped at 50,000 characters. SELECT outputs are limited to 100 rows.
An empty result can mean either that the graph has not been populated with the
relevant historical data or that the model's query did not match the graph;
inspect the visible SPARQL to distinguish these cases.

## Safety and limitations

- Only RDFLib-parseable model-generated `SELECT` and `ASK` are sent to Fuseki.
  The app's separate, fixed readiness probes are read-only `ASK`/`SELECT`
  requests. SPARQL Update,
  malformed queries, `SERVICE`, `FROM`, `FROM NAMED`, subqueries, property
  paths, and variable predicates are rejected. SELECT results are capped at
  100 rows (a missing limit is added; a larger limit is rejected); OFFSET is
  capped at 10,000 rows. Triple predicates are checked against ontology
  declarations and active mapping properties, including properties from the
  repository-pinned ELI vocabularies.
- The Fuseki query request has a 15-second timeout and uses only the configured
  `/query` endpoint. LLM requests time out after 45 seconds.
- The generated text is untrusted. Parsing, an operation allowlist, and simple
  endpoint/result restrictions are not a complete SPARQL sandbox; expensive
  graph patterns may still time out. Use a disposable/local Fuseki instance
  and do not expose this unauthenticated POC to untrusted users.
- The gate is not a complete SPARQL sandbox or full static type checker: it
  validates predicate vocabulary, but a supported predicate can still be used
  with the wrong resource type or graph pattern.
- A well-formed query can still be semantically wrong, miss facts not present
  in the dataset, or misunderstand the distinction between people, dated
  memberships, houses/terms, parties, independent collections, and recognised
  groups. Always inspect the query and answer.
- The schema prompt is derived from every ontology module and active mapping
  terms; application-side predicate validation rejects predicates outside the
  ontology/mapping vocabulary. This is not a full ontology reasoner,
  query planner, or data retrieval/RAG system. There is no auth, persistent
  history, conversational follow-up, or entity-resolution subsystem.
- Fuseki remains the factual source. The prompt includes schema descriptions,
  never the full RDF dataset.

This is an experimental evaluation POC only. It is deliberately separate from
ETL, validation, reconciliation, and graph publication.
