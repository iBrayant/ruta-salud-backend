"""Composición del servicio de IA."""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ruta_comun.auditoria import AuditoriaNoDisponible, ClienteAuditoria
from ruta_comun.logs import configurar_logs
from ruta_comun.oauth_cliente import ClienteCredenciales
from ruta_comun.seguridad import ValidadorJWT, construir_dependencias

from .application.casos_uso import IANoDisponible, LimiteExcedido, RutaNoAccesible, ServicioIA
from .infrastructure.limites_redis import LimitesRedis
from .infrastructure.openai_cliente import ModeloOpenAI
from .infrastructure.rutas_cliente import ClienteRutas
from .presentation.api import construir_router

log = configurar_logs("ia")
E = os.environ

llm = ModeloOpenAI(
    api_key=E.get("OPENAI_API_KEY") or None,
    modelo=E.get("OPENAI_MODEL", "gpt-4.1-mini"),
    precio_entrada_1m=float(E.get("OPENAI_PRECIO_ENTRADA_1M", "0.40")),
    precio_salida_1m=float(E.get("OPENAI_PRECIO_SALIDA_1M", "1.60")),
)
limites = LimitesRedis(E["REDIS_URL"], int(E.get("IA_CHATS_POR_HORA", "30")), int(E.get("IA_TOKENS_POR_DIA", "300000")))
credenciales = ClienteCredenciales(E["KEYCLOAK_TOKEN_URL"], E["OAUTH_CLIENT_ID"], E["OAUTH_CLIENT_SECRET"])
servicio = ServicioIA(llm, limites, ClienteRutas(E["RUTAS_URL"]), ClienteAuditoria(E["AUDITORIA_URL"], credenciales))
_, requerir_roles = construir_dependencias(
    ValidadorJWT(E["KEYCLOAK_JWKS_URL"], E["KEYCLOAK_ISSUER"], E.get("API_AUDIENCE", "ruta-salud-api")))

app = FastAPI(
    title="Ruta Salud Rural · Servicio de IA",
    version="1.0.0",
    description="Explicación de rutas con revisión ética y asistente de consulta. La IA explica; no decide.",
    docs_url="/api/ia/docs",
    openapi_url="/api/ia/openapi.json",
    redoc_url=None,
)
app.include_router(construir_router(servicio, requerir_roles))
log.info("Servicio de IA listo (modelo=%s, disponible=%s)", llm.modelo, llm.disponible)


@app.exception_handler(IANoDisponible)
async def _ia(_: Request, e: IANoDisponible) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": f"Asistente no disponible: {e}"})


@app.exception_handler(LimiteExcedido)
async def _limite(_: Request, e: LimiteExcedido) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(e)})


@app.exception_handler(RutaNoAccesible)
async def _ruta(_: Request, __: RutaNoAccesible) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Ruta no encontrada o sin permiso"})


@app.exception_handler(AuditoriaNoDisponible)
async def _aud(_: Request, __: AuditoriaNoDisponible) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Auditoría no disponible: la operación no se realizó"})


@app.get("/health", include_in_schema=False)
async def salud() -> dict:
    return {"servicio": "ia", "redis": await limites.ping(), "modelo": llm.modelo, "ia_configurada": llm.disponible}
