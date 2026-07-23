# Functional Review — P2-005 + P2-006 (Main loop + handoff payload builder)

**Date:** 2026-07-22
**Reviewer:** Functional Analyst
**Task:** Combined review of P2-005 (main loop) and P2-006 (handoff payload
builder), implemented per the R3 plan approved in PR #7.
**Files reviewed:**
- `src/yoker_assistant/loop.py` — main implementation
- `src/yoker_assistant/__main__.py` — thin CLI
- `tests/test_loop.py` — 27 new tests
- `agents/assistant.md` — Step 0 sentinel instruction
- `analysis/functional.md` — §4.3 and §7 updates
- `src/yoker_assistant/handoff.py` — verified DELETED

## Verdict

**approved.** All acceptance criteria met, edge cases handled, no regressions,
R3 plan compliant. `make check` passes (42 tests, 0 failures).

## P2-005 acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| `async def run()` | PASS | `loop.py:129` |
| `Agent` constructed ONCE directly | PASS | `loop.py:144-147` — `Agent(agent_path=..., context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"))`; no `Assistant` wrapper |
| `IMAPClient`/`SMTPClient` directly | PASS | `loop.py:152-153`; no `Mailbox` wrapper |
| Poll loop: search→fetch→build_message→process→branch→mark→archive | PASS | `loop.py:166-185` + `_process_one` |
| `--once` flag | PASS | `__main__.py:20` parses it; `loop.py:179` breaks after one iteration |
| Graceful shutdown on SIGINT/SIGTERM | PASS | `loop.py:156-162` installs signal handlers via `asyncio.Event`; `stop.is_set()` checked between messages; `imap.disconnect()` in `finally` |
| No `Mailbox`/`Assistant` wrapper | PASS | Confirmed — only `Agent`, `IMAPClient`, `SMTPClient`, `build_message` called directly |
| `python -m yoker_assistant --once` exits cleanly on empty inbox | PASS | `loop.py:181` — empty `uids` + `once=True` → break |
| Seeded unread email → reply + mark read + archived | PASS | Branch 4 (`loop.py:104-113`) |
| Reply via `smtp.reply_email(..., html_body=reply_html, in_reply_to=msg["message_id"])` | PASS | `loop.py:105-111` — exactly this signature; NOT `body=`, NOT `send_email` |
| Empty reply body → no send attempted | PASS | Branch 2 (`loop.py:86-88`) |
| Persistent session across iterations | PASS | `Agent` constructed once with `Persisted(SimpleContextManager(), session_id="yoker-assistant")`; each `process()` is next turn in same session |
| Per-message exception → skip and continue | PASS | `loop.py:171-177` — `try/except Exception` logs and `continue`s; message stays UNSEEN |

## P2-006 acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| `build_message(email_message) -> str` | PASS | `loop.py:49` |
| From/Subject/Date headers + body | PASS | `loop.py:64` — `f"From: {from_}\nSubject: {subject}\nDate: {date_}\n\n{body}"` |
| NO `Instructions:` block | PASS | Confirmed — only 3 headers + blank line + body |
| Pure function, no I/O | PASS | No `await`, no network, no file reads in `build_message` |
| Accepts raw `simple_email_gw` message dict | PASS | `loop.py:49` — `dict[str, Any]` parameter; uses `.get("from", "")` etc. |
| Unit-testable with fixture dict matching `fetch_message` shape | PASS | `tests/test_loop.py:28-67` — 4 tests with fixture dicts |

## R3 plan compliance

### Four-way branching (R3)

| Branch | Trigger | Action | Implemented |
|---|---|---|---|
| 1 | `{{NO_REPLY}}` sentinel | mark read + archive, no send | PASS — `loop.py:82-85` |
| 2 | empty/whitespace reply | leave UNSEEN for retry | PASS — `loop.py:86-88` |
| 3 | unsafe HTML (guard fail) | mark read (no archive) + reply notice to original sender | PASS — `loop.py:89-102` |
| 4 | valid HTML | send + mark read + archive | PASS — `loop.py:103-113` |

