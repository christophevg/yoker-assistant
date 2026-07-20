# API Design Analysis — Task P1-003 (Mailbox Seam Module)

**Date:** 2026-07-20
**Task:** P1-003 — Implement the mailbox seam module (`yoker_assistant/mailbox.py`)
**Reviewer:** API Architect Agent
**Related documents:**
- `TODO.md` (P1-003 entry)
- `analysis/functional.md` §2.4, §4.3, §4.4, §5.1, §7
- `analysis/security-p1-003-mailbox.md` (security-engineer review)

## Summary

P1-003 introduces `yoker_assistant/mailbox.py`: a thin async seam wrapping
`simple_email_gw` 0.3.0's `IMAPClient`/`SMTPClient` around an `EmailAccount`
built from `.env`. The seam is **pure wrapping** — each public method maps 1:1
to a gateway call. No business logic, no mailbox-state machine, no recipient
allowlist reimplementation, no HTML re-rendering, no `subprocess`, no file I/O.

This analysis defines the typed public surface of `Mailbox`, the exact
mapping from each seam method to the verified `simple_email_gw` 0.3.0
function signatures, and the design decisions on connection lifecycle,
threading, ordering ownership, and testability. It is the contract between
the implementer (python-developer) and the reviewers (functional-analyst,
security-engineer).

### Consensus with security-engineer

This design adopts the security-engineer's recommendations in
`analysis/security-p1-003-mailbox.md`:

1. **`html_body` parameter name adopted per security-engineer.** The seam's
   `reply()` method takes `html_body` (not `body`) as the HTML reply
   parameter, making the routing to `simple_email_gw`'s `html_body=` kwarg
   explicit and unambiguous at every call site. A separate keyword-only
   `text_body=""` carries the plain-text alternative.
2. **P1-002 env-var errata is a blocking fix that lands alongside P1-003.**
   `.env.example` and `README.md` currently document
   `EMAIL_RECIPIENT_ADDRESSES`, but `simple_email_gw`'s pydantic
   `ServerConfig` binds `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (verified
   empirically). With the wrong name, `RecipientWhitelist.enabled` is
   silently `False` and `reply_email()` never raises `WhitelistError` —
   the agent replies to arbitrary senders. This must be corrected as part
   of landing P1-003 (see Blocking Concerns).
3. **The seam must NOT reinvent the recipient allowlist.** It delegates to
   `simple_email_gw`'s `RecipientWhitelist` (enforced inside
   `reply_email()`/`send_email()`). The seam must construct `EmailAccount`
   via the gateway's `ServerConfig`/`get_accounts()` so the gateway's TLS
   defaults and config binding apply. The seam must never call
   `SecretStr.get_secret_value()` outside gateway calls (the gateway
   handles credential extraction internally for auth).

## Verified `simple_email_gw` 0.3.0 Surface

Confirmed by reading the installed package at
`.venv/lib/python3.12/site-packages/simple_email_gw/`:

**Public API (`simple_email_gw/__init__.py`):**
- `EmailAccount`, `ServerConfig`, `RecipientWhitelist`, `RateLimitConfig`
- `IMAPClient`, `SMTPClient` (async)
- `SyncIMAPClient`, `SyncSMTPClient` (sync wrappers)
- `WhitelistError`, `SecurityError`, `validate_email`
- `sanitize_subject`, `sanitize_message_id`, `sanitize_references`,
  `sanitize_header_value`, `validate_append_flags`
- `log_email_sent`, `log_auth_attempt`, `log_event`, etc.

**`IMAPClient` async methods (verified signatures):**
```python
async def connect(self) -> IMAP4_SSL
async def disconnect(self) -> None
async def search(self, folder: str = "INBOX", criteria: str = "ALL", ...) -> list[str]
async def fetch_message(self, message_id: str, folder: str = "INBOX", ...) -> dict
async def mark_message(self, message_id: str, folder: str, flag: str, action: str) -> None
async def move_message(self, message_id: str, source_folder: str, dest_folder: str) -> None
```

**`SMTPClient` async methods (verified signatures):**
```python
async def send_email(
    self,
    to: list[str],
    subject: str,
    body: str,                          # plain text (text/plain) — required
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html_body: str | None = None,       # HTML (text/html) — optional
    attachments: list[str] | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    append_to_sent: bool = False,
    append_folder: str | None = None,
    imap_client: IMAPClient | None = None,
) -> dict[str, str | bool | None]

