"""Independent source-to-RDF validation for the Committee owner graph."""
from __future__ import annotations

from importlib.resources import files

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from ..reference_coverage import (COMMITTEE_PURPOSES, COMMITTEE_TYPES,
                                 committee_identity)
from ..transforms.common import MEMBERS, OIR, datetime_literal, integer, string
from .houses import validate_rdf
from .reference import assert_expected


RESOURCES = files("oireachtas_etl.validation.resources")
TYPE_CONCEPTS = {
    "Select": OIR.SelectCommitteeType,
    "Joint": OIR.JointCommitteeType,
    "Special": OIR.SpecialCommitteeType,
}
PURPOSE_CONCEPTS = {
    "Policy": OIR.PolicyPurpose,
    "Shadow Department": OIR.ShadowDepartmentPurpose,
}


def _expected_committee_graph(records: list[dict]) -> Graph:
    """Build expected triples independently of the production transformer."""
    expected = Graph()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each Committee record must be an object")
        identity, term, _code, _number = committee_identity(
            record.get("uri"), house_code=record.get("houseCode"),
            house_no=record.get("houseNo"))
        subject = URIRef(identity)
        expected.add((subject, RDF.type, MEMBERS.Committee))
        expected.add((subject, MEMBERS.committeeInHouseTerm, URIRef(term)))
        if record.get("committeeCode") is not None:
            expected.add((subject, MEMBERS.committeeCode,
                          string(record["committeeCode"])))
        if record.get("committeeID") is not None:
            expected.add((subject, MEMBERS.committeeID,
                          integer(record["committeeID"])))

        types = record.get("committeeType", [])
        if not isinstance(types, list) or any(not isinstance(value, str) for value in types):
            raise ValueError("committeeType must be an array of strings")
        for value in set(types):
            if value in TYPE_CONCEPTS:
                expected.add((subject, OIR.hasCommitteeType, TYPE_CONCEPTS[value]))
            elif value in PURPOSE_CONCEPTS:
                expected.add((subject, OIR.hasCommitteePurpose, PURPOSE_CONCEPTS[value]))

        dates = record.get("committeeDateRange")
        if dates is not None:
            if (not isinstance(dates, dict) or set(dates) - {"start", "end"}
                    or dates.get("start") is None):
                raise ValueError("committeeDateRange must contain start and optional end")
            start = datetime_literal(dates["start"])
            period = URIRef(identity + "#committee-date-range")
            expected.add((subject, MEMBERS.hasCommitteeDateRange, period))
            expected.add((period, RDF.type, MEMBERS.DateRange))
            expected.add((period, MEMBERS.StartDate, start))
            if dates.get("end") is not None:
                end = datetime_literal(dates["end"])
                if end.toPython() < start.toPython():
                    raise ValueError("committeeDateRange has reverse dates")
                expected.add((period, MEMBERS.EndDate, end))

        names = record.get("committeeName", [])
        if not isinstance(names, list) or len(names) > 1:
            raise ValueError("committeeName must contain at most one selected name record")
        for name in names:
            if not isinstance(name, dict) or set(name) - {"nameEn", "nameGa"}:
                raise ValueError("selected Committee name has an invalid shape")
            for field, language in (("nameEn", "en"), ("nameGa", "ga")):
                value = name.get(field)
                if value is not None:
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f"{field} must be a non-empty string")
                    expected.add((subject, SKOS.prefLabel,
                                  Literal(value, lang=language)))
    return expected


def validate_source(records: list[dict]) -> None:
    if not isinstance(records, list) or not records:
        raise ValueError("Committee reference dataset must be a non-empty list")
    _expected_committee_graph(records)


def validate_shacl(graph: Graph) -> None:
    conforms, _, report = validate(
        graph, shacl_graph=RESOURCES.joinpath("committees.ttl").read_text(),
        shacl_graph_format="turtle", inference="none", abort_on_first=False)
    if not conforms:
        raise ValueError("SHACL validation failed:\n" + str(report))


def validate_quality(graph: Graph) -> None:
    failures = list(graph.query(
        RESOURCES.joinpath("committees-quality.rq").read_text()))
    if failures:
        raise ValueError("Committee quality checks failed: "
                         + "; ".join(str(row) for row in failures))


def validate_committees(records: list[dict], graph: Graph, *,
                        retained_graph: Graph | None = None) -> None:
    expected = _expected_committee_graph(records)
    if retained_graph is not None:
        expected += retained_graph
    assert_expected(graph, set(expected))
    validate_rdf(graph)
    validate_shacl(graph)
    validate_quality(graph)
