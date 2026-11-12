# Frozen composition experiment protocol

Authority: [readiness §§3, 5–6](../nlq-bounded-composition-experiment-readiness.md)
and the human approvals recorded in this task. Experimental only; no production
admission, semantic contract, RDF owner, IRI or graph change is authorised.
`asOf=2026-11-11`, inclusive calendar-day comparison, not machine-clock “now”.

## Inputs and replay

`development/inputs.json` is a **schema-neutral test specification**, not a new
compiler IR. Preserve its original intent when adapting it to the candidate's
representation. Feed independently mutated candidates to semantic validation;
do not just test what the candidate's own constructors can produce. Do not
substitute weaker English questions or score refusal as supported answering.
The experiment does not test general English admission or AI repair.
In these test inputs, singular `house: "Dail"` means exactly one House variant;
`houses: ["Dail", "Seanad"]` means both permitted variants. Adapt the notation
without widening the former or silently narrowing the latter.

The immutable test reference is the captured typed bindings and resource audit
in `development/captures/`, with a lossless scoped quad-set reconstruction in
`development/evidence.nq`. This is an offline read-only evidence replay, **not a
Fuseki reload** or a whole-store export. Source graph is part of each fact.
Preserve original datatype/language/lexical values. The query and page hashes,
timestamps, offsets and short-page completion certificates are recorded beside
each capture. Replay recorded query outcomes or derive candidate-specific SELECT
bindings over this scoped quad set; the harness must prove that every required
candidate/evidence lookup is covered, rather than interpret out-of-scope absence
as false. Record the replay mapping, SELECT text, typed responses and complete
request ledger. An uncovered query is an evidence nonanswer, not an empty result.
Live reruns are separate evidence: changed bytes require a new named baseline,
never quietly updating this oracle. Changes to frozen inputs, oracles, controls
or scored expectations require explicit human approval and a separately identified
experiment; they cannot be used to rescue the frozen candidate's acceptance.

`oracle.json` lists all five representation candidates and fifteen committee
episodes, their original witness resources, endpoint types/values, independent
current flags, qualifying alternatives and distinct identity projection. House
periods, owner ranges and source graphs remain separate evidence roles. The raw
resource audits preserve additional asserted types and alternate/historical
facts; `oracle.json` is not a replacement for them. No row count, display-name
join, IRI substring inference, inferred superclass or external identity lookup
may replace exact typed RDF links. Party episodes must link to their exact
Member-linked containing parliamentary membership and its own party/HouseTerm.
R+P additionally shares that exact membership/term with R. K+P joins only Member;
either current Dáil or Seanad party paths qualify without committee-term equality.
K does not invent a parliamentary-containment predicate on CommitteeMembership.

## Control interpretation

`development/controls.json` freezes independently specified mutations. Each test
starts afresh from the named baseline; mutations are **not cumulative**.

* `candidateSemanticPatches`: RFC 6902 operations on the named original semantic
  input. Keep the original request fixed. The candidate must be rejected for
  dropping, altering or adding material requirements, even when well typed.
* `removeQuads` / `addQuads`: exact N-Quads statements, applied only to a fresh
  in-memory copy of the frozen evidence. Every removal must exist. Additions are
  explicitly synthetic adversarial data, not source observations, publication,
  changed protected fixtures or new identifier/ownership policy. Do not load
  these variants into Fuseki. Adapt their consequences to typed SELECT bindings
  without prefiltering away malformed candidates.
* `rowTransform`: response-row transformations after the equivalent retrieval.
  Duplicates/order changes preserve the canonical witness **set**, not multiplicity;
  retain distinct episodes. Transform only requests whose transformed raw rows
  remain <=100, with complete enumeration and the same whole-plan bounds. Otherwise
  the over-budget expectation takes precedence. Missing optional display fields
  cannot silently remove identities; an existing stricter family nonanswer is
  allowed, invented display facts are not.
  Retain the pre/post-transform raw count for each request, resulting join count,
  and which disposition applied (within-bounds invariance or over-budget nonanswer).
