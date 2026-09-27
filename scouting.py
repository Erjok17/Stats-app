# scouting.py
import pandas as pd
import numpy as np

# ---------------------------------------------------------------
# League-average benchmarks (approximate; refine with your data)
# ---------------------------------------------------------------
BENCHMARKS = {
    "eFG%":     {"weak": 0.45, "avg": 0.50, "elite": 0.55},
    "TS%":      {"weak": 0.50, "avg": 0.55, "elite": 0.60},
    "TOV%":     {"elite": 0.10, "avg": 0.15, "weak": 0.20},  # inverted
    "ORB%":     {"weak": 0.20, "avg": 0.26, "elite": 0.32},
    "AST/TO":   {"weak": 1.0,  "avg": 1.5,  "elite": 2.5},
    "USG%":     {"low": 0.15,  "avg": 0.20, "high": 0.28},
    "FT%":      {"weak": 0.60, "avg": 0.72, "elite": 0.82},
    "3P%":      {"weak": 0.28, "avg": 0.33, "elite": 0.38},
}


def _grade(value, thresholds, invert=False):
    """Return 'elite', 'avg', or 'weak' for a value against a thresholds dict."""
    if pd.isna(value):
        return "unknown"
    weak = thresholds.get("weak", thresholds.get("low"))
    avg = thresholds.get("avg")
    elite = thresholds.get("elite", thresholds.get("high"))
    if invert:
        if value <= elite: return "elite"
        if value <= avg:   return "avg"
        return "weak"
    if value >= elite: return "elite"
    if value >= avg:   return "avg"
    return "weak"


def _fmt_pct(v):
    return f"{v:.1%}" if pd.notna(v) else "—"


def _fmt(v, digits=2):
    return f"{v:.{digits}f}" if pd.notna(v) else "—"


# ---------------------------------------------------------------
# Team scouting report
# ---------------------------------------------------------------

def build_team_report(agg_teams: pd.DataFrame, agg_players: pd.DataFrame,
                      team_code: str, sample_size: int) -> dict:
    """
    agg_teams: from multi_game.aggregate_teams()
    agg_players: from multi_game.aggregate_players()
    """
    tr = agg_teams[agg_teams["Team"] == team_code].iloc[0]
    roster = agg_players[agg_players["Team"] == team_code]

    report = {
        "team": team_code,
        "sample_size": sample_size,
        "profile": {},
        "traditional": {},
        "advanced": {},
        "strengths": [],
        "weaknesses": [],
        "exploit": [],
        "avoid": [],
    }

    # --- Profile ---
    report["profile"] = {
        "GP": int(tr["GP"]),
        "OffRtg": _fmt(tr["OffRtg"], 1),
        "DefRtg": _fmt(tr["DefRtg"], 1),
        "NetRtg": _fmt(tr["NetRtg"], 1),
        "Pace": _fmt(tr["Pace"], 1),
    }

    # --- Traditional (per game) ---
    report["traditional"] = {
        "Points": _fmt(tr.get("Points", 0), 1),
        "Rebounds": _fmt(tr.get("Rebounds", 0), 1),
        "Assists": _fmt(tr.get("Assists", 0), 1),
        "Turnovers": _fmt(tr.get("Turnovers", 0), 1),
    }

    # --- Advanced ---
    # eFG% = (FGM + 0.5*3PM) / FGA
    fgm = tr.get("FGM", tr.get("fieldGoalsMade", 0))
    fga = tr.get("FGA", tr.get("fieldGoalsAttempted", 0))
    tpm = tr.get("3PM", tr.get("threePointersMade", 0))
    fta = tr.get("FTA", tr.get("freeThrowsAttempted", 0))
    pts = tr.get("Points", tr.get("points", 0))
    tov = tr.get("Turnovers", tr.get("turnovers", 0))
    ast = tr.get("Assists", tr.get("assists", 0))
    oreb = tr.get("OREB", tr.get("reboundsOffensive", 0))

    efg = (fgm + 0.5 * tpm) / fga if fga else 0
    ts = pts / (2 * (fga + 0.44 * fta)) if (fga + 0.44 * fta) else 0
    tov_pct = tov / (fga + 0.44 * fta + tov) if (fga + 0.44 * fta + tov) else 0
    ast_to = ast / tov if tov else 0

    report["advanced"] = {
        "eFG%": _fmt_pct(efg),
        "TS%": _fmt_pct(ts),
        "TOV%": _fmt_pct(tov_pct),
        "AST/TO": _fmt(ast_to, 2),
    }

    # --- Strengths / Weaknesses ---
    efg_grade = _grade(efg, BENCHMARKS["eFG%"])
    tov_grade = _grade(tov_pct, BENCHMARKS["TOV%"], invert=True)
    ast_grade = _grade(ast_to, BENCHMARKS["AST/TO"])

    if efg_grade == "elite":
        report["strengths"].append(f"Elite shooting efficiency (eFG% {_fmt_pct(efg)})")
    elif efg_grade == "weak":
        report["weaknesses"].append(f"Poor shooting efficiency (eFG% {_fmt_pct(efg)})")

    if tov_grade == "weak":
        report["weaknesses"].append(f"Turnover-prone (TOV% {_fmt_pct(tov_pct)})")
    elif tov_grade == "elite":
        report["strengths"].append(f"Excellent ball security (TOV% {_fmt_pct(tov_pct)})")

    if ast_grade == "elite":
        report["strengths"].append(f"Strong playmaking (AST/TO {_fmt(ast_to, 2)})")

    # --- Exploit / Avoid ---
    if tov_grade == "weak":
        report["exploit"].append("Pressure the ball — live-ball turnovers")
    if efg_grade == "weak":
        report["exploit"].append("Force them into half-court jump shots")

    if efg_grade == "elite":
        report["avoid"].append("Don't leave shooters open — they convert efficiently")
    if ast_grade == "elite":
        report["avoid"].append("Disrupt passing lanes — they create easy looks")

    # --- Key players ---
    top = roster.sort_values("PTS", ascending=False).head(3)
    report["key_players"] = []
    for _, p in top.iterrows():
        report["key_players"].append({
            "name": p["Player"],
            "pts": _fmt(p["PTS"], 1),
            "eFG%": _fmt_pct(p["eFG%"]),
            "USG%": _fmt_pct(p["USG%"]),
        })

    return report


