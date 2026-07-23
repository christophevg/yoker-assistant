# API Review — Stage b (Domain Review: api-architect)

**Date:** 2026-07-23
**Reviewer:** api-architect agent
**Branch:** `feature/bucket-a-hardening`
**Scope:** S-02 (Makefile `pre-publish` streaming guard) + P3-001/P3-002 (test correctness from backend-correctness perspective)

## Verdict: APPROVE

The implementation matches the approved Phase 3 design exactly. No deviations, no scope creep, no new abstractions. The Makefile recipe is the streaming-`grep` approach I recommended; the tests correctly assert the `loop.py` contracts including the propagation behavior that underpins the API seam between `_process_one` and `run`.

## S-02 — Makefile `pre-publish` guard (lines 62-84)

### Criterion 1 — Wheel METADATA streaming
`unzip -p "$$whl" '*.dist-info/METADA'` (line 75-76). Correct. `unzip -p` streams the matched file to stdout without writing to disk; the quoted glob `'*.dist-info/METADATA'` is handled by `unzip`'s own pattern matcher, not the shell. Matches design review recommendation (v) exactly. ✅

### Criterion 2 — Sdist PKG-INFO streaming
`tar -xzOf "$$sdist" '*/PKG-INFO'` (line 76). Correct. Flags: `-x` extract, `-z` gunzip, `-O` to stdout, `-f` file. The `*/PKG-INFO` pattern matches `<name>-<ver>/PKG-INFO` inside the tarball. This is the correct file name (sdists contain `PKG-INFO`, not `METADATA` — the design review's correction of the original plan's wrong claim). ✅

### Criterion 3 — grep pattern completeness
Line 77: `(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )`

Matches the design review's recommended pattern verbatim. Verification:
- `^Requires-Dist:.*@` — the primary catch-all for PEP 508 direct references (file, path, URL, VCS, relative). Catches `yoker @ file://...`, `yoker @ git+https://...`, `yoker @ https://...`, `yoker @ /abs/path`, `yoker @ ../rel`. ✅
- `file://` — global substring; no legitimate metadata field contains it. ✅
- `git\+|hg\+|svn\+|bzr\+` — VCS scheme substrings; safe to flag globally. ✅
- `path =` — defense-in-depth per owner's acceptance wording; structurally excluded from built PyPI metadata but harmless. ✅
- The broken `^ \.\./` sub-pattern from the original proposal is correctly dropped. ✅
- `https://`/`http://`/`ssh://` are NOT matched globally — `Project-URL:` lines legitimately contain HTTPS. They are only caught via `^Requires-Dist:.*@`. ✅

Confirmed against `pyproject.toml` dependencies (`yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` — all registry names, no `@`): the positive path will pass. ✅

### Criterion 4 — `twine check` retained as complementary check
Line 74: `@uv run twine check dist/* >/dev/null`. Correctly retained BEFORE the streaming grep. The design review explicitly approved keeping `twine check` as a rendering/required-field check (it does NOT catch path deps). ✅

### Criterion 5 — Empty `dist/` handling
Two layers of defense:
1. `pre-publish: check build` (line 62) — `build` is now a Make dependency, so `dist/` is populated on standalone `make pre-publish`. This is the design review's recommended fix. ✅
2. `[ -e "$$whl" ]` / `[ -e "$$sdist" ]` guards inside the loops (lines 75-76) — if one artifact type is missing (e.g. wheel-only build), the glob literal `dist/*.whl` would otherwise be passed to `unzip` and error. The existence check short-circuits cleanly. ✅

### Criterion 6 — Multiple wheels/tarballs
`for whl in dist/*.whl; do ...; done` and `for sdist in dist/*.tar.gz; do ...; done` iterate all matches; the concatenated stream is piped to a single `grep`. Correct. In practice hatchling produces one of each, but the loop form is robust to duplicates. ✅

