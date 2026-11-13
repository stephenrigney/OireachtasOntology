# OireachtasOntology NLQ — Natural-Language Composition in the Main Query Interface

Starting point: `636e0dbd4429309bd3795d7556187e4446beacf0`, worktree
`query-service`, branch `nlq-composition-integration-slice`.

## Delivered behaviour

The default `/ask` interface directly executes independently admitted, unambiguous
current Member questions using **R + P, K + P and K + R**. R + P supports lists
and distinct recorded Member counts; committee-containing pairs remain list-only.
Yes/no requests are explicitly unsupported, not silently converted to lists.
There is no compulsory confirmation. `/composition` remains a temporary attended
comparison route; other established query families and candidate continuations
remain available.

The existing semantic planner now selects typed kernel operations, exact mention
spans, temporal scope and projection. `composition_admission.py` independently
accounts for residual vocabulary/operators, relationship and answer-head cues,
dates, negation, House scope and count/list/Boolean requirements. It is not a
sentence-template recognizer or a second model judging the first model. Unknown
conditions fail closed, including under a willing model that omits them. Older
current-family drafts cannot bypass these omission checks; their original
preflight and approved current-Dáil temporal interpretation are preserved.
Regression verification caught overly broad early routing: the established
Government planner and reviewed committee diagnostics now retain precedence,
and `on <date>` is not mistaken for a committee cue. The dated single-R count
path still supports its approved qualified recorded-zero result; native pair
counts retain the kernel's stricter nonempty-evidence rule. Existing acceptance
tests and source fixtures were not changed.

Execution reuses `composition_kernel.py` adapters, typed exact-identity binding
and evidence projection. Named P resolution reuses the reviewed affiliation
register **within current House terms**, preserving historical same-name identity
distinctions. K short names match whole source-labelled cores, retain every
matching incarnation, and support the already reviewed PAC alias. R resolves the
current **term-scoped constituency occurrence**, not a cross-term name concept.
R + P requires the exact same containing parliamentary membership and term.

Backend `asOf`, independent inclusive intervals, actual owner graphs, raw typed
facts, all name values, whole-plan limits and nonanswer behaviour are retained.
Resolution, every pagination probe and names share the eight-SELECT budget.
No candidate/invalid evidence is hidden by new term/date inner filters or by
changing the kernel's audited Member seed. There are no combination-specific
executors, arbitrary model-generated SPARQL, ontology/ETL changes, or Fuseki writes.

The main UI shows the interpretation, date, readable names/count and expandable
supporting paths, plus a downloadable typed ledger. Results are qualified as
local recorded evidence, never a certified complete roster. Evidence retention
remains bounded and process-local. The frozen experiment and its retained
historical evidence were not changed.

## Actual live answers

Real Chromium → `/ask` → configured semantic planner → existing read-only local
Fuseki, `asOf=2026-11-13`. All eight cases returned answers directly, using **six
charged SELECTs each**, including resolution and display evidence:

| Question | Actual answer |
|---|---|
| Who are the Sinn Féin TDs for Dublin Central? | Mary Lou McDonald |
| Please identify the representatives for Dublin Central who belong to Sinn Féin. | Mary Lou McDonald |
| Tell me the number of Sinn Féin TDs representing Dublin Central. | **1** distinct recorded Member, with Mary Lou McDonald's supporting paths |
| Which Fine Gael TDs represent Kildare North? | Joe Neville |
| Who on the Committee of Public Accounts belongs to Fianna Fáil? | Albert Dolan; Martin Daly; Paul McAuliffe; Séamus McGrath |
| Public Accounts members affiliated with Fianna Fáil: who are they? | The same four Members |
| For Galway East, show me the TDs who serve on the Committee of Public Accounts. | Albert Dolan |
| Name the Roscommon-Galway representatives serving on the Joint Committee on Health. | Martin Daly |

The first question is verbatim human Q1 from
[`user-question-regression.md`](user-question-regression.md). Other variants are
constructed functionality checks, not newly collected human questions or a held-out
generalisation experiment. The illustrative K + R Kildare North question also
returned Aidan Farrelly and Joe Neville in a direct application smoke check.
The illustrative “Are there TDs…” question was refused with the kernel's yes/no
projection limitation; this is a **safe refusal, not a factual answer**.

## Verification

New tests cover varied word/clause order, polite requests, all three pairs,
R + P count/list parity and exact membership binding, short-name ambiguity,
term-scoped party ambiguity, wrong-owner evidence, resource exhaustion, invalid
dates, negation, modal/Boolean/answer-target substitutions, third-role omissions,
conditions consumed inside mentions, legacy-family omission attempts, and the
approved legacy current-Dáil wording. Browser tests use the actual `/ask` form,
not rendered HTML alone, and distinguish answers from refusals.

Commands:

```sh
.venv/bin/python -m pytest -q tests/test_nlq_main_composition.py \
  tests/test_nlq_main_composition_browser.py tests/test_nlq_composition_integration.py \
  tests/test_nlq_composable_party_temporal.py tests/test_nlq_committee_members.py \
  tests/test_nlq_government_membership.py tests/test_nlq_stage_b.py
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
# With the normal planner/Fuseki environment configured:
OIR_RUN_COMPOSITION_LIVE=1 OIR_NLQ_AS_OF_DATE=2026-11-13 \
  .venv/bin/python -m pytest -q -s tests/test_nlq_main_composition_browser.py -k live_main
```

Final focused run: **294 passed, 8 skipped** (the eight opt-in live checks were
run separately: **8 passed, 18 deselected**). Ontology/HermiT validation passed
with **2,586 triples**. Final full repository run: **2,595 passed, 46 skipped**.
Skipped environment/integration checks are not counted as passes.
Disposable logs are
under `/tmp/oireachtasontology/nlq-main-composition/`; no large evaluation captures
or custody package was added. Independent review found no remaining blocking
issue after the routing, cue, projection and legacy-compatibility fixes.

## Remaining limitations

This is bounded natural-language admission, not unrestricted English. Unaccounted
wording/conditions may require rephrasing; explicit dates/historical requests use
existing handlers only where the complete request is already supported. Native
committee counts, yes/no and additional relationships are not available. Missing,
conflicting, ambiguous, empty or over-budget evidence yields no factual answer,
not a fabricated zero or partial list. No upstream completeness or transactional
snapshot is certified. Evidence downloads may expire or be evicted.

Recommended next gate: ordinary human use of the main interface on fresh questions,
with attention to safe refusals and ambiguity. No merge or deployment is part of
this task.
