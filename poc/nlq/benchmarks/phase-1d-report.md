# Phase 1D — Local Member-name ambiguity handling

## Outcome and boundaries

The shared browser/benchmark pipeline now checks exact local Member
`foaf:name` labels before translation. Matching is whole-label,
case-insensitive after NFC normalization, and accent-preserving. It treats each
actual local Member IRI as a separate candidate, uses local HouseTerm and
constituency/panel labels as possible disambiguating context, and returns a
first-class clarification outcome when two or more candidates remain. That
outcome stops before LLM translation and answer-query execution. No Member
resources are merged and no same-person assertion or external identity lookup
is made.

Partial-name/set-valued requests such as “Which Martin served in the Dáil?” and
explicitly plural Member requests continue through the ordinary direct
LLM-to-SPARQL path; the number of answer rows does not trigger ambiguity.

Contextual narrowing has one important limit: when a local HouseTerm or
constituency/panel label leaves one candidate, the pipeline continues, but it
does not inject that candidate IRI into or otherwise constrain the generated
answer SPARQL. The answer query must still implement the context correctly. The
context test supplies the corresponding term filter in its deterministic
translation fixture; this verifies the expected query path, not mechanical
binding. Inspect generated SPARQL for such answers. Stronger binding would need
a separately designed and tested query-rewriting/binding mechanism and is not
claimed by this phase.

## Benchmark changes and measured evidence

Benchmark v0.3.0 is preserved alongside v0.1.0 and v0.2.0. It adds automated
`ambiguity_handling` cases for Michael Collins and Cathy Honan, while keeping
the broad Martin case under manual review as a supported, potentially
set-valued question. The Martin coverage probe verifies at least two matching
Dáil Member records, including Micheál Martin and Martin Heydon; it does not
assert the complete answer set.

- Benchmark: `benchmark-v3.json`, SHA-256
  `b5936a129ee206a7b9a22963bb7d2064d28363d584dcd866a0863b68156c939f`.
- Deterministic regression run `36828be1-9365-4986-a86a-fd4f17b8e02b`:
  **10 passed, 0 failed**.
- Measured run `2070abdd-651e-43b1-8de4-e06e5c41358c`, created
  `2026-10-07T17:10:53Z`: **42 cases, 34 passed, 0 failed, 8 not scored**
  (5 manual-review cases and 3 source-data-coverage outcomes). The three
  `ambiguous_names` cases comprise **2 passed ambiguity outcomes and 1 manual
  review**.
- Both exact-name cases returned three distinct capture-backed local Member
  IRIs, with no translation, answer SPARQL, or selected candidate. Michael
  Collins records have 1st–3rd, 28th–29th, and 32nd–34th Dáil context; Cathy
  Honan records have 11th–12th, 16th, and 20th Seanad context. These are
  separate records, not evidence that the records denote either the same or
  different people.
- The Martin case proceeded to a set-valued query and returned 26 Member rows;
  its exact interpretation and completeness remain manually reviewed.
- Run artifact SHA-256:
  `a3ace51c22d40ab73e7619618e82cfa0a9e165f1721a1938b1bdfa04d464767c`.
  Dataset ID: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`.
  The run used disposable `stain/jena-fuseki:5.1.0` with loopback binding,
  automatic container removal, and no persistent volume. The capture-backed
  dataset is explicitly non-authoritative.

The measured-run JSON does not record resolved LLM settings. The benchmark
runner loads repository `.env` (without overriding process environment) and
defaults to model `gpt-6-luna` and endpoint
`https://opencode.ai/inference/openai/v1`. The checked `.env` specifies that
model and no base-URL override; however, because the run artifact omits resolved
configuration, a one-off process-environment override at invocation cannot be
ruled out retrospectively. The two automated ambiguity cases themselves use a
translator that fails if called, so their outcomes do not depend on LLM
sampling.

## Verification

- Focused NLQ tests: **114 passed**.
- Full repository suite (under `mise` for the pinned Java runtime): **770
  passed, 14 skipped**.
- Ontology validation: **passed**, 2,504 triples; HermiT completed.
- `git diff --check`: run after the report was added.

The phase changes only the NLQ POC, its benchmark/schema/documentation, and
tests. Ontology and mapping semantics, RDF ownership, identity reconciliation,
query safety acceptance, and benchmark history were not changed.
