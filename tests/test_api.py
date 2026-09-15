import json
import pytest
from oireachtas_etl.api import ApiPage, HousesApiClient
from oireachtas_etl.transforms.common import integer, midnight

def test_harvest_uses_skip_limit_until_short_page(monkeypatch):
    client = HousesApiClient("https://example.test/houses")
    calls = []
    pages = [[{"house": 1}, {"house": 2}], [{"house": 3}]]
    def page(*, skip, limit):
        calls.append((skip, limit))
        return ApiPage(json.dumps(pages.pop(0)).encode(), 200, {"skip": skip, "limit": limit})
    monkeypatch.setattr(client, "page", page)
    result = list(client.harvest(limit=2))
    assert calls == [(0, 2), (2, 2)] and len(result) == 2

def test_transient_http_error_is_retried(monkeypatch):
    from urllib.error import HTTPError
    client = HousesApiClient("https://example.test/houses", retries=1)
    calls = []
    class Response:
        status = 200
        def read(self): return b"[]"
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def open_url(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1: raise HTTPError("https://example.test", 503, "unavailable", {}, None)
        return Response()
    monkeypatch.setattr("oireachtas_etl.api.urlopen", open_url)
    monkeypatch.setattr("oireachtas_etl.api.time.sleep", lambda _: None)
    assert client.page(skip=0, limit=10).body == b"[]" and len(calls) == 2

@pytest.mark.parametrize("value", ["1.0", 1.0, True, " 1", "1e2"])
def test_integer_rejects_lossy_or_noncanonical_values(value):
    with pytest.raises(ValueError): integer(value)

@pytest.mark.parametrize("value", ["2024-2-01", "2024-01-01T00:00:00", "2024-02-30"])
def test_midnight_requires_a_real_canonical_date(value):
    with pytest.raises(ValueError): midnight(value)
