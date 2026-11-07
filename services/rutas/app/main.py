"""Composición: conecta los adaptadores con los casos de uso y expone la API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ruta_comun.auditoria import AuditoriaNoDisponible, ClienteAuditoria
from ruta_comun.logs import configurar_logs
from ruta_comun.oauth_cliente import ClienteCredenciales
from ruta_comun.seguridad import ValidadorJWT, construir_dependencias

from .application.casos_uso import RutaNoEncontrada, ServicioRutas
from .config import Config
from .infrastructure.cache_redis import CacheRedis
from .infrastructure.ia_cliente import ClienteIA
from .infrastructure.openmeteo_cliente import ProveedorOpenMeteo
from .infrastructure.osrm_cliente import ProveedorOSRM
from .infrastructure.repositorio_rutas_pg import RepositorioRutasPG
from .infrastructure.repositorio_veredas import RepositorioVeredasJSON
from .presentation.api import construir_router

log = configurar_logs("rutas")
cfg = Config.desde_entorno()

cache = CacheRedis(cfg.redis_url)
repo_rutas = RepositorioRutasPG(cfg.database_url)
credenciales = ClienteCredenciales(cfg.keycloak_token_url, cfg.client_id, cfg.client_secret)
servicio = ServicioRutas(
    veredas=RepositorioVeredasJSON(cfg.ruta_veredas),
    distancias=ProveedorOSRM(cfg.osrm_url, cache),
    clima=ProveedorOpenMeteo(cfg.openmeteo_url, cache),
    rutas=repo_rutas,
    explicacion=ClienteIA(cfg.ia_url, credenciales),
    auditoria=ClienteAuditoria(cfg.auditoria_url, credenciales),
)
_, requerir_roles = construir_dependencias(ValidadorJWT(cfg.keycloak_jwks_url, cfg.keycloak_emisor, cfg.audiencia))


@asynccontextmanager
async def ciclo_vida(_: FastAPI):
    await repo_rutas.iniciar()
    log.info("Servicio de rutas listo (%s)", servicio.veredas.version())
    yield
    await repo_rutas.cerrar()


app = FastAPI(
    title="Ruta Salud Rural · Servicio de rutas",
    version="1.0.0",
    description="Priorización y optimización de visitas domiciliarias en veredas de Fusagasugá.",
    docs_url="/api/rutas/docs",
    openapi_url="/api/rutas/openapi.json",
    redoc_url=None,
    lifespan=ciclo_vida,
)
if cfg.cors_origenes:
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origenes, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])
app.include_router(construir_router(servicio, requerir_roles))


@app.exception_handler(RutaNoEncontrada)
async def _no_encontrada(_: Request, __: RutaNoEncontrada) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Ruta no encontrada"})


@app.exception_handler(AuditoriaNoDisponible)
async def _sin_auditoria(_: Request, e: AuditoriaNoDisponible) -> JSONResponse:
    log.error("Operación bloqueada por falta de auditoría: %s", e)
    return JSONResponse(status_code=503, content={"detail": "Auditoría no disponible: la operación no se realizó"})


@app.get("/health", include_in_schema=False)
async def salud() -> dict:
    return {"servicio": "rutas", "postgres": await repo_rutas.ping(), "redis": await cache.ping()}
