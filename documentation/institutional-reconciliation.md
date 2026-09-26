# Phase 4.5 Tranche 3 — Institutional reconciliation

## Status

This document records the approved semantic and architectural contract for
Phase 4.5 Tranche 3.

Tranche 1 established the authoritative local institutional identities and is
complete. Tranche 2 defines the generic reconciliation architecture that
Tranche 3 must reuse, but its implementation is not yet merged into
`master` at the time this note is written. Tranche 3 implementation must
therefore not freeze policy interfaces, state schemas, review-file envelopes,
CLI shape or final external-link graph IRI syntax until the Tranche 2
reconciliation refactor has landed and been reviewed.

The semantic decisions in this document are independent of those integration
details.

## Purpose

Tranche 3 reconciles authoritative local Oireachtas institutional identities
to reviewed external authority identities without conflating:

- ontology classes with institution individuals;
- enduring institutions with numbered parliamentary terms;
- the modern constitutional institutions with historical or revolutionary
  predecessors; or
- identity with label similarity, topical relation or organisational
  association.

External identity data is derived enrichment. It must remain operationally and
semantically separate from the authoritative local institutional model.

## Authoritative local model

The following Tranche 1 identities are settled and are not reopened by this
tranche.

### Enduring Oireachtas

```text
https://data.oireachtas.ie/oireachtas
```

This is the enduring Oireachtas individual and an instance of
`agents:ParliamentaryBody`.

### Enduring Houses

```text
https://data.oireachtas.ie/house/dail
https://data.oireachtas.ie/house/seanad
```

These are enduring `agents:House` identities. They are distinct from every
numbered Dáil or Seanad term.

### Numbered House terms

Numbered terms are instances of `agents:HouseTerm` (more specifically
`agents:DailTerm` or `agents:SeanadTerm`) and are linked to the enduring
House through `agents:termOf`.

For example:

```text
33rd Dáil
    agents:termOf
        enduring Dáil Éireann
```

A HouseTerm is not a temporal spelling of the House IRI and is not identical
to the enduring House.

### Government

The enduring constitutional Government resource is:

```text
https://data.oireachtas.ie/government
```

It is a separate `org:FormalOrganization`, not a ParliamentaryBody, and is
linked to the enduring Dáil with `agents:responsibleTo`.

The generic Government Bill-source concept is a separate controlled concept
and is not an institutional reconciliation target in this tranche.

President modelling remains deferred.

## Scope

The initial Tranche 3 reconciliation targets are exactly:

```text
https://data.oireachtas.ie/oireachtas
https://data.oireachtas.ie/house/dail
https://data.oireachtas.ie/house/seanad
```

HouseTerm reconciliation is explicitly deferred from the initial Tranche 3
runtime implementation.

The implementation must nevertheless include semantic and regression tests
that prevent any HouseTerm from being conflated with its enduring House or
with an external identity for that enduring House.

A later follow-on may add HouseTerm reconciliation where an external authority
contains an identity for the exact numbered term.

## External authority hierarchy

### Wikidata

Wikidata is the primary external identity authority for this tranche.

The first accepted Wikidata identity for each local institution requires
explicit human review. Candidate strength, exact label agreement or a seemingly
obvious organisational relationship is not sufficient for automatic
acceptance.

The approved initial review candidates are:

| Local institution | Initial Wikidata candidate |
|---|---|
| Oireachtas | `Q129821` |
| Dáil Éireann | `Q651981` |
| Seanad Éireann | `Q1127591` |

These QIDs are review candidates, not hard-coded identity truths. The
reconciliation implementation must not treat these identifiers as accepted
merely because they appear in this document. Acceptance occurs only through
the reviewed reconciliation decision.

A reviewer must evaluate the external item's current meaning at the time of
acceptance, including its type, jurisdiction, history and relationships.

### Wikipedia

Wikipedia enrichment is downstream from an accepted Wikidata identity.

Where the accepted Wikidata item has a Wikipedia sitelink and that article is
genuinely about the local institution itself, the local institution may be
linked with:

