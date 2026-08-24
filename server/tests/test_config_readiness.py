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
        {"SARVAM_API_KEY": "", "GROQ_API_KEY": "", "CARTESIA_API_KEY": ""},
    )
    assert config.missing_required_keys() == [
        "CARTESIA_API_KEY",
        "GROQ_API_KEY",
        "SARVAM_API_KEY",
    ]


def test_tts_key_is_not_forgotten():
    """A session with no Cartesia key connects but can never speak."""
    assert "CARTESIA_API_KEY" in config._REQUIRED_KEYS


def test_openai_is_required_for_llm():
    """Default LLM_PROVIDER=openai requires OPENAI_API_KEY, not Groq/Cerebras."""
    required_names = set(config._REQUIRED_KEYS)
    assert "OPENAI_API_KEY" in required_names
    assert "GROQ_API_KEY" not in required_names
    assert "CEREBRAS_API_KEY" not in required_names


def test_nothing_missing_when_keys_are_present(monkeypatch):
    monkeypatch.setattr(
        config,
        "_REQUIRED_KEYS",
        {"SARVAM_API_KEY": "s", "GROQ_API_KEY": "g", "CARTESIA_API_KEY": "t"},
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


def test_production_blockers_fail_closed(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", [])
    monkeypatch.setattr(config, "SESSION_SECRET", "")
    monkeypatch.setattr(config, "ALLOW_ANONYMOUS_WS", True)
    blockers = config.production_blockers()
    assert "FRONTEND_ORIGIN" in blockers
    assert "SESSION_SECRET" in blockers
    assert "ALLOW_ANONYMOUS_WS" in blockers


def test_production_wildcard_cors_blocked(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["*"])
    blockers = config.production_blockers()
    assert "FRONTEND_ORIGIN" in blockers


def test_pipeline_metrics_are_off_in_production(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    assert config.collect_pipeline_metrics() is False
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    assert config.collect_pipeline_metrics() is True


def test_pipeline_timing_defaults_match_previous_hardcodes():
    """Unset env keeps the values that used to be literals in pipeline.py."""
    assert config.VAD_START_SECS == 0.2
    assert config.VAD_STOP_SECS == 1.1
    assert config.STT_KEEPALIVE_TIMEOUT_SECS == 15.0
    assert config.STT_KEEPALIVE_INTERVAL_SECS == 5.0
    assert config.SARVAM_MIN_SPEECH_FRAMES == 6
    assert config.SARVAM_NEGATIVE_FRAMES_COUNT == 35
    assert config.SARVAM_NEGATIVE_FRAMES_WINDOW == 48
    assert config.SARVAM_PRE_SPEECH_PAD_FRAMES == 16
    assert config.AUDIO_GATE_DECAY_SECS == 0.35
    assert config.SILENCE_THRESHOLD_SECS == 15.0
    assert config.MEDIUM_SILENCE_THRESHOLD_SECS == 120.0
    assert config.LONG_SILENCE_THRESHOLD_SECS == 300.0
    assert config.USER_TURN_STOP_TIMEOUT_SECS == 3.0
    assert config.LLM_EMPTY_GUARD_TIMEOUT_SECS == 20.0
    assert config.CARTESIA_TTS_MODEL == "sonic-3.5"


def test_env_float_override_and_invalid_fallback(monkeypatch):
    monkeypatch.setenv("VAD_STOP_SECS", "1.5")
    assert config._env_float("VAD_STOP_SECS", 1.1) == 1.5
    monkeypatch.setenv("VAD_STOP_SECS", "nope")
    assert config._env_float("VAD_STOP_SECS", 1.1) == 1.1
    monkeypatch.setenv("VAD_STOP_SECS", "0")
    assert config._env_float("VAD_STOP_SECS", 1.1) == 1.1


def test_pipeline_reads_timing_from_config():
    source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "stop_secs=VAD_STOP_SECS" in source
    assert "model=CARTESIA_TTS_MODEL" in source
    assert "timeout_secs=LLM_EMPTY_GUARD_TIMEOUT_SECS" in source
    assert "stop_secs=1.1" not in source
    assert 'model="sonic-3.5"' not in source
    assert "timeout_secs=20.0" not in source
