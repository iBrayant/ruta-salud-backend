"""Entidades del dominio. Python puro: sin FastAPI, sin base de datos, sin red."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ID_HOSPITAL = "HSR"


@dataclass(frozen=True)
class Vereda:
    id: str
    nombre: str
    corregimiento: str
    lat: float
    lon: float
    vulnerabilidad: float            # índice de necesidad de atención, 0..1
    componentes: dict[str, float]    # desglose del índice
    tipo_via: str                    # terciaria | mixta | primer_orden


@dataclass(frozen=True)
class Hospital:
    id: str
    nombre: str
    lat: float
    lon: float


@dataclass(frozen=True)
class ParametrosJornada:
    fecha: date
    alpha: float = 0.7               # peso de la vulnerabilidad frente a la accesibilidad
    gamma: float = 0.15              # peso de la equidad (días sin visita)
    dias_minimos_entre_visitas: int = 7   # periodo de descanso: no repetir vereda antes de N días
    n_veredas: int = 5
    minutos_atencion: int = 45
    minutos_jornada: int = 480
    hora_inicio: str = "07:00"
    considerar_lluvia: bool = True


@dataclass(frozen=True)
class MatrizViaje:
    """Matriz origen-destino. El índice 0 es siempre el hospital."""
    ids: list[str]
    km: list[list[float]]
    minutos: list[list[float]]
    fuente: str                      # "osrm" | "haversine_x1.4"

    def idx(self, id_: str) -> int:
        return self.ids.index(id_)


@dataclass(frozen=True)
class ClimaVereda:
    prob_lluvia_max: float           # % máximo en horas de jornada
    precipitacion_mm: float          # mm acumulados en horas de jornada
    # Pronóstico hora a hora en la jornada: {"07": {"prob": 13, "mm": 0.0}, ...}
    por_hora: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class Puntaje:
    vereda_id: str
    prioridad: float
    vulnerabilidad: float
    accesibilidad: float
    equidad: float
    dias_sin_visita: int | None
    lluvia_fuerte: bool
    penalizada_por_lluvia: bool
    en_descanso: bool = False        # visitada hace menos de dias_minimos_entre_visitas


@dataclass(frozen=True)
class Parada:
    posicion: int
    vereda_id: str
    nombre: str
    corregimiento: str
    tramo_km: float
    tramo_min: float
    llegada: str
    salida: str
    puntaje: Puntaje


@dataclass
class ResultadoRuta:
    paradas: list[Parada]
    regreso_km: float
    regreso_min: float
    distancia_total_km: float
    tiempo_viaje_min: float
    tiempo_total_min: float          # viaje + atención
    hora_regreso: str
    costo_heuristico_min: float
    costo_optimo_min: float
    brecha_vs_optimo_pct: float
    descartadas: list[dict] = field(default_factory=list)
    ranking: list[Puntaje] = field(default_factory=list)
