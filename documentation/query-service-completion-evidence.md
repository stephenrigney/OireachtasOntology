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

### Memorandum queryability review

Independent review confirmed that exposing the already-emitted document chain
is a narrow Query Service contract extension permitted by the campaign, not a
mapping/ontology/ownership change. Authority is `bill_mapping.csv` rows 74–80,
the existing Bill transformer, pinned ELI 1.5 and Bill ETL chain tests:

`Bill → eli:has_part → Work → eli:is_realized_by → LegalExpression → eli:is_embodied_by → Format → eli:uri_schema → rendition`.

The existing safety allowlist lacks exactly the first three connector
predicates; `eli:uri_schema` already passes the active-mapping safety gate.
All four need compiler queryability metadata, and `eli:Format` needs the
compiler class gate. Extension must be finite, deliberately versioned, checked
against the reviewed emitted pattern and contained in the resolved Bill's own
graph. Do not add mapping rows, ontology declarations, general ELI allowlisting,
graph families or live document retrieval. Preserve every read-only safeguard.

Tests must distinguish an absent Bill graph, a loaded Bill with no recorded
memo, an unavailable query mapping, and available memo renditions. Failure to
query the document chain must never be reported as absence of a memorandum.
Final implementation/version evidence belongs in the recovery report.

Compatibility review found a stale README sentence requiring major bumps for
every capability extension, while its consumer-major number is also obsolete.
The accepted ancestor `a2009a5` is the exact finite-connector precedent: it
added `skos:altLabel`/`org:heldBy` to the same contract-owned allowlist with
contract and safety **minor** bumps. `9e8b019` used a major bump for a breaking
semantic cutover; Q23 (`ae26f53`) used a minor for additive queryability.
Orchestration verified that `a2009a5` is an ancestor of campaign baseline.
Follow the accepted additive discipline for the finite memorandum extension,
record the versions, and correct the ordinary implementation README rather
than silently retaining contradictory compatibility guidance. Rejected query
features, enforced limits, federation and all existing semantic meanings remain
unchanged. A breaking meaning/identity/ownership or safety-boundary change is
not authorised by this reconciliation.

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

## Stage B implementation recovery

- The accepted finite Bill document chain is now enabled as query contract
  `2.7.0` and local-safety `1.1.0`; the composable plan contract is `2.6.0`.
  Exactly `eli:has_part`, `eli:is_realized_by`, and `eli:is_embodied_by` were
  added as unconditional safety predicates; all four chain predicates including
  already-mapped `eli:uri_schema` are queryable, and `eli:Format` is the only
  added queryable class. Limits, read-only operations, rejected features,
  ownership, and graph identity are unchanged. Bill document retrieval is
  bounded to the resolved Bill's own graph.
- Q24A uses the exact captured `2025/23` title, status URI, official Bill IRI,
  and Committee Stage date recorded above. Its empty `relatedDocs` means no
  memorandum is recorded in this Bill graph, not that none exists elsewhere.
  A synthetic in-memory Bill graph separately exercises a present memorandum
  rendition through all four connectors. No corpus rebuild or protected source
  fixture was used.
- Q25 and Q27 reuse the accepted Q35 Member-owned OfficeHolding interval path.
  Q25 is an inclusive September window and filters the exact Member; Q27 uses
  the requested single calendar date. Their execution fixtures are synthetic;
  the source-backed accepted holding citations remain the reviewed 2026-10-02
  records cited above, not a current office census.
- Q12 now runs the shared Committee-owner/date catalogue first and returns the
  dated current Committee identity (or explicit ambiguity/date-coverage
  diagnostic); the missing chair relationship remains a precise Query Service
  capability gap. Q14 reports the development source conflict/quarantine and
  does not promote reviewed ID-115 owner evidence to a current roster. Q26
  reports the incomplete 22-holding current-office coverage boundary.
- Q18/Q19/Q20/Q21/Q22 have finite title/year plan families and read-only Bill
  queries. After B2 correction (`c4c1e08`), Q19 selects any mapped, typed Published
  lifecycle event with an `xsd:date` in the requested calendar year, even when
  the latest activity is another stage. The reviewed activity/process pattern
  exposes existing `eli-dl:forms_part_of` evidence; legislativeYear is display
  metadata, never the publication-year selector. Q20 preserves missing/conflicting status diagnostics. Q22 preserves
  primary-status unknowns and role-only Participation rows, with Member labels
  joined only on exact RDF identity.

On B2 checkpoint `c4c1e08`, the orchestrator reran `tests/validate.py` and
`python -m tools.validation` using `.venv/bin/python`: both passed (2,584
ontology triples; active mapping integrity). Office exact-identity integration
remains a separate B3 unit; office descriptions above are not B3 acceptance.

Independent Bill review of `c4c1e08` found two acceptance blockers in Q21/Q22:
required process/participation joins remove title-matching Bills with missing
facts, causing misleading lookup failure and potentially hiding a second
candidate. Title identity must be retained independently of fact availability.
Executable asymmetric-candidate and single-missing-fact regressions are required
before Stage B exit. Q18/Q19/Q20/Q24A had no P1 findings. These review findings
supersede any earlier broad statement of B2 acceptance for Q21/Q22; corrections
and exact tested checkpoint belong in the progress record.

## Independent Stage A acceptance review

Read-only independent review at `c4c1e08` confirmed all six earlier P1 findings
were corrected and regression-pinned: historical open-end handling, distinct
counts and cap discipline, reviewed owners/joins, owner-first current committee
resolution, closed typed plans, and family diagnostics. No Stage A blockers
remain. Q10 nomination data remains specifically unavailable, not inferred.
The review's T01 debugger observation had already been corrected in `870aefc`;
its remaining wording/defensive-edge observations are non-blocking. The
orchestrator's 202-test Stage A and 231-test post-B2 runs remain the executable
integration evidence; review itself did not run tests.

## Initial semantic verification

On baseline `844e51b`, `.venv/bin/python tests/validate.py` passed ontology
consistency (2,584 triples), and `.venv/bin/python -m tools.validation` passed
active mapping integrity. Campaign integration verification is recorded in
`documentation/query-service-completion-progress.md`.

While the Stage A writer was active, independent unchanged semantic-contract
checks also passed:

- `.venv/bin/python -m pytest -q tests/test_ontology_validation.py tests/test_mapping_integrity.py tests/test_debates_ontology_contract.py tests/test_debates_mapping_contract.py` — **24 passed**.
- `.venv/bin/python -m pytest -q tests/test_houses_etl.py tests/test_reference_etl.py tests/test_members_etl.py tests/test_bills_etl.py` — **379 passed**.

These checks protect reviewed input/transform semantics; they do not replace
post-integration Query Service regression and final full-suite verification.
