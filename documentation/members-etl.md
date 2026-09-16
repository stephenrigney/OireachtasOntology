# Phase 3 Members ETL decisions

Member graphs are named `https://data.oireachtas.ie/graph/member/{percent-encoded memberCode}`.  `memberCode` must equal the decoded final segment of `member.uri`.

Nested records with no source IRI use a parent-scoped IRI with a SHA-256 digest of canonical, identity-bearing JSON. Canonical JSON sorts object keys and treats only the full approved schema paths (`memberships.membership.*`) as unordered; unknown arrays retain source order. Date ranges use stable fragments of their parent membership IRI. Exact duplicate Member records coalesce; divergent records with the same `member.uri` fail.

Members own only Member, membership, generated role, and generated date-range descriptions. House/HouseTerm, Party, constituency/panel and Committee IRIs are references. Historical reference acquisition remains follow-up work: current reference endpoints do not cover the historical IRIs in Member history.

Member roots and agent terms use `https://data.oireachtas.ie/ontology#`; every membership, Party, constituency/panel, role and DateRange term uses `https://data.oireachtas.ie/ontology/members#` (including `members:Independent`).

The Members refresh manifest defaults outside the checkout, at `~/.local/share/oireachtas-etl/members-state.json`, and can be overridden with `--state-file` or `OIR_MEMBERS_STATE_FILE`. It records a published source hash only after graph replacement and competency verification. Missing Members are retained and reported, never deleted automatically.

Online runs take an advisory exclusive lock on `<state-file>.lock` for extraction, publication, and state updates. A state file must therefore be shared by only one concurrent writer.

Before every PUT the atomically written manifest marks that Member dirty with a pending source hash and graph IRI while retaining the last successful published hash. Only a clean matching entry may skip. PUT and per-PUT exact graph-count/core competency gates must succeed before the entry becomes clean and advances its published hash; failures remain dirty and are republished on the next run, including after source reversion. The five fixture-backed semantic competency queries are integration acceptance across all Member graphs, not per-record production PUT checks.
