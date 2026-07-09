"""Generic prompt-first translator.

For platforms without a public agent-management read API (Hooman Labs,
Shunya Labs today) or any custom stack: supply the system prompt and
whatever pipeline facts you know, get a manifest back.

>>> from superbryn.translators import generic
>>> manifest = generic.manifest_from_prompt(
...     open("prompt.txt").read(),
...     source="hooman-labs",
...     name="Support Agent",
...     llm={"provider": "openai", "model": "gpt-4o"},
... )
"""

from __future__ import annotations

from typing import Any

from ..manifest import SYNC_SOURCES, Manifest
from ._util import assemble


def manifest_from_prompt(
    prompt: str,
    *,
    source: str = "custom",
    source_agent_id: str | None = None,
    name: str | None = None,
    llm: dict[str, Any] | None = None,
    stt: dict[str, Any] | None = None,
    tts: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    primary_language: str | None = None,
    phone_number: str | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
) -> Manifest:
    if source not in SYNC_SOURCES:
        raise ValueError(f"source must be one of {SYNC_SOURCES}, got {source!r}")
    return assemble(
        source,
        source_agent_id=source_agent_id,
        llm=llm,
        stt=stt,
        tts=tts,
        voice=voice,
        name=name,
        prompt=prompt,
        tools=tools,
        primary_language=primary_language,
        phone_number=phone_number,
        policy_guardrails=policy_guardrails,
        additional_details=additional_details,
    )
