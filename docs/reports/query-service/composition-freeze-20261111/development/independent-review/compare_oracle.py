#!/usr/bin/env python3
"""Compare the regenerated oracle to an independent derivation from evidence.nq."""
from __future__ import annotations
import json, re, sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote
from rdflib import Dataset, URIRef, Literal
from rdflib.namespace import RDF

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd().resolve()
DEV=ROOT/'docs/reports/query-service/composition-freeze-20261111/development'
ASOF=date(2026,11,11)
A='https://data.oireachtas.ie/ontology#'; M='https://data.oireachtas.ie/ontology/members#'
DCT='http://purl.org/dc/terms/'; DCAT='http://www.w3.org/ns/dcat#'
FOAF='http://xmlns.com/foaf/0.1/'; SKOS='http://www.w3.org/2004/02/skos/core#'
G='https://data.oireachtas.ie/graph/'; MEMBER_G=G+'member/'; PARTIES=URIRef(G+'parties')
IDENTITIES=URIRef(G+'political-affiliations/identities'); HOUSES=URIRef(G+'houses')
DATE_RANGE=URIRef(M+'DateRange'); errors=[]
def ck(ok,msg):
    if not ok: errors.append(msg)
def U(x): return URIRef(x) if x else None
def objs(s,p,g): return {o for ss,pp,o,gg in quads if ss==s and pp==U(p) and gg==g}
def quads_for(s=None,p=None,o=None,g=None):
    return {(ss,pp,oo,gg) for ss,pp,oo,gg in quads if (s is None or ss==U(s)) and (p is None or pp==U(p)) and (o is None or oo==U(o)) and (g is None or gg==U(g))}
def date_day(v):
    if not isinstance(v,Literal) or str(v.datatype)!='http://www.w3.org/2001/XMLSchema#dateTime' or v.language is not None: return None
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).date()
    except ValueError: return None
def scalar(v):
    if v is None: return None
    return {'datatype':str(v.datatype),'type':'literal','value':str(v)}
def active(starts,ends):
    if len(starts)!=1 or len(ends)>1:return False
    s=date_day(next(iter(starts))); e=date_day(next(iter(ends))) if ends else None
    return s is not None and s<=ASOF and (not ends or (e is not None and ASOF<=e))
def interval(resource,graph,link=M+'hasMembershipDateRange',startp=M+'StartDate',endp=M+'EndDate',expected_type=DATE_RANGE):
    rs=objs(resource,link,graph)
    ck(len(rs)==1,f'{resource}: expected exactly one interval range via {link}, got {len(rs)}')
    if len(rs)!=1: return None
    r=next(iter(rs)); types=objs(r,str(RDF.type),graph); starts=objs(r,startp,graph); ends=objs(r,endp,graph)
    ck(types=={expected_type},f'{resource}: interval range type/graph mismatch {types}')
    ck(len(starts)==1 and len(ends)<=1 and all(date_day(v) is not None for v in starts|ends),f'{resource}: missing/conflicting/untypeable interval dates')
    if len(starts)!=1 or len(ends)>1 or any(date_day(v) is None for v in starts|ends): return None
    start=next(iter(starts)); end=next(iter(ends)) if ends else None
    out={'currentAtAsOf':active(starts,ends),'end':scalar(end),'graph':str(graph),'range':str(r),
         'rangeType':str(expected_type),'resource':str(resource),'start':scalar(start)}
    return out

ds=Dataset(default_union=True); ds.parse(DEV/'evidence.nq',format='nquads')
quads={(s,p,o,g) for s,p,o,g in ds.quads((None,None,None,None))}
oracle=json.loads((DEV/'oracle.json').read_text())
def v(row,k): return row[k]['value'] if k in row else None

