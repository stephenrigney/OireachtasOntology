from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from oireachtas_etl import reconciliation
from oireachtas_etl.config import Settings
from oireachtas_etl.reconciliation import ExternalHttpTransport, ExternalServicePolicy


class Response:
    status = 200

    def __init__(self, body=b'{"ok":true}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def transport(*, retries=0, ttl=0, entries=0, rate=0, base=0.5, maximum=1.0):
    policy = ExternalServicePolicy(ttl, entries, rate)
    return ExternalHttpTransport(retries=retries, backoff_base_seconds=base,
                                 backoff_max_seconds=maximum,
                                 service_policies={"wikidata": policy, "dbpedia": policy})


def test_successful_responses_are_cached_per_service_and_cache_is_bounded(monkeypatch):
    opened = []

    def open_request(request, *, timeout):
        opened.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    client = transport(ttl=60, entries=1)
    request = Request("https://example.test/response")

    assert client.get_bytes("wikidata", request, timeout=2) == b'{"ok":true}'
    assert client.get_bytes("wikidata", request, timeout=2) == b'{"ok":true}'
    client.get_bytes("wikidata", Request("https://example.test/other"), timeout=2)
    # The one-entry Wikidata LRU evicted the first response.
    client.get_bytes("wikidata", request, timeout=2)
    # Identical URLs are independent cache entries for separate authorities.
    assert client.get_bytes("dbpedia", request, timeout=2) == b'{"ok":true}'
    assert len(opened) == 4
    summary = client.summary()
    assert summary["wikidata"]["requests"] == 3
    assert summary["wikidata"]["cache_hits"] == 1
    assert summary["dbpedia"]["requests"] == 1


def test_response_cache_expires_after_configured_ttl(monkeypatch):
    now, opened = [0.0], []

    def open_request(request, *, timeout):
        opened.append(request.full_url)
        return Response()

    monkeypatch.setattr(reconciliation.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    client = transport(ttl=5, entries=2)
    request = Request("https://example.test/response")
    client.get_bytes("wikidata", request, timeout=1)
    now[0] = 5.0
    client.get_bytes("wikidata", request, timeout=1)

    assert opened == [request.full_url, request.full_url]
    assert client.summary()["wikidata"]["cache_misses"] == 2


def test_reviewed_target_verification_bypasses_response_cache(monkeypatch):
    responses = [b'{"entities":{"Q123":{"id":"Q123"}}}',
                 b'{"entities":{"Q123":{"id":"Q123","missing":""}}}']
    opened = []

    def open_request(request, *, timeout):
        opened.append(request.full_url)
        return Response(responses.pop(0))

    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    client = reconciliation.WikidataClient(
        endpoint="https://example.test/api", timeout=1,
        transport=transport(ttl=300, entries=10))

    assert client.entity("Q123")["entities"]["Q123"]["id"] == "Q123"
    assert client.entity("Q123")["entities"]["Q123"].get("missing") == ""
    assert len(opened) == 2


def test_transient_http_errors_use_bounded_exponential_backoff_with_jitter(monkeypatch):
    attempts, sleeps = [], []

    def open_request(request, *, timeout):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise HTTPError(request.full_url, 503, "unavailable", None, BytesIO(b"retry"))
        return Response(b"ok")

    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    monkeypatch.setattr(reconciliation.time, "sleep", sleeps.append)
    monkeypatch.setattr(reconciliation.random, "uniform", lambda low, high: high)
    client = transport(retries=2, base=0.25, maximum=0.4)

    assert client.get_bytes("wikidata", Request("https://example.test/query"), timeout=1) == b"ok"
    assert len(attempts) == 2
    assert sleeps == [0.25]
    assert client.summary()["wikidata"]["retries"] == 1


def test_non_transient_http_error_is_not_retried(monkeypatch):
    attempts = []

    def open_request(request, *, timeout):
        attempts.append(request.full_url)
        raise HTTPError(request.full_url, 400, "bad request", None, BytesIO())

    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    client = transport(retries=4)
    with pytest.raises(HTTPError):
        client.get_bytes("wikidata", Request("https://example.test/query"), timeout=1)
    assert len(attempts) == 1
    assert client.summary()["wikidata"]["failures"] == 1


def test_retry_count_is_bounded_and_rate_limit_is_per_service(monkeypatch):
    now, attempts, sleeps = [0.0], [], []

    def fake_sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    def open_request(request, *, timeout):
        attempts.append(request.full_url)
        if request.full_url.endswith("/failure"):
            raise HTTPError(request.full_url, 429, "limited", None, BytesIO())
        return Response()

    monkeypatch.setattr(reconciliation.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(reconciliation.time, "sleep", fake_sleep)
    monkeypatch.setattr(reconciliation.random, "uniform", lambda _low, _high: 0.0)
    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    client = transport(retries=1, entries=0, rate=2.0)

    with pytest.raises(HTTPError):
        client.get_bytes("wikidata", Request("https://example.test/failure"), timeout=1)
    client.get_bytes("wikidata", Request("https://example.test/success"), timeout=1)

    assert len(attempts) == 3  # two bounded failures and one independent request
    assert client.summary()["wikidata"]["retries"] == 1
    assert client.summary()["wikidata"]["rate_limit_wait_seconds"] == 1.0
    assert sleeps == [0.5, 0.5]


def test_external_http_settings_are_environment_configurable(monkeypatch):
    monkeypatch.setenv("OIR_EXTERNAL_HTTP_RETRIES", "4")
    monkeypatch.setenv("OIR_EXTERNAL_HTTP_BACKOFF_BASE_SECONDS", "0.2")
    monkeypatch.setenv("OIR_EXTERNAL_HTTP_BACKOFF_MAX_SECONDS", "3")
    monkeypatch.setenv("OIR_WIKIDATA_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("OIR_WIKIDATA_REQUESTS_PER_SECOND", "3.5")
    monkeypatch.setenv("OIR_DBPEDIA_CACHE_MAX_ENTRIES", "7")

    settings = Settings.from_environment()
    assert settings.external_http_retries == 4
    assert settings.external_http_backoff_base_seconds == 0.2
    assert settings.external_http_backoff_max_seconds == 3
    assert settings.wikidata_cache_ttl_seconds == 0
    assert settings.wikidata_requests_per_second == 3.5
    assert settings.dbpedia_cache_max_entries == 7


def test_reconciliation_metrics_count_due_and_overdue_records(tmp_path):
    import json
    from pathlib import Path

    from oireachtas_etl.reconciliation import ReconciliationStore, reconcile_records

    root = Path(__file__).resolve().parents[1]
    member = json.loads((root / "data/api_examples/member.json").read_text())["member"]

    class Unavailable:
        def lookup_member_code(self, _code):
            raise OSError("Wikidata unavailable")

    class UnusedDbpedia:
        def resolve_wikidata(self, _qid):
            return []

    store = ReconciliationStore(tmp_path / "reconciliation.sqlite")
    try:
        metrics = {}
        results = reconcile_records([{"member": member}], store, {}, "review", Unavailable(),
                                    UnusedDbpedia(), run_metrics=metrics)
        row = store.get_record("member", member["uri"])
        assert results[0][1].state == "pending"
        assert row["enrichment_reason"] == "lookup-error"
        assert metrics["due"] == 1 and metrics["stale"] == 0

        store.connection.execute(
            "UPDATE reconciliation_record SET next_recheck_at='2000-01-01T00:00:00+00:00' "
            "WHERE entity_kind='member' AND local_iri=?", (member["uri"],))
        metrics = {}
        reconcile_records([{"member": member}], store, {}, "review", Unavailable(),
                          UnusedDbpedia(), run_metrics=metrics)
        assert metrics["due"] == 1 and metrics["stale"] == 1
        assert store.get_record("member", member["uri"])["state"] == "pending"
    finally:
        store.close()
