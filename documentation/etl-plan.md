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

- [x] Reconcile the enduring Oireachtas institution to a reviewed Wikidata identity.
- [x] Reconcile the enduring Dáil Éireann House identity to a reviewed Wikidata identity.
- [x] Reconcile the enduring Seanad Éireann House identity to a reviewed Wikidata identity.
- [x] Require explicit human review before the first Wikidata acceptance for each institutional target.
- [x] Key institutional review decisions by the authoritative local institutional IRI, not by label or external identifier.
- [x] Treat Q129821, Q651981 and Q1127591 as initial review candidates only; do not hard-code them as accepted identities.
- [x] Publish `owl:sameAs` only where the reviewed external resource denotes the same enduring institution.
- [x] Derive Wikipedia only from the accepted Wikidata identity and publish `foaf:isPrimaryTopicOf` only where the article's primary topic is that institution.
- [x] Keep DBpedia outside the initial Tranche 3 publication contract.

##### Candidate evidence and historical disambiguation

- [x] Generate candidates from high-precision evidence such as labels/aliases, institution type, Irish jurisdiction, organisational relationships, official-site or authoritative properties, and compatible historical scope.
- [x] Do not automatically accept exact-label, normalised-label, near-label or fuzzy matches in the absence of reviewed identity evidence.
- [x] Record positive, negative and contradictory candidate evidence structurally rather than using an arbitrary numeric confidence score.
- [x] Explicitly exclude classes, categories, concepts, lists and other resources that do not denote an institution individual.
- [x] Explicitly exclude numbered Dáil or Seanad terms when reconciling an enduring House.
- [x] Explicitly identify historical/revolutionary Dáil bodies, predecessor legislatures, the historical Parliament of Ireland and other similarly named institutions as non-identical where their identity scope differs from the local target.
- [x] Distinguish candidate exclusion from a final reviewed rejection of the local entity, and retain auditable reason evidence for exclusions.
- [x] Do not import external constitutional, organisational or historical facts into authoritative local graphs merely because they were used as reconciliation evidence.

##### HouseTerm boundary

- [x] Defer runtime HouseTerm reconciliation from the initial Tranche 3 implementation.
- [x] Preserve `agents:termOf` as the relationship from a numbered HouseTerm to its enduring House.
- [x] Add tests that prevent a HouseTerm from receiving `owl:sameAs` to the enduring House or to the accepted external enduring-House identity.
- [x] Ensure HouseTerms continue to reach enduring external institutional identity through `agents:termOf` and the accepted House identity.
- [x] Keep the architecture open to later exact term-specific reconciliation where an external resource denotes the same numbered term, House and temporal scope.

##### Generic reconciliation integration

- [x] Reuse the generic Tranche 2 reconciliation core rather than creating a separate institutional subsystem.
- [x] Reuse generic state selection, review precedence and hashing, attempt audit history, retry/recheck scheduling, dirty publication recovery, exact stored-payload replay, graph replacement and post-publication whole-graph verification.
- [x] Keep institution-specific identity, eligibility, fingerprinting, candidate generation, evidence rules, accepted-link semantics and graph selection behind the entity-policy/adaptor boundary delivered by Tranche 2.
- [x] Implement the institution policy against the merged Tranche 2 policy contract and shared schema-v4 `ReconciliationStore`; do not introduce a parallel subsystem or schema migration.
- [x] Preserve the existing recovery guarantee that unresolved, ambiguous or external-service-failure outcomes do not clear a previously accepted external-link graph.
- [x] Permit an explicit reviewed revocation/rejection to clear the institution's owned external-link graph through the generic publication mechanism.
- [x] Ensure dirty recovery replays the exact stored payload before attempting new reconciliation work.

##### External-link graph ownership

- [x] Publish one independently replaceable external-link graph per reconciled local institution.
- [x] Ensure every institutional external-link graph is keyed by stable local identity rather than mutable label.
- [x] Keep authoritative Oireachtas and Houses graphs unchanged by reconciliation publication.
- [x] Restrict the external-link graph to approved link assertions whose subject is the authoritative local institution; do not copy arbitrary Wikidata or Wikipedia descriptive facts.
- [x] Use the settled graph IRIs: `https://data.oireachtas.ie/graph/institution/oireachtas/external-links`, `https://data.oireachtas.ie/graph/institution/house/dail/external-links`, and `https://data.oireachtas.ie/graph/institution/house/seanad/external-links`.

##### Validation and competency queries

- [x] Test that first institutional Wikidata acceptance requires review and that review is keyed by full local IRI.
- [x] Test that label equality or similarity cannot auto-accept an institution.
- [x] Test rejection/exclusion of historical predecessors, wrong entity levels and wrong temporal levels with explicit evidence.
- [x] Test that Wikipedia is published only as `foaf:isPrimaryTopicOf` downstream from an accepted Wikidata identity.
- [x] Test that DBpedia is not emitted by the initial institutional policy.
- [x] Test unresolved/ambiguous/outage preservation, explicit reviewed revocation, dirty exact-payload replay, no-network dirty replay and post-publication whole-graph verification through the generic core.
- [x] Test independent replacement of Oireachtas, Dáil and Seanad external-link graphs.
- [x] Add a competency query proving each enduring institution reaches its reviewed external identity.
- [x] Add a competency query proving `HouseTerm -> agents:termOf -> House -> owl:sameAs -> external House` traversal.
- [x] Add a negative competency query proving no HouseTerm is `owl:sameAs` to an accepted enduring-House external identity.
- [x] Add graph-boundary competency checks proving institutional external-link graphs contain only the approved local subject and predicates.
- [x] Add an authoritative-graph isolation check proving reconciliation predicates are not written to the Houses/Oireachtas graph.

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

#### Implementation verification record (2026-09-28; complete)

The user-approved identities are Oireachtas Q129821, Dáil Éireann Q651981 and
Seanad Éireann Q1127591, recorded in the real reviewed decision file and
exercised. Offline tests accepted all three. A disposable Fuseki dataset
published all three and verified exact `owl:sameAs`-only external-link graphs;
no direct HouseTerm `owl:sameAs` was published, and the Houses graph remained
unchanged at 50 triples. Ontology validation passed at 2370 triples; the full
pytest suite passed (272 passed, 8 skipped without Fuseki); the disposable
Fuseki suite passed separately (8 passed), and the full suite with disposable
Fuseki enabled passed (280 passed). No Wikipedia review was supplied, so no
Wikipedia link is asserted. Nothing was published to production.

### Phase 4.5 overall exit criteria

- The external-link subsystem supports Members, ParliamentaryParties and parliamentary institutions without entity-specific architectural duplication.
- Each supported entity class has documented identity, matching, review and publication rules.
- Weak or ambiguous matches remain reviewable rather than being promoted automatically.
- External identities enrich but do not replace Oireachtas-owned identities.
- The institutional ontology distinguishes class/type, enduring institution, organisational/constitutional relationship and temporally bounded term.
- All Phase 0–4 regression and integration suites continue to pass after the institutional refactor.

## Reference-coverage corrective tranche — Phase 2/3 closure

### Status and purpose

**Implementation complete; technical validation complete; authoritative
reference census complete; authoritative coverage acceptance blocked by one
source conflict.** The deterministic census, historical-owner transforms,
Committee vertical, pre-publication and remote closure checks, capture
provenance, and Core State publication/recovery handling are implemented and
regression-tested. Repository validation passed with the Java runtime pinned in
`mise.toml`. The exact-IRI Committee conflict remains fail-closed. The global
all-or-nothing conflict gate is deliberately retained; affected-graph/partial
publication is deferred to a separate operational-design task. No production
Graph Store publication has been performed.

The acceptance statuses are distinct:

- **Implementation:** complete for the approved contracts and explicitly
  documented limitations.
- **Technical validation:** complete. Ontology and mapping-integrity
  validation, synthetic closure, publication/recovery, deterministic/golden,
  SHACL, and full-suite checks passed under `mise`. The real-capture candidate
  preflight correctly stops on the Committee conflict before closure
  evaluation; authoritative graph-level closure has therefore **not** passed.
- **Authoritative reference census:** complete. The integrity-checked complete
  source captures were inventoried and the counts are recorded below.
