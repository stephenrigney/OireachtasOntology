# Semantic dispatch acceptance: independent holdout methodology

## Purpose and freeze boundary

This is a newly authored semantic-dispatch acceptance set for the query-service worktree. It contains natural-language questions, exact local SPARQL oracle projections, and question-specific scoring/qualification rules. The set is frozen before any `/ask` request. No `/ask` request or implementation/compiler output was used to derive an expected answer. The orchestrator must commit this freeze before any execution or scoring begins.

## Authority and limits

Question semantics were drawn only from `poc/specs/composable-query-plan-contract.json`, `poc/specs/composable-query-plan.schema.json`, `poc/specs/query-schema-contract.json`, and `poc/specs/query-plan-contract.json`, plus the required `docs/architecture/etl.md` orientation. The task-provided `AGENTS.md` was followed. No query-service guide, question set, implementation, tests, git diff, old evaluation, or other report was consulted. No `/capabilities` catalogue was needed. Answers were authored from fresh, direct, read-only `SELECT` queries to `http://localhost:3030/houses/query` only.

The local dataset profile (7,982 graphs / 1,119,860 triples) and reference date (2026-11-06) are task-supplied context. The profile is explicitly nonauthoritative/incomplete: no question or score may interpret local absence as historical nonexistence or a complete roster. Every query is a standalone read-only SPARQL SELECT; raw result bindings preserve RDF URI/literal types, datatype, and language in `oracle-context.json.gz`.

## Question coverage and scoring

There are 44 questions: 38 factual questions, one ambiguity control, and five unsupported/unavailable controls. Coverage spans exact/set-valued Member lookup, Dáil and Seanad service, House-term date/month selection, term and Committee aggregates, seat complement, party/group listing, constituency representation and bounded compositions, collections, Bill title/lookup/publication/sponsor paths, accepted OfficeHolding point/window/episode projections, and Debate metadata. The bounded compositions are only the expressly enumerated exact-identity/shared-resource/term-scoped shapes; no arbitrary relationship closure is assumed.

For factual entity answers, score exact RDF identity sets, not label-only matches. The question oracle includes any requested label/date/episode evidence and per-item qualification rules. Count questions require the exact integer and the stated distinct identity target; they are not seat/election totals. Boolean questions require the expected value and, when positive, the exact relationship evidence. Date comparisons use the public contract's inclusive point/month/interval semantics. Missing end dates are open only where the relevant contract says so. Keep separate episodes and distinguish local recorded evidence from complete coverage.

The group control must list the exact term-scoped party IRIs and report missing ParliamentaryGroup instances rather than inventing a group roster. The ambiguity control requires clarification over the complete distinct Member candidate set; selecting either one and answering the dependent count is incorrect. Unsupported controls must state the contract boundary and must not infer voting from sponsorship, chairing from membership, substantive transcript/topic content from metadata, or nickname identity from resemblance.

Current member/office/party selections require only the exact dated evidence declared by their family. Where current-office or current-roster coverage is explicitly incomplete, the answer must say so and must not present local matches as complete. Shared-resource co-membership is term-wide and does not imply simultaneous service. Party composition joins by exact PartyMembership → same OireachtasMembership → exact term-scoped party and reviewed PoliticalAffiliationIdentity, with inclusive interval overlap; independent collection status is not a party.

## Oracle construction and audit

Each question has its own authored `SELECT` query, endpoint response status, result header, raw bindings, and question-level projection/scoring metadata. Oracle queries are not derived from the `/ask` route or any compiler. Query result sets reaching 100 bindings are rejected to avoid freezing a potentially truncated result. The generation process checks current Seanad-party list/count parity, shared-resource list/count parity, current Seanad/prior-Dáil list/count parity, and equality of the complete sponsorship Bill set between QD-22 and QD-23 before writing any freeze output. QD-23 retains each Bill's typed Published-date evidence and fails closed if any selected Bill lacks it. All `SELECT` statements are read-only; no `ASK`, update, `SERVICE`, `FROM`, or `/ask` call was used.

A possible common-intersection composition candidate using Micheál Martin's Taoiseach holding and Cork South-Central representation was excluded before freeze because the exploratory direct oracle query did not yield a usable joined result. It is not part of this acceptance set, and it will not be replaced based on post-execution behavior.

## Freeze digest

`freeze.json` records the UTC freeze time, file SHA-256 values, and aggregate freeze digest. The aggregate digest is SHA-256 over the UTF-8 path name, NUL, exact file bytes, NUL for each of `holdout.json`, `oracle-context.json.gz`, and `methodology.md`, in that order. The digest intentionally excludes `freeze.json` itself. The compressed oracle file is hashed as stored bytes.
