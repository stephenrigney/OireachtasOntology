# EuroVoc semantic-enrichment evaluation results

**Run:** 2026-10-09, bounded offline PoC; final full run completed against a
fresh disposable Fuseki dataset.
**Recommendation:** Do not integrate the current semantic matcher or its
provisional suggestions into the production ontology, ETL, Fuseki or Query
Service. The PoC demonstrates working graph joins, but its small provisional
review does not establish an accuracy or retrieval-quality improvement. No
follow-on work was started.

## Findings at a glance

- Both methods ran on the same frozen 736-speech sample. The exact-label
  baseline produced suggestions for 58.7% of evaluation speeches; the
  semantic matcher produced suggestions for all of them, generally five per
  speech. This is higher coverage, not demonstrated higher relevance.
- The seven frozen queries executed against isolated named graphs. Semantic
  retrieval added results for the historical health-policy and education
  questions, matched the baseline for climate change, returned nothing for the
  fisheries questions, and underperformed the label baseline on the explicit
  narrower fishing-industry and cross-period public-health questions.
- In the blind provisional review, the semantic method missed the only
  reviewed relevant example for the narrower fishing-industry question and
  had one true positive versus two for the baseline on cross-period public
  health. Conversely, it found one reviewed relevant historical health-policy
  contribution where the baseline found none. The review is too small and
  uncertain to support general accuracy claims.
- The final run was repeatable on a representative subset, used 963.08 MiB
  peak RSS (below the 4 GiB limit), took 396.33 seconds end to end, and
  loaded 108,023 triples into 14 graphs in the disposable dataset.

## Corpus and provenance

The sample contains 736 identifiable speeches from seven preserved AKN Works:
64 deliberately selected pre-2011 historical speeches and 672 post-2011
speeches. Whole Works were kept within a single split: 276 development and
460 evaluation speeches. The historical stratum is exploratory and is not
representative of all earlier debates.

| Work | Source speeches | Sample | Split | Period |
| --- | ---: | ---: | --- | --- |
| Joint Committee on Health and Children, 2009-01-29 | 313 | 64 | evaluation | historical |
| Dáil, 2025-02-27 | 472 | 180 | development | post-2011 |
| Seanad, 2025-02-27 | 102 | 60 | evaluation | post-2011 |
| Joint Committee on Finance etc., 2026-09-30 | 36 | 36 | development | post-2011 |
| Seanad, 2026-09-30 | 103 | 60 | development | post-2011 |
| Committee of Public Accounts, 2026-09-24 | 929 | 160 | evaluation | post-2011 |
| Dáil, 2026-02-25 | 428 | 176 | evaluation | post-2011 |
| **Total** |  | **736** | **276 development / 460 evaluation** | **64 historical / 672 post-2011** |

The deterministic sample SHA-256 is
`c222648f3ce604a92ccc10e401df9ff947005485b2a5200a77f02283aa708220`;
the source-manifest SHA-256 is
`31545560286f5dc8cc5891445ebf6a8382f42a087d30dc6a7b7d92327959d4aa`.
The source hashes, exact URLs, selected counts, and taxonomy provenance are
recorded in [`sources.json`](../sources.json). The approved Debates
transformation supplied Work and contribution identities. Sampled Dáil and
Seanad House owner links resolved against the validated House data; the
selected committee owner links remain unresolved where no matching owner
evidence was available. No owner identities were invented.

Source transcript text was used only in local classification artifacts and
was not copied into RDF. The generated graphs refer to stable contribution
IRIs and record source/text checksums and provisional classifier provenance.
Every suggestion has status `provisional-unreviewed`; none is an accepted
Oireachtas subject assignment.

## EuroVoc projection and metadata discrepancy

