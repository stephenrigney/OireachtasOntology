# OireachtasOntology NLQ — Stage 2: Executable Capability Inventory

> Persistence note: This report was initially delivered for ChatGPT review after a
> read-only Stage 2 investigation. The user subsequently authorized saving it
> here. Working-tree and no-change statements below describe that investigation,
> before this report file was added. No Stage 3 work is authorized or recorded by
> this document.

## 1. Baseline and evidence provenance

**Disposition:** The implemented capabilities and their conditional routes are inventoried. Current-baseline factual correctness and reliability remain **Unknown**: focused pytest execution was blocked, and no live services were contacted.

### Baseline

| Item | Finding |
|---|---|
| Repository | **Observed—execution:** expected `stephenrigney/OireachtasOntology` checkout |
| Branch / HEAD | `master` / `563a385173d312d33d22ca7868524714487967aa`, matching the requested baseline |
| Working tree | No tracked changes. One pre-existing untracked file: `docs/reports/query-service/nlq-stage-1-forensic-architecture-reconstruction.md` |
| Environment | Linux x86-64; system Python `3.14.8`; `.venv` Python `3.12.14` |
| Available facilities | RDFLib `7.6.0`, FastAPI `0.142.2`, HTTPX `0.28.1`, Jinja2, multipart, dotenv and Uvicorn |
| Blockers | `pytest` and `jsonschema` unavailable; nothing installed |
| Contract versions | Query/schema `2.12.0`; semantic-v1 `1.2.0`; composable-v2 `2.29.0` |
| Live configuration/data | **Unknown:** serving revision, effective configuration, provider availability and loaded graph identity were not inspected |

The Stage 1 handoff was read and its relevant catalogue, routing, validation, execution and retained-evidence references checked. Its SHA-256 is `f1203d21ab283ab3030a3db3843c822119fa381c6be1faf43906095a55bf26c9`.

### Evidence labels

- **Observed—static:** source, contracts or test assertions inspected.
- **Observed—execution:** diagnostics executed during Stage 2.
- **Observed—historical:** retained earlier execution evidence inspected.
- **Inferred:** supported reconstruction, not a demonstrated trace.
- **Hypothesis:** explanation requiring controlled investigation.
- **Unknown:** evidence insufficient.

Neither test existence nor historical success is classified as current-baseline correctness.

### Evidence provenance

| Material | Provenance and limitation |
|---|---|
| Source/contracts/tests | Revision-pinned baseline evidence; source existence is not execution evidence |
| Human questions | Three external Question/Expected/Actual files survive. Their expansion into 26 cases is documented in `docs/reports/query-service/user-question-regression.md:38–65,80–107`; they lack per-request execution provenance |
| Local feedback | Three ignored streams contain 16, 2 and 0 records. Records store only question, expected, actual and adequacy—not timestamp, author, SHA, plan or SPARQL (`poc/nlq/feedback.py:64–81`) |
| Benchmark definitions | Inputs and expectations, not execution results. Capture/source pins are retained in `poc/nlq/benchmarks/development-{api-capture,source}-selection.json:3–49` |
| Historical reports/responses | Different revisions, configurations, datasets and scoring rules; kept separate below |
| External artifacts | Human-response HTML and supplementary investigations survive under `/tmp/opencode/` and `/tmp/oireachtasontology/`; disposable retention is weaker than revision-pinned repository evidence |
| Other-worktree investigations | Retained failed PR #27 and later Tranche 2 evidence belongs to different source states—not this baseline. It was not imported into current capability classifications |

Some older raw benchmark paths are absent, although reports and hashes survive. No historical collection was rerun or rescored.

---

## 2. Advertisements, selections, validators and dispatch

### Three distinct execution paths

