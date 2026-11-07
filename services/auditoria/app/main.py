"""Composición del servicio de auditoría."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ruta_comun.logs import configurar_logs
from ruta_comun.seguridad import ValidadorJWT, construir_dependencias

from .application.casos_uso import ServicioAuditoria
from .infrastructure.repositorio_pg import RepositorioEventosPG
from .presentation.api import construir_router

log = configurar_logs("auditoria")
repo = RepositorioEventosPG(os.environ["DATABASE_URL"])
servicio = ServicioAuditoria(repo)
_, requerir_roles = construir_dependencias(
    ValidadorJWT(os.environ["KEYCLOAK_JWKS_URL"], os.environ["KEYCLOAK_ISSUER"],
                 os.environ.get("API_AUDIENCE", "ruta-salud-api"))
)


@asynccontextmanager
async def ciclo_vida(_: FastAPI):
    await repo.iniciar()
    log.info("Servicio de auditoría listo")
    yield
    await repo.cerrar()


app = FastAPI(
    title="Ruta Salud Rural · Servicio de auditoría",
    version="1.0.0",
    description="Registro append-only con cadena de hashes SHA-256.",
    docs_url="/api/auditoria/docs",
    openapi_url="/api/auditoria/openapi.json",
    redoc_url=None,
    lifespan=ciclo_vida,
)
app.include_router(construir_router(servicio, requerir_roles))


@app.get("/health", include_in_schema=False)
async def salud() -> dict:
    return {"servicio": "auditoria", "postgres": await repo.ping()}
