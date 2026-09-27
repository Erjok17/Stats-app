import streamlit as st
import pandas as pd
import plotly.express as px
from main import fetch_pbp, DATA_DIR
from fuba import fetch_fuba_pbp, fetch_fuba_players, fetch_fuba_boxscore
from metrics import load_boxscore, estimated_possessions, four_factors
from analytics import player_metrics, team_ratings, scouting_report
from multi_game import fetch_games, aggregate_players, aggregate_teams
from scouting import (
    build_team_report,
    build_player_report,
    team_report_markdown,
    player_report_markdown,
)

st.set_page_config(page_title="Basketball Analytics", layout="wide")
st.title("Basketball Analytics & Scouting")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Configuration")
    source = st.radio("Data source", ["FUBA (Uganda)", "NBA"])

    if source == "FUBA (Uganda)":
        league = st.text_input("League code", value="UBBF")
        multi = st.checkbox("Multi-game mode")
        if multi:
            ids_raw = st.text_area(
                "Game IDs (one per line or comma-separated)",
                value="2842268\n2913911",
                height=120,
            )
            game_ids = [
                g.strip()
                for g in ids_raw.replace(",", "\n").splitlines()
                if g.strip()
            ]
        else:
            game_id = st.text_input("Game ID", value="2913911")
            game_ids = [game_id]
    else:
        league = None
        multi = False
        game_id = st.text_input("Game ID", value="0022300001")
        game_ids = [game_id]

    st.divider()
    view_mode = st.radio(
        "Analytics view",
        ["Combined", "By team", "By player", "Scouting report"],
    )

load = st.button("Load / Fetch Game(s)")

if not load and "loaded" not in st.session_state:
    st.info("Enter a game ID in the sidebar and click **Load / Fetch Game(s)**.")
    st.stop()

# ---------------- Load ----------------
if load:
    with st.spinner("Loading..."):
        if multi:
            pbops, boxes, playerss = fetch_games(game_ids, league=league)
            st.session_state["boxes"] = boxes
            st.session_state["pbops"] = pbops
            st.session_state["playerss"] = playerss
            st.session_state["multi_agg_players"] = aggregate_players(playerss, boxes)
            st.session_state["multi_agg_teams"] = aggregate_teams(boxes)
            st.session_state["mode"] = "multi"
        else:
            gid = game_ids[0]
            if source == "FUBA (Uganda)":
                df = fetch_fuba_pbp(gid, league=league)
                box = fetch_fuba_boxscore(gid, league=league)
                players = fetch_fuba_players(gid, league=league)
            else:
                df = fetch_pbp(gid)
                box = load_boxscore(gid, source="nba")
                players = pd.DataFrame()
            st.session_state["df"] = df
            st.session_state["box"] = box
            st.session_state["players"] = players
            st.session_state["mode"] = "single"
        st.session_state["loaded"] = True

# ---------------- Render ----------------
mode = st.session_state.get("mode")

