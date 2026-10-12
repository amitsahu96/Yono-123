# API Keys
FOUR_SIM_API_KEY = "6155ce0f0d95e090ddceaba215eb7d30"
OTPDOCTOR_API_KEY = "c1i12bb1qbc7easy8zbx24u08imvq0zb"

# SpyEye
BASE_URL = "https://spyeyeloots4.online/up_yonoV3"

# License
LICENSE_KEY = "LF-BALI-001"
SPYEYE_API_KEY = "TBRASAHUREG77H1"
SECRET_KEY = "7g0k9fs74m2b4c5e"
LICENSE_SERVER = "https://spyeye-cv4o.onrender.com/api/check-license"

# Timers
MAIN_GAME_WAIT = 130
SUBGAME_FOREGROUND_WAIT = 40
NEXT_GAME_DELAY = 3

BACKGROUND_TIMEOUT_4SIM = 600
BACKGROUND_TIMEOUT_OTPDOCTOR = 600

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Games map...
GAME_MAP = {
    "567slots": {"api": "567slots", "ui": "567slots"},
    "MBMBet": {"api": "mbmbet", "ui": "MBMBet"},
    "Bingo": {"api": "bingo101", "ui": "Bingo"},
    "IndSlots": {"api": "indslots", "ui": "IndSlots"},
    "HiRummy": {"api": "hirummy", "ui": "HiRummy"},
    "Maha": {"api": "mahagames", "ui": "Maha"},
    "YonoVip": {"api": "yonovip", "ui": "YonoVip"},
    "789Jackpots": {"api": "789jackpots", "ui": "789Jackpots"},
    "INDRummy": {"api": "indrummy", "ui": "INDRummy"},
    "YonoGames": {"api": "yonogames", "ui": "YonoGames"},
    "SpinCrush": {"api": "spincrush", "ui": "SpinCrush"},
    "YonoSlots": {"api": "yonoslots", "ui": "YonoSlots"},
    "GoGoRummy": {"api": "gogorummy", "ui": "GoGoRummy"},
    "INDclub": {"api": "indclub", "ui": "INDclub"},
    "YonoArcade": {"api": "yonoarcade", "ui": "YonoArcade"},
    "YonoRummy": {"api": "yonorummy", "ui": "YonoRummy"},
    "Rummy91": {"api": "rummy91", "ui": "Rummy91"},
    "RummyLudo": {"api": "rummyludo", "ui": "RummyLudo"},
    "ShareSlots": {"api": "shareslots", "ui": "ShareSlots"},
}

API_TO_UI = {v["api"].lower(): v["ui"] for v in GAME_MAP.values()}
