# Oireachtas Open Data ETL — Phase Plan and Backlog

## 1. Objective

Build a deterministic and maintainable ETL pipeline that:

1. extracts JSON data from the Houses of the Oireachtas Open Data API;
2. preserves source responses for reproducibility;
3. transforms API records into RDF using the Oireachtas ontology and existing mapping specifications;
4. validates the resulting RDF;
5. loads validated RDF into a persistent triple store; and
6. supports repeatable full and incremental refreshes.

The pipeline should make the existing ontology and mapping work executable without coupling transformation logic to a particular triple-store implementation.

## 2. Target architecture

```text
api.oireachtas.ie
        |
        v
   Extract API data
        |
        v
 Immutable raw JSON
        |
        v
 Endpoint transformer
        |
        v
      RDF dataset
        |
        +------> RDF / SHACL / quality validation
        |
        v
   Staging named graph
        |
        v
      Triple store
        |
        v
 SPARQL query / applications
```

Operational ETL state should be maintained separately from the semantic RDF dataset.

A normal execution is therefore:

```text
extract -> persist raw source -> transform -> validate -> publish
```

Publishing invalid RDF to the production dataset must not be part of the normal execution path.

## 3. Design principles

### 3.1 Deterministic transformation

The same source JSON, ontology version and mapping version should produce the same RDF.

Generated resource identifiers must therefore be deterministic. Where the mapping currently suggests anonymous RDF nodes for derived resources such as date periods, deterministic IRIs should normally be preferred, for example:

```text
<house-term-uri#term-period>
```

rather than a newly generated blank node on each run.

### 3.2 Preserve source data

API responses should be retained outside Git as immutable raw inputs. This allows RDF to be regenerated when:

- mappings change;
- the ontology changes;
- transformation bugs are corrected; or
- validation requirements change.

### 3.3 Mapping specifications remain the semantic contract

The mapping CSV files and mapping documentation define the intended relationship between API fields and ontology terms. Python transformation code implements that contract.

The initial implementation should use RDFLib rather than attempting to convert the existing mappings directly into RML or another declarative mapping language.

### 3.4 Explicit RDF ownership

Each endpoint has responsibility for the descriptive triples of particular resource types.

| API source | RDF ownership |
|---|---|
| Houses | House and HouseTerm |
| Parties | Party |
| Constituencies | Constituency and Seanad panel |
| Members | Member and memberships |
| Legislation | Bill, legislative stages, events and related legislative resources |

Transformers may reference resources owned by another endpoint but should not independently recreate their descriptive triples. This avoids multiple sources attempting to maintain the same RDF statements.

### 3.5 Atomic graph replacement

Mutable root resources should normally be published as replaceable named graphs, for example:

```text
https://data.oireachtas.ie/graph/member/{member-id}
https://data.oireachtas.ie/graph/bill/{year}/{number}
```

When a resource changes, the complete validated graph can be replaced rather than attempting to determine individual triples that must be deleted.

### 3.6 Validate before publication

Validation occurs before production graph replacement. At minimum:

1. source-data validation;
2. RDF syntax and datatype validation;
3. SHACL validation; and
4. semantic-quality SPARQL tests.

# 4. Delivery phases

## Phase 0 — Stabilise ontology and mapping baseline

### Outcome

Establish a versioned semantic baseline against which ETL development can proceed.

### Backlog

- [ ] Review current ontology modules used by the API mappings.
- [ ] Review all existing mapping CSV files.
- [ ] Review `documentation/mapping_notes.md`.
- [ ] Identify mappings marked `mapped`, `new`, `implicit`, and `future_work`.
- [ ] Confirm every `mapped` and `new` ontology term exists in the Oireachtas ontology or an explicitly referenced external vocabulary.
- [ ] Correct the ontology validation script's ontology path if required.
- [ ] Add automated mapping-integrity tests.
- [ ] Establish namespace constants for ETL code.
- [ ] Record ontology and mapping versions used by ETL runs.
- [ ] Tag a stable ETL baseline in Git.

### Baseline validation

Run the Phase 0 checks from the repository root:

```text
.venv/bin/python tests/validate.py
.venv/bin/python -m tools.validation
.venv/bin/python -m pytest tests
```

The ontology validator parses every Turtle file beneath `ontology/` and runs
the existing Owlready2/HermiT consistency check over the repository's local
modules. The vendored ELI-DL schema is syntax-checked but excluded from HermiT
because it declares datatypes unsupported by HermiT. The approved local
`:dateSigned` `xsd:date` range is likewise syntax-checked and omitted only
from HermiT input because `xsd:date` is outside HermiT's OWL 2 datatype map.

Mapping-integrity validation examines all CSV rows with status `mapped` or
`new`. Local terms (`:`, `agents:`, and `members:`) must be declared in the
repository ontology. Terms from the explicitly approved external vocabulary
prefixes are accepted without remote retrieval. `implicit` and `future_work`
rows are intentionally outside this baseline check: the former emits no term,
and the latter remains deferred work.

Suggested baseline tag:

```text
v0.1-etl-baseline
```

### Exit criteria

- Ontology parses successfully.
- Ontology consistency validation passes.
- Mapping references are machine-checked.
- Mapping and ontology versions can be identified unambiguously.
- ETL development can proceed without unresolved fundamental namespace or term issues.

## Phase 1 — End-to-end ETL foundation and Houses vertical slice

### Outcome

Demonstrate the complete API-to-triplestore pipeline using the Houses endpoint. This phase establishes patterns that later endpoint transformers should reuse.

### Backlog

#### Project structure

- [ ] Create Python package under `src/oireachtas_etl/`.
- [ ] Add project configuration and dependencies.
- [ ] Add command-line entry point.
- [ ] Add shared configuration handling.

Suggested structure:

```text
src/oireachtas_etl/
    __init__.py
    cli.py
    config.py
    api.py
    state.py
    provenance.py
    loader.py
    transforms/
        __init__.py
        common.py
        houses.py
    validation/
        __init__.py
        source.py
        ontology.py
        shacl.py
        quality.py
```

#### Extraction

- [ ] Implement Oireachtas API client.
- [ ] Implement pagination using `skip` and `limit`.
- [ ] Implement retries for transient HTTP failures.
- [ ] Preserve API request parameters.
- [ ] Store API responses without modifying their content.
- [ ] Generate extraction metadata.

Suggested raw-data structure:

```text
data/raw/
    houses/
        YYYY-MM-DD/
            skip-000000.json
            skip-000000.meta.json
```

Metadata should include:

- endpoint;
- request parameters;
- retrieval timestamp;
- HTTP status;
- SHA-256 source hash;
- ETL version;
- ontology version; and
- mapping version.

Full harvested datasets should not normally be committed to Git.

#### Transformation

- [ ] Implement shared RDF namespace definitions.
- [ ] Implement URI validation helpers.
- [ ] Implement datatype-conversion helpers.
- [ ] Implement language-tagged literal helpers.
- [ ] Implement deterministic derived-resource identifiers.
- [ ] Implement Houses transformer.
- [ ] Implement documented HouseTerm class selection.
- [ ] Implement `termNo`.
- [ ] Implement `houseCode`.
- [ ] Implement `seats`.
- [ ] Implement `termOf`.
- [ ] Implement temporal period.
- [ ] Omit end-date triples when the API end date is null.
- [ ] Exclude API fields explicitly marked redundant or discarded.

#### Serialisation

- [ ] Support Turtle for developer inspection.
- [ ] Support N-Quads or TriG for dataset publication.
- [ ] Ensure deterministic output suitable for golden tests.

#### Validation

- [ ] Validate generated RDF syntax.
- [ ] Validate RDF datatypes.
- [ ] Add initial SHACL shapes for House and HouseTerm.
- [ ] Add SPARQL quality checks.

Initial invariants should include:

- every HouseTerm has a term number;
- every HouseTerm references its persistent House;
- every HouseTerm has a start date;
- known Dáil terms are typed as Dáil terms;
- known Seanad terms are typed as Seanad terms; and
- invalid null-valued RDF statements are not emitted.

