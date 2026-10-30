# Legislation ETL reference

This is the current domain-specific contract for Bill and legislative-lifecycle
publication. The [ETL architecture](../../architecture/etl.md) and
[state/refresh reference](state-and-refresh.md) describe shared pipeline rules.
The executable implementation, tests, ontology and mapping remain authoritative.

Bills are transformed into one Bill-owned graph named
`https://data.oireachtas.ie/graph/bill/{year}/{number}`.  A Graph Store PUT
replaces the complete graph only after source, RDF and SHACL validation pass.
Competency verification runs against the graph after PUT; a PUT or competency
failure leaves the record dirty for retry. The shared core ETL SQLite database
stores each complete Bill source hash, deterministic publication payload hash
and durable pending publication data, so unchanged records are source-validated
and skipped before RDF transformation or publication. The former
`bills-state.json` file is imported once as read-only legacy state. Phase 5
online Bills runs now use incremental `last_updated` extraction by default;
`run bills --full` performs complete source reconciliation. The first incremental
run without a cursor reads the whole source, then advances to its fixed upper
source-time boundary only after all selected Bills complete. Later runs re-read
one hour before the cursor by default (`--overlap-seconds` or
`OIR_BILLS_CURSOR_OVERLAP_SECONDS`). The API may filter at day granularity, so
the upper boundary is also enforced locally against `bill.lastUpdated`.
Only successful `--full` runs infer non-destructive `missing`, then
`confirmed_missing` after a second complete absence; no graph is erased.
Full runs do not advance the incremental cursor. Deployment scheduling of
periodic full runs remains outside Phase 5. SQLite v2 upgrades v1 state
transactionally and retains successfully published payloads for exact graph
verification and verified mismatch repair. Legacy clean rows without payloads
are republished once to establish that baseline. Immutable online API pages
are retained under date/run-ID paths, preventing same-day refresh collisions.
Fixture-backed online runs may exercise graph publication but do not advance
the API source-time cursor or establish source-absence evidence, because a
fixture cannot attest to the completeness of the current API dataset.

The Bill is an `eli-dl:DraftLegislationWork`/`eli:LegalResource` and owns one
`{bill-uri}#process`. Stages and supported lifecycle events are owned
`eli-dl:LegislativeActivity` resources. Stage occurrence IRIs remain their
source URIs; supported lifecycle-event occurrence IRIs are derived from the
canonical source `event.uri`, controlled event type, sorted unique activity
dates, and chamber URI (including explicit null). `showAs` and source-array
ordinal are not identity inputs. Exact duplicates collapse, while conflicting
mapped semantics under one complete event identity fail closed. Stage source
order and `:progressStage` are retained; `eli-dl:latest_activity` points to the
source stage IRI.
Delivery and sponsor participations without source IRIs use SHA-256-derived
fragment IRIs. When a derived resource is itself the parent of another
derived resource, append the child component to the existing fragment; do not
create an invalid second `#` fragment. Resolved sponsors use
`eli-dl:had_participant_person`; unresolved role text is retained only as an
`rdfs:label` on the Participation.

