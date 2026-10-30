# Political-affiliation identity enrichment publication

`reports/party-identity-decisions.json` is the only identity/association authority.
The deterministic builder in `oireachtas_etl.political_affiliations` fails closed
unless it sees exactly 33 identities, 315 unique full source IRIs, 314 accepted
links, one exclusion, and no unresolved/unknown outcomes. The excluded source
record is the reviewed Ceann Comhairle office record. No association is derived
from labels and Independent records have no identity.
The generator checks the exact reviewed JSON digest and source-inventory digest,
verifies each source IRI and label against the inventory, and requires the one
excluded outcome to be the exact reviewed Ceann Comhairle office row. Thus
count-preserving reassignment edits fail closed.

The owned graph is
`https://data.oireachtas.ie/graph/political-affiliations/identities`. This is one
cohesive registry-plus-links enrichment graph: identity descriptions and their
reviewed collection links have the same decision-register lifecycle and must be
replaced together. It follows the ETL plan's independently replaceable derived
graph convention. It is disjoint from `https://data.oireachtas.ie/graph/parties`
and all Member graphs; the publisher only PUTs this exact graph and performs
whole-graph verification after replacement. It does not invoke either source
transform or write source descriptions.
The Graph Store Protocol request targets the graph using its `graph` parameter
and sends an `application/n-triples` payload; N-Quads is not sent to a
single-graph GSP endpoint.

GSP PUT is atomic and replacing the same deterministic complete graph is
idempotent. If PUT or post-PUT verification fails or the process is interrupted,
rerun the command: it regenerates from the pinned reviewed register, replaces
the same graph, and verifies full contents. No other graph is touched.

Publish explicitly to an isolated or otherwise selected test dataset with:

```sh
.venv/bin/python tools/publish_political_affiliations.py \
  --gsp-endpoint http://localhost:3030/test/data \
  --sparql-endpoint http://localhost:3030/test/query
```

The command has no production dataset default. `tests/competency/` contains
example SPARQL showing term-scoped parties retaining their term context while
grouping by identity and the intentionally separate Sinn Féin identities.
`members:recognisedAsParty` remains the independent external-party assertion.
