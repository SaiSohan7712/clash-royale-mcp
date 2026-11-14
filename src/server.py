"""Clash Royale MCP server: suggests the best deck for your card levels."""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

import store
from client import ClashClient, ClashAPIError
from collector import collect
from recommend import owned_cards, score_decks

mcp = MCPServer(
    "clash-royale",
    instructions=(
        "Tools for choosing a Clash Royale deck. Typical flow: call meta_status to see "
        "what data exists (run collect_meta if empty), then recommend_decks with the "
        "player's tag. Explain the trade-off between meta win rate and the player's "
        "card-level deficit."
    ),
)

_client: ClashClient | None = None


def resolve_tag(tag: str | None) -> str:
    """Use the given tag, else PLAYER_TAG from .env."""
    tag = (tag or os.environ.get("PLAYER_TAG", "")).strip()
    if not tag:
        raise ClashAPIError("No player tag given and PLAYER_TAG is empty in .env.")
    return tag


def client() -> ClashClient:
    global _client
    if _client is None:
        _client = ClashClient()
    return _client


@mcp.tool()
async def get_my_cards(player_tag: str | None = None) -> dict:
    """Get a player's profile and every card they own with level (level/maxLevel).
    Omit player_tag to use PLAYER_TAG from .env."""
    try:
        p = await client().player(resolve_tag(player_tag))
    except ClashAPIError as e:
        return {"error": str(e)}
    cards = sorted(owned_cards(p).values(), key=lambda c: -c["level"])
    return {
        "name": p["name"],
        "trophies": p.get("trophies"),
        "current_deck": [c["name"] for c in p.get("currentDeck", [])],
        "card_count": len(cards),
        "cards": [f"{c['name']} {c['level']}/{c['maxLevel']}" for c in cards],
    }


@mcp.tool()
async def collect_meta(top_players: int = 200) -> dict:
    """Fetch battle logs of the top Path of Legends players and store their deck
    results locally. Run this regularly; history is built from the first run onward."""
    try:
        return await collect(client(), top=top_players)
    except ClashAPIError as e:
        return {"error": str(e)}


@mcp.tool()
def meta_status() -> dict:
    """Show which seasons (YYYY-MM) have collected battle data and how much."""
    conn = store.connect()
    try:
        return {"seasons": store.seasons_collected(conn)}
    finally:
        conn.close()


@mcp.tool()
def get_meta_decks(season: str | None = None, min_games: int = 5, top: int = 10) -> list[dict]:
    """Best decks by win rate among top players. season is YYYY-MM (omit for all
    collected data)."""
    conn = store.connect()
    try:
        decks = store.deck_stats(conn, season, min_games)
    finally:
        conn.close()
    decks.sort(key=lambda d: -(d["wins"] / d["games"]))
    return [
        {
            "cards": [c["name"] for c in d["cards"]],
            "avg_elixir": d["avg_elixir"],
            "games": d["games"],
            "winrate": round(d["wins"] / d["games"], 3),
        }
        for d in decks[:top]
    ]


@mcp.tool()
async def recommend_decks(
    player_tag: str | None = None, season: str | None = None, min_games: int = 5, top: int = 5
) -> dict:
    """Rank meta decks for THIS player: meta win rate adjusted by how far the
    player's card levels are below max, excluding decks with cards they don't own.
    Omit player_tag to use PLAYER_TAG from .env."""
    conn = store.connect()
    try:
        decks = store.deck_stats(conn, season, min_games)
    finally:
        conn.close()
    if not decks:
        return {"error": "No meta data yet. Run collect_meta first (or lower min_games)."}
    try:
        player = await client().player(resolve_tag(player_tag))
    except ClashAPIError as e:
        return {"error": str(e)}
    return {
        "player": player["name"],
        "decks_considered": len(decks),
        "recommendations": score_decks(player, decks, top),
        "how_scored": "fit_score = shrunk meta win rate - 0.012 * total level deficit",
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"ok": True})


@mcp.custom_route("/collect", methods=["POST"])
async def collect_endpoint(request):
    """Scheduled trigger (e.g. GitHub Actions cron). Requires COLLECT_TOKEN."""
    from starlette.responses import JSONResponse
    token = os.environ.get("COLLECT_TOKEN", "")
    if not token or request.headers.get("authorization") != f"Bearer {token}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        return JSONResponse(await collect(client(), top=int(os.environ.get("COLLECT_TOP", "200"))))
    except ClashAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


if __name__ == "__main__":
    if os.environ.get("MCP_TRANSPORT", "stdio") == "http":
        import uvicorn
        app = mcp.streamable_http_app(host="0.0.0.0", stateless_http=True)
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
    else:
        mcp.run()
