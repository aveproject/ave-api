import hashlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from conftest import FAKE_CATALOG, FAKE_RECORDS

# captured before the autouse fixture swaps it for a fake
REAL_REFRESH_CACHE = main._refresh_cache

TAG = "v1.2.0"
COMMIT = "a" * 40
RELEASE_RECORDS = [
    {
        "ave_id": "AVE-0001",
        "schema_version": "1.2.0",
        "title": "Prompt injection via tool output, as pinned",
        "description": "The record as it stood in the release.",
        "attack_class": "instruction-injection",
        "behavioral_fingerprint": "unexpected-tool-call-sequence",
        "mitigation": {"summary": "Pinned mitigation."},
    },
]

DATA_ROUTES = [
    "/records",
    "/records/AVE-0001",
    "/records/AVE-0001/mitigation",
    "/search?q=prompt",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_release(tag=TAG, records=None, **manifest_overrides) -> dict[str, bytes]:
    """The three files of a consistent release, built the way the catalog-release
    workflow builds them, with SHA256SUMS written last."""
    body = json.dumps(records or RELEASE_RECORDS, indent=2).encode() + b"\n"
    manifest = {
        "release": tag,
        "schema_version": "1.2.0",
        "record_count": len(records or RELEASE_RECORDS),
        "generated_at": "2026-10-29T04:51:04.844Z",
        "source": "https://github.com/aveproject/ave",
        "sha256": _sha(body),
        "source_commit": COMMIT,
    }
    manifest.update(manifest_overrides)
    manifest_bytes = json.dumps(manifest, indent=2).encode() + b"\n"
    sums = (
        f"{_sha(body)}  ave-records.json\n"
        f"{_sha(manifest_bytes)}  ave-records.manifest.json\n"
    ).encode()
    return {
        "ave-records.json": body,
        "ave-records.manifest.json": manifest_bytes,
        "SHA256SUMS": sums,
    }


class FakeGitHub:
    """Serves release assets and the Releases API from memory, counting requests."""

    def __init__(self, releases=None, api_releases=None, api_etag='"releases-1"'):
        self.releases = releases if releases is not None else {TAG: make_release()}
        self.api_releases = api_releases
        self.api_etag = api_etag
        self.api_status = 200
        self.calls: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if request.url.host == "api.github.com":
            if self.api_status != 200:
                return httpx.Response(self.api_status)
            if request.headers.get("if-none-match") == self.api_etag:
                return httpx.Response(304, headers={"etag": self.api_etag})
            return httpx.Response(
                200, json=self.api_releases, headers={"etag": self.api_etag}
            )
        prefix = "/aveproject/ave/releases/download/"
        if path.startswith(prefix):
            tag, name = path[len(prefix) :].split("/", 1)
            files = self.releases.get(tag)
            if files and name in files:
                return httpx.Response(200, content=files[name])
        return httpx.Response(404)

    def downloads(self) -> int:
        return sum(1 for call in self.calls if "/releases/download/" in call.url.path)

    def api_calls(self) -> list[httpx.Request]:
        return [call for call in self.calls if call.url.host == "api.github.com"]


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()

    def client_factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(fake.handler), **kwargs)

    monkeypatch.setattr(main, "_client", client_factory)
    return fake


# --- the contract and its headers --------------------------------------------------


@pytest.mark.parametrize("prefix", ["", "/v1"])
@pytest.mark.parametrize("route", DATA_ROUTES)
def test_every_data_route_states_its_catalog(client, prefix, route):
    response = client.get(prefix + route)

    assert response.status_code == 200
    headers = response.headers
    assert headers["AVE-API-Version"] == "1"
    assert headers["AVE-Schema-Version"] == "1.2.0"
    assert headers["AVE-Catalog"] == "latest"
    assert headers["AVE-Records-SHA256"] == FAKE_CATALOG["sha256"]
    assert "AVE-Source-Commit" not in headers  # the latest manifest names none
    assert headers["ETag"].startswith('"') and headers["ETag"].endswith('"')
    assert headers["Last-Modified"] == "Wed, 28 Oct 2026 23:50:03 GMT"
    assert headers["Cache-Control"] == "public, max-age=300"


