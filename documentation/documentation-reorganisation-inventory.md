# Complete Documentation Reorganisation — Tranche 1 Inventory

**Status:** Complete inventory and recommendation for human review; no moves,
deletions, or implementation changes are made by this tranche. Reviewed against
`master` (`c2cd3e4`, 2026-10-30). The register is a proposal, not approval to
execute Tranche 2.

## Scope and inventory method

`git ls-files` on this branch finds **89 tracked Markdown files** and **2
tracked HTML files** (91 documentation-like text files total). Of the Markdown
files, 11 are under `documentation/wiki/`; 7 are OpenCode agent/skill material,
and `AGENTS.md` is repository operating policy. All tracked Markdown paths are
accounted for below. The two HTML files are application templates, not
documentation: keep them in place (`poc/nlq/templates/capabilities.html` and
`poc/nlq/templates/index.html`). The inventory does not count OWL, CSV, JSON,
Turtle, Python, or other implementation/data files as documents.

The GitHub-hosted Wiki is **not verified**: neither likely wiki remote
(`Oireachtas/OireachtasOntology.wiki` nor `stephenrigney/OireachtasOntology.wiki`)
is available to this checkout (GitHub returned “Repository not found”), and no
Wiki URL/remote is recorded in the repository. `documentation/wiki/*.md` is
tracked repository content and is fully inventoried below; do not assume it is
the hosted Wiki. Human owner should confirm whether another Wiki exists before
closing that part of scope.

## Disposition vocabulary and target structure

- **Keep:** retain a useful document in a canonical location, with only link or
  factual maintenance as needed.
- **Merge:** incorporate unique current material into a named canonical
  document, then retire the duplicate source.
- **Condense:** preserve the necessary contract/instructions while splitting
  completed history, obsolete backlog, and repeated explanation out.
- **Archive:** preserve a completed or evidentiary record under
  `docs/reports/` only where traceability has continuing value.
- **Delete:** remove content that is stale/duplicative and has no enduring
  evidentiary value, after checking inbound references and retaining any unique
  finding. Git history is not a substitute for required operational authority.

Proposed navigation homes are `docs/guides/`, `docs/reference/`,
`docs/architecture/`, `docs/development/`, `docs/reports/`, and exceptional
`docs/archive/`. These are *destination proposals*, not an instruction to
create parallel documents. Existing OWL, mappings, registries, schemas,
executable code, tests and machine-readable contracts remain at their current
canonical paths. During migration, first nominate one existing canonical
document per subject; only create a new page if review establishes that no
existing page can own it.

## Current authority and duplication check

| Subject | Current authority to preserve | Inventory implication |
|---|---|---|
| Ontology meaning | `ontology/*.owl.ttl`; `mappings/*.csv` and `documentation/mapping_notes.md` for mapped field meaning/status | Prose wiki/README/catalogues explain; they do not override executable terms or mapping status. |
| ETL behavior | `src/oireachtas_etl/**`, tests, and the accepted design/ownership boundaries in `documentation/etl-plan.md` | The plan is not a reliable live backlog: it is 2,784 lines and mixes current architecture, completed records, unchecked historical tasks and stale examples. Split current normative contract from milestone evidence; reconcile against code/tests before declaring any detail current. |
| Publication/operations | Current ETL CLI/config/code/tests plus `documentation/production-operations.md`, `documentation/fuseki-user-guide.md`, and narrower state/refresh contracts | Do not copy operating procedures into multiple “reference” and “development” homes. Verify each command/flag against current CLI. |
| Party identity | OWL/mappings; `documentation/political-affiliation-identity.md`, `documentation/political-affiliation-publication.md`, and `documentation/party-reconciliation.md` for their distinct identity, publication and process scopes | Keep identity, publication ownership, and reconciliation workflow distinct; avoid restating a single contract in the Wiki, ETL plan, cookbook, NLQ guide, and review report. |
| Query Service | Current POC implementation, tests and `poc/specs/` contracts; `poc/nlq/README.md` for run/use workflow; benchmark reports for measured results | README (890 lines), roadmap (1,160), approved-question file (754), and redesign docs overlap. The user guide must not silently become an independent semantic/query-planning authority. |
| Debate/office phases | OWL/mappings and current ETL/tests; `documentation/phase-7-debates.md` and `documentation/phase-7-ministerial-offices.md` contain phase-level design/evidence | Multiple debate audits/reports and the 2,784-line ETL plan repeat decisions and status. Keep one current contract; preserve only distinct evidence/results. |

