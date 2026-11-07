"""Logs estructurados en JSON (sin datos sensibles ni tokens)."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "servicio": getattr(record, "servicio", None) or record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            base["error"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


def configurar_logs(servicio: str, nivel: str = "INFO") -> logging.Logger:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(_FormatoJSON())
    raiz = logging.getLogger()
    raiz.handlers = [h]
    raiz.setLevel(nivel)
    return logging.getLogger(servicio)
