# Committee membership

**Draft — for review** · Needs clarification

Original brief: What parties was Stephen Donnelly a member of?
Reporting date: 2026-11-13

Please clarify the person, organisation or period intended before this question can be answered.


## Unanswered research questions

- What parties was Stephen Donnelly a member of?

## Assertion evidence and reasoning

## Evidence references

### e-7cb50f494df74a4783b879d9a1d15b47
```json
{
  "evidenceId": "e-7cb50f494df74a4783b879d9a1d15b47",
  "request": {
    "factualRequest": "What parties was Stephen Donnelly a member of?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "clarification_required",
  "queryServiceOutcome": "clarification_required",
  "compilerStatus": "ambiguous",
  "researchOutcome": {
    "kind": "clarification_required",
    "label": "Clarification needed",
    "description": "Please clarify the person, organisation or period intended before this question can be answered."
  },
  "factualEvidenceStatus": "not_applicable",
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
    "referents": {
      "member": {
        "type": "Member",
        "mention": "Stephen Donnelly",
        "resolution": "ambiguous",
        "candidates": [
          {
            "iri": "https://data.oireachtas.ie/member/id/second-stephen-donnelly",
            "label": "Stephen Donnelly"
          },
          {
            "iri": "https://data.oireachtas.ie/member/id/synthetic-stephen-donnelly",
            "label": "Stephen Donnelly"
          }
        ]
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
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:fcec8d199e8347842145951acc231d5026dfb2872872d3571cc561956dad050a",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "df5503f5ad4e4a4fbc71cc92290969df",
      "endpointId": "injected-test-client",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T13:22:21.798234+00:00",
    "finishedAt": "2026-11-13T13:22:21.875061+00:00",
    "queries": [
      {
        "queryId": "q-388abdad940745c8bfe6348debd731a5",
        "sha256": "9110db10ccfdf622774ea7f5b82d140bf245957faaa63e027ef73f4b493f959c",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?member ?name ?sourceId WHERE {\n  GRAPH ?memberGraph { ?member a agents:Member ; foaf:name ?name . OPTIONAL { ?member agents:pId ?sourceId . } }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n  FILTER(CONTAINS(LCASE(STR(?name)), LCASE(STR(\"Stephen Donnelly\"))) ||\n         LCASE(STR(?sourceId)) = LCASE(STR(\"StephenDonnelly\")))\n} ORDER BY ?member ?name LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:21.826642+00:00",
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
              "https://data.oireachtas.ie/member/id/second-stephen-donnelly",
              "Stephen Donnelly",
              "—"
            ],
            [
              "https://data.oireachtas.ie/member/id/synthetic-stephen-donnelly",
              "Stephen Donnelly",
              "—"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T13:22:21.874801+00:00"
      }
    ],
    "plannerProposals": []
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
      "Please clarify the person, organisation or period intended before this question can be answered."
    ]
  },
  "error": {
    "code": "ambiguous",
    "message": "Please clarify the person, organisation or period intended before this question can be answered.",
    "technicalMessage": "Several local Member records match “Stephen Donnelly”; none was selected.",
    "candidates": [
      {
        "iri": "https://data.oireachtas.ie/member/id/second-stephen-donnelly",
        "label": "Stephen Donnelly"
      },
      {
        "iri": "https://data.oireachtas.ie/member/id/synthetic-stephen-donnelly",
        "label": "Stephen Donnelly"
      }
    ],
    "clarification": null
  },
  "diagnostic": "Several local Member records match “Stephen Donnelly”; none was selected.",
  "debugOutput": null,
  "debugSource": null
}
```
