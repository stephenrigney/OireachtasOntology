# Entity-linking evaluation — technical evidence

## 1. Decision boundary and method

This is a bounded, non-production evaluation of transcript mention detection
and provisional linking. It preserves existing contribution and target
identities, creates no target IRI, does not copy full transcripts into RDF, and
loads only disposable loopback Fuseki. It does not change ontology/mapping
semantics, production stores, Query Service, or Elasticsearch.

The frozen candidate inventory came only from validated local data: one Member,
one Bill, three reviewed NamedOffices, and one reviewed AdministrativeUnit.
This inventory is intentionally incomplete. A match outside it is recorded as
out-of-registry; it is not assigned a fabricated target.

Both methods share the same Unicode-normalized whole-token mention detector:

1. **Exact baseline** (`exact-name-identifier-v1`) accepts a unique exact name,
   alias, or supported identifier without contextual constraints.
2. **Contextual conservative** (`context-aware-conservative-v1`) additionally
   checks Member membership dates, Bill source-event timing, reviewed office
   alias validity and nearby same-sentence office wording, and reviewed unit
   names. It abstains where office-versus-holder evidence is insufficient.
3. Generic/anaphoric references are retained as unresolved mentions. A small
   set of title-led forms can be labelled out-of-registry; this is not general
   NER and does not create targets.

Because the detector is shared, the baseline/contextual comparison is about
resolution and abstention, not an independent detector comparison. The frozen
review rubric counts exact contribution/category/span boundaries for mention
detection. Resolution can align exact spans or full containment spans within
the same contribution/category, so a determiner-boundary difference does not
erase a supported target comparison.

## 2. Frozen corpus and provenance

Seven hash-pinned Works supplied 2,383 source speeches; deterministic
contribution sampling selected 736 (below the 1,000 cap). A Work-level split
was fixed before comparison: 276 development and 460 evaluation. The
evaluation contains four Works; 64 selected contributions are from the
explicitly historical 2009 committee Work.

| Work source | Split | Selected | Source SHA-256 |
|---|---:|---:|---|
| Joint Committee on Health and Children, 2009-01-29 | evaluation | 64 | `62192e167006b3a974654be417c62e98da02fd1c77da210049f1f8fb7f132ff3` |
| Dáil, 2025-02-27 | development | 180 | `fb5167c2cefb3d468c03ac0418a46de8a71c2cda078daec859d8ed4a454380e6` |
| Seanad, 2025-02-27 | evaluation | 60 | `aff86778d8f0804224c8c0042c8fefe27060135843c3fd1a311d0d1fee14d0eb` |
| Joint Committee on Finance, 2026-09-30 | development | 36 | `53d196077a672cd36fdea8e28b76e1950dff6e836eb0c5d73719cc3a2e453ab7` |
| Seanad, 2026-09-30 | development | 60 | `bf3c338fa4cb2b230d4f180e2af5189a903662660bb6732c1ae93c53e9c45eb2` |
| Committee of Public Accounts, 2026-09-24 | evaluation | 160 | `690dada15afa1cb76ece7dd8387b973b00b43804023521b9ffb821d8944ff60e` |
| Dáil, 2026-02-25 | evaluation | 176 | `1e6762bae013b22c37a4167f630530189bbf8f7057214b0676e699d97ed946ad` |

All downloaded AKN and run artifacts stayed under the external work directory.
Two already checked-in AKN examples were reused unchanged. The frozen
source-manifest hash is
`31545560286f5dc8cc5891445ebf6a8382f42a087d30dc6a7b7d92327959d4aa`; the
selected sample hash is
`a31de22d150540b8fcc65faab5eebb1ed40056fa81baff81d595bd4c789bf249`.