| Path | Selection and execution | Default `/ask` reachability |
|---|---|---|
| **Composable-v2** | Deterministic recognition **and** LLM-selected capabilities/graph drafts; local resolution, validation and family-specific compilation | **Observed—static:** default `phase2` path |
| **Phase 1** | LLM generates interpretation and SPARQL after Member-ambiguity lookup; prefix completion and safety validation precede execution | Optional `mode=phase1`; not a fallback from v2 |
| **Semantic-v1** | `StructuredPlanner` → validated semantic plan → `PlanSparqlGenerator` → execution/evaluation | No default-browser handoff found; separate callable/evaluation path |

References: `poc/nlq/app.py:266–318,979–1047`; `pipeline.py:31–94`; `plan_pipeline.py:73–175`; `plan_benchmark.py:177–192,296–299`.

### Default-route gates

**Observed—static:** `poc/nlq/composable_plan.py:_execute_question:7219–7348` applies:

1. Whole-intent unsupported and future-date gates.
2. Interpretation preflight.
3. Locally grounded current-office interception.
4. Geographic-set clarification or early semantic-composition routing.
5. Representation → Government → Stage A → Stage C → Stage B.
6. Office-calendar semantic routing.
7. Remaining deterministic `plan_question`; only its `UnrecognizedQuestion` invokes semantic fallback.

Recognized evidence failures do **not** automatically retry another planner. Semantic failure does not downgrade to Phase 1.

### Catalogue mechanisms are different inventories

**Observed—static/execution:**

- The composable contract contains **39 question-family entries**, including refusal/coverage families.
- `/capabilities` renders **32 relation entries**, assigning each the same bounded-executable status. It is not an operation-by-operation capability inventory (`app.py:247–264`).
- The semantic-dispatch catalogue contains **nine capability IDs**.
- The strict model draft additionally exposes graph families such as `shared_dail_terms`, `member_relationship_composition`, `member_party_history` and sponsorship (`poc/specs/composable-query-plan-draft.schema.json:12`).
- Prompt instructions combine catalogue-derived text with handwritten guidance (`composable_semantic_planner.py:67–163`).

### Generic capability-selection map

All rows are **Observed—static**, with the registration mismatch also reproduced offline.

| Advertised ID | Local validation / dispatch target |
|---|---|
| `member_lookup` | Stage A request and executor |
| `seanad_entry` | Stage A request and executor |
| `dail_parties_and_groups` | Stage C canonical plan and executor |
| `bill_lookup` | Stage B exact-number/year plan and executor |
| `current_committee_members` | Closed Committee roster executor |
| `current_office_constituency` | Accepted current holding → exact Member → current representation |
| `office_holding_evidence` | `interpretation.office_holding_boundary`; direct evidence outcome, not a final graph-plan construction |
| `office_holding_window` | Canonical office point/window plan → office executor |
| `member_bill_sponsorship` | **No generic selector adapter or dispatch branch.** A separate graph-family adapter and executor exist |

Validator: `composable_semantic_planner.py:_validate_capability_selection_draft:838–1060`.
Dispatch: `composable_plan.py:_execute_shared_dail_terms_question:6540–6643`.

---

## 3. Capability matrix

### Classification key

- **I: S** — answer-producing implementation exists in inspected source; not a blanket runtime certification.
- **I: B** — implemented boundary/coverage response, not factual capability.
- **Discoverability:** **C** generic capability catalogue; **G** explicit model graph guidance; **—** no dedicated current model selection found.
- **Reachability:** **D** deterministic default-route recognition; **M** semantic/model route. These are **conditional static routes**, not current-runtime demonstrations.
- **Correctness:** **U/T** current verdict Unknown; relevant acceptance assertions exist. **+H** adds historical positive evidence, with provenance limitations.
- **Reliability:** **U** Unknown at this baseline. No family has repeated, revision/configuration/data-pinned current-baseline evidence.

Source abbreviations below denote files under `poc/nlq/`: **CP** `composable_plan.py`; **SP** `composable_semantic_planner.py`; **A/B/C** `stage_a.py`, `stage_b.py`, `stage_c.py`.

