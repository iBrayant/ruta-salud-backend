"""Contratos HTTP (Pydantic). Validación estricta: campos desconocidos se rechazan."""
from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.entities import ParametrosJornada


class SolicitudRuta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: date = Field(description="Fecha de la jornada")
    alpha: float = Field(0.7, ge=0, le=1, description="Peso de la vulnerabilidad frente a la accesibilidad")
    gamma: float = Field(0.15, ge=0, le=0.5, description="Peso de la equidad (días sin visita)")
    dias_minimos_entre_visitas: int = Field(7, ge=0, le=60)
    n_veredas: int = Field(5, ge=1, le=7)
    minutos_atencion: int = Field(45, ge=15, le=120)
    minutos_jornada: int = Field(480, ge=120, le=720)
    hora_inicio: str = Field("07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    considerar_lluvia: bool = True

    @field_validator("fecha")
    @classmethod
    def _rango_fecha(cls, v: date) -> date:
        hoy = date.today()
        if not hoy - timedelta(days=30) <= v <= hoy + timedelta(days=60):
            raise ValueError("La fecha debe estar entre 30 días atrás y 60 días adelante")
        return v

    def a_dominio(self) -> ParametrosJornada:
        return ParametrosJornada(**self.model_dump())


class SolicitudSimulacion(SolicitudRuta):
    n_jornadas: int = Field(10, ge=1, le=30)

    def a_dominio(self) -> ParametrosJornada:
        return ParametrosJornada(**self.model_dump(exclude={"n_jornadas"}))
