"""
main.py — FastAPI application entry point.
Thin route handlers; all business logic lives in service modules.
"""

import asyncio
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv
import io

load_dotenv()

from crawler import crawl_site
from generation import generate_test_suite
from xlsx_builder import build_workbook


app = FastAPI(title="QA Suite Builder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    url: str
    username: Optional[str] = None
    password: Optional[str] = None


class CrawlOnlyRequest(BaseModel):
    url: str
    username: Optional[str] = None
    password: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/crawl")
async def crawl_endpoint(request: CrawlOnlyRequest):
    """
    Crawl only — returns raw crawl data as JSON.
    Useful for debugging and inspecting what the crawler found.
    """
    try:
        crawl_data = await crawl_site(
            base_url=str(request.url),
            username=request.username,
            password=request.password,
        )
        return JSONResponse(content=crawl_data)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate_endpoint(request: GenerateRequest):
    """
    Full pipeline: crawl → generate test cases → return .xlsx file.
    Streams the binary .xlsx back to the client.
    """
    try:
        # Step 1: Crawl
        crawl_data = await crawl_site(
            base_url=str(request.url),
            username=request.username,
            password=request.password,
        )

        if not crawl_data.get("pages"):
            raise HTTPException(status_code=422, detail="No pages were crawled. Check the URL and try again.")

        # Step 2: Generate test suite via Anthropic API
        test_suite = generate_test_suite(crawl_data)

        # Step 3: Build .xlsx workbook
        xlsx_bytes = build_workbook(test_suite)

        # Step 4: Stream back as file download
        site_name = test_suite.get("site_name", "qa_suite").lower().replace(" ", "_")
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
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@app.post("/api/generate-from-crawl")
async def generate_from_crawl_endpoint(crawl_data: dict):
    """
    Generate .xlsx from pre-existing crawl data (skip crawl step).
    Useful for re-running generation without re-crawling.
    """
    try:
        test_suite = generate_test_suite(crawl_data)
        xlsx_bytes = build_workbook(test_suite)

        site_name = test_suite.get("site_name", "qa_suite").lower().replace(" ", "_")
        filename = f"{site_name}_qa_suite.xlsx"

        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