async def reply_email(
    self,
    to: str,
    subject: str,
    body: str,                          # plain text (text/plain) — required positional
    in_reply_to: str,                   # required positional
    references: list[str] | None = None,
    html_body: str | None = None,       # HTML (text/html) — optional
    append_to_sent: bool = False,
    append_folder: str | None = None,
    imap_client: IMAPClient | None = None,
) -> dict[str, str | bool | None]
```

**Key observations:**
- `reply_email` requires `body` (plain text) as a positional arg even when
  `html_body` is set — the seam must supply a plain-text fallback.
- `reply_email` enforces the recipient whitelist via
  `get_recipient_whitelist().is_allowed(to)` and raises `WhitelistError`
  before sending.
- `SMTPClient` is stateless per-send (`_send` opens/closes the connection
  each call via `aiosmtplib.send`) — no SMTP connection pooling is needed
  in the seam.
- `IMAPClient` holds a single long-lived `_client`; reconnects on demand
  when `_client is None`.
- All headers are sanitized inside `reply_email`/`send_email`
  (CRLF-injection protection). The seam must NOT bypass this by
  constructing raw MIME itself.

## Proposed `Mailbox` Interface (Typed Signatures)

```python
# yoker_assistant/mailbox.py

from __future__ import annotations
from typing import Any

from simple_email_gw import EmailAccount, IMAPClient, SMTPClient


class Mailbox:
  """Thin async seam over simple_email_gw's IMAPClient/SMTPClient.

  Pure wrapping. Each method maps 1:1 to a simple_email_gw call. No
  business logic, no recipient allowlist (delegates to the gateway's
  RecipientWhitelist), no HTML re-rendering, no subprocess, no file I/O.

  The EmailAccount is constructed via simple_email_gw's ServerConfig /
  get_accounts() so the gateway's TLS 1.2+ defaults and env-var binding
  apply. The seam never calls SecretStr.get_secret_value() outside
  gateway calls.
  """

  def __init__(self, account: EmailAccount) -> None: ...

  async def __aenter__(self) -> "Mailbox": ...
  async def __aexit__(self, *args: Any) -> None: ...

  async def connect(self) -> None:
    """Idempotent: return existing IMAP client if connected, else connect.
    Verifies the recipient whitelist is enabled at first connect (defense
    in depth per security-engineer Finding 1) and raises/warns if not."""

  async def close(self) -> None:
    """Safe to call when already closed. Disconnects IMAP. SMTP is per-send."""

  async def unread_ids(self) -> list[str]:
    """Search INBOX for UNSEEN message ids."""

  async def fetch(self, message_id: str) -> dict[str, Any]:
    """Fetch a single message by id from INBOX. Returns the gateway's
    message dict (id, folder, subject, from, to, body, attachments, ...)."""

  async def reply(
    self,
    to: str,
    subject: str,
    html_body: str,
    in_reply_to: str,
    *,
    text_body: str = "",
  ) -> None:
    """Send an HTML reply preserving thread context.

    html_body  -> gateway's html_body= (Content-Type: text/html)
    text_body  -> gateway's body=      (Content-Type: text/plain fallback)
    in_reply_to -> gateway's in_reply_to= (sets In-Reply-To/References headers)

    Reply-safety is enforced by simple_email_gw's RecipientWhitelist inside
    reply_email(); this seam does NOT reimplement the allowlist."""

  async def mark_read(self, message_id: str) -> None:
    """Add the \\Seen flag to a message in INBOX."""

  async def archive(self, message_id: str) -> None:
    """Move a message from INBOX to the archive folder."""

  def __repr__(self) -> str:
    """Redacting repr — includes account.name, imap_host, smtp_host only.
    Never username, password, oauth2_token, or the EmailAccount object."""
