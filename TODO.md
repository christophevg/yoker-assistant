# TODO

## Release 0.1.0 — Initial PyPI Release

Everything needed to get the package published and on par with
yoker-writing-assistant.

### Done

- [x] **Fix 4 failing tests** in `tests/test_loop.py`
  - Replaced `test_process_one_logs_conversation_turns` with
    `test_process_one_outputs_handoff_to_ui` (asserts UI handler calls
    instead of removed log messages).
  - Patched module-level `ui` in `_mock_session` to a MagicMock with
    AsyncMock for `start()` — fixes the `Path.relative_to()` crash on
    MagicMock `source_path`.

- [x] **Update `yoker` dependency version**
  - `pyproject.toml` updated from `yoker>=0.8.0` to `yoker>=0.10.1`,
    matching the actual API surface used (`Session`, `UIBridge`,
    `UIHandler`, `get_yoker_config`).

- [x] **Remove `agent.py` placeholder stub**
  - Deleted `src/yoker_assistant/agent.py` — the agent construction
    lives in `loop.py` (per the P1-004 descope). No imports referenced it.

- [x] **Clean up untracked / uncommitted state**
  - `handler.py` committed (RichUIHandler implementation).
  - `PERSONAL.md` and `context/` added to `.gitignore` (runtime-generated).
  - All modified files committed.
  - Removed `# temporary - comment before publishing!` above
    `[tool.uv.sources]`.

- [x] **Fix typecheck errors in `handler.py`**
  - `output_stats` signature updated to match `UIHandler` protocol
    (added `usage_limits` parameter).
  - Added `output_content` method (was commented out, protocol requires it).
  - Added type annotation for `str_summary` inner function.
  - Replaced `Path.relative_to(walk_up=True)` with `os.path.relpath`
    (Python 3.10 compatibility).

- [x] **Fix hatchling >=1.30 build issue**
  - Added `core-metadata-version = "2.4"` to both sdist and wheel
    build targets in `pyproject.toml`.

- [x] **Verify `make check` and `make pre-publish` pass**
  - 48 tests green, lint clean, typecheck clean, build clean, no
    local-path leakage in built metadata.

- [x] **Verify ReadTheDocs build**
  - `.readthedocs.yaml` exists, `make docs` builds successfully.

### Remaining

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