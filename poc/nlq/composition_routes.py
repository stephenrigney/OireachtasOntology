"""Isolated opt-in routes; /ask admission and execution are untouched."""

from collections import OrderedDict
from copy import deepcopy
from datetime import date
import json
import os
import re
from secrets import token_urlsafe, compare_digest
from threading import Lock
from time import monotonic

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .composition_kernel import validate_as_of
from .composition_transport import CompositionTransport, typed_json
from .composition_workflow import execute_confirmed, interpretation, propose, validate_scope
from .errors import NLQError
from .fuseki import DEFAULT_FUSEKI_QUERY_URL, FUSEKI_QUERY_URL_ENV
from .structured_planner import PlannerModelError


COOKIE = "oireachtas_composition_session"
TTL_SECONDS = 600
MAX_PENDING = 128
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def configured_date():
    try:
        return validate_as_of(os.getenv("OIR_NLQ_AS_OF_DATE", date.today().isoformat())).isoformat()
    except ValueError as error:
        raise ValueError("OIR_NLQ_AS_OF_DATE must be an ISO calendar date (YYYY-MM-DD).") from error


def install_composition_routes(app, render, *, proposer_factory=None, transport_factory=None):
    pending, evidence, attempts = OrderedDict(), OrderedDict(), OrderedDict()
    lock = Lock()

    def trim(store):
        now = monotonic()
        for token in list(store):
            if now - store[token]["created"] > TTL_SECONDS:
                del store[token]
        while len(store) > MAX_PENDING:
            store.popitem(last=False)

    def session(request):
        cookie = request.cookies.get(COOKIE, "")
        return cookie if TOKEN.fullmatch(cookie) else token_urlsafe(32)

    def page(request, *, owner=None, **kwargs):
        response = render(request, composition=True, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "same-origin"
        if owner:
            response.set_cookie(COOKIE, owner, httponly=True, samesite="strict",
                                secure=request.url.scheme == "https", max_age=TTL_SECONDS)
        return response

    def same_origin(request):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Cross-origin composition submission refused.")

    def present_execution(request, *, question, structured, report, result, confirmed=False, dashboard=False):
        """One evidence/result adapter shared by /ask and the comparison route."""
        owner = session(request)
        evidence_token = token_urlsafe(32)
        artifact = typed_json({"question": question, "request": structured, "report": report,
                               **({"confirmedRequest": structured} if confirmed else {})})
        byte_size = len(json.dumps(artifact, ensure_ascii=False).encode("utf-8"))
        if byte_size > MAX_EVIDENCE_BYTES:
            raise NLQError("Evidence storage byte budget exceeded; no partial answer returned.")
        with lock:
            evidence[evidence_token] = {"owner": owner, "artifact": artifact, "created": monotonic(), "bytes": byte_size}
            trim(evidence)
            retained = sum(item["bytes"] for item in evidence.values())
            while retained > MAX_EVIDENCE_BYTES:
                _, evicted = evidence.popitem(last=False)
                retained -= evicted["bytes"]
        status = ("clarification_required" if report["status"] == "ambiguous" else
                  "source_data_unavailable" if result is None else "answer")
        kwargs = dict(question=question, result=result, interpretation=interpretation(structured),
                      execution_attempted=bool(report["ledger"]), composition_report=artifact["report"],
                      composition_evidence_token=evidence_token, interaction_status=status,
                      composition_request=structured,
                      error=report.get("error") if result is None else None,
                      result_notice=f"Recorded evidence as of {structured['asOf']}; not a certified complete roster. Missing ends remain open-ended. Multiple source-recorded names are shown together for the same exact Member identity.")
        if confirmed:
            return page(request, owner=owner, **kwargs)
        response = render(request, composition_direct=not dashboard, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(COOKIE, owner, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", max_age=TTL_SECONDS)
        return response

    @app.get("/composition", response_class=HTMLResponse)
    def index(request: Request):
        return page(request)

    @app.post("/composition/propose", response_class=HTMLResponse)
    def proposal(request: Request, question: str = Form(...)):
        same_origin(request)
        question = question.strip()
        owner = session(request)
        generation = token_urlsafe(32)
        with lock:
            # Any new proposal attempt supersedes earlier browser state, including
            # an unsupported question or a failed planner call.
            for old in list(pending):
                if pending[old]["owner"] == owner:
                    del pending[old]
            attempts[owner] = {"generation": generation, "created": monotonic()}
            attempts.move_to_end(owner)
            trim(attempts)
        try:
            as_of = configured_date()
            structured = propose(question, as_of, proposer_factory)
            token = token_urlsafe(32)
            with lock:
                if attempts.get(owner, {}).get("generation") != generation:
                    raise ValueError("A newer question superseded this interpretation. Propose the current question again.")
                pending[token] = {"owner": owner, "question": question, "as_of": as_of,
                                  "request": deepcopy(structured), "created": monotonic()}
                trim(pending)
            return page(request, owner=owner, question=question,
                        composition_confirmation={"token": token, "text": interpretation(structured)})
        except (ValueError, NLQError, PlannerModelError) as error:
            return page(request, owner=owner, question=question[:2000],
                        interaction_status="unsupported_request", error=str(error))

    @app.post("/composition/confirm", response_class=HTMLResponse)
    async def confirm(request: Request):
        same_origin(request)
        form = await request.form()
        # No browser-supplied question, date, mentions, plan or hidden model draft
        # can override the server-held interpretation. Reject even extra fields.
        if set(form) != {"token", "decision"} or any(len(form.getlist(k)) != 1 for k in form):
            return page(request, error="Altered confirmation submission refused. Ask the original question again.")
        token, decision = form["token"], form["decision"]
        owner = request.cookies.get(COOKIE, "")
        with lock:
            trim(pending)
            saved = pending.get(token) if isinstance(token, str) else None
            if saved and TOKEN.fullmatch(owner) and compare_digest(saved["owner"], owner):
                pending.pop(token)
            else:
                saved = None
        if saved is None or decision not in {"confirm", "reject"}:
            return page(request, error="The interpretation is invalid, expired or already used. Ask the original question again.")
        if decision == "reject":
            return page(request, question=saved["question"],
                        result_notice="Interpretation rejected. Edit the question and propose again; nothing was executed.")
        transport = None
        try:
            if saved["as_of"] != configured_date():
                raise ValueError("The reference date changed. Ask the original question again before confirming.")
            structured = saved["request"]
            roles = {s["role"]: s for s in structured["requiredSelections"]}
            validate_scope(saved["question"], roles["K"]["committee"]["mention"], roles["R"]["constituency"]["mention"])
            transport = (transport_factory or CompositionTransport)(
                os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
                username=os.getenv("OIR_FUSEKI_USER"), password=os.getenv("OIR_FUSEKI_PASSWORD"))
            report, result = await run_in_threadpool(execute_confirmed, structured, transport)
            return present_execution(request, question=saved["question"], structured=structured,
                                     report=report, result=result, confirmed=True)
        except (ValueError, NLQError) as error:
            return page(request, question=saved["question"], error=str(error))
        finally:
            if transport is not None:
                transport.close()

    @app.get("/composition/evidence/{token}")
    def download(request: Request, token: str):
        with lock:
            trim(evidence)
            saved = evidence.get(token)
        owner = request.cookies.get(COOKIE, "")
        if saved is None or not TOKEN.fullmatch(owner) or not compare_digest(saved["owner"], owner):
            raise HTTPException(404, "Evidence is unavailable or expired. Ask the question again.")
        return JSONResponse(saved["artifact"], headers={"Cache-Control": "no-store",
                            "Content-Disposition": 'attachment; filename="composition-evidence.json"'})

    def present_composition(request, *, question, structured, report, result, dashboard=False):
        return present_execution(request, question=question, structured=structured, report=report,
                                 result=result, dashboard=dashboard)

    return present_composition
