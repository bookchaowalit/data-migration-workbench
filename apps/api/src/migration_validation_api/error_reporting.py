"""Opt-in Sentry error reporting for the local API (errors only, no traces, no PII).

Off unless ``SENTRY_DSN`` is set and the ``sentry`` extra is installed
(``pip install -e ".[sentry]"``). Every event passes :func:`scrub_event`, an allowlist:
exception types and stack frame locations, the request method and path, and messages from
:data:`ALLOWED_MESSAGES` only (anything else becomes ``[redacted]``). Exception values,
local variables, query strings, headers, bodies, user data, breadcrumbs and extras are
dropped, so uploaded rows, file names and column names never leave the machine.
"""

from __future__ import annotations

import os
from importlib import import_module
from typing import Any
from urllib.parse import urlsplit

# The API sends no messages of its own today (exceptions only); add static texts here if it does.
ALLOWED_MESSAGES: frozenset[str] = frozenset()
_TOP_LEVEL_KEYS = frozenset(
    {
        "event_id",
        "timestamp",
        "level",
        "platform",
        "logger",
        "environment",
        "release",
        "transaction",
        "tags",
    }
)
_FRAME_KEYS = ("filename", "module", "function", "lineno", "in_app")


def scrub_event(event: dict[str, Any], hint: object = None) -> dict[str, Any]:
    """Allowlist ``before_send``: keep only fields that cannot carry uploaded data."""

    clean: dict[str, Any] = {
        key: value for key, value in event.items() if key in _TOP_LEVEL_KEYS
    }
    if "exception" in event:
        values = []
        for value in (event["exception"] or {}).get("values") or []:
            frames = ((value.get("stacktrace") or {}).get("frames")) or []
            values.append(
                {
                    "type": value.get("type"),
                    "stacktrace": {
                        "frames": [
                            {k: f[k] for k in _FRAME_KEYS if k in f} for f in frames
                        ]
                    },
                }
            )
        clean["exception"] = {"values": values}
    request = event.get("request")
    if isinstance(request, dict):
        url = request.get("url")
        clean["request"] = {
            "method": request.get("method"),
            "url": urlsplit(url).path if isinstance(url, str) else None,
        }
    message = event.get("message")
    if message is None and isinstance(event.get("logentry"), dict):
        message = event["logentry"].get("message")
    if message is not None:
        clean["message"] = message if message in ALLOWED_MESSAGES else "[redacted]"
    return clean


def init_error_reporting() -> bool:
    """Initialise Sentry when configured; return whether it is on."""

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        sdk = import_module("sentry_sdk")
    except ImportError:
        return False
    sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
        send_default_pii=False,
        traces_sample_rate=0.0,
        max_breadcrumbs=0,
        before_send=scrub_event,
    )
    return True
