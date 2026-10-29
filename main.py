import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from constants import (
    API_VERSION,
    MSG_INDEX_REFRESH_FAILED,
    MSG_INITIAL_FETCH_FAILED,
    MSG_LATEST_COUNT_MISMATCH,
    MSG_LATEST_SHA256_MISMATCH,
    MSG_MITIGATION_NOT_FOUND,
    MSG_RECORD_NOT_FOUND,
    MSG_REFRESH_FAILED,
    MSG_RELEASE_FETCH_FAILED,
    MSG_RELEASE_NOT_FOUND,
    MSG_RELEASE_UNVERIFIED,
    MSG_RELEASES_REFRESH_FAILED,
    MSG_RELEASES_UNAVAILABLE,
    REPO_URL,
    SERVICE_NAME,
    STANDARD_URL,
)

logger = logging.getLogger("ave-api")
logging.basicConfig(level=logging.INFO)

SOURCE_URL = (
    "https://raw.githubusercontent.com/aveproject/ave/main/"
    "dist/ave-records-latest.json"
)
MANIFEST_URL = (
    "https://raw.githubusercontent.com/aveproject/ave/main/"
    "dist/ave-records-latest.manifest.json"
)
RELEASE_ASSET_URL = "https://github.com/aveproject/ave/releases/download/{tag}/{name}"
RELEASES_API_URL = "https://api.github.com/repos/aveproject/ave/releases?per_page=100"
REFRESH_INTERVAL_SECONDS = 15 * 60
RELEASES_REFRESH_SECONDS = 60 * 60
RELEASE_CACHE_SIZE = 3
OUTBOUND_TIMEOUT_SECONDS = 10

RECORDS_ASSET = "ave-records.json"
MANIFEST_ASSET = "ave-records.manifest.json"
SUMS_ASSET = "SHA256SUMS"
RELEASE_TAG_PATTERN = r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
LATEST_CACHE_CONTROL = "public, max-age=300"
RELEASE_CACHE_CONTROL = "public, max-age=86400, immutable"
RELEASES_CACHE_CONTROL = "public, max-age=300"
# the root's catalog object, in this order; schema_version sits beside it
CATALOG_FIELDS = (
    "channel",
    "record_count",
    "sha256",
    "generated_at",
    "source_commit",
    "release",
)

_cache: dict = {"records": [], "fetched_at": 0.0, "catalog": None}
# pinned releases never change, so they are kept until evicted, oldest use first
_release_cache: OrderedDict = OrderedDict()
_releases: dict = {"items": None, "etag": None, "fetched_at": 0.0}
_release_manifests: dict = {}