The four evaluation Works supplied a 21-contribution review packet: four
deterministic random contributions per Work plus up to four identity-name
opportunities per category, deduplicated. The name-stratified selection found
one AdministrativeUnit opportunity, four NamedOffice opportunities, and no
Member or Bill opportunities. One AI reviewer supplied provisional labels;
there was no independent human review. The checked-in reference contains 85
mention annotations (39 Member, 2 Bill, 27 NamedOffice, 17 AdministrativeUnit),
of which 15 were marked uncertain and excluded from positive metrics. Only one
reviewed mention had an existing supported target: Department of Finance.
There was no supported Member, Bill, or NamedOffice resolution denominator.
As an additional prediction-side scoring rule beyond the frozen annotation
labels, predictions overlapping an uncertain annotation of the same category
in the same contribution were excluded from scoring; this removed three
NamedOffice predictions from each method. The frozen rubric was not changed,
and reviewer labels were not relabelled.

## 3. Evaluation outcomes

The figures below cover the 460 evaluation contributions, not the development
split. `Out-of-registry` denotes a detected surface without a validated target;
generic references are expected abstentions. All decisions are provisional.

| Category | Evaluation mentions | Exact baseline | Contextual conservative | Interpretation |
|---|---:|---|---|---|
| Members | 232 | 171 out-of-registry; 61 abstained; 0 resolved | Same | No explicit match to the one supported Member. The sample does not test Member linking quality for known targets. |
| Bills | 43 | 4 out-of-registry; 39 abstained; 0 resolved | Same | No match to Finance Bill 2025. Generic references remain unresolved. |
| NamedOffices | 239 | 38 resolved; 185 abstained; 16 out-of-registry | 1 resolved; 37 ambiguous; 185 abstained; 16 out-of-registry | Context reduced title-only acceptance sharply; correctness of the single contextual result is unreviewed. |
| AdministrativeUnits | 59 | 1 resolved; 44 abstained; 14 out-of-registry | Same | One exact Department of Finance identity resolved; all other mentions lack a supported target or are generic. |

Abstentions above are generic/anaphoric references. Counts are mention
occurrences, not unique contributions. The out-of-registry detector uses
bounded title-led patterns and is not a census of unknown entities.

### Provisional reviewed-span and target scores

The detector is shared, so both methods have identical span-detection scores on
the 21 reviewed contributions. Exact boundaries are strict; uncertainty is not
counted as a positive span, and overlapping predictions are excluded rather
than counted as false positives.

| Category | Exact-span TP / FP / missed | Precision / recall | Supported target mentions | Baseline target outcome | Contextual target outcome |
|---|---:|---:|---:|---|---|
| Members | 33 / 5 / 6 | 0.868 / 0.846 | 0 | No denominator | No denominator |
| Bills | 2 / 1 / 0 | 0.667 / 1.000 | 0 | No denominator | No denominator |
| NamedOffices | 6 / 10 / 17 | 0.375 / 0.261 | 0 | 6 accepted links in reviewed contributions were unsupported/annotated office-holder ambiguity; precision 0/6 | No reviewed accepted link; no target-resolution denominator |
| AdministrativeUnits | 1 / 3 / 5 | 0.250 / 0.167 | 1 | 1 correct; coverage 1/1; accepted-link precision 1/1 | 1 correct; coverage 1/1; accepted-link precision 1/1 |

The office exact baseline therefore over-resolved all six of its reviewed
Taoiseach candidate mentions that the reviewer judged ambiguous. The contextual
method abstained on those reviewed cases. The one supported AdministrativeUnit
resolution is promising but far too small to establish category accuracy. The
Member/Bill span scores concern generic/out-of-registry references, not
successful target linking.

## 4. Frozen retrieval questions and joins

All queries use evaluation-only speech IDs. `structured-only` results were zero
for all eight questions. The offline phrase scan is normalized whole-phrase
search on the same in-memory sample; it is not an Elasticsearch benchmark.
“Link results” are distinct contributions; “mention outcomes” are occurrence
counts. The surface filter prevents a resolved named mention elsewhere in a
speech from answering a question about a different generic mention.

