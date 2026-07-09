"""TTS block extractor for Pipecat services."""

from __future__ import annotations

from typing import Any

from ._shared import MODEL_ATTRS, VOICE_ATTRS, provider_from_module, read_attr_chain


def extract_tts(processor: Any) -> dict[str, Any] | None:
    module = type(processor).__module__ or ""
    block: dict[str, Any] = {}

    provider = provider_from_module(module)
    if provider:
        block["provider"] = provider

    model = read_attr_chain(processor, *MODEL_ATTRS)
    if isinstance(model, str) and model:
        block["model"] = model

    voice = read_attr_chain(processor, *VOICE_ATTRS)
    if isinstance(voice, str) and voice:
        block["voice_id"] = voice

    return block or None
