# SPARQL query cookbook

This cookbook uses the repository's actual IRIs, graph ownership and predicates.
Run read-only `SELECT` queries in Fuseki's `houses` dataset at
[`http://localhost:3030/`](http://localhost:3030/) (query endpoint
`http://localhost:3030/houses/query`). Start/connect as described in the
[`direct graph exploration guide`](direct-graph-exploration.md).

## Evidence and scope of examples

Queries marked **tested on development dataset** were issued to the local
Fuseki service on 2026-10-20. At that time it contained 7,981 named graphs:
6,044 Bill graphs, 1,928 Member graphs, 3 Debate graphs, and one each for
Houses, parties, constituencies, committees, offices and administrative units.
This persistent local dataset is development/bootstrap data, not a signed
production snapshot or completeness claim. The Query Service readiness panel
and bootstrap manifest describe expected graph ownership; they do not turn local
data authoritative. Results can change after refresh. “Not verified” means the
currently loaded local data could not support a positive query result, not that
the vocabulary or transformer lacks support.

Prefix block for the examples:

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX debates: <https://data.oireachtas.ie/ontology/debates#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
```

Each query is self-contained enough to paste separately; add any missing
prefixes from the block. Fuseki's active dataset is a named-graph dataset, so
patterns must say `GRAPH <...>` or `GRAPH ?g`; do not assume a default graph
union.

## 1. Explore graph families and scope

### 1.1 List named graphs with triple counts

```sparql
SELECT ?g (COUNT(*) AS ?triples)
WHERE { GRAPH ?g { ?s ?p ?o } }
GROUP BY ?g
ORDER BY ?g
```

This is a live inventory of non-empty graphs. `GRAPH ?g` binds the graph name;
the count is triples in that graph. To summarize graph families rather than
list thousands of per-Member/per-Bill graphs, use a subquery:

```sparql
SELECT ?family (COUNT(?g) AS ?graphs) (SUM(?triples) AS ?tripleCount)
WHERE {
  {
    SELECT ?g (COUNT(*) AS ?triples)
    WHERE { GRAPH ?g { ?s ?p ?o } }
    GROUP BY ?g
  }
  BIND(REPLACE(STR(?g), "^https://data.oireachtas.ie/graph/([^/]+).*$", "$1") AS ?family)
}
GROUP BY ?family
ORDER BY ?family
```

**Tested on development dataset:** returned 9 families: administrative-units,
bill, committees, constituencies, debate, houses, member, offices and parties.
The counts above are a point-in-time observation, not an expected permanent
baseline.

### 1.2 List classes present and typed instance counts

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?class (COUNT(DISTINCT ?instance) AS ?instances)
WHERE { GRAPH ?g { ?instance rdf:type ?class } }
GROUP BY ?class
ORDER BY DESC(?instances)
```

This counts explicit `rdf:type` assertions and aggregates across graph owners.
It is not OWL reasoner output: inferred types may not be stored. To inspect
selected classes only, add `VALUES ?class { members:ParliamentaryParty ... }`.
Never infer “unpopulated” merely because a class is absent from these explicit
triples without checking the correct graph family and any expected inference.

### 1.3 Find resources by a literal label

Member names use `foaf:name`; HouseTerms, party collections and constituencies
normally use language-tagged `skos:prefLabel`. Match the correct predicate and
return the graph and IRI:

```sparql
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?resource ?label ?g
WHERE {
  GRAPH ?g {
    { ?resource foaf:name ?label }
    UNION
    { ?resource skos:prefLabel ?label }
  }
  FILTER(CONTAINS(LCASE(STR(?label)), "bertie ahern"))
}
ORDER BY ?g ?resource
```

**Tested on development dataset:** one Bertie Ahern Member IRI was returned.
Label search is a discovery operation, not a safe identity resolution rule.
For source identifiers, search the appropriate datatype property, e.g. `oir:memberCode`
or `members:partyCode`, then verify type and graph.

### 1.4 Inspect a resource's incoming/outgoing statements

