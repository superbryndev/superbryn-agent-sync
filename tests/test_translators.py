import pytest

from superbryn.translators import bland, bolna, elevenlabs, generic, retell, vapi


def test_vapi_assistant():
    assistant = {
        "id": "asst-1",
        "name": "Vapi Agent",
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.6,
            "maxTokens": 512,
            "messages": [{"role": "system", "content": "You are helpful."}],
            "tools": [
                {
                    "function": {
                        "name": "lookup",
                        "description": "d",
                        "parameters": {"type": "object"},
                    }
                },
            ],
        },
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "en-US"},
        "voice": {"provider": "cartesia", "voiceId": "v-1"},
    }
    manifest = vapi.manifest_from_assistant(assistant, phone_number="+15551234567")
    assert manifest["source"] == "vapi"
    assert manifest["source_agent_id"] == "asst-1"
    assert manifest["llm"] == {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.6,
        "max_tokens": 512,
    }
    assert manifest["stt"] == {"provider": "deepgram", "model": "nova-2", "language": "en-US"}
    assert manifest["voice"] == {"provider": "cartesia", "voice_id": "v-1"}
    config = manifest["config"]
    assert config["identity"] == {"name": "Vapi Agent"}
    assert config["behavior"] == {"prompt": "You are helpful."}
    assert config["tools"] == [{"name": "lookup", "description": "d", "schema": {"type": "object"}}]
    assert config["language"] == {"primary_language": "en-US"}
    assert config["telephony"] == {"phone_number": "+15551234567"}


def test_retell_agent_with_llm():
    agent = {
        "agent_id": "ag-1",
        "agent_name": "Retell Agent",
        "voice_id": "11labs-Adrian",
        "language": "en-US",
    }
    llm = {
        "model": "gpt-4o",
        "general_prompt": "Be nice.",
        "states": [{"name": "intro", "state_prompt": "Greet the caller."}],
        "general_tools": [{"name": "end_call", "description": "End"}],
    }
    manifest = retell.manifest_from_agent(agent, llm)
    assert manifest["source"] == "retell"
    assert manifest["llm"]["model"] == "gpt-4o"
    assert manifest["voice"] == {"provider": "retell", "voice_id": "11labs-Adrian"}
    assert "Be nice." in manifest["config"]["behavior"]["prompt"]
    assert "## State: intro" in manifest["config"]["behavior"]["prompt"]
    assert manifest["config"]["tools"] == [{"name": "end_call", "description": "End"}]


def test_retell_agent_without_llm():
    manifest = retell.manifest_from_agent({"agent_id": "ag-2", "language": "hi-IN"})
    assert "llm" not in manifest
    assert manifest["config"]["language"] == {"primary_language": "hi-IN"}


def test_elevenlabs_agent():
    agent = {
        "agent_id": "el-1",
        "name": "EL Agent",
        "conversation_config": {
            "agent": {
                "language": "en",
                "prompt": {"prompt": "You are calm.", "llm": "gemini-2.0-flash", "tools": []},
            },
            "tts": {"voice_id": "voice-9", "model_id": "eleven_turbo_v2"},
        },
    }
    manifest = elevenlabs.manifest_from_agent(agent)
    assert manifest["source"] == "elevenlabs"
    assert manifest["llm"] == {"provider": "elevenlabs", "model": "gemini-2.0-flash"}
    assert manifest["tts"] == {
        "provider": "elevenlabs",
        "model": "eleven_turbo_v2",
        "voice_id": "voice-9",
    }
    assert manifest["voice"] == {"provider": "elevenlabs", "voice_id": "voice-9"}
    assert manifest["config"]["behavior"] == {"prompt": "You are calm."}


def test_bland_agent_wrapped():
    manifest = bland.manifest_from_agent(
        {
            "agent": {
                "agent_id": "bl-1",
                "prompt": "Do things.",
                "voice": "maya",
                "model": "base",
                "language": "en",
            }
        }
    )
    assert manifest["source"] == "bland"
    assert manifest["source_agent_id"] == "bl-1"
    assert manifest["llm"] == {"provider": "bland", "model": "base"}
    assert manifest["voice"] == {"provider": "bland", "voice_id": "maya"}
    assert manifest["config"]["behavior"] == {"prompt": "Do things."}


def test_bolna_agent():
    agent = {
        "id": "bo-1",
        "agent_name": "Bolna Agent",
        "agent_prompts": {
            "task_1": {"system_prompt": "Task one."},
            "task_2": {"system_prompt": "Task two."},
        },
        "tasks": [
            {
                "tools_config": {
                    "llm_agent": {
                        "llm_config": {"provider": "openai", "model": "gpt-4o", "temperature": 0.4}
                    },
                    "synthesizer": {
                        "provider": "elevenlabs",
                        "provider_config": {"voice": "Rachel"},
                    },
                    "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "en"},
                }
            }
        ],
    }
    manifest = bolna.manifest_from_agent(agent)
    assert manifest["source"] == "bolna"
    assert manifest["llm"] == {"provider": "openai", "model": "gpt-4o", "temperature": 0.4}
    assert manifest["stt"] == {"provider": "deepgram", "model": "nova-2", "language": "en"}
    assert manifest["voice"] == {"provider": "elevenlabs", "voice_id": "Rachel"}
    prompt = manifest["config"]["behavior"]["prompt"]
    assert "Task one." in prompt and "Task two." in prompt


def test_generic_prompt_manifest():
    manifest = generic.manifest_from_prompt(
        "You are a support agent.",
        source="hooman-labs",
        name="HL Agent",
        llm={"provider": "openai", "model": "gpt-4o"},
        policy_guardrails="# Rules",
    )
    assert manifest["source"] == "hooman-labs"
    assert manifest["config"]["policy_guardrails"] == "# Rules"
    assert manifest["config"]["behavior"] == {"prompt": "You are a support agent."}


def test_generic_rejects_unknown_source():
    with pytest.raises(ValueError):
        generic.manifest_from_prompt("x", source="not-a-platform")


def test_translators_never_raise_on_garbage():
    assert vapi.manifest_from_assistant({}) == {"source": "vapi"}
    assert retell.manifest_from_agent({}) == {"source": "retell"}
    assert elevenlabs.manifest_from_agent({}) == {"source": "elevenlabs"}
    assert bland.manifest_from_agent({}) == {"source": "bland"}
    assert bolna.manifest_from_agent({}) == {"source": "bolna"}
