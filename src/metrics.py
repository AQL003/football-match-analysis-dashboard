import pandas as pd
import numpy as np

def get_basic_stats(df_events, team):
    
    stats = {
            "shots": "NA",
            "shots_opp": "NA",
            "sot": "NA",
            "sot_opp": "NA",
            "xg": "NA",
            "xg_opp": "NA",
            "possession": "NA",
            "possession_opp": "NA",
            "fouls": "NA",
            "fouls_opp": "NA",
            "yellow": "NA",
            "yellow_opp": "NA",
            "corners": "NA",
            "corners_opp": "NA",
        }

    opp = df_events[df_events["team.name"] != team]["team.name"].unique()[0]

    df_team = df_events[df_events["team.name"] == team]
    df_opp  = df_events[df_events["team.name"] == opp]

    # Shots
    stats["shots"] = len(df_team[df_team["type.name"] == "Shot"])
    stats["shots_opp"] = len(df_opp[df_opp["type.name"] == "Shot"])

    # Shots on target
    sot_names = ["Saved", "Saved To Post", "Goal"]
    stats["sot"] = len(df_team[df_team["shot.outcome.name"].isin(sot_names)])
    stats["sot_opp"] = len(df_opp[df_opp["shot.outcome.name"].isin(sot_names)])

    # xG
    stats["xg"] = df_team["shot.statsbomb_xg"].sum()
    stats["xg_opp"] = df_opp["shot.statsbomb_xg"].sum()

    # Possession (by actions)
    stats["possession"] = len(df_team) / len(df_events)
    stats["possession_opp"] = len(df_opp) / len(df_events)

    # Passes completed
    stats["passes"] = len(df_team[(df_team["type.name"] == "Pass") & (df_team["pass.outcome.name"].isna())])
    stats["passes_opp"] = len(df_opp[(df_opp["type.name"] == "Pass") & (df_opp["pass.outcome.name"].isna())])

    # Fouls
    stats["fouls"] = len(df_team[df_team["type.name"] == "Foul Committed"])
    stats["fouls_opp"] = len(df_opp[df_opp["type.name"] == "Foul Committed"])

    # Detectar nombre real de columna de tarjetas
    card_columns = [c for c in df_events.columns if "card" in c.lower()]

    # Si existe foul_committed.card.name
    card_col = None
    for c in card_columns:
        if "foul_committed.card.name" in c.lower():
            card_col = c
            break

    # Si no encontramos nada → no hay tarjetas en este dataset
    if card_col is None:
        stats["yellow"] = 0
        stats["yellow_opp"] = 0
    else:
        # Tarjetas amarillas
        stats["yellow"] = len(df_team[df_team[card_col] == "Yellow Card"])
        stats["yellow_opp"] = len(df_opp[df_opp[card_col] == "Yellow Card"])

        # Corners
        if "type.name" in df_team.columns:
            stats["corners"] = len(df_team[df_team["type.name"] == "Corner"])
            stats["corners_opp"] = len(df_opp[df_opp["type.name"] == "Corner"])

    return stats, team, opp

def add_pass_flags(df_events, team):
    """Añade is_key_pass e is_assist para un equipo específico."""
    df = df_events[df_events["team.name"] == team].copy()

    passes = df[df["type.name"] == "Pass"].copy()
    shots  = df[df["type.name"] == "Shot"][["id", "shot.outcome.name"]].copy()

    shots.rename(columns={
        "id": "shot_id",
        "shot.outcome.name": "shot_outcome"
    }, inplace=True)

    # Key Pass = pase que asiste un tiro
    passes["is_key_pass"] = passes["pass.assisted_shot_id"].notna()

    # Join con los tiros para determinar si fue gol
    passes = passes.merge(
        shots,
        how="left",
        left_on="pass.assisted_shot_id",
        right_on="shot_id"
    )

    # Assist = key pass cuyo tiro terminó en gol
    passes["is_assist"] = passes["shot_outcome"] == "Goal"

    return passes


