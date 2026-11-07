"""Casos de uso de auditoría."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from ..domain import cadena
from .ports import RepositorioEventos


class ServicioAuditoria:
    def __init__(self, repo: RepositorioEventos) -> None:
        self.repo = repo

    async def registrar(self, evento: dict[str, Any], servicio_origen: str) -> dict[str, Any]:
        datos = {**evento, "servicio_origen": servicio_origen}

        def construir(seq: int, hash_anterior: str) -> tuple[str, str]:
            ts = datetime.now().astimezone().isoformat(timespec="microseconds")
            return cadena.encadenar(datos, seq, ts, hash_anterior)

        return await self.repo.insertar_encadenado(construir, datos)

    async def listar(self, **filtros: Any) -> list[dict[str, Any]]:
        return await self.repo.listar(**filtros)

    async def obtener(self, seq: int) -> dict[str, Any] | None:
        return await self.repo.obtener(seq)

    async def verificar(self) -> dict[str, Any]:
        eslabones = [e async for e in self.repo.eslabones()]
        return asdict(cadena.verificar(eslabones))
