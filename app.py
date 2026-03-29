import streamlit as st

from src.load_data import (
    data_mode,
    load_events_local, load_lineups_local,
    load_all_matches_remote, load_events_remote, load_lineups_remote
)

from src.metrics import (
    add_pass_flags, build_player_stats, get_basic_stats,
    get_loss_recovery_profile, determine_starting_xi
)

from src.plotting import (
    plot_shotmap, plot_passmap, plot_heatmap,
    plot_pass_network, plot_xg_timeline,
    plot_loss_map, plot_recovery_map,
    render_vertical_timeline
)

# =================== PAGE CONFIG (primero) =====================
st.set_page_config(page_title="Football Dashboard", layout="wide", page_icon="⚽")

# =================== LOAD MATCH LIST (remote) ==================
# Para que Cloud tenga "todo", usamos remote siempre para matches.
all_matches = load_all_matches_remote()

if all_matches.empty:
    st.error(
        "No pude cargar la lista de partidos desde StatsBomb Open Data.\n\n"
        "Revisa tu conexión o intenta recargar. Si estás en Streamlit Cloud, "
        "puede ser un fallo temporal."
    )
    st.stop()

# =================== SIDEBAR: filters ==========================
competitions = sorted(all_matches["competition.competition_name"].dropna().unique())
competition_choice = st.sidebar.selectbox("Select Competition", competitions)

filtered_by_comp = all_matches[all_matches["competition.competition_name"] == competition_choice].copy()

seasons = sorted(filtered_by_comp["season.season_name"].dropna().unique())
season_choice = st.sidebar.selectbox("Select Year / Season", seasons)

filtered_matches = filtered_by_comp[filtered_by_comp["season.season_name"] == season_choice].copy()

filtered_matches["match_label"] = (
    filtered_matches["home_team.home_team_name"]
    + " vs "
    + filtered_matches["away_team.away_team_name"]
    + " (" + filtered_matches["competition_stage.name"] + ")"
)

match_label = st.sidebar.selectbox("Select Match", filtered_matches["match_label"].tolist())

match_id = int(
    filtered_matches.loc[filtered_matches["match_label"] == match_label, "match_id"].iloc[0]
)

# =================== LOAD EVENTS/LINEUPS (local o remote) ======
mode = data_mode()  # "local" si existe data/matches, sino "remote"

if mode == "local":
    df_events = load_events_local(match_id)
    df_lineups = load_lineups_local(match_id)
else:
    df_events = load_events_remote(match_id)
    df_lineups = load_lineups_remote(match_id)

# =================== META from matches row =====================
row = all_matches[all_matches["match_id"] == match_id].iloc[0]

home = row["home_team.home_team_name"]
away = row["away_team.away_team_name"]
home_score = int(row["home_score"])
away_score = int(row["away_score"])
competition = row["competition.competition_name"]
season = row["season.season_name"]

# =================== HEADER =====================
st.title(f"⚽ {home} vs {away}")
st.caption(f"🏆 {competition} — {season}")

tab1, tab2, tab3 = st.tabs(["📊 Match Overview", "🧠 Team Tactical Analysis", "🧍 Player Analysis"])

# ============================================================
# TAB 1 — MATCH OVERVIEW (ESPN + timeline + xG only)
# ============================================================
with tab1:
    st.header("📊 Match Summary — ESPN Style")

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

    stat_row("Final Score", home_score, away_score)
    stat_row("Shots", stats.get("shots", "NA"), stats.get("shots_opp", "NA"))
    stat_row("Shots on Target", stats.get("sot", "NA"), stats.get("sot_opp", "NA"))

    # Possession ya lo calculas como ratio de acciones (0-1), aquí lo convertimos a %
    hp = stats.get("possession", "NA")
    ap = stats.get("possession_opp", "NA")
    home_pos = round(hp * 100) if isinstance(hp, (int, float)) else "NA"
    away_pos = round(ap * 100) if isinstance(ap, (int, float)) else "NA"
    stat_row("Possession %", home_pos, away_pos)

    stat_row("Fouls", stats.get("fouls", "NA"), stats.get("fouls_opp", "NA"))
    stat_row("Yellow Cards", stats.get("yellow", "NA"), stats.get("yellow_opp", "NA"))
    stat_row("Corners", stats.get("corners", "NA"), stats.get("corners_opp", "NA"))

    st.header("🕒 Match Timeline")
    st.markdown(render_vertical_timeline(df_events, home, away), unsafe_allow_html=True)

    st.header("📈 xG Timeline")
    st.pyplot(plot_xg_timeline(df_events, home, away))

# ============================================================
# TAB 2 — TEAM TACTICAL (selector team + shotmap + network + losses/recoveries + profile)
# ============================================================
with tab2:
    st.header("🧠 Team Tactical Analysis")
    teams = sorted(df_events["team.name"].dropna().unique())
    team = st.selectbox("Select Team", teams)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📍 Shot Map")
        st.pyplot(plot_shotmap(df_events, team))
    with col2:
        st.subheader("🔗 Pass Network")
        st.pyplot(plot_pass_network(df_events, team))

    st.subheader("🧭 Ball Losses & Recoveries")
    colL, colR = st.columns(2)
    with colL:
        st.pyplot(plot_loss_map(df_events, team))
    with colR:
        st.pyplot(plot_recovery_map(df_events, team))

    st.subheader("🧱 Defensive & Possession Profile")
    profile, _, _ = get_loss_recovery_profile(df_events, team)

    cA, cB = st.columns(2)
    with cA:
        st.markdown(f"**Estimated Block:** `{profile['block_type']}`")
        st.dataframe(profile["recoveries_by_third"])
    with cB:
        st.dataframe(profile["losses_by_third"])

    cC, cD = st.columns(2)
    with cC:
        st.dataframe(profile["losses_by_player"])
    with cD:
        st.dataframe(profile["recoveries_by_player"])

# ============================================================
# TAB 3 — PLAYER ANALYSIS (selector team + player + stats + maps)
# ============================================================
with tab3:
    st.header("🧍 Player Analysis")

    teams = sorted(df_events["team.name"].dropna().unique())
    team_pa = st.selectbox("Select Team (Player Analysis)", teams)

    passes = add_pass_flags(df_events, team_pa)
    player_list = sorted(passes["player.name"].dropna().unique())
    player = st.selectbox("Select Player", player_list)

    st.subheader("📊 Player Stats")
    pstats = build_player_stats(df_events, team_pa)
    if player in pstats.index:
        st.dataframe(pstats.loc[[player]])
    else:
        st.write("No stats available.")

    colp1, colp2 = st.columns(2)
    with colp1:
        st.subheader("🗺️ Pass Map")
        st.pyplot(plot_passmap(passes, player))
    with colp2:
        st.subheader("🔥 Heatmap")
        st.pyplot(plot_heatmap(df_events, player))