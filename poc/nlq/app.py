"""Minimal server-rendered browser for the experimental NLQ-to-SPARQL flow."""

from __future__ import annotations

import logging
import os
from pathlib import Path

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
from .plan_pipeline import process_planned_question
from .plan_sparql import PlanSparqlGenerator
from .results import QueryResult, format_debug_payload
from .structured_planner import ResponsesPlanGenerator
from .schema import build_schema_context
from .vocabulary import supported_predicates
from .presentation import capability_catalogue, catalogue_metadata, explain_plan


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = Path(__file__).resolve().parent / "templates"
logger = logging.getLogger(__name__)


def create_app(*, repository_root: Path = ROOT) -> FastAPI:
    load_local_environment(repository_root)
    app = FastAPI(title="Oireachtas NLQ POC", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES))
    schema_context = build_schema_context(repository_root / "ontology")
    predicate_vocabulary = supported_predicates(repository_root / "ontology")
    phase2_sparql_generator = PlanSparqlGenerator(
        supported_predicates=predicate_vocabulary,
    )

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
        return templates.TemplateResponse(request, "capabilities.html", {
            "request": request, "capabilities": capability_catalogue(),
            **catalogue_metadata(),
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
            phase2_fuseki = None
            phase = "structured planner"

            def remember_phase(current: str) -> None:
                nonlocal phase
                phase = current

            def remember_phase2_fuseki():
                nonlocal phase2_fuseki
                phase2_fuseki = FusekiQueryClient(
                    os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
                    username=os.getenv("OIR_FUSEKI_USER"),
                    password=os.getenv("OIR_FUSEKI_PASSWORD"),
                )
                return phase2_fuseki

            def make_planner_generator():
                return ResponsesPlanGenerator(
                    os.getenv("NLQ_LLM_API_KEY", ""),
                    os.getenv("NLQ_LLM_BASE_URL", ""),
                    os.getenv("NLQ_LLM_MODEL", ""),
                )

            try:
                outcome = process_planned_question(
                    question,
                    planner_generator_factory=make_planner_generator,
                    plan_sparql_generator=phase2_sparql_generator,
                    fuseki_factory=remember_phase2_fuseki,
                    supported_predicates=predicate_vocabulary,
                    on_phase=remember_phase,
                )
                planner_result = outcome.planner_result
                plan_for_display = (
                    planner_result.plan or planner_result.draft_plan
                    if planner_result is not None else None
                )
                interpretation = (
                    plan_for_display.get("intent")
                    if isinstance(plan_for_display, dict) else None
                )
                entity_outcomes = tuple(
                    entity for entity in plan_for_display.get("entities", [])
                    if entity.get("resolution") in {"ambiguous", "unresolved"}
                ) if isinstance(plan_for_display, dict) else ()
                plan_heading = (
                    "Validated query plan" if planner_result and planner_result.plan
                    else "Planner draft (not validated)"
                ) if plan_for_display is not None else None
                plan_json = (
                    format_debug_payload(plan_for_display)
                    if plan_for_display is not None else None
                )
                plan_explanation = explain_plan(
                    plan_for_display, validated=bool(planner_result and planner_result.plan),
                    blocked_reason=(outcome.diagnostic if outcome.status != "success" else None),
                ) if isinstance(plan_for_display, dict) else None
                sparql = (
                    outcome.generation.sparql
                    if outcome.generation is not None and outcome.generation.generated
                    else None
                )
                messages = {
                    "unsupported_request": (
                        "This question or semantic combination is not supported by the current "
                        "Phase 2 query path. No answer query was run."
                    ),
                    "planner_failure": (
                        "The structured planner could not produce a usable query plan. "
                        "No answer query was run."
                    ),
                    "validation_failure": (
                        "The query plan or generated SPARQL did not pass validation. "
                        "No answer query was run."
                    ),
                    "execution_failure": (
                        "The validated query could not be completed by Fuseki. "
                        "Inspect the development details below."
                    ),
                }
                if outcome.status == "ambiguous_entity":
                    labels = ", ".join(
                        f"{entity.get('type', 'entity')} “{entity.get('label', '')}”"
                        for entity in entity_outcomes if entity.get("resolution") == "ambiguous"
                    )
                    message = (
                        f"More than one local match exists for {labels}. Add distinguishing "
                        "context; no record was selected and no answer query was run."
                        if labels else
                        "More than one local entity match remains. Add distinguishing context; "
                        "no record was selected and no answer query was run."
                    )
                elif outcome.status == "unresolved_entity":
                    labels = ", ".join(
                        f"{entity.get('type', 'entity')} “{entity.get('label', '')}”"
                        for entity in entity_outcomes if entity.get("resolution") == "unresolved"
                    )
                    message = (
                        f"No exact local match was found for {labels}. Check the name or whether "
                        "the relevant data is loaded. No answer query was run."
                        if labels else
                        "No exact local match was found for an entity in the question. "
                        "No answer query was run."
                    )
                elif outcome.status == "success":
                    result = outcome.result
                    if result.kind == "select" and not result.rows:
                        debug_message = (
                            "Fuseki accepted the generated SELECT query but returned zero bindings. "
                            "This is not a syntax error; inspect the query and response below."
                        )
                    elif result.kind == "ask" and result.boolean is False:
                        debug_message = "Fuseki accepted the ASK query and returned false."
                    else:
                        debug_message = None
                    return render(
                        request, question=question, mode=mode,
                        interpretation=interpretation, plan_json=plan_json,
                        plan_heading=plan_heading, sparql=sparql, result=result,
                        debug_output=outcome.debug_output,
                        debug_message=debug_message, debug_source=outcome.debug_source,
                        entity_outcomes=entity_outcomes, plan_explanation=plan_explanation,
                    )
                else:
                    message = messages.get(
                        outcome.status,
                        "The structured query could not be completed. No answer query was run.",
                    )

                debug_message = (
                    f"Phase 2 stopped during {outcome.debug_source or phase}. "
                    "The diagnostic is available in the development details."
                )
                return render(
                    request, question=question, mode=mode,
                    interpretation=interpretation, plan_json=plan_json,
                    plan_heading=plan_heading, sparql=sparql,
                    error=message, interaction_status=outcome.status,
                    debug_output=outcome.debug_output,
                    debug_message=debug_message,
                    debug_source=outcome.debug_source or "Structured query",
                    entity_outcomes=entity_outcomes, plan_explanation=plan_explanation,
                )
            except Exception:
                logger.exception("Unexpected failure in structured Phase 2 NLQ POC")
                return render(
                    request, question=question, mode=mode,
                    error="An unexpected problem prevented the structured query from being processed.",
                    interaction_status="planner_failure",
                    debug_message=f"Unexpected failure during {phase}; see the server log for details.",
                    debug_source="Structured query",
                )
            finally:
                if phase2_fuseki is not None:
                    phase2_fuseki.close()

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
