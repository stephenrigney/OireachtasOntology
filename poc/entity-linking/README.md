# Entity-linking evaluation PoC

This CPU-only experiment tests provisional transcript-mention links to existing
Oireachtas identities. It is **not production ETL** and publishes no facts to a
production store. Read [`plan.md`](plan.md) and the technical findings in
[`results/entity-linking-evaluation.md`](results/entity-linking-evaluation.md)
before running it.

## Isolation and data handling

- The runner accepts only `http://127.0.0.1:13037/entity_linking`. It fails
  closed on another host, port, path, or a non-empty dataset.
- Fuseki is disposable, loopback-bound, CPU/memory limited, and stores its
  dataset in container tmpfs. The experiment does not contact production
  Fuseki, Core State, Query Service, or Elasticsearch.
- The allowlist, contribution split, and identity-input checksums are frozen in
  `sources.json`. Missing downloaded AKN Works are fetched only from their
  listed official URLs and verified before use. Existing checked-in AKN example
  fixtures are reused as-is; no new transcript fixture is added.
- `prepare` writes the blind, transcript-bearing review packet and raw source
  cache only under the external work directory. The checked-in
  `results/provisional-reference.json` contains source pointers, hashes, spans,
  labels, and short mention surfaces, **not full contribution text**.
- Derived RDF is provisional and isolated in PoC named graphs. Mention surfaces
  and source offsets may be present; full transcript text is not. No candidate
  target IRI is minted.

## Setup and run

From the repository root, install the project's test/runtime environment if it
is not already present:

```bash
uv sync --extra test
```

Review the Compose configuration and start the disposable endpoint:

```bash
docker compose -p oireachtas-entity-linking-evaluation \
  -f poc/entity-linking/fuseki-compose.yml config
docker compose -p oireachtas-entity-linking-evaluation \
  -f poc/entity-linking/fuseki-compose.yml up -d
```

Optionally set a local password before both Compose and the runner:

```bash
export FUSEKI_ADMIN_PASSWORD='local-only-password'
```

Prepare the frozen sample and external blind-review packet, then run both
methods and the read-only SPARQL comparisons:

```bash
.venv/bin/python poc/entity-linking/run.py prepare \
  --work-dir /tmp/oireachtasontology/entity-linking-evaluation
.venv/bin/python poc/entity-linking/run.py run \
  --work-dir /tmp/oireachtasontology/entity-linking-evaluation \
  --fuseki-base-url http://127.0.0.1:13037/entity_linking
```

The run loads the transcript-free checked-in provisional reference by default.
It verifies the reference spans against the pinned evaluation sample and the
blind-packet/rubric fingerprints before scoring. The runner writes manifests,
identity snapshots, decision rows, RDF, retrieval results, and summaries under
`/tmp/oireachtasontology/entity-linking-evaluation/artifacts/`.

The Fuseki dataset must be empty for each run. To repeat the experiment, remove
the disposable container/tmpfs and recreate it; do not merely restart it:

```bash
docker compose -p oireachtas-entity-linking-evaluation \
  -f poc/entity-linking/fuseki-compose.yml down -v
docker compose -p oireachtas-entity-linking-evaluation \
  -f poc/entity-linking/fuseki-compose.yml up -d
```

The exact sources and identity owners are hash-checked. A failed download,
checksum mismatch, graph-integrity failure, non-empty dataset, transcript leak,
validation error, or SPARQL failure stops the run.

## Cleanup and checks

Stop and remove the isolated service and, when no longer needed, the external
source/artifact cache:

```bash
docker compose -p oireachtas-entity-linking-evaluation \
  -f poc/entity-linking/fuseki-compose.yml down -v
rm -rf /tmp/oireachtasontology/entity-linking-evaluation
```

Focused checks:

```bash
.venv/bin/python -m pytest tests/test_entity_linking_poc.py -q
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
```

Deleting the external work directory removes the blind packet and downloaded
raw AKN cache; the transcript-free provisional reference and reports remain in
the repository.
