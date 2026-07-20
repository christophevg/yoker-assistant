# Testing Engineer Review — P1-002 (Add runtime dependencies)

Branch: `feature/p1-002-runtime-deps`
Scope: dependency wiring + reference config docs. No new application logic.

## Acceptance criteria vs. evidence

| P1-002 acceptance | Evidence | Status |
|---|---|---|
| `make env-dev` resolves all deps | `uv.lock` committed; `uv run python -c "import yoker, simple_email_gw, pkgq"` succeeds (`yoker 0.8.0`, `simple_email_gw ok`, `pkgq ok`) | MET |
| README documents required `~/.yoker.toml` lines | `README.md` Configuration section shows `[plugins]`, `[plugins.trusted]`, `[skills]` with self-trust rationale | MET |
| `yoker.toml.example` provided with REFERENCE ONLY header and no real `api_key` | Header block present; `api_key` line commented with `REDACTED`; `tomllib.load` parses cleanly | MET |
| `make pre-publish` (or equivalent) confirms no `file://`/path deps in built sdist/wheel metadata | `uv build` produced wheel + sdist; `Requires-Dist` lines inspected in both `*.whl/METADATA` and `sdist/PKG-INFO` — only PyPI names (`yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2`), no `file:`, no `@ file://` | MET |

All four acceptance criteria are satisfied by the working tree.

## Existing test infrastructure

- `tests/test_import_safety.py::test_package_imports` — asserts `yoker_assistant` imports cleanly and `__YOKER_MANIFEST__.tools == []`.
- `make check` = format-check + lint + typecheck + test. Ran green: 1 passed.
- `pyproject.toml` configures `testpaths = ["tests"]`, `asyncio_mode = "auto"`, coverage over `src`.
- No `conftest.py` (none needed yet — no shared fixtures).

## Is the existing infrastructure sufficient for P1-002?

Yes. P1-002 is a dependency-wiring and reference-docs task. Its acceptance is
about *resolution* and *metadata hygiene*, not behavior. The existing
`test_package_imports` already transitively exercises dependency resolution:
`import yoker_assistant` only succeeds if `[project.dependencies]` is
installed (the `__init__.py` exposes `__YOKER_MANIFEST__`, which references
yoker's `PluginManifest`). If `uv sync` had failed to resolve any dep, the
test could not pass.

The behavior seams that would need real tests (mailbox, agent, handoff, loop)
are explicitly scheduled as P3-001/002/003. Adding them now would be out of
scope for P1-002 and would preempt those tasks.

## Should P1-002 add a runtime-deps smoke test?

**Recommendation: no. Non-blocking nice-to-have at most; I would not add it.**

A test of the form `import yoker; import simple_email_gw; import pkgq` was
considered. Arguments against:

1. **It tests pip/uv, not this package.** Resolving and installing declared
   dependencies is the package manager's job. The declared names are already
   checked by `uv lock` / `uv sync`; re-checking at import time in a test
   duplicates that and would only fail if pip/uv broke.
2. **`pkgq` is not directly imported by this package.** Per `functional.md`
   §2.3.1 and the `pyproject.toml` comment, `pkgq` is loaded by yoker as a
   plugin via `~/.yoker.toml [plugins]`. A bare `import pkgq` does not
   exercise the actual usage seam; it tests that pkgq is *installed*, which
   is already implied by `uv sync` succeeding.
3. **The existing package-import test already covers install resolution.**
   `import yoker_assistant` running under `make env-dev` proves the
   dependency set is resolvable and importable in the project's venv.
4. **Proportionality.** P1-002 ships no behavior. A smoke test here would be
   the only test in the suite for the next several tasks, and it would be
   testing the wrong thing (third-party installability). The behavior tests
   land in P3-001/002/003, where they belong.

If the owner wants belt-and-braces, a single short test asserting the three
declared names appear in `importlib.metadata.requires("yoker-assistant")`
would at least test *this package's* declaration (not pip's behavior). I'd
still consider it over-engineering for P1-002, but it's the least-bad
option if any smoke test is added.

## Edge cases in P1-002 scope

- **`yoker.toml.example` parseability.** It is documentation only (header
  says so, no real `api_key`). I confirmed it parses as valid TOML and
  yields the expected `plugins`/`trusted`/`skills` structure. Adding a
  pytest that `tomllib.load`s this file would catch a future typo for ~zero
  cost. **Non-blocking nice-to-have.** Not required by P1-002 acceptance.
  I lean against: testing doc-only files is the kind of low-value test the
  testing-engineer role exists to discourage (it tests "the file exists and
  is TOML", not behavior).
- **`.env.example` format.** Same shape: documentation, `KEY=VALUE`
  lines, no secrets. Parse-testing it is over-engineering. Not recommended.
- **Built-metadata leakage guard.** This IS in P1-002 acceptance ("`make
  pre-publish` or equivalent confirms no `file://`/path deps leak"). I
  verified it manually via `uv build` + METADATA inspection. Automating it
  as a test is explicitly the scope of **S-02** ("`make pre-publish` guard
  rejecting non-registry source URLs in built metadata"), which is a
  separate scheduled task. **Do not add it in P1-002** — it would preempt
  S-002 and belongs in the publish pipeline, not in `make test`.

## Coverage gaps vs. acceptance

None blocking. The deferred items are correctly deferred:

- **P3-001** (handoff contract tests) — awaits `handoff.py` behavior (P2-006).
- **P3-002** (polling loop tests with fake Mailbox/Assistant) — awaits the loop (P2-005).
- **P3-003** (mailbox seam integration tests) — awaits the seam (P1-003).
- **S-02** (publish-time metadata guard) — awaits its own task.

P1-002 introduces no behavior to test. The existing `test_import_safety`
plus the build-metadata inspection is proportionate evidence.

## Positive observations

- `test_import_safety.py` is well-targeted: it pins the dual-mode
  `__init__.py` discipline (manifest present, tools empty for now, no
  Agent construction at import time). This is exactly the kind of
  invariant worth a test, and it is the right test to keep as P2-008
  populates the manifest.
- `pyproject.toml` `[tool.mypy.overrides]` correctly ignores missing
  imports for `yoker.*`, `simple_email_gw.*`, `pkgq.*` — typecheck stays
  green without falsely testing third-party stubs.
- The `pyproject.toml` dependency comments are tight and explain *why*
  each pin is what it is (SDK surface, async client contract, plugin
  loading) — useful for reviewers without being verbose.

## Verdict

**approved**

No additional tests required for P1-002. The existing
`test_import_safety::test_package_imports` plus the build-metadata
inspection (performed in this review: wheel + sdist METADATA contain only
PyPI names, no `file://`/path leaks) satisfies the acceptance criteria.
Behavior tests are correctly deferred to P3-001/002/003; the
publish-time metadata guard is correctly deferred to S-02.

If the owner wants a smoke test, the least-overtesting form is
`importlib.metadata.requires("yoker-assistant")` containing the three
declared names — but I do not recommend adding it; it would test this
package's `pyproject.toml` rather than pip's behavior and is still
marginal value for a dependency-wiring task.