# Derive current terms directly from captured house-owner assertions.
current_terms={}
for t in {s for s,p,o,g in quads if p==RDF.type and o in {U(A+'DailTerm'),U(A+'SeanadTerm')} and g==HOUSES}:
    periods=objs(t,DCT+'temporal',HOUSES)
    if len(periods)!=1: continue
    per=next(iter(periods)); starts=objs(per,DCAT+'startDate',HOUSES); ends=objs(per,DCAT+'endDate',HOUSES)
    if U(DCT+'PeriodOfTime') in objs(per,str(RDF.type),HOUSES) and active(starts,ends):
        current_terms[str(t)]=interval(t,HOUSES,DCT+'temporal',DCAT+'startDate',DCAT+'endDate',U(DCT+'PeriodOfTime'))
ck(set(current_terms)=={
 'https://data.oireachtas.ie/ie/oireachtas/house/dail/34',
 'https://data.oireachtas.ie/ie/oireachtas/house/seanad/27'},f'raw current-term set unexpected: {sorted(current_terms)}')
ck(oracle.get('asOf')==ASOF.isoformat(),'oracle asOf differs from frozen date')

# Capture order is part of the comparison: use first occurrence in the raw, explicitly
# ORDER BY candidate-party SELECT result, never an evaluator sort of oracle output.
pcap=DEV/'captures/candidate-party'; pmanifest=json.loads((pcap/'capture.json').read_text()); prows=[]
for pg in pmanifest['pages']: prows += json.loads((pcap/pg['file']).read_text())['results']['bindings']
party_order=defaultdict(list)
for r in prows:
    m=v(r,'member'); ep=v(r,'episode')
    if m and ep and ep not in party_order[m]: party_order[m].append(ep)
party_rank={m:{ep:i for i,ep in enumerate(eps)} for m,eps in party_order.items()}

# Raw graph facts become typed oracle-style witness records; nothing is read from oracle
# to discover or select witnesses.
def get_party_witnesses(member,member_graph):
    found=[]
    episodes=objs(member,M+'hasMembersMembership',member_graph)
    order=party_rank.get(str(member),{})
    for ep in sorted(episodes,key=lambda x:order.get(str(x),len(order))):
        if U(M+'PartyMembership') not in objs(ep,str(RDF.type),member_graph): continue
        if str(ep) not in order:
            ck(False,f'{ep}: raw graph PartyMembership absent from frozen party query order')
        parties=objs(ep,M+'isPartyMembershipOf',member_graph)
        parents=objs(ep,M+'inOireachtasMembership',member_graph)
        if len(parties)!=1 or len(parents)!=1:
            ck(False,f'{ep}: party/parent link missing or ambiguous')
            continue
        party=next(iter(parties)); parent=next(iter(parents))
        terms=objs(parent,M+'inHouseTerm',member_graph)
        identities=objs(party,M+'hasPoliticalAffiliationIdentity',IDENTITIES)
        if len(terms)!=1 or len(identities)!=1:
            ck(False,f'{ep}: parent term/curated affiliation identity missing or ambiguous')
            continue
        term=next(iter(terms)); affiliation=next(iter(identities))
        pterms=objs(party,M+'activeDuringTerm',PARTIES)
        if term not in pterms:
            ck(False,f'{ep}: party activeDuringTerm does not match parent term')
        ep_iv=interval(ep,member_graph)
        pm_iv=interval(parent,member_graph)
        if ep_iv is None or pm_iv is None: continue
        pt=re.search(r'/house/(dail|seanad)/(\d+)$',str(term))
        if not pt:
            ck(False,f'{ep}: unrecognized term IRI {term}'); continue
        house=pt.group(1)
        ck(U(M+'OireachtasMembership') in objs(parent,str(RDF.type),member_graph),f'{parent}: missing explicit OireachtasMembership type')
        ck((member,U(M+'hasMembersMembership'),parent,member_graph) in quads,
           f'{ep}: containing membership is not independently linked from same Member in owner graph')
        ck((ep,U(M+'memberOfCollection'),party,member_graph) in quads,
           f'{ep}: party collection relation differs from isPartyMembershipOf')
        witness={'affiliation':str(affiliation),'affiliationGraph':str(IDENTITIES),
          'currentAtAsOf':ep_iv['currentAtAsOf'] and pm_iv['currentAtAsOf'],
          'episode':str(ep),'episodeInterval':ep_iv,'episodeType':M+'PartyMembership',
          'memberGraph':str(member_graph),
          'parliamentary':{'house':house,'interval':pm_iv,'membership':str(parent),'term':str(term)},
          'party':str(party),'partyGraph':str(PARTIES)}
        found.append({'object':witness,'term':str(term),'party':str(party),'affiliation':str(affiliation),
                      'episodeCurrent':ep_iv['currentAtAsOf'],'parentCurrent':pm_iv['currentAtAsOf'],
                      'parent':str(parent),'episode':str(ep),'member':str(member)})
    return found

