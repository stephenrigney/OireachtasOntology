"""Load local POC configuration without overriding explicit process settings."""

from pathlib import Path
import os
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values, load_dotenv


DEFAULT_LLM_MODEL = "gpt-6-luna"
DEFAULT_LLM_BASE_URL = "https://opencode.ai/inference/openai/v1"
LLM_TIMEOUT_SECONDS = 45.0
LLM_MAX_OUTPUT_TOKENS = 2000


def load_local_environment(repository_root: str | Path) -> bool:
    """Load ``<repository_root>/.env``; existing environment values win."""
    dotenv_path = Path(repository_root) / ".env"
    return load_dotenv(dotenv_path=dotenv_path, override=False, encoding="utf-8")


def resolved_llm_configuration(
    repository_root: str | Path,
    *,
    process_environment: dict[str, str] | None = None,
) -> dict:
    """Return resolved, non-secret translator settings and their provenance."""
    root = Path(repository_root)
    process_environment = process_environment if process_environment is not None else os.environ
    dotenv = dotenv_values(root / ".env", encoding="utf-8")

    def setting(name: str, default: str) -> dict[str, str]:
        if name in process_environment:
            value, source = process_environment[name], "process_environment"
        elif dotenv.get(name) is not None:
            value, source = dotenv[name], "repository_dotenv"
        else:
            value, source = default, "default"
        return {"value": value, "source": source}

    model = setting("NLQ_LLM_MODEL", DEFAULT_LLM_MODEL)
    base_endpoint = setting("NLQ_LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    parsed_endpoint = urlsplit(base_endpoint["value"])
    # Endpoint URLs should not be a back door for serializing credentials or
    # token-like query parameters into a public benchmark artifact.
    safe_netloc = parsed_endpoint.netloc.rsplit("@", 1)[-1]
    base_endpoint["value"] = urlunsplit((
        parsed_endpoint.scheme, safe_netloc, parsed_endpoint.path.rstrip("/"), "", "",
    ))
    return {
        "model": model,
        "base_endpoint": base_endpoint,
        "request_timeout_seconds": {"value": LLM_TIMEOUT_SECONDS, "source": "default"},
        "max_output_tokens": {"value": LLM_MAX_OUTPUT_TOKENS, "source": "default"},
    }
