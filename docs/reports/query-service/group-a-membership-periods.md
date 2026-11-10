# Query Service — Group A: Seanad Membership and Office Period Queries

Reference date: **2026-11-09**. Scope: A1/A2/A3 only, based on remote master
`a74883b`; not based on PR #27. No ontology, mappings, source records, golden
fixtures, publication, Bills functionality or Group B changes.

## Implementation

- **A1:** scoped `present_seanad_party_as_of` interpretation for unqualified
  present-tense named-party Senator queries. Reuses `currentTerm`, House-owned
  date resolution and the existing two independently active membership/party
  interval checks. The interpretation question/date are locally revalidated.
- **A2:** extends the same party-only `member_relationship_composition` graph
  to an exact numbered SeanadTerm. Reuses the Stage C term-scoped party gate,
  reviewed PoliticalAffiliationIdentity resolution, exact containing-membership
  join, inclusive interval evaluator and complete bounded pagination. No current
  party shortcut. Separate qualifying episodes survive Member deduplication.
  Whole reviewed party names may omit the terminal generic word “Party”;
  “Labour” cannot match “National Labour Party”, and ambiguity remains explicit.
  No alias register or source data was changed.
- **A3:** `office_holding_evidence` gains `selection: latestRecorded`. Reuses
  exact Member/NamedOffice resolution and the complete accepted OfficeHolding
  episode reader/compiler. Validated starts order distinct episodes; only a
  unique latest start with all earlier intervals ending strictly before it can
  select a row. Ties, earlier open/overlapping intervals, future starts and any
  invalid interval prevent selection. A missing latest end stays open-ended,
  never proof of a completed tenure. Exact Member, office, holding and DateRange
  identities are displayed. This is **latest recorded**, not proven historically
  last service or a complete career history. The all-episodes projection remains.

Additional dates, conflicting terms, party combinations, exclusions and
unrepresented relationships are refused, not silently simplified. The existing
v2 graph/dispatch architecture, read-only safety and pagination remain in use.

## Live route and factual verification

Actual `POST /ask` with `mode=phase2` was exercised through the worktree's FastAPI
ASGI application (`TestClient`), with the **real configured semantic planner**
and **real local Fuseki**, not a fixed-plan generator. `OIR_NLQ_AS_OF_DATE` was
fixed to `2026-11-09`. Configuration was inherited from the running local
development service; its server, configuration and RDF were not changed.

Before implementation all three original questions returned unsupported;
both working comparisons returned answers. After implementation:

| Request | Result | Checked answer |
|---|---|---|
| Who are the Fianna Fáil Senators? | PASS / answer | 19 exact Member identities, identical to explicit-current comparison |
| Who are the Fianna Fáil Senators in the current Seanad? | PASS / answer | Same 19 identities and interval evidence |
| Who were the Labour Senators in the 25th Seanad? | PASS / answer | Five exact identities below, with historical overlap evidence |
| When was Simon Harris last Taoiseach? | PASS / qualified answer | Latest recorded episode: 2024-11-29–2025-01-22 |
| When was Simon Harris the Taoiseach? | PASS / answer | Both separate accepted episodes retained |

These answers were compared by **exact RDF identities and source intervals**
against independently written read-only RDF queries, not just HTTP status,
planner validity or generated SPARQL. All requests returned HTTP 200; the
application's `data-outcome` and actual result rows distinguished answers from
safe nonanswers.

The final five verbatim original/comparison requests were repeated after A3;
all preserved the checked identities and intervals. Across the 17 distinct
originals, comparisons, paraphrases and constraint controls below there were
**nine evidenced answers and eight safe unsupported outcomes**. None of the
negative controls returned result rows.

### A1 — current Fianna Fáil Senators

The complete typed Seanad chronology had 31 records; House-owned
`dct:temporal` / `dcat:startDate` / `dcat:endDate` evidence uniquely selects
`https://data.oireachtas.ie/ie/oireachtas/house/seanad/27`, starting 2025-01-29
with no recorded end. The exact affiliation is
`https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail`,
linked from `https://data.oireachtas.ie/ie/oireachtas/party/seanad/27/Fianna_Fáil`.

The answer is Aidan Davitt, Alison Comyn, Anne Rabbitte, Dee Ryan, Diarmuid
Wilson, Fiona O'Loughlin, Imelda Goldsboro, Joe Flaherty, Lorraine Clifford-Lee,
Margaret Murphy O'Mahony, Mark Daly, Mary Fitzpatrick, Niall Blaney, Ollie Crowe,
Pat Casey, Paul Daly, Robbie Gallagher, Shane Curley and Teresa Costello.