- **Authoritative coverage acceptance:** blocked by the one unresolved
  Committee source conflict. Candidate owner graphs are not published from
  that conflicting census.
- **Production publication:** not performed.

This corrective tranche closes a source-coverage assumption in the implemented
Phase 2/3 boundary; it does not reopen the Member semantic model or redesign the
Phase 5 state architecture.

Phase 2 treats `/v1/parties` and `/v1/constituencies` as the owner sources
for parliamentary collections and constituencies/panels. Those endpoints are
valid authoritative observations, but their default responses are not a
complete historical inventory. The complete Members source contains additional
historical Party/Independent-collection, constituency/panel and Committee IRIs.
Member graphs correctly reference those resources without describing them, so
the RDF ownership rule is sound but owner-graph coverage is incomplete.

The outcome of this tranche is a deterministic, source-grounded reference
coverage layer in which every Member reference that carries enough Oireachtas
source evidence resolves to an owner description, while Member graphs remain
reference-only for those resources.

This tranche is also a prerequisite for Phase 7 Debates cross-dataset
integration where debate records resolve Committee references. It does not
change the NLQ tool.

### Ownership and authoritative-source contract

Retain the existing ownership boundaries:

| Resource | Owner graph | Authoritative observations |
|---|---|---|
| House / HouseTerm | `https://data.oireachtas.ie/graph/houses` | Houses endpoint |
| ParliamentaryParty / IndependentMemberCollection | `https://data.oireachtas.ie/graph/parties` | Parties endpoint plus nested complete-Members observations |
| Dáil constituency / Seanad panel | `https://data.oireachtas.ie/graph/constituencies` | Constituencies endpoint plus nested complete-Members observations |
| Committee | `https://data.oireachtas.ie/graph/committees` | nested complete-Members observations |
| Member and membership records | per-Member graph | Members endpoint |

The standalone Parties and Constituencies endpoints remain preferred
owner-source observations when they contain a resource. A resource missing
from those endpoint responses is **not** negative evidence: a valid nested
Member observation may supply the historical owner description. Member
transformers still emit only references and Member-owned membership records;
they must not start emitting Party, constituency/panel or Committee
descriptions.

The complete Members scan is the completeness boundary for member-derived
reference evidence. Fixture-backed or otherwise incomplete scans may exercise
the logic but must not advance authoritative coverage/missing-resource state or
justify removal of an existing owner description.

### Work package 1 — Deterministic reference census

Add a reference-observation extractor over the complete preserved Members
capture. It is separate from the Member RDF transformer and does not change the
Member contract.

Inventory every distinct canonical reference IRI found in:

- `membership.parties[].party`;
- `membership.represents[].represent`; and
- `membership.committees[]`.

For each IRI record, deterministically, at least:

- reference kind;
- canonical IRI;
- containing Member and source JSON pointer;
- HouseTerm/context needed to validate the source identity;
- all owner-relevant fields supplied by each observation;
- observation source (`members`, `parties`, or `constituencies`);
- evidence completeness;
- normalized comparison values; and
- consolidation status.

The census report must distinguish:

- endpoint-only;
- Members-only;
- overlap/concordant;
- overlap/conflicting; and
- insufficient-evidence references.

The report is reproducible audit output, not a second operational-state store
and not semantic RDF. Record aggregate counts by reference kind and coverage
class so a future source regression is visible.

### Work package 2 — Consolidation rules and historical owner coverage

Use the exact validated Oireachtas IRI as the identity key. Never merge
different IRIs because codes or labels look similar, and do not use Wikidata,
DBpedia, fuzzy matching or other external evidence for authoritative
consolidation.

Normalize only comparison-safe lexical differences (for example Unicode
normalization, surrounding whitespace and equivalent numeric representation).
Preserve the selected authoritative source lexical value in emitted RDF.

For an IRI observed in both its standalone owner endpoint and Members:

1. validate independently that both observations identify the same resource
   and HouseTerm/type encoded by the IRI;
2. require all non-null mapped semantic values to agree after permitted
   normalization;
3. use the standalone endpoint value for serialization when the normalized
   values agree but harmless source formatting differs; and
4. allow nested Members evidence to fill an owner field that the standalone
   record genuinely omits.

For an IRI observed only in Members, require all non-null normalized
observations of each mapped owner field to agree. Identical repetition across
Members is corroborating evidence, not duplicate RDF.

A material conflict is never resolved by majority vote or source-order
accident. Record the competing source observations and fail the affected
candidate owner-graph build before publication. The last clean published graph
therefore remains intact. A later reviewed source correction or explicit
policy change may resolve the conflict; this tranche does not add a generic
manual identity-merging mechanism.

Re-use the existing Party and Constituency source-to-RDF contracts by
normalizing accepted Member observations into their existing logical record
shape before transformation. This must cover historical
`ParliamentaryParty`, `IndependentMemberCollection`, `DailConstituency`
and `SeanadPanel` instances without altering Member-owned membership dates.

Member-only fields that describe a relationship rather than the referenced
resource remain Member-owned. In particular, party membership `dateRange`,
Committee `memberDateRange`, and Committee role/role tenure must never be
copied into owner graphs.

### Work package 3 — Committee owner vertical

Add:

```text
https://data.oireachtas.ie/graph/committees
```

as a shared replaceable authoritative graph with the same validate-before-PUT,
dirty-state and post-PUT exact-verification behavior as the other core
reference graphs.

The Committee vertical is sourced initially from nested observations in a
**complete** Members capture. It must validate the source IRI form actually
used by the API:

```text
https://data.oireachtas.ie/ie/oireachtas/committee/{houseCode}/{houseNo}/{slug}
```

where `houseCode` is `dail` or `seanad`. Derive the Committee's term
context from its own IRI. Do not infer it from the containing Member's House
membership: a Seanad Member may legitimately reference a Committee whose
source IRI is anchored under a Dáil term. If `houseCode` or `houseNo` is
also supplied as fields, require it to agree with the IRI.

The first owner contract should map:

- the source IRI as a `members:Committee`;
- `members:committeeCode` where supplied;
- `members:committeeID` where supplied;
- a new explicit Committee-to-HouseTerm relation, without reusing
  `members:inHouseTerm` (whose domain is OireachtasMembership);
- `agents:hasCommitteeType` for supported structural values already present
  in the controlled vocabulary;
- `agents:hasCommitteePurpose` for supported purpose values already present
  in the controlled vocabulary;
- the Committee operational date range through a Committee-specific relation
  to the existing date-range pattern; and
- English/Irish preferred labels from the latest unambiguous supplied
  Committee-name observation.

Committee names are the intentional temporal exception to all-observation
field concordance: the latest valid open-ended name interval (or latest valid
historical interval if none is open-ended) is selected independently per
language; a tie with different lexical values is reported ambiguous and omitted.
This does not alter the exact-IRI identity rule or the agreement requirement
for Committee codes, IDs, classification, term and operational date range.

Do not infer Select/Joint/Special type from a label or URI slug when the source
does not supply that classification.

Keep temporally qualified historical Committee-name intervals, `expiryType`,
`mainStatus`/`status`, and `serviceUnit` explicitly deferred unless the
implementation can add them without widening this tranche. The raw source
evidence remains preserved, and the coverage contract must not pretend those
fields have been semantically represented.

Correct the existing ontology/documentation annotation for Committee source URI
shape if it still documents an older non-source pattern. Add a Committee
mapping/source contract, transformer, independent source-to-RDF validator,
SHACL, deterministic golden fixture and competency queries.

### Work package 4 — Coverage-closure validation and publication gate

Add a graph-independent closure validator over the complete Member candidate
dataset plus the candidate owner graphs. At minimum it must check these Member
reference edges:

- `members:memberOfCollection` /
  `members:isPartyMembershipOf` -> Parties owner graph;
- `members:isRepresentativeFrom` -> Constituencies owner graph; and
- `members:isCommitteeMembershipOf` -> Committees owner graph.

For every referenced IRI whose source observation satisfies the minimum owner
contract, require an owner description with the expected class, source key and
term/context relation. A malformed or genuinely insufficient observation is
reported explicitly as `insufficient_evidence`; it must not cause creation of
a placeholder resource. A contradictory observation is a conflict, not
insufficient evidence, and fails the candidate reference publication.

