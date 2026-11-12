#!/usr/bin/env python3
"""Independent, read-only check of the 2026-11-11 NLQ evidence freeze.

Reads only development capture manifests/pages, query texts and evidence.nq.
It deliberately does not read oracle.json or invoke/modify the triple store.
Run from anywhere: .venv/bin/python /tmp/.../check.py [repo-root]
"""
from __future__ import annotations
import hashlib, json, re, sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
DEV = REPO / "docs/reports/query-service/composition-freeze-20261111/development"
CAP = DEV / "captures"
ASOF = date(2026, 11, 11)
M = "https://data.oireachtas.ie/ontology/members#"
A = "https://data.oireachtas.ie/ontology#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
FOAF = "http://xmlns.com/foaf/0.1/"
DCT = "http://purl.org/dc/terms/"
DCAT = "http://www.w3.org/ns/dcat#"
GRAPH_PREFIX = "https://data.oireachtas.ie/graph/"

errors: list[str] = []
def check(ok: bool, message: str) -> None:
    if not ok: errors.append(message)
def termval(binding, key):
    x = binding.get(key)
    return x.get("value") if x else None

def load_capture(name: str):
    d = CAP / name
    manifest = json.loads((d / "capture.json").read_text())
    check(manifest.get("asOf") == ASOF.isoformat(), f"{name}: wrong asOf")
    check(manifest.get("enumeration_complete") is True, f"{name}: not marked enumeration_complete")
    check("not a transactional" in manifest.get("snapshot", "").lower(), f"{name}: no sequential-snapshot limitation")
    qpath = d / "query.rq"
    check(hashlib.sha256(qpath.read_bytes()).hexdigest() == manifest.get("query_sha256"), f"{name}: query hash mismatch")
    rows=[]; expected_offset=0
    pages=manifest.get("pages", [])
    for page in pages:
        path=d/page["file"]
        raw=path.read_bytes()
        check(hashlib.sha256(raw).hexdigest() == page.get("sha256"), f"{name}/{path.name}: page hash mismatch")
        check(page.get("http_status") == 200, f"{name}/{path.name}: non-200 response")
        check(page.get("offset") == expected_offset, f"{name}/{path.name}: non-contiguous offset")
        obj=json.loads(raw); bindings=obj.get("results",{}).get("bindings",[])
        check(len(bindings) == page.get("rows"), f"{name}/{path.name}: row count mismatch")
        rows.extend(bindings); expected_offset += len(bindings)
    check(expected_offset == sum(p.get("rows",0) for p in pages), f"{name}: manifest totals mismatch")
    return manifest, rows

names=sorted(p.name for p in CAP.iterdir() if p.is_dir())
captures={name:load_capture(name) for name in names}
first_read_pages=sum(len(captures[n][0].get("pages",[])) for n in names)
first_read_rows=sum(len(captures[n][1]) for n in names)
check(len(names)==16 and first_read_pages==36 and first_read_rows==2491,
      f"first-read capture totals changed: {len(names)} queries/{first_read_pages} requests/{first_read_rows} binding rows")
print(f"First-read captures: {len(names)} queries, {first_read_pages} requests, {first_read_rows} typed binding rows")

# Explicitly parse the saved N-Quads (not the oracle or inferred query result).
ds=Dataset(default_union=True)
ds.parse(DEV / "evidence.nq", format="nquads")
quads={(s,p,o,g) for s,p,o,g in ds.quads((None,None,None,None))}
triples={(s,p,o) for s,p,o,g in quads}

# Compare evidence.nq with raw finite-slice RDF rows from the quads-shaped captures.
def term_from_json(x):
    if x["type"] == "uri": return URIRef(x["value"])
    if x["type"] == "bnode":
        from rdflib import BNode
        return BNode(x["value"])
    return Literal(x["value"], lang=x.get("xml:lang"), datatype=URIRef(x["datatype"]) if x.get("datatype") else None)

audit_quads=set()
for name in names:
    if not (name.startswith("resource-audit-") or name == "identity-audit"): continue
    _, rows=captures[name]
    for r in rows:
        if all(k in r for k in ("g","s","p","o")):
            audit_quads.add((URIRef(r['s']['value']), URIRef(r['p']['value']),
                             term_from_json(r['o']), URIRef(r['g']['value'])))

print(f"evidence.nq: {len(quads)} quads, {len(triples)} distinct triples")
print(f"quads-shaped capture result rows/unique quads: {sum(len(captures[n][1]) for n in names if n.startswith('resource-audit-') or n == 'identity-audit')}/{len(audit_quads)}")
print(f"captured quads missing from evidence.nq: {len(audit_quads-quads)}; evidence quads not in captures: {len(quads-audit_quads)}")
check(audit_quads == quads, "evidence.nq does not equal the union of resource/identity audit capture quads")
if audit_quads-quads:
    for q in sorted(audit_quads-quads,key=lambda x: tuple(map(str,x)))[:10]: print("  missing:",q)

