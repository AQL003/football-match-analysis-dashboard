from mplsoccer import Pitch
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def plot_shotmap(df_events, team):
    """Shot map profesional con colores por jugador y shapes por resultado."""

    shots = df_events[
        (df_events["team.name"] == team) &
        (df_events["type.name"] == "Shot")
    ].copy()

    # Extraer coordenadas
    shots["x"] = shots["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    shots["y"] = shots["location"].apply(lambda v: v[1] if isinstance(v, list) else None)

    # Obtener jugadores únicos y asignar colores
    players = shots["player.name"].unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(players)))
    color_map = dict(zip(players, colors))

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(10, 7))

    # Dibujar cada tiro individual
    for _, row in shots.iterrows():
        player = row["player.name"]
        color = color_map[player]
        outcome = row["shot.outcome.name"]
        x, y = row["x"], row["y"]

        # Tamaño por xG
        xg = row.get("shot.statsbomb_xg", 0) or 0
        size = xg * 2000 + 100

        # Forma según resultado
        if outcome == "Goal":
            marker = "*"
            marker_color = color
        elif outcome in ["Saved", "Saved To Post"]:
            marker = "o"
            marker_color = color
        else:
            marker = "X"
            marker_color = color

        pitch.scatter(
            x, y,
            s=size,
            marker=marker,
            color=marker_color,
            edgecolor="black",
            linewidth=1.3,
            alpha=0.9,
            ax=ax
        )

    # ---- LEYENDAS ----

    # 1) Leyenda de outcomes
    outcome_legend = [
        plt.Line2D([0], [0], marker='*', color='w', label='Goal',
                   markerfacecolor='black', markersize=12, markeredgecolor='black'),
        plt.Line2D([0], [0], marker='o', color='w', label='On Target',
                   markerfacecolor='black', markersize=10, markeredgecolor='black'),
        plt.Line2D([0], [0], marker='X', color='w', label='Off Target / Blocked',
                   markerfacecolor='black', markersize=12, markeredgecolor='black'),
    ]

    legend1 = ax.legend(
        handles=outcome_legend,
        title="Shot Outcome (Shape)",
        loc="lower left"
    )
    ax.add_artist(legend1)

    # 2) Leyenda de jugadores (por color)
    player_legend = [
        plt.Line2D([0], [0], marker='o', color='w',
                   label=player,
                   markerfacecolor=color_map[player],
                   markersize=10)
        for player in players
    ]

    ax.legend(
        handles=player_legend,
        title="Players (Color)",
        loc="lower right"
    )

    ax.set_title(f"{team} — Shot Map (Color=Player, Shape=Outcome, Size=xG)", fontsize=16)

    return fig



def plot_passmap(passes_df, player):
    df = passes_df[passes_df["player.name"] == player].copy()

    df = df.dropna(subset=["location", "pass.end_location"])

    df["x"] = df["location"].apply(lambda v: v[0])
    df["y"] = df["location"].apply(lambda v: v[1])
    df["end_x"] = df["pass.end_location"].apply(lambda v: v[0])
    df["end_y"] = df["pass.end_location"].apply(lambda v: v[1])

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(8, 6))

    pitch.arrows(df["x"], df["y"], df["end_x"], df["end_y"],
                 width=2, color="blue", alpha=0.7, ax=ax)

    ax.set_title(f"{player} – Pass Map")
    return fig

def plot_heatmap(df_events, player):
    """Heatmap de localizaciones de un jugador."""
    df = df_events[
        (df_events["player.name"] == player) &
        (df_events["location"].notna())
    ].copy()

    # Extraer coordenadas
    df["x"] = df["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    df["y"] = df["location"].apply(lambda v: v[1] if isinstance(v, list) else None)

    df = df.dropna(subset=["x", "y"])

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(8, 6))

    pitch.kdeplot(
        x=df["x"], y=df["y"],
        ax=ax,
        cmap="Reds",
        shade=True,
        levels=100
    )

    ax.set_title(f"{player} – Heatmap")
    return fig

