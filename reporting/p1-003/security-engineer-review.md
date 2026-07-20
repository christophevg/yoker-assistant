# Security-Engineer Review — P1-003 Mailbox Seam Implementation (Stage B)

- **Task:** P1-003 Implement the mailbox seam module
- **Reviewer:** security-engineer
- **Date:** 2026-07-20
- **Inputs:** `src/yoker_assistant/mailbox.py`, `tests/test_mailbox.py`, `.env.example`, `README.md`, `analysis/security-p1-003-mailbox.md` (design), `reporting/p1-003/consensus.md`
- **Steer:** owner directed "keep it slim" — dropped `assert_reply_safety_enabled()` (deferred startup whitelist check to P2-005/loop) and dropped custom `__repr__` (pydantic `SecretStr` redacts by default). Calibrate against this steer; do not demand abstractions the owner explicitly told us to drop unless security-load-bearing.

## Executive Summary

Both blocking items from the design review are resolved. The seam is a pure
1:1 wrapper over `simple_email_gw`; it does not reinvent the recipient
allowlist, does not read secrets, does not log, does not swallow
exceptions, and does not downgrade TLS. The deferral of the startup
whitelist assertion to P2-005 is acceptable: `simple_email_gw` enforces
the whitelist at send time regardless, so the deferred assertion is
defense-in-depth timing, not a correctness hole. The owner's slimness
steer did not remove any security-load-bearing control.

## Blocking Items — Verification

### 1. `reply()` routes HTML through `html_body=` in BOTH branches — PASS

`src/yoker_assistant/mailbox.py` lines 55-83. The `reply()` method's
signature names the parameter `html_body` (per consensus), and both
gateway call sites route it correctly:

- `reply_email` branch (lines 70-76): `body=text_body, html_body=html_body`
- `send_email` fallback branch (lines 78-83): `body=text_body, html_body=html_body`

`body=` is used ONLY for the plain-text `text_body` (default `""`). The
HTML content is never passed as `body=`. The agent's HTML is sent
verbatim as `text/html`; the seam does not sanitize or re-render it
(module docstring lines 6-9 assert this contract). OWASP A05
content-type confusion is avoided.

### 2. `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` present; wrong name absent — PASS

- `.env.example` line 15: `EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com`
- `README.md` line 72 (config block) and line 75 (prose): correct name used
- Grep over `src/`, `tests/`, `.env.example`, `README.md` for the wrong
  name `EMAIL_RECIPIENT_ADDRESSES`: **zero occurrences**. The silent-disable
  footgun documented in the design review is removed.

The README prose (lines 75-79) explicitly calls out that the whitelist
is the primary reply-safety boundary and that leaving it broad allows
replies to arbitrary senders — the security note is preserved.

## Design-Review Checklist — Verification

### 3. Seam does NOT reinvent the recipient allowlist — PASS

`mailbox.py` contains no allowlist code, no `is_allowed()` call, no
`WhitelistError` handling. `reply()` delegates directly to
`smtp.reply_email()` / `smtp.send_email()`, which call
`get_recipient_whitelist().is_allowed(to)` and raise `WhitelistError`
before sending. The enforcement point stays in the gateway, as
designed. The seam is pure wrapping.

### 4. No `get_secret_value()` outside gateway calls — PASS

Grep for `get_secret_value` / `secret_value` in `mailbox.py`: zero
matches. The seam never reads the password; it passes the
`EmailAccount` object to `IMAPClient(account)` / `SMTPClient(account)`,
and the gateway does its own `get_secret_value()` internally for auth.
Credential hygiene is preserved.

### 5. `Mailbox.__repr__` default does not leak the password — PASS

The custom `__repr__` was dropped per owner steer. Verified empirically
against the installed `simple_email_gw`:

- `EmailAccount.__repr__` renders `password=SecretStr('**********')` —
  pydantic redacts `SecretStr` fields by default. `username`,
  `imap_host`, `smtp_host` are shown (these are not credentials; the
  password is the credential and it is redacted).
- `Mailbox`'s default `repr` (no custom `__repr__`) renders as
  `<yoker_assistant.mailbox.Mailbox object at 0x...>` — it does NOT
  traverse `_account` at all. The `EmailAccount` is not surfaced by
  default repr.

No leak path. The owner's slimness call (drop custom `__repr__`) is
security-safe because pydantic does the redaction at the data layer and
the default object repr does not expand attributes. Note for future
contributors: if anyone later adds a custom `__repr__` that interpolates
`self._account`, they must exclude `password`/`oauth2_token` — but that
is a future-contributor concern, not a current finding.

### 6. Startup whitelist assertion deferred to P2-005 — ACCEPTABLE

The design review's blocking item #1 had two parts: (a) fix the env var
name, and (b) add a startup assertion that the whitelist is enabled.
Part (a) is done (item 2 above). Part (b) was deferred to P2-005 (the
loop) per owner steer.

Security assessment of the deferral:

- **Correctness is not affected.** `simple_email_gw`'s
  `SMTPClient.reply_email()`/`send_email()` call
  `get_recipient_whitelist().is_allowed(to)` on every send and raise
  `WhitelistError` before transmitting. The whitelist is enforced at
  send time regardless of whether the seam asserts at startup. The
  dangerous state (whitelist silently disabled) is now prevented by
  the correct env var name in `.env.example` and `README.md`.
- **The deferred assertion is defense-in-depth**, not the primary
  control. Its value is catching a future regression (e.g., a future
  env-var rename, an upstream field change, an operator typo in `.env`)
  before the loop starts rather than at first reply. That is a
  timing/visibility improvement, not a correctness gap.
