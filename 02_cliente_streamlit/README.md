![Cabecera](../assets/cabecera_thebridge.png)

# Cliente Streamlit → agente cultural

**Cliente HTTP hacia el backend que hemos creado con FastAPI.**  [`../01_api_agente_segura/`](../01_api_agente_segura/).

La guía de arranque (venv API + venv cliente, dos terminales) está en el **[README raíz](../README.md)**.

Atajo si ya tenemos la API en `:8000`:

```bash
python -m venv .venv
source .venv/bin/activate          # Git Bash / macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

pip install -r requirements.txt
cp .env.example .env               # misma API_KEY que el servidor
streamlit run app.py
```

La `API_KEY` sale del **`.env` de este cliente** (no del sidebar). Debe coincidir con la del servidor.  
Sidebar: URL (o `API_BASE_URL` del `.env`) + `thread_id`.

Botones: **Preguntar (con clave)** → 200; **sin clave** → 401; **Ver historial** → GET messages.

Si la API está en otra URL, cambiáis la base en el sidebar (o en `.env`).
