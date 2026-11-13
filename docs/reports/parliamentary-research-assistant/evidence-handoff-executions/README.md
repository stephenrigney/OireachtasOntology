# Evidence handoff and plain-language execution archive

These are retained observations, not reference answers or human acceptance.
The accompanying [report](../evidence-handoff-and-plain-language.md) distinguishes
technical integration from the pending product decision.

## Actual configured-model / read-only Fuseki runs

Root `*.json` archives retain genuine proposals, model calls, accepted facts,
queries, results and state; matching Markdown retains the generated report and
evidence. `instructions.json` records the model's supplied discovery/instructions.
These early vertical-slice runs preceded the last presentation/selection-status
polish, and are not substituted for final browser checks:

- `j-committee-current`: exact mandatory current-membership question.
- `k-committee-history`: exact unsupported history question; no accepted findings.
- `l-chronology-independent`: independently chosen, previously unprojected full
  Dáil chronology.
- `m-partial-committee`: current members plus historical changes since 2020.
- `a-party-history`: Donnelly's parties and dates.
- `b-r1`, `b-r1-revision`: Malcolm Byrne Bills, progress and an actual editorial
  revision without additional reads; facts/tables remain identical.

Actual browser observations:

- `browser-live/`: initial current report/source/query/export/mobile checks;
  history legitimately retrieved narrower current supporting facts. A harness
  assumption that unsupported history must have zero supporting facts stopped
  the run; its genuine state/output is retained, not relabelled a product failure.
- `browser-final/`: fresh final current report, assertion/source/query inspection,
  qualified export, 390px containment and no JavaScript errors. The following
  history case stopped on a harness assertion expecting SPARQL in its first,
  refused/no-read operation even though a different supporting operation read
  data. Exact archives and report screenshots remain retained.
- `browser-completion/`: fresh history, multi-domain current-membership/speech
  brief, and independent ordinary-language chronology question. History and
  partial-report/source/query/export/mobile checks passed. The chronology
  paraphrase was refused by existing query selection; its untouched genuine
  output is retained as a language-coverage limitation, not an evidence-handoff
  failure. The harness compares each inspected operation's exact reads, including
  zero-read refusals.
- `browser-chronology-fixture/`: a separate fresh browser execution of the
  ordinary-language chronology formulation already frozen in the root live
  cases, “When did each Dáil start and finish?” All 34 accepted findings pass the
  same report/source/query/export/mobile checks. The failed paraphrase above is
  not overwritten or relabelled successful.

These harness corrections did not change the questions or weaken factual gates.
Every browser case checks plan visibility before dispatch and retains genuine
model output, rather than serving a saved report to the browser.

## Synthetic / replayed controls — not genuine-model evidence

- `browser-controls-complete/`: injected model and real compiler
  fixtures, including an intentionally removed handoff and injected transport
  exception. Technical disclosures retain the exact failure while ordinary
  language distinguishes records found from a failed search. The latest rerun
  also exercises a real compiler's dated zero selection, ambiguous identity and a
  completed result without a service assessment that records matched. This last
  subtype says “Search completed — result not included”, not “Records found”.
- `browser-regressions-final/`: existing v0.6 injected-model/exact-compiler-replay suite:
  responsive opening, revisions, evidence navigation/focus, failure retention,
  retry/pause and source inspection. Its summary explicitly disclaims human
  acceptance.

Genuine early runs remain labelled by their directory; they are not pooled into
an apparent success rate. Superseded duplicate synthetic screenshots are omitted.
Root reports may contain earlier, more repetitive
qualifications; final presentation evidence is in the final browser directories.

## Deterministic-suite environment diagnosis

`configured-office-current.txt`, `configured-office-9148002.txt` and
`hermetic-office-current.txt` retain the isolated Finance-only refusal test.
It fails both on current code and with the exact `9148002` compiler loaded in
memory, because configured model discovery performs a registry read the test
expects not to occur. It passes with `NLQ_LLM_API_KEY=''`. No branch, source file,
test assertion or query rule was changed for this diagnosis. The final broad
deterministic run uses that empty-key setting; live observations above retain the
actual configured model and Fuseki separately.
