"""Normalise existing accepted evidence, never infer facts from rendered rows.

This is an evidence-shape boundary, not an executable capability catalogue.
Unknown shapes fail closed while the original service response stays inspectable.
"""
from __future__ import annotations

import copy

from .research_adapter import AcceptedMember


def accept_query_evidence(outcome, queries):
    data = copy.deepcopy(outcome.accepted_evidence)
    if not data:
        return None, ("The Query Service returned a response, but this capability supplies no accepted structured "
                      "research evidence. Its response is retained for inspection; no research fact was promoted.")
    refs = outcome.plan["referents"]
    try:
        if set(data) == {"memberIri", "bills"}:
            if data["memberIri"] != refs["member"]["iri"]:
                raise ValueError("Sponsorship Member identity mismatch.")
            # Use resolved compiler identity/label, never parse a name from model wording.
            data["memberName"] = refs["member"]["label"]
        elif set(data) in ({"lifecycle"}, {"representation"}):
            pass  # Existing compiler-owned, exact-proposition projections.
        elif set(data) == {"members"}:
            if not data["members"]:
                raise ValueError("No accepted Member witnesses.")
            term, affiliation = refs["term"]["iri"], refs["affiliation"]["iri"]
            for member in data["members"]:
                for witness in member["witnesses"]:
                    witness["queryRefs"] = [q["queryId"] for q in queries]
                    if witness["termIri"] != term or witness["affiliationIri"] != affiliation:
                        raise ValueError("Accepted Member witness scope mismatch.")
                AcceptedMember.model_validate(member)
            # Same list/count parity acceptance as the established ResearchAdapter.
            if outcome.plan["answer"]["kind"] == "count":
                if outcome.result.rows != ((str(len({m["memberIri"] for m in data["members"]})),),):
                    raise ValueError("Count/witness mismatch.")
            elif {r[1]: r[0] for r in outcome.result.rows} != {m["memberIri"]: m["displayName"] for m in data["members"]}:
                raise ValueError("List/witness mismatch.")
            data["partyScope"] = {"termIri": term, "affiliationIri": affiliation,
                "label": refs["affiliation"]["label"], "asOf": outcome.plan["asOf"]}
        else:
            return None, "The Query Service's accepted evidence shape is not supported by the research fact boundary; no facts were promoted."
    except (ValueError, KeyError, TypeError, IndexError):
        return None, "The accepted evidence did not agree with its compiler scope or result; no research facts were promoted."
    return data, None
