"""Extractor dispatch for known Pipecat service classes.

Each extractor reads a fixed allow-list of configuration attributes —
including private fields such as ``_settings``, ``_model`` and
``_voice_id`` where Pipecat services keep their settings. Credential
attributes (API keys, tokens, secrets) are never part of that list and
are never read or transmitted.
"""

from .llm import extract_llm
from .stt import extract_stt
from .tts import extract_tts

__all__ = ["extract_llm", "extract_stt", "extract_tts"]