For all 19, the recorded SeanadMembership and linked PartyMembership intervals
start 2025-01-29 and have no recorded end; both independently contain asOf.
Exact Member IDs (suffixes of `https://data.oireachtas.ie/ie/oireachtas/member/id/`):

```text
Aidan-Davitt.S.2016-04-25
Alison-Comyn.S.2025-01-29
Anne-Rabbitte.D.2016-10-03
Dee-Ryan.S.2025-01-29
Diarmuid-Wilson.S.2002-09-12
Fiona-O'Loughlin.D.2016-10-03
Imelda-Goldsboro.S.2025-01-29
Joe-Flaherty.D.2020-02-08
Lorraine-Clifford-Lee.S.2016-04-25
Margaret-Murphy-O'Mahony.D.2016-10-03
Mark-Daly.S.2007-07-23
Mary-Fitzpatrick.S.2020-06-29
Niall-Blaney.D.2002-06-06
Ollie-Crowe.S.2020-03-30
Pat-Casey.D.2016-10-03
Paul-Daly.S.2016-04-25
Robbie-Gallagher.S.2016-04-25
Shane-Curley.S.2025-01-29
Teresa-Costello.S.2025-01-29
```

This is an active-at-date result over local recorded evidence, not certification
of a complete current roster.

### A2 — Labour in the 25th Seanad

The exact term is `https://data.oireachtas.ie/ie/oireachtas/house/seanad/25`,
with House dates 2016-04-25–2020-03-29. The exact party occurrence is
`https://data.oireachtas.ie/ie/oireachtas/party/seanad/25/Labour_Party`, linked to
`https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party`.

| Member | Exact Member ID suffix | Membership interval | Party interval |
|---|---|---|---|
| Aodhán Ó Ríordáin | Aodhán-Ó-Ríordáin.D.2011-03-09 | 2016-04-25–2020-02-08 | 2016-03-10–2020-02-08 |
| Denis Landy | Denis-Landy.S.2011-05-25 | 2016-04-25–2017-11-28 | 2016-03-10–2017-11-28 |
| Ged Nash | Gerald-Nash.D.2011-03-09 | 2016-04-25–2020-02-08 | 2016-03-10–2020-02-08 |
| Ivana Bacik | Ivana-Bacik.S.2007-07-23 | 2016-04-25–2020-03-29 | 2016-03-10–2020-03-29 |
| Kevin Humphreys | Kevin-Humphreys.D.2011-03-09 | 2016-04-25–2020-03-29 | 2016-03-10–2020-03-29 |

All endpoints are recorded `xsd:dateTime` midnight values. Each overlap starts
at 2016-04-25 and ends at the membership end shown. The returned evidence retains
the Member, membership, episode, party, affiliation and term IRIs. Distinct
source episodes are not merged. Historical completeness is not certified;
missing/uncertain evidence is unavailable, not a genuine negative.

### A3 — Simon Harris's latest recorded Taoiseach episode

Member: `https://data.oireachtas.ie/ie/oireachtas/member/id/Simon-Harris.D.2011-03-09`.
Reviewed NamedOffice: `https://data.oireachtas.ie/office/o-000001`.
Both accepted episodes are in the corresponding Member-owned graph:

| Holding suffix after Member IRI | Start | End |
|---|---|---|
| `#office-holding-5613228dcc3c98ed2b4828697e417c13c6b74c7af7fd5c2ee9642c5b87053077` | 2024-04-09 | 2024-11-08 |
| `#office-holding-006a66cfbe57cac87c660210a72dd6f1dc781f22430fcb31e5b94d48e8af259f` | 2024-11-29 | 2025-01-22 |

The second is uniquely latest in these records. Its DateRange IRI is the holding
IRI plus `#date-range`; endpoints are midnight `xsd:dateTime`. The original
comparison still returns both rows. No episode is merged across the source gap,
and no inference is made about service during that gap or complete career
coverage. The response prominently says **not a proven historically last tenure**.

### Live paraphrase and constraint controls

Each of these returned an answer with the same qualifying identities/episodes:

- “Which Fianna Fáil Senators are there?” — 19;
- “Which Labour Party Senators served during the 25th Seanad?” — the same five;
- “How many Labour Senators were in the 25th Seanad?” — five distinct Members;
- “When did Simon Harris most recently serve as Taoiseach?” — the same latest
  accepted episode and explicit local-evidence qualification.

Each of these returned `unsupported_capability`, with no answer substituted:

