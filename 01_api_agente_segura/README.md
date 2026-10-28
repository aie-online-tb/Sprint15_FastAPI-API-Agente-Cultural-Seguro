![Cabecera](../assets/cabecera_thebridge.png)

# Workout — API agente cultural segura

**El agente ya está dado:** cultural + historial SQLite (`/ask`, `/threads/.../messages`). Nos centramos en crear un agente de IA más seguro.

**En qué nos centramos:** capa de **seguridad y observabilidad** — API key por query, rate limit, CORS, logs con `thread_id` + `duration_ms`, y timeout por turno (`ASK_TIMEOUT_SECONDS` → **504**).

```text
cliente → /ask?api_key=... → rate limit → procesar_turno (con timeout)
                ↓
        logs: thread_id + duration_ms
                ↓
        /health y /docs sin clave
```

### Cómo funciona la clave (servidor vs cliente)

1. **En el servidor** guardamos la clave válida en `.env` (`API_KEY=...`).
2. **Quien haga una petición** a las rutas protegidas envía `api_key` en la query (`?api_key=...`).
3. Esa `api_key` **debe coincidir** con la del `.env`. Si el cliente no la envía o es incorrecta → **401**.

No confundir con **503**: eso es cuando el **servidor** no tiene `API_KEY` en su `.env` (mal configurado). El cliente puede enviar lo que sea; la API no puede validar.

`GEMINI_API_KEY` es **otra** clave: solo la usa el proceso para llamar a Gemini. No la enviamos en la query ni la logueamos.

---

## Estructura

```text
.
├── app.py             # Rutas + CORS + Depends + timeout + logs
├── schemas.py         # AskIn / AskOut / ApproveIn / MessageOut
├── config.py          # agente + API_KEY, rate limit, CORS, timeout
├── security.py        # require_api_key (?api_key=)
├── rate_limit.py      # Contador en memoria → 429
├── gemini_auth.py     # carga GEMINI_API_KEY
├── src/               # agente + SQLModel (dado)
├── data/              # guía + fallback eventos
├── assets/
├── requirements.txt
├── .env.example
└── README.md
```

Ejecutamos siempre **desde esta carpeta** (donde está `app.py`).

---

## Instalación y arranque

```bash
python -m venv .venv
source .venv/bin/activate          # Git Bash / macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

pip install -r requirements.txt
cp .env.example .env               # GEMINI_API_KEY + API_KEY
uvicorn app:app --reload --port 8000
```

**http://127.0.0.1:8000/docs** — en rutas protegidas: *Try it out* → query **`api_key`**.

**Tiempo del `/ask`:** en `config.py`, `MAX_STEPS_DEFAULT`, `MAX_TURNS_DEFAULT` y `MAX_ITER` limitan cuánto “piensa” el agente (llamadas a Gemini / tools). Si la demo va lenta o la cuota free da **429** de Google, se pueden bajar un poco (p. ej. steps/iter menores). Tras editar `config.py`, uvicorn con `--reload` suele recargar solo.

---

## Rutas

| Método | Ruta | ¿`api_key`? | Qué hace |
|--------|------|-------------|----------|
| GET | `/health` | No | Pulso + `"storage": "sqlite"` |
| GET | `/docs` | No | Swagger |
| POST | `/ask` | **Sí** | Un turno; timeout → 504 |
| GET | `/threads/{thread_id}/messages` | **Sí** | Historial SQL |

---

## Práctica guiada

Sustituimos `<CLAVE>` por el valor de `API_KEY` en nuestro `.env`.

### 1) Health sin clave

GET `http://127.0.0.1:8000/health` → **200** `{"status":"ok", ...}`.

### 2) Ask sin API KEY → 401

POST `http://127.0.0.1:8000/ask` con body:

```json
{
  "pregunta": "¿Hay algo cultural esta tarde?",
  "thread_id": "demo-1",
  "auto_aprobar": true
}
```

→ **401** (sin `?api_key=`).

En consola: `WARNING` de auth (sin imprimir la clave).

### 3) Ask con API KEY → 200

POST `http://127.0.0.1:8000/ask?api_key=<CLAVE>` con el mismo body → **200** y una `respuesta`.

En consola: `INFO POST /ask thread_id=demo-1 duration_ms=...` (sin secretos).

### 4) Historial con clave

GET `http://127.0.0.1:8000/threads/demo-1/messages?api_key=<CLAVE>` → mensajes `user` / `assistant` en SQLite.

### 5) Rate limit → 429

Usamos el GET de messages para comprobar el rate limit. Limitamos las peticiones a 5 por minuto.

1. Bajamos `RATE_LIMIT_PER_MINUTE=5` en `.env` y **reiniciamos** uvicorn (el `.env` no se recarga solo).
2. Repetimos GET `http://127.0.0.1:8000/threads/demo-1/messages?api_key=<CLAVE>` **más de 5 veces** en menos de un minuto → **429**.

`/health` no cuenta (no pasa por `require_api_key`). `/ask` también suma al cupo, pero para la demo preferimos `messages` para no gastar cuota del LLM.

### 6) Timeout — margen y forzar 504

`ASK_TIMEOUT_SECONDS` en `.env` limita cuánto puede durar un turno. Si se pasa → **504**.

El ejemplo usa **300** s (5 min). Si el tope es más bajo que lo que tarda Gemini, casi todos los `/ask` fallan con 504.

**Importante:** tras cambiar el `.env`, **reiniciamos uvicorn** (Ctrl+C y volver a lanzar). El `--reload` no aplica cambios del `.env` solo.

**A) Uso normal (margen)**

1. Tras un `/ask` OK (paso 3), miramos `duration_ms` en consola.
2. En `.env`, ponemos `ASK_TIMEOUT_SECONDS` con margen (p. ej. el doble, o dejamos **300**).
3. Reiniciamos uvicorn.

**B) Forzar un 504 (ver el efecto)**

1. En `.env`: `ASK_TIMEOUT_SECONDS=15`.
2. Reiniciamos uvicorn.
3. POST `/ask?api_key=<CLAVE>` (mismo body que el paso 3) → **504**.

En consola: `ERROR POST /ask timeout 504 thread_id=... limit_s=15`.

Luego volvemos a un valor holgado (p. ej. **300**) y reiniciamos otra vez.

---

## Cómo leer el código

1. **`schemas.py` / rutas del agente** — API de negocio (ya dada).
2. **`config.py`** — paths del agente + `API_KEY`, rate limit, `CORS_ORIGINS`, `ASK_TIMEOUT_SECONDS`.
3. **`security.py`** + **`rate_limit.py`** — 401 / 429 / 503.
4. **`app.py`** — `CORSMiddleware`, `Depends(require_api_key)`, logs `thread_id`/`duration_ms`, timeout → 504.

**Python decide los guardrails** (quién entra, cuántas peticiones por minuto, cuánto puede tardar un turno); el LLM solo propone el contenido de la respuesta.

---

## Qué NO hace

- Rate limit distribuido (Redis): el contador vive en RAM del proceso.
- JWT / OAuth / login de usuarios.
- Docker / Render / CI/CD.

---

## Checklist

- [ ] `/health` sin clave OK.
- [ ] `/ask` sin `api_key` → 401; con `?api_key=` → 200.
- [ ] Vimos en consola `thread_id` + `duration_ms` (sin keys).
- [ ] Forzamos un **429** con GET `messages` (bajando `RATE_LIMIT_PER_MINUTE`).
- [ ] GET `/threads/.../messages` exige clave.
- [ ] Ajustamos / forzamos `ASK_TIMEOUT_SECONDS` (reiniciando uvicorn) y vimos un **504**.
