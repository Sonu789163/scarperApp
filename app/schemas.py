from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class OcrResponse(BaseModel):
    text: str


class CaptionResponse(BaseModel):
    caption: str


class ScrapeRequest(BaseModel):
    url: str = Field(description="Page URL to scrape")
    headless: bool = Field(default=True, description="Run browser headless")


class ScrapeResponse(BaseModel):
    title: str
    text: str
    images: list[str] = []

