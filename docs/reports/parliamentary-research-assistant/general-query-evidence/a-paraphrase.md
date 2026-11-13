# Stephen Donnelly’s recorded political party affiliations

**Draft — for review** · Incomplete / qualified research

Original brief: Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?
Reporting date: 2026-11-13

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The source's last update and completeness are not established. Retrieval time is not source freshness.
- Results can describe accepted local records, but cannot certify that they are a complete or up-to-date account of Stephen Donnelly’s affiliations.

## Unanswered research questions

- What party affiliations and membership dates, if any, are supported by recorded evidence?

## Assertion evidence and reasoning

## Evidence references

### e-391870483dca472ba58efb23661176b9
```json
{
  "evidenceId": "e-391870483dca472ba58efb23661176b9",
  "request": {
    "factualRequest": "Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "unsupported_capability",
  "queryServiceOutcome": "unsupported_capability",
  "compilerStatus": "unsupported_request",
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:a4933e7c4e580ed79fc4d8fa750baae4b72eaa1c073a908bdcced81ff1d8df7e",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:52:41.219803+00:00",
    "finishedAt": "2026-11-13T08:52:44.620932+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?",
        "output": "{\"version\":2,\"supported\":false,\"family\":null,\"unsupportedReason\":\"The available party-history query does not support adding membership dates to the affiliation list.\",\"intent\":\"Trace Stephen Donnelly's recorded political party affiliations and show membership dates where available.\",\"referents\":null,\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "The source's last update and completeness are not established. Retrieval time is not source freshness.",
      "The available party-history query does not support adding membership dates to the affiliation list."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "The available party-history query does not support adding membership dates to the affiliation list.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "The available party-history query does not support adding membership dates to the affiliation list."
}
```

### e-ec2247f0c3854b658be83f1ea120033a
```json
{
  "evidenceId": "e-ec2247f0c3854b658be83f1ea120033a",
  "request": {
    "factualRequest": "What political party affiliations are recorded for Stephen Donnelly?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "unsupported_capability",
  "queryServiceOutcome": "unsupported_capability",
  "compilerStatus": "unsupported_request",
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:a4933e7c4e580ed79fc4d8fa750baae4b72eaa1c073a908bdcced81ff1d8df7e",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:52:51.870813+00:00",
    "finishedAt": "2026-11-13T08:52:55.044322+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "What political party affiliations are recorded for Stephen Donnelly?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_party_history\",\"unsupportedReason\":null,\"intent\":\"Find the recorded political party affiliations for Stephen Donnelly.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":\"Stephen Donnelly\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"r1\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"r2\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"r3\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[],\"preserveEvidence\":true}}"
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
      "The source's last update and completeness are not established. Retrieval time is not source freshness.",
      "A present/current party question requires dated current collection evidence; career-wide party history cannot substitute for current membership."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "A present/current party question requires dated current collection evidence; career-wide party history cannot substitute for current membership.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "A present/current party question requires dated current collection evidence; career-wide party history cannot substitute for current membership."
}
```

