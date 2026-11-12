"""Retain unedited generated bodies and exact review data from the browser trial."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def retain(source: Path, destination: Path, earlier_trials=()):
    destination.mkdir(parents=True, exist_ok=True)
    labels = ["r1-initial", "r1-revision", "r1-evidence-discussion", "r3-same-session"]
    archives = {label: json.loads((source / f"{label}.json").read_text()) for label in labels}
    final = archives[labels[-1]]
    bundle = {"kind": "Actual configured LLM and read-only Fuseki; unedited application output; human acceptance pending",
              "implementationBase": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "factRegistry": final["state"]["facts"], "evidence": final["evidence"], "modelCalls": final["modelCalls"],
              "snapshots": {label: {k: v for k, v in archive["state"].items() if k != "facts"} for label, archive in archives.items()},
              "boundaryRuns": {label: json.loads((source / f"{label}.json").read_text()) for label in ("r4-boundary", "r5-boundary")}}
    bundle["earlierTrials"] = []
    for trial in earlier_trials:
        initial = json.loads((trial / "r1-initial.json").read_text())
        revision = json.loads((trial / "r1-revision.json").read_text())
        bundle["earlierTrials"].append({"label": trial.name, "countedAsFinalAcceptanceEvidence": False,
            "modelCalls": revision["modelCalls"], "evidence": revision["evidence"], "factRegistry": revision["state"]["facts"],
            "snapshots": {"initial": {k: v for k, v in initial["state"].items() if k != "facts"},
                          "revision": {k: v for k, v in revision["state"].items() if k != "facts"}}})
    (destination / "research-review-bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
    for label in labels:
        generated = (source / f"{label}.md").read_text()
        body = generated.split("## Assertion evidence and reasoning", 1)[0].rstrip()
        (destination / f"{label}.md").write_text(
            "> Unedited generated report body. Full assertion/source appendices are retained in the review bundle and full combined export.\n\n" + body + "\n")
    shutil.copyfile(source / "r3-same-session.md", destination / "full-combined-export.md")
    shutil.copyfile(source / "browser-summary.json", destination / "browser-summary.json")
    (destination / "screenshots").mkdir(exist_ok=True)
    for path in source.glob("*.png"):
        shutil.copyfile(path, destination / "screenshots" / path.name)
    transcript = {label: archive["state"]["messages"] for label, archive in archives.items()}
    (destination / "conversation-transcripts.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2))
    manifest = {"implementationBase": bundle["implementationBase"],
                "applicationDiffSha256": hashlib.sha256(subprocess.check_output(["git", "diff", "--", "poc/nlq"])).hexdigest(),
                "applicationFiles": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                    Path("poc/nlq/research_collaborator.py"), Path("poc/nlq/research_assertions.py"),
                    Path("poc/nlq/research_presentation.py"), Path("poc/nlq/research_ui/workspace.js"),
                    Path("poc/nlq/research_ui/workspace.css"))},
                "artefacts": {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(destination.rglob("*")) if p.is_file() and p.name != "manifest.json"}}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--earlier-trial", type=Path, action="append", default=[])
    args = parser.parse_args()
    retain(args.source, args.destination, args.earlier_trial)
