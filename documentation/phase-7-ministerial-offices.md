# Phase 7 ministerial office and tenure vertical slice — approved design

## Status and scope

**Design approved; Tranches 1 and 2 are implemented; Tranches 3–6 have not
started.** This document records the first Phase 7 vertical slice. Tranche 1
introduced its ontology vocabulary and office/unit registry publication path;
Tranche 2 added source-observation review and occurrence correspondence. The
small reviewed bootstrap is recorded in
`registries/ministerial-office-registry.json` and
`reconciliation/office-decisions.json`. Member holdings, Cabinet membership,
and Bill reconciliation remain unimplemented; the active Member mapping and
published Member/Bill RDF behavior are not changed by these tranches. The
broader Phase 7 debates, votes and questions slices remain separate.

The existing Member transformer currently interprets every
`membership.offices[]` observation as a `MinisterOfStateMembership` and creates
an occurrence-specific `MinisterOfStateRole`. That interpretation is not valid
for the generic source collection; it must be migrated, not treated as the new
contract. See `mappings/member_mapping.csv:72-78`,
`src/oireachtas_etl/transforms/members.py:_office` and
`documentation/etl-plan.md` (Phase 7). The example has null
`officeName.uri` values and an observation naming two departments
(`data/api_examples/member.json`); an office label or external identifier is
not a sufficient local identity. Bills already preserve unresolved sponsor
role text on their Participation (`src/oireachtas_etl/transforms/bills.py`,
`documentation/phase-4-legislative-lifecycle.md`).

## 1. Enduring identities and RDF vocabulary

Introduce the following terms in the `members:` namespace. These are proposed
ontology changes for implementation, **not** declarations already present in
the executable ontology.

| Term | Contract |
|---|---|
| `NamedOffice` | `owl:Class`: a particular enduring institutional office, independent of its holder, label, associated Department or responsibilities. Similar names/functions do not prove continuity; their change does not by itself prove discontinuity. |
| `AdministrativeUnit` | `owl:Class`, subclass of `org:Organization`: a distinct, locally determined enduring institutional unit. ISAD historical units/events are evidence, not automatic local identities. |
| `OfficeHolding` | `owl:Class`, subclass of `org:Membership`: a dated relationship between a person and one particular `NamedOffice`, separate from `CabinetMembership`. |
| `OfficeType` | `owl:Class`, subclass of `skos:Concept`: the controlled category of a particular office. |
| `TaoiseachOfficeType`, `TanaisteOfficeType`, `MinisterOfficeType`, `MinisterOfStateOfficeType` | Distinct individual IRIs, each typed `OfficeType`. Add `CeannComhairleOfficeType`, `CathaoirleachOfficeType` and `AttorneyGeneralOfficeType` for reviewed identities needing them. |
| `hasRoleType` | `owl:ObjectProperty`, domain `NamedOffice`, range `OfficeType`; the object is an **office-type concept**, not an OWL role class. Label/comment it “has office type” and explain the naming distinction. |
| `heldOffice` | Object property `OfficeHolding` → `NamedOffice`; exactly one target per published holding, enforced by validation. |
| `officeHolder` / `hasOfficeHolding` | Inverse object properties `OfficeHolding` → `foaf:Person` and `foaf:Person` → `OfficeHolding`. Member ETL explicitly emits both directions and independent acceptance checks both. Do not restrict all future office holders to Members merely because this source is Members. |
| `headsAdministrativeUnit` | Object property `NamedOffice` → `AdministrativeUnit` for evidenced departmental Minister headship. |
| `assignedToAdministrativeUnit` | Object property `NamedOffice` → `AdministrativeUnit` for evidenced Minister-of-State assignment; **not** a subproperty of headship. |
| `predecessorOffice` / `successorOffice` | Inverse object properties `NamedOffice` → `NamedOffice`; reviewed, positively evidenced assertions only, without transitivity or chronology-based inference. |
| `reconciledSponsorOffice` / `reconciledSponsorHolding` | Object properties from `eli-dl:Participation` to `NamedOffice` / `OfficeHolding` respectively, owned by Bill *local reconciliation*, not the Bill source graph. |
| `supportedByOfficeHolding` | Object property `CabinetMembership` → qualifying `OfficeHolding`; support need not span the entire merged Cabinet period individually. |