| Frozen question | Offline phrase results | Structured-only | Exact link | Contextual link | Exact phrase mention outcomes (exact / contextual) |
|---|---:|---:|---:|---:|---|
| Timmy Dooley, not merely speaker | 0 | 0 | 0 | 0 | 0 / 0 |
| Timmy Dooley historical validity | 0 | 0 | 0 | 0 | 0 / 0 |
| Finance Bill 2025 | 0 | 0 | 0 | 0 | 0 / 0 |
| Generic “the Bill” | 10 | 0 | 0 | 0 | 19 abstained / 19 abstained |
| Taoiseach office vs holder | 22 | 0 | 22 | 1 | 35 resolved / 34 ambiguous + 1 resolved |
| Minister for Finance office/headship | 1 | 0 | 1 | 0 | 1 resolved / 1 ambiguous |
| Department of Finance and headship join | 1 | 0 | 1 | 1 | 1 resolved / 1 resolved |
| Generic “the Department” | 39 | 0 | 0 | 0 | 44 abstained / 44 abstained |

Every returned graph speech was also found by its equivalent offline phrase
scan; thus graph-incremental-over-phrase counts were zero for these questions.
The baseline’s 22 Taoiseach returns equal the lexical result set; its single
Minister-for-Finance return equals the one lexical result. Contextual results
are subsets. The Department of Finance link likewise adds no new speech beyond
phrase search, but its provisional graph joins that speech to the existing
Minister-for-Finance office via `members:headsAdministrativeUnit`. The
Taoiseach and Finance office queries also joined existing `hasRoleType` office
type relationships. These are graph relationship paths, not evidence that
transcript linking improves speech discovery beyond full text.

The provisional reviewer did not review the single contextual Taoiseach result
or the Finance-office retrieval result. Their relevance remains unknown. The
Department of Finance reference was reviewed as an explicit mention of the
supported unit identity.

## 5. RDF, operations, and reproducibility

- The disposable Fuseki dataset contained 21 named graphs: 13 validated owner
  and Debate input graphs plus eight derived mention/link graphs (method ×
  development/evaluation × graph role). Total: 69,554 triples.
- The four derived method/split pairs use distinct
  `https://data.oireachtas.ie/graph/poc/entity-linking/` named graphs. Owner and
  Debate graph sets are disjoint from derived graph names. Whole-graph counts
  and canonical content hashes were verified after import; SPARQL relationship
  joins succeeded.
- Full contribution text was checked against every RDF literal, including
  short contributions. No transcript literal was found. Only source pointers,
  checksums, code-point offsets, mention surfaces, status/evidence, and
  supported target links are stored in provisional RDF.
- The final fresh-Fuseki run, after adding the overlapping-reference guard and
  with the external source cache populated, took 35.22 seconds wall time;
  measured linking-process peak RSS was 172.91 MiB (Fuseki container RSS is not
  included). Earlier runs measured 167.99 MiB and 1,030 MiB, so process memory
  varied substantially; all were below the 4 GiB limit. Final artifact output
  was 32,078,584 bytes (about 30.6 MiB, excluding the external raw AKN cache).
  Fuseki upload took 3.26 seconds; the 96 representative SPARQL calls took 5.41
  seconds total. Across per-source query calls, median timings were 0.029 s
  structured-only, 0.038 s exact, and 0.029 s contextual; maximums were 0.235 s,
  0.273 s, and 0.206 s, respectively. These are local disposable-store timings,
  not production or Elasticsearch performance.
- Two fresh-Fuseki runs before the uncertainty-scoring adjustment matched on
  sample/run IDs, decision-file checksums, derived graph hashes, graph counts,
  question results, joins, and mention outcomes. The post-adjustment run and the
  final run with the overlapping-reference guard preserved the same decisions,
  graph hashes, counts, and question result sets; the uncertainty exclusion
  changed only the provisional reference scores, while the guard does not affect
  the valid frozen labels. The comparison digest reported during execution had
  no retained calculation recipe or manifest, so it is not presented as a
  reproducible fingerprint here.
