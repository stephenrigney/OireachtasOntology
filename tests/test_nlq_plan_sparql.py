"""Deterministic semantic-plan to local-SPARQL compiler tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from poc.nlq.errors import NLQError
from poc.nlq.plan_contract import validate_query_plan
from poc.nlq.plan_sparql import PlanSparqlGenerator
from poc.nlq.structured_planner import PlannerResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
_GENERATOR = PlanSparqlGenerator(
    supported_predicates=supported_predicates(ROOT / "ontology"),
)
_MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
_DAIL_34 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
_SEANAD_26 = "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26"
_COLLECTION = "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_Fáil"
_COMMITTEE = "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/joint_committee_on_transport_and_communications"


def _entity(entity_id: str, entity_type: str, iri: str, label: str = "Local entity") -> dict:
    return {
        "id": entity_id,
        "type": entity_type,
        "label": label,
        "resolution": "resolved",
        "iri": iri,
    }


def _plan(*, entities=None, requirements=None, filters=None, temporal=None,
          aggregation=None, answer=None) -> dict:
    return validate_query_plan({
        "contractId": "https://data.oireachtas.ie/specs/query-plan-contract",
        "schemaVersion": 1,
        "contractVersion": "1.1.0",
        "intent": "deterministic compiler fixture",
        "source": "oireachtas",
        "entities": entities or [],
        "requirements": requirements or [],
        "filters": filters or [],
        "temporalConstraints": temporal or [],
        "aggregation": aggregation,
        "answerShape": answer or {"kind": "boolean"},
    })


def _generate(plan: dict, *, status: str = "validated_plan"):
    return _GENERATOR.generate(PlannerResult(status, plan=plan))


def _member_name_plan() -> dict:
    return _plan(
        entities=[_entity("member", "Member", _MEMBER, "Timmy Dooley")],
        requirements=[{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        answer={"kind": "fact", "target": "name"},
    )


def _member_term_plan() -> dict:
    return _plan(
        entities=[_entity("member", "Member", _MEMBER, "Timmy Dooley")],
        requirements=[{
            "id": "term-membership", "fact": "member_house_term_membership",
            "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
        }],
        answer={"kind": "entities", "entityType": "DailTerm"},
    )


def _collection_term_plan() -> dict:
    return _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("term", "DailTerm", _DAIL_34, "34th Dáil"),
        ],
        requirements=[{
            "id": "collection-membership", "fact": "member_collection_membership",
            "subject": {"entity": "member"},
            "object": {"type": "ParliamentaryMemberCollection"},
        }],
        temporal=[{
            "target": "collection-membership", "kind": "during",
            "period": {"entity": "term"},
        }],
        answer={"kind": "entities", "entityType": "ParliamentaryMemberCollection"},
    )


def _representation_term_plan() -> dict:
    return _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("term", "SeanadTerm", _SEANAD_26, "26th Seanad"),
        ],
        requirements=[{
            "id": "representation", "fact": "member_constituency_representation",
            "subject": {"entity": "member"}, "object": {"type": "SeanadPanel"},
        }],
        temporal=[{
            "target": "representation", "kind": "during",
            "period": {"entity": "term"},
        }],
        answer={"kind": "entities", "entityType": "SeanadPanel"},
    )


def _committee_code_plan() -> dict:
    return _plan(
        entities=[_entity("committee", "Committee", _COMMITTEE, "Joint Committee")],
        requirements=[{
            "id": "committee-code", "fact": "committee_code",
            "subject": {"entity": "committee"},
        }],
        answer={"kind": "fact", "target": "committee-code"},
    )


def _boolean_member_term_plan() -> dict:
    return _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("term", "DailTerm", _DAIL_34, "34th Dáil"),
        ],
        requirements=[{
            "id": "served-in", "fact": "member_house_term_membership",
            "subject": {"entity": "member"}, "object": {"entity": "term"},
        }],
        answer={"kind": "boolean"},
    )


def _count_dail_terms_plan() -> dict:
    return _plan(
        requirements=[{
            "id": "term-label", "fact": "parliamentary_term_label",
            "subject": {"type": "DailTerm"},
        }],
        aggregation={
            "operation": "count",
            "target": {"requirement": "term-label", "participant": "subject"},
            "groupBy": [],
        },
        answer={"kind": "count", "target": "aggregation"},
    )


def test_member_full_name_maps_to_reviewed_member_graph_and_exact_iri():
    result = _generate(_member_name_plan())

    assert result.generated
    assert result.query_form == "SELECT"
    assert "SELECT DISTINCT ?value0" in result.sparql
    assert f"VALUES ?entity0 {{ <{_MEMBER}> }}" in result.sparql
    assert "GRAPH ?graph_entity0" in result.sparql
    assert "foaf:name" in result.sparql
    assert "agents:Member" in result.sparql
    assert "https://data.oireachtas.ie/graph/member/" in result.sparql
    assert "GRAPH {" not in result.sparql
    assert "skos:prefLabel" not in result.sparql
    [trace] = result.generation_trace["requirements"]
    assert trace["pattern_ids"] == ["member-description"]
    assert trace["graph_families"] == ["member-records"]
    assert "queryableProperties:foaf:name" in trace["reviewed_contract_refs"]


def test_member_to_dail_term_uses_reviewed_membership_join_and_returns_resource():
    result = _generate(_member_term_plan())

    assert result.generated
    assert result.query_form == "SELECT"
    assert "SELECT DISTINCT ?role0" in result.sparql
    assert "members:hasMembersMembership" in result.sparql
    assert "members:inHouseTerm" in result.sparql
    assert "members:DailMembership" in result.sparql
    assert "agents:DailTerm" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in result.sparql
    assert "skos:prefLabel" not in result.sparql  # presentation is not execution
    assert result.generation_trace["requirements"][0]["pattern_ids"] == [
        "member-description", "house-term-description", "member-house-membership",
    ]


def test_member_membership_date_fact_uses_the_reviewed_date_range_path():
    plan = _plan(
        entities=[_entity("member", "Member", _MEMBER, "Timmy Dooley")],
        requirements=[{
            "id": "start-date", "fact": "member_parliamentary_membership_start_date",
            "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
        }],
        answer={"kind": "fact", "target": "start-date"},
    )

    result = _generate(plan)

    assert result.generated
    assert "members:hasMembershipDateRange" in result.sparql
    assert "members:DateRange" in result.sparql
    assert "members:StartDate" in result.sparql
    assert "members:EndDate" not in result.sparql
    assert result.generation_trace["answer_value_kind"] == "literal"


def test_entity_label_list_and_grouped_result_answer_shapes_are_compiled_explicitly():
    entity_plan = _member_term_plan()
    entity_plan["answerShape"] = {"kind": "entity", "entityType": "DailTerm"}
    entity_result = _generate(entity_plan)
    assert entity_result.generated
    assert entity_result.generation_trace["answer_value_kind"] == "resource"
    assert "SELECT DISTINCT ?role0" in entity_result.sparql

    label_plan = _member_name_plan()
    label_plan["answerShape"] = {"kind": "label", "target": "name"}
    label_result = _generate(label_plan)
    assert label_result.generated
    assert label_result.generation_trace["answer_value_kind"] == "literal"
    assert "SELECT DISTINCT ?value0" in label_result.sparql

    list_plan = _member_name_plan()
    list_plan["answerShape"] = {"kind": "list", "target": "name"}
    list_result = _generate(list_plan)
    assert list_result.generated
    assert "SELECT DISTINCT ?value0" in list_result.sparql

    grouped_plan = _plan(
        requirements=[{
            "id": "collection-membership", "fact": "member_collection_membership",
            "subject": {"type": "Member"},
            "object": {"type": "ParliamentaryMemberCollection"},
        }],
        aggregation={
            "operation": "count",
            "target": {"requirement": "collection-membership", "participant": "subject"},
            "groupBy": [{
                "requirement": "collection-membership", "participant": "object",
            }],
        },
        answer={"kind": "grouped_result", "target": "aggregation"},
    )
    grouped_result = _generate(grouped_plan)
    assert grouped_result.generated
    assert "COUNT(DISTINCT ?role0) AS ?count" in grouped_result.sparql
    assert "GROUP BY ?role1" in grouped_result.sparql


def test_member_collection_in_dail_term_joins_through_oireachtas_membership():
    result = _generate(_collection_term_plan())

    assert result.generated
    assert "members:inOireachtasMembership" in result.sparql
    assert "members:memberOfCollection" in result.sparql
    assert "members:inHouseTerm" in result.sparql
    assert "members:isPartyMembershipOf" not in result.sparql
    assert "members:PartyMembership" not in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/parties>" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in result.sparql
    assert result.generation_trace["temporal_constraints"] == [{
        "requirement": "collection-membership",
        "fact": "member_collection_membership",
        "kind": "during",
        "period_entity": "term",
        "patterns": ["member-house-membership"],
    }]
    [trace] = result.generation_trace["requirements"]
    assert set(trace["pattern_ids"]) == {
        "member-description", "member-collection-membership",
        "member-house-membership", "house-term-description",
    }
    assert "https://data.oireachtas.ie/graph/member/" in result.sparql


def test_member_representation_in_seanad_term_uses_membership_path():
    result = _generate(_representation_term_plan())

    assert result.generated
    assert "members:isRepresentativeFrom" in result.sparql
    assert "members:inHouseTerm" in result.sparql
    assert "members:SeanadMembership" in result.sparql
    assert "members:DailMembership" not in result.sparql
    assert "VALUES ?membershipType" not in result.sparql
    assert "agents:SeanadTerm" in result.sparql
    assert "members:SeanadPanel" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/constituencies>" in result.sparql
    assert result.generation_trace["requirements"][0]["pattern_ids"] == [
        "member-description", "house-term-description", "member-house-membership",
        "representation-reference",
    ]


def test_committee_code_uses_committee_owned_code_and_description_graph():
    result = _generate(_committee_code_plan())

    assert result.generated
    assert "members:committeeCode" in result.sparql
    assert "members:Committee" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/committees>" in result.sparql
    assert result.generation_trace["requirements"][0]["pattern_ids"] == ["committee-description"]
    assert "queryableProperties:members:committeeCode" in (
        result.generation_trace["requirements"][0]["reviewed_contract_refs"]
    )


def test_bill_year_and_status_list_has_title_relation_and_controlled_filters():
    plan = _plan(
        requirements=[
            {"id": "title", "fact": "bill_title", "subject": {"type": "Bill"}},
            {"id": "year", "fact": "bill_year", "subject": {"type": "Bill"}},
            {"id": "status", "fact": "bill_status", "subject": {"type": "Bill"}},
        ],
        filters=[
            {"requirement": "year", "field": "bill_year", "operator": "equals", "value": 2026},
            {"requirement": "status", "field": "bill_status", "operator": "equals", "value": "current"},
        ],
        answer={"kind": "entities", "entityType": "Bill"},
    )

    result = _generate(plan)

    assert result.generated
    assert result.semantic_answer_shape == {"kind": "entities", "entityType": "Bill"}
    assert "eli:title" in result.sparql
    assert "agents:legislativeYear" in result.sparql
    assert "eli-dl:process_status" in result.sparql
    assert "agents:Bill" in result.sparql
    assert 'FILTER(?value2 = "2026"^^<http://www.w3.org/2001/XMLSchema#integer>)' in result.sparql
    assert "FILTER(?billStatus0 = <https://data.oireachtas.ie/ontology#CurrentBill>)" in result.sparql


def test_named_bill_sponsor_is_bill_to_member_relation_and_returns_member_role():
    bill_iri = "https://data.oireachtas.ie/ie/oireachtas/bill/2026/93"
    member_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Malcolm-Byrne.D.2019-11-29"
    plan = _plan(
        entities=[
            _entity("bill", "Bill", bill_iri, "Artificial Intelligence Companion Services Bill"),
        ],
        requirements=[{
            "id": "sponsor", "fact": "bill_sponsor",
            "subject": {"entity": "bill"}, "object": {"type": "Member"},
        }],
        answer={"kind": "entities", "entityType": "Member"},
    )

    result = _generate(plan)

    assert result.generated
    assert "eli-dl:had_participation" in result.sparql
    assert "eli-dl:had_participant_person" in result.sparql
    assert f"VALUES ?entity0 {{ <{bill_iri}> }}" in result.sparql
    assert result.semantic_answer_shape == {"kind": "entities", "entityType": "Member"}
    assert member_iri not in result.sparql  # the answer Member is a type-only role


@pytest.mark.parametrize("fact", ["bill_status", "bill_sponsor"])
def test_generated_bill_facts_do_not_cross_associate_processes_in_one_graph(fact):
    dl = Namespace("http://data.europa.eu/eli/eli-draft-legislation-ontology#")
    oir = Namespace("https://data.oireachtas.ie/ontology#")
    eli = Namespace("http://data.europa.eu/eli/ontology#")
    dataset = Dataset()
    graph = dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2026/93"))
    own = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2026/93")
    other = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2026/94")
    for bill, status, member in [(own, oir.CurrentBill, URIRef(_MEMBER)),
                                  (other, oir.EnactedBill, URIRef(_MEMBER + "-other"))]:
        process = URIRef(str(bill) + "#process")
        delivery = URIRef(str(bill) + "#delivery")
        participation = URIRef(str(bill) + "#sponsor")
        graph.add((bill, RDF.type, dl.DraftLegislationWork))
        graph.add((bill, eli.type_document, oir.Bill))
        graph.add((bill, eli.title, Literal("Test Bill", lang="en")))
        graph.add((delivery, RDF.type, oir.BillDelivery))
        graph.add((delivery, dl.created_a_realization_of, bill))
        graph.add((delivery, dl.forms_part_of, process))
        graph.add((process, RDF.type, dl.LegislativeProcess))
        graph.add((process, dl.process_status, status))
        graph.add((process, dl.had_participation, participation))
        graph.add((participation, RDF.type, dl.Participation))
        graph.add((participation, dl.had_participant_person, member))
        member_graph = dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/" + str(member).split("/")[-1]))
        member_graph.add((member, RDF.type, oir.Member))
    requirement = {"id": "fact", "fact": fact, "subject": {"entity": "bill"}}
    if fact == "bill_sponsor":
        requirement["object"] = {"type": "Member"}
    answer = ({"kind": "entities", "entityType": "Member"} if fact == "bill_sponsor"
              else {"kind": "fact", "target": "fact"})
    plan = _plan(entities=[_entity("bill", "Bill", str(own))],
                 requirements=[requirement], answer=answer)
    generated = _generate(plan)
    assert generated.generated
    assert "eli-dl:created_a_realization_of" in generated.sparql
    rows = list(dataset.query(generated.sparql))
    assert len(rows) == 1
    assert rows[0][0] == (Literal("Current") if fact == "bill_status" else URIRef(_MEMBER))
    graph.remove((URIRef(str(own) + "#delivery"), dl.created_a_realization_of, own))
    assert not list(dataset.query(generated.sparql))


def test_office_holder_on_date_compiles_inclusive_officeholding_range():
    office_iri = "https://data.oireachtas.ie/office/o-000003"
    plan = _plan(
        entities=[_entity("office", "NamedOffice", office_iri, "Minister for Finance")],
        requirements=[{
            "id": "holding", "fact": "member_office_holding",
            "subject": {"type": "Member"},
        }],
        filters=[{
            "requirement": "holding", "field": "office", "operator": "equals",
            "value": {"entity": "office"},
        }],
        temporal=[{"target": "holding", "kind": "on", "date": "2021-07-01"}],
        answer={"kind": "entities", "entityType": "Member"},
    )

    result = _generate(plan)

    assert result.generated
    assert "members:hasOfficeHolding" in result.sparql
    assert "members:heldOffice" in result.sparql
    date_time = '"2021-07-01T00:00:00"^^<http://www.w3.org/2001/XMLSchema#dateTime>'
    assert f"FILTER(?officeStart0 <= {date_time})" in result.sparql
    assert f"!BOUND(?officeEnd0) || ?officeEnd0 >= {date_time}" in result.sparql
    assert result.semantic_answer_shape == {"kind": "entities", "entityType": "Member"}


def test_committee_debate_body_and_exact_date_compile_without_a_named_debate_entity():
    plan = _plan(
        requirements=[
            {"id": "identity", "fact": "debate_identity", "subject": {"type": "DebateRecord"}},
            {"id": "date", "fact": "debate_date", "subject": {"type": "DebateRecord"}},
        ],
        filters=[{
            "requirement": "identity", "field": "debate_body", "operator": "equals",
            "value": "committee-of-public-accounts",
        }],
        temporal=[{"target": "date", "kind": "on", "date": "2026-09-24"}],
        answer={"kind": "entities", "entityType": "DebateRecord"},
    )

    result = _generate(plan)

    assert result.generated
    assert "agents:DebateRecord" in result.sparql
    assert "agents:debateDate" in result.sparql
    assert "committee_of_public_accounts" in result.sparql
    assert "2026-09-24T00:00:00" in result.sparql
    assert "FILTER(REGEX(STR(?graph_debates_role0)" in result.sparql
    assert result.semantic_answer_shape == {"kind": "entities", "entityType": "DebateRecord"}


def test_boolean_member_term_query_is_ask_and_safety_validated():
    result = _generate(_boolean_member_term_plan())

    assert result.generated
    assert result.query_form == "ASK"
    assert result.sparql.startswith("PREFIX ")
    assert "ASK WHERE" in result.sparql
    assert "SELECT" not in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in result.sparql


def test_term_count_counts_distinct_semantic_target_not_intermediate_rows():
    result = _generate(_count_dail_terms_plan())

    assert result.generated
    assert result.query_form == "SELECT"
    assert "COUNT(DISTINCT ?role0) AS ?count" in result.sparql
    assert "GROUP BY" not in result.sparql
    assert "agents:DailTerm" in result.sparql
    assert "skos:prefLabel" in result.sparql


def test_count_of_a_single_entity_bound_by_iri_fails_closed():
    plan = _plan(
        entities=[_entity("term", "DailTerm", _DAIL_34, "34th Dáil")],
        requirements=[{
            "id": "term-label", "fact": "parliamentary_term_label",
            "subject": {"entity": "term"},
        }],
        aggregation={
            "operation": "count",
            "target": {"requirement": "term-label", "participant": "subject"},
            "groupBy": [],
        },
        answer={"kind": "count", "target": "aggregation"},
    )

    result = _generate(plan)

    assert result.status == "unsupported_generation"
    assert result.failure_class == "unsupported_aggregation_target"
    assert result.sparql is None


def test_filters_constrain_the_value_of_the_referenced_requirement_safely():
    member_name = _plan(
        entities=[_entity("member", "Member", _MEMBER, "Timmy Dooley")],
        requirements=[{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        filters=[{
            "requirement": "name", "field": "member_name", "operator": "equals",
            "value": 'Timmy "Dooley" } SERVICE <https://evil.example/x> #',
        }],
        answer={"kind": "fact", "target": "name"},
    )
    result = _generate(member_name)

    assert result.generated
    assert 'FILTER(?value0 = "Timmy \\"Dooley\\" } SERVICE <https://evil.example/x> #")' in result.sparql
    assert "SERVICE" in result.sparql  # only inside a serialized literal
    assert result.generation_trace["filters"][0]["requirement"] == "name"
    assert result.generation_trace["filters"][0]["value_variable"] == "?value0"


@pytest.mark.parametrize(
    ("operator", "syntax"),
    [("greater_than", ">"), ("greater_than_or_equal", ">="),
     ("less_than", "<"), ("less_than_or_equal", "<=")],
)
def test_numeric_filters_are_serialized_and_constrain_term_number(operator, syntax):
    plan = _plan(
        requirements=[{
            "id": "term-number", "fact": "parliamentary_term_number",
            "subject": {"type": "DailTerm"},
        }],
        filters=[{
            "requirement": "term-number", "field": "parliamentary_term_number",
            "operator": operator, "value": 33,
        }],
        answer={"kind": "fact", "target": "term-number"},
    )
    result = _generate(plan)

    assert result.generated
    assert f"FILTER(?value0 {syntax} \"33\"^^<http://www.w3.org/2001/XMLSchema#integer>)" in result.sparql


def test_entity_inequality_filter_targets_the_requirement_object_not_a_similar_role():
    plan = _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("collection", "ParliamentaryMemberCollection", _COLLECTION, "Fianna Fáil"),
        ],
        requirements=[{
            "id": "membership", "fact": "member_collection_membership",
            "subject": {"entity": "member"}, "object": {"type": "ParliamentaryMemberCollection"},
        }],
        filters=[{
            "requirement": "membership", "field": "parliamentary_collection",
            "operator": "not_equals", "value": {"entity": "collection"},
        }],
        answer={"kind": "entities", "entityType": "ParliamentaryMemberCollection"},
    )
    result = _generate(plan)

    assert result.generated
    assert "FILTER(?role0 != ?entity0)" in result.sparql
    assert result.generation_trace["filters"][0]["value_variable"] == "?role0"


def test_exists_filter_is_preserved_by_the_required_fact_pattern():
    plan = _plan(
        entities=[_entity("committee", "Committee", _COMMITTEE, "Joint Committee")],
        requirements=[{
            "id": "committee-code", "fact": "committee_code",
            "subject": {"entity": "committee"},
        }],
        filters=[{
            "requirement": "committee-code", "field": "committee_code", "operator": "exists",
        }],
        answer={"kind": "fact", "target": "committee-code"},
    )
    result = _generate(plan)

    assert result.generated
    assert "members:committeeCode" in result.sparql
    assert "FILTER(" not in result.sparql


@pytest.mark.parametrize(
    "plan_factory",
    [_member_name_plan, _member_term_plan, _collection_term_plan,
     _representation_term_plan, _committee_code_plan, _boolean_member_term_plan,
     _count_dail_terms_plan],
)
def test_repeated_generation_is_byte_deterministic(plan_factory):
    plan = plan_factory()

    assert _generate(plan).as_dict() == _generate(copy.deepcopy(plan)).as_dict()


def test_ambiguous_unresolved_set_valued_and_failed_plans_are_not_executable():
    ambiguous = _plan(
        entities=[{
            "id": "member", "type": "Member", "label": "Michael Collins",
            "resolution": "ambiguous", "candidates": [
                {"iri": _MEMBER, "label": "Michael Collins"},
                {"iri": _MEMBER + "2", "label": "Michael Collins"},
            ],
        }],
        requirements=[{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        answer={"kind": "fact", "target": "name"},
    )
    unresolved = _plan(
        entities=[{
            "id": "member", "type": "Member", "label": "Unknown Member",
            "resolution": "unresolved",
        }],
        requirements=[{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        answer={"kind": "fact", "target": "name"},
    )

    results = [
        _GENERATOR.generate(PlannerResult("clarification_required", plan=ambiguous)),
        _GENERATOR.generate(PlannerResult("validated_plan", plan=ambiguous)),
        _GENERATOR.generate(PlannerResult("unresolved_entity", plan=unresolved)),
        _GENERATOR.generate(PlannerResult("set_valued_member_identity")),
        _GENERATOR.generate(PlannerResult("invalid_model_output")),
    ]

    assert all(not result.generated and result.sparql is None for result in results)
    assert results[0].status == "rejected_plan"
    assert results[1].status == "unsupported_generation"
    assert results[1].failure_class == "entity_binding"
    assert results[2].status == "rejected_plan"
    assert results[3].failure_class == "set_valued_member_identity"
    assert results[4].failure_class == "planner_failure"


def test_invalid_final_plan_is_rejected_before_generation():
    result = _GENERATOR.generate(PlannerResult(
        "validated_plan",
        plan={"contractId": "wrong", "answerShape": {"kind": "boolean"}},
    ))

    assert result.status == "invalid_plan"
    assert result.failure_stage == "plan_validation"
    assert result.sparql is None


def test_valid_but_unreviewed_date_window_temporal_translation_fails_closed():
    plan = _plan(
        entities=[_entity("member", "Member", _MEMBER, "Timmy Dooley")],
        requirements=[{
            "id": "membership", "fact": "member_house_term_membership",
            "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
        }],
        temporal=[{
            "target": "membership", "kind": "during",
            "period": {"start": "2020-01-01", "end": "2020-12-31"},
        }],
        answer={"kind": "entities", "entityType": "DailTerm"},
    )
    result = _generate(plan)

    assert result.status == "unsupported_generation"
    assert result.failure_class == "unsupported_temporal_translation"
    assert "date-window temporal scope is not reviewed" in result.failure_reason
    assert result.sparql is None


def test_member_committee_membership_during_term_is_not_guessed():
    plan = _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("term", "DailTerm", _DAIL_34, "34th Dáil"),
        ],
        requirements=[{
            "id": "committee-membership", "fact": "member_committee_membership",
            "subject": {"entity": "member"}, "object": {"type": "Committee"},
        }],
        temporal=[{
            "target": "committee-membership", "kind": "during",
            "period": {"entity": "term"},
        }],
        answer={"kind": "entities", "entityType": "Committee"},
    )
    result = _generate(plan)

    assert result.status == "unsupported_generation"
    assert result.failure_class == "unsupported_temporal_translation"
    assert result.sparql is None


def test_member_term_requirement_and_during_scope_must_use_the_same_house_term_type():
    plan = _plan(
        entities=[
            _entity("member", "Member", _MEMBER, "Timmy Dooley"),
            _entity("term", "SeanadTerm", _SEANAD_26, "26th Seanad"),
        ],
        requirements=[{
            "id": "membership", "fact": "member_house_term_membership",
            "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
        }],
        temporal=[{
            "target": "membership", "kind": "during", "period": {"entity": "term"},
        }],
        answer={"kind": "boolean"},
    )

    result = _generate(plan)

    assert result.status == "unsupported_generation"
    assert result.failure_class == "incompatible_temporal_term_type"
    assert result.sparql is None


def test_unsafe_or_not_allowlisted_mapping_never_returns_executable_query(monkeypatch):
    unsafe_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/name>evil"
    plan = _plan(
        entities=[_entity("member", "Member", unsafe_iri, "Injected")],
        requirements=[{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        answer={"kind": "fact", "target": "name"},
    )
    result = _generate(plan)
    assert result.status == "unsupported_generation"
    assert result.failure_class == "invalid_entity_iri"
    assert result.sparql is None

    allowed = _member_name_plan()
    reduced = PlanSparqlGenerator(supported_predicates=frozenset({URIRef("urn:only:type")}))
    result = reduced.generate(PlannerResult("validated_plan", plan=allowed))
    assert result.status == "unsupported_generation"
    assert result.failure_class == "predicate_not_allowlisted"
    assert result.sparql is None


def test_safety_validator_failure_is_a_distinct_generation_outcome(monkeypatch):
    import poc.nlq.plan_sparql as module

    def reject(_query, *, supported_predicates):
        raise NLQError("SPARQL was rejected")

    monkeypatch.setattr(module, "validate_sparql", reject)
    result = module.PlanSparqlGenerator(
        supported_predicates=supported_predicates(ROOT / "ontology"),
    ).generate(PlannerResult("validated_plan", plan=_member_name_plan()))

    assert result.status == "safety_failure"
    assert result.failure_class == "sparql_safety_validation"
    assert result.sparql is None
    assert result.generation_trace["requirements"][0]["pattern_ids"] == ["member-description"]


def test_binding_evidence_is_preserved_outside_the_semantic_plan():
    evidence = ({"entityId": "member", "decision": "resolved_by_unique_context_match"},)
    plan = _member_name_plan()
    result = _GENERATOR.generate(PlannerResult(
        "validated_plan", plan=plan, binding_evidence=evidence,
    ))

    assert result.generated
    assert result.binding_evidence == evidence
    assert "binding_evidence" not in plan
    assert "binding_evidence" not in result.semantic_answer_shape


def test_query_has_no_unintended_predicates_or_default_graph_dependence():
    result = _generate(_collection_term_plan())

    assert result.generated
    assert "members:isPartyMembershipOf" not in result.sparql
    assert "members:activeDuringTerm" not in result.sparql
    assert "members:constituencyInHouseTerm" not in result.sparql
    assert "dct:temporal" not in result.sparql
    assert "SERVICE" not in result.sparql
    assert "FROM NAMED" not in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/parties>" in result.sparql
    assert "GRAPH ?graph_entity0" in result.sparql
