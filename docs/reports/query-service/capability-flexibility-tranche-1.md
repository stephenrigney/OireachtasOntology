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

The local Fuseki endpoint was available. Requests ran through FastAPI `/ask`
and the real read-only Fuseki client/compiler/executor at
`OIR_NLQ_AS_OF_DATE=2026-11-09`. The environment had no `NLQ_LLM_API_KEY`, so
the semantic draft was supplied by the fixed test generator: this exercises
the actual validated-plan `/ask` execution route, but **not live LLM
interpretation or draft generation**. Draft interpretation/admission and
negative cases were exercised separately through the real validators.

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
validation failure with no answer query. The returned evidence displays exact
Member, membership, episode, party, affiliation, and term identities plus
separate interval evidence. These are **positive local-record selections**,
not a certification that the local RDF is a complete real-world roster.

For a neighboring numbered-term case, an independent term-33 SPARQL selection
and inclusive interval-overlap evaluator returned 35 Fine Gael Member
identities. The live `/ask` result for “Who were the Fine Gael TDs in the 33rd
Dáil?” matched the exact 35-identity set. Existing Group A factual review also
records exact RDF identity/interval checks for the 25th Seanad Labour result
(five identities) and current Fianna Fáil Seanad result (19 identities).
This run additionally confirmed HTTP 200 / answer for current Seanad Fine Gael
selection; no new exact independent comparison for that party was claimed.

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
- Actual LLM interpretation was not tested because no key was configured;
  fixed validated drafts isolated compilation and live execution. The question
  admission behavior is covered by validator tests and explicit `/ask`
  nonanswer, but real-model phrasing remains outside this evidence.

## Verification

- Focused regression: `.venv/bin/python -m pytest tests/test_nlq_seanad_party_periods.py tests/test_nlq_composable_party_temporal.py tests/test_nlq_composable_member_relationship_composition.py tests/test_nlq_composable_current_house_membership.py -q` — **184 passed**.
- Full suite: `.venv/bin/python -m pytest tests -q` — **2,351 passed, 26 skipped, 23 subtests passed**. (The first attempt hit the 120-second command timeout; a rerun with a longer timeout completed successfully.)
- Ontology validation: `.venv/bin/python tests/validate.py` — passed; 2,586 triples validated.
- `git diff --check` — passed.
- Representative live `/ask` checks and independent read-only SPARQL comparisons: completed as described above.

No commit or PR has been created yet. Tranche exit evidence is now available for
the approved bounded correction; the work is ready for Human Gate 1. No merge
or follow-on tranche is proposed here.