@pytest.mark.parametrize("route", DATA_ROUTES)
def test_the_unversioned_path_is_an_exact_alias(client, route):
    old = client.get(route)
    new = client.get("/v1" + route)

    assert old.status_code == new.status_code == 200
    assert old.content == new.content
    assert dict(old.headers) == dict(new.headers)


def test_the_root_is_an_alias_too(client):
    old = client.get("/").json()
    new = client.get("/v1/").json()

    old.pop("cache_age_seconds")
    new.pop("cache_age_seconds")
    assert old == new


def test_the_api_version_header_is_on_every_response(client):
    for path in ["/", "/v1/", "/docs", "/records/does-not-exist"]:
        assert client.get(path).headers["AVE-API-Version"] == "1"


def test_the_root_reports_the_catalog_it_serves(client):
    body = client.get("/v1/").json()

    assert body["api_version"] == "1"
    assert body["schema_version"] == "1.2.0"
    assert body["catalog"] == {
        "channel": "latest",
        "record_count": len(FAKE_RECORDS),
        "sha256": FAKE_CATALOG["sha256"],
        "generated_at": "2026-10-28T23:50:03.886Z",
        "source_commit": None,
        "release": None,
    }
    assert body["status"] == "ok"


def test_the_root_reports_no_catalog_while_there_is_no_data(monkeypatch):
    async def failing_refresh() -> None:
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(main, "_refresh_cache", failing_refresh)

    with TestClient(main.app) as test_client:
        body = test_client.get("/v1/").json()

    assert body["catalog"] is None
    assert body["schema_version"] is None
    assert body["api_version"] == "1"


def test_a_404_still_says_which_catalog_was_searched(client):
    response = client.get("/v1/records/does-not-exist")

    assert response.status_code == 404
    assert response.headers["AVE-Catalog"] == "latest"
    assert response.headers["AVE-Records-SHA256"] == FAKE_CATALOG["sha256"]


def test_browsers_may_read_the_catalog_headers(client):
    response = client.get("/v1/records", headers={"Origin": "https://example.com"})

    exposed = response.headers["access-control-expose-headers"]
    for name in ["AVE-Catalog", "AVE-Records-SHA256", "ETag", "AVE-Source-Commit"]:
        assert name in exposed


def test_deprecated_records_are_served_with_their_status(client):
    response = client.get("/v1/records/AVE-0003")

    assert response.status_code == 200
    assert response.json()["status"] == "deprecated"
    assert "AVE-0003" in [r["ave_id"] for r in client.get("/v1/records").json()]


# --- ETag and 304 -------------------------------------------------------------------


