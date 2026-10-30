# Political affiliation identities

## Purpose and boundary

`members:PoliticalAffiliationIdentity` is the implemented local identity for an
enduring, recognised political affiliation represented in Oireachtas member
records. It may describe a political party, an alliance, a combined
electoral/parliamentary affiliation, or another recognised affiliation. The
user-facing model is not a register of Electoral Commission registration: an
identity does not claim that every target is a formally registered
organisation, nor that an alliance's constituent organisations are identical
to it.

The identity is additional to, not a replacement for, the existing
term-scoped `members:ParliamentaryParty`. The latter remains the Oireachtas
source-backed collection with its authoritative source IRI, original
`partyCode`, `showAs` label and term. A reviewed local link is expressed as
`members:hasPoliticalAffiliationIdentity`:

```text
term-scoped ParliamentaryParty
    -- hasPoliticalAffiliationIdentity --> local enduring affiliation identity
    -- recognisedAsParty ----------------> reviewed external registered-party identity (existing)
```

These properties express different assertions. The local identity link is a
curated, user-oriented grouping; `members:recognisedAsParty` is the existing
external reconciliation link and must not be redefined to point at the local
identity. Neither property makes the term-scoped collection identical to its
target. The local link must not be inferred from label equality, nor imply
legal registration, formal parliamentary-group recognition, succession, or
constituent membership.

## Identity and naming policy

Stable local identifiers use
`https://data.oireachtas.ie/ie/oireachtas/political-affiliation/{id}`.
The final path segment is a permanent, lowercase ASCII registry key, not a
source party code, term number, date, label slug, or external identifier.
Once assigned it is not changed when preferred labels or aliases are edited.
The identity registry supplies the preferred label and unscoped aliases.
Original source labels and source IRIs remain on their term-scoped records;
aliases do not rewrite those records.

Aliases are plain, non-time-bound labels in this tranche. Where one alias
(`Sinn Féin`, for example) occurs on multiple intentionally distinct
identities, it is ambiguous display/search evidence only, never a key or an
automatic association. Do not add time-bounded alias machinery now.

## Decisions from the user review

`reports/party-identity-decisions.json` is the versioned, reproducible
record-level register. Every inventory row is keyed by its complete source IRI
and has exactly one outcome: accepted association, unresolved association, or
exclusion. The generator is `tools/party_identity_decisions.py`; run
`python tools/party_identity_decisions.py` from any directory in the checkout.
It reads the preserved review inventory, sorts records by full source IRI,
checks its reviewed SHA-256 and 315 unique rows, and writes stable JSON. The
digest guard means a new/edited source row fails closed until reviewed. No
source record is changed.

Accepted identity definitions (aliases are not time-scoped):

| Registry key | Preferred label | Aliases / assigned source records |
|---|---|---|
| `sinn-fein-pre-independence` | Sinn Féin (Pre-Independence) | Sinn Féin; 1st–3rd Dáil records |
| `sinn-fein-anti-treaty` | Sinn Féin (Anti-Treaty) | Republican; Sinn Féin; 4th–6th Dáil Sinn Féin records and 4th Dáil Republican records |
| `sinn-fein-1957` | Sinn Féin (1957) | Sinn Féin; 16th Dáil record |
| `sinn-fein` | Sinn Féin | 28th Dáil onward and 23rd–27th Seanad records |
| `workers-party` | Workers Party | Sinn Féin the Workers Party and Workers Party records; one identity per the reviewed 1982 name change |
| `people-before-profit-solidarity` | People Before Profit–Solidarity affiliation | All six reviewer-provided variants, plus source spellings; Anti-Austerity Alliance–People Before Profit and People Before Profit-Solidarity records |
| `people-before-profit-alliance` | People Before Profit Alliance | Kept distinct from the combined AAA/Solidarity–PBP affiliation |
| `business-and-professional-group` | Business and Professional Group | Both term-scoped records; included by reviewer decision |