The following lists outgoing statements for a known URI; change the graph scope
if resource ownership is unknown:

```sparql
SELECT ?predicate ?object
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/member/Bertie-Ahern.D.1977-07-05> {
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>
      ?predicate ?object
  }
}
ORDER BY ?predicate ?object
```

For incoming links, reverse the subject/object positions:

```sparql
SELECT ?graph ?subject ?predicate
WHERE {
  GRAPH ?graph { ?subject ?predicate
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05> }
}
ORDER BY ?graph ?predicate ?subject
```

The first walks only the Member-owned graph. The second searches every named
graph for a link to that IRI. `?object` can be a URI resource or a literal.

### 1.5 Inspect type and all properties of an IRI

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?graph ?predicate ?object
WHERE {
  GRAPH ?graph {
    <https://data.oireachtas.ie/ie/oireachtas/party/dail/22/Fianna_Fáil>
      ?predicate ?object
  }
}
ORDER BY ?graph ?predicate
```

The type is simply the row with predicate `rdf:type`. The graph column is
important: a descriptive party row should be in the parties owner graph, while
a membership record pointing to the party belongs in a Member graph.

## 2. Members, collections and representation

### 2.1 Find Bertie Ahern's parliamentary membership records

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?membership ?term ?termLabel ?house ?start ?end
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/member/Bertie-Ahern.D.1977-07-05> {
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>
      foaf:name "Bertie Ahern" ; members:hasMembersMembership ?membership .
    ?membership a members:OireachtasMembership ;
      members:inHouseTerm ?term ;
      members:isOireachtasMembershipOf ?house ;
      members:hasMembershipDateRange ?period .
    ?period members:StartDate ?start .
    OPTIONAL { ?period members:EndDate ?end }
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel }
}
ORDER BY ?start
```

Member-owned graph contains the relationship and date range; the Houses graph
supplies term labels. The query deliberately asks for OireachtasMembership
records rather than every `hasMembersMembership` object, which also includes
party/committee/office relationships. **Tested on development dataset:** returns
the expected sequence of Dáil terms for Bertie Ahern.

### 2.2 Find party collections and constituencies connected to a Member

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?termLabel ?collection ?partyLabel ?constituency ?constituencyLabel
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/member/Bertie-Ahern.D.1977-07-05> {
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>
      foaf:name "Bertie Ahern" ; members:hasMembersMembership ?om .
    ?om a members:OireachtasMembership ; members:inHouseTerm ?term .
    OPTIONAL { ?om members:isRepresentativeFrom ?constituency }
    OPTIONAL {
      ?cm members:inOireachtasMembership ?om ;
           members:memberOfCollection ?collection .
    }
  }
  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel } }
  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/parties> { ?collection skos:prefLabel ?partyLabel } }
  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/constituencies> { ?constituency skos:prefLabel ?constituencyLabel } }
}
ORDER BY ?termLabel
```

The necessary join is `?cm members:inOireachtasMembership ?om`: it associates a
party-collection membership with the specific House membership. Without that
context, one could accidentally pair a party membership from one term with a
constituency in another. `OPTIONAL` keeps terms visible if one kind of
relationship is missing. **Tested on development dataset:** Bertie's 22nd Dáil
row associates Fianna Fáil and Dublin Central; the 21st Dáil association is
Dublin Finglas.

### 2.3 List TDs representing Dublin Central

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT DISTINCT ?member ?name ?membership ?term ?termLabel
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/constituencies> {
    ?constituency skos:prefLabel ?constituencyLabel ;
      members:constituencyInHouseTerm ?term .
    FILTER(STR(?constituencyLabel) = "Dublin Central")
  }
  GRAPH ?memberGraph {
    ?member a <https://data.oireachtas.ie/ontology#Member> ;
      foaf:name ?name ; members:hasMembersMembership ?membership .
    ?membership a members:DailMembership ;
      members:isRepresentativeFrom ?constituency ;
      members:inHouseTerm ?term .
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel }
  FILTER(STRSTARTS(STR(?memberGraph), "https://data.oireachtas.ie/graph/member/"))
}
ORDER BY ?termLabel ?name
```

