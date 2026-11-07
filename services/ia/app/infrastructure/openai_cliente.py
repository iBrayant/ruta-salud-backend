"""Adaptador ModeloLenguaje: API de OpenAI (Chat Completions) vía HTTP.

Solo se envían datos agregados de la ruta (veredas, tiempos, puntajes). Nunca
datos de pacientes ni del usuario; las preguntas pasan antes por el filtro de PII.
"""
from __future__ import annotations

import httpx

from ..application.casos_uso import IANoDisponible
from ..application.ports import RespuestaLLM


class ModeloOpenAI:
    def __init__(self, api_key: str | None, modelo: str, precio_entrada_1m: float, precio_salida_1m: float,
                 base_url: str = "https://api.openai.com/v1", timeout_s: float = 30) -> None:
        self._key = api_key
        self.modelo = modelo
        self.disponible = bool(api_key)
        self._p_in, self._p_out = precio_entrada_1m, precio_salida_1m
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout_s

    async def completar(self, sistema: str, usuario: str, json: bool = False, max_tokens: int = 700) -> RespuestaLLM:
        if not self._key:
            raise IANoDisponible("Sin API key")
        cuerpo: dict = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "max_completion_tokens": max_tokens,
        }
        if not self.modelo.startswith(("o", "gpt-5")):  # los modelos de razonamiento no aceptan temperature
            cuerpo["temperature"] = 0.2
        if json:
            cuerpo["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                r = await http.post(self._url, json=cuerpo, headers={"Authorization": f"Bearer {self._key}"})
            if r.status_code >= 400:
                # No se registra el cuerpo completo: puede contener eco del prompt
                raise IANoDisponible(f"OpenAI respondió {r.status_code}: {r.json().get('error', {}).get('code')}")
            d = r.json()
            u = d.get("usage", {})
            return RespuestaLLM(
                texto=d["choices"][0]["message"]["content"] or "",
                tokens_entrada=int(u.get("prompt_tokens", 0)),
                tokens_salida=int(u.get("completion_tokens", 0)),
                modelo=d.get("model", self.modelo),
            )
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise IANoDisponible(f"Error de comunicación con OpenAI: {type(e).__name__}") from e

    def costo_usd(self, tokens_entrada: int, tokens_salida: int) -> float:
        return tokens_entrada / 1e6 * self._p_in + tokens_salida / 1e6 * self._p_out