### e-6ced8e40602641379fd770028927458c
```json
{
  "evidenceId": "e-6ced8e40602641379fd770028927458c",
  "request": {
    "factualRequest": "Which political parties are linked to Stephen Donnelly through recorded party-membership episodes over his career?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": false
  },
  "data": null,
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "referents": {
      "member": {
        "type": "Member",
        "mention": "Stephen Donnelly",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
        "label": "Stephen Donnelly"
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
      }
    },
    "relations": [
      {
        "id": "member-party-episode",
        "fact": "member_party_membership",
        "from": "member",
        "to": "episode"
      },
      {
        "id": "episode-party",
        "fact": "episode_in_parliamentary_party",
        "from": "episode",
        "to": "party"
      },
      {
        "id": "party-affiliation",
        "fact": "parliamentary_party_has_affiliation_identity",
        "from": "party",
        "to": "affiliation"
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
          "referent": "episode",
          "display": [
            "start",
            "end"
          ]
        }
      ],
      "preserveGaps": true
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Political affiliation",
      "Supporting membership episodes"
    ],
    "rows": [
      [
        "Fianna Fáil",
        "2017-02-02T00:00:00 – 2020-01-14T00:00:00; 2020-02-08T00:00:00 – 2024-11-08T00:00:00"
      ],
      [
        "Social Democrats",
        "2015-07-15T00:00:00 – 2016-03-09T00:00:00; 2016-03-10T00:00:00 – 2016-09-04T00:00:00"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:a4933e7c4e580ed79fc4d8fa750baae4b72eaa1c073a908bdcced81ff1d8df7e",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:53:04.363806+00:00",
    "finishedAt": "2026-11-13T08:53:07.820605+00:00",
    "queries": [
      {
        "queryId": "q-9c0c7549e3aa43eebe06805c8147436e",
        "sha256": "9110db10ccfdf622774ea7f5b82d140bf245957faaa63e027ef73f4b493f959c",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?name ?sourceId WHERE {\n  GRAPH ?memberGraph { ?member a agents:Member ; foaf:name ?name . OPTIONAL { ?member agents:pId ?sourceId . } }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n  FILTER(CONTAINS(LCASE(STR(?name)), LCASE(STR(\"Stephen Donnelly\"))) ||\n         LCASE(STR(?sourceId)) = LCASE(STR(\"StephenDonnelly\")))\n} ORDER BY ?member ?name LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T08:53:07.754184+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [],
          "variableGraphs": [
            "?memberGraph"
          ]
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "member",
            "name",
            "sourceId"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
              "Stephen Donnelly",
              "StephenDonnelly"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T08:53:07.777391+00:00"
      },
      {
        "queryId": "q-bf2287aa6b9249fe85e18bc09cd58b70",
        "sha256": "bd1b041a986269a0080fe8cc5e19c74b0ddff653ef37243336998e44c94beb11",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?episode ?identity ?affiliationLabel ?start ?end WHERE {\n  VALUES ?member { <https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09> }\n  GRAPH ?memberGraph {\n    <https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09> a agents:Member ; members:hasMembersMembership ?episode .\n    ?episode a members:PartyMembership ; members:inOireachtasMembership ?membership ; members:isPartyMembershipOf ?party .\n    ?membership members:inHouseTerm ?term .\n    OPTIONAL { ?episode members:hasMembershipDateRange ?dateRange .\n      ?dateRange a members:DateRange .\n      OPTIONAL { ?dateRange members:StartDate ?start . }\n      OPTIONAL { ?dateRange members:EndDate ?end . }\n    }\n  }\n  GRAPH <https://data.oireachtas.ie/graph/parties> { ?party a members:ParliamentaryParty ; members:activeDuringTerm ?term . }\n  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . }\n  VALUES ?termType { agents:DailTerm agents:SeanadTerm }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> {\n    ?party members:hasPoliticalAffiliationIdentity ?identity .\n    ?identity a members:PoliticalAffiliationIdentity .\n    OPTIONAL { ?identity skos:prefLabel ?affiliationLabel . FILTER(LANG(?affiliationLabel) = \"en\") }\n  } }\n} ORDER BY ?affiliationLabel ?identity ?episode ?start ?end ?member\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T08:53:07.813796+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/parties",
            "https://data.oireachtas.ie/graph/houses",
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
            "episode",
            "identity",
            "affiliationLabel",
            "start",
            "end"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09/house/dail/32#party-membership-c32070aaae46564df8dbe809ed97a33e64fd43a794ff0321d021c53a55a3f713",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
              "Fianna Fáil@en",
              "2017-02-02T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2020-01-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09/house/dail/33#party-membership-95d28a40bfcc10e7d03b06ca9a517491596eca22f33c08c4cba70001727913a7",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
              "Fianna Fáil@en",
              "2020-02-08T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2024-11-08T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09/house/dail/31#party-membership-408d07d9f690b6f5e78be11f27f6acc1f38c614ae3acbc612c09e3978397fc14",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/social-democrats",
              "Social Democrats@en",
              "2015-07-15T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09/house/dail/32#party-membership-10335da3f9a90ee7bac715054fbe75d674a37d610c4f2215c0feb141631baee9",
              "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/social-democrats",
              "Social Democrats@en",
              "2016-03-10T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-09-04T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T08:53:07.820315+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which political parties are linked to Stephen Donnelly through recorded party-membership episodes over his career?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_party_history\",\"unsupportedReason\":null,\"intent\":\"Find the political-party affiliations linked to Stephen Donnelly through his recorded party-membership episodes over his career.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":\"Stephen Donnelly\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"r1\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"r2\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"r3\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[],\"preserveEvidence\":true}}"
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
      "The source's last update and completeness are not established. Retrieval time is not source freshness.",
      "The Query Service returned a response, but this capability supplies no accepted structured research evidence. Its response is retained for inspection; no research fact was promoted."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "The Query Service returned a response, but this capability supplies no accepted structured research evidence. Its response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Affiliations are grouped by reviewed local identity; dated source episodes remain separate."
}
```
