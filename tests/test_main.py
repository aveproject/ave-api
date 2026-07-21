import time

from fastapi.testclient import TestClient

import main
from conftest import FAKE_RECORDS


def test_index_reports_service_metadata(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "AVE Reference API"
    assert body["record_count"] == len(FAKE_RECORDS)
    assert "cache_age_seconds" in body


def test_list_records_returns_all_cached_records(client):
    response = client.get("/records")

    assert response.status_code == 200
    assert len(response.json()) == len(FAKE_RECORDS)


def test_get_record_returns_matching_record(client):
    response = client.get("/records/AVE-0001")

    assert response.status_code == 200
    assert response.json()["ave_id"] == "AVE-0001"


def test_get_record_404s_for_unknown_id(client):
    response = client.get("/records/does-not-exist")

    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_get_mitigation_returns_only_the_mitigation_object(client):
    response = client.get("/records/AVE-0001/mitigation")

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Treat tool output as untrusted data, not instructions."
    }


def test_get_mitigation_404s_when_record_has_no_mitigation(client):
    response = client.get("/records/AVE-0002/mitigation")

    assert response.status_code == 404


def test_get_mitigation_404s_for_unknown_id(client):
    response = client.get("/records/does-not-exist/mitigation")

    assert response.status_code == 404


def test_search_matches_title_case_insensitively(client):
    response = client.get("/search", params={"q": "PROMPT"})

    assert response.status_code == 200
    assert [r["ave_id"] for r in response.json()] == ["AVE-0001"]


def test_search_matches_across_attack_class_and_behavioral_fingerprint(client):
    response = client.get("/search", params={"q": "unconfirmed"})

    assert [r["ave_id"] for r in response.json()] == ["AVE-0002"]


def test_search_returns_empty_list_for_no_match(client):
    response = client.get("/search", params={"q": "nothing-matches-this"})

    assert response.status_code == 200
    assert response.json() == []


def test_every_route_is_rate_limited(client):
    for _ in range(60):
        response = client.get("/records")
        assert response.status_code == 200

    response = client.get("/records")

    assert response.status_code == 429


def test_startup_does_not_crash_when_initial_fetch_fails(monkeypatch):
    async def failing_refresh() -> None:
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(main, "_refresh_cache", failing_refresh)

    with TestClient(main.app) as test_client:
        response = test_client.get("/")

    assert response.status_code == 200
    assert response.json()["record_count"] == 0


def test_refresh_failure_serves_stale_cache_instead_of_failing(client, monkeypatch):
    # `client` already has a populated, fresh cache via the autouse fixture;
    # push it past REFRESH_INTERVAL_SECONDS so the next request tries a
    # refresh, then make that refresh fail.
    main._cache["fetched_at"] = time.time() - main.REFRESH_INTERVAL_SECONDS - 1

    async def failing_refresh() -> None:
        raise RuntimeError("simulated transient network failure")

    monkeypatch.setattr(main, "_refresh_cache", failing_refresh)

    response = client.get("/records")

    assert response.status_code == 200
    assert len(response.json()) == len(FAKE_RECORDS)


def test_refresh_failure_is_a_real_failure_when_cache_was_never_populated(
    monkeypatch,
):
    async def failing_refresh() -> None:
        raise RuntimeError("simulated network failure, never succeeded")

    monkeypatch.setattr(main, "_refresh_cache", failing_refresh)
    main._cache["records"] = []
    main._cache["fetched_at"] = 0.0

    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/records")

    assert response.status_code == 500
