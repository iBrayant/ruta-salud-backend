"""Pruebas del dominio: sin red, sin base de datos (gracias a la arquitectura limpia)."""
from datetime import date

from app.domain import optimizacion as opt
from app.domain.entities import ClimaVereda, MatrizViaje, ParametrosJornada, Vereda
from app.domain.planificador import planificar
from app.domain.priorizacion import equidad, puntuar
from app.domain.simulacion import simular

FECHA = date(2026, 11, 5)


def _vereda(i: int, v: float, via: str = "terciaria") -> Vereda:
    return Vereda(f"V{i}", f"Vereda {i}", "Corr", 4.3, -74.3, v, {}, via)


def _matriz(n: int) -> MatrizViaje:
    # Nodos en una línea: tiempo = |i - j| * 10 min; el hospital es el 0
    ids = ["HSR"] + [f"V{i}" for i in range(1, n + 1)]
    m = [[abs(i - j) * 10.0 for j in range(n + 1)] for i in range(n + 1)]
    return MatrizViaje(ids, [[x / 2 for x in f] for f in m], m, "prueba")


def test_equidad_nunca_visitada_es_maxima():
    assert equidad(None) == 1.0
    assert equidad(0) == 0.0
    assert equidad(15) == 0.5
    assert equidad(400) == 1.0


def test_dos_opt_no_empeora_y_alcanza_optimo_en_linea():
    m = _matriz(6).minutos
    nodos = [4, 1, 6, 2, 5, 3]
    vmc = opt.vecino_mas_cercano(nodos, m)
    mejor = opt.dos_opt([6, 1, 5, 2, 4, 3], m)
    assert opt.costo_tour(mejor, m) <= opt.costo_tour([6, 1, 5, 2, 4, 3], m)
    assert opt.costo_tour(opt.heuristico(nodos, m), m) == opt.costo_tour(opt.optimo_exacto(nodos, m), m)
    assert vmc == [1, 2, 3, 4, 5, 6]


def test_mayor_vulnerabilidad_gana_a_igual_distancia():
    veredas = [_vereda(1, 0.2), _vereda(2, 0.9)]
    m = MatrizViaje(["HSR", "V1", "V2"], [[0, 5, 5], [5, 0, 1], [5, 1, 0]], [[0, 10, 10], [10, 0, 2], [10, 2, 0]], "p")
    ranking = puntuar(veredas, m, {}, None, ParametrosJornada(fecha=FECHA))
    assert ranking[0].vereda_id == "V2"


def test_periodo_de_descanso_excluye_vereda_visitada():
    veredas = [_vereda(i, 0.5) for i in range(1, 7)]
    res = planificar(veredas, _matriz(6), {"V1": 2}, None, ParametrosJornada(fecha=FECHA))
    assert "V1" not in [p.vereda_id for p in res.paradas]
    assert any(d["vereda_id"] == "V1" and "descanso" in d["motivo"] for d in res.descartadas)


def test_respeta_duracion_de_jornada():
    veredas = [_vereda(i, 0.5) for i in range(1, 7)]
    p = ParametrosJornada(fecha=FECHA, minutos_jornada=200, minutos_atencion=45)
    res = planificar(veredas, _matriz(6), {}, None, p)
    assert res.tiempo_total_min <= 200
    assert len(res.paradas) < 5


def test_lluvia_penaliza_solo_vias_destapadas():
    veredas = [_vereda(1, 0.5, "terciaria"), _vereda(2, 0.5, "primer_orden")]
    m = MatrizViaje(["HSR", "V1", "V2"], [[0, 5, 5], [5, 0, 1], [5, 1, 0]], [[0, 10, 10], [10, 0, 2], [10, 2, 0]], "p")
    clima = {"V1": ClimaVereda(90, 10), "V2": ClimaVereda(90, 10)}
    r = {s.vereda_id: s for s in puntuar(veredas, m, {}, clima, ParametrosJornada(fecha=FECHA))}
    assert r["V1"].penalizada_por_lluvia and not r["V2"].penalizada_por_lluvia


def test_lluvia_no_favorece_a_la_vereda_mas_lejana():
    # V1 cerca, V2 la más lejana (accesibilidad 0); ambas con vía destapada
    veredas = [_vereda(1, 0.5), _vereda(2, 0.5)]
    m = MatrizViaje(["HSR", "V1", "V2"], [[0, 2, 20], [2, 0, 18], [20, 18, 0]],
                    [[0, 5, 40], [5, 0, 35], [40, 35, 0]], "p")
    p = ParametrosJornada(fecha=FECHA)
    seco = {s.vereda_id: s for s in puntuar(veredas, m, {}, None, p)}
    lluvia = {s.vereda_id: s for s in puntuar(veredas, m, {}, {"V1": ClimaVereda(90, 9), "V2": ClimaVereda(90, 9)}, p)}
    # Ambas pierden exactamente lo mismo: la lluvia no cambia su orden relativo
    for vid in ("V1", "V2"):
        assert round(seco[vid].accesibilidad - lluvia[vid].accesibilidad, 4) == 0.5
    assert lluvia["V1"].prioridad > lluvia["V2"].prioridad


def test_planificacion_es_determinista():
    veredas = [_vereda(i, 0.1 * i) for i in range(1, 8)]
    a = planificar(veredas, _matriz(7), {}, None, ParametrosJornada(fecha=FECHA))
    b = planificar(veredas, _matriz(7), {}, None, ParametrosJornada(fecha=FECHA))
    assert a == b


def test_simulacion_cubre_todas_las_veredas():
    veredas = [_vereda(i, 0.1 * i) for i in range(1, 11)]
    s = simular(veredas, _matriz(10), ParametrosJornada(fecha=FECHA, minutos_jornada=720), n_jornadas=6)
    assert s["metricas"]["cobertura_pct"] == 100.0
    assert s["metricas"]["veredas_nunca_visitadas"] == []
