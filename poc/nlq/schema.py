"""Build NLQ schema and dataset context from ontology and ETL source files."""

from __future__ import annotations

import csv
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS


SCHEMA_TYPE_URIS = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty)
MAX_SCHEMA_CONTEXT_CHARS = 48_000
COMMENT_CHARS = 120


def _one_line(graph: Graph, subject: URIRef, predicate: URIRef, limit: int = COMMENT_CHARS) -> str:
    values = sorted(
        (" ".join(str(value).split()) for value in graph.objects(subject, predicate)),
        key=str.casefold,
    )
    if not values:
        return ""
    value = values[0]
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _qname(value, prefixes: dict[str, str]) -> str:
    if not isinstance(value, URIRef):
        return str(value)
    candidates = [
        (namespace, prefix)
        for prefix, namespace in prefixes.items()
        if prefix and str(value).startswith(namespace)
    ]
    if candidates:
        namespace, prefix = max(candidates, key=lambda item: len(item[0]))
        return f"{prefix}:{str(value)[len(namespace):]}"
    return f"<{value}>"


def _dataset_context(repository_root: Path) -> list[str]:
    """Describe dataset graph ownership and identifiers from ETL conventions.

    Fixed reference graph identifiers come from the ETL config module. The
    per-resource graph patterns are the conventions implemented by the Member
    and Bills transforms and documented in the ETL plan.
    """
    try:
        from oireachtas_etl.config import (ADMINISTRATIVE_UNITS_GRAPH, CONSTITUENCIES_GRAPH,
                                           HOUSES_GRAPH, OFFICES_GRAPH, PARTIES_GRAPH)
    except ImportError as error:
        raise RuntimeError("Could not load the repository ETL graph identifiers") from error

    return [
        "Dataset graph ownership (these are named-graph IRIs, not ontology terms):",
        f"  Houses descriptions: <{HOUSES_GRAPH}> (HouseTerm resources and labels).",
        f"  Parties descriptions: <{PARTIES_GRAPH}> (term-scoped ParliamentaryMemberCollection resources and labels).",
        f"  Constituency/panel descriptions: <{CONSTITUENCIES_GRAPH}>.",
        f"  Reviewed administrative-unit and office descriptions: <{ADMINISTRATIVE_UNITS_GRAPH}> and <{OFFICES_GRAPH}>; current bootstrap registries are empty.",
        "  Member and all Member membership records: <https://data.oireachtas.ie/graph/member/{percent-encoded-memberCode}>.",
        "  Bill and legislative-process records: <https://data.oireachtas.ie/graph/bill/{year}/{number}>.",
        "  Optional Member reconciliation links: the Member graph pattern plus /external-links; this graph uses owl:sameAs for reviewed Wikidata/DBpedia identities and foaf:isPrimaryTopicOf for reviewed Wikipedia links.",
        "  Optional ParliamentaryParty reconciliation links: <https://data.oireachtas.ie/graph/party/{houseCode}/{houseNo}/{percent-encoded-partyCode}/external-links>; members:recognisedAsParty links a term-scoped collection to its reviewed external party identity and does not mean identity or group recognition.",
        "  Join graphs using the same RDF resource IRI; do not require descriptions to be co-located with their references.",
        "  The store does not entail OWL subclass types: match explicit instance types such as agents:DailTerm or agents:SeanadTerm, or omit a term type filter when matching its label.",
        "  Houses, Parties and Constituencies ETL writes skos:prefLabel as an English-language (@en) literal. For user-entered label matching, bind ?label and compare STR(?label) in a FILTER rather than matching an untagged literal directly. Member foaf:name values are plain literals.",
        "  Current Member ETL emits Member, parliamentary/committee memberships and legacy MinisterOfStateMembership; it does not emit CabinetMembership, TaoiseachRole or MinisterRole instances. The new OfficeHolding vocabulary is not populated. Do not infer executive tenure.",
        "  The Debates ontology is a schema module; this repository does not currently publish debate instances through a Debates ETL. Bill queryability likewise depends on Bill graphs actually being loaded.",
        "  Current emitted patterns:",
        "    Member graph: ?member a agents:Member; foaf:name ?name; members:hasMembersMembership ?membership. The membership resource is explicitly typed members:OireachtasMembership and DailMembership or SeanadMembership, and links to its term with members:inHouseTerm.",
        "    Party/independent collection record is another members:hasMembersMembership value, linked to its containing OireachtasMembership by members:inOireachtasMembership and to a term-scoped collection by members:memberOfCollection. Party records may also be specifically typed members:PartyMembership and linked via members:isPartyMembershipOf; Independent records must not be queried only through that party-specific property.",
        "    Do not rely on superclass type inference for collection-membership records. Some already-published Member graphs may omit the explicit members:ParliamentaryCollectionMembership superclass type even when members:PartyMembership is asserted; prefer the actual relationship predicates and specific type when known.",
        "    Use separate GRAPH patterns for Member records and referenced HouseTerm/collection/constituency descriptions; name matching uses foaf:name, skos:prefLabel, or rdfs:label as appropriate.",
    ]


