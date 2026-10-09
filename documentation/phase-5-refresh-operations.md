# Phase 5 refresh operation

The approved contract is `incremental-refresh-state.md`; this note records the
implemented external-reconciliation handoff and its operational limits.

Online Member and Party core publication uses the core SQLite state store for
authoritative graph recovery. After a graph has been verified and marked clean,
the run marks eligible identities due in the separate schema-v4 reconciliation
store using the existing entity-specific fingerprints. This is a local SQLite
operation, not an external lookup or external-graph publication. A core Member
scan also revisits unchanged records so a missed handoff can be retried without
republishing the core graph. Parties remain complete-refresh endpoint graphs:
another Party core run replaces that graph, even if its identity is unchanged.

If the reconciliation store cannot be opened or marked due, core publication
remains successful and emits a warning to stderr. No second queue is created.
The missed invalidation is recovered by the next complete-source
`reconcile members` or `reconcile parties` run, whose existing fingerprint and
due-state selection detects new and changed identities; an unavailable store
cannot durably record an immediate external due marker. Thus external freshness
can lag until reconciliation runs again. The operator should restore the
reconciliation store and run the appropriate complete-source reconcile command.
Deployment scheduling and monitoring of that retry are outside Phase 5.

Reviewed accepted Wikidata identifiers are checked at scheduled reconciliation
time, including reviewed Parties and institutions without optional Wikipedia
links. Redirected, retired, disappeared, malformed, and unavailable targets are
recorded as retry evidence with a short recheck interval; they do not silently
replace or revoke a human-reviewed identity or clear its accepted graph. A
reviewer must explicitly change a human decision. Offline response fixtures
must provide valid responses for reviewed targets; malformed fixture evidence
is rejected before reconciliation publication.

The existing Member policy fingerprints only its stable member code and the
institutional policy fingerprints its fixed local IRI. Party identity-relevant
changes are determined by the existing Party fingerprint (including name and
House term); unrelated core source changes do not force an external recheck.
Periodic due dates and recovery of dirty external-link graphs remain owned by
the reconciliation store, independently of the core state and Bill cursor.

## External request resilience

Member, Party and institution reconciliation use command-scoped Wikidata and
DBpedia HTTP clients. Successful response bodies are cached only in memory; no
second durable cache or queue is created. Defaults can be overridden with:

| Setting | Default | Meaning |
|---|---:|---|
| `OIR_WIKIDATA_CACHE_TTL_SECONDS` | `300` | Wikidata response cache lifetime; `0` disables caching. |
| `OIR_WIKIDATA_CACHE_MAX_ENTRIES` | `256` | Maximum cached Wikidata responses in one process. |
| `OIR_WIKIDATA_REQUESTS_PER_SECOND` | `2` | Maximum network request rate across Wikidata API/SPARQL calls; `0` disables throttling. |
| `OIR_DBPEDIA_CACHE_TTL_SECONDS` | `300` | DBpedia response cache lifetime; `0` disables caching. |
| `OIR_DBPEDIA_CACHE_MAX_ENTRIES` | `128` | Maximum cached DBpedia responses in one process. |
| `OIR_DBPEDIA_REQUESTS_PER_SECOND` | `1` | Maximum DBpedia network request rate; `0` disables throttling. |
| `OIR_EXTERNAL_HTTP_RETRIES` | `3` | Retries after the initial request, bounded to `0`–`10`. |
| `OIR_EXTERNAL_HTTP_BACKOFF_BASE_SECONDS` | `0.5` | Base for exponential retry delay with full jitter. |
| `OIR_EXTERNAL_HTTP_BACKOFF_MAX_SECONDS` | `8` | Maximum retry delay. |

Retries apply to transient HTTP statuses (408, 425, 429, 500, 502, 503 and 504)
and connection/time-out errors. CLI JSON includes `run_summary` counters for
work selected in this invocation (including `--all`), records whose stored
deadline was already overdue at run start, unresolved or
dirty/degraded current state, and verified dirty-payload recovery. Its coverage
and review metrics identify the exact validated input and review hashes; HTTP
cache/request counters describe only that process. None of these controls call
external services from the authoritative transformation or publication path.
