"""yoker-assistant — a personal assistant that communicates by email.

This package is yoker-as-SDK: Python owns the email loop and calls yoker as a
library. It is ALSO a yoker plugin provider (dual-mode): the
``__YOKER_MANIFEST__`` below exposes this package's own tools to any yoker
consumer, including itself.

This module is import-safe: importing it must NOT trigger any Agent
construction, email logic, or loop logic. Those live in ``__main__``,
``loop``, and ``agent``. The manifest only declares tool
functions — no side effects at import time.
"""

from yoker.plugins import PluginManifest

from yoker_assistant.tools import md_to_html

__version__ = "0.1.0"

__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)

__all__ = ["__YOKER_MANIFEST__", "__version__"]
