# OWL source modules

The root ontology imports six modules. The Turtle files in this directory are
the authority for classes, properties, individuals, axioms and annotations;
this page is only a navigation index. For an introduction, see the
[ontology guide](../docs/guides/ontology.md) and [subject references](../docs/README.md).

| Module | Ontology IRI | Subject |
|---|---|---|
| [oireachtas.owl.ttl](oireachtas.owl.ttl) | `https://data.oireachtas.ie/ontology` | Umbrella ontology; imports all modules |
| [agents.owl.ttl](agents.owl.ttl) | `https://data.oireachtas.ie/ontology/agents` | Parliamentary institutions, persons, roles and organisations |
| [events.owl.ttl](events.owl.ttl) | `https://data.oireachtas.ie/ontology/events` | Journal events, Bill stages and procedural outcomes |
| [legislation.owl.ttl](legislation.owl.ttl) | `https://data.oireachtas.ie/ontology/legislation` | Legislative works, processes, versions and statuses |
| [members.owl.ttl](members.owl.ttl) | `https://data.oireachtas.ie/ontology/members` | Membership, parliamentary collections, roles and offices |
| [vocabulary.owl.ttl](vocabulary.owl.ttl) | `https://data.oireachtas.ie/ontology/vocabulary` | SKOS concept-scheme declarations |
| [debates.owl.ttl](debates.owl.ttl) | `https://data.oireachtas.ie/ontology/debates` | Official Report structure, questions, speeches and votes |

Import declarations are recorded in each Turtle module; consult those files for
the current import relationships. The Oireachtas term namespace is
`https://data.oireachtas.ie/ontology#`. Classes conventionally use
UpperCamelCase and properties lowerCamelCase; actual IRIs and axioms in OWL
remain authoritative.

External ontology versions and source checksums are recorded in
[`external-vocabulary-pins.md`](external-vocabulary-pins.md).
