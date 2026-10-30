# Private Beta Deployment Plan

## Status and purpose

**Status:** proposed planning baseline; no hosting provider, access gateway, production database, or institutional integration has been selected. This plan does not authorise deployment.

Deploy a limited, invitation-only, cloud-hosted beta of the OireachtasOntology NLQ application and Query Service for subject-matter expert (SME) evaluation. Gather evidence about usefulness, correctness, coverage, usability, and operational requirements **before** deciding whether, where, or how to integrate with existing institutional infrastructure.

The beta is an evaluation environment, not the first instance of a settled production architecture. Apache Jena Fuseki is the current demonstration RDF store, **not** an approved production-store decision.

## Scope and boundaries

- Invite a small, explicitly managed cohort of SMEs; provide individual access, revocation, and a clear feedback channel.
- Serve the application over HTTPS from public-cloud infrastructure, but keep RDF storage, administration, publication, and internal service endpoints off the public internet.
- Put an independently enforced identity-aware access boundary in front of **all** beta application routes and APIs. Require MFA where supported; do not build a custom password system.
- Use a controlled, documented, reproducible beta dataset. Clearly distinguish authoritative accepted RDF from development/bootstrap data, quarantined identities, incomplete coverage, and experimental external facts.
- Preserve the ability to replace the cloud provider, identity gateway, query implementation, and RDF store.
- Do not expose Fuseki administration, SPARQL update, or Graph Store Protocol publication endpoints to SMEs.
- Exclude public self-registration, general public access, production SLA commitments, and institutional identity integration from this tranche.

## Proposed logical topology

```text
Invited SMEs
    |
 HTTPS + individual identity + access policy + MFA
    |
Cloud access gateway / ingress
    |
NLQ application + Query Service (private service boundary)
    |
read-only, bounded query interface
    |
isolated RDF store (Fuseki for beta only if accepted at gate)

Separate operator / ETL publication path; never routed through SME access.
```

Gateway protection is necessary but not sufficient: the Query Service must enforce its own query safety, read-only backend permissions, resource limits, and safe error handling. Prevent direct-origin bypass of the gateway.

## Delivery work and acceptance gates

### Gate 1 — Beta design approval (before provisioning)

- Confirm SME cohort size, expected usage, beta duration, hosting region, budget, and accountable operator.
- Select temporary hosting and identity gateway only after comparing operational effort, isolation, access revocation, cost, and portability.
- Document a lightweight threat model: public ingress, identity provider, application/API, model provider, outbound connections, RDF store, ETL, backups, logs, and administrative access.
- Define dataset snapshot, coverage limitations, source authority labels, refresh approach, and whether any unresolved development data may appear; never represent bootstrap output as authoritative.
- Decide which NLQ features and third-party model calls are enabled. Review data sent to model providers, retention and participant notices.
- Record data-protection assessment, logging/retention policy, contact for security issues, and incident response owner.
- Approve a minimal topology, cost cap, rollback plan, and explicit stop conditions.

**Exit:** written approval of design and risk assumptions; no public deployment yet.

### Gate 2 — Staging security and operational acceptance

- Enforce invited-user authentication, MFA policy, access revocation, session expiry, and operator separation. Test that unauthenticated users and revoked accounts cannot reach UI **or APIs**, including by bypassing the gateway.
- Verify HTTPS, private store networking, firewall rules, secret storage/rotation, least-privilege service accounts, no default passwords, and no public admin/update endpoints.
- Confirm Query Service rejects SPARQL updates and forbidden operations, bounds execution time, concurrency, query cost and result size, and handles hostile NLQ inputs without exposing internals. Enforce backend read-only permissions independently.
- Test XML/source-input protections and outbound request restrictions where ETL or remote querying is enabled.
- Scan dependencies, containers, configuration and Git history for vulnerabilities and leaked secrets; triage findings.
- Verify startup, health checks, access/security logs, alerting, backup/restore appropriate to beta, reproducible redeploy, and teardown. Avoid collecting unnecessary personal information in logs.
- Run targeted adversarial tests against the **deployed** staging topology, including unauthorised updates, expensive queries, authentication bypass, malicious inputs, and denial-of-service controls.
- Verify application behaviour and query benchmarks against the selected dataset; publish known limitations and a participant feedback mechanism.

**Exit:** critical/high exploitable findings resolved or explicitly risk-accepted by an accountable owner where appropriate; no unauthorised data mutation or gateway bypass; staging evidence recorded.

### Gate 3 — Controlled beta launch

- Recheck the actual cloud configuration, origin isolation, TLS, gateway policy, accounts, secrets, endpoint permissions, monitoring and spend alerts.
- Admit only the approved SME cohort. Supply onboarding instructions, data/accuracy caveats, support contact, feedback instructions, and expected end date.
- Record deployment version, dataset identity, security checks, known limitations, accountable operator and rollback procedure.
- Monitor errors, abuse, query latency, availability, costs and feedback. Be able to suspend access immediately.

**Exit:** explicit go/no-go approval; beta access can be disabled without changing authoritative ETL state.

### Gate 4 — Evaluation and disposition

- Assess SME findings: correctness, coverage, explainability/provenance, usability, query failure modes, demand and performance.
- Record actual operating cost, security incidents, maintenance burden and technical limitations.
- Decide whether to stop, extend, redesign or seek institutional integration. Only then assess production hosting, identity, RDF-store choice, SLAs, formal penetration testing and institutional security requirements.
- Revoke accounts and remove or retain cloud resources/data according to the agreed retention and teardown policy.

## Responsibilities and dependencies

- **Query Service:** stable query/schema contract, bounded read-only execution, useful diagnostics and provenance; no assumption that Fuseki remains the production backend.
- **NLQ application:** SME-friendly entry point, safe error handling, visibility of interpretation and generated queries where appropriate, and feedback collection.
- **ETL / reference coverage / Debates / Bills:** provide a versioned dataset with explicit completeness and authority status; unresolved source conflicts remain fail-closed for authoritative publication.
- **Phase 6 operations:** reuse tested backup, recovery, deployment and monitoring patterns where proportionate; Phase 6 completion alone is **not** cloud-beta security approval.
- **Beta deployment:** gateway, cloud isolation, access lifecycle, configuration, security evidence, operational ownership and teardown.

Implementation should be a bounded workstream after Gate 1, with evidence reviewed at each gate. Do not introduce a second task-management system; record defects and deferred controls in the existing backlog, marking beta launch blockers explicitly.

## Open decisions (not yet approved)

1. SME cohort, beta length and expected concurrent usage.
2. Hosting provider/region and managed ingress or identity-aware gateway.
3. Authentication identity sources, MFA requirements, account approval and revocation ownership.
4. Dataset snapshot and refresh cadence; inclusion or exclusion of experimental/partial records.
5. External model provider and data-handling terms; whether remote federation is enabled.
6. Log retention, participant privacy notice, feedback collection and incident contact.
7. Cost ceiling, resource limits, backup/restore target and teardown date.
8. Evidence required for independent security review based on actual exposure.

## Non-goals and decision guardrails

Do not commit to Fuseki as the production RDF store, a permanent cloud platform, an institutional identity system, or a final deployment topology on the strength of this beta. No externally accessible beta is authorised until the staged security gate passes.