```

### Signature decisions

- **`reply(to, subject, html_body, in_reply_to, *, text_body="")`** —
  `html_body` is the required positional for the HTML reply (adopted per
  security-engineer). `text_body=""` is keyword-only so callers do not
  accidentally pass HTML as the plain-text alternative. `in_reply_to` is
  positional because it is structurally required for a threaded reply
  (the gateway's `reply_email` requires it positionally too).
- **`unread_ids() -> list[str]`** — narrows the gateway's `search()` to
  the only criteria the loop uses (`UNSEEN` in `INBOX`). Hides the
  `folder`/`criteria` kwargs from the loop; the loop does not need them.
- **`fetch(message_id) -> dict`** — narrows `fetch_message` to INBOX and
  the single id-per-iteration model. The returned dict is the gateway's
  own shape; the seam does not re-shape it (reshaping belongs in the
  handoff builder, P2-006).
- **`mark_read(message_id)`** and **`archive(message_id)`** — narrow
  `mark_message`/`move_message` to the loop's fixed folders. The archive
  folder name is configured at construction (from env), not per-call.
- **No `send()` method** — the only outbound path is `reply()`. A
  non-threaded send would be a separate seam method only if the loop
  needs it (P2-007 fallback to `send_email` when no Message-ID is
  available). For the first pass, `reply()` is the only send surface; if
  P2-007 needs the fallback, a `send(to, subject, html_body, *,
  text_body="")` method is added at that time with the same `html_body` /
  `text_body` convention. Documented here so the convention is settled.

## Mapping Table

| Seam method | simple_email_gw call | Notes |
|---|---|---|
| `Mailbox.__init__(account)` | (store `account`; lazy `IMAPClient(account)`) | Do not construct `SMTPClient` here — it is stateless per-send. |
| `Mailbox.connect()` | `await self._imap.connect()` | Idempotent: if `self._imap._client is not None`, return. Also call `simple_email_gw.get_recipient_whitelist()` once at first connect and assert `enabled is True` and addresses non-empty (fail-closed per security-engineer Finding 1). |
| `Mailbox.close()` | `await self._imap.disconnect()` | Safe to call when already closed (guard on `self._imap._client`). SMTP is per-send, nothing to close. |
| `Mailbox.unread_ids()` | `await self._imap.search(folder="INBOX", criteria="UNSEEN")` | Returns `list[str]`. |
| `Mailbox.fetch(message_id)` | `await self._imap.fetch_message(message_id=message_id, folder="INBOX")` | Returns the gateway's message dict verbatim. |
| `Mailbox.reply(to, subject, html_body, in_reply_to, *, text_body="")` | `smtp = SMTPClient(self._account); await smtp.reply_email(to=to, subject=subject, body=text_body, in_reply_to=in_reply_to, html_body=html_body)` | Constructs a fresh `SMTPClient` per reply (stateless per-send, cheap). Routes HTML through `html_body=` and plain-text through `body=`. Reply-safety enforced inside `reply_email` via `RecipientWhitelist`. |
| `Mailbox.mark_read(message_id)` | `await self._imap.mark_message(message_id=message_id, folder="INBOX", flag="\\Seen", action="add")` | Idempotency: adding `\Seen` twice is a no-op. |
| `Mailbox.archive(message_id)` | `await self._imap.move_message(message_id=message_id, source_folder="INBOX", dest_folder=self._archive_folder)` | `dest_folder` from env (default `Archive`), stored at construction. |
| `Mailbox.__repr__()` | (no gateway call) | `f"Mailbox(name={self._account.name!r}, imap={self._account.imap_host!r}, smtp={self._account.smtp_host!r})"` — never `username`/`password`/`oauth2_token`. |

### Fallback path (P2-007, documented for convention continuity)

If `in_reply_to` is unavailable (no RFC Message-ID in the fetched
message), P2-007 will add a `send()` seam method:

```python
async def send(
    self,
    to: str,
    subject: str,
    html_body: str,
    *,
    text_body: str = "",
) -> None:
    smtp = SMTPClient(self._account)
    await smtp.send_email(to=[to], subject=subject, body=text_body, html_body=html_body)
