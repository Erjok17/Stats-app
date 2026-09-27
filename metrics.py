from pathlib import Path
import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv3

DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------

def load_pbp(game_id: str, source: str = "nba") -> pd.DataFrame:
    """Load cached play-by-play CSV."""
    prefix = "fuba_pbp_" if source == "fuba" else "pbp_"
    return pd.read_csv(
        DATA_DIR / f"{prefix}{game_id}.csv",
        dtype={"gameId": str},
    )


def load_boxscore(game_id: str, source: str = "nba") -> pd.DataFrame:
    """NBA box score from API, or FUBA box score from the same JSON."""
    if source == "fuba":
        from fuba import fetch_fuba_boxscore
        return fetch_fuba_boxscore(game_id)

    game_id = str(game_id).zfill(10)
    box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
    df = box.team_stats.get_data_frame().copy()
    df = df[df["teamTricode"].notna()]
    if df.empty:
        raise RuntimeError(
            f"Empty box score for {game_id!r}. Likely rate-limited."
        )
    return df.reset_index(drop=True)


# ---------------------------------------------------------------
# Possessions (Basketball-Reference estimate)
# ---------------------------------------------------------------

def estimated_possessions(box: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, t in box.iterrows():
        fga = int(t["fieldGoalsAttempted"])
        fta = int(t["freeThrowsAttempted"])
        orb = int(t["reboundsOffensive"])
        tov = int(t["turnovers"])
        pts = int(t["points"])

        poss = fga + 0.44 * fta - orb + tov
        rows.append({
            "Team": t["teamTricode"],
            "Points": pts,
            "Possessions": round(poss, 1),
            "PPP": round(pts / poss, 3) if poss else 0.0,
        })
    return pd.DataFrame(rows).sort_values("PPP", ascending=False)


# ---------------------------------------------------------------
# Four Factors
# ---------------------------------------------------------------

def four_factors(box: pd.DataFrame) -> pd.DataFrame:
    lookup = {row["teamTricode"]: row for _, row in box.iterrows()}

    rows = []
    for tri, t in lookup.items():
        opp = next(v for k, v in lookup.items() if k != tri)

        fga = int(t["fieldGoalsAttempted"])
        fgm = int(t["fieldGoalsMade"])
        fg3m = int(t["threePointersMade"])
        fta = int(t["freeThrowsAttempted"])
        tov = int(t["turnovers"])
        orb = int(t["reboundsOffensive"])
        opp_drb = int(opp["reboundsDefensive"])

        efg = (fgm + 0.5 * fg3m) / fga if fga else 0
        denom = fga + 0.44 * fta + tov
        tov_pct = tov / denom if denom else 0
        orb_pct = orb / (orb + opp_drb) if (orb + opp_drb) else 0
        ft_rate = fta / fga if fga else 0

        rows.append({
            "Team": tri,
            "FGA": fga, "FGM": fgm, "3PM": fg3m,
            "FTA": fta, "TOV": tov, "ORB": orb,
            "eFG%": round(efg, 3),
            "TOV%": round(tov_pct, 3),
            "ORB%": round(orb_pct, 3),
            "FTr": round(ft_rate, 3),
        })
    return pd.DataFrame(rows).sort_values("eFG%", ascending=False)


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------

if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "nba"
    game_id = sys.argv[2] if len(sys.argv) > 2 else (
        "2913911" if source == "fuba" else "0022300001"
    )

    box = load_boxscore(game_id, source=source)
    print(f"=== {source.upper()} Box Score ===")
    print(box.to_string(index=False))

    print("\n=== Possessions & PPP ===")
    print(estimated_possessions(box).to_string(index=False))

    print("\n=== Four Factors ===")
    print(four_factors(box).to_string(index=False))