from pathlib import Path
import requests
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

BASE = "https://fibalivestats.dcd.shared.geniussports.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------

def _fetch_json(game_id: str, league: str = "UBBF") -> dict:
    """Two-step fetch: HTML first (sets session), then JSON."""
    s = requests.Session()
    html_url = f"{BASE}/u/{league}/{game_id}/bs.html"
    s.get(html_url, headers=HEADERS)
    r = s.get(
        f"{BASE}/data/{game_id}/data.json",
        headers={**HEADERS, "Referer": html_url, "Accept": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------
# Box score → NBA-style schema
# ---------------------------------------------------------------

def fetch_fuba_boxscore(game_id: str, league: str = "UBBF") -> pd.DataFrame:
    data = _fetch_json(game_id, league)
    teams = data["tm"]

    rows = []
    for tno in ("1", "2"):
        t = teams[tno]
        rows.append({
            "teamTricode": t["code"],
            "teamName": t["name"],
            "points": t["score"],
            "fieldGoalsMade": t["tot_sFieldGoalsMade"],
            "fieldGoalsAttempted": t["tot_sFieldGoalsAttempted"],
            "threePointersMade": t["tot_sThreePointersMade"],
            "threePointersAttempted": t["tot_sThreePointersAttempted"],
            "freeThrowsMade": t["tot_sFreeThrowsMade"],
            "freeThrowsAttempted": t["tot_sFreeThrowsAttempted"],
            "reboundsOffensive": t["tot_sReboundsOffensive"],
            "reboundsDefensive": t["tot_sReboundsDefensive"],
            "turnovers": t["tot_sTurnovers"],
            "assists": t["tot_sAssists"],
            "steals": t["tot_sSteals"],
            "blocks": t["tot_sBlocks"],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# Play-by-play → NBA-style schema
# ---------------------------------------------------------------

def fetch_fuba_pbp(
    game_id: str,
    league: str = "UBBF",
    save: bool = True,
) -> pd.DataFrame:
    data = _fetch_json(game_id, league)
    teams = data["tm"]
    tno_to_code = {"1": teams["1"]["code"], "2": teams["2"]["code"]}

    rows = []
    for e in data["pbp"]:
        at = (e.get("actionType") or "").lower()
        success = e.get("success", 0)
        is_fg = at in ("2pt", "3pt")

        if at == "3pt":
            shot_value = 3
        elif at == "2pt":
            shot_value = 2
        elif at == "freethrow":
            shot_value = 1
        else:
            shot_value = 0

        # Only shots and free throws have a meaningful Made/Missed result
        if at in ("2pt", "3pt", "freethrow"):
            shot_result = "Made" if success == 1 else "Missed"
        else:
            shot_result = ""

        rows.append({
            "gameId": game_id,
            "actionNumber": e.get("actionNumber"),
            "period": e.get("period"),
            "clock": e.get("clock"),
            "teamTricode": tno_to_code.get(str(e.get("tno")), ""),
            "personId": e.get("shirtNumber", ""),
            "playerName": e.get("player", ""),
            "actionType": at,
            "subType": e.get("subType", ""),
            "shotResult": shot_result,
            "isFieldGoal": 1 if is_fg else 0,
            "shotValue": shot_value,
            "scoreHome": e.get("s1"),
            "scoreAway": e.get("s2"),
        })

    df = pd.DataFrame(rows)

    if save:
        out = DATA_DIR / f"fuba_pbp_{game_id}.csv"
        df["gameId"] = df["gameId"].astype(str)
        df.to_csv(out, index=False)
        print(f"Saved {len(df)} rows to {out}")

    return df


# ---------------------------------------------------------------
# Per-player box score
# ---------------------------------------------------------------

def _get_num(d: dict, *keys, default=0):
    """Return the first present key's value, else default."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def fetch_fuba_players(game_id: str, league: str = "UBBF") -> pd.DataFrame:
    """
    Per-player box score from FIBA LiveStats.
    `pl` may be a dict (keyed by player number) or a list — handle both.
    """
    data = _fetch_json(game_id, league)
    teams = data["tm"]

    rows = []
    for tno in ("1", "2"):
        team = teams[tno]
        code = team["code"]

        pl = team.get("pl", {})
        if isinstance(pl, dict):
            players_iter = pl.values()
        elif isinstance(pl, list):
            players_iter = pl
        else:
            players_iter = []

        for p in players_iter:
            if not isinstance(p, dict):
                continue
            full_name = (
                p.get("name")
                or p.get("playerName")
                or f"{p.get('firstName','')} {p.get('familyName','')}".strip()
            )
            rows.append({
                "teamTricode": code,
                "playerName": full_name,
                "shirtNumber": p.get("shirtNumber", p.get("no", "")),
                "starter": p.get("starter", 0),
                "position": p.get("playingPosition", ""),
                "minutes": _get_num(p, "sMinutes", "minutes", "min", default="0:00"),
                "points": _get_num(p, "sPoints", "points", "pts"),
                "fgm": _get_num(p, "sFieldGoalsMade", "fieldGoalsMade", "fgm"),
                "fga": _get_num(p, "sFieldGoalsAttempted", "fieldGoalsAttempted", "fga"),
                "tpm": _get_num(p, "sThreePointersMade", "threePointersMade", "tpm"),
                "tpa": _get_num(p, "sThreePointersAttempted", "threePointersAttempted", "tpa"),
                "ftm": _get_num(p, "sFreeThrowsMade", "freeThrowsMade", "ftm"),
                "fta": _get_num(p, "sFreeThrowsAttempted", "freeThrowsAttempted", "fta"),
                "oreb": _get_num(p, "sReboundsOffensive", "reboundsOffensive", "oreb"),
                "dreb": _get_num(p, "sReboundsDefensive", "reboundsDefensive", "dreb"),
                "ast": _get_num(p, "sAssists", "assists", "ast"),
                "tov": _get_num(p, "sTurnovers", "turnovers", "tov"),
                "stl": _get_num(p, "sSteals", "steals", "stl"),
                "blk": _get_num(p, "sBlocks", "blocks", "blk"),
                "pf": _get_num(p, "sFoulsPersonal", "foulsPersonal", "pf"),
            })

    df = pd.DataFrame(rows)

    num_cols = ["points", "fgm", "fga", "tpm", "tpa", "ftm", "fta",
                "oreb", "dreb", "ast", "tov", "stl", "blk", "pf"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    return df


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------

if __name__ == "__main__":
    import sys

    game_id = sys.argv[1] if len(sys.argv) > 1 else "2913911"
    league = sys.argv[2] if len(sys.argv) > 2 else "UBBF"

    print(f"=== {league} Game {game_id} ===")

    print("\n=== Box Score ===")
    box = fetch_fuba_boxscore(game_id, league=league)
    print(box.to_string(index=False))

    print("\n=== Play-by-Play (first 10) ===")
    pbp = fetch_fuba_pbp(game_id, league=league, save=True)
    print(pbp.head(10).to_string(index=False))

    print("\n=== Action types ===")
    print(pbp["actionType"].value_counts())

    print("\n=== Players (first 10) ===")
    players = fetch_fuba_players(game_id, league=league)
    print(players.head(10).to_string(index=False))