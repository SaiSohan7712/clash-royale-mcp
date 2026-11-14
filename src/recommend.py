"""Score meta decks against a player's actual card levels."""
from __future__ import annotations

# Each level below a card's max is roughly a 6-7% stat gap; in win-rate terms
# we treat one level of deficit as ~1.2 percentage points. Tunable.
LEVEL_PENALTY = 0.012
PRIOR_GAMES = 20  # shrink small samples toward 50%


def shrunk_winrate(wins: int, games: int) -> float:
    return (wins + 0.5 * PRIOR_GAMES) / (games + PRIOR_GAMES)


def owned_cards(player: dict) -> dict[int, dict]:
    return {
        c["id"]: {
            "name": c["name"],
            "level": c["level"],
            "maxLevel": c.get("maxLevel", c["level"]),
        }
        for c in player.get("cards", [])
    }


def score_decks(player: dict, decks: list[dict], top: int = 5) -> list[dict]:
    owned = owned_cards(player)
    results = []
    for d in decks:
        missing, details, deficit = [], [], 0
        for c in d["cards"]:
            mine = owned.get(c["id"])
            if not mine:
                missing.append(c["name"])
                continue
            gap = mine["maxLevel"] - mine["level"]
            deficit += gap
            details.append(f"{c['name']} {mine['level']}/{mine['maxLevel']}")
        raw = shrunk_winrate(d["wins"], d["games"])
        avg_gap = deficit / max(len(details), 1)
        fit = raw - LEVEL_PENALTY * deficit
        results.append(
            {
                "cards": [c["name"] for c in d["cards"]],
                "avg_elixir": d["avg_elixir"],
                "games": d["games"],
                "meta_winrate": round(d["wins"] / d["games"], 3),
                "your_levels": details,
                "total_level_deficit": deficit,
                "avg_level_deficit": round(avg_gap, 2),
                "missing_cards": missing,
                "fit_score": round(fit, 4),
                "playable": not missing,
            }
        )
    playable = sorted((r for r in results if r["playable"]), key=lambda r: -r["fit_score"])
    return playable[:top]
