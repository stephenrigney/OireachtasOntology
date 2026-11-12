/* Phase 1: one original objective, explicit publication, automatic bounded steps. */
"use strict";
const $ = id => document.getElementById(id);
let run = null, paused = false, generation = 0, busy = false, preparing = false, opener = null;
const sectionVersions = new Map();
const memberVersions = new Map();
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function button(text, action, cls) { const b = node("button", text, cls); b.type = "button"; b.addEventListener("click", action); return b; }
function announce(text) { $("announcement").textContent = text; }
function message(speaker, text) {
  const box = node("div", undefined, "message"); box.append(node("strong", speaker), node("div", text));
  $("conversation-log").append(box);
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) throw new Error(`Request failed (${response.status}). Your previous report and message are preserved.`);
  return response.json();
}
function setView(view) {
  document.querySelector(".workspace").dataset.view = view;
  $("show-conversation").setAttribute("aria-pressed", String(view === "conversation"));
  $("show-report").setAttribute("aria-pressed", String(view === "report"));
}
$("show-conversation").onclick = () => setView("conversation");
$("show-report").onclick = () => setView("report");
function openDrawer() { opener = document.activeElement; if (!$("activity-drawer").open) $("activity-drawer").showModal(); }
$("close-activity").onclick = () => $("activity-drawer").close();
$("activity-drawer").addEventListener("close", () => { if (opener?.isConnected) opener.focus(); });
$("activity").onclick = () => { renderActivity(); openDrawer(); };

function taskList(tasks) {
  const ol = node("ol");
  tasks.forEach(task => { const li = node("li", task.title); li.append(node("span", task.state, "task-state"));
    if (task.reason) li.append(node("p", task.reason, "metadata")); ol.append(li); });
  return ol;
}
function renderPlan() {
  let card = $("plan-card");
  if (!card) {
    card = node("section", undefined, "plan-card"); card.id = "plan-card"; $("conversation-log").append(card);
    const tasks = node("div"); tasks.id = "plan-tasks";
    card.append(node("h2", "Research plan"), tasks, node("p", `Fixed reporting date: ${run.reportingDate}. Current means both parliamentary and party membership active on that date.`, "metadata"));
    const details = node("details"); details.append(node("summary", "Scope & original requirement"), node("p", run.brief), node("p", "Each party request remains linked to this original brief. Unaccounted conditions are not discarded. Phase 2 conversational refinement is not enabled.")); card.append(details);
    run.unanswered.forEach(item => card.append(node("p", `${item.state}: ${item.reason}`, "notice")));
  }
  $("plan-tasks").replaceChildren(taskList(run.tasks));
}
function evidenceButtons(refs, parent, member = null, offset = 0) {
  refs.forEach((ref, i) => parent.append(button(`Evidence ${i + offset + 1} · ${ref.slice(0, 10)}`, () => showEvidence(ref, member), "evidence-link")));
}
async function showEvidence(ref, member = null) {
  openDrawer(); const content = $("activity-content"); content.replaceChildren(node("p", "Loading retained evidence…"));
  try {
    const e = await api(`/runs/${run.id}/evidence/${ref}`);
    content.replaceChildren(button("← All research activity", renderActivity), node("h3", "Evidence reference"), node("p", e.evidenceId, "term-iri"),
      node("p", `Outcome: ${e.outcome} · Compiler status: ${e.compilerStatus}`), node("p", e.request.factualRequest),
      node("p", `Operation: ${e.request.operation.operation}`), node("p", `Requirement: ${e.request.requirementId}`),
      node("p", `Reporting date: ${e.resolvedScope.reportingDate} · ${e.resolvedScope.temporalMeaning.replaceAll("_", " ")}`),
      node("p", `Validation accepted: ${e.validation.accepted ? "yes" : "no"}. Actual read-only queries: ${e.execution.queries.length}.`));
    if (member) {
      const accepted = e.data?.members?.find(m => m.memberIri === member.memberIri);
      if (accepted) { content.append(node("h3", accepted.displayName), node("p", accepted.memberIri, "term-iri"), node("pre", JSON.stringify(accepted.witnesses, null, 2))); }
    }
    content.append(node("h3", "Provenance & qualifications"));
    e.completeness.limitations.forEach(l => content.append(node("p", l, "metadata")));
    content.append(node("p", "RDF resource references and actual query results are retained. Exact per-row owner graphs are unknown where not projected. No ETL capture or refresh timestamp is invented.", "metadata"));
    const advanced = node("details"); advanced.append(node("summary", "Advanced: plan, all SPARQL pages, returned RDF evidence & diagnostics"), node("pre", JSON.stringify(e, null, 2))); content.append(advanced);
  } catch (error) { content.replaceChildren(node("p", error.message, "notice"), button("All research activity", renderActivity)); }
}
function renderActivity() {
  const content = $("activity-content"); content.replaceChildren();
  if (!run) { content.append(node("p", "Start research to see its plan, execution history and evidence.")); return; }
  content.append(node("h3", "Research plan"), taskList(run.tasks), node("h3", "Execution history"));
  Object.values(run.evidence).forEach(e => {
    const item = node("div", undefined, "notice"); item.append(node("p", e.request.factualRequest), node("p", `${e.outcome} · ${e.queryCount} actual read-only queries`, "metadata"));
    if (e.error) item.append(node("p", e.error.message)); evidenceButtons([e.evidenceId], item); content.append(item);
  });
  content.append(node("h3", "Evidence"), node("p", "Only accepted compiler findings populate report claims. Deterministic calculations retain their input evidence references. Model interpretation is not factual proof.", "metadata"));
  run.unanswered.forEach(u => content.append(node("p", `${u.state}: ${u.requirement} — ${u.reason}`, "notice")));
}