Related-document source IRIs identify Bill-owned Work groups rooted as
`{source-uri}#work`. Each Work has its controlled `eli:type_document`; its
Expressions are derived from source URI, type, language, date, and `showAs`,
not from rendition URIs. The Bill links to the Work with ELI core
`eli:has_part`, and the Work uses `eli:is_realized_by` for each Expression.
Bill Digests, Errata, Glossaries, and Explanatory Memoranda are Bill-owned.
Format IRIs are derived from owning Expression, controlled media type, and
canonical rendition URI, so distinct renditions of one media type remain
distinct. Amendment lists are separate derived Works, Expressions and
`#tabling` activities; each nested IRI extends its parent fragment with a
deterministic SHA-256-derived component. Source stage IRIs identify concrete
`eli-dl:LegislativeActivity`
occurrences; `stageURI` resolves each occurrence to a controlled local value
typed both `eli-dl:ProcessStage` and `eli-dl:ActivityType`. The occurrence uses
that value for both `eli-dl:occured_at_stage` and `eli-dl:had_activity_type`.
The Article 26 referral event and the `bill-stage/referral-to-supreme-court`
stage URI both map to `:ReferralToSupremeCourtArt26`; this one BillEventTable
concept is typed as both `eli-dl:ProcessStage` and `eli-dl:ActivityType`.
The `bill-stage/referendum` definition and referendum event type both use the
single `:Referendum` individual, typed as both `eli-dl:ProcessStage` and
`eli-dl:ActivityType`. The `bill-stage/6` definition maps to the distinct
`:CreamListStage` concept;
it is not the `:CreamList` amendment-list type. A valid same-Bill amendment
stage reference ending exactly in `/6` may target `:CreamListStage` when its
concrete occurrence is absent, without minting an occurrence. Other unmatched
references retain the unresolved-source diagnostic. `:progressStage` orders
occurrences and does not determine controlled stage identity.
An amendment's source stage reference resolves through its associated occurrence
to the same controlled `eli-dl:ProcessStage`. `eventURI` and `methodURI` map to
controlled `eli-dl:ActivityType` values only. A Bill `version.uri` is a source
identifier/key, not necessarily a unique Expression identity. Each Bill-version
Expression source URI must be beneath its owning Bill IRI. Its RDF Expression IRI
is derived from the canonical source URI, suffix, `docType`, language, date and
label using canonical JSON SHA-256; rendition URIs and array ordinals are
excluded. Format IRIs are derived from their owning Expression,
controlled media type and canonical rendition URI, allowing distinct PDF/XML
renditions of one Expression to remain separate Formats. PDF/XML formats are
embodied by Expressions, with controlled ELI language and IANA media-type IRIs
rather than literals.

Canonical House and HouseTerm IRIs are references only. Sponsor Member IRIs
are references only; no Member labels are emitted. The resulting Act is only
the `eli:basis_for` target; no Act triples, including `dateSigned`, are owned.
Debate source values remain in raw JSON and emit no RDF.

The vocabulary baseline is ELI 1.5 and vendored ELI-DL 3.0; pins and checksums
are recorded in `ontology/external-vocabulary-pins.md`. Validation rejects an
emitted ELI/ELI-DL term outside that audited baseline.

The API provides no explicit amendment-list identity URI. Each amendment-list
Work, its Expression, and its tabling activity therefore use one deterministic
identity key containing stage reference, `stageNo`, date, chamber, amendment
type, and a canonical, format-labelled signature of all non-null PDF/XML
rendition URIs. The rendition URI is only a source-record discriminator when
base fields collide; it does not assert that a manifestation is the Work. The
signature order is deterministic and uses neither `showAs` nor source-array
position. Exact duplicates with the same mapped content collapse; conflicting
mapped content for one complete identity, including a different `showAs`, fails
closed.
Sponsor participations use Member or role IRIs where supplied. The API supplies
no stable identity for a role-text-only sponsor, so its role text and primary
flag remain the documented residual identity inputs. A null `isPrimary` is
unknown: retain the Participation, omit `:isPrimarySponsor`, and report a
deterministic source diagnostic. That property is optional, Boolean, and
zero-or-one.

The Bill process status is derived only from controlled `bill.statusURI`.
`stageOutcome` is preserved source evidence only: it neither sets
`eli-dl:process_status` nor creates `BillEventOutcome` assertions. The initial
Bills publication contract remains version 1; no accepted Bill graph had been
published before this contract correction.

The complete-source runner quarantines only the reviewed malformed source
records (the invalid `2024/48` stage identity and missing required stage dates
for `1959/P3`, `1965/P1`, and `1965/P3`). It retains the complete raw source,
reports Bill identity/path/reason, and constructs no replacement Bill graph.
Unknown transform or validation failures still fail the run. The reviewed
unresolved amendment stage-3/stage-4 references remain diagnostic-only; the
exact stage-6 fallback is unchanged.