* `retrievalOverride`: mock transport/ledger conditions, not RDF edits. Incomplete,
  malformed, timed-out, exhausted or oversized required evidence must not yield
  partial lists, partial totals or “zero”. `selectRequests` includes resolution,
  lookahead/completion pages and both House variants, not merely answer queries.
* `resolverOverride`: introduce a second distinct, equally current matching
  resource in the mock resolver response, retaining its separate identity and
  required typed owner/date evidence. The exact additional owner quads and IRI
  are frozen in the control. Never merge or choose by row order.

`budget-boundary` controls also exercise the budget counter directly with the
frozen equivalent witness data: inclusive ceilings are allowed, not off-by-one
refusals. Padding means exact duplicate typed rows/tuples, not invented identities.
Any completion request is already charged in the supplied total. This unit-level
counter check is not a claim that a particular end-to-end plan naturally makes
eight requests; retain actual ledgers for all candidate executions separately.
Retain boundary-test raw row counts before deduplication, padding counts and
intermediate witness counts so the inclusive boundary cannot be asserted by prose.

Ended/future intervals are valid evidence excluding that witness, not automatically
malformed evidence. A supported nonempty reduced selection must be exact; an empty
selection is an evidence nonanswer in this experiment. Missing/conflicting required
evidence fails the whole selection before filtering or Member deduplication.
The naturally ended committee episodes remain excluded despite current party
evidence. Distinct party episodes are not prohibited by an invented universal
one-party-at-a-time rule. The synthetic either-House test makes the selected
Member's **only Member-linked** qualifying party path Seanad-scoped; it must still
qualify with separate committee and party terms. Multi-episode and reordered rows
must retain row-local sources, ranges, terms and all supporting alternatives.
Canonicalising exactly equivalent, already validated evidence is permitted for
idempotence. It cannot erase conflicting evidence, evade the raw request-row limit
(which counts duplicates), or discard distinct relationship witnesses to fit a join
cap. Record actual retained intermediate witness-tuple counts before projection;
Member deduplication is not a substitute for validating those witnesses.

## Frozen pass/fail rubric (readiness §6)

All gates are conjunctive; no averaging, retrospective budget relaxation, control
deletion or “safety refusal” credit on verified supported positives.

1. **Exact answers/evidence:** both disclosed positives and every frozen withheld
   positive return 100% correct Member IRIs, measure/unit, date scope and all scored
   relationship, containment, owner, range, original endpoint and graph assertions.
   R+P count equals distinct qualifying Member list cardinality internally. K+P
   remains list-only; common projection code does not authorise committee counts.
   Qualify the answer as identities recorded in this evidence, never complete
   real-world coverage. Any wrong factual/provenance assertion fails. Supported
   positive nonanswer fails capability, not safety.
2. **Intent fidelity:** zero factual answers for the semantic mutation controls.
   No dropped party/constituency/committee/current/date/exact-membership/count
   requirement; no added HouseTerm equality, Dáil-only K+P restriction, attendance,
   negation or extra projection. Score semantic admission separately from valid-plan
   evidence evaluation and resolution ambiguity.
3. **Evidence safety:** every malformed/conflicting/missing/incomplete/budget control
   returns a nonanswer with no factual partial answer. Ambiguity never chooses an
   arbitrary identity. Ended paths are excluded; current party evidence does not
   rescue an ended K path, nor current R an ended P. No successful zero/empty list
   or claim of real-world absence. Conflicts are checked at resource level before
   filtering/deduplication, including nonqualifying candidates.
4. **Determinism:** exact identity/count and canonical witness set invariant under
   equivalent within-bounds row ordering/duplicates. Distinct supporting episodes
   remain distinct witnesses; each keeps its own term, graph and endpoint metadata.
   The candidate's structured output ordering and rendered answer must also be
   identical, excluding only declared volatile request timestamps/durations. Sorting
   output inside the evaluator must not hide unstable candidate ordering.
