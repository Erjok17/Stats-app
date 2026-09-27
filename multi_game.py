import time
from pathlib import Path
import pandas as pd

from fuba import fetch_fuba_pbp, fetch_fuba_boxscore, fetch_fuba_players
from analytics import player_metrics, team_ratings, _secs_to_min, _min_to_secs

DATA_DIR = Path(__file__).resolve().parent / "data"


def fetch_games(game_ids: list[str], league: str = "UBBF", delay: float = 1.0):
    pbops, boxes, playerss = [], [], []
    for gid in game_ids:
        gid = gid.strip()
        if not gid:
            continue
        try:
            pb = fetch_fuba_pbp(gid, league=league, save=True)
            bx = fetch_fuba_boxscore(gid, league=league)
            pl = fetch_fuba_players(gid, league=league)
            pbops.append(pb)
            boxes.append(bx.assign(gameId=gid))
            playerss.append(pl.assign(gameId=gid))
            print(f"Fetched {gid}: {len(pb)} pbp rows, {len(pl)} players")
            time.sleep(delay)
        except Exception as e:
            print(f"Skipping {gid}: {e}")
    return pbops, boxes, playerss


def aggregate_players(players_list, boxes_list):
    per_game = []
    for pl, bx in zip(players_list, boxes_list):
        m = player_metrics(pl, bx)
        m["gameId"] = bx["gameId"].iloc[0]
        per_game.append(m)

    if not per_game:
        return pd.DataFrame()

    all_pg = pd.concat(per_game, ignore_index=True)

    if "MIN_secs" not in all_pg.columns:
        if "MIN" in all_pg.columns:
            all_pg["MIN_secs"] = all_pg["MIN"].apply(_min_to_secs)
        else:
            all_pg["MIN_secs"] = 0

    for c in all_pg.columns:
        if c in ("Player", "Team", "gameId", "MIN"):
            continue
        all_pg[c] = pd.to_numeric(all_pg[c], errors="coerce")

    drop_for_mean = {"Player", "Team", "gameId", "MIN"}
    numeric_cols = [c for c in all_pg.columns if c not in drop_for_mean]
    numeric_cols = [c for c in numeric_cols if all_pg[c].notna().any()]

    agg = (
        all_pg.groupby(["Player", "Team"], as_index=False, sort=False)[numeric_cols]
        .mean()
    )
    agg["GP"] = all_pg.groupby(["Player", "Team"]).size().values

    if "MIN_secs" in agg.columns:
        agg["MIN"] = agg["MIN_secs"].apply(_secs_to_min)
        agg = agg.drop(columns=["MIN_secs"])

    front = ["Player", "Team", "GP", "MIN"]
    rest = [c for c in agg.columns if c not in front]
    agg = agg[front + rest]

    return agg.sort_values("PTS", ascending=False)


def aggregate_teams(boxes_list):
    rows = []
    for bx in boxes_list:
        r = team_ratings(bx)
        r["gameId"] = bx["gameId"].iloc[0]
        rows.append(r)
    if not rows:
        return pd.DataFrame()

    all_rtg = pd.concat(rows, ignore_index=True)

    for c in all_rtg.columns:
        if c in ("Team", "gameId"):
            continue
        all_rtg[c] = pd.to_numeric(all_rtg[c], errors="coerce")

    numeric = [c for c in all_rtg.columns if c not in ("Team", "gameId")]
    numeric = [c for c in numeric if all_rtg[c].notna().any()]

    agg = all_rtg.groupby("Team", as_index=False)[numeric].mean()
    agg["GP"] = all_rtg.groupby("Team").size().values
    return agg.sort_values("NetRtg", ascending=False)