def serialized_in_raw_order(xs):
    return xs

def compare_witnesses(actual,expected,label):
    actual=actual if isinstance(actual,list) else []
    akeys=[json.dumps(x,sort_keys=True,ensure_ascii=False) for x in actual]
    ekeys=[json.dumps(x,sort_keys=True,ensure_ascii=False) for x in expected]
    ck(len(akeys)==len(set(akeys)),f'{label}: duplicate oracle witnesses')
    ck(akeys==ekeys,f'{label}: ordered witness array differs: oracle {len(actual)}, raw-derived {len(expected)}')

# Committee member candidate identities and all per-candidate dispositions.
cap=DEV/'captures/committee-members'
manifest=json.loads((cap/'capture.json').read_text()); rows=[]
for pg in manifest['pages']: rows += json.loads((cap/pg['file']).read_text())['results']['bindings']
def v(row,k): return row[k]['value'] if k in row else None
committee_rows={}
for r in rows:
    m=v(r,'member'); link=v(r,'membership'); graph=v(r,'g')
    if not m or not link or not graph: continue
    rec=(m,link,v(r,'code'),v(r,'name'),v(r,'range'),graph)
    committee_rows[link]=rec
ck(len(committee_rows)==15,f'committee query has {len(committee_rows)} distinct linked candidates, expected 15')
Kcase=oracle['K+P']; kd={d.get('committeeMembership'):d for d in Kcase.get('candidateDispositions',[])}
committee=U('https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts')
committees_graph=U(G+'committees')
committee_terms=objs(committee,M+'committeeInHouseTerm',committees_graph)
committee_iv=interval(committee,committees_graph,M+'hasCommitteeDateRange')
ck(Kcase.get('committee')==str(committee),'K+P selected committee IRI mismatch')
ck(committee_terms=={U('https://data.oireachtas.ie/ie/oireachtas/house/dail/34')},'K+P current committee owner term differs from raw owner graph')
ck(Kcase.get('committeeTerm')==str(next(iter(committee_terms))) if len(committee_terms)==1 else False,'K+P oracle committeeTerm differs from raw owner graph')
ck(Kcase.get('committeeOwnerInterval')==committee_iv,'K+P committee-owner interval differs from raw owner graph')
ck(len(kd)==len(Kcase.get('candidateDispositions',[])),'K+P oracle repeats committee membership dispositions')
ck(set(kd)==set(committee_rows),f'K+P candidate disposition membership set differs: missing {set(committee_rows)-set(kd)}, extra {set(kd)-set(committee_rows)}')
ck([d.get('committeeMembership') for d in Kcase.get('candidateDispositions',[])]==list(committee_rows),
   'K+P candidate disposition order differs from captured committee query order')
