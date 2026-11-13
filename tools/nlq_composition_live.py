"""Evaluation-only typed HTTP transport; no composition or result-selection logic.

The frozen executor owns query generation, safety, pagination, limits, validation,
binding and projection. ``complete`` certifies one fully received JSON page, NOT
that the entire selection is enumerated; the executor requires a short page.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

import httpx
from rdflib import Literal, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from poc.nlq.errors import NLQError


def decode_select(payload):
    """Preserve RDF lexical/datatype/language identity, rejecting unsupported terms."""
    try:
        columns = payload["head"]["vars"]
        bindings = payload["results"]["bindings"]
        if (not isinstance(columns, list) or len(set(columns)) != len(columns)
                or any(not isinstance(c, str) for c in columns)
                or not isinstance(bindings, list)):
            raise ValueError("Malformed SELECT envelope")
        rows = []
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) - set(columns):
                raise ValueError("Malformed SELECT binding")
            row = {}
            for name, term in binding.items():
                if not isinstance(term, dict) or not isinstance(term.get("value"), str):
                    raise ValueError("Malformed RDF term")
                if term.get("type") == "uri" and set(term) == {"type", "value"}:
                    row[name] = URIRef(term["value"])
                elif (term.get("type") in {"literal", "typed-literal"}
                      and not set(term) - {"type", "value", "datatype", "xml:lang"}
                      and not ("datatype" in term and "xml:lang" in term)
                      and all(isinstance(term[k], str) for k in ("datatype", "xml:lang") if k in term)):
                    row[name] = Literal(term["value"], datatype=term.get("datatype"),
                                        lang=term.get("xml:lang"), normalize=False)
                else:
                    raise ValueError("Unsupported or conflicting RDF term")
            rows.append(row)
        return columns, rows
    except (KeyError, TypeError, ValueError) as error:
        raise NLQError(f"Live SELECT decoding failed: {error}") from error


class LiveTransport:
    timeout = 15

    def __init__(self, endpoint="http://localhost:3030/houses/query", *, client=None):
        url = urlsplit(endpoint)
        if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1"}
                or url.port != 3030 or url.path != "/houses/query"
                or url.query or url.fragment or url.username or url.password):
            raise ValueError("Evaluation transport requires the existing local houses/query endpoint")
        self.endpoint = endpoint
        self.client = client or httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False)
        self.exchanges = []

    def select(self, lookup, query, offset):
        # lookup/offset are deliberately not used to alter query text or results.
        exchange = {"query": query, "offset": offset,
                    "startedAt": datetime.now(timezone.utc).isoformat()}
        self.exchanges.append(exchange)
        try:
            response = self.client.post(self.endpoint, data={"query": query},
                                        headers={"Accept": "application/sparql-results+json"},
                                        timeout=self.timeout)
            exchange.update(status=response.status_code, headers=dict(response.headers),
                            body=response.text, finishedAt=datetime.now(timezone.utc).isoformat())
            if response.status_code != 200:
                raise NLQError(f"Live SELECT returned HTTP {response.status_code}")
            if response.headers.get("content-type", "").split(";", 1)[0] != "application/sparql-results+json":
                raise NLQError("Live SELECT did not return SPARQL Results JSON")
            payload = response.json()
            columns, rows = decode_select(payload)
            return {"columns": columns, "rows": rows, "complete": True,
                    "pageCertificate": "HTTP 200, fully received and parsed SPARQL Results JSON; short-page completion is kernel-owned"}
        except (httpx.HTTPError, ValueError) as error:
            exchange["error"] = str(error)
            raise NLQError(f"Live SELECT transport failed: {error}") from error

    def close(self):
        self.client.close()


def typed_json(value):
    from poc.nlq.experimental_composition import term_json
    if isinstance(value, (URIRef, Literal)):
        return term_json(value)
    if isinstance(value, dict):
        return {key: typed_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [typed_json(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # Reserve before execution: an existing first result can never be overwritten.
    with args.output.open("x") as saved:
        from poc.nlq.experimental_composition import execute
        spec = json.loads(args.input.read_text())
        transport = LiveTransport()
        artifact = {"original": spec, "candidate": spec, "endpoint": transport.endpoint,
                    "startedAt": datetime.now(timezone.utc).isoformat()}
        try:
            artifact["report"] = execute(spec, spec, transport)
        except Exception as error:
            artifact["unexpectedError"] = repr(error)
            raise
        finally:
            artifact["exchanges"] = transport.exchanges
            artifact["finishedAt"] = datetime.now(timezone.utc).isoformat()
            json.dump(typed_json(artifact), saved, indent=2, ensure_ascii=False)
            saved.write("\n")
            transport.close()
    print(json.dumps({"status": artifact["report"]["status"],
                      "requests": len(artifact["report"]["ledger"]),
                      "error": artifact["report"].get("error")}))
    return 0 if artifact["report"]["status"] == "answer" else 1


if __name__ == "__main__":
    raise SystemExit(main())
