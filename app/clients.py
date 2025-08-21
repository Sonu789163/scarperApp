from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from .config import settings


@asynccontextmanager
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client


