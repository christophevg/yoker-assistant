# Functional Analyst Review — PR #1 Feedback (yoker.toml removal)

**Scope:** Scoped re-review of P1-001 acceptance criteria after the PR-feedback
change that deleted `yoker.toml` and updated documentation
(README.md, TODO.md, analysis/functional.md) to reflect plugin registration in
the user's `~/.yoker.toml` instead of a repo-level config.

**Date:** 2026-07-19

## 1. P1-001 Acceptance Criteria — Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `make help` lists targets | PASS | Ran `make help`; all standard targets listed (build, check, clean, env-dev, env-run, format, help, lint, pre-publish, publish, run, test, typecheck, …). yoker.toml removal has no bearing on Makefile targets. |
| `make env-dev` installs | PASS (by inspection) | `make env-dev` resolves deps from `pyproject.toml` / `uv.lock`; no dependency on `yoker.toml`. The deleted file was not referenced by any install step. |
| `make test` runs | PASS | Ran `make test`: `1 passed in 1.75s` (`tests/test_import_safety.py::test_package_imports`). The criterion's "zero tests passing" wording is a pre-existing deviation — the single import-safety test was already present before this PR-feedback change and is not a regression introduced here. |
| `python -m yoker_assistant` imports without error, exits cleanly when no config | PASS | Ran `uv run python -m yoker_assistant`; printed `yoker-assistant: not configured yet (see P2-005).` and exited with code 0. |

### `__main__.py` stub — confirmed

The stub in `src/yoker_assistant/__main__.py` does ONLY:
```python
print("yoker-assistant: not configured yet (see P2-005).")
sys.exit(0)
```
It does NOT import yoker, does NOT read any `yoker.toml` (neither repo-level nor
`~/.yoker.toml`), and does NOT construct an `Agent`. The deletion of the
repo-level `yoker.toml` therefore cannot affect this code path.

### `tests/test_import_safety.py` — confirmed

The test asserts only:
- `hasattr(yoker_assistant, "__YOKER_MANIFEST__")`
- `yoker_assistant.__YOKER_MANIFEST__.tools == []`

No config loading, no yoker runtime import, no `yoker.toml` dependency. The test
passes after the deletion.

## 2. Documentation Accuracy & Consistency

### README.md
- The `yoker.toml` bullet is replaced with a `~/.yoker.toml` bullet that
  correctly explains yoker's config resolution order
  (`~/.yoker.toml` and `./yoker.toml`, not the package install location).
- **Minor forward-looking inaccuracy:** the README states "A `yoker.toml.example`
  in this repo documents the required lines" in the present tense, but
  `yoker.toml.example` does not yet exist in the repo. It is a P1-002
  deliverable. This is a P1-002 concern, not a P1-001 acceptance issue.

### TODO.md (P1-002 entry)
- P1-002's yoker.toml bullet and acceptance criterion are rewritten to reflect
  the user-config approach: document the required `~/.yoker.toml` lines and
  provide a `yoker.toml.example` as reference. Consistent with the analysis
  document and with the README.

### analysis/functional.md
- §2.3.1, §3.3 (line 295), §5.2 (retitled `~/.yoker.toml`), §8 Q12, and §8.1
  are all updated to describe plugin registration in the user's `~/.yoker.toml`
  with the rationale (uvx deployment model, cwd/home resolution, clobber risk).
- Internally consistent with README and TODO.

The three documents are consistent with each other regarding the new
plugin-registration location.

## 3. Regressions

None identified. Specifically:
- No code in `src/yoker_assistant/` referenced the deleted `yoker.toml`.
- No test referenced the deleted file.
- No Makefile target referenced the deleted file.
- `make test` still passes; `python -m yoker_assistant` still exits 0.

## 4. Remaining References to a Repo-Level `yoker.toml`

A `grep` for `yoker.toml` across the repo surfaces several residual references
in FUTURE tasks and in historical review documents:

### Future-task references (TODO.md)
- **P2-008 (lines 152-153, 160):** "Register it via the package's own
  `yoker.toml [plugins]`" and "Loadable as a yoker tool via `yoker.toml [plugins]`".
  These are stale relative to the new approach but describe work that has not
  been done yet. They will be naturally corrected when P2-008 is implemented
  (the corrected pattern is already documented in §2.3.1 of the analysis and in
  P1-002's revised bullet, which P2-008 depends on).
- **P2-009 (line 179):** "in the consumer's `yoker.toml`" — this is actually
  correct: it refers to an EXTERNAL consumer's own config, not this package's
  repo-level config. Acceptable as written.
- **P4-001 (line 294):** "in `yoker.toml`" — stale; should read `~/.yoker.toml`
  for consistency. A documentation task that will be corrected when P4-001 is
  implemented (it explicitly cross-references §2.3.1, which is already
  corrected).

### Analysis document (functional.md)
- **Line 273 (§3.3 porting map):** "via `yoker.toml [plugins]` / `--with pkgq`"
  — a stale shorthand. The same section's surrounding prose and §2.3.1/§5.2
  already establish the `~/.yoker.toml` location, so a reader has the correct
  context, but the shorthand is inconsistent with the rest of the document.

### Historical review documents (reporting/p1-001-project-skeleton/)
- `functional-analyst-review.md` and `summary.md` reference the yoker.toml
  self-trust entry as PASS and list `yoker.toml` in the project structure.
  These are HISTORICAL snapshots of the original P1-001 review and should NOT
  be retroactively edited — they reflect what was true at the time of that
  review. They are superseded by this PR-review document.

### Assessment
The residual references in P2-008, P4-001, and the §3.3 porting-map shorthand
do NOT affect P1-001's acceptance criteria. P1-001 is the project skeleton
task; the corrected plugin-registration pattern is already documented in the
authoritative sections (§2.3.1, §5.2, §8 Q12 of the analysis, and the P1-002
bullet of TODO.md) that the future tasks depend on. The stale shorthands are
cosmetic inconsistencies in not-yet-started work, not acceptance blockers.

**Recommendation (non-blocking):** When P2-008 / P4-001 are picked up, update
their `yoker.toml` references to `~/.yoker.toml` for consistency. Optionally,
fix the §3.3 line-273 shorthand now to keep the analysis document internally
uniform.

## 5. Verdict

**APPROVED.** The change satisfies all of P1-001's acceptance criteria with no
regressions:

- `make help`, `make test`, and `python -m yoker_assistant` all behave
  correctly; `make env-dev` is unaffected by inspection.
- The `__main__.py` stub does not load yoker config — confirmed by code
  inspection and by running the module (exits 0).
- The `test_import_safety.py` test has no config dependency — confirmed by code
  inspection and by running `make test` (passes).
- README.md, TODO.md, and analysis/functional.md are mutually consistent in
  describing the user-config approach.
- Residual `yoker.toml` references exist only in future-task descriptions
  (P2-008, P4-001) and one analysis shorthand (§3.3 line 273), plus historical
  review snapshots that should not be edited. These are not P1-001 blockers.