kqual=set(); kqual_order=[]
for link,(m,link,code,name,range_iri,graph_s) in committee_rows.items():
    g=U(graph_s); member=U(m); d=kd.get(link)
    if d is None: continue
    owner_graphs={gg for ss,pp,oo,gg in quads if ss==member}
    ck(owner_graphs=={g},f'{m}: candidate member owner graph not exact')
    iv=interval(U(link),g)
    party_all=get_party_witnesses(member,g)
    examined=[x['object'] for x in party_all if x['term'] in current_terms and U(x['term']) in objs(U(x['party']),M+'activeDuringTerm',PARTIES)]
    target=[x['object'] for x in party_all if x['affiliation']=='https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail' and x['term'] in current_terms and x['episodeCurrent'] and x['parentCurrent']]
    target=serialized_in_raw_order(target); examined=serialized_in_raw_order(examined)
    expected_qual=bool(iv and iv['currentAtAsOf'] and target)
    reasons=[]
    if not (iv and iv['currentAtAsOf']): reasons.append('committee membership interval excludes asOf')
    if not target: reasons.append('no independently current target-affiliation party witness in either current House')
    ck(d.get('member')==m,f'K+P {name}: Member IRI mismatch')
    ck(d.get('memberGraph')==graph_s,f'K+P {name}: member graph mismatch')
    ck(d.get('name')==name,f'K+P {name}: display name mismatch')
    ck(objs(member,FOAF+'name',g)=={Literal(name)},f'K+P {name}: rendered display does not match explicit Member foaf:name in owner graph')
    ck(d.get('committeeInterval')==iv,f'K+P {name}: committee interval does not match raw owner-graph facts')
    ck(d.get('qualifies') is expected_qual,f'K+P {name}: qualifies flag mismatch')
    ck(d.get('exclusionReasons')==reasons,f'K+P {name}: exclusion reasons differ: {d.get("exclusionReasons")} != {reasons}')
    compare_witnesses(d.get('partyWitnesses'),target,f'K+P {name} partyWitnesses')
    compare_witnesses(d.get('examinedCurrentTermPartyWitnesses'),examined,f'K+P {name} examinedCurrentTermPartyWitnesses')
    if expected_qual: kqual.add(m); kqual_order.append(m)
ck(len(kqual)==len(set(kqual)),'K+P qualifying Member set not unique')
ck(Kcase.get('expectedMembers',[])==kqual_order,
   f'K+P expectedMembers order/content differs from raw candidate order filtered by independently derived dispositions: {Kcase.get("expectedMembers")} vs {kqual_order}')

# Representation candidates: exact Member + same ParliamentaryMembership + same term.
cap=DEV/'captures/representation'; manifest=json.loads((cap/'capture.json').read_text()); rows=[]
for pg in manifest['pages']: rows += json.loads((cap/pg['file']).read_text())['results']['bindings']
rep_rows={}
for r in rows:
    m=v(r,'member'); link=v(r,'membership'); term=v(r,'term'); con=v(r,'constituency'); graph=v(r,'g')
    if not (m and link and term and con and graph): continue
    rep_rows[link]=(m,link,v(r,'code'),v(r,'name'),term,con,v(r,'range'),graph)
rp_expected=set(); rqual=[]; rp_expected_order=[]
Rcase=oracle['R+P']; rd={d.get('representation',{}).get('membership'):d for d in Rcase.get('candidateDispositions',[])}
ck(len(rd)==len(Rcase.get('candidateDispositions',[])),'R+P oracle repeats representation membership dispositions')
ck(set(rd)==set(rep_rows),f'R+P candidate disposition membership set differs: missing {set(rep_rows)-set(rd)}, extra {set(rd)-set(rep_rows)}')
ck([d.get('representation',{}).get('membership') for d in Rcase.get('candidateDispositions',[])]==list(rep_rows),
   'R+P candidate disposition order differs from captured representation query order')