| Operation or bounded family | Executor and supported meaning | I | Discoverable | Reachable | Correctness | Reliability |
|---|---|---:|---|---|---|---|
| `member_lookup`, `dail_all` | A `execute_stage_a:813–902,1183–1191`; grounded names, House-service restriction, alternatives or all exact-name Dáil identities | S | C lookup; — all | D/M lookup; D all | U/T+H | U |
| `previous_service` | A `:919–929`; named Member in globally previous House-date-selected Dáil | S | — | D | U/T | U |
| `dail_duration` | A `:930–995`; inclusive union of accepted service episodes through `asOf`, preserving gaps | S | — | D | U/T | U |
| `term_count` | A `:797–809,909–918`; distinct Member-linked Dáil terms or typed Dáil-term catalogue count | S | — | D | U/T | U |
| `seanad_entry`, `seanad_representation` | A `:1056–1102`; earliest recorded start/later episodes, or term-scoped source designation | S | C entry; — representation | D/M entry; D representation | U/T | U |
| `current_collection` | A `:999–1054`; dated party/Independent parliamentary status at `asOf` | S | — | D | U/T | U |
| `committee_boolean`, `committee_count` | A `:1108–1176`; current exact-incarnation membership evidence, or distinct recorded Committee IRIs | S | — | D | U/T | U |
| `house_terms` | A `:631–795`; chronology, exact-date selection or full-month interval selection | S | — | D | U/T | U |
| `dail_seats` | C `:427–470`; authoritative positive `agents:seats` for one numbered Dáil—not Member count | S | — | D | U/T | U |
| `dail_parties_and_groups` | C `:471–531`; exact-term ParliamentaryParty list; separately reports unavailable group coverage | S | C | D/M | U/T | U |
| `constituency_representation` | `representation.execute_representation:269–430`; current Member↔constituency, career occurrences, latest recorded term/constituency | S | G | D/M | U/T+H | U |
| `shared_dail_terms` | CP `:6645–6865`; two independently resolved Members’ exact DailTerm-identity intersection | S | G | M | U/T+H | U |
| Two-term / constituency Member composition | CP `_execute_member_relationship_composition_plan:5832–6452`; same Member in two numbered terms, or one-term constituency list/count | S | G | M | U/T+H | U |
| Anchored shared constituency | Same executor; independent anchor/answer paths, numbered or previous Dáil, excluding anchor; term-wide list/count | S | G | M | U/T | U |
| Dated party composition | CP `_execute_member_party_temporal_composition:5693–5810`; exact party episodes and containing membership; Dáil/Seanad, historical/current scoped lists and permitted counts | S | G | M | U/T+H | U |
| Bounded OR / office-anchored composition | Same executor; 2–4 explicit constituency identities, or shared constituency plus four-interval common intersection | S | G | M | U/T+H | U |
| Current cross-house term intersection | CP `:5447–5536,5832–6452`; Member identity in both current **terms**, not simultaneous/current-point service | S | G | M | U/T+H | U |
| Current Seanad with prior Dáil service | CP `:5539–5689,5832–6452`; active Seanad membership and strictly earlier finite Dáil end; list/count | S | G | M | U/T+H | U |
| `government_party_members` | `government.execute_government:156–238`; constitutional Cabinet and party/membership intervals active at `asOf` | S | G | D/M | U/T | U |
| `current_committee_members` | `committee_members.execute_committee_members:173–193`; current owner/HouseTerm and independently active membership episodes | S | C | M | U/T+H | U |
| `current_office_constituency` | `office_representation.execute_office_representation:57–121`; unique accepted current holding → exact Member → independently current Dáil representation | S | C | M | U/T+H | U |
| Office point/window | CP `_execute_office_question:4606–4810`; accepted holdings overlapping date/month/year/window; bounded Stage B variants | S | C | D/M, wording-dependent | U/T+H | U |
| Exact person/office episodes | `interpretation.office_holding_boundary:211` and CP projector `:3997`; separate episodes or uniquely latest recorded start | S | C | M | U/T+H | U |
| `member_party_history` | CP `_execute_affiliation_question:7051`; enduring affiliations with separate recorded episodes/gaps | S | G | D/M | U/T+H | U |
| Bill lookup/title/lifecycle | B `execute_stage_b:557–585`, projections `:679–866`; exact lookup, title candidates, Published-year selection, non-enacted status groups, recorded status/history/documents | S | C exact lookup; — others | D/M lookup; D others | U/T | U |
| Bill sponsors / Member-sponsored Bills | B `:787–819`; CP `_execute_bill_sponsorship_question:4851`; forward Participations, reverse distinct Bills, bounded Published-year count | S | G; C registration inconsistent | D/M, excluding broken generic selector | U/T+H list; U/T count | U |
| Debate lookup / existence | C `:545–565`; CP `:7349–7370`; actual sitting→record, controlled chamber/date, links or Boolean | S | — | D | U/T | U |
| Coverage/refusal families | B `:997–1067`; C `:532–574`; chair gap, quarantine probes, current-coverage warning, PAC/HSE latest, Bill votes, transcript | B; factual operation absent where stated | — | D | Boundary assertions only | U |