# Utilities for exact quads / typed values.
def objects(s,p,g=None):
    return {o for ss,pp,o,gg in quads if ss==s and pp==URIRef(p) and (g is None or gg==g)}
def subjects(p,o,g=None):
    return {s for s,pp,oo,gg in quads if pp==URIRef(p) and oo==o and (g is None or gg==g)}
def g_quads(s=None,p=None,o=None,g=None):
    return {(ss,pp,oo,gg) for ss,pp,oo,gg in quads if (s is None or ss==s) and (p is None or pp==URIRef(p)) and (o is None or oo==o) and (g is None or gg==g)}
def iri(x): return URIRef(x) if x else None
def is_typed_date(value): return isinstance(value,Literal) and value.datatype==XSD.dateTime and value.language is None
def day(value):
    if not is_typed_date(value): return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError: return None
def active(start_values, end_values):
    if len(start_values)!=1 or len(end_values)>1: return False
    starts=list(start_values); ends=list(end_values)
    s=day(starts[0]); e=day(ends[0]) if ends else None
    return s is not None and s<=ASOF and (not ends or (e is not None and ASOF<=e))

# Manifest counts/hashes above are independent of the reported candidate values.
print("capture rows:", ", ".join(f"{n}={len(captures[n][1])}" for n in names))

# Establish explicitly recorded current HouseTerms from the raw N-Quads.
houses_graph=URIRef(GRAPH_PREFIX+"houses")
periods={}
term_subjects={s for s,p,o,g in quads if p==RDF.type and o in {URIRef(A+"DailTerm"),URIRef(A+"SeanadTerm")} and g==houses_graph}
check(len(term_subjects)==65, f"expected 65 explicit Dail/Seanad term resources in audit slice, found {len(term_subjects)}")
for t in term_subjects:
    term_types=objects(t,str(RDF.type),houses_graph)
    period_set=objects(t,DCT+"temporal",houses_graph)
    starts=set(); ends=set(); period_ok=(len(period_set)==1)
    if period_ok:
        per=next(iter(period_set))
        period_ok=(URIRef("http://purl.org/dc/terms/PeriodOfTime") in objects(per,str(RDF.type),houses_graph))
        starts=objects(per,DCAT+"startDate",houses_graph); ends=objects(per,DCAT+"endDate",houses_graph)
        period_ok=period_ok and len(starts)==1 and len(ends)<=1 and all(is_typed_date(v) for v in starts|ends)
    is_current=period_ok and active(starts,ends)
    if is_current:
        periods[str(t)]=next(iter(starts)) if len(starts)==1 else None
        print("CURRENT TERM",t,"types",sorted(map(str,term_types)),"start",sorted(map(str,starts)),"end",sorted(map(str,ends)))
check(set(periods)=={
    "https://data.oireachtas.ie/ie/oireachtas/house/dail/34",
    "https://data.oireachtas.ie/ie/oireachtas/house/seanad/27",
}, f"unexpected current-term set: {sorted(periods)}")
term_rows=captures["terms"][1]
term_captured={termval(r,"term") for r in term_rows}
check(term_captured=={str(t) for t in term_subjects}, "terms SELECT does not cover the explicit Dail/Seanad term set from the raw audit quads")

# Check memberCode -> percent-encoded named-graph identity over the explicit evidence slice.
member_graph_codes=defaultdict(set)
member_subjects={s for s,p,o,g in quads if p==RDF.type and o==URIRef(A+"Member")}
for m in member_subjects:
    codes=objects(m,A+"memberCode")
    check(len(codes)==1, f"member {m}: expected one memberCode, got {sorted(map(str,codes))}")
    if len(codes)==1:
        code=next(iter(codes))
        check(isinstance(code,Literal) and not code.language, f"member {m}: memberCode not a plain literal")
        expected=GRAPH_PREFIX+"member/"+quote(str(code),safe="")
        owner_graphs={g for s,p,o,g in quads if s==m}
        check(owner_graphs=={URIRef(expected)}, f"member {m}: owner graph(s) {sorted(map(str,owner_graphs))}, expected {expected}")
        member_graph_codes[expected].add(str(code))
for g in {g for s,p,o,g in quads if str(g).startswith(GRAPH_PREFIX+"member/")}:
    check(str(g) in member_graph_codes and len(member_graph_codes[str(g)])==1,
          f"member graph {g}: no unique encoded code owner in captured slice")
