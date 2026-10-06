"""Post-publication competency checks scoped to the fixed named graphs."""
from importlib.resources import files
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD
from .loader import FusekiSparqlClient

QUERIES = files("oireachtas_etl.validation.resources")
EXPECTED = {
    "current-dail.rq": [{"term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"}],
    "current-seanad.rq": [{"term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/27"}],
    "term-details.rq": [{"number": "33", "house": "https://data.oireachtas.ie/house/dail", "start": "2020-02-08T00:00:00", "end": "2024-11-08T00:00:00"}],
}

def verify_houses_competency(client: FusekiSparqlClient) -> None:
    for filename, expected in EXPECTED.items():
        actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(QUERIES.joinpath(filename).read_text())]
        if actual != expected:
            raise ValueError(f"post-load competency check {filename} failed: expected {expected!r}, got {actual!r}")


PARTIES_EXPECTED = {
    "party-details.rq": [
        {"party": "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael", "code": "Fine_Gael", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"},
        {"party": "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent", "code": "Independent", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"},
    ],
}
CONSTITUENCIES_EXPECTED = {
    "representation-details.rq": [
        {"representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Mid-West", "kind": "DailConstituency", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"},
        {"representation": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/9/panel/Agricultural-Panel", "kind": "SeanadPanel", "term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/9"},
    ],
}
COMMITTEES_EXPECTED = {
    "committee-details.rq": [
        {"committee": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_finance",
         "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/33",
         "code": "FC", "en": "Select Committee on Finance",
         "ga": "An Roghchoiste um Airgeadas"},
    ],
}


def _verify(client: FusekiSparqlClient, expected_queries: dict[str, list[dict]]) -> None:
    for filename, expected in expected_queries.items():
        actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(QUERIES.joinpath(filename).read_text())]
        if actual != expected:
            raise ValueError(f"post-load competency check {filename} failed: expected {expected!r}, got {actual!r}")


def verify_parties_competency(client: FusekiSparqlClient) -> None:
    _verify(client, PARTIES_EXPECTED)


def verify_constituencies_competency(client: FusekiSparqlClient) -> None:
    _verify(client, CONSTITUENCIES_EXPECTED)


def verify_committees_competency(client: FusekiSparqlClient) -> None:
    _verify(client, COMMITTEES_EXPECTED)


def verify_member_competency(client: FusekiSparqlClient, graph_iri: str, member_iri: str, expected_triples: int | None = None) -> None:
    query = f'''SELECT ?member (COUNT(?membership) AS ?memberships) WHERE {{ GRAPH <{graph_iri}> {{ BIND(<{member_iri}> AS ?member) . <{member_iri}> a <https://data.oireachtas.ie/ontology#Member> . OPTIONAL {{ <{member_iri}> <https://data.oireachtas.ie/ontology/members#hasMembersMembership> ?membership }} }} }} GROUP BY ?member'''
    actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(query)]
    if len(actual) != 1 or actual[0].get("member") != member_iri or int(actual[0].get("memberships", "0")) < 1:
        raise ValueError(f"post-load Member competency check failed for {member_iri}")
    if expected_triples is not None:
        rows = client.query(f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}")
        if len(rows) != 1 or int(rows[0]["count"]["value"]) != expected_triples:
            raise ValueError(f"post-load Member graph count failed for {member_iri}")


def verify_bill_competency(client: FusekiSparqlClient, graph_iri: str, bill_iri: str, expected_triples: int | None = None) -> None:
    query = f'''SELECT ?bill ?latest WHERE {{ GRAPH <{graph_iri}> {{ BIND(<{bill_iri}> AS ?bill) . <{bill_iri}> a <http://data.europa.eu/eli/eli-draft-legislation-ontology#DraftLegislationWork> . <{bill_iri}#process> <http://data.europa.eu/eli/eli-draft-legislation-ontology#latest_activity> ?latest . ?latest a <http://data.europa.eu/eli/eli-draft-legislation-ontology#LegislativeActivity> }} }}'''
    actual = [{name: binding["value"] for name, binding in row.items()} for row in client.query(query)]
    if len(actual) != 1 or actual[0].get("bill") != bill_iri:
        raise ValueError(f"post-load Bill competency check failed for {bill_iri}")
    if expected_triples is not None:
        rows = client.query(f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}")
        if len(rows) != 1 or int(rows[0]["count"]["value"]) != expected_triples:
            raise ValueError(f"post-load Bill graph count failed for {bill_iri}")


# These acceptance parameters and rows are deliberately pinned to the Member
# golden fixture.  They exercise public query resources; operational per-PUT
# verification above remains data-independent.
MEMBER_FIXTURE_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
MEMBER_FIXTURE_PARAMETERS = {
    "members-of-term.rq": {"term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"},
    "member-representation.rq": {"member": MEMBER_FIXTURE_IRI},
    "member-party-at-time.rq": {"member": MEMBER_FIXTURE_IRI, "instant": "2025-01-01T00:00:00"},
    "member-service-history.rq": {"member": MEMBER_FIXTURE_IRI},
    "current-members.rq": {},
}
MEMBERS_COMPETENCY_EXPECTED = {
    "members-of-term.rq": [{"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/dail/34"}],
    "member-representation.rq": [
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/30/constituency/Clare"},
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31/constituency/Clare"},
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/32/constituency/Clare"},
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Clare"},
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/22/panel/Administrative-Panel"},
        {"member": MEMBER_FIXTURE_IRI, "representation": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26/panel/Nominated-by-the-Taoiseach"},
    ],
    "member-party-at-time.rq": [{"member": MEMBER_FIXTURE_IRI, "party": "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_Fáil", "start": "2024-11-29T00:00:00"}],
    "member-service-history.rq": [
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/dail/30", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/30"},
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/dail/31", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31"},
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/dail/32", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/32"},
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/dail/34", "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"},
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/seanad/22", "term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/22"},
        {"member": MEMBER_FIXTURE_IRI, "membership": MEMBER_FIXTURE_IRI + "/house/seanad/26", "term": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26"},
    ],
    "current-members.rq": [{"member": MEMBER_FIXTURE_IRI, "term": "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"}],
}


def render_member_competency_query(filename: str, parameters: dict[str, str] | None = None) -> str:
    """Render one bounded Member competency query with RDF terms, not text input."""
    if filename not in MEMBER_FIXTURE_PARAMETERS:
        raise ValueError(f"unknown Member competency query: {filename}")
    values = {**MEMBER_FIXTURE_PARAMETERS[filename], **(parameters or {})}
    query = QUERIES.joinpath(filename).read_text()
    for name, value in values.items():
        token = "{{" + name + "}}"
        if name == "instant":
            rendered = Literal(value, datatype=XSD.dateTime).n3()
        else:
            rendered = URIRef(value).n3()
        query = query.replace(token, rendered)
    if "{{" in query or "}}" in query:
        raise ValueError(f"unrendered Member competency parameter in {filename}")
    return query


def verify_members_competency(client: FusekiSparqlClient) -> None:
    """Execute the five fixture-pinned Member competency resources exactly."""
    for filename, expected in MEMBERS_COMPETENCY_EXPECTED.items():
        actual = [{name: binding["value"] for name, binding in row.items()}
                  for row in client.query(render_member_competency_query(filename))]
        if actual != expected:
            raise ValueError(f"post-load Members competency check {filename} failed: expected {expected!r}, got {actual!r}")
def verify_core_graph(client, graph_iri: str, payload: str) -> None:
    """Fail closed unless the entire remote resource graph equals the validated payload."""
    from rdflib import Graph, Literal, URIRef, BNode
    from rdflib.namespace import XSD

    expected = Graph().parse(data=payload, format="nt")
    rows = client.query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}")

    def term(binding):
        if not isinstance(binding, dict) or not isinstance(binding.get("value"), str):
            raise ValueError("malformed core graph verification response")
        kind = binding.get("type")
        if kind == "uri": return URIRef(binding["value"])
        if kind == "literal" or kind == "typed-literal":
            return Literal(binding["value"], lang=binding.get("xml:lang"),
                           datatype=URIRef(binding["datatype"]) if binding.get("datatype") else None)
        if kind == "bnode": return BNode(binding["value"])
        raise ValueError("unknown core graph verification term")

    def normalise(triple):
        return tuple(Literal(str(value)) if isinstance(value, Literal)
                     and value.language is None and value.datatype in (None, XSD.string)
                     else value for value in triple)

    try:
        actual = {normalise(tuple(term(row[key]) for key in ("s", "p", "o"))) for row in rows}
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("malformed core graph verification response") from error
    if actual != {normalise(triple) for triple in expected}:
        raise ValueError(f"core graph/state mismatch for {graph_iri}; retry verified whole-graph replacement")