The top-level README still links to the local legacy Wiki and repeats ontology
history/terminology and technical reference material. `ontology/README.md` is a
590-line catalogue with useful module detail but its OWL sources are authority.
The wiki pages are not trustworthy current specifications without claim-by-
claim comparison: many describe planned or older ontology terms. The ETL and
NLQ files are not safely reducible to simple “large guide” rewrites; they
contain material contracts, accepted decisions, evidence, limits and abandoned
backlog mixed together. Preserve that information selectively and visibly
label what's normative, implemented, proposed, and historical.

## Complete disposition register

Every tracked Markdown file is listed. Same-row paths have the same proposed
action and destination; “merge then delete source” means unique verified
material is incorporated before source removal. *Delete* recommendations are
conditional on migration review and inbound-link updates.

| Tracked path(s) | Proposed disposition | Destination / rationale |
|---|---|---|
| `README.md` | Condense | Keep root overview, reliable setup entry points and links only; move ontology explanation to `docs/guides/ontology.md` and runbooks to development/guides. Remove legacy Wiki index and duplicated/obsolete vocabulary prose. |
| `AGENTS.md` | Keep | Repository root operating policy, outside user-document migration; retain its explicit authority links. |
| `.opencode/README.md`, `.opencode/agents/architecture-plan-auditor.md`, `.opencode/agents/executor-high.md`, `.opencode/agents/executor-low.md`, `.opencode/agents/orchestrator.md`, `.opencode/skills/executor/SKILL.md`, `.opencode/skills/orchestrator/SKILL.md` | Keep | Tool/agent operating documentation remains next to its executable configuration; not part of `docs/` reorganisation. |
| `ontology/README.md` | Condense | Keep a short module/source index beside the OWL. If detailed human reference is still needed, merge verified unique usage explanation into `docs/reference/ontology/`; OWL stays authoritative. At 590 lines, it repeats source annotations and historical migrations. |
| `ontology/external-vocabulary-pins.md` | Keep | Keep by pinned ontology sources as provenance/version record; link from reference docs rather than duplicate pins. |
| `documentation/mapping_notes.md` | Keep | Keep in place as mapping-contract companion; mapping CSVs are the field/status authority. Do not merge its semantic mapping meaning into a general guide. |
| `documentation/etl-plan.md` | Condense / split | Retain a concise current ETL architecture, ownership, identifiers, graph and validation contract in `docs/architecture/etl.md` (or maintain this file as the sole canonical page pending approval). Move current operation to `docs/development/`; archive only milestone evidence worth preserving; delete stale completed backlog after code/test reconciliation. Do not create parallel architecture authorities. |
| `documentation/production-operations.md` | Condense | `docs/development/operations.md`; preserve current operational contract and incident/recovery details, verify commands/config against implementation, merge only overlapping current ETL run procedures. 722 lines. |
| `documentation/documentation-reorganisation-inventory.md` | Keep | Retain as the approved Tranche 1 disposition record at its current path until human review and Tranche 2 closeout; do not self-move as part of this inventory. |
| `documentation/fuseki-user-guide.md` | Keep / condense | `docs/guides/fuseki.md`; retain operator-facing local service/query workflow, link to production operations for deployment/production policy. 398 lines. |
| `documentation/incremental-refresh-state.md` | Keep / condense | `docs/reference/etl/state-and-refresh.md`; one source for Core State and refresh semantics, reconcile any overlapping production operations/ETL-plan descriptions. |
| `documentation/houses-etl.md`, `documentation/members-etl.md` | Merge then delete source | Endpoint-specific mapping/run details belong in one `docs/reference/etl/endpoints.md` or linked endpoint reference only if still useful; check against code and tests. Avoid multiple per-endpoint copies of shared ETL contract. |
| `documentation/house_model.md` | Merge then delete source | Merge any distinct historical rationale into `docs/architecture/etl.md`; otherwise delete as superseded by ontology source and accepted ETL contract. |
| `documentation/ontology-guide.md` | Keep / condense | `docs/guides/ontology.md`; practical introduction only, checked against OWL. Avoid duplicating detailed ontology README tables. |
| `documentation/sparql-cookbook.md` | Keep / condense | `docs/guides/sparql-cookbook.md`; keep tested query recipes and link to ontology reference; remove duplicated political-affiliation authority text. 532 lines. |
| `documentation/direct-graph-exploration.md` | Keep / condense | `docs/guides/graph-exploration.md`; retain local read-only exploration steps, eliminate overlap with Fuseki runbook and fix paths after approval. |
| `documentation/private-beta-deployment-plan.md` | Keep / review | `docs/development/private-beta.md`; current gated deployment plan, clearly label proposal/status; coordinate with production operations without merging security gates into functional query acceptance. |
| `documentation/political-affiliation-identity.md` | Keep / condense | `docs/architecture/party-identities.md`; current reviewed identity distinctions and decision rationale. The ontology is executable authority. |
| `documentation/political-affiliation-publication.md` | Keep | `docs/reference/graph-publication/political-affiliations.md`; distinct graph/predicate publication contract, link to identity model. |
| `documentation/party-reconciliation.md` | Keep / condense | `docs/development/reconciliation/parties.md`; workflow, review and evaluation contract only. Do not duplicate identity semantics or external graph publication policy. |
| `documentation/bill-sponsor-reconciliation.md` | Keep / review | `docs/reference/etl/sponsors.md`; verify against current implementation/contract and merge only if it documents active supported behavior. |
| `documentation/member-reconciliation.md` | Keep / condense | `docs/development/reconciliation/members.md`; distinct member reconciliation workflow; link to shared party/identity policy instead of restating it. |
| `documentation/institutional-reconciliation.md` | Keep / condense | `docs/development/reconciliation/institutions.md`; current review policy and process, preserve historical disambiguation decisions; verify runtime status. 795 lines. |
| `documentation/parliamentary-member-collection-model.md` | Keep / condense | `docs/architecture/member-collections.md`; accepted model and rationale; OWL remains normative. Remove duplicate implementation checklist once checked. |
| `documentation/ministerial-office-registry.md` | Keep | `docs/reference/etl/offices.md`; registry/contract explanation beside machine registry and its review rules; avoid redefining office identity elsewhere. |
| `documentation/office-occurrence-ledger.md` | Keep | `docs/reference/etl/office-occurrences.md`; narrowly scoped active ledger contract. |
| `documentation/office-observation-reconciliation.md`, `documentation/office-external-reconciliation.md` | Merge / condense | `docs/development/reconciliation/offices.md`; consolidate shared office reconciliation procedure while preserving locally distinct observation vs external identity semantics. |
| `documentation/debates-mapping.md` | Keep / condense | `docs/reference/etl/debates.md`; current mapping/implementation contract, reconcile every claim with OWL/mappings/code. |
| `documentation/debates-identity-contract.md` | Keep / merge | `docs/architecture/debate-identities.md` or a clearly separated section of debate reference; keep accepted identity constraints, avoid duplicate active design in phase plan. |
| `documentation/phase-7-debates.md` | Condense / split | Move accepted, implemented contract to one debate reference; retain distinct phase acceptance/evidence in `docs/reports/debates/`. Remove completed checklist after useful evidence is captured. 540 lines. |
| `documentation/phase-7-ministerial-offices.md` | Condense / split | Move current office contract to office reference; archive only materially useful tranche evidence. Keep no duplicate implementation checklist. 407 lines. |
| `documentation/debates_ontology_outline.md` | Merge then delete source | Compare with current debate OWL and debates-mapping; merge any unique enduring explanation into one reference, delete superseded outline. |
| `documentation/debates-handoff.md`, `documentation/debates-tranche-1.md` | Archive or delete | Archive under `docs/reports/debates/` only if the handoff/phase decision remains necessary evidence; otherwise delete after unique decisions are transferred to current reference. |
| `documentation/debates-production-execution-plan.md` | Archive / condense | Preserve any executed acceptance evidence in `docs/reports/debates/`; retire the plan/checklist as active instructions after checking completion against implementation and retaining unique rationale. |
| `documentation/debates-controlled-staging-report.md`, `documentation/debates-local-snapshot-completion.md`, `documentation/debates-production-benchmark.md`, `documentation/debates-production-readiness.md`, `documentation/debates-production-resource-assessment.md`, `documentation/debates-semantic-review.md`, `documentation/debates-source-audit.md` | Archive / selectively merge | `docs/reports/debates/`; preserve distinct evidence, benchmark, readiness and audit results that support decisions. Condense repeated status and duplicate conclusions; do not treat reports as current implementation instructions. Readiness report (822 lines) particularly needs a clear superseded/current status. |
| `documentation/phase-4-legislative-lifecycle.md`, `documentation/phase-5-refresh-operations.md`, `documentation/phase-6-tranche-a.md`, `documentation/phase-6-tranche-c.md` | Archive / selectively merge | `docs/reports/etl/`; completed phase records only when they contain distinct accepted decisions/evidence. Move any still-current contract to a single reference first; remove duplicated phase checklists. |
| `documentation/query-service-completion-evidence.md` | Archive | `docs/reports/query-service/`; preserve outcome and exact acceptance evidence, link from user guide/roadmap. |
| `documentation/query-service-completion-progress.md` | Merge then delete source | Merge any final nonduplicated evidence into completion-evidence report; progress snapshots are superseded by final record. |
| `documentation/member-nested-evidence-audit.md` | Archive / merge | `docs/reports/members/`; preserve distinct source audit evidence if relied on by reconciliation decisions; otherwise merge findings into the current member reconciliation record and remove redundant audit. |
| `documentation/query-service-q06-slice.md` | Merge / condense | Query Service semantic contract/reference only after checking current code, tests and query schema; eliminate duplicate/conflicting Q06 explanations in POC README and old wiki. |
| `poc/nlq/README.md` | Condense | `docs/guides/query-service.md` or retain as the single POC README (choose one owner); keep quickstart/config/use and links to specification/evidence. Split operational bootstrap, architecture contracts and results rather than reproducing all three. 890 lines. |
| `poc/specs/query-service-plan.md` | Condense | `docs/architecture/query-service.md` (or retain as sole plan), distinguish accepted implemented design from future direction; reconcile all “current baseline” text against code and README. 1,160 lines. |
| `poc/specs/query-service-questions-approved.md` | Keep / condense | `docs/reference/query-service/approved-questions.md` only if it remains an actively maintained semantic contract; otherwise keep in `poc/specs/` as machine-adjacent specification. Must not duplicate benchmark cases or capability catalogue. 754 lines. |
| `poc/specs/query-plan-redesign-design.md`, `poc/specs/query-plan-redesign-requirements.md` | Merge / archive | Merge accepted decisions into the current query-service design/reference; archive separately only if historical rationale is valuable; delete superseded requirements/design after link audit. |
| `poc/specs/query-service-completion-campaign.md` | Archive / merge | Archive under `docs/reports/query-service/` if it supplies needed phase evidence; final user-facing outcome belongs in completion evidence, not as a second active plan. |
| `poc/nlq/benchmarks/realistic-phase2-report.md`, `poc/nlq/benchmarks/phase-2-controlled-capability-expansion.md`, `poc/nlq/benchmarks/phase-2c-report.md` | Keep / archive | `docs/reports/query-service/`; preserve measured results and limitations; realistic phase-2 report is the key current benchmark record and is linked by README. Clarify which is final vs supporting evidence. |
| `poc/nlq/benchmarks/phase-1a-baseline.md`, `poc/nlq/benchmarks/phase-1b-baseline.md`, `poc/nlq/benchmarks/phase-1-completion.md`, `poc/nlq/benchmarks/phase-1c-report.md`, `poc/nlq/benchmarks/phase-1d-report.md` | Archive / merge | `docs/reports/query-service/history/`; retain only historical comparisons/unique evidence; fold meaningful baseline comparisons into the final report and remove redundant snapshots after approval. |
| `poc/nlq/benchmarks/development-data-evidence.md` | Keep / archive | `docs/reports/query-service/`; retain reproducibility/evidence if still needed by benchmark claims; otherwise merge into the relevant final report. |
| `poc/semantic-enrichment/README.md` | Keep / condense | Keep as POC-specific entrypoint adjacent to code or move to `docs/guides/`; clarify experimental status and link to current specification. |
| `poc/semantic-enrichment/plan.md` | Keep / condense | `docs/architecture/semantic-enrichment.md` only if still active; distinguish proposed work from current ETL authority, keep implementation-adjacent if plan is only for POC. |
| `poc/semantic-enrichment/results/eurovoc-evaluation.md`, `poc/semantic-enrichment/results/summary.md` | Archive / merge | `docs/reports/semantic-enrichment/`; preserve evaluation evidence, make summary point to detailed result and remove repeated conclusions if redundant. |
| `reports/party-identity-review.md` | Keep / archive | `docs/reports/party-identity-review.md`; preserve review/evidence, but link to current identity/publishing contracts and label as report, not normative source. |
| `documentation/wiki/Home.md`, `documentation/wiki/Agents.md`, `documentation/wiki/Bill-Classes.md`, `documentation/wiki/Bill-Properties.md`, `documentation/wiki/Bills.md`, `documentation/wiki/Concept-Schemes.md`, `documentation/wiki/Debates-body.md`, `documentation/wiki/Debates.md`, `documentation/wiki/Departments.md`, `documentation/wiki/Members.md`, `documentation/wiki/Ordering-Business.md` | Merge then delete source (conditional) | Compare individual claims with current OWL, mappings, source implementation and user-facing guides; incorporate only distinct accurate explanatory material into `docs/guides/`/`docs/reference/`. Delete stale/duplicated pages only after inbound links are migrated. `Ordering-Business` has no established current implementation authority; do not migrate as fact without verification. |

