# Query Service completion — targeted local evidence

Evidence inspected read-only on 2026-10-28. This note is not a dataset rebuild,
publication acceptance, or completeness assertion. The approved question
catalogue remains unchanged.

## Bill 2025/23 (Q24A)

- Selected capture: `7bab00fc-4637-463e-a42e-fdb7ce626439` from
  `poc/nlq/benchmarks/development-api-capture-selection.json`.
- Preserved page:
  `/var/home/stephen/Projects/OireachtasOntology/data/raw/legislation/2026-10-13/run-7bab00fc-4637-463e-a42e-fdb7ce626439/skip-000100.json`.
- Record: `/results/57/bill`.
- Independently computed page SHA-256, matching adjacent metadata:
  `24dff7eaa325d649f82fb3f9b36b12c98d81aab844048cd24546f94919011ec2`.
  Metadata identifies the selected run, HTTP 200, skip 100 and limit 100.
- Bill: `https://data.oireachtas.ie/ie/oireachtas/bill/2025/23`.
- English title: **Pregnancy Loss (Miscellaneous Provisions) Bill 2025**.
- Source status text: `Current`; status URI ends `/bill-status/published`
  (the approved Bill mapping maps that URI to `CurrentBill`).
- Initiated PDF:
  `https://data.oireachtas.ie/ie/oireachtas/bill/2025/23/eng/initiated/b2325s.pdf`;
  version date 2025-05-20.
- `relatedDocs` is empty. No explanatory memorandum is known from this record;
  this does not prove no memorandum exists elsewhere.
- Dated stage/event evidence includes Committee Stage on 2025-07-09.

This verifies record availability in the preserved capture, not its presence
in an arbitrary running Fuseki dataset or current real-world legislative status.

## Seat complement (Q16)

The catalogue's data-readiness note says seats are not explicitly represented.
The approved desired meaning is nevertheless unambiguous: term seat complement,
never a count of people who served. Existing executable authority already
supports precisely that meaning:

- `mappings/houses_mapping.csv`: `[].house.seats` → `:seats`, datatype property,
  status `new`; notes explicitly give 33rd Dáil 160 and 34th Dáil 174.
- `src/oireachtas_etl/transforms/houses.py`: emits `OIR.seats` from the source
  `house.get("seats")`.
- `ontology/agents.owl.ttl` and `ontology/README.md`: term-specific integer seat
  complement.
- `tests/expected/houses.ttl`: 33rd Dáil `:seats 160`.
- `poc/specs/query-schema-contract.json`: already lists `agents:seats` among
  queryable properties.

Exposing this existing mapped fact needs no new ontology or source ownership
rule. The older catalogue readiness observation must not cause either a false
unavailable result or substitution of a Member count.

## Retained evidence boundaries

- Bill 2024/48: reviewed source stage identity ending `bill-stage/None`;
  no graph in the pinned development dataset. See `documentation/etl-plan.md`
  and `poc/nlq/benchmarks/development-data-evidence.md`.
- Good Friday committee: authoritative owner decision for the exact reviewed
  33rd-term ID-115 evidence does **not** change the development bootstrap's
  non-authoritative conflict/quarantine treatment, nor establish a current
  committee roster. See `documentation/etl-plan.md` reference-coverage section.
- Offices: pinned development bootstrap has 22 accepted holdings across three
  registered offices, not a complete current roster.
- PAC: one pinned Committee of Public Accounts debate (2026-09-24) does not
  prove substantive HSE examination or latest hearing through an as-of date.
- Bill-linked voting has no reviewed Query Service path. Debate speech text is
  deliberately outside the RDF and has no approved transcript retrieval path.

## Accepted office evidence (Q25–Q27)

These are committed review citations, inspected without scanning raw captures or
opening operational databases. They are not a fresh/current office census.

- Q25: `reconciliation/office-decisions.json` accepts Micheál Martin's
  Taoiseach observation, mapped to `https://data.oireachtas.ie/office/o-000001`,
  starting 2025-01-23 with no recorded end. Review cites the 2026-10-02 Members
  capture, skip 1100,
  `/results/98/member/memberships/8/membership/offices/0/office`, page SHA-256
  `aa591dff3ae205238f5a2731e9922f6ec08f42721f159795b073d9e55918b60c`.
  This supports locally evidenced overlap with September 2026 under the mapped
  open-ended interval convention, not proof of later/current roster completeness.
- Q27: the same review file accepts Paschal Donohoe's Finance observation,
  mapped to `https://data.oireachtas.ie/office/o-000003`, 2020-06-27 through
  2022-12-17. Review cites the 2026-10-02 Members capture, skip 500,
  `/results/71/member/memberships/3/membership/offices/0/office`, page SHA-256
  `4b9f8031c4200bf7bfcbd2b3868b663a29693f0edee37b50fe8e9ddefa7cfbaa`.
  This covers the requested 2021-07-01 date. A registry alias start is not an
  office-establishment date.
- Q26: no accepted Simon Harris Finance tenure is recorded in that review file.
  Registered office identity/aliases do not establish the current holder. The
  incomplete development holdings cannot certify the 2026-10-28 roster.

Office identities are independently described in
`registries/ministerial-office-registry.json`. Existing Q35 tests use synthetic
RDF and must not be presented as real-data current-office acceptance.

## Initial semantic verification

On baseline `844e51b`, `.venv/bin/python tests/validate.py` passed ontology
consistency (2,584 triples), and `.venv/bin/python -m tools.validation` passed
active mapping integrity. Campaign integration verification is recorded in
`documentation/query-service-completion-progress.md`.
