# Committee membership

**Draft — for review** · Records found — report not completed

Original brief: Who are the current members of the Committee of Public Accounts?
Reporting date: 2026-11-13

Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist.


## Unanswered research questions

- Who are the current members of the Committee of Public Accounts?

## Assertion evidence and reasoning

## Evidence references

### e-ed934264967647a99b306f3fa5f09d6c
```json
{
  "evidenceId": "e-ed934264967647a99b306f3fa5f09d6c",
  "request": {
    "factualRequest": "Who are the current members of the Committee of Public Accounts?",
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
    "label": "Records found; not included",
    "description": "Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist."
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
    "family": "current_committee_members",
    "referents": {
      "member": {
        "type": "Member"
      },
      "membership": {
        "type": "CommitteeMembership"
      },
      "committee": {
        "type": "Committee",
        "mention": "Committee of Public Accounts"
      }
    },
    "relations": [
      {
        "id": "member_has_committee_membership",
        "fact": "member_has_committee_membership",
        "from": "member",
        "to": "membership"
      },
      {
        "id": "committee_membership_of_committee",
        "fact": "committee_membership_of_committee",
        "from": "membership",
        "to": "committee"
      }
    ],
    "constraints": [
      {
        "referent": "committee",
        "field": "interval",
        "operator": "currentAt",
        "value": "2026-11-13"
      },
      {
        "referent": "membership",
        "field": "interval",
        "operator": "currentAt",
        "value": "2026-11-13"
      }
    ],
    "answer": {
      "kind": "entities",
      "referent": "member",
      "distinctBy": "identity",
      "display": [
        "name"
      ],
      "preserveEvidence": true
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Member",
      "Member identity",
      "Committee",
      "Committee identity",
      "Membership evidence",
      "Committee date range",
      "Committee start",
      "Committee end",
      "HouseTerm identity",
      "HouseTerm period",
      "HouseTerm start",
      "HouseTerm end",
      "As of"
    ],
    "rows": [
      [
        "Jane",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
        "Committee of Public Accounts",
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1 | https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range | 2025-05-07T00:00:00 – open-ended | source graph: https://data.oireachtas.ie/graph/member/Jane",
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "2024-12-18T00:00:00",
        "open-ended",
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "2024-11-29",
        "open-ended",
        "2026-11-13"
      ],
      [
        "Patrick",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
        "Committee of Public Accounts",
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1 | https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range | 2025-05-07T00:00:00 – open-ended | source graph: https://data.oireachtas.ie/graph/member/Patrick",
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "2024-12-18T00:00:00",
        "open-ended",
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "2024-11-29",
        "open-ended",
        "2026-11-13"
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
      "observationContextId": "b19f2142c30147ad9f1a59015f28884a",
      "endpointId": "injected-test-client",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T13:22:14.330340+00:00",
    "finishedAt": "2026-11-13T13:22:14.519307+00:00",
    "queries": [
      {
        "queryId": "q-1a9eab0b7f154adb82b48a5157f54ac0",
        "sha256": "89793470a3ee9bf34439b1b292214483d9f30780cc2b8b9c97eb328edb90afb8",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/committees> {\n    ?committee a members:Committee .\n    OPTIONAL { ?committee members:committeeInHouseTerm ?term . }\n    OPTIONAL { ?committee skos:prefLabel ?label . }\n    OPTIONAL { ?committee members:hasCommitteeDateRange ?range . ?range a members:DateRange . OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . VALUES ?termType { agents:DailTerm agents:SeanadTerm } ?term dct:temporal ?period . ?period a dct:PeriodOfTime . OPTIONAL { ?period dcat:startDate ?termStart . } OPTIONAL { ?period dcat:endDate ?termEnd . } } }\n} ORDER BY ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:14.394926+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/committees",
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "returned",
        "result": {
          "kind": "select",
          "columns": [
            "committee",
            "label",
            "term",
            "start",
            "end",
            "termStart",
            "termEnd",
            "range",
            "period",
            "termType"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "Committee of Public Accounts@en",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "2024-12-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "—",
              "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
              "—",
              "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
              "https://data.oireachtas.ie/ontology#DailTerm"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:14.431217+00:00"
      },
      {
        "queryId": "q-6889ac9c37a34585baa76ab879311cea",
        "sha256": "e7b09321a105e5f8bbf273874cbec1b94e14716a69d6ca611b30a016d12773d5",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?memberGraph ?member ?name ?membership ?committee ?range ?start ?end WHERE {\n  GRAPH ?memberGraph {\n    ?member a agents:Member ; members:hasMembersMembership ?membership .\n    OPTIONAL { ?member foaf:name ?name . }\n    ?membership a members:CommitteeMembership ; members:isCommitteeMembershipOf <https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts> ; members:isCommitteeMembershipOf ?committee .\n    OPTIONAL { ?membership members:hasMembershipDateRange ?range .\n      OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n} ORDER BY ?member ?membership ?committee ?range ?start ?end ?name ?memberGraph LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:14.487246+00:00",
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
            "memberGraph",
            "member",
            "name",
            "membership",
            "committee",
            "range",
            "start",
            "end"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/graph/member/Jane",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
              "Jane",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1",
              "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range",
              "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "—"
            ],
            [
              "https://data.oireachtas.ie/graph/member/Patrick",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
              "Patrick",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1",
              "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range",
              "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "—"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:14.518657+00:00"
      }
    ],
    "plannerProposals": [
      {
        "prompt": "Who are the current members of the Committee of Public Accounts?",
        "output": "{\"version\": 2, \"supported\": true, \"family\": \"capability_selection\", \"unsupportedReason\": null, \"intent\": \"List current named committee members\", \"referents\": {\"capability\": \"current_committee_members\", \"parameters\": {\"committee\": \"Committee of Public Accounts\"}}, \"relations\": [], \"constraints\": [], \"answer\": null}"
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
      "Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist."
    ]
  },
  "error": {
    "code": "research_evidence_unavailable",
    "message": "Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist.",
    "technicalMessage": "The Query Service's evidence shape is not supported by its structured factual boundary. The response is retained for inspection; no research fact was promoted.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Locally recorded CommitteeMemberships active at 2026-11-13; not a certified complete current roster. The Committee and its HouseTerm independently contain asOf. Membership does not establish chairmanship or attendance; missing end dates remain open-ended.",
  "debugOutput": null,
  "debugSource": null
}
```
