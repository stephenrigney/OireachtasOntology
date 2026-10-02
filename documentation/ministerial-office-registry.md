# Ministerial office and unit registry bootstrap

Phase 7 Tranche 1 introduces the ontology vocabulary and the deterministic
registry-to-reference-graph path. It does **not** resolve Member office
observations, publish OfficeHoldings, change Member RDF/SHACL, or reconcile
external office identities.

## Registry and graphs

`registries/ministerial-office-registry.json` is a versioned, reviewed local
registry. Its version-1 shape is:

```json
{
  "version": 1,
  "administrative_units": [
    {
      "key": "u-000001",
      "label_en": "Reviewed unit label",
      "label_ga": "Optional Irish label",
      "aliases": [{"language": "en", "label": "Reviewed alias"}],
      "reviewer_notes": "Why this local enduring unit identity is supported.",
      "evidence": ["https://example.invalid/reviewed-source"]
    }
  ],
  "offices": [
    {
      "key": "o-000001",
      "label_en": "Reviewed office label",
      "aliases": [],
      "office_type": "MinisterOfficeType",
      "unit_relationships": [
        {"relationship": "headsAdministrativeUnit", "unit_key": "u-000001"}
      ],
      "reviewer_notes": "Why this enduring office identity and unit relationship are supported.",
      "evidence": ["https://example.invalid/reviewed-source"]
    }
  ]
}
```

`label_ga` is optional. Aliases are language-tagged (`en` or `ga`). For
Tranche 2 candidate generation an alias may also contain the optional reviewed
scope fields `source_uris`, `contexts`, `validity` (`start` and optional `end`),
and `unit_keys`; see
`documentation/office-observation-reconciliation.md`. These fields constrain
candidate evidence only and are not emitted as RDF or interpreted as office
establishment/abolition assertions. Office
types are the registered `members:OfficeType` concepts. Only
`MinisterOfficeType` may assert `headsAdministrativeUnit`, and only
`MinisterOfStateOfficeType` may assert `assignedToAdministrativeUnit`; these
are distinct relationships. References must target a unit key in this
registry. Office keys use `o-NNNNNN` and unit keys use `u-NNNNNN`; they are
allocated locally and are never derived from labels, functions, holders, source
identifiers, or external identifiers. Every
populated entry requires reviewer notes and at least one evidence reference.

The complete validated unit registry is the sole owner of
`https://data.oireachtas.ie/graph/administrative-units`; the complete office
registry is the sole owner of `https://data.oireachtas.ie/graph/offices`.
`oir-etl run administrative-units` publishes the unit graph first.
`oir-etl run offices` refuses online publication unless the current validated
unit payload is already clean in state, then replaces only the office graph.
Both commands accept `--registry-file`, `--offline`, `--output-ttl` and
`--output-nq`. Online publication requires configured Fuseki GSP and SPARQL
endpoints, persists publication state before graph replacement, and verifies
the exact whole graph after PUT. Registry graphs do not contain Member
holdings, external identity links or Bill-local links.

## Bootstrap coverage limitation

The registry is intentionally initialized with no named offices or
administrative units. The repository's Member fixture contains two
Minister-of-State observations with null source office URIs. Their labels each
name more than one Department, and the fixture alone does not establish which
local enduring office identities or unit identities those observations
represent. The label wording cannot be used to split appointments or mint
identities under the approved contract. There is therefore no positive reviewed
identity evidence in the current fixture from which to bootstrap a local office
or unit. Both reference graphs are valid empty graphs until reviewed evidence
supports specific entries.

This is a coverage limitation, not a transformation failure. The four primary
Cabinet office-type concepts and the Ceann Comhairle, Cathaoirleach and
Attorney General office-type concepts exist in the ontology, but no particular
NamedOffice instance is inferred from a category. The active Member office
mapping and Member transformer remain unchanged until the approved later
Member-migration tranche.

The deterministic ETL policy table is explicitly versioned as
`OFFICE_TYPE_POLICY_VERSION = 1`: Taoiseach, Tánaiste and Minister office types
qualify for Cabinet episodes, while Minister of State does not. Other office
types remain unclassified rather than receiving a category by similarity. The
table is established here for the later Cabinet tranche; Tranche 1 emits no
CabinetMembership RDF.
