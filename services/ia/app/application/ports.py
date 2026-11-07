from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RespuestaLLM:
    texto: str
    tokens_entrada: int
    tokens_salida: int
    modelo: str


class ModeloLenguaje(Protocol):
    disponible: bool
    modelo: str

    async def completar(self, sistema: str, usuario: str, json: bool = False, max_tokens: int = 700
                        ) -> RespuestaLLM: ...
    def costo_usd(self, tokens_entrada: int, tokens_salida: int) -> float: ...


class Limites(Protocol):
    async def permitir_chat(self, usuario: str) -> bool: ...
    async def presupuesto_disponible(self) -> bool: ...
    async def consumir_tokens(self, n: int) -> None: ...


class FuenteRutas(Protocol):
    async def obtener(self, ruta_id: str, token_usuario: str) -> dict[str, Any] | None: ...


class RegistroAuditoria(Protocol):
    async def registrar(self, accion: str, actor: Any, recurso: str, detalle: dict[str, Any], ip: str = ...
                        ) -> dict[str, Any]: ...
