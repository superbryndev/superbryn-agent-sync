"""ElevenLabs Conversational AI agent → AgentSyncManifest.

Input is the agent JSON from
``GET https://api.elevenlabs.io/v1/convai/agents/:agent_id``:
- system prompt:  ``conversation_config.agent.prompt.prompt``
- LLM model:      ``conversation_config.agent.prompt.llm``
- language:       ``conversation_config.agent.language``
- voice:          ``conversation_config.tts.voice_id``
- tools:          ``conversation_config.agent.prompt.tools[]``
"""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest
from ._util import assemble, clean_block, get_path, normalize_tools


def manifest_from_agent(agent: dict[str, Any], *, phone_number: str | None = None) -> Manifest:
    prompt = get_path(agent, "conversation_config", "agent", "prompt", "prompt")
    llm_model = get_path(agent, "conversation_config", "agent", "prompt", "llm")
    language = get_path(agent, "conversation_config", "agent", "language")
    voice_id = get_path(agent, "conversation_config", "tts", "voice_id")
    tts_model = get_path(agent, "conversation_config", "tts", "model_id")
    tools = get_path(agent, "conversation_config", "agent", "prompt", "tools")

    return assemble(
        "elevenlabs",
        source_agent_id=agent.get("agent_id") if isinstance(agent.get("agent_id"), str) else None,
        llm=clean_block({"provider": "elevenlabs", "model": llm_model}) if llm_model else None,
        tts=clean_block({"provider": "elevenlabs", "model": tts_model, "voice_id": voice_id})
        if (tts_model or voice_id)
        else None,
        voice=clean_block({"provider": "elevenlabs", "voice_id": voice_id}) if voice_id else None,
        name=agent.get("name") if isinstance(agent.get("name"), str) else None,
        prompt=prompt if isinstance(prompt, str) else None,
        tools=normalize_tools(tools),
        primary_language=language if isinstance(language, str) else None,
        phone_number=phone_number,
    )