Release = Annotated[
    str | None,
    Query(
        pattern=RELEASE_TAG_PATTERN,
        description=(
            "Serve this catalog release, for example v1.2.0, instead of the "
            "latest data. See /v1/releases."
        ),
    ),
]

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=SERVICE_NAME,
    description=(
        "A read-only reference implementation of the AVE standard's record "
        "lookup API.\n\n"
        "Version 1 of the contract lives under `/v1/`. The unversioned paths "
        "(`/`, `/records`, `/records/{ave_id}`, `/records/{ave_id}/mitigation`, "
        "`/search`) are aliases of the `/v1` paths with identical behaviour.\n\n"
        "Every data response states the catalog it came from in its headers "
        "(`AVE-Catalog`, `AVE-Records-SHA256`, `AVE-Schema-Version`, "
        "`AVE-Source-Commit` when known), carries an `ETag`, and answers a "
        "matching `If-None-Match` with `304`. Add `?release=vX.Y.Z` to any data "
        "route to pin a catalog release.\n\n"
        "This service runs as a single instance that scales to zero. Use it for "
        "lookups, not in a scanner's hot path: download a catalog release from "
        "aveproject/ave for that."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public, read-only data, no reason to restrict
    allow_methods=["GET"],
    allow_headers=["*"],
    # browsers hide non-safelisted response headers from scripts unless listed
    expose_headers=[
        "AVE-API-Version",
        "AVE-Schema-Version",
        "AVE-Catalog",
        "AVE-Records-SHA256",
        "AVE-Source-Commit",
        "ETag",
    ],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["AVE-API-Version"] = API_VERSION
    return response


def _client(**kwargs) -> httpx.AsyncClient:
    # every outbound call has an explicit timeout, never the library default
    return httpx.AsyncClient(timeout=OUTBOUND_TIMEOUT_SECONDS, **kwargs)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _latest_catalog(body: bytes, manifest: dict) -> tuple[list, dict]:
    """The records in the latest file, and the catalog its manifest describes.

    The two files are fetched separately, so a refresh that straddles a commit
    can get a records file and a manifest that do not belong together; that is
    refused (the last known-good cache keeps serving) rather than labelled
    with the wrong sha256.
    """
    sha256 = _sha256(body)
    if manifest.get("sha256", sha256) != sha256:
        raise ValueError(MSG_LATEST_SHA256_MISMATCH)
    records = json.loads(body)
    if manifest.get("record_count", len(records)) != len(records):
        raise ValueError(MSG_LATEST_COUNT_MISMATCH)
    return records, {
        "channel": "latest",
        "schema_version": manifest.get("schema_version"),
        "record_count": len(records),
        "sha256": sha256,
        "generated_at": manifest.get("generated_at"),
        "source_commit": manifest.get("source_commit"),
        "release": None,
    }


async def _refresh_cache() -> None:
    async with _client() as client:
        records_response = await client.get(SOURCE_URL)
        records_response.raise_for_status()
        manifest_response = await client.get(MANIFEST_URL)
        manifest_response.raise_for_status()
    records, catalog = _latest_catalog(
        records_response.content, manifest_response.json()
    )
    _cache["records"] = records
    _cache["catalog"] = catalog
    _cache["fetched_at"] = time.time()


async def _ensure_fresh() -> None:
    if time.time() - _cache["fetched_at"] > REFRESH_INTERVAL_SECONDS:
        try:
            await _refresh_cache()
        except Exception as e:
            if not _cache["records"]:
                # Never had a successful fetch at all; nothing to fall
                # back to, this has to surface as a real failure.
                raise
            logger.warning(MSG_REFRESH_FAILED.format(error=e))


class ReleaseNotFound(Exception):
    pass


class ReleaseUnverified(Exception):
    pass


def _verify_release(tag: str, files: dict[str, bytes]) -> tuple[list, dict]:
    """The records of a downloaded release, once its three files agree.

    The same checks as aveproject/ave's scripts/check_release_assets.py: every
    file matches SHA256SUMS, and the manifest matches the records file and the
    tag. They prove the files belong together, not who published them;
    `gh attestation verify` is the check for that.
    """
    sums = {}
    for line in files[SUMS_ASSET].decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1].lstrip("*")] = parts[0].lower()
    for name in (RECORDS_ASSET, MANIFEST_ASSET):
        if sums.get(name) != _sha256(files[name]):
            raise ReleaseUnverified(f"{name} does not match {SUMS_ASSET}")
    try:
        manifest = json.loads(files[MANIFEST_ASSET])
        records = json.loads(files[RECORDS_ASSET])
    except ValueError as e:
        raise ReleaseUnverified(f"unreadable JSON: {e}") from None
    if not isinstance(manifest, dict) or not isinstance(records, list):
        raise ReleaseUnverified("the manifest or the records file has the wrong shape")
    if manifest.get("sha256") != _sha256(files[RECORDS_ASSET]):
        raise ReleaseUnverified(f"the manifest's sha256 is not that of {RECORDS_ASSET}")
    if manifest.get("release") != tag:
        raise ReleaseUnverified(
            f"the manifest names release {manifest.get('release')!r}"
        )
    if manifest.get("record_count") != len(records):
        raise ReleaseUnverified("the manifest's record_count is not the record count")
    schema_version = manifest.get("schema_version")
    if any(
        not isinstance(record, dict) or record.get("schema_version") != schema_version
        for record in records
    ):
        raise ReleaseUnverified("a record's schema_version is not the manifest's")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise ReleaseUnverified("the manifest's source_commit is not a commit SHA")
    return records, {
        "channel": tag,
        "schema_version": schema_version,
        "record_count": len(records),
        "sha256": manifest["sha256"],
        "generated_at": manifest.get("generated_at"),
        "source_commit": source_commit,
        "release": tag,
    }


async def _download_release(tag: str) -> dict[str, bytes]:
    files = {}
    async with _client(follow_redirects=True) as client:
        for name in (SUMS_ASSET, MANIFEST_ASSET, RECORDS_ASSET):
            response = await client.get(RELEASE_ASSET_URL.format(tag=tag, name=name))
            if response.status_code == 404:
                raise ReleaseNotFound(tag)
            response.raise_for_status()
            files[name] = response.content
    return files