### Criterion 7 — Shell portability
- `unzip`: ships with macOS and most Linux distros. Available in the project's dev environment (`twine`/`build` deps already assume a POSIX toolchain). ✅
- `tar -xzOf`: the `-O` flag is supported by both macOS bsdtar and GNU tar. The `*/PKG-INFO` wildcard pattern is supported by both (bsdtar by default; GNU tar enables wildcards for list/extract by default in modern versions). ✅
- Minor note (not blocking): on very old GNU tar (<1.32) wildcards may need `--wildcards`. The project targets modern dev machines and CI — acceptable.
- The recipe uses POSIX `sh` constructs only (`for`, `[ -e ]`, `$(...)`, `||`, `&&`). No bashisms. ✅

### Criterion 8 — Error output diagnostic quality
On failure, the recipe prints:
```
ERROR: non-registry source URLs found in built metadata:
<grep -n output with line numbers and matching lines>
```
The grep `-n` line numbers are relative to the concatenated stream (wheel METADATA first, then sdist PKG-INFO), not per-file. This means the developer can see WHICH `Requires-Dist:` line leaked and the matching pattern, but must inspect the artifacts directly to know which file. The design review explicitly accepted this tradeoff per the Simplicity Principle ("per-file labels would add a wrapper; skip it"). ✅

The output is sufficient to diagnose: it shows the exact leaking line content (e.g. `Requires-Dist: yoker @ file://../yoker`), which makes the source obvious. The developer then runs `unzip -p dist/*.whl '*.dist-info/METADATA' | grep -n @` to locate it. Acceptable. ✅

### S-02 Summary
All 7 criteria pass. The implementation is a verbatim copy of the design-review-approved recipe. No new Python scripts, no temp dirs, no wrapper classes — exactly the slim Makefile snippet the Simplicity Principle demands.

## P3-001 / P3-002 — Test correctness (backend perspective)

### P3-001 — `test_build_message_omits_instructions_block` (lines 72-88)

**Contract being asserted:** the per-email handoff payload must NOT contain an `Instructions:` block. Identity/instructions live in the agent definition + the one-time session-setup turn (P1-004), not in each email's handoff.

**Assertion mechanism:** iterates `out.splitlines()` and asserts `not line.lower().startswith("instructions:")` for every line.

**Correctness:** `build_message` (loop.py:54-69) emits exactly four lines — `From:`, `Subject:`, `Date:`, blank line, then body. None start with `instructions:`. The test passes against current code and is a true regression guard: if someone reintroduces a c3-style `Instructions:` header in `build_message`, the test fires. ✅

**Bug fix verified:** the tautological `.endswith("instructions:")` assertion from the original proposal (which passed for any input) is NOT present. Only the meaningful per-line `startswith` loop remains. ✅

**Test input:** uses a realistic payload (`from`, `subject`, `date`, `body` all populated). The body `"Give me a status update."` doesn't accidentally start with `instructions:` — no false positive risk. ✅

### P3-002 — `test_process_one_send_failure_does_not_archive` (lines 237-250)

**Contract being asserted:** §7 error handling — if `smtp.reply_email` raises, the message is NOT marked read or archived. The exception propagates out of `_process_one` to `run()`'s per-message `except Exception:` block (loop.py:184-189), which logs and continues; the message stays UNSEEN for retry.

**Developer's pattern:** `pytest.raises(RuntimeError, match="smtp boom")` wrapping the `_process_one` call, followed by `mark_message.assert_not_awaited()` and `move_message.assert_not_awaited()`.

**Is `pytest.raises` the right pattern?** Yes. Verified against production code (loop.py:115-125, branch 4):
```python
await smtp.reply_email(...)      # raises here
await imap.mark_message(...)     # never reached
await imap.move_message(...)     # never reached
```
`_process_one` has no try/except — the exception propagates. The test asserts BOTH the propagation (via `pytest.raises`) AND the no-side-effect contract (via `assert_not_awaited`). This mirrors the real production flow: `run()`'s `except Exception:` catches whatever propagates.

