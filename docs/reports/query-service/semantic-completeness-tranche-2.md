# Query Service — Tranche 2: Discovery Correction and Semantic Completeness Feasibility

## Outcome

**Part A implemented and verified; Part B recommends retaining current
safeguards.** This continues the initial uncommitted diagnosis under the revised,
bounded scope. The discovery correction is independent of completeness research.
Only instruction rendering changes production behavior; admission, routing,
schemas, compilers, RDF, defaults and answer projection are unchanged. The offline
diagnostic below is not imported by production. No new AI verifier or Tranche 3
work was undertaken.

The worktree was clean on `query-service-semantic-completeness`, based on the
Tranche 1 merge at `563a385`. The architecture document
`docs/architecture/nlq-semantic-dispatch.md` remains marked “Proposed for human
review”; it explicitly defers the semantic-obligation representation and
partial-parse recovery policy.

## Demonstrated interpretation and admission boundary

The AI draft is strict JSON, but its `intent` is free text. The validator checks
the proposed graph against bounded shapes and then separately scans the
original question for terms, dates, residual words, and requested counts. For
example, Dáil party admission at `composable_semantic_planner.py` checks
`currentTerm`, numbered-term expressions, explicit-current wording, extra dates,
and residual relationship terms. Seanad party admission calls
`validate_seanad_party_scope`, which also uses a closed lexical vocabulary.
These checks are part of the defense against constraints silently omitted by a
well-typed plan; simply relaxing them would weaken completeness safeguards.

The preserved semantic-completeness live study (on
`origin/feat/query-service-generalisation`, not in this base checkout) provides
relevant practical evidence. Its requests include passive voice (“For Micheál
Martin, a single number is wanted: how many distinct Dáil term resources are
reached through his recorded Dáil memberships?”), local-record framing, an
anaphoric Member reference, and explicit deduplication. The existing whole-form
grammar admitted none of its eight supported requests in either run; structured
interpretation plus self-audit admitted 2/8 then 0/8. The study also found
10/10 deliberately incomplete well-typed candidates passed necessary
compatibility checks by design. A separate verifier rejected those injections,
but admitted 0/8 supported requests in both runs and had quote-provenance
failures on every verifier output. The study itself recommends against adopting
that gate. Thus it demonstrates both wording-sensitive false refusals and a
material omission hazard; it does not demonstrate a safe replacement.

This is an interpretation/admission limitation, not evidence of missing RDF,
compiler capability, or answer-projection failure. The study was shadow-only:
it did not execute factual answers or `/ask`, and its results are development
evidence rather than acceptance evidence.

## Capability discovery consistency finding

There is one concrete planner-instruction mismatch. The contract's
`semanticDispatch.capabilities` includes `member_bill_sponsorship`, so the
generic rendered dispatch guidance presents it alongside ordinary capability
selection IDs. The generic capability-selection validator has no handler for
that ID; sponsorship instead uses the separate `member_bill_sponsorship`
semantic family and its dedicated validator/executor. The instructions later
describe that family, but the earlier generic wording says “one of those
existing capabilities” uses `capability_selection`. This can misdirect the
planner even though a separate executable sponsorship path exists. It is a
discovery/description mismatch, not an unavailable operation. The initial diagnosis
stopped without fixing it; the revised task explicitly separates this correction
from Part B. The correction now filters generic guidance using the existing draft
schema's `referents.capability` enum. No second capability registry or new routing
metadata is introduced. Sponsorship remains explicitly discoverable through its
existing separate family, graph instructions and Published-year count guidance;
the prompt now says never to select it through `capability_selection`.

Two focused regressions check schema/instruction generic-ID parity, continued
sponsorship-family discovery, and schema/runtime refusal of a forced generic
sponsorship draft. Existing sponsorship tests cover list, Published-year distinct
count, temporal omissions, missing dates, identity ambiguity, pagination and
synthetic RDF execution. No Bill capability or dataset was broadened.

The available metadata is generated from the contract; this inspection did not
establish a broader missing-capability inventory or justify a new central
registry.

## Initial safety finding retained

