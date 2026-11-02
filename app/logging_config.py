import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

from app.config import settings

# Identifiant de la question en cours, ajouté automatiquement à chaque log
request_id_var = ContextVar("request_id", default=None)

# Attributs standard d'un message de log : tout ce qui s'ajoute vient de `extra=`
_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Écrit chaque message de log sur une seule ligne JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            data["request_id"] = request_id
        data.update(
            {k: v for k, v in record.__dict__.items() if k not in _STANDARD_FIELDS}
        )
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Envoie tous les logs de l'application, en JSON, sur la sortie standard."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)
