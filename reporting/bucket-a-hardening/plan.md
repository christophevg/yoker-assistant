# Bucket A — Implementation & Hardening PR: Consolidated Plan

Status: DRAFT for owner blocking approval (Phase 5.3).
Scope: P2-004, P2-007, P3-003, S-02, P3-001, P3-002, S-01, (optional S-03).
Excluded: P2-002, P2-003 (separate triage pass). P4-001 deferred to Bucket B.

## Phase 3 Design Reviews (Incorporated)

The three Phase 3 design reviews are APPROVED-with-changes and their
feedback is incorporated into this plan. The project-review cycle at
Phase 5.6 can therefore focus on implementation correctness rather than
re-debating design.

- `reporting/bucket-a-hardening/testing-design-review.md` — testing-engineer, Q1 (P3-001/P3-002)
- `reporting/bucket-a-hardening/security-design-review.md` — security-engineer, Q2 (S-01)
- `reporting/bucket-a-hardening/api-design-review.md` — api-architect, Q3 (S-02)

Key changes applied:

- **P3-001**: switched from option (a) to option (b). No `tests/test_handoff.py`
  is created. One new test (`test_build_message_omits_instructions_block`)
  is added to the existing `tests/test_loop.py`. The tautological
  `endswith("instructions:")` assertion in the original proposal was
  dropped (it always passed regardless of input).
- **P3-002**: the send-failure-no-archive test drops the unused `monkeypatch`
  fixture. The ordering assertion uses the tightened form (keep existing
  `_make_clients` stubs, add three `side_effect` lambdas appending to a
  shared `order` list, assert `order == ["reply", "mark", "archive"]`).
- **S-01**: the "process bug... will be reverted" framing is replaced with
  immediate revert PLUS retroactive security review of the merge-to-revert
  exposure window. Section renamed from "Addition Review Process" to
  "Change Review Process" and widened to cover manifest additions OR
  capability-changing edits to existing tools (pure-refactor carve-out).
  Disclosure response window (72-hour ack / 30-day fix on the current
  release line) added. Supported-versions table, CVE-handling section,
  PGP key, and `security.txt` are deliberately omitted as premature for 0.1.0.
- **S-02**: the `find dist -name METADATA` block (a silent no-op because
  both `.whl` and `.tar.gz` are archives) is replaced with the streaming
  approach: `unzip -p dist/*.whl '*.dist-info/METADATA'` and
  `tar -xzOf dist/*.tar.gz '*/PKG-INFO'` piped to a single `grep`. The
  grep pattern is corrected to
  `(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )` — drops
  the broken `^ \.\./` sub-pattern, scopes `https://`/`http://`/`ssh://`/`../`
  to `Requires-Dist:.*@` only (Project-URL lines legitimately contain
  HTTPS). The "both contain a METADATA file" claim is corrected: sdists
  contain `PKG-INFO`. `twine check` is retained as a complementary
  rendering check (it does NOT catch path deps).

## Bundle Overview

This bundle closes out the loose ends from the P1/P2 implementation wave:
flips the checkboxes for work already folded into shipped PRs (P2-004,
P2-007, P3-003), lands the test coverage the backlog promised for the
handoff contract and the polling loop (P3-001, P3-002), and adds two
defense-in-depth security pieces that should land before Phase B — a
publish-time guard against path-dep leakage into PyPI metadata (S-02) and
a `SECURITY.md` documenting the `__YOKER_MANIFEST__` change review
process (S-01). An optional S-03 records the upstream simple-email-gw
docs issue URL if filed in time.

**Task list (owner-approved):**

1. P2-004 — flip checkbox to `[x]` (rationale already in functional.md §3.4)
2. P2-007 — flip checkbox to `[x]` (scope folded into P2-005)
3. P3-003 — mark dropped (cosmetic — already struck through)
4. S-02 — `make pre-publish` guard: reject `file://`/`path =`/non-registry source URLs in built sdist/wheel METADATA
5. P3-001 — add one test to `tests/test_loop.py` asserting `build_message` produces no `Instructions:` block
6. P3-002 — `tests/test_loop.py`: fake IMAP/SMTP/Agent stubs; assert fetch→process→reply→mark→archive order, `html_body=` routing, skip-on-empty-reply-body, error paths
7. S-01 — `SECURITY.md` at repo root: document `__YOKER_MANIFEST__` change review process; README links to it
8. (Optional) S-03 — record upstream issue URL as one-line TODO.md edit if filed in time

