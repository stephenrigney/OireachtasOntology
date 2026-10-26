# Political affiliation identities

## Purpose and boundary

`members:PoliticalAffiliationIdentity` is the proposed local identity for an
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
`partyCode`, `showAs` label and term. A reviewed local link is proposed as
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

Proposed stable local identifiers use
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
checks the expected 315 unique rows and writes stable JSON. No source record is
changed.

Accepted identity definitions (aliases are not time-scoped):

| Registry key | Preferred label | Aliases / assigned source records |
|---|---|---|
| `sinn-fein-pre-independence` | Sinn Féin (Pre-Independence) | Sinn Féin; 1st–3rd Dáil records |
| `sinn-fein-anti-treaty` | Sinn Féin (Anti-Treaty) | Republican; Sinn Féin; 4th–6th Dáil Sinn Féin records and 4th Dáil Republican records |
| `sinn-fein-1957` | Sinn Féin (1957) | Sinn Féin; 16th Dáil record |
| `sinn-fein` | Sinn Féin | 28th Dáil onward records; Seanad assignment is unresolved |
| `workers-party` | Workers Party | Sinn Féin the Workers Party and Workers Party records; one identity per the reviewed 1982 name change |
| `people-before-profit-solidarity` | People Before Profit–Solidarity affiliation | All six reviewer-provided variants, plus source spellings; Anti-Austerity Alliance–People Before Profit and People Before Profit-Solidarity records |
| `people-before-profit-alliance` | People Before Profit Alliance | Kept distinct from the combined AAA/Solidarity–PBP affiliation |
| `business-and-professional-group` | Business and Professional Group | Both term-scoped records; included by reviewer decision |

The source record named `Republican` in the 4th Dáil is associated with
`sinn-fein-anti-treaty`; its own ParliamentaryParty identity and label remain
`Republican`. The combined AAA/Solidarity–PBP identity is distinct from both
People Before Profit Alliance and Socialist Party. Socialist Party records
remain unresolved as to their own cross-term identity, but must not be
associated with the combined affiliation. Ceann Comhairle and Cathaoirleach
records are excluded as parliamentary offices, not political affiliations.

The review's parenthetical “Seanad terms should:” has no answer. Therefore no
Seanad Sinn Féin source records are assigned to one of the four identities by
this register; the five Seanad 23rd–27th term records remain unresolved. The
initial inventory proposal is not used to fill that gap.

The reviewed separation decisions are retained: Historical/pre-Independence,
Anti-Treaty, 1957 and modern Sinn Féin are four identities; Sinn Féin the
Workers Party is not Sinn Féin; Cumann na nGaedheal is not Fine Gael; National
Progressive Democrats is not Progressive Democrats; Democratic Left is not
Labour Party; National Labour Party is not Labour Party. The register does not
create successor/predecessor links.

## Accounting and unresolved identity work

The current inventory has 315 distinct non-Independent term-scoped records.
The generated register assigns 29 records to eight local identities, excludes
the one Ceann Comhairle office record, and leaves 285 affiliations unresolved
for identity association. Every source IRI is present once. The unresolved
records are still affiliations (the user's default classification); they are
not rejected as parties and must not be assigned by same-name matching. In
particular, the initial review's proposed groupings do not by themselves
settle continuity for the other recurring names. Their cross-term associations
remain explicit future review, not hidden assumptions in this register.

Explicit separations above are constraints on later decisions, not claims that
the associated organizations are related. Business and Professional Group is
included as directed. Date discrepancies and invalid/out-of-term affiliation
intervals remain source-data limitations; they neither split nor merge
identities.

## Minimum implementation tranche after this decision

1. **Ontology:** add `members:PoliticalAffiliationIdentity` and the local
   ParliamentaryParty-to-identity property; document domain/range and the
   distinction from `recognisedAsParty`. Do not declare all identities
   registered organizations or assert `owl:sameAs`/temporal specialization.
2. **Registry and reconciliation:** load the reviewed identity definitions
   and full-source-IRI associations as deterministic reviewed data. Keep the
   existing term-scoped source IRI as key; retain unresolved and excluded
   outcomes, fail on duplicate/missing/unknown keys, and do not infer from
   labels. Reuse existing Party reconciliation validation, review, audit and
   recovery machinery rather than introducing another state subsystem.
3. **RDF ownership/publication:** leave authoritative Parties and Member graphs
   untouched. Reuse the existing replaceable derived-enrichment publication,
   graph-validation and whole-graph-verification mechanisms. The graph IRI and
   ownership for local identity descriptions/links are not decided here; settle
   them against the ETL plan before coding, escalating if a new ownership rule
   is required.
4. **Query Service:** extend the existing vocabulary/capability allow-list and
   query examples so users can retrieve term-scoped parties by their local
   identity and preferred label/aliases. Preserve the source term and label in
   results, distinguish this local link from external `recognisedAsParty`, and
   do not treat ambiguous aliases as unique identifiers. Update its query
   contract and focused tests.

Implementation is deliberately not part of this decision tranche. The exact
graph name/ownership, registry file schema and Query Service query surface are
implementation details to fit existing mechanisms; any change to identity
meaning or a new ownership rule requires review before implementation.
