"""Local single-workspace Phase 1 application. No dataset writes or background agent."""
from __future__ import annotations

import os
import hashlib
from collections import OrderedDict
from datetime import date
from pathlib import Path
from threading import Lock
from time import monotonic

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .config import load_local_environment
from .fuseki import DEFAULT_FUSEKI_QUERY_URL, FUSEKI_QUERY_URL_ENV, FusekiQueryClient
from .research_collaborator import ResearchRun, create_collaborator
from .research_tools import ResearchTools, CATALOGUE, ToolTask
from .research_adapter import ClosedModel, ResearchAdapter, OperationRequest, OperationEnvelope, ROOT
from .vocabulary import supported_predicates


class BriefInput(ClosedModel):
    brief: str = Field(min_length=1, max_length=2000)
    requestId: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class StepInput(ClosedModel):
    version: int = Field(ge=0)


class MessageInput(ClosedModel):
    text: str = Field(min_length=1, max_length=2000)
    sectionId: str | None = None
    requestId: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class DiagnosticInput(ClosedModel):
    requestId: str = Field(pattern=r"^[a-f0-9]{32}$")
    operation: str = Field(min_length=1, max_length=100)
    diagnostic: str = Field(min_length=1, max_length=4000)


def create_app(*, planner_factory=create_collaborator, client_factory=None, reporting_date=None, run_factory=ResearchRun):
    load_local_environment(ROOT)
    application = FastAPI(title="Parliamentary Research · Draft workspace", docs_url=None, redoc_url=None)
    assets = Path(__file__).parent / "research_ui"
    application.mount("/assets", StaticFiles(directory=assets), name="assets")
    runs, registry_lock = OrderedDict(), Lock()
    start_requests = {}
    predicates = supported_predicates(ROOT / "ontology")
    query_url = os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL)
    username, password = os.getenv("OIR_FUSEKI_USER"), os.getenv("OIR_FUSEKI_PASSWORD")
    endpoint_id = "injected-test-client" if client_factory else "query-endpoint-sha256:" + hashlib.sha256(query_url.encode()).hexdigest()

    def client():
        return (client_factory() if client_factory else FusekiQueryClient(
            query_url, username=username, password=password))

    def lookup(run_id):
        with registry_lock:
            saved = runs.get(run_id)
            if saved is None or monotonic() - saved[0].created > 3600:
                raise HTTPException(404, "Research expired or not found. Export within one hour; runs are in memory only.")
            return saved

    @application.middleware("http")
    async def security_headers(request, call_next):
        # Local same-origin workspace. No arbitrary remote callers or active
        # markup from model/dataset output; export/evidence can contain names.
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Use the same-origin research workspace."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @application.get("/")
    def index():
        return FileResponse(assets / "index.html")

    @application.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    @application.get("/contracts")
    def contracts():
        from .query_evidence import AcceptedEvidence
        return {"request": OperationRequest.model_json_schema(), "envelope": OperationEnvelope.model_json_schema(),
                "queryServiceEvidence": AcceptedEvidence.model_json_schema(),
                "researchCatalogue": CATALOGUE, "researchQueryTask": ToolTask.model_json_schema()}

    @application.post("/runs", status_code=201)
    def prepare(payload: BriefInput):
        if not payload.brief.strip():
            raise HTTPException(422, "Describe a research objective.")
        request_fingerprint = hashlib.sha256(payload.brief.encode()).hexdigest()
        if payload.requestId:
            with registry_lock:
                registration = start_requests.get(payload.requestId)
                if registration and registration[1] != request_fingerprint:
                    raise HTTPException(409, "That request id was already used for a different question.")
                prior_id = registration[0] if registration else None
                prior = runs.get(prior_id) if prior_id else None
            if prior and monotonic() - prior[0].created <= 3600:
                # Never hold the global run registry while waiting for an
                # individual run's long-running model/compiler lock.
                with prior[1]:
                    return prior[0].view()
        try:
            fixed_date = reporting_date or date.fromisoformat(os.getenv("OIR_NLQ_AS_OF_DATE", date.today().isoformat()))
        except ValueError as error:
            raise HTTPException(503, "OIR_NLQ_AS_OF_DATE must be an ISO date.") from error
        # Planning has no query client and cannot dispatch RDF operations.
        run = (run_factory(payload.brief, fixed_date, None, planner_factory, defer_planning=True)
               if run_factory is ResearchRun else run_factory(payload.brief, fixed_date, None, planner_factory))
        adapter_type = ResearchTools if isinstance(run, ResearchRun) else ResearchAdapter
        run.adapter = adapter_type(None, predicates, context_id=run.id, endpoint_id=endpoint_id)
        duplicate = None
        with registry_lock:
            for key, (old, _) in list(runs.items()):
                if monotonic() - old.created > 3600:
                    del runs[key]
            for request_id, (run_id, _) in list(start_requests.items()):
                if run_id not in runs:
                    del start_requests[request_id]
            registration = start_requests.get(payload.requestId) if payload.requestId else None
            if registration and registration[1] != request_fingerprint:
                raise HTTPException(409, "That request id was already used for a different question.")
            prior_id = registration[0] if registration else None
            duplicate = runs.get(prior_id) if prior_id else None
            if duplicate is None:
                if len(runs) >= 32:
                    raise HTTPException(429, "Local research capacity reached. Existing reports are preserved; try after expiry.")
                runs[run.id] = (run, Lock())
                if payload.requestId:
                    start_requests[payload.requestId] = (run.id, request_fingerprint)
        if duplicate:
            with duplicate[1]:
                return duplicate[0].view()
        return run.view()

    def has_work(run):
        check = getattr(run, "has_work", None)
        if callable(check):
            return check()
        # The original ResearchRun factory predates the processing contract;
        # retain its bounded-step HTTP compatibility without changing its API.
        return any(task.get("state") == "Pending" for task in run.tasks)

    def processing_view(run):
        view = getattr(run, "processing_view", None)
        if callable(view):
            return view()
        pending = next((task for task in run.tasks if task.get("state") == "Pending"), None)
        task_states = [task.get("state") for task in run.tasks]
        state = "ready" if pending else (
            "completed_with_findings" if task_states and all(value == "Validated" for value in task_states)
            else "completed_with_unanswered")
        return {"state": state, "label": {"ready": "Ready to continue",
                "completed_with_findings": "Completed with findings",
                "completed_with_unanswered": "Completed with unanswered questions"}[state],
            "active": False, "phase": None, "phaseLabel": None, "activeOperation": None,
            "elapsedSeconds": 0, "phaseElapsedSeconds": 0, "lastDurationSeconds": None,
            "requestId": None, "stages": [], "targetSectionIds": [],
            "nextPhase": "retrieving" if pending else None,
            "nextOperation": (pending.get("title") or pending.get("request", {}).get("factualRequest")) if pending else None}

    def seed_step(run):
        next_step = getattr(run, "next_processing", None)
        if callable(next_step):
            phase, operation = next_step()
            return (phase, operation) if phase else ("assessing", "Reviewing research outcomes")
        pending = next((task for task in run.tasks if task.get("state") == "Pending"), None)
        return "retrieving", (pending.get("title") or pending.get("request", {}).get("factualRequest")
                              if pending else "Retrieving parliamentary records")

    @application.get("/runs/{run_id}")
    def state(run_id: str):
        run, lock = lookup(run_id)
        with lock:
            return run.view()

    @application.get("/runs/{run_id}/progress")
    def progress(run_id: str):
        # This endpoint intentionally does not acquire the research-state lock.
        # Long model/compiler calls hold that lock so versioned mutations remain
        # serial, but their read-only operation snapshot must stay inspectable.
        run, _ = lookup(run_id)
        return processing_view(run)

    @application.post("/runs/{run_id}/diagnostics")
    def diagnostic(run_id: str, payload: DiagnosticInput):
        run, _ = lookup(run_id)
        return run.record_client_diagnostic(payload.requestId, payload.operation, payload.diagnostic)

    @application.post("/runs/{run_id}/step")
    def step(run_id: str, payload: StepInput):
        run, lock = lookup(run_id)
        with lock:
            if payload.version != run.version or not has_work(run):
                return run.view()
            phase, operation = seed_step(run)
            begin_processing = getattr(run, "begin_processing", None)
            request_id = begin_processing(phase, operation) if callable(begin_processing) else None
            class LazyClient:
                instance = None

                def query(self, sparql):
                    if self.instance is None:
                        self.instance = client()
                    return self.instance.query(sparql)

                def close(self):
                    close = getattr(self.instance, "close", None)
                    if close:
                        close()

            query_client = LazyClient()
            try:
                # Configuration/connection setup errors are captured at the
                # actual read boundary too, never mistaken for empty evidence.
                run.adapter.client = query_client
                run.step(payload.version)
            finally:
                query_client.close()
                run.adapter.client = None
                finish_processing = getattr(run, "finish_processing", None)
                processing = finish_processing(request_id) if callable(finish_processing) else processing_view(run)
            result = run.view()
            result["processing"] = processing
            return result

    @application.get("/runs/{run_id}/evidence/{evidence_id}")
    def evidence(run_id: str, evidence_id: str):
        run, lock = lookup(run_id)
        with lock:
            if evidence_id not in run.evidence:
                raise HTTPException(404, "Evidence not found.")
            return run.evidence[evidence_id]

    @application.post("/runs/{run_id}/messages")
    def message(run_id: str, payload: MessageInput):
        run, lock = lookup(run_id)
        with lock:
            if not payload.text.strip():
                raise HTTPException(422, "Write a research question or revision request.")
            if payload.requestId and payload.requestId in run.message_requests:
                return run.view()
            request_id = run.begin_processing("understanding", payload.text)
            try:
                run.message(payload.text, payload.sectionId, payload.requestId)
            except ValueError as error:
                status = 409 if run.plan_pending else 429
                raise HTTPException(status, str(error)) from error
            finally:
                processing = run.finish_processing(request_id)
            result = run.view()
            result["processing"] = processing
            return result

    @application.get("/runs/{run_id}/archive")
    def archive(run_id: str):
        run, lock = lookup(run_id)
        with lock:
            return {"state": run.view(), "evidence": run.evidence, "modelCalls": getattr(run, "modelCalls", []),
                    "clientDiagnostics": getattr(run, "client_diagnostics", [])}

    @application.get("/runs/{run_id}/report.md", response_class=PlainTextResponse)
    def export(run_id: str):
        run, lock = lookup(run_id)
        with lock:
            return PlainTextResponse(run.markdown(), headers={"Content-Disposition": 'attachment; filename="parliamentary-research.md"'})

    return application


app = create_app()
