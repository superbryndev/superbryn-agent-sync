"""Extractor dispatch for known Pipecat service classes.

Each extractor reads **public attributes only** — API keys and other
secrets held by service objects are never read or transmitted.
"""

from .llm import extract_llm
from .stt import extract_stt
from .tts import extract_tts

__all__ = ["extract_llm", "extract_stt", "extract_tts"]