print(f"Member resources with explicit type/code/owner checked: {len(member_subjects)}")

# Validate the original DateRange resource assertions and group repeated range nodes.
range_types=URIRef(M+"DateRange")
start_p=M+"StartDate"; end_p=M+"EndDate"; has_range=M+"hasMembershipDateRange"
range_parents=defaultdict(set)
for s,p,o,g in quads:
    if p==URIRef(has_range): range_parents[o].add((s,g))
range_errors=[]; range_summary=[]
for r, parents in sorted(range_parents.items(),key=lambda x:str(x[0])):
    rg={g for s,g in parents}
    # Membership owner and range owner should coincide; types/date assertions must be explicit in that owner graph.
    starts={(o,g) for s,p,o,g in quads if s==r and p==URIRef(start_p)}
    ends={(o,g) for s,p,o,g in quads if s==r and p==URIRef(end_p)}
    types={(o,g) for s,p,o,g in quads if s==r and p==RDF.type}
    problems=[]
    if len(rg)!=1: problems.append("multiple parent owner graphs")
    if types!={(range_types,next(iter(rg)))} if len(rg)==1 else True: problems.append("missing/wrong DateRange type or owner")
    if len(starts)!=1: problems.append(f"{len(starts)} start assertions")
    if len(ends)>1: problems.append(f"{len(ends)} end assertions")
    if any(not is_typed_date(v) for v,g in starts|ends): problems.append("non-xsd:dateTime original date")
    if any(g not in rg for v,g in starts|ends): problems.append("range values in wrong graph")
    # Distinct range values are reported without collapsing separate nodes or suppressing conflicts.
    sv=sorted({str(v) for v,g in starts}); ev=sorted({str(v) for v,g in ends})
    if problems: range_errors.append((str(r),problems))
    range_summary.append((str(r),sv,ev,sorted(str(s) for s,g in parents),sorted(str(g) for g in rg),problems))
for r,pb in range_errors: errors.append(f"range {r}: {', '.join(pb)}")
print(f"Membership DateRange nodes linked in evidence: {len(range_parents)}; grouped errors/conflicts: {len(range_errors)}")
for row in range_summary:
    if row[-1]: print("RANGE ISSUE",row)

# Verify each historical/current Committee owner and its distinct operational interval in the owner graph.
committees_graph=URIRef(GRAPH_PREFIX+"committees")
owner_rows=captures["committee-owners"][1]
owner_current=[]
for row in owner_rows:
    c=iri(termval(row,"committee")); t=iri(termval(row,"term")); r=iri(termval(row,"range"))
    labels=objects(c,SKOS+"prefLabel",committees_graph) if c else set()
    cterms=objects(c,M+"committeeInHouseTerm",committees_graph) if c else set()
    cranges=objects(c,M+"hasCommitteeDateRange",committees_graph) if c else set()
    check(c is not None and URIRef(M+"Committee") in objects(c,str(RDF.type),committees_graph), f"committee owner {c}: missing explicit Committee type in committees graph")
    check(labels and all(isinstance(x,Literal) for x in labels), f"committee owner {c}: no explicit display label; still retained as candidate")
    check(cterms=={t}, f"committee owner {c}: explicit own term missing/conflicting")
    check(cranges=={r}, f"committee owner {c}: explicit operational-range link missing/conflicting")
    if r:
        starts=objects(r,start_p,committees_graph); ends=objects(r,end_p,committees_graph)
        check(range_types in objects(r,str(RDF.type),committees_graph) and len(starts)==1 and len(ends)<=1
              and all(is_typed_date(x) for x in starts|ends), f"committee owner {c}: missing/conflicting/wrongly typed operational dates")
        if active(starts,ends): owner_current.append(c)
