import streamlit as st
from src.load_data import load_events, load_match_metadata, load_all_matches, load_lineups
from src.metrics import (
    add_pass_flags, build_player_stats, get_basic_stats,
    get_loss_recovery_profile, get_substitutions, determine_starting_xi,
)
from src.plotting import (
    plot_shotmap, plot_passmap, plot_heatmap,
    plot_pass_network, plot_xg_timeline,
    plot_loss_map, plot_recovery_map,
    render_vertical_timeline
)

# =================== LOAD MATCHES =====================
all_matches = load_all_matches()

competitions = sorted(all_matches["competition.competition_name"].unique())
competition_choice = st.sidebar.selectbox("Select Competition", competitions)

filtered_by_comp = all_matches[
    all_matches["competition.competition_name"] == competition_choice
]

seasons = sorted(filtered_by_comp["season.season_name"].unique())
season_choice = st.sidebar.selectbox("Select Year / Season", seasons)

filtered_matches = filtered_by_comp[
    filtered_by_comp["season.season_name"] == season_choice
].copy()

filtered_matches["match_label"] = (
    filtered_matches["home_team.home_team_name"]
    + " vs "
    + filtered_matches["away_team.away_team_name"]
    + " (" + filtered_matches["competition_stage.name"] + ")"
)

match_label = st.sidebar.selectbox("Select Match", filtered_matches["match_label"])
match_id = int(filtered_matches.loc[
    filtered_matches["match_label"] == match_label, "match_id"
].iloc[0])

# =================== LOAD EVENTS & META =====================
df_events = load_events(match_id)
df_meta = load_match_metadata(match_id)

home = df_meta["home_team.home_team_name"].iloc[0]
away = df_meta["away_team.away_team_name"].iloc[0]
home_score = int(df_meta["home_score"].iloc[0])
away_score = int(df_meta["away_score"].iloc[0])

# =================== PAGE LAYOUT =====================
st.set_page_config(page_title="Football Dashboard", layout="wide", page_icon="⚽")

st.title(f"⚽ {home} vs {away}")
st.subheader("🏟️ Match Dashboard")

tab1, tab2, tab3 = st.tabs(["📊 Match Overview", "🧠 Team Tactical Analysis", "🧍 Player Analysis"])

# ============================================================
# ==================== TAB 1 — MATCH OVERVIEW =================
# ============================================================
with tab1:
    
    st.header("📊 Match Summary ")

    # SELECT TEAM FOR STATS IN TAB 1 (home/away)
    team_for_stats = home  # default compare home vs away
    stats, _, _ = get_basic_stats(df_events, home)

    def stat_row(label, home_val, away_val):
        h = home_val if isinstance(home_val, (int, float)) else "NA"
        a = away_val if isinstance(away_val, (int, float)) else "NA"

        if isinstance(home_val, (int, float)) and isinstance(away_val, (int, float)):
            total = home_val + away_val
            width = (home_val / total * 100) if total > 0 else 50
        else:
            width = 50

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin:6px 0;">
                <span style="font-weight:600;font-size:18px;">{h}</span>
                <span style="opacity:0.7;">{label}</span>
                <span style="font-weight:600;font-size:18px;">{a}</span>
            </div>
            <div style="background:#ddd;height:4px;position:relative;margin-bottom:14px;">
                <div style="background:#2d89e5;height:4px;width:{width}%"></div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # STATS PANEL
    stat_row("Final Score", home_score, away_score)
    stat_row("Shots", stats["shots"], stats["shots_opp"])
    stat_row("Shots on Target", stats["sot"], stats["sot_opp"])

    home_pos = round(stats["possession"]*100) if stats["possession"] != "NA" else "NA"
    away_pos = round(stats["possession_opp"]*100) if stats["possession_opp"] != "NA" else "NA"
    stat_row("Possession %", home_pos, away_pos)

    stat_row("Fouls", stats["fouls"], stats["fouls_opp"])
    stat_row("Yellow Cards", stats["yellow"], stats["yellow_opp"])
    stat_row("Corners", stats["corners"], stats["corners_opp"])
