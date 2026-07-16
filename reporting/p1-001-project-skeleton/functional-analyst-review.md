# Functional Review — P1-001: Initialize uv Python project structure

**Reviewer:** functional-analyst
**Stage:** A (Functional Review, BLOCKING)
**Branch:** feature/p1-001-project-skeleton
**Date:** 2026-07-16
**Verdict:** approved

## Summary

The P1-001 skeleton is clean, minimal, and meets every acceptance criterion
from TODO.md. The dual-mode `__init__.py` discipline is correctly observed:
the manifest is defined with an empty tools list and no Agent/loop/email
logic is imported at package import time. Placeholders are one-line docstrings
pointing to the task that will fill them — no speculative abstractions, no
dead code. The yoker.toml self-trust entry and the .env.example recipient
whitelist are present and correct.

## Acceptance Criteria Check

### 1. `make help` lists the standard targets — PASS

All required targets are present and listed: `build`, `check`, `clean`,
`clean-all`, `env-dev`, `env-run`, `format`, `help`, `lint`, `pre-publish`,
`publish`, `run`, `test-all`, `test-cov`, `test`, `typecheck`. Extra targets
(`docs`, `docs-view`, `publish-test`, `install-pythons`) are harmless
additions; `install-pythons` is intentionally filtered out of the help
listing via `grep -v`.

Minor cosmetic note (non-blocking): the Makefile include of
`~/.claude/Makefile` emits two make warnings about overriding the `help`
target:
```
Makefile:92: warning: overriding commands for target `help`
/Users/xtof/.claude/Makefile:101: warning: ignoring old commands for target `help`
```
The project's own `help` target correctly wins, and the output is correct.
This is a pre-existing condition of the include pattern, not a P1-001
defect.

### 2. `make env-dev` installs all dependencies — PASS (trusted)

The developer reported `make env-dev` succeeds. I did not re-run it (slow,
per instructions). `make test` itself runs `uv sync --all-extras` as a
prerequisite and that completed successfully, which confirms the dependency
set resolves and installs. The local-path wiring for `yoker`,
`simple-email-gw`, and `pkgq` is configured under `[tool.uv.sources]` with
a clear comment to remove before publishing.

### 3. `make test` runs with clean exit — PASS

`make test` collects and runs 1 test (`tests/test_placeholder.py::
test_package_imports`) and passes. The smoke test is a useful addition
accepted per the task brief: it verifies the dual-mode import safety
contract (importing `yoker_assistant` exposes `__YOKER_MANIFEST__` with an
empty tools list and triggers no side effects). Coverage report shows
`__init__.py` at 100%, placeholders at 100% (empty modules), `__main__.py`
at 0% (uncovered stub — expected for a stub that exits).

### 4. `python -m yoker_assistant` imports and exits 0 with no config — PASS

`uv run python -m yoker_assistant` prints
`yoker-assistant: not configured yet (see P2-005).` and exits with code 0.
The `__main__.py` stub is minimal and correct.

## Additional Functional Checks

### Dual-mode `__init__.py` discipline — PASS

`src/yoker_assistant/__init__.py` contains only:
- A docstring explaining the import-safety contract.
- `from yoker.plugins import PluginManifest`.
- `__version__ = "0.1.0"`.
- `__YOKER_MANIFEST__ = PluginManifest(tools=[])` with a comment pointing
  to P2-008 for the `md_to_html` tool.
- `__all__ = ["__YOKER_MANIFEST__"]`.

No `Agent` construction, no loop logic, no email handling, no imports of
`agent`/`loop`/`mailbox`/`handoff`/`tools` modules. Verified by reading
the file and by running
`uv run python -c "import yoker_assistant; print(yoker_assistant.__YOKER_MANIFEST__)"`,
which returns `PluginManifest(tools=[], ...)` with no side effects.

### `yoker.toml` self-trust entry — PASS

`yoker.toml` contains:
```toml
[plugins]
enabled = true
packages = ["yoker_assistant", "pkgq"]

[plugins.trusted]
yoker_assistant = true
pkgq = true
```
The self-trust entry required for unattended dual-mode operation is
present. The `skills.directories = ["./skills"]` entry is also present.

### `.env.example` documents the recipient whitelist — PASS

`.env.example` documents `EMAIL_RECIPIENT_ADDRESSES=owner@example.com`
with a comment: "Whitelist of addresses the assistant may reply to
(simple-email-gw safety gate)." The other simple-email-gw config vars
(`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`,
`EMAIL_PASSWORD`) are present.

### No speculative abstractions / dead code — PASS

Placeholders (`tools.py`, `mailbox.py`, `agent.py`, `loop.py`,
`handoff.py`) are each a single module docstring pointing to the task
that will fill them. No stub classes, no half-built interfaces, no
unused imports. `py.typed` is present (empty marker file, correct).
`__main__.py` is a minimal stub. The package surface is as small as it
can be while still meeting the acceptance criteria.

## Findings

None blocking. One minor cosmetic note about the Makefile `help` override
warning, which is a property of the `~/.claude/Makefile` include pattern
and not a P1-001 defect.

## Verdict

**approved** — all four acceptance criteria met, dual-mode discipline
correctly observed, self-trust and recipient-whitelist configuration
present, no speculative abstractions. The skeleton is ready to support
the subsequent tasks (P1-002 through P2-008).