#### Triple store

- [ ] Add a local Apache Jena Fuseki/TDB2 deployment.
- [ ] Configure persistent storage.
- [ ] Implement Graph Store Protocol loading.
- [ ] Implement graph replacement.
- [ ] Establish graph URI conventions.

Initial graph:

```text
https://data.oireachtas.ie/graph/houses
```

#### Testing

- [ ] Preserve a small Houses JSON fixture.
- [ ] Produce expected RDF fixture.
- [ ] Add transformation unit tests.
- [ ] Add golden RDF comparison tests.
- [ ] Add idempotency test.
- [ ] Add load-and-query integration test.
- [ ] Add competency queries.

Example competency queries:

- current Dáil term;
- current Seanad term;
- term number for a specified HouseTerm;
- start and end dates for a term; and
- persistent House associated with a term.

#### CLI

Target command:

```text
oir-etl run houses
```

Useful supporting commands may include:

```text
oir-etl extract houses
oir-etl transform houses
oir-etl validate houses
oir-etl load houses
```

### Exit criteria

Given an official Houses API response, the system can:

1. preserve the response;
2. transform it deterministically;
3. validate the RDF;
4. load it into Fuseki;
5. repeat the operation without duplicate or stale data; and
6. answer agreed competency queries correctly.

## Phase 2 — Parliamentary reference data

### Outcome

Extend the established ETL pattern to Parties and Constituencies. These resources provide relatively stable reference data required by Member transformation.

### Backlog

#### Parties

- [ ] Implement Party transformer.
- [ ] Map PartyGrouping resources.
- [ ] Distinguish political parties from Independent grouping where required.
- [ ] Map party code.
- [ ] Map preferred label.
- [ ] Map HouseTerm activity relationship.
- [ ] Add Party SHACL shape.
- [ ] Add Party golden fixtures.
- [ ] Add Party competency queries.

#### Constituencies

- [ ] Implement constituency transformer.
- [ ] Implement Seanad panel transformer.
- [ ] Select RDF class based on `representType`.
- [ ] Map preferred label.
- [ ] Map representation code.
- [ ] Link resource to HouseTerm.
- [ ] Add constituency/panel SHACL shapes.
- [ ] Add golden fixtures.
- [ ] Add competency queries.

#### Publication

- [ ] Create stable reference graph conventions.

Suggested graphs:

```text
https://data.oireachtas.ie/graph/parties
https://data.oireachtas.ie/graph/constituencies
```

- [ ] Add graph-replacement integration tests.

### Exit criteria

- Houses, Parties and Constituencies can be independently refreshed.
- Cross-resource IRIs resolve consistently.
- Member transformation can rely on stable identifiers for its principal referenced resources.

## Phase 3 — Members and parliamentary memberships

### Outcome

Represent Members and their parliamentary history, including membership periods and representation relationships. This is the first substantially nested API transformation.

### Backlog

#### Transformation

- [ ] Implement Member transformer.
- [ ] Map Member resource.
- [ ] Map preferred/display name.
- [ ] Map structured FOAF names where source data supports them.
- [ ] Transform nested Oireachtas memberships.
- [ ] Create deterministic membership resource identifiers.
- [ ] Map membership date periods.
- [ ] Link memberships to HouseTerm.
- [ ] Link memberships to persistent House.
- [ ] Map constituency representation.
- [ ] Map Seanad panel representation.
- [ ] Map Party membership.
- [ ] Map committee memberships currently classified as supported.
- [ ] Map supported office relationships.

#### Scope control

- [ ] Explicitly exclude mappings currently marked `future_work`.
- [ ] Produce a report identifying omitted future-work fields.
- [ ] Ensure unsupported data is not silently represented with speculative predicates.

#### Ownership

- [ ] Ensure Member transformation references Party resources without recreating Party descriptions.
- [ ] Ensure Member transformation references Constituency/Panel resources without recreating their descriptions.
- [ ] Ensure Member transformation references HouseTerm resources without recreating House descriptions.

#### Named graphs

Adopt a stable per-Member graph convention:

```text
https://data.oireachtas.ie/graph/member/{id}
```

- [ ] Implement complete Member graph replacement.
- [ ] Test deletion of obsolete membership triples through graph replacement.

#### Change detection

Because the Members endpoint does not expose a general record-modification cursor:

- [ ] Implement complete Member scanning.
- [ ] Canonicalise source Member records.
- [ ] Generate per-Member source hashes.
- [ ] Skip transformation and graph replacement for unchanged Members.
- [ ] Detect new Members.
- [ ] Detect changed Members.
- [ ] Decide policy for Members no longer returned by the API.

#### Validation

- [ ] Add Member SHACL shape.
- [ ] Add membership SHACL shape.
- [ ] Add representation constraints.
- [ ] Add temporal consistency tests.
- [ ] Add cross-resource quality queries.

Competency queries should include:

- Members of a specified HouseTerm;
- Member representing a constituency;
- Member's party at a specified time;
- parliamentary service history for a Member; and
- currently serving Members.

### Exit criteria

- Complete Member data can be harvested.
- Unchanged Member records are not unnecessarily republished.
- Membership history is represented deterministically.
- Cross-resource references use the reference data created in previous phases.
- Member graphs can be replaced without leaving stale membership triples.

## Phase 3.5 — External identity reconciliation pilot

### Outcome

Establish a reusable external-identity reconciliation layer using Members as the first and best-supported entity type. External identity data is derived enrichment and must remain operationally and semantically separate from authoritative Oireachtas RDF.

### Architectural rules

- The deterministic Oireachtas transformation pipeline must not call Wikidata, DBpedia or other external services.
- Failure or unavailability of an external service must never prevent publication of validated Oireachtas RDF.
- External identity assertions must be stored separately from endpoint-owned authoritative graphs.
- Reconciliation evidence and provenance must be retained separately from the resulting link assertion.
- External ontologies must not be imported wholesale into the Oireachtas domain model merely to support linking.
- `owl:sameAs` must be asserted conservatively and only where identity is sufficiently established.

### Settled implementation decisions

- Store reconciliation operational state in SQLite, separately from core publication state.
- Store explicit human reconciliation decisions in a small version-controlled review file. Human decisions take precedence over machine reconciliation and must never be overwritten automatically.
- For exact-identifier reconciliation, record explicit matching method, evidence and status rather than an arbitrary numeric confidence score.
- Publish an accepted unique Member-to-Wikidata Q-item identity as `owl:sameAs`.
- Publish a Member-to-DBpedia person identity as `owl:sameAs` only where the DBpedia resource is established to denote the same person.
- Link a Member to a Wikipedia article with `foaf:isPrimaryTopicOf`, not `owl:sameAs`.
- Use Wikidata P4690 as the primary identity-reconciliation path. Resolve DBpedia and Wikipedia downstream from an accepted Wikidata identity rather than performing an independent fuzzy DBpedia match.
- On the initial reconciliation run, process all Members. On normal runs, process new or identity-relevant changed Members; periodically re-check accepted links; re-check ambiguous or pending records more frequently where useful; and never automatically override a human decision.

The Phase 3.5 pilot implements these decisions in
`src/oireachtas_etl/reconciliation.py`. Operational details, failure handling,
and the review workflow are documented in
`documentation/member-reconciliation.md`.

Conceptually:

```text
Oireachtas API
     |
     v
core deterministic ETL
     |
     +------> authoritative Oireachtas RDF
                    |
                    v
            reconciliation queue
                    |
                    v
                Wikidata
                    |
              accepted Q-ID
               /         \
              v           v
         Wikipedia      DBpedia
              \           /
               v         v
             external-link graphs
```

### Backlog

#### Reconciliation model

- [x] Define a SQLite reconciliation record containing local entity, external entity, source, matching method, status, evidence and checked timestamp.
- [x] Define accepted, rejected, ambiguous and pending reconciliation states.
- [x] Keep reconciliation evidence auditable independently of published RDF links.
- [x] Implement a version-controlled manual-review file for ambiguous or conflicting matches and ensure explicit human decisions override automated reconciliation.

