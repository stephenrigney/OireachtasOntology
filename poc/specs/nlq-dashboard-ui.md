# NLQ dashboard — approved UI design contract

**Status:** Approved visual design, implementation pending  
**Date:** 2026-11-06  
**Scope:** `poc/nlq` UI only; no compiler, ontology, query semantics or feedback-storage changes.  
**Companion image:** [Dashboard visual reference](nlq-dashboard-visual.svg) (vector rendition of the approved text-only-header mockup).

## Authority

Use this specification and the companion visual as the **binding design contract**, rather than interpreting "modern dashboard" freely. References: [Oireachtas debates](https://www.oireachtas.ie/en/debates/) and [Chamber Vote PoC](https://bubcass.github.io/chamber-vote-poc/?chamber=dail). These are visual-language references, not asset sources or frontend dependencies. Existing Query Service specs/code, and merged PRs #21 and #22, remain authoritative for functionality.

The mockup is authoritative for **appearance and layout**, not example results, party affiliations, Dáil numbers or query completion. Never hardcode its sample data, fake traces or result status.

## Visual tokens

Use central CSS custom properties. The intended light theme is **warm off-white page, near-white content boxes, clearly visible grey borders, dark text and restrained gold accents**.

| Role | Initial token | Constraint |
| --- | --- | --- |
| Page background | `#F6F3EA` | Warm off-white, distinct from cards |
| Main card surface | `#FFFFFF` | Near-white question, answer, explanation, feedback boxes; **not beige** |
| Subtle/inset surface | `#F7F6F2` | Inputs and inactive stages only |
| Primary text | `#202124` | Strong dark contrast |
| Secondary text | `#4A463D` | Readable supporting text |
| Gold accent / selected | `#6B5922` | Primary CTA, current stage, restrained highlights |
| Gold hover | `#473A16` | Hover/focus emphasis |
| Card/input border | `#ABB0B6` | Visible 1–1.5px outlines, not shadow-only separation |
| Soft separators | `#D4D7DB` | Dividers and table rows |
| Success | `#146B37` | With readable status text, not colour alone |
| Failure | `#A3272F` | With readable status text, not colour alone |
| Focus | `#3F3414` | Visible keyboard focus indicator |

Typography: IBM Plex Sans if available, otherwise system sans-serif (do not commit font binaries). Body at least 16px at default zoom; crisp hierarchy, bold card titles, comfortable line-height. Cards approximately 6–8px corner radii, 16–24px padding and 18–24px section gaps. Width about 1100–1240px, centred on desktop; single column on mobile. Prefer minimal shadow. Ensure WCAG AA contrast for meaningful text/control boundaries; test states and keyboard focus.

## Page composition, in order

1. **Text-only header:** `OIREACHTAS ONTOLOGY`, large `Natural language queries`, short subtitle and thin gold horizontal rule. **No harp, Leinster House image, logo, photography or AI imagery.**
2. **Ask a question:** white outlined card, clearly labelled generous input/textarea and gold primary Ask action. Preserve mode and continuation behaviour.
3. **Results:** white outlined card with actual answer shape (not necessarily a Member/party table), real outcome and any partial-coverage notices, error or absence-of-evidence qualifications. Preserve relevant official-source hyperlinks.
4. **How this query was processed:** white outlined card with three selectable stages: **Interpreted / Compiled / Executed**. Show a concise human explanation and stage-specific detail; keep plan JSON, SPARQL and diagnostics accessible behind disclosures. This *is* the core before/after explanation, not an additional feature.
5. **Response adequacy:** white outlined card with Yes/No only **when active opt-in feedback makes it available**. Preserve PR #22's expected-answer field for No, explicit Save and saved/error messages. Keep compact, discoverable Start/Stop Evidence Session controls and recording status. Do not display false recording status.

Initial/no-query state should emphasize the question form, not display a dummy result. Preserve link to `/capabilities`, Fuseki readiness, developer/debug details and all existing failure/clarification presentations.

## Compiler-stage semantics

The stages are **post-response navigation**, not a live progress indicator. No simulated running animation or new backend tracing required.

- **Interpreted:** present actual interpretation, relevant entities, temporal constraints, validated/draft state and unresolved-entity/clarification evidence when available.
- **Compiled:** present actual validated plan and generated SPARQL **only when produced**. If compilation was blocked, say so; do not imply it completed.
- **Executed:** show real execution outcome, answer, limitations, source-data unavailability or errors. An HTTP response is not itself proof of execution success.

If a stage is not reached or its output unavailable, label it honestly, disable it or omit it with explanation. The UI must never fabricate a trace or claim an unsupported request ran. Tabs/disclosures must work with keyboard and assistive technology. Only subtle optional transitions; respect reduced-motion settings.

## Compatibility and exclusions

- **PR #21:** Bill query features and outcomes must continue unchanged.
- **PR #22:** preserve opt-in session start/stop/recovery, feedback eligibility, Yes/No, expected answer requirement for No, immediate durable JSONL storage, API endpoints, saved/retry messages and no recording without consent.
- Preserve all current query routes, candidate-choice continuation, capabilities, Fuseki readiness, security/escaping of arbitrary text, plan/debug access, and outcome classifications.
- Keep FastAPI + Jinja with lightweight JS/CSS. No React/build-system migration solely for appearance.
- **Out of scope:** ontology/relationship graph explorer, separate "before and after" module, live execution animation, progress streams, invented KPIs, new query persistence or compiler changes.

## Verification and exit criteria

- Show desktop (approximately 1440px) and mobile (approximately 390px) screenshots against the reference; strong page/card distinction, nearly white cards, gold accents, text-only header and consistent spacing must be evident.
- Verify successful, unsupported, validation-failed, ambiguous/clarification, empty, incomplete-source and execution-error results; missing stages must not imply success.
- Existing plan/JSON/SPARQL/debug access remains discoverable without overwhelming normal users.
- Verify PR #22 states: off/on/restored/stopped, adequate/inadequate, save success and retry after failure. No recording outside active sessions.
- Pass existing NLQ and feedback regression tests plus targeted UI/state tests. No backend behaviour regression.
- Check responsive layout, keyboard access, focus and accessible status announcements; long technical blocks may scroll inside their containers.
- Agent's final implementation report must include comparison screenshots and material deviations. Escalate changes requiring additional backend instrumentation, frontend framework or a different visual direction.

**Companion visual is schematic, not a pixel-perfect test baseline.** Styling and functional behaviour above govern implementation.
