"""SQLite storage for collected meta-deck battle results."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# DATA_DIR lets a host point the DB at a persistent disk.
DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
DB_PATH = DATA_DIR / "meta.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    deck_key TEXT PRIMARY KEY,
    cards_json TEXT NOT NULL,
    avg_elixir REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS battles (
    player_tag TEXT NOT NULL,
    battle_time TEXT NOT NULL,
    season TEXT NOT NULL,          -- YYYY-MM, taken from battle_time
    deck_key TEXT NOT NULL,
    won INTEGER NOT NULL,
    PRIMARY KEY (player_tag, battle_time)
);
CREATE INDEX IF NOT EXISTS idx_battles_season ON battles(season, deck_key);
"""


DATABASE_URL = os.environ.get("DATABASE_URL", "")


class _PG:
    """Minimal adapter so the same '?' SQL runs on Postgres."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, args=()):
        return self._c.execute(sql.replace("?", "%s"), args)

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def connect():
    if DATABASE_URL:  # hosted: free Postgres (e.g. Neon) survives restarts
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        conn.execute(SCHEMA)
        conn.commit()
        return _PG(conn)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_battle(conn, player_tag, battle_time, cards, won) -> bool:
    """Insert one battle. Returns True if it was new."""
    ids = sorted(c["id"] for c in cards)
    key = "-".join(map(str, ids))
    slim = [
        {
            "id": c["id"],
            "name": c["name"],
            "maxLevel": c.get("maxLevel"),
            "elixir": c.get("elixirCost", 0),
            "rarity": c.get("rarity"),
            "evo": bool(c.get("evolutionLevel")),
        }
        for c in sorted(cards, key=lambda c: c["id"])
    ]
    elixir = sum(c["elixir"] or 0 for c in slim) / len(slim)
    season = f"{battle_time[:4]}-{battle_time[4:6]}"
    conn.execute(
        "INSERT INTO decks VALUES (?,?,?) ON CONFLICT DO NOTHING",
        (key, json.dumps(slim), round(elixir, 2)),
    )
    cur = conn.execute(
        "INSERT INTO battles VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
        (player_tag, battle_time, season, key, int(won)),
    )
    return cur.rowcount > 0


def deck_stats(conn, season: str | None = None, min_games: int = 5) -> list[dict]:
    where, args = ("WHERE b.season = ?", [season]) if season else ("", [])
    rows = conn.execute(
        f"""SELECT b.deck_key, d.cards_json, d.avg_elixir,
                   COUNT(*) AS games, SUM(b.won) AS wins
            FROM battles b JOIN decks d USING (deck_key)
            {where}
            GROUP BY b.deck_key, d.cards_json, d.avg_elixir
            HAVING COUNT(*) >= ?""",
        args + [min_games],
    ).fetchall()
    return [
        {
            "deck_key": r["deck_key"],
            "cards": json.loads(r["cards_json"]),
            "avg_elixir": r["avg_elixir"],
            "games": r["games"],
            "wins": int(r["wins"]),
        }
        for r in rows
    ]


def seasons_collected(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT season, COUNT(*) AS battles, COUNT(DISTINCT player_tag) AS players "
        "FROM battles GROUP BY season ORDER BY season"
    ).fetchall()
    return [dict(r) for r in rows]
