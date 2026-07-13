"""superbryn — SuperBryn agent config sync SDK.

>>> from superbryn import Superbryn, Manifest
>>> manifest = (
...     Manifest.builder(source="custom")
...     .set_identity(name="Support Agent", type="inbound", agent_modality="voice")
...     .set_llm(provider="openai", model="gpt-4o", temperature=0.7)
...     .set_policy_guardrails("# Guardrails\\n...")
...     .build()
... )
>>> Superbryn(api_key="sk_agent_...").sync(manifest)

Framework adapters are lazy submodules — ``superbryn.pipecat`` and
``superbryn.livekit`` import only if the respective framework is
installed in the customer's environment.
"""

from .__about__ import __version__
from .canonical import canonicalize, compute_manifest_hash
from .client import AsyncSuperbryn, Superbryn
from .errors import (
    AmbiguousScanError,
    AuthenticationError,
    BusinessRuleError,
    ConfigurationError,
    ManifestValidationError,
    NotFoundError,
    RateLimitError,
    ScopeError,
    SuperbrynAPIError,
    SuperbrynError,
)
from .manifest import Manifest, ManifestBuilder, load_manifest_schema

__all__ = [
    "__version__",
    "Superbryn",
    "AsyncSuperbryn",
    "Manifest",
    "ManifestBuilder",
    "load_manifest_schema",
    "canonicalize",
    "compute_manifest_hash",
    "SuperbrynError",
    "SuperbrynAPIError",
    "ConfigurationError",
    "AmbiguousScanError",
    "AuthenticationError",
    "ScopeError",
    "NotFoundError",
    "ManifestValidationError",
    "BusinessRuleError",
    "RateLimitError",
]
