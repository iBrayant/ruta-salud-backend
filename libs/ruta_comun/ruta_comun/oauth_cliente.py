"""Cliente OAuth 2.0 *client credentials* para llamadas servicio a servicio."""
from __future__ import annotations

import asyncio
import time

import httpx


class ClienteCredenciales:
    def __init__(self, token_url: str, client_id: str, client_secret: str) -> None:
        self._url = token_url
        self._id = client_id
        self._secret = client_secret
        self._token: str | None = None
        self._expira = 0.0
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if self._token and time.time() < self._expira - 30:
                return self._token
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.post(
                    self._url,
                    data={"grant_type": "client_credentials"},
                    auth=(self._id, self._secret),
                )
                r.raise_for_status()
                datos = r.json()
            self._token = datos["access_token"]
            self._expira = time.time() + int(datos.get("expires_in", 60))
            return self._token
