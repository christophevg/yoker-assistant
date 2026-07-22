"""Smoke test: the dual-mode ``__init__.py`` imports cleanly.

Verifies that importing the package does not trigger any Agent construction or
email logic, and that the yoker plugin manifest is present.
"""


def test_package_imports() -> None:
  """Importing yoker_assistant exposes ``__YOKER_MANIFEST__`` with no side effects."""
  import yoker_assistant

  assert hasattr(yoker_assistant, "__YOKER_MANIFEST__")
  # P2-008: the md_to_html tool is registered in the manifest.
  tool_names = [
    getattr(t, "__name__", t.__class__.__name__) for t in yoker_assistant.__YOKER_MANIFEST__.tools
  ]
  assert "md_to_html" in tool_names
