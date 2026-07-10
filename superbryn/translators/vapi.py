"""Vapi assistant → AgentSyncManifest.

Input is the assistant JSON from ``GET https://api.vapi.ai/assistant/:id``:
- system prompt:  ``model.messages[role=system].content``
- LLM:            ``model.provider`` / ``model.model`` / ``model.temperature`` / ``model.maxTokens``
- STT:            ``transcriber.provider`` / ``transcriber.model`` / ``transcriber.language``
- voice:          ``voice.provider`` / ``voice.voiceId``
- tools:          ``model.tools[]``
"""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest
from ._util import assemble, clean_block, get_path, normalize_tools


def manifest_from_assistant(
    assistant: dict[str, Any], *, phone_number: str | None = None
) -> Manifest:
    model = assistant.get("model") if isinstance(assistant.get("model"), dict) else {}
    transcriber = (
        assistant.get("transcriber") if isinstance(assistant.get("transcriber"), dict) else {}
    )
    voice = assistant.get("voice") if isinstance(assistant.get("voice"), dict) else {}

    prompt = None
    messages = model.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "system":
                content = message.get("content")
                if isinstance(content, str):
                    prompt = content
                break

    llm = clean_block(
        {
            "provider": model.get("provider"),
            "model": model.get("model"),
            "temperature": model.get("temperature"),
            "max_tokens": model.get("maxTokens"),
        }
    )
    stt = clean_block(
        {
            "provider": transcriber.get("provider"),
            "model": transcriber.get("model"),
            "language": transcriber.get("language"),
        }
    )
    voice_block = clean_block(
        {
            "provider": voice.get("provider"),
            "voice_id": voice.get("voiceId") or voice.get("voice_id"),
        }
    )

    return assemble(
        "vapi",
        source_agent_id=assistant.get("id") if isinstance(assistant.get("id"), str) else None,
        llm=llm,
        stt=stt,
        voice=voice_block,
        name=assistant.get("name") if isinstance(assistant.get("name"), str) else None,
        prompt=prompt,
        tools=normalize_tools(model.get("tools")),
        primary_language=get_path(assistant, "transcriber", "language"),
        phone_number=phone_number,
    )