The constituency IRI and term are joined to the Member-owned DailMembership.
This returns representatives across historical term-specific Dublin Central
resources; add a fixed `?term` IRI to ask about only one Dáil. **Tested on
development dataset:** Dublin Central labels occur under multiple HouseTerms;
this query returned 67 Member/membership/term rows in the observed snapshot,
not 67 distinct people or a single current roster.

### 2.4 Fianna Fáil TDs sharing Dublin Central with Bertie during overlapping periods

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?other ?otherName ?term ?termLabel ?bStart ?bEnd ?oStart ?oEnd
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/member/Bertie-Ahern.D.1977-07-05> {
    <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>
      members:hasMembersMembership ?bertieOM .
    ?bertieOM a members:DailMembership ; members:inHouseTerm ?term ;
      members:isRepresentativeFrom ?constituency ;
      members:hasMembershipDateRange ?bPeriod .
    ?bPeriod members:StartDate ?bStart . OPTIONAL { ?bPeriod members:EndDate ?bEnd }
    ?bertieCM members:inOireachtasMembership ?bertieOM ;
      a members:PartyMembership ; members:isPartyMembershipOf ?ff .
    ?bertieCM members:hasMembershipDateRange ?bfPeriod .
    ?bfPeriod members:StartDate ?bfStart . OPTIONAL { ?bfPeriod members:EndDate ?bfEnd }
  }
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?ff skos:prefLabel ?ffLabel ; members:activeDuringTerm ?term .
    FILTER(STR(?ffLabel) = "Fianna Fáil")
  }
  GRAPH <https://data.oireachtas.ie/graph/constituencies> {
    ?constituency skos:prefLabel ?constituencyLabel ;
      members:constituencyInHouseTerm ?term .
    FILTER(STR(?constituencyLabel) = "Dublin Central")
  }
  GRAPH ?otherGraph {
    ?other a <https://data.oireachtas.ie/ontology#Member> ; foaf:name ?otherName ;
      members:hasMembersMembership ?otherOM .
    ?otherOM a members:DailMembership ; members:inHouseTerm ?term ;
      members:isRepresentativeFrom ?constituency ;
      members:hasMembershipDateRange ?oPeriod .
    ?oPeriod members:StartDate ?oStart . OPTIONAL { ?oPeriod members:EndDate ?oEnd }
    ?otherCM members:inOireachtasMembership ?otherOM ;
      a members:PartyMembership ; members:isPartyMembershipOf ?ff .
    ?otherCM members:hasMembershipDateRange ?ofPeriod .
    ?ofPeriod members:StartDate ?ofStart . OPTIONAL { ?ofPeriod members:EndDate ?ofEnd }
  }
  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term skos:prefLabel ?termLabel }
  FILTER(STRSTARTS(STR(?otherGraph), "https://data.oireachtas.ie/graph/member/"))
  FILTER(?other != <https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern.D.1977-07-05>)
  # Overlap between Bertie's party spell and the other Member's party spell.
  FILTER((!BOUND(?bfEnd) || ?ofStart <= ?bfEnd) && (!BOUND(?ofEnd) || ?bfStart <= ?ofEnd))
  # Also require overlap between the two House memberships.
  FILTER((!BOUND(?bEnd) || ?oStart <= ?bEnd) && (!BOUND(?oEnd) || ?bStart <= ?oEnd))
}
ORDER BY ?termLabel ?otherName
```

This intentionally joins on exact HouseTerm, constituency IRI and term-scoped
party IRI, then checks interval overlap. Labels alone would mix repeated
historical resources. Missing ends are treated as open for this query's overlap
test; inspect source semantics before reusing that policy. **Tested on
development dataset:** returned 10 distinct Member/term rows in the observed
snapshot. The count is sensitive to membership end-date availability and the
explicit open-end overlap policy; inspect names and periods and check the
intended date before interpreting it as a roster. It is a historical overlap
query, not a current membership question.

## 3. Governments and ministerial offices

### 3.1 Inspect enduring Government and accountability link

```sparql
PREFIX agents: <https://data.oireachtas.ie/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?predicate ?target ?label
WHERE {
  GRAPH ?g { <https://data.oireachtas.ie/government> ?predicate ?target }
  OPTIONAL { GRAPH ?g2 { ?target rdfs:label ?label } }
}
```

Use the exact Government individual. Do not substitute the generic bill-source
concept ending `/def/bill-source/government`, which has a different meaning.
The global `?g` pattern is for discovery. **Tested on development dataset:**
returned no rows for this subject, so this snapshot did not contain an assertion
about the enduring Government IRI. Member office/Cabinet relationships do
exist, illustrating why ontology definition is not graph availability.

### 3.2 List office holdings with people, office labels and periods

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?person ?name ?holding ?office ?officeLabel ?start ?end
WHERE {
  GRAPH ?memberGraph {
    ?person members:hasOfficeHolding ?holding ; foaf:name ?name .
    ?holding a members:OfficeHolding ; members:heldOffice ?office ;
      members:hasMembershipDateRange ?period .
    ?period members:StartDate ?start . OPTIONAL { ?period members:EndDate ?end }
  }
  GRAPH <https://data.oireachtas.ie/graph/offices> { ?office skos:prefLabel ?officeLabel }
  FILTER(STRSTARTS(STR(?memberGraph), "https://data.oireachtas.ie/graph/member/"))
}
ORDER BY ?officeLabel ?start
```

This joins the office owner graph for descriptions to person-owned holding
records. A count of few offices means limited bootstrap coverage, not that other
office tenures never existed. **Tested on development dataset:** office graph
and Member holdings were present; use this query to inspect the current rows.

## 4. Bills and Debates

### 4.1 Find a Bill Work by title

```sparql
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
SELECT ?bill ?title
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/bill/2022/1> {
    ?bill a eli-dl:DraftLegislationWork ; eli:title ?title ;
      eli:id_local "2022/1" .
  }
}
```

This looks up the Bill Work and its local identifier in the Bill-owned graph.
**Tested on development dataset:** returned the Higher Education Authority
Bill 2022. `eli:is_realized_by` is a Work-to-Expression predicate in the
implemented Bill transform; do not use it to guess a Work-to-process link.

The code also emits a deterministic Process and `eli-dl:latest_activity` on
that Process, while activities use `eli-dl:forms_part_of` to point to it.
However, inspection of the transformer and current graphs found **no asserted
predicate linking the Bill Work to its Process**. The Process IRI convention
(`{bill IRI}#process`) and common named-graph placement do not themselves create
an RDF edge. Thus a SPARQL query cannot semantically traverse Bill Work →
Process → latest activity. This is a documented implementation/design-contract
gap for owner review, not a query to work around by manufacturing a join.

### 4.2 Follow a Debate to a process or supported Bill event

The ontology supports links where exact source-to-owner resolution establishes
them. This query finds only such actual assertions and can legitimately return
zero rows:

```sparql
PREFIX debates: <https://data.oireachtas.ie/ontology/debates#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
SELECT DISTINCT ?record ?section ?event
WHERE {
  GRAPH ?debateGraph {
    ?record a debates:DebateRecord .
    ?section debates:refersToEvent ?event .
  }
  GRAPH ?billEventGraph {
    ?event a <https://data.oireachtas.ie/ontology#BillEvent> .
  }
}
```

This asks only whether a Debates section points to the same concrete resource
typed as an existing BillEvent in another graph; it does not infer a Bill from
a title, date, graph placement or event label. **Query executed against
development dataset, no rows returned; no positive example verified.** The
approved Phase 7 evidence records section-to-Bill event crosswalks as deferred,
and the local snapshot contained only three Debate graphs. The query's design
supports future source-resolved links, but none is demonstrated by current
loaded evidence. Do not use the missing Bill Work-to-Process edge above as a
surrogate join.

## 5. Diagnostics and empty results

### 5.1 Why “Fianna Fáil” matches multiple local collections

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?collection ?term ?label
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?collection a members:ParliamentaryParty ;
      members:activeDuringTerm ?term ; skos:prefLabel ?label .
  }
  FILTER(STR(?label) = "Fianna Fáil")
}
ORDER BY ?term
```

**Tested on development dataset:** many distinct terms have the same label
(including separate Dáil and Seanad instances). The API preserves each
source-IRI as a term-scoped ParliamentaryParty. Thus the Query Service message
“More than one local match exists for ParliamentaryMemberCollection ‘Fianna
Fáil’” reflects multiple exact local IRIs with the requested label; the
resolver's contract is to select none without distinguishing context. It does
not establish a bad party transformation or an external identity conflict. A
distinct-IRI count for this label in the observed development snapshot was 60;
that is a point-in-time result and does not prove the exact graph state when an
earlier error was reported.
The user must add context such as the House/term, a Member, or a time period.
The resolver performs local label lookup and stops before running the answer
query when ambiguous; no Query Service behavior was changed for this guide.

### 5.2 Distinguish similarly labelled term-scoped entities

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
SELECT ?resource ?term ?label
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/parties> {
    ?resource skos:prefLabel ?label ; members:activeDuringTerm ?term .
  }
  FILTER(STR(?label) = "Fianna Fáil")
}
ORDER BY ?term
```