The input was the official EuroVoc 4.24 SKOS-AP-ACT RDF/XML asset pinned as
release `20260708-0`, 496,964,538 bytes, SHA-256
`f3fa0e26f15e4ea9aa10241daa37af6a27f28557d20d50bb44cbc541dddd2fb3`, under
the CC BY 4.0 license. The projection retained English preferred/alternative
labels and hierarchy links for current concepts. Streaming parsing observed
7,536 typed `skos:Concept` resources: 7,429 current and 107 deprecated; 7,429
current concepts and 40,066 triples were projected.

The separate official catalog descriptor identifies a 2026-07-09 record
(`20260709-0`, also version 4.24) and reports 7,615 entities, including 7,486
`skos:Concept` entities. Its reported concept count differs by 50 from the
7,536 concepts parsed from the pinned `20260708-0` asset. These are distinct
release identifiers: the evaluation pins and describes the acquired bytes by
checksum and does not claim that the adjacent catalog record is byte-identical
or that its counts describe those bytes. The discrepancy was not reconciled
by substituting or modifying taxonomy data.

## Methods and classification outcomes

Both classifiers used the same 736 contributions and the same English
EuroVoc projection. The label baseline matched whole preferred/alternative
labels, ignored one-token labels shorter than seven characters, and retained
up to five suggestions. FastEmbed 0.9.0 with
`BAAI/bge-small-en-v1.5` ran CPU-only with two threads. It compared cosine
similarity across bounded 180-word contribution chunks and concept labels,
used the frozen 0.54 threshold, and retained at most five suggestions. Rank,
exact-match evidence and raw cosine similarity are not calibrated
probabilities. The 17-file model cache was 200,825,674 bytes with SHA-256
`83cce0877503f80d56cf911dfad6be4a5612a443eb7b262b70afd04f71cb5b7f`.

| Split / method | Speeches with suggestions | Coverage | Suggestions | Mean suggestions per speech | Abstentions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development — label baseline | 188 / 276 | 68.1% | 711 | 2.58 | 88 |
| Development — semantic | 276 / 276 | 100% | 1,377 | 4.99 | 0 |
| Evaluation — label baseline | 270 / 460 | 58.7% | 897 | 1.95 | 190 |
| Evaluation — semantic | 460 / 460 | 100% | 2,296 | 4.99 | 0 |

The semantic matcher did not abstain on any sampled speech despite the score
threshold. This experiment therefore does not show that its broader coverage
is a usable precision/recall trade-off; it shows that this configuration
nearly always emits its maximum number of suggestions. The threshold was not
retuned against the evaluation set.

## Frozen retrieval questions

The questions were frozen before comparing the methods and are preserved in
[`questions.json`](../questions.json). Each count below is a number of unique
speech IRIs returned in the sampled Works, not a count of independently
verified relevant speeches. For the subject queries, both classifier graphs
were queried with the same structured Work/date/House constraints. Narrower
EuroVoc traversal was used only for the two questions that explicitly opted
in.

| Question | Retrieval policy | Label baseline | Semantic | Query time, label / semantic |
| --- | --- | ---: | ---: | ---: |
| q1 Historical health policy | exact concept | 0 | 2 | 0.111 / 0.091 s |
| q2 Seanad fisheries policy | exact concept | 0 | 0 | 0.052 / 0.051 s |
| q3 Seanad fishing industry | concept plus narrower concepts | 2 | 0 | 0.038 / 0.086 s |
| q4 Dáil climate change | exact concept | 2 | 2 | 0.070 / 0.096 s |
| q5 Cross-period public health | concept plus narrower concepts | 5 | 4 | 0.076 / 0.213 s |
| q6 Dáil education policy | exact concept | 0 | 8 | 0.036 / 0.064 s |
| q7 Seanad structured-only control | no subject classifier | 102 | — | 0.034 s |

Examples and interpretation:

- For q1, semantic retrieval returned two speeches, including the sampled
  contribution `.../e-spk_296`; the blind reviewer judged that contribution
  relevant to health policy. The baseline returned no results. The other
  semantic hit was not in the reviewed subset, so its relevance is unknown.
