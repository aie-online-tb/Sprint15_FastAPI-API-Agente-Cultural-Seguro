"""
Cliente mínimo (Streamlit) → llama a la API del agente cultural seguro que hemos creado.

El front NO es la API. Aquí solo hacemos HTTP (POST /ask, GET messages)
y mostramos status + cuerpo. La API key viaja en la query (?api_key=...).
La clave se lee del .env de ESTE cliente (no se teclea en el sidebar).

Arranque: ver README (venv propio + streamlit run app.py; API en :8000).
"""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # .env junto a este app.py (API_KEY, API_BASE_URL)

# Misma clave que API_KEY del servidor; el cliente la envía en ?api_key=
api_key = (os.getenv("API_KEY") or "").strip()
default_base = (os.getenv("API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Cliente → Agente cultural", layout="centered")
st.title("Cliente Streamlit → API `/ask`")
st.caption(
    "Demo corta: un proceso cliente habla con el agente por HTTP. "
    "La clave vive en el `.env` de este cliente (solo local)."
)

with st.sidebar:
    st.header("Conexión")
    if api_key:
        st.success("API_KEY cargada desde `.env`")
    else:
        st.warning("Falta API_KEY en `.env` (copiad `.env.example`).")
    base_url = st.text_input(
        "URL base de la API",
        value=default_base,
        help="Donde corre uvicorn (carpeta 01_api_agente_segura). Por defecto: API_BASE_URL del .env.",
    ).rstrip("/")
    thread_id = st.text_input(
        "thread_id",
        value="demo-streamlit",
        help="Mismo hilo = mismo historial en SQLite.",
    )
    # /ask puede tardar (Gemini). Alineado con ASK_TIMEOUT_SECONDS del servidor (~300).
    timeout_s = st.number_input(
        "Timeout cliente (s)",
        min_value=30,
        max_value=600,
        value=300,
        help="Debe ser ≥ ASK_TIMEOUT_SECONDS del servidor; si no, requests corta antes.",
    )

st.markdown(
    """
**Flujo:** Streamlit (este proceso) → `requests.post/get(...)` → FastAPI (`:8000`).

Nota: como la petición sale de **Python** (no del navegador hacia la API),
aquí **no entra CORS**. CORS importa cuando el JS del navegador llama a otro origen.
"""
)

pregunta = st.text_area(
    "Pregunta al agente",
    value="¿Hay algo cultural esta tarde?",
    height=80,
)

col1, col2, col3 = st.columns(3)


def _params(*, with_key: bool) -> dict:
    params: dict = {}
    if with_key and api_key:
        params["api_key"] = api_key
    return params


def _mostrar_http(r: requests.Response) -> None:
    """Status + cuerpo JSON o texto."""
    st.metric("Status HTTP", r.status_code)
    try:
        body = r.json()
    except ValueError:
        st.text(r.text)
        return

    if r.status_code == 200:
        st.success("200 — OK")
        st.json(body)
    elif r.status_code == 401:
        st.warning("401 — falta api_key o no coincide con el .env del servidor")
        st.json(body)
    elif r.status_code == 429:
        st.warning("429 — rate limit; esperad un minuto o subid RATE_LIMIT_PER_MINUTE")
        st.json(body)
    elif r.status_code == 504:
        st.error("504 — el turno superó ASK_TIMEOUT_SECONDS en el servidor")
        st.json(body)
    else:
        st.error(f"Respuesta {r.status_code}")
        st.json(body)


def _ask(*, with_key: bool) -> None:
    """POST /ask con auto_aprobar=True (sin UI HITL)."""
    url = f"{base_url}/ask"
    params = _params(with_key=with_key)
    payload = {
        "pregunta": pregunta.strip(),
        "thread_id": (thread_id or "default").strip() or "default",
        "auto_aprobar": True,
    }

    # No mostramos api_key ni la URL con query (secreto)
    auth_nota = "con api_key" if with_key else "sin api_key (esperamos 401)"
    st.code(
        f"POST /ask  ({auth_nota})\n"
        f"pregunta: {payload['pregunta']}\n"
        f"thread_id: {payload['thread_id']}",
        language="text",
    )

    if not pregunta.strip():
        st.warning("Escribí una pregunta.")
        return

    try:
        with st.spinner("Esperando al agente…"):
            r = requests.post(
                url,
                params=params,
                json=payload,
                timeout=float(timeout_s),
            )
    except requests.Timeout:
        st.error(
            f"El cliente cortó a los {timeout_s}s (timeout de requests). "
            "Subid el valor del sidebar o bajad la carga del agente."
        )
        return
    except requests.RequestException as exc:
        st.error(f"No pudimos conectar con la API: {exc}")
        st.info(
            "¿Está uvicorn en marcha? "
            "Desde `01_api_agente_segura/`: `uvicorn app:app --reload --port 8000`"
        )
        return

    _mostrar_http(r)
    if r.status_code == 200:
        data = r.json()
        st.markdown("**Respuesta**")
        st.write(data.get("respuesta", ""))
        st.caption(f"thread_id={data.get('thread_id')} · done={data.get('done')}")


def _messages(*, with_key: bool) -> None:
    """GET /threads/{id}/messages."""
    tid = (thread_id or "default").strip() or "default"
    url = f"{base_url}/threads/{tid}/messages"
    params = _params(with_key=with_key)

    auth_nota = "con api_key" if with_key else "sin api_key"
    st.code(
        f"GET /threads/{tid}/messages  ({auth_nota})",
        language="text",
    )

    try:
        r = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        st.error(f"No pudimos conectar con la API: {exc}")
        return

    _mostrar_http(r)
    if r.status_code == 200:
        rows = r.json()
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Historial vacío para este thread_id.")


with col1:
    if st.button("Preguntar (con clave)", type="primary", use_container_width=True):
        if not api_key:
            st.warning("Falta API_KEY en el `.env` de este cliente (misma que la del servidor).")
        else:
            _ask(with_key=True)

with col2:
    if st.button("Preguntar sin clave → 401", use_container_width=True):
        _ask(with_key=False)

with col3:
    if st.button("Ver historial", use_container_width=True):
        if not api_key:
            st.warning("Falta API_KEY en el `.env` de este cliente.")
        else:
            _messages(with_key=True)
