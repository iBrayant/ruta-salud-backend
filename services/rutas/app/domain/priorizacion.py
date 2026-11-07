"""Fase 1: heurístico de priorización.

    P_i = α·V_i + (1 − α)·A_i + γ·E_i

V_i  vulnerabilidad (necesidad de atención) del territorio, 0..1
A_i  accesibilidad = 1 − t_hospital_i / t_max − 0.5·factor_lluvia_i
     (factor = 1 vía terciaria, 0.5 mixta, 0 primer orden, solo con lluvia fuerte)
E_i  equidad = min(días sin visita, 30) / 30; nunca visitada → 1

Regla de descanso: una vereda visitada hace menos de `dias_minimos_entre_visitas`
no es elegible (evita que las veredas cercanas acaparen todas las jornadas).
"""
from __future__ import annotations

from .entities import ClimaVereda, MatrizViaje, ParametrosJornada, Puntaje, Vereda

# Qué tanto afecta la lluvia según el tipo de vía (0 = nada, 1 = máximo)
FACTOR_VIA = {"terciaria": 1.0, "mixta": 0.5, "primer_orden": 0.0}
UMBRAL_PROB_LLUVIA = 60.0     # %
UMBRAL_MM_LLUVIA = 5.0        # mm en horas de jornada
PENALIZACION_ACCESO = 0.5     # reduce A_i hasta en 50 %
RECARGO_TIEMPO_LLUVIA = 0.3   # aumenta tiempos de viaje hasta en 30 %
DIAS_EQUIDAD_MAX = 30


def es_lluvia_fuerte(c: ClimaVereda | None) -> bool:
    return c is not None and (c.prob_lluvia_max >= UMBRAL_PROB_LLUVIA or c.precipitacion_mm >= UMBRAL_MM_LLUVIA)


def factor_lluvia(v: Vereda, clima: dict[str, ClimaVereda] | None, p: ParametrosJornada) -> float:
    """0..1: cuánto afecta la lluvia el acceso a esta vereda hoy."""
    if not p.considerar_lluvia or not clima:
        return 0.0
    return FACTOR_VIA.get(v.tipo_via, 1.0) if es_lluvia_fuerte(clima.get(v.id)) else 0.0


def equidad(dias_sin_visita: int | None) -> float:
    if dias_sin_visita is None:
        return 1.0
    return min(max(dias_sin_visita, 0), DIAS_EQUIDAD_MAX) / DIAS_EQUIDAD_MAX


def puntuar(
    veredas: list[Vereda],
    matriz: MatrizViaje,
    dias_sin_visita: dict[str, int | None],
    clima: dict[str, ClimaVereda] | None,
    p: ParametrosJornada,
) -> list[Puntaje]:
    """Devuelve el ranking ordenado de mayor a menor prioridad (desempate estable por id)."""
    t_hosp = {v.id: matriz.minutos[0][matriz.idx(v.id)] for v in veredas}
    t_max = max(t_hosp.values()) or 1.0
    salida: list[Puntaje] = []
    for v in veredas:
        f = factor_lluvia(v, clima, p)
        # Penalización ABSOLUTA (se resta): todas las veredas con vía destapada pierden lo mismo
        # bajo lluvia fuerte. Multiplicar favorecía a la más lejana (0 × factor = 0).
        acceso = (1.0 - t_hosp[v.id] / t_max) - PENALIZACION_ACCESO * f
        dias = dias_sin_visita.get(v.id)
        e = equidad(dias)
        prioridad = p.alpha * v.vulnerabilidad + (1 - p.alpha) * acceso + p.gamma * e
        salida.append(
            Puntaje(
                vereda_id=v.id,
                prioridad=round(prioridad, 4),
                vulnerabilidad=round(v.vulnerabilidad, 4),
                accesibilidad=round(acceso, 4),
                equidad=round(e, 4),
                dias_sin_visita=dias,
                lluvia_fuerte=es_lluvia_fuerte(clima.get(v.id)) if clima else False,
                penalizada_por_lluvia=f > 0,
                en_descanso=dias is not None and dias < p.dias_minimos_entre_visitas,
            )
        )
    return sorted(salida, key=lambda s: (-s.prioridad, s.vereda_id))
