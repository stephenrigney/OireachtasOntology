# Direct graph exploration guide

This guide connects to the project's existing local Fuseki and explains how to
inspect its named graphs without the natural-language Query Service. It adds no
service or UI. For the model see the [`ontology guide`](../docs/guides/ontology.md); for
queries see the [`SPARQL cookbook`](sparql-cookbook.md). The existing
[`Fuseki User Guide`](fuseki-user-guide.md) remains the operational reference.

## Connect to the development Fuseki

From the repository root, start (or reuse) the existing Compose service:

```bash
docker compose up -d fuseki
docker compose ps
```

The existing dataset is named `houses`. Open the Fuseki home/admin page at
`http://localhost:3030/`, select `houses`, then open **query**. The direct
SPARQL endpoint is:

```text
http://localhost:3030/houses/query
```

The Graph Store Protocol endpoint is
`http://localhost:3030/houses/data`; it is a write/load interface, not the
query UI. Do not use write/update operations for exploration. The local admin
fallback is described in `fuseki-user-guide.md`; it is for loopback development
only. The ETL uses `OIR_FUSEKI_SPARQL_URL` and `OIR_FUSEKI_GSP_URL` when
publishing.

Starting the container does not load data. Ordinary
`scripts/dev-nlq.sh` startup also does not load data. The optional
`scripts/dev-nlq.sh --load-data` explicitly runs the development bootstrap from
preserved raw captures. It can take resources and replaces owned graphs; do not
run it merely to open the query interface. Before intentionally bootstrapping,
read [`poc/nlq/README.md`](../poc/nlq/README.md) and confirm which data/volume
you intend to use. Do not use `docker compose down -v` to “refresh”: it deletes
the persistent local Fuseki volume.

## Run and save a query

1. Open the `houses` dataset query interface in Fuseki.
2. Paste one query from the SPARQL cookbook, including its `PREFIX` declarations.
3. Run it as a read-only `SELECT` or `ASK`. Inspect IRIs and graph names, not
   just labels; adjust the `LIMIT` while exploring.
4. Save useful queries as `.rq` or `.sparql` files outside any protected
   semantic contract, or copy them into a documentation example after review.
   The Fuseki form is an editor, not a versioned query notebook.
5. To execute from a shell and save result JSON locally (without changing RDF):

   ```bash
   curl -fsSG http://localhost:3030/houses/query \
     --data-urlencode 'query=SELECT ?g WHERE { GRAPH ?g { ?s ?p ?o } } LIMIT 20' \
     -H 'Accept: application/sparql-results+json' > /tmp/graph-sample.json
   ```

   Replace only the query string; keep `GET /query`. Endpoint authentication
   may be required if local credentials were customized.

## Find an IRI and walk it manually

Start with label or identifier discovery and return `?resource`, `?label` and
`?g`. The predicates differ by resource: `foaf:name` for a Member,
`skos:prefLabel` for a HouseTerm, ParliamentaryMemberCollection or constituency.
Then copy the resulting IRI into an exact outgoing query:

```sparql
SELECT ?p ?o
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/member/Bertie-Ahern.D.1977-07-05> {
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>
      ?p ?o
  }
}
ORDER BY ?p
```

If the object is another IRI, use it as the next subject in the graph that owns
its description. To find incoming references, reverse the pattern (`?s ?p
<IRI>`) inside `GRAPH ?g`. This manual back-and-forth is often the clearest way
to learn exact predicates before adding a multi-join query. Do not assume the
IRI itself is dereferenceable or that its description lives alongside every
reference to it.

## Inspect named graphs and graph families

List all graph names and counts with the first query in the cookbook. Endpoint
ownership conventions from the ETL plan are:

| Family | Owner graph pattern |
|---|---|
| Houses / HouseTerms | `https://data.oireachtas.ie/graph/houses` |
| Party collections | `https://data.oireachtas.ie/graph/parties` |
| Constituencies / panels | `https://data.oireachtas.ie/graph/constituencies` |
| Members / parliamentary memberships | `https://data.oireachtas.ie/graph/member/{memberCode}` |
| Bills and lifecycle | `https://data.oireachtas.ie/graph/bill/{year}/{number}` |
| Debates (per Work) | `https://data.oireachtas.ie/graph/debate/...` |
| Committees | Shared owner graph `.../graph/committees` |
| Office registries / enrichments | Check exact graph family and documentation; ownership can differ |

Published additions include separate external-link graphs (for accepted
reconciliation results); do not count these as copied facts in authoritative
owner graphs. A graph family with zero rows can mean not loaded, not populated,
or unsupported source mapping. Ontology classes can exist without instances.

On the 2026-10-20 development snapshot used for the cookbook, the family query
found 6,044 Bill graphs, 1,928 Member graphs, three Debate graphs, and one each
for Houses, parties, constituencies, committees, offices and
administrative-units. It found no graph names containing `external-links` and
no separate party/institution external-link graph. This is a local
point-in-time observation; production Debates remain un-ingested and the count
does not establish completeness.

## Know what kind of data is loaded

Keep these evidence layers separate:

* **Ontology:** vocabulary and axioms in `ontology/*.owl.ttl`; does not itself
  populate Fuseki.
* **Fixtures:** checked-in examples under `data/api_examples/` and debate source
  examples/goldens. They support deterministic tests and are deliberately small,
  not the live corpus.
* **Development bootstrap:** ETL transforms preserved API captures and loads
  owned graphs into local Fuseki. The NLQ README documents bootstrap modes,
  graph counts, dataset identity and non-authoritative coverage. This is the
  source for this guide's 2026-10-20 development query observations.
* **Authoritative production publications:** a separate operational act after
  validation and approval. Local Fuseki state, fixture tests and a bootstrap
  manifest are not proof of production publication or completeness.

Before relying on a result, run graph counts and compare them with the current
development bootstrap identity/coverage report. Then inspect the exact source
graph and resource. See the top-level [`README.md`](../README.md),
[ETL architecture](../docs/architecture/etl.md), [`fuseki-user-guide.md`](fuseki-user-guide.md),
and [`poc/nlq/README.md`](../poc/nlq/README.md) for commands and data provenance.

## Debates availability note

Debates classes, mappings, transformer, validation, and controlled staging
evidence exist. However, Phase 7's accepted production scope (Dáil, Seanad and
committee Debates dated 2011 onward, with written answers excluded) has **not
been ingested into production**; the production readiness report says human
exceptions, resource budgets, owner evidence and publication authorisation are
still gates. The local development dataset observed on 2026-10-20 contained
three Debate graphs. Do not equate those with the approved production corpus.
The cookbook's debate-to-Bill event example has no verified positive crosswalk
against accepted evidence. Recheck dataset evidence and those examples after
Debates ingestion; no ingestion or publication is part of this guide.


### Reviewed political-affiliation identities (2026)

The implemented `members:PoliticalAffiliationIdentity` provides a local, enduring, reviewed affiliation identity distinct from the term-scoped `members:ParliamentaryParty` source collection and from externally reconciled party identities. `members:hasPoliticalAffiliationIdentity` links the term-scoped collection to the local identity; `members:recognisedAsParty` remains a separate reviewed external link. The approved register (`reports/party-identity-decisions.json`) contains 33 identities, 314 accepted links among 315 reviewed non-Independent records, and one excluded Ceann Comhairle record. Independents have no political-affiliation identity. Neither labels nor aliases establish identity; the four reviewed Sinn Féin identities remain distinct. Descriptions and reviewed links are published together in the replaceable derived graph `https://data.oireachtas.ie/graph/political-affiliations/identities`, without modifying Parties or Members owner graphs. Q06 uses the local identity with synthetic execution evidence only; production completeness is not established. See [`political-affiliation-identity.md`](political-affiliation-identity.md), [`political-affiliation-publication.md`](political-affiliation-publication.md) and [`query-service-q06-slice.md`](query-service-q06-slice.md).
