"""Committee owner-graph transformation from consolidated Members evidence."""
from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from .common import MEMBERS, OIR, datetime_literal, integer, iri, string
from ..reference_coverage import committee_identity


TYPE_CONCEPTS = {
    "Select": OIR.SelectCommitteeType,
    "Joint": OIR.JointCommitteeType,
    "Special": OIR.SpecialCommitteeType,
}
PURPOSE_CONCEPTS = {
    "Policy": OIR.PolicyPurpose,
    "Shadow Department": OIR.ShadowDepartmentPurpose,
}


def transform_committees(records: list[dict]) -> Graph:
    """Emit only Committee-owned facts; membership tenure and roles stay local."""
    graph = Graph()
    graph.bind("members", MEMBERS)
    graph.bind("agents", OIR)
    graph.bind("skos", SKOS)
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each Committee record must be an object")
        subject, term, _house_code, _house_no = committee_identity(
            record.get("uri"), house_code=record.get("houseCode"),
            house_no=record.get("houseNo"))
        subject_ref = iri(subject)
        graph.add((subject_ref, RDF.type, MEMBERS.Committee))
        graph.add((subject_ref, MEMBERS.committeeInHouseTerm, URIRef(term)))

        if record.get("committeeCode") is not None:
            graph.add((subject_ref, MEMBERS.committeeCode,
                       string(record["committeeCode"])))
        if record.get("committeeID") is not None:
            graph.add((subject_ref, MEMBERS.committeeID,
                       integer(record["committeeID"])))

        classifications = record.get("committeeType", [])
        if not isinstance(classifications, list):
            raise ValueError("committeeType must be an array")
        for value in sorted(set(classifications)):
            if value in TYPE_CONCEPTS:
                graph.add((subject_ref, OIR.hasCommitteeType,
                           TYPE_CONCEPTS[value]))
            elif value in PURPOSE_CONCEPTS:
                graph.add((subject_ref, OIR.hasCommitteePurpose,
                           PURPOSE_CONCEPTS[value]))

        dates = record.get("committeeDateRange")
        if dates is not None:
            if not isinstance(dates, dict) or dates.get("start") is None:
                raise ValueError("committeeDateRange must contain a start")
            period = URIRef(f"{subject}#committee-date-range")
            start = datetime_literal(dates["start"])
            graph.add((period, RDF.type, MEMBERS.DateRange))
            graph.add((period, MEMBERS.StartDate, start))
            if dates.get("end") is not None:
                end = datetime_literal(dates["end"])
                if end.toPython() < start.toPython():
                    raise ValueError("committeeDateRange has reverse dates")
                graph.add((period, MEMBERS.EndDate, end))
            graph.add((subject_ref, MEMBERS.hasCommitteeDateRange, period))

        names = record.get("committeeName", [])
        if not isinstance(names, list):
            raise ValueError("committeeName must be an array")
        for name in names:
            if not isinstance(name, dict):
                raise ValueError("selected Committee name must be an object")
            if name.get("nameEn") is not None:
                value = name["nameEn"]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("English Committee name must be non-empty")
                graph.add((subject_ref, SKOS.prefLabel, Literal(value, lang="en")))
            if name.get("nameGa") is not None:
                value = name["nameGa"]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("Irish Committee name must be non-empty")
                graph.add((subject_ref, SKOS.prefLabel, Literal(value, lang="ga")))
    return graph
