# Committee membership

**Draft — for review** · Research interrupted

Original brief: Who are the current members of the Committee of Public Accounts?
Reporting date: 2026-11-13

The search couldn't be completed. No findings were established by this search.


## Unanswered research questions

- Who are the current members of the Committee of Public Accounts?

## Assertion evidence and reasoning

## Evidence references

### e-550bf497baf84bbcb5f7da6c967d9a7d
```json
{
  "evidenceId": "e-550bf497baf84bbcb5f7da6c967d9a7d",
  "request": {
    "factualRequest": "Who are the current members of the Committee of Public Accounts?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "execution_failure",
  "queryServiceOutcome": "execution_failure",
  "compilerStatus": "execution_failure",
  "researchOutcome": {
    "kind": "execution_failure",
    "label": "Search interrupted",
    "description": "The search couldn't be completed. No findings were established by this search."
  },
  "factualEvidenceStatus": "unavailable",
  "selectionOutcome": null,
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:fcec8d199e8347842145951acc231d5026dfb2872872d3571cc561956dad050a",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "c5097b0896b14906a83c28ea34062203",
      "endpointId": "injected-test-client",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T13:22:18.579926+00:00",
    "finishedAt": "2026-11-13T13:22:18.644371+00:00",
    "queries": [
      {
        "queryId": "q-61722bd5f33642338524053ce0569aac",
        "sha256": "89793470a3ee9bf34439b1b292214483d9f30780cc2b8b9c97eb328edb90afb8",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/committees> {\n    ?committee a members:Committee .\n    OPTIONAL { ?committee members:committeeInHouseTerm ?term . }\n    OPTIONAL { ?committee skos:prefLabel ?label . }\n    OPTIONAL { ?committee members:hasCommitteeDateRange ?range . ?range a members:DateRange . OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . VALUES ?termType { agents:DailTerm agents:SeanadTerm } ?term dct:temporal ?period . ?period a dct:PeriodOfTime . OPTIONAL { ?period dcat:startDate ?termStart . } OPTIONAL { ?period dcat:endDate ?termEnd . } } }\n} ORDER BY ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:18.644127+00:00",
        "offset": 0,
        "graphScope": {
          "fixedGraphs": [
            "https://data.oireachtas.ie/graph/committees",
            "https://data.oireachtas.ie/graph/houses"
          ],
          "variableGraphs": []
        },
        "outcome": "execution_failure",
        "result": null,
        "technicalDiagnostic": "RuntimeError: Injected browser transport diagnostic 457",
        "debugOutput": "",
        "error": "The read-only query failed.",
        "finishedAt": "2026-11-13T13:22:18.644272+00:00"
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
      "The search couldn't be completed. No findings were established by this search."
    ]
  },
  "error": {
    "code": "execution_failure",
    "message": "The search couldn't be completed. No findings were established by this search.",
    "technicalMessage": "The local read-only query failed: The configured read-only query failed.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "The local read-only query failed: The configured read-only query failed.",
  "debugOutput": "{\n  \"failed_read_only_query\": \"PREFIX agents: <https://data.oireachtas.ie/ontology#>\\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\\nPREFIX dct: <http://purl.org/dc/terms/>\\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\\nSELECT DISTINCT ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType WHERE {\\n  GRAPH <https://data.oireachtas.ie/graph/committees> {\\n    ?committee a members:Committee .\\n    OPTIONAL { ?committee members:committeeInHouseTerm ?term . }\\n    OPTIONAL { ?committee skos:prefLabel ?label . }\\n    OPTIONAL { ?committee members:hasCommitteeDateRange ?range . ?range a members:DateRange . OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\\n  }\\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . VALUES ?termType { agents:DailTerm agents:SeanadTerm } ?term dct:temporal ?period . ?period a dct:PeriodOfTime . OPTIONAL { ?period dcat:startDate ?termStart . } OPTIONAL { ?period dcat:endDate ?termEnd . } } }\\n} ORDER BY ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType\\nLIMIT 100\",\n  \"endpoint_debug\": null\n}",
  "debugSource": "Fuseki"
}
```
