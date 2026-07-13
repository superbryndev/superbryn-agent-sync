"""Source-code extraction — works for EVERY provider.

You never know in advance what a provider's public API returns: some give
back the full agent config, others little more than an id — and some
(Hooman Labs, Shunya Labs today) have no agent-read API at all. Whatever
the API does or doesn't return, the customer's own code — the place where
they instantiate the provider's package/SDK with a prompt, model, voice —
is always available as a source of truth.

Two ways to use it:

- Sole source (no API, or API returned nothing useful):
  ``build_manifest_from_source(...)`` builds the whole manifest from code.
- Gap filler after any translator: ``fill_manifest_gaps(manifest, root)``
  scans the code and adds ONLY the fields the provider's API didn't
  provide; API-provided values always win.

This module statically scans source files and pulls those values out:

- **Python** files are parsed with ``ast`` — keyword arguments on any
  call (``prompt=``, ``instructions=``, ``model=``, ``voice_id=``, ...)
  are collected, simple variable references are resolved to their
  assigned string constants, and provider/role hints are taken from the
  called class name (e.g. ``DeepgramSTTService`` → stt/deepgram).
- **JS/TS** files are scanned with conservative regexes for the same
  keys in object-literal form (``prompt: "..."``, ``voiceId: '...'``).

>>> from superbryn import Superbryn
>>> from superbryn.codescan import build_manifest_from_source
>>> manifest = build_manifest_from_source(
...     "path/to/agent-project",
...     source="hooman-labs",
...     identity={"name": "Support Agent"},
... )
>>> Superbryn(api_key="sk_agent_...").sync(manifest)

Extraction is best-effort and read-only: unparseable files are skipped,
only values bound to the known config keys are collected (credential-style
keys are never in the key sets), and a scan that finds nothing produces a
source-only manifest.

Safety constraints:

- Prefer scanning the **specific agent file** over a whole project tree —
  everything the scan collects is uploaded to SuperBryn on sync.
- Symlinks are never followed (neither directories nor files), so a scan
  cannot escape the given root.
- When several distinct prompt-length strings compete for
  ``behavior.prompt``, the scan raises
  :class:`superbryn.errors.AmbiguousScanError` instead of guessing; pass
  ``on_ambiguity="longest"`` to opt back into longest-wins.
"""

from ..errors import AmbiguousScanError
from ._scan import ScanFindings, build_manifest_from_source, fill_manifest_gaps, scan_source

__all__ = [
    "AmbiguousScanError",
    "build_manifest_from_source",
    "fill_manifest_gaps",
    "scan_source",
    "ScanFindings",
]
