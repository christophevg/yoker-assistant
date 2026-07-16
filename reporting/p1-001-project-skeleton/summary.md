# P1-001 — Project Skeleton

## What was implemented

Scaffolded the uv-managed Python project for `yoker-assistant` (yoker-as-SDK
mode, dual-mode plugin provider). The skeleton compiles, lints, type-checks,
and passes its import-safety test. `make check` is green.

## Key decisions

- **Dual-mode `__init__.py` discipline (manifest only).** `src/yoker_assistant/__init__.py`
  exposes `__YOKER_MANIFEST__` and nothing else. Importing the package triggers
  no agent construction, no email logic, no loop. Those live in `__main__`,
  `loop`, `agent`, and `mailbox`. The manifest declares tools; today the list is
  empty (the `md_to_html` tool arrives in P2-008).
- **Self-trust in `yoker.toml`.** `yoker_assistant` is listed under
  `[plugins.trusted]` so the package can consume its own tools as a plugin —
  the dual-mode contract. `pkgq` is trusted too.
- **Local dev deps via `[tool.uv.sources]`.** `pyproject.toml` pins runtime
  deps (`yoker`, `pkgq`) and dev deps (`pytest`, `pytest-asyncio`,
  `pytest-cov`, `ruff`, `mypy`) with a local source override for `yoker` so the
  sibling checkout is used during development.
- **Makefile completed to the c3:python-project standard.** `help`, `env-dev`,
  `env-run`, `format`, `lint`, `typecheck`, `test`, `test-cov`, `check`,
  `build`, `clean`, `clean-all`, `pre-publish`, `publish`, `run` targets.

## Files modified

- `pyproject.toml` — project metadata, deps, uv sources, tool config.
- `src/yoker_assistant/__init__.py` — dual-mode manifest, import-safe.
- `src/yoker_assistant/__main__.py` — entry point stub.
- `src/yoker_assistant/tools.py` — tool registration seam (placeholder).
- `src/yoker_assistant/mailbox.py` — email integration seam (placeholder).
- `src/yoker_assistant/agent.py` — agent construction seam (placeholder).
- `src/yoker_assistant/loop.py` — poll/parse/handoff/reply loop seam (placeholder).
- `src/yoker_assistant/handoff.py` — Python↔agent handoff seam (placeholder).
- `src/yoker_assistant/py.typed` — PEP 561 marker.
- `tests/test_import_safety.py` — asserts import is side-effect free.
- `.env.example` — documented env vars, no secrets.
- `yoker.toml` — backend, context, permissions, plugins (self-trust), skills.
- `README.md` — project intro.
- `Makefile` — completed to the c3:python-project standard.
- `reporting/p1-001-project-skeleton/functional-analyst-review.md`
- `reporting/p1-001-project-skeleton/testing-engineer-review.md`

## Pull request

https://github.com/christophevg/yoker-assistant/pull/1

## Review verdict

Approved — all stages (functional, testing). `make check` green.