function memberSummary(section) {
  const summary = node("div", undefined, "member-summary");
  if (section.count !== null) {
    const count = node("p", undefined, "finding-number"); count.append(node("strong", String(section.count)), document.createTextNode(" distinct recorded Members")); summary.append(count);
    summary.append(node("p", "Compiler count agrees with the distinct accepted Member identities below. Local coverage is not certified.", "metadata"));
  } else summary.append(node("p", "Accepted Member list available; compiler total is awaiting verification.", "metadata"));
  return summary;
}
function renderSection(section) {
  // Stable section IDs and unchanged DOM preserve unrelated reading position.
  const serialized = JSON.stringify(section);
  if (sectionVersions.get(section.id) === serialized) return;
  sectionVersions.set(section.id, serialized);
  let el = $("section-" + section.id);
  const memberSignature = JSON.stringify(section.members);
  if (el?.querySelector(".table-scroll") && memberVersions.get(section.id) === memberSignature) {
    // A compiler-count update must not detach the table a reader is operating.
    // Keep its open identities, keyboard focus and horizontal scroll position.
    el.querySelector(".section-state").textContent = section.state;
    el.querySelector(".member-summary").replaceWith(memberSummary(section));
    let reason = el.querySelector(".section-reason");
    if (section.reason) {
      if (!reason) { reason = node("p", undefined, "notice section-reason"); el.append(reason); }
      reason.textContent = section.reason;
    } else reason?.remove();
    const refs = el.querySelector(".evidence-links"), count = refs.children.length;
    evidenceButtons(section.evidenceRefs.slice(count), refs, null, count);
    return;
  }
  if (!el) { el = node("section", undefined, "report-section"); el.id = "section-" + section.id; $("report-sections").append(el); }
  memberVersions.set(section.id, memberSignature);
  const heading = node("div", undefined, "section-heading"); heading.append(node("h2", section.title), node("span", section.state, "section-state"));
  el.replaceChildren(heading);
  if (section.term) {
    const t = section.term; el.append(node("p", `${t.label} · reporting date ${run.reportingDate}`),
      node("p", `Recorded start: ${t.start}. End: ${t.end || "not recorded (open-ended)"}. House dates identify the term, not a parliamentary sitting.`, "metadata"), node("p", t.iri, "term-iri"));
  }
  if (section.members?.length) {
    el.append(memberSummary(section));
    const scroller = node("div", undefined, "table-scroll"); scroller.tabIndex = 0; scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", `${section.title} Member table`);
    const table = node("table"); table.append(node("caption", `Recorded Members active on ${run.reportingDate} · exact term above`));
    const thead = node("thead"), tr = node("tr"); ["Member", "Supporting evidence"].forEach(label => { const th = node("th", label); th.scope = "col"; tr.append(th); }); thead.append(tr); table.append(thead);
    const tbody = node("tbody"); section.members.forEach(m => {
      const row = node("tr"), name = node("td", m.displayName), evidence = node("td");
      const identity = node("details"); identity.append(node("summary", "Member identity"), node("p", m.memberIri, "term-iri")); name.append(identity);
      evidence.append(button("View accepted witnesses", () => showEvidence(section.evidenceRefs[0], m))); row.append(name, evidence); tbody.append(row);
    }); table.append(tbody); scroller.append(table); el.append(scroller);
  }
  if (section.calculation) {
    el.append(node("p", "A deterministic comparison of separately observed local query results—not a snapshot-consistent statement of real-world party strength."));
    section.calculation.differences.forEach(d => el.append(node("p", `${d.left} minus ${d.right}: ${d.leftMinusRight} distinct recorded Member IRIs.`)));
  }
  if (section.reason) el.append(node("p", section.reason, "notice section-reason"));
  if (section.state === "Pending") el.append(node("p", "Awaiting validated evidence.", "metadata"));
  const refs = node("div", undefined, "evidence-links"); evidenceButtons(section.evidenceRefs, refs); el.append(refs);
  if (section.evidenceRefs.length) el.append(button("Explain this finding", () => {
    message("Assistant", `${section.title}: this section uses only the accepted evidence linked below it. Open its evidence references to inspect exact identities, time scope, validated witnesses and query history. Further conversational refinement requires Phase 2.`);
    setView("conversation"); $("brief").focus();
  }, "evidence-link"));
}
function render() {
  $("session-title").textContent = run.title;
  $("overall-state").textContent = paused ? "Paused · previous findings retained" : run.status;
  $("report-heading").textContent = run.title;
  $("report-scope").textContent = `Reporting date: ${run.reportingDate}. Scope: ${run.brief}`;
  const incomplete = run.tasks.some(t => t.state !== "Validated") || run.unanswered.length;
  $("report-status").textContent = `${run.status}${incomplete ? " · Incomplete findings" : " · Qualified local findings"}`;
  $("overview").hidden = $("limitations").hidden = $("report-footer").hidden = false;
  renderPlan(); run.sections.forEach(renderSection);
  $("limitation-list").replaceChildren(...run.limitations.map(l => node("li", l)));
  $("unanswered").replaceChildren(...run.unanswered.map(u => node("p", `${u.state}: ${u.reason}`, "notice")),
    ...run.tasks.filter(t => !["Validated", "Pending"].includes(t.state)).map(t => node("p", `${t.title}: ${t.state}. ${t.reason || ""}`, "notice")));
  $("pause").hidden = !run.tasks.some(t => ["Pending", "Running"].includes(t.state));
  $("pause").textContent = paused ? "Resume research" : "Pause research";
  $("copy").disabled = $("export").disabled = false;
  $("submit").textContent = "Send message";
}
async function executeSteps(myGeneration) {
  if (busy) return;
  busy = true;
  try {
    while (run && !paused && generation === myGeneration && run.tasks.some(t => t.state === "Pending")) {
      const task = run.tasks.find(t => t.state === "Pending");
      task.state = "Running"; renderPlan(); announce(task.title + ": running");
      const next = await api(`/runs/${run.id}/step`, {method: "POST", body: JSON.stringify({version: run.version})});
      if (generation !== myGeneration) break;
      run = next; render(); announce(`${task.title}: ${run.tasks.find(t => t.id === task.id).state}`);
      // A rendering opportunity between each accepted section, not one final
      // response pretending to be progressive research.
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 100)));
    }
    if (run && generation === myGeneration && !run.tasks.some(t => ["Pending", "Running"].includes(t.state))) {
      message("Assistant", "Initial research finished. Validated findings are in the report; coverage limitations and unanswered requirements remain visible. You can inspect the evidence or export the qualified report.");
      announce("Initial research completed with limitations. Report updated.");
    }
  } catch (error) {
    if (run && generation === myGeneration) {
      paused = true;
      run.tasks.filter(t => t.state === "Running").forEach(t => t.state = "Pending");
      message("Assistant", error.message + " Resume to retry the same bounded step."); render(); announce("Research interrupted. Earlier validated findings preserved.");
    }
  } finally { busy = false; }
}
$("pause").onclick = () => { paused = !paused; render(); announce(paused ? "Paused. The in-flight query may finish; no further query will be dispatched." : "Research resumed."); if (!paused) executeSteps(generation); };
$("brief").addEventListener("input", () => { $("submit").disabled = preparing || !$("brief").value.trim(); });
$("brief").addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$("submit").disabled) $("composer-form").requestSubmit(); } });
$("example").onclick = () => {
  $("brief").value = "Prepare a short report comparing Fine Gael and Fianna Fáil membership in the current Dáil, including membership totals, the Members involved and a short comparison.";
  $("brief").dispatchEvent(new Event("input")); $("brief").focus();
};
$("composer-form").addEventListener("submit", async event => {
  event.preventDefault(); const brief = $("brief").value; if (!brief.trim()) return;
  if (preparing) return;
  if (run) {
    message("You", brief); message("Assistant", "This Phase 1 workspace retains one original research objective. Your existing report is unchanged. Use New research for another brief; multi-turn scope changes and report refinement require Phase 2 authorisation.");
    $("brief").value = ""; $("submit").disabled = true; return;
  }
  preparing = true; $("submit").disabled = true; $("submission-error").textContent = "";
  message("You", brief); message("Assistant", "Preparing the research plan. No factual queries have been dispatched.");
  announce("Preparing research plan.");
  try {
    const next = await api("/runs", {method: "POST", body: JSON.stringify({brief})});
    run = next; paused = false;
    if ($("brief").value === brief) $("brief").value = "";
    render();
    message("Assistant", "The plan is published. Supported operations will now run automatically. The report will develop as findings are validated.");
    $("plan-card").scrollIntoView({block: "start"});
    announce("Research plan published. Supported queries will run automatically.");
    // Two animation frames + a short visible interval ensure the initial plan
    // is painted BEFORE even the first factual-query dispatch.
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 350))));
    executeSteps(generation);
  } catch (error) { $("submission-error").textContent = error.message; announce("Submission failed. Your message is preserved."); }
  finally { preparing = false; $("submit").disabled = !$("brief").value.trim(); }
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
    $("copy").textContent = "Copied";
  } catch { announce("Copy unavailable. Use Export .md to retain the complete qualified report."); $("copy").textContent = "Use Export .md"; }
};