async def _release_catalog(tag: str) -> tuple[list, dict]:
    if tag in _release_cache:
        _release_cache.move_to_end(tag)
        return _release_cache[tag]
    try:
        records, catalog = _verify_release(tag, await _download_release(tag))
    except ReleaseNotFound:
        raise HTTPException(
            status_code=404, detail=MSG_RELEASE_NOT_FOUND.format(tag=tag)
        ) from None
    except ReleaseUnverified as e:
        detail = MSG_RELEASE_UNVERIFIED.format(tag=tag, reason=e)
        logger.warning(detail)
        raise HTTPException(status_code=502, detail=detail) from None
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=MSG_RELEASE_FETCH_FAILED.format(tag=tag, error=e)
        ) from None
    _release_cache[tag] = (records, catalog)
    while len(_release_cache) > RELEASE_CACHE_SIZE:
        _release_cache.popitem(last=False)
    return records, catalog


async def _catalog(release: str | None) -> tuple[list, dict]:
    if release is None:
        await _ensure_fresh()
        return _cache["records"], _cache["catalog"]
    return await _release_catalog(release)


def _catalog_headers(catalog: dict) -> dict[str, str]:
    headers = {
        "AVE-Catalog": catalog["channel"],
        "AVE-Records-SHA256": catalog["sha256"],
    }
    if catalog.get("schema_version"):
        headers["AVE-Schema-Version"] = catalog["schema_version"]
    if catalog.get("source_commit"):
        headers["AVE-Source-Commit"] = catalog["source_commit"]
    return headers


def _etag(request: Request, catalog: dict) -> str:
    # /records and /v1/records are one resource, so the path is taken without
    # its /v1 prefix: an ETag from one is valid on the other
    path = request.url.path.removeprefix("/v1")
    query = sorted(request.query_params.multi_items())
    key = f"{API_VERSION}|{catalog['sha256']}|{path}|{query}"
    return '"' + _sha256(key.encode())[:32] + '"'


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    candidates = [candidate.strip() for candidate in if_none_match.split(",")]
    return "*" in candidates or any(
        candidate.removeprefix("W/") == etag for candidate in candidates
    )