The correctness evidence underlying these classifications is mapped in §6. Historical outcomes do not upgrade **U** to verified current correctness.

---

## 4. Supported dimensions and explicit limits

All findings in this section are **Observed—static**, unless stated otherwise.

### Identity, relationships and graph evidence

- Identity joins use exact RDF resources across declared owner graphs—not matching labels or graph co-containment. Required owners are specified in `poc/specs/query-schema-contract.json:140–241`.
- Member resolution distinguishes exact names, source-identifier aliases and bounded lookup-token matching. These are not general fuzzy identity resolution.
- Ambiguous identities remain alternatives; the interactive continuation is limited to validated Member lookup and rechecks evidence.
- Party composition requires typed PartyMembership episodes, their exact containing parliamentary membership and reviewed enduring affiliation identity. Independent collection status is not party membership.
- Bill/process association requires the explicit BillDelivery→Bill/process path. The legacy identifier `bill_process_cocontained` does **not** permit co-containment inference.
- Optional graph-family presence is not completeness or per-question readiness. `FusekiQueryClient.readiness:208–260` checks presence only.

### Temporal meanings are operation-specific

| Dimension | Supported meaning / refusal boundary |
|---|---|
| Current/previous terms | House-owned dates select unique identities; missing, tied or conflicting chronology can block selection |
| Plain constituency “in this Dáil” | Term-wide in the bounded non-party projection; explicit current-point wording additionally requires active membership |
| Historical party selection | Inclusive overlap of exact party and membership intervals |
| Current party selection | Both intervals independently contain `asOf`; historical overlap alone is insufficient |
| Shared term/constituency | Does not imply simultaneous service |
| Office-anchored composition | One common intersection of holding, anchor membership, answer membership and party episode—not merely pairwise overlaps |
| Prior Dáil service | Finite Dáil end strictly before the qualifying Seanad episode’s start; equal endpoints/open Dáil ends do not qualify |
| Office window | Inclusive overlap, not service throughout the complete window |
| Latest recorded office episode | Unique greatest validated start after checking all episodes; not proven historically last tenure |
| Duration | Dáil service union is implemented; office-tenure duration is unsupported |

Temporal validators: CP `:551–1205,5122–5689`; `interpretation.py:143–208`; A `:463–480,930–995`; SP `:963–1013`.

### Filters, projections and aggregation

