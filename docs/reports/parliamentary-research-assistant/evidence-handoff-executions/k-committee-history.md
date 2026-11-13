# Committee of Public Accounts membership history

**Draft — for review** · Incomplete / qualified research

Original brief: What is the membership history of the Committee of Public Accounts?
Reporting date: 2026-11-13

I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.

## Evidence limitations

- These are findings from the available parliamentary records, not a certified complete account.
- The source's last update and completeness are not established. Retrieval time is not source freshness.
- Historical coverage and its limits have not yet been established.
- I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.

## Unanswered research questions

- What is the membership history of the Committee of Public Accounts?

## Assertion evidence and reasoning

## Evidence references

### e-3c8b3488e12c4922ab03302071db5563
```json
{
  "evidenceId": "e-3c8b3488e12c4922ab03302071db5563",
  "request": {
    "factualRequest": "What is the membership history of the Committee of Public Accounts?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "unsupported_capability",
  "queryServiceOutcome": "unsupported_capability",
  "compilerStatus": "unsupported_request",
  "researchOutcome": {
    "kind": "unsupported_question",
    "label": "Question not answered",
    "description": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
  },
  "factualEvidenceStatus": "not_applicable",
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:6eb055652fea40247fe7862126891f89e447f48df0caeaf7b620c42681d00d87",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T12:57:48.280040+00:00",
    "finishedAt": "2026-11-13T12:57:50.796966+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "What is the membership history of the Committee of Public Accounts?",
        "output": "{\"version\":2,\"supported\":false,\"family\":null,\"unsupportedReason\":\"Historical committee membership is not supported; the committee capability covers current members only.\",\"intent\":\"Find the membership history of the Committee of Public Accounts.\",\"referents\":null,\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.",
    "technicalMessage": "Historical committee membership is not supported; the committee capability covers current members only.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Historical committee membership is not supported; the committee capability covers current members only.",
  "debugOutput": null,
  "debugSource": null
}
```

### e-285279ba23174341806edb2b80b144d7
```json
{
  "evidenceId": "e-285279ba23174341806edb2b80b144d7",
  "request": {
    "factualRequest": "Which members are recorded as serving on the current Committee of Public Accounts?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "unsupported_capability",
  "queryServiceOutcome": "unsupported_capability",
  "compilerStatus": "unsupported_request",
  "researchOutcome": {
    "kind": "unsupported_question",
    "label": "Question not answered",
    "description": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
  },
  "factualEvidenceStatus": "not_applicable",
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:6eb055652fea40247fe7862126891f89e447f48df0caeaf7b620c42681d00d87",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T12:57:57.906175+00:00",
    "finishedAt": "2026-11-13T12:58:00.379532+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Which members are recorded as serving on the current Committee of Public Accounts?",
        "output": "{\"version\":2,\"supported\":true,\"family\":\"capability_selection\",\"unsupportedReason\":null,\"intent\":\"List locally recorded members of the current Committee of Public Accounts.\",\"referents\":{\"capability\":\"current_committee_members\",\"parameters\":{\"committee\":\"Committee of Public Accounts\"}},\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.",
    "technicalMessage": "Current committee Member listing cannot discard historical dates, extra conditions or other answer fields.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Current committee Member listing cannot discard historical dates, extra conditions or other answer fields.",
  "debugOutput": "{\n  \"draft\": \"{\\\"version\\\":2,\\\"supported\\\":true,\\\"family\\\":\\\"capability_selection\\\",\\\"unsupportedReason\\\":null,\\\"intent\\\":\\\"List locally recorded members of the current Committee of Public Accounts.\\\",\\\"referents\\\":{\\\"capability\\\":\\\"current_committee_members\\\",\\\"parameters\\\":{\\\"committee\\\":\\\"Committee of Public Accounts\\\"}},\\\"relations\\\":[],\\\"constraints\\\":[],\\\"answer\\\":null}\",\n  \"diagnostic\": \"Current committee Member listing cannot discard historical dates, extra conditions or other answer fields.\"\n}",
  "debugSource": "Composable semantic planner"
}
```

### e-8c0f36aeffb449818a50ea6c7e30cc87
```json
{
  "evidenceId": "e-8c0f36aeffb449818a50ea6c7e30cc87",
  "request": {
    "factualRequest": "Are there recorded membership periods for the Committee of Public Accounts in earlier parliamentary terms?",
    "requirementId": "r0",
    "operation": {
      "operation": "query"
    }
  },
  "outcome": "unsupported_capability",
  "queryServiceOutcome": "unsupported_capability",
  "compilerStatus": "unsupported_request",
  "researchOutcome": {
    "kind": "unsupported_question",
    "label": "Question not answered",
    "description": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
  },
  "factualEvidenceStatus": "not_applicable",
  "validation": {
    "planValidated": false,
    "executionCompleted": false,
    "accepted": false
  },
  "data": null,
  "plan": null,
  "queryServiceResult": null,
  "execution": {
    "compilerRevision": "sha256:6eb055652fea40247fe7862126891f89e447f48df0caeaf7b620c42681d00d87",
    "contractVersions": {
      "composable-query-plan-contract": "2.30.0",
      "query-schema-contract": "2.12.0"
    },
    "datasetContext": {
      "observationContextId": "general-integration-validation",
      "endpointId": "configured-read-only-fuseki",
      "snapshotId": null
    },
    "startedAt": "2026-11-13T12:58:07.451768+00:00",
    "finishedAt": "2026-11-13T12:58:09.720995+00:00",
    "queries": [],
    "plannerProposals": [
      {
        "prompt": "Are there recorded membership periods for the Committee of Public Accounts in earlier parliamentary terms?",
        "output": "{\"version\":2,\"supported\":false,\"family\":null,\"unsupportedReason\":\"Historical Committee membership periods in earlier parliamentary terms are not supported.\",\"intent\":\"Find recorded membership periods for the Committee of Public Accounts in earlier parliamentary terms.\",\"referents\":null,\"relations\":[],\"constraints\":[],\"answer\":null}"
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
      "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."
    ]
  },
  "error": {
    "code": "unsupported_request",
    "message": "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.",
    "technicalMessage": "Historical Committee membership periods in earlier parliamentary terms are not supported.",
    "candidates": [],
    "clarification": null
  },
  "diagnostic": "Historical Committee membership periods in earlier parliamentary terms are not supported.",
  "debugOutput": null,
  "debugSource": null
}
```
