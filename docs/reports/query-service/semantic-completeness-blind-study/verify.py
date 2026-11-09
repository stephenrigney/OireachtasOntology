"""Post-run byte integrity, freeze, response-blindness and secret checks."""
import hashlib
import json
from pathlib import Path
import subprocess

from run import BASELINE, HERE, ROOT, configuration, save, source_input


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main(pid, output):
    changed = []
    entries = git("ls-tree", "-rz", BASELINE).split(b"\0")
    count = 0
    for entry in entries:
        if not entry:
            continue
        info, path = entry.split(b"\t", 1)
        mode, kind, oid = info.split()
        if kind != b"blob":
            continue
        name = path.decode(); count += 1
        if not (ROOT/name).exists() or (ROOT/name).read_bytes() != git("cat-file", "blob", oid.decode()):
            changed.append(name)
    assert not changed, changed
    manifest = json.loads((HERE/"results/manifest.json").read_text())
    frozen_changes = [name for name, digest in manifest["files"].items()
                      if hashlib.sha256((HERE/name).read_bytes()).hexdigest() != digest]
    assert not frozen_changes, frozen_changes
    config = configuration(pid)
    secret = config["NLQ_LLM_API_KEY"].encode()
    assert not any(secret in p.read_bytes() for p in HERE.rglob("*") if p.is_file())
    cases = {c["id"]: c for c in json.loads((HERE/"cases.json").read_text())["cases"]}
    rows = [json.loads(p.read_text()) for p in (HERE/"results").glob("*-r*.json")]
    assert len(rows) == 36
    for row in rows:
        digest = hashlib.sha256(json.dumps(source_input(cases[row["id"]]["question"]), ensure_ascii=False).encode()).hexdigest()
        assert row["proposal"]["request_input_sha256"] == digest == row["blind"]["request_input_sha256"]
    pr = json.loads(subprocess.check_output(["gh", "pr", "view", "27", "--repo", "stephenrigney/OireachtasOntology",
        "--json", "state,isDraft,mergedAt,title,headRefName"], cwd=ROOT))
    assert pr["isDraft"] and pr["mergedAt"] is None and pr["state"] == "OPEN"
    changed_paths = git("diff", "--name-only", BASELINE, "HEAD").decode().splitlines()
    assert all(p.startswith(str(HERE.relative_to(ROOT)) + "/") for p in changed_paths)
    branch = git("branch", "--show-current").decode().strip()
    assert branch == "feat/query-service-generalisation"
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    save(Path(output), {"baseline": BASELINE, "freeze_commit": manifest["freeze_commit"],
        "repository": "stephenrigney/OireachtasOntology", "branch": branch,
        "baseline_blob_count": count, "baseline_changed": changed,
        "frozen_changed": frozen_changes, "all_request_inputs_question_only_hash_verified": True,
        "provider_calls": len(rows)*2, "preflight_calls": 0,
        "credential_exact_bytes_absent_from_all_artifacts": True, "pr_27": pr,
        "acceptance": "NOT ACCEPTED", "production_acceptance_campaign": "not rerun",
        "existing_test_command": ".venv/bin/python -m pytest tests/test_nlq_term_count_intent.py tests/test_nlq_composable_semantic_capability_discovery.py tests/test_nlq_composable_stage_a.py tests/test_nlq_plan_sparql.py -q",
        "test_log": "existing-tests.txt", "diff_check": "passed",
        "scope": "Only new files in semantic-completeness-blind-study; no production integration or data writes"})


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--provider-pid", type=int, required=True); p.add_argument("--output", required=True)
    args = p.parse_args(); main(args.provider_pid, args.output)
