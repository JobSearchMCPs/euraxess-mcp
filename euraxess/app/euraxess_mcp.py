# euraxess_mcp.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import httpx, xmltodict, logging
from dateutil import parser as dateparser
from pydantic import BaseModel
from typing import List, Optional
import os
from functools import lru_cache

app = FastAPI(title="euraxess-mcp", version="0.1.0")
logger = logging.getLogger("uvicorn.error")

EURAXESS_RSS = os.getenv("EURAXESS_RSS", "https://euraxess.ec.europa.eu/job-feed")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "50"))

class JobItem(BaseModel):
    source: str
    source_ref: Optional[str]
    url: Optional[str]
    title: Optional[str]
    description_raw: Optional[str]
    posted_date: Optional[str]
    raw: Optional[dict]

def _parse_item(item) -> JobItem:
    title = item.get("title")
    link = item.get("link")
    desc = item.get("description") or ""
    pubDate = item.get("pubDate")
    try:
        posted_date = dateparser.parse(pubDate).date().isoformat() if pubDate else None
    except Exception:
        posted_date = None
    source_ref = item.get("guid") or link
    return JobItem(
        source="euraxess",
        source_ref=source_ref,
        url=link,
        title=title,
        description_raw=desc,
        posted_date=posted_date,
        raw=item
    )

@lru_cache(maxsize=32)
def parse_rss_text_to_items(rss_text: str) -> List[JobItem]:
    data = xmltodict.parse(rss_text)
    items = data.get("rss", {}).get("channel", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    parsed = [_parse_item(it) for it in items]
    return parsed

@app.get("/list_jobs", response_model=dict)
async def list_jobs(limit: int = Query(DEFAULT_LIMIT, ge=1, le=500)):
    """Return latest jobs from the EURAXESS RSS feed, normalized."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(EURAXESS_RSS, headers={"User-Agent":"euraxess-mcp/0.1"})
            r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch EURAXESS feed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch euraxess feed")
    items = parse_rss_text_to_items(r.text)
    result = {"count": len(items[:limit]), "jobs": [i.dict() for i in items[:limit]]}
    return JSONResponse(result)

@app.get("/get_job", response_model=dict)
async def get_job(url: str = Query(...)):
    """Fetch raw job page HTML (for richer parsing)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers={"User-Agent":"euraxess-mcp/0.1"})
            r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch job url %s : %s", url, exc)
        raise HTTPException(status_code=502, detail="Failed to fetch job URL")
    return {"url": url, "status_code": r.status_code, "headers": dict(r.headers), "raw_html": r.text}

@app.get("/health", response_model=dict)
def health():
    return {"ok": True}

@app.get("/meta", response_model=dict)
def meta():
    """Machine-readable descriptor for the Agent registry."""
    return {
        "name":"euraxess",
        "description":"EURAXESS RSS feed connector. list_jobs(limit), get_job(url).",
        "endpoints": {
            "list_jobs": {"method":"GET","path":"/list_jobs","params":[{"name":"limit","type":"int","required":False}]},
            "get_job": {"method":"GET","path":"/get_job","params":[{"name":"url","type":"string","required":True}]},
            "health": {"method":"GET","path":"/health","params":[]}
        },
        "auth": {"type":"none"}
    }
