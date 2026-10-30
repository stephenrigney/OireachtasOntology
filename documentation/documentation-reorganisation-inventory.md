# Documentation reorganisation — Tranche 1 inventory (working draft)

**Status:** Partial inventory, **not yet at the Tranche 1 exit gate**. Reviewed against `master` on 2026-10-30. This document records only paths individually confirmed through the GitHub file interface; a repository-wide file enumeration and link audit remain outstanding. Do not execute moves or deletions from this draft.

## Target structure

- `docs/guides/` — user-facing workflows, query examples, exploration
- `docs/reference/` — implemented ontology, RDF and service contracts
- `docs/architecture/` — current design and accepted decisions
- `docs/development/` — developer setup, testing, operations and active plans
- `docs/reports/` — evidence, benchmarks and evaluations
- `docs/archive/` — exceptional historical records whose original form is needed

Keep ontology sources, mappings, machine-readable registries and executable scripts at their existing canonical paths. The top-level README becomes a short entry point. Do not assume `documentation/wiki/` is the GitHub-hosted Wiki: inventory that separately.

## Confirmed file dispositions (provisional)

| Existing path | Proposed disposition | Proposed canonical home / action |
|---|---|---|
| `README.md` | Condense | Root overview and links; remove duplicated setup and ontology detail |
| `ontology/README.md` | Merge/condense | `docs/reference/ontology/`; keep only a small source-module index beside TTL |
| `documentation/ontology-guide.md` | Keep/rewrite | `docs/guides/ontology.md`; accessible explanation, not competing vocabulary authority |
| `documentation/wiki/Bills.md` | Merge/review | `docs/reference/ontology/bills.md`; verify claims against current ontology |
| `documentation/wiki/Debates.md` | Merge/review | `docs/reference/ontology/debates.md`; verify current coverage |
| `documentation/wiki/Members.md` | Merge/review | `docs/reference/ontology/members.md`; remove duplicate identity descriptions |
| `documentation/wiki/Departments.md` | Merge/review | `docs/reference/ontology/institutions.md` |
| `documentation/wiki/Concept-Schemes.md` | Merge/review | `docs/reference/vocabularies/` |
| `documentation/wiki/Ordering-Business.md` | Verify then merge/archive | `docs/reference/ontology/` only if implemented; otherwise retain useful historical context selectively |
| `documentation/political-affiliation-identity.md` | Keep/condense | `docs/architecture/party-identities.md`; authoritative decisions and historical identity distinctions |
| `documentation/political-affiliation-publication.md` | Keep | `docs/reference/graph-publication/political-affiliations.md` |
| `documentation/party-reconciliation.md` | Split/condense | Current external reconciliation policy in architecture; completed phase evidence in reports only if needed |
| `documentation/query-service-q06-slice.md` | Split/condense | Current Q06 semantics in Query Service reference; evidence/limitations in reports |
| `documentation/sparql-cookbook.md` | Keep/trim | `docs/guides/sparql-cookbook.md`; remove repeated ontology introduction |
| `documentation/direct-graph-exploration.md` | Keep/trim | `docs/guides/graph-exploration.md` |
| `documentation/etl-plan.md` | Split/condense/archive selectively | Current ETL architecture and operations in reference/development; completed phase plan and backlog are historical, not current instructions |
| `poc/nlq/README.md` | Split/condense | User Query Service guide plus development setup; keep PoC-specific material clearly scoped |

**Scale warning:** `documentation/etl-plan.md` is ~2,785 lines; `poc/nlq/README.md` ~891 lines; `ontology/README.md` ~591 lines. These are high-value condensation candidates, not automatic deletion candidates.

## Rules and authority

1. One canonical description of *current* behaviour per subject. Guides explain how to use it; references define it; architecture explains why.
2. Preserve accepted decisions, authoritative contracts, provenance, acceptance evidence and material limitations. Git history alone is not a substitute for necessary traceability.
3. Distinguish reviewed local enduring party identities, term-scoped ParliamentaryParty collections, and external reconciliation. Do not collapse historical Sinn Féin identities or Independent status.
4. Completed plans do not remain active implementation instructions. Prefer concise milestone summaries; archive originals only when the full original has continuing evidential value.
5. Delete duplicates and obsolete instructions only after their unique content has been incorporated or explicitly judged unnecessary.
6. Do not migrate stale claims from wiki pages without checking current OWL, mappings and implementations.

## PR #2 dependency

Draft PR #2 (`docs/party-identity-refresh-20261030`) contains nine documentation updates, but is unmerged and omits the ETL plan. Before the consolidation tranche, decide whether to merge its correct current-contract changes or supersede them with the canonical rewritten pages. Avoid duplicating both sets.

## Outstanding Tranche 1 checks (blocking)

- Enumerate **all** tracked documentation, Markdown, report and planning files, including nested directories and reports outside `documentation/`. The available GitHub file interface confirmed the paths above but did not provide a complete repository tree.
- Inspect current reports, plans, README files in subprojects, and any separately hosted GitHub Wiki.
- Compare candidates against authoritative ontology modules, mappings, Query Service contracts and recent implementation evidence.
- Identify duplicate passages, outdated commands, broken/relative links, inbound links and references from code/scripts.
- Expand this register to **every** document with a keep/merge/archive/delete disposition and record any genuine authority conflict.
- Approve the completed disposition register and target structure **before** Tranche 2 rewriting or file moves.

**Tranche 1 exit criterion:** full coverage and agreed dispositions; no implementation changes, moves or deletions.
