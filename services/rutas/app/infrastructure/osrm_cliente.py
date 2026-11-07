"""Adaptador ProveedorDistancias: OSRM (OpenStreetMap) con respaldo Haversine.

Si OSRM falla, se usa la distancia en línea recta × 1.4 (factor de tortuosidad
para vías de montaña) a 30 km/h. La fuente usada queda en la matriz y en auditoría.
"""
from __future__ import annotations

import hashlib
import logging
import math

import httpx

from ..domain.entities import Hospital, MatrizViaje, Vereda
from .cache_redis import CacheRedis

log = logging.getLogger("rutas.osrm")
FACTOR_TORTUOSIDAD = 1.4
VELOCIDAD_RESPALDO_KMH = 30.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


class ProveedorOSRM:
    def __init__(self, base_url: str, cache: CacheRedis, ttl_s: int = 7 * 24 * 3600) -> None:
        self._url = base_url.rstrip("/")
        self._cache = cache
        self._ttl = ttl_s

    async def matriz(self, hospital: Hospital, veredas: list[Vereda]) -> MatrizViaje:
        ids = [hospital.id] + [v.id for v in veredas]
        puntos = [(hospital.lat, hospital.lon)] + [(v.lat, v.lon) for v in veredas]
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in puntos)
        clave = "osrm:" + hashlib.sha256(coords.encode()).hexdigest()
        if (c := await self._cache.obtener(clave)) is not None:
            return MatrizViaje(ids=ids, km=c["km"], minutos=c["minutos"], fuente="osrm")
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "ruta-salud-fusa/1.0"}) as http:
                r = await http.get(f"{self._url}/table/v1/driving/{coords}", params={"annotations": "distance,duration"})
                r.raise_for_status()
                d = r.json()
            if d.get("code") != "Ok" or any(x is None for fila in d["distances"] for x in fila):
                raise ValueError(f"Respuesta OSRM incompleta: {d.get('code')}")
            km = [[round(x / 1000, 3) for x in fila] for fila in d["distances"]]
            minutos = [[round(x / 60, 2) for x in fila] for fila in d["durations"]]
            await self._cache.guardar(clave, {"km": km, "minutos": minutos}, self._ttl)
            return MatrizViaje(ids=ids, km=km, minutos=minutos, fuente="osrm")
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("OSRM no disponible, usando respaldo Haversine: %s", e)
            km = [[round(haversine_km(*a, *b) * FACTOR_TORTUOSIDAD, 3) for b in puntos] for a in puntos]
            minutos = [[round(x / VELOCIDAD_RESPALDO_KMH * 60, 2) for x in fila] for fila in km]
            return MatrizViaje(ids=ids, km=km, minutos=minutos, fuente="haversine_x1.4")
