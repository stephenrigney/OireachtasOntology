"""Byte-preservation and structural checks for representative AKN fixtures."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AKN_NAMESPACE = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN_NAMESPACE}

FIXTURES = {
    "seanad_2015-07-02.akn.xml": {
        "sha256": "6e2920af4b97aa0f692162f9fcd94324a18a1c26495399e8600a5ca450d762c0",
        "source_feature": "declared-vote-outcome",
    },
    "committee_public_accounts_2026-09-24.akn.xml": {
        "sha256": "690dada15afa1cb76ece7dd8387b973b00b43804023521b9ffb821d8944ff60e",
        "source_feature": "roll-call-table",
    },
    "dail_written_answers_2015-07-02.akn.xml": {
        "sha256": "0d0a1d49c67772a073cf762017efc56f3e8cab93a47629091b8e10c3fc2c4cab",
        "source_feature": "written-answer-structure",
    },
}


def test_debates_source_fixtures_preserve_authoritative_bytes_and_structure():
    fixture_directory = REPOSITORY_ROOT / "data" / "debates_examples"

    for filename, expectations in FIXTURES.items():
        source_bytes = (fixture_directory / filename).read_bytes()
        assert hashlib.sha256(source_bytes).hexdigest() == expectations["sha256"]

        root = ET.fromstring(source_bytes)
        assert root.tag == f"{{{AKN_NAMESPACE}}}akomaNtoso"
        assert root.find("akn:debate", NS) is not None
        assert root.find("akn:debate/akn:debateBody", NS) is not None

        if expectations["source_feature"] == "declared-vote-outcome":
            assert root.find(
                ".//akn:voting[@outcome='#declared']", NS
            ) is not None
        elif expectations["source_feature"] == "roll-call-table":
            assert root.find(".//akn:rollCall/akn:table", NS) is not None
        elif expectations["source_feature"] == "written-answer-structure":
            assert root.find(
                ".//akn:FRBRname[@value='writtens']", NS
            ) is not None
            assert root.find(
                ".//akn:debateSection[@name='writtenAnswers']"
                "/akn:debateSection[@name='writtenAnswer']/akn:question",
                NS,
            ) is not None