Keep the existing `TaoiseachRole`, `TanaisteRole`, `MinisterRole` and
`MinisterOfStateRole` as **classes only**. Do not use OWL class/individual
punning; do not type a `NamedOffice` as one of these role classes. A versioned,
deterministic ETL table maps the four corresponding `OfficeType` concepts to
Cabinet qualification: the first three qualify, `MinisterOfStateOfficeType`
does not. There is no RDF concept-to-role-class link added for symmetry. The
existing role classes retain their separate generic-role meaning
(`ontology/members.owl.ttl`, Cabinet and ministerial role definitions).
Uncategorized historical offices must not be assigned a Cabinet category by
similarity. Validate category membership against the registered concepts.

Retain `CabinetMembership`, `CabinetMember`, `hasCabinetRole`,
`isCabinetMembershipOf`, `hasMembersMembership`, `DateRange`, `StartDate`,
`EndDate` and `hasMembershipDateRange`. A generated Cabinet membership has one
role individual typed `CabinetMember`, linked with `hasCabinetRole` and
`org:heldBy` to its person; do not type that same individual as multiple
possibly disjoint role subclasses when holdings overlap. Query the precise
offices/categories through `supportedByOfficeHolding` → `heldOffice` →
`hasRoleType`. The Government target is the **enduring constitutional**
`<https://data.oireachtas.ie/government>`, not a numbered administration
(`ontology/agents.owl.ttl`, Government individual;
`ontology/members.owl.ttl`, CabinetMembership axioms). Temporal coverage and
absence of duplicate Government memberships need closed-world validation:
the existing OWL restrictions alone do not establish those conditions.

Retire active `MinisterOfStateMembership`, `hasMinisterOfStateRole` and
`officeNameUri` use; deprecate their declarations rather than repurpose them.
Remove the `GovernmentExecutive` OWL union restriction that requires
`MinisterOfStateMembership`; retain its organizational class/disjointness and
explain the wider executive tier in its comment. Validate any asserted
executive membership against holdings if populated. Correct the
`MinisterOfStateRole` comment: disjoint role classes prohibit *the same role
individual* having both types, not a person concurrently holding distinct
roles. Preserve the existing Cabinet/Oireachtas-membership restrictions
(`ontology/members.owl.ttl`, MinisterOfStateMembership,
GovernmentExecutive and CabinetMembership axioms).

Detailed establishment, alteration, renaming, succession and abolition may
later be grounded in Constitution, Acts, statutory instruments and specific
provisions; do not assert unreviewed statutory facts in this slice.

## 2. URI and named-graph ownership

Opaque, locally registered office/unit keys never derive from current labels,
functions, holders, ISAD IDs or Wikidata QIDs. Allocate a successor office a
new key only after reviewed evidence of office discontinuity.

| Resource or graph | Proposed deterministic IRI | Owner |
|---|---|---|
| NamedOffice | `https://data.oireachtas.ie/office/{registered-key}` | Office registry |
| AdministrativeUnit | `https://data.oireachtas.ie/administrative-unit/{registered-key}` | Unit registry |
| OfficeHolding | `{member-source-iri}#office-holding-{stable-occurrence-key}` | That Member graph |
| Holding DateRange | `{holding-iri}#date-range` | That Member graph |
| CabinetMembership | `{member-source-iri}#cabinet-membership-{digest}` | That Member graph |
| Cabinet DateRange and role | `{cabinet-membership-iri}#date-range` and `#role` | That Member graph |
| Shared office reference graph | `https://data.oireachtas.ie/graph/offices` | Office registry only |
| Shared unit reference graph | `https://data.oireachtas.ie/graph/administrative-units` | Unit registry only |
| Office external identity graph | `https://data.oireachtas.ie/graph/office/{registered-key}/external-links` | External office reconciliation only |
| Per-Bill local office links | `https://data.oireachtas.ie/graph/bill/{year}/{number}/office-reconciliation` | Bill local reconciliation only |