- Supported counts are bounded and distinct-identity based: Members, terms, Committees or Bills as specified—not interchangeable with seats, elections or episode cardinalities.
- List/count parity applies only to reviewed selections. It does not create arbitrary aggregation or composition.
- Explicit-current Dáil party selection requires explicit current wording; the Seanad has a separately reviewed unqualified present-tense default.
- Plain Member/constituency composition supports one exact membership-date point; arbitrary windows and extra relations remain unsupported.
- Committee roster and officeholder→constituency capabilities reject historical scope, party filters, counts and extra fields.
- Bill Published-year selection uses typed activity `xsd:date`, never legislative year. Memoranda require a complete typed Work→Expression→Format→URI chain.
- Bill sponsor projections preserve primary/supporting/unknown/role-only evidence; sponsorship is not voting.
- Debate metadata is not transcript content or substantive topic evidence. The development contract describes only three pinned representative Debate graphs.

### Missing, uncertain and capped evidence

There is no universal evidence policy:

- Many Stage A/C and temporal constituency/office paths reject a 100-row boundary.
- Ordered pagination is used by several Member, party-only, roster and episode paths; exhaustion fails closed (`pagination.py:8–32`).
- Stage B can expose qualified partial results with `incomplete_results`.
- Historical office-window uncertainty can display verified partial rows under `insufficient_holding_evidence`; current-point uncertainty returns no holder list (CP `:4686–4747`).
- Party-history display permits missing dates as “not recorded”; temporal party composition cannot treat those dates as established overlap.
- Empty evidence generally does not establish historical absence. Qualified zero/negative results exist only for particular validated selections.

### Separate semantic-v1 capability surface

**Observed—static:** `plan_sparql.py:82–162` implements Member identity/name/service/date/collection/representation/Committee facts; House/term/collection/constituency/Committee labels and codes; Bill title/year/status/sponsor; office holdings; Debate identity/date.

It supports controlled filters, reviewed conjunctive composition, Boolean/entity/value/list/count/grouped projections. Temporal compilation is narrower than its advertised vocabulary:

- `during` only for reviewed HouseTerm-scoped facts;
- `on` for office holdings and Debate dates;
- other date/window/current forms fail as unsupported generation.

References: `plan_sparql.py:339–369,897–1122,1290–1384`. None establishes default composable-v2 support.

Phase 1 has no equivalent finite typed-operation guarantee: executable syntax is safety-gated, while semantic fidelity remains model-dependent (`llm.py:24–53`; `pipeline.py:58–94`).

---

## 5. Inconsistencies, unreachable selections and unsupported operations

| Finding | Classification and consequence |
|---|---|
| Advertised sponsorship generic selector has no adapter/dispatch | **Observed—static/execution.** That selection is rejected. The separate sponsorship graph route remains implemented and conditionally reachable; the operation as a whole is not unreachable |
| Final v2 schema omits `current_committee_members` and `current_office_constituency` | **Observed—static/execution.** Python accepts both families, but the final JSON-schema family enum does not (`composable-query-plan.schema.json:21`; CP `:1745–1750`). Runtime impact is **Unknown**; browser validation is handwritten |
| Dáil party-count contract disagreement | **Observed—static.** Contract `composable-query-plan-contract.json:98` restricts constituency-free party counts to numbered Dáil terms; SP `:644–672` and `tests/test_nlq_seanad_party_periods.py:95,191–250` also admit explicit-current selection. **Raised for review; no semantic interpretation chosen** |
| `/capabilities` is relation-based | **Observed—static.** Its uniform executable label does not document each operation’s selection, projection or refusal bounds |
| Implemented deterministic families absent from model catalogue | **Observed—static.** Examples include duration, term count, House-calendar selection, seats and several Bill operations. This is a discoverability distinction—not proof of default-route unreachability |
| Semantic-v1 unavailable through default browser path | **Observed—static.** Its compiler capabilities must not be credited to composable-v2 |
| Coverage handlers describe development conditions | **Observed—static.** Fixed chair/group/quarantine/coverage messages are not fresh measurements of the current dataset. Some handlers additionally perform exact availability probes |
| Routing can depend on local grounding | **Inferred from source.** Current-office interception can precede Stage B’s Finance coverage response. Effective runtime branch remains Unknown |
| Stage C recognition uses substring matching | **Observed—static:** `stage_c_request_family:103–119`. Whether particular additional wording loses intent requires evidence; no general defect is concluded |

