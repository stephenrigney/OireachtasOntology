# Query Service — Group B: Committee Membership and Officeholder Constituency

Reference date: **2026-11-09**. Base: merged Group A, `f13722c` (PR #28).
Branch: `query-service-member-memberships`. No PR #27 functionality, Group C,
Bills work, ontology/mapping/ETL changes or RDF writes.

## Outcomes and before/after behaviour

| Slice / original question (verbatim) | Before | After / factual outcome |
|---|---|---|
| B1 — Who are the members of the Committee on Public Accounts? | `unsupported_capability`: “Committee membership is outside the supported local parliamentary query capabilities.” | **PASS**, 13 distinct locally recorded current Members, with exact membership and temporal evidence below. Not a certified complete current roster. |
| B2 — What constituency does the Tánaiste represent? | `unresolved_identity`: “No local Member record was found for ‘the Tánaiste’.” | **BLOCKED by accepted source evidence**, now correctly treated as a NamedOffice. No accepted current Tánaiste holding is recorded; no Member or constituency is substituted. |

The reusable B2 chain is implemented and deterministically tested, including
its successful identity-preserving path, but those synthetic tests are **not** a
factual PASS for the requested Tánaiste answer. The user's expected Simon Harris
identity cannot be independently established by the accepted officeholding RDF
at this reference date. His separately evidenced constituency is not a substitute.

## Read-only investigation and bounded implementation

The initial investigation inspected existing CommitteeMembership, Committee,
NamedOffice, accepted OfficeHolding and current constituency-representation
compilers/resolvers before changing behaviour. It queried Committee owner
triples, the exact current PAC membership/date paths, every accepted Tánaiste
holding, Simon Harris's accepted officeholding paths and his term-scoped
representation paths. No data was loaded, repaired, refreshed or published.

### B1 — `current_committee_members`

- AI selects one approved capability with one grounded Committee mention; local
  validation accounts for the whole current Member-list request. Past periods,
  additional dates, party filters, counts, attendance, chairs and extra requested
  fields cannot be silently dropped.
- Reuses the Stage A owner catalogue compiler, with an opt-in evidence projection
  retaining Committee DateRange, typed HouseTerm and House-owned period identities.
  Catalogue and membership selection both use existing bounded ordered pagination.
- Resolves whole source-backed labels, preserving the source spelling in answers.
  Only the **initial generic** `Committee on` / `Committee of` connector is
  normalised. Subject words are never omitted, reordered, accent-folded or matched
  by substring. Thus the user's “Committee on Public Accounts” can resolve to the
  recorded “Committee of Public Accounts”; bare “Public Accounts” cannot. No new
  alias registry, manufactured Committee IRI or external identity decision exists.
- Every matching incarnation's owner/HouseTerm dates must be usable and
  consistent. Both intervals must contain configured `asOf`; more than one current
  owner remains ambiguous. A historical label match is not a current identity.
- Uses the existing reviewed Member → CommitteeMembership → Committee predicates
  and mapped inclusive interval evaluator. Each membership must independently
  contain `asOf`. All evidence is validated before distinct-Member projection;
  separate qualifying episodes survive deduplication. Missing/conflicting dates,
  identities, names, Committee targets, malformed rows or incomplete paging fail
  closed. No matches is unavailable, not a certified zero roster.
- Final rendering preserves Member, Committee, membership, range, source graph,
  HouseTerm and period identities, dates and reference date. It prominently
  distinguishes positive local membership evidence from roster certification,
  chairmanship or attendance.

### B2 — `current_office_constituency`

- AI selects the bounded office-to-constituency operation with **only** the
  grounded NamedOffice mention. Neither identity nor date can be model-supplied.
  Exact current office titles encountered by the early Member-representation
  recogniser are routed to semantic selection, rather than authoritative
  Member-name resolution. This is routing, not a new identity resolver.
- Reuses reviewed NamedOffice label resolution, the accepted dated OfficeHolding
  evidence compiler, current-point evaluator, complete bounded pagination and
  strict mapped interval validation. Requires exactly one accepted active
  **relationship**, not merely a guessed person or the most recent historical row.
- Passes the exact resulting Member IRI to the existing current-Dáil
  representation executor. A local-only resolved-Member argument prevents a
  second name lookup; same-name people cannot change the relationship join.
  House-owned dates select the current Dáil independently, and the exact
  DailMembership interval must itself contain `asOf`.
- An opt-in projection retains representation membership/range identities and
  dates alongside the existing Member/constituency/term identities. Successful
  chain answers additionally preserve NamedOffice, holding, holding range and
  holding dates. Conflicting current constituency identities fail closed.
- The local chain's evidence reads retain unlabelled competing holdings and
  constituency paths, so a missing display label cannot hide a second
  relationship before uniqueness validation. This is opt-in; existing office and
  representation query projections retain their original behaviour. Blank names
  produce a structured blocker. Successful debug evidence retains both queries.
- No current Dáil representation is a qualified unavailable result identifying
  the accepted officeholder and holding, **not** an assumption that the person
  must be a TD, and never a former-holder/historical-constituency substitution.
  Local officeholding evidence never certifies a complete government roster.

Both operations have closed canonical v2 plans and validators. They reuse
validated read-only SPARQL and existing evidence evaluators, not arbitrary graph
composition or a new semantic-verification mechanism. Existing representation
answer shapes remain unchanged unless the new local adapter requests evidence.

## B1 — accepted source findings and exact answer

Owner graph: `https://data.oireachtas.ie/graph/committees`.
Three recorded Public Accounts Committee incarnations exist in Dáil 32, 33 and
34. The first two end on 2020-01-14 and 2024-11-08 respectively. The selected
current incarnation is:

```text
Committee: https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts
Source English label: Committee of Public Accounts
Committee ID / code: 236 / ACC
Committee DateRange: Committee IRI + #committee-date-range
Committee interval: 2024-12-18T00:00:00 – open-ended
HouseTerm: https://data.oireachtas.ie/ie/oireachtas/house/dail/34
HouseTerm period: HouseTerm IRI + #term-period
HouseTerm interval: 2024-11-29 – open-ended
Reference date: 2026-11-09
```

The owner starts and membership endpoints are recorded `xsd:dateTime`; absent
ends remain open-ended evidence, not proof of permanent service. The current
owner has **15** recorded membership episodes. Two are correctly excluded:
Catherine Ardagh, 2025-05-07–2026-05-28; Catherine Connolly,
2025-05-07–2025-10-25. All 13 returned episodes have no recorded end.

The exact returned Members and relationship identities follow. To keep long
identifiers reviewable, these **lossless** expansions apply to every row:

- `Member IRI = https://data.oireachtas.ie/ie/oireachtas/member/id/` + Member ID;
- `Membership IRI = Member IRI + /house/dail/34#committee-membership-` + hash;
- `Membership DateRange IRI = Membership IRI + #member-date-range`;
- source graph is `https://data.oireachtas.ie/graph/member/` + Member ID, with
  `Séamus` percent-encoded as `S%C3%A9amus` in that graph IRI only.

| Returned name | Exact Member ID | CommitteeMembership hash | Start (midnight) |
|---|---|---|---|
| Aidan Farrelly | Aidan-Farrelly.D.2024-11-29 | `7a2d9746a8c5bcd6f35632c508fe12088e51dce5270a016d79a9e5e5a7e9ad86` | 2025-05-07 |
| Albert Dolan | Albert-Dolan.D.2024-11-29 | `83ee419568331dfb794f79cd3762741bdba677951e3bbc287cdf5ef79807a3bf` | 2025-05-07 |
| Cathy Bennett | Cathy-Bennett.D.2024-11-29 | `23a748f26e866b5774885cae7959df18dd79f44332f66921fc5f1e72c91fe572` | 2025-05-07 |
| Eoghan Kenny | Eoghan-Kenny.D.2024-11-29 | `4e90992d1a1d43776921a4ccff8c19066e1a3705674291ec7cc2663bd3d9d2ee` | 2025-05-07 |
| Grace Boland | Grace-Boland.D.2024-11-29 | `332a9b9bf82c1b09bc876733deaf3dde2d15c9f963931ccbf65883b989d719a9` | 2025-05-07 |
| James Geoghegan | James-Geoghegan.D.2024-11-29 | `09fc8af09070919a9c78be0f4acc258c5c92050b5777c4545f63148581256c98` | 2025-05-07 |
| Joanna Byrne | Joanna-Byrne.D.2024-11-29 | `5f5eae6b81ca16f17e04520361115d1e30ce5d1b29ebfe413e08ed8dbde0b5f9` | 2025-05-07 |
| Joe Neville | Joe-Neville.D.2024-11-29 | `9870c9b8b2956a07259682c60f6134c2629a885a3fabaf577e5077f7f618b22e` | 2025-05-07 |
| John Brady | John-Brady.D.2016-10-03 | `897ebbb535915271ce2ca1d3a68b87494914716085e8dc8d8807266df8b13349` | 2025-05-07 |
| Martin Daly | Martin-Daly.D.2024-11-29 | `f3c35f58f00541e0680b6bf5fd1c2a24a49941c160fc29f6c07ea2d31a56ac0c` | 2026-07-15 |
| Paul McAuliffe | Paul-McAuliffe.D.2020-02-08 | `adf2def11234f4f15a787e2fd09c4f780aaa5501d6889d6b34951964c345bbdf` | 2025-05-07 |
| Paul Murphy | Paul-Murphy.D.2014-10-10 | `89703cbd028ee24c36338a53eafa8bb0f6bec308fe31cf8227fc03a39aa3f8a5` | 2025-11-26 |
| Séamus McGrath | Séamus-McGrath.D.2024-11-29 | `62f3b3423921cb4b42aaef70d040465d9a38e4d73fdcf8314746caeb50788a61` | 2025-05-07 |

Each rendered row includes the common Committee and HouseTerm evidence above,
its full Member IRI and full membership/range/source graph IRIs, interval and
`As of`. The final notice is exactly:

> Locally recorded CommitteeMemberships active at 2026-11-09; not a certified complete current roster. The Committee and its HouseTerm independently contain asOf. Membership does not establish chairmanship or attendance; missing end dates remain open-ended.

## B2 — exact accepted-evidence blocker

The reviewed NamedOffice is
`https://data.oireachtas.ie/office/o-000002`, labelled **Tánaiste**, with recorded
`TanaisteOfficeType`. Independent read-only selection finds seven accepted
Member-owned holdings for that exact office:

| Recorded Member | Accepted start | Accepted end |
|---|---|---|
| Seán T. O'Kelly | 1944-06-09 | 1945-06-14 |
| William Norton | 1957-03-20 | 1959-06-23 |
| Dick Spring | 1982-12-14 | 1987-01-20 |
| Brian Lenihan Snr. | 1989-06-29 | 1990-10-31 |
| Bertie Ahern | 1994-11-17 | 1994-12-15 |
| Mary Harney | 2002-06-06 | 2006-09-13 |
| Brian Cowen | 2007-06-14 | 2008-05-07 |

All have finite ends before `asOf`. The exact gap is **no accepted current
Member → OfficeHolding → Tánaiste relationship**, not missing office identity,
not proof of vacancy, and not a reason to select the last historical row.
No source/mapping/semantic repair is authorised or attempted here.

Simon Harris's exact Member identity is
`https://data.oireachtas.ie/ie/oireachtas/member/id/Simon-Harris.D.2011-03-09`.
His accepted holdings are two Taoiseach episodes (2024-04-09–2024-11-08 and
2024-11-29–2025-01-22, already preserved by Group A) and an open Minister for
Finance episode starting 2025-11-18 (`office/o-000003`); none targets Tánaiste.

Independently, his recorded current Dáil representation **does** link:

```text
Member: .../member/id/Simon-Harris.D.2011-03-09
DailMembership: Member IRI + /house/dail/34
DateRange: DailMembership IRI + #date-range
Membership interval: 2024-11-29T00:00:00 – open-ended
Constituency: https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Wicklow
Source label: Wicklow
HouseTerm: https://data.oireachtas.ie/ie/oireachtas/house/dail/34
```

That verifies only the second relationship for the **separately named** person;
it cannot establish that he is the current Tánaiste. The separate live question
“What constituency does Simon Harris represent?” returns Wicklow, but B2 returns
**no result rows** and exactly:

> No accepted current OfficeHolding for Tánaiste (https://data.oireachtas.ie/office/o-000002) is locally evidenced at 2026-11-09. No officeholder or constituency was substituted. Local current-office coverage is not certified; this does not establish a vacancy.

### Separate live positive control for the reusable chain

“What constituency does the Minister for Finance represent?” was also executed
through the actual planner and read-only `/ask` route. It returns **Simon Harris
— Wicklow — 34th Dáil**, using NamedOffice `office/o-000003`, not the Tánaiste
office. Its exact holding is the Simon Harris Member IRI above plus:

```text
#office-holding-fdfe27d29558fecfa50a8802f02fe249b68f27254b97b236b58b0335b69cde20
```

The holding DateRange is that IRI plus `#date-range`; its start is
2025-11-18T00:00:00, with no recorded end. The final row preserves that holding,
office and range alongside the exact current membership/constituency identities
and 2024-11-29T00:00:00 membership start above, open ends and reference date.
An independent comparison against both source paths checked every identity and
date. This establishes live positive execution of the reusable capability,
**not** that Simon Harris is the Tánaiste. B2 remains BLOCKED. The final notice is:

> Locally evidenced accepted officeholder and independently dated Dáil representation at 2026-11-09. Exact Member identity joins the two relationships; not a certified complete current-office or government roster. Missing ends remain open-ended.

## Live `/ask` verification

The complete FastAPI **POST `/ask`**, `mode=phase2`, was exercised through
`TestClient`, with the **actual configured semantic planner and real local
read-only Fuseki**. Configuration was inherited from the running local service;
only this test process fixed `OIR_NLQ_AS_OF_DATE=2026-11-09`. No running service,
endpoint, credentials, dataset or production configuration was changed. ASGI
testing executes the real route; it is not a fixed-plan simulation or HTTP-200
acceptance shortcut.

The configured model was `gpt-6-luna`, using
`https://opencode.ai/inference/openai/v1` through the existing planner transport.

All 17 final requests returned HTTP 200. Actual projections and evidence, not
that status, determine the outcomes below. All three B1 answer identity sets,
relationship/range/source graph identities and displayed dates were asserted
equal to independently written RDF selections. All three B2 refusals were
checked against the complete seven accepted holdings and the lack of an active
interval. Historical/extra-condition controls returned no answer rows.

| Live question | Checked outcome |
|---|---|
| Who are the members of the Committee on Public Accounts? | Same 13 exact Members and dated paths above |
| Which members serve on the Committee of Public Accounts? | Same 13 identities and source intervals |
| List the current members of the Committee on Public Accounts. | Same 13 identities and source intervals |
| Who are the members of the Committee on Public Accounts in 2020? | Unsupported historical scope; no simplified current answer |
| Who are the Fianna Fáil members of the Committee on Public Accounts? | Unsupported party condition; no unfiltered answer |
| Who are the members of the Committee on Public Accounts and their parties? | Unsupported extra field; no partial Member answer |
| Who are the members of the Public Accounts? | No whole owner-label match; no guessed identity |
| What constituency does the Tánaiste represent? | Missing accepted current holding, exact blocker above |
| Which constituency does the current Tánaiste represent? | Same accepted-source blocker |
| What Dáil constituency does the Tánaiste currently represent? | Same accepted-source blocker |
| What constituency did the Tánaiste represent in 2020? | Unsupported historical officeholder composition |
| What constituency does the Tánaiste represent and what is their party? | Unsupported extra party projection; no partial answer |
| What constituency does the Minister represent? | Unresolved generic identity; no office/person guessed |
| Who are the Fianna Fáil Senators? | Group A preserved: same 19 Members |
| Who were the Labour Senators in the 25th Seanad? | Group A preserved: same five Members |
| When was Simon Harris last Taoiseach? | Group A preserved: latest recorded 2024-11-29–2025-01-22, qualified local episode |
| What constituency does Simon Harris represent? | Separately named Member: Wicklow, exact Dáil 34 occurrence; not a B2 answer |

Ambiguous current Committee incarnations, ambiguous reviewed NamedOffice labels,
same-name Members and multiple active OfficeHolding relationships are tested
deterministically; they were not manufactured in the read-only live RDF.
After the final routing adjustment, both original questions were repeated and
retained exactly the same answer/blocker; “What constituency does the Tánaiste
currently represent?” also returned the same source blocker. Thus there were
20 requests in that matrix/recheck run, covering 18 distinct questions. After
the review-driven evidence-read tightening, these three were repeated again,
and the Minister for Finance positive control above was added: **24 final-campaign
requests covering 19 distinct questions**, all with checked answers or safe
nonanswers. Both original questions retained exactly the same projection/blocker.

### Independent RDF selections

These were written independently of application compilers. The Committee
selection returned 15 rows, and the office selection seven, both below a
100-row page boundary. No filtering on the reference date hid ended, future or
uncertain evidence before checking it. Python independently checked interval
starts/ends and compared exact output identities and evidence strings.

```sparql
PREFIX a: <https://data.oireachtas.ie/ontology#>
PREFIX m: <https://data.oireachtas.ie/ontology/members#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?graph ?member ?name ?membership ?range ?start ?end WHERE {
  GRAPH ?graph {
    ?member a a:Member; foaf:name ?name; m:hasMembersMembership ?membership .
    ?membership a m:CommitteeMembership;
      m:isCommitteeMembershipOf
        <https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts> .
    OPTIONAL { ?membership m:hasMembershipDateRange ?range .
      OPTIONAL { ?range m:StartDate ?start }
      OPTIONAL { ?range m:EndDate ?end } }
  }
  FILTER(STRSTARTS(STR(?graph), "https://data.oireachtas.ie/graph/member/"))
} ORDER BY ?member ?membership
```

```sparql
PREFIX a: <https://data.oireachtas.ie/ontology#>
PREFIX m: <https://data.oireachtas.ie/ontology/members#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?graph ?member ?name ?holding ?range ?start ?end WHERE {
  GRAPH ?graph {
    ?member a a:Member; foaf:name ?name; m:hasOfficeHolding ?holding .
    ?holding a m:OfficeHolding;
      m:heldOffice <https://data.oireachtas.ie/office/o-000002> .
    OPTIONAL { ?holding m:hasMembershipDateRange ?range .
      OPTIONAL { ?range m:StartDate ?start }
      OPTIONAL { ?range m:EndDate ?end } }
  }
  FILTER(STRSTARTS(STR(?graph), "https://data.oireachtas.ie/graph/member/"))
} ORDER BY ?member ?start
```

Separate owner-triple and HouseTerm queries verified the exact Committee IDs,
labels and dates; separate exact-Member queries checked Simon Harris's accepted
holdings and all four recorded Dáil representation paths. No web knowledge or
expected answer was used as a missing RDF relationship.

## Verification and residual limits

The Phase 1 query-schema context remains **47,931 / 48,000 characters**; the
cap was not increased, and real application startup was exercised repeatedly.
No query-schema context redesign was needed: new capability metadata belongs
to the composable semantic contract, not the Phase 1 RDF context.

Focused capability/dispatch tests: **82 passed**. The initial broader runs found
four stale exact-version assertions (`2.27.0`) after the intentional composable
contract version bump; these were updated to `2.29.0`, without removing any
semantic assertions. A focused rerun of those contract checks passed (17 tests).
Fresh broader-suite results are recorded in the completion update.

Independent static review of the officeholder chain identified edge-case gaps
around blank Member names, an empty routing mention, unlabelled competing
relationships and successful-query diagnostics. The bounded fixes retain those
relationships for validation, return structured blockers, skip empty name
prefilters and retain both query/evidence sets. New negative tests cover them.
The follow-up independent review found no material remaining correction; it was
a separate review perspective, not execution approval or a data acceptance gate.

The ordinary ontology validator passes (2,586 triples; HermiT completes).
No source/golden fixtures or acceptance constraints were changed. Optional
mutation-capable capture/Fuseki/production acceptance is not enabled: the local
configured dataset is read-only evidence, not a disposable write target.

Remaining limits are deliberate: AI interpretation can vary; wording and
compositions remain bounded; neither local current nor historical completeness
is certified. B2 requires a separately reviewed source-evidence update before
the requested Tánaiste relationship can be factually answered. This work does
not authorise that update or any Group C implementation.
