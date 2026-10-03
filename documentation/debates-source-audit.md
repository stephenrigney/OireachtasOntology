# Phase 7 Debates — representative source audit

This records source evidence for the approved [Phase 7 design](phase-7-debates.md),
not a transformation or production-corpus census. Three full official AKN
responses were added byte-for-byte; the two existing Dáil examples were left
untouched. Audit retrieval date: 2026-10-02. Transcript text remains source-only
under the approved RDF boundary. The ontology-gap descriptions below are
explicitly the historical, pre-approval baseline; the approved I1/I2/O1–O8
contract and current implementation status are recorded in the
[semantic review](debates-semantic-review.md).

## Representative source inventory

The AKN namespace in all five files is
`http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13`. All parse as
`akomaNtoso/debate` with `meta/identification` and `debateBody`.

| Local fixture | Official AKN URL | Observed structure |
|---|---|---|
| `dail_2015-07-02.akn.xml` (existing) | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul@/main.xml` | 54 sections; 10 `<question>`; 1,020 `<speech>`; 8 analysis `<voting>`; `debate`, `questions`, `question`, `division`, `ta`, `nil`. Older in-repository source snapshot. |
| `dail_2026-02-26.akn.xml` (existing) | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-02-25/debate/mul@/main.xml` | 54 sections; 428 `<speech>`; 9 `<voting>` with `ta`/`nil`/`staon`; `topical`, `motion`, `statement`, `questions`. Its filename date differs from its record date. |
| `seanad_2015-07-02.akn.xml` (added) | `https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate/mul@/main.xml` | 17 sections; 205 `<speech>`; 2 `<voting>`; `orderofBusiness`, `billReport`, `division`, `ta`, `nil`. One voting outcome is `#declared`. |
| `committee_public_accounts_2026-09-24.akn.xml` (added) | `https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate/mul@/main.xml` | 3 sections; 929 `<speech>`; one `<rollCall>` containing a table with 11 referenced people; `statement`. |
| `dail_written_answers_2015-07-02.akn.xml` (added) | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens/mul@/main.xml` | 217 sections: 20 `writtenAnswers` groups and 197 `writtenAnswer` sections; 229 `<question>` and 197 `<speech>`; no `<answer>` element. |

All new fixtures are full `main.xml` source documents, not edited excerpts.
The checked-in byte counts and SHA-256 hashes are:

| Local fixture | Bytes | SHA-256 |
|---|---:|---|
| `dail_2015-07-02.akn.xml` | 927,249 | `0ca15d12a7154c460f7459090b2838f25f5a63ef85017a2cce474ddc5f1731c6` |
| `dail_2026-02-26.akn.xml` | 964,819 | `1e6762bae013b22c37a4167f630530189bbf8f7057214b0676e699d97ed946ad` |
| `seanad_2015-07-02.akn.xml` | 230,459 | `6e2920af4b97aa0f692162f9fcd94324a18a1c26495399e8600a5ca450d762c0` |
| `committee_public_accounts_2026-09-24.akn.xml` | 408,509 | `690dada15afa1cb76ece7dd8387b973b00b43804023521b9ffb821d8944ff60e` |
| `dail_written_answers_2015-07-02.akn.xml` | 1,075,045 | `0d0a1d49c67772a073cf762017efc56f3e8cab93a47629091b8e10c3fc2c4cab` |

## Corpus census and resource gate

As of the audit date, calendar-year queries to the Open Data API
`/v1/debates` (`date_start`/`date_end`, `limit=1000`) returned 26,468 debate
records for observed record dates 1919-01-21 through 2026-10-01:

| API house grouping | Records |
|---|---:|
| Dáil | 8,918 |
| Seanad | 5,180 |
| Committees | 12,370 |
| **Total** | **26,468** |

The broad API query reports a capped count, so the census sums the per-calendar-
year result counts. Every enumerated item had `debateType="debate"`. This is
not the complete intended corpus census: `/v1/debates` does not count the
separate `writtens` AKN documents. On 2015-07-02, `/v1/questions` returns 239
questions (10 oral in the Dáil debate file and 229 written in the separate
`writtens` file), illustrating that boundary.

The Phase 7 full-corpus-versus-Bill-debates production gate is **insufficiently
measured**: the API census excludes written-answer XML, and record counts do not
establish total XML volume, runtime or RDF output. This gate does **not** block
Tranche 1 semantic/source-contract work or Tranche 2 representative
transformation. After the core transformer exists and before broad production
ingestion, enumerate all in-scope AKN main documents (including `writtens`) and
measure primary XML bytes, elapsed runtime, RDF output and working/storage needs
on representative records. Compare the measured costs with deployment budgets
to choose full-corpus or Bill-debates-first production ingestion. Do not infer a
scope decision from record counts or set an arbitrary cutoff; no production
scope has been selected by this source audit.

## Historical ontology baseline reviewed before semantic approval

This section records the ontology/mapping baseline and open questions at the
2026-10-02 audit, before I1/I2/O1–O8 were approved. These are historical
findings, not claims about the current approved vocabulary or mapping. The
approved contract and implementation-verification status are in the
[semantic review](debates-semantic-review.md).

At audit time, `ontology/debates.owl.ttl` already defined the principal
`DebateRecord`, `DebateExpression`, `DebateSitting`, `DebateSection`, `Speech`,
`Summary`, `ParliamentaryQuestion`, and `Division` classes. It provided some
section, speech, summary and division containment; question/speaker shortcuts;
division counts/outcome/vote links; and ELI-DL activity/vote terms. This was
candidate coverage evidence, not approval to emit every source relationship.

| AKN paths / observed variants | Historical baseline coverage | Audit-time gap or ambiguity; current disposition |
|---|---|---|
| `meta/identification/{FRBRWork,FRBRExpression,FRBRManifestation}`; `FRBRname` absent in the older Dáil sample, `debate` in current debate samples, `writtens` in written answers. Work paths include `/debate/` or `/writtens/`; the older Dáil snapshot lacks that segment. Expression paths use both `eng@` and `mul@` while inspected `FRBRlanguage` values say `eng`. | At audit time, record/expression/sitting classes and source identity evidence existed. | The baseline lacked explicit Work/Expression links and a language-code property. **O2 now approves** `:hasExpression`, `:expressionHasSection` and `:expressionLanguageCode`; the exact IRI policy is approved under I1. Never infer language from URI spelling. |
| `debateBody/debateSection[@name]`, recursively nested; observed names include `prelude`, `debate`, `questions`, `question`, `topical`, `motion`, `statement`, `orderofBusiness`, `billReport`, `division`, `ta`, `nil`, `staon`, `writtenAnswers`, and `writtenAnswer`. XML sibling order is present. | The baseline covered some section/contribution containment; transcript prose was out of scope. | The baseline lacked a source ordinal and approved host links. **O1/O4 now define** `:sourceOrdinal`, `:recordOfBody` and `:recordOfHouseTerm`; their ontology/mapping contract checks pass. Runtime ordinal assignment and owner resolution remain transformation work. |
| `<speech by="…" as="…">`, `<from>`, and `recordedTime`; committee speeches and a committee roll call are present. | The baseline had `Speech`, resolved-Member `:speaker`, and recorded-time metadata. | The ELI-DL `Activity` domain made `eli-dl:had_participation` unsafe on Speech. **O5 now approves** local `:hasSpeechParticipation`; unresolved person/role references remain non-RDF evidence. |
| `<question by="…" to="…">`; written answers group `<question>` and `<speech>` inside `writtenAnswer` sections. No `<answer>` element occurs in these samples. | The baseline had `ParliamentaryQuestion` and `:askedBy`. | **O3 now approves** immediate `:hasQuestion` containment and clarifies that written response `<speech>` is not a one-to-one answer link. `:directedTo` still requires an existing resolved role; O6 approves a separate conditional office link. |
| `meta/analysis/parliamentary/voting` with `count/@refersTo` values `#ta`, `#nil` and (in 2026) `#staon`; body `division` subsections can carry individual `person` votes. Seanad 2015 includes `voting/@outcome="#declared"` and `voting/@refersTo="#sum_7"`. | The baseline had Division/count/outcome/vote terms. | **O7 keeps `#declared` source-only for outcome purposes** (no carried/lost inference) and keeps `voting/@refersTo` inactive under the initial boundary. The current 2015 Staon evidence supersedes the old temporal annotation; the approved annotation now says “when supplied.” |
| Committee `<rollCall><summary/><table>`; table `person/@refersTo` entries identify those present. | No roll-call attendance model existed in the baseline. | **O8 approves source-only attendance** in the initial RDF scope. Do not infer speech participation, Division or votes; a future attendance RDF model needs separate approval. |

