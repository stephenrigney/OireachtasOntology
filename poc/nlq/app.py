"""Minimal server-rendered browser for the experimental NLQ-to-SPARQL flow."""

from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from datetime import date

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import load_local_environment
from .errors import NLQError
from .fuseki import (
    DEFAULT_FUSEKI_QUERY_URL,
    FUSEKI_QUERY_URL_ENV,
    FusekiQueryClient,
    FusekiReadiness,
)
from .llm import ResponsesTranslator
from .pipeline import process_question
from .composable_plan import execute_question
from .results import QueryResult, format_debug_payload
from .schema import build_schema_context
from .vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = Path(__file__).resolve().parent / "templates"
logger = logging.getLogger(__name__)


def create_app(*, repository_root: Path = ROOT) -> FastAPI:
    load_local_environment(repository_root)
    app = FastAPI(title="Oireachtas NLQ POC", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES))
    schema_context = build_schema_context(repository_root / "ontology")
    predicate_vocabulary = supported_predicates(repository_root / "ontology")

    def check_fuseki_readiness() -> FusekiReadiness:
        client = None
        try:
            client = FusekiQueryClient(
                os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
                username=os.getenv("OIR_FUSEKI_USER"),
                password=os.getenv("OIR_FUSEKI_PASSWORD"),
            )
            return client.readiness()
        except NLQError as error:
            logger.info("Read-only Fuseki readiness check failed: %s", error)
            return FusekiReadiness(
                state="unavailable",
                has_triples=False,
                sources=tuple((name, False) for name in ("Houses", "Parties", "Constituencies", "Members", "Bills")),
                message=f"Could not check Fuseki readiness: {error}",
            )
        except Exception:
            logger.exception("Unexpected failure during read-only Fuseki readiness check")
            return FusekiReadiness(
                state="unavailable",
                has_triples=False,
                sources=tuple((name, False) for name in ("Houses", "Parties", "Constituencies", "Members", "Bills")),
                message="Could not check Fuseki readiness; see the server log for details.",
            )
        finally:
            if client is not None:
                client.close()

    def render(request: Request, *, question: str = "", interpretation: str | None = None,
               sparql: str | None = None, result: QueryResult | None = None,
               ambiguity=None,
               error: str | None = None, debug_output: str | None = None,
               debug_message: str | None = None, debug_source: str | None = None,
               readiness: FusekiReadiness | None = None,
               mode: str = "phase2", interaction_status: str | None = None,
               plan_json: str | None = None, plan_heading: str | None = None,
               entity_outcomes: tuple[dict, ...] = (), plan_explanation=None):
        if readiness is None:
            readiness = check_fuseki_readiness()
        return templates.TemplateResponse(request, "index.html", {
            "question": question,
            "interpretation": interpretation,
            "sparql": sparql,
            "result": result,
            "ambiguity": ambiguity,
            "error": error,
            "debug_output": debug_output,
            "debug_message": debug_message,
            "debug_source": debug_source,
            "readiness": readiness,
            "mode": mode,
            "interaction_status": interaction_status,
            "plan_json": plan_json,
            "plan_heading": plan_heading,
            "entity_outcomes": entity_outcomes,
            "plan_explanation": plan_explanation,
        })

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request)

    @app.get("/capabilities", response_class=HTMLResponse)
    def capabilities(request: Request):
        contract = json.loads((repository_root / "poc/specs/composable-query-plan-contract.json").read_text())
        facts = {item["id"]: item for item in contract["relations"]}
        capabilities = [{
            "id": fact["id"], "description": fact["predicate"],
            "subjectTypes": [fact["subjectType"]], "objectTypes": [fact["objectType"]],
            "filters": [], "status": "Executable for the previous-Dáil representation slice",
        } for fact in facts.values()]
        return templates.TemplateResponse(request, "capabilities.html", {
            "request": request, "capabilities": capabilities,
            "temporal_constraints": ["previousTerm(Dail, asOf) using date evidence"],
            "answer_shapes": [{"kind": "entities", "description": "Distinct Member identities with readable names."}],
        })

    @app.post("/ask", response_class=HTMLResponse)
    def ask(request: Request, question: str = Form(...), mode: str = Form("phase2")):
        question = question.strip()
        if not question:
            return render(request, question=question, mode=mode,
                          error="Enter a question to continue.")
        if len(question) > 2000:
            return render(request, question=question[:2000], mode=mode,
                          error="Questions must be 2,000 characters or fewer.")
        if mode not in {"phase1", "phase2"}:
            return render(request, question=question, mode="phase2",
                          error="Choose a supported development query path.")

        if mode == "phase2":
            fuseki = None
            try:
                try:
                    as_of = date.fromisoformat(os.getenv("OIR_NLQ_AS_OF_DATE", date.today().isoformat()))
                except ValueError:
                    return render(request, question=question, mode=mode,
                                  error="OIR_NLQ_AS_OF_DATE must be an ISO calendar date.")
                fuseki = FusekiQueryClient(
                    os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
                    username=os.getenv("OIR_FUSEKI_USER"),
                    password=os.getenv("OIR_FUSEKI_PASSWORD"),
                )
                outcome = execute_question(
                    question, as_of=as_of, fuseki=fuseki,
                    supported_predicates=predicate_vocabulary,
                )
                plan_json = format_debug_payload(outcome.plan) if outcome.plan else None
                summary = "Find distinct Members who represented this constituency in the previous Dáil."
                if outcome.status == "success":
                    return render(request, question=question, mode=mode,
                                  interpretation=summary, plan_json=plan_json,
                                  plan_heading="Validated composable query plan",
                                  plan_explanation={"summary": summary, "validated": True,
                                                    "answer_text": "Distinct Members, displayed by name."},
                                  sparql=outcome.sparql, result=outcome.result,
                                  debug_output=outcome.result.raw_json if outcome.result else None,
                                  debug_source="Fuseki")
                messages = {
                    "unsupported_capability": "This query form is not supported; no answer query was run.",
                    "source_data_unavailable": "The local source data does not contain enough House-term evidence to resolve the previous Dáil.",
                    "not_found": "No constituency with that name was found in the previous Dáil.",
                    "ambiguous": "More than one constituency matches in the previous Dáil; no identity was selected.",
                    "unsupported_mapping": "A required relation or query mapping is unsupported; no answer was returned.",
                }
                return render(
                    request, question=question, mode=mode,
                    interpretation=summary if outcome.plan else None, plan_json=plan_json,
                    plan_heading="Proposed composable query plan" if outcome.plan else None,
                    error=messages.get(outcome.status, outcome.diagnostic),
                    interaction_status=outcome.status,
                    debug_output=format_debug_payload({"diagnostic": outcome.diagnostic,
                                                       "candidates": outcome.candidates}),
                    debug_message="No answer query was executed after this resolution failure.",
                    debug_source="Query planning / entity resolution",
                )
            except Exception:
                logger.exception("Unexpected failure in composable Query Service plan")
                return render(
                    request, question=question, mode=mode,
                    error="An unexpected problem prevented the query from being processed.",
                    interaction_status="execution_failure",
                    debug_message="See the server log for details.",
                    debug_source="Structured query",
                )
            finally:
                if fuseki is not None:
                    fuseki.close()

        translation = None
        translator = fuseki = None
        phase = "LLM translation"

        def set_phase(current: str) -> None:
            nonlocal phase
            phase = current

        def remember_translation(current) -> None:
            nonlocal translation
            translation = current

        def remember_fuseki():
            nonlocal fuseki
            fuseki = FusekiQueryClient(
                os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
                username=os.getenv("OIR_FUSEKI_USER"),
                password=os.getenv("OIR_FUSEKI_PASSWORD"),
            )
            return fuseki

        try:
            translator = ResponsesTranslator(
                os.getenv("NLQ_LLM_API_KEY", ""),
                os.getenv("NLQ_LLM_BASE_URL", ""),
                os.getenv("NLQ_LLM_MODEL", ""),
            )
            outcome = process_question(
                question,
                translator=translator,
                fuseki_factory=remember_fuseki,
                schema_context=schema_context,
                supported_predicates=predicate_vocabulary,
                on_phase=set_phase,
                on_translation=remember_translation,
            )
            translation = outcome.translation
            if outcome.error is not None:
                phase = outcome.error_phase or phase
                raise outcome.error
            if outcome.ambiguity is not None:
                ambiguity_debug = format_debug_payload(outcome.ambiguity.as_dict())
                return render(
                    request,
                    question=question,
                    mode=mode,
                    ambiguity=outcome.ambiguity,
                    debug_message=(
                        "Local Member-name ambiguity was detected before SPARQL generation. "
                        "No answer query was sent to Fuseki."
                    ),
                    debug_output=ambiguity_debug,
                    debug_source="Local Member resolution",
                )
            safe_sparql = outcome.validated_sparql
            result = outcome.result
            debug_message = None
            if result.kind == "select" and not result.rows:
                debug_message = (
                    "Fuseki accepted the SELECT query but returned zero bindings. This is not a syntax error; "
                    "inspect the query and raw response below to check for a pattern mismatch or missing data."
                )
            elif result.kind == "ask" and result.boolean is False:
                debug_message = "Fuseki accepted the ASK query and returned false; inspect its graph pattern below."
            return render(request, question=question, mode=mode,
                          interpretation=translation.interpretation,
                          sparql=safe_sparql, result=result, debug_output=result.raw_json,
                          debug_message=debug_message, debug_source="Fuseki")
        except NLQError as error:
            if phase == "Member name resolution":
                debug_message = (
                    "Local Member-name resolution failed; no answer query was sent to Fuseki."
                )
            elif phase == "SPARQL validation":
                debug_message = "Generated SPARQL failed local syntax/safety validation and was not sent to Fuseki."
            elif phase == "Fuseki query":
                debug_message = "The SPARQL passed local validation, but the Fuseki query failed. The endpoint response is shown below when available."
            else:
                debug_message = "LLM translation failed; no SPARQL query was sent to Fuseki."
            debug_source = error.debug_source or (
                "LLM API" if phase == "LLM translation" else
                "Local Member resolution" if phase == "Member name resolution" else
                "Fuseki"
            )
            return render(request, question=question, mode=mode,
                          interpretation=translation.interpretation if translation else None,
                          sparql=translation.sparql if translation else None,
                          error=str(error), debug_output=error.debug_output,
                          debug_message=debug_message, debug_source=debug_source)
        except Exception:
            logger.exception("Unexpected failure in NLQ POC")
            return render(request, question=question, mode=mode,
                          interpretation=translation.interpretation if translation else None,
                          sparql=translation.sparql if translation else None,
                          error="An unexpected error prevented the question from being processed.",
                          debug_message=f"Unexpected failure during {phase}; see the server log for details.",
                          debug_source="LLM API" if phase == "LLM translation" else "Fuseki")
        finally:
            if translator is not None:
                translator.close()
            if fuseki is not None:
                fuseki.close()

    return app


app = create_app()