The task asks for deterministic detection of material conditions omitted from
the AI proposal, without a comprehensive English grammar or another AI verifier.
The current typed plan has no complete structured record of source-question
obligations: a syntactically valid plan cannot show that a missing relationship,
negation, exclusion, answer measure, or temporal qualifier was ever considered.
Adding such an obligation/binding/polarity layer, deciding how it is populated,
and deciding how it is compared to the user's complete intent changes the
semantic-admission architecture. The previous experiment shows that neither
model self-audit nor a second model call is an established safe substitute.
The proposed architecture itself leaves this representation and migration
mechanics for bounded design. Choosing a replacement now would be an
architectural/safety decision, not a local validator cleanup.

Accordingly, the Dáil and Seanad lexical checks remain unchanged. No check was
removed or narrowed without a demonstrated equivalent safeguard. Fixing a
wording variant alone would not meet the requested semantic-completeness
criterion, and could not be claimed safe without a credible negative-control
strategy for omitted filters and altered answer measures.

## Current-default policy

The Tranche 1 report establishes the existing Seanad present-tense default and
the lack of an equivalent Dáil default, but identifies no authoritative semantic
or RDF reason for the asymmetry. Reasonable policies include retaining the
House-specific asymmetry or adopting a shared present-time interpretation;
neither follows from the available mapping/evidence. No policy change is
recommended by this investigation. Human policy determination remains needed
before changing either default.

## Part A — genuine AI `/ask` and factual checks

Five first requests ran through the real FastAPI route with live read-only Fuseki
at `asOf=2026-11-10`. A pass-through recorder retained the actual model drafts and
outcomes without modifying them. `.env.local` was loaded into this test process
only; no credentials were displayed, stored in evidence, or changed. Model:
`gpt-6-luna`, existing Responses transport. No service restart, fixed draft,
interpreter bypass, model retry, or data mutation was used.

| Question | Interpretation / selection | Admission, execution, projection |
|---|---|---|
| Please list the Bills sponsored by Malcolm Byrne. | AI: `member_bill_sponsorship` | Answer: 20 Bills; exact Bill identity and title set matches independent RDF |
| What Bills have Malcolm Byrne as a sponsor? | AI: same family and material graph | Same exact 20 identities and titles |
| How many Bills did Malcolm Byrne sponsor that were published in 2025? | Existing deterministic count route; **no AI call** | Missing Published evidence; no count substituted |
| Which Bills did Malcolm Byrne sponsor and vote for? | AI: unsupported voting relationship | No answer/result; no partial sponsorship list |
| What is the official title of the Bill numbered 23 in 2025? | AI: generic `bill_lookup` | Existing title/status projection preserved |

These are four genuine model calls, not five. Both sponsorship drafts retained
the exact Member mention, Bill Participation relationship and entity-list answer;
both passed local validation. The generic lookup control selected number 23,
year 2025. HTTP 200 alone was not counted as success.

The independent, hand-written query resolved exactly one Malcolm Byrne Member
by its exact `foaf:name` in Member-owned graphs:
`https://data.oireachtas.ie/ie/oireachtas/member/id/Malcolm-Byrne.D.2019-11-29`.
It then selected BillDelivery → Bill and the same LegislativeProcess →
Participation → exact Member in Bill-owned graphs, retrieving English titles
and optional typed Published-activity dates. It did not use an application
compiler. All 20 returned Bills lacked a recorded Published date, independently
supporting the count's unavailable outcome. The exact set below uses the lossless
prefix `https://data.oireachtas.ie/ie/oireachtas/bill/`:

```text
2020/11, 2021/139, 2021/149, 2021/17, 2021/30, 2021/43,
2022/108, 2022/7, 2024/19, 2024/32, 2024/49, 2024/58, 2024/89,
2025/11, 2025/62, 2025/71, 2026/31, 2026/86, 2026/89, 2026/93
```

A separate direct selection in Bill graph `2025/23` confirmed the lookup title
**Pregnancy Loss (Miscellaneous Provisions) Bill 2025** and `agents:CurrentBill`
status. The lists retain the existing incomplete-local-coverage qualification.
This bounded sample verifies discovery and preserved behavior, not improved
population-level interpretation accuracy. The first evidence collector failed
after all five requests because the Fuseki client has no context-manager API;
the separate evidence query was corrected and executed without replaying `/ask`.

