# Changelog

All notable changes to this project are documented in this file. The
format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `docs/` folder with Sphinx + MyST + `sphinx_rtd_theme` configuration for
  ReadTheDocs (P4-001).
- `docs/tutorial.md` — the full build-story narrative (12 sections).
- `docs/architecture.md`, `docs/porting-map.md`, `docs/security.md`,
  `docs/configuration.md`, `docs/api.md`, `docs/installation.md`,
  `docs/quickstart.md`, `docs/changelog.md`, `docs/index.md`.
- `.readthedocs.yaml` ReadTheDocs build configuration.
- README rewritten as the lean front-door (per `c3:readme`) with a
  Documentation section linking the full docs on ReadTheDocs.

## [0.1.0] — 2026-07-23

### Added
- **P1-001** — uv Python project skeleton (`pyproject.toml`, `src/`
  layout, console script `yoker-assistant`, standard Makefile targets).
- **P1-002** — runtime dependencies (`yoker>=0.8.0`, `simple-email-gw>=0.3.0`,
  `pkgq>=0.3.2`); local-path dev-wiring via `[tool.uv.sources]`;
  `yoker.toml.example` and `.env.example` reference templates.
- **P1-003** — errata fixes: renamed `EMAIL_RECIPIENT_ADDRESSES` →
  `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in `.env.example` and `README.md`;
  `analysis/functional.md` corrections (§2.2, §2.4, §4.3, §4.4). The
  originally-scoped `Mailbox` wrapper class was descoped per owner feedback.
- **P1-004** — agent construction + one-time session setup. The loop
  constructs yoker's `Agent` directly (no `Assistant` wrapper); the
  one-time `Initialize` turn is inlined in the loop.
- **P2-001** — ported the assistant agent definition to
  `src/yoker_assistant/agents/assistant.md`; the `tools:` frontmatter was
  reworked to the bounded yoker set; `pkgq:find` (not `find_package`)
  used as the plugin tool name.
- **P2-008** — implemented the `md_to_html` tool as a yoker tool in
  `src/yoker_assistant/tools.py`, exposed via `__YOKER_MANIFEST__` in
  `src/yoker_assistant/__init__.py`. The conversion logic is vendored
  from `c3/bin/md-to-html.py` per owner instruction, with an HTML-escaping
  fix for XSS prevention.
- **P2-009** — verified the dual-mode / external plugin load: a separate
  minimal yoker consumer loads `yoker-assistant` as a plugin and calls
  `yoker_assistant:md_to_html`.
- **P2-005 / P2-006 / P2-007** — the main loop, the handoff payload
  builder, and the reply sending with correct threading (combined
  implementation per owner directive). The loop polls IMAP for `UNSEEN`,
  hands each email to the agent as the next user message in the persistent
  session, branches four ways on the reply, sends via `smtp.reply_email`
  with `html_body=` and `in_reply_to=`, marks read, archives. Connect/
  disconnect bookend each iteration.
- **P3-001** — tests for the handoff contract (`tests/test_handoff.py`):
  assert `build_message` produces the documented format (From/Subject/Date
  + body; NO `Instructions:` block).
- **P3-002** — tests for the polling logic (`tests/test_loop.py`): with
  fake `IMAPClient`/`SMTPClient` stubs and a fake `Agent`, assert the loop
  fetches unseen, calls `process`, sends via `smtp.reply_email` with
  `html_body=` (not `body=`, not `send_email`), marks read, archives, in
  order; skips the send when the agent returns an empty reply body.
- **S-01** — `SECURITY.md` documenting the `__YOKER_MANIFEST__` change
  review process (blast-radius assessment, capability review, version
  pinning, review checklist).
- **S-02** — `make pre-publish` guard rejecting non-registry source URLs
  in built sdist/wheel metadata (`file://`, VCS schemes, `@ <url>`,
  `path =`); also rejects relative image paths in `README.md` and
  verifies `pyproject.toml` version matches `__init__.py` `__version__`.

### Decisions
- **Descoped `Mailbox` wrapper** (P1-003): wrapping two existing classes
  in a third class added no benefit for a demo/tutorial. The loop calls
  `IMAPClient`/`SMTPClient` directly.
- **Descoped `Assistant` wrapper** (P1-004): same useless-wrapper
  pattern. The loop constructs `Agent` directly; the one-time setup is an
  inlined `await agent.process(_INITIALIZE_PROMPT)`.
- **Dropped `pa-session`** (P2-004): yoker's persistent context manager
  carries session state natively across `process()` calls; no external
  state file needed.
- **Reused `c3/bin/md-to-html.py`** (P2-008, owner instruction): did not
  reinvent the markdown-to-HTML converter; vendored the existing logic
  with an HTML-escaping fix.

[Unreleased]: https://github.com/christophevg/yoker-assistant/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/christophevg/yoker-assistant/releases/tag/v0.1.0