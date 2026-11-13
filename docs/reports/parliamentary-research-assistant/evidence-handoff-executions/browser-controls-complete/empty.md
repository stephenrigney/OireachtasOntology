# Committee membership

**Draft — for review** · No matching records found

Original brief: How many TDs represented Meath East in this Dáil on 2026-10-28?
Reporting date: 2026-11-13

No matching records were found in the available data. The data may be incomplete.


## Unanswered research questions

- How many TDs represented Meath East in this Dáil on 2026-10-28?

## Assertion evidence and reasoning

## Evidence references

### e-7f32b3b70d1b49418379db72f39b0edb
```json
{
  "evidenceId": "e-7f32b3b70d1b49418379db72f39b0edb",
  "request": {
    "factualRequest": "How many TDs represented Meath East in this Dáil on 2026-10-28?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "missing_or_unaccepted_evidence",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "no_matching_records",
    "label": "No matching records",
    "description": "No matching records were found in the available data. The data may be incomplete."
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": "no_matches",
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
          "kind": "currentTerm",
          "house": "Dail"
        },
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/34",
        "asOfEvidence": "2026-11-13"
      },
      "constituency": {
        "type": "DailConstituency",
        "mention": "Meath East",
        "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/constituency/dail/Galway-West-34",
        "label": "Meath East"
      }
    },
    "relations": [
      {
        "id": "member-membership",
        "fact": "member_has_membership",
        "from": "member",
        "to": "membership"
      },
      {
        "id": "membership-term",
        "fact": "membership_in_term",
        "from": "membership",
        "to": "term"
      },
      {
        "id": "membership-constituency",
        "fact": "membership_represents",
        "from": "membership",
        "to": "constituency"
      },
      {
        "id": "constituency-term",
        "fact": "constituency_in_term",
        "from": "constituency",
        "to": "term"
      }
    ],
    "constraints": [
      {
        "referent": "membership",
        "field": "membershipInterval",
        "operator": "on",
        "value": "2026-10-28"
      }
    ],
    "answer": {
      "kind": "count",
      "referent": "member",
      "distinctBy": "identity"
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Distinct recorded Members"
    ],
    "rows": [
      [
        "0"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:fcec8d199e8347842145951acc231d5026dfb2872872d3571cc561956dad050a",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "67e3547f2034402392e4e2fe05d7dd1b",
      "endpointId": "injected-test-client",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T13:22:20.167360+00:00",
    "finishedAt": "2026-11-13T13:22:20.257365+00:00",
    "queries": [
      {
        "queryId": "q-4c900f9a3f7841649a42ca29e67be8db",
        "sha256": "9bf0737110e856d57303dc2dc964f173bbb488510a4d5b676461f024a8d371a8",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT ?term ?start ?end WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm ; dct:temporal ?period .\n    ?period dcat:startDate ?start .\n    OPTIONAL { ?period dcat:endDate ?end . }\n  }\n} LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:20.189226+00:00",
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
            "term",
            "start",
            "end"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/34",
              "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
              "—"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:20.197019+00:00"
      },
      {
        "queryId": "q-5b4196f2974049f2817dea68fc61921e",
        "sha256": "7eea603b29e3e914b95ed02c3272d7f1666fd1146968bccf7156e3edfa014b2d",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?constituency ?label WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency ; skos:prefLabel ?label ;\n      members:constituencyInHouseTerm <https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/34> .\n  }\n}\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:20.203636+00:00",
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
              "https://data.oireachtas.ie/ie/oireachtas/constituency/dail/Galway-West-34",
              "Meath East@en"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:20.208543+00:00"
      },
      {
        "queryId": "q-a37c085ab74141caa44d8de0cd0af1f1",
        "sha256": "1ebe1b8f6e2d044c9ce2adc626b413f45c6075c5649a0c53cac104decf612e4f",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?memberName ?membership ?membershipRange ?membershipStart ?membershipEnd WHERE {\n  GRAPH ?memberGraph {\n    ?member a agents:Member .\n    OPTIONAL { ?member foaf:name ?memberName . }\n    ?membership a members:DailMembership .\n    ?member members:hasMembersMembership ?membership .\n    ?membership members:inHouseTerm ?term .\n    ?membership members:isRepresentativeFrom ?constituency .\n    OPTIONAL { ?membership members:hasMembershipDateRange ?membershipRange .\n      ?membershipRange a members:DateRange .\n      OPTIONAL { ?membershipRange members:StartDate ?membershipStart . }\n      OPTIONAL { ?membershipRange members:EndDate ?membershipEnd . } }\n  }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm .\n    VALUES ?term { <https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/34> }\n  }\n  GRAPH <https://data.oireachtas.ie/graph/constituencies> {\n    ?constituency a members:DailConstituency .\n    VALUES ?constituency { <https://data.oireachtas.ie/ie/oireachtas/constituency/dail/Galway-West-34> }\n    ?constituency members:constituencyInHouseTerm ?term .\n  }\n} ORDER BY ?memberName ?member ?membership LIMIT 100 OFFSET 0",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:20.232417+00:00",
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
            "memberName",
            "membership",
            "membershipRange",
            "membershipStart",
            "membershipEnd"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne",
              "Aoife Byrne",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne#dail-membership-33",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne#membership-date-range-0",
              "2024-11-29T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2025-12-31T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:20.256995+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "How many TDs represented Meath East in this Dáil on 2026-10-28?",
        "output": "{\"version\": 2, \"supported\": true, \"family\": \"member_relationship_composition\", \"unsupportedReason\": null, \"intent\": \"Count or list Members represented by one exact constituency occurrence in this selected D\\u00e1il.\", \"referents\": {\"member\": {\"type\": \"Member\", \"mention\": null}, \"membership\": {\"type\": \"DailMembership\", \"mention\": null}, \"term\": {\"type\": \"DailTerm\", \"mention\": null, \"selector\": {\"kind\": \"currentTerm\"}}, \"constituency\": {\"type\": \"DailConstituency\", \"mention\": \"Meath East\"}}, \"relations\": [{\"id\": \"member-membership\", \"fact\": \"member_has_membership\", \"from\": \"member\", \"to\": \"membership\"}, {\"id\": \"membership-term\", \"fact\": \"membership_in_term\", \"from\": \"membership\", \"to\": \"term\"}, {\"id\": \"membership-constituency\", \"fact\": \"membership_represents\", \"from\": \"membership\", \"to\": \"constituency\"}, {\"id\": \"constituency-term\", \"fact\": \"constituency_in_term\", \"from\": \"constituency\", \"to\": \"term\"}], \"constraints\": [{\"referent\": \"membership\", \"field\": \"membershipInterval\", \"operator\": \"on\", \"value\": \"2026-10-28\"}], \"answer\": {\"kind\": \"count\", \"referent\": \"member\", \"distinctBy\": \"identity\"}}"
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
      "No matching records were found in the available data. The data may be incomplete."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "No matching records were found in the available data. The data may be incomplete.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Members are deduplicated by exact RDF identity. Members are matched through the complete selected membership/term/constituency graph. Membership date ranges were evaluated inclusively for 2026-10-28; unknown/conflicting intervals fail closed. The recorded count is 0 distinct Member RDF identities, not seats or election events. No matching membership interval is recorded for this date; this is not proof that no Member served, because local source completeness is not certified. Results reflect local records; historical source completeness is not certified.",
  "debugOutput": null,
  "debugSource": null
}
```
