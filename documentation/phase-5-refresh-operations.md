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
