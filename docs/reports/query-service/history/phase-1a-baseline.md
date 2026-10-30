# Phase 1A — Measured local NLQ baseline

## Run identity and configuration

- Run: `fe26146d-79f9-4c03-b0a9-4f84e9c3a2f8`, created `2026-10-06T18:06:04.109738+00:00` (UTC), tier `measured`.
- Benchmark: `oireachtas-local-nlq` v`0.1.0`, schema v1; artifact `poc/nlq/benchmarks/benchmark-v1.json`, SHA-256 `afaebc738c86e150e73d1bf997c2fe739df3e22226e566e4416508bdf48885c3`.
- Dataset: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d` (Phase 0A development bootstrap; reference closure **NOT authoritative / not complete**).
- LLM: `gpt-6-luna`, OpenCode inference Responses-compatible endpoint, effective base URL `https://opencode.ai/inference/openai/v1` (the translator appends `/responses`). The key was present through the runner's `.env` loading path; no credential is recorded here.
- Runner: `uv run --locked --extra nlq python scripts/run-nlq-benchmark.py --tier measured --raw-dir /var/home/stephen/Projects/OireachtasOntology/data/raw --state-db /var/home/stephen/.local/share/oireachtas-etl/core-state.sqlite`.
- Preserved captures were integrity-checked against the existing Core State complete-run pointers before execution: Houses `896630a4-9389-4a8f-bf58-65c16a05425c` (68 records), Parties `91255248-e348-4d60-a8d6-73a26df49f8b` (11), Constituencies `e6a472b1-b6e0-4e02-8304-9e6cfa73c44d` (8), and Members `d2c089d0-5203-40f1-97b8-ae0d8285e74d` (1,928). No data was fetched or copied.
- Fuseki: disposable `stain/jena-fuseki:5.1.0`, loopback-only, no persistent volume; container `fda4ff6fbad9da37263c5d893201aad574da822b4c177a802fd6e24448e37160`.
- Raw result: ignored runtime artifact `var/nlq-benchmark/runs/fe26146d-79f9-4c03-b0a9-4f84e9c3a2f8.json`, SHA-256 `d349f91d44995429212b697645026c739f5b4dc57a69539327141546545f5a07`.

The artifact contains all 42 measured case IDs exactly once and embeds the dataset baseline and disposable-instance metadata. It is retained in the established ignored runtime-results directory; this report is the durable summary.

## Measured outcomes

**42 cases: 15 passed, 8 failed, 19 not scored.** The not-scored cases are 12 `coverage_unavailable` outcomes and 7 `manual_review` outcomes. Coverage failures are kept separate from NLQ failures.

| Category | Total | Passed | Failed | Not scored |
|---|---:|---:|---:|---:|
| Ambiguous names | 3 | 0 | 0 | 3 |
| Committees | 4 | 1 | 0 | 3 |
| Constituencies/panels | 4 | 2 | 2 | 0 |
| Counts/aggregates | 4 | 4 | 0 | 0 |
| Dates/temporal | 4 | 0 | 3 | 1 |
| House-term membership | 5 | 2 | 2 | 1 |
| Joins | 4 | 0 | 1 | 3 |
| Parliamentary collections | 5 | 3 | 0 | 2 |
| Simple lookup | 5 | 3 | 0 | 2 |
| Unsupported requests | 4 | 0 | 0 | 4 |
| **Total** | **42** | **15** | **8** | **19** |

| Recorded failure class | Tagged outcomes | Scored failures | Not-scored outcomes |
|---|---:|---:|---:|
| `source_data_coverage` | 12 | 0 | 12 |
| `query_safety_validation` | 7 | 6 | 1 |
| `semantic_result_mismatch` | 2 | 2 | 0 |

The class counts include every tagged outcome, not only scored failures. In particular, the seventh safety-tagged result is an unsupported request kept in manual review. The eight scored failures are six validation rejections and two semantic-result mismatches.

## Diagnostic review

### Source-data coverage (12 cases; not NLQ failures)

