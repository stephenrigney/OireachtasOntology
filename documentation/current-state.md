# OireachtasOntology: current system overview

This page describes the repository's integrated state on `master` (2026-10-07).
It is the concise current-state entry point; phase plans, tranche reports and
benchmarks remain preserved as design and implementation history. See
[documentation navigation](../README.md) for the repository map.

## What the system contains

The project combines an OWL ontology, source-to-RDF mappings, deterministic
Python ETL and validation, and Fuseki publication/query support. The ontology
reuses ELI/ELI-DL, W3C ORG, FOAF, SKOS and other vocabularies where useful.
The ETL implements the ontology and mapping contracts; it is not a separate
authority for their semantics.

```text
Oireachtas API / preserved source evidence
                 -> endpoint transformation -> RDF validation
                 -> owner-specific named graph publication -> Fuseki/SPARQL
```

Production publication follows validate-before-replace and graph ownership
boundaries. Raw source capture, operational state and RDF have distinct roles;
Fuseki is a published projection, not the authoritative store of source
evidence. The detailed architecture and phase-level design are in
[the ETL plan](etl-plan.md), [incremental refresh/state contract](incremental-refresh-state.md),
and [Fuseki User Guide](fuseki-user-guide.md).

## Conceptual model and principal relationships

The ontology models durable institutions and identities separately from
time-bounded participation and source observations. The principal patterns are:

| Concept | Current model |
|---|---|
| Oireachtas and Houses | The enduring Oireachtas is a named individual. `agents:ParliamentaryBody` is a class, and `agents:House` models enduring Dáil and Seanad institutions. Houses own numbered `agents:HouseTerm` individuals (typed `agents:DailTerm` or `agents:SeanadTerm`). House and term are distinct identities; a term is not an organisation. See [House model](house_model.md). |
| Parliamentary body | `agents:ParliamentaryBody` represents enduring parliamentary formal organisations; it is not the Oireachtas singleton, a HouseTerm or the Government. |
| Government | The constitutional Government is `agents:Government`, distinct from House and term. Members' ministerial roles, the wider `members:GovernmentExecutive`, and the parliamentary whip bloc `members:GovernmentBenches` are separate tiers, not interchangeable meanings of “Government”. |
| People and memberships | `agents:Member` is the canonical person class. Dated `members:OireachtasMembership` records represent Dáil or Seanad service and connect a person to an enduring House and its particular term. `members:CommitteeMembership` is a separate membership type linking a Member to a Committee. A person can serve in different Houses and committees over a career. |
| Parliamentary collections | `members:ParliamentaryParty` and `members:IndependentMemberCollection` are term-scoped collections. Dated `ParliamentaryCollectionMembership` records connect a person's membership to the collection and containing Oireachtas membership. An independent collection is not a party; no ParliamentaryGroup is inferred from party or government status. |
| Offices and tenure | `members:NamedOffice` is an enduring particular office; `members:AdministrativeUnit` is a distinct institution. `members:OfficeHolding` records a person's dated tenure in one office. Reviewed office-type concepts—not generic OWL role classes—distinguish office categories. Qualifying holdings can support derived `agents:Government` `members:CabinetMembership` episodes. See [ministerial office design/status](phase-7-ministerial-offices.md). |
| Committees | `members:Committee` is an organisation with shared descriptive ownership. Committee membership and tenure are represented in the Member's membership graph. Committee instances are distinct from HouseTerms and are not created by copying committee descriptions into Member graphs. |
| Bills and legislation | ELI/ELI-DL resources represent a Bill's legislative process, source, lifecycle activities, versions and related document resources. The Bill graph owns Bill/process data and sponsor evidence; it does not own Member, Act or Debate descriptions. |
| Debates | The structured model follows Akoma Ntoso Works and Expressions, with debate records, sittings where supported, ordered sections, speeches, summaries, questions and divisions/votes. AKN XML is authoritative; transcript text is not copied into RDF. Questions and votes belong to their Debate record. Cross-resource identities are linked only where resolved evidence supports them. |

For the approachable topic-by-topic explanation of these relationships, see
the [ontology conceptual guide](wiki/Home.md), particularly its pages on
[Agents and institutions](wiki/Agents.md),
[Members and membership](wiki/Members.md),
[offices and administrative units](wiki/Departments.md),
[Bills](wiki/Bills.md), and [Debates](wiki/Debates.md).

These are a guide to the implemented model, not a claim that every ontology
class is populated in every dataset. The module inventory is in
[ontology/README.md](../ontology/README.md); field-level meanings and status
are in [mapping notes](mapping_notes.md) and [`mappings/`](../mappings/).

## Data coverage and limits

“Implemented” below means the transform/model and relevant validation exist; it
does not mean a complete production dataset is currently loaded. Local Fuseki
is populated only when an operator explicitly loads data. Debates' bounded
transformation and publication implementation likewise does not mean its
approved first production scope has been ingested.

