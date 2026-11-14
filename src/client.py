"""Thin async client for the official Clash Royale API."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Override to route through a fixed-IP proxy (e.g. https://proxy.royaleapi.dev/v1).
BASE_URL = os.environ.get("CLASH_API_BASE", "https://api.clashroyale.com/v1").rstrip("/")


class ClashAPIError(Exception):
    pass


def normalize_tag(tag: str) -> str:
    tag = tag.strip().upper().replace("O", "0")
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


class ClashClient:
    def __init__(self) -> None:
        key = os.environ.get("CLASH_ROYALE_KEY", "").strip()
        if not key:
            raise ClashAPIError("CLASH_ROYALE_KEY is empty. Add it to the .env file.")
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )

    async def get(self, path: str, params: dict | None = None):
        for attempt in range(4):
            r = await self._http.get(path, params=params)
            if r.status_code == 429:  # rate limited
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            break
        if r.status_code == 403:
            raise ClashAPIError(
                "403 from Clash Royale API: your current public IP is not on the key's "
                "allowed list (or the key is invalid). Check your IP and update the key "
                "at developer.clashroyale.com."
            )
        if r.status_code == 404:
            raise ClashAPIError(f"404 not found: {path} (check the player tag).")
        if r.status_code != 200:
            raise ClashAPIError(f"API error {r.status_code}: {r.text[:200]}")
        return r.json()

    async def player(self, tag: str) -> dict:
        return await self.get(f"/players/{quote(normalize_tag(tag))}")

    async def battlelog(self, tag: str) -> list[dict]:
        return await self.get(f"/players/{quote(normalize_tag(tag))}/battlelog")

    async def top_players(self, limit: int = 200, season: str | None = None) -> list[dict]:
        base = "/locations/global/pathoflegend"
        path = f"{base}/{season}/rankings/players" if season else f"{base}/players"
        return (await self.get(path, {"limit": limit}))["items"]

    async def aclose(self) -> None:
        await self._http.aclose()
