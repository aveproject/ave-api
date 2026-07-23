import time

import pytest
from fastapi.testclient import TestClient

import main

FAKE_RECORDS = [
    {
        "ave_id": "AVE-0001",
        "title": "Prompt injection via tool output",
        "description": "An agent trusts unsanitized tool output as instructions.",
        "attack_class": "instruction-injection",
        "behavioral_fingerprint": "unexpected-tool-call-sequence",
        "mitigation": {
            "summary": "Treat tool output as untrusted data, not instructions."
        },
    },
    {
        "ave_id": "AVE-0002",
        "title": "Excessive agency",
        "description": "An agent takes an irreversible action without confirmation.",
        "attack_class": "privilege-escalation",
        "behavioral_fingerprint": "unconfirmed destructive action",
        "mitigation": None,
    },
]


@pytest.fixture(autouse=True)
def isolated_service_state(monkeypatch):
    """Every test starts from known cache and rate-limit state, and no test
    ever reaches the real network."""

    async def fake_refresh_cache() -> None:
        main._cache["records"] = FAKE_RECORDS
        main._cache["fetched_at"] = time.time()

    monkeypatch.setattr(main, "_refresh_cache", fake_refresh_cache)
    main._cache["records"] = []
    main._cache["fetched_at"] = 0.0
    main.limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client
