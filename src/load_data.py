import json
import pandas as pd
from pathlib import Path

def load_events(match_id: int, data_path="data/events/"):
    file = Path(data_path) / f"{match_id}.json"
    if not file.exists():
        raise FileNotFoundError(f"El archivo no existe: {file}")

    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.json_normalize(data, sep=".")
    return df


def load_match_metadata(match_id: int, matches_path="data/matches/"):
    """Busca metadata del partido explorando subcarpetas por competición."""
    matches_root = Path(matches_path)

    # Recorrer todas las carpetas dentro de matches/
    for competition_folder in matches_root.iterdir():
        if competition_folder.is_dir():  # ejemplo: matches/43/
            # Buscar todos los archivos JSON dentro de esta carpeta
            for json_file in competition_folder.glob("*.json"):
                with open(json_file, "r", encoding="utf-8") as f:
                    matches = json.load(f)

                # Revisar cada partido
                for m in matches:
                    if m["match_id"] == match_id:
                        return pd.json_normalize(m, sep=".")

    raise ValueError(f"No se encontró metadata para match_id {match_id}")


def load_all_matches(matches_path="data/matches/"):
    """Carga todos los partidos de todas las competiciones."""
    matches_root = Path(matches_path)
    all_matches = []

    for competition_folder in matches_root.iterdir():
        if competition_folder.is_dir():  # ejemplo: matches/43/
            for json_file in competition_folder.glob("*.json"):
                with open(json_file, "r", encoding="utf-8") as f:
                    matches = json.load(f)
                
                all_matches.extend(matches)

    df = pd.json_normalize(all_matches, sep=".")
    return df

def load_lineups(match_id: int, lineups_path="data/lineups/"):
    file = Path(lineups_path) / f"{match_id}.json"
    if not file.exists():
        return None
    
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    lineups = []

    for team in data:
        team_name = team.get("team_name", "Unknown Team")

        for player in team.get("lineup", []):
            player_name = player.get("player_name", "Unknown Player")
            number = player.get("jersey_number", "NA")

            if "position" in player and isinstance(player["position"], dict):
                position = player["position"].get("name", "NA")
            else:
                position = "NA"

            lineups.append({
                "team": team_name,
                "player": player_name,
                "number": number,
                "position": position
            })

    return pd.DataFrame(lineups)