## Conflicts, obsolete material and reference audit

1. **PR #2 is already merged into `master`.** Git evidence: `origin/master` is
   `c2cd3e4`, a merge of PR #2; its nine identity-refresh changes are ancestors
   of this branch (including the README, ontology README, Wiki Members,
   cookbook, direct exploration, party reconciliation and identity pages). The
   draft in PR #3 incorrectly describes PR #2 as unmerged and says it contains
   nine updates that must still be merged or superseded. Replace that dependency
   with “already on base; treat its edits as existing material and consolidate
   only once.” No separate PR #2 merge is pending.
2. **Authority duplication:** wiki pages and top-level/ontology READMEs repeat
   vocabulary/class/property descriptions. The live OWL files and mappings
   control; do not make a wiki-derived description a second reference authority.
   Preserve explanatory content only after term-by-term verification.
3. **ETL backlog contradictions:** the ETL plan interleaves settled implementation
   records with numerous unchecked tasks and older examples. It can be mistaken
   for current backlog even where code/docs state delivery. The tracked file is
   2,784 lines; disposition is not “delete the plan,” but review its normative
   decisions against implementation, tests and later accepted phase records,
   then separate only present-day contract from historical evidence.
4. **NLQ overlap/status:** POC README, roadmap, approved questions, redesign
   specs, completion reports and Q06 note all describe capabilities/semantics.
   README says Phase 2 is complete and links the realistic benchmark; the roadmap
   has older “current baseline” and future-facing language. A single contract
   plus a single user guide and reports is preferable, but exact canonical
   ownership and any plan retirement need human confirmation.
