# Which Dáil was in office during June 1994?

**Draft — for review** · Incomplete / qualified research

Original brief: Which Dáil was in office during June 1994?
Reporting date: 2026-11-13

## Dáil term covering June 1994

The House-owned records identify 27th Dáil as overlapping June 1994 (1994-06-01 through 1994-06-30). [a-09caaac93c909945a39d]
_Directly supported recorded fact_

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The source's last update and completeness are not established. Retrieval time is not source freshness.
- The requested term identification does not establish sitting dates; no separate sitting investigation is proposed.

## Unanswered research questions


## Assertion evidence and reasoning

### a-09caaac93c909945a39d
```json
{
  "id": "a-09caaac93c909945a39d",
  "text": "The House-owned records identify 27th Dáil as overlapping June 1994 (1994-06-01 through 1994-06-30).",
  "level": 1,
  "evidenceRefs": [
    "e-ca72b50aa16b4dea97e9a84ed88b776f"
  ],
  "factRefs": [],
  "reasoning": "Exact Query Service accepted proposition.",
  "assumptions": [],
  "conflicts": [],
  "limitations": [
    "These are findings from the available parliamentary records, not a certified complete account.",
    "The source's last update and completeness are not established. Retrieval time is not source freshness.",
    "Findings describe available source records, not a certified complete account.",
    "Source freshness is unknown; separate reads do not establish a common snapshot.",
    "A term-date match does not establish that a parliamentary sitting occurred."
  ],
  "confidence": null,
  "confidenceRationale": null,
  "reviewStatus": "provisional",
  "proposition": {
    "predicate": "house_term_calendar_selection",
    "text": "The House-owned records identify 27th Dáil as overlapping June 1994 (1994-06-01 through 1994-06-30).",
    "fields": {
      "term": {
        "label": "Dáil term",
        "text": "27th Dáil"
      },
      "start": {
        "label": "House start",
        "text": "1992-12-14"
      },
      "end": {
        "label": "House end",
        "text": "1997-05-15"
      }
    },
    "scope": {
      "meaning": "house_date_overlap_not_actual_sitting",
      "selector": {
        "kind": "duringMonth",
        "year": 1994,
        "month": 6
      },
      "start": "1992-12-14",
      "end": "1997-05-15"
    },
    "witnesses": [
      {
        "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
        "label": "27th Dáil@en",
        "number": "27^^<http://www.w3.org/2001/XMLSchema#integer>",
        "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27#term-period",
        "periodType": "http://purl.org/dc/terms/PeriodOfTime",
        "start": "1992-12-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
        "end": "1997-05-15T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
      }
    ],
    "qualifications": [
      "Findings describe available source records, not a certified complete account.",
      "Source freshness is unknown; separate reads do not establish a common snapshot.",
      "A term-date match does not establish that a parliamentary sitting occurred."
    ],
    "kind": "entity",
    "entity": {
      "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
      "type": "DailTerm",
      "label": "27th Dáil"
    }
  },
  "display": {
    "fields": {
      "term": {
        "label": "Dáil term",
        "text": "27th Dáil"
      },
      "start": {
        "label": "House start",
        "text": "1992-12-14"
      },
      "end": {
        "label": "House end",
        "text": "1997-05-15"
      }
    }
  },
  "queryRefs": [
    "q-4f456b580f8a48bba09266418c8436dc"
  ]
}
```

## Evidence references