The current official 2015 Dáil response (distinct from the older checked-in
snapshot) also has `#staon` aggregate counts without a corresponding Staon
member subsection. This contradicted the historical ontology annotation that
Staon counts appeared from 2026 onward; the approved annotation now says “when
supplied.” A count is not evidence for a complete individual voter list; the
aggregate and voter membership remain distinct source assertions.

These findings preserve source evidence and explain the historical review
baseline; they do not define current ontology gaps or claim a Debates
transformation. Current approval and verification status belongs to the semantic
review. This source audit itself does not alter ontology or mapping semantics,
RDF ownership, source identifiers, or publication behavior.

## Existing repository samples versus current official bytes

The following comparisons were fetched from the current official AKN URLs above
on 2026-10-02. Existing repository samples were deliberately not replaced:

| Existing sample | Repository snapshot | Current official response | Observed difference |
|---|---|---|---|
| `dail_2015-07-02.akn.xml` | 927,249 bytes; SHA-256 `0ca15d12a7154c460f7459090b2838f25f5a63ef85017a2cce474ddc5f1731c6` | 905,547 bytes; SHA-256 `720bf72e40ed824c9d01efc8a919713e524e6b058794e75fab56c20b6858fff5` | Not byte-identical: repository has 1,020 speeches versus 1,006 current; both have 54 sections, 10 questions and 8 votes. Repository FRBR paths use the older no-`/debate/`, `eng@` form and publication date 2015-12-07; current source has `debate` FRBR name and publication date 2025-07-09. |
| `dail_2026-02-26.akn.xml` | 964,819 bytes; SHA-256 `1e6762bae013b22c37a4167f630530189bbf8f7057214b0676e699d97ed946ad` | 966,774 bytes; SHA-256 `42fd5d635d217e23abf6a97e4ed7342eb1111bbc565a4c7450d896173d161371` | Not byte-identical: repository has 54 sections versus 53 current; both have 428 speeches and 9 votes. Repository filename says 2026-02-26 while FRBR record date is 2026-02-25; publication dates are 2026-02-27 versus 2026-08-12. |

The byte and observed structural differences are recorded as audit evidence only;
this tranche intentionally leaves those existing fixtures unchanged.
