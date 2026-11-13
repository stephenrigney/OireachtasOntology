# Query Service accepted factual evidence — v1

**13 November 2026 · bounded interoperability contract**

Executable schema: `poc/nlq/query_evidence.py:AcceptedEvidence`. The service's
`PlanOutcome.factual_evidence` is separate from its readable `result` and legacy
`accepted_evidence` payloads. `execute_question` publishes the contract only from
successful, validated execution/evidence projectors. This is not a new query
language, source authority, compiler operation or RDF ownership rule.

## Authority and binding

The envelope contains `version=1`, exact resolved `plan`, `answerQuery`, a digest
of the corresponding result, non-empty typed `facts`, and explicit uncertified
source coverage/unknown freshness. The digest binds a view to the executed
outcome; it is **not** a signature, source-freshness proof or authority for
client-supplied JSON. Only the trusted local executor may issue this envelope.
Schema-valid model output, arbitrary rows and rendered prose cannot issue it.

Consumers validate the version/union and exact plan/query/result binding, retain
the actual successful resolution/answer/page query records and query IDs, and
reject absent/unknown/invalid evidence. A successful service response without
this contract remains inspectable, separately from a research answer. A missing
source record, unsupported operation, semantic-selection refusal, evidence
projection failure and execution failure are distinct observations.

## Typed propositions, not universal rows

| Variant | Semantic payload |
|---|---|
| `entity` | Exact entity IRI/type/label, predicate and accepted selection scope |
| `relationship` | Named participant roles, each exact IRI/type/label, predicate and scope |
| `episode` | Named participants plus separate typed intervals with resource/range identities, recorded start/end, end meaning and temporal role |
| `measure` | Integer value, unit, approved method and distinct input identity set; cardinality is validated |

Every variant retains a compiler-owned exact statement, source witnesses,
qualifications and optional compact display fields (`key → {label,text}`).
Participant roles, predicate, scope and witnesses are authoritative together:
the same participants can have different relationships or temporal meanings.
Scope and source witness dictionaries deliberately retain operation-specific
semantics; they are not an invitation for a consumer to interpret a new family.
Adding another service projector requires its own focused semantic tests.

### Default handoff, conditional semantic coverage

Executors may issue typed `PlanOutcome.validated_facts` at their existing semantic
validation step, before readable rendering. The shared service boundary
`query_evidence.finalize_evidence` binds these propositions to the exact plan,
answer query and result digest by default. No capability registry or consumer-side
row interpretation participates. Existing direct envelopes and reviewed legacy
payload projections remain compatible. `factual_evidence_status` distinguishes
`available`, `unavailable`, `invalid` and `not_applicable`; successful retrieval
remains successful even if a handoff is unavailable or fails validation.

Semantic coverage is **conditional**, not automatic for every successful query.
An executor must establish the propositions it issues; relationships, independent
intervals, measures and source qualifications still require service-owned meaning.
`selection_outcome`, when supplied by an executor, distinguishes a validated
matching selection from a valid empty selection (`matches` / `no_matches`). A
consumer must not infer a negative finding from absent accepted evidence, an
unknown selection, or an arbitrary scalar/boolean result. Selection outcomes are
execution metadata, not a replacement for accepted Level 1/2 propositions.

Intervals preserve source date/dateTime precision and source lexical values in
witnesses. Resource/range identities are nullable where the authoritative
projection does not expose them: legacy lifecycle observations establish Bill
identity plus activity type/date, not individual activity IRIs. Never substitute
the Bill IRI for an unprojected activity resource. `recorded`, `not_recorded` and
`open_ended` ends are distinguishable.
An unknown end in party history does not prove current membership. A validated
open end in current party selection follows that operation's existing policy.
Separate episodes are never collapsed into continuous tenure or absence in gaps.
Parliamentary service dates do not substitute for missing party dates.

Current implemented projections:

- Party history: exact Member, enduring affiliation and separate source episodes,
  including source party/containing membership/term/range/owner graph identities.
- Current Dáil named-party Member selection and approved identity counts: exact
  independent party/parliamentary intervals both containing the reporting date.
- Constituency representation: term-specific relationships; current-point
  selection additionally retains its accepted source interval/reporting date.
- Sponsorship: exact Member/Bill/participation classifications and roles; approved
  distinct-Bill cardinality over the accepted enumeration.
- Bill lifecycle: exact recorded status and individual dated activities, not
  certified final outcomes or necessarily latest developments.
- Independent holdout, House-term calendar selection: exact House-owned dated
  entity selection, preserving date/full-month selector and non-sitting meaning.
- Current committee membership: exact Member/Committee relationships, separate
  membership, committee-owner and House-term intervals containing the reporting
  date, raw owner/member witnesses and source graphs; not a complete roster,
  chairmanship or attendance finding.
- Independent additional slice, full Dáil chronology: recorded House-owned term
  dates with exact term identities and source witnesses. Unexposed period
  identities remain null; missing ends do not become recorded finishes. Neither
  sitting dates nor completeness of parliamentary history is inferred.

This is not universal compiler-family coverage. Other successful operations may
still lack a projector. No consumer may fill that gap from their result tables.

## Research consumption and authorship

`research_evidence.accept_query_evidence` performs only generic contract/binding
validation and links actual reads. `research_assertions.facts_from` wraps each
accepted proposition unchanged as Level 1, or the approved measure as Level 2.
It does not decide a query family's factual meaning. Legacy assertion handling
exists solely for retained sessions; new service projections belong in the
service, not in a Research Assistant adapter or capability catalogue.

The LLM still chooses subsidiary investigations, section structure, selected
facts, narrative and table columns. A `records` table selects exact compiler field
keys; it cannot author headings/cells, join records or compute values. Missing
keys, incompatible headings, duplicate columns and non-established assertions
are rejected. Full propositions/qualifications remain inspectable per row even
when only concise fields appear in the table. Existing specialised Bill and
representation views remain replay-compatible, not prerequisites for new
capabilities. No new capability-specific research presentation is required.

The LLM cannot author Level 1/2 sentences. Free explanatory synthesis retains
provisional Level 3 authority with referenced facts, qualitative rationale,
assumptions/conflicts/limitations; Level 4 remains segregated. Neither a citation,
table nor a model's requirement assessment certifies arbitrary prose or the full
original question. Supporting retrieval, requirement disposition and factual
authority remain separate. Markdown export retains the draft status, meaningful
qualifications, assertion registry, exact evidence, plans and all query reads.
