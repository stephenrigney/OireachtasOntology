# Oireachtas party identity inventory — human review

**Status: proposal only; no identity assertions are authoritative.** This review
uses only preserved Oireachtas data. The semantic distinction in the collection
model is retained: each source IRI is a term-scoped `members:ParliamentaryParty`,
not the enduring party itself. Names, codes, term context and dated membership
observations are candidate evidence only.

## Coverage and method

The record-level table is [`party-identity-inventory.csv`](party-identity-inventory.csv).
It inventories distinct, non-Independent party IRIs observed in the preserved
Member API captures under `data/raw/members/` (snapshot date 2026-10-04).
Repeated observations of the same source IRI are coalesced; their capture count
is retained. Identity key is the full source IRI, not `partyCode`. Independent
collections are excluded.

| Measure | Count |
|---|---:|
| Distinct eligible term-scoped source IRIs | 315 |
| Records placed in a proposed grouping | 314 |
| Explicitly unresolved records | 1 |
| Eligible records accounted for exactly once | 315 / 315 |
| Distinct proposed group labels, including the unresolved bucket | 37 |
| Independent records included | 0 |

The inventory is derived from preserved Member API records because these
captures contain term-linked party resources and dated party observations. It
does not claim to be an exhaustive historical Parties-endpoint harvest. The
preserved `data/raw/parties` captures are a current-term endpoint sample, not a
complete historic register. Source availability therefore bounds this review.

## Proposed identities and observed coverage

All periods below mean **observed House terms in this source snapshot**, not
party foundation or dissolution dates. Term-specific record lists, exact source
IRIs, labels, date endpoints and provenance occurrence counts are in the CSV.
Each exact-name grouping is only a proposal; it is not automatically validated
as one enduring identity. Gaps between observed terms are not interpreted as
cessation.

| Proposed grouping | Records | Observed House-term coverage | Review note |
|---|---:|---|---|
| Labour Party | 63 | Dáil 3–34 | Name/code family; review continuity and gaps. |
| Fianna Fáil | 60 | Dáil 4–34 | Name/code family; review continuity and gaps. |
| Fine Gael | 58 | Dáil 4–34 | Name/code family; review continuity and gaps. |
| Historical Sinn Féin (1st–6th Dáil) | 6 | Dáil 1–6 | Separate proposed identity. No continuity within these terms is assumed. |
| Modern Sinn Féin (from 1970; proposed) | 7 | Dáil 28–34 | Separate from historical Sinn Féin; name alone does not prove continuity. |
| Modern Sinn Féin (proposed; Seanad records) | 5 | Seanad 23–27 | Same-name Senate records; relationship to the proposed modern identity requires review. |
| UNRESOLVED — Sinn Féin intermediate/boundary | 1 | Dáil 16 | Boundary-crossing record; do not force into either identity. |
| All other proposed exact-name groupings | 115 | See CSV (House and term per row) | Provisional exact code/display-name groupings; review possible aliases, splits, mergers and successor relationships. |

The last aggregate consists of 30 separately named candidate groupings in the
CSV. Notable potential name/identity transitions requiring human review include
Cumann na nGaedheal / Fine Gael; National Progressive Democrats / Progressive
Democrats; Workers Party / Sinn Féin the Workers Party; Democratic Left / Labour
Party; Anti-Austerity Alliance–People Before Profit / People Before Profit
Alliance / People Before Profit–Solidarity; and Sinn Féin / Sinn Féin the
Workers Party. These are flagged as candidate relationships, not asserted
aliases or succession.

## Required human review / limitations

1. Decide whether proposed exact-name families represent enduring registered
   party identity across terms, Houses, spelling/code changes and gaps.
2. Review the Dáil 16 Sinn Féin record independently. It is not grouped with
   either the 1st–6th Dáil records or the modern Sinn Féin records.
3. Review Seanad Sinn Féin records (Seanad 23–27) against the proposed modern
   identity; the CSV does not silently equate House-specific collections.
4. Review every potential transition named above and any other apparent naming
   change in the record-level rows. A similar label, related membership dates,
   or repeated code cannot establish identity.
5. This report does not establish party start/end dates, consult external
   historical sources, make QID mappings, or create ontology assertions. No
   graph was published. The output remains at the human review gate.

Reproduce the inventory with:

```sh
python tools/party_identity_inventory.py --csv reports/party-identity-inventory.csv
```
