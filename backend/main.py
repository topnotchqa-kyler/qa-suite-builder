"""
main.py — FastAPI application entry point.
Thin route handlers; all business logic lives in service modules.
"""

import asyncio
import ipaddress
import logging
import re
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import io

load_dotenv()

from crawler import crawl_site
from generation import generate_test_suite
from xlsx_builder import build_workbook


logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="QA Suite Builder", version="1.0.0")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Pages-Crawled", "X-Sections-Generated", "Content-Disposition"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


class GenerateRequest(BaseModel):
    url: str
    username: Optional[str] = None
    password: Optional[str] = None


class CrawlOnlyRequest(BaseModel):
    url: str
    username: Optional[str] = None
    password: Optional[str] = None


def _validate_url(url: str) -> None:
    """Raise HTTPException if URL targets private/internal infrastructure (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: missing hostname.")

    # Block known internal/metadata hostnames
    blocked_hosts = {
        "localhost",
        "metadata",
        "metadata.google.internal",
        "169.254.169.254",  # AWS/GCP/Azure metadata endpoint
    }
    if hostname.lower() in blocked_hosts:
        raise HTTPException(status_code=400, detail="URL not allowed.")

    # If hostname is already an IP, validate it directly
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail="URL not allowed.")
        return
    except ValueError:
        pass  # Not an IP literal — resolve below

    # Resolve hostname and validate the resulting IP
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail="URL not allowed.")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Could not resolve URL hostname.")


def _sanitize_filename(name: str) -> str:
    """Strip characters unsafe for Content-Disposition filenames."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return safe[:50] or "qa_suite"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/crawl")
@limiter.limit("20/hour")
async def crawl_endpoint(request: Request, body: CrawlOnlyRequest):
    """
    Crawl only — returns raw crawl data as JSON.
    Useful for debugging and inspecting what the crawler found.
    """
    _validate_url(body.url)
    try:
        crawl_data = await crawl_site(
            base_url=body.url,
            username=body.username,
            password=body.password,
        )
        return JSONResponse(content=crawl_data)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Crawl error for URL: %s", body.url)
        raise HTTPException(status_code=500, detail="An error occurred while crawling. Check the URL and try again.")


@app.post("/api/generate")
@limiter.limit("10/hour")
async def generate_endpoint(request: Request, body: GenerateRequest, format: Optional[str] = None):
    """
    Full pipeline: crawl → generate test cases → return .xlsx file.
    Pass ?format=json to skip the xlsx build and return the test suite as JSON instead.
    """
    _validate_url(body.url)
    try:
        # Step 1: Crawl
        crawl_data = await crawl_site(
            base_url=body.url,
            username=body.username,
            password=body.password,
        )

        if not crawl_data.get("pages"):
            raise HTTPException(status_code=422, detail="No pages were crawled. Check the URL and try again.")

        # Step 2: Generate test suite via Anthropic API
        test_suite = await asyncio.to_thread(generate_test_suite, crawl_data)

        # JSON preview — skip xlsx build, return structured data directly
        if format == "json":
            return JSONResponse(content={
                "pages_crawled": crawl_data.get("pages_crawled", 0),
                "site_architecture": crawl_data.get("site_architecture"),
                "sections_generated": len(test_suite.get("sections", [])),
                "test_suite": test_suite,
            })

        # Step 3: Build .xlsx workbook
        xlsx_bytes = await asyncio.to_thread(build_workbook, test_suite)

        # Step 4: Stream back as file download
        site_name = _sanitize_filename(
            test_suite.get("site_name", "qa_suite").lower().replace(" ", "_")
        )
        filename = f"{site_name}_qa_suite.xlsx"

        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Pages-Crawled": str(crawl_data.get("pages_crawled", 0)),
                "X-Sections-Generated": str(len(test_suite.get("sections", []))),
            }
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Pipeline error for URL: %s", body.url)
        raise HTTPException(status_code=500, detail="An error occurred generating the test suite. Please try again.")


@app.post("/api/generate-from-crawl")
@limiter.limit("10/hour")
async def generate_from_crawl_endpoint(request: Request, crawl_data: dict):
    """
    Generate .xlsx from pre-existing crawl data (skip crawl step).
    Useful for re-running generation without re-crawling.
    """
    try:
        test_suite = await asyncio.to_thread(generate_test_suite, crawl_data)
        xlsx_bytes = await asyncio.to_thread(build_workbook, test_suite)

        site_name = _sanitize_filename(
            test_suite.get("site_name", "qa_suite").lower().replace(" ", "_")
        )
        filename = f"{site_name}_qa_suite.xlsx"

        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception:
        logger.exception("Generate-from-crawl error")
        raise HTTPException(status_code=500, detail="An error occurred generating the test suite. Please try again.")
