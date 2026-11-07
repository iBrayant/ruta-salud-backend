import json

from app.domain.cadena import GENESIS, encadenar, verificar


def _cadena(n: int):
    eslabones, previo = [], GENESIS
    for i in range(1, n + 1):
        ev = {"accion": "ruta_generada", "actor": "coord", "actor_tipo": "usuario", "roles": ["coordinador"],
              "recurso": f"ruta:{i}", "detalle": {"km": 10.5 * i}, "ip": "1.2.3.4", "servicio_origen": "svc-rutas"}
        reg, h = encadenar(ev, i, f"2026-11-05T07:0{i}:00-05:00", previo)
        eslabones.append((i, reg, h))
        previo = h
    return eslabones


def test_cadena_integra():
    r = verificar(_cadena(5))
    assert r.integra and r.eventos_verificados == 5


def test_detecta_contenido_alterado():
    c = _cadena(5)
    seq, reg, h = c[2]
    d = json.loads(reg)
    d["detalle"]["km"] = 1.0
    c[2] = (seq, json.dumps(d), h)
    r = verificar(c)
    assert not r.integra and r.primer_seq_invalido == 3


def test_detecta_evento_borrado():
    c = _cadena(5)
    del c[1]
    r = verificar(c)
    assert not r.integra and r.primer_seq_invalido == 3