**Unsupported semantics**, rather than merely missing data, include election-event inference, office duration, unrestricted compositions/aggregates, unrepresented exclusions/filters, Bill voting and transcript speech retrieval. Conversely, absent accepted current officeholding, Published activity or roster evidence is a **data/evidence limitation**, not proof that the requested real-world fact is false.

---

## 6. Verification and retained-execution coverage

### Stage 2 execution

**Observed—execution:**

| Check | Result |
|---|---|
| Focused pytest selection: catalogue registration, selector adaptation/rejection, integrated shared-term `/ask`, office-duration boundary | Exit 1: `No module named pytest`; **no tests ran** |
| Catalogue/AST registration diagnostic | Nine advertised IDs; sponsorship alone absent from generic adapter and dispatch branches |
| Prompt construction | All nine advertised IDs included |
| Existing Bill selector examples | Exact Bill lookup adapted; attempted sponsorship-through-lookup rejected |
| Sponsorship generic selector | Rejected with “no reviewed dispatch adapter” |
| Semantic-v1 executor boundary | Raw dictionary rejected as `planner_result_required` |
| SPARQL safety | Safe SELECT capped at 100; SERVICE rejected |
| Default v2 boundary diagnostics | Election request refused; future explicit date clarified; neither required a query client or produced result/SPARQL |

Diagnostics used `.venv/bin/python -B` with bytecode disabled. No saved tests were added. No network, Fuseki, LLM, launcher, bootstrap, benchmark or environment modification occurred.

### Existing acceptance assertions inspected—not rerun

| Capability / transition | Representative references |
|---|---|
| Catalogue, adaptation, HTTP handoff | `tests/test_nlq_composable_semantic_capability_discovery.py:106–204`; `test_nlq_composable_shared_dail_terms.py:194–419` |
| Stage A identity/service/count/calendar | `test_nlq_composable_stage_a.py:195–606,698–767` |
| Bill paths, activities, status, documents, caps | `test_nlq_stage_b.py:100–605,881–1093` |
| Seats, parties, exact availability probes/refusals | `test_nlq_stage_c.py:126–543` |
| Member composition, dates/count parity/paging/latest | `test_nlq_composable_member_relationship_composition.py:415–1233` |
| Party intervals and bounded operators | `test_nlq_composable_party_temporal.py:455–1040`; `test_nlq_bounded_composition.py:170–330,622–695` |
| Cross-house/prior service/current and historical parties | `test_nlq_composable_current_house_membership.py:374–853`; `test_nlq_seanad_party_periods.py:95–398` |
| Government and closed roster/office chains | `test_nlq_government_membership.py:80–245`; `test_nlq_committee_members.py:91–217`; `test_nlq_office_representation.py:74–257` |
| Office evidence/latest and sponsorship | `test_nlq_composable_office_evidence.py:139–314`; `test_nlq_latest_office_episode.py:45–174`; `test_nlq_composable_q23.py:163–576` |
| Party history / previous constituency / Debate | `test_nlq_composable_q06.py:118–179`; `test_nlq_composable_q09.py:86–311`; `test_nlq_composable_debates.py:78–182` |
| Semantic-v1 compiler boundaries | `test_nlq_plan_sparql.py:160–811` |

These include synthetic owner-scoped RDF, fixed generators, mocked clients and ETL-produced fixture graphs. They are not uniformly genuine-data tests. Opt-in capture-backed Fuseki tests exist but were not run (`test_nlq_plan_sparql_fuseki.py:24–28`).

### Historical live evidence

All entries below are **Observed—historical**, not current-baseline certification.

