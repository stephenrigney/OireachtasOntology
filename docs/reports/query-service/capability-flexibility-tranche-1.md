# Query Service — Tranche 1: Capability Flexibility

Status: **verification complete for the bounded explicit-current Dáil party
capability**. No ontology, mapping, source, or golden fixture changes. No
Tranche 2 work was started.

## Restriction investigated and classification

The party-only Dáil Member plan and draft validators required a numbered
DáilTerm, while the same party-only temporal graph supported current Seanad
selection. This was an **implementation/admission restriction**, not an
established semantic or temporal-evidence requirement for an *explicitly
current* Dáil request. The existing executor already resolved `currentTerm`
against House-owned dates and independently checked both the exact
DailMembership interval and PartyMembership episode interval at the configured
`asOf` date.

The unqualified current-default asymmetry remains: `present_seanad_party_default`
is a narrowly scoped, explicitly tested policy for unqualified present-tense
Senator questions; equivalent unqualified Dáil party questions are rejected.
Group A records this Seanad policy but establishes no semantic/RDF reason why
the Houses must have different defaults. Thus the Seanad default is an existing
policy, but the *asymmetry's rationale is unresolved*. This tranche does not
extend or remove either default.

## Reusable corrections and safeguard found

- Party-only Dáil list/count plans now admit either one exact numbered term or
  an explicit `currentTerm` request. The current term remains House-date
  resolved and both separate membership/party date intervals must contain
  `asOf`; identity joining and inclusive overlap requirements remain intact.
- Current-term count validation now uses the same distinct-Member projection
  as the list selection. It does not count party resources, seats, or episodes.
- The initial negative-control run demonstrated two admission holes: an
  additional calendar date and an additional committee condition could be
  silently ignored by the proposed current-Dáil shape. The draft validator was
  tightened narrowly for this shape: an extra calendar date or relationship,
  identity, or temporal condition is refused. Regression tests cover those
  cases, multiple parties, and unqualified present tense. No weakened
  validation was introduced.
- One changed-file entry documents explicit-current wording and the retained
  interval checks. No universal composition engine or capability-model
  redesign was needed.

Before: party-only Dáil lists/counts accepted numbered terms only. After:
numbered-term and explicit-current Dáil lists/counts are supported; no
unqualified Dáil default was added. Seanad default and numbered-term behavior
remain as previously accepted.

## Factual and end-to-end evidence

The local Fuseki endpoint was available. The initial tranche pass ran through
FastAPI `/ask` and the real read-only Fuseki client/compiler/executor at
`OIR_NLQ_AS_OF_DATE=2026-11-09`, using fixed drafts because the process
environment and `.env` did not expose an LLM key at that time. This execution-
only limitation is superseded by the genuine AI `/ask` verification below,
after `.env.local` was loaded into the process environment.

An independent hand-written SPARQL selection, separate from the application
compiler, first inspected the complete typed Dáil chronology and resolved one
current term at the reference date:
`https://data.oireachtas.ie/ie/oireachtas/house/dail/34`. Its membership query
joined exact Member → DailMembership → DáilTerm and Member → PartyMembership →
same DailMembership → ParliamentaryParty → PoliticalAffiliationIdentity paths,
requiring party active-during-term evidence. Independent date evaluation
required both membership and party intervals to contain 2026-11-09 (inclusive;
absent ends are open). The exact identity sets matched the live `/ask` result:

| `/ask` request | Independent active Member IRIs | `/ask` count result |
|---|---:|---:|
| Who are the Fine Gael Deputies in the current Dáil? | 38 | 38 |
| Who are the Fianna Fáil Deputies in the current Dáil? | 48 | 48 |

Both count answers were the distinct RDF Member identity count from the same
verified set. Live paraphrases “Which Fine Gael TDs are currently serving?” and
“Which Fianna Fáil Deputies are currently serving?” also returned answers.
The exact target form “Who are the current Fianna Fáil Deputies?” returned an
answer; the unqualified “Who are the Fianna Fáil Deputies?” was a safe
unsupported response with no answer query. The returned evidence displays exact
Member, membership, episode, party, affiliation, and term identities plus
separate interval evidence. These are **positive local-record selections**,
not a certification that the local RDF is a complete real-world roster.

For a neighboring numbered-term case, an independent term-33 SPARQL selection
and inclusive interval-overlap evaluator returned 35 Fine Gael Member
identities. The live `/ask` result for “Who were the Fine Gael TDs in the 33rd
Dáil?” matched the exact 35-identity set. Existing Group A factual review also
records exact RDF identity/interval checks for the 25th Seanad Labour result
(five identities) and current Fianna Fáil Seanad result (19 identities).
The genuine AI follow-up independently compared current Seanad Fine Gael
selection (16 identities) as well as the 25th Seanad Labour result.

The reusable synthetic RDF regression includes current Fine Gael and Fianna
Fáil occurrences, ended membership, ended party affiliation, a historical
numbered Dáil path, and a second qualifying Fine Gael party occurrence for one
Member. Independent fixture SPARQL and application selection agree; the list
and count deduplicate the repeated Member identity. Added current-Dáil negative
controls refuse a second date, committee condition, multiple party request,
and unqualified current default. A current-list paraphrase is covered. Existing
Seanad and numbered-Dáil behavior remains covered by prior/current regressions.

