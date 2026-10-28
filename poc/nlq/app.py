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
from .stage_a import parse_stage_a_question
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
               result_notice: str | None = None,
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
            "result_notice": result_notice,
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
            "id": fact["id"], "description": fact.get("predicate", fact.get("association", fact.get("joinKey", fact["id"]))),
            "subjectTypes": [fact["subjectType"]], "objectTypes": [fact["objectType"]],
            "filters": [], "status": "Executable for the bounded composable query slices",
        } for fact in facts.values()]
        return templates.TemplateResponse(request, "capabilities.html", {
            "request": request, "capabilities": capabilities,
            "temporal_constraints": ["previousTerm(Dail, asOf) using date evidence", "Separate dated party-membership evidence episodes", "Inclusive calendar-day overlap for accepted Member office holdings"],
            "answer_shapes": [{"kind": "entities", "description": "Distinct Member or reviewed enduring affiliation identities with readable labels and separate supporting episodes."}],
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
                is_q06 = bool(outcome.plan and outcome.plan.get("answer", {}).get("referent") == "affiliation")
                is_debate = bool(outcome.plan and outcome.plan.get("referents", {}).get("sitting", {}).get("type") == "DebateSitting")
                is_q35 = bool(outcome.plan and outcome.plan.get("referents", {}).get("holding", {}).get("type") == "OfficeHolding")
                is_q23 = bool(outcome.plan and outcome.plan.get("referents", {}).get("participation", {}).get("type") == "BillParticipation")
                parsed_stage_a = parse_stage_a_question(question)
                stage_a_family = (outcome.plan.get("family") if outcome.plan else
                                  parsed_stage_a.family if parsed_stage_a else None)
                is_stage_a = stage_a_family is not None
                member_mention = outcome.plan.get("referents", {}).get("member", {}).get("mention", "the named Member") if is_q06 else None
                q35_office = outcome.plan.get("referents", {}).get("office", {}) if is_q35 else {}
                q35_interval = outcome.plan.get("constraints", [{}])[0].get("value", {}) if is_q35 else {}
                q23_member = outcome.plan.get("referents", {}).get("member", {}).get("mention", "the named Member") if is_q23 else None
                q35_summary = (
                    f"Find each locally evidenced accepted {q35_office.get('label', q35_office.get('mention', 'office'))} "
                    f"holding overlapping {q35_interval.get('start', 'the requested start')} through "
                    f"{q35_interval.get('end', 'the requested end')}, preserving separate holding episodes. "
                    "The development dataset does not establish complete historical coverage."
                ) if is_q35 else None
                q23_summary = (
                    f"Find distinct Bills with a recorded sponsor Participation whose participant-person IRI "
                    f"exactly matches the resolved local Member identity for {q23_member}. Include every "
                    "recorded participation regardless of primary status and preserve its source evidence."
                ) if is_q23 else None
                stage_a_summaries = {
                    "member_lookup": "Resolve the grounded Member name against local Member identities without guessing.",
                    "previous_service": "Check Dáil membership in the previous term selected from House date evidence at the supplied as-of date.",
                    "dail_duration": "Calculate the union of dated Dáil membership episodes and preserve gaps.",
                    "term_count": "Count distinct Dáil term resources or distinct Dáil terms served, according to the requested referent.",
                    "seanad_entry": "Find the earliest dated Seanad membership episode and retain later term episodes as separate evidence.",
                    "seanad_representation": "Resolve the requested Seanad term and report its source-provided representation designation.",
                    "current_collection": "Evaluate dated parliamentary collection membership at the supplied as-of date; Independent remains a status, not a political party.",
                    "committee_boolean": "Check Member committee service against the uniquely dated current Committee incarnation.",
                    "committee_count": "Count distinct Committee resource identities rather than membership records.",
                    "house_terms": "List Dáil HouseTerm date evidence, distinguishing absent end dates from dated ends.",
                    "dail_all": "Return every distinct matching Member identity with Dáil membership evidence.",
                }
                summary = (stage_a_summaries.get(stage_a_family) if is_stage_a else None) or (f"Find {member_mention}’s distinct enduring political affiliations, grouped by reviewed local identity."
                           if is_q06 else ("Find the requested actual DebateSitting and its official record link."
                                             if is_debate else
                                             (q35_summary if is_q35 else
                                              (q23_summary if is_q23 else "Find distinct Members who represented this constituency in the previous Dáil."))))
                if outcome.status == "success":
                    return render(request, question=question, mode=mode,
                                  interpretation=summary, plan_json=plan_json,
                                    plan_heading="Validated composable query plan" if outcome.plan else None,
                                    plan_explanation={"summary": summary, "validated": bool(outcome.plan),
                                                         "answer_text": ("Distinct political-affiliation identities with separate supporting membership episodes."
                                                                         if is_q06 else ("Yes/no based on an actual DebateSitting, not a dated written-answer record."
                                                                                         if is_debate and outcome.result.kind == "ask" else
                                                                                         "Readable sitting date and official debate record link."
                                                                                         if is_debate else
                                                                                         "Member names with exact start/end dates for every separate accepted holding; open ends are identified explicitly."
                                                                                         if is_q35 else
                                                                                         ("One row per Bill identity, with English short title, recorded sponsorship evidence, and source-backed number/year/link where available."
                                                                                           if is_q23 else ("Stage A typed family result using reviewed RDF ownership, with identity and date qualifications preserved." if is_stage_a else "Distinct Members, displayed by name."))))},
                                   sparql=outcome.sparql, result=outcome.result,
                                    result_notice=(outcome.diagnostic if is_stage_a else
                                                   "Bill graphs are optional. These rows show recorded local sponsorship evidence; the dataset does not certify complete historical coverage."
                                                   if is_q23 else None),
                                  debug_output=outcome.result.raw_json if outcome.result else None,
                                   debug_source="Fuseki")
                if is_stage_a:
                    message = outcome.diagnostic or "The local dataset does not contain enough reviewed evidence to answer this Stage A question."
                    resolution_ref = (outcome.plan.get("referents", {}).get("committee", {})
                                      if outcome.plan and outcome.plan.get("referents", {}).get("committee", {}).get("resolution") == "ambiguous"
                                      else outcome.plan.get("referents", {}).get("member", {}) if outcome.plan else {})
                    entity_outcomes = ()
                    if resolution_ref.get("resolution") == "ambiguous":
                        entity_outcomes = tuple({"type": resolution_ref.get("type", "Member"),
                                                 "status": "ambiguous", "candidates": outcome.candidates}
                                                for _ in (0,))
                    return render(request, question=question, mode=mode, error=message,
                                  interaction_status=outcome.status, plan_json=plan_json,
                                   plan_heading="Validated composable query plan" if outcome.plan else None,
                                   plan_explanation=({"summary": summary, "validated": True} if outcome.plan else None),
                                  sparql=outcome.sparql, result=outcome.result,
                                  entity_outcomes=entity_outcomes,
                                  debug_output=getattr(outcome, "debug_output", None) or (outcome.result.raw_json if outcome.result else None),
                                  debug_source=getattr(outcome, "debug_source", None) or ("Fuseki" if outcome.sparql else "Structured planner"))
                messages = {
                    "unsupported_capability": "This query form is not supported; no answer query was run.",
                    "source_data_unavailable": "The local source data does not contain enough House-term evidence to resolve the previous Dáil.",
                    "insufficient_holding_evidence": "Some accepted local office holdings lack valid start/end date evidence. Any rows below show only holdings whose dates can be verified.",
                    "not_found": "No constituency with that name was found in the previous Dáil.",
                    "ambiguous": "More than one constituency matches in the previous Dáil; no identity was selected.",
                    "unsupported_mapping": "A required relation or query mapping is unsupported; no answer was returned.",
                    "missing_identity_link": "Parliamentary party-membership evidence exists, but the reviewed local enduring-identity link is missing.",
                }
                if is_q23:
                    if outcome.status == "missing_sponsorship_evidence":
                        message = "Bill sponsorship evidence is missing from the local dataset; this is not a confirmed negative answer."
                    elif outcome.status == "source_data_unavailable":
                        message = (
                            "Local Member identity evidence could not be read."
                            if outcome.plan.get("referents", {}).get("member", {}).get("resolution") == "source_data_unavailable"
                            else "The local dataset contains no matching sponsorship evidence for this Member, and its historical coverage is not certified complete."
                        )
                    elif outcome.status == "incomplete_primary_status_evidence":
                        message = "Some Participation records do not contain isPrimarySponsor; those sponsorship statuses are shown as Unknown."
                    elif outcome.status == "incomplete_display_evidence":
                        message = "Some Bills lack the required English short-title evidence or have conflicting display metadata; affected rows are marked explicitly."
                    elif outcome.status == "conflicting_sponsorship_evidence":
                        message = "Conflicting sponsorship evidence was preserved and called out in the result; no conflicting value was selected silently."
                    elif outcome.status == "incomplete_sponsorship_evidence":
                        message = "The result reached the local safety cap; additional sponsorship evidence may be omitted."
                    elif outcome.status == "not_found":
                        message = "No matching local Member record was found."
                    elif outcome.status == "ambiguous":
                        message = "More than one local Member record matches; no Member was selected."
                    else:
                        message = messages.get(outcome.status, outcome.diagnostic)
                elif outcome.status == "source_data_unavailable" and is_q06:
                    message = "The local dataset has no usable dated party-membership evidence for this Member."
                elif outcome.status == "source_data_unavailable" and is_debate:
                    message = "No matching actual sitting was found. The local dataset does not certify complete coverage for this date, so absence cannot be reported as a confirmed No."
                elif outcome.status == "source_data_unavailable" and is_q35:
                    if (outcome.sparql and outcome.diagnostic
                            and "No accepted local holding is recorded overlapping" in outcome.diagnostic):
                        message = ("No accepted dated holding in the local dataset overlaps the requested interval. "
                                   "This development capture is incomplete, so absence is not a confirmed historical negative.")
                    elif outcome.sparql:
                        message = "The local holding query and its typed date evidence could not be reconciled; no historical answer was returned."
                    elif outcome.diagnostic and "No accepted Member-owned OfficeHolding" in outcome.diagnostic:
                        message = "No accepted local office-holding records are available for this office in the dataset."
                    else:
                        message = "The local office registry or accepted holding evidence could not be read well enough to answer."
                elif outcome.status == "insufficient_holding_evidence" and is_q35:
                    message = messages["insufficient_holding_evidence"]
                elif outcome.status == "not_found" and is_q35:
                    message = "The office name could not be matched to a reviewed local NamedOffice identity."
                elif outcome.status == "ambiguous" and is_q35:
                    message = "More than one reviewed local office identity matches; no office was selected."
                elif outcome.status == "not_found" and is_q06:
                    message = "No matching local Member record was found."
                elif outcome.status == "ambiguous" and is_q06:
                    message = "More than one local Member record matches; no Member was selected."
                else:
                    message = messages.get(outcome.status, outcome.diagnostic)
                resolution_ref = (
                    outcome.plan.get("referents", {}).get("office", {}) if is_q35 and outcome.plan else
                    outcome.plan.get("referents", {}).get("member", {}) if (is_q06 or is_q23) and outcome.plan else {}
                )
                if is_stage_a and outcome.plan:
                    resolution_ref = (outcome.plan.get("referents", {}).get("committee", {})
                                      if stage_a_family == "committee_boolean" and
                                      outcome.plan.get("referents", {}).get("committee")
                                      else outcome.plan.get("referents", {}).get("member", {}))
                entity_outcomes = ()
                if resolution_ref.get("resolution") == "ambiguous":
                    entity_type = "NamedOffice" if is_q35 else ("Committee" if resolution_ref.get("type") == "Committee" else "Member")
                    entity_outcomes = ({
                        "type": entity_type,
                        "label": resolution_ref.get("mention", "the requested entity"),
                        "resolution": "ambiguous", "candidates": resolution_ref.get("candidates", []),
                    },)
                return render(
                    request, question=question, mode=mode,
                    interpretation=summary if outcome.plan else None, plan_json=plan_json,
                    plan_heading=("Validated composable query plan" if outcome.sparql is not None else
                                  "Proposed composable query plan") if outcome.plan else None,
                    error=message,
                    interaction_status=outcome.status,
                    entity_outcomes=entity_outcomes,
                    result=outcome.result,
                    result_notice=("Bill graphs are optional. These rows show recorded local sponsorship evidence; the dataset does not certify complete historical coverage."
                                   if is_q23 and outcome.result else None),
                    debug_output=format_debug_payload({"diagnostic": outcome.diagnostic,
                                                       "candidates": outcome.candidates}),
                    debug_message=("The read-only answer query ran, but returned no matching result."
                                   if outcome.sparql is not None else
                                   "No answer query was executed after this resolution failure."),
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
