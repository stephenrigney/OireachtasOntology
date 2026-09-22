# Institutional, House and HouseTerm model

## Type and institutional identity

`agents:ParliamentaryBody` is the class for enduring parliamentary formal
organisations. It replaced the ambiguous `agents:Oireachtas` class. The
enduring Oireachtas is instead the named individual
`<https://data.oireachtas.ie/oireachtas>`. No OWL punning is used.

The enduring Oireachtas uses `org:hasSubOrganization` for its Dáil and Seanad
structure; each House reciprocally uses `org:subOrganizationOf`. This is an
organisational relation, not an `is-a` assertion: Dáil and Seanad are not kinds
of Oireachtas. The Constitution also comprises the President. President
identity and ETL are deferred because this repository has no authoritative
source contract for them; the model does not fabricate a President resource.

## Enduring Houses and numbered terms

`agents:House` is a subclass of `agents:ParliamentaryBody`. The authoritative
enduring identities are:

- `<https://data.oireachtas.ie/house/dail>`
- `<https://data.oireachtas.ie/house/seanad>`

`agents:HouseTerm` (with `agents:DailTerm` and `agents:SeanadTerm`) is a
temporally bounded sitting, not an organisation. It is disjoint from
`agents:ParliamentaryBody`. `agents:hasTerm` and its inverse `agents:termOf`
connect each numbered term to its enduring House. Membership records therefore
retain both `members:isOireachtasMembershipOf` (House) and
`members:inHouseTerm` (term), without conflating their identities.

## Government

`agents:Government` is a separate `org:FormalOrganization`, disjoint from the
parliamentary-body class. The enduring constitutional resource
`<https://data.oireachtas.ie/government>` is `agents:responsibleTo` the enduring
Dáil. `agents:responsibleTo` is a subproperty of `org:reportsTo`, retaining the
specific constitutional meaning while permitting ORG interoperability.

Government accountability is distinct from membership. A Cabinet office is a
`members:CabinetMember` role and a `members:CabinetMembership` records its
holder; recorded Cabinet holders are constrained to also have an
`members:OireachtasMembership`. Temporal overlap and office-specific rules are
quality-validation concerns, not invented OWL facts.

The API's generic
`<https://data.oireachtas.ie/ie/oireachtas/def/bill-source/government>` remains
the `eli-dl:was_submitted_by` target for Government bills, but is now a
`agents:GovernmentBillSource` controlled concept. It is neither the enduring
Government resource nor a numbered Government administration.