def build_player_stats(df_events, team):
    """Tabla final de stats por jugador: shots, xG, passes, KP, assists."""
    df = df_events[df_events["team.name"] == team].copy()

    shots = df[df["type.name"] == "Shot"].copy()
    passes = add_pass_flags(df_events, team)

    shot_stats = shots.groupby("player.name").agg(
        shots=("shot.statsbomb_xg", "count"),
        xg=("shot.statsbomb_xg", "sum")
    )

    pass_stats = passes.groupby("player.name").agg(
        passes=("pass.end_location", "count"),
        key_passes=("is_key_pass", "sum"),
        assists=("is_assist", "sum")
    )

    table = shot_stats.join(pass_stats, how="outer").fillna(0)

    # Convertir a int
    for col in ["shots", "passes", "key_passes", "assists"]:
        if col in table.columns:
            table[col] = table[col].astype(int)

    return table


def _third_from_x(x, pitch_length=120):
    if pd.isna(x):
        return np.nan
    if x <= pitch_length / 3:
        return "Defensive third"
    elif x <= 2 * pitch_length / 3:
        return "Middle third"
    else:
        return "Attacking third"


def get_loss_recovery_profile(df_events, team):
    """
    Calcula perfil de pérdidas y recuperaciones para un equipo:
    - pérdidas por tercio
    - recuperaciones por tercio
    - top jugadores que más pierden
    - top jugadores que más recuperan
    - clasificación aproximada del bloque defensivo (bajo / medio / alto)
    """

    cols = df_events.columns
    df_team = df_events[df_events["team.name"] == team].copy()

    # ----------------- PÉRDIDAS -----------------
    loss_mask = False

    if "type.name" in cols:
        loss_mask = df_team["type.name"].isin(["Dispossessed", "Miscontrol", "Foul Committed"])

    if "type.name" in cols and "pass.outcome.name" in cols:
        loss_mask = loss_mask | (
            (df_team["type.name"] == "Pass") &
            (df_team["pass.outcome.name"].notna())
        )

    if "type.name" in cols and "dribble.outcome.name" in cols:
        loss_mask = loss_mask | (
            (df_team["type.name"] == "Dribble") &
            (df_team["dribble.outcome.name"] != "Complete")
        )

    df_losses = df_team[loss_mask & df_team["location"].notna()].copy()

    if not df_losses.empty:
        df_losses["x"] = df_losses["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
        df_losses["y"] = df_losses["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
        df_losses["third"] = df_losses["x"].apply(_third_from_x)
        losses_by_third = (
            df_losses.groupby("third")
            .size()
            .rename("losses")
            .to_frame()
        )
        losses_by_third["pct"] = (losses_by_third["losses"] / losses_by_third["losses"].sum() * 100).round(1)
        losses_by_player = (
            df_losses["player.name"].value_counts().head(5)
            .rename("losses")
            .to_frame()
        )
    else:
        losses_by_third = pd.DataFrame(columns=["losses", "pct"])
        losses_by_player = pd.DataFrame(columns=["losses"])

    # ----------------- RECUPERACIONES -----------------
    if "type.name" in cols and "location" in cols:
        df_rec = df_team[
            (df_team["type.name"] == "Ball Recovery") &
            (df_team["location"].notna())
        ].copy()
    else:
        df_rec = pd.DataFrame()

    if not df_rec.empty:
        df_rec["x"] = df_rec["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
        df_rec["y"] = df_rec["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
        df_rec["third"] = df_rec["x"].apply(_third_from_x)
        rec_by_third = (
            df_rec.groupby("third")
            .size()
            .rename("recoveries")
            .to_frame()
        )
        rec_by_third["pct"] = (rec_by_third["recoveries"] / rec_by_third["recoveries"].sum() * 100).round(1)
        rec_by_player = (
            df_rec["player.name"].value_counts().head(5)
            .rename("recoveries")
            .to_frame()
        )
    else:
        rec_by_third = pd.DataFrame(columns=["recoveries", "pct"])
        rec_by_player = pd.DataFrame(columns=["recoveries"])

    # ----------------- CLASIFICAR BLOQUE DEFENSIVO -----------------
    block_type = "Unknown"
    if not rec_by_third.empty:
        pct_def = rec_by_third["pct"].get("Defensive third", 0)
        pct_mid = rec_by_third["pct"].get("Middle third", 0)
        pct_att = rec_by_third["pct"].get("Attacking third", 0)

        # reglas simples, se pueden ajustar
        if pct_att >= max(pct_mid, pct_def) and pct_att >= 40:
            block_type = "High press"
        elif pct_mid >= max(pct_att, pct_def) and pct_mid >= 40:
            block_type = "Mid block"
        elif pct_def >= max(pct_mid, pct_att) and pct_def >= 40:
            block_type = "Low block"
        else:
            block_type = "Mixed / Flexible"

    summary = {
        "losses_by_third": losses_by_third,
        "losses_by_player": losses_by_player,
        "recoveries_by_third": rec_by_third,
        "recoveries_by_player": rec_by_player,
        "block_type": block_type,
    }

    return summary, df_losses, df_rec

def get_substitutions(df_events, team=None):
    subs = df_events[df_events["type.name"] == "Substitution"].copy()
    
    if subs.empty:
        return pd.DataFrame(columns=["minute", "player_out", "player_in", "team"])
    
    subs["minute"] = subs["minute"].fillna(0)
    subs["player_out"] = subs["player.name"]
    subs["player_in"] = subs["substitution.replacement.name"]
    subs["team"] = subs["team.name"]

    if team:
        subs = subs[subs["team"] == team]

    return subs[["minute", "team", "player_out", "player_in"]]

def determine_starting_xi(df_events, df_lineups, team_name):
    """
    Determina los 11 titulares usando una lógica híbrida:
    1. Si hay 'position' válida → titular
    2. Si NO hay posición:
       - Si el jugador aparece como reemplazo → suplente
       - Si nunca entra → titular
    3. Si todo falla → usar minutos jugados aproximados
    """

    # Filtrar jugadores del equipo
    team_players = df_lineups[df_lineups["team"] == team_name].copy()

    # --- 1. Si tiene posición (no 'NA') → titular directo ---
    starters_pos = team_players[team_players["position"] != "NA"].copy()
    if len(starters_pos) == 11:
        return starters_pos[["number", "player", "position"]]

    # --- 2. Detectar reemplazos (suplentes que entraron) ---
    subs_in = df_events[df_events["type.name"] == "Substitution"]["substitution.replacement.name"].dropna().unique()
    subs_in = set(subs_in)

    team_players["is_sub_in"] = team_players["player"].apply(lambda x: x in subs_in)

    starters_guess = team_players[~team_players["is_sub_in"]].copy()

    if len(starters_guess) >= 11:
        return starters_guess.head(11)[["number", "player", "position"]]

    # --- 3. Uso de minutos jugados (si lo anterior no alcanza) ---
    # minuto de salida = evento donde jugador sale
    df_subs_out = df_events[df_events["type.name"] == "Substitution"][["minute","player.name"]]

    # ponemos 90 por defecto
    team_players["minutes_played"] = 90

    # si sale
    for _, row in df_subs_out.iterrows():
        if row["player.name"] in team_players["player"].values:
            team_players.loc[
                team_players["player"] == row["player.name"],
                "minutes_played"
            ] = row["minute"]

    # si entra
    df_subs_in2 = df_events[df_events["type.name"] == "Substitution"][["minute","substitution.replacement.name"]]
    for _, row in df_subs_in2.iterrows():
        if row["substitution.replacement.name"] in team_players["player"].values:
            team_players.loc[
                team_players["player"] == row["substitution.replacement.name"],
                "minutes_played"
            ] = 90 - row["minute"]

    # tomar los 11 con más minutos
    starters_final = team_players.sort_values("minutes_played", ascending=False).head(11)

    return starters_final[["number","player"]]