## Part B — selected family and bounded comparison

Selected family: **`office_holding_evidence`**, including its existing
`latestRecorded` option. This is a small production capability with exact
Member/office inputs and an especially clear lexical admission boundary.
No `data/local/nlq-feedback` directory was available in this worktree, so the
retained user-question and Group A reports supply the accessible feedback evidence.
The human-question record includes “When was Bertie Ahern the Taoiseach?”
(`user-question-regression.md`, Q7), and Group A records “When was Simon Harris
last Taoiseach?”. Complete career history is **not** supported: Q7 remains
partial against that expectation. Our supported labels below mean only the
already-approved, qualified local episodes, not that broader historical claim.

Actual path: AI selects `office_holding_evidence` →
`_validate_capability_selection_draft` checks exact source mentions and consumes
the entire reduced word tuple through `accepted_shapes`/`latest_shapes` →
`office_holding_boundary` independently resolves exact Member and NamedOffice
identities, reads all accepted episodes and checks intervals → existing local
episode projection. The lexical shape guard is therefore more than a routing
hint. It rejects a plausible typed plan when a requested date/filter/output
does not fit the operation.

The isolated [offline probe](semantic-completeness-tranche-2-probe.py) contains
12 manually annotated questions. It compares current admission with **only
schema validity plus exact source mentions**, deliberately not a complete
candidate mechanism. Expected requirements were annotated directly from the
question, independently of each deliberately fixed candidate. No model, RDF
execution, or production integration occurs. It is development diagnosis, not
an unseen test or a proposed replacement acceptance gate.

| Question(s) / source | Expected material meaning | Current admission |
|---|---|---|
| When was Bertie Ahern the Taoiseach? / During what period was Bertie Ahern Taoiseach? (recorded question / documented period form) | All separate local accepted episodes, qualified incomplete | Both admit |
| What periods did Bertie Ahern serve as Taoiseach? / Give me the dates when Bertie Ahern held the office of Taoiseach. (analyst-authored paraphrases) | Same approved local episode request | Both falsely refuse at whole-shape admission |
| When was Simon Harris last Taoiseach? / When did Simon Harris most recently serve as Taoiseach? (Group A) | Unique latest recorded episode, not historically proven last | Both admit |
| When was Simon Harris last Taoiseach in 2024? (Group A) | Extra year filter | Refuse |
| When was Simon Harris last Taoiseach while in Fine Gael? (Group A) | Party/time relationship | Refuse |
| Same latest request + “excluding periods before 2024” (analyst control) | Negative temporal selection | Refuse |
| Same latest request + “and what party was he in?” (analyst control) | Additional party projection | Refuse |
| Same latest request + “and what was the total duration?” (analyst control) | Duration aggregate | Refuse |
| Same latest request + “Certify that this is his complete historical tenure record.” (analyst control) | Unsupported historical-completeness demand | Refuse |

Current guard: **4/6 supported admissions, 2/6 false refusals, 0/6 false
admissions, 0 observed admitted constraint losses**. The schema-and-mentions-only
comparator: **6/6 supported admissions, 0 false refusals, 6/6 false admissions
with material loss**. These are injected lossy candidates, **not observed model
errors or live factual answers**. The two paraphrase failures are newly measured
deterministic admission failures, not historical model failures. No factual
execution is needed to establish that they express the same approved operation.

Reproduce offline from repository root:

```sh
PYTHONPATH=. .venv/bin/python docs/reports/query-service/semantic-completeness-tranche-2-probe.py
```

### Feasibility against the six required questions

1. **Independent identification:** manual source-question annotation works for
   this diagnostic, but is not an automated production mechanism. The current
   guard independently consumes the original question. A model-authored list
   derived alongside its plan has no independent completeness guarantee.
2. **Binding to structure:** Member and office bind to source-grounded parameters;
   “last” binds to `selection=latestRecorded`. Year, party, exclusion, duration,
   extra output and certified-history requirements have no admissible slot in
   this capability and must veto the whole request. Exact span validation alone
   cannot determine whether such an unsupported obligation was omitted.