Run closure validation before shared reference graphs are replaced. After
publication, run a graph-scoped SPARQL closure check against Fuseki as an
integration/acceptance check. Normal full-load ordering should publish and
verify the consolidated reference graphs before publishing Member graphs that
depend on them.

A successful complete reference run must report zero unresolved **closable**
Member references. It may report insufficient-evidence references separately,
with their source paths and reasons.

### Refresh, state and deletion semantics

Re-use the Phase 5 core SQLite state and publication-recovery boundary; do not
create a second scheduler or reference-state database.

- A complete Members scan may add or update historical owner descriptions.
- The consolidated owner graph is the union of accepted standalone endpoint
  observations and accepted complete-Members observations.
- Absence from the standalone Parties/Constituencies response alone never
  deletes historical owner data.
- Missing-resource removal requires complete-source evidence and the existing
  Phase 5 non-destructive confirmation policy.
- Any incomplete/quarantined Members scan that prevents a trustworthy
  reference census must not be used to replace a supposedly complete shared
  owner graph.
- Fixture runs remain non-authoritative and do not advance missing/coverage
  evidence.
- Newly covered ParliamentaryParty resources may flow into the existing
  reconciliation due/recheck mechanism; no new external-reconciliation
  architecture is introduced.
- Committee external reconciliation is outside this tranche.

### Required tests and exit criteria

Implementation is complete only when:

- a deterministic census over the complete Members capture reports every
  distinct Party/Independent-collection, constituency/panel and Committee
  reference and its source observations;
- the census comparison shows exactly which references were absent from the
  standalone Phase 2 owner inputs;
- historical Member-only ParliamentaryParty and IndependentMemberCollection
  records appear in the Parties owner graph with the existing collection
  semantics;
- historical Dáil constituencies and Seanad panels appear in the
  Constituencies owner graph;
- every closable Committee reference has a description in the new Committee
  owner graph;
- repeated identical Member observations deduplicate deterministically;
- a material cross-observation conflict prevents the affected shared graph
  replacement and preserves the previous clean graph;
- a Committee's term context is taken from its own source IRI rather than from
  the Member who references it;
- Member graphs still contain no descriptive triples for Party,
  constituency/panel or Committee resources;
- closure validation reports zero unresolved closable Member references;
- graph replacement, dirty-state recovery, fixture/non-authoritative behavior
  and complete-source missing semantics are regression-tested;
- ontology consistency, mapping integrity, SHACL, deterministic/golden tests,
  closure queries and the full existing test suite pass; and
- no NLQ behavior or Member semantic contract is changed.

### Deterministic census checkpoint

The repeatable audit command is `tools/reference_census.py`; it verifies raw
page hashes, pagination, advertised totals and the Members unique-record count
before emitting the full deterministic JSON observation report. Against the
complete 1,928-Member API capture `run-d2c089d0-5203-40f1-97b8-ae0d8285e74d`
and the captured standalone Parties and Constituencies runs from 2026-10-04,
the census found:

| Kind | Distinct IRIs | Members-only | Endpoint overlap/concordant | Conflicting |
|---|---:|---:|---:|---:|
| Party/Independent collection | 378 | 367 | 11 | 0 |
| Dáil constituency/Seanad panel | 1,529 | 1,521 | 8 | 0 |
| Committee | 268 | 267 | 0 | 1 |

The report contains 17,557 observations: 7,329 Party, 7,174 representation and
3,054 Committee observations. It identifies 2,174 closable identities, zero
minimum-contract insufficient-evidence identities, one conflicting identity,
18 malformed observations and 24 Committee-name ambiguity diagnostics. No
placeholder owner is emitted. The census consolidates 367 historical
Party/Independent owners absent from the standalone Parties capture and 1,521
historical constituency/panel owners absent from the standalone Constituencies
capture; 11 Party and 8 representation IRIs overlap concordantly with their
standalone captures. It also consolidates 267 closable Committee owners. These
are source-grounded candidate records, not evidence that a shared graph was
published: the material Committee conflict currently blocks candidate graph
construction and authoritative coverage acceptance.

#### Raw evidence for the single Committee conflict

The evidence below was inspected directly in the immutable, hash-verified raw
Members pages from run
`run-d2c089d0-5203-40f1-97b8-ae0d8285e74d`, not inferred from RDF. All 14
observations use this exact Committee IRI:

```text
https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_the_implementation_of_the_good_friday_agreement
```

The IRI itself derives Committee HouseTerm
`https://data.oireachtas.ie/ie/oireachtas/house/dail/33`. All 14 containing
Member membership objects also identify HouseTerm
`https://data.oireachtas.ie/ie/oireachtas/house/dail/33`. No nested Committee
object supplies explicit `houseCode` or `houseNo`; the source IRI supplies the
Committee term independently of Member context.

Thirteen observations have the same Committee-owned evidence: code `"115"`,
ID `115`, type/purpose `Shadow Department`, operational range
2020-07-23–2024-11-08, `status`/`mainStatus` `Archived`, `expiryType`
`Sessional`, and `serviceUnit` `Committees' Secretariat`. Their name interval
starts 2020-07-23 and is open-ended; English is “Select Committee on the
Implementation of the Good Friday Agreement ” (the source value has a trailing
space) and Irish is “An Roghchoiste um Fhorfheidhmiú Chomhaontú Aoine an
Chéasta”. The trailing English space is harmless under the documented
comparison normalization. The individual raw locations and Member relationship
date ranges are:

| Source Member IRI | Raw page and JSON Pointer | Member's Committee-membership range |
|---|---|---|
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Jennifer-Carroll-MacNeill.D.2020-02-08` | `skip-000200.json` `/results/77/member/memberships/0/membership/committees/2` | 2020-09-08–2022-12-21 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Rose-Conway-Walsh.S.2016-04-25` | `skip-000300.json` `/results/82/member/memberships/1/membership/committees/8` | 2020-09-08–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick-Costello.D.2020-02-08` | `skip-000400.json` `/results/14/member/memberships/0/membership/committees/0` | 2020-09-08–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Frank-Feighan.S.2002-09-12` | `skip-000600.json` `/results/62/member/memberships/4/membership/committees/4` | 2023-03-07–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/James-Lawless.D.2016-10-03` | `skip-001000.json` `/results/72/member/memberships/1/membership/committees/1` | 2020-09-08–2024-06-27 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Pádraig-MacLochlainn.D.2011-03-09` | `skip-001100.json` `/results/42/member/memberships/2/membership/committees/6` | 2020-09-08–2021-09-28 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-McAuliffe.D.2020-02-08` | `skip-001200.json` `/results/7/member/memberships/0/membership/committees/2` | 2024-09-25–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-McNamara.D.2011-03-09` | `skip-001300.json` `/results/0/member/memberships/1/membership/committees/3` | 2020-09-08–2022-10-25 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Fergus-O'Dowd.S.1997-09-17` | `skip-001400.json` `/results/98/member/memberships/5/membership/committees/4` | 2020-09-08–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Smith.D.1992-12-14` | `skip-001700.json` `/results/60/member/memberships/6/membership/committees/0` | 2020-09-08–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Pauline-Tully.D.2020-02-08` | `skip-001800.json` `/results/19/member/memberships/0/membership/committees/0` | 2021-09-28–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Peadar-Tóibín.D.2011-03-09` | `skip-001800.json` `/results/25/member/memberships/2/membership/committees/1` | 2020-09-08–2024-11-08 |
| `https://data.oireachtas.ie/ie/oireachtas/member/id/Violet-Anne-Wynne.D.2020-02-08` | `skip-001800.json` `/results/85/member/memberships/0/membership/committees/0` | 2022-11-22–2024-11-08 |

At the adjacent `/results/98/member/memberships/5` location for Fergus
O'Dowd, the same membership simultaneously contains a second Committee object
at `skip-001400.json` `/results/98/member/memberships/5/membership/committees/5`.
It repeats the exact Committee IRI but supplies code `"156"`, ID `156`,
`committeeType` `["Shadow Department", "Policy"]`, a
`committeeDateRange` whose `start` and `end` are both null, and
`status`/`mainStatus` `Deleted`. Its English name has the same normalized
lexical value but no trailing space, its name interval starts 2020-09-09 and
is open-ended, and its Irish name is null. `expiryType` and `serviceUnit` match
the other observations. Its containing Committee-membership range is
2020-09-08–2020-09-18 and its Member role is `Cathaoirleach`; these are
Member-owned relationship facts, not Committee-owner tenure. The matching
`committeeCode` 115 observation for the same Member carries a role with an
open-ended date range.

