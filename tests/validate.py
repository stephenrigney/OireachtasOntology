"""Fail-closed validation for the local Oireachtas ontology modules."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import owlready2
from rdflib import Graph, OWL


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_DIR = REPOSITORY_ROOT / "ontology"


class OntologyValidationError(RuntimeError):
    """Raised when parsing or OWL consistency validation cannot complete."""


def ontology_files(ontology_dir: Path = ONTOLOGY_DIR) -> list[Path]:
    """Return the local ontology modules, rejecting an empty directory."""
    files = sorted(ontology_dir.glob("*.owl.ttl"))
    if not files:
        raise OntologyValidationError(f"No ontology files found in {ontology_dir}")
    return files


def load_ontology_graph(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    """Parse every local Turtle module, propagating parse failures."""
    graph = Graph()
    for path in ontology_files(ontology_dir):
        graph.parse(path, format="turtle")
    return graph


def run_consistency_check(graph: Graph) -> None:
    """Run HermiT and reject inconsistent or unsatisfiable ontology classes."""
    flattened = Graph()
    for triple in graph:
        if triple[1] != OWL.imports:
            flattened.add(triple)

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
    run_consistency_check(graph)
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