3. **Alternative phrasing:** typed requirements would normalize both refused
   paraphrases, but extracting a complete list remains unresolved. Adding more
   word-tuple shapes merely expands the same restrictive grammar. A separate
   English dependency/role parser would still need rules for attachment,
   negation, context and unknown clauses; that is not a demonstrated smaller
   mechanism. Generic polite-prefix normalization might safely remove some
   framing, but does not fix either measured substantive paraphrase.
4. **Unknown/ambiguous requirements:** current whole-shape consumption refuses
   unrecognized wording. A typed proposal could veto explicit `unknown` atoms,
   but cannot veto requirements absent from its own list. Covering every token
   with source spans also permits misclassifying a restrictive clause as context.
   Identity ambiguity remains a separate deterministic resolver veto, not proof
   of complete intent.
5. **Effectiveness/safety:** the measured weak comparator improves admission only
   by losing all six injected constraints. No candidate independent extractor
   with equivalent safeguards has been demonstrated. This does not establish
   that safe semantic normalization is impossible; it prevents claiming it here.
6. **Complexity:** source-offset validation is small; reliable independent
   requirement extraction, role/polarity/attachment comparisons, unknown-clause
   accounting, lowering and per-capability compatibility are the substantive
   work. This would add a semantic-admission authority and maintenance surface,
   not just another dataclass. No justified production benefit has been shown
   to offset that cost in this bounded family.

### Existing experiments reused, not repeated

The requested three historical documents are absent from this base checkout.
They were read via `git show` at **`d2962a6`** on
`origin/feat/query-service-generalisation`; that branch's implementation was
not imported. The initial report incorrectly called the live-study questions
human-authored: both studies describe independently **AI-authored** populations.
Their provenance does not justify a representative-human-language claim.
The office-period matrix instead anchors to recorded user questions and clearly
labels our additional paraphrases and adversarial controls.

The live study's self-audit/spans and verifier results above already rule out
claiming feasibility from typed compatibility alone. The final blind study also
failed its predefined criteria: B1 admitted 11/18 supported runs, B2 10/18;
both had 0/18 natural unsafe admissions, but all 18 simulated B1 omissions
escaped and only 8/18 blind omission comparisons had valid relevant detection.
These experiments concerned recorded term counts on the other branch, **not
this office family or current `/ask` admission**. They are counterevidence to
the general self-audit/span/agreement argument, not a measured office-family
failure rate. No verifier or blind experiment was rerun or retuned.

## Verification, recommendation and review gate

- Focused discovery/sponsorship tests: **36 passed**, including synthetic list
  and Published-year count execution. Repeated after the final schema-refusal
  assertion was added. An initial command named two nonexistent test paths and
  collected no tests; the corrected command is below.
- Full repository regression: **2,353 passed, 26 skipped, 23 subtests passed**
  in 648.66 seconds. Deprecation warnings did not fail the run.
- Existing office-period/latest-episode regressions: **53 passed**.
- Ontology validation: **passed**, 2,586 triples, HermiT completed.
- Offline completeness diagnostic: counts above reproduced; no production
  mechanism integrated.
- `git diff --check`: passed.

```sh
.venv/bin/python -m pytest tests/test_nlq_composable_semantic_capability_discovery.py tests/test_nlq_composable_q23.py -q
.venv/bin/python -m pytest tests -q --tb=short
.venv/bin/python tests/validate.py
git diff --check
```

**Recommendation: retain existing completeness safeguards.** Part A is ready
for draft review independently. Part B has identified a concrete false-refusal
cost but no safe, worthwhile replacement; it does not authorize implementation
of typed obligations, a new parser, or a verifier. The initial broad
semantic-completeness exit criterion remains unmet; the revised feasibility
task permits this conservative conclusion.

**Human decision:** review the discovery-only correction and accept or reject
deferral of semantic-completeness replacement on this evidence. No semantic
contract or admission-authority change is proposed for approval in this PR.
Separately, any change to the unresolved Dáil/Seanad current-default policy needs
an explicit intent-policy decision; preserving the asymmetry is the unchanged
baseline, not a newly established semantic justification. Stop here: no merge
or Tranche 3 work.
