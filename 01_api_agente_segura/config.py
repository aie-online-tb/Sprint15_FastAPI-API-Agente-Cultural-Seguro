"""Configuración — agente cultural + SQLite + seguridad/observabilidad."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"

# URL del motor SQLModel: fichero local historial.db (sin servidor Postgres).
DATABASE_URL = f"sqlite:///{ROOT / 'historial.db'}"

GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.3
MAX_STEPS_DEFAULT = 2
MAX_TURNS_DEFAULT = 4
MAX_ITER = 8

MADRID_EVENTOS_URL = (
    "https://datos.madrid.es/egob/catalogo/206974-0-agenda-eventos-culturales-100.json"
)
HTTP_TIMEOUT_SECONDS = 12

GUIA_PATH = DATA_DIR / "guia_cultural.txt"
EVENTOS_FALLBACK_PATH = DATA_DIR / "eventos_fallback.json"

CARTEL_DEFAULT_PATH = ASSETS_DIR / "cartel_demo.jpg"

DEMO_MENSAJES = [
    (
        "Quiero una tarde cultural barata en el centro de Madrid: "
        "museo o exposición y algo de música si encaja. "
        "Consulta la guía y el catálogo de eventos."
    ),
]

# --- Seguridad (API key, rate limit, CORS, timeout) -----------------------

API_KEY: str | None = os.getenv("API_KEY") or None
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8501,http://localhost:3000",
)
CORS_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

# Tope de tiempo por turno (POST /ask y /approve).
# Ajustar según lo que tarda Gemini en nuestra red (mirar duration_ms en los logs).
ASK_TIMEOUT_SECONDS: int = int(os.getenv("ASK_TIMEOUT_SECONDS", "300"))
