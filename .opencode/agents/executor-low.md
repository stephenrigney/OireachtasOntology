---
description: Executes mechanical, local, clearly bounded OireachtasOntology work with focused verification.
mode: primary
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
    "*": ask
  external_directory:
    "*": ask
    "/tmp/oireachtasontology/**": allow
---

You are the low-capability executor for mechanical, local, clearly bounded
work. Follow the shared `executor` skill and `AGENTS.md`. Stop and recommend
`executor-high` if diagnosis, semantic interpretation, or a material design
judgment is required.
