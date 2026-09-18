from datetime import date, datetime, timezone
import re
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, RDF, SKOS, XSD

OIR = Namespace("https://data.oireachtas.ie/ontology#")
MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
ELIDL = Namespace("http://data.europa.eu/eli/eli-draft-legislation-ontology#")

def iri(value: str) -> URIRef:
    if not isinstance(value, str) or not value.startswith(("http://", "https://")) or any(c.isspace() for c in value):
        raise ValueError(f"invalid absolute IRI: {value!r}")
    return URIRef(value)

def integer(value: object) -> Literal:
    if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value))):
        raise ValueError(f"invalid integer: {value!r}")
    return Literal(int(value), datatype=XSD.integer)

def string(value: object) -> Literal:
    if not isinstance(value, str): raise ValueError(f"invalid string: {value!r}")
    return Literal(value, datatype=XSD.string)

def english(value: object) -> Literal:
    if not isinstance(value, str) or not value: raise ValueError("English label must be a non-empty string")
    return Literal(value, lang="en")

def midnight(value: object) -> Literal:
    if not isinstance(value, str): raise ValueError("date must be a YYYY-MM-DD string")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value): raise ValueError(f"invalid date: {value!r}")
    try: date.fromisoformat(value)
    except ValueError as error: raise ValueError(f"invalid date: {value!r}") from error
    return Literal(value + "T00:00:00", datatype=XSD.dateTime)


def datetime_literal(value: object) -> Literal:
    """Return a canonical xsd:dateTime literal for API dates or timestamps."""
    if not isinstance(value, str):
        raise ValueError(f"invalid date-time: {value!r}")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"invalid date-time: {value!r}") from error
        return Literal(value + "T00:00:00", datatype=XSD.dateTime)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid date-time: {value!r}") from error
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return Literal(parsed.isoformat(timespec="seconds"), datatype=XSD.dateTime)


def date_literal(value: object) -> Literal:
    """Return a validated canonical xsd:date literal."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"invalid date: {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid date: {value!r}") from error
    return Literal(value, datatype=XSD.date)
