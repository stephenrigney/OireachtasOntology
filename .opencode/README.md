# OireachtasOntology OpenCode Harness

This is a minimal project-local coding harness. Its four roles are:

- `executor-low`: mechanical, local, clearly bounded implementation or investigation.
- `executor-high`: diagnosis, design-sensitive implementation, or bounded work with material uncertainty.
- `architecture-plan-auditor`: independent, read-only review when independence itself adds value.
- `orchestrator`: manages executors for phased implementation of plans.

Direct bounded implementation is the default. The executor retains the task
through verification and works from: outcome, boundaries/invariants,
verification, and escalation conditions. There is no project planner,
orchestrator, per-step workflow, or specialist-agent hierarchy.

The shared executor policy is in `.opencode/skills/executor/SKILL.md`.
`AGENTS.md` defines the repository's semantic contracts and protected areas.
Restart OpenCode after changing this directory or `opencode.json`; configuration
is loaded when the session starts.