The runner assessed coverage before calling the LLM. Nine supported cases were therefore not scored because their curated prerequisite probe returned `ASK false`:

- Aengus Ó Snodaigh's name and 33rd Dáil membership/collection/date/constituency cases (`lookup.aengus-name`, `term.aengus-dail-33`, `collection.aengus-dail-33`, `date.aengus-active-mid-2023`, and the two corresponding `join.aengus-*` cases).
- Timmy Dooley's 26th Seanad committee membership/count/owner cases (`committee.timmy-transport-committee`, `committee.timmy-committee-count`, `join.timmy-committee-owner`).

For example, `lookup.aengus-name` asks for the full name and expects at least one row containing “Aengus Ó Snodaigh”; its exact-member-graph name probe returned false, so no model interpretation, generated query, safety decision, or execution result exists for that case. The Timmy committee cases likewise had false membership/owner probes before NLQ was invoked.

The other three coverage outcomes are expected dataset limitations: the Good Friday Agreement Committee resource is quarantined due to conflicting preserved observations; Bills are not loaded by the Phase 0A bootstrap; and Debate data is not published/loaded. These are not NLQ-generation failures. The baseline reports 267 committee owner identities while the particular quarantined identity remains unresolved; the dataset remains explicitly non-authoritative.

### Query safety/validation (six scored failures; one manual-review rejection)

All six scored rejections shared one generation pattern: the model emitted prefixed names such as `agents:Member`, `foaf:name`, `members:inHouseTerm`, and `skos:prefLabel` without declaring their `PREFIX` mappings. The validator rejected the query before Fuseki execution. Its automatic reason says “property paths,” but the reviewed queries use ordinary direct triple patterns; the undeclared prefixes leave predicates unresolved in the parser and trigger the validator's direct-predicate guard. The human diagnostic is primarily **SPARQL generation (missing prefix declarations)**, with validation as the observed failure stage.

Example `term.timmy-seanad-26`:

- Question: “Was Timmy Dooley a member of the 26th Seanad?”
- Interpretation: check whether Timmy has a Seanad membership record linked to the 26th Seanad term (consistent with the expected invariant, `ASK true`).
- Generated SPARQL: `ASK { GRAPH ?memberGraph { ?member a agents:Member ; foaf:name "Timmy Dooley" ; members:hasMembersMembership ?membership . ?membership a members:SeanadMembership ; members:inHouseTerm ?term . } GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a agents:SeanadTerm ; skos:prefLabel ?label . FILTER(STR(?label) = "26th Seanad") } }`.
- Safety: rejected with the property-path message; no validated query or execution result.

The same condition rejected `representation.timmy-dail-34-constituency`:

- Question: “Which constituency did Timmy Dooley represent in the 34th Dáil?”
- Interpretation: find the constituency linked to Timmy's Dáil membership in the 34th Dáil.
- Expected invariant: at least one row containing “Clare”.
- Generated SPARQL: `SELECT DISTINCT ?constituencyLabel WHERE { GRAPH ?memberGraph { ?member a agents:Member ; foaf:name ?name ; members:hasMembersMembership ?membership . FILTER(?name = "Timmy Dooley") ?membership a members:DailMembership ; members:inHouseTerm ?term ; members:isRepresentativeFrom ?constituency . } GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel . FILTER(STR(?termLabel) = "34th Dáil") } GRAPH <https://data.oireachtas.ie/graph/constituencies> { ?constituency a members:DailConstituency ; skos:prefLabel ?constituencyLabel . } } LIMIT 100`.
- Safety/execution: rejected before Fuseki for the same unresolved-prefix reason; no execution result.

Four other scored queries across temporal membership, constituency-owner lookup, and panel joins failed identically. `unsupported.member-birthplace` was also rejected this way, but remains manual-review/not-scored; its interpretation correctly stated that birthplace is not in the supplied schema.

### Semantic-result mismatch (two scored failures; schema/benchmark scope concern)

