# Entity Linking — Bounded Evaluation Plan

**Status:** Design plan for review; implementation not yet authorised.
**Repository:** `stephenrigney/OireachtasOntology`
**Working branch:** `entity-linking-evaluation`
**Decision gate:** Review evidence before any production integration or corpus expansion.

## 1. Objective

Determine whether identifying **entities mentioned in parliamentary contributions** and linking them to existing Oireachtas RDF identities provides reliable, useful graph retrieval beyond (a) existing structured Debates participation/metadata and (b) the existing Elasticsearch full-text application. A negative or category-specific result is acceptable.

**All four categories are in scope from the outset:** Members, Bills, ministerial NamedOffices, and AdministrativeUnits (departments). Evaluate them separately; do not quietly drop a difficult category. This is a distinct experiment from EuroVoc subject classification, which remains non-production.

Read current contracts before implementation: `documentation/phase-7-debates.md`, `documentation/debates_ontology_outline.md`, `ontology/debates.owl.ttl`, `poc/specs/query-service-plan.md`, ministerial/Member/Bill ontology and mapping documentation, and `poc/semantic-enrichment/results/summary.md`. This plan does not supersede them.

## 2. Corpus and evidence boundaries

- Use at most **1,000 identifiable speeches/contributions** from preserved AKN, predominantly post-2011 Dáil, Seanad and committee debates, with a small explicitly labelled historical sample. Prefer reuse of the EuroVoc PoC's verified seven-Work sample where it supports all four entity categories; add a small targeted sample if necessary, remaining within the cap. Record category opportunities and selection biases. Do not claim production corpus coverage.
- Preserve source Work/contribution IRIs and provenance. Extract text **offline**; no full transcript text in RDF or Git. Preserve local source pointers, offsets or verifiable spans and checksums. Do not invent authoritative entities.
- Freeze a development/evaluation split at **Work level** before tuning rules. Avoid same-Work and near-duplicate leakage.
- Obtain candidate identities and aliases from existing validated ontology/registry data and reviewed source evidence, not from invented string-to-IRI mappings. Missing owner/reference coverage is an observed limitation, not permission to invent it.
- Do not confuse the speech's speaker, participation, Bill debate section or other structured links with **entities actually mentioned in the transcript**. Evaluate added value beyond those existing links.

## 3. Linking approach

Implement a small shared pipeline: mention detection → typed candidate retrieval → contextual disambiguation → accept/abstain → provisional RDF output. Start with explicit named references; indirect expressions such as “the Minister”, “the Deputy” or “the Bill” are **unresolved by default**, unless source-local context yields a unique, demonstrable antecedent. Do not infer mention from mere topic similarity.

Category-specific constraints:

| Category | Candidate/evidence policy | Failure cases to test |
| --- | --- | --- |
| **Members** | Names, attested aliases, membership dates/House, speaker and local context; distinguish mention target from current speaker | Shared surnames, name variants, historical Members, honorifics, references to a Member who is not speaking |
| **Bills** | Existing Bill identifiers and attested titles, year/session, legislative context and date; prefer exact identifiers where available | Generic “the Bill”, repeated/renamed titles, same-title different years, discussion of a Bill other than the debate's structured target |
| **NamedOffices** | Enduring office registry, title variants and time-valid OfficeHolding evidence; office identity is not automatically the person | “Minister for Finance” as office vs incumbent, renamed offices, generic “the Minister”, historically invalid holdings |
| **AdministrativeUnits** | Reviewed department/unit identities, names, historical aliases and succession where represented | Department renaming, similarly named bodies, organisational references with no supported registry identity |

Use deterministic exact/normalised-name and identifier matching as an explicit **baseline**. The candidate implementation may add bounded alias/rule/context resolution; an ML/NER detector is optional if it materially improves evidence within resource limits. Record which stage produced each link and the grounds for accepting or abstaining. Avoid an LLM service, GPU, model training, new persistent search/vector infrastructure or open-ended tuning for the initial experiment.

Distinguish: (1) detected surface mention; (2) zero/multiple candidate identities; (3) resolved provisional link; and (4) unsupported/ambiguous cases. **Abstention is a valid outcome**, not an error to eliminate. A speech can mention multiple entities of the same or different categories.

## 4. RDF and system isolation

