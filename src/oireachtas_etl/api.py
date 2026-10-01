"""Small HTTP client with explicit skip/limit pagination and transient retry."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collections.abc import Mapping

TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}

@dataclass(frozen=True)
class ApiPage:
    body: bytes
    status: int
    params: dict[str, str | int]

class ApiClient:
    def __init__(self, url: str, *, retries: int = 3, timeout: float = 30):
        self.url, self.retries, self.timeout = url, retries, timeout

    def page(self, *, skip: int, limit: int,
             query_params: Mapping[str, str | int] | None = None) -> ApiPage:
        params = {"skip": skip, "limit": limit}
        if query_params:
            if {"skip", "limit"}.intersection(query_params):
                raise ValueError("query parameters must not override pagination")
            if any(not isinstance(key, str) or not key for key in query_params):
                raise ValueError("query parameter names must be non-empty strings")
            if any(not isinstance(value, (str, int)) or isinstance(value, bool)
                   for value in query_params.values()):
                raise ValueError("query parameter values must be strings or integers")
            params.update(query_params)
        separator = "&" if "?" in self.url else "?"
        request = Request(self.url + separator + urlencode(params), headers={"Accept": "application/json"})
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return ApiPage(response.read(), response.status, params)
            except HTTPError as error:
                if error.code not in TRANSIENT_STATUSES or attempt == self.retries:
                    raise
            except URLError:
                if attempt == self.retries:
                    raise
            time.sleep(0.25 * (2 ** attempt))
        raise AssertionError("unreachable")

    def harvest(self, *, limit: int,
                query_params: Mapping[str, str | int] | None = None):
        skip = 0
        while True:
            # Preserve the original call signature for unparameterised endpoint
            # clients and their existing page adapters.
            if query_params:
                page = self.page(skip=skip, limit=limit, query_params=query_params)
            else:
                page = self.page(skip=skip, limit=limit)
            decoded = json.loads(page.body)
            records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
            if not isinstance(records, list):
                raise ValueError("API page must be an array or an object with results")
            yield page
            if len(records) < limit:
                return
            skip += limit

# Kept as a public compatibility alias for the Phase 1 Houses slice.
HousesApiClient = ApiClient