```turtle
foaf:isPrimaryTopicOf
```

A sitelink to a list, historical predecessor, category, broader topic or other
non-identical subject must not be published merely because it is reachable
from Wikidata.

Independent fuzzy or title-based Wikipedia reconciliation is out of scope.

### DBpedia

DBpedia enrichment is deferred from the initial Tranche 3 implementation.

The architecture may support it later, but any future institutional DBpedia
link must be derived only after an accepted primary identity and may use
`owl:sameAs` only where the DBpedia resource is independently established to
denote the same institution.

No independent fuzzy or title-based DBpedia matching is permitted.

## Identity predicates

### `owl:sameAs`

`owl:sameAs` is permitted only where the local resource and external
resource denote the same individual institution.

For the initial targets this means:

```text
enduring Oireachtas
    owl:sameAs
        same enduring external Oireachtas identity

enduring Dáil
    owl:sameAs
        same enduring external Dáil identity

enduring Seanad
    owl:sameAs
        same enduring external Seanad identity
```

`owl:sameAs` must not be used merely because:

- labels are equal or similar;
- one resource is historically related to another;
- one institution succeeds or replaces another;
- one resource is a class or category describing the other;
- one external item represents a numbered parliamentary term; or
- an external page discusses the institution.

### `foaf:isPrimaryTopicOf`

`foaf:isPrimaryTopicOf` may link a local institution to a Wikipedia article
only when the article's primary topic is that institution.

It must not be used for an article whose primary topic is a historical
predecessor, a numbered term, a list, a category or a broader/narrower related
entity.

### Predicates not to use as uncertainty fallbacks

Unproven identity must remain unresolved or reviewable. Tranche 3 must not use
weaker predicates merely to force publication of a candidate.

In particular, do not substitute:

- `skos:exactMatch`;
- `rdfs:seeAlso`; or
- `prov:specializationOf`

for an unresolved institutional identity decision.

The settled local `agents:termOf` relationship remains the correct relation
between a HouseTerm and its enduring House.

## HouseTerm semantics

A numbered term must never be asserted identical to the enduring House.

The following is invalid:

```text
33rd Dáil
    owl:sameAs
        enduring Dáil Éireann
```

The normal traversal is instead:

```text
HouseTerm
    agents:termOf
        enduring House
            owl:sameAs
                accepted external enduring House
```

A future HouseTerm reconciliation policy may publish an external identity only
where the external resource denotes that exact numbered term.

The minimum evidence for any future HouseTerm match must establish:

- the correct House;
- the correct ordinal term number; and
- compatible temporal scope.

If no exact term-specific external identity is accepted, no direct external
identity assertion is required for the HouseTerm.

## Candidate generation

Candidate generation is deliberately high-precision. Fuzzy matching is not
required for the initial three institutional targets.

Labels may be used to discover candidates, but label evidence alone can never
accept one.

Candidate evidence should be recorded structurally rather than collapsed into
an arbitrary numeric confidence score.

### Positive evidence

Useful positive evidence includes:

- exact or near-exact English and Irish labels or aliases;
- external entity type compatible with a parliament or parliamentary House;
- Irish jurisdiction;
- organisational relationships consistent with the accepted institutional
  structure;
- official-site links or authoritative identifiers;
- inception and historical scope compatible with the proposed identity; and
- relationships between candidate Oireachtas, Dáil and Seanad items that
  corroborate the local institutional model.

External facts are evidence for identity review only. They must not be copied
into authoritative local Oireachtas graphs merely because they contributed to
a match.

### Negative and contradictory evidence

Negative evidence must be retained explicitly and be reviewable.

A candidate is ineligible for identity acceptance where the available evidence
establishes one of the following contradictions:

1. **Wrong entity level** — class, category, concept, list or other
   non-institutional entity instead of an institution individual.
2. **Wrong temporal level** — numbered legislative term proposed for an
   enduring House, or enduring House proposed for a numbered HouseTerm.
