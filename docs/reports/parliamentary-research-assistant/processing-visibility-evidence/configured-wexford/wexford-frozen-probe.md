# Labour Party Members representing Wexford during the 31st Dáil

**Draft — for review** · Records found — report not completed

Original brief: Which Labour Party Members represented Wexford during the 31st Dáil?
Reporting date: 2026-11-13

The search completed, but its result could not be safely included. No findings were established by this search.


## Unanswered research questions

- Which Labour Party Members represented Wexford during the 31st Dáil?

## Assertion evidence and reasoning

## Evidence references

### e-1dcbb594fee2488e805c66cab190d118
```json
{
  "evidenceId": "e-1dcbb594fee2488e805c66cab190d118",
  "request": {
    "factualRequest": "Which Labour Party Members represented Wexford during the 31st Dáil?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "integration_unavailable",
    "label": "Result not included",
    "description": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "failureStage": "evidence_handoff",
    "retryable": false
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": null,
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": false
  },
  "data": null,
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "family": "member_relationship_composition",
    "referents": {
      "member": {
        "type": "Member",
        "answer": true
      },
      "membership": {
        "type": "DailMembership"
      },
      "term": {
        "type": "DailTerm",
        "selector": {
          "kind": "termNumber",
          "number": 31
        },
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
      },
      "episode": {
        "type": "PartyMembershipEpisode"
      },
      "party": {
        "type": "ParliamentaryParty"
      },
      "affiliation": {
        "type": "PoliticalAffiliationIdentity",
        "mention": "Labour Party",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party",
        "label": "Labour Party"
      },
      "constituency": {
        "type": "DailConstituency",
        "mention": "Wexford",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
        "label": "Wexford"
      }
    },
    "relations": [
      {
        "id": "member_has_membership",
        "fact": "member_has_membership",
        "from": "member",
        "to": "membership"
      },
      {
        "id": "membership_in_term",
        "fact": "membership_in_term",
        "from": "membership",
        "to": "term"
      },
      {
        "id": "membership_represents",
        "fact": "membership_represents",
        "from": "membership",
        "to": "constituency"
      },
      {
        "id": "constituency_in_term",
        "fact": "constituency_in_term",
        "from": "constituency",
        "to": "term"
      },
      {
        "id": "member_party_membership",
        "fact": "member_party_membership",
        "from": "member",
        "to": "episode"
      },
      {
        "id": "party_episode_in_membership",
        "fact": "party_episode_in_membership",
        "from": "episode",
        "to": "membership"
      },
      {
        "id": "episode_in_parliamentary_party",
        "fact": "episode_in_parliamentary_party",
        "from": "episode",
        "to": "party"
      },
      {
        "id": "party_active_during_term",
        "fact": "party_active_during_term",
        "from": "party",
        "to": "term"
      },
      {
        "id": "parliamentary_party_has_affiliation_identity",
        "fact": "parliamentary_party_has_affiliation_identity",
        "from": "party",
        "to": "affiliation"
      }
    ],
    "constraints": [
      {
        "referent": "episode",
        "field": "partyEpisodeInterval",
        "operator": "overlaps",
        "value": "membership"
      }
    ],
    "answer": {
      "kind": "entities",
      "referent": "member",
      "distinctBy": "identity",
      "display": [
        "name"
      ],
      "details": [
        {
          "referent": "affiliation",
          "display": [
            "label"
          ]
        },
        {
          "referent": "episode",
          "display": [
            "start",
            "end"
          ]
        },
        {
          "referent": "membership",
          "display": [
            "start",
            "end"
          ]
        }
      ],
      "preserveEvidence": true
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "TD",
      "Member identity",
      "Established affiliation/representation overlap evidence"
    ],
    "rows": [
      [
        "Brendan Howlin",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23",
        "Labour Party; Brendan Howlin (https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23); affiliation 2011-02-25T00:00:00 – 2016-03-09T00:00:00; Dáil representation 2011-03-09T00:00:00 – 2016-03-09T00:00:00; membership https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31; term https://data.oireachtas.ie/ie/oireachtas/house/dail/31; affiliation identity https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party; established overlap 2011-03-09T00:00:00 – 2016-03-09T00:00:00; episode https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d; party https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:9f0677d592e531f20d4d9c238f95cc1e2af90d1798751cfc4eebd1b8a04fad39",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "14ddc43f2f964344bcf6153aaaa202fc",
      "endpointId": "query-endpoint-sha256:1f0e208be610f8d65270a2aba31144d018ac14927ea13fc5b32a148ca187944e",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T16:13:30.001972+00:00",
    "finishedAt": "2026-11-13T16:13:36.053520+00:00",
    "queries": [
      {
        "queryId": "q-3445c0d2aac04cbcbce6758b675efc10",
        "sha256": "255050976d52f924e343592b74fa9fd94c1b32b732f43484ba2c958cfa5b2580",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm ; agents:termNo \"31\"^^xsd:integer .\n  }\n} LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:35.495957+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:35.506249+00:00"
      },
      {
        "queryId": "q-e8b8a8bcc4b44312a24f3d24f1ad6e71",
        "sha256": "8160ebec0de037ce88ae035dd4ae7d666a56b0a75ea0da4cf50a6750f5241cd4",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?constituency ?label WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency ; skos:prefLabel ?label ;\n      members:constituencyInHouseTerm <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> .\n  }\n}\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:35.511116+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/constituencies"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "constituency",
            "label"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-Central",
              "Dublin South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North",
              "Dublin North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-North",
              "Tipperary North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South",
              "Dublin South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wicklow",
              "Wicklow@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Carlow-Kilkenny",
              "Carlow-Kilkenny@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-North",
              "Kildare North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-Central",
              "Dublin North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-North-West-Limerick",
              "Kerry North-West Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Laois-Offaly",
              "Laois-Offaly@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-Central",
              "Cork North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-South",
              "Kerry South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "Wexford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cavan-Monaghan",
              "Cavan-Monaghan@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-West",
              "Dublin South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-West",
              "Dublin West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-West",
              "Galway West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-North-East",
              "Donegal North-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Waterford",
              "Waterford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-East",
              "Galway East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-Central",
              "Cork South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-West",
              "Meath West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick",
              "Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Mayo",
              "Mayo@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-East",
              "Cork East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Roscommon-South-Leitrim",
              "Roscommon-South-Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Mid-West",
              "Dublin Mid-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-West",
              "Dublin North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-South-West",
              "Donegal South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-East",
              "Meath East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dún-Laoghaire",
              "Dún Laoghaire@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-East",
              "Dublin South-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Louth",
              "Louth@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Longford-Westmeath",
              "Longford-Westmeath@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-South",
              "Kildare South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick-City",
              "Limerick City@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-West",
              "Cork South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Clare",
              "Clare@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Central",
              "Dublin Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Sligo-North-Leitrim",
              "Sligo-North Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-South",
              "Tipperary South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-West",
              "Cork North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-East",
              "Dublin North-East@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:35.517458+00:00"
      },
      {
        "queryId": "q-bcc8ba96705444848aeb85a69a6ade5f",
        "sha256": "b464b016525639f5fce92c83d8e237c9efdf7670403c856bffc37582ff9b31ca",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?party ?partyLabel ?affiliation ?affiliationLabel WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> { ?selectedTerm a agents:DailTerm . }\n  VALUES ?selectedTerm { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> }\n  GRAPH <https://data.oireachtas.ie/graph/parties> {\n    ?party a members:ParliamentaryParty ; members:activeDuringTerm ?selectedTerm .\n    OPTIONAL { ?party skos:prefLabel ?partyLabel . FILTER(LANG(?partyLabel) = \"en\") }\n  }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> {\n    ?party members:hasPoliticalAffiliationIdentity ?affiliation .\n    ?affiliation a members:PoliticalAffiliationIdentity .\n    OPTIONAL { ?affiliation skos:prefLabel ?affiliationLabel . FILTER(LANG(?affiliationLabel) = \"en\") }\n  } }\n} ORDER BY ?affiliationLabel ?partyLabel ?party ?affiliation LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:35.550668+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses",
            "https://data.oireachtas.ie/graph/parties",
            "https://data.oireachtas.ie/graph/political-affiliations/identities"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "party",
            "partyLabel",
            "affiliation",
            "affiliationLabel"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil",
              "Fianna Fáil@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
              "Fianna Fáil@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
              "Fine Gael@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party",
              "Labour Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party",
              "Labour Party@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/People_Before_Profit_Alliance",
              "People Before Profit Alliance@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/people-before-profit-alliance",
              "People Before Profit Alliance@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Anti-Austerity_Alliance_People_Before_Profit",
              "Anti-Austerity Alliance - People Before Profit@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/people-before-profit-solidarity",
              "People Before Profit–Solidarity affiliation@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Renua",
              "Renua@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/renua",
              "Renua@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Sinn_Féin",
              "Sinn Féin@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein",
              "Sinn Féin@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Social_Democrats",
              "Social Democrats@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/social-democrats",
              "Social Democrats@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Socialist_Party",
              "Socialist Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/socialist-party",
              "Socialist Party@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Workers_and_Unemployed_Action",
              "Workers and Unemployed Action@en",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/workers-and-unemployed-action",
              "Workers and Unemployed Action@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:35.556814+00:00"
      },
      {
        "queryId": "q-4e38394ebb954659960e005c694e89ef",
        "sha256": "ff670c6027df7bd8d3b6fb03cc5822985fd032077c764a972a08d9b15c09a5ca",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?memberName ?membership ?membershipRange ?membershipStart ?membershipEnd ?episode ?party ?partyLabel ?partyRange ?partyStart ?partyEnd ?affiliation ?affiliationLabel ?constituency ?term WHERE {\nGRAPH ?memberGraph { ?member a agents:Member . ?membership a members:DailMembership . ?episode a members:PartyMembership . ?member members:hasMembersMembership ?membership . ?membership members:inHouseTerm ?term . ?membership members:isRepresentativeFrom ?constituency . ?member members:hasMembersMembership ?episode . ?episode members:inOireachtasMembership ?membership . ?episode members:isPartyMembershipOf ?party . OPTIONAL { ?member foaf:name ?memberName . } OPTIONAL { ?membership members:hasMembershipDateRange ?membershipRange .\n      ?membershipRange a members:DateRange .\n      OPTIONAL { ?membershipRange members:StartDate ?membershipStart . }\n      OPTIONAL { ?membershipRange members:EndDate ?membershipEnd . } } OPTIONAL { ?episode members:hasMembershipDateRange ?partyRange .\n      ?partyRange a members:DateRange .\n      OPTIONAL { ?partyRange members:StartDate ?partyStart . }\n      OPTIONAL { ?partyRange members:EndDate ?partyEnd . } } } FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\nGRAPH <https://data.oireachtas.ie/graph/houses> { ?term a agents:DailTerm . VALUES ?term { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> } ?term agents:termNo \"31\"^^xsd:integer . }\nGRAPH <https://data.oireachtas.ie/graph/constituencies> { ?constituency a members:DailConstituency . VALUES ?constituency { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford> } ?constituency members:constituencyInHouseTerm ?term . }\nGRAPH <https://data.oireachtas.ie/graph/parties> { ?party a members:ParliamentaryParty . ?party members:activeDuringTerm ?term . OPTIONAL { ?party skos:prefLabel ?partyLabel . FILTER(LANG(?partyLabel) = \"en\") } }\nOPTIONAL { GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> { ?affiliation a members:PoliticalAffiliationIdentity . ?party members:hasPoliticalAffiliationIdentity ?affiliation . OPTIONAL { ?affiliation skos:prefLabel ?affiliationLabel . FILTER(LANG(?affiliationLabel) = \"en\") } } }\n} ORDER BY ?affiliationLabel ?memberName ?partyStart ?membershipStart ?episode ?membership LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:35.602421+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses",
            "https://data.oireachtas.ie/graph/constituencies",
            "https://data.oireachtas.ie/graph/parties",
            "https://data.oireachtas.ie/graph/political-affiliations/identities"
          ],
          "variableGraphs": [
            "?memberGraph"
          ]
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "member",
            "memberName",
            "membership",
            "membershipRange",
            "membershipStart",
            "membershipEnd",
            "episode",
            "party",
            "partyLabel",
            "partyRange",
            "partyStart",
            "partyEnd",
            "affiliation",
            "affiliationLabel",
            "constituency",
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14",
              "John Browne",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#party-membership-5f8778100aa2fe5798f4f4a6d578cb25e5dd47c9c8bc001152a113d412a61b97",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil",
              "Fianna Fáil@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#party-membership-5f8778100aa2fe5798f4f4a6d578cb25e5dd47c9c8bc001152a113d412a61b97#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
              "Fianna Fáil@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06",
              "Liam Twomey",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#party-membership-3854440112c10818f2e07f356b54c6e52e1d532454ba073152ffbc1d175a0c3f",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#party-membership-3854440112c10818f2e07f356b54c6e52e1d532454ba073152ffbc1d175a0c3f#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06",
              "Paul Kehoe",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#party-membership-c8fc94b0457068d33c3a5c087561e0070b1ad5d7882dac2ddd47a2e6828e060c",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#party-membership-c8fc94b0457068d33c3a5c087561e0070b1ad5d7882dac2ddd47a2e6828e060c#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23",
              "Brendan Howlin",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party",
              "Labour Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party",
              "Labour Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:36.052951+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which Labour Party Members represented Wexford during the 31st Dáil?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_relationship_composition\",\"unsupportedReason\":null,\"intent\":\"List Labour Party Members whose Dáil membership represented Wexford during the 31st Dáil, with party membership overlapping that same representation membership.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":null},\"membership\":{\"type\":\"DailMembership\",\"mention\":null},\"term\":{\"type\":\"DailTerm\",\"mention\":null,\"selector\":{\"kind\":\"termNumber\",\"number\":31}},\"constituency\":{\"type\":\"DailConstituency\",\"mention\":\"Wexford\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":\"Labour Party\"}},\"relations\":[{\"id\":\"member_has_membership\",\"fact\":\"member_has_membership\",\"from\":\"member\",\"to\":\"membership\"},{\"id\":\"membership_in_term\",\"fact\":\"membership_in_term\",\"from\":\"membership\",\"to\":\"term\"},{\"id\":\"membership_represents\",\"fact\":\"membership_represents\",\"from\":\"membership\",\"to\":\"constituency\"},{\"id\":\"constituency_in_term\",\"fact\":\"constituency_in_term\",\"from\":\"constituency\",\"to\":\"term\"},{\"id\":\"member_party_membership\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"party_episode_in_membership\",\"fact\":\"party_episode_in_membership\",\"from\":\"episode\",\"to\":\"membership\"},{\"id\":\"episode_in_parliamentary_party\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"party_active_during_term\",\"fact\":\"party_active_during_term\",\"from\":\"party\",\"to\":\"term\"},{\"id\":\"parliamentary_party_has_affiliation_identity\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[{\"referent\":\"episode\",\"field\":\"partyEpisodeInterval\",\"operator\":\"overlaps\",\"value\":\"membership\"}],\"answer\":{\"kind\":\"entities\",\"referent\":\"member\",\"distinctBy\":\"identity\",\"display\":[\"name\"],\"details\":[{\"referent\":\"affiliation\",\"display\":[\"label\"]},{\"referent\":\"episode\",\"display\":[\"start\",\"end\"]},{\"referent\":\"membership\",\"display\":[\"start\",\"end\"]}],\"preserveEvidence\":true}}"
      }
    ]
  },
  "resolvedScope": {
    "reportingDate": "2026-11-13",
    "temporalMeaning": "compiler_plan_scope_only",
    "intent": null,
    "parentRequirementSatisfied": false
  },
  "completeness": {
    "enumeration": "unknown",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The records' last update is unknown. Separate searches may reflect different updates to the data.",
      "The search completed, but its result could not be safely included. No findings were established by this search."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Only established inclusive endpoint overlaps are reported. An absent EndDate is preserved as open-ended; missing date ranges/starts never count as overlap. PartyMembership and DailMembership retain their separate source intervals; local historical source completeness is not certified.",
  "debugOutput": null,
  "debugSource": null
}
```

