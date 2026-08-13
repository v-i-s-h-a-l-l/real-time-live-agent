"""Readiness must fail loudly when a session could not actually run."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


def test_all_three_pipeline_stages_are_required(monkeypatch):
    """Speech in, reasoning, and speech out are each unrecoverable if absent."""
    monkeypatch.setattr(
        config,
        "_REQUIRED_KEYS",
        {"SARVAM_API_KEY": "", "CEREBRAS_API_KEY": "", "CARTESIA_API_KEY": ""},
    )
    assert config.missing_required_keys() == [
        "CARTESIA_API_KEY",
        "CEREBRAS_API_KEY",
        "SARVAM_API_KEY",
    ]


def test_tts_key_is_not_forgotten():
    """A session with no Cartesia key connects but can never speak."""
    assert "CARTESIA_API_KEY" in config._REQUIRED_KEYS


def test_failover_key_is_optional():
    """Groq only backs up Cerebras, so its absence must not block a session."""
    assert "GROQ_API_KEY" not in config._REQUIRED_KEYS


def test_nothing_missing_when_keys_are_present(monkeypatch):
    monkeypatch.setattr(
        config,
        "_REQUIRED_KEYS",
        {"SARVAM_API_KEY": "s", "CEREBRAS_API_KEY": "c", "CARTESIA_API_KEY": "t"},
    )
    assert config.missing_required_keys() == []


def test_production_wildcard_cors_is_warned(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["*"])
    warnings = config.config_warnings()
    assert any("FRONTEND_ORIGIN" in note for note in warnings)


def test_local_wildcard_cors_is_silent(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["*"])
    assert config.config_warnings() == []


def test_pipeline_metrics_are_off_in_production(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    assert config.collect_pipeline_metrics() is False
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    assert config.collect_pipeline_metrics() is True
