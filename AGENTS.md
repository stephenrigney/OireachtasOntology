# OireachtasOntology Agent Guidance

## Purpose and Architecture

This repository defines the Houses of the Oireachtas OWL ontology and the
mapping contract for a deterministic Python ETL pipeline. The intended flow is:

```text
Oireachtas Open Data API -> immutable raw JSON -> RDF transformation -> validation -> staging graph -> production triple store
```

ETL code implements the mapping contract; it does not redefine ontology or
mapping meaning. Valid RDF must be produced and validated before publication.
The ETL architecture, RDF ownership, deterministic identifier expectations,
and named-graph strategy are defined in `documentation/etl-plan.md`.

## Authoritative Information

Read the smallest relevant authoritative material before changing behavior:

- `documentation/etl-plan.md` for ETL architecture, phase boundaries, RDF
  ownership, identifier strategy, named graphs, and acceptance expectations.
- `documentation/mapping_notes.md` and `mappings/*.csv` for field-level
  mapping meaning and status.
- `ontology/*.owl.ttl` for executable Oireachtas vocabulary definitions.
- `ontology/README.md` for the module structure, ontology terms, and external
  vocabularies.
- `README.md` for repository purpose and namespace conventions.
- `tests/` for executable acceptance and validation behavior.

When documentation and executable ontology/mapping material disagree, do not
silently choose an interpretation: report the discrepancy for semantic review.

## Mutable and Protected Areas

Routine implementation work may modify:

- `src/oireachtas_etl/**`
- `tests/**`
- `tools/**` when present
- ordinary implementation documentation, including `documentation/**`
- disposable files under `/tmp/oireachtasontology/**`

The following are semantic-contract areas. Obtain explicit approval before
changing them:

- `ontology/**`
- `mappings/**`
- mapping documentation where a change alters mapping meaning or status
- source or golden fixtures where a change could weaken acceptance criteria
- production triple-store mutation or configuration

Do not use shell commands, scratch copies, or delegation to bypass an approval
boundary.

## Working Contract

For a bounded task, establish: outcome, boundaries/invariants, verification,
and escalation conditions.

For ordinary standalone work, select `executor-low` for mechanical, local work
with a clear path or `executor-high` for diagnosis, design-sensitive work,
broad uncertainty, or a material trade-off inside existing project decisions.
Keep the selected executor through its deterministic verification tail while
its context helps.

For phased implementation where decomposition, sequencing, delegation,
integration, or phase-level acceptance materially benefits from a persistent
control point, use `orchestrator`. The orchestrator may delegate bounded work
to either executor, review their results, invoke independent audit when useful,
and retain responsibility for scope, integration, verification, and escalation.
Do not route every bounded task through the orchestrator merely because it
exists.

Use `architecture-plan-auditor` when independent review materially adds value,
such as for consequential architecture, irreversible work, broad regression
risk, or a phase where an independent challenge would strengthen acceptance.
Independent review is a separate perspective, not an execution approval gate.

Do not create additional planner/orchestrator layers, specialist-agent
hierarchies, per-step workflow machinery, or agent tiers solely to encode
model variants.

If a prompt names a repository, worktree, or branch that does not match the
current session, stop before mutation and report the expected and actual
location. Do not switch branches, create a worktree, or write elsewhere to
make it fit.

Git history and deterministic tests are normal evidence. Persist only durable
findings, decisions, limitations, or risks that future work depends on.

## Verification

Use focused checks while working and the smallest broader credible check before
completion. The current Phase 0 checks are:

```text
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
```

Validation must fail closed: Turtle parse failures, ontology inconsistency,
unsatisfiable classes, or reasoner execution failures are failures. Mapping
integrity checks must report every active (`mapped` or `new`) mapping term that
does not resolve to a local Oireachtas definition or a recognised external
vocabulary.

Never weaken tests, validation, ontology constraints, identifiers, fixtures,
golden outputs, SHACL, competency queries, or mapping-integrity acceptance to
obtain a passing result.

## Mandatory Escalation

Stop and report rather than deciding silently if work requires:

- changing ontology semantics;
- changing a mapping's meaning or status;
- introducing an RDF ownership rule;
- changing IRI strategy;
- changing named-graph identity or ownership;
- weakening SHACL, golden-output, competency-query, or mapping-integrity
  acceptance;
- modifying source fixtures to make output pass;
- permitting invalid or unvalidated RDF publication; or
- a material architecture decision not already covered by
  `documentation/etl-plan.md`.
