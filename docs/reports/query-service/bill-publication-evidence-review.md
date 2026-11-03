# Query Service — Review Bill Publication Evidence and Count Semantics

## Scope and evidence

Read-only review of the live local Fuseki snapshot on 2026-11-03. Fuseki
readiness was `ready` with Bill graphs present. Re-ran the integrated Q23
question for Malcolm Byrne, then inspected Published activity evidence only in
the 20 distinct Bill graphs returned by that answer. No data refresh, graph
mutation, raw-corpus scan, or benchmark replay was performed. These findings
describe this local snapshot, not the whole Oireachtas Bill corpus.

| Published lifecycle evidence among the 20 Q23 Bills | Bills |
|---|---:|
| Valid dated Published activity | 0 |
| Published activity present, date missing or malformed | 0 |
| No Published activity recorded in the Bill graph | 20 |
| Conflicting/otherwise ambiguous Published activity evidence | 0 |

The 20 identities were: 2020/11; 2021/17, 30, 43, 139, 149; 2022/7, 108;
2024/19, 32, 49, 58, 89; 2025/11, 62, 71; and 2026/31, 86, 89, 93. The five
2024 Bill identities are legislative-year identities only; that fact is not
publication-date evidence. In the inspected graphs the query found other
lifecycle/stage evidence (111 rows across the Q23 Bills), but no occurrence
asserting `agents:Published` with any date, nor any such Published occurrence
without a date. Therefore none can be classified as a recorded 2024 publication
or a verified non-publication.

## Cause assessment

**Confirmed:** the service failure is caused by absent Published activity rows
in the exact 20 Bill sponsorship records, not by malformed dates on a Published
activity. The temporal compiler binds `?publishedActivity` and
`?publishedDate` optionally on the same Bill process
(`poc/nlq/composable_plan.py:1855-1888`). With no Published match, the optional
bindings are empty; `_published_year_bill_identities` treats an unbound
activity as unresolved and raises `NLQError` (`:3732-3767`). The executor
returns `source_data_unavailable` without a count (`:3837-3843`). Thus the
observed error is the expected conservative outcome for this evidence.

**ETL/mapping behavior reviewed:** `mappings/bill_mapping.csv` maps
`results[].bill.events[].event.eventURI` `published` to `agents:Published` and
event dates to `eli-dl:activity_date`; its note says multiple dates may
represent repeated occurrences (including initiation and signing). The
transformer maps supported events and attaches them to the Bill process
(`src/oireachtas_etl/transforms/bills.py:519-554, 599-609`). It does not filter
out Published events. A supported event must carry a non-empty date array and
each date is parsed through `date_literal`; invalid/missing dates fail
transformation rather than being silently converted to an untyped RDF date
(`:344-371, 546-553`). An absent `events` field defaults to an empty list
(`:599-601`). The mapping also explicitly lists Published as a supported event
(`:441-454`). These facts provide no evidence of a Published-specific ETL
omission/bug in the reviewed code.

**Unresolved:** the live RDF cannot establish whether the source API omitted
these events/captured an incomplete event array, whether particular Bills had
not undergone the lifecycle event represented by `Published`, or whether a
source capture boundary explains the absence. A Bill can have other stages and
events without a Published event in the graph; that is not proof that it was
never published. Raw source records for these Bills were not inspected, by
scope. No source omission or legitimate lifecycle cause can therefore be
assigned per Bill from this evidence alone. No ETL correction is currently
justified; if a focused source-backed check later finds a supported Published
event in retained raw JSON that is absent from its RDF graph, investigate that
specific transform/publication mismatch only.

Relevant semantics: approved Q23 is a distinct-Bill list with primary or
supporting status where evidenced and unknown preserved; it does not approve a
count. Approved Q19 prefers source-backed dated Published activity and says
missing dates are not inferred, with only a disclosed introduction/presentation
fallback for Q19. That fallback does not authorize a Q23 sponsorship count
substitution. The Bill capability inventory likewise warns that coverage is
data-dependent and mapping presence does not establish source completeness.

## Count and zero recommendations

Recommend **both count modes, with different claims**, only after human
approval; do not weaken the existing safeguards as part of this review:

1. **Exact count:** answer only when the service has an accepted completeness
   basis for the relevant sponsorship records and Published-event evidence, and
   all selected Bills can be evaluated. Otherwise report unavailable rather
   than imply a corpus-exact total. The current local dataset does not meet this
   standard, even if every returned Bill had a date, because complete historical
   sponsorship/publication coverage is not certified.
2. **Qualified recorded-evidence count:** can be useful where exact completeness
   is not established, but it must be a separately labelled count of distinct
   Bill IRIs with *recorded valid dated Published activity in the requested
   year*. Also disclose the number of sponsored Bills with no Published
   evidence/date (unknown with respect to the year), and state that those Bills
   may change the result. Do not call this simply “the number of Bills published
   in [year]”; do not use legislative year or document/version dates. If the
   service cannot establish the denominator of locally recorded sponsored
   Bills, it should return unavailable, not a deceptively precise partial count.

For this snapshot the qualified outcome is **0 evidenced matches among 20
recorded Q23 Bills, with 20 publication-year-unknown Bills**—not “0 Bills” and
not an estimate of the true total. The current strict evaluator returns
unavailable instead; that is safer than silently counting missing evidence as a
non-match.

Zero presentation must be evidence-qualified. A zero exact result requires
completeness sufficient to rule out matches. A qualified zero must say “0
recorded matches; N records have unknown publication year” (and show the
coverage scope). No sponsorship rows, unavailable Bill graphs, failed queries,
or missing event evidence must never render as zero. Existing no-sponsorship
handling already distinguishes unavailable local evidence from a negative
(`composable_plan.py:3810-3835`); preserve that distinction.

## Decision and smallest next action

**Keep the existing strict fail-closed behavior unchanged for now.** It correctly
avoids converting these 20 absent-event cases into an unsupported year count,
and this read-only review does not authorize a new count meaning. Its present
diagnostic could be more specific (“no Published activity recorded” versus
“Published activity date missing/malformed”), but changing statuses or result
presentation is an implementation/semantic follow-up, not part of this review.

The smallest justified next action is a **human decision** whether to approve a
qualified recorded-evidence count alongside a separately defined exact count,
including its coverage denominator and unknown-evidence presentation. Only
after that decision should a bounded Query Service follow-up be specified. No
general Bill ETL work is recommended. An ETL/data correction is conditional on
focused evidence that retained raw source contains supported Published events
that the existing transformer failed to emit; otherwise source completeness
and lifecycle meaning remain unresolved rather than assumed.
