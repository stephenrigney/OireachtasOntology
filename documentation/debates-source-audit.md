# Phase 7 Debates — source audit (proposal-only partial tranche)

This records source evidence for the approved [Phase 7 design](phase-7-debates.md),
not a transformation or final mapping contract. Three full official AKN responses
were added byte-for-byte; the two existing Dáil examples were left untouched.
Audit retrieval date: 2026-10-02. Transcript text remains source-only under the
approved RDF boundary.

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

The Phase 7 full-corpus-versus-Bill-debates gate is **insufficiently measured**;
record counts alone cannot establish storage or processing cost, and the written
answer source family is outside the count above. Do not infer a scope decision
or an arbitrary cutoff from this census. The smallest useful next measurement is
to enumerate all in-scope AKN main documents (including `writtens`) and sum
their primary immutable-source bytes, then record bytes actually written for
source preservation and derived/temporary processing on a representative full
record. Measure the processing multiplier against primary input bytes (with
peak working storage and elapsed time) before comparing the extrapolated totals
with deployment budgets. No numeric threshold or Bill-only decision is proposed
here.

## AKN structure, intended RDF coverage, and open questions

The baseline in `ontology/debates.owl.ttl` already defines the principal
`DebateRecord`, `DebateExpression`, `DebateSitting`, `DebateSection`, `Speech`,
`Summary`, `ParliamentaryQuestion`, and `Division` classes. It provides section,
speech, summary and division containment; question/speaker shortcuts; division
counts/outcome/vote links; and ELI-DL activity/vote terms. This is evidence of
candidate coverage, not approval to emit every source relationship.

| AKN paths / observed variants | Intended existing coverage | Ambiguity requiring review |
|---|---|---|
| `meta/identification/{FRBRWork,FRBRExpression,FRBRManifestation}`; `FRBRname` absent in the older Dáil sample, `debate` in current debate samples, `writtens` in written answers. Work paths include `/debate/` or `/writtens/`; the older Dáil snapshot lacks that segment. Expression paths use both `eng@` and `mul@` while inspected `FRBRlanguage` values say `eng`. | Record/expression/sitting resources and source identity. Preserve AKN IDs and source bytes; do not treat expression path spelling as a language assertion. | The ontology has no explicit expression-to-record link or language term. Stable public IRI normalization and source identity remain subject to the Phase 7 contract; do not infer language from `mul@`/`eng@`. |
| `debateBody/debateSection[@name]`, recursively nested; observed names include `prelude`, `debate`, `questions`, `question`, `topical`, `motion`, `statement`, `orderofBusiness`, `billReport`, `division`, `ta`, `nil`, `staon`, `writtenAnswers`, and `writtenAnswer`. XML sibling order is present. | `DebateSection`, `:hasSection`, `:hasSubSection`, `:hasSpeech`, `:hasSummary`, `:hasDivision`; transcript prose is excluded from RDF. | RDF is unordered and the ontology has no source ordinal. Phase 7 design calls for a lightweight source ordinal, but its ontology representation needs semantic approval. Host House/committee links also need review; the outline's `:inHouse` suggestion conflicts with its declared `BillEvent` domain, and a committee is not an enduring House. |
| `<speech by="…" as="…">`, `<from>`, and `recordedTime`; committee speeches and a committee roll call are present. | `Speech`, the `:speaker` shortcut for a resolved Member, and recorded-time metadata; canonical participation is intended to use ELI-DL. | `:speaker` cannot represent witnesses. The `eli-dl:had_participation` domain is `Activity`, despite the ontology comment suggesting it on `Speech`; do not assert it without semantic review. A `TLCRole`/label does not itself establish a `ParticipationRole`. |
| `<question by="…" to="…">`; written answers group `<question>` and `<speech>` inside `writtenAnswer` sections. No `<answer>` element occurs in these samples. | `ParliamentaryQuestion`, `:askedBy`, `:directedTo`; source remains available for replay. | The ontology has no question-to-section or explicit question-to-answer link. A written response encoded as `<speech>` is not necessarily an oral `Speech`; `:directedTo` expects `eli-dl:ParticipationRole`, not a `TLCRole` merely because the labels match. |
| `meta/analysis/parliamentary/voting` with `count/@refersTo` values `#ta`, `#nil` and (in 2026) `#staon`; body `division` subsections can carry individual `person` votes. Seanad 2015 includes `voting/@outcome="#declared"` and `voting/@refersTo="#sum_7"`. | `Division`, its count/outcome terms, and recorded Member vote properties are present in the ontology. | **`#declared` is a semantic review gap:** current named outcomes cover `#carried`/`#lost`, not `#declared`. Also, the observed summary target does not match the outline's proposed `DebateSection`/`BillEvent` target for `:refersToProposal`. Do not coerce either source reference. |
| Committee `<rollCall><summary/><table>`; table `person/@refersTo` entries identify those present. | No explicit attendance/roll-call class or relation is defined in the existing Debates ontology. | **`rollCall` is a semantic review gap:** attendance must not be inferred as speech participation or a vote. Decide whether and how presence is represented before mapping it. |

The current official 2015 Dáil response (distinct from the older checked-in
snapshot) also has `#staon` aggregate counts without a corresponding Staon
member subsection. This contradicts the ontology annotation that Staon counts
appear from 2026 onward. A count is not evidence for a complete individual
voter list; map the supplied aggregate independently of voter membership after
the source join is validated.

These findings preserve the approved phase boundary: no ontology or mapping
semantics, RDF ownership, source identifiers, or publication behavior are changed
by this partial source audit.

## Existing repository samples versus current official bytes

The following comparisons were fetched from the current official AKN URLs above
on 2026-10-02. Existing repository samples were deliberately not replaced:

| Existing sample | Repository snapshot | Current official response | Observed difference |
|---|---|---|---|
| `dail_2015-07-02.akn.xml` | 927,249 bytes; SHA-256 `0ca15d12a7154c460f7459090b2838f25f5a63ef85017a2cce474ddc5f1731c6` | 905,547 bytes; SHA-256 `720bf72e40ed824c9d01efc8a919713e524e6b058794e75fab56c20b6858fff5` | Not byte-identical: repository has 1,020 speeches versus 1,006 current; both have 54 sections, 10 questions and 8 votes. Repository FRBR paths use the older no-`/debate/`, `eng@` form and publication date 2015-12-07; current source has `debate` FRBR name and publication date 2025-07-09. |
| `dail_2026-02-26.akn.xml` | 964,819 bytes; SHA-256 `1e6762bae013b22c37a4167f630530189bbf8f7057214b0676e699d97ed946ad` | 966,774 bytes; SHA-256 `42fd5d635d217e23abf6a97e4ed7342eb1111bbc565a4c7450d896173d161371` | Not byte-identical: repository has 54 sections versus 53 current; both have 428 speeches and 9 votes. Repository filename says 2026-02-26 while FRBR record date is 2026-02-25; publication dates are 2026-02-27 versus 2026-08-12. |

The byte and observed structural differences are recorded as audit evidence only;
this tranche intentionally leaves those existing fixtures unchanged.