5. **Wiki-era content:** local wiki pages are historical-style content, not
   proven current specs. `Ordering-Business` and some Bills/Debates/Departments
   pages describe areas not clearly evidenced by current ETL. Do not claim
   implemented support based on those pages.
6. **Internal links:** checked 201 local Markdown destinations. There are no
   missing ordinary repository-relative links outside the Wiki-style path
   conventions and the issues below; GitHub Wiki slug links (extensionless and
   case-insensitive) need separate handling if pages are retired. The root
   README and wiki Home use scheme-less `www.w3.org/...` links, which resolve as
   relative paths in Markdown; change to `https://www.w3.org/...` during approved
   link cleanup. `documentation/wiki/Members.md:160` contains three relative
   links (`political-affiliation-identity.md`, `political-affiliation-
   publication.md`, `query-service-q06-slice.md`) that resolve inside
   `documentation/wiki/` and do not exist there. The reference audit found the
   same legacy page links in root README and Wiki Home; these are intentional
   only while the local Wiki export remains. Update all inbound paths before
   any move/delete.
7. **Cross-references from implementation/docs:** references to
   `documentation/etl-plan.md` occur in AGENTS and OpenCode guidance, ETL
   comments, `phase-7-*`, query-service evidence and semantic-enrichment plan;
   other docs refer to `documentation/wiki/Departments.md`, Q06, party policy,
   and `poc/nlq/README.md`. Migration must update those references in the same
   tranche. Keep `AGENTS.md` and OpenCode materials outside the docs migration,
   but update their authority links only with explicit project approval if the
   ETL authority path changes.