**Key finding from reading the tree:** `tests/test_loop.py` **already
exists** and is substantial (370 lines). It covers `build_message` (four
tests: format, CR/LF collapse, missing fields, body verbatim),
`_contains_unsafe_html` (two parametrized suites), the four-way
`_process_one` branching (sentinel, sentinel-in-HTML, empty reply,
guard-failure notice, valid-HTML reply with `html_body=` + `in_reply_to=`
+ ordering), conversation-turn logging, the C1 whitelist startup guard,
per-iteration connect/disconnect, and exception-continuation. `build_message`
lives in `loop.py` (no `handoff.py`). This materially affects P3-001 and
P3-002 — see those sections.

## Per-task Changes

### P2-004 — Flip checkbox to `[x]`

**Files to modify:** `TODO.md` (line 231).

**Change:** Replace `- [ ] **P2-004: Record decision to drop pa-session**`
with `- [x] **P2-004: Record decision to drop pa-session** ✅ (2026-07-23, PR #<this>)`.

**Rationale verification (already done, just confirming):**
- `analysis/functional.md` §3.4 `#### pa-session — DROPPED` (lines 447-459)
  records the decision and the why (persistent context manager carries
  session state natively; memory files + `PERSONAL.md` via `yoker:git`
  cover the rest; keeping it would be dead surface area).
- `ls src/yoker_assistant/` confirms no `skills/pa-session/` exists.

**Verification:** `grep -n "P2-004" TODO.md` shows `[x]`; `grep -rn "pa-session" analysis/functional.md` shows the DROPPED section.

---

### P2-007 — Flip checkbox to `[x]`

**Files to modify:** `TODO.md` (line 375).

**Change:** Replace `- [ ] **P2-007: Wire reply sending with correct threading (HTML)** — FOLDED INTO P2-005`
with `- [x] **P2-007: Wire reply sending with correct threading (HTML)** — FOLDED INTO P2-005 ✅ (2026-07-23, PR #<this>)`.