def plot_pass_network(df_events, team, min_passes=3):
    """Pass network con jitter para nodos y grosor por número de pases."""

    df = df_events[df_events["team.name"] == team].copy()

    # Solo pases completados
    passes = df[
        (df["type.name"] == "Pass") &
        (df["pass.outcome.name"].isna())
    ].copy()

    # Coordenadas de inicio / fin
    passes["x"] = passes["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    passes["y"] = passes["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
    passes["end_x"] = passes["pass.end_location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    passes["end_y"] = passes["pass.end_location"].apply(lambda v: v[1] if isinstance(v, list) else None)

    passes = passes.dropna(subset=["x", "y", "end_x", "end_y"])

    # Posición promedio por jugador
    avg_pos = passes.groupby("player.name").agg(
        x=("x", "mean"),
        y=("y", "mean"),
        pass_count=("pass.recipient.name", "count")
    )

    # Pequeño jitter para separar nodos muy juntos
    rng = np.random.default_rng(42)  # semilla fija para reproducibilidad
    jitter_strength = 2.0
    avg_pos["jx"] = avg_pos["x"] + rng.normal(0, jitter_strength, size=len(avg_pos))
    avg_pos["jy"] = avg_pos["y"] + rng.normal(0, jitter_strength, size=len(avg_pos))

    # Conexiones entre jugadores
    combos = passes.groupby(["player.name", "pass.recipient.name"]).size().reset_index(name="count")

    # Umbral mínimo para mostrar conexión
    combos = combos[combos["count"] >= min_passes]

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(12, 9))

    # Dibujar líneas de conexión
    for _, row in combos.iterrows():
        p1 = row["player.name"]
        p2 = row["pass.recipient.name"]

        if p1 not in avg_pos.index or p2 not in avg_pos.index:
            continue

        x1, y1 = avg_pos.loc[p1, ["jx", "jy"]]
        x2, y2 = avg_pos.loc[p2, ["jx", "jy"]]

        pitch.lines(
            x1, y1, x2, y2,
            lw=row["count"] * 0.4,
            color="steelblue",
            ax=ax,
            alpha=0.6,
            zorder=2
        )

    # Dibujar nodos (jugadores)
    pitch.scatter(
        avg_pos["jx"],
        avg_pos["jy"],
        s=avg_pos["pass_count"] * 35,
        color="white",
        edgecolor="black",
        linewidth=1.5,
        ax=ax,
        zorder=3
    )

    # Etiquetas con fondo para que se lean bien
    for name, row in avg_pos.iterrows():
        ax.text(
            row["jx"], row["jy"], name,
            ha="center", va="center",
            fontsize=9,
            bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.2"),
            zorder=4
        )

    ax.set_title(f"{team} — Pass Network", fontsize=18)
    return fig


def plot_xg_timeline(df_events, home, away):
    """
    Crea un xG timeline acumulado para home y away,
    marcando los goles con puntos sobre la línea.
    """

    # Verificar que existan las columnas necesarias
    required_cols = ["type.name", "team.name", "shot.statsbomb_xg", "minute", "second", "shot.outcome.name"]
    for col in required_cols:
        if col not in df_events.columns:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, f"xG timeline no disponible\n(falta columna: {col})",
                    ha="center", va="center")
            ax.axis("off")
            return fig

    # Filtrar solo tiros
    df_shots = df_events[df_events["type.name"] == "Shot"].copy()

    # Separar por equipo
    df_home = df_shots[df_shots["team.name"] == home].copy()
    df_away = df_shots[df_shots["team.name"] == away].copy()

    # Función auxiliar para preparar cada equipo
    def prepare_team_df(df_team):
        if df_team.empty:
            return df_team

        df_team["minute"] = df_team["minute"].fillna(0)
        df_team["second"] = df_team["second"].fillna(0)
        # Tiempo como minuto + fracción de segundo
        df_team["time"] = df_team["minute"] + df_team["second"] / 60.0

        df_team = df_team.sort_values("time")
        df_team["xg_cum"] = df_team["shot.statsbomb_xg"].fillna(0).cumsum()
        return df_team

    df_home = prepare_team_df(df_home)
    df_away = prepare_team_df(df_away)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Líneas de xG acumulado
    if not df_home.empty:
        ax.plot(df_home["time"], df_home["xg_cum"], label=home, color="red", linewidth=2)
    if not df_away.empty:
        ax.plot(df_away["time"], df_away["xg_cum"], label=away, color="blue", linewidth=2)

    # ---- MARCADORES DE GOLES ----
    # Home
    if not df_home.empty:
        home_goals = df_home[df_home["shot.outcome.name"] == "Goal"]
        ax.scatter(
            home_goals["time"],
            home_goals["xg_cum"],
            color="red",
            edgecolor="black",
            s=80,
            zorder=3,
            label=f"{home} goals" if not home_goals.empty else None
        )

    # Away
    if not df_away.empty:
        away_goals = df_away[df_away["shot.outcome.name"] == "Goal"]
        ax.scatter(
            away_goals["time"],
            away_goals["xg_cum"],
            color="blue",
            edgecolor="black",
            s=80,
            zorder=3,
            label=f"{away} goals" if not away_goals.empty else None
        )

    ax.set_title("xG Timeline", fontsize=16)
    ax.set_xlabel("Minute")
    ax.set_ylabel("Cumulative xG")

    # Límites de tiempo (0–100 aprox para seguridad)
    ax.set_xlim(left=0, right=max(
        df_events["minute"].max() + 5 if "minute" in df_events.columns else 95, 95
    ))

    ax.legend()
    ax.grid(alpha=0.2)

    return fig

