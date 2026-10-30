# Member nested-evidence quality audit

## Scope and result

The complete captured Members scan retrieved on 2026-10-02 was checked before
changing behavior: 20 hash-verified `GET /v1/members?skip={n}&limit=100`
responses, 1,928 unique Member records, and 3,054 committee-role observations.
The Members API's `committees.items` schema is untyped. The capture contained
2,737 empty-array committee roles and 317 meaningful role objects (211
`Cathaoirleach`, 106 `Leas-Chathaoirleach`); the previously implemented role
normalizer supports those two mapped forms. No role object in the capture had
another shape or title.

Before the party-date fix, source validation and transformation each stopped
on the same 12 Member records, all for `reverse membership date range` at a
nested party date. Exhaustive nested party-date inspection found exactly those
12 malformed observations and no other unusable party ranges or party
container/identity shape failures. The remaining 1,916 records transformed
and passed independent RDF validation. No other source-validation or
transformation failure class was found.

The capture also contains 1,142 office observations, two reversed office
ranges. Those are already isolated by the existing office-level quarantine
and do not prevent Member transformation:

| Member | Source pointer | Response SHA-256 |
|---|---|---|
| Jack Chambers | `/results/95/member/memberships/1/membership/offices/5` (`skip=200`) | `5763957939c2fa6270b8805e2d899d9cb2dddfc07165e2d92d624afbf4cb92d5` |
| Leo Varadkar | `/results/28/member/memberships/0/membership/offices/3` (`skip=1800`) | `93ad1c43f5e9d65f750fa946b69de5ac94b0c331c0d8c3059feb14cac6010f2e` |

## Malformed party-date inventory

All pointers below address the original individual API page response, not the
combined offline fixture. The date strings and JSON values are preserved
exactly as captured; no dates were swapped, corrected, or emitted as RDF.

| Member | Party | Captured range (`start` → `end`) | Source pointer (`skip`) | Response SHA-256 |
|---|---|---|---|---|
| Bobby Aylward | `Fianna_Fáil` | `2016-03-10` → `2016-03-09` | `/results/29/member/memberships/1/membership/parties/0/party/dateRange` (`0`) | `832a12d7cb701dad7e5ef72169e18ad37a828f40a018d8807550705048471855` |
| Richard Bruton | `Fine_Gael` | `2016-03-10` → `1982-04-16` | `/results/89/member/memberships/10/membership/parties/0/party/dateRange` (`100`) | `5ddbf3cc914f2f7c209da7e32623a3ddf7c07ee8e918f1072ff8f92ae57ccff6` |
| Ruth Coppinger | `Anti-Austerity_Alliance_People_Before_Profit` | `2016-03-10` → `2016-03-09` | `/results/91/member/memberships/1/membership/parties/0/party/dateRange` (`300`) | `b6a9d17ae897e34d697f4d0886f0b41fa594230784e2af766ea967a018821042` |
| Simon Coveney | `Fine_Gael` | `2016-03-10` → `2002-04-25` | `/results/25/member/memberships/4/membership/parties/0/party/dateRange` (`400`) | `367bfadaf5323e64ef88651c0314126905ca52ca779247428ac8273032b00916` |
| Michael Fitzmaurice | `Independent` | `2016-03-10` → `2016-03-09` | `/results/94/member/memberships/1/membership/parties/0/party/dateRange` (`600`) | `6b5457bf4e156d5e4ce3207a099af0a7ea5400525ec8ba26f37b2c98a3f0ec3e` |
| Seamus Healy | `Independent` | `2016-03-10` → `2002-04-25` | `/results/62/member/memberships/3/membership/parties/0/party/dateRange` (`800`) | `935d6d18c2879d48ec6921086a86563ec07f3c468623732997b92c60e49ddb26` |
| Enda Kenny | `Fine_Gael` | `2016-03-10` → `1977-05-25` | `/results/11/member/memberships/12/membership/parties/0/party/dateRange` (`1000`) | `2edf3f03ebed077b3d5a49be74d7b9af44ef7af254433e33b22cd1f3013de686` |
| Helen McEntee | `Fine_Gael` | `2016-03-10` → `2016-03-09` | `/results/46/member/memberships/1/membership/parties/0/party/dateRange` (`1200`) | `ce16088691b014627c984487fe9811040937036fa8d925a837bde9a37725217a` |
| Gabrielle McFadden | `Fine_Gael` | `2016-04-25` → `2016-03-09` | `/results/48/member/memberships/1/membership/parties/0/party/dateRange` (`1200`) | `ce16088691b014627c984487fe9811040937036fa8d925a837bde9a37725217a` |
| Paul Murphy | `Anti-Austerity_Alliance_People_Before_Profit` | `2016-03-10` → `2016-03-09` | `/results/91/member/memberships/1/membership/parties/0/party/dateRange` (`1300`) | `55ac3e6af74ede6e949307a50f5779a844e7ef3c5a440d98fddc770fcb2700b4` |
| Michael Ring | `Fine_Gael` | `2016-03-10` → `1997-05-15` | `/results/77/member/memberships/5/membership/parties/0/party/dateRange` (`1600`) | `1b22c6571957459fa4bdb6477757973396db1f4d2068bace1897c43b99b096a8` |
| Shane P. N. Ross | `Independent` | `2016-03-10` → `1982-04-16` | `/results/95/member/memberships/10/membership/parties/0/party/dateRange` (`1600`) | `1b22c6571957459fa4bdb6477757973396db1f4d2068bace1897c43b99b096a8` |

## Classification and treatment

| Finding | Classification | Treatment |
|---|---|---|
| Committee role object forms | Valid repeated API variation | Map the two observed Irish titles to existing Chair/Deputy Chair terms; validate and report tenure dates without inventing a role-tenure predicate. |
| Twelve reversed party ranges | Malformed nested evidence safely isolatable when the party identity is valid | Preserve raw nested source; quarantine only the party record; emit no party membership/date RDF for it; continue other Member and party data. |
| Previously accepted party evidence in an affected House membership | Malformed current evidence requiring retention of accepted state | Online runs compose the exact previously published party-membership triples from that affected House membership, then validate the result. If the accepted payload is unavailable/unverifiable, leave the entire prior Member graph untouched. |
| Unsafe Member, House-membership, party-container or party-identity structures | Fail-closed boundary; none occurred among the 1,928 captured records | Keep strict validation; tests cover malformed wrappers, collections, identities and Member-level date ranges. |
| Ontology/mapping ambiguity | None found | Existing mapping clearly maps party date ranges to Member-owned dated collection memberships; no ontology or mapping change was needed. |