Labels are literal values; term plus resource IRI distinguishes entities.
Use the same pattern for historical constituency labels, then check the class
and HouseTerm before interpreting a result.

### 5.3 Diagnose an empty query in a deliberate order

1. Run graph-family counts (1.1), confirm the required owner graph exists and
   is non-empty.
2. Search the right label predicate (`foaf:name` vs `skos:prefLabel`) and return
   `?g` and IRI.
3. Inspect types and raw triples (1.4–1.5). Check the subject's actual type and
   exact predicate direction.
4. Add one join at a time. A party collection is linked through
   `PartyMembership`, not by a direct Member `party` property; a representation
   is linked from OireachtasMembership via `isRepresentativeFrom`.
5. Check named graph scope. A Member record can reference a collection whose
   label is only in `graph/parties`; both GRAPH blocks are necessary.
6. Check temporal assumptions and datatypes. A term end, membership end,
   collection active term and office holding period mean different things.
7. Distinguish no local graph/resource (coverage gap), no supported relationship
   (source/mapping boundary), mismatched IRI/graph (incorrect traversal), and a
   valid relation whose end date was not supplied. Do not manufacture a join to
   force a row.

SPARQL examples marked as tested ran against the current development Fuseki
service, not production. The *Debate event link* query has no verified
positive result; current production Debates availability is explicitly limited
by [`phase-7-debates.md`](phase-7-debates.md). Re-run after data refresh and
after Debates ingestion; see the direct exploration guide for local setup and
dataset identity checks.


### Reviewed enduring affiliations across parliamentary terms

The following query groups term-scoped party collections by reviewed local identity without conflating identically labelled but distinct historical identities. It requires the political-affiliation enrichment graph to be loaded.

```sparql
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?identity ?label (COUNT(DISTINCT ?collection) AS ?termCollections)
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> {
    ?collection members:hasPoliticalAffiliationIdentity ?identity .
    ?identity a members:PoliticalAffiliationIdentity ; skos:prefLabel ?label .
    FILTER(LANG(?label) = "en")
  }
}
GROUP BY ?identity ?label
ORDER BY ?label ?identity
```

To inspect the distinct reviewed Sinn Féin identities, filter the identity IRIs by their approved registry keys rather than collapsing on the shared alias `Sinn Féin`. Member affiliation dates belong to the separate `members:PartyMembership` episodes, not the enduring identity.