check(len(owner_rows)==3 and len(owner_current)==1 and owner_current[0]==URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts"), "historical/current Committee owner interval set is not as expected")

# Exact committee membership rows from captured SELECT, then independently validate the explicit graph facts.
comm_manifest,comm_rows=captures["committee-members"]
committee=URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts")
K=[]
for row in comm_rows:
    member=iri(termval(row,"member")); link=iri(termval(row,"membership")); code=termval(row,"code")
    if not link: continue
    K.append((member,link,code,termval(row,"name"),termval(row,"range"),termval(row,"start"),termval(row,"end"),termval(row,"g")))
check(len(K)==15, f"expected 15 current-committee membership relation candidates, found {len(K)}")
active_K=[]
for member,link,code,name,r,start,end,graph in K:
    g=iri(graph); range_iri=iri(r)
    check(member is not None, f"committee relation {link}: no Member link (display name not used as filter)")
    if member:
        check((member,URIRef(M+"hasMembersMembership"),link,g) in quads, f"committee relation {link}: missing exact Member hasMembersMembership link in owner graph")
        check(objects(member,A+"memberCode",g)=={Literal(code)}, f"committee relation {link}: code/owner does not match linked member")
    check((link,RDF.type,URIRef(M+"CommitteeMembership"),g) in quads, f"committee relation {link}: no explicit CommitteeMembership type in member graph")
    check((link,URIRef(M+"isCommitteeMembershipOf"),committee,g) in quads, f"committee relation {link}: missing committee link in owner graph")
    check(range_iri is not None and (link,URIRef(has_range),range_iri,g) in quads, f"committee relation {link}: missing explicit range link")
    # The ontology makes CommitteeMembership a MembersMembership, not a ParliamentaryCollectionMembership;
    # do not infer a containing OireachtasMembership or force committee-term equality.
    if range_iri:
        starts=objects(range_iri,start_p,g); ends=objects(range_iri,end_p,g)
        valid=(range_iri in objects(link,has_range,g) and range_types in objects(range_iri,str(RDF.type),g)
               and len(starts)==1 and len(ends)<=1 and all(is_typed_date(x) for x in starts|ends))
        check(valid, f"committee relation {link}: missing/conflicting/wrongly-typed membership dates")
        if valid and active(starts,ends): active_K.append((member,link,code,name,range_iri,graph))
        if valid and not active(starts,ends): print("INACTIVE COMMITTEE RECORD",code,"name",name,"start",sorted(map(str,starts)),"end",sorted(map(str,ends)))
print("Current committee owner rows:",len(K),"active CommitteeMembership records:",len(active_K))

# Candidate-party records: preserve distinct episode/parent membership/term; do not join on labels.
_,party_rows=captures["candidate-party"]
party_rows_by_ep=defaultdict(list)
for row in party_rows:
    ep=termval(row,"episode")
    if ep: party_rows_by_ep[ep].append(row)
party_facts=[]
incomplete_party_episodes=[]
for ep, rows in party_rows_by_ep.items():
    # Each SELECT row can repeat because of inferred rdf:type values; the raw source has one episode fact set.
    types={termval(r,"episodeType") for r in rows}
    if M+"PartyMembership" not in types: continue
    rr=next((r for r in rows if termval(r,"episodeType")==M+"PartyMembership"),rows[0])
    member=iri(termval(rr,"member")); member_code=termval(rr,"code"); party=iri(termval(rr,"party")); pm=iri(termval(rr,"membership")); term=iri(termval(rr,"term")); graph=iri(termval(rr,"g"))
    # Data rows hold this linkage true if matched; exact graph assertions below are the check.
    episode_range=iri(termval(rr,"er")); member_range=iri(termval(rr,"mr"))
    if not (member and party and pm and term and graph and episode_range):
        incomplete_party_episodes.append((ep,sorted(types)))
        continue
    check((member,URIRef(M+"hasMembersMembership"),URIRef(ep),graph) in quads, f"party episode {ep}: missing exact Member link in owner graph")
    check((URIRef(ep),URIRef(M+"inOireachtasMembership"),pm,graph) in quads, f"party episode {ep}: missing parent OireachtasMembership containment in owner graph")
    check((URIRef(ep),URIRef(M+"isPartyMembershipOf"),party,graph) in quads and (URIRef(ep),URIRef(M+"memberOfCollection"),party,graph) in quads, f"party episode {ep}: missing party/collection relationship")
    check((pm,URIRef(M+"inHouseTerm"),term,graph) in quads, f"party episode {ep}: parent membership term differs/missing")
    check(member in member_subjects, f"party episode {ep}: Member not explicitly typed in evidence")
    check(objects(member,A+"memberCode",graph)=={Literal(member_code)}, f"party episode {ep}: graph/code owner mismatch")
    # Both independent timelines must be explicitly typed, owned in graph, and active on asOf.
    pm_ranges=objects(pm,has_range,graph)
    pm_ok=(len(pm_ranges)==1 and (pm,RDF.type,URIRef(M+"OireachtasMembership"),graph) in quads)
    pm_range=next(iter(pm_ranges)) if len(pm_ranges)==1 else None
    pm_start=objects(pm_range,start_p,graph) if pm_range else set(); pm_end=objects(pm_range,end_p,graph) if pm_range else set()
    pm_ok=pm_ok and pm_range in {s for s,p,o,g in quads if s==pm_range and p==RDF.type and o==range_types and g==graph}
    pm_ok=pm_ok and len(pm_start)==1 and len(pm_end)<=1 and all(is_typed_date(x) for x in pm_start|pm_end) and active(pm_start,pm_end)
    ep_start=objects(episode_range,start_p,graph); ep_end=objects(episode_range,end_p,graph)
    ep_ok=((URIRef(ep),URIRef(has_range),episode_range,graph) in quads
           and range_types in objects(episode_range,str(RDF.type),graph)
           and len(ep_start)==1 and len(ep_end)<=1 and all(is_typed_date(x) for x in ep_start|ep_end)
           and active(ep_start,ep_end))
    party_owner=URIRef(GRAPH_PREFIX+"parties")
    pterms=objects(party,M+"activeDuringTerm",party_owner)
    party_link_type=objects(party,str(RDF.type),party_owner)
    party_term_current=any(str(t) in periods for t in pterms)
    party_label=objects(party,SKOS+"prefLabel",party_owner)
    check(URIRef(M+"ParliamentaryMemberCollection") in party_link_type and URIRef(M+"ParliamentaryParty") in party_link_type,
          f"party resource {party}: missing explicit ParliamentaryParty/collection types in parties graph")
    check(len(pterms)==1,
          f"party resource {party}: activeDuringTerm missing/conflicting")
    expected_party_term=re.search(r"/party/(dail|seanad)/(\d+)/",str(party))
    check(expected_party_term is not None, f"party resource {party}: no explicit House/term path")
    if expected_party_term:
        expected_term=f"https://data.oireachtas.ie/ie/oireachtas/house/{expected_party_term.group(1)}/{expected_party_term.group(2)}"
        check(pterms=={URIRef(expected_term)}, f"party resource {party}: activeDuringTerm conflicts with its resource term scope")
    check(len(party_label)==1 and isinstance(next(iter(party_label)),Literal), f"party resource {party}: missing/conflicting explicit label")
    # Keep records only for analysis; report current Dail/Seanad Fianna Fáil and Sinn Féin evidence.
    fact=(member,member_code,URIRef(ep),party,pm,term,episode_range,graph,pm_ok,ep_ok,pterms,party_owner,party_link_type)
    party_facts.append(fact)

# Independently compare the broader direct Member->membership enumeration against the
# narrower PartyMembership/isPartyMembershipOf query, preserving optional fields.
ml_rows=captures["member-link-enumeration"][1]
records=defaultdict(lambda: {"members":set(),"graphs":set(),"types":set(),"containing":set(),"party":set(),"collection":set(),"term":set()})
for row in ml_rows:
    record=termval(row,"record")
    if not record: continue
    z=records[record]
    for key,out in [("member","members"),("g","graphs"),("recordType","types"),("containing","containing"),("party","party"),("collection","collection"),("term","term")]:
        value=termval(row,key)
        if value is not None: z[out].add(value)
ml_members={m for z in records.values() for m in z["members"]}
ml_query=(CAP/"member-link-enumeration"/"query.rq").read_text()
seed_block=re.search(r"VALUES\s+\?member\s*\{(.*?)\}",ml_query,re.S)
seed_members=set(re.findall(r"<([^>]+)>",seed_block.group(1))) if seed_block else set()
check(len(ml_rows)==309 and len(ml_members)==20, f"direct link enumeration coverage changed: {len(ml_rows)} rows, {len(ml_members)} Members")
check(len(seed_members)==20 and ml_members==seed_members, f"direct link query VALUES/bindings mismatch: {len(seed_members)} seeds, {len(ml_members)} bound Members")
k_seed_members={termval(r,"member") for r in captures["committee-members"][1] if termval(r,"member")}
r_seed_members={termval(r,"member") for r in captures["representation"][1] if termval(r,"member")}
check(len(k_seed_members)==15 and len(r_seed_members)==5 and not (k_seed_members&r_seed_members)
      and k_seed_members|r_seed_members==seed_members,
      f"R/K seed partition differs from direct-link VALUES: R={len(r_seed_members)} K={len(k_seed_members)} intersection={len(k_seed_members&r_seed_members)}")
print("Direct-link query seed count (verified from query text and bindings):",len(seed_members),"; R=5 and K=15 are disjoint and cover all seeds")
collection_records={rec for rec,z in records.items() if z["collection"]}
party_episode_ids={f"{ep}" for _,_,ep,_,_,_,_,_,_,_,_,_,_ in party_facts}
check(len(collection_records)==40, f"expected 40 direct linked collection records, found {len(collection_records)}")
check(collection_records-party_episode_ids=={
    "https://data.oireachtas.ie/ie/oireachtas/member/id/Catherine-Connolly.D.2016-10-03/house/dail/32#party-membership-5d78f039fbb2070db40838ca40385260e8e2a173d11ab0d9b659c7c3237996e4",
    "https://data.oireachtas.ie/ie/oireachtas/member/id/Catherine-Connolly.D.2016-10-03/house/dail/33#party-membership-595b8036c625e5368583049ef41f168c74129112a7b16e352f7d60acbe711370",
    "https://data.oireachtas.ie/ie/oireachtas/member/id/Catherine-Connolly.D.2016-10-03/house/dail/34#party-membership-9d1a950f1592383df394b2ba8b553f6353104d3939ebf6bca15d455935d9639d",
}, f"unexpected records hidden outside PartyMembership/isPartyMembershipOf query: {sorted(collection_records-party_episode_ids)}")
check(party_episode_ids<=collection_records, "some typed/isPartyMembershipOf candidate episodes are missing from direct collection enumeration")
for rec in sorted(collection_records-party_episode_ids):
    z=records[rec]
    code="Catherine-Connolly.D.2016-10-03"
    member=URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/"+code)
    graph=URIRef(GRAPH_PREFIX+"member/"+quote(code,safe=""))
    coll={URIRef(x) for x in z["collection"]}
    contained={URIRef(x) for x in z["containing"]}
    check(z["members"]=={str(member)} and z["graphs"]=={str(graph)}, f"untyped collection record {rec}: Member/owner link mismatch")
    check(len(coll)==1 and str(next(iter(coll))).endswith("/Independent"), f"untyped collection record {rec}: unexpected party collection")
    check(not z["party"] and M+"PartyMembership" not in z["types"], f"untyped collection record {rec}: named PartyMembership witness unexpectedly present")
    check(len(contained)==1, f"untyped collection record {rec}: missing/ambiguous containing OireachtasMembership")
    check((member,URIRef(M+"hasMembersMembership"),URIRef(rec),graph) in quads, f"untyped collection record {rec}: direct Member link missing in raw quads")
    check((URIRef(rec),URIRef(M+"memberOfCollection"),next(iter(coll)),graph) in quads if len(coll)==1 else False, f"untyped collection record {rec}: direct Independent collection link missing")
    check((URIRef(rec),URIRef(M+"inOireachtasMembership"),next(iter(contained)),graph) in quads if len(contained)==1 else False, f"untyped collection record {rec}: containing membership link missing")
    ru=URIRef(rec)
    check(URIRef(M+"ParliamentaryCollectionMembership") in objects(ru,str(RDF.type),graph), f"untyped collection record {rec}: missing explicit ParliamentaryCollectionMembership type")
    check(len(objects(ru,has_range,graph))==1, f"untyped collection record {rec}: missing/ambiguous collection-episode DateRange")
    expected_by_term={
        "/dail/32/Independent": ("2016-03-10T00:00:00","2016-05-30T00:00:00"),
        "/dail/33/Independent": ("2020-02-08T00:00:00","2024-11-08T00:00:00"),
        "/dail/34/Independent": ("2024-11-29T00:00:00","2025-10-25T00:00:00"),
    }
    suffix=next((k for k in expected_by_term if k in str(next(iter(coll)))),None) if len(coll)==1 else None
    check(suffix is not None, f"untyped collection record {rec}: unexpected Independent term")
    if suffix is not None:
        episode_ranges=objects(ru,has_range,graph)
        er=next(iter(episode_ranges)) if len(episode_ranges)==1 else None
        es=objects(er,start_p,graph) if er else set(); ee=objects(er,end_p,graph) if er else set()
        check(er is not None and range_types in objects(er,str(RDF.type),graph) and len(es)==1 and len(ee)==1
              and all(is_typed_date(v) for v in es|ee), f"untyped collection record {rec}: invalid/ambiguous own interval")
        if len(es)==1 and len(ee)==1:
            check((str(next(iter(es))),str(next(iter(ee))))==expected_by_term[suffix], f"untyped collection record {rec}: own interval does not match expected term evidence")
        parent=next(iter(contained)) if len(contained)==1 else None
        parent_terms=objects(parent,M+"inHouseTerm",graph) if parent else set()
        parent_ranges=objects(parent,has_range,graph) if parent else set()
        check(parent is not None and URIRef(M+"OireachtasMembership") in objects(parent,str(RDF.type),graph)
              and len(parent_terms)==1 and len(parent_ranges)==1, f"untyped collection record {rec}: containing parliamentary membership/type/term missing or ambiguous")
        if len(parent_terms)==1:
            check(suffix.split("/Independent")[0] in str(next(iter(parent_terms))), f"untyped collection record {rec}: parent term conflicts with collection scope")
        if len(parent_ranges)==1:
            pr=next(iter(parent_ranges)); ps=objects(pr,start_p,graph); pe=objects(pr,end_p,graph)
            check(range_types in objects(pr,str(RDF.type),graph) and len(ps)==1 and len(pe)<=1
                  and all(is_typed_date(v) for v in ps|pe), f"untyped collection record {rec}: invalid/ambiguous parent-membership interval")
            if len(ps)==1:
                check(day(next(iter(ps)))<=ASOF, f"untyped collection record {rec}: parent starts after asOf")
            check(not active(es,ee), f"untyped collection record {rec}: Independent collection episode unexpectedly current at asOf")
    print("NON-PARTY COLLECTION WITNESS",rec,"collection",sorted(z["collection"]),"parent",sorted(z["containing"]),"own dates", sorted(map(str,es)) if suffix else [], sorted(map(str,ee)) if suffix else [],"term",sorted(map(str,parent_terms)) if suffix else [])
print("Direct Member-link enumeration: rows",len(ml_rows),"Members",len(ml_members),"unique records",len(records),"collection records",len(collection_records),"candidate-party typed/party records",len(party_episode_ids),"extra Independent records",len(collection_records-party_episode_ids))

# Check the repeated captures against primary byte hashes. Identical hashes establish
# repeatability of each bounded query result, not transactionality or source completeness.
stability=json.loads((DEV/"stability.json").read_text())
stable_checks=stability.get("checks",[])
check(len(stable_checks)==16, f"expected 16 repeated-query checks, found {len(stable_checks)}")
for item in stable_checks:
    qname=item.get("query","").removesuffix(".rq")
    check(item.get("same_typed_binding_multiset") is True, f"stability check failed for {qname}")
    check(qname in captures, f"stability check references missing capture {qname}")
    if qname not in captures: continue
    manifest,primary_rows=captures[qname]
    second=item.get("second_capture",{})
    check(item.get("rows")==len(primary_rows)==sum(p.get("rows",0) for p in second.get("pages",[])), f"stability row-count mismatch for {qname}")
    check(manifest.get("query_sha256")==second.get("query_sha256"), f"stability query mismatch for {qname}")
    prim=[(p.get("offset"),p.get("rows"),p.get("sha256")) for p in manifest.get("pages",[])]
    sec=[(p.get("offset"),p.get("rows"),p.get("sha256")) for p in second.get("pages",[])]
    check(prim==sec, f"stability page hash mismatch for {qname}")
print("Repeated sequential query manifests: checks",len(stable_checks),"matching page hashes",sum(bool(x.get("same_typed_binding_multiset")) for x in stable_checks))

# Validate curated identity links in their independent owner graph (labels are not used to join Members).
identity_graph=URIRef(GRAPH_PREFIX+"political-affiliations/identities")
for party_uri,identity_uri,label in [
    ("https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_Fáil","https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail","Fianna Fáil"),
    ("https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Sinn_Féin","https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein","Sinn Féin")]:
    pu=URIRef(party_uri); iu=URIRef(identity_uri); party_graph=URIRef(GRAPH_PREFIX+"parties")
    check((pu,URIRef(M+"hasPoliticalAffiliationIdentity"),iu,identity_graph) in quads, f"party {pu}: missing exact curated identity link in identity graph")
    check((iu,RDF.type,URIRef(M+"PoliticalAffiliationIdentity"),identity_graph) in quads, f"identity {iu}: missing explicit type in identity owner graph")
    check(any(str(v)==label for v in objects(iu,SKOS+"prefLabel",identity_graph)), f"identity {iu}: label missing in identity owner graph")

check(not incomplete_party_episodes, f"candidate-party capture has incomplete typed episodes: {incomplete_party_episodes}")
check(len(party_facts)==37, f"expected 37 complete distinct party episodes from member-scoped capture, found {len(party_facts)}")

# Count exact current recorded candidate-party facts for K; accept distinct people only after all checks.
current_p_by_code=defaultdict(list)
for member,code,ep,party,pm,term,er,graph,pm_ok,ep_ok,pterms,party_owner,ptypes in party_facts:
    local=str(party)
    relevant_party=(local.endswith("/Fianna_Fáil") and (local.startswith("https://data.oireachtas.ie/ie/oireachtas/party/dail/34/") or local.startswith("https://data.oireachtas.ie/ie/oireachtas/party/seanad/27/")))
    if relevant_party:
        print("CURRENT-TERM FF candidate fact",code,"member",member,"party",party,"parent",pm,"term",term,"episode",ep,"partyTerm",sorted(map(str,pterms)),"pm_ok",pm_ok,"episode_ok",ep_ok,"owner",graph)
        if pm_ok and ep_ok and str(term) in periods and str(term) in {str(t) for t in pterms}:
            current_p_by_code[code].append((member,ep,party,pm,term))
    if local.endswith("/Sinn_Féin") and local.startswith("https://data.oireachtas.ie/ie/oireachtas/party/dail/34/") and pm_ok and ep_ok:
        print("CURRENT-TERM SF candidate fact",code,"party",party,"parent",pm,"term",term,"episode",ep,"partyTerm",sorted(map(str,pterms)),"owner",graph)

active_codes={c for m,l,c,n,r,g in active_K}
intersection=set(active_codes)&set(current_p_by_code)
print("K active memberCodes:",", ".join(sorted(active_codes)))
print("P (active exact candidate Member records in current Dail34/Seanad27 FF):",", ".join(sorted(current_p_by_code)))
print("K intersect P (Member-only; no Committee-term equality):",", ".join(sorted(intersection)))

# R + P: current Dail34 Dublin Central representation crossed only to party episode
# sharing exact Member, parent OireachtasMembership IRI and term.
_,rep_rows=captures["representation"]
R=[]; R_all=[]; seen_R=set()
for row in rep_rows:
    link=iri(termval(row,"membership")); member=iri(termval(row,"member")); code=termval(row,"code"); term=iri(termval(row,"term")); con=iri(termval(row,"constituency")); g=iri(termval(row,"g")); rng=iri(termval(row,"range"))
    if not link or not member or not code or not term or not g: continue
    key=(member,link,code,term,con,g,rng)
    if key in seen_R: continue
    seen_R.add(key)
    if term!=URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34") or con!=URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Central"): continue
    if ((member,URIRef(M+"hasMembersMembership"),link,g) not in quads
        or (link,URIRef(M+"inHouseTerm"),term,g) not in quads
        or (link,URIRef(M+"isRepresentativeFrom"),con,g) not in quads
        or (link,RDF.type,URIRef(M+"DailMembership"),g) not in quads):
        # Query type may be reasoner-derived; this condition asks explicit DailMembership fact.
        print("R EXPLICIT STRUCTURE GAP",code,link)
        continue
    rstart=objects(rng,start_p,g); rend=objects(rng,end_p,g)
    valid=(range_types in objects(rng,str(RDF.type),g) and len(rstart)==1 and len(rend)<=1
           and all(is_typed_date(x) for x in rstart|rend))
    if valid:
        R_all.append((member,code,link,term,con,rng,g,active(rstart,rend),rstart,rend))
        if active(rstart,rend): R.append((member,code,link,term,con,rng,g))