## Verification completed and approval gate

- Inventory coverage: 89 tracked `.md` paths enumerated; this includes all 11
  local wiki pages, all README files, reports, phase plans, POC specs, and
  agent/skill documentation. Two tracked `.html` templates are explicitly
  classified as application UI, not docs. 91 total Markdown/HTML files.
- Primary proposed dispositions across those 89 Markdown documents: **36 keep,
  8 condense, 21 merge, 24 archive**. Some merge/archive recommendations retire
  their source only after verified unique content is transferred; no immediate
  delete is proposed without that review.
- Link check: 201 local Markdown link destinations examined; Wiki slug-style
  links are separated from normal repository links. Scheme-less W3C links and
  three nonexistent Wiki Members links recorded above.
- Authority check: canonical targets retain OWL/mappings, ETL source/tests,
  machine registries and schemas as authorities; proposals consolidate prose
  and explicitly avoid duplicating existing owners. The route to a sole
  canonical page for ETL and Query Service remains subject to human choice.
- Repository state: this branch is `docs/documentation-inventory-20261030`,
  based on `master`; the only intended tracked change is this inventory.

**Approval required before Tranche 2:** confirm whether a separate hosted Wiki
exists; approve the proposed canonical locations/owners (especially ETL and NLQ
contracts); choose which historical debate/NLQ/phase evidence merits archival;
approve conditional deletion of stale/duplicate sources after claim and inbound
link review; and resolve whether the target `docs/` tree is accepted. This
document does not authorize moves/deletions, implementation changes, or merge
of the inventory PR.
