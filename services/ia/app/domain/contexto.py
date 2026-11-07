"""Construye el contexto factual que recibe el modelo y una explicación de respaldo sin IA."""
from __future__ import annotations

from typing import Any


GLOSARIO = {
    "prioridad": "Puntaje final P = α·necesidad + (1−α)·accesibilidad + γ·equidad.",
    "necesidad_atencion": "Índice 0–1 de necesidad de atención del territorio (no describe a las personas).",
    "accesibilidad": ("Valor RELATIVO 0–1 dentro de las 15 veredas: 1 = la más cercana al hospital, 0 = la más "
                      "lejana del conjunto. Un 0 NO significa que no haya acceso; significa mayor tiempo de viaje."),
    "equidad": "0–1 según días sin visita (1 = nunca visitada o 30+ días).",
    "lluvia_por_hora": ("Pronóstico Open-Meteo por hora local: probabilidad de lluvia (%) y precipitación (mm). "
                        "Si una hora no aparece, no hay dato para esa hora."),
    "tipo_via": ("terciaria = destapada, la más afectada por la lluvia; mixta = parcialmente pavimentada; "
                 "primer_orden = pavimentada, casi no se afecta."),
}


def _hora(hhmm: str) -> int:
    return int(hhmm[:2])


def _lluvia_parada(clima: dict[str, Any] | None, vereda_id: str, llegada: str, salida: str) -> dict[str, Any] | None:
    c = (clima or {}).get(vereda_id)
    if not c or not c.get("por_hora"):
        return None
    por_hora = {f"{h}:00": f"{v['prob']:.0f}% / {v['mm']:.1f} mm" for h, v in sorted(c["por_hora"].items())}
    durante = [v for h, v in c["por_hora"].items() if _hora(llegada) <= int(h) <= _hora(salida)]
    return {
        "tipo_via": c.get("tipo_via"),
        "durante_visita": {
            "prob_max_pct": max((v["prob"] for v in durante), default=None),
            "mm_total": round(sum(v["mm"] for v in durante), 1) if durante else None,
        },
        "por_hora": por_hora,
    }


def hechos_ruta(ruta: dict[str, Any]) -> dict[str, Any]:
    """Resumen compacto y verificable: solo lo que el algoritmo calculó."""
    paradas = ruta.get("paradas") or ruta.get("orden") or []
    clima = ruta.get("clima_por_vereda")
    return {
        "glosario": GLOSARIO,
        "codigo": ruta.get("codigo"),
        "fecha_jornada": ruta.get("fecha_jornada"),
        "parametros": {k: ruta.get("parametros", {}).get(k) for k in
                       ("alpha", "gamma", "dias_minimos_entre_visitas", "n_veredas", "minutos_atencion",
                        "hora_inicio", "considerar_lluvia")},
        "paradas": [
            {
                "posicion": p["posicion"],
                "vereda": p["nombre"],
                "corregimiento": p["corregimiento"],
                "llegada": p["llegada"],
                "salida": p["salida"],
                "tramo_km": p["tramo_km"],
                "tramo_min": p["tramo_min"],
                "prioridad": p["puntaje"]["prioridad"],
                "necesidad_atencion": p["puntaje"]["vulnerabilidad"],
                "accesibilidad": p["puntaje"]["accesibilidad"],
                "equidad": p["puntaje"]["equidad"],
                "dias_sin_visita": p["puntaje"]["dias_sin_visita"],
                "lluvia_fuerte_en_jornada": p["puntaje"]["lluvia_fuerte"],
                "lluvia": _lluvia_parada(clima, p["vereda_id"], p["llegada"], p["salida"]),
            }
            for p in paradas
        ],
        "distancia_total_km": ruta.get("distancia_total_km"),
        "tiempo_total_min": ruta.get("tiempo_total_min"),
        "hora_regreso": ruta.get("hora_regreso") or (ruta.get("regreso") or {}).get("hora"),
        "brecha_vs_optimo_pct": ruta.get("brecha_vs_optimo_pct",
                                         (ruta.get("optimizacion") or {}).get("brecha_vs_optimo_pct")),
        "no_incluidas": [{"vereda_id": d["vereda_id"], "motivo": d["motivo"]} for d in ruta.get("descartadas", [])][:10],
        "fuente_distancias": ruta.get("fuente_distancias"),
        "clima_disponible": ruta.get("clima_disponible"),
    }


def explicacion_plantilla(h: dict[str, Any]) -> dict[str, Any]:
    """Respaldo determinista cuando la IA no está disponible o su texto no pasa la revisión."""
    por_parada = []
    for p in h["paradas"]:
        partes = [f"prioridad {p['prioridad']:.2f}", f"necesidad de atención {p['necesidad_atencion']:.2f}",
                  f"accesibilidad relativa {p['accesibilidad']:.2f}"]
        if p["dias_sin_visita"] is None:
            partes.append("sin visitas registradas")
        else:
            partes.append(f"{p['dias_sin_visita']} días sin visita")
        dv = (p.get("lluvia") or {}).get("durante_visita") or {}
        if dv.get("prob_max_pct") is not None:
            partes.append(f"probabilidad de lluvia durante la visita hasta {dv['prob_max_pct']:.0f} %")
        elif p["lluvia_fuerte_en_jornada"]:
            partes.append("se prevé lluvia fuerte en la jornada")
        por_parada.append({"vereda": p["vereda"], "razon": "Incluida por " + ", ".join(partes) + "."})
    return {
        "resumen": (
            f"Ruta de {len(h['paradas'])} veredas, {h['distancia_total_km']} km en total, regreso estimado "
            f"{h['hora_regreso']}. El orden minimiza el tiempo de viaje "
            f"(diferencia con el óptimo exacto: {h['brecha_vs_optimo_pct']} %)."
        ),
        "por_parada": por_parada,
        "advertencias": ["Explicación generada por plantilla, sin modelo de lenguaje."],
    }