- For q3, the label baseline returned two speeches, including `.../e-spk_67`,
  judged relevant to fishing-industry activity; semantic retrieval returned
  none. This is a concrete sampled regression, despite the semantic method's
  additional coverage elsewhere.
- For q4, both methods returned the same two climate-change speeches. They
  were not in the reviewed subset, so these matching results are not
  independently confirmed relevant.
- For q5, baseline results were exact-label matches in the 2009 Work; semantic
  results spanned the 2009 and 2026 Works through explicit narrower traversal.
  The reviewed semantic hit `.../e-spk_914` was judged relevant to public
  health, but the sampled review still favored the baseline on recall. The
  no-overlap between returned speeches is a reminder that result counts alone
  are not quality measures.
- For q6, semantic retrieval returned eight speeches and the baseline none.
  The sole relevant contribution in that question's eight-speech blind review
  (`.../e-spk_177`) was not among the semantic results. The relevance of the
  eight returned speeches was not otherwise adjudicated.
- The q7 structured-only control returned 102 speeches from the sampled
  Seanad Work using debate structure and validated HouseTerm data, without
  subject links.

All 13 SPARQL query executions completed; per-query times ranged from 0.034
to 0.213 seconds in this local run. These timings are illustrative for the
small local dataset, not production service benchmarks.

## Blind provisional review

An independent agent, blind to classifier outputs, judged eight deterministic
evaluation contributions per evaluation Work: 32 distinct speeches and 56
question/contribution judgments. The rubric was frozen with the questions;
uncertain judgments were retained and excluded from TP/FP/FN/TN counts. The
complete judgments and reasons are in
[`provisional-review.json`](provisional-review.json). They are provisional
agent assessments, not human validation or a gold standard.

| Question | Relevant / irrelevant / uncertain | Label TP / FN / FP / TN | Semantic TP / FN / FP / TN |
| --- | ---: | ---: | ---: |
| q1 Historical health policy | 6 / 0 / 2 | 0 / 6 / 0 / 0 | 1 / 5 / 0 / 0 |
| q2 Seanad fisheries policy | 1 / 3 / 4 | 0 / 1 / 0 / 3 | 0 / 1 / 0 / 3 |
| q3 Seanad fishing industry | 1 / 3 / 4 | 1 / 0 / 0 / 3 | 0 / 1 / 0 / 3 |
| q4 Dáil climate change | 0 / 4 / 4 | 0 / 0 / 0 / 4 | 0 / 0 / 0 / 4 |
| q5 Cross-period public health | 7 / 2 / 7 | 2 / 5 / 0 / 2 | 1 / 6 / 0 / 2 |
| q6 Dáil education policy | 1 / 3 / 4 | 0 / 1 / 0 / 3 | 0 / 1 / 0 / 3 |

The table's denominators are the small reviewed subset only. For q1, recall
on the six determinate relevant judgments was 0/6 for the baseline and 1/6
for semantic. For q3 it was 1/1 and 0/1; for q5, 2/7 and 1/7. No false
positives were observed in this review, but that does not establish high
precision: the sample is small, deliberately stratified, has many uncertain
judgments, and does not independently assess all query hits. The reviewed
results cannot support corpus-wide accuracy or recall estimates.

## Runtime, memory, disk and graph isolation

| Measure | Final run |
| --- | ---: |
| End-to-end wall time | 396.33 s (6 min 36 s) |
| Classification process peak RSS | 963.08 MiB (below 4 GiB limit) |
| Semantic classification stage | 206.51 s |
| Model load / candidate embedding stage | 159.48 s |
| Label-baseline classification stage | 0.31 s |
| Repeatability sample (both methods) | 16 contributions; both stable |
| Fuseki upload plus queries | 6.19 s (upload 5.17 s) |
| Fuseki graph / triple count | 14 / 108,023 |

