# Query Service — Planner HTTP 400 Diagnosis

## Finding

The HTTP 400 failures were caused by a Responses strict-JSON-Schema
incompatibility, not provider authentication/configuration or prompt/request
construction. On revision `9f0e5cd`, a single synthetic planner probe returned:

```text
HTTP 400; type=invalid_request_error; code=invalid_json_schema;
param=text.format.schema;
Invalid schema for response_format 'composable_query_plan_v2_draft':
In context=(), 'oneOf' is not permitted.
```

Only the allowlisted status/error fields and provider diagnostic were recorded.
The probe used no holdout question; its input, API key, full request, and raw
provider payload were not retained.

The historical working preflight recorded in
[`fresh-holdout-20261101.md`](fresh-holdout-20261101.md) succeeded on 2026-11-01
at revision `77b724f` with the same configured model (`gpt-6-luna`) and
Responses endpoint. Comparing its draft schema with the failing one shows the
relevant request delta: the temporal/count tranche added separate entity-list
and count answer shapes under JSON Schema `oneOf`. The earlier schema had one
closed entity-answer object. The provider's explicit `text.format.schema`
diagnostic and the prior configured preflight rule out provider credentials as
the cause and isolate the unsupported schema keyword.

## Correction

Changed the answer-shape union from `oneOf` to `anyOf`. The branches remain
mutually exclusive because their required `kind` values are the distinct
constants `entities` and `count`; the local plan validator still enforces the
complete exact answer shape. This keeps the accepted semantics and fail-closed
validation unchanged while using the provider-supported schema dialect.

## Verification

- Focused suites for Member composition/counts, Stage A temporal selection,
  bounded OfficeHolding composition, and semantic capability discovery:
  **163 passed**.
- Draft JSON Schema meta-validation passed; the regression asserts that the
  provider-facing schema contains no `oneOf` and retains both answer branches.
- No frozen holdout question was rerun, and no planner prompt was tuned.

## Live `/ask` smoke results

The corrected branch was served on loopback port 8001 with `asOf=2026-11-03`
and the existing local Fuseki dataset. All requests returned HTTP 200. The
smoke exercised the semantic planner as well as the deterministic selections:

| Capability / request | Observable result |
|---|---|
| Bertie Ahern's latest recorded Dáil term and constituency | Answer; validated plan selected the exact 30th Dáil identity from its recorded HouseTerm chronology (term start 2007-06-14). |
| HouseTerm on 14 June 1994; HouseTerm during June 1994 | Both answered with the exact 27th Dáil identity (1992-12-14–1997-05-15), preserving point versus full-month scope. |
| Distinct Members representing Dublin Central in the 31st Dáil on 14 June 2012 | Answered **4** using the dated bounded-count path. |
| Taoiseach on 14 June 1994; during June 1994; during 1994 | Each returned Albert Reynolds with the accepted holding interval 1992-12-14–1994-12-15. Date-point, full-month, and full-year scope were preserved. |
| Taoiseach on/during January 2020 or during 2020 | The validated date/month/year paths ran but found no accepted local holding. The UI correctly qualified this as incomplete historical evidence, not a confirmed negative. |

One exploratory count prompt paired the 31st Dáil with a 1994 date, which
predates that term; it was excluded from the smoke result. The accepted count
smoke used an in-term 2012 date. The 2020 OfficeHolding nonmatches likewise do
not establish absence of service because local historical office coverage is
incomplete.
