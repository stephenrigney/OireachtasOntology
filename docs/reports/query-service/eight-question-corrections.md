# Eight natural-language question corrections

This implementation repairs Query Service interpretation, identity lookup and
answer projection. It does not change ontology, ETL, source/golden fixtures or
publication. Tests execute the actual `/ask` route and compiled SPARQL against
small named-graph datasets; no LLM or complete-corpus bootstrap is required.

## Checkpoint 1

- Member lookup for party history and Bill sponsorship now applies a grounded
  name prefilter **before** the bounded result limit. Exact NFC/casefold name
  acceptance and distinct RDF identities determine resolution. A capped lookup
  cannot establish absence or uniqueness.
- Current representation resolves a unique Dáil from House-owned dates at the
  reference date and checks the Dáil membership's own interval. It does not
  require a previous term or guess a term ordinal. Expired/future memberships
  are excluded; missing/conflicting interval evidence fails closed.
- Career-wide representation projects constituency occurrences with their
  respective Dáil terms, without collapsing different occurrences by label.
- Ordinary party-history and sponsorship paraphrases reach the existing
  compilers. “Join” means recorded party membership, not a joining event.
  Semantic fallback can propose these implemented graphs and representation
  graphs, subject to closed local graph/projection validation and grounded
  mentions. Extra constraints cannot be silently discarded.
- Party history and sponsorship use bounded, deterministically ordered answer
  pages. A page boundary does not silently omit later Bills or episodes; the
  maximum pagination range fails closed without a partial answer.
- Sponsorship retains contract-2 BillDelivery/process/Participation paths and
  includes primary, supporting and unknown-primary evidence. Unknown primary
  status remains an explicit qualified outcome, not a removed sponsorship.

`tests/test_nlq_question_failures.py` records compact source-backed excerpts and
their capture locations. Waterford returns Mary Butler, David Cullinane, John
Cummins and Conor D. McGuinness in the dated 34th-Dáil fixture. Mary Lou McDonald
returns Dublin Central; Bertie Ahern returns Dublin Finglas (21st) and Dublin
Central (22nd–30th). Stephen Donnelly returns two reviewed enduring party
identities (Social Democrats and Fianna Fáil), excluding Independent; sponsorship
includes the recorded supporting Participation for Bill 2017/9. These are local
evidence claims, not certification of a live or complete historical dataset.

Checkpoint verification: 34 focused failure-class tests pass, including all
seven `/ask` questions; the existing Q06, Q23 and Member-composition tests pass
(42 tests), as do the contract/shared-term/Q06 checks (41 tests). Ontology
validation, including HermiT, passes (2,586 triples). The broader NLQ suite is
also run for delivery; no complete-corpus scan or dataset reload is needed.

The Checkpoint 1 broader NLQ run passed **757 tests, 1 skipped**.

## Checkpoint 2

The Government route grounds the **existing** emitted CabinetMembership pattern
in the Query Service contracts. It requires the enduring constitutional
Government target and CabinetMember role; OfficeHolding alone, GovernmentExecutive
and Minister-of-State-only evidence are not substitutes. No ontology, mapping,
ETL, office reconciliation or publication behavior changes.

An exact reviewed affiliation identity filters the party path. Cabinet and
party-episode intervals must both contain the reference date; the party episode
must also have contemporaneous containing parliamentary-membership and HouseTerm
evidence. Missing/conflicting dates fail closed. Members are deduplicated by RDF
identity while Cabinet episodes, party episodes and supporting holding identities
remain inspectable. Semantic fallback and ordinary Government paraphrases use
the same closed validated path.

The controlled source-backed Q3 fixture transforms Micheál Martin's captured
34th-Dáil Taoiseach observation using its **existing committed accepted office
decision** and registry type, then runs Member validation. It returns Micheál
Martin with Fianna Fáil affiliation and both dated episodes; this one positive
match is deliberately **not** claimed to be a full real-world party/Cabinet
roster. The existing Timmy Dooley source fixture and explicitly synthetic
adversarial cases exercise Minister-of-State-only exclusion, expired/future
memberships, incomplete coverage and uncertainty. No source fixture is altered.

### Live-data limitations

There is no accepted completeness marker for current office or party coverage in
the local query contracts. Accordingly, every positive Government answer says
that it contains **recorded matches, not a complete Government roster**. No
contemporaneous match is a source-coverage outcome, never a certified empty roster.
An old Cabinet/party record cannot establish current membership merely because
its person has a current parliamentary record. The local Fuseki service was not
running during delivery (loopback port 3030 refused connection); no dataset was
started, reloaded or reconciled to manufacture live coverage. Acceptance uses
the integrated `/ask` route with real compiled SPARQL over controlled named-graph
fixtures, not a live-data completeness claim.

Checkpoint 2 focused verification passes 21 Government tests, including a
same-calendar-day but non-overlapping party/Cabinet interval regression. Multiple
supporting holdings do not duplicate the Member answer. A separate pinned
raw-page test transforms and validates the actual captured Bill 2017/9, replaces
only its in-memory test graph, and verifies Stephen Donnelly's supporting
sponsorship through `/ask`; it also passes. This optional source replay reads
one known page and skips when that preserved capture is not installed. The
always-available source-excerpt tests remain the offline regression gate.

Final broader verification: `.venv/bin/python -m pytest -q tests
--disable-warnings` passed **1,911 tests, 25 skipped**, with **23 subtests
passed**. The final sponsorship coverage-message hardening was additionally
verified by the pagination-limit regression and existing Q23 suite (**16
passed**). `git diff --check` passed. Existing dependency deprecation warnings
remain; the skipped tests retain their normal optional integration prerequisites.