The first-pass approved identity labels are: 100% RDR; Aontú; Business and
Professional Group; Clann na Poblachta; Clann na Talmhan; Cumann na
nGaedheal; Democratic Left; Farmers Party; Fianna Fáil; Fine Gael; Green
Party; Independent Ireland; Independents 4 Change; Irish Worker League;
Labour Party; National Centre Party; National Labour Party; National League
Party; National Progressive Democrats; People Before Profit Alliance; the
combined People Before Profit–Solidarity affiliation; Progressive Democrats;
Renua; the four Sinn Féin identities above; Workers Party; Social Democrats;
Socialist Labour Party; Socialist Party; Workers and Unemployed Action; and
Democratic Socialist Party.
The record-level associations for every identity are in the JSON register.
For these reviewed records, the first-pass same-label groupings are approved;
this is not permission to infer an association for a future or otherwise
unreviewed source record.

The source record named `Republican` in the 4th Dáil is associated with
`sinn-fein-anti-treaty`; its own ParliamentaryParty identity and label remain
`Republican`. The five Sinn Féin records in the 23rd–27th Seanads are now
explicitly approved for modern Sinn Féin. The combined AAA/Solidarity–PBP
identity is distinct from both People Before Profit Alliance and Socialist
Party. The Sinn Féin the Workers Party / Workers Party records share one
identity; this identity remains distinct from all four Sinn Féin identities.
Other reviewed separations remain explicit: Cumann na nGaedheal / Fine Gael,
National Progressive Democrats / Progressive Democrats, Democratic Left /
Labour Party, and National Labour Party / Labour Party. No
predecessor/successor relationships are inferred.

The 23rd, 25th and 26th Dáil records named Democratic Socialist Party are
associated with one `democratic-socialist-party` identity by explicit user
approval. This does not associate them with Democratic Left, Socialist Party,
Socialist Labour Party or other similarly named identities.

## Accounting and review boundary

The current inventory has 315 distinct non-Independent term-scoped records.
The generated register assigns 314 records to 33 local identities, excludes
the one Ceann Comhairle office record, and has no unresolved associations.
Every source IRI is present exactly once. The Democratic Socialist Party rows
from the 23rd, 25th and 26th Dáils now share one identity by explicit user
approval; the identity is not merged with similarly named parties.

The generator pins the exact inventory byte digest and fails closed if the
inventory changes. A future source record is not covered by these approvals:
it requires an explicit decision keyed by its complete source IRI, even when
its label matches an existing identity.

Explicit separations above are constraints on later decisions, not claims that
the associated organizations are related. Business and Professional Group is
included as directed. Ceann Comhairle and Cathaoirleach are excluded as
parliamentary offices (the current inventory contains one Ceann Comhairle
record and no Cathaoirleach record). Date discrepancies and invalid/out-of-term
affiliation intervals remain source-data limitations; they neither split nor
merge identities.

## Implemented publication and Query Service

The approved registry and source-IRI associations are implemented as deterministic reviewed enrichment. `members:PoliticalAffiliationIdentity` and `members:hasPoliticalAffiliationIdentity` are declared in `ontology/members.owl.ttl`. Identity descriptions and links are published together in `https://data.oireachtas.ie/graph/political-affiliations/identities`, separate from authoritative Parties and Members graphs. Publication fails closed on changes to the reviewed inventory or association register and verifies the complete replaced graph. See [`political-affiliation-publication.md`](../reference/graph-publication-political-affiliations.md).

Query Service Q06 follows dated Member PartyMembership records through term-scoped ParliamentaryParty collections to reviewed local identities, and uses their English preferred labels. It excludes Independent collections and does not resolve identities from labels or use external `recognisedAsParty` links. Its acceptance evidence is synthetic, not proof of production historical completeness; see [`query-service-q06-slice.md`](../reports/query-service/q06-political-affiliation-evidence.md).
