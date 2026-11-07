"""Fase 2: orden de visita (problema del viajante con depósito = hospital).

1. Vecino más cercano: desde el hospital, ir a la vereda pendiente más cercana.
2. Mejora 2-opt: invertir tramos mientras se reduzca el costo.
3. Óptimo exacto por fuerza bruta (n ≤ 8) para medir la brecha del heurístico.
Todos los tours son cerrados: hospital → … → hospital.
"""
from __future__ import annotations

from itertools import permutations

Matriz = list[list[float]]
MAX_EXACTO = 8


def costo_tour(tour: list[int], m: Matriz) -> float:
    if not tour:
        return 0.0
    c = m[0][tour[0]] + m[tour[-1]][0]
    for a, b in zip(tour, tour[1:]):
        c += m[a][b]
    return c


def vecino_mas_cercano(nodos: list[int], m: Matriz) -> list[int]:
    pendientes = sorted(nodos)
    tour: list[int] = []
    actual = 0
    while pendientes:
        sig = min(pendientes, key=lambda j: (m[actual][j], j))
        tour.append(sig)
        pendientes.remove(sig)
        actual = sig
    return tour


def dos_opt(tour: list[int], m: Matriz) -> list[int]:
    mejor = list(tour)
    mejor_costo = costo_tour(mejor, m)
    mejora = True
    while mejora:
        mejora = False
        for i in range(len(mejor) - 1):
            for k in range(i + 1, len(mejor)):
                candidato = mejor[:i] + mejor[i : k + 1][::-1] + mejor[k + 1 :]
                c = costo_tour(candidato, m)
                if c < mejor_costo - 1e-9:
                    mejor, mejor_costo, mejora = candidato, c, True
    return mejor


def heuristico(nodos: list[int], m: Matriz) -> list[int]:
    return dos_opt(vecino_mas_cercano(nodos, m), m)


def optimo_exacto(nodos: list[int], m: Matriz) -> list[int]:
    if len(nodos) > MAX_EXACTO:
        raise ValueError(f"Fuerza bruta limitada a {MAX_EXACTO} nodos")
    if not nodos:
        return []
    return list(min(permutations(sorted(nodos)), key=lambda t: (costo_tour(list(t), m), t)))


def brecha_pct(c_heur: float, c_opt: float) -> float:
    return 0.0 if c_opt <= 0 else round(100.0 * (c_heur - c_opt) / c_opt, 2)