# ---------------------------------------------------------------
# Player scouting report
# ---------------------------------------------------------------

def build_player_report(p: pd.Series, sample_size: int) -> dict:
    """p: a single row from aggregate_players()."""
    report = {
        "player": p["Player"],
        "team": p["Team"],
        "sample_size": sample_size,
        "profile": {},
        "traditional": {},
        "advanced": {},
        "strengths": [],
        "weaknesses": [],
        "how_to_defend": [],
        "how_to_attack": [],
    }

    # --- Profile ---
    report["profile"] = {
        "GP": int(p.get("GP", 0)),
        "MIN": p.get("MIN", "—"),
        "USG%": _fmt_pct(p.get("USG%", 0)),
    }

    # --- Traditional (per game) ---
    report["traditional"] = {
        "PTS": _fmt(p.get("PTS", 0), 1),
        "FGM/A": f"{int(p.get('FGM',0))}/{int(p.get('FGA',0))}",
        "3PM/A": f"{int(p.get('3PM',0))}/{int(p.get('3PA',0))}",
        "FTM/A": f"{int(p.get('FTM',0))}/{int(p.get('FTA',0))}",
        "OREB": _fmt(p.get("OREB", 0), 1),
        "DREB": _fmt(p.get("DREB", 0), 1),
        "AST": _fmt(p.get("AST", 0), 1),
        "TOV": _fmt(p.get("TOV", 0), 1),
        "STL": _fmt(p.get("STL", 0), 1),
        "BLK": _fmt(p.get("BLK", 0), 1),
    }

    # --- Advanced ---
    report["advanced"] = {
        "eFG%": _fmt_pct(p.get("eFG%", 0)),
        "TS%": _fmt_pct(p.get("TS%", 0)),
        "AST/TO": _fmt(p.get("AST/TO", 0), 2),
        "ORB%": _fmt_pct(p.get("ORB%", 0)),
        "DRB%": _fmt_pct(p.get("DRB%", 0)),
    }

    # --- Grading ---
    efg = p.get("eFG%", 0)
    ts = p.get("TS%", 0)
    ast_to = p.get("AST/TO", 0)
    usg = p.get("USG%", 0)
    tpa = p.get("3PA", 0)
    fta = p.get("FTA", 0)
    ftm = p.get("FTM", 0)
    tov = p.get("TOV", 0)
    pf = p.get("PF", 0)
    stl = p.get("STL", 0)
    blk = p.get("BLK", 0)

    if _grade(efg, BENCHMARKS["eFG%"]) == "elite":
        report["strengths"].append(f"Elite shooter (eFG% {_fmt_pct(efg)})")
    elif _grade(efg, BENCHMARKS["eFG%"]) == "weak":
        report["weaknesses"].append(f"Struggles with efficiency (eFG% {_fmt_pct(efg)})")

    if _grade(ts, BENCHMARKS["TS%"]) == "elite":
        report["strengths"].append(f"Highly efficient scorer (TS% {_fmt_pct(ts)})")

    if _grade(ast_to, BENCHMARKS["AST/TO"]) == "elite":
        report["strengths"].append(f"Excellent ball control (AST/TO {_fmt(ast_to, 2)})")
    elif ast_to < 1.0 and tov > 1:
        report["weaknesses"].append(f"Turnover-prone (AST/TO {_fmt(ast_to, 2)})")

    if _grade(usg, BENCHMARKS["USG%"]) == "high":
        report["strengths"].append(f"High-usage focal point (USG% {_fmt_pct(usg)})")

    # Free throws
    if fta >= 3 and (ftm / fta) < 0.65:
        report["weaknesses"].append(f"Poor FT shooter ({int(ftm)}/{int(fta)}) — foul late")

    # How to defend
    if tpa >= 4:
        report["how_to_defend"].append("Close out hard on 3-point line")
    if fta >= 4:
        report["how_to_defend"].append("Don't foul — gets to the line")
    if tpa <= 1 and p.get("FGA", 0) >= 5:
        report["how_to_defend"].append("Sag off — prefers inside scoring")
    if p.get("AST", 0) >= 4:
        report["how_to_defend"].append("Deny passing lanes")

    # How to attack
    if pf >= 3:
        report["how_to_attack"].append("Attack them — foul-prone")
    if stl + blk <= 1:
        report["how_to_attack"].append("Drive at them — low defensive playmaking")

    return report


