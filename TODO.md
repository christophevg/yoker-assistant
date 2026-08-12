# TODO

## Release 0.1.0 — Initial PyPI Release

Everything needed to get the package published and on par with
yoker-writing-assistant.

### Blocking

- [ ] **Fix 4 failing tests** in `tests/test_loop.py`
  - `test_process_one_logs_conversation_turns` — expects `INFO` log
    messages (`=== Incoming message (user turn) ===` / `=== Agent reply ===`)
    that no longer exist after the `RichUIHandler` migration. Either add the
    log lines back to `_process_one` or update the test to assert UI handler
    calls instead.
  - `test_run_proceeds_when_whitelist_enabled`,
    `test_run_continues_after_process_one_exception`,
    `test_run_connects_and_disconnects_per_iteration` — all fail with
    `ValueError: 'MagicMock/mock.agent.definition.source_path/...' and
    '/Users/...' have different anchors`. The `RichUIHandler.start()` calls
    `Path.relative_to()` on `agent.definition.source_path`, which is a
    MagicMock. Fix: patch `RichUIHandler` or set
    `agent.definition.source_path` to a real `Path` in the test mocks.

- [ ] **Update `yoker` dependency version**
  - `pyproject.toml` pins `yoker>=0.8.0` but the code uses `Session`,
    `UIBridge`, `UIHandler`, `get_yoker_config`, and other APIs from newer
    yoker releases. The sister project (`yoker-writing-assistant`) uses
    `yoker>=0.10.1`. Update the lower bound to match the actual API
    surface used.

- [ ] **Remove `agent.py` placeholder stub**
  - `src/yoker_assistant/agent.py` is a 3-line docstring-only stub left
    over from P1-001. The agent construction lives in `loop.py` (per the
    P1-004 descope). Delete the file and remove any references.

- [ ] **Clean up untracked / uncommitted state**
  - `handler.py` — new file, part of the RichUIHandler work; needs to be
    committed.
  - `PERSONAL.md` — runtime-generated, should be `.gitignore`d (not
    committed).
  - `context/` — runtime session data, should be `.gitignore`d.
  - Review all modified files (`Makefile`, `pyproject.toml`,
    `__main__.py`, `agents/assistant.md`, `loop.py`, `uv.lock`) and
    commit them.
  - Remove the `# temporary - comment before publishing!` comment above
    `[tool.uv.sources]` in `pyproject.toml` (but keep the section — the
    sister project keeps it too).

- [ ] **Verify `make check` and `make pre-publish` pass**
  - All tests green, lint clean, typecheck clean, build clean, no
    local-path leakage in built metadata.

- [ ] **Verify ReadTheDocs build**
  - `docs/` has the full Sphinx + MyST setup. Confirm `.readthedocs.yaml`
    exists and the docs build locally (`make docs`).

- [ ] **Publish to PyPI**
  - `make publish` (or `make publish-test` first to TestPyPI).
  - Create GitHub release tag `v0.1.0`.
  - Confirm `pip install yoker-assistant` works from a clean venv.

---

## Post-Release Backlog (deferred)

These are explicitly out of scope for the initial release. All were
listed as "Unsorted" in the original backlog and are non-blocking
enhancements.

- **HTML rendering polish** — CSS, inline styles, dark-mode friendliness
  for the `md_to_html` output. The first release ships unstyled HTML.
- **Attachment handling** — out of scope for the first pass.
- **Batch per-iteration processing** — multiple emails per loop
  iteration. First release is one email per iteration.
- **Multi-account email support** — single account only for now.
- **`make run-demo` target** — seed a local mailbox and run one iteration
  end-to-end for showcase purposes.