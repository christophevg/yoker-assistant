# Bucket A Hardening — Stage a Functional Review

Reviewer: functional-analyst
Date: 2026-07-23
Branch: `feature/bucket-a-hardening`
Plan reference: `reporting/bucket-a-hardening/plan.md`

## Verdict: APPROVE

All 7 tasks' acceptance criteria are met. Edge-case probes pass. `make
pre-publish` passes with clean deps and the streaming grep guard correctly
rejects every member of the path-dep class (including the `@ <rel-path>`
forms the original `^ \.\./` sub-pattern missed), while sparing the
legitimate `Project-URL: … https://…` lines. No functional regressions
identified.

## Per-task acceptance criteria check

### 1. P2-004 — "no `skills/pa-session/` is created; §3.4 records the drop"

PASS.

- TODO.md line 231: `- [x] **P2-004: Record decision to drop pa-session** ✅ (2026-07-23, PR #8)` — checkbox flipped.
- `analysis/functional.md` §3.4 (`#### pa-session — DROPPED`, lines 447-459) records the decision and the why (persistent context manager carries session state natively; memory files + `PERSONAL.md` via `yoker:git` cover the rest; keeping it would be dead surface area). The summary at §3.5 also lists it under DROPPED.
- `find … -name pa-session -type d` returns nothing. No `skills/pa-session/` directory exists anywhere in the tree.

### 2. P2-007 — "Wire reply sending with correct threading (HTML)"

PASS.

- TODO.md line 375: `- [x] **P2-007: Wire reply sending with correct threading (HTML)** —` — checkbox flipped (with `FOLDED INTO P2-005 ✅ (2026-07-23, PR #8)` on the continuation line).
- `src/yoker_assistant/loop.py` lines 117-123: the Branch 4 send call is
  ```python
  await smtp.reply_email(
    to=sender,
    subject=f"Re: {subject}",
    body="",
    html_body=reply_html,
    in_reply_to=in_reply_to,
  )
  ```
  Uses `reply_email` (not `send_email`), routes the agent HTML through
  `html_body=` (not `body=`), passes `in_reply_to=msg["message_id"]`-derived
  value, and every send is a reply (no `send_email` fallback anywhere in
  the module).
- The Branch 3 guard-failure notice (lines 109-114) correctly uses
  `body=notice` with no `html_body` — the only legitimate `body=` use, and
  the test suite asserts `"html_body" not in call.kwargs` for that branch.

### 3. P3-003 — "dropped (cosmetic) — checkbox flipped on the strikethrough line"

PASS.

- TODO.md line 427: `- [x] ~~**P3-003: Tests for the mailbox seam**~~ — DROPPED` — checkbox is `[x]`, strikethrough and DROPPED annotation intact, and the explanatory paragraph below is preserved.

### 4. P3-001 — "covers the contract that would regress if the format changed"

PASS.

