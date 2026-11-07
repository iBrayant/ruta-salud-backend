"""Límites de uso en Redis: consultas por usuario por hora y tokens por día (cuida los 5 USD)."""
from __future__ import annotations

import logging
from datetime import datetime

import redis.asyncio as redis

log = logging.getLogger("ia.limites")


class LimitesRedis:
    def __init__(self, url: str, chats_por_hora: int, tokens_por_dia: int) -> None:
        self._r = redis.from_url(url, decode_responses=True)
        self._chats = chats_por_hora
        self._tokens = tokens_por_dia

    async def permitir_chat(self, usuario: str) -> bool:
        clave = f"ia:chat:{usuario}:{datetime.now():%Y%m%d%H}"
        try:
            n = await self._r.incr(clave)
            if n == 1:
                await self._r.expire(clave, 3700)
            return n <= self._chats
        except redis.RedisError as e:
            log.warning("Redis no disponible; se niega la consulta por seguridad: %s", e)
            return False

    async def presupuesto_disponible(self) -> bool:
        try:
            usados = int(await self._r.get(f"ia:tokens:{datetime.now():%Y%m%d}") or 0)
            return usados < self._tokens
        except redis.RedisError:
            return False

    async def consumir_tokens(self, n: int) -> None:
        clave = f"ia:tokens:{datetime.now():%Y%m%d}"
        try:
            await self._r.incrby(clave, n)
            await self._r.expire(clave, 2 * 86400)
        except redis.RedisError as e:
            log.warning("No se pudo contabilizar tokens: %s", e)

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except redis.RedisError:
            return False