**Rationale verification (already done):**
- P2-005 is already `[x]` (PR #7).
- `loop.py` lines 117-123 confirm the single `smtp.reply_email(..., body="", html_body=reply_html, in_reply_to=in_reply_to)` call — every send is a reply, `html_body=` routing is loop-side, `in_reply_to=` passthrough is loop-side, no `send_email` fallback.
- `tests/test_loop.py::test_process_one_valid_reply_sends_html_then_marks_and_archives` already asserts `call.kwargs["html_body"] == "<p>Hello.</p>"`, `call.kwargs["body"] == ""`, `call.kwargs["in_reply_to"] == "<orig@example.com>"`.

**Verification:** `grep -n "P2-007" TODO.md` shows `[x]`; existing `make test` already covers the routing.

---

### P3-003 — Mark dropped (cosmetic)

**Files to modify:** `TODO.md` (line 427).

**Current state:** line is already `~~strikethrough~~` with `— DROPPED` annotation and a paragraph explaining the descope and the absorption into P3-002.

**Change:** The strikethrough + DROPPED text is already the canonical
"dropped" marker. To make the checkbox state explicit and consistent with
P2-004/P2-007, replace the leading `- [ ]` with `- [x]` on the strikethrough
line so the box reflects "resolved (as dropped)" rather than "open". Keep
the strikethrough and the DROPPED annotation. (This is the cosmetic edit
the owner's bundle references.)

**Verification:** `grep -n "P3-003" TODO.md` shows the line marked `[x]` with strikethrough and DROPPED text intact.

---

### S-02 — `make pre-publish` guard against non-registry source URLs

**Files to modify:** `Makefile` (the `pre-publish` target, lines 62-73).

**Current state of `pre-publish`:** depends on `check` only; runs README
image-path grep + version-sync check. Does NOT build, does NOT inspect
sdist/wheel METADATA. `publish: clean build` runs `build` before
`pre-publish`, so artifacts exist when invoked via `make publish` — but
`make pre-publish` standalone has no artifacts to check.

**Change:** Make `pre-publish` depend on `build` (so dist/ exists for the
guard), then append a `twine check` + streaming-archive grep step over
the built artifacts. Keep it a pure Makefile recipe (no Python wrapper,
no temp dir, no extraction to disk) per the owner's Wrapper-Check
directive and the api-architect's Simplicity Principle check.

**Why streaming, not `find`:** both `.whl` and `.tar.gz` are archives.
`find dist -name METADATA` returns nothing because `find` does not
penetrate archive contents. The original proposed guard was a silent
no-op — worse than no guard, because it looked like it worked. The
streaming approach (`unzip -p` for wheels, `tar -xzOf` for sdists)
pipes the metadata file to stdout without writing to disk, so a single
`grep` over the concatenated stream catches `Requires-Dist:` lines in
either format. Note: sdists contain `PKG-INFO` (not `METADATA`) — the
two files are format-equivalent core-metadata (email-header style, same
`Requires-Dist:` lines), just at different paths inside different
archive types.

**Proposed recipe (appended after the existing version-sync block, before
the closing `@echo "Pre-publication checks passed"`):**

```make
pre-publish: check build ## Pre-publication checks (run before publishing)
	@echo "Checking for relative image paths in README..."
	@grep -n '!\[.*](media/' README.md && (echo "ERROR: Relative image paths found - use raw GitHub URLs for PyPI"; exit 1) || echo "OK: No relative image paths"
	@echo "Checking version sync..."
	@VERSION_PY=$$(grep '^version =' pyproject.toml | cut -d'"' -f2); \
	VERSION_INIT=$$(grep '^__version__ = ' src/yoker_assistant/__init__.py | cut -d'"' -f2); \
	if [ "$$VERSION_PY" != "$$VERSION_INIT" ]; then \
		echo "ERROR: Version mismatch - pyproject.toml ($$VERSION_PY) vs __init__.py ($$VERSION_INIT)"; \
		exit 1; \
	fi; \
	echo "OK: Versions match ($$VERSION_PY)"
	@echo "Checking built distribution metadata for non-registry source URLs..."
	@uv run twine check dist/* >/dev/null
	@hits=$$( { for whl in dist/*.whl; do [ -e "$$whl" ] && unzip -p "$$whl" '*.dist-info/METADATA' 2>/dev/null; done; \
		for sdist in dist/*.tar.gz; do [ -e "$$sdist" ] && tar -xzOf "$$sdist" '*/PKG-INFO' 2>/dev/null; done; } \
		| grep -nE '(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )' ); \
	if [ -n "$$hits" ]; then \
		echo "ERROR: non-registry source URLs found in built metadata:"; \
		echo "$$hits"; \
		exit 1; \
	fi; \
	echo "OK: No non-registry source URLs in built metadata"
	@echo "Pre-publication checks passed"
```

**Notes on the grep pattern:**
- `^Requires-Dist:.*@` — the primary guard. In `Requires-Dist:` lines,
  `@` is the PEP 508 direct-reference separator and is unambiguous
  (markers use `;`, `and`, `or`, comparison operators — never `@`). So
  any `Requires-Dist:` line containing `@` is a direct reference —
  file, path, URL, VCS, or relative. This single sub-pattern catches
  `yoker @ file://...`, `yoker @ git+https://...`, `yoker @ https://...`,
  `yoker @ ssh://...`, `yoker @ /abs/path`, `yoker @ ./rel/path`, and
  `yoker @ ../rel` — covering the case the original `^ \.\./` sub-pattern
  tried and failed to catch (`Requires-Dist:` is single-line, does not
  wrap, so `../` never appears at line start).
- `file://` — global substring. No legitimate metadata field contains
  `file://`; catches `Download-URL` or `Project-URL` typos too.
- `git\+|hg\+|svn\+|bzr\+` — global substrings for VCS URL schemes. No
  legitimate metadata field contains them.
- `path =` — kept per owner's acceptance wording. Defense-in-depth only:
  `[tool.uv.sources]` is a uv-specific tool section that is structurally
  excluded from built PyPI metadata, so `path =` will never appear in a
  real `Requires-Dist:` line. Paranoid but harmless.
- `https://`, `http://`, `ssh://`, `../`, `/` are NOT matched globally —
  `Project-URL:` lines legitimately contain HTTPS URLs (Homepage,
  Repository, Issues). Those forms are caught only via `^Requires-Dist:.*@`.
- The original `^ \.\./` sub-pattern is dropped — it was wrong
  (`Requires-Dist:` is single-line, so `../` never appears at line
  start) and would never match.
- The original `@ file://` sub-pattern is dropped — redundant with the
  bare `file://` substring and now subsumed by `^Requires-Dist:.*@`.
- `twine check` is retained as a complementary rendering check — it
  validates long_description rendering and required metadata fields, but
  it does NOT reject `Requires-Dist: yoker @ file://...`. It is not the
  path-dep guard.

**Verification:**
1. Positive path: `make clean && make build && make pre-publish` passes with the current `pyproject.toml` (deps are `yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` — all registry names, no `@`).
2. Negative path (wheel, throwaway, NOT committed): temporarily inject `yoker @ file://../yoker` into `[project.dependencies]`, run `make clean && make build && make pre-publish`, confirm it fails with the ERROR line and a non-zero exit. Revert the injection.
3. Negative path (VCS): temporarily inject `yoker @ git+https://github.com/x/yoker.git`, confirm failure. Revert.
4. Negative path (sdist-only leakage): if a path dep somehow lands only in the sdist's `PKG-INFO`, confirm the `tar -xzOf` arm catches it. (In practice hatchling writes the same `Requires-Dist` to both, so this is belt-and-suspenders.)
5. `make publish` end-to-end: `publish: clean build` then `@$(MAKE) pre-publish` — `build` dedups under make, no double build.

---

### P3-001 — Tests for the handoff contract

**Files to modify:** `tests/test_loop.py` (already exists — 370 lines).

**Key finding:** `build_message` is in `loop.py` (not `handoff.py` — that
module was never created). `tests/test_loop.py` already has four
`test_build_message_*` tests covering the format (headers + blank line +
body), CR/LF collapse, missing fields, and body verbatim. P3-001's
remaining unique value is the explicit "no `Instructions:` block"
assertion, which the existing tests do NOT make.

**Decision (per testing-engineer Phase 3 review, option (b)):** do NOT
create `tests/test_handoff.py`. A new test file is an indirection that
adds no value here — two of the three tests in the proposed
`test_handoff.py` were duplicate assertions already covered by the
existing `test_build_message_*` suite, and the "easy to move if
`build_message` ever moves" argument is YAGNI (`handoff.py` was never
created; if/when `build_message` moves, the tests can move at the same
commit). Add a single focused test to `tests/test_loop.py` next to the
existing `test_build_message_*` suite, with the contract concern named
in the docstring:

```python
def test_build_message_omits_instructions_block() -> None:
  """P3-001 handoff contract: the per-email payload must NOT contain an
  ``Instructions:`` block. Identity and workflow instructions live in the
  agent definition + the one-time session-setup turn (P1-004), not in each
  email's handoff. This is the regression test that fires if someone
  reintroduces the old c3-style instructions header.
  """
  msg = {"from": "o@example.com", "subject": "Hi", "date": "D", "body": "b"}
  out = build_message(msg)
  for line in out.splitlines():
    assert not line.lower().startswith("instructions:")
```

**Bug fix in the original proposal:** the earlier draft
`test_handoff_has_no_instructions_block` contained a tautological
assertion that always passed regardless of input:

```python
assert "instructions:" not in out.lower().split("instructions:")[0].endswith("instructions:")
```

`"foo instructions: bar".lower().split("instructions:")[0]` returns the
text *before* the first delimiter (`"foo "`), which never ends with
`"instructions:"`, so `.endswith(...)` returns `False` and `not False`
is `True` — the assertion holds for any input string, including ones
that contain `Instructions:`. It was bloat that looked like a real
check. The corrected test above keeps only the meaningful per-line
`startswith` loop, which catches the contract concern case-insensitively.

**Verification:** `make test TEST=tests/test_loop.py::test_build_message_omits_instructions_block` passes; `make test` (full suite) still passes; `make check` green.

---

### P3-002 — Tests for the polling logic

**Files to modify:** `tests/test_loop.py` (already exists — 370 lines).

**Key finding:** `tests/test_loop.py` ALREADY covers the full P3-002
acceptance criteria and more:

| P3-002 acceptance criterion | Existing test |
|---|---|
| fetches unseen | `test_run_proceeds_when_whitelist_enabled` (search called with `"INBOX", "UNSEEN"`) |
| calls `process` | `test_process_one_valid_reply_sends_html_then_marks_and_archives` |
| sends reply via `smtp.reply_email(..., html_body=<agent output>, in_reply_to=msg["message_id"])` (NOT `body=`, NOT `send_email`) | `test_process_one_valid_reply_sends_html_then_marks_and_archives` (asserts `html_body=="<p>Hello.</p>"`, `body==""`, `in_reply_to=="<orig@example.com>"`) |
| marks read, archives, in order | same test (asserts `mark_message` then `move_message` awaited in order) — **ordering assertion to be tightened** (see below) |
| on empty inbox, no error | `test_run_proceeds_when_whitelist_enabled` (empty search, no raise) |
| on agent failure, does not mark read | `test_run_continues_after_process_one_exception` (first message raises, second proceeds; loop continues) |
| on send failure, does not archive | **NOT YET COVERED** — see below |
| skip-on-empty-reply-body (no `reply_email`, no mark-read) | `test_process_one_empty_reply_leaves_unseen` |

**Gap to fill (send-failure-no-archive):** the "on send failure, does not
archive" path is not covered. Add one test (per testing-engineer's
corrected version — the unused `monkeypatch` fixture parameter is
dropped):