This is not a harmless normalization difference. It is direct same-snapshot
contradiction of the mapped code, ID, classification and operational range.
Although the name interval and `Deleted` status suggest a stale or superseded
record, both Committee objects occur simultaneously in one Member membership,
and the disputed operational range supplies no dates by which to model code/ID
as temporal values. Under the approved exact-IRI owner contract this is a
demonstrable source-data inconsistency; the raw evidence alone cannot distinguish
an upstream duplicate/error from two underlying Committee records being
assigned one IRI. No majority vote, observation precedence, deleted-status or
dated-record preference, label similarity, IRI rewrite or ID/code selection is
applied.

#### Follow-up review of first-party Oireachtas evidence

A narrowly scoped source review on 2026-10-05 did not resolve the conflict:

- **Preserved Members API captures in this project:** each of the three
  successful, complete 1,928-Member runs on 2026-10-04
  (`run-ea875759-12ef-4fd0-8e0c-fce050f0725f`,
  `run-53f4ded0-c074-46f9-8cf3-490b05ca19d2`, and
  `run-d2c089d0-5203-40f1-97b8-ae0d8285e74d`) passed the capture hash,
  pagination, advertised-count, endpoint and Core State provenance checks.
  Each contains the same 14 observations for this IRI. Their `skip-001400.json`
  bodies have the same SHA-256
  `c702d32887456df3a4eb4293e1e2b2054550496f514b214a3cab40cdf4e9dd31`.
  Each reproduces thirteen observations with code/ID `115` and one with
  code/ID `156`, `Deleted` status, null Committee dates and the additional
  `Policy` purpose. These repeated captures establish persistence of the API
  response, not an independent resolution.
- **Current first-party Members API response:**
  `GET https://api.oireachtas.ie/v1/members?skip=1400&limit=100` reported
  `memberCount: 1928`. In `/results/98/member/memberships/5/membership`,
  `committees/4` again has the exact disputed IRI, code/ID `115`, `Archived`,
  `Shadow Department`, and Committee dates 2020-07-23–2024-11-08; `committees/5`
  has the same exact IRI, code/ID `156`, `Deleted`, `Shadow Department` plus
  `Policy`, and null Committee dates. Its Member-role range ends 2020-09-18.
  Thus the live first-party API still publishes both alternatives together.
- **Published Oireachtas API specification:**
  `https://api.oireachtas.ie/swagger.json` identifies API version 1.1.0 and
  documents `/v1/members`, `/v1/parties`, `/v1/constituencies`, Houses,
  legislation, debates, questions and votes, but no dedicated Committee
  endpoint. `/v1/committees` returned 404 during this review. No separate
  first-party structured Committee record with code/ID was found through the
  documented API.
