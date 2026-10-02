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

## Initial reviewed bootstrap and coverage limit

Tranche 1 and Tranche 2 are implemented. The intentionally small initial
registry contains these locally reviewed identities:

| Key | Identity | Identity evidence |
|---|---|---|
| `u-000001` | Department of Finance | Section 1(ii) of the [Ministers and Secretaries Act 1924](https://www.irishstatutebook.ie/eli/1924/act/16/section/1/enacted/en/html) specifies the named Department and its head; the [current revised consolidation](https://revisedacts.lawreform.ie/eli/1924/act/16/revised/en/html) retains the provision. |
| `o-000001` | Taoiseach (`TaoiseachOfficeType`) | The [Constitution](https://www.irishstatutebook.ie/eli/cons/en/html), in force from 29 December 1937, defines appointment of the Taoiseach and the Government's composition (Articles 13 and 28). |
| `o-000002` | Tánaiste (`TanaisteOfficeType`) | Constitution Article 28.6.1 defines the distinct office of Tánaiste. |
| `o-000003` | Minister for Finance (`MinisterOfficeType`) | Ministers and Secretaries Act 1924 section 1(ii) names the Department's head as Minister for Finance; the current revised text preserves that named office and Department. |

The Minister for Finance office's `headsAdministrativeUnit` relationship to
`u-000001` follows that same explicit statutory provision. The reviewed aliases
are limited by validity dates in the registry: constitutional titles from
29 December 1937, and the Minister for Finance source label only from the first
accepted bootstrap observation on 27 June 2020. These are candidate-matching
limits, not RDF establishment/abolition dates or claims about earlier
historical observations.

Three exact observations from the official Members API are accepted by explicit
review decisions: Micheál Martin as Taoiseach (Dáil 34, from 2025-01-23), Mary
Harney as Tánaiste (Dáil 29, 2002-06-06–2006-09-13), and Paschal Donohoe as
Minister for Finance (Dáil 33, 2020-06-27–2022-12-17). The decisions record
response hashes, JSON pointers, fingerprints and primary legal evidence in
`reconciliation/office-decisions.json`.

The repository's Member fixture still contains two explicit unresolved
Minister-of-State observations with null source office URIs. Each label names
two Departments; the fixture does not positively establish local unit identity,
department-level Minister-of-State office identity, or (for the later wording)
Department continuity. The observations are not split and no Minister-of-State
office or unit is minted from their labels or dates. This is a deliberate
coverage limit, not a transformation failure.

The primary Cabinet office-type concepts and the Ceann Comhairle,
Cathaoirleach and Attorney General office-type concepts exist in the ontology,
but no instance is inferred from a category. The active Member office mapping
and Member transformer remain unchanged until Tranche 3.

The deterministic ETL policy table is explicitly versioned as
`OFFICE_TYPE_POLICY_VERSION = 1`: Taoiseach, Tánaiste and Minister office types
qualify for Cabinet episodes, while Minister of State does not. Other office
types remain unclassified rather than receiving a category by similarity. The
table is established here for the later Cabinet tranche; Tranche 1 emits no
CabinetMembership RDF.