### C1 blocking fix — whitelist startup check

PASS — `loop.py:137-141`:
```python
if not get_recipient_whitelist().enabled:
    raise RuntimeError(
        "EMAIL_RECIPIENT_WHITELIST_ADDRESSES not set — refusing to run "
        "(recipient whitelist fails open)"
    )
```
Runs before `Agent` construction or any IMAP connection. Tested by
`test_run_refuses_to_start_when_whitelist_disabled`.

### HTML guardrail (7-line denylist)

PASS — `loop.py:37-46`:
- 7 unsafe tag prefixes: `<script`, `<style`, `<img`, `<iframe`, `<object`,
  `<embed`, `<form`
- 1 regex for `on\w+=` event handlers: `_UNSAFE_HANDLER = re.compile(r"\son\w+\s*=")`
- Case-insensitive via `.lower()` on the tag check
- 10 unsafe-input test cases + 6 clean-input test cases all pass

### NO_REPLY_SENTINEL

PASS — `loop.py:31`: `NO_REPLY_SENTINEL = "{{NO_REPLY}}"`. Detected via
substring check (`NO_REPLY_SENTINEL in reply_html`) which handles both the
raw sentinel and the `<p>{{NO_REPLY}}</p>` md_to_html-wrapped form. Tested
by `test_process_one_sentinel_wrapped_in_html_still_detected`.

### Guard failure: mark read, no archive, reply notice to sender

PASS — `loop.py:89-102`:
- `mark_message(..., "\\Seen", action="add")` — mark read
- NO `move_message` call — no archive
- `reply_email(to=sender, subject=f"Re: {subject}", body=notice, in_reply_to=in_reply_to)` — plain-text notice to original sender via `reply_email` (loop-constructed text, not agent output; no `html_body`)
- Test asserts: `mark_message` called, `move_message` NOT called, `reply_email` called with `body` containing "unable to produce a safe reply", NO `html_body` kwarg

### build_message: CR/LF collapse in headers

PASS — `loop.py:57-58`:
```python
def _clean(value: Any) -> str:
  return str(value or "").replace("\r", " ").replace("\n", " ")
```
Applied to `from`, `subject`, `date` (header fields). Body is NOT cleaned
(newlines are legitimate). Tested by `test_build_message_collapses_crlf_in_headers`
which verifies a `From: alice\r\nBcc: evil\r\n` cannot inject a real `Bcc:`
header line.

### SDK errata (5 corrections from api-loop.md)

| Erratum | Implemented |
|---|---|
| `SMTPClient` has no `connect()`/`disconnect()` | PASS — `loop.py:153` constructs `SMTPClient(account)` and never calls connect/disconnect on it; comment documents this |
| `reply_email(to=str)` — single address string | PASS — `loop.py:78` uses `parseaddr(msg.get("from", ""))[1]` to extract bare address |
| `reply_email` requires `body: str` | PASS — `loop.py:108` passes `body=""` in branch 4; `loop.py:100` passes `body=notice` in branch 3 |
| `move_message(mid, "INBOX", "Archive")` — source folder required | PASS — `loop.py:85, 113` call `move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)` |
| `parseaddr` for sender extraction | PASS — `loop.py:78` |

## Edge cases

| Edge case | Status | Evidence |
|---|---|---|
| Missing fields in message dict | PASS | `build_message` uses `.get("from", "")` etc. — `test_build_message_missing_fields_become_empty_strings` |
| Empty/whitespace reply | PASS | Branch 2 — `not reply_html.strip()` → no mark, no archive, no send; `test_process_one_empty_reply_leaves_unseen` |
| Sentinel wrapped in HTML (`<p>{{NO_REPLY}}</p>`) | PASS | Substring match catches it; `test_process_one_sentinel_wrapped_in_html_still_detected` |
| Graceful shutdown during message processing | PASS | `stop.is_set()` checked at `loop.py:169` (between messages); in-flight message completes; `imap.disconnect()` in `finally` at `loop.py:187` |
| Per-message exception handling | PASS | `loop.py:171-177` — `try/except Exception` logs and `continue`s; message stays UNSEEN and retries |

