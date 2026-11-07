"""Cadena de hashes del registro de auditoría (evidencia de manipulación).

Cada evento guarda el hash del anterior: hash_n = SHA-256(registro canónico_n),
y el registro canónico incluye hash_{n-1}. Si alguien altera, borra o inserta
un evento en medio, la verificación falla desde ese punto.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

GENESIS = "0" * 64
CAMPOS = ("seq", "ts", "accion", "actor", "actor_tipo", "roles", "recurso", "detalle", "ip", "servicio_origen",
          "hash_anterior")


def canonico(evento: dict[str, Any]) -> str:
    return json.dumps({k: evento[k] for k in CAMPOS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calcular_hash(registro_canonico: str) -> str:
    return hashlib.sha256(registro_canonico.encode("utf-8")).hexdigest()


def encadenar(evento: dict[str, Any], seq: int, ts: str, hash_anterior: str) -> tuple[str, str]:
    """Devuelve (registro_canonico, hash) del nuevo eslabón."""
    reg = canonico({**evento, "seq": seq, "ts": ts, "hash_anterior": hash_anterior})
    return reg, calcular_hash(reg)


@dataclass(frozen=True)
class ResultadoVerificacion:
    integra: bool
    eventos_verificados: int
    primer_seq_invalido: int | None
    motivo: str | None
    hash_final: str


def verificar(eslabones: Iterable[tuple[int, str, str]]) -> ResultadoVerificacion:
    """eslabones: (seq, registro_canonico, hash) en orden ascendente de seq."""
    previo, esperado_seq, n = GENESIS, 1, 0
    for seq, reg, h in eslabones:
        datos = json.loads(reg)
        if seq != esperado_seq or datos["seq"] != seq:
            return ResultadoVerificacion(False, n, seq, f"Secuencia rota: se esperaba {esperado_seq}", previo)
        if datos["hash_anterior"] != previo:
            return ResultadoVerificacion(False, n, seq, "El enlace con el evento anterior no coincide", previo)
        if calcular_hash(reg) != h:
            return ResultadoVerificacion(False, n, seq, "El contenido del evento fue alterado", previo)
        previo, esperado_seq, n = h, seq + 1, n + 1
    return ResultadoVerificacion(True, n, None, None, previo)
