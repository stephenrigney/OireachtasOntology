"""Controlled research-outcome language, independent of query family or model.

Diagnostic strings are deliberately not inputs to this policy. A technical
cause must not become either a parliamentary finding or a model-invented cause.
"""
import re


DESCRIPTIONS = {
    "findings_available": ("Findings available", "The recorded findings and their sources are available in the report."),
    "integration_unavailable": ("Records found; not included", "Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist."),
    "unsupported_question": ("Question not answered", "I couldn't establish this from the available queries. This does not show that no such parliamentary records exist."),
    "no_matching_records": ("No matching records", "No matching records were found in the available data. The data may be incomplete."),
    "clarification_required": ("Clarification needed", "Please clarify the person, organisation or period intended before this question can be answered."),
    "identity_unresolved": ("Identity not established", "I couldn't reliably identify the person or organisation named. Please provide a fuller name or more context."),
    "execution_failure": ("Search interrupted", "The search couldn't be completed. No findings were established by this search."),
    "evidence_incomplete": ("Records not established", "The available information wasn't sufficient to establish findings for this question. This is not proof that no relevant records exist."),
}


def describe(kind):
    label, description = DESCRIPTIONS[kind]
    return {"kind": kind, "label": label, "description": description}


def classify(outcome, *, accepted, plan_validated, execution_completed):
    if accepted:
        return describe("findings_available")
    if outcome.interaction == "answer" and plan_validated and execution_completed:
        if outcome.selection_outcome == "no_matches":
            return describe("no_matching_records")
        if outcome.selection_outcome == "matches":
            return describe("integration_unavailable")
        # A successful scalar/boolean/other response is not proof that records
        # matched. Only the service executor can establish selection semantics.
        return {"kind": "integration_unavailable", "label": "Result not included",
                "description": "The search completed, but the application couldn't include its result in this report. No research findings were established by this search."}
    return describe({"unsupported_capability": "unsupported_question",
                     "clarification_required": "clarification_required",
                     "unresolved_identity": "identity_unresolved",
                     "execution_failure": "execution_failure",
                     "validation_failure": "execution_failure"}.get(outcome.interaction, "evidence_incomplete"))


# Enforce the ordinary-language boundary as well as guiding authorship. Exact
# technical text is retained separately, never silently rewritten or discarded.
INTERNAL_LANGUAGE = re.compile(
    r"\b(?:evidence[- ]shape|factual boundary|promot(?:ed|able|ion) facts?|compiler status|"
    r"projection|unsupported capability|missing_or_unaccepted_evidence|"
    r"structured factual|research[- ]evidence adapter|(?-i:SPARQL|IRIs?))\b", re.I)


def require_plain_language(text):
    if INTERNAL_LANGUAGE.search(text):
        raise ValueError("Use plain research language, not implementation terminology. Use the supplied researchOutcome descriptions for system-determined limitations; technical details belong in Research Activity.")
    return text