```

Same `html_body` / `text_body` convention; routes through
`send_email(..., html_body=html_body, ...)`.

## Connection-Lifecycle Recommendation

- **IMAP is long-lived; SMTP is per-send.** The seam holds a single
  `IMAPClient(account)` for the loop's lifetime and reconnects on drop.
  `SMTPClient(account)` is constructed fresh inside each `reply()` call
  (the gateway's `_send` opens/closes the SMTP connection per call via
  `aiosmtplib.send`, so pooling gains nothing).
- **`connect()` is idempotent.** If `self._imap._client is not None`,
  return immediately. Otherwise call `await self._imap.connect()`. This
  lets the loop call `connect()` at the top of every iteration without
  spawning duplicate connections.
- **`close()` is safe to call when already closed.** Guard on
  `self._imap._client is not None` before calling `disconnect()`. Called
  on graceful shutdown (`SIGINT`/`SIGTERM`) and from `__aexit__`.
- **On IMAP drop, disconnect and let the loop reconnect.** If an IMAP
  operation raises `RuntimeError`/`aioimaplib.Abort`/`aioimaplib.Error`
  (the gateway wraps most drops into `RuntimeError`), the seam should
  call `await self._imap.disconnect()` so the next operation triggers a
  fresh `connect()`. The seam does NOT retry inside itself — backoff is
  the loop's job (P2-005, §7).
- **No reconnect storm.** The loop backs off (double the interval up to
  a cap) when `connect()` fails; the seam's job is to fail cleanly and
  let the loop decide. `connect()` raising is the correct signal.
- **No `ConnectionPool`.** The gateway ships one, but the single-account,
  single-loop first pass does not need it. `IMAPClient(account)` directly
  is correct; do not pool across iterations.
- **Context manager.** `async with Mailbox(account) as mb:` calls
  `connect()` on enter and `close()` on exit. The loop may also
  construct it once and call `connect()`/`close()` explicitly to span
  many iterations.

## Threading/Reply Recommendation

- **Use `reply_email()`, not `send_email()`, for replies.** The fetched
  message dict from `IMAPClient.fetch_message()` includes the RFC
  Message-ID header, so `in_reply_to` is available and `reply_email` is
  usable. `reply_email` sets `In-Reply-To` and `References` headers
  (sanitized by the gateway) and preserves thread context in the owner's
  mail client.
- **P2-007 fallback** (documented above): if no Message-ID is available,
  fall back to `send_email` with `subject=f"Re: {subject}"`. The seam
  provides the `send()` method for this path; the loop chooses which to
  call based on the fetched message's Message-ID.
- **`references` is not surfaced** in the seam's `reply()` signature for
  the first pass. The gateway derives `References` from `in_reply_to`
  internally. If threading across multiple ancestors is ever needed, add
  a `references: list[str] | None = None` keyword-only arg then.

## Ordering Ownership

The seam does NOT own the reply → mark-read → archive ordering. That is
the loop's job (P2-005, §4.4):

1. `reply()` must succeed before `mark_read()` is called.
2. `mark_read()` must succeed before `archive()` is called.
3. If `reply()` fails, the message stays `UNSEEN` and is retried next
   iteration (no `mark_read`, no `archive`).
4. If `reply()` succeeds but `mark_read()` fails, the message stays
   `UNSEEN`; next iteration it is reprocessed and a duplicate reply is
   sent. To avoid duplicates on this partial-failure path, the loop
   marks read **immediately** after a successful send, before archiving.
   A marked-read-but-not-archived message is excluded from `UNSEEN`, so
   it will not be reprocessed; it lingers in INBOX until the next loop
   tidies it.

The seam's methods are callable in that order without hidden state
between them — `reply()` does not mark read, `mark_read()` does not
archive, `archive()` does not reply. This is the pure-seam property the
functional spec requires.

## No Business Logic Confirmation

The seam contains:
- No `subprocess`.
- No `open()` of local files.
- No `attachments=` kwarg passed to `send_email`/`reply_email`
  (attachments are out of scope per `functional.md` §8.6).
- No agent/reasoning logic.
- No interpretation of message bodies (the fetched dict is returned
  verbatim).
- No recipient allowlist (delegates to `simple_email_gw`'s
  `RecipientWhitelist`).
- No HTML sanitization or re-rendering (the HTML is sent verbatim via
  `html_body=`; sanitization is the agent's responsibility per §4.2 —
  the agent authored the HTML via a bounded tool).
- No `SecretStr.get_secret_value()` calls outside gateway calls (the
  gateway handles credential extraction internally for auth).

Each seam method maps 1:1 to a gateway call. The implementer should add a
module-level docstring asserting this contract so a future contributor
does not drift it.

## Type Hints + Guardrails

- Full type hints on every public method (see Proposed Interface above).
- `from __future__ import annotations` for forward references.
- `dict[str, Any]` for the fetched message (the gateway's shape is
  dict-based; a TypedDict can be added later if the handoff builder
  P2-006 would benefit, but for the first pass `dict[str, Any]` is
  honest).
- No `Optional` leak: `connect()`/`close()` take no args; `fetch` takes
  a required `message_id`; `reply` takes four required positionals and
  one keyword-only default.
- The seam does not catch `WhitelistError`, `SecurityError`, or
  `RuntimeError` to swallow them — it lets them propagate (the loop
  decides retry/skip per §7). Exception *wrapping* to strip host/PII
  detail is recommended (see below) but must chain the original via
  `from e`.

### Exception wrapping (security-engineer Finding 6, recommended)

Wrap gateway exceptions in a seam-specific exception carrying a
sanitized message; chain the original via `from e` so debug mode can
still see it. Surface `"IMAP connect failed"` / `"SMTP send failed"` /
`"mailbox fetch failed"` to INFO; keep the `{e}` detail for DEBUG only.
Never include `account.username`, `account.password`, or the full
`EmailAccount` in an exception message or log line — use `account.name`.

```python
class MailboxError(RuntimeError):
  """Sanitized seam error. Original chained via `from e`."""
