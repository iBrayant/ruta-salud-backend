"""Adaptador RepositorioRutas sobre PostgreSQL (asyncpg).

El usuario de base de datos del servicio solo puede INSERT/SELECT y actualizar las
columnas de estado y explicación: no puede modificar parámetros ni resultados.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import asyncpg

_COLS = ("id, codigo, fecha_jornada, creado_en, creado_por, estado, parametros, snapshot, huella_entradas, "
         "resultado, huella_resultado, version_datos, explicacion, ejecutada_por, ejecutada_en")


async def _init_conexion(con: asyncpg.Connection) -> None:
    await con.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class RepositorioRutasPG:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def iniciar(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5, init=_init_conexion)

    async def cerrar(self) -> None:
        if self._pool:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        assert self._pool is not None, "Repositorio no iniciado"
        return self._pool

    async def siguiente_codigo(self, fecha: date) -> str:
        n = await self.pool.fetchval("SELECT count(*) FROM rutas WHERE fecha_jornada = $1", fecha)
        return f"R-{fecha:%Y%m%d}-{n + 1:02d}"

    async def guardar(self, r: dict[str, Any]) -> None:
        await self.pool.execute(
            """INSERT INTO rutas (id, codigo, fecha_jornada, creado_en, creado_por, estado, parametros, snapshot,
                                  huella_entradas, resultado, huella_resultado, version_datos)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
            r["id"], r["codigo"], r["fecha_jornada"], r["creado_en"], r["creado_por"], r["estado"], r["parametros"],
            r["snapshot"], r["huella_entradas"], r["resultado"], r["huella_resultado"], r["version_datos"],
        )

    async def obtener(self, ruta_id: str) -> dict[str, Any] | None:
        fila = await self.pool.fetchrow(f"SELECT {_COLS} FROM rutas WHERE id = $1::uuid", ruta_id)
        return _a_dict(fila) if fila else None

    async def listar(self, limite: int, desplazamiento: int) -> list[dict[str, Any]]:
        filas = await self.pool.fetch(
            """SELECT id, codigo, fecha_jornada, creado_en, creado_por, estado,
                      resultado->'orden' AS orden, resultado->'distancia_total_km' AS distancia_total_km,
                      resultado->'hora_regreso' AS hora_regreso
               FROM rutas ORDER BY creado_en DESC LIMIT $1 OFFSET $2""",
            limite, desplazamiento,
        )
        return [_a_dict(f) for f in filas]

    async def ultima_visita(self, antes_de: date) -> dict[str, date]:
        filas = await self.pool.fetch(
            """SELECT v.id, max(r.fecha_jornada) AS fecha
               FROM rutas r, jsonb_array_elements_text(r.resultado->'orden') AS v(id)
               WHERE r.estado = 'ejecutada' AND r.fecha_jornada < $1
               GROUP BY v.id""",
            antes_de,
        )
        return {f["id"]: f["fecha"] for f in filas}

    async def marcar_ejecutada(self, ruta_id: str, usuario: str) -> dict[str, Any] | None:
        fila = await self.pool.fetchrow(
            f"""UPDATE rutas SET estado = 'ejecutada', ejecutada_por = $2, ejecutada_en = $3
                WHERE id = $1::uuid AND estado = 'propuesta' RETURNING {_COLS}""",
            ruta_id, usuario, datetime.now(timezone.utc),
        )
        return _a_dict(fila) if fila else None

    async def guardar_explicacion(self, ruta_id: str, explicacion: dict[str, Any]) -> None:
        await self.pool.execute("UPDATE rutas SET explicacion = $2 WHERE id = $1::uuid", ruta_id, explicacion)

    async def ping(self) -> bool:
        try:
            return await self.pool.fetchval("SELECT 1") == 1
        except Exception:  # noqa: BLE001
            return False


def _a_dict(fila: asyncpg.Record) -> dict[str, Any]:
    d = dict(fila)
    if "id" in d:
        d["id"] = str(d["id"])
    return d