- “Who are the Fianna Fáil Senators on 2020-01-01?”
- “Who were the Labour Senators in the 25th Seanad on 2018-01-01?”
- “Who were the Labour Senators in the 25th and 26th Seanad?”
- “Who were the Labour and Fine Gael Senators in the 25th Seanad?”
- “Who are the Fianna Fáil Senators who serve on a committee?”
- “When was Simon Harris last Taoiseach in 2024?”
- “When was Simon Harris last Taoiseach while in Fine Gael?”
- “Who were the Fianna Fáil Senators?” — no present default for past tense.

## Independent evidence query

This hand-written selection was used independently of application compilers,
with `(term number, identity)` set to `(27, fianna-fail)` and
`(25, labour-party)`. All rows were retained before Python checked required
starts, finite-end ordering, inclusive overlap and (for A1) both active-at-date
tests. The returned identity sets and all displayed interval/source identities
were asserted equal to the `/ask` results. There were 19 and five evidence rows,
respectively, below the endpoint's page bound. Separate queries inspected every
typed SeanadTerm with optional dates (31 rows), term-scoped parties and exact
Simon Harris/NamedOffice accepted holdings (two rows).

```sparql
PREFIX a: <https://data.oireachtas.ie/ontology#>
PREFIX m: <https://data.oireachtas.ie/ontology/members#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?graph ?member ?name ?membership ?mr ?ms ?me
       ?episode ?party ?identity ?pr ?ps ?pe WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term a a:SeanadTerm; a:termNo 25 .
  }
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?party a m:ParliamentaryParty; m:activeDuringTerm ?term .
  }
  GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> {
    ?party m:hasPoliticalAffiliationIdentity ?identity .
    VALUES ?identity {
      <https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party>
    }
  }
  GRAPH ?graph {
    ?member a a:Member; foaf:name ?name;
      m:hasMembersMembership ?membership, ?episode .
    ?membership a m:SeanadMembership; m:inHouseTerm ?term .
    ?episode a m:PartyMembership; m:inOireachtasMembership ?membership;
      m:isPartyMembershipOf ?party .
    OPTIONAL { ?membership m:hasMembershipDateRange ?mr .
      OPTIONAL { ?mr m:StartDate ?ms } OPTIONAL { ?mr m:EndDate ?me } }
    OPTIONAL { ?episode m:hasMembershipDateRange ?pr .
      OPTIONAL { ?pr m:StartDate ?ps } OPTIONAL { ?pr m:EndDate ?pe } }
  }
  FILTER(STRSTARTS(STR(?graph), "https://data.oireachtas.ie/graph/member/"))
} ORDER BY ?member ?membership ?episode
```

## Verification and limitations

Focused party checks: **196 passed**. Final focused office checks: **62 passed**.
There are **57 new deterministic regression cases**: 27 for Seanad party
selection and 30 for office episode selection, including raw malformed date
bindings that rdflib would otherwise normalize before testing.

The complete existing NLQ suite passed: **1,144 passed, 2 skipped**. The skipped
NLQ cases require an opt-in disposable capture-backed Fuseki run or an optional
preserved source capture.

The final full-repository run passed: **2,276 passed, 26 skipped**, plus
**23 subtests passed**. The first broad run caught a test-fixture issue in a new
case: rdflib normalized an intentionally truncated timestamp before the reader
saw it. The regression now supplies the invalid raw endpoint binding directly;
both the focused suite and fresh full run pass without weakening the lexical
validation assertion. No acceptance assertion was weakened, and no source or
golden fixture was changed.

Commands used from this worktree (dependencies installed with
`uv sync --locked --extra test --extra nlq`):

```text
.venv/bin/python -m pytest tests/test_nlq*.py -q --tb=short
.venv/bin/python -m pytest tests -q --tb=short
.venv/bin/python tests/validate.py
git diff --check
```

Optional mutation-capable disposable-Fuseki/capture acceptance and production
release-gate tests were not enabled. The configured local dataset was used only
for read-only `/ask` and independent evidence checks, not as a disposable write
target. The optional preserved source capture is also absent from this worktree.

The ordinary Phase 0 ontology validator passed: **2,586 triples**, HermiT
completed successfully. No semantic-verification experiments or PR #27
acceptance campaign were rerun.

The generated query-schema context is 47,931 / 48,000 characters. The existing
context cap was not raised; only 69 characters of headroom remain for future
query-schema additions.

Remaining limits are deliberate: the model can still vary; the grammar and
supported combinations remain bounded; local source completeness is not
certified. No new authoritative historical-completeness claim was made.
Group B remains a separate human approval gate and was not started.