```

This is a recommendation, not a blocking requirement; the first pass may
let gateway exceptions propagate raw if the loop's logging already
sanitizes them. The blocking concerns are in Blocking Concerns below.

## Testability

- **Dependency injection via constructor.** `Mailbox(account)` takes the
  `EmailAccount` as its only argument. Tests construct a fixture
  `EmailAccount` (or a stub with the same shape) and pass it in.
- **`P3-003` test scope:** `tests/test_mailbox.py` exercises the seam
  against `simple_email_gw`'s public surface with a stub/spool or a
  documented test account if the gateway provides one. Behavior-based,
  not exhaustive: assert each seam method calls the expected gateway
  method with the expected args; assert `reply()` routes HTML through
  `html_body=` and plain-text through `body=`; assert `__repr__` redacts
  credentials.
- **No network in unit tests.** The seam's purity (1:1 delegation) makes
  it mockable: patch `IMAPClient`/`SMTPClient` at the module level and
  assert call args. A live IMAP/SMTP integration test belongs in a
  separate, opt-in test marker (`@pytest.mark.live`) so `make test`
  stays hermetic.
- **`--once` flag (P2-005) is the end-to-end smoke test.** The seam
  itself does not own a `--once` path; the loop does. The seam's
  testability rests on its 1:1 mapping being trivially mockable.

## Action Items / `TODO.md` Recommendations

I do not edit `TODO.md` directly. Recommendations to integrate into
P1-003 and related entries:

1. **P1-003 acceptance criteria — add two blocking checks:**
   - "the seam's `reply()` passes the agent's HTML through the gateway's
     `html_body=` parameter (not `body=`), so the reply is sent as
     `text/html`; a plain-text fallback is passed as `body=` via the
     keyword-only `text_body` parameter;"
   - "the seam (or the loop at startup) asserts that
     `simple_email_gw.get_recipient_whitelist().enabled` is `True` and
     the address list is non-empty, and fails closed (or warns loudly,
     per owner decision) otherwise."

2. **P1-003 scope note — seam contract.** Append to the scope note:
   "The seam is pure wrapping. It must NOT (a) reinvent the recipient
   whitelist — it delegates to `simple-email-gw`'s `RecipientWhitelist`;
   (b) sanitize or re-render the HTML reply — it sends the agent's HTML
   verbatim via `html_body=`; (c) call `SecretStr.get_secret_value()`
   except where required to pass credentials to the gateway (the gateway
   already does this internally, so the seam should not need to);
   (d) add `subprocess`, file I/O, or business logic; (e) pass
   `attachments=` to `send_email`/`reply_email` (attachments are out of
   scope)."

3. **P1-003 scope note — TLS.** Append: "The seam must not downgrade
   transport security. Construct `EmailAccount` via the gateway's
   `ServerConfig`/`get_accounts()` so TLS 1.2+ defaults apply. If the
   seam builds `EmailAccount` directly, it must refuse or loudly warn on
   any configuration that would authenticate over a plaintext transport."

4. **P1-003 scope note — logging.** Append: "The seam logs connection
   events and counts (unread count, fetched id, replied recipient
   subject prefix, mark_read id, archived id) at INFO; it never logs
   message bodies, credentials, or full headers."

5. **P1-003 scope note — `reply()` signature.** Update the task's
   method sketch from `reply(to, subject, body, in_reply_to)` to
   `reply(to, subject, html_body, in_reply_to, *, text_body="")` and
   note that the HTML routes through `html_body=` and the plain-text
   fallback through `body=`.

6. **P1-002 errata / fix — env-var name.** Open a follow-up to rename
   `EMAIL_RECIPIENT_ADDRESSES` → `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`
   (and `EMAIL_RECIPIENT_DOMAINS` → `EMAIL_RECIPIENT_WHITELIST_DOMAINS`
   if documented) in `.env.example` and `README.md` (Configuration
   section). This is a P1-002 deliverable correction but blocks
   P1-003's reply-safety guarantee, so it lands alongside P1-003. Add a
   note to the P1-003 entry referencing this dependency.

7. **P2-007 — reply-safety config name.** Update P2-007's
   "Recipient safety is a `simple-email-gw` config concern
   (`EMAIL_RECIPIENT_ADDRESSES`)" line to the correct env var
   `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`.

8. **P4-001 (tutorial README) — reply-safety subsection.** When the
   tutorial is written, the "Security configuration" subsection must
   use the correct env var name `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`
   and explicitly call out that the whitelist is the primary
   reply-safety boundary and is silently disabled if the env var is
   wrong or unset.

9. **New backlog item S-03** (already proposed by security-engineer):
   file an upstream issue/PR against `simple-email-gw` — its README
   documents `EMAIL_RECIPIENT_ADDRESSES` / `EMAIL_RECIPIENT_DOMAINS`,
   but the pydantic config binds `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` /
   `EMAIL_RECIPIENT_WHITELIST_DOMAINS`. Low effort, high value.

## Blocking Concerns

Two items must land before P1-003's `reply()` can be considered
safe-to-ship:

1. **Env-var errata (security-engineer Finding 1, Critical).**
   `.env.example` and `README.md` must use
   `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (the env var the gateway's
   pydantic `ServerConfig` actually binds), not
   `EMAIL_RECIPIENT_ADDRESSES`. With the wrong name,
   `RecipientWhitelist.enabled` is silently `False` and `reply_email()`
   never raises `WhitelistError` — the agent replies to arbitrary
   senders. Verified empirically against the installed package. This is
   a P1-002 deliverable correction that blocks P1-003's reply-safety
   guarantee, so it lands alongside P1-003.

2. **`html_body=` routing (security-engineer Finding 3, High).** The
   seam's `reply()` must route the agent's HTML through the gateway's
   `html_body=` parameter (not `body=`), so the reply is sent as
   `text/html`. The adopted signature `reply(to, subject, html_body,
   in_reply_to, *, text_body="")` makes this unambiguous at every call
   site: `html_body` → `reply_email(..., html_body=html_body, ...)`,
   `text_body` → `reply_email(..., body=text_body, ...)`.

The remaining security-engineer findings (redacting `__repr__`,
exception wrapping, logging posture, TLS-downgrade refusal,
reconnect/backoff) are hardening recommendations, not blocking. They
should be implemented as part of P1-003 where trivial (e.g.,
`__repr__`, `html_body=` routing, whitelist-enabled assert) and tracked
as follow-ups where they touch the loop (P2-005 backoff) or cross-cut
logging posture.