#### Wikidata Member reconciliation

Use the Oireachtas Member identifier as the first deterministic reconciliation path:

```text
Oireachtas :memberCode
        <->
Wikidata P4690
```

- [x] Implement exact `memberCode` to Wikidata P4690 lookup.
- [x] Reject multiple external entities claiming the same Oireachtas identifier pending review.
- [x] Record unmatched Members without inventing a fuzzy match.
- [ ] Use `wikiTitle` as an independent verification/enrichment signal rather than as the primary identity key where P4690 is available.
- [x] Record the Wikidata Q-ID as the primary external identity anchor for matched Members.

#### DBpedia and Wikipedia enrichment

- [x] Resolve DBpedia and Wikipedia identifiers from an accepted Wikidata identity where available.
- [ ] Compare derived DBpedia/Wikipedia targets with the existing `wikiTitle` value.
- [ ] Record redirects or title mismatches as reconciliation evidence.
- [x] Publish `owl:sameAs` for accepted Wikidata identities and same-person DBpedia resources, and `foaf:isPrimaryTopicOf` for Wikipedia article links.
- [x] Do not copy arbitrary DBpedia facts into authoritative Member graphs.

#### Refresh policy

- [x] Reconcile all Members on the initial run.
- [x] Reconcile new Members and Members whose identity-relevant source fields change during normal runs.
- [x] Periodically re-check accepted external links independently of Member source hashes.
- [x] Re-check ambiguous or pending records more frequently where useful.
- [x] Never automatically overwrite a version-controlled human decision.

#### Named graphs

The reconciliation subsystem exclusively owns one replaceable graph per Member:

```text
https://data.oireachtas.ie/graph/member/{percent-encoded-memberCode}/external-links
```

- [x] Publish only accepted identity links.
- [x] Ensure external-link graphs can be rebuilt without regenerating core Oireachtas graphs.
- [x] Add graph-boundary tests proving that enrichment does not alter endpoint-owned authoritative graphs.

#### Evaluation

Measure at least:

- percentage of Members matched through P4690;
- unmatched Member count;
- duplicate or ambiguous identifier count;
- agreement between P4690 matches and `wikiTitle`;
- DBpedia coverage for accepted Member matches;
- manually sampled false-match rate; and
- useful enrichment yield per external source.

### Exit criteria

- Member reconciliation is reproducible from authoritative Oireachtas identifiers.
- Wikidata matching is based primarily on exact P4690 identifier equality rather than name similarity.
- Reconciliation state and evidence are persisted in SQLite, while explicit human decisions are version-controlled and take precedence over automation.
- Accepted Wikidata, DBpedia and Wikipedia links use the documented predicates appropriate to what each external URI denotes.
- DBpedia is downstream secondary enrichment from an accepted Wikidata identity and is not an independent fuzzy-matching dependency.
- External links are refreshed independently of core Member publication and can be periodically re-verified even when Member source records are unchanged.
- Rebuilding or failing the external-link layer cannot corrupt or block authoritative Oireachtas publication.

## Phase 4 — Legislative lifecycle

### Outcome

Represent Bills and their legislative lifecycle using the existing legislation mappings.

### Settled implementation decisions

- Normalise Bill-origin and lifecycle House references to the canonical persistent House IRIs owned by Phase 1; do not mint or describe competing House identities from API definition URIs.
- Pin the Phase 4 external semantic baseline to ELI 1.5 and ELI-DL 3.0. Vendor or otherwise reproducibly pin those exact versions and audit every ELI/ELI-DL mapping against them before Phase 4 is accepted.
- Revise mappings to terms actually declared by the pinned vocabularies rather than adding local bridge declarations merely to preserve obsolete or incorrect external property names.
- Model `act.dateSigned` as `xsd:date` because the API supplies a date-only value; update the ontology/mapping contract accordingly rather than inventing a time component.
- HermiT may exclude only the exact `:dateSigned rdfs:range xsd:date` axiom from its reasoner input because HermiT does not support that datatype. A regression test must independently prove that the ontology still contains exactly the required range axiom; no general `xsd:date` exclusion is permitted.
- Use one deterministic legislative-process resource per Bill with IRI `{bill-uri}#process`; use the class/property names defined by the pinned ELI-DL 3.0 vocabulary.
- Use deterministic IRIs for any source-less derived legislative activities, including the Bill delivery activity.
- Use ELI core `eli:has_part`, not `eli-dl:has_part`, for supporting-document inclusion.
- Link the deterministic amendment-list activity to the relevant process stage using ELI-DL 3.0 `eli-dl:occured_at_stage`, not the undeclared `eli-dl:related_to`.
- Represent each supporting document with separate deterministic Work and Expression identities. For an API expression IRI `{expression-uri}`, derive the Work as `{expression-uri}#work`; link the Bill to the Work with `eli:has_part`, and the Work to the source Expression with `eli:is_realized_by`.
- Represent amendment-list formats on a separate deterministic Expression `{amendment-list-work-uri}#expression`, not directly on the amendment-list Work.
- Bill versions such as "As Initiated" and amended printings remain ELI Expression resources of the Bill.
- ELI language and media-type values must follow the object-resource semantics of pinned ELI 1.5; do not emit them as string/MIME literals where ELI requires object IRIs.
- Bill graphs may reference Member IRIs for sponsors but must not emit Member labels or other Member descriptions owned by Phase 3.
- For a resolved sponsoring Member, use the participant-person predicate defined by pinned ELI-DL 3.0. When only role text such as "Minister for Finance" is supplied and no role IRI exists, preserve that text as `rdfs:label` on the deterministic Participation resource; do not mint a ministerial-role identity from the label.
- Defer reconciliation of textual sponsor roles to authoritative ministerial office/tenure identities to a later dedicated coverage phase.
- Defer debate-resource RDF in Phase 4. Preserve debate data in raw source responses for a later authoritative Debates ETL rather than emitting partial debate resources.
- Bill graphs may reference the resulting Act but must not own or reproduce the Act description; authoritative Act descriptions are deferred to a later Acts ETL.

### Backlog

#### Bill transformation

- [ ] Implement Bill transformer.
- [ ] Map Bill as `eli-dl:DraftLegislationWork`.
- [ ] Map Bill as appropriate ELI legal resource.
- [ ] Create deterministic `{bill-uri}#process` LegislativeProcess.
- [ ] Map process number.
- [ ] Map legislative year.
- [ ] Map Bill type.
- [ ] Map English and Irish titles.
- [ ] Map process status.
- [ ] Map submitting source.
- [ ] Normalise originating House to the Phase 1 canonical House IRI.
- [ ] Map legislative method and deterministic delivery activity.
- [ ] Map last-updated timestamp.
- [ ] Map latest activity.
- [ ] Correct `dateSigned` ontology/mapping datatype to `xsd:date`.
- [ ] Pin/vendor ELI 1.5 and ELI-DL 3.0 and record the exact source/version used.
- [ ] Audit every active ELI/ELI-DL mapping against the pinned vocabularies and correct incompatible term names, ranges and object/literal treatment.
- [ ] Implement the narrowly scoped HermiT `dateSigned` range exclusion plus its independent regression assertion.

#### Legislative lifecycle

- [ ] Transform legislative stages.
- [ ] Transform supported legislative events.
- [ ] Transform amendment-list Work, deterministic tabling/activity resource, and Expression separately; link the activity to its stage with `eli-dl:occured_at_stage`.
- [ ] Transform supported related-document Work/Expression pairs and link the Bill to each supporting Work using `eli:has_part`.
- [ ] Attach PDF/XML formats to Expressions rather than Works and use ELI 1.5 object semantics for language/media type.
- [ ] Transform Bill-version expressions.
- [ ] Transform Bill-to-Act reference without emitting an authoritative Act description.
- [ ] Define deterministic identifiers for nested activities/events.
- [ ] Preserve event ordering where source data permits it.
- [ ] Ensure `latest_activity` references a generated activity resource.
- [ ] Ensure House and HouseTerm references reuse identifiers owned by earlier phases.

