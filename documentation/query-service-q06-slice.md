# Query Service Q06 political-affiliation slice

The composable v2 Query Service supports Q06 through the same typed plan,
reviewed relation registry, validator, compiler entry point and result rendering
used by Q09. Q06 follows a local Member's `PartyMembership` episode through its
term-scoped `ParliamentaryParty` to the reviewed
`members:hasPoliticalAffiliationIdentity` link in
`https://data.oireachtas.ie/graph/political-affiliations/identities`. The local
identity resource's English `skos:prefLabel` is the answer label. External
`members:recognisedAsParty` links and label equality are not used.

The answer is distinct by the local identity IRI. Membership episodes stay
separate and their available date ranges are displayed as supporting evidence;
no interval union or continuity assumption is made. Only records typed
`members:PartyMembership` enter this path, so Independent collection membership
is not presented as a political affiliation.

## Verification evidence and limits

`tests/test_nlq_composable_q06.py` executes generated SPARQL in RDFLib and posts
the approved Q06 wording through `/ask`. The fixture builds its identity graph
from `reports/party-identity-decisions.json`; it uses the exact reviewed
term-party IRIs for Social Democrats and Fianna Fáil. Its Member, term-specific
membership episodes and dates are explicitly synthetic and exist only to test
joins, deduplication, date presentation, missing evidence and Independent
exclusion. This is not historical acceptance evidence for Stephen Donnelly.

Real-data acceptance requires the corresponding Member-owned membership
evidence, the term-scoped party records in the Parties graph, and the complete
reviewed political-affiliation enrichment graph in one selected local dataset.
Use an isolated/disposable development dataset for loading or rebuilding those
graphs. Do not replace graphs in an existing dataset or use production
publication for Query Service fixture verification. Historical date accuracy
and completeness remain dependent on source membership records.