The existing Member graph URI remains
`https://data.oireachtas.ie/graph/member/{percent-encoded memberCode}`
(`src/oireachtas_etl/transforms/members.py:member_graph_iri`). A Cabinet
`digest` is SHA-256 of canonical serialization of the Member IRI, enduring
Government IRI, normalized *start* of the maximal continuous qualifying
episode and a fixed kind/version marker. Exclude the episode end, contributing
holdings, labels and category names. Different maximal episodes for one person
cannot have the same start; validate that invariant. An end correction may
preserve the URI, while a start correction, merge or split may change it.
**No CabinetMembership identity ledger is needed.** By contrast, source office
observations lack stable IRIs and dates can change: persist OfficeHolding
occurrence correspondence so an identifiable corrected holding keeps its URI.
Do not hash its entire office JSON or choose its array position as its identity
(`src/oireachtas_etl/transforms/members.py:_generated`, `_office`).

Shared graphs replace their complete validated registry payloads; Member
graphs own holdings, source-derived dates and generated Cabinet memberships;
office external-link graphs contain only approved external identity assertions;
per-Bill local-link graphs contain only approved Participation links. Every
graph-scoped PUT affects only its owner, so replacing a Member graph cannot
erase an office description, and replacing a Bill core graph cannot erase its
separate local links. This extends the existing endpoint reference-only and
graph-replacement rules (`documentation/etl-plan.md` §§3.4–3.6) and the
institutional external-link precedent
(`documentation/institutional-reconciliation.md`, graph ownership section).
Local Participation links must **not** be placed in an external-link graph.

## 3. Bootstrap and office-observation reconciliation

Maintain a version-controlled, reviewed registry with stable office/unit keys,
labels/aliases, office-type concept, evidenced unit relationship, reviewer
notes and evidence references. Start with positively identified offices and
units needed for the first fixture/source coverage; do not auto-mint them from
ISAD or Wikidata. Sequence: validate/publish units; validate/publish offices;
resolve source office observations; generate/publish Member holdings/Cabinet
episodes; then reconcile optional external identities and Bill sponsor roles.
An observation can cause a reviewed addition to the registry, but the source
label does not itself create an identity. The Departments wiki is explicitly
draft/deferred and its function-derived URI sketches are not this contract
(`documentation/wiki/Departments.md`).

For each generic Member `membership.offices[].office`, keep the Member IRI,
containing House-membership IRI, label, optional source office URI, raw start
and end, and immutable raw-response pointer. Validate the observation even if
its identity is unresolved. Generate candidates from reviewed office aliases,
context, dates, unit aliases and any actual source URI; optional ISAD/Wikidata
evidence may corroborate candidates. Recognize Taoiseach, Tánaiste, Minister,
Minister of State, Ceann Comhairle, Cathaoirleach, Attorney General and
historical wording as candidate patterns, **not** authoritative exact-English
classifiers. A record explicitly describing simultaneous departmental
appointments can resolve to multiple department-level offices and holdings;
responsibility/portfolio wording cannot independently create an office.

Automatic acceptance requires a unique match to an already-reviewed registry
identity or reviewed alias/context rule, compatible office type and unit
scope, and no material conflict. Ambiguous candidates, uncertain
multi-department parsing, historical succession, category or date
contradictions and uncertain correspondence after a source change require
review. Once Person + office + occurrence resolve, holding generation is
automatic: manual approval of every holding is unnecessary.

