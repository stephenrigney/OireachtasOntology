"""Fuseki Graph Store Protocol loading, using atomic whole-graph PUT only."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rdflib import Graph


class FusekiGraphStoreLoader:
    def __init__(
        self,
        endpoint: str,
        *,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 30,
    ):
        self.endpoint, self.user, self.password, self.timeout = endpoint, user, password, timeout

    def replace(self, graph_iri: str, payload: str, *, content_type: str = "application/n-quads") -> None:
        separator = "&" if "?" in self.endpoint else "?"
        url = self.endpoint + separator + urlencode({"graph": graph_iri})
        headers = {"Content-Type": content_type}
        if self.user is not None:
            if self.password is None:
                raise ValueError("Fuseki password is required when user is set")
            token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            headers["Authorization"] = "Basic " + token
        request = Request(url, data=payload.encode("utf-8"), headers=headers, method="PUT")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"GSP replacement failed: HTTP {response.status}")
        except HTTPError as error:
            raise RuntimeError(f"GSP replacement failed: HTTP {error.code}") from error

class FusekiSparqlClient:
    def __init__(
        self,
        endpoint: str,
        *,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 30,
    ):
        self.endpoint, self.user, self.password, self.timeout = endpoint, user, password, timeout

    def query(self, sparql: str) -> list[dict]:
        headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"}
        if self.user is not None:
            if self.password is None:
                raise ValueError("Fuseki password is required when user is set")
            headers["Authorization"] = "Basic " + base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        request = Request(self.endpoint, data=urlencode({"query": sparql}).encode(), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"SPARQL query failed: HTTP {response.status}")
                return json.loads(response.read())["results"]["bindings"]
        except HTTPError as error:
            raise RuntimeError(f"SPARQL query failed: HTTP {error.code}") from error

    def construct_graph(self, graph_iri: str) -> Graph:
        """Read a named graph for safe carry-forward of pre-payload state."""
        query = ("CONSTRUCT {?subject ?predicate ?object} WHERE { "
                 f"GRAPH <{graph_iri}> {{ ?subject ?predicate ?object }} }}")
        headers = {"Accept": "application/n-triples",
                   "Content-Type": "application/x-www-form-urlencoded"}
        if self.user is not None:
            if self.password is None:
                raise ValueError("Fuseki password is required when user is set")
            headers["Authorization"] = "Basic " + base64.b64encode(
                f"{self.user}:{self.password}".encode()).decode()
        request = Request(self.endpoint, data=urlencode({"query": query}).encode(),
                          headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"SPARQL CONSTRUCT failed: HTTP {response.status}")
                body = response.read()
        except HTTPError as error:
            raise RuntimeError(f"SPARQL CONSTRUCT failed: HTTP {error.code}") from error
        graph = Graph()
        if body:
            try:
                graph.parse(data=body, format="nt")
            except Exception as error:
                raise RuntimeError("SPARQL CONSTRUCT returned invalid N-Triples") from error
        return graph
