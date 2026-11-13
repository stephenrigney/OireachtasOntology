"""Controlled research-outcome language, independent of query family or model.

Diagnostic strings are deliberately not inputs to this policy. A technical
cause must not become either a parliamentary finding or a model-invented cause.
"""
import re


DESCRIPTIONS = {
    "findings_available": ("Findings available", "The recorded findings and their sources are available in the report."),
    "integration_unavailable": ("Results could not be included", "Relevant records were found, but they couldn't be safely included in this report. This does not mean that no records exist."),
    "unsupported_question": ("Question not answered", "The available queries could not answer this question. This does not show that no such parliamentary records exist."),
    "no_matching_records": ("No matching records", "No matching records were found in the available data. The data may be incomplete."),
    "clarification_required": ("Clarification needed", "Please clarify the person, organisation or period intended before this question can be answered."),
    "identity_unresolved": ("Identity not established", "I couldn't reliably identify the person or organisation named. Please provide a fuller name or more context."),
    "execution_failure": ("Search could not be completed", "The records search could not be completed, so it established no findings. The reason has not been established; see Research Activity for technical details."),
    "query_validation_failure": ("Question could not be checked", "This question could not be checked safely, so no findings were established by this search. Try clarifying or narrowing it rather than retrying unchanged."),
    "planner_failure": ("Research could not be planned", "This part could not be planned safely, so no search was run. Try again, or clarify or narrow the question if the problem continues."),
    "evidence_incomplete": ("Evidence not established", "The available records did not establish findings for this question. This does not show that no relevant records exist."),
}

FAILURE_DETAILS = {
    "findings_available": (None, False),
    "integration_unavailable": ("evidence_handoff", False),
    "unsupported_question": ("query_selection", False),
    "no_matching_records": ("query_execution", False),
    "clarification_required": ("query_interpretation", False),
    "identity_unresolved": ("query_interpretation", False),
    "execution_failure": ("query_execution", True),
    "query_validation_failure": ("query_validation", False),
    "planner_failure": ("query_planning", True),
    "evidence_incomplete": ("evidence_assessment", False),
}


def describe(kind):
    label, description = DESCRIPTIONS[kind]
    stage, retryable = FAILURE_DETAILS[kind]
    return {"kind": kind, "label": label, "description": description,
            "failureStage": stage, "retryable": retryable}


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
        result = describe("integration_unavailable")
        if outcome.selection_outcome != "matches":
            result["label"] = "Result not included"
            result["description"] = "The search completed, but its result could not be safely included. No findings were established by this search."
        return result
    if outcome.interaction == "validation_failure":
        if outcome.status == "unsupported_mapping":
            return describe("unsupported_question")
        return describe("query_validation_failure")
    return describe({"unsupported_capability": "unsupported_question",
                     "clarification_required": "clarification_required",
                     "unresolved_identity": "identity_unresolved",
                     "execution_failure": "execution_failure"}.get(outcome.interaction, "evidence_incomplete"))


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
