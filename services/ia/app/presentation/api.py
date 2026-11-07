"""Endpoints del servicio de IA."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ruta_comun.seguridad import Principal, ip_cliente

from ..application.casos_uso import ServicioIA


class Consulta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ruta_id: UUID
    pregunta: str = Field(min_length=3, max_length=500)


def construir_router(servicio: ServicioIA, requerir_roles) -> APIRouter:
    r = APIRouter(prefix="/api/ia")

    @r.post("/explicar", summary="Explicar una ruta con revisión ética (solo servicios internos)")
    async def explicar(ruta: dict[str, Any], p: Principal = Depends(requerir_roles("servicio_interno"))
                       ) -> dict[str, Any]:
        return await servicio.explicar(ruta, p)

    @r.post("/consultas", summary="Pregunta del equipo de salud sobre una ruta")
    async def consultar(body: Consulta, request: Request,
                        p: Principal = Depends(requerir_roles("coordinador", "equipo_salud"))) -> dict[str, Any]:
        return await servicio.consultar(str(body.ruta_id), body.pregunta, p, ip_cliente(request))

    return r
