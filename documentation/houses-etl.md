# Phase 1 Houses ETL

`oir-etl run houses --fixture data/api_examples/houses.json --offline` preserves
the fixture bytes under `data/raw/houses/YYYY-MM-DD/`, transforms the Houses
mapping, validates the result, and can write inspection/publication formats:

```text
oir-etl run houses --fixture data/api_examples/houses.json --offline \
  --output-ttl houses.ttl --output-nq houses.nq
```

Without `--fixture`, the configured API is paged using `skip` and `limit` and
transient HTTP failures are retried. Set `OIR_API_URL`, `OIR_API_LIMIT`,
`OIR_RAW_DIR`, `OIR_API_RETRIES`, or `OIR_API_TIMEOUT` as needed.

Set `OIR_FUSEKI_GSP_URL` (or pass `--fuseki-gsp-url`) to publish after all
validation succeeds. Publication is one Graph Store Protocol `PUT` with
`graph=https://data.oireachtas.ie/graph/houses`; it replaces the entire named
graph, rather than delete/insert. Credentials are accepted only from
`OIR_FUSEKI_USER` and `OIR_FUSEKI_PASSWORD`; do not place credentials in files.
`OIR_FUSEKI_SPARQL_URL` (or `--fuseki-sparql-url`) is also required for a
publishing run: the CLI checks the packaged, graph-scoped competency queries
before reporting success. The run summary includes every excluded combined-house
record. Only `houseCode == "dail & seanad"` is excluded; other unknown codes
remain errors.

Raw JSON and its sidecar metadata are immutable. A path collision with different
bytes fails. Metadata records endpoint, exact parameters, retrieval timestamp,
HTTP status, SHA-256, ETL version, and identifiers for the agents ontology and
Houses mapping versions. `data/raw/` is ignored by Git. The ontology and
mapping version identifiers default to the packaged Phase 1 baseline
identifiers (they are not necessarily hashes) and can be explicitly pinned
with `OIR_ONTOLOGY_VERSION` and `OIR_MAPPING_VERSION`; no repository-relative
file is required by an installed CLI.

The Houses graph owns and emits the exact persistent House descriptions, while
the transformer describes HouseTerm resources and references those persistent
House IRIs. It emits no redundant source fields.
The deterministic period resource is `<term-uri>#term-period`. Turtle is for
inspection; sorted N-Quads is the deterministic dataset serialization.

For a reproducible local store, run `docker compose up -d fuseki`. Its persistent
`fuseki-data` volume is local development storage only. Use
`http://localhost:3030/houses/data` for GSP and
`http://localhost:3030/houses/query` for SPARQL. Set
`OIR_TEST_FUSEKI_GSP_URL` and `OIR_TEST_FUSEKI_SPARQL_URL` to run the optional
real-Fuseki integration test. For an authenticated Fuseki, optionally set
`OIR_TEST_FUSEKI_USER` and `OIR_TEST_FUSEKI_PASSWORD`; do not place credentials
in files.
