import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def package_version() -> str:
    try:
        return version("oireachtas-ontology")
    except PackageNotFoundError:
        return "0.1.0"

def file_version(path: Path) -> str:
    return sha256(path.read_bytes())