3. **Historical or revolutionary predecessor** — a resource denotes only a
   historical/revolutionary body rather than the accepted enduring local
   institution.
4. **Wrong jurisdiction** — an incompatible jurisdiction or constitutional
   context.
5. **Termination or succession contradiction** — the candidate is explicitly
   a predecessor, successor or replaced body rather than the same institution.
6. **Wrong organisational context** — the proposed House belongs to a
   different parliament or otherwise contradicts the accepted institutional
   structure.
7. **HouseTerm mismatch** — wrong House, ordinal number or temporal period.

Candidate rejection and local-entity reconciliation rejection are distinct.
The system may automatically exclude an individual candidate for a concrete
contradiction while leaving the local entity unresolved. A final local
`rejected` reconciliation decision remains a human review action.

Reason codes should be explicit and auditable, for example:

```text
wrong-entity-level
wrong-temporal-level
historical-predecessor
wrong-jurisdiction
succession-contradiction
wrong-organisational-context
house-term-mismatch
```

The exact enum or storage representation is an implementation detail for the
generic reconciliation core.

## Historical disambiguation

Institutional reconciliation must explicitly guard against false matches to:

- revolutionary or historical Dáil bodies;
- the Oireachtas or legislatures of predecessor constitutional orders;
- the historical Parliament of Ireland;
- other institutions with similar English or Irish names;
- Wikidata classes, categories or concepts;
- numbered Dáil or Seanad terms; and
- broader or narrower organisations that are related but not identical.

Historical continuity must be reviewed as an identity question rather than
assumed from a label.

This is particularly important where an external authority chooses an identity
scope spanning several constitutional periods. A candidate may be strong while
still requiring the reviewer to decide whether its identity scope matches the
settled enduring local institution.

## Review model

Review identity is the authoritative local institutional IRI, not a label,
alias or external identifier.

Conceptually the generic reconciliation key is:

```text
(entity_kind, local_iri)
```

For example:

```text
institution
https://data.oireachtas.ie/house/dail
```

The exact representation in SQLite or the version-controlled review file must
follow the generic Tranche 2 reconciliation design once merged.

Review decisions must:

- remain deterministic and version controlled where the generic design
  requires that;
- take precedence over machine candidate generation;
- be auditable with the evidence available at the time of review;
- survive mutable label changes because they are keyed by local IRI; and
- support explicit revocation/rejection without relying on absence of a
  candidate.

The initial Wikidata acceptance for each of the three institutions requires
human review.

## Publication and graph ownership

Institutional external links are derived enrichment and must not be written
into authoritative Oireachtas or Houses graphs.

Each independently reconciled local institution owns one independently
replaceable external-link graph.

The graph contains only approved external-link assertions whose subject is that
authoritative local institution.

For the initial implementation the permitted RDF forms are therefore:

```turtle
<local-institution> owl:sameAs <accepted-wikidata-institution> .

<local-institution>
    foaf:isPrimaryTopicOf <accepted-wikipedia-article> .
```

DBpedia is not emitted in the initial implementation.

The authoritative Houses graph, ontology graph and any other endpoint-owned
authoritative graph must remain unchanged by reconciliation publication.

The institutional external-link graph IRI convention is settled as:

```text
https://data.oireachtas.ie/graph/institution/oireachtas/external-links
https://data.oireachtas.ie/graph/institution/house/dail/external-links
https://data.oireachtas.ie/graph/institution/house/seanad/external-links
```

These graph names are policy-specific, deterministic, keyed by the stable local
institutional identity and independently replaceable. They do not modify the
authoritative Houses graph and leave a separate namespace available for any
future exact HouseTerm reconciliation.

## Reuse of the generic reconciliation core

Tranche 3 must not create a separate institutional reconciliation subsystem.

Institutional reconciliation must reuse the Tranche 2 generic core implemented
by `reconcile_entities(...)`. The shared engine owns:

- state selection;
- review hashing and review precedence;
- reconciliation attempt audit history;
- publication-attempt audit history;
- retry and recheck scheduling;
- dirty publication recovery;
- exact stored-payload replay;
- graph replacement; and
- post-publication whole-graph verification.

The institution policy must follow the existing Member/Party policy contract and
supply:

- entity extraction and validation;
- `entity_kind = "institution"`;
- stable local IRI and entity key;
- review key;
- source/identity fingerprint;
- eligibility;
- policy-specific graph IRI and stored graph IRI;
- candidate generation and resolution;
- accepted-link graph construction; and
- dirty stored-payload validation.

Review loading remains entity-specific, as it is for Members and Parties.
Institutional review decisions are keyed by the full local institutional IRI.
The version-controlled default review file is
`reconciliation/institution-decisions.json`.

The CLI surface is `oir-etl reconcile institutions`, reusing the shared
reconciliation SQLite store.

## Failure and recovery semantics

Tranche 3 inherits the Phase 3.5 recovery guarantees through the generic core.

In particular:

- an unresolved candidate does not clear a previously accepted graph;
- ambiguity does not clear a previously accepted graph;
- external-service failure does not clear a previously accepted graph;
- optional downstream enrichment failure does not invalidate an accepted
  primary Wikidata identity;
- an explicit reviewed revocation/rejection may clear the owned external-link
  graph;
- dirty state must replay the exact stored payload before new reconciliation
  work is attempted;
- dirty replay must not depend on fresh external lookups; and
- a publication is clean only after graph replacement and exact whole-graph
  post-publication verification succeed.

Authoritative Oireachtas ETL remains independent of external-service
availability.

## Tranche 2 integration contract

The merged Tranche 2 implementation settles the integration boundary for this
tranche:

- reconciliation SQLite schema version remains version 4;
- state identity is `(entity_kind, local_iri)`;
- institutional reconciliation uses `entity_kind = "institution"`;
- the shared `ReconciliationStore` is reused without an institutional schema
  migration;
- the shared `reconcile_entities(...)` engine is reused rather than copied;
- review loading and graph naming remain entity-policy-specific;
- institutional review uses a strict version-1 decisions file keyed by the full
  local IRI;
- institutional graph IRIs use the convention fixed in this document;
- dirty replay validates and republishes the exact stored N-Triples payload
  before any fresh lookup;
- publication uses the shared graph replacement and exact whole-graph
  verification path; and
- the CLI extends the existing reconcile endpoint choices with
  `institutions`.

The generic engine currently formats stale-review errors around Member/Party
names. Tranche 3 may make the smallest generic change needed to let a policy
supply the appropriate entity display name; this must not become a broader
reconciliation refactor.

Exact reason-code representation and offline fixture helper structure may be
chosen during implementation provided they preserve the semantic rules,
determinism and fail-closed behavior in this document.

## Tests

Implementation should add focused institutional tests while reusing the generic
reconciliation tests for state and publication behavior.

### Semantic tests

At minimum:

- an accepted Oireachtas candidate emits only approved predicates;
- an accepted Dáil candidate emits only approved predicates;
- an accepted Seanad candidate emits only approved predicates;
- the first institutional Wikidata acceptance cannot occur without review;
- exact or near-exact label equality cannot auto-accept a candidate;
- an external class/category/concept cannot be accepted as the institution;
- a historical/revolutionary Dáil candidate is excluded with explicit negative
  evidence;
- a predecessor institution is not accepted as the modern institution;
- a numbered HouseTerm cannot be accepted as the enduring House;
- an enduring House cannot be accepted as a HouseTerm;
- a HouseTerm never receives `owl:sameAs` to the accepted enduring-House
  Wikidata identity; and
- Wikipedia is emitted only as `foaf:isPrimaryTopicOf` and only downstream
  from an accepted Wikidata identity.

### Review and state tests

At minimum:

- review decisions are keyed by the full local IRI;
- a local label change does not change review identity;
- explicit review overrides machine candidate generation;
- malformed or stale review input fails before publication;
- structured rejection evidence is retained;
- unresolved candidate exclusion does not silently become a final human
  rejection; and