#### Ownership

- [ ] Do not recreate House or HouseTerm descriptions.
- [ ] Do not recreate Member descriptions when linking sponsors.
- [ ] Preserve unresolved sponsor-role text only as a label on Participation; do not mint role identities from labels.
- [ ] Do not publish authoritative Act descriptions from the Bill graph.
- [ ] Keep debate-resource descriptions deferred to the later Debates ETL.

#### External identity policy

- [ ] Keep Oireachtas identifiers and ELI identifiers authoritative for Bills, Acts and legislative lifecycle resources.
- [ ] Do not route legislation identity through DBpedia merely because external-reconciliation infrastructure exists.
- [ ] Treat any future Wikidata/DBpedia links for legislation as optional enrichment in separate external-link graphs.
- [ ] Ensure external-service availability cannot affect Bill transformation, validation or publication.

#### Scope

- [ ] Keep debate transformation explicitly deferred.
- [ ] Preserve debate fields in immutable raw source responses.
- [ ] Record API fields intentionally omitted from the first legislation implementation.

#### Named graphs

Use one graph per Bill:

```text
https://data.oireachtas.ie/graph/bill/{year}/{number}
```

- [ ] Replace entire Bill graph when the source Bill changes.

#### Validation

- [ ] Add Bill SHACL shapes.
- [ ] Add LegislativeProcess and legislative activity shapes.
- [ ] Add Bill-to-Act reference consistency checks.
- [ ] Add latest-stage consistency test.
- [ ] Add event-date validation.
- [ ] Add vocabulary-coverage tests proving every emitted ELI/ELI-DL predicate/class is declared by the pinned external ontology versions.
- [ ] Add Work/Expression/Format-level validation for supporting documents and amendment lists.
- [ ] Add chronology and latest-stage source-correspondence tests.
- [ ] Add ownership/boundary tests preventing House, Member, Act and Debate descriptions from leaking into Bill graphs.
- [ ] Add publication-failure/recovery tests and reviewable golden RDF fixtures.

Competency queries should include:

- latest stage of a Bill;
- status of a Bill;
- originating House;
- chronology of Bill stages;
- Act resulting from a Bill; and
- Bills updated within a particular period.

### Exit criteria

A Bill can be represented from introduction through its currently available legislative lifecycle, references earlier-phase resources through canonical identities, links to a resulting Act without owning its description, leaves debate RDF deferred, and updating the source Bill causes its complete RDF graph to be replaced safely.

## Phase 4.5 — External identity and institutional alignment

### Outcome

Extend the Phase 3.5 external-identity subsystem while correcting the local semantic models on which broader reconciliation depends. Phase 4.5 is delivered in three ordered tranches so that institutional identity and parliamentary-member-collection semantics are settled and regression-tested before external links depend on them.

### Tranche 1 — Institutional identity model

#### Implementation record

The ontology distinguishes class from institution: `agents:ParliamentaryBody`
is an enduring parliamentary-body class and
`<https://data.oireachtas.ie/oireachtas>` is the enduring Oireachtas individual.
Dáil and Seanad are enduring `agents:House` individuals connected to it by ORG
organisational structure; numbered HouseTerms remain temporal and are connected
to their House with `agents:termOf`. `is-a` is not used for constitutional
composition.

The constitutional Government is a separate formal organisation, not a
ParliamentaryBody or constituent by class inheritance. Its enduring resource is
accountable to the enduring Dáil through `agents:responsibleTo` (a subproperty
of `org:reportsTo`), while Cabinet/Oireachtas membership remains a separate
membership-record relationship. The generic Phase 4 Government bill-source IRI
is a controlled source concept, not a Government administration. President
modelling is deferred pending an authoritative source and ETL scope.

Tranches 2 (Party reconciliation) and 3 (institutional external reconciliation)
must use these stable local identities and do not alter them.

#### Purpose

Separate the ontology's current umbrella use of `:Oireachtas` from the identity of the enduring Oireachtas institution, and express constitutional/organisational relationships explicitly rather than through inappropriate subclassing.

#### Backlog

- [x] Introduce a class for parliamentary bodies, provisionally `:ParliamentaryBody`, as the organisational superclass needed by the Oireachtas and its Houses.
- [x] Introduce a persistent named individual for the enduring Oireachtas institution.
- [x] Retain the persistent Dáil and Seanad House individuals as authoritative local identities.
- [x] Model Dáil and Seanad as constituent/sub-organisations of the enduring Oireachtas using an explicit organisational relationship; do not use class inheritance to represent part-whole structure.
- [x] Preserve the existing `:HouseTerm -> :House` distinction so numbered Dáil/Seanad terms remain temporally bounded terms rather than enduring institutions.
- [x] Remove the current `:Government rdfs:subClassOf :Oireachtas` modelling.
- [x] Retain the constitutional Government as an organisation distinct from the Oireachtas.
- [x] Add an explicit Government-to-Dáil constitutional accountability relation, provisionally `:responsibleTo`, aligned as appropriate with `org:reportsTo`.
- [x] Preserve the relationship between Government and the Oireachtas through people and memberships: Government members must be Oireachtas members, represented through Cabinet membership/role records plus their parliamentary memberships.
- [x] Keep the generic Bill-source Government concept distinct from any later modelling of numbered Government administrations.
- [x] Decide whether a general constitutional constituent relation is required for the Oireachtas composition (President, Dáil, Seanad), rather than forcing all constitutional composition through organisational-subordination predicates.
- [x] Audit domain/range axioms and inference consequences affected by replacing the current `:Oireachtas` umbrella class.
- [x] Update mapping notes and competency queries where existing assumptions depend on the current hierarchy.
- [x] Regression-test all Phase 0–4 transformations, ownership boundaries, validation, and Fuseki publication behaviour.
- [x] Obtain an architecture/ontology review before closing the tranche.

#### Exit criteria

- The enduring Oireachtas, Dáil and Seanad have unambiguous local identities distinct from classes and numbered parliamentary terms.
- The ontology no longer uses subclassing to mean that Dáil, Seanad, Government, or House terms are parts/aspects of the Oireachtas.
- Government is modelled as constitutionally distinct from the Oireachtas while retaining explicit accountability to Dáil and membership links through Oireachtas members.
- Existing Phase 0–4 ETL and validation behaviour remains correct.
- Tranches 2 and 3 have stable semantic targets for reconciliation.

### Tranche 2 — Parliamentary member collection model and party reconciliation

#### Design record

The semantic contract for this tranche is documented in
`documentation/parliamentary-member-collection-model.md`.

The Oireachtas API's term-scoped party resources are treated as parliamentary
collections of Members, not as temporal versions of enduring political-party
organisations. `members:ParliamentaryMemberCollection` is the general class.
Non-`Independent` API records are `members:ParliamentaryParty` instances;
`Independent` records are `members:IndependentMemberCollection` instances.

Standing Orders also justify `members:ParliamentaryGroup` and
`members:TechnicalGroup` as ontology classes. They are distinct from
`members:ParliamentaryParty`: a parliamentary party may or may not also be a
recognised parliamentary group. The current API does not provide enough
information to populate ParliamentaryGroup or TechnicalGroup instances with
confidence, so this tranche defines those classes but does not infer instances
from non-API sources.

An enduring registered political party is a distinct external entity. A reviewed
relationship from a term-scoped ParliamentaryParty to that enduring party uses
`members:recognisedAsParty`. Neither `owl:sameAs` nor
`prov:specializationOf` is used between those two different entities.

#### Purpose

Replace the ambiguous PartyGrouping model with a Standing-Orders-grounded
parliamentary-member-collection model, preserve only API-supported instance
assertions, and then reconcile API-derived ParliamentaryParty instances to
reviewed enduring external political-party identities through an explicit
relationship rather than identity.