# These public Debates query resources are parameterized with RDF terms rather
# than interpolated SPARQL text. They are exercised against disposable joined
# Debates/owner datasets by tests/test_debates_competency.py; no production
# publication path is changed here.
DEBATES_COMPETENCY_PARAMETER_TYPES = {
    "debate-records-by-body-date.rq": {
        "body": "iri", "body_graph": "iri", "body_type": "iri", "date": "dateTime",
    },
    "debate-record-sittings.rq": {"record": "iri"},
    "debate-ordered-components.rq": {"record": "iri", "container": "iri"},
    "debate-member-contributions.rq": {"member": "iri", "member_graph": "iri"},
    "debate-question-recipients.rq": {"member": "iri", "member_graph": "iri"},
    "debate-divisions-and-votes.rq": {
        "record": "iri", "member": "iri", "member_graph": "iri",
    },
    "debate-bill-event-sections.rq": {"bill": "iri", "bill_graph": "iri"},
    "debate-owner-office-holdings.rq": {
        "member": "iri", "member_graph": "iri", "office_graph": "iri",
    },
}


def render_debate_competency_query(filename: str, parameters: dict[str, str]) -> str:
    """Render a public Debates competency resource using RDF-term parameters."""
    parameter_types = DEBATES_COMPETENCY_PARAMETER_TYPES.get(filename)
    if parameter_types is None:
        raise ValueError(f"unknown Debates competency query: {filename}")
    if set(parameters) != set(parameter_types):
        raise ValueError(
            f"Debates competency parameters for {filename} must be "
            f"{sorted(parameter_types)!r}, got {sorted(parameters)!r}"
        )

    query = QUERIES.joinpath(filename).read_text()
    for name, parameter_type in parameter_types.items():
        value = parameters[name]
        if not isinstance(value, str) or not value:
            raise ValueError(f"Debates competency parameter {name} must be a non-empty string")
        if parameter_type == "dateTime":
            rendered = Literal(value, datatype=XSD.dateTime).n3()
        else:
            rendered = URIRef(value).n3()
        query = query.replace("{{" + name + "}}", rendered)
    if "{{" in query or "}}" in query:
        raise ValueError(f"unrendered Debates competency parameter in {filename}")
    return query
