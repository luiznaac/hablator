"""The spec's env names: `MAILGUN__*` for the email channel and `AUTH__API_TOKEN` for the API.

Both secrets have no default in code, so their absence fails the boot loudly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hablator.application.settings import Settings


def test_mailgun_and_auth_read_the_spec_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILGUN__API_KEY", "key-123")
    monkeypatch.setenv("MAILGUN__API_URL", "https://api.mailgun.test/v3/dom/messages")
    monkeypatch.setenv("MAILGUN__FROM", "from@example.test")
    monkeypatch.setenv("MAILGUN__BCC", "bcc@example.test")
    monkeypatch.setenv("AUTH__API_TOKEN", "token-abc")

    settings = Settings(_env_file=None, app_env="test")

    assert settings.mailgun.api_key == "key-123"
    assert settings.mailgun.api_url == "https://api.mailgun.test/v3/dom/messages"
    assert settings.mailgun.from_email == "from@example.test"
    assert settings.mailgun.bcc_email == "bcc@example.test"
    assert settings.auth.api_token == "token-abc"


def test_missing_mailgun_api_key_fails_the_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAILGUN__API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="test")


def test_missing_api_token_fails_the_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH__API_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="test")
