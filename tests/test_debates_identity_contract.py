"""Regression-test the proposal's examples, not a Debates ETL implementation.

The small calculations here are a test-local reference of the contract in
documentation/debates-identity-contract.md. There is deliberately no import
from the ETL package and no assertion about transformed RDF.
"""

from __future__ import annotations

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
UNRESERVED = "-._~"
WORK_PREFIX = "https://data.oireachtas.ie/"
EXPRESSION_PREFIX = "https://data.oireachtas.ie/"
GRAPH_PREFIX = "https://data.oireachtas.ie/graph/debate/"


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
        self.assertIn("multiple expressions", CONTRACT_TEXT)
        normalized_doc = " ".join(CONTRACT_TEXT.split())
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

    def test_order_is_a_mixed_sibling_proposal_not_an_identifier(self):
        self.assertIn("1-based source ordinal among all", CONTRACT_TEXT)
        normalized_doc = " ".join(CONTRACT_TEXT.split())
        self.assertIn("pending ontology/semantic approval", normalized_doc)
        self.assertIn(
            "never an identifier, fallback input, or tie-breaker", normalized_doc
        )
        self.assertIn("No property assertion or mapping is authorized", CONTRACT_TEXT)


if __name__ == "__main__":
    unittest.main()
