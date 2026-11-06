#!/usr/bin/env python3
"""Independent direct-SPARQL oracle construction; run BEFORE /ask evaluation.

No Query Service implementation imports. Semantic authority is the public
2.26.0 contract; facts are the local accepted-evidence slice, not world truth.
"""
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location("collector", Path(__file__).with_name("evaluate-query-generalisation.py"))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
P = """PREFIX a: <https://data.oireachtas.ie/ontology#>
PREFIX m: <https://data.oireachtas.ie/ontology/members#>
PREFIX f: <http://xmlns.com/foaf/0.1/>
PREFIX s: <http://www.w3.org/2004/02/skos/core#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
"""
G = "https://data.oireachtas.ie/graph/"
H = "https://data.oireachtas.ie/ie/oireachtas/house/"
ASOF = "2026-11-06"
CASES = []


def ordinal(number):
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def add(question, capability, category, query=None, expected="answer", properties="", **fields):
    CASES.append(dict(id=f"H{len(CASES)+1:02}", question=question, capability=capability,
                      category=category, expected_outcome=expected, acceptable_properties=properties,
                      evidence_query=(P + query if query else None), **fields))


def select(cols, body):
    return f"SELECT DISTINCT {cols} WHERE {{ {body} }} ORDER BY {cols}"


def member(name, var="person", graph="g"):
    return f'GRAPH ?{graph} {{ ?{var} a a:Member; f:name {json.dumps(name, ensure_ascii=False)}. }} FILTER(STRSTARTS(STR(?{graph}), "{G}member/")) '


def path(term, var="person", ms="membership", graph="g", house="Dail"):
    return f"GRAPH ?{graph} {{ ?{var} m:hasMembersMembership ?{ms}. ?{ms} a m:{house}Membership; m:inHouseTerm <{H}{house.lower()}/{term}>. }} "


def interval(var, start, end, graph="g"):
    return f"GRAPH ?{graph} {{ ?{var} m:hasMembershipDateRange ?{var}Range. ?{var}Range m:StartDate ?{start}. OPTIONAL {{ ?{var}Range m:EndDate ?{end}. }} }} "


def at(start, end, day=ASOF):
    return f'FILTER(SUBSTR(STR(?{start}),1,10) <= "{day}" && (!BOUND(?{end}) || SUBSTR(STR(?{end}),1,10) >= "{day}")) '


def constituency(names, term, point=None, party=None):
    names = [names] if isinstance(names, str) else names
    body = f'GRAPH ?g {{ ?person a a:Member; f:name ?name; m:hasMembersMembership ?membership. ?membership a m:DailMembership; m:inHouseTerm <{H}dail/{term}>; m:isRepresentativeFrom ?constituency. }} FILTER(STRSTARTS(STR(?g), "{G}member/")) '
    body += f'GRAPH <{G}constituencies> {{ ?constituency m:constituencyInHouseTerm <{H}dail/{term}>; s:prefLabel ?constituencyLabel. VALUES ?constituencyLabel {{ ' + " ".join(json.dumps(n,ensure_ascii=False)+"@en" for n in names) + " } } "
    if point:
        body += interval("membership", "ms", "me") + at("ms", "me", point)
    if party:
        body += party_path(party, term, "Dail", current=point)
    return body


def party_path(party, term, house="Dail", current=None):
    b = f'GRAPH ?g {{ ?person m:hasMembersMembership ?episode. ?episode a m:PartyMembership; m:inOireachtasMembership ?membership; m:isPartyMembershipOf ?party. }} GRAPH <{G}parties> {{?party a m:ParliamentaryParty; m:activeDuringTerm <{H}{house.lower()}/{term}>.}} GRAPH <{G}political-affiliations/identities> {{ ?party m:hasPoliticalAffiliationIdentity ?affiliation. ?affiliation a m:PoliticalAffiliationIdentity; s:prefLabel {json.dumps(party,ensure_ascii=False)}@en. }} '
    b += interval("membership", "ms", "me") + interval("episode", "ps", "pe")
    b += "FILTER((!BOUND(?me) || ?ps <= ?me) && (!BOUND(?pe) || ?ms <= ?pe)) "
    if current:
        b += at("ms", "me", current) + at("ps", "pe", current)
    return b