#### Backlog

##### Ontology and API model

- [x] Introduce `members:ParliamentaryMemberCollection` as the general collection-of-Members class.
- [x] Replace the current `members:Party` semantics with `members:ParliamentaryParty`, a subclass of `members:ParliamentaryMemberCollection`.
- [x] Introduce `members:IndependentMemberCollection` for term-scoped API `Independent` collections.
- [x] Introduce `members:ParliamentaryGroup` as the Standing-Orders recognition concept and `members:TechnicalGroup` as its subclass.
- [x] Do not make `members:ParliamentaryParty` a subclass of `members:ParliamentaryGroup`; the same individual may be typed as both only where recognition is independently established.
- [x] Define `members:recognisedAsParty` from a ParliamentaryParty to the enduring registered political party on which that parliamentary collection is based; explicitly distinguish this from ParliamentaryGroup recognition.
- [x] Do not require a local enduring `PoliticalParty` class or locally minted enduring party individuals merely for reconciliation.
- [x] Preserve each Parties API source IRI as the identity of its term-scoped ParliamentaryMemberCollection instance.
- [x] Preserve party code, display label and HouseTerm context on API-derived collections.
- [x] Remove or retire the term-independent `members:Independent` grouping as a target for API records; API Independent collections remain term-scoped.
- [x] Audit and retire the unsupported `PartyInGovernment`, `PartyInOpposition`, `PartiesMembership`, `hasPartiesMembership`, and `isPartyIn` model; defer `isWhipFor` until a supported source is modelled.

##### Member collection membership

- [x] Introduce a general parliamentary-collection membership record for dated Member-to-ParliamentaryMemberCollection relationships.
- [x] Retain `members:PartyMembership` as the more specific membership record for a ParliamentaryParty target.
- [x] Represent an API Independent record with the general collection-membership record rather than falsely treating Independent as membership of a political party.
- [x] Preserve the explicit relationship between each collection-membership record and the OireachtasMembership under which the API supplies it.
- [x] Update Member transformation, mappings and validation consistently with the collection model.

##### Population boundary

- [x] Populate ParliamentaryParty only from non-`Independent` Parties API records.
- [x] Populate IndependentMemberCollection only from `Independent` Parties API records.
- [x] Define ParliamentaryGroup and TechnicalGroup in the ontology but do not populate instances unless an API source explicitly provides sufficient evidence.
- [x] Do not infer Rural Independent, Civil Engagement or other technical/parliamentary groups from debates, biographies, Standing Orders application, press material or other non-API evidence in this iteration.
- [x] Do not infer ParliamentaryGroup recognition from party size, Opposition status or ministerial membership even where Standing Orders would permit the conclusion; record such information as a later gap-analysis/source-extension concern.

##### Generic reconciliation architecture

- [x] Refactor the Phase 3.5 reconciliation infrastructure so state, review, audit, dirty publication recovery and graph replacement are generic rather than copied into entity-specific implementations.
- [x] Use generic reconciliation identity `(entity_kind, local_iri)`; do not generalise the Member table's unique `memberCode` assumption because party codes repeat across House terms.
- [x] Migrate reconciliation SQLite schemas v1-v3 in place while preserving Member rows, attempt histories, publication histories and dirty payloads; keep Member reconciliation behavior and review-file format.
- [x] Keep entity-specific eligibility, fingerprinting, candidate generation, review validation, accepted-link semantics and external graph naming behind Member/Party policies or adapters.

##### Party candidate generation and review

- [x] Reconcile only `members:ParliamentaryParty` instances; exclude IndependentMemberCollection.
- [x] Define candidate generation from party code, label, Irish political-party context, Wikidata political-party type/Ireland jurisdiction and available historical evidence.
- [x] Do not automatically accept label, normalised-label or fuzzy matches where no deterministic external identifier exists.
- [x] Require human review before first acceptance of an enduring external party identity unless a future deterministic authority key is identified.
- [x] Key party review decisions by the full term-scoped ParliamentaryParty IRI, not by party code, so a decision does not silently propagate across House terms.
- [x] Record candidate evidence, ambiguity, rejection and accepted decisions in deterministic review/state data.
- [x] Publish only `members:recognisedAsParty` for an accepted external political-party target; never publish `owl:sameAs` or `prov:specializationOf` between the ParliamentaryParty and enduring PoliticalParty.
- [x] Publish accepted links in independently replaceable external-link graphs without importing external party facts into authoritative Parties graphs.
- [x] Preserve Phase 3.5 recovery semantics: unresolved/ambiguous/service-failure outcomes do not clear an accepted graph; explicit reviewed rejection may clear it; dirty state replays the exact stored payload before new lookup work, including changed source/review and `--all` runs.
- [x] Define coverage and false-match review metrics before broad publication (see `documentation/party-reconciliation.md`); actual sampling requires reviewed accepted links.
- [ ] Decide separately whether DBpedia/Wikipedia enrichment adds sufficient value once the Wikidata relationship is accepted.

#### Tranche 2 verification record

The ontology reasoner and mapping-integrity checks passed. The full Phase 0–4,
Member reconciliation and Party reconciliation suite passed (206 tests),
including seven tests against an isolated, disposable local Fuseki 5.1.0
dataset. No Party review acceptance is included in the default decisions file;
broad publication and a measured false-match sample remain contingent on
actual human-reviewed links. Tranche 3 institutional reconciliation is not
part of this delivery.

#### Exit criteria

- The PartyGrouping/Party model has been replaced by the documented ParliamentaryMemberCollection model.
- Non-Independent Parties API resources are term-scoped ParliamentaryParty instances; Independent resources are term-scoped IndependentMemberCollection instances.
- Member API records preserve dated collection membership and their containing OireachtasMembership context.
- ParliamentaryGroup and TechnicalGroup are defined from Standing Orders but are not populated through unsupported inference.
- ParliamentaryParty does not entail ParliamentaryGroup recognition.
- Party reconciliation reuses the generic reconciliation subsystem rather than duplicating the Member implementation.
- A term-scoped ParliamentaryParty is not asserted `owl:sameAs` or `prov:specializationOf` an enduring political party.
- Accepted external party relationships use `members:recognisedAsParty` and remain derived enrichment.
- Weak/ambiguous party matches remain reviewable and IndependentMemberCollection remains outside political-party reconciliation.
- Authoritative Parties and Member graphs remain independent of external-link publication.
- Phase 0-4 and Phase 3.5 regression/integration behaviour remains correct.

### Tranche 3 — Institutional reconciliation

#### Design record

The semantic and architectural contract for this tranche is documented in
`documentation/institutional-reconciliation.md`.

The initial reconciliation scope is limited to the three enduring institutional
identities established by Tranche 1:

```text
https://data.oireachtas.ie/oireachtas
https://data.oireachtas.ie/house/dail
https://data.oireachtas.ie/house/seanad
```

Wikidata is the primary external identity authority. The first accepted
Wikidata identity for each institution requires explicit human review; labels
or apparently obvious organisational relationships are not sufficient for
automatic acceptance. The initial review candidates are Q129821 for the
Oireachtas, Q651981 for Dáil Éireann and Q1127591 for Seanad Éireann. These are
review candidates rather than hard-coded accepted identities.

An accepted external resource may be linked with `owl:sameAs` only where it
denotes the same enduring institution. Wikipedia enrichment is derived
downstream from the accepted Wikidata identity and uses
`foaf:isPrimaryTopicOf` only where the article is genuinely about that
institution. DBpedia enrichment is deferred from the initial Tranche 3
implementation.

Numbered HouseTerm reconciliation is also deferred from the initial runtime
implementation. A HouseTerm must never be linked with `owl:sameAs` to the
enduring House or to the accepted external identity for that enduring House.
The normal traversal remains:

```text
HouseTerm
    agents:termOf
        enduring House
            owl:sameAs
                accepted external enduring House
```