5. **Whole-plan ceilings:** only the three reusable R/P/K primitive adapters overall,
   <=2 relationship selections per plan, P <=2 explicit House
   variants, <=8 SELECT HTTP requests **including all resolution and pagination**,
   <=100 retained raw rows in each request, <=20-second request timeout and <=100
   binding-join witness tuples. Reject oversized intermediate results; never silently
   deduplicate/cap to make them fit. Preserve existing stricter family failures,
   query safety (32,000 characters, SELECT limit 100, offset <=10,000, no Update,
   SERVICE, dataset clauses, subqueries, property paths or variable predicates).
   Do not increase an existing shorter configured timeout to 20. A full page needs
   a charged completion request unless another independently sufficient completion
   certificate exists. Diagnostic custodian acquisition requests are NOT an experiment
   plan execution or proof that future compiled plans fit eight requests. A frozen
   positive exceeding any ceiling fails budget fit; do not relax ceilings.
6. **Withheld zero-change reuse:** freeze the candidate commit SHA, clean tracked/
   untracked status, dependencies, capability configuration, adapter/replay mapping
   and evaluation harness hashes **before release of exact K+R input/oracle**. K+R
   must then execute using those frozen primitives, binding/validation, lowering and
   evidence projection, with no topology-specific schema union, validator, compiler,
   executor branch, projection or assembler. Only test data and previously approved
   capability configuration may be supplied; record every difference. Any code fix,
   even generic, ends strict zero-change reuse credit for that run. No party condition
   or cross-path term equality belongs in K+R. Configuration containing new
   topology-specific query templates, validators or projection assemblers counts
   as changed logic, not innocent input data. A prebuilt K+R special case already
   present in the frozen commit also fails the mechanism criterion: zero edits
   after release alone do not prove generic reuse. Nonanswer on a verified positive fails.
7. **Regression:** applicable existing production refusal, typed response, query
   safety, pagination, representation, party, committee, composition, interpretation
   and query-explainer tests remain passing without weakening. Run
   `.venv/bin/python tests/validate.py` and `.venv/bin/python -m pytest tests` on the
   candidate; any infrastructure/unavailable test is recorded as unverified, not
   passed. Preserve all existing source/golden fixtures, SHACL and ontology checks.

Retain the original inputs, mutated candidates, validators' dispositions, SELECTs,
typed responses, request ledger, intermediate witnesses, joins, projection and
assertion-level scores. Charge representation, adapters, schema alignment,
validation, lowering, evidence/projection and tests under the same implementation
cost/reuse rubric; no topology-specific work hidden in adapters or the harness.

## Custody and release

The public repository retains development data, protocol, private-package hash and
custody record only. The private package contains the exact K+R parameters, complete
candidate captures, oracle and adversarial controls. It must not be committed in
plaintext or made available to the implementation agent. The K+R topology and the
readiness report's Galway East/Albert Dolan primitive exemplar were already disclosed;
they are **not unseen**. This is procedural withholding of exact test artifacts,
not confidentiality against this workstation's owner or statistical independence.

1. User transfers the identified tar package to durable user-held storage outside
   the implementation agent's accessible environment; checks its published SHA-256,
   extracts it and verifies its internal manifest. Retain the complete package.
2. User confirms custody, exact package hash, removal of all accessible withheld
   plaintext/package copies and exclusion of custodian/subagent transcripts from
   implementation context. Disposable private paths are explicitly listed in the
   handoff. Shell/session tool logs can contain private query text/results; filesystem
   deletion alone is not proof those logs are inaccessible. If transcript exclusion
   cannot be established, report a custody blocker, not a blind-probe pass.
3. Only after that confirmation, finalise/commit non-secret freeze artifacts.
   Launch implementation in a fresh development-only context. The custodian's
   verification tooling is evidence analysis, not candidate implementation.
4. User records candidate SHA and frozen harness/config hashes, verifies no later
   code changes, then releases the exact private package to the evaluator. Do not
   expose withheld answers to aid development before freeze. Record release time,
   recipient/context and package hash. The evaluator checks internal hashes before
   scoring. Loss/alteration/premature disclosure invalidates strict withheld credit;
   do not secretly regenerate cases or retune expectations.

The non-secret report remains **pending custody**, not ready for implementation,
until the user's confirmation is durably recorded.
