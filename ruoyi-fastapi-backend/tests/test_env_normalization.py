import pytest

from config.env import NormalizedBaseSettings, normalize_env_string


class DummySettings(NormalizedBaseSettings):
    quoted_url: str = ''
    quoted_port: int = 0


def test_normalize_env_string_strips_matching_quotes():
    assert normalize_env_string(" 'https://example.com/api' ") == 'https://example.com/api'
    assert normalize_env_string(' "/prod-api" ') == '/prod-api'
    assert normalize_env_string('plain-text') == 'plain-text'
    assert normalize_env_string(123) == 123


def test_normalized_base_settings_strips_wrapping_quotes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('QUOTED_URL', "'https://runtime.internal/v1'")
    monkeypatch.setenv('QUOTED_PORT', "'29099'")

    settings = DummySettings()

    assert settings.quoted_url == 'https://runtime.internal/v1'
    assert settings.quoted_port == 29099