Candidate generation and review must explicitly distinguish the modern
institution from historical/revolutionary predecessors, other similarly named
bodies, classes/concepts and numbered parliamentary terms. Negative and
contradictory evidence must be retained explicitly and auditably rather than
collapsed into a numeric confidence score.

Tranche 3 reuses the merged Tranche 2 generic reconciliation core:
`ReconciliationStore` schema v4, state identity `(entity_kind, local_iri)`,
and the shared `reconcile_entities(...)` engine. Institutional reconciliation
uses `entity_kind = "institution"`, a strict version-1 review file keyed by
full local IRI, and the CLI surface `oir-etl reconcile institutions`.
Review loading and graph naming remain policy-specific.

#### Purpose

Bridge the authoritative enduring Oireachtas, Dáil and Seanad identities to
reviewed external authority identities while preserving the distinctions
between class and individual, enduring institution and numbered term, and
modern institution and historical/predecessor bodies.

#### Backlog

##### Institutional identity and review

- [ ] Reconcile the enduring Oireachtas institution to a reviewed Wikidata identity.
- [ ] Reconcile the enduring Dáil Éireann House identity to a reviewed Wikidata identity.
- [ ] Reconcile the enduring Seanad Éireann House identity to a reviewed Wikidata identity.
- [ ] Require explicit human review before the first Wikidata acceptance for each institutional target.
- [ ] Key institutional review decisions by the authoritative local institutional IRI, not by label or external identifier.
- [ ] Treat Q129821, Q651981 and Q1127591 as initial review candidates only; do not hard-code them as accepted identities.
- [ ] Publish `owl:sameAs` only where the reviewed external resource denotes the same enduring institution.
- [ ] Derive Wikipedia only from the accepted Wikidata identity and publish `foaf:isPrimaryTopicOf` only where the article's primary topic is that institution.
- [ ] Keep DBpedia outside the initial Tranche 3 publication contract.

##### Candidate evidence and historical disambiguation

- [ ] Generate candidates from high-precision evidence such as labels/aliases, institution type, Irish jurisdiction, organisational relationships, official-site or authoritative properties, and compatible historical scope.
- [ ] Do not automatically accept exact-label, normalised-label, near-label or fuzzy matches in the absence of reviewed identity evidence.
- [ ] Record positive, negative and contradictory candidate evidence structurally rather than using an arbitrary numeric confidence score.
- [ ] Explicitly exclude classes, categories, concepts, lists and other resources that do not denote an institution individual.
- [ ] Explicitly exclude numbered Dáil or Seanad terms when reconciling an enduring House.
- [ ] Explicitly identify historical/revolutionary Dáil bodies, predecessor legislatures, the historical Parliament of Ireland and other similarly named institutions as non-identical where their identity scope differs from the local target.
- [ ] Distinguish candidate exclusion from a final reviewed rejection of the local entity, and retain auditable reason evidence for exclusions.
- [ ] Do not import external constitutional, organisational or historical facts into authoritative local graphs merely because they were used as reconciliation evidence.

##### HouseTerm boundary

- [ ] Defer runtime HouseTerm reconciliation from the initial Tranche 3 implementation.
- [ ] Preserve `agents:termOf` as the relationship from a numbered HouseTerm to its enduring House.
- [ ] Add tests that prevent a HouseTerm from receiving `owl:sameAs` to the enduring House or to the accepted external enduring-House identity.
- [ ] Ensure HouseTerms continue to reach enduring external institutional identity through `agents:termOf` and the accepted House identity.
- [ ] Keep the architecture open to later exact term-specific reconciliation where an external resource denotes the same numbered term, House and temporal scope.

##### Generic reconciliation integration

- [ ] Reuse the generic Tranche 2 reconciliation core rather than creating a separate institutional subsystem.
- [ ] Reuse generic state selection, review precedence and hashing, attempt audit history, retry/recheck scheduling, dirty publication recovery, exact stored-payload replay, graph replacement and post-publication whole-graph verification.
- [ ] Keep institution-specific identity, eligibility, fingerprinting, candidate generation, evidence rules, accepted-link semantics and graph selection behind the entity-policy/adaptor boundary delivered by Tranche 2.
- [ ] Implement the institution policy against the merged Tranche 2 policy contract and shared schema-v4 `ReconciliationStore`; do not introduce a parallel subsystem or schema migration.
- [ ] Preserve the existing recovery guarantee that unresolved, ambiguous or external-service-failure outcomes do not clear a previously accepted external-link graph.
- [ ] Permit an explicit reviewed revocation/rejection to clear the institution's owned external-link graph through the generic publication mechanism.
- [ ] Ensure dirty recovery replays the exact stored payload before attempting new reconciliation work.

##### External-link graph ownership

- [ ] Publish one independently replaceable external-link graph per reconciled local institution.
- [ ] Ensure every institutional external-link graph is keyed by stable local identity rather than mutable label.
- [ ] Keep authoritative Oireachtas and Houses graphs unchanged by reconciliation publication.
- [ ] Restrict the external-link graph to approved link assertions whose subject is the authoritative local institution; do not copy arbitrary Wikidata or Wikipedia descriptive facts.
- [ ] Use the settled graph IRIs: `https://data.oireachtas.ie/graph/institution/oireachtas/external-links`, `https://data.oireachtas.ie/graph/institution/house/dail/external-links`, and `https://data.oireachtas.ie/graph/institution/house/seanad/external-links`.

##### Validation and competency queries

- [ ] Test that first institutional Wikidata acceptance requires review and that review is keyed by full local IRI.
- [ ] Test that label equality or similarity cannot auto-accept an institution.
- [ ] Test rejection/exclusion of historical predecessors, wrong entity levels and wrong temporal levels with explicit evidence.
- [ ] Test that Wikipedia is published only as `foaf:isPrimaryTopicOf` downstream from an accepted Wikidata identity.
- [ ] Test that DBpedia is not emitted by the initial institutional policy.
- [ ] Test unresolved/ambiguous/outage preservation, explicit reviewed revocation, dirty exact-payload replay, no-network dirty replay and post-publication whole-graph verification through the generic core.
- [ ] Test independent replacement of Oireachtas, Dáil and Seanad external-link graphs.
- [ ] Add a competency query proving each enduring institution reaches its reviewed external identity.
- [ ] Add a competency query proving `HouseTerm -> agents:termOf -> House -> owl:sameAs -> external House` traversal.
- [ ] Add a negative competency query proving no HouseTerm is `owl:sameAs` to an accepted enduring-House external identity.
- [ ] Add graph-boundary competency checks proving institutional external-link graphs contain only the approved local subject and predicates.
- [ ] Add an authoritative-graph isolation check proving reconciliation predicates are not written to the Houses/Oireachtas graph.

#### Exit criteria

- Oireachtas, Dáil and Seanad enduring identities can be traversed to explicitly reviewed Wikidata identities without conflating them with classes, historical predecessors or numbered terms.
- First institutional Wikidata acceptance is human-reviewed and keyed by the authoritative local IRI.
- Accepted same-entity Wikidata links use `owl:sameAs`; accepted Wikipedia links use `foaf:isPrimaryTopicOf` and are derived from the accepted Wikidata identity.
- DBpedia and runtime HouseTerm reconciliation remain deferred from the initial Tranche 3 implementation.
- Historical, revolutionary, predecessor, class/concept and term-level false candidates remain rejected or excluded with explicit auditable evidence rather than being promoted through fuzzy matching.
- Numbered HouseTerms are never linked to enduring House identities or enduring-House external identities with `owl:sameAs`; they reach those identities through `agents:termOf`.
- External-link publication remains independently replaceable and isolated from authoritative institutional graphs.
- Reconciliation state, review, audit, recovery, graph replacement and post-publication verification are shared with Members and Parties through the generic Tranche 2 subsystem.
- Institutional reconciliation uses `entity_kind = "institution"`, the shared schema-v4 state store and `reconcile_entities(...)`, a strict full-IRI review file, the `reconcile institutions` CLI route and the settled institutional external-link graph IRIs.
- Earlier Phase 0-4, Phase 3.5 and Phase 4.5 regression/integration behaviour remains correct.

