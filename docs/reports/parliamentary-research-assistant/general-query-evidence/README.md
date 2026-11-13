# General Query Service integration — execution evidence

These are configured-model/read-only Fuseki observations, **not human product
acceptance**. `tools/verify_research_general_queries.py` reproduces the bounded
checks without changing the dataset. The requested model and reporting date are
recorded in each archive. Dataset snapshot, source completeness and freshness are
not certified.

- `underlying-a.json`, `underlying-d.json`: preflight checks of the established
  party-history and current-party-membership capabilities against actual data.
- `a-party-history.*`, `b-r1.*`, `c-career.*`, `d-party-members.*`,
  `e-unsupported.*`: the five requested validation cases. JSON contains original
  brief, plans, subsidiary questions, all research model inputs/outputs, service
  planner proposals, admitted plans, structured outcomes and every actual read.
  Markdown retains reports, assertion classifications and source evidence.
- `a-paraphrase.*`: natural paraphrase, not an exact-string replay.
- `d-party-members-additional-evidence.*`: same-session follow-up needing new
  supported evidence, preserving the earlier selection.
- `b-r1-revision.*`: same-session editorial revision and selective evidence reuse.
- `instructions.json`: shared research instructions and Query Service-derived
  discovery/planner context used by the real runs.
- `final-d/`: fresh independent capability and follow-up observations after the
  reusable exact-fact table correction, with their own full instructions. The
  original top-level D archives are retained: they accepted real Member evidence
  but rejected every report proposal because the model tried to use a
  constituency-only table for party-membership facts. No table/evidence guard
  was relaxed. The generic `facts` table displays exact accepted wording for any
  established proposition; it adds no party-specific field mapping or tool.
- `checks/`: deterministic suite, ontology/reasoner and browser-control logs.
- `injected-browser/`: **injected-model/exact compiler-response replay** browser
  controls, separately labelled; not real-model research observations.

`interrupted-trial/a-party-history.*` is the **earlier unsuccessful trial**. It
repeated technical paraphrases which the existing service refused, then the
shell's 120-second timeout interrupted the campaign. It is not counted as a
successful factual investigation. The generic research instruction was corrected
to prefer ordinary questions, retain original tense/conditions and not repeatedly
paraphrase refusals. The final campaign used an unlimited shell timeout but the
application's bounded research loop. No per-question exception or compiler change
was introduced.

The initial underlying-A capture exposes an existing positional `QueryResult`
debug-string value in its non-ASK Boolean field. Final normalisation retains a
Boolean only for ASK responses; SELECT evidence remains its columns and rows.
Neither that diagnostic field nor a successful response authorises a research
fact. Party history has no `accepted_evidence` payload in this compiler revision;
its real result is retained **without factual promotion**. This is an integration
limitation, not missing party records or proof of historical absence.
