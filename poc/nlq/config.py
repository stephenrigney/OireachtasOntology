"""Load local POC configuration without overriding explicit process settings."""

from pathlib import Path

from dotenv import load_dotenv


def load_local_environment(repository_root: str | Path) -> bool:
    """Load ``<repository_root>/.env``; existing environment values win."""
    dotenv_path = Path(repository_root) / ".env"
    return load_dotenv(dotenv_path=dotenv_path, override=False, encoding="utf-8")