| Collection | What it establishes / limitation |
|---|---|
| Human regression campaign | Retained answers include current party/representation, bounded counts, cross-house/prior service and office-anchored composition. Final summary does not pin serving SHA. Refusals/partial results remain separate (`user-question-regression.md:607–655`) |
| Independent November 6 evaluation | Frozen questions/oracles and dirty-source hashes/patch retained. Reports 22 factual answers among 48 evidence-backed supported questions, with disclosed admissibility disputes. Not this SHA (`independent-generalisation-evaluation.md:41–131,234–315`) |
| Repetition subset | Twenty questions repeated three times; only six answered at least once, five consistently. Stable refusals must not be called reliable answering (`independent-generalisation-evaluation.md:334–401`) |
| Group A/B | Latest-recorded office evidence; PAC roster; Finance-office→Wicklow positive chain. Tánaiste chain remained blocked by missing accepted current holding—not missing representation (`group-a-membership-periods.md:46–64,130–145`; `group-b-committee-officeholder.md:93–228`) |
| Tranche 1 | Genuine-AI party lists/counts matched independent RDF selections in eight positive cases; three negative controls refused. Explicitly a finite sample, not reliability estimation (`capability-flexibility-tranche-1.md:128–182`) |
| Bill sponsorship | Historical distinct-Bill lists succeeded. Published-year count was unavailable where Published activities were absent—not zero (`q23-bounded-bill-temporal-aggregation-20261103.md:5–49`; `bill-publication-evidence-review.md:12–64`) |
| Earlier semantic-v1 / Phase 1 | Separate compiler/direct-generation evaluations. Their scores cannot establish default-v2 capability performance |
| November 3 holdout | Dominated by provider HTTP-400 schema rejection; not evidence of corresponding semantic incapability (`temporal-aggregation-holdout-20261103.md:40–61`) |

The supplementary unmerged PR #27 campaign also retains negative projection/generalisation evidence. Its source was different and its acceptance failed; neither its development gains nor failures are attributed to this master baseline.

---

## 7. Candidate Stage 3 questions

These are experimental questions, not conclusions or replacement-architecture proposals:

1. For operations with deterministic and semantic entry points, do controlled equivalent phrasings reach the same validated selection?
2. How often does the model choose the unusable generic sponsorship selector rather than the working graph family?
3. Can implemented but uncatalogued operations be reached through ordinary unfamiliar wording without changing their constraints?
4. Are term-wide, active-at-date, prior-service and common-intersection meanings preserved across phrasing variation?
5. Do repeated requests preserve factual answer availability, exact identities, episodes and projections—not merely outcome class?
6. When evidence is absent or uncertain, are unsupported semantics, source gaps, provider failures and execution failures distinguished consistently?
7. Do representative historical successes reproduce with pinned source, configuration and graph evidence at this baseline?
8. What observable consequences follow from the schema/validator and contract/code discrepancies, once their intended meaning is reviewed?

---

## 8. Stage 2 exit criteria

| Criterion | Assessment |
|---|---|
| Baseline, working tree, environment and facilities recorded | **Met** |
| Stage 1 read and relevant reconstruction verified | **Met** |
| Meaningful operations, dimensions, executors and constraints inventoried | **Met—static evidence** |
| Implementation/discoverability/reachability/correctness/reliability separated | **Met** |
| Default v2, Phase 1 and semantic-v1 kept distinct | **Met** |
| Advertisements, validators, routes and inconsistencies mapped | **Met** |
| Focused offline verification | **Partial:** dependency-light checks completed; pytest blocked |
| Current factual correctness / repeated reliability established | **Not established** |
| No changes, services, broad benchmark or Stage 3 experiments | **Met** |

**Stage 2 is ready for ChatGPT review, with runtime acceptance explicitly incomplete.** Unknown runtime configuration/data is not silently resolved. No capability success percentage is inferred from the incomplete evidence.

**Stopped after Stage 2.**