```python
async def test_process_one_send_failure_does_not_archive() -> None:
  """If smtp.reply_email raises, the message is NOT marked read or archived
  (§7 error handling: agent/send failure does not mark read)."""
  imap, smtp, agent = _make_clients("<p>Hello.</p>")
  smtp.reply_email = AsyncMock(side_effect=RuntimeError("smtp boom"))
  await _process_one(imap, smtp, agent, "1")
  smtp.reply_email.assert_awaited_once()
  imap.mark_message.assert_not_awaited()
  imap.move_message.assert_not_awaited()
```

**Tighten the ordering assertion** on the existing
`test_process_one_valid_reply_sends_html_then_marks_and_archives`. The
current test asserts each of `reply_email` / `mark_message` /
`move_message` was awaited, but not the order. The §7 contract is
"send → mark → archive"; a regression that swapped mark-before-send
would currently slip past. Per testing-engineer's tightened form: keep
the existing `_make_clients` stubs, wrap just the three methods to
record order via `side_effect` lambdas appending to a shared list, and
assert the list equals `["reply", "mark", "archive"]`. Minimal diff —
add the `order` list and the single `assert order == [...]` line; leave
the existing `assert_awaited_once_with` lines in place if you want to
also lock the exact args (the current test does):

```python
async def test_process_one_valid_reply_sends_html_then_marks_and_archives() -> None:
  """Branch 4: valid HTML → reply_email with html_body + mark read + archive,
  in that order (send → mark → archive per §7)."""
  imap, smtp, agent = _make_clients("<p>Hello.</p>")

  order: list[str] = []
  smtp.reply_email.side_effect = lambda *a, **kw: order.append("reply")
  imap.mark_message.side_effect = lambda *a, **kw: order.append("mark")
  imap.move_message.side_effect = lambda *a, **kw: order.append("archive")

  await _process_one(imap, smtp, agent, "1")

  assert order == ["reply", "mark", "archive"]

  call = smtp.reply_email.call_args
  assert call.kwargs["to"] == "owner@example.com"
  assert call.kwargs["subject"] == "Re: Hi"
  assert call.kwargs["body"] == ""
  assert call.kwargs["html_body"] == "<p>Hello.</p>"
  assert call.kwargs["in_reply_to"] == "<orig@example.com>"
```