# =================================================================
# SINGLE GAME
# =================================================================
if mode == "single":
    df = st.session_state["df"]
    box = st.session_state["box"]
    players = st.session_state["players"]

    # -------- Combined --------
    if view_mode == "Combined":
        st.header("Combined analytics")

        st.subheader("Team ratings")
        st.dataframe(team_ratings(box), width='stretch', hide_index=True)

        st.subheader("Four Factors")
        st.dataframe(four_factors(box), width='stretch', hide_index=True)

        st.subheader("Possessions & PPP")
        st.dataframe(estimated_possessions(box), width='stretch', hide_index=True)

        # --- Actions per period
        st.subheader("Actions per period")
        st.bar_chart(df.groupby("period").size())

        # --- Score progression
        st.subheader("Score progression")
        progress = (
            df.dropna(subset=["scoreHome", "scoreAway"])
            .loc[:, ["actionNumber", "scoreHome", "scoreAway"]]
            .rename(columns={
                "actionNumber": "Event",
                "scoreHome": "Home",
                "scoreAway": "Away",
            })
            .sort_values("Event")
        )
        if not progress.empty:
            st.line_chart(progress, x="Event", y=["Home", "Away"])

        # --- Shot chart
        st.subheader("Shot chart")
        if "xLegacy" in df.columns and "yLegacy" in df.columns:
            shots = df[
                (df["isFieldGoal"] == 1)
                & df["xLegacy"].notna()
                & df["yLegacy"].notna()
            ].copy()
        else:
            shots = pd.DataFrame()

        if not shots.empty:
            shots["Made"] = shots["shotResult"].map({"Made": "Made", "Missed": "Missed"})
            st.scatter_chart(shots, x="xLegacy", y="yLegacy",
                             color="Made", size="shotValue")
            st.caption(f"{len(shots)} field goal attempts")
        else:
            st.info("Shot coordinates not available — showing action-type breakdown instead.")
            st.bar_chart(df["actionType"].value_counts().head(15))

        # --- PIE #1: Action type share
        st.subheader("Action type share")
        action_df = df["actionType"].value_counts().head(8).reset_index()
        action_df.columns = ["actionType", "count"]
        if not action_df.empty:
            fig = px.pie(
                action_df,
                names="actionType",
                values="count",
                title="Action type share",
            )
            st.plotly_chart(fig, width='stretch')

    # -------- By team --------
    elif view_mode == "By team":
        teams = box["teamTricode"].tolist()
        selected = st.selectbox("Team", teams)
        team_df = df[df["teamTricode"] == selected]

        st.subheader(f"{selected} — play-by-play")
        st.dataframe(team_df, width='stretch', hide_index=True)

        st.subheader(f"{selected} — actions per period")
        st.bar_chart(team_df.groupby("period").size())

        st.subheader(f"{selected} — action type breakdown")
        st.bar_chart(team_df["actionType"].value_counts().head(10))

        st.subheader(f"{selected} — score progression")
        prog = (
            team_df.dropna(subset=["scoreHome", "scoreAway"])
            .loc[:, ["actionNumber", "scoreHome", "scoreAway"]]
            .rename(columns={"actionNumber": "Event",
                             "scoreHome": "Home", "scoreAway": "Away"})
            .sort_values("Event")
        )
        if not prog.empty:
            st.line_chart(prog, x="Event", y=["Home", "Away"])

        # --- PIE: team's action share
        st.subheader(f"{selected} — action type share")
        team_actions = team_df["actionType"].value_counts().head(8).reset_index()
        team_actions.columns = ["actionType", "count"]
        if not team_actions.empty:
            fig = px.pie(
                team_actions,
                names="actionType",
                values="count",
                title=f"{selected} action type share",
            )
            st.plotly_chart(fig, width='stretch')

    # -------- By player --------
    elif view_mode == "By player":
        if players.empty:
            st.warning("Player data unavailable.")
            st.stop()
        metrics = player_metrics(players, box)
        st.subheader("Player metrics (this game)")
        st.dataframe(metrics, width='stretch', hide_index=True)

        # --- PIE #2: Points share by player
        st.subheader("Points share by player")
        if not metrics.empty and "PTS" in metrics.columns:
            fig = px.pie(
                metrics,
                names="Player",
                values="PTS",
                title="Points share by player",
            )
            st.plotly_chart(fig, width='stretch')

    # -------- Scouting report --------
    elif view_mode == "Scouting report":
        if players.empty:
            st.warning("Player data unavailable.")
            st.stop()
        metrics = player_metrics(players, box)
        player_name = st.selectbox("Pick a player", metrics["Player"].tolist())
        row = metrics[metrics["Player"] == player_name].iloc[0]

        st.header(f"Scouting report: {player_name}")
        st.caption(f"Team: {row['Team']}  ·  MIN: {row['MIN']}  ·  PTS: {row['PTS']}")

        report = scouting_report(row)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("✅ Strengths")
            for s in report["strengths"] or ["—"]:
                st.write(f"- {s}")
            st.subheader("🎯 How to score on them")
            for s in report["how_to_score_on_them"] or ["—"]:
                st.write(f"- {s}")
        with col2:
            st.subheader("⚠️ Weaknesses")
            for s in report["weaknesses"] or ["—"]:
                st.write(f"- {s}")
            st.subheader("🛡️ How to defend them")
            for s in report["how_to_defend_them"] or ["—"]:
                st.write(f"- {s}")

        st.subheader("Full metric line")
        st.dataframe(row.to_frame().T, width='stretch', hide_index=True)

