# OireachtasOntology NLQ — Stage 4: Causal and Generalisation-Mechanism Investigation

> Persistence note: This report was initially returned for ChatGPT review after a
> read-only Stage 4 investigation. The user subsequently authorized saving,
> committing and pushing it. Working-tree and no-change statements below describe
> that investigation, before this report file was added. No Stage 5 work is
> authorized or recorded by this document.

## Executive finding

The default composable-v2 service generalises through **parameterised, reviewed query shapes**, canonical adapters, exact identity joins and reusable evidence evaluators. It does **not** provide general closure under combinations of its individually supported operations.

This distinction explains both successes and limitations:

- **A2:** an implemented seat operation is missed by deterministic recognition and has no valid semantic-planner exposure.
- **C2:** the model selects the correct capability, but a local lexical admission gate rejects equivalent passive wording.
- **D8:** selection and temporal intersection produce the checked Member and interval, but evidence formatting leaks a term value from another retrieved row.

These failures do not establish a fundamental inability to execute multi-relationship queries. Successful cases demonstrate that ability. Conversely, those successes do not establish arbitrary composability or architectural soundness.

---

## 1. Baseline and evidence sources

### Repository revision

**Observed—execution:**

| Item | Finding |
|---|---|
| Repository | Expected `stephenrigney/OireachtasOntology` checkout |
| Branch | `master` |
| Reference revision | `563a385173d312d33d22ca7868524714487967aa` |
| Current HEAD | `3bdaa2b871096965ccc1b07d376b242879bc8585` |
| Working tree | Clean before and after investigation |
| Remote freshness | Not established; no fetch performed |

The checkout has advanced since Stage 3. The following differences were examined before attributing behaviour:

| Subsequent change | Relevance |
|---|---|
| Sponsorship discovery changes, including `30a611c` | Current prompt construction excludes schema-inadmissible generic selectors and explicitly directs sponsorship to its graph family. |
| Present-time policy changes, including `03ee123` | Contract advances from **2.29.0 to 2.30.0**; shared current-scope classification and broader scoped defaults are introduced. Additional historical-scope guards also appear. |
| Latency instrumentation, including `44ceec1` and `0305220` | Adds timing wrappers and presentation diagnostics. This is not evidence of unchanged end-to-end runtime behaviour. |
| Report persistence at `3bdaa2b` | Retains Stage 1–3 reports and experimental evidence. |

Relevant differences are visible in:

- `poc/nlq/composable_semantic_planner.py`
- `poc/nlq/interpretation.py`
- `poc/nlq/{app,representation,stage_a,committee_members,office_representation,government}.py`
- `poc/specs/composable-query-plan-contract.json`
- `poc/specs/composable-query-plan.schema.json`

The semantic draft schema is **byte-identical** between the reference and current revisions. The principal dispatcher, semantic dispatch function, top-level draft validator and D8 projector were also compared structurally. Their implicated logic is unchanged, except where explicitly distinguished below.

**No current-HEAD live `/ask` campaign was conducted.** Stage 3 runtime observations remain attributed to its recorded reference revision.

### Evidence and integrity

The three authoritative reports were read, together with selected raw proposals, plans, queries, results, HTML, independent expectations and RDF bindings.

**Observed—execution:**

- All **48 files** listed in the Stage 3 SHA-256 manifest match.
- All seven input pins in `nlq-stage-3-20261110/baseline.json` match, including Stage 1/2 reports, lockfile, reviewed office decisions and capture-selection manifests.
- All 30 retained response records are present.

Principal retained evidence:

- `docs/reports/query-service/nlq-stage-3-20261110/responses.jsonl`
- `…/oracle-before.json`
- `…/expected-answers.json`
- `…/execution-log.txt`
- `…/independent-oracle-review.md`
- Individual `ID-rN.html` responses.

