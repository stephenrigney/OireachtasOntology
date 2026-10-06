# Phase 7 Tranche 5 — local Bill sponsor reconciliation

The Bill source graph owns its original `eli-dl:Participation` and unchanged
source `rdfs:label`. The independent local graph
`https://data.oireachtas.ie/graph/bill/{year}/{number}/office-reconciliation`
contains only supported links from those current Participations to reviewed
local `NamedOffice` identities and, when the source person and applicable Bill
time support it, accepted published `OfficeHolding` identities. It does not
describe any office, holding, person or Bill, and it never reads Wikidata or
office external-link assertions. Replacing this complete graph does not replace
the Bill core graph or any other graph.

Role text is matched to reviewed office aliases, not used to infer a person.
An explicitly supplied source person without an applicable, uniquely identified
holding may still have an office-only link. `bill.lastUpdated` is never a
holding date. Unknown or ambiguous identities and times remain review cases;
no additional offices are created for coverage. Review decisions and the
observation ledger record the current Participation IRI, source fingerprint,
candidate evidence, target and review version. A change to the Participation
may change its IRI: publication replaces the **entire** local Bill graph, so
no previous Participation link survives merely because the old subject is
absent from the new source.

Operator command: `oir-etl reconcile bills-local`. A fixture is a scoped
inspection source, never evidence that another Bill disappeared. Offline:

```text
oir-etl reconcile bills-local --fixture data/api_examples/bill.json --offline \
  --bill-state-file /tmp/oireachtasontology/bill-sponsors.sqlite \
  --output-nq /tmp/oireachtasontology/bill-sponsors.nq
```

For publication, first publish the current reviewed office registry and Bill
core graphs with `run offices` and `run bills` (and the applicable Members for
holding links). Then run `reconcile bills-local --fixture ... --publish` with
`--state-db`, `--office-state-file`, `--bill-state-file`, `--fuseki-gsp-url`
and `--fuseki-sparql-url` pointing to the same **isolated** dataset for tests.
Without a fixture, the command makes a complete Legislation source scan and
preserves its raw pages before any local publication. It uses no external
identity services. `--review-file` selects versioned human decisions (the
default file initially contains none). The CLI never modifies the review file.
Publication records a pending payload before PUT and marks it clean only after
exact graph verification; a failed or interrupted PUT remains dirty for replay.
An absent Bill in a **complete** source scan is persisted as missing/review
required and reported, never silently cleared or removed from the core or
local graph. A new Bill, changed sponsor text, reviewed registry alias or
relevant Member holding changes the sponsor input fingerprint when the local
command revisits it; no external queue is used. Candidate role text may
automatically accept a unique reviewed office but never a person or holding.
A holding link needs an explicit source person and a fingerprint-bound human
decision selecting one current Bill stage/event date and one uniquely
person/date-qualified, published Member holding. Date-only source precision
is corroborated against the reviewed Member occurrence ledger **and** the
verified Member graph; a normalized midnight RDF instant by itself cannot
establish date-only source precision. Changed Participation identities and
stale decisions become review-required and lose their old links on complete
local-graph replacement. `rejected` and `unresolved` also emit no links.
Unresolved/review-required cases return exit code 1 after safe publication;
input, evidence or state corruption fails closed with an error. The reviewer
can inspect `bill-sponsor` observation keys, evidence fingerprints and event
dates from the state report before supplying a reviewed decision.

The observation key is based on the source-derived Participation identity,
not array position; a changed role/person/primary value creates a new key and
retains the old observation as absent review evidence. The full Bill source
hash and reviewed registry hash conservatively invalidate all observations
for that Bill when either changes, even where the final local RDF is
unchanged. Office display labels are reviewed local identities independent of
alias validity; specifically bounded aliases require a reviewer-selected Bill
event date to support a match, while an exact enduring office display label
may support an office-only match without inferring a historical holder.
Neither `lastUpdated` nor external-office links can authorize a holding.

No Tranche 6 final acceptance, Debate work or production publication is
performed by this tranche.

## Verification and deliberately narrow coverage

The checked-in Bill fixture (`2025/60`) has `Minister for Finance` role text
and a null `sponsor.by.uri`. It produces exactly one office-only link to the
reviewed `o-000003` office and no person or holding assertion. A separate
synthetic, fixture-backed review supplies an explicit Member IRI, a selected
Bill stage/event date, and a verified published date-only Taoiseach holding;
only that positive combination produces the `o-000001` office and matching
OfficeHolding links. These synthetic test identities are not claims about the
real Bill's sponsor. Rejected, unresolved, stale and overlapping-holding
cases emit no guessed link. A changed Participation subject is cleared by
complete local graph PUT while its core Bill label remains unchanged.

The acceptance run used a disposable Fuseki 5.1 dataset, not production:
exact post-PUT graph checks and unchanged Bill core, Member, office,
administrative-unit, office external-link, Debate and unrelated Bill-local
graphs passed. Pinned-Java ontology validation (2,504 triples), mapping
integrity, the focused local/office/Bill tests, and the full suite (630 passed,
23 subtests, no optional skips with the isolated dataset) passed. No local
office registry expansion or external-identity lookup was used.