def _http_date(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return format_datetime(moment.astimezone(timezone.utc), usegmt=True)


def _data_response(request: Request, payload, catalog: dict) -> Response:
    etag = _etag(request, catalog)
    headers = {
        **_catalog_headers(catalog),
        "ETag": etag,
        "Cache-Control": (
            RELEASE_CACHE_CONTROL if catalog["release"] else LATEST_CACHE_CONTROL
        ),
    }
    last_modified = _http_date(catalog.get("generated_at"))
    if last_modified:
        headers["Last-Modified"] = last_modified
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


@app.on_event("startup")
async def startup() -> None:
    try:
        await _refresh_cache()
    except Exception as e:
        logger.error(MSG_INITIAL_FETCH_FAILED.format(error=e))


@app.get("/v1/", summary="Service status and the catalog being served")
@app.get("/", include_in_schema=False)
@limiter.limit("60/minute")
async def index(request: Request) -> dict:
    """Service info, the API contract version, and the catalog the latest data
    comes from, read from the manifest beside the records file."""
    try:
        await _ensure_fresh()
    except Exception as e:
        # The index stays reachable so a person or an uptime check can see
        # that data is missing. /records still fails loudly when the cache
        # has never been populated.
        logger.warning(MSG_INDEX_REFRESH_FAILED.format(error=e))
    fetched_at = _cache["fetched_at"]
    age = round(time.time() - fetched_at) if fetched_at else None
    if not _cache["records"]:
        status = "no data yet"
    elif age > REFRESH_INTERVAL_SECONDS:
        status = "stale"
    else:
        status = "ok"
    catalog = _cache["catalog"]
    return {
        "name": SERVICE_NAME,
        "standard": STANDARD_URL,
        "repo": REPO_URL,
        "api_version": API_VERSION,
        "status": status,
        "record_count": len(_cache["records"]),
        "cache_age_seconds": age,
        "schema_version": catalog["schema_version"] if catalog else None,
        "catalog": {field: catalog[field] for field in CATALOG_FIELDS}
        if catalog
        else None,
        "docs": "/docs",
    }


@app.get("/v1/records", summary="All records")
@app.get("/records", include_in_schema=False)
@limiter.limit("60/minute")
async def list_records(request: Request, release: Release = None) -> Response:
    """Every published record, deprecated ones included, with their status."""
    records, catalog = await _catalog(release)
    return _data_response(request, records, catalog)


@app.get("/v1/records/{ave_id}", summary="One record")
@app.get("/records/{ave_id}", include_in_schema=False)
@limiter.limit("60/minute")
async def get_record(
    request: Request, ave_id: str, release: Release = None
) -> Response:
    """One record by ave_id. A deprecated record is served with its status; only
    an id the catalog has never published is a 404."""
    records, catalog = await _catalog(release)
    for record in records:
        if record.get("ave_id") == ave_id:
            return _data_response(request, record, catalog)
    raise HTTPException(
        status_code=404,
        detail=MSG_RECORD_NOT_FOUND.format(ave_id=ave_id),
        headers=_catalog_headers(catalog),
    )


@app.get("/v1/records/{ave_id}/mitigation", summary="One record's mitigation")
@app.get("/records/{ave_id}/mitigation", include_in_schema=False)
@limiter.limit("60/minute")
async def get_mitigation(
    request: Request, ave_id: str, release: Release = None
) -> Response:
    """The record's neutral mitigation object, and nothing else."""
    records, catalog = await _catalog(release)
    for record in records:
        if record.get("ave_id") == ave_id:
            mitigation = record.get("mitigation")
            if mitigation is None:
                raise HTTPException(
                    status_code=404,
                    detail=MSG_MITIGATION_NOT_FOUND.format(ave_id=ave_id),
                    headers=_catalog_headers(catalog),
                )
            return _data_response(request, mitigation, catalog)
    raise HTTPException(
        status_code=404,
        detail=MSG_RECORD_NOT_FOUND.format(ave_id=ave_id),
        headers=_catalog_headers(catalog),
    )


@app.get("/v1/search", summary="Search records")
@app.get("/search", include_in_schema=False)
@limiter.limit("60/minute")
async def search(
    request: Request, q: str = Query(..., min_length=1), release: Release = None
) -> Response:
    """Case-insensitive substring match across title, description, attack class
    and behavioral fingerprint."""
    records, catalog = await _catalog(release)
    needle = q.lower()
    fields = ("title", "description", "attack_class", "behavioral_fingerprint")
    return _data_response(
        request,
        [
            record
            for record in records
            if any(needle in str(record.get(field, "")).lower() for field in fields)
        ],
        catalog,
    )


async def _release_entry(client: httpx.AsyncClient, release: dict) -> dict:
    tag = release.get("tag_name")
    assets = {
        asset["name"]: asset["browser_download_url"]
        for asset in release.get("assets", [])
    }
    pinnable = all(
        name in assets for name in (RECORDS_ASSET, MANIFEST_ASSET, SUMS_ASSET)
    )
    manifest = None
    if pinnable:
        manifest = _release_manifests.get(tag)
        if manifest is None:
            response = await client.get(assets[MANIFEST_ASSET])
            response.raise_for_status()
            manifest = response.json()
            _release_manifests[tag] = manifest
    return {
        "tag": tag,
        "published_at": release.get("published_at"),
        "pinnable": pinnable,
        "schema_version": manifest.get("schema_version") if manifest else None,
        "record_count": manifest.get("record_count") if manifest else None,
        "sha256": manifest.get("sha256") if manifest else None,
        "assets": assets,
    }


async def _refresh_releases() -> None:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if _releases["etag"]:
        # a 304 answer does not spend the unauthenticated rate limit's budget
        # on a list that has not changed
        headers["If-None-Match"] = _releases["etag"]
    async with _client(follow_redirects=True) as client:
        response = await client.get(RELEASES_API_URL, headers=headers)
        if response.status_code == 304 and _releases["items"] is not None:
            _releases["fetched_at"] = time.time()
            return
        response.raise_for_status()
        items = [
            await _release_entry(client, release)
            for release in response.json()
            if not release.get("draft")
        ]
    _releases["items"] = items
    _releases["etag"] = response.headers.get("etag")
    _releases["fetched_at"] = time.time()


async def _ensure_releases() -> None:
    if (
        _releases["items"] is not None
        and time.time() - _releases["fetched_at"] < RELEASES_REFRESH_SECONDS
    ):
        return
    try:
        await _refresh_releases()
    except Exception as e:
        if _releases["items"] is None:
            raise HTTPException(
                status_code=502, detail=MSG_RELEASES_UNAVAILABLE
            ) from None
        logger.warning(MSG_RELEASES_REFRESH_FAILED.format(error=e))


@app.get("/v1/releases", summary="Catalog releases that can be pinned")
@limiter.limit("60/minute")
async def list_releases(request: Request) -> Response:
    """aveproject/ave's catalog releases, newest first, from the GitHub Releases
    API (cached for an hour). `pinnable` releases carry ave-records.json, its
    manifest and SHA256SUMS, and work with `?release=`; their schema_version,
    record_count and sha256 are read from the release's own manifest."""
    await _ensure_releases()
    return JSONResponse(
        _releases["items"], headers={"Cache-Control": RELEASES_CACHE_CONTROL}
    )
