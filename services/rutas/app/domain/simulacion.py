"""Simulación de N jornadas consecutivas y métricas de impacto y equidad.

Responde a la pregunta del jurado: ¿el algoritmo deja comunidades atrás?
Supone que cada ruta generada se ejecuta (la vereda queda visitada ese día).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from .entities import ClimaVereda, MatrizViaje, ParametrosJornada, Vereda
from .planificador import planificar


def simular(
    veredas: list[Vereda],
    matriz: MatrizViaje,
    p: ParametrosJornada,
    n_jornadas: int,
    ultima_visita: dict[str, date] | None = None,
    clima: dict[str, ClimaVereda] | None = None,
) -> dict:
    ultima = dict(ultima_visita or {})
    visitas = {v.id: 0 for v in veredas}
    esperas: dict[str, list[int]] = {v.id: [] for v in veredas}
    jornadas = []
    for k in range(n_jornadas):
        fecha = p.fecha + timedelta(days=k)
        dias = {v.id: ((fecha - ultima[v.id]).days if v.id in ultima else None) for v in veredas}
        res = planificar(veredas, matriz, dias, clima if k == 0 else None, replace(p, fecha=fecha))
        for par in res.paradas:
            if par.vereda_id in ultima:
                esperas[par.vereda_id].append((fecha - ultima[par.vereda_id]).days)
            ultima[par.vereda_id] = fecha
            visitas[par.vereda_id] += 1
        jornadas.append(
            {
                "fecha": fecha.isoformat(),
                "veredas": [par.nombre for par in res.paradas],
                "distancia_km": res.distancia_total_km,
                "hora_regreso": res.hora_regreso,
            }
        )

    fin = p.fecha + timedelta(days=n_jornadas - 1)
    nombre = {v.id: v.nombre for v in veredas}
    por_corr: dict[str, dict] = {}
    for v in veredas:
        c = por_corr.setdefault(v.corregimiento, {"veredas": 0, "visitas": 0})
        c["veredas"] += 1
        c["visitas"] += visitas[v.id]
    nunca = [nombre[i] for i, n in visitas.items() if n == 0]
    # Espera máxima: mayor intervalo entre visitas, o desde el inicio si nunca fue visitada
    espera_max = {
        i: max(esperas[i] + ([(fin - p.fecha).days + 1] if visitas[i] == 0 else [])) if (esperas[i] or visitas[i] == 0) else None
        for i in visitas
    }
    total_visitas = sum(visitas.values())
    # Equidad entre veredas ponderada por necesidad: visitas esperadas ∝ vulnerabilidad
    suma_v = sum(v.vulnerabilidad for v in veredas) or 1
    desviacion = {
        nombre[v.id]: round(visitas[v.id] - total_visitas * v.vulnerabilidad / suma_v, 2) for v in veredas
    }
    return {
        "jornadas": jornadas,
        "metricas": {
            "n_jornadas": n_jornadas,
            "cobertura_pct": round(100 * (len(veredas) - len(nunca)) / len(veredas), 1),
            "veredas_nunca_visitadas": nunca,
            "visitas_por_vereda": {nombre[i]: n for i, n in visitas.items()},
            "espera_maxima_dias": {nombre[i]: d for i, d in espera_max.items() if d is not None},
            "visitas_por_corregimiento": por_corr,
            "desviacion_vs_necesidad": desviacion,
            "distancia_total_km": round(sum(j["distancia_km"] for j in jornadas), 2),
        },
        "supuestos": [
            "Cada ruta generada se ejecuta completa el día planificado.",
            "El pronóstico de lluvia solo se aplica a la primera jornada (no hay pronóstico confiable a largo plazo).",
            "desviacion_vs_necesidad > 0: más visitas que las proporcionales a su vulnerabilidad; < 0: menos.",
        ],
    }