check(len(R_all)==5, f"expected five recorded Dublin-Central term-34 memberships, found {len(R_all)}")
print("R recorded identities and asOf status:",[(x[1],x[7],sorted(map(str,x[8])),sorted(map(str,x[9]))) for x in R_all])
print("R current Member/pm candidates:",", ".join(sorted(x[1] for x in R)))

rp=[]
for member,code,pm,term,con,rng,g in R:
    for fact in party_facts:
        mem2,code2,ep,party,party_pm,party_term,er,pg,pm_ok,ep_ok,pterms,powner,ptypes=fact
        if mem2!=member or party_pm!=pm or party_term!=term: continue
        if not str(party).endswith("/Sinn_Féin"): continue
        if pm_ok and ep_ok and str(term) in periods and str(term) in {str(t) for t in pterms}:
            rp.append((member,code,pm,term,con,ep,party))
print("R∩P exact Member+same-parent-pm+same-term:",[(x[1],str(x[2]),str(x[6])) for x in rp])

# Historical evidence that could otherwise be accidentally treated as current.
print("Historical committee owner candidates:")
_,owner_rows=captures["committee-owners"]
for r in owner_rows:
    print(" ",termval(r,"committee"),"term",termval(r,"term"),"range",termval(r,"range"),"start",termval(r,"start"),"end",termval(r,"end"))

# Explicitly state coverage/completeness boundaries, from capture structures and query text.
print("Scope notes: sequential SELECT captures; finite query predicate/VALUES slices; not a transaction; not source-completeness or provenance certification.")
prov_manifest,prov_rows=captures["provenance-presence"]
print("provenance-presence rows:",len(prov_rows),"(a zero-row bounded diagnostic is not completeness certification)")

if errors:
    print("\nCHECK FAILURES")
    for e in errors: print(" -",e)
    sys.exit(1)
print("\nIndependent raw-evidence checks: PASS (not a kernel or oracle pass).")
