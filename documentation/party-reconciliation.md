# Phase 4.5 Parliamentary Party reconciliation

Party reconciliation is a derived enrichment pipeline for term-scoped
`members:ParliamentaryParty` collections. It is separate from the Parties
transform and never writes the authoritative Parties graph. API records with
`partyCode == "Independent"` are `members:IndependentMemberCollection` records
and are excluded.

## Identity, review and graph ownership

The complete, validated Oireachtas source Party IRI is the SQLite local identity
and review key. For example, a Dáil term-scoped Party URI remains distinct from
the same `partyCode` in another HouseTerm. `partyCode` is useful evidence and is
stored as non-unique descriptive state; it is never the reconciliation key.

The independently replaceable graph convention is:

```text
https://data.oireachtas.ie/graph/party/{houseCode}/{houseNo}/{percent-encoded-partyCode}/external-links
```

For example:

```text
https://data.oireachtas.ie/graph/party/dail/34/Fianna_F%C3%A1il/external-links
```

An accepted, human-reviewed QID produces exactly one assertion:

```turtle
<term-scoped-parliamentary-party>
    members:recognisedAsParty <https://www.wikidata.org/entity/Q123> .
```

No external facts are copied into the graph. `owl:sameAs` and
`prov:specializationOf` are forbidden between a term-scoped ParliamentaryParty
and the enduring external political party. The generic reconciliation graph
gate verifies the entire named graph after each PUT, including a reviewed empty
graph.

## Candidate policy

Candidate discovery uses the API `partyCode`, its underscore-normalized form,
and `showAs` as exact, case-insensitive Wikidata label/alias search terms. A
candidate must be described as an instance/subclass of Wikidata's political
party type (Q7278) and have Ireland (Q27) as its country or applicable
jurisdiction. Candidate evidence retains matching labels, type, jurisdiction,
Wikidata inception/dissolution dates and, when supplied by the source, HouseTerm
dates. A demonstrable date conflict is recorded as historical evidence for
review; it is not a fuzzy score or an identity assertion. Previous candidate
evidence remains available in state and the append-only attempt history.

Candidate generation is not deterministic identity matching. Even one exact
label candidate remains pending human review; zero candidates remain pending;
multiple candidates remain ambiguous. External-service failure is pending.
None of those outcomes clears an already accepted external graph. No fuzzy,
normalized-label-only or label-only automatic acceptance exists. No
deterministic external Party identifier has been established for this policy.

`reconciliation/party-decisions.json` is the strict, version-controlled Party
review file. Its independent version-1 schema is:

```json
{
  "version": 1,
  "decisions": {
    "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_F%C3%A1il": {
      "status": "accepted",
      "wikidata": "Q123",
      "note": "Reviewed against the registered party identity"
    }
  }
}
```

An accepted decision requires a canonical Wikidata QID and is authoritative
human review; it does not depend on candidate lookup availability. A reviewed
`{"status":"rejected"}` decision explicitly revokes the Party relationship
and may replace a formerly accepted graph with an empty graph. Unknown fields,
malformed IRIs, invalid decisions, decisions for Independent collections, and
review keys absent from the validated current Parties input fail closed. This
file format is separate from the unchanged Member version-1 review file, which
continues to be keyed by `memberCode`.

## Shared state and recovery

Members and Parties share one schema-version-4 SQLite reconciliation store,
defaulting to the existing Phase 3.5 path
`~/.local/share/oireachtas-etl/member-reconciliation.sqlite`. Its record
identity is `(entity_kind, local_iri)`; party codes are not unique in the
database. Member v1-v3 SQLite schemas are migrated in place to the generic
tables. Member records, audit histories, publication attempts and dirty stored
payloads are copied transactionally; the Member API and review format remain
compatible.

Before any lookup, a dirty record replays its exact stored N-Triples payload,
even if the current source fingerprint or review file changed or `--all` was
requested. The payload hash, graph IRI derived from the saved identity, RDF
parse and entity-specific graph boundary are validated before PUT. A failed
validation or publication fails closed. State becomes clean only after PUT and
whole-graph verification. Once recovery succeeds, changed source/review input
can proceed in the same invocation. The exact old payload is never regenerated
from new lookup results.

Unresolved, ambiguous, or unavailable candidate results do not publish an
empty graph and do not clear a prior accepted link. Only an explicit reviewed
rejection clears it. The generic subsystem owns review precedence, scheduling,
audit, dirty-payload recovery, graph replacement and post-publication
verification; Member and Party policies supply entity-specific validation,
candidate generation, graph semantics and graph identity.