### Phase 4.5 overall exit criteria

- The external-link subsystem supports Members, ParliamentaryParties and parliamentary institutions without entity-specific architectural duplication.
- Each supported entity class has documented identity, matching, review and publication rules.
- Weak or ambiguous matches remain reviewable rather than being promoted automatically.
- External identities enrich but do not replace Oireachtas-owned identities.
- The institutional ontology distinguishes class/type, enduring institution, organisational/constitutional relationship and temporally bounded term.
- All Phase 0–4 regression and integration suites continue to pass after the institutional refactor.

## Phase 5 — Incremental refresh and ETL state

### Outcome

Move from manually repeatable transformations to reliable routine synchronisation with the Oireachtas API while refreshing external identity links independently of the authoritative ETL path.

### Backlog

#### ETL state store

Introduce a small operational state store, initially SQLite.

Suggested information:

```text
etl_run
resource_state
source_hash
last_seen
last_success
status
error
reconciliation_state
external_source
external_checked_at
```

- [ ] Record ETL run identifier.
- [ ] Record start and completion time.
- [ ] Record endpoint.
- [ ] Record source hash.
- [ ] Record RDF graph URI.
- [ ] Record success/failure status.
- [ ] Record validation result.
- [ ] Record error details.
- [ ] Record external-reconciliation state separately from core publication state.

#### Endpoint refresh policies

Implement explicit policies rather than assuming all endpoints support equivalent change tracking.

| Endpoint | Initial refresh strategy |
|---|---|
| Houses | full refresh |
| Parties | full refresh |
| Constituencies | full refresh |
| Members | full scan with per-resource hashing |
| Legislation | `last_updated` incremental fetch plus overlap |
| External identity links | queued refresh for new/changed entities plus periodic verification |
| Debates | deferred |
| Votes | deferred |
| Questions | deferred |

#### Legislation incremental loading

- [ ] Store last successful legislation cursor.
- [ ] Request records using `last_updated`.
- [ ] Use an overlap window to protect against boundary errors.
- [ ] Deduplicate by Bill identifier.
- [ ] Hash individual Bill source records.
- [ ] Periodically perform a complete source reconciliation.

#### Core source reconciliation

- [ ] Implement scheduled full comparison against current Oireachtas API results.
- [ ] Identify resources missing from current API results.
- [ ] Define deletion/tombstone policy.
- [ ] Detect RDF graph/state mismatches.

#### External identity refresh

Core ETL and external reconciliation are separate pipelines:

```text
Oireachtas source change
        |
        v
core ETL -----------------> authoritative RDF published
        |
        v
reconciliation candidate queued
        |
        v
external lookup ----------> external-link graph refreshed
```

- [ ] Queue newly created entities for external reconciliation.
- [ ] Queue entities whose identity-relevant fields change.
- [ ] Periodically re-verify accepted external links.
- [ ] Detect redirects, retired identifiers and disappeared external targets.
- [ ] Retry external-service failures without rolling back successful core publication.
- [ ] Permit a run state where core ETL is successful while external links are stale or pending.
- [ ] Keep external freshness timestamps separate from Oireachtas source freshness timestamps.

### Exit criteria

Routine execution processes only resources requiring publication, periodic source reconciliation protects against missed Oireachtas updates, and external identity links can lag or fail independently without affecting authoritative graph publication.

## Phase 6 — Production hardening

### Outcome

Make the ETL and external-reconciliation processes observable, recoverable and suitable for unattended operation.

### Backlog

#### Error handling

- [ ] Separate record-level failures from run-level failures.
- [ ] Introduce quarantine storage.
- [ ] Preserve failing source record.
- [ ] Record transformation exception.
- [ ] Record mapping and ontology versions.
- [ ] Allow unaffected resources to continue processing where safe.
- [ ] Establish thresholds that cause publication to fail.

#### Schema drift

- [ ] Detect previously unseen JSON properties.
- [ ] Report additional fields as warnings.
- [ ] Detect disappearance of fields required by mappings.
- [ ] Treat required mapped-field disappearance as a higher-severity issue.
- [ ] Produce schema-drift report.

#### Provenance

Record graph/run-level provenance. Possible information:

- `prov:wasGeneratedBy`;
- `prov:wasDerivedFrom`;
- retrieval timestamp;
- API request;
- source hash;
- ETL version;
- ontology version; and
- mapping version.

- [ ] Define provenance vocabulary usage.
- [ ] Create ETL-run resources.
- [ ] Create provenance/catalog named graph.
- [ ] Link published graphs to ETL runs.
- [ ] Record external source, lookup time, matching method and evidence for reconciliation assertions.

Per-triple provenance and RDF-star are explicitly outside the initial scope.

#### External enrichment operations

- [ ] Cache external lookup responses where permitted and useful.
- [ ] Implement rate limiting per external service.
- [ ] Implement retry/backoff for transient external failures.
- [ ] Provide a manual-review queue for ambiguous reconciliation results.
- [ ] Record reconciliation coverage, accepted, rejected, ambiguous and unmatched counts.
- [ ] Make external-link graphs reproducibly rebuildable independently of core RDF graphs.
- [ ] Add tests preventing external enrichment statements from leaking into authoritative endpoint-owned graphs.
- [ ] Ensure a Wikidata or DBpedia outage cannot fail an otherwise successful Oireachtas ETL run.

#### Observability

- [ ] Structured logging.
- [ ] Run summary.
- [ ] Extracted resource count.
- [ ] Changed resource count.
- [ ] Unchanged resource count.
- [ ] Published graph count.
- [ ] Quarantine count.
- [ ] Validation-failure count.
- [ ] API request count and failures.
- [ ] External reconciliation request count and failures.
- [ ] External-link coverage and pending-review count.
- [ ] Duration metrics.

#### Deployment

- [ ] Containerise ETL application.
- [ ] Add Fuseki/TDB2 container configuration.
- [ ] Add Docker Compose development deployment.
- [ ] Configure persistent volumes.
- [ ] Configure environment-specific settings.
- [ ] Protect update endpoints where required.
- [ ] Establish backup procedure.

#### Scheduling

Start with simple orchestration:

- cron;
- systemd timer; or
- scheduled container execution.

Do not introduce Airflow, Kafka or equivalent infrastructure until the workload demonstrates a need for it.

Core Oireachtas refresh and external identity refresh may run on different schedules. External reconciliation should normally be less time-critical than authoritative source publication.

#### CI

CI should run:

- [ ] ontology parse test;
- [ ] ontology consistency test;
- [ ] mapping-integrity test;
- [ ] transformation unit tests;
- [ ] golden RDF tests;
- [ ] SHACL validation;
- [ ] competency SPARQL queries;
- [ ] external-link graph-boundary tests; and
- [ ] integration tests where practical.

### Exit criteria

The ETL process can run unattended, failures are diagnosable, malformed resources are recoverable, successful graph publication can be traced to its source data and software versions, and external enrichment can fail or be rebuilt independently of the authoritative graph.

## Phase 7 — Extend dataset coverage

### Outcome

Extend the graph beyond the initial core Houses, Member and legislation data once the ETL architecture is proven.

Candidate vertical slices:

- debates;
- votes;
- questions; and
- ministerial office/tenure identities, including reconciliation of Phase 4 textual sponsor-role labels.

These should not block completion of the core ETL system.

### Backlog

- [ ] Review ontology coverage for Debates.
- [ ] Review ontology coverage for Votes.
- [ ] Review ontology coverage for Questions.
- [ ] Define authoritative ministerial office/tenure identities and reconcile unresolved Phase 4 sponsor-role labels without changing their preserved source evidence.
- [ ] Create or update mapping specifications.
- [ ] Identify resource ownership.
- [ ] Define graph granularity.
- [ ] Define incremental extraction strategy.
- [ ] Implement transformer.
- [ ] Add SHACL validation.
- [ ] Add competency queries.
- [ ] Add incremental loading.

