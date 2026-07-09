"""Shared attribute-walking helpers for Pipecat extractors."""

from __future__ import annotations

from typing import Any

# Pipecat groups services as pipecat.services.<provider>.<role>
# (e.g. pipecat.services.deepgram.stt). Known-provider keyword map so
# subpackage layout changes don't break detection.
PROVIDER_KEYWORDS: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "gemini": "google",
    "azure": "azure",
    "groq": "groq",
    "together": "together",
    "deepgram": "deepgram",
    "assemblyai": "assemblyai",
    "cartesia": "cartesia",
    "elevenlabs": "elevenlabs",
    "rime": "rime",
    "playht": "playht",
    "sarvam": "sarvam",
}

MODEL_ATTRS = ("model_name", "model", "_model", "_settings.model", "settings.model")
VOICE_ATTRS = (
    "voice_id",
    "voice",
    "_voice_id",
    "_voice",
    "_settings.voice_id",
    "_settings.voice",
    "settings.voice_id",
    "settings.voice",
)


def read_attr_chain(source: Any, *names: str) -> Any:
    """First non-empty attribute along dotted candidate paths (never raises)."""
    for name in names:
        cur: Any = source
        for part in name.split("."):
            cur = getattr(cur, part, None)
            if cur is None:
                break
        if cur not in (None, ""):
            return cur
    return None


def provider_from_module(module: str) -> str | None:
    for needle, name in PROVIDER_KEYWORDS.items():
        if needle in module:
            return name
    return None


def service_role(processor: Any) -> str | None:
    """Which role (llm/stt/tts) a pipecat.services.* processor plays, if any."""
    module = type(processor).__module__ or ""
    if "pipecat.services." not in module:
        return None
    for role in ("stt", "tts", "llm"):
        if role in module:
            return role
    return None