- **P2-005 is the right owner for it.** The loop is where startup
  configuration is loaded and where fail-closed-vs-warn-loudly policy
  belongs (functional.md §7). Putting the assertion there keeps the
  seam pure.

Acceptable. Recommend the P2-005 entry retain the assertion requirement
(consensus blocking item #2 already records it).

### 7. No logging of message bodies / credentials / full headers — PASS

`mailbox.py` has no `logging` import, no logger, no `log.` calls
(grep confirmed zero matches). The seam emits nothing. The gateway's
own `safety.audit` module logs account name, subject prefix,
recipients, and success/failure (not bodies/passwords) — that posture
stands unmodified. No new logging surface is introduced, so there is
no new leak surface.

### 8. Exceptions propagated (no swallow) — PASS

`mailbox.py` has no `try`/`except` blocks (grep confirmed; the only
match for "except" was the word "exception" in the module docstring).
Every method `await`s the gateway call and returns its result
verbatim. Gateway exceptions (`RuntimeError`, `WhitelistError`,
`aioimaplib.Abort`, etc.) propagate to the caller (the loop, P2-005),
which owns §7's error policy (backoff/skip). The seam does not retry,
does not wrap, does not suppress. This matches the consensus ("the
seam propagates exceptions without retry").

### 9. TLS inherited from `simple_email_gw`; no downgrade — PASS

The seam's `__init__` takes an `EmailAccount` from the caller
(`account: EmailAccount` parameter) and passes it unchanged to
`IMAPClient(account)` / `SMTPClient(account)`. The seam does not
construct an `EmailAccount` itself, does not set `use_ssl`,
`imap_port`, `smtp_port`, or `use_starttls`, and does not build an
`ssl.create_default_context()` with downgraded options. TLS settings
are entirely the caller's responsibility; the seam cannot downgrade
what it does not touch.

Note: this means TLS-correctness now depends on whoever constructs the
`EmailAccount` (P2-005 loop / a future config loader). The design
review's Related finding (construct via `ServerConfig`/`get_accounts()`
so TLS 1.2+ defaults apply) carries forward to that task, not this
seam. The seam itself is neutral — it neither enforces nor weakens
TLS. Acceptable for P1-003's scope.

## STRIDE Re-check

- **Spoofing:** TLS inherited from gateway defaults (caller's account); seam does not downgrade. Inbound spoofed senders are P2-006's concern; reply-safety is enforced by gateway whitelist at send time. No change from design.
- **Tampering:** Seam methods are stateless 1:1 calls; ordering (send → mark read → archive) is the loop's job per §4.4. No hidden state in the seam.
- **Repudiation:** Gateway `safety.audit` logs stand unmodified; seam adds no logging, suppresses none.
- **Information Disclosure:** No `get_secret_value()` in seam; default `repr` does not traverse `_account`; `SecretStr` redacts password. No logging surface added. No exception wrapping that could leak or strip context.
- **Denial of Service:** No reconnect/backoff logic in seam (correct — loop owns §7). Seam cannot spin a reconnect storm because it does not retry.
- **Elevation of Privilege:** Unchanged from P1-002; no new privilege boundary.

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| `reply()` HTML routing via `html_body=` in both branches | Blocking — PASS | Verified; no change needed. |
| `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in `.env.example` + `README.md`; wrong name absent | Blocking — PASS | Verified; no change needed. |
| Startup whitelist assertion deferred to P2-005 | Related — ACCEPTABLE | Carry forward to P2-005 (consensus blocking item #2 already records it). Not blocking P1-003. |
| `Mailbox.__repr__` dropped (owner steer) | Related — PASS | Default repr does not leak; pydantic `SecretStr` redacts. No action. |
| TLS construction ownership | New — carry to P2-005 | Seam is neutral; whoever constructs `EmailAccount` (P2-005) should use `ServerConfig`/`get_accounts()` so TLS 1.2+ defaults apply. Add to P2-005 scope note. |
| Logging posture (counts, not bodies) | Related — N/A | Seam has no logging; nothing to enforce here. Carry posture requirement to P2-005 when the loop adds logging. |
| Exception wrapping in `MailboxError` | New — backlog | Owner kept the seam pure (no wrapping). Acceptable for P1-003; if the loop (P2-005) needs sanitized messages for log forwarders, add wrapping there. |

## Positive Observations

- Module docstring (lines 1-10) explicitly asserts the seam contract:
  pure wrapping, no allowlist, no HTML re-rendering, no exception
  wrapping, HTML routes through `html_body=`. This is a future-contributor
  guardrail exactly as the design review requested.
- `reply()` parameter named `html_body` (not `body`), making the routing
  unambiguous at the call site — the consensus synthesis resolved the
  only cross-review difference cleanly.
- No `subprocess`, no `open()`, no `__import__`, no shell, no file I/O
  in the seam (grep confirmed). Pure wrapping confirmed.
- The smoke test (`tests/test_mailbox.py`) confirms the seam constructs
  without network and exposes the expected method surface — a correct
  P1-003 scope test (full behavior tests land in P3-003, per the test
  file's own docstring).
- `.env.example` comment (lines 12-14) explicitly frames the whitelist
  as the primary reply-safety boundary and warns that leaving it broad
  allows replies to arbitrary senders — the security note survives.

## Verdict

**approved.**

Both blocking items from the design review are resolved and verified.
The owner's slimness steer (drop `assert_reply_safety_enabled()`, drop
custom `__repr__`) removed no security-load-bearing control: the
whitelist is enforced at send time by `simple_email_gw` regardless, and
pydantic `SecretStr` redacts the password in the default repr (which
does not even traverse `_account`). The deferred startup assertion and
TLS-construction-via-`ServerConfig` recommendation carry forward to
P2-005, where they belong. The seam is safe to ship as the P1-003
deliverable.