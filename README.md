![Cabecera](./assets/cabecera_thebridge.png)

# Agente cultural seguro + cliente Streamlit

Repo de práctica: una **API FastAPI** con agente cultural (historial SQLite), endurecida con API key, rate limit, CORS, logs (`thread_id` / `duration_ms`) y timeout por turno; y un **cliente Streamlit** que la consume. Dos carpetas a propósito — backend y front no se mezclan.

```text
cliente (Streamlit :8501) ──HTTP──► API agente (FastAPI :8000)
         02_cliente_streamlit/         01_api_agente_segura/
```

## Estructura

```text
.
├── README.md                 # Esta guía (arranque unificado)
├── 01_api_agente_segura/     # Servidor: agente + seguridad + logs
│   ├── app.py
│   ├── security.py
│   ├── rate_limit.py
│   ├── config.py
│   ├── src/                  # agente + SQLite (dado)
│   └── README.md             # Práctica guiada (curl / Swagger / errores)
└── 02_cliente_streamlit/     # Cliente: POST /ask + GET messages
    ├── app.py
    ├── requirements.txt
    └── README.md
```

| Carpeta | Rol | Puerto típico |
|---------|-----|----------------|
| [`01_api_agente_segura/`](./01_api_agente_segura/) | Servidor | `8000` (`/docs`) |
| [`02_cliente_streamlit/`](./02_cliente_streamlit/) | Cliente | `8501` |

Cada una tiene su propio `requirements.txt` y su propio `.venv`.

---

## Cómo ejecutarlo

Clonamos el repo y abrimos **dos terminales**.

### Terminal A — API

```bash
cd 01_api_agente_segura
python -m venv .venv
source .venv/bin/activate          # Git Bash / macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

pip install -r requirements.txt
cp .env.example .env               # GEMINI_API_KEY + API_KEY
uvicorn app:app --reload --port 8000
```

Comprobación: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status":"ok", ...}`  
Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (rutas protegidas: query `api_key`).

### Terminal B — Cliente Streamlit

```bash
cd 02_cliente_streamlit
python -m venv .venv
source .venv/bin/activate          # Git Bash / macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

pip install -r requirements.txt
cp .env.example .env               # misma API_KEY que el servidor
streamlit run app.py
```

La `API_KEY` va en el **`.env` del cliente** (igual que en el del servidor).  
Sidebar: URL + `thread_id`. **Preguntar con clave** → 200. **Sin clave** → 401. **Ver historial** → mensajes SQL.

---

## Qué practicamos

1. **Auth en el agente:** `/ask` e historial con `?api_key=`; `/health` y `/docs` públicos.
2. **Observabilidad mínima:** cada turno loguea `thread_id` + `duration_ms`. No logueamos secretos (`API_KEY`, `GEMINI_API_KEY`, ni el valor de `?api_key=`).
3. **Timeout:** Python corta el turno si supera `ASK_TIMEOUT_SECONDS` → 504.
4. **Front que consume API:** Streamlit hace `requests` → status + cuerpo (401 / 429 / 504 visibles en UI).
5. **Capa de protección** alrededor del negocio dado (el agente ya viene listo).

**CORS:** el cliente Streamlit llama desde **Python** (`requests`), así que CORS no interviene aquí. CORS importa cuando el **navegador** pide a otro origen; la API ya declara `CORS_ORIGINS` en el `.env` para ese caso.

Detalle paso a paso (401 / 429 / ask / logs / 504): [`01_api_agente_segura/README.md`](./01_api_agente_segura/README.md).

---

## Orden recomendado

1. Arrancar la API y probar en `/docs` o curl (README de `01_`).
2. Arrancar el cliente y repetir ask / 401 / historial desde la UI.
