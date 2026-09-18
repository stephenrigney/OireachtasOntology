"""Fail-closed validation for the repository's Oireachtas ontology modules."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import owlready2
from rdflib import Graph, OWL, RDFS, URIRef


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_DIR = REPOSITORY_ROOT / "ontology"
XSD_DATE = URIRef("http://www.w3.org/2001/XMLSchema#date")


class OntologyValidationError(RuntimeError):
    """Raised when parsing or OWL consistency validation cannot complete."""


def turtle_files(ontology_dir: Path = ONTOLOGY_DIR) -> list[Path]:
    """Return every Turtle file under the ontology directory."""
    files = sorted(ontology_dir.rglob("*.ttl"))
    if not files:
        raise OntologyValidationError(f"No Turtle files found in {ontology_dir}")
    return files


def ontology_files(ontology_dir: Path = ONTOLOGY_DIR) -> list[Path]:
    """Return local ontology modules used for the HermiT consistency check."""
    files = sorted(ontology_dir.glob("*.owl.ttl"))
    if not files:
        raise OntologyValidationError(f"No local ontology modules found in {ontology_dir}")
    return files


def load_ontology_graph(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    """Parse every Turtle file, identifying a file if parsing fails."""
    graph = Graph()
    for path in turtle_files(ontology_dir):
        try:
            graph.parse(path, format="turtle")
        except Exception as error:
            raise OntologyValidationError(f"Failed to parse {path}: {error}") from error
    return graph


def load_local_ontology_graph(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    """Parse local modules only for HermiT, excluding vendored external schemas."""
    graph = Graph()
    for path in ontology_files(ontology_dir):
        try:
            graph.parse(path, format="turtle")
        except Exception as error:
            raise OntologyValidationError(f"Failed to parse {path}: {error}") from error
    return graph


def hermit_input(graph: Graph) -> Graph:
    """Return HermiT-safe graph, excluding only the approved exact axiom."""
    flattened = Graph()
    for triple in graph:
        # HermiT implements the OWL 2 datatype map, which excludes xsd:date.
        # Phase 4 deliberately uses xsd:date for :dateSigned because the API
        # provides a date-only value. Turtle parsing still validates the range;
        # omit only this unsupported range axiom from the HermiT input.
        if triple[1] != OWL.imports and triple != (URIRef("https://data.oireachtas.ie/ontology#dateSigned"), RDFS.range, XSD_DATE):
            flattened.add(triple)
    return flattened


def run_consistency_check(graph: Graph) -> None:
    """Run HermiT and reject inconsistent or unsatisfiable ontology classes."""
    flattened = hermit_input(graph)

    with tempfile.NamedTemporaryFile(suffix=".owl", delete=False) as handle:
        ontology_path = Path(handle.name)
        data = flattened.serialize(format="xml")
        handle.write(data.encode() if isinstance(data, str) else data)

    world = owlready2.World()
    try:
        ontology = world.get_ontology(ontology_path.as_uri()).load()
        owlready2.sync_reasoner([ontology], infer_property_values=True)
        inconsistent = list(world.inconsistent_classes())
        if inconsistent:
            names = ", ".join(str(item) for item in inconsistent)
            raise OntologyValidationError(f"Unsatisfiable ontology classes: {names}")
    except owlready2.OwlReadyInconsistentOntologyError as error:
        raise OntologyValidationError("Ontology is inconsistent") from error
    except OntologyValidationError:
        raise
    except Exception as error:
        raise OntologyValidationError("Ontology reasoner failed") from error
    finally:
        ontology_path.unlink(missing_ok=True)


def validate_ontology(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    """Parse and reason over the ontology, raising on every validation error."""
    graph = load_ontology_graph(ontology_dir)
    # Vendored ELI-DL and approved local :dateSigned xsd:date are syntax
    # checked above. xsd:date is outside HermiT's OWL 2 datatype support, so
    # retain the executable consistency boundary for all other local axioms.
    run_consistency_check(load_local_ontology_graph(ontology_dir))
    return graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ontology-dir",
        type=Path,
        default=ONTOLOGY_DIR,
        help="directory containing local *.owl.ttl modules",
    )
    args = parser.parse_args(argv)
    try:
        graph = validate_ontology(args.ontology_dir)
    except Exception as error:
        print(f"Ontology validation failed: {error}", file=sys.stderr)
        return 1

    print(f"Ontology validation passed: {len(graph)} triples from {args.ontology_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
