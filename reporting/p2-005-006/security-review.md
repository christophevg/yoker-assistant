# Security Review — P2-005 + P2-006 (round 0, implementation)

**Scope:** `src/yoker_assistant/loop.py`, `src/yoker_assistant/__main__.py`,
`tests/test_loop.py`. Verifies that the fixes from the design-stage review
(`analysis/security-loop.md`) are correctly implemented.

**Status:** round 0 of the project-review cycle. Stage a (functional) passed.

## Verdict

**approved.** All blocking and related findings from the design-stage review
are correctly implemented. No new security issues found.

## Verification of design-stage fixes

### C1 (BLOCKING) — whitelist startup check: IMPLEMENTED

`loop.py:136-141`:

```python
if not get_recipient_whitelist().enabled:
    raise RuntimeError(
        "EMAIL_RECIPIENT_WHITELIST_ADDRESSES not set — refusing to run "
        "(recipient whitelist fails open)"
    )
```

- Checked before entering the loop: yes (first statement in `run()`).
- Raises `RuntimeError` (fails closed): yes.
- Before `Agent` construction (line 144) and before `imap.connect()`
  (line 164): yes — the guard cannot be bypassed by reaching the agent
  or opening a network connection.
- Test coverage: `test_run_refuses_to_start_when_whitelist_disabled`
  (`tests/test_loop.py:208-216`) monkeypatches `get_recipient_whitelist`
  and asserts `RuntimeError` matching `"recipient whitelist"`.

The fails-open default is now closed at the loop boundary, exactly as the
design review required.

### M2 — CR/LF collapse in build_message: IMPLEMENTED

`loop.py:57-58`:

```python
def _clean(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")
```

Applied to `from`, `subject`, `date` (lines 60-62). Body is passed through
verbatim (line 63) — correct per the design review (newlines are legitimate
in the body).

Test coverage: `test_build_message_collapses_crlf_in_headers`
(`tests/test_loop.py:41-55`) injects `Bcc:` and `Injected-Header:` via CR/LF
in From/Subject/Date and asserts the header block contains no CR and the
injected lines do not appear as real header lines. Handoff-format injection
is prevented.

### HTML guardrail (owner-approved addition): IMPLEMENTED CORRECTLY

`loop.py:37-46`:

```python
_UNSAFE_TAGS = ("<script", "<style", "<img", "<iframe", "<object", "<embed", "<form")
_UNSAFE_HANDLER = re.compile(r"\son\w+\s*=")

def _contains_unsafe_html(html: str) -> bool:
    lowered = html.lower()
    if any(tag in lowered for tag in _UNSAFE_TAGS):
        return True
    return bool(_UNSAFE_HANDLER.search(html))
```

- Tags checked: exactly the seven specified (`<script`, `<style`, `<img`,
  `<iframe`, `<object`, `<embed`, `<form`), case-insensitive via `lower()`.
- Event handlers: `\son\w+\s*=` matches whitespace-prefixed `on*=` handlers
  (`onclick`, `onload`, `onmouseover`, etc.). Test cases confirm all three
  variants are caught (`tests/test_loop.py:85-87`).

**Branch 3 behavior** (`loop.py:89-102`) — on guard failure:

- Mark read: `imap.mark_message(..., "\\Seen", action="add")` (line 91).
- No archive: `imap.move_message` is NOT called — verified by
  `test_process_one_guard_failure_marks_no_archive_sends_notice`
  (`tests/test_loop.py:178`). The message will not be re-fetched by the
  next UNSEEN poll, so no infinite-retry loop.
- Plain-text notice sent to the original sender: `to=sender` (line 98),
  where `sender = parseaddr(msg["from"])[1]` (line 78) — the bare address,
  not the owner. `body=notice` (plain text), no `html_body` kwarg passed
  (asserted at `tests/test_loop.py:185`). The notice is loop-constructed
  constant text, not agent output — no XSS surface.
- Notice content is generic (lines 92-96): no details about the unsafe
  content, no error internals, no paths. Information-disclosure-safe.

One observation (not a finding): the event-handler regex requires a
whitespace character before `on`. Constructs like `<svg/onload=...>` (slash
separator) would not match. This is a known XSS bypass pattern, but email
clients generally do not render `<svg>` and the seven-tag list already
catches the high-risk email-rendable vectors (`<img>`, `<style>`, `<form>`).
For a loop-side defense-in-depth guardrail (the `md_to_html` tool is the
primary XSS prevention path), this is acceptable. Flagging only as a
future-hardening note if yoker-assistant moves toward production use.