Hereafter, **S3/** abbreviates `docs/reports/query-service/nlq-stage-3-20261110/`.

### Evidence labels and limits

- **Observed—static:** inspected source, contracts or assertions.
- **Observed—historical:** retained Stage 3 execution.
- **Observed—diagnostic:** bounded offline execution during Stage 4.
- **Inferred:** supported reconstruction without a complete original trace.
- **Hypothesis / Unknown:** not established.

Stage 3’s limitations remain: loaded capture identity, complete subsidiary-query timelines, sponsorship role/primary-status adjudication and comprehensive unlabelled/conflicting-evidence certification are not established. No new service, provider or RDF requests were made to erase those limitations.

---

## 2. Actual generalisation mechanisms and boundaries

### 2.1 Three different representation/admission surfaces

**Observed—static:** the system does not have one schema whose accepted documents uniformly compile.

1. **Model draft:** a closed union of semantic graph shapes or one capability/input selection.
2. **Canonical/final plan:** locally constructed typed referents, relationships, selectors, constraints and projections.
3. **Executable admission:** handwritten family validators and family-specific executors.

The final JSON envelope is structurally more permissive in some respects than the model draft, but these inventories are **not nested supersets**:

- `dail_seats` is a final-plan family but not a model-draft family or selectable capability.
- Python accepts `current_committee_members` and `current_office_constituency`, although the final-schema family enum omits them.
- Some draft family names are adaptation instructions rather than persistent final-family names. E1/E2’s canonical sponsorship plans omit `family` entirely.

Therefore, an enum comparison alone cannot establish executable capability.

Sources: `poc/specs/composable-query-plan-draft.schema.json:6–12,18–193`; `poc/specs/composable-query-plan.schema.json:21–62`; `poc/nlq/composable_plan.py:1720–1767`; `poc/nlq/composable_semantic_planner.py:263–278`.

### 2.2 What enables reuse

**Observed—static and historical:**

- **Parameters rather than fixed answers:** term numbers, grounded Member mentions, offices, parties and constituencies are resolved locally.
- **Exact resource joins:** separate membership paths join through Member, HouseTerm and constituency IRIs—not matching labels.
- **Canonical adaptation:** different draft relation identifiers and wording can collapse to the same reviewed execution plan.
- **Shared evidence operations:** interval parsing, intersection, pagination, identity checks and result envelopes are reused.
- **Family-specific orchestration:** the officeholder chain reuses current representation after passing the exact resolved Member identity.

Concrete controls:

- B3/B4 retain identical party labels but use disjoint term-specific party identities.
- E1/E2 produce identical canonical plans, SPARQL and checked result rows.
- D1–D4 preserve the applicable current/historical relationships despite wording, entity and term changes.
- D7 resolves an explicit constituency set and performs an identity-based union.
- D8 executes a substantially more complex graph and four-interval intersection.

Sources: `S3/responses.jsonl:4–7,12–22`; `poc/nlq/composable_semantic_planner.py:490–533`; `poc/nlq/office_representation.py:60–109`; `poc/nlq/composable_plan.py:3081–3192,5172–5444`.

### 2.3 What prevents unrestricted composition

**Observed—static:** validators require particular role sets, edges, selectors, constraints and answer shapes. An extra supported relationship is not automatically an admissible addition.

The model draft has no general:

- Boolean expression tree;
- arbitrary aggregation/computed-projection language;
- sequence of stages with intermediate-result bindings;
- instruction to compose arbitrary selected executors.

Existing multi-stage behaviour is implemented inside particular executors. It is not exposed as general pipeline construction.

Sources: `poc/specs/composable-query-plan-draft.schema.json:6–8,18–207`; `poc/nlq/composable_semantic_planner.py:719–795,1100–1237,1598–1817`; `poc/nlq/composable_plan.py:6540–6643`.

**Inferred:** the architectural constraint is the **closed admitted language and family execution design**, not a demonstrated inability of graph representations or SPARQL to express the relationships.

The optional Phase 1 translator and separate semantic-v1 compiler are different paths. Their capabilities are not default composable-v2 fallbacks.

---

## 3. Compositional expressiveness matrix

“Representable” below means a schema-conforming semantic draft or existing selector, unless otherwise stated. “Static” does not imply a new runtime demonstration. A dash means downstream execution is not reached—not factual impossibility.

| Concrete query combination and intended meaning | Representable | Admissible | Existing execution | NL reachability | Evidence / first limiting boundary |
|---|---|---|---|---|---|
| Members recorded in **two numbered Dáil terms**, joined by exact Member identity | Yes | Yes, reviewed shape | Yes, static | Semantic route, static | Source evidence required; not newly executed |
| Same intersection across **three numbered terms** | Not in the draft’s closed referent shapes; a generic final graph container could store additional roles | No corresponding admitted shape | No general executor fallback | No supported draft route | **Draft/admitted-language boundary**, not proven graph-format incapacity |
| Current named-party TDs representing one constituency—both relationships active at `asOf` | Yes | Yes | Yes | D1/D2/D3 observed | Checked identities and intervals agree |
| Historical party/constituency selection in a numbered Dáil—validated episode/membership overlap | Yes | Yes | Yes | D4 observed | Correct term-33 paths; no substitution of current relationships |
| Explicit OR across two to four constituencies, retaining current party and representation tests | Yes, bounded identity set | Yes | `VALUES` identity-set compilation | D7 observed | Correct checked union; not arbitrary disjunction |
| Current unfiltered constituency list → distinct-Member count | Yes | Yes | Reviewed count after selection | D5 semantic / D6 deterministic | Count 4 matches the checked four-Member list |
| Add that count projection to the named-party-plus-constituency selection | Count syntax exists | Rejected: party counts restricted to the reviewed party-only selection | — | No admitted equivalent count route | **Family projection validation**, not demonstrated inability to count |
| Other party TDs sharing an anchor’s constituency while the anchor held office | Yes, independent paths and four intervals | Yes | Yes | D8 observed | Checked Member/intersection correct; **projection annotation fails** |
| Current officeholder → exact Member → independently current constituency | Yes, capability selector | Yes for admitted wording | Fixed multi-stage executor | C1 observed; C2 rejected | C2 first fails **lexical admission** |
| Current committee members **and** current named-party membership, joined by Member identity | No combined draft shape | No corresponding admitted family | Separate operations do not supply automatic combined execution | No supported combined route | **Draft/admission boundary**; available combined evidence not evaluated |
| Sponsored Bills → distinct count restricted by typed Published activity year | Yes | Yes | Yes | E5 observed | **Required publication evidence unavailable**; no zero inferred |
| Sponsored Bill list → unqualified all-time count | Count syntax exists | Unsupported reviewed projection | — | E4 correctly refused | **Explicit scope/projection restriction**, not generic counting impossibility |
| Membership in both current House terms → simultaneous active service | Existing term-intersection shape represents a different meaning | Additional simultaneity/date conditions rejected | No admitted simultaneous-service variant | Bounded semantic route only | **Semantic/admission boundary**; term membership must not be relabelled simultaneous service |

Sources:

- Draft shapes: `poc/specs/composable-query-plan-draft.schema.json:64–162,196–207,303–315`.
- Exact-edge and projection admission: `poc/nlq/composable_semantic_planner.py:719–795,1100–1237,1330–1499,1598–1817`.
- Execution/evaluation: `poc/nlq/composable_plan.py:3081–3192,5317–5403,5447–5689,6418–6436`.
- Historical controls: `S3/responses.jsonl:8–24`.

Additional boundaries:

- Anchor exclusion is an implemented **specific identity exclusion**, not generic negation.
- Arbitrary grouping, sums, averages and computed projections are not implied by the existence of distinct counts.
- Historical officeholder/representation composition requires an established interpretation of which holding, membership and common period are intended. Combining two existing operations does not resolve that semantic question automatically.

---

## 4. Selection and reachability

### 4.1 A2: implemented seats, absent semantic exposure

**Observed—historical:** A2 correctly identifies its intent as counting seats in the 34th Dáil, but returns `supported=false` and says the capability is unsupported. A1 executes the implemented seat lookup and returns 174.

Evidence: `S3/responses.jsonl:1–2`; `S3/A2-r1.html`.

The causal boundaries are:

1. **Deterministic recognition is narrow.**
   `stage_c_request_family` recognises “how many members were in the Nth Dáil”, not A2’s explicit-seat form.

2. **The semantic interface does not expose `dail_seats`.**
   It is absent from both the draft-family enum and capability-selector enum.

3. **No generic numeric-property escape exists.**
   Count-intent drafts are restricted to reviewed Member-composition or Bill-sponsorship counts. Member counts are explicitly prevented from substituting for seats.

Sources: `poc/nlq/stage_c.py:103–132`; `poc/specs/composable-query-plan-draft.schema.json:12,164–193`; `poc/nlq/composable_semantic_planner.py:244–278`.

**Observed—diagnostic:** `plan_stage_c(A1)` returns `dail_seats`; `plan_stage_c(A2)` returns `None`. Independent recognition probes also reject another explicit-seat paraphrase.

The seat executor itself reads a unique positive typed `agents:seats` value; it does not count Members. Its operation already exists and was exercised by A1/A3.

Source: `poc/nlq/stage_c.py:427–470`.

**Conclusion:** A2 demonstrates a recognition/exposure gap, not a seat-compilation limitation. Missing catalogue exposure alone would not prove this; the absence of a direct graph-family alternative and the relevant validation gates complete the explanation.

**Unknown:** the model’s internal reason for choosing that refusal text and its refusal repeatability. Nevertheless, repeating A2 is unnecessary to establish the missing schema-conforming seat route.

The refusal prose also misdescribes the implementation: the operation exists. Model-authored refusal text is not reliable evidence of actual system capability.

This conclusion concerns **default composable-v2**. It does not establish that optional Phase 1 could never produce a seat query.

### 4.2 C2: correct selection, lexical false negative

**Observed—historical:** C1 and C2 select:

```text
current_office_constituency
office = "Minister for Finance"
```

Their drafts differ materially only in free-text intent. C2 is rejected locally.

Evidence: `S3/responses.jsonl:8–9`.

The reference-baseline `office_representation.validate_request` admits two closed forms:

- constituency **does office represent**;
- constituency **is office a TD/deputy for**.

It does not admit:

> “Which constituency **is represented by** the current office?”

Source: `poc/nlq/office_representation.py:23–30`, with the same lexical gate at the reference revision.

**Observed—diagnostic:**

| Captured draft | Original question supplied to validation | Result |
|---|---|---|
| C1 | C1 | Accepted |
| C1 | C2 | Rejected |
| C2 | C1 | Accepted |
| C2 | C2 | Rejected |

Executing the exact reference validator in memory independently reproduces C1 acceptance and C2 rejection.

**Conclusion:** the discriminating input is the original surface wording, not capability selection, office identity, graph representation or available Finance evidence.

The local `ValueError` is converted to `UnsupportedComposableRequest`; the public outcome is `unsupported_capability`. That status does not establish unsupported underlying semantics.

Sources: `poc/nlq/composable_semantic_planner.py:881–891`; `poc/nlq/composable_plan.py:6504–6509`.

### 4.3 Important current-source difference

The reference office validator contained the lexical gate alone. Current HEAD additionally calls `current_relationship_scope`.

**Observed—diagnostic at current HEAD:**

```text
C1 → "inferred"
C2 → None
```

The shared classifier treats `represented` as a historical marker without distinguishing this present passive construction.

Sources: `poc/nlq/office_representation.py:31–33`; `poc/nlq/interpretation.py:12–35`.

Thus:

- **Reference C2 cause:** local positive-form admission regex.
- **Current additional boundary:** a shared scope classifier independently rejects the same wording.

The later shared mechanism must not be retrospectively attributed to Stage 3.

### 4.4 Shared mechanisms versus isolated failures

Office and committee admission both substitute the grounded mention and apply a closed fullmatch. A bounded committee probe accepts:

> “Who are the members of the Committee on Public Accounts?”

but rejects:

> “Which Members belong to the Committee on Public Accounts?”

This demonstrates another **component-level wording boundary**, not another live application failure.

Source: `poc/nlq/committee_members.py:27–39`.

These positive admission gates must be distinguished from negative whole-intent guards that prevent dropping conditions. Similar lexical implementation style does not make them one central mechanism.

Another static wording dependency exists in sponsorship adaptation: ordinary lists use a canonical question, whereas Published-year sponsorship adaptation calls the deterministic planner with the original question. No additional runtime failure is claimed.

Source: `poc/nlq/composable_semantic_planner.py:490–499`.

### 4.5 Successful cross-route controls

**Observed—historical and diagnostic comparison:**

- **B1/B2:** identical SPARQL and result rows. Plans differ only by explicit `includeGroups=true` versus omission, whose executor default is true.
- **E1/E2:** identical canonical plans, SPARQL and checked result rows. E2 uses the working sponsorship graph family.

Sources: `S3/responses.jsonl:4–5,20–21,27,30`; `poc/nlq/stage_c.py:424–425`; `poc/nlq/composable_semantic_planner.py:490–533`.

At the reference revision, sponsorship was misleadingly advertised among generic selectors even though its selector was absent from the strict schema and adapter dispatch. A **schema-conforming** proposal could not use that generic selector. E2’s success therefore does not establish a probability of choosing between two equally valid routes.

Current prompt guidance removes that misdirection, but the contract inventory still contains the sponsorship entry and the generic adapter remains absent. No Stage 3 success is credited to the later prompt change.

Finally, fallback is bounded: one model proposal, no automatic repair, no automatic Phase 1 downgrade, and no universal retry after recognised-handler failures.

Sources: `poc/nlq/structured_planner.py:256–306`; `poc/nlq/composable_plan.py:6456–6643,7331–7342`.

---

## 5. Cross-family semantic consistency

| Concept | Implemented meaning and controls | Assessment |
|---|---|---|
| **Current relationship** | Party composition tests membership and party episode independently at `asOf`; officeholder composition independently tests holding and representation. D1/D2 and C1 support these meanings. | Reusable date helpers plus family-specific obligations—not one universal current operator. |
| **Current term versus current service** | Plain non-party “in this Dáil” can be term-wide; explicit current representation requires active membership. Current cross-House term intersection does not assert simultaneous service. | Deliberate distinctions, not demonstrated semantic drift. |
| **Historical overlap** | D4 validates the historical party/membership overlap in term 33 rather than using today’s relationships. | Positive control supports temporal fidelity. |
| **Identity** | Exact Member and occurrence IRIs join relationships. B3/B4’s identical labels have disjoint party IRIs. C1 passes the accepted holder’s exact Member identity to representation. | Demonstrated identity preservation in checked cases. |
| **Distinct counts** | Count after identity and temporal selection. D5=4 agrees with D6’s four active Members. | Supported within reviewed selections, not a general aggregate guarantee. |
| **Filter removal/addition** | D1→D6 removes party filtering while retaining current representation. D7 adds a bounded constituency identity set. | Successful supported transformations; not automatic graph-edit closure. |
| **Common interval** | D8 intersects holding, anchor membership, answer membership and party episode together. | Checked common interval correct despite separate annotation defect. |
| **Evidence completeness** | Pagination, hard-cap rejection and qualified partial results vary by family. Missing evidence is not universally treated as zero or absence. | Family-specific policy; no universal completeness certification. |

Sources: `poc/nlq/composable_plan.py:5122–5164,5300–5328,5390–5442,5447–5689`; `poc/nlq/office_representation.py:72–113`; `poc/nlq/pagination.py:8–32`; `poc/nlq/representation.py:391–402`.

### Shared mechanisms and duplication

**Observed—static:** interval parsing, identity validation, pagination and some temporal projection are shared. Graph admission, interpretation defaults, current-term selection obligations and projection assembly remain substantially family-specific.

Duplication alone is not evidence of inconsistent behaviour. The positive controls demonstrate agreement across several different implementations. Conversely, shared code is not automatically safe: D8 occurs inside a reused temporal projector.

### Revision-sensitive semantic finding

At the reference revision, unqualified named-party current defaults differed between Dáil and Seanad. Current contract 2.30 explicitly generalises the scoped policy.

The Stage 2 disagreement over current Dáil party counts is therefore retained as a **reference-version contract/code discrepancy**; the later contract wording is not silently applied retrospectively. Stage 4 does not adjudicate a replacement meaning for the reference contract.

### Evidence restrictions are not compiler failures

- C3 lacks accepted current holding evidence; no holder or constituency is substituted.
- E5 lacks required valid Published-date evidence; no zero is returned.
- B’s group qualification is not an assertion that historical groups did not exist.

These controls distinguish source/evidence boundaries from inability to express a supported operation.

---

## 6. D8 evidence-integrity causal analysis

### 6.1 Earliest erroneous association

**Observed—historical:**

- D8 displays Cyprian Brady’s `/30` membership alongside an additional `term /25`, then correctly states shared term `/30`.
- The retained qualifying binding identifies both membership and term as `/30`.
- Independent expected evidence also identifies term 30 and common interval `2007-06-14–2008-05-07`.

Sources:

- `S3/D8-r1.html:109,436–438,494–497`
- `S3/oracle-before.json:3221–3228`
- `S3/expected-answers.json:373–389`
- `S3/responses.jsonl:19,26,29`

Other-term candidates legitimately occur in the broad retrieval. A retained Dermot Fitzpatrick candidate has term `/25`.

Source: `S3/D8-r1.html:548–564,606–608`.

Thus `/25` is not inherently erroneous RDF. The error is attaching another candidate’s term to Cyprian’s qualifying evidence.

### 6.2 Exact source cause

In `_temporal_member_party_result`:

1. The raw-row loop assigns:

   ```python
   term_iri = _require_local_iri(row[index["term"]], term_type)
   ```

   at `poc/nlq/composable_plan.py:5249`.

2. Anchored records retain their own term in the grouping key, at `:5214–5216`.

3. After the raw-row loop, evidence assembly prints:

   ```python
   f"membership {_membership_iri}; term {term_iri}; ..."
   ```

   at `:5365`.

   That variable still contains the term from the **last raw row processed**, including a row that subsequently fails temporal selection.

4. The anchored suffix correctly prints the qualifying record’s own `key[7]`, at `:5368–5372`.

This directly accounts for contradictory term assertions in one evidence string.

The faulty text addition originated in commit:

```text
1dce0cbab581a25fddfa2b2ccdcf6acd0fd1983c
```

dated 2026-11-09. It is present at the reference revision and unchanged at current HEAD.

### 6.3 Bounded counterfactual confirmation

An initial exploratory shaped-row probe was subsequently confirmed using **unchanged, complete RDF binding objects recovered from the retained debug prefix**, the captured full D8 plan and the existing projector.

Eleven complete bindings could be recovered before truncation. No missing tail was reconstructed.

| Projector input | Member / common interval | Displayed term assertions |
|---|---|---|
| Qualifying Cyprian `/30` binding only | Cyprian; checked interval | `/30`, `/30` |
| Same binding followed by nonqualifying Dermot `/25` binding | Unchanged | **`/25`, `/30`** |
| Same two bindings in reverse order | Unchanged | `/30`, `/30` |

**Observed—diagnostic:** annotation depends on unrelated row order; the checked Member and intersection do not.

This was a component-level causal probe, not a new factual-query result, full-query replay or completeness test.

### 6.4 Scope and remaining uncertainty

The projector is shared by temporal Member/party list paths. However:

- valid unanchored plans select one exact term, masking this cross-term leak;
- anchored retrieval can span terms and exposes it;
- count output does not display the affected evidence string;
- Stage 3 D4 supplies a single-term positive annotation control.

Sources: `poc/nlq/composable_plan.py:5250–5254,5391–5411`; `S3/D4-r1.html:109`.

**Unknown:** the exact final binding that supplied `/25` during the original full execution. The debug payload is truncated at 50,000 characters. The particular candidate cannot be identified from the retained tail.

Source: `poc/nlq/results.py:11–24`.

**Conclusion:** D8 establishes incorrect explanation/provenance annotation—not an incorrect checked Member or common interval. The earliest erroneous semantic association is in Python evidence-string assembly, before HTML presentation.

---

## 7. Competing hypotheses and diagnostic results

| Hypothesis | Supporting or falsifying evidence sought | Result and alternatives |
|---|---|---|
| **The representation fundamentally cannot execute multi-relationship compositions.** | Support: no admitted multi-path examples. Falsification: real execution preserving multiple joins and temporal obligations. | **Rejected in this broad form:** C1, D7 and D8 execute meaningful compositions. The narrower closed-language constraint is established statically. This does not prove arbitrary graph expressiveness. |
| **A2/C2 are simply model-selection variability.** | Support: wrong capability or differing semantic parameters determine failure. Falsification: absent valid exposure or acceptance changes with question wording alone. | A2 has no valid exposed seat route; C2 selects correctly and cross-tests isolate lexical admission. A2’s internal model reasoning and refusal repeatability remain unknown. |
| **Apparent limits are mainly inconsistent temporal meanings or missing evidence.** | Support: controls use wrong dates/identities, or required evidence is absent. Falsification: positive evidence exists while selection/admission fails. | C3/E5 are evidence-limited; A2/C2 are not explained by those gaps. D1–D7 support the checked temporal distinctions. This is not exhaustive semantic-consistency certification. |
| **D8’s wrong term originates in qualifying RDF rather than projection.** | Support: qualifying binding already has `/25`. Falsification: qualifying `/30` plus order-dependent annotation from another row. | **Rejected for the demonstrated mismatch:** retained bindings and counterfactual projector calls establish a cross-row annotation leak. Original final-row identity remains unknown. |

No implementation change was needed to resolve these causal questions. No additional provider sampling or broad benchmark campaign was justified.

---

## 8. Classification of verified limitations

| Limitation | Classification | Basis |
|---|---|---|
| A2’s narrow deterministic recognition plus absent semantic exposure | **Shared implementation weakness, with a local recognition gap** | Capability availability is not consistently reflected across recognition, draft exposure, catalogue guidance and adapters. Seats are a demonstrated instance; sponsorship supplies a separate registration inconsistency. |
| Reference C2 passive-form rejection | **Local defect—false-negative admission** | The requested semantics match the implemented current chain; only surface form determines rejection. No semantic/evidence justification for this exclusion was found. Intentional narrow syntax versus intended language coverage remains a requirements-level distinction. |
| Current shared scope classifier’s treatment of passive `represented` | **Shared implementation weakness** | A central classifier independently misclassifies the same present passive construction. Its wider runtime effect is unmeasured. |
| D8 stale `term_iri` in evidence formatting | **Local defect in shared projection code** | Exact variable-lifetime error established. Wider annotation exposure is conditional; other factual answers are not shown incorrect. |
| No arbitrary combination of supported graph operations or executor stages | **Architectural constraint** | Closed draft shapes, exact admission rules and family execution dispatch. Not automatically a defect. |
| Current-only chains, bounded counts, finite OR and rejection of unrepresented conditions | **Deliberate restrictions** | Explicit reviewed scope prevents dropping requested semantics. Their existence does not prove every excluded combination inherently unsafe. |
| Independent interval, identity, ambiguity and completeness checks | **Deliberate semantic/evidence restrictions** | Required to avoid replacing unknown relationships with assumed facts. |
| Final-schema/Python family discrepancies | **Unresolved operational impact** | Static inconsistency verified; browser validation is handwritten, and successful C1 is not blocked by the final-schema enum. |
| Loaded-source lineage and stopped oracle facets | **Unresolved evidence limitations** | Insufficient retained evidence for complete provenance or whole-projection certification. |

---

## 9. Implications for wider capability

### Demonstrated consequences

1. New entities, numbered terms and admitted wordings can reuse existing functionality without question-specific implementation.
2. A natural paraphrase can lose access to an implemented operation before compilation.
3. Successful model interpretation does not guarantee local admission.
4. Multiple relationships can compose correctly when their complete graph and temporal meaning are reviewed.
5. An existing list operation does not imply an admitted count, exclusion or additional join.
6. Validated plans and correct selected identities do not guarantee correct evidence annotations.
7. Repeatability is not sufficient for evidence correctness: D8 repeats the same annotation defect.

### Conditional predictions—not measured outcomes

- A deterministic-only operation whose wording misses recognition cannot be recovered through a semantic interface that exposes no valid equivalent route.
- Combinations outside the admitted shapes will remain unavailable through schema-conforming proposals, regardless of evidence availability.
- Similar mixed-term inputs to the affected projector can leak term annotations; this is not a claim that all projection families are affected.
- Lexical admission and scope classification can create further paraphrase boundaries. No frequency or general failure rate is inferred.

None of these findings establishes that a different architecture is required.

---

## 10. Questions reserved for Stage 5

1. What degree of compositional closure is required beyond the current reviewed family language?
2. Which additional combinations have sufficiently defined temporal meaning, identity requirements and evidence obligations to be considered valid capabilities?
3. Which distinctions must be explicit in plans, and which may remain family-defined—for example, current term versus active-at-date service?
4. What constitutes authoritative agreement among capability inventories, draft schemas, canonical plans, validators and presentation contracts?
5. What evidence/provenance consistency is required for acceptance independently of primary-answer correctness?
6. What source identity and completeness evidence is necessary to resolve the still-stopped factual certification facets?
7. How should language-coverage boundaries be distinguished from genuinely unsupported semantics in reported outcomes?

These are unresolved questions, not implementation proposals or architectural decisions made by Stage 4.

---

## 11. Stage 4 exit-criteria assessment

| Criterion | Assessment |
|---|---|
| Composition, selection and validation mechanisms established | **Met**, through source reconstruction, retained executions and bounded diagnostics |
| A2, C2 and D8 causally explained as far as evidence permits | **Met**, with model-internal reasoning and D8’s exact final source binding explicitly unknown |
| Successful generalisation controls examined | **Met:** B1/B2, E1/E2 and D1–D7 |
| Defects, shared weaknesses, architectural constraints and deliberate restrictions distinguished | **Met**, with unresolved operational impacts identified |
| Practical implications for wider capability identified | **Met**, separating demonstrated consequences from conditional predictions |
| Remaining decisions reserved for Stage 5 | **Met** |
| Current-HEAD live reliability or complete factual certification | **Not established; not claimed** |
| Read-only/non-destructive constraints | **Met** |

### Verification and preservation

- Repository and retained-evidence integrity checks passed.
- Focused pytest execution was attempted:

  ```text
  .venv/bin/python -B -m pytest -p no:cacheprovider -q \
    tests/test_nlq_office_representation.py tests/test_nlq_stage_c.py
  ```

  It exited with `No module named pytest`; no pytest tests ran.

- Offline diagnostics exercised existing recognisers, validators, the scope classifier and projector.
- No fixes, source/fixture changes, dependency installation, service requests, production mutation or architectural redesign occurred.
- Final Git status and diff checks are clean.
- This report is returned here for review; no repository report file was written.

**Disposition:** Stage 4 is complete for its bounded causal objective and returned for ChatGPT review. **Stopped after Stage 4. No Stage 5 work has begun.**
