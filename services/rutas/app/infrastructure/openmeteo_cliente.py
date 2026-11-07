"""Adaptador ProveedorClima: pronóstico horario de lluvia con Open-Meteo (gratuito, sin API key)."""
from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta

import httpx

from ..domain.entities import ClimaVereda, Vereda
from .cache_redis import CacheRedis

log = logging.getLogger("rutas.clima")
DIAS_PRONOSTICO = 15


class ProveedorOpenMeteo:
    def __init__(self, base_url: str, cache: CacheRedis, ttl_s: int = 3600) -> None:
        self._url = base_url.rstrip("/")
        self._cache = cache
        self._ttl = ttl_s

    async def pronostico(self, veredas: list[Vereda], fecha: date, hora_inicio: int, hora_fin: int
                         ) -> dict[str, ClimaVereda] | None:
        if not (date.today() - timedelta(days=1) <= fecha <= date.today() + timedelta(days=DIAS_PRONOSTICO)):
            return None  # fuera del horizonte de pronóstico
        lats = ",".join(f"{v.lat:.4f}" for v in veredas)
        lons = ",".join(f"{v.lon:.4f}" for v in veredas)
        clave = "clima:v2:" + hashlib.sha256(f"{lats}|{lons}|{fecha}|{hora_inicio}|{hora_fin}".encode()).hexdigest()
        if (c := await self._cache.obtener(clave)) is not None:
            return {k: ClimaVereda(**x) for k, x in c.items()}
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"{self._url}/v1/forecast",
                    params={
                        "latitude": lats,
                        "longitude": lons,
                        "hourly": "precipitation_probability,precipitation",
                        "start_date": fecha.isoformat(),
                        "end_date": fecha.isoformat(),
                        "timezone": "America/Bogota",
                    },
                )
                r.raise_for_status()
                datos = r.json()
            datos = datos if isinstance(datos, list) else [datos]
            salida: dict[str, ClimaVereda] = {}
            for v, d in zip(veredas, datos, strict=True):
                horas = d["hourly"]
                idx = [i for i, t in enumerate(horas["time"]) if hora_inicio <= int(t[11:13]) <= hora_fin]
                prob = [horas["precipitation_probability"][i] or 0 for i in idx]
                mm = [horas["precipitation"][i] or 0 for i in idx]
                por_hora = {horas["time"][i][11:13]: {"prob": float(p), "mm": float(m)} for i, p, m in zip(idx, prob, mm)}
                salida[v.id] = ClimaVereda(prob_lluvia_max=float(max(prob, default=0)), precipitacion_mm=round(sum(mm), 2),
                                           por_hora=por_hora)
            await self._cache.guardar(clave, {k: vars(c) for k, c in salida.items()}, self._ttl)
            return salida
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("Open-Meteo no disponible, se planifica sin clima: %s", e)
            return None
