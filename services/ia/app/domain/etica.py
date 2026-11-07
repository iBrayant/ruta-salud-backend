"""Reglas deterministas de lenguaje responsable (primera capa de revisión ética).

Marco Ético para la IA en Colombia (2021): no discriminación, privacidad,
transparencia y explicación, control humano. Estas reglas no dependen del
modelo de lenguaje: se aplican siempre, antes y después de él.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Expresiones que atribuyen características negativas a una comunidad o a sus habitantes.
_PATRONES_ESTIGMA = [
    r"\b(gente|personas|habitantes|comunidad(es)?|poblaci[oó]n|familias|campesinos)\s+(es|son|muy|m[aá]s|tan)?\s*"
    r"(pobres?|peligros[oa]s?|atrasad[oa]s?|conflictiv[oa]s?|ignorantes?|problem[aá]tic[oa]s?|marginales?|"
    r"miserables?|incult[oa]s?|suci[oa]s?|violent[oa]s?|perezos[oa]s?)\b",
    r"\b(zona|vereda|sector)\s+(roja|peligrosa|conflictiva|problem[aá]tica|marginal|miserable)\b",
    r"\b(miserables?|ignorantes?|atrasad[oa]s?|incultos?|invasores?|focos? de (pobreza|delincuencia|enfermedad))\b",
    r"\b(los|las)\s+(pobres|vulnerables|necesitados)\b",
]
# Lo que el asistente no debe hacer en un contexto de salud.
_PATRONES_CLINICOS = [
    r"\b(diagn[oó]stic[oa]|recet[ae]|prescrib|dosis|medicamento\s+recomendado)\b",
]
# Afirmaciones imprecisas sobre métricas relativas (la accesibilidad 0 es "la más lejana", no "sin acceso").
_PATRONES_IMPRECISOS = [
    r"\baccesibilidad\s+(es\s+)?(nula|cero|inexistente|ninguna)\b",
    r"\b(sin|no\s+tiene|carece\s+de)\s+(ning[uú]n\s+)?acceso\b",
    r"\b(inaccesible|incomunicad[oa])\b",
]
_REGEX_ESTIGMA = [re.compile(p, re.IGNORECASE) for p in _PATRONES_ESTIGMA]
_REGEX_IMPRECISO = [re.compile(p, re.IGNORECASE) for p in _PATRONES_IMPRECISOS]
_REGEX_CLINICO = [re.compile(p, re.IGNORECASE) for p in _PATRONES_CLINICOS]

# Datos personales que no deben viajar al proveedor de IA (Ley 1581 de 2012).
_PII = [
    (re.compile(r"\b\d{6,10}\b"), "[NÚMERO OCULTO]"),                       # cédulas, teléfonos
    (re.compile(r"\b3\d{2}[\s-]?\d{3}[\s-]?\d{4}\b"), "[TELÉFONO OCULTO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[CORREO OCULTO]"),
]


@dataclass(frozen=True)
class Hallazgo:
    tipo: str        # estigma | clinico
    fragmento: str


def detectar(texto: str, incluir_clinico: bool = False, incluir_imprecision: bool = False) -> list[Hallazgo]:
    h = [Hallazgo("estigma", m.group(0)) for rx in _REGEX_ESTIGMA for m in rx.finditer(texto)]
    if incluir_clinico:
        h += [Hallazgo("clinico", m.group(0)) for rx in _REGEX_CLINICO for m in rx.finditer(texto)]
    if incluir_imprecision:
        h += [Hallazgo("impreciso", m.group(0)) for rx in _REGEX_IMPRECISO for m in rx.finditer(texto)]
    return h


def ocultar_datos_personales(texto: str) -> tuple[str, int]:
    n = 0
    for rx, reemplazo in _PII:
        texto, k = rx.subn(reemplazo, texto)
        n += k
    return texto, n


PRINCIPIOS = (
    "1) El índice de vulnerabilidad describe NECESIDAD DE ATENCIÓN de un territorio, nunca una característica de "
    "las personas. 2) No uses adjetivos negativos sobre comunidades (pobres, peligrosas, atrasadas, conflictivas, "
    "etc.). 3) Explica solo con los datos entregados; no inventes cifras, nombres ni hechos. 4) Recuerda que la "
    "decisión final es del equipo humano. 5) No emitas diagnósticos ni recomendaciones clínicas. 6) Lenguaje claro, "
    "respetuoso y en español de Colombia. 7) Las métricas son RELATIVAS al conjunto de veredas (ver glosario): una "
    "accesibilidad de 0 significa 'la más lejana del conjunto', nunca 'accesibilidad nula' ni 'sin acceso'. "
    "8) Sobre lluvia, usa solo el pronóstico por hora entregado; si no hay dato para una hora, dilo."
)