# --- Starting XI ---
    st.header("📋 Starting XI")

    df_lineups = load_lineups(match_id)

    if df_lineups is not None:
        col_home, col_away = st.columns(2)

        with col_home:
            st.subheader(f"🔴 {home} – Starting XI")
            home_starting = determine_starting_xi(df_events, df_lineups, home)
            st.dataframe(
                home_starting[["number", "player"]].reset_index(drop=True)
            )


        with col_away:
            st.subheader(f"🔵 {away} – Starting XI")
            away_starting = determine_starting_xi(df_events, df_lineups, away)
            st.dataframe(
                home_starting[["number", "player"]].reset_index(drop=True)
            )

    else:
        st.write("No lineup data available for this match.")

    
    timeline_html = render_vertical_timeline(df_events, home, away)
    st.markdown(timeline_html, unsafe_allow_html=True)

    # XG TIMELINE
    st.header("📈 xG Timeline")
    fig_xg = plot_xg_timeline(df_events, home, away)
    st.pyplot(fig_xg)

# ============================================================
# =========== TAB 2 — TEAM TACTICAL ANALYSIS =================
# ============================================================
with tab2:

    st.header("🧠 Team Tactical Analysis")

    # TEAM SELECTOR (solo aquí)
    teams = sorted(df_events["team.name"].unique())
    team = st.selectbox("Select Team", teams)

    # SHOT MAP
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📍 Shot Map")
        st.pyplot(plot_shotmap(df_events, team))

    with col2:
        st.subheader("🔗 Pass Network")
        st.pyplot(plot_pass_network(df_events, team))

    # LOSSES & RECOVERIES
    st.header("🧭 Ball Losses & Recoveries")

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("❌ Loss Map")
        st.pyplot(plot_loss_map(df_events, team))

    with col_r:
        st.subheader("✅ Recovery Map")
        st.pyplot(plot_recovery_map(df_events, team))

    # DEFENSIVE PROFILE
    st.header("🧱 Defensive & Possession Profile")
    profile, _, _ = get_loss_recovery_profile(df_events, team)

    colA, colB = st.columns(2)
    with colA:
        st.subheader("🧱 Defensive Block")
        st.markdown(f"**Estimated Block:** `{profile['block_type']}`")
        st.dataframe(profile["recoveries_by_third"])

    with colB:
        st.subheader("⚠ Losses by Third")
        st.dataframe(profile["losses_by_third"])

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("🔻 Top Ball Losers")
        st.dataframe(profile["losses_by_player"])

    with col4:
        st.subheader("🟢 Top Recoveries")
        st.dataframe(profile["recoveries_by_player"])

# ============================================================
# ================ TAB 3 — PLAYER ANALYSIS ===================
# ============================================================
with tab3:

    st.header("🧍 Player Analysis")

    # FILTER TEAM FIRST
    teams = sorted(df_events["team.name"].unique())
    team_pa = st.selectbox("Select Team (Player Analysis)", teams)

    # LOAD PASSES
    passes = add_pass_flags(df_events, team_pa)

    # PLAYER SELECTOR
    player_list = sorted(passes["player.name"].unique())
    player = st.selectbox("Select Player", player_list)

    # PLAYER STATS
    st.subheader("📊 Player Stats")
    pstats = build_player_stats(df_events, team_pa)
    if player in pstats.index:
        st.dataframe(pstats.loc[[player]])
    else:
        st.write("No stats available.")

    # VISUALS
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.subheader(f"🗺️ Pass Map — {player}")
        st.pyplot(plot_passmap(passes, player))

    with col_p2:
        st.subheader(f"🔥 Heatmap — {player}")
        st.pyplot(plot_heatmap(df_events, player))