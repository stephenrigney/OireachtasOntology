# Phase 1B — corrected v0.2.0 NLQ benchmark baseline

## Run identity and configuration

- Run: `39d326ef-f600-42ca-9783-d7cb8fefcc4d`, created
  `2026-10-07T11:39:21.447048+00:00` (UTC), tier `measured`.
- Benchmark: `oireachtas-local-nlq` v`0.2.0`, schema v1;
  `benchmark-v2.json`, SHA-256
  `f5a5b9d50d6a534360a727ebc73ae321142ace41404228e4e6b098cb67475692`.
- Historical benchmark `benchmark-v1.json` remains v`0.1.0` and retains its
  original SHA-256:
  `afaebc738c86e150e73d1bf997c2fe739df3e22226e566e4416508bdf48885c3`.
  The Phase 1A report and measured result were not changed.
- Historical Phase 1A run: `fe26146d-79f9-4c03-b0a9-4f84e9c3a2f8`, result
  SHA-256 `d349f91d44995429212b697645026c739f5b4dc57a69539327141546545f5a07`;
  see [`phase-1a-baseline.md`](phase-1a-baseline.md).
- Dataset: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`
  (the same Phase 0A development bootstrap; reference closure remains
  **NOT authoritative / not complete**).
- Preserved capture run IDs: Houses
  `896630a4-9389-4a8f-bf58-65c16a05425c`; Parties
  `91255248-e348-4d60-a8d6-73a26df49f8b`; Constituencies
  `e6a472b1-b6e0-4e02-8304-9e6cfa73c44d`; Members
  `d2c089d0-5203-40f1-97b8-ae0d8285e74d`. No API data was fetched.
- LLM: `gpt-6-luna`, OpenCode inference Responses-compatible endpoint at
  `https://opencode.ai/inference/openai/v1` (the translator appends
  `/responses`). A credential was configured for the run; no secret is
  recorded here.
- Runner: `uv run --locked --extra nlq python scripts/run-nlq-benchmark.py
  --tier measured --benchmark poc/nlq/benchmarks/benchmark-v2.json --raw-dir
  /var/home/stephen/Projects/OireachtasOntology/data/raw --state-db
  /var/home/stephen/.local/share/oireachtas-etl/core-state.sqlite`.
- Fuseki: disposable `stain/jena-fuseki:5.1.0`, loopback-only, no persistent
  volume, automatically removed; container ID
  `b847ef1b177c7d47b81a984a93f3cfc238161a44c117dd792364e31b0d37304f`.
- Result: ignored runtime artifact
  `var/nlq-benchmark/runs/39d326ef-f600-42ca-9783-d7cb8fefcc4d.json`, SHA-256
  `2f98004341c67d12adafd672c120223c779f758e3473ae2b2d78717a6a6aa91a`.

The artifact contains every v0.2.0 case ID exactly once and embeds the dataset
baseline and disposable-instance association. It was checked for the configured
credential and authorization-token text; neither was present.

## Benchmark validity audit

All 42 cases were reviewed against the active query/schema contract and the
preserved Phase 0A captures. The ten benchmark categories remain represented.
Coverage checks on the isolated bootstrap found 39 cases available and three
unavailable; missing source data is kept separate from NLQ scoring.

The main v0.2.0 corrections were:

- **Aengus Ó Snodaigh coverage:** the six lookup, term, collection, temporal,
  and join cases now discover the Member graph with `GRAPH ?memberGraph` and
  identify the member by `foaf:name`. They no longer use a Unicode graph-name
  literal that did not match the percent-encoded Member graph IRI. The probes
  verify the captured 33rd Dáil membership, Sinn Féin collection, Dublin
  South-Central constituency, and membership date range.
- **Timmy Dooley committee cases:** committee membership is represented as a
  separate Member-owned `CommitteeMembership`; the Committee owner graph
  supplies its 26th Seanad term and label. The probes and expectations now
  follow that cross-graph join rather than assuming committee membership is
  nested under ordinary Seanad membership. The two captured committees are
  Select Committee on Transport and Communications and Select Committee on
  Environment and Climate Action.
- **House-term start date:** `dct:temporal` is emitted but explicitly excluded
  from the active queryable predicate contract. “On what date did the 34th
  Dáil begin?” is therefore retained as unsupported/manual review, with its
  source-date coverage probe, and no regression query follows `#term-period`.
  The duplicate House-term-start-date case was replaced by a captured,
  contract-supported query for Micheál Martin's Dáil terms.
- **Optional party recognition:** the case relying on optional reviewed-party
  recognition was replaced by a local, term-scoped collection-membership
  question for Micheál Martin in the 34th Dáil. It tests the loaded graph and
  current local contract, not an unpopulated external-link graph.
- **Ambiguous names:** the weak John O'Brien and Mary Byrne examples were
  replaced by exact duplicate-name cases for Michael Collins and Cathy Honan;
  “Which Martin served in the Dáil?” remains. All three now have capture-backed
  candidate probes and remain manual review, without asserting a single
  intended identity.
- **Unsupported facts:** the favourite-colour question is classified under
  unsupported requests, with no expected fact asserted. The birthplace and
  home-address requests also remain manual review.
- **Date-range output:** the Aengus date case expects the two requested
  membership date values, not member and term labels that need not be projected
  by a valid answer query.

The other retained cases were checked for category, expected-result and
prerequisite consistency. In particular, deterministic regression queries use
name/label and contract-supported relationship navigation rather than
manufactured internal Member, term, or graph IRIs.