| Dataset / capability | Current state and important boundary | Detailed reference |
|---|---|---|
| Houses and HouseTerms | ETL and fixed Houses graph are implemented. Includes enduring House and numbered term identities. | [Houses ETL](houses-etl.md), [House model](house_model.md) |
| Parties, constituencies and committees | Reference transformations and distinct owner graph families exist. Committee ownership was added to close nested Members-source coverage. The authoritative reference-coverage acceptance remains explicitly blocked by unresolved/ambiguous evidence; do not describe all historical observations as closed. | [ETL plan](etl-plan.md), [mapping notes](mapping_notes.md) |
| Members and memberships | Per-Member graphs include resolved Oireachtas, collection, constituency/panel, committee and office records. Ambiguous evidence is quarantined or remains under review; office holdings depend on accepted local resolutions. | [Members ETL](members-etl.md), [collection model](parliamentary-member-collection-model.md), [office design](phase-7-ministerial-offices.md) |
| Bills | Per-Bill graph lifecycle ETL and separate local sponsor reconciliation are implemented. Sponsor role labels alone do not establish a person or office identity; Act descriptions remain separately owned/deferred. | [Phase 4 legislative lifecycle](phase-4-legislative-lifecycle.md), [Bill sponsor reconciliation](bill-sponsor-reconciliation.md) |
| Debates | Tranches 1–4 implement the bounded source/transformation/validation/replay and opt-in supplied-batch publication path. Approved initial production scope: Dáil, Seanad and committee Works dated 2011-01-01 onward, excluding written answers. Production readiness is still open; enumeration, exact quarantine inventory and approved operational limits are prerequisites. | [Phase 7 Debates status](phase-7-debates.md), [production benchmark](debates-production-benchmark.md), [identity contract](debates-identity-contract.md) |
| External identities | Reviewed external links are separately owned and replaceable; external reconciliation can lag or fail independently of authoritative local RDF. Label similarity alone is not identity evidence. | [Institutional reconciliation](institutional-reconciliation.md), [Member reconciliation](member-reconciliation.md), [Party reconciliation](party-reconciliation.md) |
| NLQ | Experimental browser application for a limited contract-defined subset of the locally available RDF; it uses read-only validated SPARQL and never publishes data. | [Canonical NLQ user/developer guide](../poc/nlq/README.md) |

Not all source API fields are mapped, not all mapped vocabulary has populated
instances, and not every historical identity conflict has a safe resolution.
There is no general OWL reasoning at query time. The ETL's precise support,
quarantine and acceptance boundaries remain in its detailed contracts rather
than being implied by this summary.

## Identifiers, reconciliation and graph ownership

* **Stable local identity:** source IRIs/codes are retained when their meaning
  matches the local entity contract. House IRI and HouseTerm IRI are different
  identities. Member and Bill graph identifiers are deterministic; Debates
  Work/Expression/graph identifiers follow the explicit AKN identity contract.
* **Reconciliation:** external identity links require reviewed evidence and are
  stored separately from source-derived descriptions. Local office registries
  contain positively reviewed identities; a label or external identifier does
  not mint an office or administrative unit. Conflicts are surfaced for review,
  not silently settled by fuzzy matching or a majority vote.
* **Graph ownership:** reference descriptions use fixed owner graphs; Members,
  Bills and Debates use replaceable per-resource graphs. Shared office and
  administrative-unit descriptions and external/local reconciliation links
  have their own owners. Cross-graph joins reuse canonical resource IRIs;
  resource descriptions are not duplicated merely to make a join local.
* **Publication:** validate the complete candidate before replacement and
  verify publication. Incomplete source evidence cannot be treated as proof of
  absence. Fuseki's graph inventory depends on what has actually been loaded.

For exact graph names, refresh semantics, provenance, recovery and owner
contracts use [ETL plan](etl-plan.md),
[incremental refresh/state contract](incremental-refresh-state.md),
[office reconciliation](office-observation-reconciliation.md), and the
[NLQ query-schema contract](../poc/specs/query-schema-contract.json).

## Local development, operations and history

The [Fuseki User Guide](fuseki-user-guide.md) covers local store operation.
The [ETL plan](etl-plan.md) contains the design history and implementation
phase records; [Phase 5 operations](phase-5-refresh-operations.md) and the
[Phase 6 section of the plan](etl-plan.md#phase-6--production-hardening) record
current operational contracts and implementation status. Use the repository
root [README](../README.md) for validation commands and entry points.

For the natural-language query application, start with its canonical
[NLQ guide](../poc/nlq/README.md); this overview intentionally does not duplicate
its setup, examples, architecture or troubleshooting instructions.

Historical wiki pages, phase plans, tranche records, audits and benchmark
reports are retained as evidence of decisions and implementation, not as a
replacement for this summary. When a historical note conflicts with verified
current ontology, mappings or tests, prefer the current implementation and
raise unresolved semantic ambiguities for review rather than inferring them.
