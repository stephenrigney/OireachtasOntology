"""Dirty/replay boundary for independently owned per-Bill local graphs.

Shares the Bill sponsor observation store's SQLite connection; this is graph
publication state, not a second reconciliation scheduler or a core Bill owner.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from rdflib import Graph, URIRef

from .bill_sponsor_reconciliation import bill_sponsor_graph_iri
from .reconciliation import ReconciliationError, verify_reconciliation_graph
from .serialization import ntriples
from .transforms.common import MEMBERS


class BillSponsorPublication:
    def __init__(self, store):
        self.connection = store.connection
        self.connection.execute("""CREATE TABLE IF NOT EXISTS bill_sponsor_publication (
            bill_iri TEXT PRIMARY KEY,
            graph_iri TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK(state IN ('clean','dirty')),
            published_payload TEXT,
            published_hash TEXT,
            published_evidence_hash TEXT,
            pending_payload TEXT,
            pending_hash TEXT,
            pending_evidence_hash TEXT
        )""")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS bill_sponsor_presence (
            bill_iri TEXT PRIMARY KEY,
            source_presence TEXT NOT NULL CHECK(source_presence IN ('present','missing')),
            review_required INTEGER NOT NULL CHECK(review_required IN (0,1)),
            checked_at TEXT NOT NULL
        )""")

    def complete_source_presence(self, seen: set[str]) -> list[str]:
        """Record complete-scan absence without mutating either Bill-owned graph."""
        known = {row[0] for row in self.connection.execute(
            "SELECT DISTINCT bill_iri FROM bill_sponsor_observation UNION "
            "SELECT bill_iri FROM bill_sponsor_publication UNION "
            "SELECT bill_iri FROM bill_sponsor_presence")}
        absent = sorted(known - seen)
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for bill in sorted(known | seen):
                self.connection.execute("""INSERT INTO bill_sponsor_presence
                    (bill_iri, source_presence, review_required, checked_at)
                    VALUES (?,?,?,?) ON CONFLICT(bill_iri) DO UPDATE SET
                    source_presence=excluded.source_presence,
                    review_required=excluded.review_required,
                    checked_at=excluded.checked_at""",
                    (bill, "missing" if bill in absent else "present",
                     1 if bill in absent else 0, now))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        return absent

    def row(self, bill_iri: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM bill_sponsor_publication WHERE bill_iri=?", (bill_iri,)).fetchone()
        return dict(row) if row else None

    def rows(self) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM bill_sponsor_publication ORDER BY bill_iri")]

    @staticmethod
    def _check_identity(bill_iri: str, graph_iri: str) -> None:
        from .transforms.bills import bill_graph_iri
        from urllib.parse import urlsplit, unquote

        path = [part for part in urlsplit(bill_iri).path.split("/") if part]
        if (not bill_iri.startswith("https://data.oireachtas.ie/ie/oireachtas/bill/")
                or len(path) != 5 or path[:3] != ["ie", "oireachtas", "bill"]
                or not path[3].isdigit() or not unquote(path[4])):
            raise ValueError("invalid local Bill publication identity")
        expected = bill_sponsor_graph_iri({"uri": bill_iri, "billYear": path[3],
                                            "billNo": unquote(path[4])})
        if graph_iri != expected or bill_graph_iri({"uri": bill_iri,
                                                    "billYear": path[3],
                                                    "billNo": unquote(path[4])}) == graph_iri:
            raise ValueError("local Bill publication graph identity mismatch")

    @staticmethod
    def _payload_graph(payload: str, expected_hash: str, bill_iri: str) -> Graph:
        if (not isinstance(payload, str) or not isinstance(expected_hash, str)
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != expected_hash):
            raise ValueError("dirty Bill local graph has no intact replayable payload")
        graph = Graph().parse(data=payload, format="nt")
        allowed = {MEMBERS.reconciledSponsorOffice, MEMBERS.reconciledSponsorHolding}
        if any(not isinstance(s, URIRef) or not str(s).startswith(bill_iri + "#process#sponsor-")
               or p not in allowed or not isinstance(o, URIRef)
               for s, p, o in graph):
            raise ValueError("dirty Bill local graph violates link-only ownership")
        return graph

    def mark_dirty(self, bill_iri: str, graph_iri: str, graph: Graph,
                   evidence_hash: str) -> str:
        self._check_identity(bill_iri, graph_iri)
        if not isinstance(evidence_hash, str) or not evidence_hash:
            raise ValueError("local publication evidence hash is required")
        payload = ntriples(graph)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._payload_graph(payload, digest, bill_iri)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            old = self.row(bill_iri)
            if old and old["graph_iri"] != graph_iri:
                raise ValueError("stored local Bill graph identity changed")
            self.connection.execute("""INSERT INTO bill_sponsor_publication
                (bill_iri, graph_iri, state, published_payload, published_hash,
                 published_evidence_hash, pending_payload, pending_hash, pending_evidence_hash)
                VALUES (?,?,'dirty',?,?,?,?,?,?)
                ON CONFLICT(bill_iri) DO UPDATE SET state='dirty',
                pending_payload=excluded.pending_payload, pending_hash=excluded.pending_hash,
                pending_evidence_hash=excluded.pending_evidence_hash""",
                (bill_iri, graph_iri, old["published_payload"] if old else None,
                 old["published_hash"] if old else None,
                 old["published_evidence_hash"] if old else None,
                 payload, digest, evidence_hash))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        return digest

    def complete(self, bill_iri: str, graph_iri: str, payload_hash: str) -> None:
        self._check_identity(bill_iri, graph_iri)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.row(bill_iri)
            if (row is None or row["state"] != "dirty" or row["graph_iri"] != graph_iri
                    or row["pending_hash"] != payload_hash):
                raise ValueError("Bill local publication has no matching pending state")
            self._payload_graph(row["pending_payload"], payload_hash, bill_iri)
            self.connection.execute("""UPDATE bill_sponsor_publication SET state='clean',
               published_payload=pending_payload, published_hash=pending_hash,
               published_evidence_hash=pending_evidence_hash,
               pending_payload=NULL, pending_hash=NULL, pending_evidence_hash=NULL
               WHERE bill_iri=?""", (bill_iri,))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def publish(self, bill_iri: str, graph_iri: str, graph: Graph,
                evidence_hash: str, loader, client) -> bool:
        """Exact graph verification on skip and after PUT; failures stay dirty."""
        self._check_identity(bill_iri, graph_iri)
        payload = ntriples(graph)
        row = self.row(bill_iri)
        if (row and row["state"] == "clean" and row["graph_iri"] == graph_iri
                and row["published_hash"] == hashlib.sha256(payload.encode()).hexdigest()
                and row["published_evidence_hash"] == evidence_hash):
            self._payload_graph(row["published_payload"], row["published_hash"], bill_iri)
            try:
                verify_reconciliation_graph(client, graph_iri, graph)
            except (ValueError, ReconciliationError):
                pass  # repair a changed remote graph with this validated candidate
            else:
                return False
        digest = self.mark_dirty(bill_iri, graph_iri, graph, evidence_hash)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_reconciliation_graph(client, graph_iri, graph)
        self.complete(bill_iri, graph_iri, digest)
        return True

    def replay_missing(self, seen: set[str], loader, client) -> list[str]:
        """A disappeared Bill never causes deletion; replay only intact pending RDF."""
        replayed = []
        for row in self.rows():
            if row["bill_iri"] in seen or row["state"] != "dirty":
                continue
            self._check_identity(row["bill_iri"], row["graph_iri"])
            graph = self._payload_graph(row["pending_payload"], row["pending_hash"], row["bill_iri"])
            loader.replace(row["graph_iri"], row["pending_payload"],
                           content_type="application/n-triples")
            verify_reconciliation_graph(client, row["graph_iri"], graph)
            self.complete(row["bill_iri"], row["graph_iri"], row["pending_hash"])
            replayed.append(row["bill_iri"])
        return replayed
