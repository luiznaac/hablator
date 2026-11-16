from __future__ import annotations

import os

import pytest

# The test profile never exports: set it before any test module imports the app.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http,database")
# `API_AUTH` has no default in code (it is the provider secret); tests supply the dev fixture.
os.environ.setdefault("API_AUTH", "dev-hablator-mailgun-key")


@pytest.fixture(autouse=True)
def _quiet_logging() -> None:
    from hablator.usecase.commons.logging import configure_logging

    configure_logging("WARNING", json=False)
