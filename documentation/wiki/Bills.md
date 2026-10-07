# Bills and legislative processes

The model keeps the **Bill as a legal/intellectual work** distinct from the
**process through which it is considered** and from each activity or document
associated with that process. It reuses ELI and ELI-DL rather than defining a
parallel local Bill/Expression hierarchy.

## Work, process, activity and version

```text
eli-dl:DraftLegislationWork (the Bill)
  ├─ deterministic #process → eli-dl:LegislativeProcess
  │     ├─ process_type / process_status / was_submitted_by
  │     └─ latest_activity → a generated legislative activity
  ├─ expressions and versions (ELI / ELI-DL resources)
  └─ amendment-list and related document resources where supplied

eli-dl:LegislativeActivity ── happens in House / HouseTerm
                            └─ may have Participation (e.g. mover)
```

The process records Bill type, status, source and latest activity. Activities
represent stages, delivery and supported Bill events, with the relevant House
and term context. A source submitter is linked with
`eli-dl:was_submitted_by`; the Government bill-source concept is distinct from
the constitutional Government. Sponsor participation is retained separately
from the Bill work. A source role label alone is not enough to establish a
person, office or office holding.

The model includes document versions, amendment lists and links to related
legislative resources. The Bill graph does not become the owner of Member,
Act or Debate descriptions merely because a Bill refers to them. A resulting
Act may be referenced, but a separately owned Acts description is not part of
the Bill core model described here.

## Current implementation boundary

Per-Bill transformation and publication cover the mapped lifecycle model.
Separate, reviewed per-Bill local sponsor reconciliation may add a supported
link to a `NamedOffice` and, only with person/time evidence, an
`OfficeHolding`. This reconciliation preserves the original source
participation and label. See [ministerial offices](Departments.md) and the
[Bill-local sponsor reconciliation record](../bill-sponsor-reconciliation.md).

For exact classes and relationships, see [Bill classes](Bill-Classes.md),
[Bill properties](Bill-Properties.md), the
[legislation lifecycle record](../phase-4-legislative-lifecycle.md), and the
[ontology module guide](../../ontology/README.md). The
[current system overview](../current-state.md#data-coverage-and-limits)
distinguishes implementation from loaded-data coverage.

## Related topics

- [Concept schemes used by legislation](Concept-Schemes.md)
- [Agents and Bill submitters](Agents.md)
- [Debates and cross-references](Debates.md)