Use a versioned `reconciliation/office-decisions.json` keyed by a stable
observation-occurrence key, with accepted/rejected/unresolved status, accepted
complete local office IRI(s), evidence references and reason. Validate accepted
targets against the registry. Keep a separate durable occurrence/evidence
store of observation fingerprints, candidate sets, previous/current source
snapshots, raw pointers, conflicts, attempts and review hash. Recheck
identity-relevant source or registry/decision changes. Flag absent/stale
observations rather than silently discarding decisions. The existing external
`ReconciliationStore` has useful review, retry and dirty-publication patterns
but its `Resolution` and SQLite target columns are Wikidata-oriented
(`src/oireachtas_etl/reconciliation.py:Resolution`, `ReconciliationStore`).
Do not turn local core-gating resolution into a second external-lookup
scheduler.

## 4. Holdings, Cabinet episodes and absence

For each accepted person–office–occurrence correspondence, emit one
`OfficeHolding`, one `heldOffice`, person link and Oireachtas-derived
`DateRange` with a required start and optional end. Reuse the existing
`xsd:dateTime` conversion for membership dates; retain original date-only
lexical values in recoverable source evidence
(`src/oireachtas_etl/transforms/common.py:datetime_literal`). Distinct
offices may have precisely overlapping dates. Deduplicate truly identical
source reports while retaining all source contexts. Uncertain same-office
duplicates/episodes and uncertain date-correction correspondence require
review, not new array-position-based IRIs. Unresolved observations emit no
holding and no invented occurrence-specific role; report their context.

Using the complete effective accepted holdings, select only offices typed by
`TaoiseachOfficeType`, `TanaisteOfficeType` or `MinisterOfficeType` concepts.
`MinisterOfStateOfficeType` and other/unknown types do not qualify. Merge
overlapping periods into maximal continuous constitutional Government
episodes; for inclusive date-only ranges, immediately consecutive calendar
days are continuous, but timestamp-bearing boundaries use their actual
instants. Genuine gaps make separate episodes. Emit one derived
`CabinetMembership` per episode, with one generic `CabinetMember` role, the
enduring Government target, date range and all supporting holdings. Exact
overlap or concurrent different qualifying offices never create duplicate
Government memberships. Recalculate episodes after holding corrections:
derived Cabinet IRIs may change as described above. Validate complete
temporal coverage of every qualifying holding, absence of Minister-of-State-
only Cabinet memberships, and no overlapping Cabinet episodes for a person.

A missing *Member* is already retained rather than deleted
(`src/oireachtas_etl/cli.py:_run_members_impl`). A nested office missing
inside a still-published, changed Member is different: an ordinary complete
Member-graph PUT would erase it. Compose the current accepted observations
with previously published, ledger-identified holdings whose observations
have disappeared; retain those holdings/dates, flag `missing_retained`, then
derive Cabinet episodes from this effective set and independently validate
the entire graph before PUT. Allow independently valid non-office Member
changes through. A changed identifiable observation updates its existing
holding subject to conflict checks; external dates never silently replace
Oireachtas dates. On a material unresolved conflict, retain the last accepted
holding and preserve both source/evidence snapshots. Only an explicit,
reviewed erroneous/revoked-assertion action removes it. Recompute Cabinet
episodes and invalidate dependent Bill links after such an action. This
implements the non-destructive missing-resource policy in
`documentation/incremental-refresh-state.md` §7 for nested observations.

## 5. Administrative units, succession and external office identity

Determine AdministrativeUnit continuity locally from evidence; ISAD IDs,
events or `Replacement` do not automatically establish discontinuity. A
departmental Minister's office `headsAdministrativeUnit` when evidenced; a
Minister-of-State office `assignedToAdministrativeUnit` without headship.
The latter office identity is **Minister of State at the Department of State**,
not a unique office for each delegated responsibility or portfolio wording.
Untimed reference links alone do not prove a particular historical assignment
at every date; leave uncertain historical links unresolved rather than
asserting false timeless relationships. Office succession is separate from
unit succession and requires reviewed positive evidence; do not infer it from
chronology, labels, functions or ISAD event type.

