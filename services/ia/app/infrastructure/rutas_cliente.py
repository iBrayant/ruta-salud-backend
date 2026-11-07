"""Adaptador FuenteRutas: consulta la ruta al servicio de rutas con el token DEL USUARIO.

Así el asistente nunca ve una ruta que el usuario no tenga permiso de ver.
"""
from __future__ import annotations

from typing import Any

import httpx


class ClienteRutas:
    def __init__(self, base_url: str) -> None:
        self._url = base_url.rstrip("/")

    async def obtener(self, ruta_id: str, token_usuario: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(f"{self._url}/api/rutas/{ruta_id}", headers={"Authorization": f"Bearer {token_usuario}"})
        if r.status_code in (403, 404, 422):
            return None
        r.raise_for_status()
        return r.json()