The 14 graphs comprised nine transformed source/owner graphs, one separate
EuroVoc projection graph (40,066 triples), and four separate
method-by-split enrichment graphs. Fuseki ran only on the loopback address
`127.0.0.1:13036`, used the disposable Compose configuration and temporary
storage, and required an empty dataset before loading. The initial execution
exposed a malformed multi-Work SPARQL `UNION`; the query builder was corrected
to emit braced UNION operands, a syntax regression test was added, and the
successful full run used a freshly recreated empty Fuseki dataset. No
production endpoint or graph was accessed or modified.

Measured local disk bytes were 496,964,538 for the taxonomy source,
200,825,674 for the 17-file model cache, 2,820,187 for the seven source files,
and 29,240,720 for generated artifacts (729,851,119 bytes total, about
696.0 MiB). Source, model, taxonomy and run artifacts remain outside Git;
generated artifacts can be regenerated using the commands below.

## Reproduction and verification

From the repository root, with the pinned inputs cached as documented in the
[PoC README](../README.md):

```bash
docker compose -f poc/semantic-enrichment/fuseki-compose.yml up -d
.venv/bin/python poc/semantic-enrichment/run.py run \
  --work-dir /tmp/oireachtasontology/eurovoc-evaluation \
  --taxonomy-path /tmp/oireachtasontology/eurovoc-evaluation/taxonomy/eurovoc-skos-ap-act.rdf \
  --fuseki-base-url http://127.0.0.1:13036/semantic_enrichment
docker compose -f poc/semantic-enrichment/fuseki-compose.yml down
```

The successful command wrote a complete machine-readable summary and query
evidence under the ignored disposable `artifacts/` directory. Both classifier
outputs were stable on an identical 16-contribution sample drawn across the
four evaluation Works. The final run used sample hash
`c222648f3ce604a92ccc10e401df9ff947005485b2a5200a77f02283aa708220`; both
repeatability flags were true. The summary also recorded `transcript_text_in_rdf:
false` and 14 named graphs with the expected counts.

Repository verification completed:

| Check | Outcome |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_semantic_enrichment_poc.py -q` | 8 passed |
| `mise exec -- .venv/bin/python tests/validate.py` | Passed (2,504 ontology triples) |
| `mise exec -- .venv/bin/python -m pytest tests` | 868 passed, 14 skipped |
| `uv lock --check` | Passed |
| `git diff --check` | Passed |
| `docker compose -f poc/semantic-enrichment/fuseki-compose.yml config --quiet` | Passed |

The repository's configured Java runtime is managed by `mise`; the
consistency validator and full suite were therefore run inside `mise exec`.
The full suite emitted existing RDFLib/pySHACL deprecation warnings; no tests
failed in the verified run.

## Limitations and conclusion

- The provisional reference is small, agent-produced, and not human-validated;
  some contributions are fragments, and many were judged uncertain.
- Query result counts are not relevance counts. Only 32 distinct speeches
  received blind review; most returned results were not individually judged.
- The semantic method's 100% coverage and near-five-suggestion density show
  little effective abstention at the selected threshold. Similarity scores
  are not probabilities, and suggestions remain unreviewed.
- EuroVoc labels are English-only in this projection. Irish-specific terms,
  historical terminology drift, ambiguous/short contributions and vocabulary
  gaps remain material risks.
- Selected Committee owner data did not resolve for all sampled Works.
  Unresolved owners were preserved as unresolved, not imputed.
- Resource measurements describe this small sample and local machine only;
  full-corpus runtime, storage and quality were not extrapolated.
- The taxonomy count discrepancy between the pinned asset and adjacent
  catalog metadata remains unresolved and is reported rather than hidden.

The PoC passes as a reproducible technical experiment: source-derived graphs,
provisional enrichment graphs, SKOS traversal, structured joins, bounded
CPU-only classification, repeatability checks and isolated Fuseki queries all
worked within the approved limits. The evidence does **not** show that the
current semantic configuration materially improves retrieval quality over
the label baseline. Keep production systems unchanged. Any future decision to
continue should first require owner approval and a substantially stronger,
human-reviewed relevance evaluation with an explicit abstention policy; no
such follow-on work is part of this result.
