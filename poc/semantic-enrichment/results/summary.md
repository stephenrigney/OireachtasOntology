# EuroVoc semantic-enrichment evaluation: summary

## Purpose

This experiment asked whether adding EuroVoc subject suggestions to debate
speeches could improve knowledge-graph search beyond exact label matching and
the existing debate, House and date structure. A shared subject vocabulary
might help connect speeches that use different wording, including across
periods. The evaluation tested one matcher and a bounded sample; it did not
test every possible use of EuroVoc.

## Approach

Two methods suggested EuroVoc concepts for the same frozen sample of 736
speeches from seven preserved debate sources:

- **Label matching baseline:** looks for exact whole-word matches to EuroVoc
  preferred or alternative labels in a speech.
- **Semantic matching:** compares speech text with EuroVoc labels using a
  language model, so it can suggest concepts even when the wording differs.

Suggestions from each method were stored in separate, disposable graphs. The
evaluation then queried those graphs alongside existing debate structure.
Queries could optionally follow EuroVoc's narrower-concept links, but only
where that behavior was explicitly requested. All suggestions remained
provisional; none became an accepted Oireachtas subject assignment.

## Results

**Measured:** On the 460-speech evaluation portion, the label baseline
suggested at least one concept for 270 speeches (58.7%). The semantic matcher
did so for all 460 (100%), usually returning its maximum of five suggestions.
Across seven frozen retrieval questions, semantic matching added results for
historical health policy and education. It returned the same two climate
change results as the baseline, and both methods returned no results for one
fisheries question.

The examples show both gains and regressions:

- For historical health policy, semantic matching returned two speeches where
  the baseline returned none. One returned speech was judged relevant in the
  provisional review.
- For fishing-industry activity, the baseline returned two speeches,
  including the only reviewed relevant example. Semantic matching returned
  none.
- For climate change, both methods returned the same two speeches. Their
  relevance was not independently reviewed, so this is matching output rather
  than confirmed useful retrieval.
- For cross-period public health, the baseline returned five speeches and the
  semantic method four, with no overlap. The provisional review judged one
  semantic result relevant, but found two relevant baseline results versus
  one semantic result among the small reviewed subset.
- For education, semantic matching returned eight speeches and the baseline
  none, but it missed the sole relevant contribution in the small provisional
  review for that question.

**Interpretation:** These results do not show consistent improvement. More
suggestions mean greater coverage, not necessarily more relevant results.
At the selected threshold, the semantic matcher never abstained and nearly
always filled its five-suggestion allowance. The evaluation therefore does
not establish that its broader coverage is useful or that its scores separate
good suggestions from poor ones.

## Limitations and practical implications

The blind provisional review covered 32 distinct speeches and 56
question/contribution judgments. It was produced by an agent, not human
reviewers or a gold-standard dataset; uncertain judgments were retained, and
most query results were not individually assessed. It cannot establish
corpus-wide accuracy or prove that either method is generally better.

The technical experiment was feasible on a local CPU: the full run took about
6 minutes 36 seconds, with peak classifier memory of 963 MiB, and loaded
108,023 triples into a disposable dataset. The measured inputs, model and
generated artifacts occupied about 696 MiB, including a roughly 497 MB
taxonomy and 201 MB model cache. Local query times were short, but this small
dataset is not a production performance benchmark. The vocabulary projection
used English labels, so Irish terminology and historical language variation
remain important limitations.

These findings do not show that EuroVoc itself is ineffective. They show that
this matcher, threshold and small evaluation did not demonstrate a reliable
retrieval benefit. EuroVoc remains a plausible source of shared concepts and
hierarchy; its value depends on appropriate classification and stronger
evidence of relevance.

## Conclusion

The current matcher should not enter production. The experiment did not
establish a consistent quality gain, and its near-maximum suggestion rate
provides no demonstrated useful abstention policy. Reconsideration would
require a larger, more representative evaluation with human-reviewed and
independently adjudicated relevance judgments, separate development and test
data, and evidence that retrieval improves over both label matching and
structured-only queries across periods and Houses. The [detailed technical
report](eurovoc-evaluation.md) documents the methods, results, resource
measurements and limitations.
