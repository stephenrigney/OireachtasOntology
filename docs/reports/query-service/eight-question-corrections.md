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