def anchor(name, term):
    b = member(name, "anchor", "ag") + path(term, "anchor", "am", "ag")
    b += f"GRAPH ?ag {{?am m:isRepresentativeFrom ?constituency.}} GRAPH ?g {{?person a a:Member; f:name ?name; m:hasMembersMembership ?membership. ?membership a m:DailMembership; m:inHouseTerm <{H}dail/{term}>; m:isRepresentativeFrom ?constituency.}} GRAPH <{G}constituencies> {{?constituency m:constituencyInHouseTerm <{H}dail/{term}>.}} FILTER(?person != ?anchor) "
    return b


def office(label, start=None, end=None, name=None):
    b = f'GRAPH ?g {{?person a a:Member; f:name ?name; m:hasOfficeHolding ?holding. ?holding a m:OfficeHolding; m:heldOffice ?office.}} GRAPH <{G}offices> {{?office a m:NamedOffice; s:prefLabel {json.dumps(label,ensure_ascii=False)}@en.}} '
    b += interval("holding", "start", "end")
    if name:
        b += member(name)
    if start:
        b += f'FILTER(SUBSTR(STR(?start),1,10) <= "{end or start}" && (!BOUND(?end) || SUBSTR(STR(?end),1,10) >= "{start}")) '
    return b


def construct():
    for name in ("Joan Burton", "Róisín Shortall"):
        add(f"Find the parliamentary record for Deputy {name}.", "member_lookup", "simple", select("?person ?name", member(name)+"GRAPH ?g {?person f:name ?name; m:hasMembersMembership ?membership. ?membership a m:DailMembership.}"))
    add("Which constituency does Alan Kelly represent now?", "current representation", "entities-periods", select("?person ?constituency ?label", member("Alan Kelly")+path(34)+interval("membership","start","end")+at("start","end")+f"GRAPH ?g {{?membership m:isRepresentativeFrom ?constituency.}} GRAPH <{G}constituencies> {{?constituency s:prefLabel ?label; m:constituencyInHouseTerm <{H}dail/34>.}}"))
    add("In Eamon Gilmore's latest recorded Dáil term, what was his constituency?", "latest recorded term + representation", "paraphrase", select("?person ?term ?start ?constituency ?label", member("Eamon Gilmore")+f"GRAPH ?g {{?person m:hasMembersMembership ?ms. ?ms a m:DailMembership; m:inHouseTerm ?term; m:isRepresentativeFrom ?constituency.}} GRAPH <{G}houses> {{?term a a:DailTerm; dct:temporal/dcat:startDate ?start.}} GRAPH <{G}constituencies> {{?constituency s:prefLabel ?label.}}"), properties="Choose maximum House-owned start date, not an election event.", oracle="latest")
    add("List every constituency Frances Fitzgerald has represented in the Dáil, keeping the terms separate.", "career representation", "paraphrase", select("?person ?term ?constituency ?label", member("Frances Fitzgerald")+f"GRAPH ?g {{?person m:hasMembersMembership ?ms. ?ms a m:DailMembership; m:inHouseTerm ?term; m:isRepresentativeFrom ?constituency.}} GRAPH <{G}constituencies> {{?constituency s:prefLabel ?label; m:constituencyInHouseTerm ?term.}}"))
    for name in ("Brendan Howlin", "Catherine Connolly"):
        add(f"How many distinct Dáil terms appear in {name}'s membership record?", "term_count", "aggregation", select("?term", member(name)+f"GRAPH ?g {{?person m:hasMembersMembership ?ms. ?ms a m:DailMembership; m:inHouseTerm ?term.}} GRAPH <{G}houses> {{?term a a:DailTerm.}}"), oracle="count")
    for x,y in (("Joan Burton","Alan Kelly"),("Dick Spring","Brendan Howlin"),("Mary Robinson","Ivana Bacik")):
        add(f"Show the Dáil terms common to the service records of {x} and {y}.", "shared_dail_terms", "novel-composition", select("?term", member(x,"one","g1")+member(y,"two","g2")+f"GRAPH ?g1 {{?one m:hasMembersMembership ?m1. ?m1 a m:DailMembership; m:inHouseTerm ?term.}} GRAPH ?g2 {{?two m:hasMembersMembership ?m2. ?m2 a m:DailMembership; m:inHouseTerm ?term.}} GRAPH <{G}houses> {{?term a a:DailTerm.}}"), properties="Exact Dáil intersection; no Seanad substitution. An empty local intersection is acceptable with coverage qualification.")
    for t1,t2 in ((25,28),(30,32)):
        add(f"Give me the Members whose records include both the {t1}th and {t2}nd Dáil.", "two-term member intersection", "novel-composition", select("?person ?name", "GRAPH ?g {?person a a:Member; f:name ?name.}"+path(t1)+path(t2,ms="second")))
    for place,term in (("Kerry North",24),("Wexford",30),("Tipperary",32)):
        add(f"Give the recorded TD roster for {place} in Dáil number {term}.", "constituency + exact term", "entities-periods", select("?person ?name", constituency(place,term)))
    for place,term,word in (("Cork South-West",31,"the 31st Dáil"),("Galway West",34,"this Dáil"),("Kerry North",24,"the 24th Dáil")):
        add(f"Count the distinct people recorded as representing {place} in {word}.", "constituency member count", "aggregation", select("?person ?name", constituency(place,term)), oracle="count")
    add("Who are the TDs for Louth today?", "current constituency", "paraphrase", select("?person ?name", constituency("Louth",34,ASOF)))
    add("How many different TDs represent Louth right now?", "current constituency count", "aggregation", select("?person ?name", constituency("Louth",34,ASOF)), oracle="count")
    add("Who represented Dublin Bay North on 15 June 2019?", "membership date point", "entities-periods", select("?person ?name", constituency("Dublin Bay North",32,"2019-06-15")))
    add("As of 1 July 2021, how many distinct Members represented Dublin Bay North?", "dated membership count", "aggregation", select("?person ?name", constituency("Dublin Bay North",33,"2021-07-01")), oracle="count")
    for party,place,term in (("Labour Party","Wexford",31),("Fine Gael","Cork South-Central",32)):
        add(f"Which {party} Members represented {place} during the {term}st Dáil?", "party + representation + overlap", "novel-composition", select("?person ?name", constituency(place,term,party=party)))
    for party,term in (("Labour Party",31),("Sinn Féin",32)):
        add(f"Count distinct recorded {party} Members in Dáil {term}, rather than seats.", "party term count", "aggregation", select("?person ?name", "GRAPH ?g {?person a a:Member; f:name ?name.}"+path(term)+party_path(party,term)), oracle="count")
    for party,places,term in (("Fine Gael",["Mayo","Galway West"],32),("Labour Party",["Wexford","Longford-Westmeath"],31)):
        add(f"List {party} representatives for either {places[0]} or {places[1]} in the {term}nd Dáil.", "identity OR set + party + term", "novel-composition", select("?person ?name", constituency(places,term,party=party)))
    for name,term,count in (("Brendan Howlin",32,False),("Alan Kelly",33,True),("Willie O'Dea",31,False)):
        question = (f"How many other Members shared Alan Kelly's constituency in the previous Dáil?" if count else f"Who else represented the same constituency as {name} in Dáil {term}?")
        add(question, "anchor shared constituency"+(" count" if count else ""), "novel-composition", select("?person ?name", anchor(name,term)), oracle="count" if count else "rows", properties="Exclude anchor by Member IRI; term-wide, not simultaneous service.")
    for label,start,end,phrase in (("Minister for Finance","2022-01-01","2022-12-31","during 2022"),("Tánaiste","2003-07-01",None,"on 1 July 2003"),("Taoiseach","1958-06-01","1958-06-30","at any time in June 1958"),("Minister for Finance",ASOF,None,"now")):
        add(f"Who held the office of {label} {phrase}?", "accepted office overlap", "entities-periods", select("?person ?name ?holding ?start ?end", office(label,start,end)), properties="Return accepted local matching episodes only; not an exhaustive roster or uninterrupted-service claim.")
    for name,label in (("Dick Spring","Tánaiste"),("Albert Reynolds","Taoiseach")):
        add(f"What periods was {name} {label}?", "named member office episodes", "paraphrase", select("?person ?name ?holding ?start ?end", office(label,name=name)), properties="All locally accepted episodes preserved; explicitly incomplete career evidence.")
    for start,end,phrase in (("1997-09-01","1997-09-01","on 1 September 1997"),("2024-11-01","2024-11-30","during November 2024"),("2020-02-01","2020-02-29","during February 2020")):
        add(f"Which Dáil term or terms were in existence {phrase}?", "House date/month selection", "entities-periods", select("?term ?label ?start ?end", f'GRAPH <{G}houses> {{?term a a:DailTerm; s:prefLabel ?label; dct:temporal ?period. ?period dcat:startDate ?start. OPTIONAL {{?period dcat:endDate ?end.}} }} FILTER(SUBSTR(STR(?start),1,10) <= "{end}" && (!BOUND(?end) || SUBSTR(STR(?end),1,10) >= "{start}"))'), properties="Term existence, not actual sittings; month uses full month.")
    add("What was the seat complement of the 28th Dáil?", "seat complement", "simple", select("?seats", f"GRAPH <{G}houses> {{<{H}dail/28> a a:DailTerm; a:seats ?seats.}}"), oracle="scalar")
    add("List the parliamentary parties recorded for Dáil 30; I am not asking for groups.", "parties exact term", "simple", select("?party ?label", f"GRAPH <{G}parties> {{?party a m:ParliamentaryParty; m:activeDuringTerm <{H}dail/30>. OPTIONAL {{?party s:prefLabel ?label.}}}}"))
    cross = "GRAPH ?g {?person a a:Member; f:name ?name.}"+path(34,ms="dm")+path(27,ms="sm",house="Seanad")+interval("dm","ds","de")+interval("sm","ss","se")
    add("Which people have a membership record in both the current Dáil term and the current Seanad term, even if the periods did not overlap?", "current cross-house intersection", "novel-composition", select("?person ?name ?ds ?de ?ss ?se",cross), properties="Term-wide intersection by identity; do not imply simultaneous service.")
    common = anchor("Dick Spring",24)+party_path("Labour Party",24)+office("Tánaiste",name="Dick Spring").replace("?person","?anchor").replace("?g ","?ag ").replace("?name","?anchorName")+interval("am","ams","ame","ag")
    common += "FILTER(?start <= COALESCE(?ame,\"9999-12-31T00:00:00\"^^xsd:dateTime) && ?start <= COALESCE(?me,\"9999-12-31T00:00:00\"^^xsd:dateTime) && ?start <= COALESCE(?pe,\"9999-12-31T00:00:00\"^^xsd:dateTime) && ?ams <= ?end && ?ms <= ?end && ?ps <= ?end && ?ams <= COALESCE(?me,\"9999-12-31T00:00:00\"^^xsd:dateTime) && ?ams <= COALESCE(?pe,\"9999-12-31T00:00:00\"^^xsd:dateTime)) "
    add("Which other Labour Party Members represented Dick Spring's constituency in the 24th Dáil while he was Tánaiste?", "anchor + party + common temporal intersection", "novel-composition", select("?person ?name", common), properties="Require one common intersection of office, anchor membership, answer membership and exact party episode; no pairwise-only shortcut.")
    for party,count in (("Labour Party",False),("Fine Gael",True)):
        add((f"How many distinct current Senators belong to {party}?" if count else f"Name the current {party} Senators."), "current Seanad party"+(" count" if count else " list"), "aggregation" if count else "paraphrase", select("?person ?name", "GRAPH ?g {?person a a:Member; f:name ?name.}"+path(27,house="Seanad")+party_path(party,27,"Seanad",ASOF)), oracle="count" if count else "rows")
    prior = "GRAPH ?g {?person a a:Member; f:name ?name; m:hasMembersMembership ?dm, ?sm. ?dm a m:DailMembership; m:inHouseTerm ?dt. ?sm a m:SeanadMembership; m:inHouseTerm <"+H+"seanad/27>.} "+interval("dm","ds","de")+interval("sm","ss","se")+at("ss","se")+"FILTER(BOUND(?de) && ?de < ?ss)"
    for count in (False,True):
        add("Count the distinct current Senators with a recorded Dáil membership ending strictly before their current Seanad membership began." if count else "Name current Senators whose recorded TD service ended before their current Seanad membership started.", "current Senator + strictly prior TD"+(" count" if count else " list"), "aggregation" if count else "novel-composition", select("?person ?name", prior), oracle="count" if count else "rows", properties="Finite Dáil end strictly before the qualifying current Seanad start; equal dates/open ends excluded.")
    bill = f'GRAPH ?bg {{?bill a dl:DraftLegislationWork. ?delivery a dl:Activity; dl:created_a_realization_of ?bill; dl:forms_part_of ?process. ?process dl:had_participation ?participation. ?participation dl:had_participant_person ?person.}} FILTER(STRSTARTS(STR(?bg), "{G}bill/")) '
    # Delivery activity types vary; the exact relation path, not an invented base type, grounds sponsorship.
    bill = bill.replace("a dl:Activity; ", "")
    published = f'GRAPH ?bg {{?activity dl:forms_part_of ?process; dl:had_activity_type a:Published; dl:activity_date ?date.}} FILTER(DATATYPE(?date)=xsd:date && YEAR(?date)=2021) '
    add("How many Bills did Brendan Howlin sponsor that were published in 2021?", "Bill sponsorship + Published year count", "aggregation", select("?bill", member("Brendan Howlin")+bill+published), oracle="count", properties="Distinct Bills via sponsorship and typed Published date; not legislative year. Zero only if complete valid sponsorship/date evidence.")
    add("Show the Bills with recorded sponsorship participation by Catherine Connolly.", "member Bill sponsorship", "paraphrase", select("?bill", member("Catherine Connolly")+bill), properties="All distinct locally recorded sponsored Bills; role/primary evidence must not be invented.")
    negatives = [
        ("At which election was Alan Kelly first elected to the Dáil?", "election events", "unsupported_capability", "Do not substitute earliest membership start for an election."),
        ("For how many years in total was Dick Spring Tánaiste?", "office duration", "unsupported_capability", "Do not sum the incomplete office episode sample or answer only dates."),
        ("Which women were Members of both the 25th and 28th Dáil?", "two-term intersection + gender", "unsupported_capability", "Gender condition must not be silently omitted."),
        ("Which Dáil terms were shared by Joan Burton, Alan Kelly and Brendan Howlin?", "three-person shared terms", "unsupported_capability", "Do not reduce three people to two."),
        ("Find Deputy Murphy.", "partial Member ambiguity", "clarification_required", "Show grounded distinct candidates; no single person chosen."),
        ("Who represented western constituencies for Fine Gael in the 32nd Dáil?", "implicit geographic identity set", "clarification_required", "Ask for exact constituencies; do not invent the geographic set."),
        ("Who served simultaneously in the current Dáil and current Seanad?", "cross-house + simultaneity", "unsupported_capability", "Term-wide intersection cannot answer simultaneous service."),
        ("How many women represented Wexford in the 31st Dáil?", "constituency count + gender", "unsupported_capability", "Do not return the unfiltered Member count."),
        ("Where was Róisín Shortall born?", "external biographical fact", "unsupported_capability", "Do not invent a birthplace or query external endpoints."),
        ("Who will be Minister for Finance in 2028?", "future office holder", "unsupported_capability", "Do not reinterpret future prediction as current point lookup."),
    ]
    for q,cap,outcome,props in negatives:
        add(q,cap,"ambiguous" if outcome=="clarification_required" else "unsupported",expected=outcome,properties=props)


