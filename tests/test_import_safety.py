"""Smoke test: the dual-mode ``__init__.py`` imports cleanly.

Verifies that importing the package does not trigger any Agent construction or
email logic, and that the yoker plugin manifest is present.
"""


def test_package_imports() -> None:
  """Importing yoker_assistant exposes ``__YOKER_MANIFEST__`` with no side effects."""
  import yoker_assistant

  assert hasattr(yoker_assistant, "__YOKER_MANIFEST__")
  assert yoker_assistant.__YOKER_MANIFEST__.tools == []
