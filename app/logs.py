import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Una línea JSON por registro (SPEC §7.2). Los campos propios llegan en
    `extra={"fields": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    """Los loggers `app.*` escriben JSON a stdout, que Render captura.

    Los de uvicorn conservan su formato: el start command de Render se capturó
    a mano y no recibe `--log-config`.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
