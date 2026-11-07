"""Adaptador: veredas desde el JSON oficial precargado (data/veredas.json, solo lectura)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..domain.entities import ID_HOSPITAL, Hospital, Vereda


class RepositorioVeredasJSON:
    def __init__(self, ruta: str | Path) -> None:
        crudo = Path(ruta).read_bytes()
        self._version = f"{json.loads(crudo)['meta']['version']}+{hashlib.sha256(crudo).hexdigest()[:12]}"
        d = json.loads(crudo)
        h = d["meta"]["hospital"]
        self._hospital = Hospital(ID_HOSPITAL, h["nombre"], h["lat"], h["lon"])
        self._detalle = d["veredas"]
        self._veredas = [
            Vereda(
                id=v["id"],
                nombre=v["nombre"],
                corregimiento=v["corregimiento"],
                lat=v["lat"],
                lon=v["lon"],
                vulnerabilidad=v["vulnerabilidad"]["indice"],
                componentes=v["vulnerabilidad"]["componentes"],
                tipo_via=v["via_acceso"]["tipo"],
            )
            for v in d["veredas"]
        ]
        if not 10 <= len(self._veredas) <= 15:
            raise ValueError("El conjunto debe tener entre 10 y 15 veredas")

    def hospital(self) -> Hospital:
        return self._hospital

    def listar(self) -> list[Vereda]:
        return list(self._veredas)

    def version(self) -> str:
        return self._version

    def detalle(self) -> list[dict[str, Any]]:
        return self._detalle
