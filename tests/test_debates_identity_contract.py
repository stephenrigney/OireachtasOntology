"""Check approved identity/source examples, not a Debates ETL implementation.

The small calculations here are a test-local reference of the contract in
documentation/debates-identity-contract.md. There is deliberately no import
from the ETL package and no assertion about transformed RDF. A few tests read
immutable AKN fixtures to verify source evidence and the reference ordering rule;
they still do not exercise runtime extraction, mapping or RDF publication.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urlsplit


CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "documentation"
    / "debates-identity-contract.md"
)
CONTRACT_TEXT = CONTRACT.read_text(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
AKN_NAMESPACE = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
AKN_NS = {"akn": AKN_NAMESPACE}
FIXTURE_DIR = ROOT / "data" / "debates_examples"
UNRESERVED = "-._~"
WORK_PREFIX = "https://data.oireachtas.ie/"
EXPRESSION_PREFIX = "https://data.oireachtas.ie/"
GRAPH_PREFIX = "https://data.oireachtas.ie/graph/debate/"
ADDRESSABLE_CHILD_TAGS = {
    f"{{{AKN_NAMESPACE}}}{local_name}"
    for local_name in ("debateSection", "speech", "summary", "question")
}


def _reference_akn_path(value: str) -> str:
    """Preserve AKN path hierarchy while encoding each literal path segment."""

    if value.startswith("/"):
        path = value
    else:
        parsed = urlsplit(value)
        if (parsed.scheme, parsed.netloc) != ("https", "data.oireachtas.ie") or parsed.query or parsed.fragment:
            raise ValueError("unexpected source origin or AKN path")
        path = parsed.path
    if "?" in path or "#" in path:
        raise ValueError("query or fragment is not source path identity")
    if not path.startswith("/akn/ie/debateRecord/"):
        raise ValueError("unexpected source origin or AKN path")
    segments = path[1:].split("/")
    if any(not segment or segment in {".", ".."} for segment in segments):
        raise ValueError("invalid source path segment")
    if any(re.search(r"%(?![0-9A-Fa-f]{2})", segment) for segment in segments):
        raise ValueError("malformed percent escape")
    return "/".join(_reference_component(segment) for segment in segments)


def _reference_component(value: str) -> str:
    """Reference calculation: UTF-8 RFC 3986 path-component encoding."""

    return quote(value, safe=UNRESERVED, encoding="utf-8", errors="strict")


def _reference_fallback_iri(
    *, container_iri: str, expanded_qname: str, c14n_subtree: str
) -> str:
    """Reference calculation for the documented fallback digest formula."""

    payload = (
        b"akn-eid-fallback-v1\0"
        + container_iri.encode("utf-8")
        + b"\0"
        + expanded_qname.encode("utf-8")
        + b"\0"
        + c14n_subtree.encode("utf-8")
    )
    digest = hashlib.sha256(payload).hexdigest()
    return f"{container_iri}/fallback/fb-{digest}"


def _reference_canonical_subtree(xml: str) -> str:
    """Reference canonicalization for the fixed C14N 2.0 regression vector."""

    return ET.canonicalize(
        xml_data=xml, with_comments=False, strip_text=False
    )


def _reference_check_ids(entries: list[dict[str, str | None]]) -> list[str]:
    """Apply the contract's duplicate checks to minimal test-only node records.

    Each entry has `eid`, `container`, `qname`, and canonical `subtree` values.
    This is a reference-model acceptance check, not production validation.
    """

    eids = [entry["eid"] for entry in entries]
    explicit = [eid for eid in eids if eid]
    if len(explicit) != len(set(explicit)):
        raise ValueError("duplicate decoded eId in source expression")

    identifiers = []
    for entry in entries:
        eid = entry["eid"]
        if eid:
            identifiers.append(
                f"{EXPRESSION_PREFIX}akn/ie/debateRecord/test/eid/e-{_reference_component(eid)}"
            )
        else:
            identifiers.append(
                _reference_fallback_iri(
                    container_iri=str(entry["container"]),
                    expanded_qname=str(entry["qname"]),
                    c14n_subtree=str(entry["subtree"]),
                )
            )

    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate proposed resource IRI")
    return identifiers


def _markdown_rows(section_heading: str) -> list[list[str]]:
    """Read simple backtick-delimited vectors from one Markdown section."""

    section = CONTRACT_TEXT.split(section_heading, maxsplit=1)[1]
    section = section.split("\n## ", maxsplit=1)[0]
    return [
        list(match.groups())
        for match in re.finditer(
            r"^\| `([^`]+)` \| `([^`]*)` \| `([^`]*)` \|$", section, re.M
        )
    ]


def _fixture_frbr_value(root: ET.Element, level: str) -> str:
    values = root.findall(
        f".//akn:identification/akn:{level}/akn:FRBRuri", AKN_NS
    )
    if len(values) != 1 or not values[0].get("value"):
        raise ValueError(f"fixture must have one non-empty {level}/FRBRuri")
    return values[0].attrib["value"]


def _addressable_ordinals(parent: ET.Element) -> dict[ET.Element, int]:
    """Test-local ordinal reference: count addressable direct children only."""

    result = {}
    ordinal = 0
    for child in parent:
        if child.tag in ADDRESSABLE_CHILD_TAGS:
            ordinal += 1
            result[child] = ordinal
    return result


class TestDebatesIdentityContract(unittest.TestCase):
    def test_eid_xml_vectors_use_parsed_value_and_exact_component_encoding(self):
        rows = _markdown_rows("## 1. URI component encoding")
        self.assertEqual(
            rows,
            [
                ['<speech eId="p&amp;1"/>', "p&1", "e-p%261"],
                ['<speech eId="rate%2F"/>', "rate%2F", "e-rate%252F"],
                ['<speech eId="sec/2"/>', "sec/2", "e-sec%2F2"],
                ['<speech eId="q?1"/>', "q?1", "e-q%3F1"],
                ['<speech eId="mark#1"/>', "mark#1", "e-mark%231"],
                ['<speech eId="dáil"/>', "dáil", "e-d%C3%A1il"],
                ['<speech eId="  p  "/>', "  p  ", "e-%20%20p%20%20"],
            ],
        )
        for fragment, documented_value, suffix in rows:
            with self.subTest(fragment=fragment):
                parsed = ET.fromstring(fragment).attrib["eId"]
                self.assertEqual(parsed, documented_value)
                self.assertEqual(f"e-{_reference_component(parsed)}", suffix)

    def test_work_expression_and_graph_iri_examples(self):
        work_value = "/akn/ie/debateRecord/dail/2015-07-02/debate"
        expression_value = work_value + "/mul@"
        work_iri = WORK_PREFIX + _reference_akn_path(work_value)
        expression_iri = EXPRESSION_PREFIX + _reference_akn_path(expression_value)
        graph_iri = GRAPH_PREFIX + _reference_akn_path(work_value).removeprefix("akn/ie/debateRecord/")

        self.assertEqual(
            work_iri,
            "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate",
        )
        self.assertEqual(
            expression_iri,
            "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul%40",
        )
        self.assertEqual(
            graph_iri,
            "https://data.oireachtas.ie/graph/debate/dail/2015-07-02/debate",
        )
        self.assertIn(f"| Work | `{work_value}` | `{work_iri}` |", CONTRACT_TEXT)
        self.assertIn(
            f"| Expression | `{expression_value}` | `{expression_iri}` |",
            CONTRACT_TEXT,
        )
        self.assertIn(work_iri + "#sitting", CONTRACT_TEXT)
        # A distinct expression for the same work is not a new graph key.
        self.assertEqual(
            GRAPH_PREFIX + _reference_akn_path(work_value).removeprefix("akn/ie/debateRecord/"), graph_iri
        )
        self.assertNotEqual(
            expression_iri,
            EXPRESSION_PREFIX
            + _reference_akn_path(work_value + "/eng@"),
        )
        normalized_doc = " ".join(CONTRACT_TEXT.split())
        self.assertIn("more than one of its Expressions is known", normalized_doc)
        self.assertIn("same graph key", normalized_doc)
        self.assertIn(
            "not an expression URI or any component eId", normalized_doc
        )

        self.assertEqual(_reference_akn_path(work_value), _reference_akn_path(work_iri))
        self.assertEqual(
            _reference_akn_path("/akn/ie/debateRecord/dail/a&b"),
            "akn/ie/debateRecord/dail/a%26b",
        )
        for invalid in (
            "https://elsewhere.invalid/akn/ie/debateRecord/dail/1",
            "/akn/ie/debateRecord/dail/../1",
            "/akn/ie/debateRecord/dail/a%Q1",
            "/akn/ie/debateRecord/dail/1?x=1",
            "/akn/ie/debateRecord/dail/1#fragment",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                _reference_akn_path(invalid)

    def test_all_immutable_fixture_frbr_values_use_the_canonical_work_expression_and_graph_rules(self):
        expected = {
            "dail_2015-07-02.akn.xml": (
                "/akn/ie/debateRecord/dail/2015-07-02",
                "/akn/ie/debateRecord/dail/2015-07-02/eng@",
                "https://data.oireachtas.ie/graph/debate/dail/2015-07-02",
            ),
            "dail_2026-02-26.akn.xml": (
                "/akn/ie/debateRecord/dail/2026-02-25/debate",
                "/akn/ie/debateRecord/dail/2026-02-25/debate/mul@",
                "https://data.oireachtas.ie/graph/debate/dail/2026-02-25/debate",
            ),
            "seanad_2015-07-02.akn.xml": (
                "/akn/ie/debateRecord/seanad/2015-07-02/debate",
                "/akn/ie/debateRecord/seanad/2015-07-02/debate/mul@",
                "https://data.oireachtas.ie/graph/debate/seanad/2015-07-02/debate",
            ),
            "committee_public_accounts_2026-09-24.akn.xml": (
                "/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate",
                "/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate/mul@",
                "https://data.oireachtas.ie/graph/debate/committee_of_public_accounts/2026-09-24/debate",
            ),
            "dail_written_answers_2015-07-02.akn.xml": (
                "/akn/ie/debateRecord/dail/2015-07-02/writtens",
                "/akn/ie/debateRecord/dail/2015-07-02/writtens/mul@",
                "https://data.oireachtas.ie/graph/debate/dail/2015-07-02/writtens",
            ),
        }

        for filename, (source_work, source_expression, expected_graph) in expected.items():
            with self.subTest(filename=filename):
                root = ET.parse(FIXTURE_DIR / filename).getroot()
                self.assertEqual(_fixture_frbr_value(root, "FRBRWork"), source_work)
                self.assertEqual(
                    _fixture_frbr_value(root, "FRBRExpression"), source_expression
                )
                work_iri = WORK_PREFIX + _reference_akn_path(source_work)
                expression_iri = EXPRESSION_PREFIX + _reference_akn_path(source_expression)
                graph_iri = GRAPH_PREFIX + _reference_akn_path(source_work).removeprefix(
                    "akn/ie/debateRecord/"
                )
                self.assertEqual(
                    work_iri, "https://data.oireachtas.ie" + source_work
                )
                self.assertEqual(
                    expression_iri,
                    "https://data.oireachtas.ie"
                    + source_expression.replace("@", "%40"),
                )
                self.assertEqual(graph_iri, expected_graph)
                # Literal @ is encoded once in the Expression path, never again
                # in the Work-keyed graph path.
                self.assertIn("%40", expression_iri)
                self.assertNotIn("%2540", expression_iri)
                self.assertNotIn("mul%40", graph_iri)

        # The written-answer Work is distinct from the same-date Dáil debate;
        # matching House/date does not merge their identities or graph keys.
        self.assertNotEqual(
            expected["dail_2015-07-02.akn.xml"][0],
            expected["dail_written_answers_2015-07-02.akn.xml"][0],
        )
        self.assertNotEqual(
            expected["dail_2015-07-02.akn.xml"][2],
            expected["dail_written_answers_2015-07-02.akn.xml"][2],
        )

    def test_contract_fails_closed_for_known_multiple_expressions_at_work_boundary(self):
        work = "/akn/ie/debateRecord/dail/2015-07-02/debate"
        expressions = (work + "/eng@", work + "/mul@")
        expression_iris = tuple(
            EXPRESSION_PREFIX + _reference_akn_path(value) for value in expressions
        )
        graph_iri = GRAPH_PREFIX + _reference_akn_path(work).removeprefix(
            "akn/ie/debateRecord/"
        )
        self.assertNotEqual(expression_iris[0], expression_iris[1])
        self.assertEqual(
            graph_iri,
            "https://data.oireachtas.ie/graph/debate/dail/2015-07-02/debate",
        )

        review_path = ROOT / "documentation" / "debates-semantic-review.md"
        review = " ".join(review_path.read_text(encoding="utf-8").split())
        self.assertIn(
            "Where more than one Expression is *known* for the same Work, preserve each exact input but fail closed for that Work rather than replacing its graph from one file.",
            review,
        )
        self.assertIn(
            "Do not claim that a single fetched file proves there is only one Expression globally.",
            review,
        )
        self.assertIn("Never silently pick the last fetched Expression", review)

    def test_fallback_vector_is_deterministic_and_excludes_position(self):
        container = (
            "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul%40"
        )
        source = (
            '<speech xmlns="urn:akn:test">'
            "<p>Vote &amp; return</p></speech>"
        )
        c14n = _reference_canonical_subtree(source)
        self.assertEqual(
            c14n,
            '<speech xmlns="urn:akn:test"><p>Vote &amp; return</p></speech>',
        )
        expected = container + "/fallback/fb-" + hashlib.sha256(
            b"akn-eid-fallback-v1\0"
            + container.encode("utf-8") + b"\0"
            + b"{urn:akn:test}speech\0" + c14n.encode("utf-8")
        ).hexdigest()
        self.assertTrue(expected.endswith("646242b40e1062e09f7d3cfbcb6d5506ecb032b190ec264e23f52940ad9749a2"))
        self.assertIn(expected, CONTRACT_TEXT)
        first = _reference_fallback_iri(
            container_iri=container,
            expanded_qname="{urn:akn:test}speech",
            c14n_subtree=c14n,
        )
        self.assertEqual(first, expected)

        def target_fallback(parent_xml: str) -> str:
            root = ET.fromstring(parent_xml)
            node = root.find("{urn:akn:test}speech")
            self.assertIsNotNone(node)
            subtree_xml = ET.tostring(node, encoding="unicode")
            return _reference_fallback_iri(
                container_iri=container,
                expanded_qname=node.tag,
                c14n_subtree=_reference_canonical_subtree(subtree_xml),
            )

        before = target_fallback(
            '<parent xmlns="urn:akn:test"><summary>first</summary>'
            "<speech><p>Vote &amp; return</p></speech></parent>"
        )
        after = target_fallback(
            '<parent xmlns="urn:akn:test"><speech><p>Vote &amp; return</p>'
            "</speech><summary>second</summary></parent>"
        )
        # Reordering an unrelated sibling does not salt identity with position.
        self.assertEqual(before, after)

    def test_missing_empty_and_duplicate_ids_fail_closed_as_specified(self):
        container = "https://data.oireachtas.ie/akn/ie/debateRecord/test"
        subtree = "<speech xmlns=\"urn:akn:test\"><p>same</p></speech>"
        base = {
            "container": container,
            "qname": "{urn:akn:test}speech",
            "subtree": _reference_canonical_subtree(subtree),
        }

        one_missing = [{**base, "eid": None}]
        one_empty = [{**base, "eid": ""}]
        self.assertEqual(
            _reference_check_ids(one_missing),
            _reference_check_ids(one_empty),
        )

        # Empty IDs take fallback; a non-empty space is preserved as an eId.
        whitespace = [{**base, "eid": " "}]
        self.assertIn("/eid/e-%20", _reference_check_ids(whitespace)[0])

        # The same decoded explicit value is a duplicate, never a fallback case.
        with self.assertRaisesRegex(ValueError, "duplicate decoded eId"):
            _reference_check_ids(
                [{**base, "eid": "p&1"}, {**base, "eid": "p&1"}]
            )
        decoded_entity_variants = [
            ET.fromstring('<speech eId="p&amp;1"/>').attrib["eId"],
            ET.fromstring('<speech eId="p&#38;1"/>').attrib["eId"],
        ]
        self.assertEqual(decoded_entity_variants, ["p&1", "p&1"])
        with self.assertRaisesRegex(ValueError, "duplicate decoded eId"):
            _reference_check_ids(
                [{**base, "eid": eid} for eid in decoded_entity_variants]
            )

        # Equal missing-ID siblings in the same context collide; adding an
        # ordinal or suffix is forbidden, so the expression fails closed.
        with self.assertRaisesRegex(ValueError, "duplicate proposed resource IRI"):
            _reference_check_ids(
                [{**base, "eid": None}, {**base, "eid": None}]
            )

    def test_reference_outcome_sidecar_has_exact_four_statuses_and_source_hash(self):
        section = CONTRACT_TEXT.split(
            "## 5. Reference outcomes and source-hash sidecar", maxsplit=1
        )[1].split("\n## ", maxsplit=1)[0]
        documented_statuses = re.findall(r"^\| `([^`]+)` \|", section, re.M)
        self.assertEqual(documented_statuses, ["resolved", "unresolved", "malformed", "absent"])
        self.assertIn("source_sha256", CONTRACT_TEXT)
        self.assertIn("exact immutable original XML", CONTRACT_TEXT)
        self.assertIn("not a named graph", CONTRACT_TEXT)
        self.assertIn("existing transform-report/raw-source state", CONTRACT_TEXT)
        source = b"<akn/>"
        self.assertEqual(
            hashlib.sha256(source).hexdigest(),
            "47ba3135b27455c5e29750e62d1085a143596d93e0b16a20af1dbfd74287d7ee",
        )
        self.assertNotEqual(
            hashlib.sha256(source).digest(),
            hashlib.sha256(source + b"\n").digest(),
        )
        self.assertIn(
            "47ba3135b27455c5e29750e62d1085a143596d93e0b16a20af1dbfd74287d7ee",
            CONTRACT_TEXT,
        )

    def test_reference_status_examples_do_not_invent_targets(self):
        def reference_status(value, *, candidates=(), grammar_ok=True):
            if value is None:
                return "absent", None
            if not grammar_ok:
                return "malformed", None
            if value == "#" or len(candidates) != 1:
                return "unresolved", None
            return "resolved", candidates[0]

        examples = [
            (None, (), True, "absent"),
            ("#", (), True, "unresolved"),
            ("#sum_29", (), False, "malformed"),
            ("#sum_29", (), True, "unresolved"),
            ("#sum_29", ("https://data.oireachtas.ie/akn/ie/debateRecord/dail/1/eid/e-sum_29",), True, "resolved"),
            ("#sum_29", ("candidate-a", "candidate-b"), True, "unresolved"),
        ]
        for value, candidates, grammar_ok, expected in examples:
            with self.subTest(value=value, candidates=candidates):
                status, target = reference_status(value, candidates=candidates, grammar_ok=grammar_ok)
                self.assertEqual(status, expected)
                self.assertEqual(target is not None, status == "resolved")
        self.assertIn('speech/@by="#"', CONTRACT_TEXT)
        self.assertIn("`#lost` used as a controlled", CONTRACT_TEXT)

    def test_approved_source_order_is_mixed_sibling_metadata_not_an_identifier(self):
        self.assertIn("1-based source ordinal among all", CONTRACT_TEXT)
        normalized_doc = " ".join(CONTRACT_TEXT.split())
        self.assertIn(
            "never an identifier, fallback input, or tie-breaker", normalized_doc
        )

    def test_written_answer_ordinal_uses_mixed_immediate_children_and_restarts_in_container(self):
        root = ET.parse(
            FIXTURE_DIR / "dail_written_answers_2015-07-02.akn.xml"
        ).getroot()
        parents = {child: parent for parent in root.iter() for child in parent}
        written_answer = root.find(
            ".//akn:debateSection[@eId='dbsect_83']", AKN_NS
        )
        self.assertIsNotNone(written_answer)
        parent = parents[written_answer]
        self.assertEqual(parent.get("eId"), "dbsect_69")

        # The thirteenth preceding writtenAnswer group makes dbsect_83 the
        # fourteenth addressable direct child; its heading is not addressable.
        self.assertEqual(_addressable_ordinals(parent)[written_answer], 14)

        # Within dbsect_83's own immediate scope, two questions and a speech
        # are mixed siblings. The nested scope starts again at one.
        children = _addressable_ordinals(written_answer)
        self.assertEqual(
            [
                (child.tag.rsplit("}", maxsplit=1)[-1], child.get("eId"), ordinal)
                for child, ordinal in children.items()
            ],
            [
                ("question", "pq_38", 1),
                ("question", "pq_57", 2),
                ("speech", "spk_1033", 3),
            ],
        )

        mapping_path = ROOT / "mappings" / "debates_mapping.csv"
        with mapping_path.open(encoding="utf-8", newline="") as handle:
            ordinal_rows = [
                row for row in csv.DictReader(handle)
                if row["ontology_term"] == ":sourceOrdinal"
            ]
        self.assertEqual(len(ordinal_rows), 1)
        self.assertEqual(ordinal_rows[0]["mapping_status"], "mapped")
        ordinal_notes = " ".join(ordinal_rows[0]["notes"].split())
        self.assertIn("across child kinds", ordinal_notes)
        self.assertIn("addressable immediate XML children", ordinal_notes)
        self.assertIn("nested container restarts at 1", ordinal_notes)
        self.assertIn("never identity", ordinal_notes)


if __name__ == "__main__":
    unittest.main()
