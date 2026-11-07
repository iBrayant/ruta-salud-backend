"""Endpoints HTTP del servicio de rutas."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ruta_comun.seguridad import Principal, ip_cliente

from ..application.casos_uso import ServicioRutas, clima_de_ruta
from .schemas import SolicitudRuta, SolicitudSimulacion


def _vista(ruta: dict[str, Any], incluir_snapshot: bool = False) -> dict[str, Any]:
    r = ruta["resultado"]
    salida = {
        "ruta_id": ruta["id"],
        "codigo": ruta["codigo"],
        "fecha_jornada": str(ruta["fecha_jornada"]),
        "estado": ruta["estado"],
        "creado_por": ruta["creado_por"],
        "creado_en": ruta["creado_en"],
        "orden": r["paradas"],
        "regreso": {"km": r["regreso_km"], "min": r["regreso_min"], "hora": r["hora_regreso"]},
        "distancia_total_km": r["distancia_total_km"],
        "tiempo_viaje_min": r["tiempo_viaje_min"],
        "tiempo_total_min": r["tiempo_total_min"],
        "optimizacion": {
            "algoritmo": "priorizacion + vecino_mas_cercano + 2-opt",
            "costo_heuristico_min": r["costo_heuristico_min"],
            "costo_optimo_min": r["costo_optimo_min"],
            "brecha_vs_optimo_pct": r["brecha_vs_optimo_pct"],
        },
        "descartadas": r["descartadas"],
        "ranking": r["ranking"],
        "parametros": ruta["parametros"],
        "fuente_distancias": ruta["snapshot"]["matriz"]["fuente"],
        "clima_disponible": ruta["snapshot"]["clima"] is not None,
        "clima_por_vereda": clima_de_ruta(ruta),
        "version_datos": ruta["version_datos"],
        "huellas": {"entradas": ruta["huella_entradas"], "resultado": ruta["huella_resultado"]},
        "explicacion": ruta.get("explicacion"),
    }
    if incluir_snapshot:
        salida["snapshot"] = ruta["snapshot"]
    return salida


def construir_router(servicio: ServicioRutas, requerir_roles) -> APIRouter:
    r = APIRouter(prefix="/api")
    lectores = requerir_roles("coordinador", "equipo_salud", "auditor")

    @r.get("/veredas", summary="Veredas precargadas con su índice de vulnerabilidad desglosado")
    async def veredas(_: Principal = Depends(lectores)) -> dict[str, Any]:
        return servicio.veredas_detalle()

    @r.post("/rutas", status_code=status.HTTP_201_CREATED, summary="Generar ruta priorizada de la jornada")
    async def generar(body: SolicitudRuta, request: Request,
                      p: Principal = Depends(requerir_roles("coordinador"))) -> dict[str, Any]:
        return _vista(await servicio.generar(body.a_dominio(), p, ip_cliente(request)))

    @r.post("/rutas/simular", summary="Simular N jornadas y medir cobertura y equidad")
    async def simular(body: SolicitudSimulacion, request: Request,
                      p: Principal = Depends(requerir_roles("coordinador", "auditor"))) -> dict[str, Any]:
        return await servicio.simular(body.a_dominio(), body.n_jornadas, p, ip_cliente(request))

    @r.get("/rutas", summary="Listar rutas generadas")
    async def listar(limite: int = Query(20, ge=1, le=100), desplazamiento: int = Query(0, ge=0),
                     _: Principal = Depends(lectores)) -> list[dict[str, Any]]:
        return await servicio.listar(limite, desplazamiento)

    @r.get("/rutas/{ruta_id}", summary="Detalle de una ruta")
    async def obtener(ruta_id: UUID, incluir_snapshot: bool = False,
                      p: Principal = Depends(lectores)) -> dict[str, Any]:
        if incluir_snapshot and not p.tiene("auditor"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el auditor puede ver las entradas completas")
        return _vista(await servicio.obtener(str(ruta_id)), incluir_snapshot)

    @r.post("/rutas/{ruta_id}/ejecutada", summary="Confirmar que la jornada se realizó (alimenta la equidad)")
    async def ejecutada(ruta_id: UUID, request: Request,
                        p: Principal = Depends(requerir_roles("coordinador"))) -> dict[str, Any]:
        return _vista(await servicio.marcar_ejecutada(str(ruta_id), p, ip_cliente(request)))

    @r.post("/rutas/{ruta_id}/reproducir", summary="Recalcular la ruta con sus entradas originales y comparar")
    async def reproducir(ruta_id: UUID, request: Request,
                         p: Principal = Depends(requerir_roles("auditor"))) -> dict[str, Any]:
        return await servicio.reproducir(str(ruta_id), p, ip_cliente(request))

    return r
