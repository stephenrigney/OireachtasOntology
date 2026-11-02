"""Errors safe to display to a POC user."""


class NLQError(Exception):
    """A controlled failure while translating or querying a question."""

    def __init__(self, message: str, *, debug_output: str | None = None,
                 debug_source: str | None = None):
        super().__init__(message)
        self.debug_output = debug_output
        self.debug_source = debug_source


class IdentityNotFound(NLQError):
    """No grounded local identity was returned by a complete bounded lookup."""


class QueryLimitError(NLQError):
    """A safety cap prevents a complete identity/evidence decision."""


class QueryExecutionFailure(Exception):
    """Endpoint failure propagated to the structured request boundary.

    Deliberately separate from semantic/evidence NLQError handlers: transport
    and client-parse failures must not become missing-source-evidence outcomes.
    """

    def __init__(self, message: str, *, query: str):
        super().__init__(message)
        self.query = query