**Notes for the implementer:**
- `AsyncMock`'s `side_effect` can be a sync callable — AsyncMock awaits
  the result if it's a coroutine, otherwise returns it. A sync lambda
  appending to a list is fine and is the standard pattern.
- This is locking existing behavior, not driving new behavior — no
  `pytest.fail` stub phase needed. Drop the snippets in, run `make test`,
  expect green.

**Verification:** `make test` passes; `make test-cov` shows `loop.py` branch coverage did not drop; `make check` green.

---

### S-01 — `SECURITY.md` for `__YOKER_MANIFEST__` change review

**Files to create:** `SECURITY.md` at repo root.
**Files to modify:** `README.md` (add a "Security configuration" subsection that links to `SECURITY.md`).

**Proposed `SECURITY.md` structure (with security-engineer Phase 3
adjustments applied):**

```markdown
# Security Policy

## Reporting a Vulnerability

Email christophe.vg with a description and repro. Expect an
acknowledgement within 72 hours and a fix or mitigation plan within
30 days for the current release line. Do not publish until the fix is
released unless we agree otherwise.

## `__YOKER_MANIFEST__` Change Review Process

yoker-assistant is a yoker plugin provider. Its `__YOKER_MANIFEST__`
(in `src/yoker_assistant/__init__.py`) declares the tools this package
exposes. When a user installs yoker-assistant and marks
`[plugins.trusted] yoker_assistant = true` in `~/.yoker.toml`, every tool
in the manifest runs with **no per-call gate** — the trust decision is
made once, at install time, and admits all tool code from the package.

This is the intended yoker trust model, but it means adding a new tool
to `__YOKER_MANIFEST__` — or making a capability-changing edit to an
existing tool — is a security-relevant change. Contributors MUST follow
this review process before merging a manifest addition **or a
capability-changing edit to an existing tool** (new args, new side
effects, new dependencies, or a change to the tool's reach). Pure
refactors that do not change the tool's inputs, outputs, reach, or
failure modes do not require this review.

### 1. Blast-radius assessment

For the proposed tool (or the proposed change to an existing tool),
document:
- **Inputs:** what arguments does it accept? Any string/path/URL input?
- **Outputs:** what does it return? Side effects beyond the return value?
- **Reach:** what can it touch? (filesystem read/write, network, shell,
  subprocess, env vars, other tools)
- **Failure modes:** what happens on bad input? On missing resources?
  Does it leak secrets in error messages?

### 2. Capability review

- Does the tool duplicate an existing yoker built-in? If so, justify why
  a second path to the same capability is warranted (it usually is not).
- Does the tool compose with `yoker:git`, `yoker:write`, or
  `yoker:webfetch` in a way that creates a new exfiltration or
  persistence path? If so, document the mitigation.
- Is the tool bounded (named, typed args, no `**kwargs` shell) or
  unbounded (accepts arbitrary commands/paths)? Unbounded tools are
  rejected by default.

### 3. Version pinning

- The tool's behavior must be deterministic for a pinned package
  version. No network-fetched code paths at call time.
- If the tool depends on a network resource, the dependency must be
  declared in `pyproject.toml` (so `uv pip install
  yoker-assistant==<version>` reproduces it), not loaded dynamically.

### 4. Review checklist (PR description)

- [ ] Blast-radius assessment recorded (for an addition or a capability-changing edit)
- [ ] Capability review recorded (duplicates check, composition check,
      bounded-args check)
- [ ] Version pinning confirmed (static deps, no dynamic fetch)
- [ ] Tests cover the happy path + at least one failure mode
- [ ] `make check` green
- [ ] `SECURITY.md` updated if the process itself changes

A manifest addition or capability-changing edit merged without this
checklist is a process violation: it is not automatically a security
incident, but it triggers (1) immediate revert of the change, and (2) a
retroactive security review of what the unreviewed code did while live,
covering the exposure window from merge to revert. CI does not enforce
this — it is a reviewer judgment gate.

## Publishing Guards

`make pre-publish` (see `Makefile`) rejects built sdist/wheel metadata
containing non-registry source URLs (`file://`, VCS schemes, direct
`@ <url>` references, `path =`). This prevents local-path development
wiring (which lives in `[tool.uv.sources]` and is structurally excluded
from PyPI metadata) from ever leaking into a published artifact if
discipline slips.

