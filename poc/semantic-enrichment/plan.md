# EuroVoc Semantic Enrichment — Bounded Evaluation Plan

**Status:** Approved PoC scope; implementation not yet authorised by this document alone.
**Repository:** `stephenrigney/OireachtasOntology`
**Working branch:** `eurovoc-evaluation`
**Owner review:** One final evidence-based decision gate; escalate only material blockers.

## 1. Purpose and hypothesis

Evaluate whether classifying parliamentary debate contributions against the official EuroVoc subject vocabulary materially improves **knowledge-graph-first retrieval** over the existing Oireachtas RDF model and a simple taxonomy-label/keyword matching baseline. This is an enrichment experiment, **not** a replacement for the existing Elasticsearch-based full-text search application or an attempt to build a second search platform.

The experiment must show which questions can be answered or answered better through subject links and SKOS relationships in Fuseki, at what classification quality and local computing cost. A negative result is acceptable. Avoid treating attractive example queries as evidence of effectiveness.

Related authoritative contracts: `documentation/phase-7-debates.md`, `documentation/debates_ontology_outline.md`, `ontology/debates.owl.ttl`, `poc/specs/query-service-plan.md`, and current repository ETL/state/publication guidance. Inspect their **current** versions before implementing; this plan does not override them.

## 2. Approved boundaries

- **Corpus:** At most 1,000 identifiable debate contributions. Predominantly post-2011 Dáil, Seanad and committee material, with a small deliberately selected pre-2011 historical sample to probe vocabulary drift. Record actual counts by period, House, contribution type and source. Do not claim the historical sample represents all earlier debates.
- **Written answers:** May be included in a small, explicitly labelled exploratory stratum if preserved suitable sources are available; they are **not** part of the approved initial post-2011 production debates load. Do not infer production coverage from PoC sampling.
- **Source:** Reuse preserved AKN XML and source identities when available. Do not undertake a corpus-wide download or production ingestion. The agent must confirm stable contribution/section identifiers against the existing Debates model; provisional PoC identifiers are allowed only if documented and reproducible.
- **Vocabulary:** Obtain an official EuroVoc SKOS/RDF release from an authoritative source; record source URL, licence, release/version, retrieval date, checksum, languages used and relevant concept counts. Prefer English labels, including alternatives, and inspect broader/narrower relationships. Never fabricate concept URIs.
- **Methods:** Compare (A) a straightforward EuroVoc preferred/alternative-label or keyword baseline with (B) a CPU-only semantic candidate matcher (small embedding model or equivalent). Optional lightweight disambiguation is permitted within budget. Do not require Jev, an LLM service, model training, a GPU or a new persistent vector/search service.
- **Infrastructure:** Disposable/isolated Fuseki dataset only. No publication to production Fuseki, no changes to authoritative ETL state, no modification of production ontology mappings, and no changes to Query Service implementation/contracts. The original execution boundary prohibited merging or pushing this experiment to master; a subsequent explicit instruction authorized merging the completed, isolated PoC on 2026-10-09. That authorization does not permit production integration or publication.
- **Local resources:** 16 GB host RAM, **target at most 4 GB peak resident memory for the classification process**, CPU-only. Use bounded batches and a bounded runtime experiment; record actual peak memory, wall time, model size and disk use. Reduce batch size or sample before breaching practical host limits. Model and source caches must not be committed.
- **Autonomy:** The executor may choose libraries, model, thresholds, evaluation samples, provisional predicates and internal layout, and correct ordinary implementation/test issues without review. Keep dependencies minimal and choices replaceable.

## 3. Intended workflow and RDF boundaries

1. Inspect current Debates AKN acquisition/replay, contribution identities, source preservation and graph naming. Select a reproducible stratified sample; document selection and any excluded/unavailable records. Prevent near-duplicate or same-debate leakage between development and evaluation subsets.
2. Load a pinned EuroVoc release into its own named graph in disposable Fuseki. Validate SKOS identifiers, language labels, hierarchy queries and version provenance.
3. Extract contribution text **offline** from preserved AKN. Do not copy full transcript text into RDF. Keep a stable source pointer, text checksum and relevant contribution metadata in local evaluation artefacts.
4. Implement the simple label/keyword baseline and semantic matcher over the **same** contributions and candidate EuroVoc concepts. Allow multiple subjects or no assignment; document selection policy, confidence meaning, limits and abstention. Similarity scores are not automatically calibrated probabilities.
5. Produce separate, disposable **derived enrichment named graphs** linking identifiable contribution resources to verified EuroVoc concepts. Use provisional RDF terms if necessary; record classifier/model version, taxonomy release, run ID, source checksum, evidence references and assignment status. Keep tentative/ambiguous suggestions distinguishable from accepted experimental assignments. No destructive update to authoritative owner graphs.
6. Demonstrate read-only SPARQL retrieval joining contributions, existing parliamentary structure and EuroVoc subject links. Include exact-concept and explicitly opted-in narrower-concept queries. Note that SKOS hierarchy does not imply every broader concept should automatically be assigned.
7. Re-run a representative batch with identical inputs and settings and compare stable outputs; explain any nondeterminism.

