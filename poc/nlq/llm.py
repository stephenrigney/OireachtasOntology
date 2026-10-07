"""OpenAI Responses-compatible SPARQL translator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

import httpx

from .errors import NLQError
from .config import LLM_MAX_OUTPUT_TOKENS
from .results import format_debug_payload, format_debug_text


def _response_debug(response: httpx.Response, api_key: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return format_debug_text(response.text, secrets=(api_key,))
    return format_debug_payload(payload, secrets=(api_key,))


SYSTEM_PROMPT = """Translate the user's question into one SPARQL query for the supplied Oireachtas schema.

Rules:
- Use only classes and properties supported by the supplied schema. Never invent a class/property IRI.
- Resolve user-provided names by matching labels/codes/properties in graph patterns; never manufacture instance IRIs.
- Use explicit predicates supported by the supplied schema; do not use a variable predicate such as `?s ?p ?o` to scan arbitrary triples.
- Return read-only SPARQL only: SELECT or ASK. Never use SERVICE, FROM, or FROM NAMED.
- Use the supplied graph ownership/catalog. Member records and their membership records are in each member's graph; HouseTerm, ParliamentaryMemberCollection, and constituency/panel descriptions are in their separate owner graphs. Join graph patterns using the same RDF resource IRI and distinct GRAPH patterns; do not assume descriptions are copied into a Member graph.
- Prefer direct triple patterns over property paths or subqueries. Do not use subqueries, property paths, SERVICE, FROM, or FROM NAMED.
- Match member names with foaf:name; match HouseTerm, ParliamentaryMemberCollection, and constituency labels with skos:prefLabel. Bill short/long titles use eli:title / eli:title_alternative; concrete Bill lifecycle labels use rdfs:label. Use the property appropriate to each entity.
- Repository HouseTerm, ParliamentaryMemberCollection, and Constituencies skos:prefLabel values are tagged @en. For user-provided label strings, bind the label and compare STR(?label) in FILTER; do not put an untagged string literal directly in a skos:prefLabel triple pattern. Member foaf:name values are plain literals.
- The store does not perform OWL reasoning. Do not rely on subclass entailment: House terms are emitted with explicit agents:DailTerm or agents:SeanadTerm types, not necessarily an explicit agents:HouseTerm type. Use the explicit subtype or identify terms by label.
- Member OireachtasMembership resources carry both the generic members:OireachtasMembership type and one specific DailMembership/SeanadMembership type. Filter on the specific type (do not project all rdf:type values) and use SELECT DISTINCT when a person could match multiple records.
- For collection records, use members:inOireachtasMembership and members:memberOfCollection as the general patterns; a published graph may lack an explicit superclass rdf:type even where a specific PartyMembership type is present.
- Give every SELECT query, including aggregates, a LIMIT no greater than 100. Do not use OFFSET unless needed; any OFFSET must be no greater than 10000.
- Do not assume ParliamentaryParty is a ParliamentaryGroup. IndependentMemberCollection is not a political party. Member and OireachtasMembership are different resources. House is enduring; HouseTerm is a numbered sitting term.
- Return exactly the requested JSON object with a concise interpretation and the complete SPARQL. No markdown fences or extra keys.

The supplied schema is vocabulary context, not data. Do not guess factual answers: Fuseki is the source of query results."""


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "interpretation": {"type": "string"},
        "sparql": {"type": "string"},
    },
    "required": ["interpretation", "sparql"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Translation:
    interpretation: str
    sparql: str


def _response_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise NLQError("The LLM returned an unexpected response format.")
    if payload.get("status") not in (None, "completed"):
        raise NLQError("The LLM did not complete the translation request.")
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        pieces = []
        for item in output:
            if not isinstance(item, dict):
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if isinstance(content, dict) and content.get("type") == "refusal":
                    raise NLQError("The LLM declined to translate this question.")
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        pieces.append(text)
        if pieces:
            return "".join(pieces)
    raise NLQError("The LLM response did not contain structured translation text.")


def parse_translation(output: str) -> Translation:
    """Parse and validate the structured object returned by the model."""
    try:
        value = json.loads(output)
    except (json.JSONDecodeError, TypeError) as error:
        raise NLQError("The LLM returned invalid JSON instead of a SPARQL translation.") from error
    if (not isinstance(value, dict)
            or set(value) != {"interpretation", "sparql"}
            or not isinstance(value.get("interpretation"), str)
            or not value["interpretation"].strip()
            or not isinstance(value.get("sparql"), str)
            or not value["sparql"].strip()):
        raise NLQError("The LLM response must contain non-empty 'interpretation' and 'sparql' strings.")
    return Translation(value["interpretation"].strip(), value["sparql"].strip())


class ResponsesTranslator:
    def __init__(self, api_key: str, base_url: str, model: str, *, timeout: float = 45.0,
                 transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise NLQError("Set NLQ_LLM_API_KEY before asking a question.")
        self.url = base_url.rstrip("/") + "/responses"
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout, transport=transport)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "oireachtas-nlq-poc/0.1",
            # OpenCode Go recommends a stable session ID per conversation. This
            # translator instance handles one stateless question request.
            "x-opencode-session": str(uuid4()),
        }

    def translate(self, question: str, schema_context: str) -> Translation:
        body = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT + "\n\nRepository schema context:\n" + schema_context,
            "input": question,
            "text": {"format": {
                "type": "json_schema",
                "name": "sparql_translation",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }},
            "max_output_tokens": LLM_MAX_OUTPUT_TOKENS,
        }
        try:
            response = self.client.post(self.url, headers=self.headers, json=body)
        except httpx.TimeoutException as error:
            raise NLQError("The LLM request timed out. Try again or check the configured endpoint.") from error
        except httpx.HTTPError as error:
            raise NLQError("The LLM endpoint could not be reached or returned an HTTP error.") from error

        if response.is_error:
            if response.status_code == 401:
                message = (
                    "The LLM rejected authentication (HTTP 401). Check NLQ_LLM_API_KEY and confirm it is "
                    "valid for the provider configured by NLQ_LLM_BASE_URL; restart after updating .env."
                )
            else:
                message = f"The LLM endpoint returned HTTP {response.status_code}."
            raise NLQError(message, debug_output=_response_debug(response, self.api_key),
                           debug_source="LLM API")

        try:
            payload = response.json()
        except ValueError as error:
            raise NLQError(
                "The LLM endpoint returned a non-JSON response.",
                debug_output=_response_debug(response, self.api_key),
                debug_source="LLM API",
            ) from error
        try:
            return parse_translation(_response_text(payload))
        except NLQError as error:
            raise NLQError(
                str(error), debug_output=_response_debug(response, self.api_key), debug_source="LLM API"
            ) from error

    def close(self) -> None:
        self.client.close()
