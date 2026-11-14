"""Collect top Path of Legends players' battle logs into the local database.

Run directly:  python src/collector.py --top 300
Run it regularly (e.g. daily) to build up season-by-season history, because the
official API only exposes each player's most recent ~25-60 battles.
"""
from __future__ import annotations

import argparse
import asyncio

from client import ClashClient, ClashAPIError
import store


async def collect(client: ClashClient, top: int = 200, season: str | None = None) -> dict:
    players = await client.top_players(limit=top, season=season)
    conn = store.connect()
    sem = asyncio.Semaphore(5)
    stats = {"players": len(players), "new_battles": 0, "failed": 0}

    async def one(p):
        async with sem:
            try:
                log = await client.battlelog(p["tag"])
            except ClashAPIError:
                stats["failed"] += 1
                return
        for b in log:
            if b.get("type") != "pathOfLegend" or not b.get("team") or not b.get("opponent"):
                continue
            me, opp = b["team"][0], b["opponent"][0]
            if me["crowns"] == opp["crowns"] or len(me.get("cards", [])) != 8:
                continue  # skip draws / malformed
            if store.save_battle(conn, p["tag"], b["battleTime"], me["cards"],
                                 me["crowns"] > opp["crowns"]):
                stats["new_battles"] += 1

    await asyncio.gather(*(one(p) for p in players))
    conn.commit()
    conn.close()
    return stats


async def _main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--season", default=None, help="e.g. 2026-10 (ranking list only)")
    args = ap.parse_args()
    client = ClashClient()
    try:
        print(await collect(client, args.top, args.season))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