for link,(m,link,code,name,term,con,range_iri,graph_s) in rep_rows.items():
    if term!='https://data.oireachtas.ie/ie/oireachtas/house/dail/34' or con!='https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Central': continue
    member=U(m); g=U(graph_s); d=rd.get(link)
    if d is None: continue
    iv=interval(U(link),g)
    party_all=get_party_witnesses(member,g)
    examined=[x['object'] for x in party_all if x['term'] in current_terms and U(x['term']) in objs(U(x['party']),M+'activeDuringTerm',PARTIES)]
    target=[x['object'] for x in party_all if x['affiliation']=='https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein'
            and x['term']==term and x['parent']==link and x['episodeCurrent'] and x['parentCurrent']]
    target=serialized_in_raw_order(target); examined=serialized_in_raw_order(examined)
    expected_qual=bool(iv and iv['currentAtAsOf'] and target)
    reasons=[]
    if not (iv and iv['currentAtAsOf']): reasons.append('representation interval excludes asOf')
    if not target: reasons.append('no independently current target-affiliation episode on the exact representation membership')
    rep={'house':'dail','interval':iv,'membership':link,'term':term}
    ck(d.get('member')==m,f'R+P {name}: Member IRI mismatch')
    ck(d.get('memberGraph')==graph_s,f'R+P {name}: member graph mismatch')
    ck(d.get('name')==name,f'R+P {name}: display name mismatch')
    ck(objs(member,FOAF+'name',g)=={Literal(name)},f'R+P {name}: rendered display does not match explicit Member foaf:name in owner graph')
    ck(d.get('constituency')==con and d.get('constituencyGraph')==str(URIRef(G+'constituencies')),f'R+P {name}: constituency owner/witness mismatch')
    ck(d.get('representation')==rep,f'R+P {name}: representation interval/link differs from raw owner-graph facts')
    ck(d.get('qualifies') is expected_qual,f'R+P {name}: qualifies flag mismatch')
    ck(d.get('exclusionReasons')==reasons,f'R+P {name}: exclusion reasons differ: {d.get("exclusionReasons")} != {reasons}')
    compare_witnesses(d.get('partyWitnesses'),target,f'R+P {name} partyWitnesses')
    compare_witnesses(d.get('examinedCurrentTermPartyWitnesses'),examined,f'R+P {name} examinedCurrentTermPartyWitnesses')
    if expected_qual: rp_expected.add(m); rqual.append(m); rp_expected_order.append(m)
ck(len(rqual)==len(set(rqual)),'R+P has multiple qualifying representation records for same Member in frozen candidate set')
ck(Rcase.get('count')==len(rp_expected),f'R+P count mismatch: {Rcase.get("count")} != {len(rp_expected)}')
ck(Rcase.get('expectedMembers',[])==rp_expected_order,
   f'R+P expectedMembers order/content differs from raw candidate order filtered by independently derived dispositions: {Rcase.get("expectedMembers")} vs {rp_expected_order}')

# Independently resolve the named Dáil constituency in its owner graph.
constituency=U('https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Central')
constituency_graph=U(G+'constituencies')
const_types=objs(constituency,str(RDF.type),constituency_graph)
const_labels=objs(constituency,SKOS+'prefLabel',constituency_graph)
const_terms=objs(constituency,M+'constituencyInHouseTerm',constituency_graph)
ck(const_types=={U(M+'Constituencies'),U(M+'DailConstituency')},f'constituency owner types missing/conflicting: {const_types}')
ck(any(str(x)=='Dublin Central' and x.language=='en' for x in const_labels),f'constituency owner label missing: {const_labels}')
ck(const_terms=={U('https://data.oireachtas.ie/ie/oireachtas/house/dail/34')},f'constituency owner term missing/conflicting: {const_terms}')

# Top-level current-term claims are exact comparisons too.
for house,termuri in [('dail','https://data.oireachtas.ie/ie/oireachtas/house/dail/34'),('seanad','https://data.oireachtas.ie/ie/oireachtas/house/seanad/27')]:
    expected={'term':termuri,'type':A+('DailTerm' if house=='dail' else 'SeanadTerm'),'interval':current_terms.get(termuri)}
    ck(oracle.get('currentTerms',{}).get(house)==expected,f'oracle currentTerms.{house} differs from raw typed house-owner evidence')

print('Oracle comparison candidate counts: K+P',len(committee_rows),'qualifying',len(kqual),'R+P',len(rep_rows),'qualifying',len(rp_expected))
print('Independent qualifying K+P Members:',sorted(kqual))
print('Independent qualifying R+P Members:',sorted(rp_expected))
print('Disposition and witness arrays compared against raw evidence; oracle not used to derive candidates.')
if errors:
    print('\nCOMPARISON FAILURES')
    for e in errors: print(' -',e)
    sys.exit(1)
print('\nIndependent raw-evidence/oracle comparison: PASS (not a kernel pass).')
