"""Phase 0 checks for active CSV mapping references."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rdflib import URIRef

import validate


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAPPINGS_DIR = REPOSITORY_ROOT / "mappings"
ACTIVE_STATUSES = {"mapped", "new"}
LOCAL_PREFIXES = {
    "": "https://data.oireachtas.ie/ontology#",
    "agents": "https://data.oireachtas.ie/ontology#",
    "members": "https://data.oireachtas.ie/ontology/members#",
}
# These namespaces are explicitly documented in README.md and ontology/README.md.
EXTERNAL_PREFIXES = {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "eli": "http://data.europa.eu/eli/ontology#",
    "eli-dl": "http://data.europa.eu/eli/eli-draft-legislation-ontology#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "org": "http://www.w3.org/ns/org#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "time": "http://www.w3.org/2006/time#",
}


@dataclass(frozen=True)
class UnresolvedTerm:
    mapping_file: Path
    row_number: int
    term: str
    reason: str

    def __str__(self) -> str:
        return f"{self.mapping_file.name}:{self.row_number}: {self.term} ({self.reason})"


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in value.split("/") if term.strip() and term.strip() != "-"]


def resolve_local_term(term: str) -> URIRef | None:
    if term.startswith(":"):
        return URIRef(LOCAL_PREFIXES[""] + term[1:])
    if ":" not in term:
        return None
    prefix, local_name = term.split(":", 1)
    namespace = LOCAL_PREFIXES.get(prefix)
    return URIRef(namespace + local_name) if namespace else None


def unresolved_active_terms() -> list[UnresolvedTerm]:
    graph = validate.load_ontology_graph()
    defined_terms = set(graph.subjects())
    unresolved: list[UnresolvedTerm] = []

    for mapping_file in sorted(MAPPINGS_DIR.glob("*.csv")):
        with mapping_file.open(newline="", encoding="utf-8") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                if row["mapping_status"] not in ACTIVE_STATUSES:
                    continue
                for term in split_terms(row["ontology_term"]):
                    local_term = resolve_local_term(term)
                    if local_term is not None:
                        if local_term not in defined_terms:
                            unresolved.append(
                                UnresolvedTerm(mapping_file, row_number, term, "not defined locally")
                            )
                        continue
                    prefix = term.split(":", 1)[0] if ":" in term else ""
                    if prefix not in EXTERNAL_PREFIXES:
                        unresolved.append(
                            UnresolvedTerm(mapping_file, row_number, term, "unrecognised vocabulary")
                        )
    return unresolved


def test_active_mapping_terms_resolve_to_local_or_recognised_external_vocabularies() -> None:
    unresolved = unresolved_active_terms()
    assert not unresolved, "Unresolved active mapping terms:\n" + "\n".join(map(str, unresolved))