def plot_loss_map(df_events, team):
    """Heatmap de pérdidas de balón del equipo."""
    cols = df_events.columns

    # Filtrar eventos del equipo
    df_team = df_events[df_events["team.name"] == team].copy()

    if "location" not in cols:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "Loss map no disponible\n(no hay columna 'location')",
                ha="center", va="center")
        ax.axis("off")
        return fig

    # Máscara de pérdidas
    loss_mask = False

    if "type.name" in cols:
        loss_mask = (
            df_team["type.name"].isin(["Dispossessed", "Miscontrol", "Foul Committed"])
        )

    # Pases fallados
    if "type.name" in cols and "pass.outcome.name" in cols:
        loss_mask = loss_mask | (
            (df_team["type.name"] == "Pass") &
            (df_team["pass.outcome.name"].notna())
        )

    # Regates fallidos (si existe la columna)
    if "type.name" in cols and "dribble.outcome.name" in cols:
        loss_mask = loss_mask | (
            (df_team["type.name"] == "Dribble") &
            (df_team["dribble.outcome.name"] != "Complete")
        )

    df_losses = df_team[loss_mask & df_team["location"].notna()].copy()

    if df_losses.empty:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No se registran pérdidas\npara este equipo/partido.",
                ha="center", va="center")
        ax.axis("off")
        return fig

    # Coordenadas
    df_losses["x"] = df_losses["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    df_losses["y"] = df_losses["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
    df_losses = df_losses.dropna(subset=["x", "y"])

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(8, 6))

    pitch.kdeplot(
        x=df_losses["x"], y=df_losses["y"],
        ax=ax,
        cmap="Blues",
        shade=True,
        levels=100,
        alpha=0.9
    )

    ax.set_title(f"{team} – Loss Map (pérdidas de balón)", fontsize=14)
    return fig


