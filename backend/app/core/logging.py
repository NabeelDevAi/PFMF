"""Structured logging (Tier 2 #11; architecture §11: "structured logs
with no financial values and no PII, request IDs only").

One JSON object per line, correlated by request_id via a contextvar that
RequestIdMiddleware sets at the start of every request -- no need to
thread a request id through every function call by hand; anyio
propagates contextvars into the threadpool a sync route runs in, so this
works whether the log call happens in the async middleware layer or deep
inside a sync service.

What this module cannot enforce mechanically: call sites must never pass
an email, password, or amount_minor as `extra`. That stays a discipline,
same as the engine-purity rule was before import-linter -- there is no
tool here that inspects *values*, only structure.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Every attribute a stdlib LogRecord carries by default. Anything else
# on the record came from a call site's `extra={...}` and is included
# in the JSON output automatically.
_STANDARD_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
    }
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
