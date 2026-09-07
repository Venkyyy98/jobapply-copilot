from __future__ import annotations

import logging
import re
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"jac_live_[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(authorization|x-openai-api-key|x-jac-token)(['\"\s:=]+)([^,'\"\s}]+)"),
]


def redact_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def install_log_redaction() -> None:
    redacting_filter = RedactingFilter()
    # Uvicorn access logs use a structured args tuple; a generic redaction
    # filter would corrupt it and produce a traceback for every request.
    for logger_name in ("fastapi", "app"):
        logging.getLogger(logger_name).addFilter(redacting_filter)


def public_error_detail(exc: Exception) -> str:
    text = redact_text(str(exc))
    if re.search(r"api[_\s-]?key|authentication|unauthorized|incorrect api key|invalid api key", text, re.I):
        return "AI provider authentication failed. Check the API key and try again."
    if re.search(r"rate limit|quota", text, re.I):
        return "AI provider rate limit reached. Try again later or use another valid key."
    return "The request could not be completed safely. Please try again."
