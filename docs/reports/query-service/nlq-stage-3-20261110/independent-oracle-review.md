# Independent oracle review

Read-only review by a separate agent context, session
`ses_e38751ad8ffeX6JHPmQZ3tEki9`, at the requested source revision.
The reviewer was instructed not to inspect responses or adjust expected answers.
No new experiment, source change or network request was performed by the reviewer.

## Findings returned

**Observed—review:** no demonstrated wrong expected identity or numeric answer.
The oracle uses independent handwritten selections, not application-generated
SPARQL. Correct owner graphs and exact identity joins are used. Current versus
historical overlap, the four-way office-anchored intersection, active Member
count/list semantics, unsupported unqualified sponsorship count and unavailable
Published-year count agree with the reviewed contracts.

Three limitations constrain interpretation:

1. **Sponsorship role/primary-status adjudication is unavailable.** The independent
   query uses `eli-dl:participation_role`; emitted role text uses `rdfs:label`,
   and the query omits `agents:isPrimarySponsor`. Thus 20/40 Bill identity-set
   agreement does not establish primary/supporting/unknown or role preservation.
   Sources: `poc/specs/query-schema-contract.json:392–397`;
   `src/oireachtas_etl/transforms/bills.py:667–690`.
2. **Complete fail-closed selection is not independently certified.** Mandatory
   English titles can omit Bills without that display field; mandatory Member
   names can omit unlabelled holding evidence. DateRange typing, conflicting
   intervals and datatypes are not comprehensively checked by the independent
   evaluator, which reduces dates to their first ten characters. No resulting
   error was demonstrated in the captured midnight-dated rows, but these are
   limits on total-selection/safety certification. Sources: scratch `oracle.py`,
   `tests/test_nlq_composable_q23.py:335–346`,
   `poc/nlq/office_representation.py:71–85`,
   `poc/nlq/composable_plan.py:5103–5137`.
3. **Seat-question construct validity is bounded.** A1/A3 use the approved
   seats interpretation of “members were in”, not distinct people; 174/160 are
   correct under that contract, but equivalence with explicit-seat A2 is an
   intended-operation comparison rather than a universal linguistic claim.
   Sources: `poc/specs/composable-query-plan-contract.json:130`;
   `tests/test_nlq_stage_c.py:126–143`.

## Stage 3 disposition of review

Expected answers and frozen evidence are unchanged. No requests were added.
Role/primary-status scoring and complete fail-closed source-selection
certification are **stopped/indeterminate**, not silently credited as passes.
Machine `assessments.json` checks are limited to their explicitly named
properties (e.g. exact observed Bill identity/title sets). Broad labels such as
`correct_and_repeatable_in_selected_three_runs` must be read with these
qualifications; they are not whole-projection or completeness certifications.
The report carries these limitations into its exit assessment.
