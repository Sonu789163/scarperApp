from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class OcrResponse(BaseModel):
    text: str


class CaptionResponse(BaseModel):
    caption: str


class ScrapeRequest(BaseModel):
    url: str = Field(description="Page URL to scrape")


class ScrapeResponse(BaseModel):
    title: str
    content: str
    images: List[str] = []
    metadata: Dict[str, Any] = {}
    url: str
    status: str
    error: Optional[str] = None

