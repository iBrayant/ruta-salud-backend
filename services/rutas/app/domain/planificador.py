"""Une las dos fases: selecciona las veredas que caben en la jornada y las ordena.

Es una función pura y determinista: con las mismas entradas siempre da la misma
ruta. Eso es lo que permite *reproducir* una ruta pasada desde la auditoría.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import optimizacion as opt
from .entities import ClimaVereda, MatrizViaje, Parada, ParametrosJornada, Puntaje, ResultadoRuta, Vereda
from .priorizacion import RECARGO_TIEMPO_LLUVIA, factor_lluvia, puntuar


def matriz_costos(
    veredas: list[Vereda], matriz: MatrizViaje, clima: dict[str, ClimaVereda] | None, p: ParametrosJornada
) -> list[list[float]]:
    """Minutos de viaje, con recargo si el tramo toca una vía destapada bajo lluvia fuerte."""
    f = [0.0] * len(matriz.ids)
    por_id = {v.id: v for v in veredas}
    for i, id_ in enumerate(matriz.ids):
        if id_ in por_id:
            f[i] = factor_lluvia(por_id[id_], clima, p)
    n = len(matriz.ids)
    return [
        [matriz.minutos[i][j] * (1 + RECARGO_TIEMPO_LLUVIA * max(f[i], f[j])) for j in range(n)] for i in range(n)
    ]


def _hhmm(base: datetime, minutos: float) -> str:
    return (base + timedelta(minutes=round(minutos))).strftime("%H:%M")


def planificar(
    veredas: list[Vereda],
    matriz: MatrizViaje,
    dias_sin_visita: dict[str, int | None],
    clima: dict[str, ClimaVereda] | None,
    p: ParametrosJornada,
) -> ResultadoRuta:
    ranking = puntuar(veredas, matriz, dias_sin_visita, clima, p)
    m = matriz_costos(veredas, matriz, clima, p)

    # Selección voraz respetando la duración de la jornada
    elegidas: list[int] = []
    descartadas: list[dict] = []
    for s in ranking:
        if len(elegidas) == p.n_veredas:
            break
        if s.en_descanso:
            descartadas.append(
                {
                    "vereda_id": s.vereda_id,
                    "prioridad": s.prioridad,
                    "motivo": f"En periodo de descanso: visitada hace {s.dias_sin_visita} días "
                    f"(mínimo {p.dias_minimos_entre_visitas})",
                }
            )
            continue
        prueba = elegidas + [matriz.idx(s.vereda_id)]
        tour = opt.heuristico(prueba, m)
        total = opt.costo_tour(tour, m) + len(prueba) * p.minutos_atencion
        if total <= p.minutos_jornada:
            elegidas = prueba
        else:
            descartadas.append(
                {
                    "vereda_id": s.vereda_id,
                    "prioridad": s.prioridad,
                    "motivo": f"No cabe en la jornada: requeriría {round(total)} de {p.minutos_jornada} min",
                }
            )

    tour = opt.heuristico(elegidas, m)
    exacto = opt.optimo_exacto(elegidas, m)
    c_h, c_o = opt.costo_tour(tour, m), opt.costo_tour(exacto, m)

    por_id = {v.id: v for v in veredas}
    puntaje = {s.vereda_id: s for s in ranking}
    inicio = datetime.strptime(p.hora_inicio, "%H:%M")
    reloj, km_total, min_viaje = 0.0, 0.0, 0.0
    paradas: list[Parada] = []
    previo = 0
    for pos, nodo in enumerate(tour, start=1):
        vid = matriz.ids[nodo]
        tramo_min, tramo_km = m[previo][nodo], matriz.km[previo][nodo]
        reloj += tramo_min
        llegada = _hhmm(inicio, reloj)
        reloj += p.minutos_atencion
        v = por_id[vid]
        paradas.append(
            Parada(pos, vid, v.nombre, v.corregimiento, round(tramo_km, 2), round(tramo_min, 1), llegada,
                   _hhmm(inicio, reloj), puntaje[vid])
        )
        km_total += tramo_km
        min_viaje += tramo_min
        previo = nodo
    regreso_min = m[previo][0] if tour else 0.0
    regreso_km = matriz.km[previo][0] if tour else 0.0
    reloj += regreso_min
    return ResultadoRuta(
        paradas=paradas,
        regreso_km=round(regreso_km, 2),
        regreso_min=round(regreso_min, 1),
        distancia_total_km=round(km_total + regreso_km, 2),
        tiempo_viaje_min=round(min_viaje + regreso_min, 1),
        tiempo_total_min=round(reloj, 1),
        hora_regreso=_hhmm(inicio, reloj),
        costo_heuristico_min=round(c_h, 2),
        costo_optimo_min=round(c_o, 2),
        brecha_vs_optimo_pct=opt.brecha_pct(c_h, c_o),
        descartadas=descartadas,
        ranking=ranking,
    )