- Generate **separate derived named graphs** in disposable, loopback-only Fuseki; never modify authoritative Debates owner graphs, ontology/mapping contracts, production Fuseki, Core State, Query Service or Elasticsearch.
- Use a documented **provisional PoC vocabulary** for mention occurrences and links. Represent contribution IRI, exact source reference/offset or reproducible span, detected surface form or privacy-safe evidence pointer, target entity IRI (only when supported), entity category, resolver method/version, evidence, source checksum, run ID, status and uncertainty. Do not conflate mentions with asserted participation, sponsorship, officeholding or formal organisational relationships.
- Keep ambiguous candidate lists and rejected/abstained mentions inspectable in local evaluation artefacts; do not emit speculative resolved links as authoritative facts. No full transcript text in RDF.
- Use existing identities where verified. A provisional source mention IRI may be minted deterministically; **target entity IRIs may not be fabricated**.
- Demonstrate read-only SPARQL joins from speech → provisional mention → linked entity → existing House, membership, Bill or office relationships. Explicitly distinguish newly enabled questions from ones already answered by existing structured RDF or Elasticsearch.

## 5. Evaluation design

Before comparing methods, freeze a compact set of practical questions and a category-balanced, independently reviewed mention/reference sample. Include positive, negative, ambiguous, cross-period and misleading-context cases. Ensure examples are not selected solely from successful system outputs. Prefer **human-reviewed** labels; if only agent review is available, call results provisional and do not assert independently established accuracy.

Compare baseline vs contextual resolver on the **same contributions and identities**. Report by category:

- Mention detection: precision/recall where defensible; missed mentions and spurious mentions.
- Entity resolution: correct, wrong, ambiguous, out-of-registry and abstained; accuracy/precision with clear denominators and coverage/abstention trade-off.
- Confusions: office versus officeholder, Member versus speaker, Bill title versus generic legislation, department versus renamed/successor unit.
- Retrieval: frozen question-by-question returned/relevant/irrelevant/missed examples; incremental value against structured-only graph queries and, where feasible, equivalent Elasticsearch searches. Do not count more returned results as proof of better retrieval.
- Operations: corpus/identity counts, runtime, peak process RSS, disk use, named graphs/triples, representative SPARQL timings, source/config hashes and reproducibility.

If a defensible human reference set is unavailable, present qualitative failure analysis and provisional agent-reviewed measures explicitly; do not invent a gold standard. Document category-specific go/modify/stop recommendations rather than one aggregate success score.

## 6. Resources, implementation and stop conditions

- Work only on `entity-linking-evaluation` in a dedicated worktree/session. Prefer one bounded OpenCode executor with autonomous reversible implementation choices and one final human review gate.
- CPU-only on a 16 GB workstation; target **≤4 GiB peak RSS** for linking processes. Keep processing batched and bounded, with no persistent services beyond disposable Fuseki. No large source/model/cache files in Git.
- Reuse useful isolation, manifest, source-verification and reporting patterns from `poc/semantic-enrichment/` without coupling this experiment to its classifier or modifying the EuroVoc result.
- Stop and escalate if completing the experiment requires production state/publication, changes to authoritative semantic contracts, unsupported identity fabrication, a new persistent service, unmanageable resource use, or a material licence/security concern. Ordinary matching errors, poor quality and missing registry coverage should be **reported**, not concealed or repeatedly tuned away.
- Do not merge to `master`, push to `master`, or start production integration without explicit owner approval.

## 7. Deliverables and final decision

Expected layout under `poc/entity-linking/`:

- `README.md`: brief purpose, setup, reproducible run/cleanup and isolation.
- Bounded code/tests, frozen source manifest, question set, review rubric and inspectable evaluation artefacts (without committed transcripts).
- `results/entity-linking-evaluation.md`: technical evidence, denominators, by-category comparisons, graph queries, resource measurements, failures and recommendations.
- `results/summary.md`: 1–2-page human-readable explanation of what was learned and whether entity links added useful retrieval capability.

Verify focused tests, ontology consistency, reproducible sample selection, isolated Fuseki import/SPARQL, graph/source boundaries, abstention behaviour, and representative repeatability; run the full repository suite when practical.

**Human decision:** For each of Members, Bills, NamedOffices and AdministrativeUnits, decide whether to extend, revise or stop. A successful PoC does not automatically authorise authoritative publication, Query Service integration or corpus-wide processing.
