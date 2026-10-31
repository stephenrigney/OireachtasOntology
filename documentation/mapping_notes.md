# Mapping Notes — `data/houses.json`

Bill-specific mappings are maintained in `mappings/bill_mapping.csv` and the
[legislation contract](../docs/reference/etl/legislation.md). The approved Bill
classification correction uses DraftLegislationWork with Work-compatible
metadata; it does not change Houses mappings documented below.

Conversion notes for transforming the Oireachtas houses API response (`data/houses.json`) into RDF triples conforming to the Oireachtas ontology.

---

## Source

`data/houses.json` — retrieved from the Oireachtas API. Each element of the top-level array contains a single `house` object representing one parliamentary term (a `HouseTerm`).

---

## Field Mapping

| API field | OWL/RDF mapping | Notes |
|---|---|---|
| `house.uri` | IRI of the `HouseTerm` instance | Use as the subject IRI directly, e.g. `<https://data.oireachtas.ie/ie/oireachtas/house/dail/34>` |
| `house.showAs` | `skos:prefLabel` on the `HouseTerm` | Plain string, e.g. `"34th Dáil"@en` |
| `house.houseNo` | `:termNo` (`xsd:integer`) | Cast from string to integer (e.g. `"34"` → `34`) |
| `house.houseCode` | `:houseCode` (`xsd:string`) | Use as-is (e.g. `"dail"`, `"seanad"`) |
| `house.chamberCode` | **Discard** | Exact duplicate of `houseCode` in all records |
| `house.houseType` | **Discard** | Exact duplicate of `houseCode` in all records |
| `house.chamberType` | OWL class typing (see below) | Always `"house"` in this dataset; expressed by typing, not a string literal |
| `house.seats` | `:seats` (`xsd:integer`) | Seat count for this term specifically; term-specific (e.g. 33rd Dáil: 160, 34th Dáil: 174) |
| `house.dateRange.start` | `dcat:startDate` on a `dct:PeriodOfTime` node linked via `dct:temporal` | Cast `"YYYY-MM-DD"` string to `xsd:dateTime` (append `T00:00:00` if required by serialiser) |
| `house.dateRange.end` | `dcat:endDate` on the same `dct:PeriodOfTime` node | **Omit entirely** when the API value is `null` (current sitting term) |

---

## OWL Typing

Each `HouseTerm` instance should be given two OWL types:

| Condition | Types to assert |
|---|---|
| `houseCode = "dail"` | `agents:DailTerm`, `eli-dl:ParliamentaryTerm` |
| `houseCode = "seanad"` | `agents:SeanadTerm`, `eli-dl:ParliamentaryTerm` |

The `eli-dl:ParliamentaryTerm` co-typing is required so the instance can be referenced via `eli-dl:parliamentary_term` on `eli-dl:LegislativeActivity` and work instances.

---

## Temporal Date Range Pattern

Use the `dct:temporal` / `dct:PeriodOfTime` pattern, not direct datatype properties on the term:

```turtle
<https://data.oireachtas.ie/ie/oireachtas/house/dail/34>
    a agents:DailTerm, eli-dl:ParliamentaryTerm ;
    skos:prefLabel "34th Dáil"@en ;
    :termNo 34 ;
    :houseCode "dail" ;
    :seats 174 ;
    dct:temporal [
        a dct:PeriodOfTime ;
        dcat:startDate "2024-11-29T00:00:00"^^xsd:dateTime
    ] .
```

For a term that has ended, include `dcat:endDate`:

```turtle
<https://data.oireachtas.ie/ie/oireachtas/house/dail/33>
    a agents:DailTerm, eli-dl:ParliamentaryTerm ;
    skos:prefLabel "33rd Dáil"@en ;
    :termNo 33 ;
    :houseCode "dail" ;
    :seats 160 ;
    dct:temporal [
        a dct:PeriodOfTime ;
        dcat:startDate "2020-02-08T00:00:00"^^xsd:dateTime ;
        dcat:endDate   "2024-11-08T00:00:00"^^xsd:dateTime
    ] .
```