## Remaining restrictions and architecture findings

- Current Dáil party selection requires explicit current/as-of wording; no
  inferred present-tense default is supported. Its policy relationship to the
  existing Seanad-only default remains for human consideration.
- Numbered historical Dáil selection preserves inclusive overlap semantics;
  it does not imply present service. Current requests preserve both independent
  as-of checks. Extra dates, parties, or relationship filters are refused.
- The fix reused the existing semantic graph, temporal evaluator, party gate,
  and answer projection. Verification does **not** demonstrate a structural
  limitation requiring capability-model consolidation. It does show the
  existing validator can silently discard a filter unless the exact question
  shape is checked; this tranche added only the narrow guards needed for the
  corrected shape.
- The initial tranche pass used fixed validated drafts; the genuine AI `/ask`
  cases below close that interpretation gap for the bounded request sample. No
  broad model reliability claim is made.

## Verification

- Focused regression: `.venv/bin/python -m pytest tests/test_nlq_seanad_party_periods.py tests/test_nlq_composable_party_temporal.py tests/test_nlq_composable_member_relationship_composition.py tests/test_nlq_composable_current_house_membership.py -q` — **184 passed**.
- Full suite: `.venv/bin/python -m pytest tests -q` — **2,351 passed, 26 skipped, 23 subtests passed**. (The first attempt hit the 120-second command timeout; a rerun with a longer timeout completed successfully.)
- Ontology validation: `.venv/bin/python tests/validate.py` — passed; 2,586 triples validated.
- `git diff --check` — passed.
- Representative live `/ask` checks and independent read-only SPARQL comparisons: completed as described above.

The implementation was committed as `aa8268f` and opened as draft PR #30 to
`master`. It remains unmerged. The live AI interpretation results for PR #30
are recorded below; no follow-on tranche is proposed here.

## Live AI interpretation follow-up (PR #30)

The `.env.local` configuration was readable through its symlink and contained
an LLM credential. The secret was loaded into the test process only; its value
was not printed, recorded, or added to repository files. Since application
configuration loads `.env` rather than `.env.local` itself, the test process
loaded `.env.local` into its environment before starting the normal FastAPI
application. The ordinary semantic planner factory was used for every request:
no fixed drafts or interpretation bypasses were used. Fuseki was also live.
Reference date remained `2026-11-09` to match the independently established
RDF evidence above.

For the eight supported requests below, the AI produced a supported
`member_relationship_composition` draft, selected the shown temporal selector
and answer kind, local validation passed, execution returned HTTP 200 / `answer`,
and the answer projection had the expected shape. Exact Member identity sets
from live `/ask` were compared to separately executed read-only SPARQL plus
inclusive interval evaluation:

| Genuine AI `/ask` question | Selector / projection | Independent RDF | Result | Stages |
|---|---|---:|---:|---|
| Who are the current Fianna Fáil Deputies? | currentTerm / Member list | 48 | 48, exact identity-set match | interpretation, selection, validation, execution, projection passed |
| How many Fianna Fáil Deputies are in the current Dáil? | currentTerm / distinct Member count | 48 | 48 | all passed |
| Which Fine Gael TDs are currently serving? | currentTerm / Member list | 38 | 38, exact identity-set match | all passed |
| How many Fine Gael Deputies are in the current Dáil? | currentTerm / distinct Member count | 38 | 38 | all passed |
| Who were the Fine Gael TDs in the 33rd Dáil? | termNumber 33 / Member list | 35 | 35, exact identity-set match | all passed |
| Who are the Fine Gael Senators in the current Seanad? | currentTerm / Member list | 16 | 16, exact identity-set match | all passed |
| Who were the Labour Senators in the 25th Seanad? | termNumber 25 / Member list | 5 | 5, exact identity-set match | all passed |
| Who are the Fine Gael Senators? | existing Seanad current default / Member list | 16 | 16, exact identity-set match | all passed |

Counts were checked against the independently selected sets and list/count
projection uses distinct Member RDF identity, not episode or party cardinality.
The existing Seanad unqualified default worked in the genuine AI route. The
asymmetry remains: no unqualified Dáil default was inferred.

Three genuine AI negative controls returned `unsupported_capability` with a
valid unsupported proposal (`supported=false`, no family/answer), no result
table, and no answer execution:

| Negative control | Interpretation / capability selection | Validation | Execution / projection |
|---|---|---|---|
| Current Dáil party plus `on 2026-01-01` | Correctly interpreted as extra date; declined | Unsupported response accepted; no answer plan | Not run / none |
| Current Dáil party plus committee condition | Correctly interpreted as extra relationship; declined | Unsupported response accepted; no answer plan | Not run / none |
| Unqualified “Who are the Fianna Fáil Deputies?” | Did not invent a current Dáil default; declined | Unsupported response accepted; no answer plan | Not run / none |

No interpretation, selection, validation, execution, or projection failure was
observed in this bounded live set. The real planner and live dataset were
verified. This was a finite sample, not a reliability estimate. No code change
was required for this follow-up; unrelated model discovery failures were not
observed and are not claimed fixed. PR #30 carries the prior verified code and
this report update.
