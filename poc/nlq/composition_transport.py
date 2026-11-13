"""Production-configured, read-only typed Fuseki SELECT transport.

Unlike QueryResult's display cells/debug JSON, these bindings are lossless RDF
terms. Pagination, completion probes and request charging belong to the kernel.
Decoder derived from tools/nlq_composition_live.py at 3a77fb2; that file stays frozen.
"""

import json

import httpx
from rdflib import Literal, URIRef

from .composition_kernel import REQUEST_TIMEOUT, term_json
from .errors import NLQError
from .fuseki import FusekiQueryClient
from .structured_planner import _object_without_duplicate_keys


MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def decode_select(payload):
    try:
        columns = payload["head"]["vars"]
        bindings = payload["results"]["bindings"]
        if (not isinstance(columns, list) or any(not isinstance(c, str) for c in columns)
                or len(set(columns)) != len(columns) or not isinstance(bindings, list)):
            raise ValueError("Malformed SELECT envelope")
        if len(bindings) > 100:
            raise ValueError("Raw response row budget exceeded before deduplication")
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
        raise NLQError(f"Typed SELECT decoding failed: {error}") from error


class CompositionTransport(FusekiQueryClient):
    timeout = REQUEST_TIMEOUT

    def __init__(self, query_url, *, username=None, password=None, transport=None):
        # Reuse the application's /query-only URL, paired credentials and client
        # configuration. Never use the evaluation transport's loopback-only policy.
        super().__init__(query_url, username=username, password=password,
                         timeout=self.timeout, transport=transport)

    def select(self, lookup, query, offset):
        # No rewriting, inferred facts, DISTINCT repair or truncation here.
        try:
            with self.client.stream("POST", self.query_url, data={"query": query},
                                    headers={"Accept": "application/sparql-results+json"},
                                    timeout=self.timeout) as response:
                if response.status_code != 200:
                    raise NLQError(f"Fuseki returned HTTP {response.status_code} while querying.")
                if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/sparql-results+json":
                    raise NLQError("Fuseki did not return SPARQL Results JSON.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise NLQError("Fuseki response byte budget exceeded; no partial answer returned.")
            payload = json.loads(body, object_pairs_hook=_object_without_duplicate_keys)
            columns, rows = decode_select(payload)
            return {"columns": columns, "rows": rows, "complete": True,
                    "pageCertificate": "HTTP 200; fully received and decoded Results JSON. Short-page enumeration is kernel-owned."}
        except httpx.TimeoutException as error:
            raise NLQError("The Fuseki query timed out; no partial answer returned.") from error
        except (httpx.HTTPError, ValueError) as error:
            raise NLQError("Fuseki returned an unreadable query response; no partial answer returned.") from error


def typed_json(value):
    if isinstance(value, (URIRef, Literal)):
        return term_json(value)
    if isinstance(value, dict):
        return {key: typed_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [typed_json(item) for item in value]
    return value
