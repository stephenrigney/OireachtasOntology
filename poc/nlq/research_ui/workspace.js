/* Phase 1: one original objective, explicit publication, automatic bounded steps. */
"use strict";
const $ = id => document.getElementById(id);
let run = null, paused = false, generation = 0, busy = false, preparing = false, opener = null, messageCount = 0, sectionContext = null;
const sectionVersions = new Map();
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
  return box;
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(`${typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`} Your previous report and message are preserved.`);
  }
  return response.json();
}
function setView(view) {
  document.querySelector(".workspace").dataset.view = view;
  $("show-conversation").setAttribute("aria-pressed", String(view === "conversation"));
  $("show-report").setAttribute("aria-pressed", String(view === "report"));
}
$("show-conversation").onclick = () => setView("conversation");
$("show-report").onclick = () => setView("report");
function openDrawer() { if (!$("activity-drawer").open) { opener = document.activeElement; $("activity-drawer").showModal(); } }
$("close-activity").onclick = () => $("activity-drawer").close();
$("activity-drawer").addEventListener("close", () => { if (opener?.isConnected) opener.focus(); });
$("activity-drawer").addEventListener("keydown", event => {
  if (event.key !== "Tab") return;
  const controls = [...$("activity-drawer").querySelectorAll("button:not(:disabled), summary, a[href], [tabindex='0']")].filter(el => el.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
$("activity").onclick = () => { renderActivity(); openDrawer(); };

function taskList(tasks) {
  const ol = node("ol");
  tasks.forEach(task => { const li = node("li", task.title); li.append(node("span", task.state, "task-state"));
    if (task.role) li.append(node("p", `${task.role === "supporting" ? "Supporting evidence" : task.role} · ${task.relevance}`, "metadata"));
    if (task.toolMeaning) li.append(node("p", task.toolMeaning, "metadata"));
    if (task.reason) li.append(node("p", task.reason, "metadata")); ol.append(li); });
  return ol;
}
function renderPlan() {
  let card = $("plan-card");
  if (!card) {
    card = node("section", undefined, "plan-card"); card.id = "plan-card"; $("conversation-log").append(card);
    const tasks = node("div"); tasks.id = "plan-tasks";
    const interpretation = node("p"); interpretation.id = "plan-interpretation";
    card.append(node("h2", "Research plan"), interpretation, tasks, node("p", `Reporting date: ${run.reportingDate}. Historical records do not certify current real-world outcomes.`, "metadata"));
    const details = node("details"); details.id = "requirements"; card.append(details);
  }
  $("plan-tasks").replaceChildren(taskList(run.tasks));
  $("plan-interpretation").textContent = run.interpretation;
  $("requirements").replaceChildren(node("summary", "Original brief & proposed requirement assessment"), node("p", run.brief));
  (run.requirements || []).forEach(r => { $("requirements").append(node("h3", r.originalWording), node("p", r.assessment));
    r.proposedConditions.forEach(c => { $("requirements").append(node("p", `${c.wording} — ${c.disposition}: ${c.explanation}`), node("p", c.conditions.join("; "), "metadata"));
      const assessment = run.questionAssessments?.[c.id];
      if (assessment) $("requirements").append(node("p", `Current provisional assessment: ${assessment.disposition}. ${assessment.explanation}`, "metadata"));
    }); });
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
  (run.processMessages || []).forEach(t => content.append(node("p", t, "notice")));
  (run.clarifications || []).forEach(t => content.append(node("p", `Clarification: ${t}`, "notice")));
  const facts = node("details"); facts.append(node("summary", "All individual factual assertions"));
  Object.values(run.facts).forEach(a => facts.append(button(a.text, () => showAssertion(a.id), "evidence-link")));
  content.append(facts);
}

const classLabel = {1: "Directly supported recorded fact", 2: "Approved calculation", 3: "Provisional interpretation", 4: "Unverified hypothesis / further question"};
function showAssertion(ref) {
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
  evidenceButtons(a.evidenceRefs, content);
  content.append(button("Challenge or explain this assertion", () => { $("activity-drawer").close(); sectionContext = null; $("brief").value = `Please explain or reconsider assertion ${ref}: `; $("brief").dispatchEvent(new Event("input")); setView("conversation"); $("brief").focus(); }));
}
function showRowEvidence(row) {
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
    row.cells.forEach((cell, i) => { const td = node(i === 0 ? "th" : "td", cell.text || "No accepted value shown"); if (i === 0) td.scope = "row"; tr.append(td); });
    const td = node("td"), inspect = button("Source records", () => showRowEvidence(row), "evidence-link");
    inspect.setAttribute("aria-label", `Evidence: individual recorded facts · ${row.cells[0].text}`);
    td.append(inspect); tr.append(td); body.append(tr);
  });
  table.append(body); region.append(table);
  return region;
}
function renderSection(section) {
  // Stable section IDs and unchanged DOM preserve unrelated reading position.
  const serialized = JSON.stringify([section, section.assertionRefs.map(ref => run.assertions[ref])]);
  if (sectionVersions.get(section.id) === serialized) return;
  sectionVersions.set(section.id, serialized);
  let el = $("section-" + section.id);
  const focusedLabel = el?.contains(document.activeElement) ? document.activeElement.getAttribute("aria-label") : null;
  const hadFocus = el?.contains(document.activeElement);
  if (!el) { el = node("section", undefined, "report-section"); el.id = "section-" + section.id; $("report-sections").append(el); }
  const heading = node("div", undefined, "section-heading"); heading.append(node("h2", section.title), node("span", section.state, "section-state"));
  el.replaceChildren(heading);
  if (section.kind === "further_questions") el.append(node("p", "Unverified hypotheses and questions for further investigation", "notice"));
  for (const ref of [...section.assertionRefs, ...section.factRefs]) {
    const a = run.assertions[ref] || run.facts[ref], p = node("p", a.text);
    if (a.level === 3) p.append(node("span", " Provisional interpretation.", "metadata"));
    if (a.level === 4) p.append(node("span", " Unverified — for investigation.", "metadata"));
    const indicator = button("Source & reasoning", () => showAssertion(ref), "evidence-link");
    indicator.setAttribute("aria-label", `Evidence: ${classLabel[a.level]} · ${ref}`); p.append(indicator); el.append(p);
  }
  (section.tables || []).forEach(table => { el.append(node("p", table.qualification, "metadata"), renderTable(table)); });
  el.append(button("Refine this section", () => { sectionContext = section.id; $("brief").value = `Please revise “${section.title}”: `; $("brief").dispatchEvent(new Event("input")); setView("conversation"); $("brief").focus(); }, "evidence-link"));
  if (hadFocus) {
    const equivalent = [...el.querySelectorAll("button")].find(b => b.getAttribute("aria-label") === focusedLabel);
    if (equivalent) equivalent.focus({preventScroll: true});
    else { const h = el.querySelector("h2"); h.tabIndex = -1; h.focus({preventScroll: true}); }
  }
}
function render() {
  $("session-title").textContent = run.title;
  $("overall-state").textContent = paused ? "Paused · previous findings retained" : run.status;
  $("report-heading").textContent = run.title;
  $("report-scope").textContent = `Reporting date: ${run.reportingDate}. Scope: ${run.brief}`;
  const incomplete = run.tasks.some(t => t.state !== "Validated") || run.unanswered.length;
  $("report-status").textContent = `Draft — for review · ${run.status} · Qualified / incomplete findings`;
  $("overview").hidden = $("limitations").hidden = $("report-footer").hidden = false;
  renderPlan(); run.sections.forEach(renderSection);
  (run.messages || []).slice(messageCount).forEach(m => {
    const box = message(m.role === "user" ? "You" : "Assistant", m.text);
    if (m.assertionRef) box.append(node("p", "Provisional explanation — for review", "metadata"), button("Evidence for this explanation", () => showAssertion(m.assertionRef), "evidence-link"));
  });
  messageCount = (run.messages || []).length;
  $("limitation-list").replaceChildren(...run.limitations.map(l => node("li", l)));
  $("unanswered").replaceChildren(node("h3", "Unanswered research questions"), ...run.unanswered.map(u => node("p", u.reason, "notice")));
  $("pause").hidden = !run.hasWork;
  $("pause").textContent = paused ? "Resume research" : "Pause research";
  $("copy").disabled = $("export").disabled = false;
  $("submit").textContent = "Send message";
}
async function executeSteps(myGeneration) {
  if (busy) return;
  busy = true;
  try {
    while (run && !paused && !preparing && generation === myGeneration && run.hasWork) {
      const task = run.tasks.find(t => t.state === "Pending");
      announce(task ? task.title + ": retrieving records" : "Writing the research draft");
      const next = await api(`/runs/${run.id}/step`, {method: "POST", body: JSON.stringify({version: run.version})});
      if (generation !== myGeneration) break;
      if (!run || next.version >= run.version) run = next;
      render(); announce("Research draft and activity updated.");
      // A rendering opportunity between each accepted section, not one final
      // response pretending to be progressive research.
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 100)));
    }
    if (run && generation === myGeneration && !run.hasWork) {
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
   $("brief").value = "Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress have they made, and what happened to them?";
  $("brief").dispatchEvent(new Event("input")); $("brief").focus();
};
$("composer-form").addEventListener("submit", async event => {
  event.preventDefault(); const brief = $("brief").value; if (!brief.trim()) return;
  if (preparing) return;
  preparing = true; $("submit").disabled = true; $("submission-error").textContent = "";
  announce("Preparing research plan.");
  try {
    const next = await api(run ? `/runs/${run.id}/messages` : "/runs", {method: "POST", body: JSON.stringify(run ? {text: brief, sectionId: sectionContext} : {brief})});
    run = next; paused = false;
    sectionContext = null;
    if ($("brief").value === brief) $("brief").value = "";
    render();
    if (run.tasks.some(t => t.state === "Pending")) message("Assistant", "The plan is published. The report will develop as findings are retrieved.");
    $("plan-card").scrollIntoView({block: "start"});
    announce(run.status === "Research planning interrupted" ? "Research planning interrupted. Your request is retained." : run.hasWork ? "Research plan published. The draft will now be updated." : run.status);
    // Two animation frames + a short visible interval ensure the initial plan
    // is painted BEFORE even the first factual-query dispatch.
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 350))));
    preparing = false; executeSteps(generation);
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