def _external_property_context(repository_root: Path, prefixes: dict[str, str],
                               locally_declared: set[URIRef], graph: Graph,
                               externally_annotated: set[URIRef]) -> list[str]:
    """Include mapped or locally annotated external predicates and guidance."""
    mapping_directory = repository_root / "mappings"
    descriptions: dict[URIRef, set[str]] = {}
    kinds: dict[URIRef, set[str]] = {}
    if not mapping_directory.is_dir():
        return []
    for path in sorted(mapping_directory.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("mapping_status") not in {"mapped", "new"}:
                    continue
                if row.get("term_type") not in {"ObjectProperty", "DatatypeProperty", "AnnotationProperty"}:
                    continue
                term = row.get("ontology_term", "").strip()
                if ":" not in term:
                    continue
                prefix, local_name = term.split(":", 1)
                namespace = prefixes.get(prefix)
                if not namespace or not local_name or any(char.isspace() for char in local_name):
                    continue
                iri = URIRef(namespace + local_name)
                if iri in locally_declared:
                    continue
                kinds.setdefault(iri, set()).add(row["term_type"])
                note = " ".join((row.get("notes") or "").split())
                if note:
                    descriptions.setdefault(iri, set()).add(note)
    for iri in externally_annotated:
        if iri in locally_declared:
            continue
        for property_type, kind in (
            (OWL.ObjectProperty, "ObjectProperty"),
            (OWL.DatatypeProperty, "DatatypeProperty"),
            (OWL.AnnotationProperty, "AnnotationProperty"),
        ):
            if (iri, RDF.type, property_type) in graph:
                kinds.setdefault(iri, set()).add(kind)
                comment = _one_line(graph, iri, RDFS.comment)
                if comment:
                    descriptions.setdefault(iri, set()).add(comment)
    if not kinds:
        return []

    lines = ["\nExternal vocabulary predicates referenced by active mappings or local ontology annotations:"]
    for iri in sorted(kinds, key=str):
        domains = sorted(
            (_qname(value, prefixes) for value in graph.objects(iri, RDFS.domain)
             if isinstance(value, URIRef)), key=str.casefold
        )
        ranges = sorted(
            (_qname(value, prefixes) for value in graph.objects(iri, RDFS.range)
             if isinstance(value, URIRef)), key=str.casefold
        )
        details = f"  {_qname(iri, prefixes)} ({', '.join(sorted(kinds[iri]))})"
        if domains or ranges:
            details += f" ({', '.join(domains) or '?'} → {', '.join(ranges) or '?'})"
        label = _one_line(graph, iri, RDFS.label)
        if label:
            details += f"; label={label!r}"
        notes = sorted(descriptions.get(iri, ()), key=str.casefold)
        if notes:
            note = notes[0]
            if len(note) > COMMENT_CHARS:
                note = note[: COMMENT_CHARS - 1].rstrip() + "…"
            details += f"; mapping: {note}"
        lines.append(details)
    return lines


def build_schema_context(ontology_dir: str | Path) -> str:
    """Serialize asserted schema from every repository Turtle ontology module.

    Descriptions are schema facts only: individual instance data is not sent to
    the model. Annotations are shortened to keep the prompt practical.
    """
    directory = Path(ontology_dir)
    graph = Graph()
    externally_annotated: set[URIRef] = set()
    prefixes: dict[str, str] = {
        "agents": "https://data.oireachtas.ie/ontology#",
        "members": "https://data.oireachtas.ie/ontology/members#",
    }
    files = sorted(directory.glob("*.owl.ttl"))
    if not files:
        raise FileNotFoundError(f"No Turtle ontology modules found in {directory}")
    for path in files:
        module = Graph().parse(path, format="turtle")
        for prefix, namespace in module.namespaces():
            if not prefix:
                continue
            prefix = str(prefix)
            namespace = str(namespace)
            if prefix not in prefixes:
                prefixes[prefix] = namespace
        for term in module.subjects(RDFS.comment):
            if isinstance(term, URIRef) and not str(term).startswith((
                "https://data.oireachtas.ie/ontology#",
                "https://data.oireachtas.ie/ontology/members#",
            )):
                externally_annotated.add(term)
        graph += module
    pinned_vocabularies = (
        (directory / "ELI-OWL" / "eli-1.5.rdf", "xml"),
        (directory / "ELI-DL-OWL" / "eli-dl.ttl", "turtle"),
    )
    for path, format_ in pinned_vocabularies:
        if path.is_file():
            vocabulary = Graph().parse(path, format=format_)
            for prefix, namespace in vocabulary.namespaces():
                if prefix:
                    prefixes.setdefault(str(prefix), str(namespace))
            graph += vocabulary

    local_namespaces = (
        "https://data.oireachtas.ie/ontology#",
        "https://data.oireachtas.ie/ontology/members#",
    )

    def local(term) -> bool:
        return isinstance(term, URIRef) and str(term).startswith(local_namespaces)

    schema_terms = {
        type_: sorted(
            {term for term in graph.subjects(RDF.type, type_)
             if local(term) and not any(str(value).lower() == "true"
                                        for value in graph.objects(term, OWL.deprecated))},
            key=str,
        )
        for type_ in SCHEMA_TYPE_URIS
    }
    # Deprecated local ontology terms are omitted from the model-facing schema
    # but remain local declarations; do not reclassify active legacy mapping
    # references as external vocabulary predicates.
    locally_declared = {
        term for type_ in SCHEMA_TYPE_URIS for term in graph.subjects(RDF.type, type_)
        if local(term)
    }

    lines = ["Authoritative vocabulary (asserted in the repository's ontology/*.owl.ttl files):", "Namespaces:"]
    namespace_uris = set()
    for terms in schema_terms.values():
        for term in terms:
            for predicate, value in graph.predicate_objects(term):
                namespace_uris.add(predicate)
                if isinstance(value, URIRef):
                    namespace_uris.add(value)
    for uri in (
        URIRef("http://xmlns.com/foaf/0.1/name"),
        URIRef("http://xmlns.com/foaf/0.1/firstName"),
        URIRef("http://xmlns.com/foaf/0.1/familyName"),
        SKOS.prefLabel,
        RDFS.label,
    ):
        namespace_uris.add(uri)
    used_namespaces = {
        namespace
        for uri in namespace_uris
        for namespace in prefixes.values()
        if str(uri).startswith(namespace)
    }
    for prefix, namespace in sorted(prefixes.items()):
        if namespace in used_namespaces:
            lines.append(f"  {prefix}: <{namespace}>")

    for type_, heading in zip(SCHEMA_TYPE_URIS, ("Classes", "Object properties", "Datatype properties")):
        lines.append(f"\n{heading}:")
        for term in schema_terms[type_]:
            if type_ == OWL.Class:
                parents = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.subClassOf)
                     if isinstance(value, URIRef)),
                    key=str.casefold,
                )
                structural = f" subClassOf {', '.join(parents)}" if parents else ""
            else:
                domains = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.domain)
                     if isinstance(value, URIRef)), key=str.casefold
                )
                ranges = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.range)
                     if isinstance(value, URIRef)), key=str.casefold
                )
                parents = sorted(
                    (_qname(value, prefixes) for value in graph.objects(term, RDFS.subPropertyOf)
                     if isinstance(value, URIRef)), key=str.casefold
                )
                structural = ""
                if domains or ranges:
                    structural = f" ({', '.join(domains) or '?'} → {', '.join(ranges) or '?'})"
                if parents:
                    structural += f" subPropertyOf {', '.join(parents)}"
            label = _one_line(graph, term, SKOS.prefLabel) or _one_line(graph, term, RDFS.label)
            comment = _one_line(graph, term, RDFS.comment)
            detail = f"  {_qname(term, prefixes)}{structural}"
            if label:
                detail += f"; label={label!r}"
            if comment:
                detail += f"; note={comment}"
            lines.append(detail)

    individuals = sorted(
        {term for term in graph.subjects(RDF.type, OWL.NamedIndividual) if local(term)},
        key=str,
    )
    labeled_individuals = []
    for term in individuals:
        label = _one_line(graph, term, SKOS.prefLabel) or _one_line(graph, term, RDFS.label)
        if label:
            types = sorted(
                (_qname(value, prefixes) for value in graph.objects(term, RDF.type)
                 if local(value) or str(value).startswith("http://data.europa.eu/eli/")),
                key=str.casefold,
            )
            labeled_individuals.append(
                f"  {_qname(term, prefixes)} ({', '.join(types)}): {label!r}"
            )
    if labeled_individuals:
        lines.append("\nLabeled local named individuals (controlled vocabulary values; not data records):")
        lines.extend(labeled_individuals)

    lines.extend(_external_property_context(
        directory.parent, prefixes, locally_declared, graph, externally_annotated
    ))

    lines.extend((
        "\nCommon instance-label predicates from the repository's mappings:",
        "  foaf:name for Member names; skos:prefLabel for HouseTerm, collection and constituency labels;",
        "  rdfs:label for Bill lifecycle resources. These predicates are not interchangeable across every resource.",
    ))

    dataset_lines = _dataset_context(directory.parent)
    context = "\n".join((*lines, "", *dataset_lines))
    if len(context) > MAX_SCHEMA_CONTEXT_CHARS:
        raise ValueError(
            f"Generated schema context is {len(context)} characters; exceeds the {MAX_SCHEMA_CONTEXT_CHARS}-character cap."
        )
    return context
