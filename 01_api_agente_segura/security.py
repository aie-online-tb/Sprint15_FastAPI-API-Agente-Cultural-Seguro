"""
Capa de seguridad: comprobar API key y, si es válida, aplicar rate limit.

FastAPI llama a `require_api_key` vía Depends(...) ANTES de entrar a la ruta.
Si aquí lanzamos HTTPException, la ruta del agente ni siquiera se ejecuta.
"""

import logging

from fastapi import HTTPException, Query

import config
from rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


def require_api_key(
    # Query(...) → FastAPI lee ?api_key=... de la URL (y lo muestra en /docs)
    api_key: str | None = Query(
        default=None,
        description="Clave de acceso (misma que API_KEY en .env)",
    ),
) -> str:
    """
    1) Servidor sin API_KEY en .env → 503 (mal configurado).
    2) Cliente sin clave o clave distinta → 401.
    3) Clave OK → rate limit; si pasa, devolvemos la clave (el endpoint sigue).
    """
    # Fallo del servidor (no del cliente): falta secreto en el entorno
    if not config.API_KEY:
        logger.error("auth 503: API_KEY no configurada en el servidor")
        raise HTTPException(
            status_code=503,
            detail="API_KEY no configurada en el servidor",
        )

    # Fallo del cliente: no envía clave o no coincide con la del .env
    if not api_key or api_key != config.API_KEY:
        # Nunca logueéis el valor de api_key (es un secreto)
        logger.warning("auth 401: api_key ausente o inválida")
        raise HTTPException(
            status_code=401,
            detail="API key inválida o ausente",
        )

    # Misma clave = mismo "cliente" a efectos del contador de peticiones
    check_rate_limit(api_key)
    return api_key
