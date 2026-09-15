"""Phase 0 checks for active CSV mapping references."""
from __future__ import annotations

import validate
from tools.validation import (
    MappingIntegrityError,
    NAMESPACES,
    unresolved_mapping_terms,
    validate_mapping_integrity,
)

def test_active_mapping_terms_resolve_to_local_or_recognised_external_vocabularies() -> None:
    unresolved = unresolved_mapping_terms(ontology_graph=validate.load_ontology_graph())
    assert not unresolved, "Unresolved active mapping terms:\n" + "\n".join(map(str, unresolved))


def test_unknown_active_term_fails_with_mapping_file_row_and_term(tmp_path) -> None:
    mapping = tmp_path / "example.csv"
    mapping.write_text(
        "ontology_term,mapping_status\nunknown:Term,mapped\n", encoding="utf-8"
    )

    try:
        validate_mapping_integrity(tmp_path, validate.load_ontology_graph())
    except MappingIntegrityError as error:
        assert "example.csv:2: unknown:Term" in str(error)
    else:
        raise AssertionError("Unknown active term must fail validation")


def test_approved_external_term_is_accepted(tmp_path) -> None:
    (tmp_path / "example.csv").write_text(
        "ontology_term,mapping_status\nfoaf:name,new\n", encoding="utf-8"
    )

    validate_mapping_integrity(tmp_path, validate.load_ontology_graph())


def test_future_work_term_is_ignored(tmp_path) -> None:
    (tmp_path / "example.csv").write_text(
        "ontology_term,mapping_status\nunknown:Term,future_work\n", encoding="utf-8"
    )

    validate_mapping_integrity(tmp_path, validate.load_ontology_graph())


def test_namespace_definition_covers_required_vocabularies() -> None:
    required = {
        "",
        "agents",
        "members",
        "rdf",
        "rdfs",
        "owl",
        "skos",
        "foaf",
        "dct",
        "dcat",
        "eli",
        "eli-dl",
    }
    assert required <= set(NAMESPACES)