`term.dail-34-start-date` (“When did the 34th Dáil begin?”) and `date.dail-34-start` (“On what date did the 34th Dáil begin?”) both expect text containing `2024-11-29`. Coverage was available. The model interpreted that the date link was not queryable under the supplied predicate allowlist and generated a safe query for the Dáil term and label only. Validation passed; Fuseki returned one row containing the term IRI and `34th Dáil`, without the expected date, so both were scored `semantic_result_mismatch`.

For `term.dail-34-start-date`, the generated query was a `SELECT DISTINCT ?term ?label` over the Houses graph, matching `agents:DailTerm` and the `skos:prefLabel` “34th Dáil”; it contained no date pattern. It passed validation and returned that one term/label row. The expected invariant still required the date substring `2024-11-29`.

The query/schema contract explicitly describes the HouseTerm-to-period link via `dct:temporal` as emitted but **not queryable** by the current local NLQ allowlist. The curated coverage probe confirms a start date on the 34th Dáil's `#term-period`, but the contract does not expose the link from the term to that period. Thus the value exists in the dataset, while the supported query contract does not expose the path needed to retrieve it. These outcomes appear to be a benchmark support-expectation/contract-scope mismatch, not evidence that temporal interpretation or execution failed. This needs semantic review; neither benchmark expectations nor the contract were changed, and the measured failures remain intact.

### Manual review (seven outcomes)

The three ambiguous-name cases were not scored. For `Who is John O'Brien?`, the model interpreted an exact-name Member lookup, generated a query for the member/name/code, and got zero rows. For `Which Martin served in the Dáil?`, it interpreted a substring search plus Dáil membership and returned 92 rows. `What did Mary Byrne do in Parliament?` generated a broader exact-name membership/representation/collection/committee query and returned zero rows. These cases have no expected result or case-specific coverage probe; the zero-row outcomes do not distinguish capture/name coverage from resolution, and the broad result is not automatically judged for ambiguity. They remain manual review, not assigned NLQ failures.

Unsupported cases also have no expected result invariant and require review rather than semantic scoring. The favourite-colour question was interpreted as unsupported; its generated query only found Aengus's Member record and returned one row. The enduring-party query attempted the local `members:recognisedAsParty` relation and returned no rows. The home-address request declined and returned an empty `FILTER(false)` result. The birthplace interpretation correctly said the fact is unavailable, but its Member-lookup SPARQL was rejected at validation for the missing-prefix condition described above. These outcomes do not establish that a requested unsupported fact exists.

## Priorities indicated by this run

1. **SPARQL generation/validation interaction:** missing prefix declarations account for six of the eight scored failures, across several query categories; this is the largest observed NLQ failure class.
2. **Date-query support scope:** two further scored failures expose a conflict between benchmark support expectations and the current query/schema contract. Resolve that semantic interpretation before treating the dates as ordinary NLQ-generation failures.
3. **Coverage-limited evaluation:** nine supported questions could not be scored because specific capture-backed prerequisites were absent; the three declared-unavailable cases also behaved as coverage outcomes. This limits evaluation reach and is separate from NLQ quality.
4. **Ambiguity behavior:** three manual cases produced zero, zero, and 92 rows, so the run does not establish reliable disambiguation behavior.

These are evidence-ranked diagnostic areas only; no Phase 1B changes were made.

## Limitations

- The benchmark's automatic failure taxonomy is coarse: safety validation is the recorded class for missing-prefix outputs, and semantic mismatch candidates (`temporal_interpretation`, `schema_grounding`, `sparql_generation`) are not definitive root causes.
- Of the ten cases defined for manual review, three stopped at the source-coverage gate; seven reached manual-review outcomes. Manual cases have no automatic semantic pass/fail score.
- The run is a single LLM sample, not a repeatability estimate. Model and endpoint identity are recorded here because the runner's raw result format does not store those settings.
- Source coverage probes establish only their particular prerequisites; they do not promote the development dataset to authoritative or complete coverage.
