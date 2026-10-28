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

## Initial semantic verification

On baseline `844e51b`, `.venv/bin/python tests/validate.py` passed ontology
consistency (2,584 triples), and `.venv/bin/python -m tools.validation` passed
active mapping integrity. Campaign integration verification is recorded in
`documentation/query-service-completion-progress.md`.