---

## Link to the Continuous House

Each `HouseTerm` should be linked to its persistent `agents:House` individual via `:termOf`:

| `houseCode` | `:termOf` target |
|---|---|
| `"dail"` | `<https://data.oireachtas.ie/house/dail>` |
| `"seanad"` | `<https://data.oireachtas.ie/house/seanad>` |

Equivalently, assert `:hasTerm` in the reverse direction on the house individual:

```turtle
<https://data.oireachtas.ie/house/dail>
    :hasTerm <https://data.oireachtas.ie/ie/oireachtas/house/dail/34> ,
             <https://data.oireachtas.ie/ie/oireachtas/house/dail/33> .
```

---

## Discarded / Re-expressed Fields

| API field | Disposition | Reason |
|---|---|---|
| `chamberCode` | Discarded | Always identical to `houseCode`; redundant |
| `houseType` | Discarded | Always identical to `houseCode`; redundant |
| `chamberType` | Not mapped as a literal | The value `"house"` distinguishes plenary chambers from committees. In RDF this is expressed by OWL class typing (`DailTerm`/`SeanadTerm`), not a string property. The distinction between plenary houses and committees is encoded in the ontology by the `members:House`/`agents:House` class hierarchy. |

---

## Prefixes Required

```turtle
@prefix :       <https://data.oireachtas.ie/ontology#> .
@prefix agents: <https://data.oireachtas.ie/ontology#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:    <http://purl.org/dc/terms/> .
@prefix dcat:   <http://www.w3.org/ns/dcat#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#> .
```

---

## Sample Data (all four records)

```turtle
# Current terms (dateRange.end = null → dcat:endDate omitted)

<https://data.oireachtas.ie/ie/oireachtas/house/dail/34>
    a agents:DailTerm, eli-dl:ParliamentaryTerm ;
    :termOf <https://data.oireachtas.ie/house/dail> ;
    skos:prefLabel "34th Dáil"@en ;
    :termNo 34 ;
    :houseCode "dail" ;
    :seats 174 ;
    dct:temporal [ a dct:PeriodOfTime ;
        dcat:startDate "2024-11-29T00:00:00"^^xsd:dateTime ] .

<https://data.oireachtas.ie/ie/oireachtas/house/seanad/27>
    a agents:SeanadTerm, eli-dl:ParliamentaryTerm ;
    :termOf <https://data.oireachtas.ie/house/seanad> ;
    skos:prefLabel "27th Seanad"@en ;
    :termNo 27 ;
    :houseCode "seanad" ;
    :seats 60 ;
    dct:temporal [ a dct:PeriodOfTime ;
        dcat:startDate "2025-01-29T00:00:00"^^xsd:dateTime ] .

# Concluded terms (dateRange.end present → dcat:endDate included)

<https://data.oireachtas.ie/ie/oireachtas/house/dail/33>
    a agents:DailTerm, eli-dl:ParliamentaryTerm ;
    :termOf <https://data.oireachtas.ie/house/dail> ;
    skos:prefLabel "33rd Dáil"@en ;
    :termNo 33 ;
    :houseCode "dail" ;
    :seats 160 ;
    dct:temporal [ a dct:PeriodOfTime ;
        dcat:startDate "2020-02-08T00:00:00"^^xsd:dateTime ;
        dcat:endDate   "2024-11-08T00:00:00"^^xsd:dateTime ] .

<https://data.oireachtas.ie/ie/oireachtas/house/seanad/26>
    a agents:SeanadTerm, eli-dl:ParliamentaryTerm ;
    :termOf <https://data.oireachtas.ie/house/seanad> ;
    skos:prefLabel "26th Seanad"@en ;
    :termNo 26 ;
    :houseCode "seanad" ;
    :seats 60 ;
    dct:temporal [ a dct:PeriodOfTime ;
        dcat:startDate "2020-03-30T00:00:00"^^xsd:dateTime ;
        dcat:endDate   "2025-01-29T00:00:00"^^xsd:dateTime ] .
```
