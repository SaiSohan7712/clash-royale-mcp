# clash-royale-mcp

MCP server that recommends a Clash Royale deck from your card levels plus the
decks winning most among top Path of Legends players.

## Setup
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # then set CLASH_ROYALE_KEY (developer.clashroyale.com)

The key is bound to your public IP; a 403 means the IP changed.

## Collect meta data (run regularly, e.g. daily)
    python src/collector.py --top 300

The official API only exposes recent battles, so season history (YYYY-MM)
accumulates from your first collection onward; it cannot be backfilled.

## Tools
get_my_cards, collect_meta, meta_status, get_meta_decks, recommend_decks

## Hosted mode
Set `MCP_TRANSPORT=http` to serve MCP at `/mcp` (streamable HTTP), plus `/health`
and `POST /collect` (needs `Authorization: Bearer $COLLECT_TOKEN`, for a daily cron).
`CLASH_API_BASE` can point at a fixed-IP proxy; `DATA_DIR` at a persistent disk.
Deploy on Render with `render.yaml` / `Dockerfile`. Free-tier disks are ephemeral.