Each endpoint should proceed as a separate vertical slice rather than being implemented simultaneously.

### Exit criteria

Each additional endpoint follows the same extract, transform, validate, publish and reconcile model as the core datasets.

# 5. Cross-cutting backlog

Some work applies across several delivery phases and should not be artificially assigned to one dataset.

## Mapping infrastructure

- [ ] Decide whether mapping CSVs remain documentation-only or become partly machine executable.
- [ ] Consider adding structured columns such as:

```text
subject_rule
predicate
object_rule
datatype
language
condition
null_policy
transform
ownership
```

- [ ] Validate mapping CSV syntax automatically.
- [ ] Validate referenced ontology terms.
- [ ] Generate mapping coverage reports.

## RDF identifier policy

- [ ] Document URI-generation rules.
- [ ] Document deterministic identifiers for derived resources.
- [ ] Ensure identifiers remain stable between ETL runs.
- [ ] Avoid identifiers derived from array position where possible.
- [ ] Add identifier regression tests.

## External identity policy

- [ ] Document the distinction between authoritative Oireachtas identifiers and derived external identities.
- [ ] Document source-specific external-link graph names.
- [ ] Document when `owl:sameAs` is permitted and when a weaker linking predicate is required.
- [ ] Document reconciliation evidence and manual-review requirements.
- [ ] Keep external identifier resolution outside deterministic endpoint transformation.

## Temporal modelling

- [ ] Standardise date and date-time conversion.
- [ ] Standardise open-ended periods.
- [ ] Define treatment of missing start dates.
- [ ] Define treatment of malformed dates.
- [ ] Validate temporal ordering.

## Language handling

- [ ] Standardise English and Irish language tags.
- [ ] Define policy where only one language is supplied.
- [ ] Prevent untagged literals where a mapping requires a language.

## Configuration

- [ ] Separate API configuration from transformation code.
- [ ] Separate triple-store configuration.
- [ ] Support development/test/production environments.
- [ ] Avoid credentials in repository files.

## Documentation

- [ ] Document architecture.
- [ ] Document command-line use.
- [ ] Document graph naming.
- [ ] Document RDF ownership.
- [ ] Document refresh policies.
- [ ] Document external identity reconciliation and graph separation.
- [ ] Document failure/recovery process.
- [ ] Document how to add a new endpoint transformer.

# 6. Deferred work

The following items should remain outside the critical path until a demonstrated requirement exists:

- conversion of mappings to RML/YARRRML;
- RDF-star provenance;
- per-triple provenance;
- stream-processing architecture;
- Kafka;
- Airflow or equivalent workflow platform;
- distributed ETL processing;
- inference-heavy production configuration;
- sophisticated graph version history;
- automatic ontology evolution;
- bulk import of external knowledge graphs;
- unsupported mapping fields currently marked `future_work`; and
- complete debates/votes/questions ingestion.

Deferral should be explicit rather than allowing these items to enter individual phases opportunistically.

# 7. Initial technical decisions

Unless later evidence requires a change, development should proceed with the following assumptions.

| Area | Initial choice |
|---|---|
| Implementation language | Python |
| RDF library | RDFLib |
| Semantic mappings | Existing CSV mappings plus mapping notes |
| RDF validation | RDFLib checks + SHACL + SPARQL quality tests |
| Ontology consistency | Existing Owlready2/HermiT approach |
| Triple store | Apache Jena Fuseki + TDB2 |
| Publication mechanism | SPARQL Graph Store Protocol |
| Mutable resource strategy | Stable named graphs and graph replacement |
| Operational state | SQLite |
| Initial orchestration | cron/systemd/scheduled container |
| Deployment | Docker Compose |
| Provenance | Graph/run level |
| Source preservation | Immutable raw JSON outside Git |
| Primary external identity authority | Wikidata, using stable identifiers where available |
| DBpedia role | Secondary enrichment and Linked Data interoperability |
| External-link storage | Separate source-specific named graphs |

These are implementation defaults, not ontology commitments.

# 8. Risks and open decisions

## API schema changes

The external API may add, remove or alter fields.

Mitigation:

- preserve raw source;
- schema-drift checks;
- mapping validation; and
- quarantine unexpected failures.

## Incomplete change tracking

Not all API endpoints expose modification timestamps.

Mitigation:

- endpoint-specific refresh strategies;
- source hashing; and
- periodic complete reconciliation.

## Duplicate RDF ownership

Nested API structures can encourage several transformers to emit descriptions of the same entity.

Mitigation:

- explicit resource ownership;
- cross-endpoint references by URI; and
- graph-boundary tests.

## Unstable generated identifiers

Blank nodes or position-based generated identifiers can produce unnecessary RDF changes.

Mitigation:

- deterministic URI-generation rules; and
- regression tests.

## External identity errors

External datasets can contain missing, stale, duplicated or incorrect identity assertions, and fuzzy matching can create false equivalence.

Mitigation:

- prefer exact stable identifiers such as Oireachtas `memberCode` matched to Wikidata P4690;
- retain reconciliation evidence;
- require manual review for ambiguous matches;
- publish external assertions in separate graphs; and
- avoid automatic `owl:sameAs` assertions from weak label similarity.

## External service availability

Wikidata, DBpedia or other external services may be unavailable or rate limited.

Mitigation:

- keep external lookups outside deterministic core ETL;
- cache where appropriate;
- retry independently; and
- allow authoritative publication to succeed while enrichment remains stale or pending.

## Ontology evolution

Changes to ontology terms can make previously generated RDF obsolete.

Mitigation:

- record ontology version for every run;
- preserve raw JSON; and
- support complete RDF regeneration.

## Over-engineering

The data volume does not initially justify complex distributed infrastructure.

Mitigation:

- begin with Python, RDFLib, SQLite and Fuseki; and
- introduce additional infrastructure only in response to measured requirements.

# 9. Milestones

### Milestone A — Semantic baseline

Ontology and mapping integrity are automatically validated.

### Milestone B — First vertical slice

Given a Houses API response, the ETL application can generate deterministic valid RDF and publish it to Fuseki.

### Milestone C — Reference graph

Houses, Parties and Constituencies are maintained as reusable reference data.

### Milestone D — Parliamentary membership graph

Members and their parliamentary service histories can be queried across House terms, parties and constituencies.

### Milestone E — External identity pilot

Members are reproducibly reconciled to Wikidata through stable identifiers, with DBpedia available as secondary enrichment in separate external-link graphs.

### Milestone F — Legislative graph

Bills and their legislative lifecycle can be queried from introduction through the latest known stage and resulting Act where applicable.

### Milestone G — Broadened identity graph

Selected parties, constituencies and institutions are linked to external authorities through the reusable reconciliation subsystem.

### Milestone H — Incremental synchronisation

Routine executions update only changed authoritative resources, periodically reconcile the complete source dataset, and refresh external links independently.

### Milestone I — Production ETL

The ETL runs unattended with validation, provenance, quarantine, monitoring and recoverable publication, while external enrichment remains independently recoverable.

# 10. Immediate implementation backlog

Phases 0-4 are complete. Phase 4.5 Tranche 1 (institutional identity model) is
implemented and has passed independent architecture review. The immediate work
is Phase 4.5 Tranche 2 as specified in
`documentation/parliamentary-member-collection-model.md`: implement the
ParliamentaryMemberCollection model first, then refactor/reuse the Phase 3.5
reconciliation subsystem for reviewed ParliamentaryParty-to-external-party
relationships.

Tranche 2 must not infer ParliamentaryGroup or TechnicalGroup instances from
non-API evidence. Standing-Orders-grounded classes may be defined even when the
current API cannot populate them. Tranche 3 institutional reconciliation remains
deferred until Tranche 2 is complete and regression-tested.

Remaining Phase 3.5 evaluation work—`wikiTitle` comparison, coverage metrics
and sampled false-match measurement—remains deferred unless directly required
to preserve or validate the generic reconciliation refactor.
