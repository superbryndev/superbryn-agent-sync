"""Provider config translators.

Unlike the Pipecat/LiveKit adapters (which read live runtime objects),
SaaS voice-agent platforms (Vapi, Retell, ElevenLabs, Bland, Bolna, ...)
keep agent config in their cloud. Fetch the agent JSON from the
provider's own API, then hand it to the matching translator to get an
AgentSyncManifest:

>>> from superbryn import Superbryn
>>> from superbryn.translators import vapi
>>> raw = requests.get("https://api.vapi.ai/assistant/ID", headers=...).json()
>>> manifest = vapi.manifest_from_assistant(raw)
>>> Superbryn(api_key="sk_agent_...").sync(manifest)

All translators are best-effort: unknown/missing fields degrade to a
sparser manifest, never an error.

Hooman Labs and Shunya Labs do not publish agent-management read APIs
yet — use :func:`superbryn.translators.generic.manifest_from_prompt`
with those sources instead.
"""

from . import bland, bolna, elevenlabs, generic, retell, vapi

__all__ = ["vapi", "retell", "elevenlabs", "bland", "bolna", "generic"]