- state identity does not depend on labels or Wikidata QIDs.

### Publication and recovery tests

The institutional policy must pass the generic equivalents of the Phase 3.5
Member recovery tests:

- unresolved/ambiguous/outage outcomes preserve existing accepted publication;
- explicit reviewed revocation can replace the owned graph with the accepted
  empty payload;
- dirty replay uses the exact stored payload;
- dirty replay performs no new external lookup;
- graph replacement is independently scoped to the target institution;
- whole-graph post-publication verification detects rogue or missing triples;
- failed post-publication verification leaves state dirty; and
- unchanged clean payload is not unnecessarily republished except under an
  explicit force/all mode supported by the generic core.

### Ownership tests

At minimum:

- reconciliation does not mutate the authoritative Houses graph;
- Oireachtas, Dáil and Seanad external-link graphs are independently
  replaceable;
- the external-link graph contains no imported Wikidata/Wikipedia descriptive
  facts; and
- any future HouseTerm external-link graph is distinct from that of the
  enduring House.

## Competency queries

Competency queries must prove the enduring-institution/term distinction, not
merely the presence of external triples.

### Enduring institution to external identity

A query should prove that each reviewed enduring institution reaches its
accepted Wikidata identity.

Conceptually:

```sparql
SELECT ?institution ?external
WHERE {
    ?institution owl:sameAs ?external .
}
```

The production query must be scoped to the relevant independently replaceable
external-link graph rather than treating every `owl:sameAs` in the dataset as
institutional reconciliation.

### HouseTerm traversal through enduring House

A query should prove that a numbered term reaches the external identity through
its local enduring House:

```sparql
SELECT ?term ?house ?external
WHERE {
    ?term agents:termOf ?house .
    ?house owl:sameAs ?external .
}
```

The production query must use the authoritative Houses graph for
`agents:termOf` and the appropriate external-link graph for the House
identity.

### No HouseTerm-to-enduring-House identity

A negative competency query must return zero rows where a HouseTerm is asserted
`owl:sameAs` to the accepted enduring Dáil or Seanad external identity.

### External graph boundary

A competency query or whole-graph verification must establish that an
institutional external-link graph:

- has exactly the local institution as subject;
- contains only the approved predicates;
- contains only approved external target namespaces/types; and
- contains no imported descriptive facts.

### Authoritative graph isolation

A competency query must establish that institutional reconciliation predicates
are not added to the authoritative Houses/Oireachtas graph by the
reconciliation publisher.

## Acceptance criteria

The initial Tranche 3 implementation is complete when:

- Oireachtas, Dáil and Seanad use the settled local enduring identities;
- each first Wikidata identity has been explicitly reviewed;
- accepted same-entity Wikidata links use `owl:sameAs`;
- accepted Wikipedia links are derived from the accepted Wikidata identity and
  use `foaf:isPrimaryTopicOf`;
- DBpedia remains outside the initial publication contract;
- historical, revolutionary, predecessor, class/concept and term-level false
  candidates are rejected or excluded with explicit auditable evidence;
- no numbered HouseTerm is asserted identical to an enduring House or its
  accepted enduring-House external identity;
- HouseTerms without term-specific reconciliation reach external identity
  through `agents:termOf` and the enduring House;
- external-link publication is independently replaceable and does not alter
  authoritative institutional graphs;
- generic state, review, audit, dirty recovery, exact payload replay, graph
  replacement and post-publication verification are reused from the Tranche 2
  reconciliation core; and
- all earlier Phase 0-4, Phase 3.5 and Phase 4.5 regression/integration
  behavior remains correct.

## Deferred follow-on

A later follow-on may add reconciliation of exact numbered HouseTerms.

That work must preserve this document's identity boundary and should proceed
only where exact term-specific external identities add enough practical value
to justify their additional candidate and historical validation surface.

President reconciliation remains outside this tranche and must not be inferred
from institutional external data.