### e-ca72b50aa16b4dea97e9a84ed88b776f
```json
{
  "evidenceId": "e-ca72b50aa16b4dea97e9a84ed88b776f",
  "request": {
    "factualRequest": "Which Dáil was in office during June 1994?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "answer",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "validation": {
    "planValidated": true,
    "executionCompleted": true,
    "accepted": true
  },
  "data": {
    "evidence": {
      "version": 1,
      "facts": [
        {
          "predicate": "house_term_calendar_selection",
          "text": "The House-owned records identify 27th Dáil as overlapping June 1994 (1994-06-01 through 1994-06-30).",
          "fields": {
            "term": {
              "label": "Dáil term",
              "text": "27th Dáil"
            },
            "start": {
              "label": "House start",
              "text": "1992-12-14"
            },
            "end": {
              "label": "House end",
              "text": "1997-05-15"
            }
          },
          "scope": {
            "meaning": "house_date_overlap_not_actual_sitting",
            "selector": {
              "kind": "duringMonth",
              "year": 1994,
              "month": 6
            },
            "start": "1992-12-14",
            "end": "1997-05-15"
          },
          "witnesses": [
            {
              "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
              "label": "27th Dáil@en",
              "number": "27^^<http://www.w3.org/2001/XMLSchema#integer>",
              "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27#term-period",
              "periodType": "http://purl.org/dc/terms/PeriodOfTime",
              "start": "1992-12-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "end": "1997-05-15T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            }
          ],
          "qualifications": [
            "Findings describe available source records, not a certified complete account.",
            "Source freshness is unknown; separate reads do not establish a common snapshot.",
            "A term-date match does not establish that a parliamentary sitting occurred."
          ],
          "kind": "entity",
          "entity": {
            "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
            "type": "DailTerm",
            "label": "27th Dáil"
          }
        }
      ],
      "plan": {
        "version": 2,
        "asOf": "2026-11-13",
        "family": "house_terms",
        "referents": {
          "term": {
            "type": "DailTerm",
            "answer": true,
            "selector": {
              "kind": "duringMonth",
              "year": 1994,
              "month": 6
            },
            "resolution": "resolved",
            "matches": [
              {
                "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
                "label": "27th Dáil",
                "start": "1992-12-14",
                "end": "1997-05-15"
              }
            ]
          }
        },
        "relations": [],
        "answer": {
          "kind": "values",
          "referent": "term"
        }
      },
      "answerQuery": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term ?label ?number ?period ?periodType ?start ?end WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm .\n    OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = \"en\") }\n    OPTIONAL { ?term agents:termNo ?number . }\n    OPTIONAL {\n      ?term dct:temporal ?period .\n      OPTIONAL { ?period a ?periodType . }\n      OPTIONAL { ?period dcat:startDate ?start . }\n      OPTIONAL { ?period dcat:endDate ?end . }\n    }\n  }\n} ORDER BY ?term ?period ?start ?end LIMIT 100",
      "resultDigest": "e740431460c5de81651012bb279db1bcdc58137670c82ff9e03043a9ea67f768",
      "sourceCoverage": "uncertified",
      "freshness": "unknown"
    },
    "queryRefs": [
      "q-4f456b580f8a48bba09266418c8436dc"
    ]
  },
  "plan": {
    "version": 2,
    "asOf": "2026-11-13",
    "family": "house_terms",
    "referents": {
      "term": {
        "type": "DailTerm",
        "answer": true,
        "selector": {
          "kind": "duringMonth",
          "year": 1994,
          "month": 6
        },
        "resolution": "resolved",
        "matches": [
          {
            "iri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
            "label": "27th Dáil",
            "start": "1992-12-14",
            "end": "1997-05-15"
          }
        ]
      }
    },
    "relations": [],
    "answer": {
      "kind": "values",
      "referent": "term"
    }
  },
  "queryServiceResult": {
    "kind": "select",
    "columns": [
      "Dáil term",
      "House start",
      "House end",
      "Term identity"
    ],
    "rows": [
      [
        "27th Dáil",
        "1992-12-14",
        "1997-05-15",
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/27"
      ]
    ],
    "boolean": null
  },
  "execution": {
    "compilerRevision": "sha256:10105b6018bc62e193d05a411b200e1120d834dcd2fe247817dfa9d67ec8b2d2",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T10:18:50.195378+00:00",
    "finishedAt": "2026-11-13T10:18:50.243928+00:00",
    "queries": [
      {
        "queryId": "q-4f456b580f8a48bba09266418c8436dc",
        "sha256": "0c001083f897b03182fa8bc92cb3d43b7ff06befd37d0df8e0067436df33dde8",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?term ?label ?number ?period ?periodType ?start ?end WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/houses> {\n    ?term a agents:DailTerm .\n    OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = \"en\") }\n    OPTIONAL { ?term agents:termNo ?number . }\n    OPTIONAL {\n      ?term dct:temporal ?period .\n      OPTIONAL { ?period a ?periodType . }\n      OPTIONAL { ?period dcat:startDate ?start . }\n      OPTIONAL { ?period dcat:endDate ?end . }\n    }\n  }\n} ORDER BY ?term ?period ?start ?end LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T10:18:50.212533+00:00",
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
            "label",
            "number",
            "period",
            "periodType",
            "start",
            "end"
          ],
          "rows": [
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/1",
              "1st Dáil@en",
              "1^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/1#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1919-01-21T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1921-05-10T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/10",
              "10th Dáil@en",
              "10^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/10#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1938-06-30T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1943-05-31T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/11",
              "11th Dáil@en",
              "11^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/11#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1943-07-01T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1944-05-10T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/12",
              "12th Dáil@en",
              "12^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/12#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1944-06-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1948-01-12T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/13",
              "13th Dáil@en",
              "13^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/13#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1948-02-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1951-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/14",
              "14th Dáil@en",
              "14^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/14#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1951-06-13T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1954-04-24T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/15",
              "15th Dáil@en",
              "15^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/15#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1954-06-02T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1957-02-12T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/16",
              "16th Dáil@en",
              "16^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/16#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1957-03-20T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1961-09-15T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/17",
              "17th Dáil@en",
              "17^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/17#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1961-10-11T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1965-03-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/18",
              "18th Dáil@en",
              "18^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/18#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1965-04-21T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1969-05-22T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/19",
              "19th Dáil@en",
              "19^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/19#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1969-07-02T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1973-02-05T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/2",
              "2nd Dáil@en",
              "2^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/2#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1921-08-16T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1922-06-16T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/20",
              "20th Dáil@en",
              "20^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/20#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1973-03-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1977-05-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/21",
              "21st Dáil@en",
              "21^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/21#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1977-07-05T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1981-05-21T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/22",
              "22nd Dáil@en",
              "22^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/22#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1981-06-30T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1982-02-27T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/23",
              "23rd Dáil@en",
              "23^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/23#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1982-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1982-11-04T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/24",
              "24th Dáil@en",
              "24^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/24#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1982-12-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1987-01-21T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/25",
              "25th Dáil@en",
              "25^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/25#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1987-03-10T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1989-05-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/26",
              "26th Dáil@en",
              "26^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/26#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1989-06-29T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1992-11-05T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/27",
              "27th Dáil@en",
              "27^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/27#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1992-12-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1997-05-15T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/28",
              "28th Dáil@en",
              "28^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/28#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1997-06-26T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2002-04-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/29",
              "29th Dáil@en",
              "29^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/29#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2002-06-06T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2007-04-30T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/3",
              "3rd Dáil@en",
              "3^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/3#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1922-09-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1923-08-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/30",
              "30th Dáil@en",
              "30^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/30#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2007-06-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2011-02-01T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31",
              "31st Dáil@en",
              "31^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/31#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2011-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2016-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/32",
              "32nd Dáil@en",
              "32^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/32#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2016-03-10T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2020-01-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/33",
              "33rd Dáil@en",
              "33^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/33#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2020-02-08T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "2024-11-08T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "34th Dáil@en",
              "34^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "2024-11-29T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "—"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/4",
              "4th Dáil@en",
              "4^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/4#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1923-09-19T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1927-05-23T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/5",
              "5th Dáil@en",
              "5^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/5#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1927-06-23T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1927-08-25T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/6",
              "6th Dáil@en",
              "6^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/6#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1927-10-11T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1932-01-29T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/7",
              "7th Dáil@en",
              "7^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/7#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1932-03-09T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1933-01-02T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/8",
              "8th Dáil@en",
              "8^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/8#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1933-02-08T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1937-06-14T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ],
            [
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/9",
              "9th Dáil@en",
              "9^^<http://www.w3.org/2001/XMLSchema#integer>",
              "https://data.oireachtas.ie/ie/oireachtas/house/dail/9#term-period",
              "http://purl.org/dc/terms/PeriodOfTime",
              "1937-07-21T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "1938-05-27T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>"
            ]
          ],
          "boolean": null
        },
        "finishedAt": "2026-11-13T10:18:50.222575+00:00"
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
    "enumeration": "bounded_query_completed",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The source's last update and completeness are not established. Retrieval time is not source freshness."
    ]
  },
  "error": null,
  "diagnostic": "Selected exact DailTerm identities whose House-owned date intervals overlap June 1994 (1994-06-01 through 1994-06-30). A term-date match does not establish that a parliamentary sitting occurred."
}
```
