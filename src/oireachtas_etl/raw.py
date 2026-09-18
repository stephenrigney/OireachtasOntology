"""Immutable raw-response store; collisions never overwrite evidence."""
from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from .provenance import package_version, sha256

def persist_raw(*, root: Path, endpoint: str, params: dict, body: bytes, status: int,
                retrieved_at: datetime | None = None, ontology_version: str = "agents.owl.ttl@phase-1-houses-2026",
                mapping_version: str = "houses_mapping.csv@phase-1-houses-2026", endpoint_name: str = "houses") -> tuple[Path, Path]:
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    day = retrieved_at.date().isoformat()
    skip = int(params["skip"])
    if endpoint_name not in {"houses", "parties", "constituencies", "members", "legislation"}:
        raise ValueError(f"unsupported raw endpoint: {endpoint_name!r}")
    destination = root / endpoint_name / day
    destination.mkdir(parents=True, exist_ok=True)
    raw_path = destination / f"skip-{skip:06d}.json"
    meta_path = destination / f"skip-{skip:06d}.meta.json"
    metadata = {
        "endpoint": endpoint, "params": params, "retrieved_at": retrieved_at.isoformat(), "status": status,
        "sha256": sha256(body), "etl_version": package_version(),
        "ontology_version": ontology_version, "mapping_version": mapping_version,
    }
    if raw_path.exists() or meta_path.exists():
        if not raw_path.exists() or not meta_path.exists():
            raise FileExistsError(f"incomplete raw storage collision: {destination}")
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        if raw_path.read_bytes() != body or existing.get("sha256") != metadata["sha256"]:
            raise FileExistsError(f"raw storage collision: {raw_path}")
        return raw_path, meta_path
    # Write both complete payloads to private files before linking either final name.
    raw_temp = meta_temp = None
    try:
        raw_fd, raw_temp = tempfile.mkstemp(dir=destination); meta_fd, meta_temp = tempfile.mkstemp(dir=destination)
        with os.fdopen(raw_fd, "wb") as handle: handle.write(body); handle.flush(); os.fsync(handle.fileno())
        with os.fdopen(meta_fd, "w", encoding="utf-8") as handle: handle.write(json.dumps(metadata, sort_keys=True, indent=2) + "\n"); handle.flush(); os.fsync(handle.fileno())
        os.link(raw_temp, raw_path); os.link(meta_temp, meta_path)
    except FileExistsError as error:
        # If the second exclusive link lost a race, do not leave a lone raw file.
        if raw_path.exists() and not meta_path.exists(): os.unlink(raw_path)
        raise FileExistsError(f"raw storage collision: {raw_path}") from error
    finally:
        for temporary in (raw_temp, meta_temp):
            if temporary and os.path.exists(temporary): os.unlink(temporary)
    return raw_path, meta_path