**Alternative considered (patch `_process_one` to catch):** would test mock behavior, not real behavior. If `_process_one` ever grew a try/except that swallowed the exception, the patched-mock test would still pass while the real contract would be broken. The `pytest.raises` pattern catches that regression. ✅

**The docstring correctly documents the propagation contract:** "The exception propagates out of `_process_one` to run()'s per-message except block; the mark/archive calls are never reached." This is exactly the API seam between `_process_one` (raises) and `run` (catches). ✅

**Unused `monkeypatch` fixture:** correctly dropped per testing-engineer's Phase 3 review. The test uses only `_make_clients` and direct `AsyncMock(side_effect=...)` assignment. ✅

### P3-002 — Tightened ordering test (lines 209-234)

**Contract being asserted:** §7 ordering — send → mark → archive. A regression that swapped mark-before-send would break the reply-threading contract (marking read before the reply is sent could race with another poller).

**Assertion mechanism:** three `side_effect` lambdas appending to a shared `order` list, then `assert order == ["reply", "mark", "archive"]`.

**Correctness:** `AsyncMock`'s `side_effect` accepts a sync callable; the lambda appends to the list and returns `None`, which `AsyncMock` wraps as a coroutine result. The lambdas wrap the existing `_make_clients` stubs (which still return `{"status": "sent"}` / `True` from the underlying `return_value` — `side_effect` overrides this, but the production code doesn't inspect the return values of `mark_message`/`move_message`, only awaits them). ✅

**The test also retains the exact-args assertions** (`call.kwargs["to"]`, `["html_body"]`, `["in_reply_to"]`, etc.) below the ordering assertion — locking both the ordering AND the per-call contract. This is the tightened form the testing-engineer specified. ✅

**`side_effect` lambdas vs. `assert_awaited_once_with` ordering:** the original test only asserted each method was awaited once, not the order. The tightened form catches the swap regression. ✅

### P3-001/P3-002 Summary
All three tests correctly assert their respective `loop.py` contracts. The `pytest.raises` pattern is the right choice for the send-failure test (it verifies the real propagation seam). The ordering test correctly uses `side_effect` lambdas. No tautological assertions remain.

## Simplicity Check

### Wrapper Check
No new classes or wrappers introduced in this bundle. The diff is:
- `Makefile`: one target's recipe expanded with a streaming-grep block. No new Make targets, no new scripts.
- `tests/test_loop.py`: one new test function + one tightened test function. No new fixtures, no new helpers, no new test file.
- `src/yoker_assistant/loop.py`: NOT modified by this bundle (the tests assert existing contracts).

✅ Wrapper Check passes.

### Owner-Proposal Alignment
Owner's directive: "bundle almost all remaining tasks now. Maybe keep documentation for a separate follow-up PR."

The bundle includes S-01 (SECURITY.md + README subsection), which is documentation — but this was explicitly approved in the plan and is a security deliverable, not scope creep. The implementation introduces no extra abstractions, no extra indirections, no extra tooling beyond what the approved plan specifies. ✅

The `path =` sub-pattern in the grep is the only "paranoid defense-in-depth" addition, and it's retained explicitly because the owner's acceptance wording named it. The design review flagged it as paranoid-but-harmless and the implementation keeps it as specified. ✅

## Cross-Domain Concerns

- **UI/UX:** none — no API surface changes in this bundle.
- **Functional Analyst:** the `loop.py` contracts being tested (`build_message` no-Instructions, send→mark→archive ordering, send-failure propagation) are the functional contracts documented in §7. The tests lock these correctly.
- **Security Engineer:** S-01's `SECURITY.md` references the `make pre-publish` guard (S-02) in its "Publishing Guards" section. The implemented guard matches what S-01 describes. ✅

## Action Items

None. The implementation is approved as-is.

## Next Steps

Proceed to Stage c (quality review, `make check` gate). No changes required from the developer for the api-architect domain.