Add an external `office` policy keyed by the established local office IRI.
Wikidata/ISAD provide candidate and conflict evidence, not local authority.
Reject wrong entity levels (person, holding, unit, historical successor).
Publish `owl:sameAs` only on reviewed same-enduring-office identity, in that
office's replaceable `/external-links` graph; do not import external dates,
labels, succession or descriptive facts. Reuse the generic reconciliation
review precedence, due/recheck, dirty replay and exact post-PUT verification;
extend its entity-kind whitelist and policy registry deliberately
(`src/oireachtas_etl/reconciliation.py:ReconciliationStore.mark_due`,
`reconcile_entities`). External failure cannot prevent valid authoritative
publication (`documentation/etl-plan.md`, Phase 3.5 architectural rules).

## 6. Bill sponsor-role local reconciliation

The existing Bill source Participation and source `rdfs:label` remain
unchanged. `sponsor.by.uri` may be null and a role label alone cannot imply a
person (`data/api_examples/bill.json`, sponsors;
`src/oireachtas_etl/transforms/bills.py:transform_bill_with_report`).
Evaluate current Participation IRI, original role text, explicit person IRI
if supplied, relevant Bill event/time context, reviewed office aliases and
accepted Member holdings. `bill.lastUpdated` is not an appointment date.
Emit `reconciledSponsorOffice` when the office is uniquely justified even if
there is no identified person. Emit `reconciledSponsorHolding` only with
positively evidenced person **and** applicable time identifying a unique
holding; check that its office agrees with any office link. Ambiguity requires
review. Persist accepted/rejected/unresolved decisions by stable Bill
sponsor-observation key, recording current Participation IRI, input
fingerprint, targets, evidence and review hash.

Sponsor role text, person and primary flag participate in the existing
Participation IRI hash (`src/oireachtas_etl/transforms/bills.py`, sponsor
transformation). Bill source changes, office-registry changes and relevant
Member-holding changes make local reconciliation due. Rebuild/validate/PUT
the **entire per-Bill local graph** against current Participations so stale
links clear when a Participation changes; keep the Bill core graph and
preserved label intact. If a Bill source record disappears, retain its core
and local assertions and flag for review, not automatic deletion. Core Bill
publication remains independent of local or external reconciliation.

## 7. Migration, validation and publication gates

Revise active `mappings/member_mapping.csv` office rows and ontology terms
together; deprecate the legacy terms, remove their active Member SHACL use and
update `ontology/README.md`. Inventory previously published office RDF and
missing historical observations before changing Member graphs. Increase the
Member `contract_version` from **2** in both hash-skip and dirty/complete
publication branches (`src/oireachtas_etl/cli.py:_run_members_impl`), so
unchanged source records are republished. Validated whole-Member-graph PUTs
naturally remove legacy occurrence-specific Minister-of-State roles,
`MinisterOfStateMembership` and `officeNameUri` triples; preserved missing
holdings are explicitly included in the new validated payload. No permanent
legacy serializer is needed. Keep existing Member/Party/Institution external
reconciliation state meanings; add new office state/policy. Bill source
transformation and its contract version need not change just to publish
separate local links.

Maintain independent source-to-RDF acceptance, Member SHACL, joined
Member/reference and temporal Cabinet-quality checks, ontology consistency,
mapping-integrity checks, exact graph verification and dirty replay.
Existing acceptance is implemented separately from the transformer in
`src/oireachtas_etl/validation/members.py:expected_member_graph` and
`validate_member`; do not replace it with the production transform as an
oracle. Test category concepts/classes never pun, headship versus assignment,
all generic office kinds, stable OfficeHolding identity on correction,
deterministic Cabinet URI changes/stability, concurrent holdings, gaps,
Cabinet coverage and deduplication, unresolved/missing/revoked/conflicting
observations, external graph isolation and retry, Bill office-only versus
person/time-qualified holding links, label preservation and graph isolation.
Update protected golden output only after semantic-contract review, never to
weaken acceptance. Run `.venv/bin/python tests/validate.py` and
`.venv/bin/python -m pytest tests` before implementation completion.

