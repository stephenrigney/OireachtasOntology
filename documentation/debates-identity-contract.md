# Phase 7 Debates — Tranche 1 identity, order and reference contract

**Status: approved identity/source contract; Tranches 1–2 complete.** The
ontology/mapping additions, static checks and representative RDF transformation
are verified. This document records the approved identity, graph, ordering and
reference-evidence rules; it does not claim that acquisition, general owner
resolution or publication is implemented.
The governing boundaries are in [Phase 7](phase-7-debates.md), especially its
identifier, order, cross-resource, and graph-ownership sections.

## 1. URI component encoding

For each source string to be placed in one URI path component, first use the
XML-parsed attribute value (entity references have already been expanded),
encode that exact Unicode string as UTF-8, and percent-encode every byte except
the RFC 3986 unreserved ASCII bytes `A-Z`, `a-z`, `0-9`, `-`, `.`, `_`, and
`~`. Write escapes with uppercase hexadecimal digits. This is ordinary
component encoding, not form encoding: a space is `%20`, never `+`.

Do not trim, collapse whitespace, lowercase, Unicode-normalize, or unescape an
existing `%HH` sequence. Thus a literal
percent sign is `%25`; source text `%2F` becomes `%252F`, while a literal slash
becomes `%2F`. The value `.` or `..` is safe in the identifier path because the
eId route below prefixes its encoded component with `e-` (so neither is a URI
dot-segment).

| Literal XML fragment | Parsed `eId` value | Encoded eId suffix component |
|---|---|---|
| `<speech eId="p&amp;1"/>` | `p&1` | `e-p%261` |
| `<speech eId="rate%2F"/>` | `rate%2F` | `e-rate%252F` |
| `<speech eId="sec/2"/>` | `sec/2` | `e-sec%2F2` |
| `<speech eId="q?1"/>` | `q?1` | `e-q%3F1` |
| `<speech eId="mark#1"/>` | `mark#1` | `e-mark%231` |
| `<speech eId="dáil"/>` | `dáil` | `e-d%C3%A1il` |
| `<speech eId="  p  "/>` | `  p  ` | `e-%20%20p%20%20` |

The XML example is source syntax; in particular `&amp;` is decoded by the XML
parser before URI encoding. Whitespace is not a delimiter: the two leading
and two trailing spaces in the last example are identity-bearing. An absent
or empty `eId` takes the fallback path in §3; a non-empty whitespace value is
preserved as written, not silently treated as absent.

## 2. Work, expression, resource, and graph identity

The approved source identity for each FRBR level is the exact XML-parsed
`@value` of that level's single `FRBRuri` element:

* Work key: `FRBRWork/FRBRuri/@value`.
* Expression key: `FRBRExpression/FRBRuri/@value`.

These two keys are validated and encoded independently. An Expression path is
not required to be a child of its Work path; the explicit `:hasExpression` link
and Work-keyed graph establish their relationship. This clarifies the approved
no-truncation identity rule and does not authorize guessing either path.

`FRBRuri` identifies the whole document at its FRBR level. Do not substitute
`FRBRthis` (which can identify a component), infer one level by truncating the
other, infer language or version from a suffix, or use file names, dates,
record order, or eIds as a root-identity fallback. Within one source XML
document, require exactly one non-empty `FRBRuri` at each required level;
missing, empty, or duplicate metadata fails closed. Preserve the source values
as evidence. A Work URI shared by separate expression inputs is expected and
does not itself constitute a duplicate Work identity.

Require a relative `/akn/ie/debateRecord/...` URI path, or an absolute URI
with the same path and the exact origin `https://data.oireachtas.ie`. Reject
userinfo, query, fragment, empty/dot path segments, malformed percent escapes,
and any different origin or path root. Retain the exact source spelling as
evidence. Split the path at literal slashes and apply §1 to each segment, so
ordinary AKN path hierarchy is preserved and raw `&`, spaces, literal `%`,
and other awkward segment characters are safely encoded. An existing `%HH`
sequence is treated as source spelling (its `%` becomes `%25`), not decoded
into a slash or a different identity. If two records canonicalize to the same
work/expression identity with conflicting source evidence, fail closed.

```text
work IRI       = https://data.oireachtas.ie/{encode-each-FRBRWork-path-segment}
expression IRI = https://data.oireachtas.ie/{encode-each-FRBRExpression-path-segment}
eId resource   = {expression IRI}/eid/e-{encode-component(eId value)}
fallback       = {container IRI}/fallback/fb-{lowercase SHA-256}
```

For the canonical example source values below, the expected public identifiers
are:

| Level | Exact `FRBRuri/@value` | Candidate local IRI |
|---|---|---|
| Work | `/akn/ie/debateRecord/dail/2015-07-02/debate` | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate` |
| Expression | `/akn/ie/debateRecord/dail/2015-07-02/debate/mul@` | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul%40` |

The approved replaceable graph URI is keyed by the Work FRBR URI, not an
expression URI or any component eId. Replace the `/akn/ie/debateRecord` prefix
of the once-encoded Work IRI path with `/graph/debate`; retain the already
encoded suffix exactly as-is and do not encode any segment a second time:

```text
graph URI = https://data.oireachtas.ie/graph/debate/{encoded Work path after /akn/ie/debateRecord/}
```

For the Work example above, this is
`https://data.oireachtas.ie/graph/debate/dail/2015-07-02/debate`.
The sitting has no source eId in the audited records. Its approved IRI is
`{work IRI}#sitting` (for the example,
`https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate#sitting`).
The fragment does not encode source position, language, or an invented
ministerial/legislative identity.

This preserves Phase 7's one-authoritative-graph-per-record boundary; it does
not authorize one graph per expression or per section. A second expression for
the same Work therefore has a distinct expression IRI but the same graph key.
The approved initial policy is to fail closed for a Work when more than one of
its Expressions is known: retain each exact input and report the condition, but
do not publish or replace that Work's graph from one Expression in isolation.
A single fetched file does not prove that the Work has only one Expression
globally; `/v1/debates` is not a complete Expression manifest. Do not merge
partial expression inputs, select one arbitrarily, or create per-Expression
graphs. Any later complete-bundle policy requires separate review and an
authoritative discovery/completeness contract. If evidence contradicts the
one-Work-to-one-record graph boundary, stop for graph-boundary review rather
than widening or narrowing graph ownership.

Create a `DebateSitting` at `{work IRI}#sitting` only when `FRBRname/@value` is
absent or exactly `debate`, the Work does not identify `/writtens`, and those
source-type signals do not conflict. Use `eli-dl:activity_date` from the Work
date and `:producedRecord` to the Work. For `FRBRname="writtens"`, emit the
separate `DebateRecord` and date but no sitting: publication of written answers
does not evidence another activity. A conflicting or unreviewed source type
fails closed for sitting emission and is reported; matching House/date alone
is not evidence of a sitting.

## 3. eId uniqueness and missing-ID fallback

Within one source expression, index every non-empty `eId` after XML parsing and
before assigning any RDF resource IRI. An eId is case-sensitive and
expression-scoped. The same decoded eId on two XML elements is a duplicate even
if one element is not mapped to RDF, the XML spellings use different entity
references, or the elements have different classes. A duplicate is a hard
contract error: do not disambiguate it by class, suffix, source position, or
fallback hash. The source expression's eId index would otherwise be ambiguous.

An addressable RDF resource with a missing or empty eId may use this approved
fallback, provided its XML subtree and containing-resource context are
available:

1. Choose the nearest containing addressable resource's canonical IRI as
   `container IRI`; use the expression IRI when there is no such ancestor.
2. Obtain the node's expanded XML QName (`{namespace-URI}local-name`) and its
   subtree serialized by W3C XML Canonicalization 2.0, without comments and
   without stripping text whitespace. Use the canonicalized subtree bytes as
   UTF-8.
3. Form the exact digest input below and use lowercase SHA-256 hex in the
   fallback route from §2:

   ```text
   b"akn-eid-fallback-v1\0"
   + UTF8(container IRI) + b"\0"
   + UTF8(expanded QName) + b"\0"
   + UTF8(C14N 2.0 subtree)
   ```

   XML 1.0 content, expanded QNames, and valid IRIs cannot contain the NUL
   separator used here. The full-document source hash, sibling index, source
   ordinal, traversal order, and byte offset are deliberately not inputs, so
   inserting or reordering unrelated siblings does not change this fallback.

Before emitting a resource, check all proposed resource IRIs for uniqueness.
If two missing-ID nodes in the same container produce the same fallback IRI
(including identical canonical subtrees), fail closed for that expression;
do not salt the hash with position or invent a numeric suffix. A changed
subtree or containing-resource identity may produce a changed fallback IRI;
this is an acknowledged limitation of the fallback, not a promise of identity
across arbitrary content edits. Explicit eId and fallback route namespaces
remain separate.

The following is a regression vector for the fallback formula, not a claim
that production code exists:

```text
container IRI: https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul%40
expanded QName: {urn:akn:test}speech
source subtree: <speech xmlns="urn:akn:test"><p>Vote &amp; return</p></speech>
C14N 2.0:      <speech xmlns="urn:akn:test"><p>Vote &amp; return</p></speech>
SHA-256:       646242b40e1062e09f7d3cfbcb6d5506ecb032b190ec264e23f52940ad9749a2
fallback IRI:  https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul%40/fallback/fb-646242b40e1062e09f7d3cfbcb6d5506ecb032b190ec264e23f52940ad9749a2
```

## 4. Source order (approved contract; static ontology/mapping checks verified)

AKN child order remains authoritative. For each containing XML resource
independently, assign each immediate addressable RDF child a **positive,
consecutive, 1-based source ordinal among all immediate addressable siblings**,
in original XML child order. Count mixed addressable resource kinds in one
sequence. Addressable children include DebateSection (including division and
ta/nil/staon groups), Speech, Summary and ParliamentaryQuestion. Skip
non-addressable elements, text and comments; do not count descendants while
processing their parent. A nested container starts its own sequence at 1. The
ordinal is ordering metadata only and is never an identifier, fallback input,
or tie-breaker.