### e-56d28e5dfa304ab388a75513787d8a47
```json
{
  "evidenceId": "e-56d28e5dfa304ab388a75513787d8a47",
  "request": {
    "factualRequest": "Which Members represented Wexford during the 31st Dáil?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "integration_unavailable",
    "label": "Results could not be included",
    "description": "Relevant records were found, but they couldn't be safely included in this report. This does not mean that no records exist.",
    "failureStage": "evidence_handoff",
    "retryable": false
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": "matches",
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": false
  },
  "data": null,
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "family": "member_relationship_composition",
    "referents": {
      "member": {
        "type": "Member",
        "answer": true
      },
      "membership": {
        "type": "DailMembership"
      },
      "term": {
        "type": "DailTerm",
        "selector": {
          "kind": "termNumber",
          "number": 31
        },
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
      },
      "constituency": {
        "type": "DailConstituency",
        "mention": "Wexford",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
        "label": "Wexford"
      }
    },
    "relations": [
      {
        "id": "r1",
        "fact": "member_has_membership",
        "from": "member",
        "to": "membership"
      },
      {
        "id": "r2",
        "fact": "membership_in_term",
        "from": "membership",
        "to": "term"
      },
      {
        "id": "r3",
        "fact": "membership_represents",
        "from": "membership",
        "to": "constituency"
      },
      {
        "id": "r4",
        "fact": "constituency_in_term",
        "from": "constituency",
        "to": "term"
      }
    ],
    "constraints": [],
    "answer": {
      "kind": "entities",
      "referent": "member",
      "distinctBy": "identity",
      "display": [
        "name"
      ],
      "details": [],
      "preserveEvidence": false
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Member",
      "Member identity"
    ],
    "rows": [
      [
        "Brendan Howlin",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23"
      ],
      [
        "John Browne",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14"
      ],
      [
        "Liam Twomey",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06"
      ],
      [
        "Mick Wallace",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Mick-Wallace.D.2011-03-09"
      ],
      [
        "Paul Kehoe",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:9f0677d592e531f20d4d9c238f95cc1e2af90d1798751cfc4eebd1b8a04fad39",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "14ddc43f2f964344bcf6153aaaa202fc",
      "endpointId": "query-endpoint-sha256:1f0e208be610f8d65270a2aba31144d018ac14927ea13fc5b32a148ca187944e",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T16:13:49.056011+00:00",
    "finishedAt": "2026-11-13T16:13:53.823742+00:00",
    "queries": [
      {
        "queryId": "q-4b5e637cd7c141cba3e9a9c0b88334c2",
        "sha256": "255050976d52f924e343592b74fa9fd94c1b32b732f43484ba2c958cfa5b2580",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm ; agents:termNo \"31\"^^xsd:integer .\n  }\n} LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:53.714340+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:53.724474+00:00"
      },
      {
        "queryId": "q-a3658249b9f64139a487500ee96b8207",
        "sha256": "8160ebec0de037ce88ae035dd4ae7d666a56b0a75ea0da4cf50a6750f5241cd4",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?constituency ?label WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency ; skos:prefLabel ?label ;\n      members:constituencyInHouseTerm <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> .\n  }\n}\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:53.730011+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/constituencies"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "constituency",
            "label"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-Central",
              "Dublin South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North",
              "Dublin North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-North",
              "Tipperary North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South",
              "Dublin South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wicklow",
              "Wicklow@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Carlow-Kilkenny",
              "Carlow-Kilkenny@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-North",
              "Kildare North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-Central",
              "Dublin North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-North-West-Limerick",
              "Kerry North-West Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Laois-Offaly",
              "Laois-Offaly@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-Central",
              "Cork North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-South",
              "Kerry South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "Wexford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cavan-Monaghan",
              "Cavan-Monaghan@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-West",
              "Dublin South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-West",
              "Dublin West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-West",
              "Galway West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-North-East",
              "Donegal North-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Waterford",
              "Waterford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-East",
              "Galway East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-Central",
              "Cork South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-West",
              "Meath West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick",
              "Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Mayo",
              "Mayo@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-East",
              "Cork East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Roscommon-South-Leitrim",
              "Roscommon-South-Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Mid-West",
              "Dublin Mid-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-West",
              "Dublin North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-South-West",
              "Donegal South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-East",
              "Meath East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dún-Laoghaire",
              "Dún Laoghaire@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-East",
              "Dublin South-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Louth",
              "Louth@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Longford-Westmeath",
              "Longford-Westmeath@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-South",
              "Kildare South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick-City",
              "Limerick City@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-West",
              "Cork South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Clare",
              "Clare@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Central",
              "Dublin Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Sligo-North-Leitrim",
              "Sligo-North Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-South",
              "Tipperary South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-West",
              "Cork North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-East",
              "Dublin North-East@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:53.737078+00:00"
      },
      {
        "queryId": "q-b31530bd25544e7493286a1b1c28f5ba",
        "sha256": "2ad5203a18a062c4b1dfd6194f091bc2ce236e1d34c12ac8f0bb3b87ea9dee35",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?memberName WHERE {\n  GRAPH ?memberGraph {\n    ?member a agents:Member .\n    OPTIONAL { ?member foaf:name ?memberName . }\n    ?membership a members:DailMembership .\n    ?member members:hasMembersMembership ?membership .\n    ?membership members:inHouseTerm ?term .\n    ?membership members:isRepresentativeFrom ?constituency .\n  }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm .\n    VALUES ?term { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> }\n    ?term agents:termNo \"31\"^^xsd:integer .\n  }\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency .\n    VALUES ?constituency { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford> }\n    ?constituency members:constituencyInHouseTerm ?term .\n  }\n} ORDER BY ?memberName ?member ?membership LIMIT 100 OFFSET 0",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:13:53.754365+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses",
            "https://data.oireachtas.ie/graph/constituencies"
          ],
          "variableGraphs": [
            "?memberGraph"
          ]
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "member",
            "memberName"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23",
              "Brendan Howlin"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14",
              "John Browne"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06",
              "Liam Twomey"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Mick-Wallace.D.2011-03-09",
              "Mick Wallace"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06",
              "Paul Kehoe"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:13:53.823491+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which Members represented Wexford during the 31st Dáil?",
        "output": "{\n  \"version\": 2,\n  \"supported\": true,\n  \"family\": \"member_relationship_composition\",\n  \"unsupportedReason\": null,\n  \"intent\": \"List the Members who represented Wexford during the 31st Dáil.\",\n  \"referents\": {\n    \"member\": {\n      \"type\": \"Member\",\n      \"mention\": null\n    },\n    \"membership\": {\n      \"type\": \"DailMembership\",\n      \"mention\": null\n    },\n    \"term\": {\n      \"type\": \"DailTerm\",\n      \"mention\": null,\n      \"selector\": {\n        \"kind\": \"termNumber\",\n        \"number\": 31\n      }\n    },\n    \"constituency\": {\n      \"type\": \"DailConstituency\",\n      \"mention\": \"Wexford\"\n    }\n  },\n  \"relations\": [\n    {\n      \"id\": \"r1\",\n      \"fact\": \"member_has_membership\",\n      \"from\": \"member\",\n      \"to\": \"membership\"\n    },\n    {\n      \"id\": \"r2\",\n      \"fact\": \"membership_in_term\",\n      \"from\": \"membership\",\n      \"to\": \"term\"\n    },\n    {\n      \"id\": \"r3\",\n      \"fact\": \"membership_represents\",\n      \"from\": \"membership\",\n      \"to\": \"constituency\"\n    },\n    {\n      \"id\": \"r4\",\n      \"fact\": \"constituency_in_term\",\n      \"from\": \"constituency\",\n      \"to\": \"term\"\n    }\n  ],\n  \"constraints\": [],\n  \"answer\": {\n    \"kind\": \"entities\",\n    \"referent\": \"member\",\n    \"distinctBy\": \"identity\",\n    \"display\": [\n      \"name\"\n    ],\n    \"details\": [],\n    \"preserveEvidence\": false\n  }\n}"
      }
    ]
  },
  "resolvedScope": {
    "reportingDate": "2026-11-13",
    "temporalMeaning": "compiler_plan_scope_only",
    "intent": null,
    "parentRequirementSatisfied": false
  },
  "completeness": {
    "enumeration": "unknown",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The records' last update is unknown. Separate searches may reflect different updates to the data.",
      "Relevant records were found, but they couldn't be safely included in this report. This does not mean that no records exist."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "Relevant records were found, but they couldn't be safely included in this report. This does not mean that no records exist.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Members are deduplicated by exact RDF identity. Members are matched through the complete selected membership/term/constituency graph. Results reflect local records; historical source completeness is not certified.",
  "debugOutput": null,
  "debugSource": null
}
```

