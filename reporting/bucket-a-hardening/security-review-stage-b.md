# Security Review — Stage b (Domain Review)

**Reviewer:** security-engineer
**Date:** 2026-07-23
**Scope:** S-01 (`SECURITY.md`), S-02 (`make pre-publish` guard effectiveness), README.md "Security configuration" subsection.
**Baseline:** `reporting/bucket-a-hardening/security-design-review.md` (Phase 3, APPROVED-with-changes) and `reporting/bucket-a-hardening/plan.md` (owner-approved bundle plan).
**Working-tree state reviewed:** `SECURITY.md` (untracked, 91 lines), `Makefile` (modified `pre-publish`), `README.md` (new subsection at lines 81-92).

## Verdict: APPROVE

All four Phase 3 adjustments are correctly reflected in the shipped `SECURITY.md`. The S-02 guard pattern is effective against the full PEP 508 direct-reference class, not just the two forms the developer negatively tested. No new classes or wrappers were introduced. No blocking findings.

## S-01 — `SECURITY.md` review

### Per-adjustment verification

| # | Adjustment (from Phase 3 review) | Present in `SECURITY.md` | Verification |
|---|---|---|---|
| 1 | Revert framing: immediate revert + retroactive exposure-window review (not "process bug") | Yes | Lines 68-73 quote exactly: "triggers (1) immediate revert of the change, and (2) a retroactive security review of what the unreviewed code did while live, covering the exposure window from merge to revert. CI does not enforce this — it is a reviewer judgment gate." The soft "process bug" framing is gone. |
| 2 | Scope widened to "manifest addition OR capability-changing edit" with pure-refactor carve-out; section renamed | Yes | Lines 20-26 widen the scope with the exact parenthetical "(new args, new side effects, new dependencies, or a change to the tool's reach)" and the pure-refactor carve-out. Section heading at line 10 is `__YOKER_MANIFEST__ Change Review Process` (renamed from "Addition"). |
| 3 | Disclosure response window: 72-hour ack / 30-day fix | Yes | Lines 5-8: "Expect an acknowledgement within 72 hours and a fix or mitigation plan within 30 days for the current release line. Do not publish until the fix is released unless we agree otherwise." |
| 4 | Deliberate Non-Additions note (no supported-versions table, no CVE section, no PGP/security.txt) | Yes | Lines 84-92 enumerate all four omissions and state the revisit trigger ("if a real CVE lands or multiple release lines emerge"). |

### Three pillars

- **Blast-radius** (lines 28-37): inputs/outputs/reach/failure-modes — substantive, 4 bullets, each names a concrete dimension. The "Does it leak secrets in error messages?" bullet under failure modes is the right Information-Disclosure probe.
- **Capability review** (lines 39-48): duplicates check, composition check against `yoker:git` / `yoker:write` / `yoker:webfetch`, bounded-args check. The composition check remains the doc's strongest item — it is the cross-tool exfil/persistence gate that a per-tool review would miss.
- **Version pinning** (lines 50-56): deterministic-for-pinned-version, no network-fetched code at call time, deps declared in `pyproject.toml` so `uv pip install yoker-assistant==<version>` reproduces. Correctly tied to the existing mechanism rather than inventing a new one.

All three pillars present and substantive.

### PR checklist actionability

Lines 58-66: 6 items, each a single concrete action. Item 1 correctly reads "for an addition or a capability-changing edit" (matches adjustment 2). Item 6 (`SECURITY.md` updated if the process itself changes) closes the self-referential gap. A contributor can follow this checklist without further guidance.

### Publishing Guards section

Lines 75-82: correctly references `make pre-publish` (S-02), names the four caught forms (`file://`, VCS schemes, direct `@ <url>` references, `path =`), and explains why the guard exists (defense-in-depth against `[tool.uv.sources]` discipline slips, which are structurally excluded from PyPI metadata anyway). Stays at 8 lines — within the "do not expand beyond ~7 lines" guidance from Phase 3.

### README "Security configuration" subsection

