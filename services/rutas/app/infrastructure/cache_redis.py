"""Caché en Redis para respuestas de APIs externas (OSRM, Open-Meteo)."""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

log = logging.getLogger("rutas.cache")


class CacheRedis:
    def __init__(self, url: str, prefijo: str = "rutas:") -> None:
        self._r = redis.from_url(url, decode_responses=True)
        self._p = prefijo

    async def obtener(self, clave: str) -> Any | None:
        try:
            v = await self._r.get(self._p + clave)
            return json.loads(v) if v else None
        except redis.RedisError as e:  # la caché nunca debe tumbar el servicio
            log.warning("Redis no disponible al leer: %s", e)
            return None

    async def guardar(self, clave: str, valor: Any, ttl_s: int) -> None:
        try:
            await self._r.set(self._p + clave, json.dumps(valor), ex=ttl_s)
        except redis.RedisError as e:
            log.warning("Redis no disponible al escribir: %s", e)

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except redis.RedisError:
            return False
