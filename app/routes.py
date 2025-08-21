from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from .clients import http_client
from .config import settings
from .schemas import CaptionResponse, HealthResponse, OcrResponse, ScrapeRequest, ScrapeResponse
from .scraper import scrape_url


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/proxy/ocr", response_model=OcrResponse)
async def proxy_ocr(file: Annotated[UploadFile, File(...)]) -> OcrResponse:
    try:
        async with http_client() as client:
            files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
            resp = await client.post(settings.ocr_api_url, files=files)
            resp.raise_for_status()
            data = resp.json()
            return OcrResponse(text=data.get("text", ""))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCR upstream error: {exc}")


@router.post("/proxy/caption", response_model=CaptionResponse)
async def proxy_caption(file: Annotated[UploadFile, File(...)]) -> CaptionResponse:
    try:
        async with http_client() as client:
            files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
            resp = await client.post(settings.caption_api_url, files=files)
            resp.raise_for_status()
            data = resp.json()
            return CaptionResponse(caption=data.get("caption", ""))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Caption upstream error: {exc}")


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    try:
        result = scrape_url(payload.url, headless=payload.headless)
        return ScrapeResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scrape error: {exc}")

