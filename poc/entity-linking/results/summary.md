# What the entity-linking experiment found

## Bottom line

This experiment shows that a transcript mention can add a useful *structured
join* for one reviewed Department of Finance reference. It does **not** show
that transcript linking is ready for broad use. The Member and Bill identity
snapshots each contain only one example, and the evaluation sample contains no
explicit mention of either supported target. Most tested entity links were
therefore abstentions or unsupported-name detections, not validated matches.

The experiment used 736 contributions from seven Oireachtas debate Works. The
Works were split before rule comparison: 276 development and 460 evaluation
contributions. Full downloaded transcripts and the review packet stayed outside
RDF and Git; no new transcript content was committed. Two pre-existing checked-in
AKN examples were reused unchanged. The checked-in reference file contains
mention spans and hashes, not full speeches. One AI reviewer produced provisional labels for 21 evaluation
contributions. There was no independent human review, so these numbers are not
a gold-standard accuracy result.

## What changed in retrieval

- **Members:** Neither exact name search nor either linker returned a mention
  of Timmy Dooley in the 460 evaluation contributions. The available Member
  owner snapshot contains one person only. This is missing coverage, not
  evidence that Member linking is ineffective.
- **Bills:** No contribution mentioned the one supported Bill, Finance Bill
  2025. A phrase search found ten contributions saying “the Bill”; both methods
  recorded 19 generic mention occurrences and abstained on all of them. No Bill
  was guessed from the debate topic.
- **Named offices:** A phrase search found 22 contributions mentioning
  “Taoiseach.” Exact matching returned all 22, but the contextual method
  returned one. In the small provisional review, six exact-method links were
  annotated as ambiguous office-versus-officeholder references; the contextual
  method did not resolve those reviewed instances. The one contextual result
  was not in the reviewed packet, so its correctness is unknown. The exact
  baseline was too willing to treat a title as the enduring office.
- **Administrative units:** Both methods found the one explicit Department of
  Finance mention in evaluation and joined it to the existing Minister for
  Finance office through the reviewed headship relationship. The provisional
  reviewer judged the one supported target correct. This is a useful graph
  join, but it is only one positive example. A full-text phrase search found
  the same contribution; the graph added the structured Department-to-office
  join, not a new speech beyond full-text retrieval.

Across the eight frozen questions, every structured-only query returned zero.
The entity graph returned no additional contribution beyond the equivalent
offline exact-phrase scan. It did expose existing identity relationships for
linked speech mentions. The offline scan is only a lexical comparator: no
Elasticsearch index or service was contacted, and no production search
performance was measured.

## Recommendation by category

| Category | Recommendation | Why |
|---|---|---|
| Members | **Modify** | No supported Member positive was observed; the one-person snapshot is far too small. Obtain reviewed identity coverage and a balanced human-reviewed sample before deciding on matching quality. |
| Bills | **Stop this bounded candidate-specific evaluation** | No Finance Bill 2025 positive was observed, and the attempted additional targeted source returned HTTP 403. Do not infer a Bill from “the Bill”; resume only with an accessible, reviewed identity/source sample. |
| NamedOffices | **Modify** | Exact title matching over-resolved officeholder references. The contextual rule was highly selective and needs human-reviewed office/holder evidence before expansion. |
| AdministrativeUnits | **Go to a larger human-reviewed evaluation only** | The one supported Department link and office join worked. Expand the reviewed unit registry and evaluate more positives/renamings; this is not authorization for production publication. |

No recommendation authorizes production RDF, Query Service integration,
corpus-wide processing, or Elasticsearch changes. All four categories need
human review before any such decision.

## Technical snapshot

In evaluation, the shared detector produced 573 mention decisions. Exact and
contextual methods behaved identically for Members (232 mentions, 171
out-of-registry and 61 generic abstentions) and Bills (43 mentions, 4
out-of-registry and 39 generic abstentions). For NamedOffices, exact matching
resolved 38 of 239 mentions; context resolved 1 and marked 37 ambiguous. For
AdministrativeUnits, both methods resolved 1 of 59 mentions, with 14
out-of-registry detections and 44 generic abstentions. The provisional
reviewer-supported resolution set had only one eligible target: Department of
Finance, resolved correctly by both methods. Members, Bills, and NamedOffices
had no supported target-resolution denominator in that review set.

The latest fresh-Fuseki run completed on CPU in about 35 seconds with 173 MiB
measured peak RSS for the linking process (the Fuseki container's RSS was not
included); earlier runs measured up to 1,030 MiB. All were below the 4 GiB
process limit, though peak memory varied across runs. It loaded 21 isolated
named graphs, including eight provisional graphs, with 69,554 triples total.
Source, decisions, derived graph hashes, and question-level SPARQL result sets
matched across four fresh disposable Fuseki runs, including one after the
uncertainty-scoring adjustment and the final reference-consistency guard. Full
details, denominators, hashes, and limitations are in
[`entity-linking-evaluation.md`](entity-linking-evaluation.md).
