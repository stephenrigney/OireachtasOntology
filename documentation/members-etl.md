# Phase 3 Members ETL decisions

Member graphs are named `https://data.oireachtas.ie/graph/member/{percent-encoded memberCode}`.  `memberCode` must equal the decoded final segment of `member.uri`.

Nested records with no source IRI use a parent-scoped IRI with a SHA-256 digest of canonical, identity-bearing JSON. Canonical JSON sorts object keys and treats only the full approved schema paths (`memberships.membership.*`) as unordered; unknown arrays retain source order. Date ranges use stable fragments of their parent membership IRI. Exact duplicate Member records coalesce; divergent records with the same `member.uri` fail. The party-membership IRI continues to hash the same containing OireachtasMembership IRI, term-scoped collection IRI and source date range; the Tranche 2 type and relationship additions do not change that deterministic identifier.

An invalid office observation is quarantined at its individual
`membership.offices[]` entry: it is reported with a source path/reason and is
not transformed into the legacy office-role triples. Other independently
valid Member content and sibling office observations continue through
validation. Member identity, membership/House context, and a malformed
non-array office collection remain fail-closed. The separate Phase 7 office
occurrence ledger retains any earlier accepted resolution for malformed
current evidence; this behavior does not introduce `OfficeHolding` RDF.

Committee special roles have two observed Members API encodings: the existing
array form (including `[]` when there is no special role), and an object form
with `title` and `dateRange`. The two object titles present in the captured
Members source, `Cathaoirleach` and `Leas-Chathaoirleach`, map respectively to
the existing `members:Chair` and `members:DeputyChair` roles. The object's
`dateRange` is validated and explicitly listed under `future_work_omitted`;
the current Member mapping has no relation for special-role tenure separate
from the committee membership's own `memberDateRange`. Unknown object shapes
or titles remain fail-closed. The published Oireachtas Swagger schema leaves
`committees.items` untyped, so the repeated captured records (rather than a
In the complete Members capture of 2026-10-02, all 317 object-form roles had
exactly this structure: 211 `Cathaoirleach` and 106 `Leas-Chathaoirleach`; all
2,737 array-form roles were empty. Garret Ahearn's instance is at
`/results/4/member/memberships/0/membership/committees/1/role` in
`skip=0&limit=100` (captured page SHA-256
`832a12d7cb701dad7e5ef72169e18ad37a828f40a018d8807550705048471855`).

Members own only Member, membership, generated role, and generated date-range descriptions. House/HouseTerm, ParliamentaryMemberCollection, constituency/panel and Committee IRIs are references. Historical reference acquisition remains follow-up work: current reference endpoints do not cover the historical IRIs in Member history.

Member roots and agent terms use `https://data.oireachtas.ie/ontology#`; every membership, ParliamentaryMemberCollection, constituency/panel, role and DateRange term uses `https://data.oireachtas.ie/ontology/members#`. Each Members API party record is represented as a `members:ParliamentaryCollectionMembership` linked to its containing `members:OireachtasMembership` with `members:inOireachtasMembership`, and to its source collection with `members:memberOfCollection`. A non-`Independent` target additionally uses `members:PartyMembership` and `members:isPartyMembershipOf` (range `members:ParliamentaryParty`); an `Independent` target uses only the general collection membership class and relationship. Parties endpoint resources remain the authoritative descriptions of both collection types. Member graphs do not assert ParliamentaryGroup or TechnicalGroup membership or any party-side/reconciliation assertions.

Member publication state is held in the shared core ETL SQLite database, defaulting to `~/.local/share/oireachtas-etl/core-state.sqlite`; select another database with `--state-db` or `OIR_ETL_STATE_DB`. The former `members-state.json` manifest is a read-only, one-time migration input. Its old path remains configurable with `OIR_MEMBERS_STATE_FILE`, or can be supplied explicitly with `--legacy-state-file` (`--state-file` remains a deprecated alias for that JSON input). Successful import makes SQLite authoritative; the legacy file is never updated. SQLite records observed/published source hashes, the publication payload hash, and dirty pending state. Because this RDF contract changes existing Member graphs without changing source hashes, the Member `contract_version` remains `2` so previously clean graphs are republished under the current model.

Online runs take an advisory exclusive lock on `<state-db>.lock` for extraction, publication, and state updates. Members are still completely scanned; an absent Member is retained and reported, never deleted automatically. `oir-etl state status` inspects recent run, endpoint and resource state.

The same core database records complete-refresh runs and shared-graph publication state for Houses, Parties, and Constituencies. Their graphs are still replaced in full; they do not gain artificial per-resource rows. Dirty shared-graph state is committed before PUT and remains dirty on failed PUT or verification until a later complete refresh succeeds.

Before every PUT a committed SQLite transaction marks that Member dirty with a pending source hash, graph IRI and exact N-Triples payload/hash while retaining the last successfully published hashes. Only a clean matching entry may skip. PUT and per-PUT exact graph-count/core competency gates must succeed before the entry becomes clean and advances its published hashes; failures remain dirty and are retried on the next full scan, including after source reversion. The five fixture-backed semantic competency queries are integration acceptance across all Member graphs, not per-record production PUT checks.
