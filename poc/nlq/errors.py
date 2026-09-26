"""Errors safe to display to a POC user."""


class NLQError(Exception):
    """A controlled failure while translating or querying a question."""

    def __init__(self, message: str, *, debug_output: str | None = None,
                 debug_source: str | None = None):
        super().__init__(message)
        self.debug_output = debug_output
        self.debug_source = debug_source
