# Stephen Donnelly’s party membership

**Draft — for review** · Incomplete / qualified research

Original brief: What parties was Stephen Donnelly a member of, and when?
Reporting date: 2026-11-13

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The source's last update and completeness are not established. Retrieval time is not source freshness.
- This limitation is known from the research interface and will qualify any findings.

## Unanswered research questions

- What political parties was Stephen Donnelly recorded as a member of, and what start and end dates are recorded for each membership episode?

## Assertion evidence and reasoning

## Evidence references

### e-dcfb6fff10c34e7eb091f7f868e18363
```json
{
  "evidenceId": "e-dcfb6fff10c34e7eb091f7f868e18363",
  "request": {
    "factualRequest": "Which political parties do local parliamentary records show Stephen Donnelly as having been a member of, and what start and end dates are recorded for each party-membership episode?",
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
    "compilerRevision": "sha256:8cb517e06498b0c03613df119815c546d28a6f9039b60b085f5aa81b16ab3549",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:44:25.005075+00:00",
    "finishedAt": "2026-11-13T08:44:28.981666+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Which political parties do local parliamentary records show Stephen Donnelly as having been a member of, and what start and end dates are recorded for each party-membership episode?",
        "output": "{\n  \"version\": 2,\n  \"supported\": true,\n  \"family\": \"member_party_history\",\n  \"unsupportedReason\": null,\n  \"intent\": \"List the political parties recorded for Stephen Donnelly and show the recorded start and end dates for each party-membership episode.\",\n  \"referents\": {\n    \"member\": {\n      \"type\": \"Member\",\n      \"mention\": \"Stephen Donnelly\"\n    },\n    \"episode\": {\n      \"type\": \"PartyMembershipEpisode\",\n      \"mention\": null\n    },\n    \"party\": {\n      \"type\": \"ParliamentaryParty\",\n      \"mention\": null\n    },\n    \"affiliation\": {\n      \"type\": \"PoliticalAffiliationIdentity\",\n      \"mention\": null\n    }\n  },\n  \"relations\": [\n    {\n      \"id\": \"member_party_membership\",\n      \"fact\": \"member_party_membership\",\n      \"from\": \"member\",\n      \"to\": \"episode\"\n    },\n    {\n      \"id\": \"episode_in_parliamentary_party\",\n      \"fact\": \"episode_in_parliamentary_party\",\n      \"from\": \"episode\",\n      \"to\": \"party\"\n    },\n    {\n      \"id\": \"parliamentary_party_has_affiliation_identity\",\n      \"fact\": \"parliamentary_party_has_affiliation_identity\",\n      \"from\": \"party\",\n      \"to\": \"affiliation\"\n    }\n  ],\n  \"constraints\": [],\n  \"answer\": {\n    \"kind\": \"entities\",\n    \"referent\": \"affiliation\",\n    \"distinctBy\": \"identity\",\n    \"display\": [\n      \"label\"\n    ],\n    \"details\": [],\n    \"preserveEvidence\": true\n  }\n}"
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

### e-e84bd1491d5a4740a2076e6f96f72b73
```json
{
  "evidenceId": "e-e84bd1491d5a4740a2076e6f96f72b73",
  "request": {
    "factualRequest": "Which recorded historical party-membership episodes link Stephen Donnelly to a political party, and what start and end dates are recorded for each episode?",
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
    "compilerRevision": "sha256:8cb517e06498b0c03613df119815c546d28a6f9039b60b085f5aa81b16ab3549",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:44:36.537581+00:00",
    "finishedAt": "2026-11-13T08:44:41.268342+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Which recorded historical party-membership episodes link Stephen Donnelly to a political party, and what start and end dates are recorded for each episode?",
        "output": "{\"version\":2,\"supported\":false,\"family\":null,\"unsupportedReason\":\"The available party-history capability returns party affiliation identities, not dated party-membership episodes with their start and end dates.\",\"intent\":\"Find Stephen Donnelly’s historical party-membership episodes and their recorded start and end dates.\",\"referents\":null,\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "The available party-history capability returns party affiliation identities, not dated party-membership episodes with their start and end dates."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "The available party-history capability returns party affiliation identities, not dated party-membership episodes with their start and end dates.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "The available party-history capability returns party affiliation identities, not dated party-membership episodes with their start and end dates."
}
```

### e-658771d402ec4dbfbbbe8968168bb3aa
```json
{
  "evidenceId": "e-658771d402ec4dbfbbbe8968168bb3aa",
  "request": {
    "factualRequest": "Which political party identities are linked to Stephen Donnelly through recorded party-membership episodes in local parliamentary records?",
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
    "compilerRevision": "sha256:8cb517e06498b0c03613df119815c546d28a6f9039b60b085f5aa81b16ab3549",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:44:47.823000+00:00",
    "finishedAt": "2026-11-13T08:44:51.031113+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Which political party identities are linked to Stephen Donnelly through recorded party-membership episodes in local parliamentary records?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_party_history\",\"unsupportedReason\":null,\"intent\":\"Find the political party identities linked to Stephen Donnelly through recorded party-membership episodes.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":\"Stephen Donnelly\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"r1\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"r2\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"r3\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[],\"preserveEvidence\":true}}"
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

### e-fac82bb2c313407d94e373c7ef4b70d0
```json
{
  "evidenceId": "e-fac82bb2c313407d94e373c7ef4b70d0",
  "request": {
    "factualRequest": "Which political-party identities are linked to Stephen Donnelly through recorded party-membership episodes in local parliamentary records?",
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
    "compilerRevision": "sha256:8cb517e06498b0c03613df119815c546d28a6f9039b60b085f5aa81b16ab3549",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T08:44:57.493115+00:00",
    "finishedAt": "2026-11-13T08:45:00.531666+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Which political-party identities are linked to Stephen Donnelly through recorded party-membership episodes in local parliamentary records?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"member_party_history\",\"unsupportedReason\":null,\"intent\":\"Find political-party identities linked to Stephen Donnelly through recorded party-membership episodes.\",\"referents\":{\"member\":{\"type\":\"Member\",\"mention\":\"Stephen Donnelly\"},\"episode\":{\"type\":\"PartyMembershipEpisode\",\"mention\":null},\"party\":{\"type\":\"ParliamentaryParty\",\"mention\":null},\"affiliation\":{\"type\":\"PoliticalAffiliationIdentity\",\"mention\":null}},\"relations\":[{\"id\":\"r1\",\"fact\":\"member_party_membership\",\"from\":\"member\",\"to\":\"episode\"},{\"id\":\"r2\",\"fact\":\"episode_in_parliamentary_party\",\"from\":\"episode\",\"to\":\"party\"},{\"id\":\"r3\",\"fact\":\"parliamentary_party_has_affiliation_identity\",\"from\":\"party\",\"to\":\"affiliation\"}],\"constraints\":[],\"answer\":{\"kind\":\"entities\",\"referent\":\"affiliation\",\"distinctBy\":\"identity\",\"display\":[\"label\"],\"details\":[],\"preserveEvidence\":true}}"
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
