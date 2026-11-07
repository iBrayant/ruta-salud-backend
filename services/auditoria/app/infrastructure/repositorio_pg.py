"""Repositorio de eventos en PostgreSQL.

- El registro canónico (texto) es la fuente de verdad; las columnas jsonb son para consultar.
- Un advisory lock serializa las inserciones para que la cadena no se bifurque.
- Triggers en la base impiden UPDATE/DELETE/TRUNCATE (ver infra/postgres).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncIterator, Callable

import asyncpg

from ..domain.cadena import GENESIS

LOCK_CADENA = 774411


async def _init(con: asyncpg.Connection) -> None:
    await con.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class RepositorioEventosPG:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def iniciar(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5, init=_init)

    async def cerrar(self) -> None:
        if self._pool:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        assert self._pool is not None
        return self._pool

    async def insertar_encadenado(self, construir: Callable[[int, str], tuple[str, str]], evento: dict[str, Any]
                                  ) -> dict[str, Any]:
        async with self.pool.acquire() as con, con.transaction():
            await con.execute("SELECT pg_advisory_xact_lock($1)", LOCK_CADENA)
            ultimo = await con.fetchrow("SELECT seq, hash FROM eventos_auditoria ORDER BY seq DESC LIMIT 1")
            seq = (ultimo["seq"] + 1) if ultimo else 1
            reg, h = construir(seq, ultimo["hash"] if ultimo else GENESIS)
            d = json.loads(reg)
            await con.execute(
                """INSERT INTO eventos_auditoria (seq, ts, accion, actor, actor_tipo, roles, recurso, detalle, ip,
                                                  servicio_origen, hash_anterior, registro_canonico, hash)
                   VALUES ($1, $2::timestamptz, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
                seq, datetime.fromisoformat(d["ts"]), d["accion"], d["actor"], d["actor_tipo"], d["roles"],
                d["recurso"], d["detalle"], d["ip"], d["servicio_origen"], d["hash_anterior"], reg, h,
            )
            return {"seq": seq, "hash": h, "hash_anterior": d["hash_anterior"], "ts": d["ts"]}

    async def listar(self, accion, recurso, actor, desde, hasta, limite, desplazamiento) -> list[dict[str, Any]]:
        filas = await self.pool.fetch(
            """SELECT seq, ts, accion, actor, actor_tipo, roles, recurso, ip, servicio_origen, hash, hash_anterior
               FROM eventos_auditoria
               WHERE ($1::text IS NULL OR accion = $1) AND ($2::text IS NULL OR recurso = $2)
                 AND ($3::text IS NULL OR actor = $3)
                 AND ($4::timestamptz IS NULL OR ts >= $4) AND ($5::timestamptz IS NULL OR ts <= $5)
               ORDER BY seq DESC LIMIT $6 OFFSET $7""",
            accion, recurso, actor, desde, hasta, limite, desplazamiento,
        )
        return [dict(f) for f in filas]

    async def obtener(self, seq: int) -> dict[str, Any] | None:
        f = await self.pool.fetchrow("SELECT registro_canonico, hash FROM eventos_auditoria WHERE seq = $1", seq)
        return {**json.loads(f["registro_canonico"]), "hash": f["hash"]} if f else None

    async def eslabones(self) -> AsyncIterator[tuple[int, str, str]]:
        async with self.pool.acquire() as con, con.transaction():
            async for f in con.cursor("SELECT seq, registro_canonico, hash FROM eventos_auditoria ORDER BY seq"):
                yield f["seq"], f["registro_canonico"], f["hash"]

    async def ping(self) -> bool:
        try:
            return await self.pool.fetchval("SELECT 1") == 1
        except Exception:  # noqa: BLE001
            return False
