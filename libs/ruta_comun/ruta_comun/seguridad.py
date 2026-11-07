"""Validación de tokens OAuth 2.0 / OIDC emitidos por Keycloak.

Cada microservicio valida por sí mismo (zero trust entre servicios):
firma RS256 contra el JWKS del realm, emisor (iss), audiencia (aud) y expiración.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

ROLES_USUARIO = {"coordinador", "equipo_salud", "auditor"}
ROL_SERVICIO = "servicio_interno"


@dataclass(frozen=True)
class Principal:
    sub: str
    usuario: str
    roles: frozenset[str]
    cliente: str          # azp: cliente OAuth que pidió el token
    es_servicio: bool     # True si es una cuenta de servicio (client credentials)
    token: str = field(repr=False)

    def tiene(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


class ValidadorJWT:
    def __init__(self, jwks_url: str, emisor: str, audiencia: str) -> None:
        self._jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=5)
        self._emisor = emisor
        self._audiencia = audiencia

    def validar(self, token: str) -> Principal:
        try:
            clave = self._jwks.get_signing_key_from_jwt(token).key
            c = jwt.decode(
                token,
                clave,
                algorithms=["RS256"],
                audience=self._audiencia,
                issuer=self._emisor,
                leeway=10,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWKClientError as e:  # Keycloak no disponible
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Servidor de autorización no disponible") from e
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado", headers={"WWW-Authenticate": "Bearer"}
            ) from e
        roles = frozenset(c.get("realm_access", {}).get("roles", []))
        usuario = c.get("preferred_username", c["sub"])
        return Principal(
            sub=c["sub"],
            usuario=usuario,
            roles=roles,
            cliente=c.get("azp", ""),
            es_servicio=usuario.startswith("service-account-"),
            token=token,
        )


_bearer = HTTPBearer(auto_error=False)


def construir_dependencias(validador: ValidadorJWT) -> tuple[Callable, Callable]:
    """Devuelve (principal_actual, requerir_roles) ligados a un validador."""

    def principal_actual(
        request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)
    ) -> Principal:
        if cred is None or cred.scheme.lower() != "bearer":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token Bearer", headers={"WWW-Authenticate": "Bearer"})
        p = validador.validar(cred.credentials)
        request.state.principal = p
        return p

    def requerir_roles(*roles: str) -> Callable:
        def _dep(p: Principal = Depends(principal_actual)) -> Principal:
            if not p.tiene(*roles):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta acción")
            return p

        return _dep

    return principal_actual, requerir_roles


def ip_cliente(request: Request) -> str:
    """IP real detrás de Nginx (X-Real-IP lo fija el gateway, no el cliente)."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "desconocida")
