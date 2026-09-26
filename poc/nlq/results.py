"""Conversion of Fuseki's SPARQL Results JSON into small HTML-ready values."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .errors import NLQError


MAX_DEBUG_OUTPUT_CHARS = 50_000


def format_debug_text(text: str, *, secrets: tuple[str, ...] = ()) -> str:
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    if len(text) <= MAX_DEBUG_OUTPUT_CHARS:
        return text
    return text[:MAX_DEBUG_OUTPUT_CHARS] + "\n… debug output truncated at 50,000 characters …"


def format_debug_payload(payload: object, *, secrets: tuple[str, ...] = ()) -> str:
    """Pretty-print a payload for the on-screen debug disclosure, with a cap."""
    return format_debug_text(json.dumps(payload, ensure_ascii=False, indent=2), secrets=secrets)


@dataclass(frozen=True)
class QueryResult:
    kind: str
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    boolean: bool | None = None
    raw_json: str | None = None


def _cell(binding: dict) -> str:
    if not isinstance(binding, dict) or not isinstance(binding.get("value"), str):
        raise NLQError("Fuseki returned a malformed SPARQL binding.")
    value = binding["value"]
    if binding.get("type") == "literal":
        language = binding.get("xml:lang") or binding.get("lang")
        if language:
            value += f"@{language}"
        elif binding.get("datatype"):
            value += f"^^<{binding['datatype']}>"
    elif binding.get("type") == "bnode":
        value = f"_:{value}"
    return value


def parse_results(payload: object) -> QueryResult:
    """Validate the standard SPARQL JSON result shape and preserve RDF hints."""
    if not isinstance(payload, dict):
        raise NLQError("Fuseki returned an unexpected response format.")
    if isinstance(payload.get("boolean"), bool):
        return QueryResult(kind="ask", boolean=payload["boolean"], raw_json=format_debug_payload(payload))

    head = payload.get("head")
    results = payload.get("results")
    if not isinstance(head, dict) or not isinstance(results, dict):
        raise NLQError("Fuseki returned neither a SELECT result nor an ASK result.")
    variables = head.get("vars")
    bindings = results.get("bindings")
    if (not isinstance(variables, list) or not all(isinstance(name, str) for name in variables)
            or not isinstance(bindings, list)):
        raise NLQError("Fuseki returned malformed SELECT results.")

    rows = []
    for row in bindings:
        if not isinstance(row, dict):
            raise NLQError("Fuseki returned a malformed SELECT row.")
        rows.append(tuple(_cell(row[name]) if name in row else "—" for name in variables))
    return QueryResult(
        kind="select", columns=tuple(variables), rows=tuple(rows), raw_json=format_debug_payload(payload)
    )
