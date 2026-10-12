import json
from pathlib import Path
from config import GAME_MAP

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRIMARY_GAME_FILE = DATA_DIR / "primary_game.json"
DEFAULT_PRIMARY_GAME = "567slots"


def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PRIMARY_GAME_FILE.exists():
        PRIMARY_GAME_FILE.write_text(
            json.dumps({"primary_game": DEFAULT_PRIMARY_GAME}, indent=2),
            encoding="utf-8",
        )


def get_primary_game():
    _ensure_file()
    try:
        data = json.loads(PRIMARY_GAME_FILE.read_text(encoding="utf-8"))
        game = str(data.get("primary_game", "")).strip()
        if game in GAME_MAP:
            return game
    except Exception:
        pass
    return DEFAULT_PRIMARY_GAME


def save_primary_game(game):
    game = str(game).strip()
    if game not in GAME_MAP:
        raise ValueError("Invalid primary game")
    _ensure_file()
    tmp = PRIMARY_GAME_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"primary_game": game}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(PRIMARY_GAME_FILE)
    return game