The only expected unavailable cases are:

1. `committee.quarantined-good-friday`: the exact Committee identity is
   quarantined due to conflicting preserved observations.
2. `unavailable.bill-status`: Bills are not loaded by the Phase 0A bootstrap.
3. `unavailable.debate-contribution`: Debate data is not loaded/published in
   the Phase 0A bootstrap.

These are source-coverage outcomes, not NLQ failures.

## Measured outcomes

**42 cases: 24 passed, 8 failed, 10 not scored.** The not-scored outcomes are
seven manual-review cases and the three unavailable source-coverage cases. All
32 supported cases had their prerequisites established and were scored.

| Category | Total | Passed | Failed | Not scored |
|---|---:|---:|---:|---:|
| Ambiguous names | 3 | 0 | 0 | 3 |
| Committees | 4 | 2 | 1 | 1 |
| Constituencies/panels | 4 | 2 | 2 | 0 |
| Counts/aggregates | 4 | 3 | 1 | 0 |
| Dates/temporal | 4 | 1 | 2 | 1 |
| House-term membership | 5 | 4 | 1 | 0 |
| Joins | 4 | 4 | 0 | 0 |
| Parliamentary collections | 5 | 4 | 1 | 0 |
| Simple lookup | 4 | 4 | 0 | 0 |
| Unsupported requests | 5 | 0 | 0 | 5 |
| **Total** | **42** | **24** | **8** | **10** |

| Recorded outcome class | Tagged outcomes | Scored failures | Not scored |
|---|---:|---:|---:|
| `query_safety_validation` | 10 | 8 | 2 |
| `source_data_coverage` | 3 | 0 | 3 |

There were no scored semantic-result mismatches in this run. The ten
safety-tagged outcomes comprise eight supported questions rejected before
execution and two unsupported/manual-review questions; only the eight supported
cases count as scored failures.

## Failure and manual-review analysis

### Query safety/validation (eight scored failures)

The scored cases were:

- `term.micheal-dail-34-membership`
- `collection.timmy-dail-34`
- `representation.timmy-seanad-26-panel`
- `representation.aidan-seanad-26-panel`
- `committee.timmy-committee-count`
- `date.timmy-seanad-26-start`
- `date.timmy-seanad-26-end`
- `aggregate.dail-33-collection-counts`

Each generated query was rejected before Fuseki execution. The automatic
validator message says “Only direct, single-property graph patterns are
allowed; SPARQL property paths are not.” Human inspection of all eight emitted
queries found prefixed terms such as `agents:Member`, `members:inHouseTerm`,
and `skos:prefLabel` but **no corresponding `PREFIX` declarations**; the
examples use direct graph patterns rather than property-path syntax. The error
message is therefore not a reliable root-cause diagnosis for these examples.
The validator correctly failed closed; its safety rules were not changed.

The same undeclared-prefix condition affected the unsupported/manual-review
cases `unsupported.member-favourite-colour` and
`unsupported.member-birthplace`. They are not scored failures. The unsupported
home-address case returned an empty safe query. The unsupported 34th Dáil
start-date case identified the term but did not infer or return a date.

### Ambiguous and unsupported manual review (seven cases)

The three ambiguous cases remained unscored. The duplicate Michael Collins and
Cathy Honan probes establish three exact-name Member resources each; the Martin
query returned multiple Dáil Member candidates. These outcomes provide
capture-backed evidence for ambiguity, not an automatic pass/fail judgment of
disambiguation quality.

The other four manual-review cases are unsupported facts: the 34th Dáil start
date, favourite colour, birthplace, and home address. Their expected result is
null by design; no invented answer is scored.

### Source coverage (three cases; not NLQ failures)

The quarantined Good Friday Committee case and the unavailable Bills and
Debates cases did not invoke the NLQ scoring pipeline. This separation is
preserved in both the artifact and the summary above.

## Phase 1C quality priority

**Prioritize SPARQL generation/validator compatibility without weakening the
read-only safety contract.** All eight scored failures stopped at validation,
and inspection shows that the generated queries omitted required namespace
prefix declarations. A focused Phase 1C investigation should improve or
constrain prefix-grounded query generation, retain fail-closed validation, and
add deterministic coverage for the observed missing-prefix pattern. Ambiguous
name behavior is the next distinct quality area; unavailable source facts remain
outside NLQ failure scoring.

This is a priority recommendation from one measured sample, not a change to the
query/schema contract or an approval to relax safety. The v0.2.0 question set
differs from v0.1.0 and the LLM is nondeterministic, so the pass counts should
not be read as a directly controlled quality comparison with Phase 1A.

## Verification and limitations

- Both v0.1.0 and v0.2.0 validate against the published JSON Schema; v0.1.0's
  bytes remain unchanged.
- Focused benchmark tests: 27 passed.
- Deterministic v0.2.0 regression tier: 10/10 passed.
- Full repository test suite: 738 passed, 14 skipped.
- Ontology validation: passed (2,504 triples; HermiT consistency check).
- Result integrity: all 42 case IDs occur exactly once; dataset ID and capture
  run IDs match the preserved Phase 0A baseline; configured credential and
  authorization-token text are absent; `git diff --check` passes.
- This is one LLM sample, not a repeatability estimate. Case-level coverage
  probes establish only their stated prerequisites and do not make the
  development dataset authoritative or complete.
