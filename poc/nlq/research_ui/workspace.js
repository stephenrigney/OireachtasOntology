/* Single-column research presentation; compiler and evidence authority stay server-side. */
"use strict";
const $ = id => document.getElementById(id);
let run = null, paused = false, generation = 0, busy = false, preparing = false, opener = null, messageCount = 0, sectionContext = null;
let planVersion = "", latestReplyVersion = "", interruption = "", serverProgress = null, progressLastSeen = 0;
let progressPollToken = 0, requestStartedAt = 0, requestPhase = "", requestOperation = "";
let pendingSubmission = null, observedStages = [], pendingDiagnostics = [];
let pauseVersion = 0, inspectorVersion = 0, openerTarget = null;
const sectionVersions = new Map();
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function button(text, action, cls) {
  const b = node("button", text, cls); b.type = "button";
  b.addEventListener("click", () => { b.focus({preventScroll: true}); action(); });
  return b;
}
function announce(text) { $("announcement").textContent = text; }
function message(speaker, text) {
  const box = node("div", undefined, "message"); box.append(node("strong", speaker), node("div", text));
  $("conversation-log").append(box);
  return box;
}
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options}); }
  catch (error) {
    error.requestPath = path;
    error.technicalDiagnostic = `${error.name || "NetworkError"}: ${error.message || "Request communication failed"}`;
    throw error;
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`);
    error.status = response.status; error.payload = payload; error.requestPath = path;
    error.technicalDiagnostic = `HTTP ${response.status}: ${error.message}`;
    throw error;
  }
  return response.json();
}
function newRequestId() { return crypto.randomUUID().replaceAll("-", "").toLowerCase(); }
function elapsed(seconds) {
  const value = Math.max(0, Math.floor(seconds || 0));
  return value < 60 ? `${value}s` : `${Math.floor(value / 60)}m ${value % 60}s`;
}
function mergeStages(stages = []) {
  for (const stage of stages) {
    const label = stage.label || stage.phase;
    if (label && observedStages.at(-1) !== label) observedStages.push(label);
  }
  observedStages = observedStages.slice(-12);
  const history = $("processing-history");
  history.hidden = !observedStages.length;
  history.textContent = observedStages.length > 1 ? `Stages observed: ${observedStages.join(" → ")}` : "";
}
function runStateLabel(processing = run?.processing) {
  if (!processing) return run?.status || "";
  if (paused && run?.hasWork) return "Paused";
  return processing.label || run?.status || "";
}
function stageForNextStep() {
  if (!run) return "understanding";
  const nextPhase = serverProgress?.active ? null : (serverProgress?.nextPhase || run.processing?.nextPhase);
  if (nextPhase) return nextPhase;
  if (!run.plans?.length && !run.tasks?.length && run.status === "Understanding the request") return "understanding";
  if (run.tasks?.some(task => task.state === "Pending")) return "retrieving";
  if (run.sections?.length || Object.keys(run.facts || {}).length) return "writing";
  return "assessing";
}
function progressText(processing = serverProgress || run?.processing) {
  if (preparing && !run) return `${requestPhase || "Understanding the request"} · ${elapsed((Date.now()-requestStartedAt)/1000)}`;
  if (!run) return "";
  if (paused) {
    return processing?.active
      ? `Paused after this operation · ${processing.phaseLabel}: ${processing.activeOperation || "Research work"} · ${elapsed(processing.elapsedSeconds)} elapsed. It may finish; no further step will be dispatched.`
      : "Research paused. Earlier findings remain available; choose Resume research to continue.";
  }
  if (preparing && !run.id) return `${requestPhase || "Understanding the request"} · ${elapsed((Date.now()-requestStartedAt)/1000)}`;
  if (processing?.active) {
    const stale = progressLastSeen && Date.now()-progressLastSeen > 6000;
    const current = `${processing.phaseLabel || "Processing"}${processing.activeOperation ? ` · ${processing.activeOperation}` : ""} · ${elapsed(processing.elapsedSeconds)} elapsed`;
    const waiting = preparing ? " Your follow-up is waiting for this operation to finish." : "";
    return stale ? `Progress check delayed. Last confirmed: ${current}; the research has not been marked complete.${waiting}` : current + waiting;
  }
  if (preparing) return `${requestPhase || "Understanding the request"} · ${elapsed((Date.now()-requestStartedAt)/1000)}`;
  if (busy && run.hasWork) {
    const phase = stageForNextStep();
    const labels = {understanding: "Understanding the request", retrieving: "Retrieving parliamentary records", assessing: "Assessing results", writing: "Writing or revising the report"};
    return `${labels[phase]} · next operation starting`;
  }
  return runStateLabel(run.processing);
}
function acceptRunState(next) {
  if (!run || next.id !== run.id || next.version >= run.version) run = next;
  mergeStages(next.processing?.stages || []);
}
function startProgressPolling() {
  if (!run) return;
  const token = ++progressPollToken, runId = run.id, myGeneration = generation;
  const poll = async () => {
    if (token !== progressPollToken || myGeneration !== generation || !run || run.id !== runId) return;
    try {
      const response = await fetch(`/runs/${runId}/progress`, {signal: AbortSignal.timeout(5000), cache: "no-store"});
      if (!response.ok) throw new Error(`Progress request returned HTTP ${response.status}`);
      serverProgress = await response.json(); progressLastSeen = Date.now();
      mergeStages(serverProgress.stages || []);
      await flushClientDiagnostics(runId);
      renderProcessing();
      if (token === progressPollToken && (busy || preparing || serverProgress.active || pendingDiagnostics.length)) setTimeout(poll, 750);
    } catch (error) {
      renderProcessing();
      if (token === progressPollToken && (busy || preparing || serverProgress?.active || pendingDiagnostics.length)) setTimeout(poll, 1250);
    }
  };
  poll();
}
function stopProgressPolling() { progressPollToken++; }
async function flushClientDiagnostics(runId) {
  const pending = pendingDiagnostics.splice(0);
  for (const item of pending) {
    try {
      const response = await fetch(`/runs/${runId}/diagnostics`, {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(item), signal: AbortSignal.timeout(3000)});
      if (!response.ok) throw new Error(`Diagnostic request returned HTTP ${response.status}`);
      const accepted = await response.json();
      if (run?.id === runId) {
        run.technicalDiagnostics = [...(run.technicalDiagnostics || []).filter(entry => entry.requestId !== accepted.requestId), accepted];
        renderActivityIfOpen();
      }
    } catch { pendingDiagnostics.push(item); }
  }
}
function renderProcessing() {
  if (!run) return;
  $("research-progress").textContent = progressText();
  const label = paused && run.hasWork ? "Paused" : preparing ? "Understanding the request"
    : busy && run.hasWork && !serverProgress?.active ? "Processing" : runStateLabel(serverProgress?.active ? serverProgress : run.processing);
  $("overall-state").textContent = label;
  $("report-status").textContent = `Draft — for review · ${label}`;
  if ($("activity-drawer").open) {
    const active = serverProgress?.active ? serverProgress : run.processing;
    const marker = $("activity-content").querySelector("#activity-live-progress");
    if (marker) marker.textContent = active?.active ? progressText(active) : `Current state: ${label}`;
  }
  if (serverProgress?.active && serverProgress.phase === "writing") {
    for (const id of serverProgress.targetSectionIds || []) {
      const section = $("section-" + id);
      if (section) section.querySelector(".section-state").textContent = "Populating";
    }
  }
}
function reachComposer() { $("brief").focus(); }
$("reach-composer").onclick = reachComposer;
$("reach-plan").onclick = () => { $("plan-disclosure").open = true; $("plan-summary").focus(); };
function openDrawer() {
  if (!$("activity-drawer").open) {
    opener = document.activeElement;
    openerTarget = {sectionId: opener.closest(".report-section")?.id, label: opener.getAttribute("aria-label"), text: opener.textContent};
    $("activity-drawer").showModal();
  }
}
$("close-activity").onclick = () => $("activity-drawer").close();
$("activity-drawer").addEventListener("close", () => {
  inspectorVersion++;
  let target = opener?.isConnected ? opener : null;
  if (!target && openerTarget?.sectionId) {
    const section = $(openerTarget.sectionId);
    target = [...(section?.querySelectorAll("button") || [])].find(b => openerTarget.label ? b.getAttribute("aria-label") === openerTarget.label : b.textContent === openerTarget.text);
    if (!target && section) { target = section.querySelector("h2"); target.tabIndex = -1; }
  }
  (target || $("plan-summary")).focus({preventScroll: true});
});
$("activity-drawer").addEventListener("keydown", event => {
  if (event.key !== "Tab") return;
  const controls = [...$("activity-drawer").querySelectorAll("button:not(:disabled), summary, a[href], [tabindex='0']")].filter(el => el.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
$("activity").onclick = () => { $("activity").focus({preventScroll: true}); renderActivity(); openDrawer(); };

function taskList(tasks, technical = false) {
  const ol = node("ol");
  tasks.forEach(task => { const li = node("li", task.title); li.append(node("span", task.outcomeLabel || task.state, "task-state"));
    if (task.role) li.append(node("p", `${task.role === "supporting" ? "Supporting evidence" : task.role} · ${task.relevance}`, "metadata"));
    if (technical && task.toolMeaning) li.append(node("p", task.toolMeaning, "metadata"));
    if (technical && task.technicalDiagnostic) li.append(node("pre", task.technicalDiagnostic));
    if (task.reason && (technical || !task.researchOutcome)) li.append(node("p", task.reason, "metadata")); ol.append(li); });
  return ol;
}
function renderPlan() {
  const completed = run.tasks.filter(t => t.state !== "Pending").length;
  $("plan-summary").textContent = completed ? `Research plan · ${completed} research tasks completed` : "Research plan";
  const serialized = JSON.stringify([run.tasks, run.interpretation, run.requirements, run.questionAssessments]);
  if (planVersion === serialized) return;
  planVersion = serialized;
  $("plan-tasks").replaceChildren(taskList(run.tasks));
  $("plan-interpretation").textContent = run.interpretation;
  $("plan-date").textContent = `Reporting date: ${run.reportingDate}.`;
  const requirements = $("requirement-content"); requirements.replaceChildren();
  (run.requirements || []).forEach((r, i) => { requirements.append(node("h3", `${i ? "Added request" : "Original question"}: ${r.originalWording}`), node("p", r.assessment));
    r.proposedConditions.forEach(c => { requirements.append(node("p", `${c.wording} — ${c.disposition}: ${c.explanation}`), node("p", c.conditions.join("; "), "metadata"));
      const assessment = run.questionAssessments?.[c.id];
      if (assessment) requirements.append(node("p", `Current provisional assessment: ${assessment.disposition}. ${assessment.explanation}`, "metadata"));
    }); });
}
function evidenceButtons(refs, parent, member = null, offset = 0) {
  refs.forEach((ref, i) => parent.append(button(`Evidence ${i + offset + 1} · ${ref.slice(0, 10)}`, () => showEvidence(ref, member), "evidence-link")));
}
async function showEvidence(ref, member = null) {
  const version = ++inspectorVersion;
  openDrawer(); const content = $("activity-content"); content.replaceChildren(node("p", "Loading retained evidence…"));
  try {
    const e = await api(`/runs/${run.id}/evidence/${ref}`);
    if (version !== inspectorVersion) return;
    content.replaceChildren(button("← All research activity", renderActivity), node("h3", "Evidence reference"), node("p", e.evidenceId, "term-iri"),
      node("p", `Outcome: ${e.outcome} · Compiler status: ${e.compilerStatus}`), node("p", e.request.factualRequest),
      node("p", `Operation: ${e.request.operation.operation}`), node("p", `Requirement: ${e.request.requirementId}`),
      node("p", `Reporting date: ${e.resolvedScope.reportingDate} · ${e.resolvedScope.temporalMeaning.replaceAll("_", " ")}`),
      node("p", `Validation accepted: ${e.validation.accepted ? "yes" : "no"}. Actual read-only queries: ${e.execution.queries.length}.`));
    if (member) {
      const accepted = e.data?.members?.find(m => m.memberIri === member.memberIri);
      if (accepted) { content.append(node("h3", accepted.displayName), node("p", accepted.memberIri, "term-iri"), node("pre", JSON.stringify(accepted.witnesses, null, 2))); }
    }
    if (e.error) content.append(node("p", e.error.message, "notice"));
    if (e.queryServiceResult) {
      const response = node("details");
      response.append(node("summary", "Query Service response · original returned values"),
        node("pre", JSON.stringify(e.queryServiceResult, null, 2)));
      content.append(response);
    }
    content.append(node("h3", "Provenance & qualifications"));
    e.completeness.limitations.forEach(l => content.append(node("p", l, "metadata")));
    content.append(node("p", "RDF resource references and actual query results are retained. Exact per-row owner graphs are unknown where not projected. No ETL capture or refresh timestamp is invented.", "metadata"));
    const advanced = node("details"); advanced.append(node("summary", "Advanced: plan, all SPARQL pages, returned RDF evidence & diagnostics"), node("pre", JSON.stringify(e, null, 2))); content.append(advanced);
  } catch (error) { if (version === inspectorVersion) content.replaceChildren(node("p", error.message, "notice"), button("All research activity", renderActivity)); }
}
function renderActivity() {
  inspectorVersion++;
  const content = $("activity-content"); content.replaceChildren();
  if (!run) { content.append(node("p", "Start research to see its plan, execution history and evidence.")); return; }
  const progress = serverProgress?.active ? serverProgress : run.processing;
  content.append(node("h3", "Current processing"), node("p", progress?.active ? progressText(progress) : `Current state: ${runStateLabel(progress)}`, "metadata"));
  content.lastChild.id = "activity-live-progress";
  content.append(node("h3", "Research plan"), taskList(run.tasks, true), node("h3", "Execution history"));
  const history = node("details"); history.append(node("summary", "Plan versions and original requests"));
  (run.plans || []).forEach(p => { const version = node("section"); version.append(node("h4", `Plan ${p.version}`), node("p", p.requirements.originalWording, "verbatim"), node("p", p.interpretation), taskList(run.tasks.filter(t => p.taskIds.includes(t.id)))); history.append(version); });
  content.insertBefore(history, content.children[2]);
  Object.values(run.evidence).forEach(e => {
    const item = node("div", undefined, "notice"); item.append(node("p", e.request.factualRequest), node("p", `${e.outcome} · ${e.queryCount} actual read-only queries`, "metadata"));
    if (e.error) item.append(node("p", e.error.message)); evidenceButtons([e.evidenceId], item); content.append(item);
  });
  content.append(node("h3", "Evidence"), node("p", "Successful Query Service answers are shown at their returned scope. Original results and execution details remain inspectable. AI-generated summaries and comparisons are drafts for review, not factual certification.", "metadata"));
  run.unanswered.forEach(u => content.append(node("p", `${u.state}: ${u.requirement} — ${u.reason}`, "notice")));
  (run.clarifications || []).forEach(t => content.append(node("p", `Clarification: ${t}`, "notice")));
  const diagnostics = [...(run.technicalDiagnostics || []), ...pendingDiagnostics];
  if (diagnostics.length) {
    const advanced = node("details"); advanced.append(node("summary", "Advanced: exact redacted technical diagnostics"));
    diagnostics.forEach(item => advanced.append(node("pre", JSON.stringify(item, null, 2))));
    content.append(advanced);
  }
  const facts = node("details"); facts.append(node("summary", "All individual factual assertions"));
  Object.values(run.facts).forEach(a => facts.append(button(a.text, () => showAssertion(a.id), "evidence-link")));
  content.append(facts);
}
function renderActivityIfOpen() { if ($("activity-drawer").open) renderActivity(); }

const classLabel = {1: "Directly supported recorded fact", 2: "Approved calculation", 3: "Provisional interpretation", 4: "Unverified hypothesis / further question"};
function showAssertion(ref) {
  inspectorVersion++;
  const a = run.assertions[ref] || run.facts[ref];
  openDrawer();
  const content = $("activity-content");
  content.replaceChildren(button("← All research activity", renderActivity), node("h3", classLabel[a.level]), node("p", a.text),
    node("p", `Assertion ${a.id} · Level ${a.level} · ${a.reviewStatus}`, "metadata"), node("h4", "Reasoning"), node("p", a.reasoning));
  if (a.level === 3) content.append(node("p", `${a.confidence} qualitative confidence — provisional, not calibrated`), node("p", a.confidenceRationale));
  for (const [key, title] of [["assumptions", "Assumptions"], ["conflicts", "Conflicts / contrary evidence"], ["limitations", "Limitations"]]) {
    content.append(node("h4", title), node("p", a[key].length ? a[key].join(" ") : "None identified within the available evidence; not a completeness guarantee."));
  }
  content.append(node("h4", "Source records · freshness unknown, coverage uncertified"));
  if (a.proposition && !Array.isArray(a.proposition)) {
    const proposition = node("details");
    proposition.append(node("summary", "Exact accepted proposition, intervals and witnesses"),
      node("pre", JSON.stringify({proposition: a.proposition, queryRefs: a.queryRefs}, null, 2)));
    content.append(proposition);
  }
  evidenceButtons(a.evidenceRefs, content);
  content.append(button("Challenge or explain this assertion", () => {
    if (!replaceDraft(`Please explain or reconsider this finding: “${a.text}”`)) return;
    // Closing returns focus first; the explicit challenge then moves to writing.
    $("activity-drawer").addEventListener("close", reachComposer, {once: true});
    sectionContext = null; renderContext(); $("activity-drawer").close();
  }));
}
function showRowEvidence(row) {
  inspectorVersion++;
  openDrawer();
  const content = $("activity-content");
  content.replaceChildren(button("← All research activity", renderActivity), node("h3", "Individual recorded facts"), node("p", row.cells[0].text),
    node("p", "All accepted facts for this row, including activities not selected for the table. Each opens its exact assertion, reasoning and full source records."));
  row.assertionRefs.forEach(ref => content.append(button(run.facts[ref].text, () => showAssertion(ref), "evidence-link")));
}
function renderTable(data) {
  const region = node("div", undefined, "table-scroll"); region.tabIndex = 0;
  region.setAttribute("role", "region"); region.setAttribute("aria-label", data.caption + " — scrollable factual table");
  const table = node("table"); table.append(node("caption", data.caption));
  const head = node("thead"), headers = node("tr");
  [...data.columns, "Evidence"].forEach(c => { const th = node("th", c); th.scope = "col"; headers.append(th); });
  head.append(headers); table.append(head);
  const body = node("tbody");
  data.rows.forEach(row => {
    const tr = node("tr");
    row.cells.forEach((cell, i) => { const td = node(i === 0 ? "th" : "td", row.evidenceRef ? cell.text : (cell.text || "No accepted value shown")); if (i === 0) td.scope = "row"; tr.append(td); });
    const td = node("td"), inspect = button("Source records", () => row.evidenceRef ? showEvidence(row.evidenceRef) : showRowEvidence(row), "evidence-link");
    inspect.setAttribute("aria-label", `Evidence: individual recorded facts · ${row.cells[0].text}`);
    td.append(inspect); tr.append(td); body.append(tr);
  });
  table.append(body); region.append(table);
  return region;
}
function renderSection(section) {
  // Stable section IDs and unchanged DOM preserve unrelated reading position.
  let el = $("section-" + section.id);
  const serialized = JSON.stringify([{...section, state: null}, section.assertionRefs.map(ref => run.assertions[ref])]);
  if (el) el.querySelector(".section-state").textContent = section.state;
  if (sectionVersions.get(section.id) === serialized) return;
  sectionVersions.set(section.id, serialized);
  const focusedLabel = el?.contains(document.activeElement) ? document.activeElement.getAttribute("aria-label") : null;
  const hadFocus = el?.contains(document.activeElement);
  if (!el) { el = node("section", undefined, "report-section"); el.id = "section-" + section.id; $("report-sections").append(el); }
  const heading = node("div", undefined, "section-heading"); heading.append(node("h2", section.title), node("span", section.state, "section-state"));
  el.replaceChildren(heading);
  if (section.kind === "further_questions") el.append(node("p", "Unverified hypotheses and questions for further investigation", "notice"));
  (section.summaries || []).forEach(summary => {
    const p = node("p", summary.text);
    p.append(node("span", " AI-generated draft summary / comparison — for review.", "metadata"));
    evidenceButtons(summary.resultRefs, p); el.append(p);
  });
  (section.results || []).forEach(result => {
    el.append(renderTable(result));
    if (result.empty) el.append(node("p", "No matching rows returned within this query scope. This is not proof of absence from parliamentary history.", "notice"));
    if (result.qualification) el.append(node("p", result.qualification, "metadata"));
    el.append(node("p", result.scope, "metadata"));
    evidenceButtons([result.evidenceRef], el);
  });
  for (const ref of [...section.assertionRefs, ...section.factRefs]) {
    const a = run.assertions[ref] || run.facts[ref], p = node("p", a.text);
    if (a.level === 3) p.append(node("span", " Provisional interpretation.", "metadata"));
    if (a.level === 4) p.append(node("span", " Unverified — for investigation.", "metadata"));
    const indicator = button("Source & reasoning", () => showAssertion(ref), "evidence-link");
    indicator.setAttribute("aria-label", `Evidence: ${classLabel[a.level]} · ${ref}`); p.append(indicator); el.append(p);
  }
  (section.tables || []).forEach(table => { el.append(renderTable(table), node("p", table.qualification, "metadata")); });
  el.append(button("Refine this section", () => {
    sectionContext = section.id; renderContext(); reachComposer();
  }, "evidence-link"));
  if (hadFocus) {
    const equivalent = [...el.querySelectorAll("button")].find(b => b.getAttribute("aria-label") === focusedLabel);
    if (equivalent) equivalent.focus({preventScroll: true});
    else { const h = el.querySelector("h2"); h.tabIndex = -1; h.focus({preventScroll: true}); }
  }
}
function replaceDraft(text) {
  if ($("brief").value.trim() && !confirm("Replace the text you have written?")) return false;
  $("brief").value = text; $("brief").dispatchEvent(new Event("input")); return true;
}
function renderContext() {
  $("section-context").hidden = !sectionContext;
  $("context-label").textContent = sectionContext ? `Regarding: ${run.sections.find(s => s.id === sectionContext)?.title || sectionContext}` : "";
}
$("clear-context").onclick = () => { sectionContext = null; renderContext(); reachComposer(); };
function replyContent(parent, m) {
  parent.replaceChildren(node("strong", "Assistant"), node("p", m.text, "verbatim"));
  if (m.assertionRef) parent.append(node("p", "Provisional explanation — for review", "metadata"), button("Evidence for this explanation", () => showAssertion(m.assertionRef), "evidence-link"));
}
function render() {
  const hasReport = run.sections.length > 0;
  $("start-canvas").hidden = true;
  $("research-canvas").hidden = $("session").hidden = $("workspace-controls").hidden = false;
  if ($("composer-form").parentElement !== $("follow-up-composer")) $("follow-up-composer").append($("composer-form"));
  $("composer-label").classList.remove("sr-only");
  $("composer-label").textContent = "Ask a follow-up or request a change";
  $("brief").rows = 3;
  $("report").hidden = !hasReport;
  $("planning-title").hidden = hasReport;
  $("return-report").hidden = !hasReport;
  $("session-title").textContent = run.title;
  const displayedState = runStateLabel(serverProgress?.active ? serverProgress : run.processing);
  $("overall-state").textContent = displayedState;
  $("report-heading").textContent = run.title;
  $("original-brief").textContent = run.brief;
  $("report-scope").textContent = `Reporting date: ${run.reportingDate}. ${run.brief}`;
  $("report-status").textContent = `Draft — for review · ${displayedState}`;
  renderPlan();
  const liveSections = new Set(run.sections.map(s => "section-" + s.id));
  $("report-sections").querySelectorAll(".report-section").forEach(el => {
    if (!liveSections.has(el.id)) { sectionVersions.delete(el.id.slice(8)); el.remove(); }
  });
  run.sections.forEach(renderSection);
  (run.messages || []).slice(messageCount).forEach(m => {
    const box = message(m.role === "user" ? "You" : "Assistant", m.text);
    if (m.assertionRef) box.append(node("p", "Provisional explanation — for review", "metadata"), button("Evidence for this explanation", () => showAssertion(m.assertionRef), "evidence-link"));
  });
  messageCount = (run.messages || []).length;
  const latest = (run.messages || []).findLast(m => m.role === "assistant");
  if (latest && latestReplyVersion !== JSON.stringify(latest)) {
    latestReplyVersion = JSON.stringify(latest); replyContent($("latest-reply"), latest);
  }
  // Findings lead. Completed search limitations appear once beside the report,
  // not also as a stack of progress notices above its answer.
  const summary = interruption || run.outcomeSummary || "";
  $("report-outcome").hidden = !hasReport || !summary;
  $("report-outcome").textContent = hasReport ? summary : "";
  const summaryIsLatestReply = Boolean(summary && latest?.text === summary && !hasReport && !interruption);
  $("workspace-outcome").hidden = hasReport || !summary || summaryIsLatestReply;
  $("workspace-outcome").textContent = hasReport || summaryIsLatestReply ? "" : summary;
  const notices = [];
  const serializedNotices = JSON.stringify(notices);
  if ($("research-notices").dataset.version !== serializedNotices) {
    $("research-notices").dataset.version = serializedNotices;
    $("research-notices").replaceChildren(...notices.filter(Boolean).map(t => node("p", t, "notice")));
  }
  $("limitation-list").replaceChildren(...run.limitations.map(l => node("li", l)));
  $("unanswered").replaceChildren(...(run.unanswered.length ? [node("h3", "Unanswered research questions"), ...run.unanswered.map(u => node("p", u.reason, "notice"))] : []));
  $("unanswered-without-report").hidden = hasReport || !run.unanswered.length;
  $("unanswered-without-report").replaceChildren(...(!hasReport && run.unanswered.length ? [node("h2", "Unanswered research questions"), ...run.unanswered.map(u => node("p", u.requirement, "notice"))] : []));
  $("pause").hidden = !run.hasWork;
  $("pause").textContent = paused ? "Resume research" : "Pause research";
  $("copy").hidden = $("export").hidden = !hasReport;
  $("submit").textContent = "Send follow-up";
  const latestReply = $("latest-reply");
  latestReply.hidden = Boolean(hasReport && summary && latest?.text === summary);
  renderContext();
  renderProcessing();
}
async function executeSteps(myGeneration) {
  if (busy) return;
  busy = true;
  startProgressPolling();
  try {
    while (run && !paused && !preparing && generation === myGeneration && run.hasWork) {
      const task = run.tasks.find(t => t.state === "Pending");
      const previousPlanCount = run.plans?.length || 0;
      requestPhase = stageForNextStep();
      requestOperation = task?.title || serverProgress?.nextOperation || run.processing?.nextOperation
        || (requestPhase === "writing" ? "Research report" : "Reviewing research outcomes");
      requestStartedAt = Date.now();
      renderProcessing();
      if (executeSteps.lastProgress !== requestOperation) {
        const labels = {understanding: "Understanding the request", retrieving: "Retrieving parliamentary records", assessing: "Assessing results", writing: "Writing or revising the report"};
        announce(`${labels[requestPhase]}${requestOperation ? `: ${requestOperation}` : ""}`);
        executeSteps.lastProgress = requestOperation;
      }
      const previousSections = JSON.stringify(run.sections);
      const requestVersion = run.version;
      const next = await api(`/runs/${run.id}/step`, {method: "POST", body: JSON.stringify({version: requestVersion})});
      if (generation !== myGeneration) break;
      interruption = "";
      acceptRunState(next); serverProgress = next.processing; progressLastSeen = Date.now();
      if (next.planningIssue && !$("brief").value.trim()) {
        const lastUserMessage = [...(next.messages || [])].reverse().find(item => item.role === "user");
        $("brief").value = lastUserMessage?.text || next.brief;
        $("submit").disabled = false;
      }
      render();
      if (JSON.stringify(run.sections) !== previousSections) announce("New findings are available in the research report.");
      if ((next.plans?.length || 0) > previousPlanCount && run.tasks.some(t => t.state === "Pending")) {
        // Paint every newly published plan before dispatching its first query.
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 350))));
      }
      // A rendering opportunity between each accepted section, not one final
      // response pretending to be progressive research.
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 100)));
    }
    if (run && generation === myGeneration && !run.hasWork) {
      const state = runStateLabel(run.processing);
      announce(run.processing.state === "awaiting_clarification" ? "Clarification required. Read the assistant’s question below." : `${state}. Read the report and outcome summary.`);
    }
  } catch (error) {
    if (run && generation === myGeneration) {
      paused = true;
      const operation = requestOperation || "Research step";
      pendingDiagnostics.push({requestId: newRequestId(), operation,
        diagnostic: `${error.technicalDiagnostic || `${error.name || "Error"}: ${error.message || "Request failed"}`} · endpoint ${error.requestPath || "unknown"}`});
      interruption = error.status
        ? "The research service could not confirm this step. Earlier findings remain available; resume to check the same version safely."
        : "The connection was lost before this step was confirmed. It may still be running; check Research Activity. Earlier findings remain available, and resuming checks the same version safely.";
      render(); renderActivityIfOpen(); announce("The browser could not confirm the research step. Earlier findings are preserved.");
      startProgressPolling();
    }
  } finally {
    busy = false;
    requestPhase = ""; requestOperation = "";
    if (!serverProgress?.active && !interruption && !pendingDiagnostics.length) stopProgressPolling();
    // A follow-up may publish a new plan while the preceding step finishes.
    if (run?.hasWork && !paused && !preparing && generation === myGeneration) queueMicrotask(() => executeSteps(myGeneration));
  }
}
$("pause").onclick = () => { pauseVersion++; paused = !paused; render(); announce(paused ? "Paused. The current operation may finish; no further step will be dispatched." : "Research resumed."); if (!paused) executeSteps(generation); };
$("brief").addEventListener("input", () => { $("submit").disabled = preparing || !$("brief").value.trim(); });
$("brief").addEventListener("keydown", event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.isComposing) { event.preventDefault(); if (!$("submit").disabled) $("composer-form").requestSubmit(); } });
for (const id of ["example", "example-career"]) $(id).onclick = () => { if (replaceDraft($(id).textContent)) reachComposer(); };
$("composer-form").addEventListener("submit", async event => {
  event.preventDefault(); const brief = $("brief").value; if (!brief.trim()) return;
  if (preparing) return;
  const initial = !run;
  if (!pendingSubmission || pendingSubmission.text !== brief || pendingSubmission.initial !== initial) {
    pendingSubmission = {id: newRequestId(), text: brief, initial};
  }
  const requestId = pendingSubmission.id;
  const submittedPauseVersion = pauseVersion;
  preparing = true; $("submit").disabled = true; $("submission-error").textContent = "";
  $("submit").textContent = initial ? "Preparing research…" : "Preparing follow-up…";
  requestPhase = "Understanding the request"; requestOperation = brief; requestStartedAt = Date.now();
  if (run) startProgressPolling();
  renderProcessing();
  announce("Preparing research plan.");
  try {
    const body = run ? {text: brief, sectionId: sectionContext, requestId} : {brief, requestId};
    const next = await api(run ? `/runs/${run.id}/messages` : "/runs", {method: "POST", body: JSON.stringify(body)});
    if (!run || next.id !== run.id) { observedStages = []; serverProgress = next.processing; }
    acceptRunState(next); serverProgress = next.processing; progressLastSeen = Date.now();
    pendingSubmission = null;
    if (!next.hasWork) interruption = "";
    // An explicit new request resumes automatic work, as in v0.5. A Pause
    // pressed while that request is preparing still takes precedence.
    if (pauseVersion === submittedPauseVersion) paused = false;
    sectionContext = null;
    if (run.status !== "Research planning interrupted" && $("brief").value === brief) $("brief").value = "";
    render();
    if (initial) {
      // Focus moves only for the user's explicit initial submission, never as
      // findings arrive or a section-context editorial revision completes.
      $("plan-summary").focus();
    }
    announce(run.status === "Research planning interrupted" ? "Research planning interrupted. Your request is retained." : paused ? "Your follow-up is ready. Research remains paused; choose Resume research to continue." : run.hasWork ? "Research request accepted. The plan will be shown before any search." : run.status);
    // Initial planning is a separate, observable step. For a follow-up the
    // new plan itself is displayed before its next search is dispatched.
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 350))));
    preparing = false; requestPhase = ""; requestOperation = "";
    renderProcessing(); executeSteps(generation);
  } catch (error) {
    if (run && error.status !== 409) {
      pendingDiagnostics.push({requestId: newRequestId(), operation: "Follow-up request",
        diagnostic: `${error.technicalDiagnostic || `${error.name || "Error"}: ${error.message || "Request failed"}`} · endpoint ${error.requestPath || "unknown"}`});
      startProgressPolling(); renderActivityIfOpen();
      $("submission-error").textContent = error.status
        ? "The follow-up could not be accepted. Your text is preserved; check Research Activity, then try again."
        : "The connection was lost before this follow-up was confirmed. Your text is preserved; retrying this same submission is safe.";
    } else {
      $("submission-error").textContent = error.status === 409 ? error.message : "The request could not be sent. Your full text is preserved; check your connection and try again.";
      if (error.technicalDiagnostic) pendingDiagnostics.push({requestId: newRequestId(), operation: initial ? "Start research" : "Follow-up request", diagnostic: error.technicalDiagnostic});
    }
    announce("Submission failed. Your message is preserved.");
  }
  finally {
    preparing = false; requestPhase = ""; requestOperation = "";
    $("submit").disabled = !$("brief").value.trim(); $("submit").textContent = run ? "Send follow-up" : "Start research";
    renderProcessing();
    if (run && !serverProgress?.active && !busy && !pendingDiagnostics.length && !interruption) stopProgressPolling();
  }
});
$("new-research").onclick = () => {
  if (run && !confirm("Start a new research workspace? Export this report first if you want to keep it. Any in-flight read may finish, but no further queries will be dispatched.")) return;
  // Reload starts a clean page, not a cross-session report library.
  generation++; paused = true; location.reload();
};
$("export").onclick = () => { if (run) location.href = `/runs/${run.id}/report.md`; };
$("copy").onclick = async () => {
  if (!run) return;
  try {
    const response = await fetch(`/runs/${run.id}/report.md`); if (!response.ok) throw new Error();
    await navigator.clipboard.writeText(await response.text()); announce("Qualified report and evidence copied as Markdown.");
  } catch { announce("Copy unavailable. Use Export .md to retain the complete qualified report."); }
};
// Scale the in-flow reading-navigation offset with wrapping and text settings.
new ResizeObserver(entries => {
  document.documentElement.style.setProperty("--reading-tools-height", `${entries[0].target.getBoundingClientRect().height}px`);
}).observe(document.querySelector(".reading-tools"));
