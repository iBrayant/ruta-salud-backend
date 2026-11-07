"""Casos de uso de IA: explicar una ruta (con revisión ética) y responder consultas."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..domain import contexto, etica, prompts
from .ports import FuenteRutas, Limites, ModeloLenguaje, RegistroAuditoria

log = logging.getLogger("ia")
AVISO = ("Texto generado con IA a partir de los resultados del algoritmo. La IA explica; no decide. "
         "La ruta la calcula el algoritmo y la aprueba el equipo de salud.")


class IANoDisponible(RuntimeError):
    pass


class LimiteExcedido(RuntimeError):
    pass


class RutaNoAccesible(LookupError):
    pass


def _h(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


def _json_seguro(texto: str) -> dict[str, Any] | None:
    try:
        d = json.loads(texto)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


def _valida_forma(d: dict[str, Any] | None, veredas: set[str]) -> bool:
    if not d or not isinstance(d.get("resumen"), str) or not isinstance(d.get("por_parada"), list):
        return False
    # Anclaje a los datos: toda vereda mencionada por parada debe existir en la ruta
    return all(isinstance(p, dict) and p.get("vereda") in veredas for p in d["por_parada"])


def _texto_plano(d: dict[str, Any]) -> str:
    return " ".join([d.get("resumen", "")] + [p.get("razon", "") for p in d.get("por_parada", [])]
                    + list(d.get("advertencias", [])))


class ServicioIA:
    def __init__(self, llm: ModeloLenguaje, limites: Limites, rutas: FuenteRutas, auditoria: RegistroAuditoria):
        self.llm = llm
        self.limites = limites
        self.rutas = rutas
        self.auditoria = auditoria

    # ------------------------------------------------------------------ explicar
    async def explicar(self, ruta: dict[str, Any], actor: Any) -> dict[str, Any]:
        hechos = contexto.hechos_ruta(ruta)
        veredas = {p["vereda"] for p in hechos["paradas"]}
        datos = json.dumps(hechos, ensure_ascii=False)
        tokens_in = tokens_out = 0
        observaciones: list[str] = []
        metodo, aprobado_revisor = "plantilla", None

        final: dict[str, Any] | None = None
        if self.llm.disponible and await self.limites.presupuesto_disponible() and hechos["paradas"]:
            try:
                r1 = await self.llm.completar(prompts.EXPLICACION, f"<datos_ruta>{datos}</datos_ruta>", json=True)
                tokens_in, tokens_out = r1.tokens_entrada, r1.tokens_salida
                borrador = _json_seguro(r1.texto)
                if _valida_forma(borrador, veredas):
                    r2 = await self.llm.completar(
                        prompts.REVISION,
                        f"<datos_ruta>{datos}</datos_ruta>\n<texto>{json.dumps(borrador, ensure_ascii=False)}</texto>",
                        json=True, max_tokens=900)
                    tokens_in += r2.tokens_entrada
                    tokens_out += r2.tokens_salida
                    rev = _json_seguro(r2.texto) or {}
                    aprobado_revisor = bool(rev.get("aprobado"))
                    observaciones = [str(o) for o in rev.get("observaciones", [])][:10]
                    candidato = borrador if aprobado_revisor else rev.get("texto_corregido")
                    if _valida_forma(candidato, veredas) and not etica.detectar(_texto_plano(candidato), incluir_imprecision=True):
                        final, metodo = candidato, "llm+revisor+reglas"
                    else:
                        observaciones.append("El texto no superó las reglas deterministas; se usó la plantilla.")
                else:
                    observaciones.append("Respuesta del modelo sin la forma esperada o con veredas inexistentes.")
                await self.limites.consumir_tokens(tokens_in + tokens_out)
            except IANoDisponible as e:
                observaciones.append(f"Modelo no disponible: {e}")
        elif not self.llm.disponible:
            observaciones.append("IA no configurada (sin OPENAI_API_KEY).")
        else:
            observaciones.append("Presupuesto diario de IA agotado o ruta vacía.")

        if final is None:
            final = contexto.explicacion_plantilla(hechos)
        reglas = etica.detectar(_texto_plano(final), incluir_imprecision=True)
        resultado = {
            **final,
            "revision_etica": {
                "metodo": metodo,
                "aprobado_revisor_ia": aprobado_revisor,
                "aprobado_reglas": not reglas,
                "observaciones": observaciones,
                "version_prompts": prompts.VERSION,
            },
            "modelo": self.llm.modelo if metodo != "plantilla" else None,
            "tokens": {"entrada": tokens_in, "salida": tokens_out},
            "costo_estimado_usd": round(self.llm.costo_usd(tokens_in, tokens_out), 6),
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "aviso": AVISO,
        }
        await self.auditoria.registrar(
            "explicacion_generada", actor, f"ruta:{ruta.get('ruta_id')}",
            {"metodo": metodo, "aprobado_revisor_ia": aprobado_revisor, "aprobado_reglas": not reglas,
             "tokens": resultado["tokens"], "costo_estimado_usd": resultado["costo_estimado_usd"],
             "modelo": resultado["modelo"], "version_prompts": prompts.VERSION,
             "huella_texto": _h(_texto_plano(final))},
        )
        return resultado

    # ------------------------------------------------------------------ chat
    async def consultar(self, ruta_id: str, pregunta: str, actor: Any, ip: str) -> dict[str, Any]:
        if not self.llm.disponible:
            raise IANoDisponible("IA no configurada")
        if not await self.limites.permitir_chat(actor.usuario):
            raise LimiteExcedido("Límite de consultas por hora alcanzado")
        if not await self.limites.presupuesto_disponible():
            raise LimiteExcedido("Presupuesto diario de IA agotado")
        ruta = await self.rutas.obtener(ruta_id, actor.token)  # respeta los permisos del usuario
        if not ruta:
            raise RutaNoAccesible(ruta_id)

        pregunta_limpia, n_pii = etica.ocultar_datos_personales(pregunta.strip())
        datos = json.dumps(contexto.hechos_ruta(ruta), ensure_ascii=False)
        r = await self.llm.completar(
            prompts.CHAT, f"<datos_ruta>{datos}</datos_ruta>\n<pregunta>{pregunta_limpia}</pregunta>", max_tokens=350)
        await self.limites.consumir_tokens(r.tokens_entrada + r.tokens_salida)
        hallazgos = etica.detectar(r.texto, incluir_clinico=True)
        bloqueada = bool(hallazgos)
        respuesta = (
            "No puedo responder eso de forma adecuada. Consulte al coordinador de la jornada."
            if bloqueada else r.texto.strip()
        )
        await self.auditoria.registrar(
            "consulta_asistente", actor, f"ruta:{ruta_id}",
            {"pregunta_redactada": pregunta_limpia[:500], "datos_personales_ocultados": n_pii,
             "respuesta_bloqueada": bloqueada, "hallazgos": [h.tipo for h in hallazgos],
             "tokens": {"entrada": r.tokens_entrada, "salida": r.tokens_salida},
             "costo_estimado_usd": round(self.llm.costo_usd(r.tokens_entrada, r.tokens_salida), 6),
             "modelo": r.modelo, "version_prompts": prompts.VERSION, "huella_respuesta": _h(respuesta)},
            ip,
        )
        return {
            "ruta_id": ruta_id,
            "respuesta": respuesta,
            "datos_personales_ocultados": n_pii,
            "bloqueada_por_revision": bloqueada,
            "aviso": AVISO,
        }
