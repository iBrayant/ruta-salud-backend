"""Adaptador ServicioExplicacion: llama al microservicio de IA con token de servicio.

La explicación es *best-effort*: si la IA falla, la ruta igual se entrega (la
decisión la toma el algoritmo, no la IA).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ruta_comun.oauth_cliente import ClienteCredenciales

log = logging.getLogger("rutas.ia")


class ClienteIA:
    def __init__(self, base_url: str, credenciales: ClienteCredenciales, timeout_s: float = 45) -> None:
        self._url = base_url.rstrip("/") + "/api/ia/explicar"
        self._cred = credenciales
        self._timeout = timeout_s

    async def explicar(self, ruta: dict[str, Any]) -> dict[str, Any] | None:
        try:
            token = await self._cred.token()
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                r = await http.post(self._url, json=ruta, headers={"Authorization": f"Bearer {token}"})
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as e:
            log.warning("Servicio de IA no disponible; ruta sin explicación: %s", e)
            return None
