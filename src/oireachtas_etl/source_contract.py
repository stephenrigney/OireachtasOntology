"""Source-shape contracts and deterministic JSON schema-drift reports.

The contracts describe fields currently read by the Houses, Parties,
Constituencies, Members and Legislation transforms (including source fields
used by their validation/helpers). Optional source properties stay optional:
an absent optional property is not drift. A malformed consumed property is a
record failure; malformed top-level record containers are source failures.

Call :func:`classify_source_contract` with the already-extracted endpoint
records and an immutable raw-page evidence pointer. ``source_evidence`` may
point at the containing result array (one pointer for the whole page) or be a
sequence of pointers, one directly to each record. Findings carry both the
page/hash evidence and a JSON pointer to the affected (or missing) property.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class _Spec:
    kinds: tuple[str, ...]
    required: bool = True
    nullable: bool = False
    fields: Mapping[str, "_Spec"] | None = None
    item: "_Spec | None" = None
    choices: frozenset[object] | None = None
    min_items: int = 0


def _scalar(*kinds: str, required: bool = True, nullable: bool = False,
            choices: Sequence[object] | None = None) -> _Spec:
    return _Spec(kinds, required, nullable,
                 choices=frozenset(choices) if choices is not None else None)


def _obj(fields: Mapping[str, _Spec], *, required: bool = True,
         nullable: bool = False) -> _Spec:
    return _Spec(("object",), required, nullable, fields=fields)


def _array(item: _Spec, *, required: bool = True, min_items: int = 0) -> _Spec:
    return _Spec(("array",), required, item=item, min_items=min_items)


def _str(*, required: bool = True, nullable: bool = False,
         choices: Sequence[object] | None = None) -> _Spec:
    return _scalar("string", required=required, nullable=nullable, choices=choices)


def _date_range(*, required: bool = True) -> _Spec:
    # Date syntax is validated by the transforms; this layer detects JSON
    # shape/type drift without duplicating date parsing semantics.
    return _obj({
        "start": _str(),
        "end": _str(required=False, nullable=True),
    }, required=required)


def _house_term(*, required: bool = True, nullable: bool = False) -> _Spec:
    return _obj({
        "uri": _str(),
        "houseCode": _str(choices=("dail", "seanad")),
        "houseNo": _scalar("string", "integer"),
        # Known reference-only fields; not required for Member/Bill output.
        "showAs": _str(required=False, nullable=True),
        "chamberType": _str(required=False, nullable=True),
        "chamberCode": _str(required=False, nullable=True),
    }, required=required, nullable=nullable)


_HOUSE_RECORD = _obj({
    "house": _obj({
        "uri": _str(), "houseCode": _str(choices=("dail", "seanad", "dail & seanad")),
        "showAs": _str(), "houseNo": _scalar("string", "integer"),
        "seats": _scalar("integer", "string"),
        "dateRange": _date_range(),
        "chamberType": _str(required=False), "chamberCode": _str(required=False),
        "houseType": _str(required=False),
    }),
})
_EXCLUDED_HOUSE_RECORD = _obj({
    # transform_houses_with_report consumes only the combined code and copies
    # uri as exclusion evidence before skipping every semantic field.
    "house": _obj({
        "houseCode": _str(choices=("dail & seanad",)),
        "uri": _str(required=False, nullable=True),
    }),
})

_PARTY_RECORD = _obj({
    "party": _obj({
        "uri": _str(), "partyCode": _str(), "showAs": _str(),
    }),
    "house": _obj({
        "uri": _str(),
        # Present in source examples but not needed to form Parties RDF.
        "houseNo": _scalar("string", "integer", required=False),
        "houseCode": _str(required=False), "showAs": _str(required=False, nullable=True),
    }),
})

_CONSTITUENCY_RECORD = _obj({
    "constituencyOrPanel": _obj({
        "uri": _str(), "representType": _str(choices=("constituency", "panel")),
        "representCode": _str(), "showAs": _str(),
    }),
    "house": _obj({
        "uri": _str(), "houseCode": _str(choices=("dail", "seanad")),
        "houseNo": _scalar("string", "integer", required=False),
        "showAs": _str(required=False, nullable=True),
    }),
})


_MEMBER_REPRESENT = _obj({
    "uri": _str(), "representType": _str(choices=("constituency", "panel")),
    "representCode": _str(),
    # Reference-only label: no Member graph assertion is made from it.
    "showAs": _str(required=False, nullable=True),
})
_MEMBER_PARTY = _obj({
    "uri": _str(), "partyCode": _str(),
    "showAs": _str(required=False, nullable=True),
    "dateRange": _date_range(),
})
_MEMBER_COMMITTEE = _obj({
    "uri": _str(), "memberDateRange": _date_range(),
    "role": _Spec(("array", "object"), required=False,
                  fields={"title": _str(choices=("Cathaoirleach", "Leas-Chathaoirleach")),
                          "dateRange": _date_range()},
                  item=_str(choices=("Chair", "Deputy Chair"))),
})
_MEMBER_OFFICE = _obj({
    "office": _obj({
        "officeName": _obj({
            "showAs": _str(), "uri": _str(required=False, nullable=True),
        }),
        "dateRange": _date_range(),
    }),
})
_MEMBER_MEMBERSHIP = _obj({
    "uri": _str(), "house": _house_term(), "dateRange": _date_range(),
    # These collections default to [] in the transformer; absence is valid.
    "represents": _array(_obj({"represent": _MEMBER_REPRESENT}), required=False),
    "parties": _array(_obj({"party": _MEMBER_PARTY}), required=False),
    "committees": _array(_MEMBER_COMMITTEE, required=False),
    "offices": _array(_MEMBER_OFFICE, required=False),
})
_MEMBER_RECORD = _obj({
    "member": _obj({
        "uri": _str(), "memberCode": _str(), "image": _scalar("boolean"),
        "memberships": _array(_obj({"membership": _MEMBER_MEMBERSHIP}), min_items=0),
        # Optional mapped description fields: absence must not be treated as drift.
        "showAs": _str(required=False, nullable=True),
        "fullName": _str(required=False, nullable=True),
        "firstName": _str(required=False, nullable=True),
        "lastName": _str(required=False, nullable=True),
        "pId": _str(required=False, nullable=True),
        "gender": _str(required=False, nullable=True),
        "wikiTitle": _str(required=False, nullable=True),
        "dateOfDeath": _str(required=False, nullable=True),
    }),
})


def _formats(*, required: bool = True) -> _Spec:
    return _obj({
        "pdf": _obj({"uri": _str()}, required=False, nullable=True),
        "xml": _obj({"uri": _str()}, required=False, nullable=True),
    }, required=required)


_BILL_HOUSE = _obj({"uri": _str()}, required=False, nullable=True)
_BILL_EVENT = _obj({
    "uri": _str(), "showAs": _str(), "eventURI": _str(),
    "dates": _array(_obj({"date": _str()}), min_items=1),
    "chamber": _obj({"uri": _str()}, required=False, nullable=True),
})
_BILL_STAGE_EVENT = _obj({
    "uri": _str(), "showAs": _str(), "dates": _array(_obj({"date": _str()}), min_items=1),
    # The transform applies int(), so integer strings are source-compatible.
    "stageURI": _str(), "progressStage": _scalar("integer", "string"),
    "stageCompleted": _scalar("boolean"), "house": _BILL_HOUSE,
    "chamber": _obj({"uri": _str()}, required=False, nullable=True),
})
_AMENDMENT = _obj({
    "amendmentTypeUri": _obj({"uri": _str()}), "chamber": _obj({"uri": _str()}),
    "date": _str(), "formats": _formats(), "showAs": _str(),
    "stage": _obj({"uri": _str()}), "stageNo": _scalar("string", "integer"),
})
_RELATED_DOC = _obj({
    "uri": _str(), "docType": _str(choices=("errata", "gluais", "memo")),
    "showAs": _str(), "date": _str(), "lang": _str(choices=("eng", "gle", "mul")),
    "formats": _formats(),
})
_VERSION = _obj({
    "docType": _str(choices=("act", "bill")),
    # The transformer only requires these for bill versions. Act versions are
    # ownership-deferred and are deliberately not made stricter here.
    "uri": _str(required=False), "date": _str(required=False),
    "lang": _str(required=False, choices=("eng", "gle", "mul")),
    "showAs": _str(required=False), "formats": _formats(required=False),
})
_BILL_RECORD = _obj({
    "bill": _obj({
        "uri": _str(), "billYear": _scalar("string", "integer"),
        "billNo": _scalar("string", "integer"),
        "originHouseURI": _str(), "lastUpdated": _str(),
        "billTypeURI": _str(), "statusURI": _str(), "sourceURI": _str(),
        "methodURI": _str(),
        "shortTitleEn": _str(required=False, nullable=True),
        "shortTitleGa": _str(required=False, nullable=True),
        "longTitleEn": _str(required=False, nullable=True),
        "longTitleGa": _str(required=False, nullable=True),
        "stages": _array(_obj({"event": _BILL_STAGE_EVENT}), min_items=1),
        "mostRecentStage": _obj({"event": _obj({"uri": _str()})}),
        "events": _array(_obj({"event": _BILL_EVENT}), required=False),
        "amendmentLists": _array(_obj({"amendmentList": _AMENDMENT}), required=False),
        "relatedDocs": _array(_obj({"relatedDoc": _RELATED_DOC}), required=False),
        "versions": _array(_obj({"version": _VERSION}), required=False),
        "act": _obj({"uri": _str(required=False, nullable=True)}, required=False, nullable=True),
        "sponsors": _array(_obj({"sponsor": _obj({
            "isPrimary": _scalar("boolean"),
            "by": _obj({"uri": _str(required=False, nullable=True),
                         "showAs": _str(required=False, nullable=True)}, required=False,
                        nullable=False),
            "as": _obj({"uri": _str(required=False, nullable=True),
                         "showAs": _str(required=False, nullable=True)}, required=False,
                        nullable=False),
        })}), required=False),
        # Debate RDF is deferred; the current transform only retains URI evidence.
        "debates": _array(_obj({"uri": _str(required=False)}, required=False), required=False),
    }),
})


_CONTRACTS: Mapping[str, _Spec] = {
    "houses": _HOUSE_RECORD,
    "parties": _PARTY_RECORD,
    "constituencies": _CONSTITUENCY_RECORD,
    "members": _MEMBER_RECORD,
    "legislation": _BILL_RECORD,
}

# Known source properties at each object location in the representative API
# examples. Paths use ``[]`` for array items. Keeping this baseline
# path-specific means that a property already seen elsewhere (for example
# ``uri`` inside a dateRange) is still reported as additive drift here.
def _shape_fields(rows: Mapping[str, str]) -> Mapping[tuple[str, ...], frozenset[str]]:
    return {tuple(path.split(".")) if path else (): frozenset(names.split())
            for path, names in rows.items()}


_KNOWN_SHAPES: Mapping[str, Mapping[tuple[str, ...], frozenset[str]]] = {
    "houses": _shape_fields({
        "": "house",
        "house": "chamberCode chamberType dateRange houseCode houseNo houseType seats showAs uri",
        "house.dateRange": "end start",
    }),
    "parties": _shape_fields({
        "": "house party",
        "house": "houseCode houseNo showAs uri",
        "party": "partyCode showAs uri",
    }),
    "constituencies": _shape_fields({
        "": "constituencyOrPanel house",
        "constituencyOrPanel": "representCode representType showAs uri",
        "house": "houseCode houseNo showAs uri",
    }),
    "members": _shape_fields({
        "": "member",
        "member": "dateOfDeath firstName fullName gender image lastName memberCode memberships pId showAs uri wikiTitle",
        "member.memberships.[]": "membership",
        "member.memberships.[].membership": "committees dateRange house offices parties represents uri",
        "member.memberships.[].membership.committees.[]": "committeeCode committeeDateRange committeeID committeeName committeeType expiryType houseCode houseNo mainStatus memberDateRange role serviceUnit status uri",
        "member.memberships.[].membership.committees.[].committeeDateRange": "end start",
        "member.memberships.[].membership.committees.[].committeeName.[]": "dateRange nameEn nameGa",
        "member.memberships.[].membership.committees.[].committeeName.[].dateRange": "end start",
        "member.memberships.[].membership.committees.[].memberDateRange": "end start",
        "member.memberships.[].membership.dateRange": "end start",
        "member.memberships.[].membership.house": "chamberType houseCode houseNo showAs uri",
        "member.memberships.[].membership.offices.[]": "office",
        "member.memberships.[].membership.offices.[].office": "dateRange officeName",
        "member.memberships.[].membership.offices.[].office.dateRange": "end start",
        "member.memberships.[].membership.offices.[].office.officeName": "showAs uri",
        "member.memberships.[].membership.parties.[]": "party",
        "member.memberships.[].membership.parties.[].party": "dateRange partyCode showAs uri",
        "member.memberships.[].membership.parties.[].party.dateRange": "end start",
        "member.memberships.[].membership.parties.[].party.dateRange": "end start",
        "member.memberships.[].membership.represents.[]": "represent",
        "member.memberships.[].membership.represents.[].represent": "representCode representType showAs uri",
        # The role-object form is exercised by focused Member transform tests.
        "member.memberships.[].membership.committees.[].role": "dateRange title",
        "member.memberships.[].membership.committees.[].role.dateRange": "end start",
    }),
    "legislation": _shape_fields({
        "": "bill billSort contextDate",
        "bill": "act amendmentLists billNo billType billTypeURI billYear debates events lastUpdated longTitleEn longTitleGa method methodURI mostRecentStage originHouse originHouseURI relatedDocs shortTitleEn shortTitleGa source sourceURI sponsors stages status statusURI uri versions",
        "bill.act": "actNo actYear dateSigned longTitleEn longTitleGa shortTitleEn shortTitleGa statutebookURI uri",
        "bill.amendmentLists.[]": "amendmentList",
        "bill.amendmentLists.[].amendmentList": "amendmentTypeUri chamber date formats showAs stage stageNo",
        "bill.amendmentLists.[].amendmentList.amendmentTypeUri": "uri",
        "bill.amendmentLists.[].amendmentList.chamber": "showAs uri",
        "bill.amendmentLists.[].amendmentList.formats": "pdf xml",
        "bill.amendmentLists.[].amendmentList.formats.pdf": "uri",
        "bill.amendmentLists.[].amendmentList.formats.xml": "uri",
        "bill.amendmentLists.[].amendmentList.stage": "showAs uri",
        "bill.debates.[]": "chamber date debateSectionId showAs uri",
        "bill.debates.[].chamber": "showAs uri",
        "bill.events.[]": "event",
        "bill.events.[].event": "chamber dates eventURI showAs uri",
        "bill.events.[].event.chamber": "chamberCode showAs uri",
        "bill.events.[].event.dates.[]": "date",
        "bill.mostRecentStage": "event",
        "bill.mostRecentStage.event": "chamber dates house progressStage showAs stageCompleted stageOutcome stageURI uri",
        "bill.mostRecentStage.event.dates.[]": "date",
        "bill.originHouse": "showAs uri",
        "bill.relatedDocs.[]": "relatedDoc",
        "bill.relatedDocs.[].relatedDoc": "date docType formats lang showAs uri",
        "bill.relatedDocs.[].relatedDoc.formats": "pdf xml",
        "bill.relatedDocs.[].relatedDoc.formats.pdf": "uri",
        "bill.relatedDocs.[].relatedDoc.formats.xml": "uri",
        "bill.sponsors.[]": "sponsor",
        "bill.sponsors.[].sponsor": "as by isPrimary",
        "bill.sponsors.[].sponsor.as": "showAs uri",
        "bill.sponsors.[].sponsor.by": "showAs uri",
        "bill.stages.[]": "event",
        "bill.stages.[].event": "chamber dates house progressStage showAs stageCompleted stageOutcome stageURI uri",
        "bill.stages.[].event.chamber": "chamberCode showAs uri",
        "bill.stages.[].event.dates.[]": "date",
        "bill.stages.[].event.house": "chamberCode chamberType houseCode houseNo showAs uri",
        "bill.versions.[]": "version",
        "bill.versions.[].version": "date docType formats lang showAs uri",
        "bill.versions.[].version.formats": "pdf xml",
        "bill.versions.[].version.formats.pdf": "uri",
        "bill.versions.[].version.formats.xml": "uri",
        "billSort": "actNoSort actShortTitleEnSort actShortTitleGaSort actYearSort billNoSort billShortTitleEnSort billShortTitleGaSort billYearSort",
    }),
}


@dataclass(frozen=True)
class SourceEvidencePointer:
    """A locator into a byte-preserved raw JSON page."""

    path: str
    sha256: str
    json_pointer: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256,
                "json_pointer": self.json_pointer}


@dataclass(frozen=True)
class DriftFinding:
    endpoint: str
    json_pointer: str
    change: str
    severity: str
    run_id: str
    source_evidence: SourceEvidencePointer
    record_index: int | None = None
    expected: tuple[str, ...] = ()
    observed: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "endpoint": self.endpoint,
            "json_pointer": self.json_pointer,
            "change": self.change,
            "severity": self.severity,
            "run_id": self.run_id,
            "source_evidence": self.source_evidence.as_dict(),
        }
        if self.record_index is not None:
            result["record_index"] = self.record_index
        if self.expected:
            result["expected"] = list(self.expected)
        if self.observed is not None:
            result["observed"] = self.observed
        return result


@dataclass(frozen=True)
class SourceContractReport:
    endpoint: str
    run_id: str
    findings: tuple[DriftFinding, ...]

    @property
    def warnings(self) -> tuple[DriftFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")

    @property
    def record_failures(self) -> tuple[DriftFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "record")

    @property
    def source_failures(self) -> tuple[DriftFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "source")

    @property
    def failed_record_indices(self) -> tuple[int, ...]:
        return tuple(sorted({item.record_index for item in self.record_failures
                             if item.record_index is not None}))

    @property
    def source_failed(self) -> bool:
        return bool(self.source_failures)

    @property
    def clean(self) -> bool:
        return not self.record_failures and not self.source_failures

    def as_dict(self) -> dict[str, Any]:
        return {"endpoint": self.endpoint, "run_id": self.run_id,
                "findings": [item.as_dict() for item in self.findings],
                "source_failed": self.source_failed,
                "failed_record_indices": list(self.failed_record_indices)}


def _json_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _join(pointer: str, token: str) -> str:
    return pointer + "/" + _escape(token)


def _validate_evidence(value: object) -> SourceEvidencePointer:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "json_pointer"}:
        raise ValueError("source evidence pointer must contain path, sha256 and json_pointer")
    path, digest, pointer = value["path"], value["sha256"], value["json_pointer"]
    if (not isinstance(path, str) or not path or path.startswith("/")
            or ".." in path.split("/") or "\\" in path
            or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
            or not isinstance(pointer, str)
            or (pointer and not pointer.startswith("/"))
            or re.search(r"~(?![01])", pointer)):
        raise ValueError("invalid immutable source evidence pointer")
    return SourceEvidencePointer(path, digest, pointer)


def classify_source_contract(endpoint: str, records: object, *, run_id: str,
                              source_evidence: Mapping[str, object] | Sequence[Mapping[str, object]]) -> SourceContractReport:
    """Classify consumed-field drift for one endpoint record set.

    ``source_evidence`` is either a pointer to the array containing ``records``
    (its ``json_pointer`` is extended by each record index), or one pointer per
    record pointing directly at that record. Evidence/hash mismatches are input
    integrity errors and raise ``ValueError`` rather than generating unverifiable
    findings. No source data is mutated.
    """
    if endpoint not in _CONTRACTS:
        raise ValueError(f"unsupported source-contract endpoint: {endpoint!r}")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("source-contract run_id must be a non-empty string")
    anchor: SourceEvidencePointer | None = None
    record_pointers: tuple[SourceEvidencePointer, ...] | None = None
    if isinstance(source_evidence, Mapping):
        anchor = _validate_evidence(source_evidence)
    elif isinstance(source_evidence, Sequence) and not isinstance(source_evidence, (str, bytes)):
        record_pointers = tuple(_validate_evidence(item) for item in source_evidence)
    else:
        raise ValueError("source evidence must be a page pointer or per-record pointer sequence")

    findings: list[DriftFinding] = []

    def add(pointer: str, change: str, severity: str, evidence: SourceEvidencePointer,
            index: int | None, expected: tuple[str, ...] = (), observed: str | None = None) -> None:
        full_pointer = evidence.json_pointer + pointer
        exact_evidence = SourceEvidencePointer(evidence.path, evidence.sha256, full_pointer)
        findings.append(DriftFinding(endpoint, full_pointer, change, severity,
                                     run_id, exact_evidence, index, expected, observed))

    if not isinstance(records, list):
        evidence = anchor or (record_pointers[0] if record_pointers else None)
        if evidence is None:
            raise ValueError("source-level drift requires an immutable source evidence pointer")
        add("", "invalid_source_container", "source", evidence, None,
            ("array",), _json_kind(records))
        return SourceContractReport(endpoint, run_id, tuple(findings))
    if record_pointers is not None and len(record_pointers) != len(records):
        raise ValueError("per-record source evidence count must match records")

    spec = _CONTRACTS[endpoint]
    known_shapes = _KNOWN_SHAPES[endpoint]

    def validate(value: object, node: _Spec, pointer: str, evidence: SourceEvidencePointer,
                 index: int) -> None:
        if value is None and node.nullable:
            return
        kind = _json_kind(value)
        if kind not in node.kinds:
            add(pointer, "type_changed", "record", evidence, index,
                tuple(node.kinds) + (("null",) if node.nullable else ()), kind)
            return
        if node.choices is not None and value not in node.choices:
            add(pointer, "incompatible_value", "record", evidence, index,
                tuple(sorted(map(str, node.choices))), _json_kind(value))
            return
        if node.fields is not None and isinstance(value, dict):
            for name, child in node.fields.items():
                child_pointer = _join(pointer, name)
                if name not in value:
                    if child.required:
                        add(child_pointer, "missing_required_field", "record", evidence,
                            index, tuple(child.kinds), "missing")
                else:
                    validate(value[name], child, child_pointer, evidence, index)
            if (endpoint == "legislation" and pointer.startswith("/bill/versions/")
                    and pointer.endswith("/version") and value.get("docType") == "bill"):
                # These values are consumed only for Bill versions; Act versions
                # are deliberately ownership-deferred and may omit them.
                for name in ("uri", "date", "lang", "showAs", "formats"):
                    if name not in value:
                        add(_join(pointer, name), "missing_required_field", "record",
                            evidence, index, ("object" if name == "formats" else "string",),
                            "missing")
        if node.item is not None and isinstance(value, list):
            if len(value) < node.min_items:
                add(pointer, "incompatible_value", "record", evidence, index,
                    (f"array with at least {node.min_items} item(s)",), f"array with {len(value)}")
            for item_index, item in enumerate(value):
                item_pointer = _join(pointer, str(item_index))
                validate(item, node.item, item_pointer, evidence, index)

    def scan_unknown(value: object, pointer: str, evidence: SourceEvidencePointer,
                     index: int, shape_path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            allowed = known_shapes.get(shape_path, frozenset())
            for key in sorted(value):
                field_pointer = _join(pointer, str(key))
                if key not in allowed:
                    add(field_pointer, "unknown_property", "warning", evidence, index,
                        (), _json_kind(value[key]))
                else:
                    scan_unknown(value[key], field_pointer, evidence, index,
                                 shape_path + (str(key),))
        elif isinstance(value, list):
            for item_index, item in enumerate(value):
                item_pointer = _join(pointer, str(item_index))
                scan_unknown(item, item_pointer, evidence, index, shape_path + ("[]",))

    for index, record in enumerate(records):
        if record_pointers is None:
            assert anchor is not None
            record_pointer = _join(anchor.json_pointer, str(index))
            evidence = SourceEvidencePointer(anchor.path, anchor.sha256, record_pointer)
        else:
            evidence = record_pointers[index]
        if not isinstance(record, dict):
            add("", "invalid_record_type", "record", evidence, index,
                ("object",), _json_kind(record))
            continue
        record_spec = spec
        if endpoint == "houses":
            house = record.get("house")
            if isinstance(house, dict) and house.get("houseCode") == "dail & seanad":
                record_spec = _EXCLUDED_HOUSE_RECORD
        validate(record, record_spec, "", evidence, index)
        scan_unknown(record, "", evidence, index)

    findings.sort(key=lambda item: (item.record_index if item.record_index is not None else -1,
                                    item.json_pointer, item.change, item.severity))
    return SourceContractReport(endpoint, run_id, tuple(findings))


def classify_source_envelope(
        endpoint: str, envelope: object, *, run_id: str,
        source_evidence: Mapping[str, object], count_field: str | None = None,
        expected_count: int | None = None,
        observed_record_count: int | None = None,
        allow_array: bool = False) -> SourceContractReport:
    """Classify consumed API page-envelope shape/count drift.

    Findings are source failures and point into the immutable raw page. Only
    consumed envelope fields are checked; values are reported by JSON type or
    a fixed description, never copied from source data into a report.
    """
    if endpoint not in _CONTRACTS:
        raise ValueError(f"unsupported source-contract endpoint: {endpoint!r}")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("source-contract run_id must be a non-empty string")
    evidence = _validate_evidence(source_evidence)
    if count_field is not None and (not isinstance(count_field, str) or not count_field):
        raise ValueError("source envelope count field must be non-empty when provided")
    if expected_count is not None and (type(expected_count) is not int or expected_count < 0):
        raise ValueError("expected envelope count must be a non-negative integer")
    if observed_record_count is not None and (
            type(observed_record_count) is not int or observed_record_count < 0):
        raise ValueError("observed record count must be a non-negative integer")

    findings: list[DriftFinding] = []

    def add(pointer: str, change: str, expected: tuple[str, ...], observed: str) -> None:
        full_pointer = evidence.json_pointer + pointer
        exact = SourceEvidencePointer(evidence.path, evidence.sha256, full_pointer)
        findings.append(DriftFinding(
            endpoint, full_pointer, change, "source", run_id, exact, None,
            expected, observed))

    root_is_object = isinstance(envelope, dict)
    if isinstance(envelope, list) and allow_array:
        result_rows = envelope
    elif not root_is_object:
        add("", "invalid_source_container", ("object", "array"), _json_kind(envelope))
        result_rows = None
    elif "results" not in envelope:
        add("/results", "missing_required_field", ("array",), "missing")
        result_rows = None
    elif not isinstance(envelope["results"], list):
        add("/results", "type_changed", ("array",), _json_kind(envelope["results"]))
        result_rows = None
    else:
        result_rows = envelope["results"]

    actual_count: int | None = None
    if count_field is not None and root_is_object:
        head = envelope.get("head")
        if head is None and "head" not in envelope:
            add("/head", "missing_required_field", ("object",), "missing")
        elif not isinstance(head, dict):
            add("/head", "type_changed", ("object",), _json_kind(head))
        else:
            counts = head.get("counts")
            if counts is None and "counts" not in head:
                add("/head/counts", "missing_required_field", ("object",), "missing")
            elif not isinstance(counts, dict):
                add("/head/counts", "type_changed", ("object",), _json_kind(counts))
            elif count_field not in counts:
                add(f"/head/counts/{_escape(count_field)}",
                    "missing_required_field", ("nonnegative integer",), "missing")
            else:
                value = counts[count_field]
                if type(value) is not int or value < 0:
                    observed = "negative integer" if type(value) is int else _json_kind(value)
                    add(f"/head/counts/{_escape(count_field)}", "type_changed",
                        ("nonnegative integer",), observed)
                else:
                    actual_count = value
                    if expected_count is not None and value != expected_count:
                        add(f"/head/counts/{_escape(count_field)}",
                            "advertised_count_changed", ("stable count across pages",),
                            "different integer")
                    if (observed_record_count is not None
                            and value != observed_record_count):
                        add(f"/head/counts/{_escape(count_field)}",
                            "advertised_count_mismatch",
                            ("count matching observed unique records",),
                            "different integer")

    if (observed_record_count is not None and actual_count is None
            and result_rows is not None and count_field is None
            and len(result_rows) != observed_record_count):
        # Retain this general branch for containers whose source contract
        # advertises a count through a separately supplied endpoint rule.
        add("/results", "result_count_mismatch",
            ("count matching observed records",), "different count")

    findings.sort(key=lambda item: (item.json_pointer, item.change, item.severity))
    return SourceContractReport(endpoint, run_id, tuple(findings))


__all__ = ["DriftFinding", "SourceContractReport", "SourceEvidencePointer",
           "classify_source_contract", "classify_source_envelope"]
