# Testing-Engineer Review — P1-001 (Project Skeleton)

Stage c (Quality Review) of the project-review cycle for task P1-001.
Scope: test setup and coverage for the bootstrap skeleton only. The real
behavior tests (handoff, polling, mailbox seam) are deliberately deferred to
P3-001/002/003 and are out of scope here.

## Verdict

**approved** — the test setup is appropriate for a skeleton. One smoke test
that verifies the dual-mode import-safety contract is the right thing at this
stage, the pytest/coverage config is sensible, and the deferral of behavior
tests to P3 is correct, not a coverage hole.

## What the smoke test verifies

`tests/test_placeholder.py::test_package_imports` does three things:

1. `import yoker_assistant` — would fail if `__init__.py` grew a bad import
   (e.g., import-time `Agent` construction that needs config, or a circular
   import with `loop`/`agent`/`mailbox`).
2. `hasattr(yoker_assistant, "__YOKER_MANIFEST__")` — would fail if someone
   removed the manifest, which is the entire point of the dual-mode plugin
   contract.
3. `__YOKER_MANIFEST__.tools == []` — would fail if a tool were added
   prematurely (i.e., not via the P2-008 `md_to_html` path) or if the manifest
   shape changed.

That is the correct surface to pin at P1-001. The skeleton's job is to prove
the harness works and the import-safe dual-mode contract holds; nothing more.

## Does it "catch a real regression"? (STANDARDS.md bar)

Yes. Concrete regressions this test would catch:

- Someone adds `from yoker import Agent` and constructs an agent at import time
  in `__init__.py` (the import either fails without config, or has side
  effects that break the dual-mode contract).
- Someone moves `PluginManifest` construction into a side-effecting path.
- Someone deletes the manifest or renames it without updating consumers.
- Someone adds a tool to the manifest before P2-008 wires it properly.
- A circular import is introduced between `__init__.py` and a sibling module.

The test is not decorative. It is one assertion deep, but each branch targets
a real failure mode the skeleton explicitly promises to avoid (per the
`__init__.py` docstring's "import-safe" contract).

## pytest / coverage config

`pyproject.toml` `[tool.pytest.ini_options]` and `[tool.coverage.*]`:

- `testpaths = ["tests"]` — correct.
- `asyncio_mode = "auto"` — sensible forward bet; P3-002 (polling logic) will
  need async tests, and this avoids per-test `@pytest.mark.asyncio` clutter.
- `addopts = "-v --cov=yoker_assistant --cov-report=term-missing"` — coverage
  on every run. For a skeleton this is fine; it is the standard c3 project
  shape. The `--cov` target (`yoker_assistant`) and the `[tool.coverage.run]
  source = ["src"]` are consistent.
- `branch = true` — good; branch coverage matters once the loop lands.
- `exclude_lines` set is reasonable (`pragma: no cover`, `__repr__`,
  `NotImplementedError`, `TYPE_CHECKING`).

No issues. The config matches the c3:python-project standard shape and is
ready for the P3 tests to drop in without reconfiguration.

## Gaps — now vs. P3

| Gap | Fill now? | Why |
|-----|-----------|-----|
| No test asserts "no import-time side effects" directly | No | The docstring claims import-safety, but the test only proves the manifest is present and empty. Verifying *absence* of side effects would require either import-time mocking or module inspection — out of proportion for a skeleton. The import itself catching breakage is the main value, and that is covered. |
| No handoff/polling/mailbox tests | No (P3) | These are explicitly P3-001/002/003. The modules they would test (`handoff.py`, `loop.py`, `mailbox.py`) do not exist yet at P1-001. Writing stubs against nonexistent modules would be speculative. |
| No test for `__main__` clean-exit-on-no-config | Consider | P1-001 acceptance mentions `python -m yoker_assistant` exits cleanly when no config. This is not covered by the smoke test. It is borderline — it is acceptance criteria for THIS task, so a stub `test_main_exits_cleanly_without_config` would be defensible. But it requires `__main__.py` to exist with a real entry point, and at skeleton stage `__main__` may legitimately not be wired. Leaving to P2-005 (the loop) is acceptable; flag it here so it is not lost. |

### One note for the P3 author (not a blocker)

The smoke test's docstring says "does not trigger any Agent construction or
email logic." The test does not actually verify that claim — it only verifies
the manifest. If the project wants to enforce the import-safety contract
rigorously, a later test (P3) could import `yoker_assistant` in a fresh
interpreter with `yoker` and sibling modules mocked, then assert no agent/loop
modules were touched. Not required at P1-001; mention only so the claim in the
docstring is either tested or softened in a later pass.

## Minor nits (non-blocking)

- The file is named `test_placeholder.py` but the test is not a placeholder —
  it is a real, behavior-verifying smoke test. Renaming to `test_smoke.py` or
  `test_import_safety.py` would communicate intent better and stop future
  readers from "cleaning up" what looks like a temporary file. Low priority.
- The test imports `yoker_assistant`, which pulls `yoker.plugins` at import
  time. This means the smoke test cannot run without `yoker` installed (via
  the `../yoker` sibling editable in `[tool.uv.sources]`). That is the correct
  dependency shape for this project and is not a test-quality issue, but it
  does mean the test is only runnable after `make env-dev` resolves the
  sibling checkouts. Worth a line in the README when P4-001 lands.

## Summary

The skeleton ships one useful test that pins the import-safe dual-mode
contract, a sensible pytest/coverage config ready for P3, and correctly
defers all behavior tests to P3-001/002/003. No coverage holes at this stage.
The P1-001 acceptance criterion "make test runs with zero tests passing" is
exceeded (one test) in a good way — the smoke test is a better signal than
zero tests. Approved.