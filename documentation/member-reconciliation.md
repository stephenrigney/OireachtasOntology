# Phase 3.5 Member external identity reconciliation

This pilot is a separate operational subsystem.  It neither changes nor blocks
`oir-etl run members`, and never writes authoritative Member graphs.  It owns
only independently replaceable graphs named:

```text
https://data.oireachtas.ie/graph/member/{percent-encoded-memberCode}/external-links
```

Each graph contains only `owl:sameAs` from the Oireachtas Member to an accepted
Wikidata entity or accepted DBpedia person, and `foaf:isPrimaryTopicOf` to that
Wikidata entity's English Wikipedia sitelink.  It contains no imported facts
or RDF provenance. An empty graph is PUT only for explicit manual rejection.
New unresolved records publish no graph; a no-match, outage, or ambiguity never
clears a previously accepted external graph.
If the primary exact Wikidata identity is accepted but optional Wikidata entity
or DBpedia enrichment fails, the accepted Wikidata link remains publishable;
the error is retained and schedules a short retry rather than claiming a fully
successful 90-day result.

## Identity and outcomes

Wikidata P4690 queried with the exact `memberCode` is the sole automated
identity key. One valid QID is accepted; no QID is an unmatched pending review
case; multiple QIDs are ambiguous; service failures are pending. Only explicit
human review is rejected. Exact-ID matching records its
method and evidence, not a made-up confidence score.  DBpedia is queried only
after Wikidata acceptance and must have one resource explicitly `owl:sameAs`
that QID and typed as a person.  Title matching and fuzzy DBpedia matching are
not performed.  Wikipedia likewise comes only from the accepted QID's enwiki
sitelink.

`reconciliation/member-decisions.json` is a version-controlled review file.
It is deterministic JSON with `version: 1` and a `decisions` object keyed by
memberCode.  A decision is either `{"status":"rejected"}` or
`{"status":"accepted","wikidata":"Q123"}` (an optional `note` is for
reviewers).  Decisions override automation.  Invalid, unknown, or stale-format
review files fail the reconciliation command before publication.
An accepted review QID bypasses the automated P4690 lookup; downstream
Wikipedia and DBpedia derivation still follows that reviewed Wikidata identity.

## State and workflow

The default SQLite path is `~/.local/share/oireachtas-etl/member-reconciliation.sqlite`
and can be overridden with `--reconciliation-state-file`; it must not be the Phase 3 JSON manifest.  Its
versioned schema records member identity fingerprint, outcome/candidates and
structured evidence, method, service errors and timestamps, review hash/use,
accepted IRIs, recheck time, and dirty/clean publication data.  An append-only
attempt table preserves every input fingerprint, decision snapshot, method,
outcome, evidence/errors, and accepted outputs. Writes use SQLite transactions.
Publication attempts and their payload hashes/results are also audited. A dirty
row replays that exact stored payload before any further external lookup; it is
clean only after PUT and whole-graph competency verification.
Initial runs use `--all`; ordinary runs select new, identity-relevant changed,
review-changed, dirty, or due records. Accepted/rejected records recheck after
90 days; pending/ambiguous and accepted records with enrichment errors recheck
after 7 days. Multiple exact DBpedia people are retained as a reviewable
downstream enrichment ambiguity: no DBpedia link is published, but accepted
Wikidata/Wikipedia links remain. A due check with an unchanged clean link payload does not PUT;
`--all` intentionally republishes.

For an offline deterministic run, pass a Members fixture and a response JSON:

```text
oir-etl reconcile members --fixture members.json --responses-file responses.json \
  --offline --all --reconciliation-state-file state.sqlite --output-nq links.nq
```

`--offline` requires both `--fixture` and `--responses-file` and forbids
publication. Fixtures are strict: requested P4690, accepted entity, and
DBpedia entries must exist. Without `--fixture`, the command harvests the complete configured Members API
using the normal pagination/count checks, but does not preserve raw data or
touch the Phase 3 manifest. The response shape is `wikidata.p4690[memberCode]`,
`wikidata.entities[QID]`, and `dbpedia.by_wikidata[QID]`; it is also the
mockable client seam used by tests.  `--publish` performs Graph Store PUTs only
for this subsystem's graph.  A lookup failure is recorded as pending and makes
the reconciliation command nonzero; it never affects authoritative ETL.

Deferred: broader entity sources, non-English sitelinks, richer provenance
graphs, automated review UI, retry orchestration, and Phase 4+ infrastructure.
