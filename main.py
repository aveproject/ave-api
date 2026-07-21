import logging
import time

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from constants import (
    MSG_INITIAL_FETCH_FAILED,
    MSG_MITIGATION_NOT_FOUND,
    MSG_RECORD_NOT_FOUND,
    MSG_REFRESH_FAILED,
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
REFRESH_INTERVAL_SECONDS = 15 * 60

_cache: dict = {"records": [], "fetched_at": 0.0}

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=SERVICE_NAME,
    description="A read-only reference implementation of the AVE standard's record lookup API.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public, read-only data, no reason to restrict
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


async def _refresh_cache() -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(SOURCE_URL)
        response.raise_for_status()
        records = response.json()
    _cache["records"] = records
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


@app.on_event("startup")
async def startup() -> None:
    try:
        await _refresh_cache()
    except Exception as e:
        logger.error(MSG_INITIAL_FETCH_FAILED.format(error=e))


@app.get("/")
async def index() -> dict:
    return {
        "name": SERVICE_NAME,
        "standard": STANDARD_URL,
        "repo": REPO_URL,
        "record_count": len(_cache["records"]),
        "cache_age_seconds": round(time.time() - _cache["fetched_at"]),
        "docs": "/docs",
    }


@app.get("/records")
@limiter.limit("60/minute")
async def list_records(request: Request) -> list[dict]:
    await _ensure_fresh()
    return _cache["records"]


@app.get("/records/{ave_id}")
@limiter.limit("60/minute")
async def get_record(request: Request, ave_id: str) -> dict:
    await _ensure_fresh()
    for record in _cache["records"]:
        if record.get("ave_id") == ave_id:
            return record
    raise HTTPException(
        status_code=404, detail=MSG_RECORD_NOT_FOUND.format(ave_id=ave_id)
    )


@app.get("/records/{ave_id}/mitigation")
@limiter.limit("60/minute")
async def get_mitigation(request: Request, ave_id: str) -> dict:
    await _ensure_fresh()
    for record in _cache["records"]:
        if record.get("ave_id") == ave_id:
            mitigation = record.get("mitigation")
            if mitigation is None:
                raise HTTPException(
                    status_code=404,
                    detail=MSG_MITIGATION_NOT_FOUND.format(ave_id=ave_id),
                )
            return mitigation
    raise HTTPException(
        status_code=404, detail=MSG_RECORD_NOT_FOUND.format(ave_id=ave_id)
    )


@app.get("/search")
@limiter.limit("60/minute")
async def search(request: Request, q: str = Query(..., min_length=1)) -> list[dict]:
    await _ensure_fresh()
    needle = q.lower()
    fields = ("title", "description", "attack_class", "behavioral_fingerprint")
    return [
        record
        for record in _cache["records"]
        if any(needle in str(record.get(field, "")).lower() for field in fields)
    ]