## No regressions

| Check | Status |
|---|---|
| Existing 15 `test_md_to_html.py` tests pass | PASS (15/15) |
| 27 new `test_loop.py` tests pass | PASS (27/27) |
| `__YOKER_MANIFEST__` intact — `md_to_html` still registered | PASS — `__init__.py:20` unchanged |
| `make check` clean | PASS — 42 tests, 0 failures |

## User flow end-to-end

- **connect → search UNSEEN → fetch → build_message → agent.process → branch → reply/mark/archive**: `run()` connects via `imap.connect()` once (`loop.py:164`), then loops: `imap.search(_INBOX_FOLDER, "UNSEEN")` → per-id `_process_one` which `fetch_message` → `build_message` → `agent.process` → four-way branch. Confirmed.
- **`--once` flag works**: `__main__.py` parses `--once`, passes to `run(once=True)`, loop breaks after one iteration. Confirmed.
- **SIGINT/SIGTERM triggers graceful shutdown**: signal handlers set `asyncio.Event`; loop checks `stop.is_set()` between messages; in-flight message completes; `imap.disconnect()` in `finally`. Confirmed.

## Owner's binding directives (simplicity)

1. **"Combine P2-005 and P2-006 into one PR"** — SATISFIED. One cohesive
   implementation in `loop.py`; `build_message` lives alongside `run` and
   the helpers. No separate PR needed for the handoff builder.

2. **"006 is 'merely' a function"** — SATISFIED. `build_message` is a plain
   module-level function (`loop.py:49`), not a class, not a module. It
   reads its input dict, concatenates, returns a string. 16 lines.

3. **"the split handoff-builder still is a residu from an overengineered
   previous design"** — SATISFIED. `src/yoker_assistant/handoff.py` is
   deleted (verified: `No such file or directory`). The handoff builder
   lives in `loop.py` as a function.

4. **"please consider simplicity"** — SATISFIED. No wrapper classes. The
   helpers (`_process_one`, `_contains_unsafe_html`, `_account_from_env`,
   `_clean`) are plain functions. `_process_one` is multi-step orchestration
   (fetch → build → process → branch), which IS earned behavior — not a
   wrapper. The four branches are flat early-returns, no nesting. No
   adapter layers, no façades, no indirection.

## Minor non-blockers (out of scope for this task)

- `src/yoker_assistant/agent.py` is a 3-line stub placeholder from P1-001.
  The `api-loop.md` action item 4 explicitly defers its cleanup to P1-004's
  close-out: "Flag `agent.py` for cleanup — it is a stub residue from the
  descoped `Assistant` wrapper." Not a blocker for P2-005+P2-006; the loop
  does not import it.
- `__init__.py` docstring still says "Those live in `__main__`, `loop`, and
  `agent`." — same stale-doc cleanup deferred to P1-004's close-out.

## Files relevant to this review

- `/Users/xtof/Workspace/agentic/yoker-assistant/src/yoker_assistant/loop.py`
- `/Users/xtof/Workspace/agentic/yoker-assistant/src/yoker_assistant/__main__.py`
- `/Users/xtof/Workspace/agentic/yoker-assistant/tests/test_loop.py`
- `/Users/xtof/Workspace/agentic/yoker-assistant/agents/assistant.md`
- `/Users/xtof/Workspace/agentic/yoker-assistant/analysis/functional.md`
- `/Users/xtof/Workspace/agentic/yoker-assistant/analysis/api-loop.md`
- `/Users/xtof/Workspace/agentic/yoker-assistant/analysis/security-loop.md`
- `/Users/xtof/Workspace/agentic/yoker-assistant/analysis/plan-revision-r1.md`
- `/Users/xtof/Workspace/agentic/yoker-assistant/analysis/plan-revision-r2.md`