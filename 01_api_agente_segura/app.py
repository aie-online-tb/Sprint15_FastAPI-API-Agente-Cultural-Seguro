"""
API FastAPI — agente cultural + seguridad (API key, rate limit) + observabilidad.

  /ask → procesar_turno → save_turn (user + assistant)
  GET /threads/{id}/messages → listar historial

Público: /, /docs, /health
Protegido (?api_key=): /ask, /approve, /threads/.../messages

Python decide timeout (ASK_TIMEOUT_SECONDS) y auth; el LLM solo propone el turno.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import asynccontextmanager
from typing import Callable, Dict, TypeVar

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import config
from gemini_auth import configurar_gemini_api_key
from schemas import ApproveIn, AskIn, AskOut, MessageOut
from security import require_api_key
from src import db
from src.agent import aprobar_plan, procesar_turno
from src.state import crear_estado

configurar_gemini_api_key()

# Logs a consola (uvicorn). Nunca logueamos API_KEY ni GEMINI_API_KEY.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Sesiones del agente en RAM (checkpointer / estado del grafo)
_sessions: Dict[str, dict] = {}
# Última pregunta por hilo (para guardar el turno tras /approve)
_last_pregunta: Dict[str, str] = {}

T = TypeVar("T")


def _con_timeout(fn: Callable[..., T], *args) -> T:
    """
    Ejecuta fn en un hilo y corta si supera ASK_TIMEOUT_SECONDS.
    Junior-simple: un ThreadPoolExecutor por llamada (no hace falta cola global).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        return future.result(timeout=config.ASK_TIMEOUT_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Al arrancar: CREATE TABLE si historial.db aún no tiene schema
    db.ensure_schema()
    yield


app = FastAPI(
    title="API agente cultural segura",
    description=(
        "Agente LangGraph + historial SQLite, con api_key, rate limit, CORS, "
        "logs por thread_id y timeout por turno. "
        "En /docs: Try it out → parámetro api_key."
    ),
    lifespan=lifespan,
)

# CORS: el navegador bloquea cross-origin salvo que la API lo permita.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


def _estado_sesion(thread_id: str, pedido: str = "") -> dict:
    if thread_id not in _sessions:
        _sessions[thread_id] = crear_estado(pedido)
    return _sessions[thread_id]


def _a_ask_out(estado: dict, thread_id: str) -> AskOut:
    return AskOut(
        respuesta=estado.get("respuesta") or "",
        thread_id=thread_id,
        done=bool(estado.get("done", False)),
        pendiente_hitl=bool(estado.get("pendiente_hitl", False)),
        error=estado.get("error") or None,
    )


def _persistir_si_hay_respuesta(thread_id: str, pregunta: str, estado: dict) -> None:
    """Puente API → SQL: escribe user+assistant en historial.db vía db.save_turn."""
    respuesta = (estado.get("respuesta") or "").strip()
    if not respuesta:
        return
    db.save_turn(thread_id, pregunta, respuesta)


@app.get("/health")
def health():
    """Público: pulso del servicio (sin API key)."""
    return {"status": "ok", "storage": db.storage_mode()}


# --- Rutas protegidas --------------------------------------------------------
# Depends(require_api_key): sin clave válida no se ejecuta el body.


@app.post("/ask", response_model=AskOut, dependencies=[Depends(require_api_key)])
def ask(body: AskIn) -> AskOut:
    """
    Un turno del agente. Tras responder, guarda user+assistant en SQLite.
    Con auto_aprobar=True, si hay HITL se aprueba y también se persiste.
    """
    pregunta = body.pregunta.strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="pregunta vacía")

    thread_id = (body.thread_id or "default").strip() or "default"
    estado = _estado_sesion(thread_id, pedido=pregunta)
    _last_pregunta[thread_id] = pregunta

    t0 = time.perf_counter()

    def _turno() -> dict:
        out = procesar_turno(estado, pregunta, thread_id)
        if body.auto_aprobar and out.get("pendiente_hitl"):
            out = aprobar_plan(thread_id, True, out)
        return out

    try:
        out = _con_timeout(_turno)
    except FuturesTimeoutError:
        logger.error(
            "POST /ask timeout 504 thread_id=%s limit_s=%s",
            thread_id,
            config.ASK_TIMEOUT_SECONDS,
        )
        raise HTTPException(
            status_code=504,
            detail="El turno del agente superó el tiempo máximo",
        ) from None

    _sessions[thread_id] = out

    # Solo persistimos si el turno cerró (sin HITL pendiente)
    if not out.get("pendiente_hitl"):
        _persistir_si_hay_respuesta(thread_id, pregunta, out)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "POST /ask thread_id=%s duration_ms=%s pendiente_hitl=%s",
        thread_id,
        duration_ms,
        bool(out.get("pendiente_hitl")),
    )
    return _a_ask_out(out, thread_id)


@app.post("/approve", response_model=AskOut, dependencies=[Depends(require_api_key)])
def approve(body: ApproveIn) -> AskOut:
    """HITL manual; si hay respuesta, se guarda en el historial."""
    thread_id = body.thread_id.strip()
    if thread_id not in _sessions:
        raise HTTPException(
            status_code=404,
            detail="No hay sesión para ese thread_id. Haz antes un POST /ask.",
        )

    estado = _sessions[thread_id]
    if not estado.get("pendiente_hitl"):
        raise HTTPException(
            status_code=400,
            detail="No hay plan pendiente de aprobación en este hilo.",
        )

    t0 = time.perf_counter()

    try:
        out = _con_timeout(aprobar_plan, thread_id, body.aprobado, estado)
    except FuturesTimeoutError:
        logger.error(
            "POST /approve timeout 504 thread_id=%s limit_s=%s",
            thread_id,
            config.ASK_TIMEOUT_SECONDS,
        )
        raise HTTPException(
            status_code=504,
            detail="La aprobación superó el tiempo máximo",
        ) from None

    _sessions[thread_id] = out

    pregunta = _last_pregunta.get(thread_id, "")
    # Tras aprobar/rechazar, si ya no hay HITL, guardamos el turno en SQLite
    if pregunta and not out.get("pendiente_hitl"):
        _persistir_si_hay_respuesta(thread_id, pregunta, out)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "POST /approve thread_id=%s duration_ms=%s aprobado=%s",
        thread_id,
        duration_ms,
        body.aprobado,
    )
    return _a_ask_out(out, thread_id)


@app.get(
    "/threads/{thread_id}/messages",
    response_model=list[MessageOut],
    dependencies=[Depends(require_api_key)],
)
def get_messages(thread_id: str) -> list[MessageOut]:
    """Lee el historial desde SQLite (no desde la RAM del agente)."""
    rows = db.list_messages(thread_id)
    return [MessageOut(**row) for row in rows]
