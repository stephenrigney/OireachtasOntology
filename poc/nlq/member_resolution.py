"""Bounded, deterministic local entity resolution for the NLQ POC.

This is deliberately not an identity-merging layer. It finds exact local
labels mentioned by the user, retains the actual RDF resources, and reports
ambiguity rather than selecting or merging distinct identities. The Phase 1
Member-question gate remains unchanged; the typed single-label resolver is used
by the independent structured-planner path.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from urllib.parse import urlsplit

from rdflib import Literal, URIRef

from .contract import load_query_contract
from .errors import NLQError
from .safety import validate_sparql


_CONTRACT = load_query_contract()
_NAMESPACES = _CONTRACT["namespaces"]
_FIXED_GRAPHS = {
    family["id"]: family["graph"]["iri"]
    for family in _CONTRACT["graphFamilies"]
    if family["graph"]["kind"] == "fixed"
}
_MEMBER_GRAPH_PREFIX = next(
    family["graph"]["iriTemplate"].split("{", 1)[0]
    for family in _CONTRACT["graphFamilies"]
    if family["id"] == "member-records"
)

_ENTITY_CLASSES = {
    "Member": "agents:Member",
    "House": "agents:House",
    "DailTerm": "agents:DailTerm",
    "SeanadTerm": "agents:SeanadTerm",
    "ParliamentaryMemberCollection": "members:ParliamentaryMemberCollection",
    "DailConstituency": "members:DailConstituency",
    "SeanadPanel": "members:SeanadPanel",
    "Committee": "members:Committee",
}
_ENTITY_GRAPH_FAMILIES = {
    "Member": "member-records",
    "House": "houses",
    "DailTerm": "houses",
    "SeanadTerm": "houses",
    "ParliamentaryMemberCollection": "parties",
    "DailConstituency": "constituencies",
    "SeanadPanel": "constituencies",
    "Committee": "committees",
}
_ENTITY_GRAPH_CONFIG = {
    family["id"]: family["graph"] for family in _CONTRACT["graphFamilies"]
}
_LOCAL_IRI = re.compile(r"^https://data\.oireachtas\.ie/[^\s?#]+$")


class UnsupportedLocalEntityType(ValueError):
    """The controlled type has no deterministic local label lookup."""


@dataclass(frozen=True)
class LocalEntityCandidate:
    """One distinct, locally returned resource and its actual label."""

    iri: str
    label: str


@dataclass(frozen=True)
class LocalEntityResolution:
    """Exact-label resolution without fuzzy matching or identity merging."""

    state: str
    candidates: tuple[LocalEntityCandidate, ...] = ()


@dataclass(frozen=True)
class MemberCandidate:
    """One actual local Member resource and its safely displayable context."""

    member_iri: str
    name: str
    member_code: str | None = None
    house_terms: tuple[str, ...] = ()
    representations: tuple[str, ...] = ()
    question_context_matches: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "member_iri": self.member_iri,
            "name": self.name,
            "member_code": self.member_code,
            "house_terms": list(self.house_terms),
            "representations": list(self.representations),
            "question_context_matches": list(self.question_context_matches),
        }


@dataclass(frozen=True)
class MemberAmbiguity:
    """A first-class clarification outcome; no answer query was executed."""

    entity_reference: str
    candidates: tuple[MemberCandidate, ...]

    def as_dict(self) -> dict:
        return {
            "status": "ambiguous",
            "entity_type": "Member",
            "entity_reference": self.entity_reference,
            "matching_rule": (
                "A complete local foaf:name label occurs in the question; "
                "case-insensitive matching preserves Irish diacritics."
            ),
            "decision": (
                "Multiple local Member resources remain after supported "
                "HouseTerm/constituency context checks; none was selected or merged."
            ),
            "candidate_count": len(self.candidates),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


def _normalise_text(value: str) -> str:
    # Canonical Unicode composition and case folding retain (rather than strip)
    # Irish diacritics. No accent-removal or approximate spelling is performed.
    return unicodedata.normalize("NFC", value).casefold()


def _entity_label_predicate(entity_type: str) -> str:
    labels = _CONTRACT.get("labelsByEntityType", {}).get(entity_type)
    if not isinstance(labels, dict):
        raise UnsupportedLocalEntityType(
            f"No local label predicate is defined for entity type {entity_type!r}."
        )
    qualified = labels.get("predicate")
    if not isinstance(qualified, str) or ":" not in qualified:
        raise UnsupportedLocalEntityType(
            f"No local label predicate is defined for entity type {entity_type!r}."
        )
    prefix, local_name = qualified.split(":", 1)
    namespace = _NAMESPACES.get(prefix)
    if not namespace or not local_name:
        raise UnsupportedLocalEntityType(
            f"The local label predicate for entity type {entity_type!r} is unsupported."
        )
    return f"<{namespace}{local_name}>"


def _entity_lookup_query(entity_type: str, label: str) -> str:
    """Build a bounded lookup only from the reviewed local type/label map."""
    class_name = _ENTITY_CLASSES.get(entity_type)
    graph_config = _ENTITY_GRAPH_CONFIG.get(_ENTITY_GRAPH_FAMILIES.get(entity_type, ""))
    if class_name is None or not isinstance(graph_config, dict):
        raise UnsupportedLocalEntityType(
            f"No deterministic local resolver is available for entity type {entity_type!r}."
        )
    predicate = _entity_label_predicate(entity_type)
    query_label = Literal(unicodedata.normalize("NFC", label)).n3()
    if graph_config.get("kind") == "resource-pattern" and entity_type == "Member":
        pattern = (
            f"GRAPH ?entityGraph {{ ?entity a {class_name} ; {predicate} ?label . }}\n"
            f'  FILTER(STRSTARTS(STR(?entityGraph), "{_MEMBER_GRAPH_PREFIX}"))'
        )
    elif graph_config.get("kind") == "fixed":
        graph_iri = graph_config.get("iri")
        if not isinstance(graph_iri, str):
            raise UnsupportedLocalEntityType(
                f"No fixed local graph is defined for entity type {entity_type!r}."
            )
        pattern = f"GRAPH <{graph_iri}> {{ ?entity a {class_name} ; {predicate} ?label . }}"
    else:
        raise UnsupportedLocalEntityType(
            f"The local graph pattern for entity type {entity_type!r} is unsupported."
        )
    return f'''PREFIX agents: <{_NAMESPACES["agents"]}>
PREFIX members: <{_NAMESPACES["members"]}>
SELECT DISTINCT ?entity ?label WHERE {{
  {pattern}
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE(STR({query_label}))))
}}
LIMIT 100'''


def resolve_local_entity_label(
    entity_type: str,
    label: str,
    fuseki,
    *,
    supported_predicates=None,
    question_context: str | None = None,
) -> LocalEntityResolution:
    """Resolve one exact user label to zero, one, or many distinct local IRIs.

    The Fuseki query is a bounded, type-scoped substring prefilter; acceptance
    uses the Phase 1 NFC/casefold exact-label rule in Python. Thus the prefilter
    cannot turn a partial, fuzzy, or accent-folded match into a resolution.
    """
    if entity_type not in _ENTITY_CLASSES:
        raise UnsupportedLocalEntityType(
            f"No deterministic local resolver is available for entity type {entity_type!r}."
        )
    query = _checked_local_query(
        _entity_lookup_query(entity_type, label),
        supported_predicates=supported_predicates,
    )
    result = fuseki.query(query)
    if result.kind != "select" or not {"entity", "label"} <= set(result.columns):
        raise NLQError("Fuseki returned an unexpected response to local entity resolution.")
    if len(result.rows) >= 100:
        raise NLQError(
            f"Local {entity_type} label resolution reached its 100-row safety cap; "
            "no entity was selected."
        )

    exact_by_iri: dict[str, set[str]] = {}
    for row in result.rows:
        iri = _binding_value(row, result.columns, "entity")
        raw_label = _binding_value(row, result.columns, "label")
        if not iri or not raw_label:
            continue
        actual_label = _context_label(raw_label)
        if _normalise_text(actual_label) != _normalise_text(label):
            continue
        try:
            parsed = urlsplit(iri)
        except ValueError:
            continue
        if (
            not _LOCAL_IRI.fullmatch(iri)
            or parsed.scheme != "https"
            or parsed.netloc != "data.oireachtas.ie"
            or parsed.query
            or parsed.fragment
        ):
            continue
        exact_by_iri.setdefault(iri, set()).add(actual_label)

    candidates = tuple(sorted(
        (
            LocalEntityCandidate(
                iri=iri,
                # A resource can carry duplicate language/case variants of a
                # label; preserve one deterministic actual literal per IRI.
                label=sorted(labels, key=lambda value: (value.casefold(), value))[0],
            )
            for iri, labels in exact_by_iri.items()
        ),
        key=lambda candidate: (_normalise_text(candidate.label), candidate.iri),
    ))
    if entity_type == "Member" and question_context and len(candidates) > 1:
        # Preserve Phase 1's deterministic HouseTerm/constituency contextual
        # narrowing before reporting duplicate Member labels to the planner.
        enriched = tuple(
            _load_context(
                MemberCandidate(candidate.iri, candidate.label), fuseki,
                supported_predicates=supported_predicates,
            )
            for candidate in candidates
        )
        matches_by_iri = {
            candidate.member_iri: _non_overlapping_context_matches(
                question_context, set(candidate.house_terms) | set(candidate.representations),
            )
            for candidate in enriched
        }
        contextual = tuple(
            LocalEntityCandidate(candidate.member_iri, candidate.name)
            for candidate in enriched
            if matches_by_iri[candidate.member_iri]
        )
        if len(contextual) == 1:
            candidates = contextual
        elif len(contextual) > 1:
            candidates = contextual
    state = "unresolved" if not candidates else "resolved" if len(candidates) == 1 else "ambiguous"
    return LocalEntityResolution(state, candidates)


def _label_position(question: str, label: str) -> int | None:
    """Return the start of a whole-label mention, not a fuzzy/token match."""
    text = _normalise_text(question)
    target = _normalise_text(label)
    if not target:
        return None
    pattern = re.compile(r"(?<!\w)" + re.escape(target) + r"(?!\w)", re.UNICODE)
    match = pattern.search(text)
    return match.start() if match else None


def _set_valued_member_reference(question: str, label: str) -> bool:
    """Recognise explicit requests for a set of Member records.

    Listing a person's terms or memberships is not enough to make the person
    reference set-valued. The plural marker must refer to Member/person/record
    candidates, rather than merely to the answer being requested.
    """
    text = _normalise_text(question)
    patterns = (
        r"\b(?:all|every|each|multiple|several)\s+(?:local\s+)?"
        r"(?:members|people|persons|individuals|records)\b",
        r"\bwhich\s+(?:members|people|persons|individuals|records)\b",
        r"\b(?:members|people|persons|individuals|records)\s+"
        r"(?:named|called|whose\s+name\s+is)\b",
        r"\bhow\s+many\s+(?:members|people|persons|individuals|records)\b",
    )
    if any(re.search(pattern, text, re.UNICODE) for pattern in patterns):
        return True

    position = _label_position(question, label)
    if position is None:
        return False
    text = _normalise_text(question)
    end = position + len(_normalise_text(label))
    # Support explicit plural forms such as “Michael Collinses” without
    # treating a plural answer shape (“list his terms”) as a plural entity.
    return bool(re.match(r"(?:es|s)(?!\w)", text[end:]))


def _member_name_query(question: str) -> str:
    escaped_question = Literal(unicodedata.normalize("NFC", question)).n3()
    return f'''PREFIX agents: <{_NAMESPACES["agents"]}>
PREFIX foaf: <{_NAMESPACES["foaf"]}>
SELECT DISTINCT ?member ?name ?memberCode WHERE {{
  BIND({escaped_question} AS ?question)
  GRAPH ?memberGraph {{
    ?member a agents:Member ; foaf:name ?name .
    OPTIONAL {{ ?member agents:memberCode ?memberCode . }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), "{_MEMBER_GRAPH_PREFIX}"))
  FILTER(CONTAINS(LCASE(STR(?question)), LCASE(STR(?name))))
}}
LIMIT 100'''


def _member_context_query(member_iri: str) -> str:
    # Member IRIs are taken from the preceding local Fuseki result, never
    # manufactured from the user's name.
    member = URIRef(member_iri)
    if not member_iri.startswith("https://data.oireachtas.ie/ie/oireachtas/member/id/"):
        raise NLQError("Fuseki returned a Member outside the local Oireachtas Member namespace.")
    if urlsplit(member_iri).scheme != "https":
        raise NLQError("Fuseki returned an invalid local Member IRI.")
    return f'''PREFIX agents: <{_NAMESPACES["agents"]}>
PREFIX members: <{_NAMESPACES["members"]}>
PREFIX skos: <{_NAMESPACES["skos"]}>
SELECT DISTINCT ?contextType ?contextLabel WHERE {{
  VALUES ?member {{ {member.n3()} }}
  {{
    GRAPH ?memberGraph {{
      ?member members:hasMembersMembership ?membership .
      ?membership members:inHouseTerm ?term .
    }}
    FILTER(STRSTARTS(STR(?memberGraph), "{_MEMBER_GRAPH_PREFIX}"))
    GRAPH <{_FIXED_GRAPHS["houses"]}> {{
      ?term a ?termType ; skos:prefLabel ?contextLabel .
      FILTER(?termType IN (agents:DailTerm, agents:SeanadTerm))
    }}
    BIND("house_term" AS ?contextType)
  }}
  UNION
  {{
    GRAPH ?memberGraph {{
      ?member members:hasMembersMembership ?membership .
      ?membership members:isRepresentativeFrom ?representation .
    }}
    FILTER(STRSTARTS(STR(?memberGraph), "{_MEMBER_GRAPH_PREFIX}"))
    GRAPH <{_FIXED_GRAPHS["constituencies"]}> {{
      ?representation skos:prefLabel ?contextLabel .
    }}
    BIND("representation" AS ?contextType)
  }}
}}
LIMIT 100'''


def _checked_local_query(query: str, *, supported_predicates) -> str:
    try:
        return validate_sparql(query, supported_predicates=supported_predicates)
    except NLQError:
        raise
    except Exception as error:  # pragma: no cover - validator errors are controlled
        raise NLQError("The local Member resolution query could not be validated.") from error


def _binding_value(row: tuple[str, ...], columns: tuple[str, ...], name: str) -> str | None:
    if name not in columns:
        return None
    value = row[columns.index(name)]
    return None if value == "—" else value


def _query_member_mentions(question: str, fuseki, *, supported_predicates) -> list[dict]:
    query = _checked_local_query(
        _member_name_query(question), supported_predicates=supported_predicates,
    )
    result = fuseki.query(query)
    if result.kind != "select" or not {"member", "name"} <= set(result.columns):
        raise NLQError("Fuseki returned an unexpected response to local Member name resolution.")
    if len(result.rows) >= 100:
        raise NLQError(
            "Local Member name resolution reached its 100-candidate safety cap; "
            "no answer query was run. Narrow the Member reference."
        )

    candidates_by_label: dict[str, dict[str, MemberCandidate]] = {}
    labels_by_key: dict[str, str] = {}
    positions: dict[str, int] = {}
    for row in result.rows:
        iri = _binding_value(row, result.columns, "member")
        name = _binding_value(row, result.columns, "name")
        member_code = _binding_value(row, result.columns, "memberCode")
        if not iri or not name or _label_position(question, name) is None:
            continue
        # A case-only spelling difference refers to the same exact local label;
        # accents, punctuation and word order remain significant.
        key = _normalise_text(name)
        labels_by_key.setdefault(key, name)
        candidates_by_label.setdefault(key, {})[iri] = MemberCandidate(
            member_iri=iri,
            name=name,
            member_code=member_code,
        )
        position = _label_position(question, name)
        assert position is not None
        positions[key] = min(positions.get(key, position), position)

    # If one local label is wholly contained in a longer matched Member label,
    # it is not a second entity reference (for example “Martin” within a full
    # “Martin Heydon” label).
    matched_keys = set(candidates_by_label)
    for key in tuple(matched_keys):
        longer = [other for other in matched_keys if len(other) > len(key) and key in other]
        if longer:
            matched_keys.discard(key)

    return [
        {
            "key": key,
            "label": labels_by_key[key],
            "candidates": tuple(sorted(
                candidates_by_label[key].values(),
                key=lambda candidate: (candidate.name.casefold(), candidate.member_iri),
            )),
            "position": positions[key],
        }
        for key in sorted(matched_keys, key=lambda value: (positions[value], value))
    ]


def _context_label(value: str) -> str:
    return re.sub(r"@[A-Za-z]+(?:-[A-Za-z0-9]+)*$", "", value)


def _question_contains_context(question: str, value: str) -> bool:
    text = _normalise_text(question)
    target = _normalise_text(value)
    if not target:
        return False
    return bool(re.search(r"(?<!\w)" + re.escape(target) + r"(?!\w)", text, re.UNICODE))


def _non_overlapping_context_matches(question: str, values: set[str]) -> set[str]:
    matched = {value for value in values if _question_contains_context(question, value)}
    return {
        value for value in matched
        if not any(
            len(other) > len(value)
            and _normalise_text(value) in _normalise_text(other)
            for other in matched
        )
    }


def _load_context(candidate: MemberCandidate, fuseki, *, supported_predicates) -> MemberCandidate:
    query = _checked_local_query(
        _member_context_query(candidate.member_iri),
        supported_predicates=supported_predicates,
    )
    result = fuseki.query(query)
    if result.kind != "select" or not {"contextType", "contextLabel"} <= set(result.columns):
        raise NLQError("Fuseki returned an unexpected response to local Member context lookup.")
    if len(result.rows) >= 100:
        raise NLQError(
            "Local Member context lookup reached its 100-row safety cap; "
            "no answer query was run."
        )
    terms: set[str] = set()
    representations: set[str] = set()
    for row in result.rows:
        context_type = _binding_value(row, result.columns, "contextType")
        label = _binding_value(row, result.columns, "contextLabel")
        if not context_type or not label:
            continue
        label = _context_label(label)
        if context_type == "house_term":
            terms.add(label)
        elif context_type == "representation":
            representations.add(label)
    return MemberCandidate(
        member_iri=candidate.member_iri,
        name=candidate.name,
        member_code=candidate.member_code,
        house_terms=tuple(sorted(terms, key=str.casefold)),
        representations=tuple(sorted(representations, key=str.casefold)),
    )


def resolve_member_ambiguity(
    question: str,
    fuseki,
    *,
    supported_predicates,
) -> MemberAmbiguity | None:
    """Return ambiguity only for unresolved exact local Member references.

    Partial-name questions such as “Which Martin served in the Dáil?” do not
    match complete Member labels and continue as ordinary set-valued queries.
    Explicitly plural requests for Member records likewise continue through the
    direct translator rather than being interpreted as one-entity ambiguity.
    """
    mentions = _query_member_mentions(
        question, fuseki, supported_predicates=supported_predicates,
    )
    for mention in mentions:
        candidates = mention["candidates"]
        if len(candidates) < 2 or _set_valued_member_reference(question, mention["label"]):
            continue

        enriched = tuple(
            _load_context(candidate, fuseki, supported_predicates=supported_predicates)
            for candidate in candidates
        )
        context_matches = {
            candidate.member_iri: _non_overlapping_context_matches(
                question,
                set(candidate.house_terms) | set(candidate.representations),
            )
            for candidate in enriched
        }
        context_matched_candidates = [
            candidate for candidate in enriched if context_matches[candidate.member_iri]
        ]
        if len(context_matched_candidates) == 1:
            # The user's exact local HouseTerm/constituency label singles out a
            # resource; the existing direct query flow remains responsible for
            # validating and answering the complete question.
            continue
        if len(context_matched_candidates) > 1:
            remaining = context_matched_candidates
        else:
            remaining = list(enriched)
        remaining = [
            MemberCandidate(
                member_iri=candidate.member_iri,
                name=candidate.name,
                member_code=candidate.member_code,
                house_terms=candidate.house_terms,
                representations=candidate.representations,
                question_context_matches=tuple(sorted(
                    context_matches[candidate.member_iri], key=str.casefold
                )),
            )
            for candidate in remaining
        ]
        if len(remaining) >= 2:
            return MemberAmbiguity(mention["label"], tuple(remaining))
    return None