Use existing project conventions where practical, but do not build a new general-purpose orchestration framework or operational publication pipeline for this PoC.

## 4. Evaluation: incremental retrieval value

Define a compact, frozen evaluation set of realistic questions **before** comparing the methods. Include exact subject retrieval, narrower-subject traversal, parliamentary/date restrictions, cross-period terminology changes and negative/ambiguous cases. Where available, compare against what the existing structured graph can answer without subject enrichment.

Measure and report:

- **Classification:** independently inspectable examples of true/false/uncertain matches and omissions; coverage, abstention and assignment density; baseline-versus-semantic differences. Use a small agent-reviewed reference sample with documented selection and review rubric, preferably evaluated blind to method. This is **provisional** assessment, not a human gold standard or proof of accuracy.
- **Retrieval:** per-question relevant/irrelevant results, missed expected results, examples of added capability over baseline and structured-only queries, and any regression. Report denominators and use precision/recall-style measures only where a defensible reference set exists.
- **Operational:** sample sizes, source/taxonomy/model hashes, elapsed time, peak process RSS, disk footprint, Fuseki graph/triple counts and representative SPARQL timings. State whether estimates extrapolated to the full corpus are speculative.
- **Limitations:** EuroVoc coverage gaps, Irish-specific terminology, historical language drift, long/short contributions, source identity gaps, ambiguity and potential evaluation bias.

The PoC succeeds as an **experiment** if it produces a reproducible end-to-end run, a fair baseline comparison, working RDF/SPARQL examples, inspectable quality evidence and an evidence-based go/modify/stop recommendation. It does **not** require the semantic method to win. No numerical accuracy threshold is pre-approved; do not manufacture one after seeing results.

## 5. Agent execution and escalation

Run in the dedicated `eurovoc-evaluation` branch/worktree. Prefer one bounded Luna Max executor session. No routine intermediate review gate. The executor may make reversible design decisions and commit PoC implementation and documentation to its branch.

**Stop and escalate** if any of the following is necessary: changing authoritative Debates or Query Service semantic contracts; touching production Fuseki or Core State; adding a persistent service; exceeding practical memory/resource bounds despite reduced batches; inability to obtain authentic EuroVoc or suitably identified debate source text; material licence/security concern; or scope expansion beyond the agreed experiment. Do not conceal a blocker with synthetic data or invented identifiers. A fixture-only demonstration may be reported as incomplete, not as measured corpus success.

If routine classifier quality is poor, perform limited bounded diagnosis and report it rather than repeatedly tuning against the evaluation set or silently expanding the work.

## 6. Deliverables and final gate

Expected repository structure (adjust only for strong compatibility reasons):

- `poc/semantic-enrichment/README.md` — concise purpose, prerequisites, commands to reproduce, isolation and cleanup.
- `poc/semantic-enrichment/` — bounded PoC code, tests, sample manifest and/or configuration; no large source/model binaries committed.
- `poc/semantic-enrichment/results/eurovoc-evaluation.md` — method, frozen questions, evidence tables, examples, failures, measured resources, provenance, limitations and recommendation.
- Reproducible RDF and SPARQL fixtures/queries or scripts sufficient to demonstrate retrieval without requiring production access.

Verify local tests, RDF identifier validity, isolated Fuseki import/query, source/graph isolation, bounded memory, and repeatability. Report commands and outcomes, commit hashes, uncommitted changes and any deviations. A full repository test suite is desirable only if relevant and practical; state what was and was not run.

**Human gate:** Review the final report and decide whether to (a) extend EuroVoc work, (b) trial entity linking, (c) investigate topic discovery/Jev, or (d) stop. No automatic Query Service integration, production deployment or broader corpus processing follows from PoC completion.