Example: for immediate children `section`, non-addressable `heading`, `speech`,
`summary`, `section`, the addressable ordinals are respectively `1`, `2`, `3`,
and `4`. A nested section's own addressable children begin again at `1`.

The approved property is `:sourceOrdinal` with `xsd:integer` range and no class
domain or key implication. Its ontology declaration and active mapping row pass
the static ontology/mapping checks. Runtime ordinal assignment and transformed-
RDF ordering validation belong to Tranche 2; do not use
`eli-dl:activity_order` as a substitute.

## 5. Reference outcomes and source-hash sidecar

Resolve a source reference only under the field's reviewed source-reference
rules and against an existing resource owned by that dataset. Preserve the
XML-parsed source reference value and the reference's source context; do not
guess from labels, invent placeholder entities, or add descriptive triples
for cross-dataset resources. Apply the attribute-specific parsing, resolution
and predicate conditions in the approved
[`debates-semantic-review.md`](debates-semantic-review.md) and mapping contract;
the generic outcome mechanics here do not authorize an otherwise inactive link.

For each reviewed source reference slot, keep one deterministic non-RDF
reference-outcome row in the existing transform-report/raw-source state
pattern, serialized as UTF-8 JSON with sorted keys and stable row sorting by
source expression, source node, attribute QName and raw value. Do not create a
second reconciliation or publication framework. A run report records the
resolver/source version so a later resolution run can be compared with the
same immutable AKN input. Each row carries at least:

* `contract_version` = `debates-reference-outcomes-v1`;
* `source_sha256` = lowercase SHA-256 of the exact immutable original XML
  bytes, before parsing or reserialization;
* work and expression IRIs, source node IRI, source attribute QName, and the
  XML-parsed `raw_reference` value (null when the optional field is absent); and
* exactly one `status` from the four-value vocabulary below, plus the
  resolution evidence/candidate IRI list needed for that outcome.

| Status | Meaning | Target evidence |
|---|---|---|
| `resolved` | The reviewed rule finds exactly one existing owned resource. | One `target_iri`; emit only the approved link to it. |
| `unresolved` | A syntactically usable present reference has no unique authoritative target (including ambiguous candidates or source placeholders such as `speech/@by="#"`). | No target IRI; retain raw value, reason and sorted candidates if any. |
| `malformed` | A syntactically present value fails the reviewed field grammar; a required empty value is an error with its exact evidence. | No target; retain raw value and reason. |
| `absent` | A reviewed optional source attribute is not present. | Null raw value; no link and not an unresolved error. |

Optional absent references create explicit `absent` outcome rows for the
reviewed slots, distinguishing omission from failed resolution. Every row is associated
with the exact raw document by `source_sha256`; a reserialized XML copy is not
the hash input. The sidecar is audit evidence, not RDF, not a named graph, and
not a change to graph ownership or the atomic graph-replacement boundary. An
unresolved/malformed/absent outcome never creates a speculative RDF entity or
link. Resolution may change as endpoint data changes while the source hash
stays the same; a sidecar consumer must therefore treat each recorded outcome
as the result of the accompanying resolution run, not as immutable source
content.
Missing *required* fields are source-validation errors, not an optional
`absent` outcome that permits publication.
For example, `speech/@by="#"` is a syntactically present source placeholder:
report `unresolved` with reason `source-placeholder`, not `absent` or a
fabricated Member. `#sum_29` used as a local element reference must be checked
against the exact eId index for that attribute; `#lost` used as a controlled
vote outcome is handled by that field's vocabulary mapping, not by a generic
`lstrip('#')` rule. A present bad fragment such as `#?` is `malformed` only
when the reviewed grammar rejects it; an unknown but valid reference is
`unresolved`. Multiple eligible targets are also `unresolved`, with sorted
candidate evidence and an ambiguity reason.

Source-hash vector: the exact six source bytes `b"<akn/>"` have SHA-256
`47ba3135b27455c5e29750e62d1085a143596d93e0b16a20af1dbfd74287d7ee`; appending
one newline changes the hash. The XML parser's canonical output is never the
input to `source_sha256`.

## 6. Regression scope and explicit non-implementation

`tests/test_debates_identity_contract.py` checks the examples, formulae and
fail-closed cases specified here using test-local reference calculations. Some
tests read immutable AKN fixtures to verify source evidence and the reference
ordering rule. The tests do not import a Debates transformer or assert
transformed RDF, and do not claim runtime extraction, URI generation, ordering,
reference resolution or graph publication is implemented. The companion static
source/mapping/ontology contract checks likewise do not execute a transform or
prove RDF non-emission.

The approved ontology/mapping additions, source-integrity checks, focused
Debates tests and repository validation have passed. This verifies the static
contract, not a transformer. Runtime identity/order/reference behavior and
actual RDF output remain Tranche 2 work; the Tranche 1 exit is confirmed.
