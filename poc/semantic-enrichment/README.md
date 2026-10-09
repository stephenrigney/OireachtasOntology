# EuroVoc debate enrichment evaluation

This bounded experiment compares exact EuroVoc English-label matching with a
CPU-only embedding matcher for a frozen sample of 736 identifiable debate
speeches. It tests whether provisional subject suggestions add useful
knowledge-graph-first retrieval to the existing Debates structure. It does not
replace Elasticsearch/full-text search, change Query Service behavior, or
authorize production ingestion/publication.

## Boundaries

- Seven preserved AKN Works, 736 sampled speeches (64 historical pre-2011;
  672 post-2011), with whole-Work development/evaluation separation. The
  frozen per-source sample counts, exact source URLs, byte sizes and hashes are
  in [`sources.json`](sources.json). Only the five allowlisted missing AKN
  sources can be downloaded; there is no API census or corpus enumeration.
- The approved Debates transformer supplies Work/Expression/contribution
  identity. Validated House owner RDF resolves the sampled Dáil/Seanad Works.
  Committee owner links are not invented: the selected committee Works remain
  unresolved where the available owner evidence does not match.
- EuroVoc labels and hierarchy are an English, current-concept projection from
  an official SKOS-AP-ACT RDF/XML release. The 496,964,538-byte source is not
  committed; the source checksum and version evidence are pinned in
  `sources.json`.
- Every derived statement uses a separate disposable PoC named graph and the
  provisional `https://data.oireachtas.ie/poc/semantic-enrichment#`
  vocabulary. Classifier suggestions are explicitly `provisional-unreviewed`;
  none is asserted as an accepted Oireachtas subject assignment. Source
  transcripts are not copied into RDF.
- The Fuseki client refuses non-loopback endpoints and refuses to load into a
  dataset that already contains named graphs. The Query Service, production
  Fuseki, Core State, ontology and mappings are not modified.

## Reproduce

Prerequisites: Python 3.10+, `uv`, Docker Compose, and about 2 GB of free disk
space for the selected sources, taxonomy, FastEmbed model and generated files.
The host RAM target for the classification process is at most 4 GiB.

```bash
uv sync --extra test --extra semantic-enrichment

# Downloads only the five exact AKN objects in sources.json; the two checked-in
# Debates examples are hash-verified in place.
.venv/bin/python poc/semantic-enrichment/run.py download-sources \
  --work-dir /tmp/oireachtasontology/eurovoc-evaluation
```

Download the **EuroVoc 4.24 SKOS-AP-ACT RDF/XML** release from the Publications
Office [EuroVoc asset page](https://op.europa.eu/en/web/eu-vocabularies/eurovoc)
and place it at:

```text
/tmp/oireachtasontology/eurovoc-evaluation/taxonomy/eurovoc-skos-ap-act.rdf
```

The command verifies the exact SHA-256 and byte count before parsing. The
manifest records the source asset identifier `20260708-0`, version 4.24, the
official landing page and the separate `20260709-0` catalog metadata identifier.
Those adjacent official records have a documented count discrepancy; see the
results report. The evaluation pins the acquired bytes by checksum and does not
claim the two metadata identifiers are byte-identical.

Prepare (and optionally inspect) the corpus and blind-review packet before any
method comparison:

```bash
.venv/bin/python poc/semantic-enrichment/run.py prepare \
  --work-dir /tmp/oireachtasontology/eurovoc-evaluation
```

The transcript-bearing blind-review packet is disposable and stays under
`/tmp`; it is not committed. Then start the isolated, loopback-only Fuseki
dataset and run the end-to-end experiment:

```bash
docker compose -f poc/semantic-enrichment/fuseki-compose.yml up -d

.venv/bin/python poc/semantic-enrichment/run.py run \
  --work-dir /tmp/oireachtasontology/eurovoc-evaluation \
  --taxonomy-path /tmp/oireachtasontology/eurovoc-evaluation/taxonomy/eurovoc-skos-ap-act.rdf \
  --fuseki-base-url http://127.0.0.1:13036/semantic_enrichment

docker compose -f poc/semantic-enrichment/fuseki-compose.yml down
```

The local development password defaults to `semantic-enrichment-local`; set
`FUSEKI_ADMIN_PASSWORD` consistently for Compose and the run command if changed.
The PoC Fuseki storage is container-local tmpfs and is discarded when the
container stops. A repeated run must start a fresh dataset. Model weights and
all generated RDF/JSON are in `/tmp/oireachtasontology/eurovoc-evaluation/`;
they are not committed.

For a classifier-only diagnostic, `--skip-fuseki` omits the isolated Fuseki
load/query acceptance and must not be described as a complete PoC run.

## Methods and evaluation policy

- **Label baseline:** exact whole-word English preferred/alternative-label
  matches; one-token labels shorter than seven characters are ignored; no more
  than five concepts are retained per speech. Preferred labels and longer
  phrases rank first. Evidence/rank is not a calibrated confidence.
- **Semantic matcher:** FastEmbed 0.9.0 with `BAAI/bge-small-en-v1.5`, ONNX
  `CPUExecutionProvider`, two threads by default, and bounded 180-word
  contribution chunks. The candidate score is the maximum cosine similarity
  across chunks and a concept's preferred/alternative label vectors. The
  frozen threshold is 0.54 and at most five suggestions are emitted. A
  similarity is not a probability.
- Both methods classify the same 736 speeches and taxonomy concepts. The
  source-level split is frozen before classification; evaluation results are
  not used to tune the threshold. Eight evaluation speeches per evaluation
  source are selected independently for blind provisional review.
- The seven frozen retrieval questions cover exact subjects, explicitly
  opted-in narrower-concept traversal, date/House joins, cross-period terms,
  ambiguity/negative cases, and a structured-only control. They are in
  [`questions.json`](questions.json). Narrower traversal is never implicit in
  an exact-subject query.

## Outputs and verification

The run writes transcript-free sample manifests, per-method suggestion JSONL,
N-Triples named-graph payloads, generated read-only SPARQL, graph/triple counts,
timings, disk/RSS measurements, query results, repeatability results and a
machine-readable summary under the disposable `artifacts/` directory. Query
templates and the run script are sufficient to regenerate retrieval examples.
No source text, full taxonomy, or model binary belongs in Git.

The final measured results, query counts, provisional review, resource
measurements and limitations are documented in
[`results/eurovoc-evaluation.md`](results/eurovoc-evaluation.md).

Focused tests:

```bash
.venv/bin/python -m pytest tests/test_semantic_enrichment_poc.py
```

Required repository checks before completion:

```bash
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
```

The end-to-end command is expected to run against the dedicated loopback
Fuseki dataset; no production graph is an accepted endpoint. Stop/cleanup is
`docker compose -f poc/semantic-enrichment/fuseki-compose.yml down`.
