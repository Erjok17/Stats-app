import pandas as pd

# Thresholds: (weak_max, strong_min) — a stat is "strong" above strong_min,
# "weak" below weak_max, otherwise "average"
THRESHOLDS = {
    "eFG%":   (0.45, 0.52),
    "TOV%":   (0.18, 0.13),   # note: lower is better, so reversed
    "ORB%":   (0.20, 0.30),
    "FTr":    (0.15, 0.25),
    "PPP":    (1.00, 1.15),
    "AST/TO": (1.00, 1.50),
    "3P%":    (0.30, 0.36),
}


def _grade(metric: str, value: float) -> str:
    if metric not in THRESHOLDS or pd.isna(value):
        return "average"
    weak, strong = THRESHOLDS[metric]
    if metric == "TOV%":  # inverted
        if value > weak:   return "weak"
        if value < strong: return "strong"
        return "average"
    if value < weak:   return "weak"
    if value > strong: return "strong"
    return "average"


def strengths_and_weaknesses(stats: dict) -> dict:
    """stats is a dict of metric -> value. Returns {'strengths': [...], 'weaknesses': [...]}."""
    strengths, weaknesses = [], []
    for metric, value in stats.items():
        if value is None or pd.isna(value):
            continue
        grade = _grade(metric, value)
        label = f"{metric}: {value:.3f}"
        if grade == "strong":
            strengths.append(label)
        elif grade == "weak":
            weaknesses.append(label)
    return {"strengths": strengths, "weaknesses": weaknesses}


def team_stats_from_box(box_row: pd.Series) -> dict:
    """Compute the threshold metrics for one team from a box-score row."""
    fga = box_row["fieldGoalsAttempted"]
    fgm = box_row["fieldGoalsMade"]
    tpm = box_row["threePointersMade"]
    fta = box_row["freeThrowsAttempted"]
    tov = box_row["turnovers"]
    oreb = box_row["reboundsOffensive"]

    efg = (fgm + 0.5 * tpm) / fga if fga else 0
    tov_pct = tov / (fga + 0.44 * fta + tov) if (fga + 0.44 * fta + tov) else 0
    ftr = fta / fga if fga else 0
    ppp = box_row["points"] / (fga + 0.44 * fta - oreb + tov) if (fga + 0.44 * fta - oreb + tov) else 0
    ast_to = box_row["assists"] / tov if tov else 0

    return {
        "eFG%": efg,
        "TOV%": tov_pct,
        "FTr": ftr,
        "PPP": ppp,
        "AST/TO": ast_to,
    }


def player_stats_from_row(player_row: pd.Series) -> dict:
    fga = player_row["fga"] or 0
    fgm = player_row["fgm"] or 0
    tpm = player_row["tpm"] or 0
    tpa = player_row["tpa"] or 0
    fta = player_row["fta"] or 0
    tov = player_row["tov"] or 0
    ast = player_row["ast"] or 0

    efg = (fgm + 0.5 * tpm) / fga if fga else 0
    tp_pct = tpm / tpa if tpa else 0
    ast_to = ast / tov if tov else (ast if ast else 0)
    ftr = fta / fga if fga else 0

    return {
        "eFG%": efg,
        "3P%": tp_pct,
        "AST/TO": ast_to,
        "FTr": ftr,
    }


def generate_advice(name: str, stats: dict, kind: str = "team") -> str:
    """Return a short prose summary of strengths and weaknesses."""
    sw = strengths_and_weaknesses(stats)
    lines = []
    if sw["strengths"]:
        lines.append(f"**{name} — strengths:** " + ", ".join(sw["strengths"]))
    if sw["weaknesses"]:
        lines.append(f"**{name} — weaknesses:** " + ", ".join(sw["weaknesses"]))
    if not lines:
        lines.append(f"**{name}:** all metrics in the average range.")
    return "\n\n".join(lines)