Lines 81-92 of `README.md`. Verified:
- Content is accurate and matches the approved plan text verbatim.
- Link `[SECURITY.md](SECURITY.md)` resolves — `SECURITY.md` exists at repo root, `README.md` is at repo root, relative path is correct.
- The subsection correctly distinguishes tool-trust (the `[plugins.trusted]` admission) from reply-safety (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`) and points to `make pre-publish` for the publish-time control. Three distinct concerns, no conflation.
- Placed at end of `## Configuration`, before `## License` — correct location per plan.

## S-02 — security effectiveness

### Does the guard catch the path-dep leakage class?

Yes. I tested the shipped grep pattern `(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )` against 14 representative `Requires-Dist:` / `Project-URL:` lines:

| Input form | Result |
|---|---|
| `yoker @ file://../yoker` | CATCH |
| `yoker @ git+https://...` | CATCH |
| `yoker @ https://example.com/...tar.gz` | CATCH |
| `yoker @ ssh://git@host/repo` | CATCH |
| `yoker @ /abs/path` | CATCH |
| `yoker @ ./rel/path` | CATCH |
| `yoker @ ../rel/path` | CATCH |
| `yoker @ file:///local; sys_platform == 'linux'` (with marker) | CATCH |
| `yoker @ git+ssh://...@v1.0` (compound VCS+ssh) | CATCH |
| `yoker>=0.8.0` (registry) | PASS |
| `pkgq>=0.3.2` (registry) | PASS |
| `Project-URL: Homepage, https://...` | PASS |
| `Project-URL: Repository, https://...` | PASS |

The `^Requires-Dist:.*@` sub-pattern is the workhorse: PEP 508 has no form for URL/path dependencies that omits `@`, so every direct reference is caught. The bare-scheme substrings (`file://`, `git\+`, etc.) are belt-and-suspenders that also catch leakage into non-`Requires-Dist` fields (e.g., a `Download-URL` typo). No false positives on legitimate registry deps or Project-URL HTTPS lines.

The developer's negative-path tests with `file://` and `git+` are representative of the two main classes (file scheme, VCS scheme) but do not exhaustively exercise every form. The `@`-anchored sub-pattern is what makes the guard complete; the two tested forms would have surfaced a broken pattern. I judge the verification sufficient — the residual untested forms (`https://`, `ssh://`, bare-path) are all subsumed by the same `@` anchor that `file://` exercises.

### Is `twine check` correctly positioned?

Yes. `twine check dist/*` runs first (line 74 of `Makefile`) and is scoped to rendering/required-field validation — it does NOT reject `Requires-Dist: yoker @ file://...`. The streaming `unzip -p` / `tar -xzOf` grep that follows is the actual path-dep guard. The SECURITY.md Publishing Guards section does not over-claim `twine check`'s role. Correct positioning.

### Could a contributor bypass the guard?

Three bypass paths exist, all acknowledged by the design and acceptable for a 0.1.0 personal package:

1. **`make publish`** invokes `pre-publish` as a sub-make (line 87: `@$(MAKE) pre-publish`) — NOT a bypass.
2. **`uv run twine upload dist/*` directly** bypasses the guard. This is a discipline gate, not an enforced gate. The SECURITY.md framing ("if discipline slips") and the Phase 3 review ("CI does not enforce this — it is a reviewer judgment gate") explicitly acknowledge this. Acceptable.
3. **`make publish-test`** (TestPyPI) does NOT invoke `pre-publish` — it goes straight to `twine upload --repository testpypi`. This is a minor gap: a path-dep leak to TestPyPI is less severe than to PyPI but is still a leak. **Classification: New (non-blocking).** Suggest adding `@$(MAKE) pre-publish` to `publish-test` in a follow-up. Not blocking for this bundle because TestPyPI artifacts are not what end users install, and the same `make pre-publish` discipline applies if run manually first.

The primary publish path (`make publish`) is guarded. The bypass risk is limited to direct `twine` invocation and the TestPyPI path, both of which are discipline-dependent — matching the documented threat model.

## Simplicity Check

**Wrapper Check:** No new classes or wrappers introduced. The changes are (a) a new markdown document, (b) a new README subsection, (c) a Makefile recipe appending a streaming-grep step. No Python code, no abstractions, no indirections. Passes.

**Owner-proposal alignment:** The owner's directive was to bundle implementation tasks tightly. `SECURITY.md` ships at 91 lines. The Phase 3 review's "~70 lines" estimate was for the pre-adjustment draft; the approved plan content (plan.md lines 381-474) is ~93 lines of markdown. The shipped 91 lines matches the approved plan, not the pre-adjustment estimate — no bloat beyond what the four adjustments required. The Deliberate Non-Additions section is the right push-back against premature policy-writing.

## Findings classification

| Finding | Classification | Action |
|---|---|---|
| All 4 Phase 3 adjustments present and correct | Verified | None |
| Three pillars present and substantive | Verified | None |
| README link resolves, content accurate | Verified | None |
| S-02 guard pattern effective across PEP 508 forms | Verified | None |
| `make publish-test` does not invoke `pre-publish` | New (non-blocking) | Add to backlog: guard TestPyPI path too. Low priority — TestPyPI is not the end-user install path. |
| Direct `twine upload` bypass | Accepted by design | None — discipline gate, documented as such |

## Positive observations

- The `^Requires-Dist:.*@` anchor is the right primary guard — it is complete for PEP 508 direct references and avoids the false-positive trap that scoping `https://` globally would create (Project-URL lines legitimately contain HTTPS).
- The streaming `unzip -p` / `tar -xzOf` approach replaces what would have been a silent no-op (`find dist -name METADATA` does not penetrate archives). The corrected recipe actually does what it claims.
- The composition check against `yoker:git` / `yoker:write` / `yoker:webfetch` remains the doc's strongest section — it is the only place that catches cross-tool exfiltration paths that a per-tool review would miss.
- "Unbounded tools are rejected by default" matches the bounded-args discipline already enforced in `tools.py` (the single declared tool, `md_to_html`, is `Annotated[str, Text(...)]` — no `**kwargs`).
- The Deliberate Non-Additions section correctly pushes back against premature policy-writing for a 0.1.0 package — no supported-versions table, no CVE section, no PGP, no `security.txt`. The revisit trigger is named.
- The revert framing now names the exposure-window review as a required follow-on, not just the revert — this is the sharpening the Phase 3 review asked for.