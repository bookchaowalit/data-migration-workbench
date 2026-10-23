"""Opt-in Sentry for the local API: inert without SENTRY_DSN, allowlist scrubber."""

from __future__ import annotations

import sys
import types

import pytest
import uvicorn
from migration_validation_api import cli, error_reporting
from migration_validation_api.error_reporting import init_error_reporting, scrub_event


def test_scrubber_keeps_exception_type_and_frames_only():
    event = {
        "level": "error",
        "message": "row 'สมชาย ใจดี' 081-234-5678 failed",
        "user": {"ip_address": "203.0.113.9"},
        "request": {
            "method": "POST",
            "url": "http://127.0.0.1:8765/reconcile?file=customers.csv",
            "headers": {"Cookie": "a=b"},
            "data": "id,name\n1,สมชาย",
        },
        "breadcrumbs": {"values": [{"message": "uploaded customers.csv"}]},
        "extra": {"rows": 10},
        "exception": {
            "values": [
                {
                    "type": "KeyError",
                    "value": "'customer_email'",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "reconcile.py",
                                "function": "reconcile",
                                "lineno": 9,
                                "vars": {"row": "x"},
                            }
                        ]
                    },
                }
            ]
        },
    }

    clean = scrub_event(event)

    assert clean["exception"]["values"] == [
        {
            "type": "KeyError",
            "stacktrace": {
                "frames": [
                    {"filename": "reconcile.py", "function": "reconcile", "lineno": 9}
                ]
            },
        }
    ]
    assert clean["request"] == {"method": "POST", "url": "/reconcile"}
    assert clean["message"] == "[redacted]"
    for dropped in ("user", "breadcrumbs", "extra"):
        assert dropped not in clean
    flat = repr(clean)
    for leaked in (
        "สมชาย",
        "081-234-5678",
        "203.0.113.9",
        "customers.csv",
        "customer_email",
        "Cookie",
    ):
        assert leaked not in flat


def test_scrubber_lets_allowlisted_messages_through(monkeypatch):
    monkeypatch.setattr(
        error_reporting, "ALLOWED_MESSAGES", frozenset({"static app message"})
    )
    assert (
        scrub_event({"message": "static app message"})["message"]
        == "static app message"
    )
    assert scrub_event({"message": "anything else"})["message"] == "[redacted]"
    assert (
        scrub_event({"logentry": {"message": "x %s", "params": ["secret"]}})["message"]
        == "[redacted]"
    )


def test_off_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_error_reporting() is False


def test_init_uses_the_scrubber(monkeypatch):
    calls: list[dict[str, object]] = []
    fake = types.ModuleType("sentry_sdk")
    fake.init = lambda **kwargs: calls.append(kwargs)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/1")

    assert init_error_reporting() is True
    assert calls[0]["before_send"] is scrub_event
    assert calls[0]["send_default_pii"] is False
    assert calls[0]["traces_sample_rate"] == 0.0


def test_cli_initialises_error_reporting_before_serving(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(
        cli, "init_error_reporting", lambda: order.append("sentry") or False
    )
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: order.append("serve"))
    cli.main(["--port", "0"])
    assert order == ["sentry", "serve"]


@pytest.mark.parametrize("dsn", ["", "   "])
def test_blank_dsn_is_off(monkeypatch, dsn):
    monkeypatch.setenv("SENTRY_DSN", dsn)
    assert init_error_reporting() is False
