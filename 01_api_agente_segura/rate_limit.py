"""
Rate limit en memoria: máximo N peticiones por API key cada 60 segundos.

Idea: guardar los timestamps de las últimas peticiones de cada clave.
Si en la ventana de 60 s hay demasiadas → 429.

Limitaciones (OK para clase, no para prod multi-proceso):
- Vive en RAM del proceso uvicorn → al reiniciar, el contador vuelve a 0.
- Varios workers / varias máquinas no comparten este dict (haría falta Redis, etc.).
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException

import config

logger = logging.getLogger(__name__)

# api_key → cola de timestamps (solo de peticiones recientes)
# defaultdict(deque): si la clave es nueva, crea una deque vacía sola
_hits: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(api_key: str) -> None:
    """Si esta clave supera RATE_LIMIT_PER_MINUTE en 60 s → 429."""
    now = time.monotonic()  # reloj estable para medir intervalos (no es hora de reloj)
    window = 60.0
    q = _hits[api_key]

    # Quitamos de la izquierda los hits demasiado antiguos (> 60 s)
    while q and (now - q[0]) > window:
        q.popleft()

    # Ya hay N hits válidos en la ventana → rechazar esta petición
    if len(q) >= config.RATE_LIMIT_PER_MINUTE:
        logger.warning(
            "rate limit 429: demasiadas peticiones (max=%s / 60s)",
            config.RATE_LIMIT_PER_MINUTE,
        )
        raise HTTPException(
            status_code=429,
            detail="Demasiadas peticiones; esperad un minuto",
        )

    # Registramos este hit (entra por la derecha)
    q.append(now)