- **Official 33rd Dáil Committee page:**
  [Committee on the Implementation of the Good Friday Agreement — 33rd Dáil,
  26th Seanad](https://www.oireachtas.ie/en/committees/33/committee-on-the-implementation-of-the-good-friday-agreement/)
  identifies the named Committee, its House context, establishment on
  2020-07-23 and dissolution on 2024-11-08. Its
  [membership history](https://www.oireachtas.ie/en/committees/33/committee-on-the-implementation-of-the-good-friday-agreement/membership/)
  lists Fergus O'Dowd as a member from September 2020 to November 2024. This
  corroborates the real-world Committee and the long membership/operational
  interval reflected by the `115` observation, but the pages expose neither
  Committee code nor Committee ID and do not explain the `156` row.
- **Official 23 July 2020 establishment motion:**
  [Dáil Éireann debate, Establishment of Joint Committee on the Implementation
  of the Good Friday Agreement](https://www.oireachtas.ie/en/debates/debate/dail/2020-07-23/21)
  records the motion establishing the joint Committee; it contains no API
  code/ID correspondence. The similarly named
  [34th Dáil / 27th Seanad Committee page](https://www.oireachtas.ie/en/committees/34/committee-on-the-implementation-of-the-good-friday-agreement/)
  describes a later committee established 2025-05-12. This supports
  term-scoped/reconstituted committees as a general temporal pattern, but does
  not establish that the two 33rd-term API rows are distinct temporal versions:
  those rows coexist under one exact IRI in one Member membership, and the
  `156` row has no Committee operational dates.

The first-party API therefore exposes **both** IDs for the exact IRI; the
official pages expose **neither** numeric ID. The official evidence identifies
the named 33rd-term Committee, but does not establish that either Members
observation is erroneous or authorize temporal/version interpretation of the
same-IRI rows. No defensible resolution is established. The conflict remains an
upstream/source-data blocker; authoritative publication remains fail-closed.

#### Independent audit dispositions and retained contract decisions

- A malformed Committee observation can no longer hide other comparable
  owner-field disagreements: normalized partial evidence participates only in
  conflict detection, never RDF record selection. Invalid optional code/ID
  values are withheld and reported while a valid IRI/HouseTerm may still form
  a closable minimal owner. If a malformed value competes with a comparable
  value for the same mapped field, the identity fails closed. There is no
  invented completeness-ratio threshold; the current contract maps code/ID
  “where supplied” and the census exposes malformed-field counts.
- Online fixtures cannot replace an already authoritative shared graph or
  establish authoritative coverage; they may still exercise non-authoritative
  publication against an empty/non-authoritative graph. The direct online
  Committee publication path now has a regression test covering candidate
  validation, dirty-state publication, graph verification and graph-scoped
  closure-query calls.
- Shared graph publication records the exact Members source-run ID used. A
  later command refuses to rebuild an owner graph from an older complete
  Members capture, preventing a failed newer Member run from causing a
  subsequent standalone refresh to roll owner data back. Identical verified
  payloads can advance this provenance without a redundant PUT.
- No global `committeeCode` uniqueness constraint is added: the preserved
  capture has 35 Committee codes reused across distinct exact IRIs, including
  across HouseTerms. `committeeID` uniqueness is also not an approved identity
  rule. The IRI remains the only consolidation key; no cross-IRI merge is
  performed.
- **Global conflict gate deliberately retained.** Per the accepted tranche
  decision, `build_reference_candidates` rejects the full candidate set when
  any identity conflicts. This Committee conflict therefore blocks publication
  of unconflicted Party/Constituency candidates and current Member graphs as
  well as the Committee graph, and defers their normal dirty-resource retry
  until the preflight passes. Affected-graph/partial publication is not part of
  this tranche. It is deferred to a separate operational-design task if needed,
  because it would create a new contract for mixed source epochs, Member
  publication against partially refreshed references, closure exceptions,
  recovery ordering and authoritative-state semantics. The global
  all-or-nothing behavior is intentional, not an unresolved policy decision.
- The audit's proposed cross-IRI `committeeCode` guard is not added because
  code reuse is present in the authoritative capture and the mapping contract
  defines exact IRI—not code—as identity. Duplicate `committeeID` values are
  not present in this capture, but uniqueness is not specified by the existing
  mapping/ontology contract. Raw-capture integrity now applies the same Member
  graph-code collision checks as Member ETL ingestion, so distinct source IRIs
  cannot pass the completeness boundary and later alias one Member owner graph.
- The Python closure validator uses the shared graph-IRI configuration. The
  graph-specific competency `.rq` remains a static acceptance query with the
  literal named-graph IRI, following the repository's existing query-resource
  pattern; it is not used as runtime publication configuration.

Automated technical validation passed using pinned `temurin-8.0.504+1` through
`mise exec`: ontology validation reported 2,504 triples; mapping-integrity
validation passed; the full suite passed with 580 passed and 9 expected skips.
Synthetic closure, publication/recovery, deterministic/golden and SHACL tests
also passed. The authoritative census was rerun after source review; its raw
capture hash, pagination, endpoint-URL, advertised-count and state-run
provenance checks passed and its counts remain as recorded above. Real-capture
candidate construction correctly stops on the Committee conflict before
closure evaluation. Accordingly, authoritative graph-level closure and
coverage acceptance are not claimed as passing. No production Graph Store was
contacted. Implementation and technical validation are complete; the
authoritative census is complete; authoritative coverage acceptance remains
blocked by this one conflict.


## Phase 5 — Incremental refresh and ETL state

### Outcome

Make routine authoritative refresh restart-safe, idempotent, and efficient,
while allowing external identity links to refresh and recover independently.

The approved Phase 5 architecture and acceptance contract are defined in
`documentation/incremental-refresh-state.md`. That document is authoritative
for state ownership, cursor semantics, complete-source reconciliation,
missing-resource handling, recovery, migration, CLI direction, tranche
boundaries, and Phase 5 exit criteria.

### Architectural summary

- Introduce a core SQLite operational-state store for authoritative ETL runs,
  endpoint state, resource publication state, and incremental cursors.
- Keep the existing schema-v4 `ReconciliationStore` separate and authoritative
  for external identity decisions, external-link publication recovery, and
  periodic rechecks.
- Migrate the existing Member and Bill JSON manifests into core SQLite; do not
  dual-write legacy manifests after migration.
- Preserve immutable raw source evidence independently of operational state.
- Record dirty/pending state before remote graph mutation and mark publication
  clean only after graph replacement and verification succeed.
- Treat extraction completeness explicitly: absence has presence semantics only
  after a successful complete scan, never after an incremental query.
- Use `last_updated` incremental legislation refresh with a configurable
  overlap (one hour by default) and periodic complete legislation extraction.
- Advance the legislation cursor only to the fixed upper boundary of a wholly
  successful incremental run.
- Keep missing-resource handling non-destructive until complete-source evidence
  satisfies the approved confirmation policy.
- Make new or identity-relevant changed entities due in the existing
  reconciliation subsystem; do not introduce a second external queue or
  scheduler.
- Leave deployment scheduling to Phase 6.

### Delivery tranches

1. **Core ETL operational state** — SQLite state model, Member/Bill manifest
   migration, publication recovery, run/endpoint/resource state, and state
   inspection.
2. **Legislation incremental refresh and complete reconciliation** —
   `last_updated` cursor, overlap, deduplication, safe cursor advancement,
   periodic full extraction, missing detection, and graph/state mismatch
   handling.
3. **External reconciliation refresh integration** — identity-relevant
   invalidation/handoff into the existing reconciliation due/recheck model,
   periodic accepted-link verification, and independent retry/freshness.

Implementation is gated in that order. Each tranche must satisfy the
verification and exit checks in
`documentation/incremental-refresh-state.md` before the next tranche proceeds.

### Completion

Phase 5 is complete.

Implementation commits, in tranche order:

- `9c0c9b2` — core SQLite state and legacy-manifest migration;
- `4e60298` — Bills incremental refresh and complete reconciliation; and
- `30e8ec5` — external-reconciliation refresh integration.

The final Phase 5 gate passed ontology validation, mapping-integrity validation,
and 331 tests with disposable Fuseki.

Compatibility decisions retained by the completed implementation:

- legacy Member and Bill manifests are one-time, read-only migration inputs;
- Bills refresh is incremental by default, with `--full` requesting a complete
  scan;
- fixture-backed runs do not advance authoritative source evidence; and
- external due/recheck state remains in the existing reconciliation store, with
  no second queue or scheduler.

If the reconciliation store is unavailable during core publication, the core
run succeeds and warns. External freshness can therefore lag until a later
complete-source reconciliation run. Reviewed external targets that disappear
or redirect are recorded for retry rather than silently replaced. Further
operational hardening of this behavior belongs to Phase 6.

### Exit criteria

Satisfied. Routine core refresh is restart-safe and idempotent; legislation
incremental state cannot advance past unprocessed source time; periodic complete
source reconciliation detects missed or disappeared resources without treating
incremental absence as deletion; and external reconciliation can lag, fail, and
recover independently of authoritative graph publication.

## Phase 6 — Production hardening

### Outcome

Make the authoritative ETL and external-reconciliation processes observable,
recoverable and suitable for unattended production operation without weakening
the deterministic publication and external-enrichment boundaries established in
earlier phases.

### Approved architecture and operating policy

#### Failure handling and quarantine

Failures have three scopes: record, source and run.

- Recoverable record-level transformation failures are quarantined with the
  failing source evidence, processing stage, exception, ETL run, mapping
  version and ontology version. Unaffected resources may continue where doing
  so is safe, and the run is explicitly degraded rather than silently
  successful.
- Source-level failure means that a trustworthy complete view of that source
  cannot be established. An incomplete source view must never be interpreted
  as authoritative evidence that missing resources should be deleted.
- Integrity, state-store, publication or other system failures that make safe
  continuation impossible abort the run.
- Quarantined records are retried automatically on subsequent applicable runs,
  with an explicit manual retry path. Unresolved records remain quarantined;
  historical failure evidence remains available through run history.
- Publication-failure thresholds and retry/retention parameters are
  configurable operational policy rather than transformation semantics.

#### Schema drift

Schema drift is classified rather than treating every source-schema change as
fatal.

- Previously unseen, unused additive JSON properties are reported as warnings.
- Missing, type-changed or otherwise incompatible fields consumed by mappings
  or source contracts fail the affected record/source/run according to their
  impact.
- Drift reporting must identify the endpoint, field/change, severity and
  affected run/source evidence.
- Source-contract tests make the consumed API contract explicit.

The policy is fail-closed where drift could alter semantic output or undermine
source completeness.

#### Provenance

Record provenance at run, published graph/entity and source-evidence level.
Per-triple provenance and RDF-star remain outside the initial scope.

Provenance should be sufficient to answer which source observation and
transformation produced a published resource or graph and should include, where
applicable:

- ETL run identity;
- `prov:wasGeneratedBy` and `prov:wasDerivedFrom`;
- retrieval timestamp and API request;
- immutable source hash;
- ETL version;
- ontology version;
- mapping version; and
- for external assertions, external source, lookup time, matching method and
  evidence.

Create ETL-run resources and a provenance/catalog named graph without making
the semantic RDF dataset the store for mutable operational state.

#### Observability

Use machine-readable structured logs together with persisted run summaries.
Every run has an explicit `success`, `degraded` or `failed` outcome.

Run summaries should record at least:

- extracted, changed and unchanged resource counts;
- published graph count;
- quarantine and validation-failure counts;
- API request/failure counts;
- external reconciliation request/failure counts;
- external-link coverage and pending-review counts;
- reconciliation freshness/degraded state;
- publication outcome; and
- stage/run duration.

A failed run alerts. Degraded runs are recorded and alert when degradation is
persistent or repeated. The notification mechanism and thresholds are
configurable operational settings.

#### Recovery semantics

Prefer idempotent deterministic replay from durable state over a complex
mid-process resume engine.

- Preserve and build on the Phase 5 authoritative and reconciliation state
  stores.
- Make stages safely replayable and publication idempotent.
- Dirty/pending state remains the recovery boundary around remote graph
  mutation.
- Explicit retry tooling may target quarantined work, but recovery must converge
  on the same state as a clean deterministic rerun.
- Reproducibility-critical provenance is retained indefinitely. Detailed
  operational/run history defaults to 12 months, configurable at deployment.

#### External enrichment operations

Authoritative publication remains independent of external enrichment.

- Wikidata, DBpedia or other external-service failure must not fail an otherwise
  valid authoritative Oireachtas publication.
- External failures produce explicit due/stale/degraded state and recover
  through the existing reconciliation store; they never silently substitute
  external identities.
- Cache external responses where permitted and useful.
- Rate limits are configurable per service.
- Transient failures use bounded retries with exponential backoff and jitter.
- Human review remains authoritative for ambiguous/conflicting matches.
- External-link graphs remain independently reproducible and replaceable.
- CI must continue to prove that enrichment statements cannot leak into
  authoritative endpoint-owned graphs.

This formalises the Phase 5 behaviour where the core run can succeed while the
reconciliation store or an external authority is unavailable.

#### Publication atomicity

A candidate graph/dataset is completely transformed and validated before it
replaces the currently published production graph. A failed or degraded build
must not leave Fuseki partially updated. Existing dirty/pending publication
state continues to make interrupted remote mutation detectable and recoverable.

#### Production topology

Use a single production host initially with a Compose-based application stack.
Containers and services are replaceable; durable data is explicitly separated
from them.

The durable/reproducible boundary consists of canonical RDF/source evidence,
core ETL state, reconciliation state, required provenance/run records and
configuration. Fuseki/TDB2 storage is a rebuildable projection rather than the
authoritative persistence layer for ETL state or provenance needed to reproduce
the dataset.

Keep triple-store-specific publication behind the publisher/loader boundary.
A future move from Fuseki to another standards-compatible store may require a
new publication adapter and store-specific validation, but must not require
changing the canonical transformation model.

#### Backup and recovery

Back up canonical RDF/source material needed for recovery, durable ETL and
reconciliation state, required provenance and deployment configuration. Do not
treat Fuseki's internal TDB2 files as the authoritative backup.

Initial configurable operational defaults are:

- recovery-point objective (RPO): no more than 24 hours;
- retention: 30 daily and 12 monthly recovery points using
  deduplicating/incremental backup where practical;
- no formal recovery-time objective (RTO) initially;
- automated backup, retention, integrity checking and backup-age/RPO
  monitoring;
- operator-triggered but scripted restoration and triple-store rebuild; and
- periodic automated restore/rebuild tests against disposable infrastructure.

A configured backup schedule is not sufficient on its own: monitoring and
restore tests must demonstrate that retained recovery points are usable.

#### Scheduling

Use a systemd timer for the initial single-host production deployment, with a
daily authoritative ETL refresh as the initial configurable default. Manual and
scheduled execution must invoke the same application path.

Core refresh and external reconciliation may use different schedules. Do not
introduce Airflow, Kafka or equivalent orchestration until measured workload
requires it.

#### Configuration and secrets

Operational schedules, retention periods, retry limits, alert thresholds and
similar policy values are configuration, not ETL semantics.

Keep non-secret environment/deployment configuration in version control where
appropriate. Inject credentials and other secrets externally at deployment or
runtime. Secrets must not be embedded in container images, RDF, run/provenance
records or ordinary backups unless the backup mechanism explicitly protects
them.

#### CI and release gate

Use a layered CI model:

- normal changes run the fast ontology, mapping, unit, golden RDF, SHACL,
  competency-query and graph-boundary checks appropriate to the change; and
- the release/deployment gate runs a complete production simulation against
  disposable infrastructure.

The release gate must exercise at least:

- a clean-state ETL run;
- an incremental second run and idempotency;
- quarantine, failure and recovery paths;
- schema-drift warning and fail-closed cases;
- external-service outage/staleness behaviour;
- provenance and persisted run summaries;
- external-enrichment graph isolation;
- interrupted/failed publication recovery; and
- reconstruction of a fresh triple store from canonical/durable state.

### Delivery tranches

Implementation is dependency-ordered. Each tranche must satisfy its exit checks
before the next tranche begins.

#### Tranche 1 — Failure model, run records and observability

Implement the operational contract on which later production behaviour depends.

- Add explicit record/source/run failure classification.
- Add quarantine persistence, inspection and retry support.
- Add persisted run records and `success/degraded/failed` outcomes.
- Add structured logging and agreed run-summary counters/timings.
- Add source-contract/schema-drift classification and reports.
- Ensure incomplete/failed source views cannot trigger authoritative deletion.
- Add tests for record quarantine, source failure, fatal run failure and schema
  drift.

**Exit:** failures are classified and diagnosable; recoverable records can be
quarantined without unsafe deletion; every run has a persisted outcome and
useful structured summary; contract-breaking drift fails closed.

#### Tranche 2 — Provenance, publication safety and deterministic recovery

Make successful publication traceable and failed/interrupted publication
recoverable.

- Define provenance vocabulary usage and ETL-run resources.
- Add provenance/catalog graph publication at run and graph/entity/source
  evidence granularity.
- Record software, ontology, mapping and immutable source evidence.
- Enforce complete validation before production graph replacement.
- Exercise dirty/pending Phase 5 publication state through failure/replay tests.
- Add deterministic replay and targeted quarantine-retry tests.
- Verify a rerun converges on the same published state.
- Keep provenance required for reproducibility independent of Fuseki internal
  storage.

**Exit:** each published graph can be traced to its producing run and source
evidence; invalid candidates cannot replace valid production graphs;
interrupted publication is detectable and deterministic replay restores a
consistent result.

#### Tranche 3 — External-enrichment operational hardening

Operationalise the independent external-reconciliation lifecycle established in
Phases 3.5, 4.5 and 5.

- Add configurable per-service caching, rate limiting and bounded
  exponential-backoff-with-jitter retry.
- Persist/report due, stale, degraded and recovery state using the existing
  reconciliation store rather than a second queue.
- Complete reconciliation coverage/review metrics in run summaries.
- Exercise external authority and reconciliation-store outages.
- Verify reviewed targets that disappear/redirect remain retryable and are not
  silently replaced.
- Verify external-link graphs remain independently rebuildable and cannot
  mutate authoritative graphs.

**Exit:** external services can fail, recover and be rebuilt independently while
authoritative publication remains correct and observable.

#### Tranche 4 — Production packaging, scheduling and recovery

Establish the initial single-host production operating model.

- Containerise the ETL application and maintain Fuseki/TDB2 Compose
  configuration with explicit durable-volume boundaries.
- Keep the triple-store publisher boundary replaceable.
- Add environment-specific configuration and runtime secret injection.
- Add systemd service/timer units or generated deployment equivalents using the
  same ETL invocation as manual runs.
- Implement configurable backup/retention/integrity/RPO monitoring.
- Implement operator-triggered scripted restore and fresh triple-store rebuild.
- Add periodic disposable restore/rebuild verification.
- Protect production update endpoints and document operating/recovery
  procedures.

**Exit:** a clean host can be configured from documented deployment inputs,
durable state can be restored, Fuseki can be rebuilt as a projection, scheduled
and manual ETL use the same path, and backup age/integrity is observable.

#### Tranche 5 — Layered CI and production release gate

Turn the Phase 6 operating contract into a repeatable deployment gate.

- Retain fast checks for normal development.
- Add disposable full-stack production-simulation CI.
- Exercise clean/incremental/idempotent runs, quarantine/recovery, schema drift,
  external outage/staleness, provenance/run summaries and graph boundaries.
- Exercise interrupted publication and deterministic replay.
- Restore a retained test backup into disposable infrastructure and rebuild a
  fresh triple store.
- Document the release-gate command/workflow and failure diagnostics.

**Exit:** the complete release gate passes from a clean environment and
demonstrates unattended execution, safe failure, traceable publication,
recoverable durable state and independent external enrichment.

### Phase 6 exit criteria

Phase 6 is complete when:

- routine production execution can run unattended on the initial single-host
  deployment;
- failures are classified, quarantined where safe, visible and recoverable;
- incomplete source evidence cannot cause destructive authoritative updates;
- contract-breaking schema drift fails closed;
- every published graph can be traced to source evidence and software/semantic
  versions;
- publication validates completely before replacement and interrupted
  publication is recoverable through deterministic replay;
- external reconciliation can lag, fail and recover independently without
  changing authoritative assertions;
- canonical/durable state can rebuild a fresh triple store;
- automated backups meet the configured RPO and have a tested restore path;
- operational schedules, retention and alert thresholds remain configurable;
  and
- the layered CI release gate passes against disposable infrastructure.

## Phase 7 — Extend dataset coverage

### Outcome

Extend the graph beyond the initial core Houses, Member and legislation data once the ETL architecture is proven.

Phase 7 proceeds as separate vertical slices:

- Debates, using Akoma Ntoso XML and owning the parliamentary questions and
  divisions/votes contained in each debate record; and
- ministerial office/tenure identities, including reconciliation of Phase 4
  textual sponsor-role labels.

Questions and votes are therefore not separate publication owners from the
Debates slice.

These slices should not block completion of the core ETL system.

### Debates vertical slice

The approved Debates design is recorded in
`documentation/phase-7-debates.md`. The existing ontology-specific baseline
remains `documentation/debates_ontology_outline.md` and
`ontology/debates.owl.ttl`.

**Status:** Debates Tranches 1–4 are complete for the bounded representative
scope. The Tranche 3 evidence review in `documentation/phase-7-debates.md`
explicitly defers unsupported legislative-section and question-recipient
positive competencies; their mappings remain inactive and source references
auditable. The **initial production scope is approved**: all Dáil, Seanad and
committee debate Works dated **2011-01-01 onward**, with written answers
excluded, irrespective of Bill linkage. This is a scope decision, **not**
authorization for broad ingestion. The production-readiness gate remains open
pending configurable Phase 6 operational limits, an exact inventory/disposition
of in-scope malformed sources, and operational acceptance. Tranche 4 supports
explicit AKN acquisition/replay and opt-in supplied-batch publication; it
does not implement production enumeration or scheduling.

Settled boundaries include:

- representative transformation includes Dáil, Seanad, committees and
  written answers, but the approved **initial production load** covers only
  Dáil, Seanad and committee debates dated 2011-01-01 or later. The all-years
  census/benchmark is recorded in `documentation/debates-production-benchmark.md`;
  the separate 2026-10-06 scoped resource assessment informed this decision.
  Neither written answers nor Bill-only filtering belong to the first load.
  Earlier debates and written answers remain explicit expansion work;
- AKN XML is authoritative source evidence;
- Debates owns its questions and divisions/votes;
- transcript text is not copied into RDF; future topic/keyword extraction is
  deferred;
- deterministic resource identity prefers stable AKN identifiers/eIds with a
  documented URI-safe normalization/encoding rule rather than copying awkward
  XML syntax such as raw ampersands into public IRIs;
- XML remains authoritative for complete document order, with only lightweight
  integer source ordinals represented where graph ordering is useful;
- unresolved cross-resource references are preserved/reported without
  inventing placeholder semantic entities;
- one replaceable authoritative named graph is used per Work/debate record;
  any eligible DebateSitting belongs in that same graph;
  and
- Phase 7 supplies source identity, hashing, replay and graph-replacement
  mechanics, while Phase 6 owns production scan cadence, reconciliation
  windows, scheduling and other operational refresh policy.

The approved identity contract uses exact Work and Expression `FRBRuri/@value`
paths with UTF-8 component-wise RFC 3986 percent encoding. The graph URI
replaces `/akn/ie/debateRecord` in the once-encoded Work IRI path with
`/graph/debate`, without a second encoding pass. A sitting IRI `{work IRI}#sitting`
is used only when the approved `FRBRname` and Work-path rule identifies an
actual non-written sitting; written-answer Works receive no `DebateSitting`.
Known multiple Expressions for one Work fail closed for that Work, rather than
publishing a graph from one Expression alone. The full rules are in
`documentation/debates-identity-contract.md`.

#### Debates implementation tranches

1. **Source contract, mapping and fixtures** — complete and implement the
   approved semantic/source contract, verify exact identity/order/reference
   rules against representative Dáil, Seanad, committee and written-answer AKN
   sources, and preserve immutable representative fixtures.
2. **Core debate transformation** — implement records/sittings, sections,
   speeches, summaries, questions, divisions/votes and source order without
   transcript text; run deterministic/golden tests across all four source
   types. Tranche 1 static contract tests do not prove RDF non-emission;
   Tranche 2 goldens must inspect actual RDF for the approved negative cases.
3. **Cross-dataset integration and validation** — resolve existing Member,
   House/HouseTerm/committee and any ministerial or legislative resources with
   reviewed exact source-to-owner evidence; otherwise defer the link explicitly
   and retain auditable unresolved evidence. Add SHACL, quality checks,
   competency queries and graph-boundary tests. The bounded representative
   acceptance and deferred competencies are recorded in
   `documentation/phase-7-debates.md`.
4. **Source ingestion, state and publication mechanics** — preserve AKN input,
   persist source identity/hashes, add replay/idempotency and per-record graph
   replacement through the normal ETL path. The census/benchmark of all
   in-scope XML (including `writtens`), runtime and RDF output/working storage
   required before broad ingestion has been measured and is recorded in
   `documentation/debates-production-benchmark.md`. The initial 2011+
   debates-only scope is now selected; operational limits, exact quarantine
   inventory and production-scale acceptance remain outstanding. Production
   scanning cadence and scheduling policy remain Phase 6 work.

#### Debates backlog

- [x] Review the existing Debates ontology baseline, including question and
  division/vote coverage.
- [x] Define authoritative source, scope and RDF ownership.
- [x] Define graph granularity and cross-resource resolution policy.
- [x] Define the Phase 6/Phase 7 refresh responsibility boundary.
- [x] Complete and verify the approved Debates mapping specification against
  the ontology and semantic-review contract.
- [x] Audit representative Dáil, Seanad, committee and written-answer source
  structures and preserve byte-checked fixtures.
- [x] Choose the initial production scope using the corpus census and scoped
  resource assessment: **Dáil, Seanad and committee debate Works from
  2011-01-01 onward, excluding written answers**; no Bill-only filter.
  This decision does not close the production-readiness gate.
- [ ] **Before initial ingestion — exact quarantine inventory:** inspect every
  in-scope Work and record affected source URL, Work/Expression IRI, preserved
  SHA-256, failure category, source evidence, review status and decision.
  Quarantine without modifying source or publishing partial RDF. The
  2026-10-06 scoped assessment estimated approximately 301 exceptions, not
  301 confirmed records: reconcile the earlier seven 2011–2012 failures with
  the later eight exact pre-2013 exceptions (including a URL/Expression mismatch)
  and determine the exact post-2012 committee count. Preserve the inventory
  and link its report here when available.
- [ ] **Before initial ingestion — operational limits:** approve configurable
  Phase 6 warning/stop thresholds and space headroom for Fuseki/TDB2, raw XML,
  immutable reference-report sidecars, Core State, temporary data and backups.
  Values suggested by the scoped assessment are proposals, not yet approved.
- [ ] **Before initial ingestion — production readiness:** complete safe
  enumeration/selection of the approved period through the Phase 6 operational
  pathway and staged acceptance of publication, verification, quarantine and
  recovery. Tranche 4's explicit-record CLI is not a production census or
  scheduling facility.

**Deferred beyond the initial 2011+ debates-only load (not prerequisites
unless new evidence affects its safety):**

- [ ] **Earlier Dáil/Seanad/committee debates (1919–2010):** reassess historical
  scope and resource limits when expanding coverage; investigate the
  concentrated 2004–2007 duplicate-eId problem and other historical failures
  with reviewed, deterministic compatibility rules, not silent normalization.
- [ ] **Written answers from 2013 onward:** reconsider as a separately scoped
  ingestion tranche once their additional RDF, TDB2, sidecar and Core State
  footprint is worthwhile and operationally acceptable.
- [ ] **Written answers before 2013:** resolve the section-fragmented AKN
  source problem with an explicitly approved complete-Work/reconstruction
  design; never publish a section fragment as the full Work graph.
- [ ] **Legislative-section → Bill/Event crosswalk:** revisit only with
  reviewed source-to-owner identity evidence and a demonstrable use case.
  Until then, retain auditable unresolved outcomes and inactive mappings.
- [ ] **Question-recipient → office/role crosswalk:** revisit only with a
  reviewed AKN TLCRole-to-NamedOffice/ParticipationRole mapping that respects
  historical identity. Do not infer links from labels.
- [ ] **Optional semantic enrichment:** topic/keyword extraction and
  committee rollCall attendance RDF remain separate future work.
- [x] Implement Debates Tranche 4 explicit source preservation, Core State,
  validated supplied-batch transformation, opt-in graph replacement, exact
  verification, and replay/retry acceptance; production enumeration remains
  outside this tranche.
- [x] Add Debates SHACL/quality validation and competency queries; positive
  legislative-section and question-recipient owner results remain deferred.
- [x] Add deterministic graph replacement and replay/idempotency tests.

### Ministerial office/tenure slice — approved design; Tranches 1–6 complete

The first ministerial office/tenure vertical slice has a complete approved
implementation design in [phase-7-ministerial-offices.md](phase-7-ministerial-offices.md).
Tranches 1–3 are implemented, including the new ontology vocabulary,
reviewed office/unit registry publication, local source-observation review and
the occurrence/evidence ledger. The initial registry and decisions are a small,
high-confidence bootstrap, not comprehensive coverage. Tranche 3 migrated the
active Member mapping and graph publication to accepted holdings and derived
Cabinet episodes; the Member contract is now version 3. Its validated
migration/whole-graph replacement removes legacy office RDF. The captured full
Member run completed deterministically; malformed nested office and party
evidence remains quarantined under the existing non-destructive policy.
Production graphs were not mutated during Tranche 3 verification. Tranche 4
implemented reviewed external office identity reconciliation with independently
replaceable per-office link graphs; see
`documentation/office-external-reconciliation.md` for its contract and
verification record. Tranche 5 adds independently replaceable local Bill
sponsor office/holding links with source Bill evidence unchanged; see
`documentation/bill-sponsor-reconciliation.md`. A known
conservative limitation remains: if an accepted holding loses its entire
containing House membership, the prior Member graph is retained and publication
for that Member is blocked pending review. See
`documentation/office-observation-reconciliation.md` for verification evidence
and operational details. Bill **core** RDF behavior remains unchanged.
Tranches 1–5 were implemented and merged on master; Tranche 6 acceptance is
complete as recorded below. This closes only the ministerial office/tenure
vertical slice; it does not change the separate Debates status above or claim
that all Phase 7 work is complete.

Settled semantics and ownership for this slice:

- A locally controlled `NamedOffice` is an enduring particular office,
  independent of holder, label, Department and responsibilities. A locally
  controlled `AdministrativeUnit` is a distinct enduring unit; ISAD IDs and
  replacement events are evidence, not automatically separate local units or
  office successions. Office succession needs reviewed positive evidence.
- `NamedOffice` has explicit `hasRoleType` links to **distinct `OfficeType`
  concept individuals** such as `MinisterOfficeType`. Existing `*Role` IRIs
  remain OWL classes only: no class/individual punning and no typing a
  particular office as a generic role class. The ETL's versioned category
  table determines Cabinet qualification without an unnecessary RDF
  concept-to-class link.
- A departmental Minister's office `headsAdministrativeUnit`; a Minister-of-
  State office `assignedToAdministrativeUnit` and does not imply headship.
  Minister-of-State office identity is department-level, not one office per
  portfolio or delegated responsibility. Those functions remain separate.
- A Member graph owns dated `OfficeHolding`s, their Oireachtas-derived dates
  and generated `CabinetMembership`s. Source office observations have no
  stable record IRI; persist their correspondence so an identifiable holding
  survives a date correction. An unresolved observation emits no guessed
  holding. Once person and office resolve, generation is automatic unless
  ambiguity or material conflict arises.
- Qualifying Taoiseach/Tánaiste/Minister office-type holdings produce
  constitutional Government membership. Minister-of-State holdings do not.
  Merge overlapping/continuous qualifying intervals so concurrent offices
  never create duplicate Government memberships. Derive the Cabinet episode
  URI deterministically from Member, Government and episode start; a corrected
  episode may change its derived URI. **Do not add a Cabinet identity ledger.**
- Shared `https://data.oireachtas.ie/graph/offices` and
  `https://data.oireachtas.ie/graph/administrative-units` own reference
  descriptions. Member graph replacement cannot erase them. Per-office
  `/external-links` graphs independently own reviewed external identities;
  external evidence never silently changes source-derived holding dates.
- A separate per-Bill `/office-reconciliation` graph owns **local** links
  from a Participation to a supported `NamedOffice`, and to an `OfficeHolding`
  only when person and temporal evidence establish it. Retain the original
  Participation and source `rdfs:label` in the Bill-owned graph. Role text
  alone cannot establish a person.
- Retain and flag a disappeared nested office observation and its previously
  published holding during Member graph replacement. Only a reviewed
  erroneous/revoked-assertion action removes it. A changed identifiable
  observation can update its holding subject to conflict review. Migrate
  away from blanket `MinisterOfStateMembership`, generated occurrence roles
  and active `officeNameUri` use through a versioned, validated Member
  republish, not generic triple deletion.

Tranches 1–6 are **complete**:

| Tranche | Status | Prerequisite/work | Exit criterion |
|---|---|---|---|
| 1. Semantic contract and reference bootstrap | Implemented | Approved design; revised ontology/mapping, distinct category concepts, reviewed office/unit registries, validated shared-graph publication. | Reasoner and mapping checks pass; office/unit graphs publish independently without prematurely changing Member behavior. |
| 2. Observation resolution and holding correspondence | Implemented | Published registries; local review decisions, source-occurrence/evidence ledger, candidate generation and source validation. | Every observation accepted, unresolved or review-required; identifiable corrections retain OfficeHolding keys; no Cabinet ledger. |
| 3. Member holdings and Cabinet migration | Implemented | Reviewed resolutions and migration inventory; Member transform, independent validation, non-destructive nested absence, contract bump and full republish. | Correct concurrent holdings and deduplicated Cabinet episodes; legacy erroneous RDF removed, missing holdings retained and recovery tested. |
| 4. External office identities | Implemented | Stable local offices; policy, reviewed external links, independent graphs and retry/recheck tests. | Reviewed external links replace independently without rewriting authoritative RDF. |
| 5. Bill local sponsor links | Implemented | Published offices/holdings; per-Bill local graph, decisions and change invalidation. | Correct office-only/person-and-time-qualified holding links, unchanged Bill evidence, stale local links cleared. |
| 6. End-to-end acceptance | Complete | Earlier core tranches; joined competency, migration, URI, absence/conflict, publication/isolation tests and operations notes. | Phase 0 validation and full tests pass; graph-scoped recovery and review boundaries verified. |

#### Tranche 6 final verification record (2026-10-06)

Pinned-Java ontology validation passed (2,504 triples); active mapping integrity
passed. The complete test suite passed against an isolated disposable Fuseki
5.1.0 dataset (685 tests, 23 subtests, no optional Fuseki skips), including
graph replacement/recovery, Member contract-v3 migration, office external-link
and Bill-local publication, and exact graph equality proving reviewed office
reconciliation left an actual transformed Debate graph unchanged. The
2026-10-04 captured Members corpus was hash-verified and rerun offline twice;
both N-Quads outputs match the accepted Tranche 3 SHA-256
`345899ca9f8494799b1b8d8fce593aca24b96290ba1058b867d56862b0995be2`.
Malformed office/party evidence remains quarantined; no source bytes were
repaired. No production service or graph was contacted or mutated.

Deferred beyond this slice: detailed delegated functions, responsibilities
and portfolios; temporally qualified office–unit assignments; ISAD
historical-incarnation ingestion; full statutory/constitutional provision-
level grounding (the model must permit this later); unsupported historical
succession; numbered Governments; weaker Cabinet attendance relationships;
competing-date-evidence RDF; and Questions recipient-role reconciliation.
Specific ambiguous identity/tenure/sponsor cases require evidence review, not
invented classifications. See the dedicated design for URI derivation,
review state, validation, migration and tranche-level gates.

Each vertical slice should follow the same extract, transform, validate,
publish and reconcile model as the core datasets.

### Exit criteria

Each implemented Phase 7 vertical slice has explicit RDF ownership,
deterministic identifiers, validation, stable graph replacement and competency
queries, and can use Phase 6 production operations without embedding
environment-specific scheduling policy in its transformer.

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

Phases 0-5 are implemented. Phase 5 completion and its final verification
baseline are recorded above.

The **reference-coverage corrective tranche (Phase 2/3 closure)** above is
pending implementation. It is the focused next step for closing historical
Party/Independent-collection, constituency/panel and Committee owner coverage
from the complete Members source before dependent Phase 7 cross-dataset
integration is treated as closed. It does not redesign the Member model or the
NLQ tool.

ParliamentaryGroup and TechnicalGroup instances remain out of scope without
authoritative API evidence.

Remaining Phase 3.5 evaluation work—`wikiTitle` comparison, coverage metrics
and sampled false-match measurement—remains deferred unless directly required
to preserve or validate the generic reconciliation refactor.
