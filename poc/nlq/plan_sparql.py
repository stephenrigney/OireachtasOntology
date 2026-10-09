"""Deterministic local SPARQL compilation for accepted semantic query plans.

This is a separate Phase 2 execution path.  It consumes ``PlannerResult``
objects, not question text, and deliberately does not participate in the live
Phase 1 browser pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from rdflib import Literal, URIRef

from .contract import load_query_contract
from .errors import NLQError
from .plan_contract import QueryPlanContractError, validate_query_plan
from .safety import validate_sparql
from .structured_planner import PlannerResult


_QUERY_SCHEMA = load_query_contract()
_NAMESPACES: dict[str, str] = _QUERY_SCHEMA["namespaces"]
_QUERYABLE_CLASSES = frozenset(_QUERY_SCHEMA["queryableClasses"])
_QUERYABLE_PROPERTIES = frozenset(_QUERY_SCHEMA["queryableProperties"])
_GRAPH_FAMILIES = {
    family["id"]: family for family in _QUERY_SCHEMA["graphFamilies"]
}
_GRAPH_FAMILY_ORDER = tuple(_GRAPH_FAMILIES)
_PATTERNS = {
    pattern["id"]: pattern for pattern in _QUERY_SCHEMA["emittedRdfPatterns"]
}
_PATTERN_ORDER = {pattern_id: i for i, pattern_id in enumerate(_PATTERNS)}
_LOCAL_MEMBER_GRAPH_PREFIX = _GRAPH_FAMILIES["member-records"]["graph"][
    "iriTemplate"
].split("{", 1)[0]
_MEMBER_EXTERNAL_GRAPH_SUFFIX = "/external-links"


@dataclass(frozen=True)
class _EntityTypeMapping:
    rdf_type: str
    graph_family: str
    pattern_id: str | None = None


@dataclass(frozen=True)
class _FactMapping:
    """Reviewed semantic-fact dispatch; no predicate is derived from an ID."""

    pattern_ids: tuple[str, ...]
    value_kind: str
    predicate: str | None = None


@dataclass(frozen=True)
class _FilterMapping:
    fact: str
    value_kind: str
    predicate: str | None = None


# Every type, graph family, pattern ID, and predicate below is an explicit
# reference to query-schema-contract.json.  An absent entry fails closed.
_ENTITY_TYPES: dict[str, _EntityTypeMapping] = {
    "Member": _EntityTypeMapping("agents:Member", "member-records", "member-description"),
    "House": _EntityTypeMapping("agents:House", "houses"),
    "DailTerm": _EntityTypeMapping("agents:DailTerm", "houses", "house-term-description"),
    "SeanadTerm": _EntityTypeMapping("agents:SeanadTerm", "houses", "house-term-description"),
    "ParliamentaryMemberCollection": _EntityTypeMapping(
        "members:ParliamentaryMemberCollection", "parties",
    ),
    "DailConstituency": _EntityTypeMapping("members:DailConstituency", "constituencies"),
    "SeanadPanel": _EntityTypeMapping("members:SeanadPanel", "constituencies"),
    "Committee": _EntityTypeMapping("members:Committee", "committees", "committee-description"),
}

_FACTS: dict[str, _FactMapping] = {
    "member_identity": _FactMapping(("member-description",), "resource"),
    "member_full_name": _FactMapping(("member-description",), "label", "foaf:name"),
    "member_house_term_membership": _FactMapping(("member-house-membership",), "resource"),
    "member_parliamentary_membership_start_date": _FactMapping(
        ("member-house-membership",), "literal", "members:StartDate",
    ),
    "member_parliamentary_membership_end_date": _FactMapping(
        ("member-house-membership",), "literal", "members:EndDate",
    ),
    "member_collection_membership": _FactMapping(("member-collection-membership",), "resource"),
    "member_constituency_representation": _FactMapping(
        ("member-house-membership", "representation-reference"), "resource",
    ),
    "member_committee_membership": _FactMapping(("committee-membership-reference",), "resource"),
    "house_label": _FactMapping((), "label"),
    "parliamentary_term_label": _FactMapping(("house-term-description",), "label"),
    "parliamentary_term_number": _FactMapping(
        (), "literal", "agents:termNo",
    ),
    "parliamentary_collection_label": _FactMapping((), "label"),
    "constituency_panel_label": _FactMapping((), "label"),
    "committee_label": _FactMapping(("committee-description",), "label"),
    "committee_code": _FactMapping((), "literal", "members:committeeCode"),
}

_LABEL_FACT_TYPES = {
    "house_label": "House",
    "parliamentary_term_label": "DailTerm",  # SeanadTerm is also supported below.
    "parliamentary_collection_label": "ParliamentaryMemberCollection",
    "constituency_panel_label": "DailConstituency",  # SeanadPanel is also supported below.
    "committee_label": "Committee",
}

_FILTERS: dict[str, _FilterMapping] = {
    "member_name": _FilterMapping("member_full_name", "string", "foaf:name"),
    "parliamentary_term_number": _FilterMapping(
        "parliamentary_term_number", "number", "agents:termNo",
    ),
    "parliamentary_collection": _FilterMapping("member_collection_membership", "entity"),
    "committee_code": _FilterMapping("committee_code", "string", "members:committeeCode"),
}

_TERM_MEMBERSHIP_TYPES = {
    "DailTerm": "members:DailMembership",
    "SeanadTerm": "members:SeanadMembership",
}
_TERM_SCOPED_FACTS = frozenset({
    "member_house_term_membership",
    "member_collection_membership",
    "member_constituency_representation",
})


class _UnsupportedGeneration(ValueError):
    def __init__(self, reason: str, failure_class: str = "unsupported_generation"):
        super().__init__(reason)
        self.failure_class = failure_class


@dataclass(frozen=True)
class GenerationResult:
    """Inspectable result of one deterministic plan compilation attempt."""

    status: str
    sparql: str | None = None
    query_form: str | None = None
    semantic_answer_shape: dict[str, Any] | None = None
    generation_trace: dict[str, Any] = field(default_factory=dict)
    failure_class: str | None = None
    failure_reason: str | None = None
    failure_stage: str | None = None
    binding_evidence: tuple[dict[str, Any], ...] = ()

    @property
    def generated(self) -> bool:
        return self.status == "generated" and self.sparql is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sparql": self.sparql,
            "query_form": self.query_form,
            "semantic_answer_shape": self.semantic_answer_shape,
            "generation_trace": self.generation_trace,
            "failure_class": self.failure_class,
            "failure_reason": self.failure_reason,
            "failure_stage": self.failure_stage,
            "binding_evidence": list(self.binding_evidence),
        }


@dataclass
class _GraphFragment:
    family_id: str
    graph_term: str
    triples: set[tuple[str, str, str]] = field(default_factory=set)


class _Compiler:
    def __init__(self, plan: dict[str, Any], supported_predicates: frozenset[URIRef]):
        self.plan = plan
        self.supported_predicates = supported_predicates
        self.entities = {entity["id"]: entity for entity in plan["entities"]}
        participant_types: set[str] = set()
        used_entity_ids: set[str] = set()
        for requirement in plan["requirements"]:
            for position in ("subject", "object"):
                participant = requirement.get(position)
                if participant is not None:
                    if "entity" in participant:
                        used_entity_ids.add(participant["entity"])
                    else:
                        participant_types.add(participant["type"])
        for filter_ in plan["filters"]:
            value = filter_.get("value")
            if isinstance(value, dict) and "entity" in value:
                used_entity_ids.add(value["entity"])
        for constraint in plan["temporalConstraints"]:
            period = constraint.get("period")
            if isinstance(period, dict) and "entity" in period:
                used_entity_ids.add(period["entity"])
        if used_entity_ids != set(self.entities):
            unused = sorted(set(self.entities) - used_entity_ids)
            raise _UnsupportedGeneration(
                "The plan contains entity mention(s) that are not connected to a semantic requirement: "
                + ", ".join(unused),
                "unbound_entity_reference",
            )
        self.entity_vars = {
            entity_id: f"?entity{index}"
            for index, entity_id in enumerate(sorted(self.entities))
        }
        self.role_vars = {
            entity_type: f"?role{index}"
            for index, entity_type in enumerate(sorted(participant_types))
        }
        requirement_order = sorted(plan["requirements"], key=lambda item: item["id"])
        self.requirement_indices = {
            requirement["id"]: index
            for index, requirement in enumerate(requirement_order)
        }
        self.requirements = {item["id"]: item for item in requirement_order}
        self.fragments: dict[tuple[str, str], _GraphFragment] = {}
        self.requirement_trace: dict[str, dict[str, Any]] = {
            requirement["id"]: {
                "requirement": requirement["id"],
                "fact": requirement["fact"],
                "pattern_ids": [],
                "graph_families": [],
                "reviewed_properties": [],
                "reviewed_contract_refs": [],
            }
            for requirement in requirement_order
        }
        self.filter_trace: list[dict[str, Any]] = []
        self.temporal_trace: list[dict[str, Any]] = []
        self.used_prefixes: set[str] = set()
        self.filter_expressions: list[str] = []
        self.values_clauses: list[str] = []
        self._value_vars: dict[str, dict[str, str]] = {}
        self._preflight()

    def _preflight(self) -> None:
        for requirement in self.requirements.values():
            fact = requirement["fact"]
            if fact not in _FACTS:
                raise _UnsupportedGeneration(
                    f"No reviewed local RDF mapping exists for semantic fact {fact!r}.",
                    "unreviewed_fact_mapping",
                )
            for pattern_id in _FACTS[fact].pattern_ids:
                self._validate_pattern(pattern_id)
        for entity in self.entities.values():
            if entity["resolution"] != "resolved" or not entity.get("iri"):
                raise _UnsupportedGeneration(
                    f"Entity {entity['id']!r} is {entity['resolution']}; singular local IRI binding is required.",
                    "entity_binding",
                )
            _iri_n3(entity["iri"])
        for requirement in self.requirements.values():
            for position in ("subject", "object"):
                participant = requirement.get(position)
                if participant is not None:
                    entity_type = self._participant_type(participant)
                    self._validate_entity_type(entity_type)
        for filter_ in self.plan["filters"]:
            mapping = _FILTERS.get(filter_["field"])
            if mapping is None:
                raise _UnsupportedGeneration(
                    f"No reviewed RDF filter mapping exists for field {filter_['field']!r}.",
                    "unreviewed_filter_mapping",
                )
            if self.requirements[filter_["requirement"]]["fact"] != mapping.fact:
                raise _UnsupportedGeneration(
                    f"Filter {filter_['field']!r} is not mapped to the fact of requirement "
                    f"{filter_['requirement']!r}.",
                    "filter_requirement_mismatch",
                )
            if mapping.predicate:
                self._validate_property(mapping.predicate)
            if filter_["operator"] != "exists" and mapping.value_kind == "entity":
                entity_id = filter_["value"]["entity"]
                _iri_n3(self.entities[entity_id]["iri"])
        for constraint in self.plan["temporalConstraints"]:
            requirement = self.requirements[constraint["target"]]
            fact = requirement["fact"]
            if constraint["kind"] != "during" or fact not in _TERM_SCOPED_FACTS:
                raise _UnsupportedGeneration(
                    f"Temporal kind {constraint['kind']!r} is not mapped to a reviewed "
                    f"date/term path for fact {fact!r}; no date semantics are inferred.",
                    "unsupported_temporal_translation",
                )
            period = constraint.get("period")
            if not isinstance(period, dict) or "entity" not in period:
                raise _UnsupportedGeneration(
                    f"Fact {fact!r} supports only a referenced HouseTerm for 'during'; "
                    "date-window temporal scope is not reviewed.",
                    "unsupported_temporal_translation",
                )
            period_entity = self.entities[period["entity"]]
            if period_entity["type"] not in {"DailTerm", "SeanadTerm"}:
                raise _UnsupportedGeneration(
                    "A 'during' term constraint must reference a DailTerm or SeanadTerm.",
                    "unsupported_temporal_translation",
                )
            if fact == "member_house_term_membership":
                object_type = self._participant_type(requirement["object"])
                if object_type != period_entity["type"]:
                    raise _UnsupportedGeneration(
                        "A Member-to-term requirement and its 'during' constraint must use "
                        "the same HouseTerm type.",
                        "incompatible_temporal_term_type",
                    )
            self._validate_entity_type(period_entity["type"])
        for filter_ in self.plan["filters"]:
            if filter_["operator"] == "exists":
                continue
            mapping = _FILTERS[filter_["field"]]
            if mapping.value_kind == "string" and not isinstance(filter_["value"], str):
                raise _UnsupportedGeneration("String filter value has an incompatible type.", "invalid_filter_value")
            if mapping.value_kind == "number" and (
                isinstance(filter_["value"], bool)
                or not isinstance(filter_["value"], (int, float))
            ):
                raise _UnsupportedGeneration("Numeric filter value has an incompatible type.", "invalid_filter_value")
        self._validate_answer_shape()

    def _validate_pattern(self, pattern_id: str) -> None:
        pattern = _PATTERNS.get(pattern_id)
        if pattern is None:
            raise _UnsupportedGeneration(
                f"Reviewed RDF pattern {pattern_id!r} is absent from the query-schema contract.",
                "query_schema_mapping_mismatch",
            )
        if pattern.get("queryableInLocalNlq") is False or pattern.get("availability") != "emitted":
            raise _UnsupportedGeneration(
                f"RDF pattern {pattern_id!r} is not currently queryable local data.",
                "non_queryable_rdf_pattern",
            )

    def _validate_entity_type(self, entity_type: str) -> None:
        mapping = _ENTITY_TYPES.get(entity_type)
        if mapping is None:
            raise _UnsupportedGeneration(
                f"No reviewed RDF class/graph mapping exists for entity type {entity_type!r}.",
                "unreviewed_entity_mapping",
            )
        if mapping.rdf_type not in _QUERYABLE_CLASSES or mapping.graph_family not in _GRAPH_FAMILIES:
            raise _UnsupportedGeneration(
                f"The local query contract does not expose the reviewed type mapping for {entity_type!r}.",
                "query_schema_mapping_mismatch",
            )
        if mapping.pattern_id:
            self._validate_pattern(mapping.pattern_id)

    def _validate_property(self, qname: str) -> None:
        if qname not in _QUERYABLE_PROPERTIES:
            raise _UnsupportedGeneration(
                f"Predicate {qname!r} is absent from query-schema-contract.json.",
                "query_schema_mapping_mismatch",
            )
        prefix = qname.split(":", 1)[0]
        if prefix not in _NAMESPACES:
            raise _UnsupportedGeneration(
                f"Predicate prefix {prefix!r} is absent from the query-schema contract.",
                "query_schema_mapping_mismatch",
            )
        if URIRef(_NAMESPACES[prefix] + qname.split(":", 1)[1]) not in self.supported_predicates:
            raise _UnsupportedGeneration(
                f"Predicate {qname!r} is not accepted by the active SPARQL safety allowlist.",
                "predicate_not_allowlisted",
            )

    def _participant_type(self, participant: dict[str, Any]) -> str:
        if "entity" in participant:
            return self.entities[participant["entity"]]["type"]
        return participant["type"]

    def _participant_var(self, participant: dict[str, Any]) -> str:
        if "entity" in participant:
            return self.entity_vars[participant["entity"]]
        return self.role_vars[participant["type"]]

    def _entity_var(self, entity_id: str) -> str:
        return self.entity_vars[entity_id]

    def _member_graph_var(self, anchor_var: str) -> str:
        return "?graph_" + anchor_var[1:]

    def _graph_term(self, family_id: str, *, anchor_var: str | None = None) -> str:
        family = _GRAPH_FAMILIES[family_id]
        graph = family["graph"]
        if graph["kind"] == "fixed":
            return _iri_n3(graph["iri"])
        if graph["kind"] == "resource-pattern" and family_id == "member-records" and anchor_var:
            return self._member_graph_var(anchor_var)
        raise _UnsupportedGeneration(
            f"Graph family {family_id!r} cannot be rendered as an explicit local graph pattern.",
            "unsupported_graph_family",
        )

    def _trace(self, requirement_id: str, *, pattern_id: str | None = None,
               family_id: str | None = None, property_qname: str | None = None,
               contract_ref: str | None = None) -> None:
        entry = self.requirement_trace[requirement_id]
        if pattern_id is not None and pattern_id not in entry["pattern_ids"]:
            entry["pattern_ids"].append(pattern_id)
        if family_id is not None and family_id not in entry["graph_families"]:
            entry["graph_families"].append(family_id)
        if property_qname is not None and property_qname not in entry["reviewed_properties"]:
            entry["reviewed_properties"].append(property_qname)
        if contract_ref is not None and contract_ref not in entry["reviewed_contract_refs"]:
            entry["reviewed_contract_refs"].append(contract_ref)

    def _add_triple(self, requirement_id: str, family_id: str, anchor_var: str | None,
                    subject: str, predicate: str, object_: str,
                    *, pattern_id: str | None = None, contract_ref: str | None = None) -> None:
        if predicate != "rdf:type":
            self._validate_property(predicate)
        elif predicate not in _QUERYABLE_PROPERTIES:
            raise _UnsupportedGeneration("rdf:type is absent from the query-schema contract.", "query_schema_mapping_mismatch")
        if predicate == "rdf:type" and not object_.startswith("?"):
            if object_ not in _QUERYABLE_CLASSES:
                raise _UnsupportedGeneration(
                    f"RDF type {object_!r} is absent from query-schema-contract.json.",
                    "query_schema_mapping_mismatch",
                )
        if pattern_id is not None:
            self._validate_pattern(pattern_id)
            if _PATTERNS[pattern_id]["graphFamily"] != family_id:
                raise _UnsupportedGeneration(
                    f"Pattern {pattern_id!r} does not belong to graph family {family_id!r}.",
                    "query_schema_mapping_mismatch",
                )
        graph_term = self._graph_term(family_id, anchor_var=anchor_var)
        key = (family_id, graph_term)
        fragment = self.fragments.setdefault(key, _GraphFragment(family_id, graph_term))
        fragment.triples.add((subject, predicate, object_))
        for term in (subject, predicate, object_):
            if term.startswith("?") or term.startswith("<"):
                continue
            prefix, separator, _local_name = term.partition(":")
            if separator and prefix in _NAMESPACES:
                self.used_prefixes.add(prefix)
        self._trace(
            requirement_id, pattern_id=pattern_id, family_id=family_id,
            property_qname=predicate, contract_ref=contract_ref,
        )
        if predicate != "rdf:type":
            self._trace(requirement_id, contract_ref=f"queryableProperties:{predicate}")
        if pattern_id:
            self._trace(requirement_id, contract_ref=f"emittedRdfPatterns:{pattern_id}")

    def _add_contract_type(self, requirement_id: str, entity_type: str, value_var: str,
                           *, anchor_var: str | None = None) -> None:
        mapping = _ENTITY_TYPES[entity_type]
        contract_ref = f"queryableClasses:{mapping.rdf_type}"
        self._add_triple(
            requirement_id, mapping.graph_family,
            value_var if mapping.graph_family == "member-records" else anchor_var,
            value_var, "rdf:type", mapping.rdf_type,
            pattern_id=mapping.pattern_id,
            contract_ref=contract_ref,
        )

    def _add_pattern(self, requirement_id: str, pattern_id: str, family_id: str,
                     anchor_var: str | None,
                     triples: tuple[tuple[str, str, str], ...]) -> None:
        self._validate_pattern(pattern_id)
        pattern = _PATTERNS[pattern_id]
        if pattern["graphFamily"] != family_id:
            raise _UnsupportedGeneration(
                f"Pattern {pattern_id!r} does not belong to graph family {family_id!r}.",
                "query_schema_mapping_mismatch",
            )
        for subject, predicate, object_ in triples:
            self._add_triple(
                requirement_id, family_id, anchor_var, subject, predicate, object_,
                pattern_id=pattern_id,
            )

    def _add_type_for_participant(self, requirement_id: str,
                                  participant: dict[str, Any]) -> None:
        entity_type = self._participant_type(participant)
        value_var = self._participant_var(participant)
        anchor = value_var if entity_type == "Member" else None
        self._add_contract_type(requirement_id, entity_type, value_var, anchor_var=anchor)

    def _add_member_type(self, requirement_id: str, member_var: str) -> None:
        self._add_pattern(
            requirement_id, "member-description", "member-records", member_var,
            ((member_var, "rdf:type", "agents:Member"),),
        )

    def _membership_type_values(self, requirement_id: str, index: int) -> str:
        if any(term_type not in _QUERYABLE_CLASSES for term_type in _TERM_MEMBERSHIP_TYPES.values()):
            raise _UnsupportedGeneration(
                "A reviewed Oireachtas membership type is absent from the query-schema contract.",
                "query_schema_mapping_mismatch",
            )
        membership_type_var = f"?membershipType{index}"
        self.values_clauses.append(
            f"VALUES {membership_type_var} {{ members:DailMembership members:SeanadMembership }}"
        )
        self.used_prefixes.add("members")
        self._trace(
            requirement_id,
            contract_ref="emittedRdfPatterns:member-house-membership",
        )
        return membership_type_var

    def _add_oireachtas_membership_type(self, requirement_id: str, member_var: str,
                                        membership_var: str, index: int,
                                        term_type: str | None = None) -> None:
        self._add_pattern(
            requirement_id, "member-house-membership", "member-records", member_var,
            ((membership_var, "rdf:type", "members:OireachtasMembership"),),
        )
        if term_type is None:
            membership_type_var = self._membership_type_values(requirement_id, index)
            self._add_pattern(
                requirement_id, "member-house-membership", "member-records", member_var,
                ((membership_var, "rdf:type", membership_type_var),),
            )
        else:
            membership_type = _TERM_MEMBERSHIP_TYPES[term_type]
            self._add_pattern(
                requirement_id, "member-house-membership", "member-records", member_var,
                ((membership_var, "rdf:type", membership_type),),
            )

    def _temporal_term_type(self, requirement_id: str) -> str | None:
        for constraint in self.plan["temporalConstraints"]:
            if constraint["target"] == requirement_id and constraint["kind"] == "during":
                period = constraint.get("period")
                if isinstance(period, dict) and "entity" in period:
                    return self.entities[period["entity"]]["type"]
        return None

    def _requirement_values(self, requirement: dict[str, Any]) -> dict[str, str]:
        requirement_id = requirement["id"]
        fact = requirement["fact"]
        index = self.requirement_indices[requirement_id]
        subject = self._participant_var(requirement["subject"])
        values = {"subject": subject}
        if "object" in requirement:
            values["object"] = self._participant_var(requirement["object"])
        value_var = f"?value{index}"

        if fact == "member_identity":
            values["value"] = subject
        elif fact == "member_full_name":
            values["value"] = value_var
            self._add_member_type(requirement_id, subject)
            self._add_pattern(
                requirement_id, "member-description", "member-records", subject,
                ((subject, "foaf:name", value_var),),
            )
        elif fact in {"member_house_term_membership", "member_parliamentary_membership_start_date",
                      "member_parliamentary_membership_end_date"}:
            term = values["object"]
            term_type = self._participant_type(requirement["object"])
            membership = f"?membership{index}"
            self._add_member_type(requirement_id, subject)
            self._add_oireachtas_membership_type(
                requirement_id, subject, membership, index, term_type=term_type,
            )
            self._add_pattern(
                requirement_id, "member-house-membership", "member-records", subject,
                ((subject, "members:hasMembersMembership", membership),
                 (membership, "members:inHouseTerm", term)),
            )
            self._add_type_for_participant(requirement_id, requirement["object"])
            if fact == "member_house_term_membership":
                values["value"] = term
            else:
                date_range = f"?dateRange{index}"
                date_value = value_var
                predicate = _FACTS[fact].predicate
                self._add_pattern(
                    requirement_id, "member-house-membership", "member-records", subject,
                    ((membership, "members:hasMembershipDateRange", date_range),
                     (date_range, "rdf:type", "members:DateRange"),
                     (date_range, predicate, date_value)),
                )
                values["value"] = date_value
        elif fact == "member_collection_membership":
            collection = values["object"]
            membership = f"?membership{index}"
            collection_membership = f"?collectionMembership{index}"
            self._add_member_type(requirement_id, subject)
            self._add_oireachtas_membership_type(
                requirement_id, subject, membership, index,
                term_type=self._temporal_term_type(requirement_id),
            )
            self._add_pattern(
                requirement_id, "member-collection-membership", "member-records", subject,
                ((subject, "members:hasMembersMembership", collection_membership),
                 (collection_membership, "members:inOireachtasMembership", membership),
                 (collection_membership, "members:memberOfCollection", collection)),
            )
            self._add_type_for_participant(requirement_id, requirement["object"])
            values["value"] = collection
        elif fact == "member_constituency_representation":
            representation = values["object"]
            membership = f"?membership{index}"
            self._add_member_type(requirement_id, subject)
            self._add_oireachtas_membership_type(
                requirement_id, subject, membership, index,
                term_type=self._temporal_term_type(requirement_id),
            )
            self._add_pattern(
                requirement_id, "representation-reference", "member-records", subject,
                ((membership, "members:isRepresentativeFrom", representation),),
            )
            self._add_type_for_participant(requirement_id, requirement["object"])
            values["value"] = representation
        elif fact == "member_committee_membership":
            committee = values["object"]
            committee_membership = f"?committeeMembership{index}"
            self._add_member_type(requirement_id, subject)
            self._add_pattern(
                requirement_id, "committee-membership-reference", "member-records", subject,
                ((subject, "members:hasMembersMembership", committee_membership),
                 (committee_membership, "rdf:type", "members:CommitteeMembership"),
                 (committee_membership, "members:isCommitteeMembershipOf", committee)),
            )
            self._add_type_for_participant(requirement_id, requirement["object"])
            values["value"] = committee
        elif fact in _LABEL_FACT_TYPES or fact == "committee_code" or fact == "parliamentary_term_number":
            entity_type = self._participant_type(requirement["subject"])
            if fact == "parliamentary_term_number":
                predicate = "agents:termNo"
            elif fact == "committee_code":
                predicate = "members:committeeCode"
            else:
                if fact == "parliamentary_term_label" and entity_type not in {"DailTerm", "SeanadTerm"}:
                    raise _UnsupportedGeneration("Term-label mapping requires a DailTerm or SeanadTerm subject.")
                if fact == "constituency_panel_label" and entity_type not in {"DailConstituency", "SeanadPanel"}:
                    raise _UnsupportedGeneration("Constituency/panel-label mapping requires a constituency or panel subject.")
                label_entry = _QUERY_SCHEMA["labelsByEntityType"].get(entity_type)
                if label_entry is None:
                    raise _UnsupportedGeneration(
                        f"No reviewed label property exists for entity type {entity_type!r}.",
                        "unreviewed_label_mapping",
                    )
                predicate = label_entry["predicate"]
                self._trace(
                    requirement_id,
                    contract_ref=f"labelsByEntityType:{entity_type}",
                )
                language = label_entry.get("language")
                languages = label_entry.get("languages")
                if isinstance(language, str) and language != "none":
                    self.filter_expressions.append(
                        f"FILTER(LANG({value_var}) = {_literal_n3(language)})"
                    )
                    self._trace(
                        requirement_id,
                        contract_ref=f"labelsByEntityType:{entity_type}.language",
                    )
                elif isinstance(languages, list) and languages:
                    language_tests = " || ".join(
                        f"LANG({value_var}) = {_literal_n3(item)}"
                        for item in languages
                    )
                    self.filter_expressions.append(f"FILTER({language_tests})")
                    self._trace(
                        requirement_id,
                        contract_ref=f"labelsByEntityType:{entity_type}.languages",
                    )
            self._add_contract_type(requirement_id, entity_type, subject,
                                    anchor_var=subject if entity_type == "Member" else None)
            value = value_var
            pattern_ids = _FACTS[fact].pattern_ids
            pattern_id = pattern_ids[0] if pattern_ids else None
            family = _ENTITY_TYPES[entity_type].graph_family
            self._add_triple(
                requirement_id, family, subject if family == "member-records" else None,
                subject, predicate, value,
                pattern_id=pattern_id,
                contract_ref=f"queryableProperties:{predicate}",
            )
            values["value"] = value
        else:
            raise _UnsupportedGeneration(
                f"No reviewed local RDF compiler exists for semantic fact {fact!r}.",
                "unreviewed_fact_mapping",
            )

        self._value_vars[requirement_id] = values
        return values

    def _apply_temporal_constraints(self) -> None:
        constraints = sorted(
            self.plan["temporalConstraints"],
            key=lambda item: (item["target"], item["kind"], repr(item.get("period"))),
        )
        for constraint in constraints:
            requirement_id = constraint["target"]
            requirement = self.requirements[requirement_id]
            fact = requirement["fact"]
            period_entity_id = constraint["period"]["entity"]
            period_entity = self.entities[period_entity_id]
            period_var = self._entity_var(period_entity_id)
            self._trace(
                requirement_id,
                contract_ref="planSemantics:temporalScoping",
            )
            if fact == "member_house_term_membership":
                object_var = self._value_vars[requirement_id]["object"]
                if object_var != period_var:
                    self.filter_expressions.append(f"FILTER({object_var} = {period_var})")
            else:
                member_var = self._participant_var(requirement["subject"])
                membership_var = f"?membership{self.requirement_indices[requirement_id]}"
                self._add_pattern(
                    requirement_id, "member-house-membership", "member-records", member_var,
                    ((membership_var, "members:inHouseTerm", period_var),),
                )
                self._add_type_for_participant(
                    requirement_id,
                    {"entity": period_entity_id},
                )
            self.temporal_trace.append({
                "requirement": requirement_id,
                "fact": fact,
                "kind": "during",
                "period_entity": period_entity_id,
                "patterns": ["member-house-membership"] if fact != "member_house_term_membership" else [],
            })

    def _apply_filters(self) -> None:
        operator_syntax = {
            "equals": "=",
            "not_equals": "!=",
            "greater_than": ">",
            "greater_than_or_equal": ">=",
            "less_than": "<",
            "less_than_or_equal": "<=",
        }
        filters = sorted(
            self.plan["filters"],
            key=lambda item: (item["requirement"], item["field"], item["operator"], repr(item.get("value"))),
        )
        for filter_ in filters:
            requirement_id = filter_["requirement"]
            field_id = filter_["field"]
            mapping = _FILTERS[field_id]
            value_var = self._value_vars[requirement_id][
                "object" if mapping.value_kind == "entity" else "value"
            ]
            operator = filter_["operator"]
            if operator != "exists":
                if mapping.value_kind == "string":
                    serialized = _literal_n3(filter_["value"])
                elif mapping.value_kind == "number":
                    serialized = _literal_n3(filter_["value"])
                else:
                    serialized = self._entity_var(filter_["value"]["entity"])
                self.filter_expressions.append(
                    f"FILTER({value_var} {operator_syntax[operator]} {serialized})"
                )
            self.filter_trace.append({
                "requirement": requirement_id,
                "field": field_id,
                "fact": mapping.fact,
                "operator": operator,
                "value_variable": value_var,
                "predicate": mapping.predicate,
            })
            self._trace(
                requirement_id,
                property_qname=mapping.predicate,
                contract_ref=f"semanticVocabulary.filterFields:{field_id}",
            )

    def _answer_var(self) -> tuple[str, str]:
        shape = self.plan["answerShape"]
        kind = shape["kind"]
        if kind == "boolean":
            return "", "boolean"
        if kind in {"entity", "entities"}:
            entity_type = shape["entityType"]
            candidates: dict[str, str] = {}
            for requirement in self.requirements.values():
                for position in ("subject", "object"):
                    participant = requirement.get(position)
                    if participant is None or self._participant_type(participant) != entity_type:
                        continue
                    variable = self._participant_var(participant)
                    candidates[variable] = "role" if "type" in participant else "entity"
            roles = sorted(variable for variable, source in candidates.items() if source == "role")
            selected = roles if roles else sorted(candidates)
            if len(selected) != 1:
                raise _UnsupportedGeneration(
                    f"Answer shape {kind!r} does not identify exactly one {entity_type!r} semantic result role.",
                    "ambiguous_answer_role",
                )
            return selected[0], "resource"
        if kind in {"label", "fact", "list"}:
            requirement_id = shape["target"]
            requirement = self.requirements[requirement_id]
            mapping = _FACTS[requirement["fact"]]
            if kind == "label" and mapping.value_kind != "label":
                raise _UnsupportedGeneration(
                    f"Answer shape 'label' is not supported for fact {requirement['fact']!r}.",
                    "unsupported_answer_shape",
                )
            if kind in {"fact", "list"} and mapping.value_kind not in {"literal", "label"}:
                raise _UnsupportedGeneration(
                    f"Answer shape {kind!r} cannot return a resource relation as a fact value.",
                    "unsupported_answer_shape",
                )
            return self._value_vars[requirement_id]["value"], "literal"
        if kind == "count":
            return self._aggregation_var(self.plan["aggregation"]["target"]), "count"
        if kind == "grouped_result":
            return "", "grouped"
        raise _UnsupportedGeneration(f"Unsupported answer shape {kind!r}.", "unsupported_answer_shape")

    def _aggregation_var(self, reference: dict[str, str]) -> str:
        requirement = self.requirements[reference["requirement"]]
        return self._participant_var(requirement[reference["participant"]])

    def _validate_answer_shape(self) -> None:
        kind = self.plan["answerShape"]["kind"]
        if kind in {"count", "grouped_result"}:
            aggregation = self.plan["aggregation"]
            if aggregation is None or aggregation["operation"] != "count":
                raise _UnsupportedGeneration("Only explicit count aggregation is supported.", "unsupported_aggregation")
            target_var = self._aggregation_var(aggregation["target"])
            target_participant = self.requirements[aggregation["target"]["requirement"]][
                aggregation["target"]["participant"]
            ]
            if "entity" in target_participant:
                raise _UnsupportedGeneration(
                    "Counting an entity already bound to one resolved IRI is not a supported result role.",
                    "unsupported_aggregation_target",
                )
            if kind == "grouped_result" and any(
                "entity" in self.requirements[item["requirement"]][item["participant"]]
                for item in aggregation["groupBy"]
            ):
                raise _UnsupportedGeneration(
                    "Grouping by an entity already bound to one resolved IRI is not supported.",
                    "unsupported_aggregation_group",
                )
            if not target_var.startswith("?"):
                raise _UnsupportedGeneration("Count target is not a bound semantic value.", "unsupported_aggregation")
            if kind == "grouped_result":
                group_vars = sorted({self._aggregation_var(item) for item in aggregation["groupBy"]})
                if not group_vars:
                    raise _UnsupportedGeneration("Grouped results require at least one supported group role.", "unsupported_aggregation")

    def _bind_entities(self) -> None:
        for entity_id in sorted(self.entities):
            entity = self.entities[entity_id]
            self.values_clauses.append(
                f"VALUES {self.entity_vars[entity_id]} {{ {_iri_n3(entity['iri'])} }}"
            )

    def _render_fragments(self) -> list[str]:
        order = {family: index for index, family in enumerate(_GRAPH_FAMILY_ORDER)}
        fragments = sorted(
            self.fragments.values(),
            key=lambda fragment: (order[fragment.family_id], fragment.graph_term),
        )
        blocks = []
        for fragment in fragments:
            triples = "\n".join(
                f"    {subject} {predicate} {object_} ."
                for subject, predicate, object_ in sorted(fragment.triples)
            )
            blocks.append(f"GRAPH {fragment.graph_term} {{\n{triples}\n  }}")
            if fragment.family_id == "member-records":
                graph_prefix = _literal_n3(_LOCAL_MEMBER_GRAPH_PREFIX)
                excluded = _literal_n3(_MEMBER_EXTERNAL_GRAPH_SUFFIX)
                self.filter_expressions.append(
                    f"FILTER(STRSTARTS(STR({fragment.graph_term}), {graph_prefix}) "
                    f"&& !CONTAINS(STR({fragment.graph_term}), {excluded}))"
                )
        return blocks

    def _render_query(self, answer_var: str, answer_value_kind: str) -> tuple[str, str]:
        shape = self.plan["answerShape"]
        kind = shape["kind"]
        query_form = "ASK" if kind == "boolean" else "SELECT"
        if kind == "count":
            target_var = self._aggregation_var(self.plan["aggregation"]["target"])
            projections = [f"(COUNT(DISTINCT {target_var}) AS ?count)"]
            group_by: list[str] = []
        elif kind == "grouped_result":
            aggregation = self.plan["aggregation"]
            group_by = sorted({self._aggregation_var(item) for item in aggregation["groupBy"]})
            target_var = self._aggregation_var(aggregation["target"])
            projections = [*group_by, f"(COUNT(DISTINCT {target_var}) AS ?count)"]
        elif kind == "boolean":
            projections = []
            group_by = []
        else:
            projections = [answer_var]
            group_by = []

        prefixes = "\n".join(
            f"PREFIX {prefix}: <{_NAMESPACES[prefix]}>"
            for prefix in sorted(self.used_prefixes)
        )
        graph_blocks = self._render_fragments()
        body = [*self.values_clauses, *graph_blocks, *self.filter_expressions]
        where = "\n".join(f"  {line}" for line in body)
        if query_form == "ASK":
            query = f"ASK WHERE {{\n{where}\n}}"
        else:
            projection = " ".join(projections)
            query = f"SELECT DISTINCT {projection} WHERE {{\n{where}\n}}"
            if group_by:
                query += "\nGROUP BY " + " ".join(group_by)
        if prefixes:
            query = prefixes + "\n" + query
        return query, query_form

    def compile(self) -> tuple[str, str, str, dict[str, Any]]:
        self._bind_entities()
        for requirement in self.requirements.values():
            # Entity-type checks are always scoped to their contract-owned graph.
            for position in ("subject", "object"):
                participant = requirement.get(position)
                if participant is not None:
                    self._add_type_for_participant(requirement["id"], participant)
            self._requirement_values(requirement)
        self._apply_temporal_constraints()
        self._apply_filters()
        answer_var, answer_value_kind = self._answer_var()
        query, query_form = self._render_query(answer_var, answer_value_kind)
        trace = {
            "requirements": [
                {
                    **entry,
                    "pattern_ids": sorted(
                        entry["pattern_ids"], key=lambda pattern: _PATTERN_ORDER.get(pattern, 10_000),
                    ),
                    "graph_families": sorted(
                        entry["graph_families"], key=lambda family: _GRAPH_FAMILY_ORDER.index(family),
                    ),
                    "reviewed_properties": sorted(entry["reviewed_properties"]),
                    "reviewed_contract_refs": sorted(entry["reviewed_contract_refs"]),
                }
                for entry in self.requirement_trace.values()
            ],
            "filters": self.filter_trace,
            "temporal_constraints": self.temporal_trace,
            "answer_variable": answer_var or None,
            "answer_value_kind": answer_value_kind,
        }
        return query, query_form, answer_value_kind, trace


def _iri_n3(value: str) -> str:
    """Serialize an IRI as RDF/SPARQL syntax; never interpolate raw plan text."""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie":
        raise _UnsupportedGeneration(
            "Resolved entity IRI is outside the local Oireachtas namespace.",
            "invalid_entity_iri",
        )
    try:
        return URIRef(value).n3()
    except Exception as error:
        raise _UnsupportedGeneration(
            "Resolved entity IRI cannot be safely serialized as an RDF IRI.",
            "invalid_entity_iri",
        ) from error


def _literal_n3(value: Any) -> str:
    try:
        return Literal(value).n3()
    except Exception as error:
        raise _UnsupportedGeneration(
            "Filter value cannot be safely serialized as an RDF literal.",
            "invalid_filter_value",
        ) from error


def _binding_evidence(result: PlannerResult) -> tuple[dict[str, Any], ...]:
    evidence = []
    for item in result.binding_evidence:
        if hasattr(item, "as_dict"):
            evidence.append(item.as_dict())
        elif isinstance(item, dict):
            evidence.append(item)
    return tuple(evidence)


class PlanSparqlGenerator:
    """Compile only accepted ``validated_plan`` results to safe local SPARQL."""

    def __init__(self, *, supported_predicates: frozenset[URIRef]):
        if not supported_predicates:
            raise ValueError("The SPARQL safety predicate allowlist is required.")
        self.supported_predicates = frozenset(supported_predicates)

    def generate(self, planner_result: PlannerResult) -> GenerationResult:
        """Return deterministic SPARQL or an inspectable fail-closed outcome."""
        evidence = _binding_evidence(planner_result) if isinstance(planner_result, PlannerResult) else ()
        if not isinstance(planner_result, PlannerResult):
            return GenerationResult(
                "rejected_plan", failure_class="planner_result_required",
                failure_reason="Generation requires a structured PlannerResult; raw plans are not executable inputs.",
                failure_stage="plan_validation",
            )
        if planner_result.status != "validated_plan" or planner_result.plan is None:
            failure_stage = "entity_binding" if planner_result.failure_stage == "entity_resolution" or planner_result.status in {
                "clarification_required", "unresolved_entity", "set_valued_member_identity",
                "entity_resolution_failure", "source_data_prerequisite_unavailable",
            } else "planner_or_plan_validation"
            failure_class = planner_result.failure_class or (
                "set_valued_member_identity"
                if planner_result.status == "set_valued_member_identity"
                else "entity_binding" if failure_stage == "entity_binding"
                else "planner_failure"
            )
            return GenerationResult(
                "rejected_plan", failure_class=failure_class,
                failure_reason=(planner_result.diagnostic or
                                f"Planner status {planner_result.status!r} is not executable."),
                failure_stage=failure_stage,
                binding_evidence=evidence,
            )
        try:
            plan = validate_query_plan(planner_result.plan)
        except QueryPlanContractError as error:
            return GenerationResult(
                "invalid_plan", failure_class="plan_validation_failure",
                failure_reason=str(error), failure_stage="plan_validation",
                semantic_answer_shape=(
                    planner_result.plan.get("answerShape")
                    if isinstance(planner_result.plan, dict) else None
                ),
                binding_evidence=evidence,
            )
        try:
            compiler = _Compiler(plan, self.supported_predicates)
            query, query_form, _value_kind, trace = compiler.compile()
        except _UnsupportedGeneration as error:
            return GenerationResult(
                "unsupported_generation", failure_class=error.failure_class,
                failure_reason=str(error), failure_stage="generation",
                semantic_answer_shape=plan.get("answerShape"),
                binding_evidence=evidence,
            )
        except Exception as error:
            return GenerationResult(
                "unsupported_generation", failure_class="generation_compiler_failure",
                failure_reason=f"Deterministic compiler failed closed: {error}",
                failure_stage="generation",
                semantic_answer_shape=plan.get("answerShape"),
                binding_evidence=evidence,
            )
        try:
            safe_query = validate_sparql(
                query,
                supported_predicates=self.supported_predicates,
            )
        except NLQError as error:
            return GenerationResult(
                "safety_failure", failure_class="sparql_safety_validation",
                failure_reason=str(error), failure_stage="sparql_safety",
                semantic_answer_shape=plan.get("answerShape"),
                generation_trace=trace,
                binding_evidence=evidence,
            )
        except Exception as error:
            return GenerationResult(
                "safety_failure", failure_class="sparql_safety_validator_failure",
                failure_reason=f"SPARQL safety validation failed closed: {error}",
                failure_stage="sparql_safety",
                semantic_answer_shape=plan.get("answerShape"),
                generation_trace=trace,
                binding_evidence=evidence,
            )
        return GenerationResult(
            "generated",
            sparql=safe_query,
            query_form=query_form,
            semantic_answer_shape=dict(plan["answerShape"]),
            generation_trace=trace,
            binding_evidence=evidence,
        )


def build_label_lookup_query(
    entity_type: str,
    entity_iri: str,
    *,
    supported_predicates: frozenset[URIRef],
) -> str:
    """Build a separate reviewed label lookup for benchmark result scoring.

    This is not appended to a generated semantic query.  It lets an evaluator
    compare resource-IRI answers with the label-valued expectations in the
    Phase 1 controlled benchmark without changing answer semantics.
    """
    mapping = _ENTITY_TYPES.get(entity_type)
    label = _QUERY_SCHEMA["labelsByEntityType"].get(entity_type)
    if mapping is None or label is None:
        raise ValueError(f"No reviewed local label mapping exists for {entity_type!r}.")
    if not supported_predicates:
        raise ValueError("The SPARQL safety predicate allowlist is required.")
    iri = _iri_n3(entity_iri)
    predicate = label["predicate"]
    prefix, local_name = predicate.split(":", 1)
    predicate_iri = URIRef(_NAMESPACES[prefix] + local_name)
    if predicate not in _QUERYABLE_PROPERTIES or predicate_iri not in supported_predicates:
        raise ValueError(f"Label predicate {predicate!r} is not queryable and allowlisted.")
    subject = "?resource"
    graph = _GRAPH_FAMILIES[mapping.graph_family]["graph"]
    if graph["kind"] == "fixed":
        graph_term = _iri_n3(graph["iri"])
        graph_pattern = f"GRAPH {graph_term} {{ {subject} {predicate} ?label . }}"
        graph_filter = ""
    elif mapping.graph_family == "member-records":
        graph_term = "?labelGraph"
        graph_pattern = f"GRAPH {graph_term} {{ {subject} {predicate} ?label . }}"
        prefix_literal = _literal_n3(_LOCAL_MEMBER_GRAPH_PREFIX)
        suffix_literal = _literal_n3(_MEMBER_EXTERNAL_GRAPH_SUFFIX)
        graph_filter = (
            f"FILTER(STRSTARTS(STR({graph_term}), {prefix_literal}) "
            f"&& !CONTAINS(STR({graph_term}), {suffix_literal}))"
        )
    else:
        raise ValueError(f"Graph family {mapping.graph_family!r} has no supported label scope.")
    query_prefix = f"PREFIX {prefix}: <{_NAMESPACES[prefix]}>"
    filters = []
    language = label.get("language")
    languages = label.get("languages")
    if isinstance(language, str) and language != "none":
        filters.append(f"FILTER(LANG(?label) = {_literal_n3(language)})")
    elif isinstance(languages, list) and languages:
        tests = " || ".join(f"LANG(?label) = {_literal_n3(item)}" for item in languages)
        filters.append(f"FILTER({tests})")
    if graph_filter:
        filters.append(graph_filter)
    query = (
        query_prefix
        + "\nSELECT DISTINCT ?label WHERE {\n"
        + f"  VALUES {subject} {{ {iri} }}\n"
        + f"  {graph_pattern}\n"
        + "\n".join(f"  {item}" for item in filters)
        + "\n}"
    )
    return validate_sparql(query, supported_predicates=supported_predicates)
