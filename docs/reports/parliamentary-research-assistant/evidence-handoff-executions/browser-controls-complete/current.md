# Committee membership

**Draft — for review** · Findings available

Original brief: Who are the current members of the Committee of Public Accounts?
Reporting date: 2026-11-13

## Recorded membership

### Members in the available records

| Member | Committee | Reporting date | Evidence |
| --- | --- | --- | --- |
| Jane | Committee of Public Accounts | 13 November 2026 | [Source records](#records-a-686057466fb0eb4751dc) |
| Patrick | Committee of Public Accounts | 13 November 2026 | [Source records](#records-a-692d81f22fa3ce531286) |

The records do not establish a complete roster, chairmanship or attendance.

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The records' last update is unknown. Separate searches may reflect different updates to the data.

## Assertion evidence and reasoning

### records-a-686057466fb0eb4751dc

Individual assertion references: a-686057466fb0eb4751dc

### records-a-692d81f22fa3ce531286

Individual assertion references: a-692d81f22fa3ce531286

### a-686057466fb0eb4751dc
```json
{
  "id": "a-686057466fb0eb4751dc",
  "text": "The available records identify Jane as a member of Committee of Public Accounts on 2026-11-13.",
  "level": 1,
  "evidenceRefs": [
    "e-d78f8d6b95334117a392e2d3e8f920ca"
  ],
  "factRefs": [],
  "reasoning": "Exact Query Service accepted proposition.",
  "assumptions": [],
  "conflicts": [],
  "limitations": [
    "These are findings from the available parliamentary records, not a certified complete account.",
    "The records' last update is unknown. Separate searches may reflect different updates to the data.",
    "Findings describe available source records, not a certified complete account.",
    "Source freshness is unknown; separate reads do not establish a common snapshot.",
    "The records do not establish a complete roster, chairmanship or attendance."
  ],
  "confidence": null,
  "confidenceRationale": null,
  "reviewStatus": "provisional",
  "proposition": {
    "predicate": "current_committee_membership",
    "text": "The available records identify Jane as a member of Committee of Public Accounts on 2026-11-13.",
    "fields": {
      "member": {
        "label": "Member",
        "text": "Jane"
      },
      "committee": {
        "label": "Committee",
        "text": "Committee of Public Accounts"
      },
      "as_of": {
        "label": "Reporting date",
        "text": "13 November 2026"
      }
    },
    "scope": {
      "meaning": "committee_membership_owner_and_house_term_contain_as_of",
      "asOf": "2026-11-13",
      "committeeOwner": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "label": "Committee of Public Accounts",
        "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "start": "2024-12-18T00:00:00",
        "end": "open-ended",
        "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "termStart": "2024-11-29",
        "termEnd": "open-ended",
        "witnesses": [
          {
            "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
            "label": "Committee of Public Accounts@en",
            "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
            "start": "2024-12-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
            "end": "—",
            "termStart": "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
            "termEnd": "—",
            "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
            "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
            "termType": "https://data.oireachtas.ie/ontology#DailTerm"
          }
        ]
      }
    },
    "witnesses": [
      {
        "memberGraph": "https://data.oireachtas.ie/graph/member/Jane",
        "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
        "name": "Jane",
        "membership": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1",
        "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "range": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range",
        "start": "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
        "end": "—"
      }
    ],
    "qualifications": [
      "Findings describe available source records, not a certified complete account.",
      "Source freshness is unknown; separate reads do not establish a common snapshot.",
      "The records do not establish a complete roster, chairmanship or attendance."
    ],
    "kind": "episode",
    "participants": {
      "member": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
        "type": "Member",
        "label": "Jane"
      },
      "committee": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "type": "Committee",
        "label": "Committee of Public Accounts"
      }
    },
    "intervals": [
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range",
        "start": "2025-05-07T00:00:00",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "committee_membership"
      },
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "start": "2024-12-18T00:00:00",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "committee_owner"
      },
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "start": "2024-11-29",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "house_term"
      }
    ]
  },
  "display": {
    "fields": {
      "member": {
        "label": "Member",
        "text": "Jane"
      },
      "committee": {
        "label": "Committee",
        "text": "Committee of Public Accounts"
      },
      "as_of": {
        "label": "Reporting date",
        "text": "13 November 2026"
      }
    }
  },
  "queryRefs": [
    "q-9b68ee9189f8414e8a5e9968105cc413",
    "q-0f12721d664847e99304e79870653c60"
  ]
}
```

### a-692d81f22fa3ce531286
```json
{
  "id": "a-692d81f22fa3ce531286",
  "text": "The available records identify Patrick as a member of Committee of Public Accounts on 2026-11-13.",
  "level": 1,
  "evidenceRefs": [
    "e-d78f8d6b95334117a392e2d3e8f920ca"
  ],
  "factRefs": [],
  "reasoning": "Exact Query Service accepted proposition.",
  "assumptions": [],
  "conflicts": [],
  "limitations": [
    "These are findings from the available parliamentary records, not a certified complete account.",
    "The records' last update is unknown. Separate searches may reflect different updates to the data.",
    "Findings describe available source records, not a certified complete account.",
    "Source freshness is unknown; separate reads do not establish a common snapshot.",
    "The records do not establish a complete roster, chairmanship or attendance."
  ],
  "confidence": null,
  "confidenceRationale": null,
  "reviewStatus": "provisional",
  "proposition": {
    "predicate": "current_committee_membership",
    "text": "The available records identify Patrick as a member of Committee of Public Accounts on 2026-11-13.",
    "fields": {
      "member": {
        "label": "Member",
        "text": "Patrick"
      },
      "committee": {
        "label": "Committee",
        "text": "Committee of Public Accounts"
      },
      "as_of": {
        "label": "Reporting date",
        "text": "13 November 2026"
      }
    },
    "scope": {
      "meaning": "committee_membership_owner_and_house_term_contain_as_of",
      "asOf": "2026-11-13",
      "committeeOwner": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "label": "Committee of Public Accounts",
        "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "start": "2024-12-18T00:00:00",
        "end": "open-ended",
        "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "termStart": "2024-11-29",
        "termEnd": "open-ended",
        "witnesses": [
          {
            "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
            "label": "Committee of Public Accounts@en",
            "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
            "start": "2024-12-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
            "end": "—",
            "termStart": "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
            "termEnd": "—",
            "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
            "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
            "termType": "https://data.oireachtas.ie/ontology#DailTerm"
          }
        ]
      }
    },
    "witnesses": [
      {
        "memberGraph": "https://data.oireachtas.ie/graph/member/Patrick",
        "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
        "name": "Patrick",
        "membership": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1",
        "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "range": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range",
        "start": "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
        "end": "—"
      }
    ],
    "qualifications": [
      "Findings describe available source records, not a certified complete account.",
      "Source freshness is unknown; separate reads do not establish a common snapshot.",
      "The records do not establish a complete roster, chairmanship or attendance."
    ],
    "kind": "episode",
    "participants": {
      "member": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
        "type": "Member",
        "label": "Patrick"
      },
      "committee": {
        "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "type": "Committee",
        "label": "Committee of Public Accounts"
      }
    },
    "intervals": [
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range",
        "start": "2025-05-07T00:00:00",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "committee_membership"
      },
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
        "start": "2024-12-18T00:00:00",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "committee_owner"
      },
      {
        "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
        "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
        "start": "2024-11-29",
        "end": null,
        "endMeaning": "open_ended",
        "meaning": "house_term"
      }
    ]
  },
  "display": {
    "fields": {
      "member": {
        "label": "Member",
        "text": "Patrick"
      },
      "committee": {
        "label": "Committee",
        "text": "Committee of Public Accounts"
      },
      "as_of": {
        "label": "Reporting date",
        "text": "13 November 2026"
      }
    }
  },
  "queryRefs": [
    "q-9b68ee9189f8414e8a5e9968105cc413",
    "q-0f12721d664847e99304e79870653c60"
  ]
}
```

## Evidence references

### e-d78f8d6b95334117a392e2d3e8f920ca
```json
{
  "evidenceId": "e-d78f8d6b95334117a392e2d3e8f920ca",
  "request": {
    "factualRequest": "Who are the current members of the Committee of Public Accounts?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "answer",
  "queryServiceOutcome": "answer",
  "compilerStatus": "success",
  "researchOutcome": {
    "kind": "findings_available",
    "label": "Findings available",
    "description": "The recorded findings and their sources are available in the report."
  },
  "factualEvidenceStatus": "available",
  "selectionOutcome": "matches",
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
          "predicate": "current_committee_membership",
          "text": "The available records identify Jane as a member of Committee of Public Accounts on 2026-11-13.",
          "fields": {
            "member": {
              "label": "Member",
              "text": "Jane"
            },
            "committee": {
              "label": "Committee",
              "text": "Committee of Public Accounts"
            },
            "as_of": {
              "label": "Reporting date",
              "text": "13 November 2026"
            }
          },
          "scope": {
            "meaning": "committee_membership_owner_and_house_term_contain_as_of",
            "asOf": "2026-11-13",
            "committeeOwner": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "label": "Committee of Public Accounts",
              "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
              "start": "2024-12-18T00:00:00",
              "end": "open-ended",
              "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
              "termStart": "2024-11-29",
              "termEnd": "open-ended",
              "witnesses": [
                {
                  "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
                  "label": "Committee of Public Accounts@en",
                  "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
                  "start": "2024-12-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
                  "end": "—",
                  "termStart": "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
                  "termEnd": "—",
                  "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
                  "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
                  "termType": "https://data.oireachtas.ie/ontology#DailTerm"
                }
              ]
            }
          },
          "witnesses": [
            {
              "memberGraph": "https://data.oireachtas.ie/graph/member/Jane",
              "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
              "name": "Jane",
              "membership": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1",
              "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "range": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range",
              "start": "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "end": "—"
            }
          ],
          "qualifications": [
            "Findings describe available source records, not a certified complete account.",
            "Source freshness is unknown; separate reads do not establish a common snapshot.",
            "The records do not establish a complete roster, chairmanship or attendance."
          ],
          "kind": "episode",
          "participants": {
            "member": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane",
              "type": "Member",
              "label": "Jane"
            },
            "committee": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "type": "Committee",
              "label": "Committee of Public Accounts"
            }
          },
          "intervals": [
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Jane#committee-membership-1#range",
              "start": "2025-05-07T00:00:00",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "committee_membership"
            },
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
              "start": "2024-12-18T00:00:00",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "committee_owner"
            },
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
              "start": "2024-11-29",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "house_term"
            }
          ]
        },
        {
          "predicate": "current_committee_membership",
          "text": "The available records identify Patrick as a member of Committee of Public Accounts on 2026-11-13.",
          "fields": {
            "member": {
              "label": "Member",
              "text": "Patrick"
            },
            "committee": {
              "label": "Committee",
              "text": "Committee of Public Accounts"
            },
            "as_of": {
              "label": "Reporting date",
              "text": "13 November 2026"
            }
          },
          "scope": {
            "meaning": "committee_membership_owner_and_house_term_contain_as_of",
            "asOf": "2026-11-13",
            "committeeOwner": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "label": "Committee of Public Accounts",
              "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
              "start": "2024-12-18T00:00:00",
              "end": "open-ended",
              "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
              "termStart": "2024-11-29",
              "termEnd": "open-ended",
              "witnesses": [
                {
                  "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
                  "label": "Committee of Public Accounts@en",
                  "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
                  "start": "2024-12-18T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
                  "end": "—",
                  "termStart": "2024-11-29^^<http://www.w3.org/2001/XMLSchema#date>",
                  "termEnd": "—",
                  "range": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
                  "period": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
                  "termType": "https://data.oireachtas.ie/ontology#DailTerm"
                }
              ]
            }
          },
          "witnesses": [
            {
              "memberGraph": "https://data.oireachtas.ie/graph/member/Patrick",
              "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
              "name": "Patrick",
              "membership": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1",
              "committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "range": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range",
              "start": "2025-05-07T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>",
              "end": "—"
            }
          ],
          "qualifications": [
            "Findings describe available source records, not a certified complete account.",
            "Source freshness is unknown; separate reads do not establish a common snapshot.",
            "The records do not establish a complete roster, chairmanship or attendance."
          ],
          "kind": "episode",
          "participants": {
            "member": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick",
              "type": "Member",
              "label": "Patrick"
            },
            "committee": {
              "iri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "type": "Committee",
              "label": "Committee of Public Accounts"
            }
          },
          "intervals": [
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Patrick#committee-membership-1#range",
              "start": "2025-05-07T00:00:00",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "committee_membership"
            },
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts#range",
              "start": "2024-12-18T00:00:00",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "committee_owner"
            },
            {
              "resourceIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
              "rangeIri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34#period",
              "start": "2024-11-29",
              "end": null,
              "endMeaning": "open_ended",
              "meaning": "house_term"
            }
          ]
        }
      ],
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
      "answerQuery": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?memberGraph ?member ?name ?membership ?committee ?range ?start ?end WHERE {\n  GRAPH ?memberGraph {\n    ?member a agents:Member ; members:hasMembersMembership ?membership .\n    OPTIONAL { ?member foaf:name ?name . }\n    ?membership a members:CommitteeMembership ; members:isCommitteeMembershipOf <https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts> ; members:isCommitteeMembershipOf ?committee .\n    OPTIONAL { ?membership members:hasMembershipDateRange ?range .\n      OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n} ORDER BY ?member ?membership ?committee ?range ?start ?end ?name ?memberGraph LIMIT 100",
      "resultDigest": "f0922633a8ab77b727a1b613aace734d7f43f606985b4c346b41a43240217044",
      "sourceCoverage": "uncertified",
      "freshness": "unknown"
    },
    "queryRefs": [
      "q-9b68ee9189f8414e8a5e9968105cc413",
      "q-0f12721d664847e99304e79870653c60"
    ]
  },
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
      "observationContextId": "8cbf85a9af45448fa93f5f54bbfcdadd",
      "endpointId": "injected-test-client",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T13:22:07.234752+00:00",
    "finishedAt": "2026-11-13T13:22:07.433710+00:00",
    "queries": [
      {
        "queryId": "q-9b68ee9189f8414e8a5e9968105cc413",
        "sha256": "89793470a3ee9bf34439b1b292214483d9f30780cc2b8b9c97eb328edb90afb8",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType WHERE {\n  GRAPH <https://data.oireachtas.ie/graph/committees> {\n    ?committee a members:Committee .\n    OPTIONAL { ?committee members:committeeInHouseTerm ?term . }\n    OPTIONAL { ?committee skos:prefLabel ?label . }\n    OPTIONAL { ?committee members:hasCommitteeDateRange ?range . ?range a members:DateRange . OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  OPTIONAL { GRAPH <https://data.oireachtas.ie/graph/houses> { ?term a ?termType . VALUES ?termType { agents:DailTerm agents:SeanadTerm } ?term dct:temporal ?period . ?period a dct:PeriodOfTime . OPTIONAL { ?period dcat:startDate ?termStart . } OPTIONAL { ?period dcat:endDate ?termEnd . } } }\n} ORDER BY ?committee ?label ?term ?start ?end ?termStart ?termEnd ?range ?period ?termType\nLIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:07.332169+00:00",
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
        "finishedAt": "2026-11-13T13:22:07.363375+00:00"
      },
      {
        "queryId": "q-0f12721d664847e99304e79870653c60",
        "sha256": "e7b09321a105e5f8bbf273874cbec1b94e14716a69d6ca611b30a016d12773d5",
        "sparql": "PREFIX agents: <https://data.oireachtas.ie/ontology#>\nPREFIX dcat: <http://www.w3.org/ns/dcat#>\nPREFIX dct: <http://purl.org/dc/terms/>\nPREFIX eli: <http://data.europa.eu/eli/ontology#>\nPREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>\nPREFIX foaf: <http://xmlns.com/foaf/0.1/>\nPREFIX members: <https://data.oireachtas.ie/ontology/members#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT DISTINCT ?memberGraph ?member ?name ?membership ?committee ?range ?start ?end WHERE {\n  GRAPH ?memberGraph {\n    ?member a agents:Member ; members:hasMembersMembership ?membership .\n    OPTIONAL { ?member foaf:name ?name . }\n    ?membership a members:CommitteeMembership ; members:isCommitteeMembershipOf <https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts> ; members:isCommitteeMembershipOf ?committee .\n    OPTIONAL { ?membership members:hasMembershipDateRange ?range .\n      OPTIONAL { ?range members:StartDate ?start . } OPTIONAL { ?range members:EndDate ?end . } }\n  }\n  FILTER(STRSTARTS(STR(?memberGraph), \"https://data.oireachtas.ie/graph/member/\"))\n} ORDER BY ?member ?membership ?committee ?range ?start ?end ?name ?memberGraph LIMIT 100",
        "stage": "read_only_query",
        "startedAt": "2026-11-13T13:22:07.406976+00:00",
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
        "finishedAt": "2026-11-13T13:22:07.430987+00:00"
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
    "enumeration": "bounded_query_completed",
    "sourceCoverage": "uncertified",
    "freshness": "unknown",
    "limitations": [
      "These are findings from the available parliamentary records, not a certified complete account.",
      "The records' last update is unknown. Separate searches may reflect different updates to the data."
    ]
  },
  "error": null,
  "diagnostic": "Locally recorded CommitteeMemberships active at 2026-11-13; not a certified complete current roster. The Committee and its HouseTerm independently contain asOf. Membership does not establish chairmanship or attendance; missing end dates remain open-ended.",
  "debugOutput": null,
  "debugSource": null
}
```