## Deliberate Non-Additions

A supported-versions table, a formal CVE-handling section, a PGP key,
and a `security.txt` are deliberately omitted. For a 0.1.0
single-tool plugin provider with no released security history, these
are ceremony — premature policy-writing that would go stale
immediately. If a real CVE lands or multiple release lines emerge,
revisit then; until then, GitHub Security Advisories is the
one-line-footnote fallback for CVE publication.
```

**Proposed `README.md` addition** — insert a new subsection at the end of
the existing `## Configuration` section, before `## License`:

```markdown
## Security configuration

Marking `[plugins.trusted] yoker_assistant = true` admits ALL tool code
from this package as trusted with no per-call gate — pin the installed
version (`uv pip install yoker-assistant==<version>`) and verify the
source. Adding a new tool to `__YOKER_MANIFEST__`, or making a
capability-changing edit to an existing tool, is a security-relevant
change; see [`SECURITY.md`](SECURITY.md) for the review process
contributors must follow before such a change. The
`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` env var is the primary reply-safety
boundary (see `.env` section above). `make pre-publish` guards against
local-path dependencies leaking into published metadata.
```

**Verification:** `SECURITY.md` exists at repo root; `grep -n "SECURITY.md" README.md` shows the link; `make check` green (markdown is not linted, but no broken links to a missing file).