### e-b798aa2986a24fdb9fe3306c97d08b96
```json
{
  "evidenceId": "e-b798aa2986a24fdb9fe3306c97d08b96",
  "request": {
    "factualRequest": "Which political parties are recorded for Members who represented Wexford during the 31st Dáil?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "integration_unavailable",
    "label": "Result not included",
    "description": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "failureStage": "evidence_handoff",
    "retryable": false
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": null,
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": false
  },
  "data": null,
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "family": "member_relationship_composition",
    "referents": {
      "member": {
        "type": "Member"
      },
      "membership": {
        "type": "DailMembership"
      },
      "term": {
        "type": "DailTerm",
        "selector": {
          "kind": "termNumber",
          "number": 31
        },
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
      },
      "episode": {
        "type": "PartyMembershipEpisode"
      },
      "party": {
        "type": "ParliamentaryParty"
      },
      "affiliation": {
        "type": "PoliticalAffiliationIdentity",
        "answer": true
      },
      "constituency": {
        "type": "DailConstituency",
        "mention": "Wexford",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
        "label": "Wexford"
      }
    },
    "relations": [
      {
        "id": "r1",
        "fact": "member_has_membership",
        "from": "member",
        "to": "membership"
      },
      {
        "id": "r2",
        "fact": "membership_in_term",
        "from": "membership",
        "to": "term"
      },
      {
        "id": "r3",
        "fact": "membership_represents",
        "from": "membership",
        "to": "constituency"
      },
      {
        "id": "r4",
        "fact": "constituency_in_term",
        "from": "constituency",
        "to": "term"
      },
      {
        "id": "r5",
        "fact": "member_party_membership",
        "from": "member",
        "to": "episode"
      },
      {
        "id": "r6",
        "fact": "party_episode_in_membership",
        "from": "episode",
        "to": "membership"
      },
      {
        "id": "r7",
        "fact": "episode_in_parliamentary_party",
        "from": "episode",
        "to": "party"
      },
      {
        "id": "r8",
        "fact": "party_active_during_term",
        "from": "party",
        "to": "term"
      },
      {
        "id": "r9",
        "fact": "parliamentary_party_has_affiliation_identity",
        "from": "party",
        "to": "affiliation"
      }
    ],
    "constraints": [
      {
        "referent": "episode",
        "field": "partyEpisodeInterval",
        "operator": "overlaps",
        "value": "membership"
      }
    ],
    "answer": {
      "kind": "entities",
      "referent": "affiliation",
      "distinctBy": "identity",
      "display": [
        "label"
      ],
      "details": [
        {
          "referent": "member",
          "display": [
            "name"
          ]
        },
        {
          "referent": "episode",
          "display": [
            "start",
            "end"
          ]
        },
        {
          "referent": "membership",
          "display": [
            "start",
            "end"
          ]
        }
      ],
      "preserveEvidence": true
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Political party",
      "Political-affiliation identity",
      "Established overlapping TD evidence"
    ],
    "rows": [
      [
        "Fianna Fáil",
        "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
        "John Browne (https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14); affiliation 2011-02-25T00:00:00 – 2016-03-09T00:00:00; Dáil representation 2011-03-09T00:00:00 – 2016-03-09T00:00:00; membership https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31; term https://data.oireachtas.ie/ie/oireachtas/house/dail/31; affiliation identity https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail; established overlap 2011-03-09T00:00:00 – 2016-03-09T00:00:00; episode https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#party-membership-5f8778100aa2fe5798f4f4a6d578cb25e5dd47c9c8bc001152a113d412a61b97; party https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil"
      ],
      [
        "Fine Gael",
        "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
        "Liam Twomey (https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06); affiliation 2011-02-25T00:00:00 – 2016-03-09T00:00:00; Dáil representation 2011-03-09T00:00:00 – 2016-03-09T00:00:00; membership https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31; term https://data.oireachtas.ie/ie/oireachtas/house/dail/31; affiliation identity https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael; established overlap 2011-03-09T00:00:00 – 2016-03-09T00:00:00; episode https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#party-membership-3854440112c10818f2e07f356b54c6e52e1d532454ba073152ffbc1d175a0c3f; party https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael; Paul Kehoe (https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06); affiliation 2011-02-25T00:00:00 – 2016-03-09T00:00:00; Dáil representation 2011-03-09T00:00:00 – 2016-03-09T00:00:00; membership https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31; term https://data.oireachtas.ie/ie/oireachtas/house/dail/31; affiliation identity https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael; established overlap 2011-03-09T00:00:00 – 2016-03-09T00:00:00; episode https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#party-membership-c8fc94b0457068d33c3a5c087561e0070b1ad5d7882dac2ddd47a2e6828e060c; party https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael"
      ],
      [
        "Labour Party",
        "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party",
        "Brendan Howlin (https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23); affiliation 2011-02-25T00:00:00 – 2016-03-09T00:00:00; Dáil representation 2011-03-09T00:00:00 – 2016-03-09T00:00:00; membership https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31; term https://data.oireachtas.ie/ie/oireachtas/house/dail/31; affiliation identity https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party; established overlap 2011-03-09T00:00:00 – 2016-03-09T00:00:00; episode https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d; party https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:9f0677d592e531f20d4d9c238f95cc1e2af90d1798751cfc4eebd1b8a04fad39",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "14ddc43f2f964344bcf6153aaaa202fc",
      "endpointId": "query-endpoint-sha256:1f0e208be610f8d65270a2aba31144d018ac14927ea13fc5b32a148ca187944e",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T16:13:56.574938+00:00",
    "finishedAt": "2026-11-13T16:14:03.079244+00:00",
    "queries": [
      {
        "queryId": "q-db4da9c4a80647f7b096908dcf5fc60f",
        "sha256": "255050976d52f924e343592b74fa9fd94c1b32b732f43484ba2c958cfa5b2580",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm ; agents:termNo \"31\"^^xsd:integer .\n  }\n} LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:14:02.539561+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:14:02.550083+00:00"
      },
      {
        "queryId": "q-672f92d9524f4511800ed8ddfb27d189",
        "sha256": "8160ebec0de037ce88ae035dd4ae7d666a56b0a75ea0da4cf50a6750f5241cd4",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?constituency ?label WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency ; skos:prefLabel ?label ;\n      members:constituencyInHouseTerm <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> .\n  }\n}\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:14:02.554224+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/constituencies"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "constituency",
            "label"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-Central",
              "Dublin South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North",
              "Dublin North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-North",
              "Tipperary North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South",
              "Dublin South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wicklow",
              "Wicklow@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Carlow-Kilkenny",
              "Carlow-Kilkenny@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-North",
              "Kildare North@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-Central",
              "Dublin North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-North-West-Limerick",
              "Kerry North-West Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Laois-Offaly",
              "Laois-Offaly@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-Central",
              "Cork North-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kerry-South",
              "Kerry South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "Wexford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cavan-Monaghan",
              "Cavan-Monaghan@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-West",
              "Dublin South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-West",
              "Dublin West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-West",
              "Galway West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-North-East",
              "Donegal North-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Waterford",
              "Waterford@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Galway-East",
              "Galway East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-Central",
              "Cork South-Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-West",
              "Meath West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick",
              "Limerick@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Mayo",
              "Mayo@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-East",
              "Cork East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Roscommon-South-Leitrim",
              "Roscommon-South-Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Mid-West",
              "Dublin Mid-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-West",
              "Dublin North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Donegal-South-West",
              "Donegal South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Meath-East",
              "Meath East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dún-Laoghaire",
              "Dún Laoghaire@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-South-East",
              "Dublin South-East@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Louth",
              "Louth@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Longford-Westmeath",
              "Longford-Westmeath@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Kildare-South",
              "Kildare South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Limerick-City",
              "Limerick City@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-South-West",
              "Cork South-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Clare",
              "Clare@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-Central",
              "Dublin Central@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Sligo-North-Leitrim",
              "Sligo-North Leitrim@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Tipperary-South",
              "Tipperary South@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Cork-North-West",
              "Cork North-West@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Dublin-North-East",
              "Dublin North-East@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:14:02.560888+00:00"
      },
      {
        "queryId": "q-e20d2eb7d6eb4782a7268dd29c10d023",
        "sha256": "ff670c6027df7bd8d3b6fb03cc5822985fd032077c764a972a08d9b15c09a5ca",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?memberName ?membership ?membershipRange ?membershipStart ?membershipEnd ?episode ?party ?partyLabel ?partyRange ?partyStart ?partyEnd ?affiliation ?affiliationLabel ?constituency ?term WHERE {\nGRAPH ?memberGraph { ?member a agents:Member . ?membership a members:DailMembership . ?episode a members:PartyMembership . ?member members:hasMembersMembership ?membership . ?membership members:inHouseTerm ?term . ?membership members:isRepresentativeFrom ?constituency . ?member members:hasMembersMembership ?episode . ?episode members:inOireachtasMembership ?membership . ?episode members:isPartyMembershipOf ?party . OPTIONAL { ?member foaf:name ?memberName . } OPTIONAL { ?membership members:hasMembershipDateRange ?membershipRange .\n      ?membershipRange a members:DateRange .\n      OPTIONAL { ?membershipRange members:StartDate ?membershipStart . }\n      OPTIONAL { ?membershipRange members:EndDate ?membershipEnd . } } OPTIONAL { ?episode members:hasMembershipDateRange ?partyRange .\n      ?partyRange a members:DateRange .\n      OPTIONAL { ?partyRange members:StartDate ?partyStart . }\n      OPTIONAL { ?partyRange members:EndDate ?partyEnd . } } } FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\nGRAPH <https://data.oireachtas.ie/graph/houses> { ?term a agents:DailTerm . VALUES ?term { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> } ?term agents:termNo \"31\"^^xsd:integer . }\nGRAPH <https://data.oireachtas.ie/graph/constituencies> { ?constituency a members:DailConstituency . VALUES ?constituency { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford> } ?constituency members:constituencyInHouseTerm ?term . }\nGRAPH <https://data.oireachtas.ie/graph/parties> { ?party a members:ParliamentaryParty . ?party members:activeDuringTerm ?term . OPTIONAL { ?party skos:prefLabel ?partyLabel . FILTER(LANG(?partyLabel) = \"en\") } }\nOPTIONAL { GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> { ?affiliation a members:PoliticalAffiliationIdentity . ?party members:hasPoliticalAffiliationIdentity ?affiliation . OPTIONAL { ?affiliation skos:prefLabel ?affiliationLabel . FILTER(LANG(?affiliationLabel) = \"en\") } } }\n} ORDER BY ?affiliationLabel ?memberName ?partyStart ?membershipStart ?episode ?membership LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:14:02.601707+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses",
            "https://data.oireachtas.ie/graph/constituencies",
            "https://data.oireachtas.ie/graph/parties",
            "https://data.oireachtas.ie/graph/political-affiliations/identities"
          ],
          "variableGraphs": [
            "?memberGraph"
          ]
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "member",
            "memberName",
            "membership",
            "membershipRange",
            "membershipStart",
            "membershipEnd",
            "episode",
            "party",
            "partyLabel",
            "partyRange",
            "partyStart",
            "partyEnd",
            "affiliation",
            "affiliationLabel",
            "constituency",
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14",
              "John Browne",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#party-membership-5f8778100aa2fe5798f4f4a6d578cb25e5dd47c9c8bc001152a113d412a61b97",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil",
              "Fianna Fáil@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/John-Browne.D.1982-12-14/house/dail/31#party-membership-5f8778100aa2fe5798f4f4a6d578cb25e5dd47c9c8bc001152a113d412a61b97#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
              "Fianna Fáil@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06",
              "Liam Twomey",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#party-membership-3854440112c10818f2e07f356b54c6e52e1d532454ba073152ffbc1d175a0c3f",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Liam-Twomey.D.2002-06-06/house/dail/31#party-membership-3854440112c10818f2e07f356b54c6e52e1d532454ba073152ffbc1d175a0c3f#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06",
              "Paul Kehoe",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#party-membership-c8fc94b0457068d33c3a5c087561e0070b1ad5d7882dac2ddd47a2e6828e060c",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Paul-Kehoe.D.2002-06-06/house/dail/31#party-membership-c8fc94b0457068d33c3a5c087561e0070b1ad5d7882dac2ddd47a2e6828e060c#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael",
              "Fine Gael@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23",
              "Brendan Howlin",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#date-range",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d",
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party",
              "Labour Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23/house/dail/31#party-membership-6f9eb7b905aca031ed452b766150c516716971d8e04c9a06e138f59e39fcd92d#date-range",
              "2011-02-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party",
              "Labour Party@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Wexford",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:14:03.078561+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which political parties are recorded for Members who represented Wexford during the 31st Dáil?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_relationship_composition\",\"unsupportedReason\":null,\"intent\":\"List the recorded political-party affiliations of Members whose Dáil membership represented Wexford during the 31st Dáil, preserving the party episode and representation evidence.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":null},\"membership\":{\"type\":\"DailMembership\",\"mention\":null},\"term\":{\"type\":\"DailTerm\",\"mention\":null,\"selector\":{\"kind\":\"termNumber\",\"number\":31}},\"constituency\":{\"type\":\"DailConstituency\",\"mention\":\"Wexford\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"r1\",\"fact\":\"member_has_membership\",\"from\":\"member\",\"to\":\"membership\"},{\"id\":\"r2\",\"fact\":\"membership_in_term\",\"from\":\"membership\",\"to\":\"term\"},{\"id\":\"r3\",\"fact\":\"membership_represents\",\"from\":\"membership\",\"to\":\"constituency\"},{\"id\":\"r4\",\"fact\":\"constituency_in_term\",\"from\":\"constituency\",\"to\":\"term\"},{\"id\":\"r5\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"r6\",\"fact\":\"party_episode_in_membership\",\"from\":\"episode\",\"to\":\"membership\"},{\"id\":\"r7\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"r8\",\"fact\":\"party_active_during_term\",\"from\":\"party\",\"to\":\"term\"},{\"id\":\"r9\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[{\"referent\":\"episode\",\"field\":\"partyEpisodeInterval\",\"operator\":\"overlaps\",\"value\":\"membership\"}],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[{\"referent\":\"member\",\"display\":[\"name\"]},{\"referent\":\"episode\",\"display\":[\"start\",\"end\"]},{\"referent\":\"membership\",\"display\":[\"start\",\"end\"]}],\"preserveEvidence\":true}}"
      }
    ]
  },
  "resolvedScope": {
    "reportingDate": "2026-11-13",
    "temporalMeaning": "compiler_plan_scope_only",
    "intent": null,
    "parentRequirementSatisfied": false
  },
  "completeness": {
    "enumeration": "unknown",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The records' last update is unknown. Separate searches may reflect different updates to the data.",
      "The search completed, but its result could not be safely included. No findings were established by this search."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Only established inclusive endpoint overlaps are reported. An absent EndDate is preserved as open-ended; missing date ranges/starts never count as overlap. PartyMembership and DailMembership retain their separate source intervals; local historical source completeness is not certified.",
  "debugOutput": null,
  "debugSource": null
}
```