# =================================================================
# MULTI-GAME
# =================================================================
elif mode == "multi":
    agg_players = st.session_state["multi_agg_players"]
    agg_teams = st.session_state["multi_agg_teams"]

    st.header(f"Multi-game analysis ({len(st.session_state['boxes'])} games)")

    # -------- Combined --------
    if view_mode == "Combined":
        st.subheader("Team averages across games")
        st.dataframe(agg_teams, width='stretch', hide_index=True)

        st.subheader("Player averages across games")
        st.caption(
            f"Players with GP ≥ 2: "
            f"{(agg_players['GP'] >= 2).sum()} / {len(agg_players)}"
        )
        st.dataframe(agg_players, width='stretch', hide_index=True)

        if not agg_teams.empty and "OffRtg" in agg_teams.columns:
            st.subheader("Team ratings comparison")
            st.bar_chart(agg_teams.set_index("Team")[["OffRtg", "DefRtg", "NetRtg"]])

        if not agg_players.empty:
            st.subheader("Top 10 scorers (avg PTS)")
            top = agg_players.sort_values("PTS", ascending=False).head(10)
            st.bar_chart(top.set_index("Player")["PTS"])

    # -------- By team --------
    elif view_mode == "By team":
        team = st.selectbox("Pick a team", agg_teams["Team"].tolist())
        row = agg_teams[agg_teams["Team"] == team].iloc[0]

        st.subheader(f"{team} — averaged team ratings")
        st.dataframe(row.to_frame().T, width='stretch', hide_index=True)

        st.subheader(f"{team} — player averages")
        roster = agg_players[agg_players["Team"] == team]
        st.dataframe(roster, width='stretch', hide_index=True)

        st.subheader(f"{team} — top scorers")
        if not roster.empty:
            st.bar_chart(roster.sort_values("PTS", ascending=False)
                         .set_index("Player")["PTS"])

        # --- PIE #3: roster points share
        st.subheader(f"{team} — points share")
        if not roster.empty and "PTS" in roster.columns:
            fig = px.pie(
                roster,
                names="Player",
                values="PTS",
                title=f"{team} — points share",
            )
            st.plotly_chart(fig, width='stretch')

    # -------- By player --------
    elif view_mode == "By player":
        player = st.selectbox("Pick a player", agg_players["Player"].tolist())
        prow = agg_players[agg_players["Player"] == player].iloc[0]

        st.subheader(f"{player} — averaged metrics (GP = {int(prow['GP'])})")
        st.dataframe(prow.to_frame().T, width='stretch', hide_index=True)

        stat_cols = ["PTS", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA",
                     "OREB", "DREB", "AST", "TOV", "STL", "BLK", "PF"]
        stat_cols = [c for c in stat_cols if c in prow.index]
        st.subheader(f"{player} — stat line")
        st.bar_chart(prow[stat_cols])

    # -------- Scouting report --------
    elif view_mode == "Scouting report":
        report_type = st.radio("Report type", ["Team", "Player"], horizontal=True)
        sample_size = len(st.session_state["boxes"])

        if report_type == "Team":
            if agg_teams.empty:
                st.warning("No team data.")
                st.stop()
            team = st.selectbox("Pick a team", agg_teams["Team"].tolist())
            report = build_team_report(agg_teams, agg_players, team, sample_size)
            st.markdown(team_report_markdown(report))
        else:
            if agg_players.empty:
                st.warning("No player data.")
                st.stop()
            player = st.selectbox("Pick a player", agg_players["Player"].tolist())
            prow = agg_players[agg_players["Player"] == player].iloc[0]
            report = build_player_report(prow, sample_size)
            st.markdown(player_report_markdown(report))