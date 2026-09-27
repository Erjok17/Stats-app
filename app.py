import streamlit as st
import pandas as pd
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

if mode == "single":
    df = st.session_state["df"]
    box = st.session_state["box"]
    players = st.session_state["players"]

    if view_mode == "Combined":
        st.header("Combined analytics")
        st.subheader("Team ratings")
        st.dataframe(team_ratings(box), width='stretch', hide_index=True)
        st.subheader("Four Factors")
        st.dataframe(four_factors(box), width='stretch', hide_index=True)
        st.subheader("Possessions & PPP")
        st.dataframe(estimated_possessions(box), width='stretch', hide_index=True)

    elif view_mode == "By team":
        teams = box["teamTricode"].tolist()
        selected = st.selectbox("Team", teams)
        st.subheader(f"{selected} — play-by-play")
        st.dataframe(
            df[df["teamTricode"] == selected],
            width='stretch',
            hide_index=True,
        )

    elif view_mode == "By player":
        if players.empty:
            st.warning("Player data unavailable.")
            st.stop()
        metrics = player_metrics(players, box)
        st.subheader("Player metrics (this game)")
        st.dataframe(metrics, width='stretch', hide_index=True)

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

elif mode == "multi":
    agg_players = st.session_state["multi_agg_players"]
    agg_teams = st.session_state["multi_agg_teams"]

    st.header(f"Multi-game analysis ({len(st.session_state['boxes'])} games)")

    tab1, tab2, tab3 = st.tabs(
        ["Team averages", "Player averages", "Scouting report"]
    )

    with tab1:
        st.subheader("Team averages across games")
        st.dataframe(agg_teams, width='stretch', hide_index=True)

    with tab2:
        st.subheader("Player averages across games")
        st.caption(
            f"Players with GP ≥ 2: "
            f"{(agg_players['GP'] >= 2).sum()} / {len(agg_players)}"
        )
        st.dataframe(agg_players, width='stretch', hide_index=True)

    with tab3:
        if agg_players.empty and agg_teams.empty:
            st.warning("No data aggregated.")
            st.stop()

        report_type = st.radio(
            "Report type", ["Team", "Player"], horizontal=True
        )
        sample_size = len(st.session_state["boxes"])

        if report_type == "Team":
            if agg_teams.empty:
                st.warning("No team data.")
                st.stop()
            team = st.selectbox("Pick a team", agg_teams["Team"].tolist())
            report = build_team_report(
                agg_teams, agg_players, team, sample_size
            )
            st.markdown(team_report_markdown(report))

        else:
            if agg_players.empty:
                st.warning("No player data.")
                st.stop()
            player = st.selectbox(
                "Pick a player", agg_players["Player"].tolist()
            )
            prow = agg_players[agg_players["Player"] == player].iloc[0]
            report = build_player_report(prow, sample_size)
            st.markdown(player_report_markdown(report))