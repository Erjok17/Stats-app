import pandas as pd
import numpy as np


def _min_to_secs(m):
    """'18:02' -> 1082 seconds. Returns 0 for blanks."""
    if not m or ":" not in str(m):
        return 0
    mm, ss = str(m).split(":")[:2]
    try:
        return int(mm) * 60 + int(ss)
    except ValueError:
        return 0


def _secs_to_min(s):
    """1082 -> '18:02'."""
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def _safe_div(a, b):
    return a / b if b else 0.0


# ---------------------------------------------------------------
# Team ratings
# ---------------------------------------------------------------

def team_ratings(box: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, t in box.iterrows():
        fga = int(t["fieldGoalsAttempted"])
        fta = int(t["freeThrowsAttempted"])
        orb = int(t["reboundsOffensive"])
        tov = int(t["turnovers"])
        poss = fga + 0.44 * fta - orb + tov
        rows.append({"teamTricode": t["teamTricode"], "possessions": poss})

    poss_df = pd.DataFrame(rows).set_index("teamTricode")

    out = []
    for _, t in box.iterrows():
        tri = t["teamTricode"]
        opp = box[box["teamTricode"] != tri].iloc[0]
        opp_poss = poss_df.loc[opp["teamTricode"], "possessions"]

        off_rtg = 100 * t["points"] / poss_df.loc[tri, "possessions"]
        def_rtg = 100 * opp["points"] / opp_poss
        out.append({
            "Team": tri,
            "Pace": round(poss_df.loc[tri, "possessions"], 1),
            "OffRtg": round(off_rtg, 1),
            "DefRtg": round(def_rtg, 1),
            "NetRtg": round(off_rtg - def_rtg, 1),
        })
    return pd.DataFrame(out).sort_values("NetRtg", ascending=False)


# ---------------------------------------------------------------
# Player metrics
# ---------------------------------------------------------------

def player_metrics(players: pd.DataFrame, team_totals: pd.DataFrame) -> pd.DataFrame:
    team_map = team_totals.set_index("teamTricode").to_dict("index")

    rows = []
    for _, p in players.iterrows():
        tri = p["teamTricode"]
        tt = team_map.get(tri, {})

        fga = p["fga"]
        fgm = p["fgm"]
        tpa = p["tpa"]
        tpm = p["tpm"]
        fta = p["fta"]
        ftm = p["ftm"]
        pts = p["points"]
        tov = p["tov"]
        ast = p["ast"]
        oreb = p["oreb"]
        dreb = p["dreb"]
        pf = p["pf"]

        team_fga = tt.get("fieldGoalsAttempted", 0) or 0
        team_fta = tt.get("freeThrowsAttempted", 0) or 0
        team_tov = tt.get("turnovers", 0) or 0
        team_pts = tt.get("points", 0) or 0
        team_oreb = tt.get("reboundsOffensive", 0) or 0
        team_dreb = tt.get("reboundsDefensive", 0) or 0

        ts = _safe_div(pts, 2 * (fga + 0.44 * fta))
        efg = _safe_div(fgm + 0.5 * tpm, fga)
        usg_num = fga + 0.44 * fta + tov
        usg_den = team_fga + 0.44 * team_fta + team_tov
        usg = _safe_div(usg_num, usg_den)

        rows.append({
            "Player": p["playerName"],
            "Team": tri,
            "MIN_secs": _min_to_secs(p["minutes"]),
            "PTS": pts,
            "FGM": fgm, "FGA": fga,
            "3PM": tpm, "3PA": tpa,
            "FTM": ftm, "FTA": fta,
            "OREB": oreb, "DREB": dreb,
            "AST": ast, "TOV": tov,
            "STL": p["stl"], "BLK": p["blk"], "PF": pf,
            "eFG%": round(efg, 3),
            "TS%": round(ts, 3),
            "USG%": round(usg, 3),
            "AST/TO": round(_safe_div(ast, tov), 2),
            "ORB%": round(_safe_div(oreb, team_oreb), 3),
            "DRB%": round(_safe_div(dreb, team_dreb), 3),
        })

    df = pd.DataFrame(rows)
    if "MIN_secs" in df.columns:
        df["MIN"] = df["MIN_secs"].apply(_secs_to_min)
        cols = ["Player", "Team", "MIN"] + [c for c in df.columns if c not in ("Player", "Team", "MIN")]
        df = df[cols]
    return df


# ---------------------------------------------------------------
# Scouting report
# ---------------------------------------------------------------

BENCH = {
    "eFG%":   {"weak": 0.45, "elite": 0.55},
    "TS%":    {"weak": 0.50, "elite": 0.60},
    "AST/TO": {"weak": 1.00, "elite": 2.50},
    "USG%":   {"low": 0.15, "high": 0.28},
    "ORB%":   {"weak": 0.05, "elite": 0.15},
}


def scouting_report(p: pd.Series) -> dict:
    strengths, weaknesses = [], []
    how_score, how_defend = [], []

    if p["eFG%"] >= BENCH["eFG%"]["elite"]:
        strengths.append(f"Elite shooter (eFG% {p['eFG%']:.3f})")
    elif p["eFG%"] < BENCH["eFG%"]["weak"]:
        weaknesses.append(f"Struggles with shot efficiency (eFG% {p['eFG%']:.3f})")

    if p["TS%"] >= BENCH["TS%"]["elite"]:
        strengths.append(f"Highly efficient scorer (TS% {p['TS%']:.3f})")
    elif p["TS%"] < BENCH["TS%"]["weak"]:
        weaknesses.append(f"Below-average efficiency (TS% {p['TS%']:.3f})")

    if p["AST/TO"] >= BENCH["AST/TO"]["elite"]:
        strengths.append(f"Excellent ball control (AST/TO {p['AST/TO']:.2f})")
    elif p["AST/TO"] < BENCH["AST/TO"]["weak"] and p["TOV"] > 1:
        weaknesses.append(f"Turnover-prone (AST/TO {p['AST/TO']:.2f})")

    if p["USG%"] >= BENCH["USG%"]["high"]:
        strengths.append(f"High-usage focal point (USG% {p['USG%']:.1%})")
    elif p["USG%"] < BENCH["USG%"]["low"]:
        weaknesses.append(f"Low involvement (USG% {p['USG%']:.1%}) — needs to be more aggressive")

    if p["ORB%"] >= BENCH["ORB%"]["elite"]:
        strengths.append(f"Strong offensive rebounder (ORB% {p['ORB%']:.1%})")

    if p["3PA"] >= 4:
        how_defend.append("Close out hard on the 3-point line — high volume shooter")
    if p["FTA"] >= 4:
        how_defend.append("Don't foul — draws contact and gets to the line")
    if p["3PA"] <= 1 and p["FGA"] >= 5:
        how_defend.append("Sag off — prefers to score inside the arc")
    if p["AST"] >= 4:
        how_defend.append("Deny passing lanes — creates for teammates")

    if p["PF"] >= 3:
        how_score.append("Attack them — foul-prone")
    if (p["STL"] + p["BLK"]) <= 1:
        how_score.append("Drive at them — low defensive playmaking")

    if p["FTA"] >= 3 and (p["FTM"] / p["FTA"] < 0.65):
        weaknesses.append(f"Free throw shooting ({int(p['FTM'])}/{int(p['FTA'])}) — critical in close games")
    if p["TOV"] >= 3:
        weaknesses.append("Ball security — too many turnovers")
    if p["PF"] >= 4:
        weaknesses.append("Foul trouble — defend without reaching")

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "how_to_score_on_them": how_score,
        "how_to_defend_them": how_defend,
    }