"""Configuración por variables de entorno (12-factor). Sin secretos en el código."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _req(nombre: str) -> str:
    v = os.environ.get(nombre)
    if not v:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return v


@dataclass(frozen=True)
class Config:
    database_url: str
    redis_url: str
    keycloak_jwks_url: str
    keycloak_emisor: str
    keycloak_token_url: str
    audiencia: str
    client_id: str
    client_secret: str
    auditoria_url: str
    ia_url: str
    osrm_url: str
    openmeteo_url: str
    ruta_veredas: str
    cors_origenes: list[str]

    @classmethod
    def desde_entorno(cls) -> "Config":
        return cls(
            database_url=_req("DATABASE_URL"),
            redis_url=_req("REDIS_URL"),
            keycloak_jwks_url=_req("KEYCLOAK_JWKS_URL"),
            keycloak_emisor=_req("KEYCLOAK_ISSUER"),
            keycloak_token_url=_req("KEYCLOAK_TOKEN_URL"),
            audiencia=os.environ.get("API_AUDIENCE", "ruta-salud-api"),
            client_id=_req("OAUTH_CLIENT_ID"),
            client_secret=_req("OAUTH_CLIENT_SECRET"),
            auditoria_url=_req("AUDITORIA_URL"),
            ia_url=_req("IA_URL"),
            osrm_url=os.environ.get("OSRM_URL", "https://router.project-osrm.org"),
            openmeteo_url=os.environ.get("OPENMETEO_URL", "https://api.open-meteo.com"),
            ruta_veredas=os.environ.get("VEREDAS_JSON", "/data/veredas.json"),
            cors_origenes=[o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o],
        )