def plot_recovery_map(df_events, team):
    """Heatmap de recuperaciones de balón del equipo."""
    cols = df_events.columns

    if "type.name" not in cols or "location" not in cols:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "Recovery map no disponible\n(faltan columnas)",
                ha="center", va="center")
        ax.axis("off")
        return fig

    df_team = df_events[
        (df_events["team.name"] == team) &
        (df_events["type.name"] == "Ball Recovery") &
        (df_events["location"].notna())
    ].copy()

    if df_team.empty:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No se registran recuperaciones\npara este equipo/partido.",
                ha="center", va="center")
        ax.axis("off")
        return fig

    df_team["x"] = df_team["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
    df_team["y"] = df_team["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
    df_team = df_team.dropna(subset=["x", "y"])

    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(8, 6))

    pitch.kdeplot(
        x=df_team["x"], y=df_team["y"],
        ax=ax,
        cmap="Greens",
        shade=True,
        levels=100,
        alpha=0.9
    )

    ax.set_title(f"{team} – Recovery Map (recuperaciones)", fontsize=14)
    return fig


def plot_team_lineup_pitch(df_lineups, team, home_side=True):
    """
    Dibuja la alineación de un equipo sobre el campo (tactical map).
    - df_lineups: DataFrame con columnas ['team','player','number','position']
    - team: nombre del equipo
    - home_side: True -> ataca de izquierda a derecha, False -> invertimos
    """
    team_df = df_lineups[df_lineups["team"] == team].copy()
    if team_df.empty:
        fig, ax = plt.subplots(figsize=(6, 8))
        ax.text(0.5, 0.5, f"No lineup data for {team}", ha="center", va="center")
        ax.axis("off")
        return fig

    # Mapeo simple de posición -> coordenadas aproximadas en StatsBomb (120 x 80)
    pos_map = {
        "Goalkeeper": (6, 40),

        "Right Back": (25, 18),
        "Right Wing Back": (28, 18),
        "Right Center Back": (20, 30),
        "Center Back": (20, 40),
        "Left Center Back": (20, 50),
        "Left Back": (25, 62),
        "Left Wing Back": (28, 62),

        "Defensive Midfield": (45, 40),
        "Right Defensive Midfield": (45, 30),
        "Left Defensive Midfield": (45, 50),

        "Central Midfield": (60, 40),
        "Right Central Midfield": (60, 30),
        "Left Central Midfield": (60, 50),

        "Attacking Midfield": (75, 40),
        "Right Attacking Midfield": (75, 30),
        "Left Attacking Midfield": (75, 50),

        "Right Wing": (85, 20),
        "Left Wing": (85, 60),
        "Right Midfield": (70, 25),
        "Left Midfield": (70, 55),

        "Center Forward": (95, 40),
        "Second Striker": (90, 40),
        "Striker": (95, 40),
    }

    # Default por si la posición no está mapeada:
    default_pos = (60, 40)

    pitch = Pitch(pitch_type="statsbomb", pitch_color="white", line_color="black")
    fig, ax = pitch.draw(figsize=(6, 8))

    # Color por equipo
    color = "#d62728" if home_side else "#1f77b4"

    for _, row in team_df.iterrows():
        pos_name = row.get("position", "NA")
        base_x, base_y = pos_map.get(pos_name, default_pos)

        x, y = base_x, base_y
        # Si es el equipo "away", invertimos el sentido del campo
        if not home_side:
            x = 120 - base_x

        # Dibujar "camiseta" como círculo
        pitch.scatter(
            x, y,
            s=900,
            color=color,
            edgecolor="black",
            linewidth=1.5,
            ax=ax,
            zorder=3
        )

        # Número en blanco encima
        num = row.get("number", "")
        ax.text(
            x, y - 1,
            str(num),
            ha="center", va="center",
            fontsize=10, color="white", weight="bold", zorder=4
        )

        # Apellido debajo
        name = row.get("player", "")
        last_name = name.split()[-1] if isinstance(name, str) else ""
        ax.text(
            x, y + 6,
            last_name,
            ha="center", va="center",
            fontsize=7, color="black", zorder=4
        )

    ax.set_title(f"{team} – Lineup", fontsize=14)
    return fig


def plot_substitution_timeline(df_subs, home, away):
    """
    Dibuja una timeline de sustituciones tipo Wyscout:
    - Eje X: minutos
    - Eje Y: una línea por equipo (home arriba, away abajo)
    - Marcadores rojos (🔻) para el jugador que sale
    - Marcadores verdes (🔺) para el jugador que entra
    """

    if df_subs is None or df_subs.empty:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "No substitutions recorded", ha="center", va="center")
        ax.axis("off")
        return fig

    fig, ax = plt.subplots(figsize=(10, 3))

    # Líneas base para cada equipo
    ax.hlines(1, 0, 90, colors="red", linewidth=1, alpha=0.3)
    ax.hlines(0, 0, 90, colors="blue", linewidth=1, alpha=0.3)

    # Recorrer cada sustitución
    for _, row in df_subs.iterrows():
        minute = row["minute"]
        team_name = row["team"]
        player_out = row["player_out"]
        player_in = row["player_in"]

        y = 1 if team_name == home else 0

        # Jugador que sale (🔻)
        ax.scatter(
            minute, y + 0.05,
            marker="v",
            color="red",
            edgecolor="black",
            s=70,
            zorder=3
        )

        # Jugador que entra (🔺)
        ax.scatter(
            minute, y - 0.05,
            marker="^",
            color="green",
            edgecolor="black",
            s=70,
            zorder=3
        )

        # Etiqueta opcional corta (apellido del que entra)
        short_name = player_in.split()[-1] if isinstance(player_in, str) else ""
        ax.text(
            minute, y - 0.18,
            short_name,
            ha="center", va="top",
            fontsize=7,
            rotation=0
        )

    ax.set_yticks([0, 1])
    ax.set_yticklabels([away, home])

    # Margen extra a la derecha
    max_minute = max(90, df_subs["minute"].max() + 5)
    ax.set_xlim(0, max_minute)

    ax.set_xlabel("Minute")
    ax.set_title("Substitution Timeline", fontsize=12)
    ax.grid(axis="x", alpha=0.2)

    return fig

