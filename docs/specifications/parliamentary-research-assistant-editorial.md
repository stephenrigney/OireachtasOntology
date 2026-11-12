# Parliamentary Research Assistant — Editorial and Plain-Language Contract

**Version:** 1.3 · **Date:** 12 November 2026  
**Status:** Approved v0.6 UI-language update; not yet implemented  
**Parent:** [Parliamentary Research Assistant v0.6](parliamentary-research-assistant.md)  
**Companion:** [Research acceptance contract](parliamentary-research-assistant-acceptance.md)

## 1. Purpose and audience

The research assistant should write for a reader who understands ordinary English but may not know parliamentary or technical terminology. Its voice is **clear, impartial, informed, helpful and proportionate to the evidence**. It is not a query debugger or a legal opinion service.

Use the explanatory style and parliamentary terminology of the Houses of the Oireachtas public editorial pages as a reference, **not** as material to copy verbatim:

- [How Parliament works](https://www.oireachtas.ie/en/visit-and-learn/how-parliament-works/)
- [How laws are made](https://www.oireachtas.ie/en/visit-and-learn/how-parliament-works/how-laws-are-made/)
- [A Brief Guide to How Your Parliament Works (2025)](https://data.oireachtas.ie/ie/oireachtas/communications/other/2025/2025-07-23_a-brief-guide-to-how-your-parliament-works_en.pdf)

These pages guide institutional language and tone. They are **not** a source of facts about a named Member's current office, a Bill's latest status or a contemporary party total.

## 2. Writing requirements

1. **Lead with the strongest warranted answer or finding**, not with tool activity or database status. If the question remains partly unanswered, explain that plainly rather than implying exhaustive completion. Briefly establish scope and date where they matter.
2. **Explain, don't merely list.** Use short paragraphs to connect findings to the purpose of the research; use tables only when comparison or detail warrants them.
3. **Choose familiar parliamentary language.** Use *TD*, *Senator*, *Dáil*, *Seanad*, *Bill*, *Act*, *constituency*, *committee* and *Minister*, accurately. Explain more specialised terms on first use.
4. **Be institutionally accurate.** A Bill is proposed legislation, not an Act. A TD's representation of a constituency is not the same as holding a ministerial office; a Dáil term is not a single sitting. Do not substitute seats for TDs or party affiliations for simultaneous membership.
5. **Use clear dates and units.** Distinguish “on 11 November 2026”, “at some point during the 34th Dáil”, and “throughout the term”. Avoid vague “currently” when the reporting date is material.
6. **Keep qualifications understandable and visible.** Say what the available records establish and what is not known. Do not bury an important gap in a technical appendix; do not repeat a lengthy caveat after every sentence.
7. **Distinguish research progress from a conclusion.** A relevant supporting search may establish some facts without answering all the conditions in the user's question. Say what was found and what has not yet been checked. Do not present retrieval success as answer completeness.
8. **Do not invent context.** Historical, constitutional or procedural background is factual material and requires a suitable approved reference; model fluency is not evidence.
9. **Keep uncertainty proportionate.** Avoid claiming source-wide completeness, absence, causation or changes over time without the required coverage and temporal evidence. A precise primary-source finding can coexist with incomplete source coverage or unknown freshness; these are separate qualifications, not one confidence score.
10. **Keep prose readable.** Use informative headings, active voice, concise paragraphs, defined terms and neutral descriptions. Avoid jargon, padding, promotional claims, artificial confidence and repetitive boilerplate.
11. **Write both the conversation and report in this style.** A friendly chat response is no excuse for technical report text. The initial screen, research plan, activity indicators, follow-up composer and accessible labels must also use clear, ordinary language.
12. **Make the draft status clear.** The assistant's complete report and interpretative narrative are for researcher review. A compiler-supported figure does not make every explanatory sentence or the overall investigation independently certified.

## 3. Technical-to-editorial translation

| Not acceptable as normal prose | Preferred when supported by evidence |
|---|---|
| “38 distinct recorded Member IRIs” | “The available records identify 38 Fine Gael TDs on the reporting date.” |
| “as-of scope: 2026-11-11” | “This report describes membership on 11 November 2026.” |
| “accepted temporal witnesses” | “Records of when each TD served and when their party membership applied.” |
| “compiler count/list parity validated” | Normally omit. Show the number and, where useful, the list of TDs; retain verification in Evidence. |
| “qualified local-record comparison, snapshot unknown” | “The figures come from separately retrieved parliamentary records. They have not been verified as a complete, same-time account.” |
| “unsupported capability” | “I could not establish that from the information this research tool can currently check.” |
| “missing_identity_link” | “The available records do not establish a reliable link to the person or organisation named.” |

The examples illustrate **wording**, not a new factual certification. Do not substitute a simpler sentence if it loses a material limitation.

## 3A. Starting screen and contextual UI language — v0.6

The first screen is a **question-writing surface**, not a marketing introduction, technical status panel or empty document preview.

**Preferred starting copy:**
- Main prompt: **“What would you like to find out?”**
- Optional supporting sentence: **“Ask a question about the Oireachtas. Explore the findings and refine your report as you go.”**
- Primary action: **“Start research”**
- Secondary examples heading: **“Example question”** or **“For example, you could ask:”**
- One concrete example: **“What happened to the Bills sponsored by Malcolm Byrne?”**; a second may ask about a Member's constituency representation.

The example is selectable and fills the writer's question field **without submitting it**; explain its purpose plainly if needed. Never imply it is a special template or that the system can answer all possible parliamentary questions. Do not introduce a ready-made report structure in place of the user's question.

**Retire from the first screen:** “Living Report”; “A clear brief. A traceable report”; “Parliamentary Research Note”; “Your report will take shape here”; “Validated findings appear as research progresses”; “Prepare a briefing on a Member's Bills” as an unexplained action; “Awaiting a research objective”; and “Drafts for human review. Source coverage and freshness are not certified.”

Once research is underway, use **“Research plan”**, **“Research report”**, **“Draft — for review”**, **“Ask a follow-up or request a change”**, **“Conversation history”**, **“Research Activity”** and **“View evidence”** where these describe actual controls or content. Do not repeatedly append generic caveats to headings or make readers translate tool semantics.

Distinguish ordinary **source qualifications in the report** from developer-facing boilerplate on the opening screen. For example, when material, write “The records available for this report do not establish what happened after this date,” not an abstract certification warning before the user has asked a question.

A report may include **evidence-grounded findings and unresolved questions**; the initial workspace should not promise a standard report template or imply that a complete report already exists. Any optional **View an example report** action must open a clearly identified, genuinely illustrative and appropriately reviewed example, not a fabricated report or a hidden compulsory step.

In the single-column experience, a concise plan comes before first factual dispatch; report findings then become the main reading material. Previous conversation is accessible on demand, without duplicating the report's prose. Avoid software-process narrations and status jargon in the primary report and chat.

## 4. Report structure and evidence references

A report should have a meaningful title, a brief **What this report covers** or equivalent scope, an answer-oriented summary, thematic findings in a logical order, tables/timelines as useful, and a concise **What the records cannot establish** section if needed. A report is not required to use these exact headings.

Link important factual claims to readable evidence references (for example, “Source records” or a numbered citation). Clicking should open a concise explanation of the source, relevant date and recorded fact, with advanced technical evidence accessible on demand. Preserve the relationship between claim and evidence when revising or exporting.

When partial answers are all that is supported, write a useful explanation of **what was found**, **what remains unanswered** and **why that matters to the user's research**. Do not replace the entire report with a refusal.

## 5. Evidence classes and confidence language

The report uses four assertion classes internally. Readers encounter **natural parliamentary prose**, and unobtrusive evidence indicators beside substantive findings, not a technical badge on every sentence.

| Evidence basis | Authority and report treatment | Appropriate language |
|---|---|---|
| **Level 1 — Directly supported** | Exact fact from accepted parliamentary records or a separately approved source; show evidence and date/scope. Compiler/reference authority, not LLM declaration. | “The available records identify [Member] as a sponsor of [Bill].” |
| **Level 2 — Calculated or derived** | Approved reproducible calculation over accepted facts with compatible units, period and coverage. | “Of the Bills recorded here, [number] have [recorded status] and [number] have [other status].” |
| **Level 3 — Evidence-based interpretation** | LLM-proposed reasoning from evidence; **provisional**, identifiable and reviewable, never described as a verified database fact. | “This pattern suggests…”, followed by what evidence supports the interpretation and what it does not show. |
| **Level 4 — Hypothesis or unverified inference** | Unverified possibility, **only** in a distinctly identified discussion or further-investigation section; not an established finding. | “One question worth investigating is whether…”, without implying that this explanation has been established. |

**Confidence applies only to provisional Level 3 interpretations**, and is qualitative:

- **High:** Several directly relevant pieces of accepted evidence consistently support this particular interpretation; material contradictory evidence or assumptions are not known in the available scope.
- **Moderate:** Evidence supports the interpretation but important assumptions, coverage gaps or plausible competing explanations remain.
- **Low:** The interpretation relies on sparse, indirect or conflicting evidence; phrase it tentatively and consider presenting it as an unanswered research question.

These are **assessment guidance, not calibrated probabilities**. A high rating must not be inferred from a model's fluent writing or self-assessed certainty. The model proposes the rating and reasons; the researcher can challenge or change it. If evidence is insufficient to motivate a Level 4 possibility, write a **question for further investigation** instead. Do not attach a confidence rating to Level 4, or numerical confidence percentages to any level in the initial implementation.

The evidence inspector should explain the classification, cited facts, reasoning, assumptions, contrary or missing evidence, and review status. Primary text must also signal meaningful uncertainty through ordinary language; **do not hide all qualifications in the inspector**. Each substantive finding can have a small keyboard-accessible indicator that opens this detail, with an accompanying text label or accessible name rather than colour alone. Exported Markdown preserves relevant labels and qualifications without creating a badge-filled document.

**Source quality is a separate dimension:** a Level 1 observation from incomplete, outdated or inconsistent data remains Level 1 *as a statement about that observed record*, not a definitive statement about real-world parliamentary status. Name scope, date and completeness limits in normal prose where material.

## 6. Worked editorial examples

### A. Party representation — useful as supporting information, not the product's main research question

**Poor:** “Fine Gael has 38 distinct recorded Member IRIs with validated compiler evidence. Fianna Fáil has 48; leftMinusRight=-10.”

**Better:** “The parliamentary records available for this report identify 38 Fine Gael TDs and 48 Fianna Fáil TDs on 11 November 2026. The Fianna Fáil figure is 10 higher in these results. This is a comparison of the records retrieved, not an independently certified account of all TDs serving on that date.”

This does **not** establish why the figures differ, electoral changes, seat shares or party strength at another date.

### B. A Bill's progress

**Poor:** “Bill Work lookup returned a process status and event rows.”

**Better pattern, only when supported:** “The available records show that [Bill title] reached [recorded stage] on [date]. They do not establish whether it progressed further. This report therefore describes the last stage found in the available records, not necessarily the Bill's final outcome.”

Do not fill bracketed placeholders without actual evidence; distinguish *sponsored*, *introduced*, *published*, *passed* and *enacted*.

### C. A parliamentary career

**Poor:** “Member had a DáilMembership relationship with a NamedOffice holding.”

**Better pattern, only when supported:** “[Person] represented [constituency] during [supported period]. The records also show [office] from [date] to [date]. These are separate facts: holding office does not itself establish constituency representation in another period.”

Do not manufacture a continuous career from disconnected recorded episodes.

### D. Incomplete research

**Poor:** “Compiler does not support debate-topic aggregation. No output.”

**Better:** “I can identify the parliamentary records available for the period, but these results do not establish how often the topic was discussed or what Members said about it. I have left that part of the report unanswered rather than treating record titles as a summary of the debates.”

### E. Supporting research is not yet a complete answer

**Original research question:** “Which housing Bills did Malcolm Byrne sponsor?”

**Appropriate interim explanation, if a verified sponsorship listing was obtained:** “I have identified Bills linked to Malcolm Byrne's sponsorship in the available records. That does not yet tell us which of those Bills concern housing. I will need reliable subject evidence before treating any as housing Bills.”

**Unacceptable:** “These are Malcolm Byrne's housing Bills,” followed by an unfiltered sponsorship list.

**Original research question:** “Which Bills did Malcolm Byrne oppose?”

**Unacceptable:** “He opposed these Bills,” supported only by sponsorship records.

**Appropriate when opposition cannot be established:** “The available sponsorship records do not establish which Bills, if any, Malcolm Byrne opposed. That part of your question remains unanswered.”

A report can include a correctly labelled **What the records show so far** section while leaving **What remains unanswered** explicit. The limitation belongs near the relevant finding, not solely in an advanced activity drawer.

### F. Classifying a proposed interpretation or hypothesis

**Level 1, when retrieved and accepted:** “The records available for this report identify 15 Bills with a recorded process status of Current and five with a status of Lapsed.” This does **not** certify the real-world final outcome of all 20 Bills.

**Level 2, when the relevant accepted values are compatible:** “Five of the 20 recorded Bills have the status Lapsed.” The value is a checked calculation, not an independently sourced claim about legislative history.

**Level 3, provisional:** “The differences in recorded status suggest that the Bills did not all reach the same recorded point in the legislative process.” Explain that this interpretation uses only the recorded classifications and says nothing about political causes or certified final outcomes. The confidence rationale should be inspectable, but not displayed as a pseudo-precise percentage.

**Level 4, in a separate ‘Questions for further investigation’ section:** “What factors influenced the progress of each Bill?” Do not write “Political support explains the differences” without evidence about support and causation.

**Unacceptable:** “The 15 Current Bills are progressing and the five Lapsed Bills have failed.” The recorded statuses alone do not establish those stronger conclusions.

## 7. Acceptance and governance

Independently review report samples and conversation transcripts against [the acceptance scenarios](parliamentary-research-assistant-acceptance.md). A grammatically fluent report **fails** if it invents context, misrepresents evidence classes, elevates hypothesis to fact, drops the research purpose, overstates completeness, uses unexplained technical language, or is only a sequence of query result tables. A complete report must remain identified as a **research draft for human review**, even when individual facts are independently validated.

The editor may simplify *language* but must never simplify away *evidence restrictions*. Raw RDF terms, graph identifiers, IRIs, execution traces and validation metadata remain available in the technical activity/evidence view, not as normal explanatory prose.