### Reply-to-sender safety: VERIFIED

- All outbound mail flows through `smtp.reply_email` (lines 97-102, 105-111).
  `reply_email` is the gateway method that enforces the recipient whitelist
  (`simple_email_gw/smtp/client.py` — `validate_email` + whitelist check
  before send). There is no `send_email` fallback in the loop.
- Sender extraction uses `parseaddr(msg["from"])[1]` (line 78), which
  returns the bare addr-spec — no display-name quoting issues, no RFC 5322
  parsing surface introduced by the loop.
- The guard-failure notice is plain text and loop-constructed (no agent
  output in the HTML path) — no XSS risk even if the sender is the owner.

### Agent output → email HTML path: VERIFIED

- `reply_html = await agent.process(handoff)` (line 76).
- Guard check `_contains_unsafe_html(reply_html)` (line 89) gates the send.
- On pass, `html_body=reply_html` is sent (line 109).
- The `md_to_html` tool (P2-008) escapes text content — that is the
  primary XSS prevention. The loop guard is defense-in-depth enforcement
  for the case where the agent emits raw HTML without calling `md_to_html`
  (e.g. via prompt injection). Both layers present, correct order.

### Credential handling: VERIFIED

- `_account_from_env` (`loop.py:116-126`) reads all values from
  `os.environ` / `os.environ.get`. No hardcoded credentials.
- `password=os.environ["EMAIL_PASSWORD"]` — required env var, no default.
- The gateway stores `password` as pydantic `SecretStr` (verified in the
  design review, `simple_email_gw/config.py:130`); `repr(account)` does
  not leak the password.
- The loop does not log the `EmailAccount` object or call
  `get_secret_value()` anywhere. The L1 implementation-time care point
  from the design review is satisfied.
- `.env` is gitignored (confirmed in the design review).

### Error handling security: VERIFIED

- Per-message exceptions: `except Exception` at `loop.py:173-177` logs via
  `logger.exception` and `continue`s. No `mark_message` call in the
  handler, so the message stays UNSEEN and is retried next poll (per
  spec §7). No reply is sent on the exception path.
- No error messages leaked to the sender: the only sender-visible text on
  a non-success path is the guard-failure notice, which is a fixed
  constant string with no error details (L2 care point satisfied).
- The agent's own replies may surface tool-error text by design (per
  `agents/assistant.md` Phase 3) — this is a documented agent-definition
  UX choice, not a loop bug, and the whitelist bounds who receives such
  text.

## New findings

None.

## Positive observations

- The four-way branching is exhaustive and ordered correctly: sentinel
  check before empty check before guard check before valid send. A
  sentinel wrapped in unsafe HTML (e.g. `<p>{{NO_REPLY}}</p>`) is
  correctly treated as no-reply, not as a guard failure
  (`test_process_one_sentinel_wrapped_in_html_still_detected`).
- The guard-failure path marks read without archiving, preventing both
  infinite retry and silent loss — the message is visible in the inbox
  for the owner to inspect.
- `_clean` handles `None` and missing fields via `value or ""` (line 58),
  so a missing `from`/`subject`/`date` cannot crash `build_message` or
  surface as the string `"None"`.
- The startup guard runs before `imap.connect()`, so no network resource
  is opened when the whitelist is unset — clean fast-fail.

## Security Findings Classification (round 0)

| Finding | Classification | Action |
|---------|----------------|--------|
| C1 — whitelist startup guard | Blocking | Implemented correctly — closed |
| M2 — CR/LF collapse in build_message | Related | Implemented correctly — closed |
| HTML guardrail (owner-approved) | Related | Implemented correctly — closed |
| L1 — credential logging care | New (from design) | Verified clean — no loop logging of secrets |
| L2 — error text in reply | New (from design) | Agent-definition concern; loop behavior correct |
| Future hardening — `<svg/onload>` bypass of `\son\w+=` | New (low) | Backlog: consider `[\s/]" prefix if production scope; acceptable for current demo |

No blocking, related, or new-actionable findings remain for P2-005/P2-006.