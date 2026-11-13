# Stephen Donnelly's party membership

**Draft — for review** · Incomplete / qualified research

Original brief: What parties was Stephen Donnelly a member of, and when?
Reporting date: 2026-11-13

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The source's last update and completeness are not established. Retrieval time is not source freshness.

## Unanswered research questions

- What parties was Stephen Donnelly a member of, and when?

## Assertion evidence and reasoning

## Evidence references

### e-183f50ffac9c4150a4341dff6005bbb4
```json
{
  "evidenceId": "e-183f50ffac9c4150a4341dff6005bbb4",
  "request": {
    "factualRequest": "What parties was Stephen Donnelly a member of, and when?",
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
    "startedAt": "2026-11-13T08:47:12.845305+00:00",
    "finishedAt": "2026-11-13T08:47:16.509814+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "What parties was Stephen Donnelly a member of, and when?",
        "output": "{\"version\":2,\"supported\":false,\"family\":null,\"unsupportedReason\":\"The local party-history capability can identify recorded party affiliations, but does not support returning when those memberships occurred.\",\"intent\":\"Find the parties Stephen Donnelly belonged to and the dates or periods of each membership.\",\"referents\":null,\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "The local party-history capability can identify recorded party affiliations, but does not support returning when those memberships occurred."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "The local party-history capability can identify recorded party affiliations, but does not support returning when those memberships occurred.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "The local party-history capability can identify recorded party affiliations, but does not support returning when those memberships occurred."
}
```

### e-e3d054a4d04a4be59514f1328b62b4b1
```json
{
  "evidenceId": "e-e3d054a4d04a4be59514f1328b62b4b1",
  "request": {
    "factualRequest": "Which political parties are recorded as having had Stephen Donnelly as a member, without establishing when each membership occurred?",
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
    "startedAt": "2026-11-13T08:47:23.066015+00:00",
    "finishedAt": "2026-11-13T08:47:26.425687+00:00",
    "queries": [
      {
        "queryId": "q-08bc428736a247f096286d5682d8b233",
        "sha256": "9110db10ccfdf622774ea7f5b82d140bf245957faaa63e027ef73f4b493f959c",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?name ?sourceId WHERE {\n  GRAPH ?memberGraph { ?member a agents:Member ; foaf:name ?name . OPTIONAL { ?member agents:pId ?sourceId . } }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n  FILTER(CONTAINS(LCASE(STR(?name)), LCASE(STR(\"Stephen Donnelly\"))) ||\n         LCASE(STR(?sourceId)) = LCASE(STR(\"StephenDonnelly\")))\n} ORDER BY ?member ?name LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T08:47:26.360788+00:00",
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
        "finishedAt": "2026-11-13T08:47:26.380779+00:00"
      },
      {
        "queryId": "q-e0607ef2d2b346e7ac57aa5c1cf7d4c7",
        "sha256": "bd1b041a986269a0080fe8cc5e19c74b0ddff653ef37243336998e44c94beb11",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?episode ?identity ?affiliationLabel ?start ?end WHERE {\n  VALUES ?member { <https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09> }\n  GRAPH ?memberGraph {\n    <https://data.oireachtas.ie/ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09> a agents:Member ; members:hasMembersMembership ?episode .\n    ?episode a members:PartyMembership ; members:inOireachtasMembership ?membership ; members:isPartyMembershipOf ?party .\n    ?membership members:inHouseTerm ?term .\n    OPTIONAL { ?episode members:hasMembershipDateRange ?dateRange .\n      ?dateRange a members:DateRange .\n      OPTIONAL { ?dateRange members:StartDate ?start . }\n      OPTIONAL { ?dateRange members:EndDate ?end . }\n    }\n  }\n  GRAPH <https://data.oireachtas.ie/graph/parties> { ?party a members:ParliamentaryParty ; members:activeDuringTerm ?term . }\n  GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . }\n  VALUES ?termType { agents:DailTerm agents:SeanadTerm }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/political-affiliations/identities> {\n    ?party members:hasPoliticalAffiliationIdentity ?identity .\n    ?identity a members:PoliticalAffiliationIdentity .\n    OPTIONAL { ?identity skos:prefLabel ?affiliationLabel . FILTER(LANG(?affiliationLabel) = \"en\") }\n  } }\n} ORDER BY ?affiliationLabel ?identity ?episode ?start ?end ?member\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T08:47:26.416616+00:00",
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
        "finishedAt": "2026-11-13T08:47:26.425190+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Which political parties are recorded as having had Stephen Donnelly as a member, without establishing when each membership occurred?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_party_history\",\"unsupportedReason\":null,\"intent\":\"List the political parties recorded as having had Stephen Donnelly as a member, without specifying when the memberships occurred.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":\"Stephen Donnelly\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"member_party_membership\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"episode_in_parliamentary_party\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"parliamentary_party_has_affiliation_identity\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[],\"preserveEvidence\":true}}"
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