## 8. Six implementation tranches

Tranches 1 and 2 are **implemented**; Tranches 3–6 are **not started**. Keep
intermediate commits valid; switch active mappings, transformer, independent
validator, SHACL, contract version and approved goldens together rather than
temporarily disabling a gate.

| Tranche | Status | Work and prerequisites | Exit criterion |
|---|---|---|---|
| 1. Semantic contract and reference bootstrap | Implemented | Approved design; ontology/mapping contract, distinct `OfficeType` concepts, reviewed office/unit registry, shared-graph transforms, state, CLI and validation. Introduce vocabulary before replacing legacy Member mapping. | Reasoner and active-mapping integrity pass; independently validated office/unit graphs publish without changing existing Member behavior yet. |
| 2. Observation resolution and OfficeHolding correspondence | Implemented | Published registries; local review loader, occurrence/evidence ledger, candidate generation, source checks and tests. **No Cabinet ledger.** The initial reviewed dataset is intentionally narrow. | Every source office observation is accepted, explicitly unresolved or review-required; identifiable changes preserve holding occurrence keys. |
| 3. Member holdings and Cabinet migration | Not started | Accepted decisions and migration inventory; Member transform, independent acceptance, SHACL/joined checks, missing-observation composition, contract bump and complete validated republish. | Correct concurrent holdings and nonduplicated, deterministically derived Cabinet episodes; legacy erroneous triples absent, missing nested offices retained, recovery verified. |
| 4. External office reconciliation | Not started | Stable office registry; new external entity policy, review file, CLI and isolation/retry tests. May follow tranche 5 if external services are unavailable. | Reviewed same-office external links replace independently without altering authoritative graphs. |
| 5. Bill local sponsor reconciliation | Not started | Published office registry and Member holdings; separate per-Bill graph, review/state, change invalidation, validation and tests. | Supported office-only/holding links; original label and Bill core graph unchanged; stale Participation links removed on local graph replacement. |
| 6. End-to-end acceptance | Not started | Core tranches; joined competency, migration, URI, missing/conflict and graph-isolation integration checks and operator documentation. | Phase 0 validation and full test suite pass; graph-scoped publication/recovery and review boundaries are exercised end to end. |

Expected implementation components: `ontology/members.owl.ttl`,
`ontology/README.md`, `mappings/member_mapping.csv`, reviewed registry and
decision files, `src/oireachtas_etl/transforms/members.py`, new registry and
resolution modules, `src/oireachtas_etl/validation/members.py`, Member SHACL,
`src/oireachtas_etl/state.py`, `cli.py`, `config.py`, `competency.py`,
`reconciliation.py`, new Bill-local-reconciliation modules and focused tests.
Touch `mappings/bill_mapping.csv` only to describe separately owned links if
necessary, without altering its original sponsor-text evidence mapping.

## 9. Deferred work and review boundaries

Defer detailed functions/delegations/portfolios, temporally qualified
office–unit assignments, ISAD historical-incarnation ingestion, full
constitutional/Act/SI provision-level grounding, unreviewed historical
succession, numbered Governments, Attorney General/Chief Whip attendance,
competing-date-evidence RDF and Questions recipient-role reconciliation.
Responsibilities remain separate from enduring office identity so later
enrichment does not require replacing office IRIs. Specific historical
identity/succession, ambiguous source occurrence and person/time-specific
Bill sponsor decisions are evidence-review cases, not new architectural
decisions or reasons to guess an identity.