---

### S-03 (optional) — Record upstream issue URL

**Files to modify:** `TODO.md` (S-03 entry, line 468).

**Change:** if an issue is filed against `simple-email-gw` for the
`EMAIL_RECIPIENT_ADDRESSES` vs `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` docs
bug, append the issue URL to the S-03 entry as a one-line edit:

```markdown
- [x] **S-03: File upstream issue ...** ✅ (2026-07-23) — https://github.com/<owner>/simple-email-gw/issues/<n>
```

**Contingency:** if not filed in time for this PR, leave S-03 as `[ ]` and
defer to a follow-up. Do NOT block the bundle on S-03.

**Verification:** `grep -n "S-03" TODO.md` shows the URL if filed.

## Execution Order

The bundle has no hard cross-task implementation dependencies (S-01's
README link is part of S-01 itself, not a separate task). Order is chosen
to land the cosmetic/checkbox flips first (low-risk, fast), then the
test work, then the security pieces, with S-03 as a trailing optional
edit:

1. **P2-004** — TODO.md checkbox flip (no code change).
2. **P2-007** — TODO.md checkbox flip (no code change).
3. **P3-003** — TODO.md checkbox flip on the strikethrough line (no code change).
4. **P3-001** — add one test (`test_build_message_omits_instructions_block`) to `tests/test_loop.py` (no new test file).
5. **P3-002** — extend `tests/test_loop.py` with the send-failure-no-archive test (no `monkeypatch` fixture) + tightened ordering assertion (side-effect lambdas + shared `order` list, assert `["reply", "mark", "archive"]`).
6. **S-02** — modify `Makefile pre-publish` (depend on `build`, append `twine check` + streaming `unzip -p` / `tar -xzOf` grep with the corrected pattern).
7. **S-01** — create `SECURITY.md`; add `## Security configuration` subsection to `README.md`.
8. **S-03** (optional, trailing) — append upstream issue URL to TODO.md if filed.

**Rationale for this order:** 1-3 are pure TODO.md edits — do them first
so the backlog state is correct before any code lands. 4-5 are test-only
(no production code change) — they validate the existing `loop.py`
contract and should land before the security pieces so `make check` is
green going into S-02. 6-7 are independent of each other but both touch
non-test files; landing S-02 before S-01 lets the publish guard be in
place for any intermediate publish attempt. S-03 is a one-liner that can
land anytime.

**Parallelization note:** 4 and 5 touch the same file
(`tests/test_loop.py`) and should be one commit to avoid merge churn. 6
and 7 can be implemented in parallel (different files). 1-3 are
sequential edits to the same file (TODO.md) and should be one commit.

## Review Plan

The Phase 3 design reviews (testing-engineer for Q1, security-engineer
for Q2, api-architect for Q3) are APPROVED-with-changes and their
feedback is incorporated into this plan — see the "Phase 3 Design
Reviews (Incorporated)" section near the top of this document and the
three cited review files. The project-review cycle at Phase 5.6 can
therefore focus on implementation correctness (did the agreed changes
land as specified) rather than re-debating design questions.

After implementation, `c3:project-review` will run the scoped review
cycle (functional → domain → quality → documentation → completeness) with
a hard `make check` gate, per the project-manage Phase 5.6 workflow. The
domain review step will specifically route:

- **S-01** content → security-engineer (the manifest review process is their domain).
- **S-02** Makefile recipe → api-architect (build tooling + the archive-penetration mechanism).
- **P3-001/P3-002** test design → testing-engineer (Q1).

The quality review runs `make check` (format-check + lint + typecheck +
test) as the hard gate. The completeness review verifies every checkbox
flipped in this bundle corresponds to work actually present in the tree
(no `[x]` without the underlying change) and verifies the three
review files' adjustments are reflected in the shipped code (no
tautological assertion, no `find dist -name METADATA`, no "process bug"
framing, widened section scope, 72/30 disclosure window, streaming
grep recipe). The documentation review verifies `SECURITY.md` and the
README subsection render correctly and the link resolves.

If the owner approves this plan, implementation proceeds in the execution
order above, then the review cycle runs, then the PR is opened for the
owner's blocking approval before merge.