## CLI and offline fixture seam

Online candidate generation can be run independently of the authoritative
Parties ETL:

```text
oir-etl reconcile parties [--all] [--publish]
```

The default review file is `reconciliation/party-decisions.json`; the default
SQLite path is the shared Phase 3.5 state file. Override either with
`--review-file` or `--reconciliation-state-file`. Publication is opt-in and
requires both configured Fuseki Graph Store and SPARQL endpoints. It only PUTs
graphs owned by reconciliation.

Offline runs use the same deterministic policy and require both source and
response fixtures. They never publish:

```text
oir-etl reconcile parties --fixture parties.json --responses-file party-candidates.json \
  --offline --all --review-file reconciliation/party-decisions.json \
  --reconciliation-state-file party-state.sqlite --output-nq party-links.nq
```

The source fixture may be a single Party wrapper, an array of wrappers, or an
API `results` envelope. Every record is validated against its complete
term-scoped IRI before state is opened. Exact duplicate records are collapsed;
conflicting duplicates, advertised-count mismatches, and graph-IRI collisions
fail before state changes. The response fixture is keyed by full Party source
IRI, never by partyCode:

```json
{
  "wikidata": {
    "party_candidates": {
      "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_F%C3%A1il": [
        {
          "qid": "Q123",
          "labels": ["Fianna Fáil"],
          "matched_on": ["Fianna Fáil"],
          "types": ["Q7278"],
          "instance_types": ["Q7278"],
          "jurisdictions": ["Q27"],
          "inception": ["1926"],
          "dissolution": []
        }
      ]
    }
  }
}
```

For an undecided eligible Party, every candidate entry must exist in the fixture;
an empty array explicitly represents no candidate. A reviewed decision bypasses
candidate lookup. Fixture QIDs, candidate metadata, matched labels, party type
and jurisdiction are validated before opening SQLite. `--offline` requires
`--fixture` and `--responses-file` and forbids `--publish`.

Offline candidate metadata is reviewer-supplied fixture content. Its schema and
QIDs are checked for consistency, but the fixture does not independently prove
that a candidate is an instance/subclass of political party (Q7278) or that it
has an Ireland (Q27) country/jurisdiction assertion. Those constraints are
applied by the live Wikidata SPARQL query (`P31` with the `P279*` path to Q7278,
and `P17` or `P1001` equal to Q27); fixture metadata must not be treated as
equivalent external verification.

The command summary reports accepted, rejected, pending and ambiguous outcomes,
unresolved Party source IRIs, excluded Independent records, and publication
count. Broad publication still requires a separate coverage and false-match
review; this implementation does not claim that candidate counts establish
match quality.

## Coverage and review measures before broad publication

Count distinct *eligible term-scoped source IRIs* (not distinct party codes) in
the complete validated Parties harvest as the denominator. Record accepted,
rejected, pending (including no candidate and lookup failure), and ambiguous
counts and their proportions of eligible IRIs, plus excluded Independent IRIs
separately. Report accepted graph coverage as independently verified accepted
graphs divided by eligible IRIs, and candidate yield as eligible IRIs with at
least one review candidate divided by eligible IRIs. Report lookup failures
separately from genuine zero-candidate outcomes; report historically conflicting
candidates and the number of manual decisions, including revocations. These
measures must come from one identified source snapshot and state/review version,
not from the CLI's *processed* count on a normal incremental run.

Before broad publication, manually sample accepted links across Houses, terms,
and party-code histories (including changed names and historical terms). For
each sampled assertion verify that the external QID denotes the enduring
registered political party underlying the exact local parliamentary collection,
not a similarly named group, current party successor, or specific HouseTerm.
Record the sample size, number of incorrect links, false-match fraction
(`incorrect / sampled`), review evidence and corrections/revocations. A zero
observed error fraction is not proof of zero risk; there is no automatic
publication threshold or asserted match-quality score in this tranche.

## Boundaries and deferred work

- No external Party assertion is added to `oir-etl run parties` or Member RDF.
- No political-party RDF is asserted for IndependentMemberCollection.
- No candidate is auto-accepted based on label, code, type or jurisdiction.
- No DBpedia or Wikipedia Party enrichment is performed.
- No production Fuseki dataset is selected implicitly; publication requires the
  explicit `--publish` option and configured endpoints.
- Coverage sampling, false-match measurement and any future deterministic
  authority-key policy remain review work before broad Party-link publication.
