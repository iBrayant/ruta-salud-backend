"""Cliente del microservicio de auditoría.

Política *fail-closed*: si el evento no se puede registrar, la operación que lo
origina falla. Una ruta sin rastro de auditoría no debe llegar al usuario.
"""
from __future__ import annotations

from typing import Any

import httpx

from .oauth_cliente import ClienteCredenciales
from .seguridad import Principal


class AuditoriaNoDisponible(RuntimeError):
    pass


class ClienteAuditoria:
    def __init__(self, base_url: str, credenciales: ClienteCredenciales) -> None:
        self._url = base_url.rstrip("/") + "/api/auditoria/eventos"
        self._cred = credenciales

    async def registrar(
        self,
        accion: str,
        actor: Principal | None,
        recurso: str,
        detalle: dict[str, Any],
        ip: str = "interna",
    ) -> dict[str, Any]:
        evento = {
            "accion": accion,
            "actor": actor.usuario if actor else "sistema",
            "actor_tipo": ("servicio" if actor.es_servicio else "usuario") if actor else "sistema",
            "roles": sorted(r for r in actor.roles if not r.startswith("default-roles")) if actor else [],
            "recurso": recurso,
            "detalle": detalle,
            "ip": ip,
        }
        try:
            token = await self._cred.token()
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.post(self._url, json=evento, headers={"Authorization": f"Bearer {token}"})
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPError, KeyError) as e:
            raise AuditoriaNoDisponible(f"No fue posible registrar el evento de auditoría: {e}") from e