- Environment: Python 3.12.14, CPU-only Linux; Fuseki image
  `stain/jena-fuseki:5.1.0` (local image ID
  `sha256:b1d0c96f19adddef417520184471ac816cf36c6e72936a88ea02b29f4305929a`).

### Frozen/configuration fingerprints

| Input | SHA-256 |
|---|---|
| `sources.json` | `3ca3d65527f39566e95d277cb21d962eb6da6411faa95d81641c31d5985ea51a` |
| Frozen source-manifest rows | `31545560286f5dc8cc5891445ebf6a8382f42a087d30dc6a7b7d92327959d4aa` |
| Selected sample | `a31de22d150540b8fcc65faab5eebb1ed40056fa81baff81d595bd4c789bf249` |
| `questions.json` | `ef5d3ead317169a51fc06d1c196084d6513a5c12851b98ba593c9382f9b58d8b` |
| `review-rubric.json` | `0a641aa74fe13b663319c2ff9b55c9ddb23e9a2718897ae76868f42dcfd40efd` |
| Provisional reference | `0318f2602593c13646643f1c38a27a6dc6c25e80bbbc1274d068459a0de88ab8` |
| Validated identity-input fingerprint | `9dedc6510e0e7f4f4958ead4cd370301bd9a54611d34ecc0468407ea8279d625` |
| `entity_linking.py` | `385d2f8460e9451d2423996c79d2206d3008e62322e5e36555ffecc1d45f78f0` |
| `run.py` | `b1fa88de63685dbd4fbf0f8ec08e2909fdf4de1df3fe82595d7656bd7c6013b6` |
| Deterministic run ID | `a179cb9586d58e94e156` |

## 6. Limitations and category decisions

1. One Member, one Bill, three offices, and one unit are examples, not complete
   registries. No positive Member or Bill target opportunity appears in the
   evaluation sample; a targeted additional Bill source attempt returned HTTP
   403 and was not added.
2. The evaluation uses four Works and 460 contributions, not a representative
   production-corpus sample. Same-Work split leakage was checked and absent.
3. One AI reviewer's 21-contribution labels are provisional. There is no human
   gold set; 15 labels were uncertain, some category membership for agencies
   was unclear, and strict exact-span scores should not be treated as
   corpus-wide precision/recall.
4. NamedOffice title strings can refer to an officeholder. The exact baseline
   did not resolve this. The contextual office rule is conservative but left
   only one evaluation resolution, whose correctness was not reviewed.
5. Out-of-registry detectors cover a small set of title-led forms only. They
   miss names/aliases outside those patterns and do not establish that every
   detected role or institution has a locally registered identity.
6. Offline phrase search is not equivalent to Elasticsearch ranking,
   stemming, or operational latency. No Elasticsearch system was contacted.

### Recommendation

- **Members — Modify:** obtain validated identity/alias coverage and a
  category-balanced, human-reviewed positive/negative sample before measuring
  target resolution. Do not interpret zero target matches as failure or success.
- **Bills — Stop this candidate-specific evaluation:** no supported Bill
  positive was observed and the supplemental source was inaccessible. Resume
  only with an accessible source and reviewed Bill coverage; generic Bill
  references must remain unresolved absent a unique antecedent.
- **NamedOffices — Modify:** revise/evaluate office-versus-holder evidence with
  independent human review. Do not promote exact title matching; the baseline
  accepted six provisionally ambiguous reviewed mentions.
- **AdministrativeUnits — Go only to a larger human-reviewed evaluation:** the
  one reviewed Department link and headship join worked, but one positive is
  insufficient for operational readiness. Expand only from reviewed identities
  and preserve a separate provisional graph boundary.

No category recommendation authorizes authoritative publication or production
integration. The human decision gate in `plan.md` remains in force.