- `tests/test_loop.py` lines 72-88: `test_build_message_omits_instructions_block` exists in the `test_build_message_*` suite (no separate `test_handoff.py` created — per the testing-engineer's option (b) decision in the plan).
- Docstring names the contract concern: "regression test that would fire if someone reintroduced the old c3-style instructions header."
- Assertion is a per-line `for line in out.splitlines(): assert not line.lower().startswith("instructions:")` — case-insensitive, line-scoped, not the tautological `endswith("instructions:")` form the plan called out and dropped. The test would fire on `Instructions: …` (any case) at line start.
- `make test` passes (48 tests, including this one).

### 5. P3-002 — "behavior-based, fake IMAP/SMTP/Agent stubs, `html_body=` asserted, skip-on-empty-reply-body asserted, error paths"

PASS.

- `tests/test_loop.py` line 237: `test_process_one_send_failure_does_not_archive` exists. Uses `_make_clients("<p>Hello.</p>")` (fake IMAP/SMTP/Agent stubs, no network, no backend), sets `smtp.reply_email = AsyncMock(side_effect=RuntimeError("smtp boom"))`, wraps the call in `pytest.raises(RuntimeError, match="smtp boom")`, then asserts `smtp.reply_email.assert_awaited_once()`, `imap.mark_message.assert_not_awaited()`, `imap.move_message.assert_not_awaited()`. Send-failure-no-archive path covered.
- The tightened ordering test (lines 209-234) uses the shared `order: list[str]` + three `side_effect` lambdas pattern and asserts `assert order == ["reply", "mark", "archive"]`. The tightening did NOT drop the routing assertions — the same test still asserts (lines 226-232):
  - `call.kwargs["body"] == ""`
  - `call.kwargs["html_body"] == "<p>Hello."`
  - `call.kwargs["in_reply_to"] == "<orig@example.com>"`
  - `call.kwargs["to"] == "owner@example.com"`
  - `call.kwargs["subject"] == "Re: Hi"`
  So `html_body=`/`in_reply_to=` routing is still locked at the loop→gateway boundary.
- Skip-on-empty-reply-body: `test_process_one_empty_reply_leaves_unseen` (lines 185-191) asserts `mark_message`/`move_message`/`reply_email` all `assert_not_awaited()` for a whitespace reply.
- Agent-failure-no-mark: `test_run_continues_after_process_one_exception` covers the per-message exception path at the `run()` level (loop continues to next message).
- Behavior-based throughout: no real IMAP/LLM. All via `MagicMock` + `AsyncMock`.
- `make test` passes (48 tests).

### 6. S-01 — "SECURITY.md documenting the __YOKER_MANIFEST__ change review process (blast-radius, capability review, version pinning); README links to it"

PASS.

- `SECURITY.md` exists at repo root.
- The three pillars are present and labelled:
  - `### 1. Blast-radius assessment` (inputs / outputs / reach / failure modes)
  - `### 2. Capability review` (duplicates check, composition check with `yoker:git`/`yoker:write`/`yoker:webfetch`, bounded-args check)
  - `### 3. Version pinning` (deterministic for pinned version, deps in `pyproject.toml` not dynamic fetch)
- Plus `### 4. Review checklist (PR description)` with the 6-item checklist, and the "process violation → immediate revert + retroactive review of exposure window" enforcement clause (incorporating the security-engineer's Phase 3 adjustment — the "will be reverted" framing was replaced with immediate-revert + retroactive review).
- Reporting a Vulnerability section has the 72-hour ack / 30-day fix window.
- Deliberate Non-Additions section records the supported-versions table / CVE / PGP / `security.txt` omissions as premature for 0.1.0.
- `README.md` lines 81-92: the `## Security configuration` subsection exists, links to `[`SECURITY.md`](SECURITY.md)`, and covers the self-trust blast radius, version pinning advice, the manifest-change review trigger, and the `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` boundary. The link target exists at repo root — link resolves.

### 7. S-02 — "Makefile target rejecting file://, path=, non-registry source URLs in built sdist/wheel METADATA"

PASS.

- `Makefile` line 62: `pre-publish: check build …` — now depends on `build`, so dist/ exists when the guard runs standalone.
- Lines 73-83: the guard appended after the existing version-sync block:
  - `uv run twine check dist/* >/dev/null` (retained as complementary rendering check)
  - streaming `unzip -p dist/*.whl '*.dist-info/METADATA'` for wheels
  - streaming `tar -xzOf dist/*.tar.gz '*/PKG-INFO'` for sdists
  - single `grep -nE '(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )'` over the concatenated stream
  - non-empty hit → ERROR + `exit 1`
- The streaming approach (no `find dist -name METADATA`, no extraction to disk, no Python wrapper) matches the api-architect's Phase 3 correction. The `find dist -name METADATA` no-op was correctly dropped — both `.whl` and `.tar.gz` are archives that `find` cannot penetrate.
- Grep pattern verification (synthetic METADATA piped through the exact pattern):
  - Catches: `Requires-Dist: yoker @ file:///tmp/fake-yoker`, `… @ git+https://…`, `… @ https://example.com/yoker.whl`, `… @ /abs/path`, `… @ ./rel/path`, `… @ ../rel` (all 6 forms the original `^ \.\./` sub-pattern missed)
  - Spares: `Project-URL: Homepage, https://github.com/…` and `Project-URL: Issues, https://github.com/…` (no false positives on legitimate HTTPS Project-URL lines)
  - The `^Requires-Dist:.*@` sub-pattern is the primary guard — `@` is the PEP 508 direct-reference separator and is unambiguous on `Requires-Dist:` lines.
- Positive path: `make pre-publish` on the clean tree builds the wheel + sdist, runs `twine check`, runs the streaming grep, prints `OK: No non-registry source URLs in built metadata`, prints `Pre-publication checks passed`, exits 0. Verified end-to-end.
- `path =` is kept per the owner's acceptance wording as defense-in-depth (harmless: `[tool.uv.sources]` is structurally excluded from built PyPI metadata).

## Edge case findings

### `pytest.raises(RuntimeError)` in `test_process_one_send_failure_does_not_archive` — correct, not a contract-masking smell

The developer's use of `pytest.raises(RuntimeError, match="smtp boom")` is the correct pattern and does NOT mask a contract violation. Verified against `loop.py`:

- `_process_one` (lines 72-125) does NOT wrap `smtp.reply_email` in a try/except. The exception propagates out of `_process_one` to `run()`'s per-message `except Exception:` block (lines 186-190), which logs and skips — leaving the message UNSEEN for retry.
- The §7 contract is "agent/send failure does not mark read" — i.e. `mark_message` and `move_message` must NOT be called when `reply_email` raises. Because the `await imap.mark_message(…)` and `await imap.move_message(…)` calls (lines 124-125) come AFTER `await smtp.reply_email(…)` (lines 117-123) with no intervening try/except, a `reply_email` exception short-circuits past them. The contract is satisfied by control flow, not by a swallowed exception.
- `pytest.raises` is the standard way to assert "this call raises" while still allowing post-raise assertions (`mark_message.assert_not_awaited()`, `move_message.assert_not_awaited()`). Without it, the test would error out at the `_process_one` call and the non-call assertions would never run.
- The test therefore correctly verifies BOTH (a) the exception propagates (matching the §7 "skip and continue" contract at the `run()` level) AND (b) mark/archive are never reached.

No issue. Approve as-is.

### Tightened ordering test — routing assertions retained

The tightening added the `order == ["reply", "mark", "archive"]` assertion but did NOT drop the `call.kwargs["html_body"]` / `call.kwargs["body"]` / `call.kwargs["in_reply_to"]` / `call.kwargs["to"]` / `call.kwargs["subject"]` assertions (lines 226-232). Both the ordering contract and the routing contract are now locked. Good.

### `make pre-publish` regression check

`make pre-publish` end-to-end on the clean tree:
- `make check` green (format-check + lint + typecheck + 48 tests passing)
- `uv build` produces `dist/yoker_assistant-0.1.0.tar.gz` and `dist/yoker_assistant-0.1.0-py3-none-any.whl`
- `twine check dist/*` passes
- streaming grep over both archives' METADATA/PKG-INFO: no hits, exit 0
- prints `Pre-publication checks passed`

Current clean deps (`yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` — all registry names, no `@`) pass the guard. No regression.

### README "Security configuration" link resolves

`README.md` line 88: `[`SECURITY.md`](SECURITY.md)` — relative link from repo root to `SECURITY.md` at repo root. Target file exists. Link resolves.

## Regression check

- Full test suite: 48 passed, 0 failed, 3.34s.
- `make check` green (format-check + lint + typecheck + test).
- `make pre-publish` green end-to-end with clean deps.
- No production code changes in this bundle (`loop.py`, `__init__.py`, `handoff` logic untouched) — the bundle is TODO.md checkbox flips + test additions + Makefile recipe + new `SECURITY.md` + README subsection. No risk of behavioral regression in the loop or the tool manifest.
- The new `test_build_message_omits_instructions_block` and `test_process_one_send_failure_does_not_archive` tests both pass against the current `loop.py` contract — they lock existing behavior, not drive new behavior.

## Consolidated feedback for the developer

None. The implementation matches the approved plan on every point, including the three Phase 3 design-review corrections:
- P3-001: option (b), no `test_handoff.py`, tautological assertion dropped.
- P3-002: unused `monkeypatch` fixture dropped, tightened ordering via `side_effect` lambdas + shared `order` list, routing assertions retained.
- S-01: "process bug… will be reverted" framing replaced with immediate-revert + retroactive review of exposure window; section widened to cover capability-changing edits; 72/30 disclosure window added; deliberate non-additions recorded.
- S-02: `find dist -name METADATA` no-op replaced with streaming `unzip -p` / `tar -xzOf`; grep pattern corrected to `(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )`; `https://`/`http://`/`ssh://`/`../`/`/` NOT matched globally — scoped to `^Requires-Dist:.*@` only so legitimate `Project-URL:` HTTPS lines pass.

Ready to advance to Stage b (domain review).