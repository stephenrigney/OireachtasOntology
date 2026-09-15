"""Namespace and mapping-integrity validation for the semantic baseline."""
from __future__ import annotations

import csv
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from rdflib import Graph, URIRef


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_DIR = REPOSITORY_ROOT / "ontology"
MAPPINGS_DIR = REPOSITORY_ROOT / "mappings"
ACTIVE_MAPPING_STATUSES = frozenset({"mapped", "new"})

# This is the authoritative prefix map for repository validation.  The local
# namespaces identify terms that must be defined by this repository; external
# namespaces are explicitly accepted without attempting to retrieve them.
NAMESPACES = {
    "": "https://data.oireachtas.ie/ontology#",
    "agents": "https://data.oireachtas.ie/ontology#",
    "members": "https://data.oireachtas.ie/ontology/members#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "dct": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "eli": "http://data.europa.eu/eli/ontology#",
    "eli-dl": "http://data.europa.eu/eli/eli-draft-legislation-ontology#",
}
LOCAL_PREFIXES = frozenset({"", "agents", "members"})
EXTERNAL_PREFIXES = frozenset(NAMESPACES) - LOCAL_PREFIXES


class MappingIntegrityError(RuntimeError):
    """Raised when an active mapping refers to an unresolved ontology term."""


@dataclass(frozen=True)
class MappingTermIssue:
    """An unresolved ontology term in a mapping row."""

    mapping_file: Path
    row_number: int
    term: str
    reason: str

    def __str__(self) -> str:
        return f"{self.mapping_file.name}:{self.row_number}: {self.term} ({self.reason})"


def split_mapping_terms(value: str) -> list[str]:
    """Split the slash-separated term field, excluding deliberate placeholders."""
    return [term.strip() for term in value.split("/") if term.strip() not in {"", "-", "—"}]


def resolve_prefixed_term(term: str) -> tuple[str, URIRef] | None:
    """Return a term's prefix and IRI, or ``None`` for an unknown prefix."""
    if term.startswith(":"):
        return "", URIRef(NAMESPACES[""] + term[1:])
    if ":" not in term:
        return None
    prefix, local_name = term.split(":", 1)
    namespace = NAMESPACES.get(prefix)
    return (prefix, URIRef(namespace + local_name)) if namespace else None


def defined_local_terms(ontology_graph: Graph) -> set[URIRef]:
    """Return repository terms that are subjects of ontology assertions."""
    return {subject for subject in ontology_graph.subjects() if isinstance(subject, URIRef)}


def load_ontology_terms(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    """Load local Turtle files for standalone mapping-integrity checks."""
    graph = Graph()
    for path in sorted(ontology_dir.rglob("*.ttl")):
        graph.parse(path, format="turtle")
    return graph


def unresolved_mapping_terms(
    mapping_dir: Path = MAPPINGS_DIR, ontology_graph: Graph | None = None
) -> list[MappingTermIssue]:
    """Return every unresolved term in ``mapped`` and ``new`` mapping rows."""
    if ontology_graph is None:
        ontology_graph = load_ontology_terms()
    local_terms = defined_local_terms(ontology_graph)
    unresolved: list[MappingTermIssue] = []

    for mapping_file in sorted(mapping_dir.glob("*.csv")):
        with mapping_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required_columns = {"ontology_term", "mapping_status"}
            if reader.fieldnames is None or not required_columns <= set(reader.fieldnames):
                unresolved.append(
                    MappingTermIssue(mapping_file, 1, "<CSV>", "missing required mapping columns")
                )
                continue
            for row_number, row in enumerate(reader, start=2):
                if row["mapping_status"].strip() not in ACTIVE_MAPPING_STATUSES:
                    continue
                for term in split_mapping_terms(row["ontology_term"]):
                    resolved = resolve_prefixed_term(term)
                    if resolved is None:
                        unresolved.append(
                            MappingTermIssue(mapping_file, row_number, term, "unrecognised vocabulary")
                        )
                        continue
                    prefix, term_iri = resolved
                    if prefix in LOCAL_PREFIXES and term_iri not in local_terms:
                        unresolved.append(
                            MappingTermIssue(mapping_file, row_number, term, "not defined locally")
                        )
    return unresolved


def validate_mapping_integrity(
    mapping_dir: Path = MAPPINGS_DIR, ontology_graph: Graph | None = None
) -> None:
    """Raise a clear error if an active mapping term cannot be resolved."""
    unresolved = unresolved_mapping_terms(mapping_dir, ontology_graph)
    if unresolved:
        details = "\n".join(str(issue) for issue in unresolved)
        raise MappingIntegrityError(f"Unresolved active mapping terms:\n{details}")


def main(argv: list[str] | None = None) -> int:
    """Run mapping-integrity validation as a small CI-friendly command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-dir", type=Path, default=MAPPINGS_DIR)
    parser.add_argument("--ontology-dir", type=Path, default=ONTOLOGY_DIR)
    args = parser.parse_args(argv)
    try:
        validate_mapping_integrity(args.mapping_dir, load_ontology_terms(args.ontology_dir))
    except Exception as error:
        print(f"Mapping-integrity validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Mapping-integrity validation passed: {args.mapping_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