def render_vertical_timeline(df_events, home, away):
    """
    Timeline vertical estilo Wyscout:
    - SOLO eventos importantes:
        ⚽ Goals
        🟨 / 🟥 Cards (si existen)
        🔁 Substitutions
    - 100% robusta (no rompe si faltan columnas)
    """

    df = df_events.copy()

    # -----------------------------
    # Detectar columna de tarjetas
    # -----------------------------
    card_col = None
    for c in df.columns:
        if c.lower().endswith("card.name"):
            card_col = c
            break

    # -----------------------------
    # Detectar columnas opcionales
    # -----------------------------
    has_outcome = "shot.outcome.name" in df.columns
    has_type = "shot.type.name" in df.columns
    has_is_og = "shot.is_own_goal" in df.columns

    # -----------------------------
    # Filtrar eventos importantes
    # -----------------------------
    mask = (
        (df["type.name"] == "Substitution")
    )

    # Goles normales y autogoles
    mask = mask | (
        (df["type.name"] == "Shot") & (
            (has_outcome and df["shot.outcome.name"].isin(["Goal", "Own Goal"])) |
            (has_type and df["shot.type.name"] == "Own Goal") |
            (has_is_og and df["shot.is_own_goal"] == True)
        )
    )

    # Tarjetas (si existen)
    if card_col:
        mask = mask | (
            (df["type.name"] == "Foul Committed") & (df[card_col].notna())
        )

    important_events = df[mask].copy()

    important_events["minute"] = important_events["minute"].fillna(0).astype(int)
    important_events = important_events.sort_values("minute")

    # -----------------------------
    # HTML / CSS
    # -----------------------------
    html = """
    <style>
        .timeline-item {
            border-left: 2px solid #888;
            margin-left: 20px;
            padding-left: 12px;
            margin-bottom: 22px;
        }
        .timeline-label {
            font-weight: 600;
            color: #333;
        }
        .player-out {
            color: #b30000;
            font-weight: 600;
        }
        .player-in {
            color: #006600;
            font-weight: 600;
        }
        .event {
            margin-left: 6px;
        }
    </style>
    """

    html += "<h4>🕒 Match Timeline</h4>"
    html += "<div class='timeline-item'><div class='timeline-label'>Kickoff</div></div>"

    
    for _, row in important_events.iterrows():
        m = int(row["minute"])
        team = row["team.name"]

        html += "<div class='timeline-item'>"
        html += f"<div class='timeline-label'>{m}’ — {team}</div>"

        # ---------------- GOALS ----------------
        if row["type.name"] == "Shot":

        # Detectar autogol de forma robusta
            is_own_goal = False

            if "shot.outcome.name" in row and row["shot.outcome.name"] == "Own Goal":
                is_own_goal = True

            if "shot.type.name" in row and row["shot.type.name"] == "Own Goal":
                is_own_goal = True

            if "shot.is_own_goal" in row and row["shot.is_own_goal"] == True:
                is_own_goal = True

            if is_own_goal:
                html += (
                    f"<div class='event'>⚽ <b>Own Goal</b> — "
                    f"{row['player.name']} (for opponent)</div>"
                )
            else:
                html += (
                    f"<div class='event'>⚽ <b>Goal</b> — "
                    f"{row['player.name']}</div>"
            )

        # ---------------- CARDS ----------------
        elif card_col and row["type.name"] == "Foul Committed":
            card = row[card_col]

            if card == "Yellow Card":
                html += (
                    f"<div class='event'>🟨 Yellow Card — "
                    f"{row['player.name']}</div>"
                )

            elif card == "Red Card":
                html += (
                    f"<div class='event'>🟥 Red Card — "
                    f"{row['player.name']}</div>"
                )

            # -------------- SUBSTITUTIONS ----------
        elif row["type.name"] == "Substitution":
                outp = row["player.name"]
                inp = row["substitution.replacement.name"]

                html += (
                    f"<div class='event'><span class='player-out'>🔻 {outp}</span></div>"
                )
                html += (
                    f"<div class='event'><span class='player-in'>🔺 {inp}</span></div>"
                )

        html += "</div>"


    html += "<div class='timeline-item'><div class='timeline-label'>End of match</div></div>"

    return html