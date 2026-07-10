"""Bolna agent → AgentSyncManifest.

Input is the agent JSON from ``GET https://api.bolna.ai/v2/agent/:agent_id``:
- system prompt: ``agent_prompts.task_N.system_prompt`` (all tasks concatenated)
- LLM:           ``tasks[0].tools_config.llm_agent`` (model / provider / temperature)
- TTS/voice:     ``tasks[0].tools_config.synthesizer`` (provider / voice)
- STT:           ``tasks[0].tools_config.transcriber`` (provider / model / language)
"""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest
from ._util import assemble, clean_block, get_path


def _combine_prompts(agent_prompts: Any) -> str | None:
    if not isinstance(agent_prompts, dict):
        return None
    task_keys = sorted(
        (k for k in agent_prompts if k.startswith("task_")),
        key=lambda k: int(k.split("_")[-1]) if k.split("_")[-1].isdigit() else 0,
    )
    blocks = []
    for key in task_keys:
        prompt = get_path(agent_prompts, key, "system_prompt")
        if isinstance(prompt, str) and prompt.strip():
            blocks.append(prompt)
    return "\n\n---\n\n".join(blocks) or None


def manifest_from_agent(agent: dict[str, Any], *, phone_number: str | None = None) -> Manifest:
    tasks = agent.get("tasks") if isinstance(agent.get("tasks"), list) else []
    first_task = tasks[0] if tasks and isinstance(tasks[0], dict) else {}
    tools_config = (
        first_task.get("tools_config") if isinstance(first_task.get("tools_config"), dict) else {}
    )

    llm_agent = (
        tools_config.get("llm_agent") if isinstance(tools_config.get("llm_agent"), dict) else {}
    )
    # Newer Bolna shapes nest the LLM settings one level down.
    llm_details = (
        llm_agent.get("llm_config") if isinstance(llm_agent.get("llm_config"), dict) else llm_agent
    )
    synthesizer = (
        tools_config.get("synthesizer") if isinstance(tools_config.get("synthesizer"), dict) else {}
    )
    synth_config = (
        synthesizer.get("provider_config")
        if isinstance(synthesizer.get("provider_config"), dict)
        else synthesizer
    )
    transcriber = (
        tools_config.get("transcriber") if isinstance(tools_config.get("transcriber"), dict) else {}
    )

    llm = clean_block(
        {
            "provider": llm_details.get("provider") or llm_details.get("family"),
            "model": llm_details.get("model") or llm_details.get("llm_model"),
            "temperature": llm_details.get("temperature"),
            "max_tokens": llm_details.get("max_tokens"),
        }
    )
    stt = clean_block(
        {
            "provider": transcriber.get("provider") or transcriber.get("model_provider"),
            "model": transcriber.get("model"),
            "language": transcriber.get("language"),
        }
    )
    voice_id = synth_config.get("voice") or synth_config.get("voice_id")
    tts = clean_block(
        {
            "provider": synthesizer.get("provider"),
            "voice_id": voice_id,
            "model": synth_config.get("model"),
        }
    )

    return assemble(
        "bolna",
        source_agent_id=(
            agent.get("id") if isinstance(agent.get("id"), str) else agent.get("agent_id")
        ),
        llm=llm,
        stt=stt,
        tts=tts,
        voice=clean_block({"provider": synthesizer.get("provider"), "voice_id": voice_id})
        if voice_id
        else None,
        name=agent.get("agent_name") if isinstance(agent.get("agent_name"), str) else None,
        prompt=_combine_prompts(agent.get("agent_prompts")),
        primary_language=(
            synth_config.get("language")
            if isinstance(synth_config.get("language"), str)
            else transcriber.get("language")
            if isinstance(transcriber.get("language"), str)
            else None
        ),
        phone_number=phone_number,
    )
