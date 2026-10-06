"""Read-only SPARQL Results JSON client for a configured Fuseki query URL."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .contract import load_query_contract
from .errors import NLQError
from .results import QueryResult, format_debug_payload, format_debug_text, parse_results


_QUERY_CONTRACT = load_query_contract()
_LOCAL_SAFETY = _QUERY_CONTRACT["localSafety"]
FUSEKI_QUERY_PATH = _LOCAL_SAFETY["endpoint"]["requiredEndpointPath"].strip("/")
FUSEKI_TIMEOUT_SECONDS = _LOCAL_SAFETY["limits"]["fusekiTimeoutSeconds"]
FUSEKI_QUERY_URL_ENV = _LOCAL_SAFETY["endpoint"]["configuration"]
DEFAULT_FUSEKI_QUERY_URL = _LOCAL_SAFETY["endpoint"]["defaultUrl"]
_GRAPH_FAMILIES = {
    family["id"]: family["graph"]
    for family in _QUERY_CONTRACT["graphFamilies"]
}


def _fixed_graph_iri(family_id: str) -> str:
    graph = _GRAPH_FAMILIES[family_id]
    if graph["kind"] != "fixed":
        raise ValueError(f"Graph family {family_id!r} is not fixed.")
    return graph["iri"]


def _resource_graph_prefix(family_id: str) -> str:
    graph = _GRAPH_FAMILIES[family_id]
    if graph["kind"] != "resource-pattern":
        raise ValueError(f"Graph family {family_id!r} is not a resource pattern.")
    return graph["iriTemplate"].split("{", 1)[0]

# These two fixed queries are read-only readiness probes, never model output.
# The wildcard predicate in the ASK is used only to tell a truly empty named
# dataset from one containing non-instance triples.
READINESS_EMPTY_QUERY = "ASK { GRAPH ?graph { ?subject ?predicate ?object } }"
READINESS_SOURCES_QUERY = """\
PREFIX agents: <__AGENTS_NS__>
PREFIX members: <__MEMBERS_NS__>
PREFIX eli-dl: <__ELI_DL_NS__>
PREFIX rdf: <__RDF_NS__>
PREFIX skos: <__SKOS_NS__>
SELECT DISTINCT ?source WHERE {
  { BIND("Houses" AS ?source)
    GRAPH <__HOUSES_GRAPH__> {
      ?term rdf:type ?termType ; skos:prefLabel ?label .
      FILTER(?termType = agents:DailTerm || ?termType = agents:SeanadTerm)
    }
  }
  UNION
  { BIND("Parties" AS ?source)
    GRAPH <__PARTIES_GRAPH__> {
      ?collection rdf:type members:ParliamentaryMemberCollection
    }
  }
  UNION
  { BIND("Constituencies" AS ?source)
    GRAPH <__CONSTITUENCIES_GRAPH__> {
      ?constituency rdf:type members:Constituencies
    }
  }
  UNION
  { BIND("Members" AS ?source)
    GRAPH ?memberGraph {
      ?member rdf:type agents:Member
    }
    FILTER(STRSTARTS(STR(?memberGraph), "__MEMBER_GRAPH_PREFIX__"))
  }
  UNION
  { BIND("Bills" AS ?source)
    GRAPH ?billGraph {
      ?bill rdf:type eli-dl:DraftLegislationWork
    }
    FILTER(STRSTARTS(STR(?billGraph), "__BILL_GRAPH_PREFIX__"))
  }
}
ORDER BY ?source
LIMIT 10
"""
for _token, _value in (
    ("__AGENTS_NS__", _QUERY_CONTRACT["namespaces"]["agents"]),
    ("__MEMBERS_NS__", _QUERY_CONTRACT["namespaces"]["members"]),
    ("__ELI_DL_NS__", _QUERY_CONTRACT["namespaces"]["eli-dl"]),
    ("__RDF_NS__", _QUERY_CONTRACT["namespaces"]["rdf"]),
    ("__SKOS_NS__", _QUERY_CONTRACT["namespaces"]["skos"]),
    ("__HOUSES_GRAPH__", _fixed_graph_iri("houses")),
    ("__PARTIES_GRAPH__", _fixed_graph_iri("parties")),
    ("__CONSTITUENCIES_GRAPH__", _fixed_graph_iri("constituencies")),
    ("__MEMBER_GRAPH_PREFIX__", _resource_graph_prefix("member-records")),
    ("__BILL_GRAPH_PREFIX__", _resource_graph_prefix("bill-records")),
):
    READINESS_SOURCES_QUERY = READINESS_SOURCES_QUERY.replace(_token, _value)
REQUIRED_READINESS_SOURCES = ("Houses", "Parties", "Constituencies", "Members")


@dataclass(frozen=True)
class FusekiReadiness:
    """Read-only presence summary for POC-relevant named graph families."""

    state: str
    has_triples: bool
    sources: tuple[tuple[str, bool], ...]
    message: str


def _response_debug(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return format_debug_text(response.text)
    return format_debug_payload(payload)


class FusekiQueryClient:
    def __init__(self, query_url: str, *, username: str | None = None,
                 password: str | None = None, timeout: float = FUSEKI_TIMEOUT_SECONDS,
                 transport: httpx.BaseTransport | None = None):
        if not query_url:
            raise NLQError(f"Set {FUSEKI_QUERY_URL_ENV} to the Fuseki SPARQL query endpoint.")
        parsed_url = urlsplit(query_url)
        if (parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc
                or parsed_url.path.rstrip("/").split("/")[-1] != FUSEKI_QUERY_PATH
                or parsed_url.query or parsed_url.fragment or parsed_url.username or parsed_url.password):
            raise NLQError(
                f"{FUSEKI_QUERY_URL_ENV} must be a Fuseki /{FUSEKI_QUERY_PATH} endpoint URL "
                "(not /update or an admin URL)."
            )
        if bool(username) != bool(password):
            raise NLQError("Set both OIR_FUSEKI_USER and OIR_FUSEKI_PASSWORD, or neither.")
        self.client = httpx.Client(timeout=timeout, auth=(username, password) if username else None,
                                   transport=transport)
        self.query_url = query_url

    def query(self, sparql: str) -> QueryResult:
        try:
            response = self.client.post(
                self.query_url,
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
        except httpx.TimeoutException as error:
            raise NLQError("The Fuseki query timed out. Try a more specific question.") from error
        except httpx.HTTPError as error:
            raise NLQError("Fuseki returned an unreadable query response.") from error

        if response.is_error:
            raise NLQError(
                f"Fuseki returned HTTP {response.status_code} while querying.",
                debug_output=_response_debug(response),
                debug_source="Fuseki",
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise NLQError(
                "Fuseki returned a non-JSON query response.", debug_output=_response_debug(response),
                debug_source="Fuseki",
            ) from error
        try:
            return parse_results(payload)
        except NLQError as error:
            raise NLQError(
                str(error), debug_output=format_debug_payload(payload), debug_source="Fuseki"
            ) from error

    def readiness(self) -> FusekiReadiness:
        """Inspect graph presence using fixed read-only ASK and SELECT queries."""
        empty_check = self.query(READINESS_EMPTY_QUERY)
        if empty_check.kind != "ask" or empty_check.boolean is None:
            raise NLQError("Fuseki returned an unexpected response to the readiness ASK query.")
        has_triples = empty_check.boolean

        present_sources: set[str] = set()
        if has_triples:
            source_result = self.query(READINESS_SOURCES_QUERY)
            if source_result.kind != "select" or "source" not in source_result.columns:
                raise NLQError("Fuseki returned an unexpected response to the readiness graph query.")
            source_index = source_result.columns.index("source")
            present_sources = {row[source_index].split("@", 1)[0] for row in source_result.rows}

        source_status = tuple((name, name in present_sources) for name in (
            "Houses", "Parties", "Constituencies", "Members", "Bills"
        ))
        missing_required = [name for name in REQUIRED_READINESS_SOURCES if name not in present_sources]
        if not has_triples:
            state = "empty"
            message = (
                "Fuseki is reachable, but no triples were found in its named graphs. "
                "The POC does not load or rebuild data automatically."
            )
        elif missing_required:
            state = "partial"
            message = (
                "Fuseki contains triples, but required graph families are missing: "
                + ", ".join(missing_required)
                + ". Use the ETL startup instructions to load data; the POC will not write to Fuseki."
            )
        else:
            state = "ready"
            message = (
                "Houses, Parties, Constituencies, and Member graph families are present. "
                "Individual questions may still return no rows when their facts are not loaded."
            )
        return FusekiReadiness(state, has_triples, source_status, message)

    def close(self) -> None:
        self.client.close()
