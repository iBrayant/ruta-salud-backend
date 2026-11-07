"""Casos de uso del servicio de rutas. Orquestan el dominio a través de los puertos."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from ..domain.entities import ParametrosJornada
from ..domain.planificador import planificar
from ..domain.simulacion import simular
from . import serializacion as ser
from .ports import (
    ProveedorClima,
    ProveedorDistancias,
    RegistroAuditoria,
    RepositorioRutas,
    RepositorioVeredas,
    ServicioExplicacion,
)

log = logging.getLogger("rutas")


class RutaNoEncontrada(LookupError):
    pass


def clima_de_ruta(ruta: dict[str, Any]) -> dict[str, Any] | None:
    """Pronóstico (agregado y por hora) y tipo de vía de las veredas que visita la ruta."""
    clima = ruta["snapshot"].get("clima")
    if not clima:
        return None
    via = {v["id"]: v["tipo_via"] for v in ruta["snapshot"]["veredas"]}
    return {vid: {**clima[vid], "tipo_via": via.get(vid)} for vid in ruta["resultado"]["orden"] if vid in clima}


class ServicioRutas:
    def __init__(
        self,
        veredas: RepositorioVeredas,
        distancias: ProveedorDistancias,
        clima: ProveedorClima,
        rutas: RepositorioRutas,
        explicacion: ServicioExplicacion,
        auditoria: RegistroAuditoria,
    ) -> None:
        self.veredas = veredas
        self.distancias = distancias
        self.clima = clima
        self.rutas = rutas
        self.explicacion = explicacion
        self.auditoria = auditoria

    # ------------------------------------------------------------------ entradas
    async def _entradas(self, p: ParametrosJornada):
        veredas = self.veredas.listar()
        matriz = await self.distancias.matriz(self.veredas.hospital(), veredas)
        clima = None
        if p.considerar_lluvia:
            h0 = int(p.hora_inicio[:2])
            clima = await self.clima.pronostico(veredas, p.fecha, h0, min(23, h0 + p.minutos_jornada // 60))
        ultima = await self.rutas.ultima_visita(p.fecha)
        dias = {v.id: ((p.fecha - ultima[v.id]).days if v.id in ultima else None) for v in veredas}
        return veredas, matriz, dias, clima

    # ------------------------------------------------------------------ generar
    async def generar(self, p: ParametrosJornada, actor: Any, ip: str) -> dict[str, Any]:
        veredas, matriz, dias, clima = await self._entradas(p)
        resultado = planificar(veredas, matriz, dias, clima, p)

        snap = ser.snapshot(veredas, matriz, dias, clima, self.veredas.version())
        params = ser.parametros_a_dict(p)
        res = ser.resultado_a_dict(resultado)
        ruta_id = str(uuid.uuid4())
        ruta = {
            "id": ruta_id,
            "codigo": await self.rutas.siguiente_codigo(p.fecha),
            "fecha_jornada": p.fecha,
            "creado_en": datetime.now(timezone.utc),
            "creado_por": actor.usuario,
            "estado": "propuesta",
            "parametros": params,
            "snapshot": snap,
            "huella_entradas": ser.huella({"parametros": params, "snapshot": snap}),
            "resultado": res,
            "huella_resultado": ser.huella(res),
            "version_datos": self.veredas.version(),
        }
        # Fail-closed: si la auditoría no registra, la ruta no se entrega.
        await self.auditoria.registrar(
            "ruta_generada",
            actor,
            f"ruta:{ruta_id}",
            {
                "codigo": ruta["codigo"],
                "parametros": params,
                "snapshot": snap,
                "huella_entradas": ruta["huella_entradas"],
                "huella_resultado": ruta["huella_resultado"],
                "orden": res["orden"],
                "distancia_total_km": res["distancia_total_km"],
                "fuente_distancias": matriz.fuente,
                "clima_disponible": clima is not None,
            },
            ip,
        )
        await self.rutas.guardar(ruta)

        explicacion = await self.explicacion.explicar(self._vista_para_ia(ruta))
        if explicacion:
            await self.rutas.guardar_explicacion(ruta_id, explicacion)
            ruta["explicacion"] = explicacion
        else:
            ruta["explicacion"] = None
        return ruta

    # ------------------------------------------------------------------ reproducir
    async def reproducir(self, ruta_id: str, actor: Any, ip: str) -> dict[str, Any]:
        ruta = await self.rutas.obtener(ruta_id)
        if not ruta:
            raise RutaNoEncontrada(ruta_id)
        integridad = ser.huella({"parametros": ruta["parametros"], "snapshot": ruta["snapshot"]}) == ruta["huella_entradas"]
        veredas, matriz, dias, clima = ser.desde_snapshot(ruta["snapshot"])
        nuevo = ser.resultado_a_dict(planificar(veredas, matriz, dias, clima, ser.parametros_desde_dict(ruta["parametros"])))
        coincide = ser.huella(nuevo) == ruta["huella_resultado"]
        informe = {
            "ruta_id": ruta_id,
            "codigo": ruta["codigo"],
            "integridad_entradas": integridad,
            "resultado_coincide": coincide,
            "orden_original": ruta["resultado"]["orden"],
            "orden_reproducido": nuevo["orden"],
            "distancia_original_km": ruta["resultado"]["distancia_total_km"],
            "distancia_reproducida_km": nuevo["distancia_total_km"],
            "huella_resultado_original": ruta["huella_resultado"],
            "huella_resultado_reproducido": ser.huella(nuevo),
        }
        await self.auditoria.registrar("ruta_reproducida", actor, f"ruta:{ruta_id}",
                                       {k: v for k, v in informe.items() if k != "ruta_id"}, ip)
        return informe

    # ------------------------------------------------------------------ ejecutar
    async def marcar_ejecutada(self, ruta_id: str, actor: Any, ip: str) -> dict[str, Any]:
        ruta = await self.rutas.marcar_ejecutada(ruta_id, actor.usuario)
        if not ruta:
            raise RutaNoEncontrada(ruta_id)
        await self.auditoria.registrar("ruta_ejecutada", actor, f"ruta:{ruta_id}",
                                       {"codigo": ruta["codigo"], "orden": ruta["resultado"]["orden"]}, ip)
        return ruta

    # ------------------------------------------------------------------ simular
    async def simular(self, p: ParametrosJornada, n_jornadas: int, actor: Any, ip: str) -> dict[str, Any]:
        veredas, matriz, _dias, clima = await self._entradas(p)
        ultima = await self.rutas.ultima_visita(p.fecha)
        sim = simular(veredas, matriz, p, n_jornadas, ultima, clima)
        await self.auditoria.registrar(
            "simulacion_ejecutada", actor, "simulacion",
            {"parametros": ser.parametros_a_dict(p), "n_jornadas": n_jornadas,
             "cobertura_pct": sim["metricas"]["cobertura_pct"], "fuente_distancias": matriz.fuente}, ip)
        return sim

    # ------------------------------------------------------------------ consultas
    async def obtener(self, ruta_id: str) -> dict[str, Any]:
        ruta = await self.rutas.obtener(ruta_id)
        if not ruta:
            raise RutaNoEncontrada(ruta_id)
        return ruta

    async def listar(self, limite: int, desplazamiento: int) -> list[dict[str, Any]]:
        return await self.rutas.listar(limite, desplazamiento)

    def veredas_detalle(self) -> dict[str, Any]:
        h = self.veredas.hospital()
        return {"version_datos": self.veredas.version(),
                "hospital": {"id": h.id, "nombre": h.nombre, "lat": h.lat, "lon": h.lon},
                "veredas": self.veredas.detalle()}

    @staticmethod
    def _vista_para_ia(ruta: dict[str, Any]) -> dict[str, Any]:
        return {**ServicioRutas._vista_para_ia_base(ruta), "clima_por_vereda": clima_de_ruta(ruta)}

    @staticmethod
    def _vista_para_ia_base(ruta: dict[str, Any]) -> dict[str, Any]:
        """Solo lo necesario para explicar: sin snapshot completo ni datos de usuario."""
        r = ruta["resultado"]
        return {
            "ruta_id": ruta["id"],
            "codigo": ruta["codigo"],
            "fecha_jornada": str(ruta["fecha_jornada"]),
            "parametros": ruta["parametros"],
            "paradas": r["paradas"],
            "distancia_total_km": r["distancia_total_km"],
            "tiempo_total_min": r["tiempo_total_min"],
            "hora_regreso": r["hora_regreso"],
            "brecha_vs_optimo_pct": r["brecha_vs_optimo_pct"],
            "descartadas": r["descartadas"][:10],
            "fuente_distancias": ruta["snapshot"]["matriz"]["fuente"],
            "clima_disponible": ruta["snapshot"]["clima"] is not None,
        }
