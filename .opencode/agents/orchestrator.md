---
description: Orchestrates phased OireachtasOntology ETL implementation.
mode: primary
model: gpt-5.6-sol

permission:
  edit:
    "*": ask
    "src/oireachtas_etl/**": allow
    "tests/**": allow
    "tools/**": allow
    "documentation/**": allow
    "README.md": allow
    "/tmp/oireachtasontology/**": allow
    "documentation/mapping_notes.md": ask
    "tests/**/fixtures/**": ask
    "tests/**/*golden*": ask
    "ontology/**": ask
    "mappings/**": ask
    "pyproject.toml": ask

  bash:
    "*": allow
    "git push*": ask
    "git switch*": ask
    "git checkout*": ask
    "git worktree*": ask
    "git rebase*": ask
    "git merge*": ask
    "git cherry-pick*": ask
    "git stash*": ask
    "git reset --hard*": ask
    "git restore*": ask
    "git clean*": ask
    "sudo*": ask
    "docker volume rm*": ask
    "docker volume prune*": ask
    "docker compose down -v*": ask
    "docker compose down --volumes*": ask
    "docker system prune*": ask

  task:
    "executor-high": allow
    "executor-low": allow
    "architecture-plan-auditor": allow
    "*": ask

  external_directory:
    "*": ask
    "/tmp/oireachtasontology/**": allow
---

You are the OireachtasOntology phase orchestrator.

Follow `AGENTS.md` and load the `orchestrator` skill before beginning work.