@pytest.mark.parametrize("route", DATA_ROUTES)
def test_a_matching_if_none_match_gets_304(client, route):
    etag = client.get("/v1" + route).headers["ETag"]

    response = client.get("/v1" + route, headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["ETag"] == etag
    assert response.headers["AVE-Catalog"] == "latest"


def test_the_alias_and_v1_share_an_etag(client):
    etag = client.get("/records/AVE-0001").headers["ETag"]

    assert client.get("/v1/records/AVE-0001").headers["ETag"] == etag
    assert (
        client.get("/v1/records/AVE-0001", headers={"If-None-Match": etag}).status_code
        == 304
    )


@pytest.mark.parametrize(
    "header",
    ['"something-else"', "", 'W/"something-else", "another"'],
)
def test_a_non_matching_if_none_match_gets_the_body(client, header):
    response = client.get("/v1/records", headers={"If-None-Match": header})

    assert response.status_code == 200
    assert len(response.json()) == len(FAKE_RECORDS)


def test_weak_list_and_wildcard_forms_match(client):
    etag = client.get("/v1/records").headers["ETag"]

    for header in [f"W/{etag}", f'"other", {etag}', "*"]:
        assert (
            client.get("/v1/records", headers={"If-None-Match": header}).status_code
            == 304
        )


def test_etags_differ_between_resources_and_queries(client):
    etags = {
        client.get(path).headers["ETag"]
        for path in [
            "/v1/records",
            "/v1/records/AVE-0001",
            "/v1/records/AVE-0002",
            "/v1/records/AVE-0001/mitigation",
            "/v1/search?q=prompt",
            "/v1/search?q=excessive",
        ]
    }

    assert len(etags) == 6


def test_the_etag_changes_when_the_records_change(client):
    before = client.get("/v1/records/AVE-0001").headers["ETag"]
    main._cache["catalog"] = dict(FAKE_CATALOG, sha256="0" * 64)

    after = client.get("/v1/records/AVE-0001")

    assert after.headers["ETag"] != before
    assert (
        client.get(
            "/v1/records/AVE-0001", headers={"If-None-Match": before}
        ).status_code
        == 200
    )


# --- pinning to a release -----------------------------------------------------------


@pytest.mark.parametrize("route", DATA_ROUTES)
def test_a_pinned_release_is_served_with_its_own_headers(client, github, route):
    joiner = "&" if "?" in route else "?"
    response = client.get(f"/v1{route}{joiner}release={TAG}")

    assert response.status_code == 200
    headers = response.headers
    assert headers["AVE-Catalog"] == TAG
    assert headers["AVE-Source-Commit"] == COMMIT
    assert headers["AVE-Records-SHA256"] == _sha(
        github.releases[TAG]["ave-records.json"]
    )
    assert headers["Cache-Control"] == "public, max-age=86400, immutable"
    assert headers["Last-Modified"] == "Thu, 29 Oct 2026 04:51:04 GMT"


def test_a_pinned_release_serves_the_release_data_not_latest(client, github):
    body = client.get(f"/v1/records/AVE-0001?release={TAG}").json()

    assert body["title"] == "Prompt injection via tool output, as pinned"
    assert client.get(f"/v1/records/AVE-0002?release={TAG}").status_code == 404
    assert client.get("/v1/records/AVE-0002").status_code == 200


def test_a_verified_release_is_downloaded_once(client, github):
    client.get(f"/v1/records?release={TAG}")
    first = github.downloads()

    client.get(f"/v1/records/AVE-0001?release={TAG}")
    client.get(f"/records?release={TAG}")

    assert first == 3
    assert github.downloads() == 3


def test_an_unknown_release_is_a_404_with_a_clear_message(client, github):
    response = client.get("/v1/records?release=v9.9.9")

    assert response.status_code == 404
    assert "v9.9.9" in response.json()["detail"]
    assert "/v1/releases" in response.json()["detail"]
    assert "v9.9.9" not in main._release_cache


def test_a_release_without_the_three_assets_is_a_404(client, github):
    files = make_release(tag="v1.1.0")
    del files["SHA256SUMS"]
    github.releases["v1.1.0"] = files

    assert client.get("/v1/records?release=v1.1.0").status_code == 404


@pytest.mark.parametrize("bad", ["1.2.0", "v1.2", "latest", "v1.2.0-rc1"])
def test_a_malformed_release_is_refused_before_any_download(client, github, bad):
    response = client.get(f"/v1/records?release={bad}")

    assert response.status_code == 422
    assert github.downloads() == 0


def test_a_tampered_asset_is_refused_and_not_cached(client, github):
    github.releases[TAG]["ave-records.json"] += b" "

    first = client.get(f"/v1/records?release={TAG}")
    second = client.get(f"/v1/records?release={TAG}")

    assert first.status_code == second.status_code == 502
    assert "SHA256SUMS" in first.json()["detail"]
    assert TAG not in main._release_cache
    assert github.downloads() == 6  # tried again, nothing was cached


def test_a_release_whose_upstream_fails_is_a_502_and_not_cached(
    client, github, monkeypatch
):
    def failing_handler(request):
        raise httpx.ConnectError("simulated outage")

    monkeypatch.setattr(github, "handler", failing_handler)

    response = client.get(f"/v1/records?release={TAG}")

    assert response.status_code == 502
    assert TAG not in main._release_cache


def test_the_release_cache_is_bounded(client, github):
    tags = [f"v1.{minor}.0" for minor in range(2, 2 + main.RELEASE_CACHE_SIZE + 1)]
    for tag in tags:
        github.releases[tag] = make_release(tag=tag)
        assert client.get(f"/v1/records?release={tag}").status_code == 200

    assert list(main._release_cache) == tags[1:]
    client.get(f"/v1/records?release={tags[0]}")
    assert github.downloads() == 3 * (len(tags) + 1)


def test_a_pinned_release_has_its_own_etag(client, github):
    latest = client.get("/v1/records/AVE-0001").headers["ETag"]
    pinned = client.get(f"/v1/records/AVE-0001?release={TAG}")

    assert pinned.headers["ETag"] != latest
    assert (
        client.get(
            f"/v1/records/AVE-0001?release={TAG}",
            headers={"If-None-Match": pinned.headers["ETag"]},
        ).status_code
        == 304
    )


# --- release verification, check by check -----------------------------------------


def test_a_consistent_release_verifies():
    records, catalog = main._verify_release(TAG, make_release())

    assert records == RELEASE_RECORDS
    assert catalog["release"] == TAG
    assert catalog["source_commit"] == COMMIT


def _tampered(change) -> dict[str, bytes]:
    files = make_release()
    change(files)
    return files


def _resummed(files: dict[str, bytes]) -> dict[str, bytes]:
    """Rewrite SHA256SUMS to match whatever the files now hold, so only the
    manifest checks can catch the change."""
    files["SHA256SUMS"] = (
        f"{_sha(files['ave-records.json'])}  ave-records.json\n"
        f"{_sha(files['ave-records.manifest.json'])}  ave-records.manifest.json\n"
    ).encode()
    return files


@pytest.mark.parametrize(
    "files, reason",
    [
        (
            _tampered(lambda f: f.update({"ave-records.json": b"[]\n"})),
            "ave-records.json does not match SHA256SUMS",
        ),
        (
            _tampered(lambda f: f.update({"ave-records.manifest.json": b"{}\n"})),
            "ave-records.manifest.json does not match SHA256SUMS",
        ),
        (_resummed(make_release(sha256="0" * 64)), "sha256 is not that of"),
        (_resummed(make_release(release="v1.1.0")), "names release 'v1.1.0'"),
        (_resummed(make_release(record_count=5)), "record_count"),
        (_resummed(make_release(schema_version="1.1.0")), "schema_version"),
        (_resummed(make_release(source_commit="abc123")), "source_commit"),
    ],
)
def test_each_inconsistency_is_refused(files, reason):
    with pytest.raises(main.ReleaseUnverified, match=reason):
        main._verify_release(TAG, files)


# --- /v1/releases -------------------------------------------------------------------


def _api_release(tag, assets, published="2026-10-29T05:09:35Z"):
    base = f"https://github.com/aveproject/ave/releases/download/{tag}/"
    return {
        "tag_name": tag,
        "draft": False,
        "published_at": published,
        "assets": [
            {"name": name, "browser_download_url": base + name} for name in assets
        ],
    }


API_RELEASES = [
    _api_release(TAG, ["ave-records.json", "ave-records.manifest.json", "SHA256SUMS"]),
    _api_release("v1.1.0", ["ave-records-v1.1.0.json"], "2026-06-24T00:00:00Z"),
    _api_release("v1.0.0", [], "2026-06-18T00:00:00Z"),
]


def test_releases_lists_each_release_from_the_api(client, github):
    github.api_releases = API_RELEASES

    response = client.get("/v1/releases")

    assert response.status_code == 200
    assert response.headers["AVE-API-Version"] == "1"
    current, older, first = response.json()
    manifest = json.loads(github.releases[TAG]["ave-records.manifest.json"])
    assert current == {
        "tag": TAG,
        "published_at": "2026-10-29T05:09:35Z",
        "pinnable": True,
        "schema_version": "1.2.0",
        "record_count": 1,
        "sha256": manifest["sha256"],
        "assets": {
            name: f"https://github.com/aveproject/ave/releases/download/{TAG}/{name}"
            for name in ["ave-records.json", "ave-records.manifest.json", "SHA256SUMS"]
        },
    }
    assert older["pinnable"] is False and older["record_count"] is None
    assert list(older["assets"]) == ["ave-records-v1.1.0.json"]
    assert first["tag"] == "v1.0.0" and first["assets"] == {}


def test_releases_are_cached_for_an_hour_then_revalidated(client, github):
    github.api_releases = API_RELEASES
    client.get("/v1/releases")
    client.get("/v1/releases")
    assert len(github.api_calls()) == 1

    main._releases["fetched_at"] = time.time() - main.RELEASES_REFRESH_SECONDS - 1
    downloads_before = github.downloads()
    response = client.get("/v1/releases")

    revalidation = github.api_calls()[-1]
    assert len(github.api_calls()) == 2
    assert revalidation.headers["if-none-match"] == '"releases-1"'
    assert response.json()[0]["tag"] == TAG
    assert github.downloads() == downloads_before  # 304: nothing re-downloaded


def test_releases_serve_the_last_list_when_github_fails(client, github):
    github.api_releases = API_RELEASES
    client.get("/v1/releases")
    main._releases["fetched_at"] = 0.0
    github.api_status = 503

    response = client.get("/v1/releases")

    assert response.status_code == 200
    assert response.json()[0]["tag"] == TAG


def test_releases_are_a_502_when_github_fails_and_nothing_is_cached(client, github):
    github.api_status = 503

    response = client.get("/v1/releases")

    assert response.status_code == 502


# --- the latest data and its manifest -----------------------------------------------


def _latest_files(records=None, **manifest_overrides):
    body = json.dumps(records or FAKE_RECORDS).encode()
    manifest = {
        "schema_version": "1.2.0",
        "record_count": len(records or FAKE_RECORDS),
        "generated_at": "2026-10-28T23:50:03.886Z",
        "source": "https://github.com/aveproject/ave",
        "sha256": _sha(body),
    }
    manifest.update(manifest_overrides)
    return body, manifest


def test_the_latest_catalog_comes_from_its_manifest():
    body, manifest = _latest_files()

    records, catalog = main._latest_catalog(body, manifest)

    assert records == FAKE_RECORDS
    assert catalog == dict(FAKE_CATALOG, sha256=_sha(body))


@pytest.mark.parametrize(
    "overrides, message",
    [({"sha256": "0" * 64}, "sha256"), ({"record_count": 99}, "record_count")],
)
def test_a_latest_manifest_from_another_commit_is_refused(overrides, message):
    body, manifest = _latest_files(**overrides)

    with pytest.raises(ValueError, match=message):
        main._latest_catalog(body, manifest)


def test_the_real_refresh_reads_the_records_and_their_manifest(monkeypatch):
    body, manifest = _latest_files()

    def handler(request):
        if request.url.path.endswith("ave-records-latest.json"):
            return httpx.Response(200, content=body)
        if request.url.path.endswith("ave-records-latest.manifest.json"):
            return httpx.Response(200, json=manifest)
        return httpx.Response(404)

    monkeypatch.setattr(
        main,
        "_client",
        lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setattr(main, "_refresh_cache", REAL_REFRESH_CACHE)

    with TestClient(main.app) as test_client:
        response = test_client.get("/v1/records")

    assert response.status_code == 200
    assert response.headers["AVE-Records-SHA256"] == _sha(body)


def test_outbound_calls_have_an_explicit_timeout():
    assert main._client().timeout == httpx.Timeout(main.OUTBOUND_TIMEOUT_SECONDS)


# --- rate limiting covers the new routes --------------------------------------------


@pytest.mark.parametrize("path", ["/v1/", "/v1/records", "/v1/records/AVE-0001"])
def test_the_v1_paths_are_rate_limited(client, path):
    # slowapi counts per IP per path, so each path has its own 60 a minute
    for _ in range(60):
        assert client.get(path).status_code == 200

    assert client.get(path).status_code == 429


def test_releases_are_rate_limited(client, github):
    github.api_releases = API_RELEASES
    for _ in range(60):
        assert client.get("/v1/releases").status_code == 200

    assert client.get("/v1/releases").status_code == 429
