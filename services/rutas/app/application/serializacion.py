"""Conversión entre entidades del dominio y diccionarios (snapshot reproducible)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from typing import Any

from ..domain.entities import ClimaVereda, MatrizViaje, ParametrosJornada, ResultadoRuta, Vereda


def huella(obj: Any) -> str:
    """SHA-256 de la representación JSON canónica."""
    texto = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(texto.encode()).hexdigest()


def parametros_a_dict(p: ParametrosJornada) -> dict[str, Any]:
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat()
    return d


def parametros_desde_dict(d: dict[str, Any]) -> ParametrosJornada:
    return ParametrosJornada(**{**d, "fecha": date.fromisoformat(d["fecha"])})


def snapshot(
    veredas: list[Vereda], matriz: MatrizViaje, dias: dict[str, int | None], clima: dict[str, ClimaVereda] | None,
    version_datos: str,
) -> dict[str, Any]:
    """Todas las entradas del algoritmo: con esto la ruta se puede volver a calcular idéntica."""
    return {
        "version_datos": version_datos,
        "veredas": [asdict(v) for v in veredas],
        "matriz": asdict(matriz),
        "dias_sin_visita": dias,
        "clima": {k: asdict(c) for k, c in clima.items()} if clima else None,
    }


def desde_snapshot(s: dict[str, Any]):
    veredas = [Vereda(**v) for v in s["veredas"]]
    matriz = MatrizViaje(**s["matriz"])
    clima = {k: ClimaVereda(**c) for k, c in s["clima"].items()} if s.get("clima") else None
    return veredas, matriz, s["dias_sin_visita"], clima


def resultado_a_dict(r: ResultadoRuta) -> dict[str, Any]:
    d = asdict(r)
    d["orden"] = [p["vereda_id"] for p in d["paradas"]]
    return d