def main():
    construct()
    assert len(CASES) == 60
    for c in CASES:
        for n in (25, 28, 30, 31, 32):
            for wrong in (f"{n}th", f"{n}nd", f"{n}st"):
                c["question"] = c["question"].replace(wrong, ordinal(n))
    CASES[34]["question"] = "Who holds the office of Minister for Finance now?"
    # Final pre-freeze selection exercises a positive common-intersection case.
    CASES[43]["question"] = "Which other Fine Gael Members represented Enda Kenny's constituency in the 32nd Dáil while he was Taoiseach?"
    CASES[43]["evidence_query"] = CASES[43]["evidence_query"].replace('"Dick Spring"','"Enda Kenny"').replace('"Labour Party"','"Fine Gael"').replace('"Tánaiste"','"Taoiseach"').replace('/dail/24>', '/dail/32>')
    CASES[9]["expected_outcome"] = "missing_or_unaccepted_evidence"
    CASES[9]["acceptable_properties"] = "Mary Robinson has no recorded Dáil membership path. Missing prerequisite evidence must not be described as a complete historical negative. Excluded from factual-answer scoring."
    CASES[9]["evidence_guard_query"] = P + select("?person ?name ?ms", member("Mary Robinson") + "GRAPH ?g {?person f:name ?name. OPTIONAL {?person m:hasMembersMembership ?ms. ?ms a m:DailMembership.}}")
    CASES[48]["expected_outcome"] = "missing_or_unaccepted_evidence"
    CASES[48]["acceptable_properties"] = "Brendan Howlin sponsorship includes Bills with absent Published activity evidence and a conflicting multi-date Published activity. No factual count, including zero, is justified. Excluded from factual-answer scoring."
    bill_query=CASES[48]["evidence_query"]
    CASES[48]["evidence_guard_query"] = bill_query[:bill_query.index('GRAPH ?bg {?activity')] + ' OPTIONAL { GRAPH ?bg {?activity dl:forms_part_of ?process; dl:had_activity_type a:Published. OPTIONAL {?activity dl:activity_date ?date.}}} } ORDER BY ?bill'
    CASES[48]["evidence_guard_query"] = CASES[48]["evidence_guard_query"].replace('SELECT DISTINCT ?bill WHERE','SELECT DISTINCT ?bill ?activity ?date WHERE')
    env = collector.environment(int(sys.argv[1]))
    def evidence(c):
        if c.get("evidence_guard_query"):
            guard=collector.query(env,c["evidence_guard_query"])
            c["evidence_guard"]=[{k:v["value"] for k,v in row.items()} for row in guard["results"]["bindings"]]
        if c["evidence_query"]:
            response = collector.query(env,c["evidence_query"])
            c["evidence"] = [{k:v["value"] for k,v in row.items()} for row in response["results"]["bindings"]]
            c["evidence_datatypes"] = {k: sorted({v.get("datatype",v.get("xml:lang",v["type"])) for row in response["results"]["bindings"] for key,v in row.items() if key==k}) for k in response["head"]["vars"]}
            rows=c["evidence"]
            if c["expected_outcome"] != "answer":
                pass
            elif c.get("oracle")=="count":
                identity="person" if rows and "person" in rows[0] else "term" if rows and "term" in rows[0] else "bill"
                c["expected_count"]=len({r[identity] for r in rows})
            elif c.get("oracle")=="latest" and rows:
                c["expected_rows"]=[r for r in rows if r["start"]==max(x["start"] for x in rows)]
            else:
                c["expected_rows"]=rows
        else:
            c["evidence_authority"]="poc/specs/composable-query-plan-contract.json 2.26.0; public capability boundaries in docs/guides/query-service.md"
        return c
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        cases=list(pool.map(evidence,CASES))
    context_queries={
        "chronology": P+select("?term ?label ?start ?end",f"GRAPH <{G}houses> {{?term a ?type; s:prefLabel ?label; dct:temporal ?period. VALUES ?type {{a:DailTerm a:SeanadTerm}} ?period dcat:startDate ?start. OPTIONAL {{?period dcat:endDate ?end.}}}}"),
        "graph_counts": "SELECT ?g (COUNT(*) AS ?triples) WHERE {GRAPH ?g {?s ?p ?o}} GROUP BY ?g ORDER BY ?g",
        "ambiguity_murphy":P+select("?person ?name",'GRAPH ?g {?person a a:Member; f:name ?name; m:hasMembersMembership ?ms. ?ms a m:DailMembership.} FILTER(CONTAINS(LCASE(STR(?name)), "murphy"))'),
    }
    context={k:{"sparql":q,"response":collector.query(env,q)} for k,q in context_queries.items()}
    collector.save("oracle-context.json",context)
    collector.save("holdout.json", {"constructed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"as_of":ASOF,"method":"Questions derived from public capability contracts, not previous campaign responses/tests. Independent direct read-only SPARQL; expected local RDF answers, not complete historical rosters.","cases":cases})
    for c in cases:
        print(c["id"], c.get("expected_count",len(c.get("expected_rows",[]))),c["question"])


if __name__=="__main__":
    main()
