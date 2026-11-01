"""Bounded ordered SELECT paging; never return a truncated answer as complete."""

from .errors import NLQError
from .results import QueryResult, format_debug_payload
from .safety import MAX_RESULT_OFFSET, MAX_RESULT_ROWS, validate_sparql


def select_pages(query, *, fuseki, supported_predicates):
    """Page a query ending in LIMIT 100 with a total, deterministic ORDER BY."""
    if not query.rstrip().endswith("LIMIT 100") or "ORDER BY" not in query:
        raise NLQError("Paged SELECT requires an ordered, explicitly bounded query.")
    rows, offsets = [], []
    columns = None
    for offset in range(0, MAX_RESULT_OFFSET + 1, MAX_RESULT_ROWS):
        page_query = validate_sparql(
            query + (f" OFFSET {offset}" if offset else ""),
            supported_predicates=supported_predicates,
        )
        page = fuseki.query(page_query)
        if page.kind != "select" or len(page.rows) > MAX_RESULT_ROWS:
            raise NLQError("Unexpected paged SELECT response.")
        if columns is not None and columns != page.columns:
            raise NLQError("SELECT columns changed between bounded pages.")
        columns = page.columns
        rows.extend(page.rows)
        offsets.append(offset)
        if len(page.rows) < MAX_RESULT_ROWS:
            return QueryResult("select", columns, tuple(rows), format_debug_payload({
                "pagination": {"pageSize": MAX_RESULT_ROWS, "offsets": offsets},
                "columns": columns, "rows": rows,
            }))
    raise NLQError("The answer exceeds the bounded pagination range; no partial answer was returned.")