### e-983269d8044a4eb2a270e76110b2f4db
```json
{
  "evidenceId": "e-983269d8044a4eb2a270e76110b2f4db",
  "request": {
    "factualRequest": "Which political parties are recorded in the 31st Dáil?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "integration_unavailable",
    "label": "Result not included",
    "description": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "failureStage": "evidence_handoff",
    "retryable": false
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": null,
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": false
  },
  "data": null,
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "family": "dail_parties_and_groups",
    "referents": {
      "term": {
        "type": "DailTerm",
        "selector": {
          "kind": "termNumber",
          "number": 31
        }
      },
      "party": {
        "type": "ParliamentaryParty",
        "answer": true
      }
    },
    "relations": [
      {
        "id": "party-active-term",
        "fact": "party_active_during_term",
        "from": "party",
        "to": "term"
      }
    ],
    "answer": {
      "kind": "family_result",
      "referent": "party",
      "projection": "dail_parties_and_groups",
      "includeGroups": false
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Party",
      "Identity"
    ],
    "rows": [
      [
        "Anti-Austerity Alliance - People Before Profit",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Anti-Austerity_Alliance_People_Before_Profit"
      ],
      [
        "Fianna Fáil",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil"
      ],
      [
        "Fine Gael",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael"
      ],
      [
        "Labour Party",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party"
      ],
      [
        "People Before Profit Alliance",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/People_Before_Profit_Alliance"
      ],
      [
        "Renua",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Renua"
      ],
      [
        "Sinn Féin",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Sinn_Féin"
      ],
      [
        "Social Democrats",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Social_Democrats"
      ],
      [
        "Socialist Party",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Socialist_Party"
      ],
      [
        "Workers and Unemployed Action",
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Workers_and_Unemployed_Action"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:9f0677d592e531f20d4d9c238f95cc1e2af90d1798751cfc4eebd1b8a04fad39",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "14ddc43f2f964344bcf6153aaaa202fc",
      "endpointId": "query-endpoint-sha256:1f0e208be610f8d65270a2aba31144d018ac14927ea13fc5b32a148ca187944e",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T16:14:15.183228+00:00",
    "finishedAt": "2026-11-13T16:14:17.821893+00:00",
    "queries": [
      {
        "queryId": "q-87cd85ca4e8f475f8adc0eb1c3df6c1f",
        "sha256": "45660e2ba53e530ba5766a741a8256d5fa182cdb27d7309652ebab7522e09cf1",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a agents:DailTerm ; agents:termNo \"31\"^^xsd:integer . }\n} LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:14:17.795089+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "term"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:14:17.807796+00:00"
      },
      {
        "queryId": "q-f60e58df03334801b720da45e6e28f20",
        "sha256": "d69ccc3b82705d61bac20644accf71e784637a04dd8fd518f1edaf8ebc80d873",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?party ?label WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> { <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> a agents:DailTerm . }\n  GRAPH <https://data.oireachtas.ie/graph/parties> {\n    ?party a members:ParliamentaryParty ; members:activeDuringTerm <https://data.oireachtas.ie/ie/oireachtas/house/dail/31> .\n    OPTIONAL { ?party skos:prefLabel ?label . }\n  }\n} ORDER BY ?party ?label LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T16:14:17.815310+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/houses",
            "https://data.oireachtas.ie/graph/parties"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "party",
            "label"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Anti-Austerity_Alliance_People_Before_Profit",
              "Anti-Austerity Alliance - People Before Profit@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fianna_Fáil",
              "Fianna Fáil@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael",
              "Fine Gael@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Labour_Party",
              "Labour Party@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/People_Before_Profit_Alliance",
              "People Before Profit Alliance@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Renua",
              "Renua@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Sinn_Féin",
              "Sinn Féin@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Social_Democrats",
              "Social Democrats@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Socialist_Party",
              "Socialist Party@en"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Workers_and_Unemployed_Action",
              "Workers and Unemployed Action@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T16:14:17.821521+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which political parties are recorded in the 31st Dáil?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"capability_selection\",\"unsupportedReason\":null,\"intent\":\"List the political parties recorded in the 31st Dáil.\",\"referents\":{\"capability\":\"dail_parties_and_groups\",\"parameters\":{\"termNumber\":31,\"includeGroups\":false}},\"relations\":[],\"constraints\":[],\"answer\":null}"
      }
    ]
  },
  "resolvedScope": {
    "reportingDate": "2026-11-13",
    "temporalMeaning": "compiler_plan_scope_only",
    "intent": null,
    "parentRequirementSatisfied": false
  },
  "completeness": {
    "enumeration": "unknown",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The records' last update is unknown. Separate searches may reflect different updates to the data.",
      "The search completed, but its result could not be safely included. No findings were established by this search."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "The search completed, but its result could not be safely included. No findings were established by this search.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Term-scoped ParliamentaryParty records for the 31st Dáil are listed separately. ",
  "debugOutput": null,
  "debugSource": null
}
```
