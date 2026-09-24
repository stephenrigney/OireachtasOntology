# OireachtasOntology OpenCode Harness

This is a minimal project-local coding harness. It has four roles:

| Role | Default model | Variant | Purpose |
|---|---|---|---|
| `orchestrator` | `openai/gpt-6-sol` | `high` | Owns phased implementation: decomposition, sequencing, delegation, integration, scope control, and phase-level verification. |
| `executor-high` | `openai/gpt-6-luna` | `max` | Handles diagnosis, design-sensitive implementation, and bounded work with material uncertainty inside settled project decisions. |
| `executor-low` | `openai/gpt-6-luna` | `medium` | Handles mechanical, local, clearly bounded implementation or investigation. |
| `architecture-plan-auditor` | `opencode-go/glm-5.3-flash` | provider default | Provides independent, read-only challenge of consequential architecture, plans, and implementation evidence. |

The agent definitions under `.opencode/agents/` are the executable source of
truth for model and permission settings. The table above documents the intended
defaults; update it when those defaults change.

## Working modes

### Direct bounded implementation

Direct bounded implementation remains the default for ordinary tasks. Select
`executor-low` or `executor-high` according to the work, and keep that
executor through focused verification while its context remains useful.

The task contract is:

```text
outcome + boundaries/invariants + verification + escalation conditions
```

Do not route a small bounded task through the orchestrator merely because the
orchestrator exists.

### Orchestrated phased implementation

Use `orchestrator` when executing a phase or plan where decomposition,
sequencing, delegation, integration, or phase-level acceptance materially
benefits from a persistent control point.

The orchestrator may delegate bounded work to either executor and may invoke
`architecture-plan-auditor` when independent challenge materially reduces
architectural, semantic, or regression risk. It retains responsibility for
scope, integration, review of delegated results, and escalation.

The orchestrator is not a second planning bureaucracy. There is no separate
project planner, per-step workflow engine, plan-amender tier, or specialist
agent hierarchy.

## Model-allocation intent

The current allocation deliberately concentrates the more expensive model at
the control point:

- `orchestrator` uses GPT-6 Sol for cross-task reasoning and integration;
- `executor-high` uses GPT-6 Luna at `max` as a cost-effective default for
  judgment-heavy implementation under an explicit bounded contract;
- `executor-low` uses GPT-6 Luna at `medium` for routine scoped work;
- `architecture-plan-auditor` uses GLM-5.3-Flash so independent review can be
  invoked frequently at low cost while preserving model-family diversity.

Do not create extra executor or auditor tiers merely to encode model variants.
A task that exceeds an agent's capability or authority should escalate rather
than silently widening its role.

The shared executor policy is in `.opencode/skills/executor/SKILL.md`.
The phased orchestration policy is in `.opencode/skills/orchestrator/SKILL.md`.
`AGENTS.md` defines the repository's semantic contracts and protected areas.

Restart OpenCode after changing `.opencode/` or `opencode.json`; configuration
is loaded when the session starts.
