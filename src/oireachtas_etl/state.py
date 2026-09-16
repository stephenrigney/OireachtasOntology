"""Small atomically-written operational manifest for Members refreshes."""
from __future__ import annotations

import json
import os
import tempfile
import fcntl
from contextlib import contextmanager
from pathlib import Path


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "members": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("members"), dict):
        raise ValueError("invalid Members state manifest")
    return value


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory = os.open(path.parent, os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        except (AttributeError, OSError):
            pass
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


@contextmanager
def manifest_lock(path: Path):
    """Advisory process lock; one online writer owns a state file at a time."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
