"""Endpoints del servicio de auditoría."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ruta_comun.seguridad import Principal, ip_cliente

from ..application.casos_uso import ServicioAuditoria


class EventoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accion: str = Field(pattern=r"^[a-z_]{3,50}$")
    actor: str = Field(min_length=1, max_length=120)
    actor_tipo: Literal["usuario", "servicio", "sistema"]
    roles: list[str] = Field(default_factory=list, max_length=20)
    recurso: str = Field(min_length=1, max_length=200)
    detalle: dict[str, Any] = Field(default_factory=dict)
    ip: str = Field("interna", max_length=64)


def construir_router(servicio: ServicioAuditoria, requerir_roles) -> APIRouter:
    r = APIRouter(prefix="/api/auditoria")
    solo_servicios = requerir_roles("servicio_interno")
    solo_auditor = requerir_roles("auditor")

    async def _auto_registro(p: Principal, request: Request, que: str, detalle: dict[str, Any]) -> None:
        """Quien consulta la auditoría también queda auditado."""
        await servicio.registrar(
            {"accion": "auditoria_consultada", "actor": p.usuario, "actor_tipo": "usuario",
             "roles": sorted(x for x in p.roles if not x.startswith("default-roles")), "recurso": que,
             "detalle": detalle, "ip": ip_cliente(request)},
            servicio_origen="auditoria",
        )

    @r.post("/eventos", status_code=status.HTTP_201_CREATED, summary="Registrar evento (solo servicios internos)")
    async def registrar(e: EventoEntrada, p: Principal = Depends(solo_servicios)) -> dict[str, Any]:
        return await servicio.registrar(e.model_dump(), servicio_origen=p.cliente)

    @r.get("/eventos", summary="Consultar eventos (auditor)")
    async def listar(
        request: Request,
        accion: str | None = Query(None, pattern=r"^[a-z_]{3,50}$"),
        recurso: str | None = Query(None, max_length=200),
        actor: str | None = Query(None, max_length=120),
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = Query(50, ge=1, le=200),
        desplazamiento: int = Query(0, ge=0),
        p: Principal = Depends(solo_auditor),
    ) -> list[dict[str, Any]]:
        filtros = dict(accion=accion, recurso=recurso, actor=actor, desde=desde, hasta=hasta, limite=limite,
                       desplazamiento=desplazamiento)
        await _auto_registro(p, request, "eventos", {k: str(v) for k, v in filtros.items() if v is not None})
        return await servicio.listar(**filtros)

    @r.get("/eventos/{seq}", summary="Evento completo con su registro canónico (auditor)")
    async def obtener(seq: int, request: Request, p: Principal = Depends(solo_auditor)) -> dict[str, Any]:
        ev = await servicio.obtener(seq)
        if not ev:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento no encontrado")
        await _auto_registro(p, request, f"evento:{seq}", {})
        return ev

    @r.get("/verificar", summary="Verificar la integridad de toda la cadena (auditor)")
    async def verificar(request: Request, p: Principal = Depends(solo_auditor)) -> dict[str, Any]:
        resultado = await servicio.verificar()
        await _auto_registro(p, request, "cadena", {"integra": resultado["integra"],
                                                    "eventos_verificados": resultado["eventos_verificados"]})
        return resultado

    return r