# ---------------------------------------------------------------
# Report formatting (for Streamlit markdown)
# ---------------------------------------------------------------

def team_report_markdown(r: dict) -> str:
    lines = []
    lines.append(f"# SCOUTING REPORT: {r['team']}")
    lines.append(f"*Sample size: last {r['sample_size']} games*")
    lines.append("")
    lines.append("## 1. Team Profile")
    lines.append(f"- Record: {r['profile']['GP']} games")
    lines.append(f"- Offensive Rating: {r['profile']['OffRtg']}")
    lines.append(f"- Defensive Rating: {r['profile']['DefRtg']}")
    lines.append(f"- Net Rating: {r['profile']['NetRtg']}")
    lines.append(f"- Pace: {r['profile']['Pace']} possessions/game")
    lines.append("")

    lines.append("## 2. Traditional Stats (per game)")
    for k, v in r["traditional"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 3. Advanced/Efficiency")
    for k, v in r["advanced"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 4. Key Players")
    for p in r["key_players"]:
        lines.append(f"- **{p['name']}** — {p['pts']} PPG, eFG% {p['eFG%']}, USG% {p['USG%']}")
    lines.append("")

    lines.append("## 5. Strengths / Weaknesses")
    lines.append("**Strengths:**")
    for s in r["strengths"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Weaknesses:**")
    for s in r["weaknesses"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## 6. Exploit / Avoid")
    lines.append("**Exploit:**")
    for s in r["exploit"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Avoid:**")
    for s in r["avoid"] or ["—"]:
        lines.append(f"- {s}")

    return "\n".join(lines)


def player_report_markdown(r: dict) -> str:
    lines = []
    lines.append(f"# SCOUTING REPORT: {r['player']}")
    lines.append(f"*Team: {r['team']} | Sample size: last {r['sample_size']} games*")
    lines.append("")
    lines.append("## 1. Player Profile")
    lines.append(f"- Games: {r['profile']['GP']}")
    lines.append(f"- Minutes: {r['profile']['MIN']}")
    lines.append(f"- Usage Rate: {r['profile']['USG%']}")
    lines.append("")

    lines.append("## 2. Traditional Stats (per game)")
    for k, v in r["traditional"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 3. Advanced/Efficiency")
    for k, v in r["advanced"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 4. Strengths / Weaknesses")
    lines.append("**Strengths:**")
    for s in r["strengths"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Weaknesses:**")
    for s in r["weaknesses"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## 5. How to Defend")
    for s in r["how_to_defend"] or ["—"]:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## 6. How to Attack")
    for s in r["how_to_attack"] or ["—"]:
        lines.append(f"- {s}")

    return "\n".join(lines)