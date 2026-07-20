# Functional Review — P1-003 Mailbox Seam Module

- **Task:** P1-003 Implement the mailbox seam module
- **Branch:** `feature/p1-003-mailbox-seam`
- **Implementation:** `src/yoker_assistant/mailbox.py` (91 lines)
- **Test:** `tests/test_mailbox.py` (smoke test, 26 lines)
- **Reviewer:** functional-analyst
- **Date:** 2026-07-20
- **Steer context:** Owner directive — keep it slim; a demo/tutorial project;
  avoid over-engineering. "I might revert it if it introduces unnecessary
  abstractions and/or indirections." Slimness is a first-class acceptance
  criterion alongside the functional criteria. The cross-domain consensus
  contract is treated as a **ceiling, not a target** — the slim version
  legitimately drops abstractions the owner flagged.

## Verdict

**approved** — The implementation is appropriately slim, meets every
functional acceptance criterion, satisfies both blocking security items, and
introduces no abstraction that fails to earn its place. `make check` passes
(format, lint, mypy strict, 2 tests).

## Functional Acceptance Criteria

### 1. One-to-one delegation; `reply()` branches on `in_reply_to` — PASS

Every method delegates to exactly one `simple_email_gw` call:
- `connect()` → `imap.connect()`
- `close()` → `imap.disconnect()`
- `unread_ids()` → `imap.search(folder=…, criteria="UNSEEN")`
- `fetch(id)` → `imap.fetch_message(id, folder=…)`
- `mark_read(id)` → `imap.mark_message(id, folder, "\\Seen", "add")`
- `archive(id)` → `imap.move_message(id, folder, archive_folder)`
- `reply(…)` branches on `in_reply_to is not None`:
  - truthy → `smtp.reply_email(to=, subject=, body=text_body, html_body=html_body, in_reply_to=)`
  - falsy  → `smtp.send_email(to=[to], subject=, body=text_body, html_body=html_body)`

The branch is transport routing (which gateway method sends the message),
not business logic. Confirmed against the installed
`simple_email_gw` 0.3.0 signatures — every call site matches the gateway's
parameter names and types (`reply_email(to: str, subject, body, in_reply_to,
references=None, html_body=None, …)`;
`send_email(to: list[str], subject, body, …, html_body=None, …)`).

### 2. No inline agent/reasoning logic — PASS

The seam contains only delegation. No categorization, no handoff
construction, no markdown/HTML manipulation, no interpretation of message
bodies. The module docstring asserts this contract explicitly.

### 3. BLOCKING SECURITY: HTML routes through `html_body=` in BOTH branches — PASS

- `reply_email` branch (line 70-76): `html_body=html_body` — correct.
- `send_email` branch (line 78-83): `html_body=html_body` — correct.
- `body=text_body` (the plain-text fallback, empty by default) in both
  branches — correct.

The agent's HTML is never passed as `body=`. The gateway sets
`Content-Type: text/html` via `msg.add_alternative(html_body, subtype="html")`
when `html_body` is provided (verified in
`simple_email_gw/smtp/client.py` lines 253-260 and 352-354).

### 4. BLOCKING SECURITY: env-var rename present — PASS

- `.env.example` line 11: `EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com`
  with an explanatory comment stressing it is the primary reply-safety
  boundary.
- `README.md` line 72: `EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com`;
  line 75 explicitly calls it "the **primary reply-safety boundary**".

The wrong name (`EMAIL_RECIPIENT_ADDRESSES`) does not appear in either file.
The silent-disable footgun documented in the security analysis is closed.

### 5. All seven methods present and async — PASS

`connect`, `close`, `unread_ids`, `fetch`, `reply`, `mark_read`, `archive`
all present, all `async def`. The smoke test programmatically asserts
`hasattr(mailbox, name)` for each.

### 6. `make check` passes — PASS

```
uv run ruff format --check src tests    → 9 files already formatted
uv run ruff check src tests             → All checks passed!
uv run mypy src                         → Success: no issues found in 7 source files
uv run pytest -v                        → 2 passed
```

The approach is sound: format → lint → strict mypy → tests. mypy strict
passing on a `dict[str, Any]` return from `fetch()` is correct — the gateway
itself returns `dict[str, Any]`, so the seam's typing reflects reality
rather than pretending a typed surface that the gateway does not guarantee.

### 7. Minimal smoke test exists; P3-003 behavior tests deferred — PASS

`tests/test_mailbox.py` builds a dummy `EmailAccount`, constructs a
`Mailbox`, asserts it is non-None, and asserts each of the seven methods
exists. No network. The docstring explicitly states full seam behavior tests
(html_body routing assertions, DI stubs) land in P3-003. Correct division.

### 8. Startup whitelist assertion deferred to P2-005 — PASS

The module docstring (lines 6-7) states: "the loop (P2-005) owns
backoff/skip and the startup whitelist-enabled check." This is the correct
seam/loop boundary: a fail-closed assertion at startup belongs in the loop
where it can refuse to enter the run state, not in a library seam that may
be constructed in tests. Acceptable per the slim steer.

## Slimness Criterion (Owner Directive)

### 9. Would using `simple_email_gw` directly be simpler? — No, the seam earns its place

Honest evaluation: the seam is a **thin facade**, not an abstraction layer.

What the seam adds over direct gateway use:
- **One object instead of two.** The loop holds a `Mailbox`, not a separate
  `IMAPClient` + `SMTPClient` pair. `connect()`/`close()` manage both
  lifecycles through a single surface.
- **Folder defaults in one place.** `inbox_folder="INBOX"` and
  `archive_folder="Archive"` are constructor parameters, so every method
  call sites stays short (`mailbox.archive(id)` vs
  `imap.move_message(id, "INBOX", "Archive")`).
- **The `reply()` branch.** The choice between `reply_email` and
  `send_email` on `in_reply_to` presence is the one piece of routing logic
  the project needs to keep out of the loop. Centralizing it here is the
  seam's actual job.
- **Named HTML parameter.** `html_body=` is the security-load-bearing
  parameter name; the seam's signature makes the routing unambiguous at
  every call site.

What the seam does NOT add: no new types, no exception hierarchy, no
logging layer, no context-manager protocol, no DI container, no retry, no
backoff, no whitelist reimplementation. Each method body is one statement.
This is the minimum viable facade.

Verdict: the seam is justified. Using the gateway directly would push the
two-client pairing and the reply-branch logic into the loop (P2-005), which
is exactly the "two halves bleed" the architecture §2.2 forbids.

### 10. Dropped abstractions verified absent — PASS

Cross-checked against the consensus contract list:

| Abstraction | Dropped? | Notes |
|---|---|---|
| `EmailMessage` dataclass | Yes | `fetch()` returns the gateway's `dict[str, Any]` verbatim with a docstring listing the keys. |
| DI kwargs (`imap_client`/`smtp_client`) | Yes | Constructor takes only `account` and folder defaults. P3-003 will adapt (see Notes). |
| `__aenter__`/`__aexit__` | Yes | Loop calls `await connect()` / `await close()` directly. |
| `MailboxError` exception wrapping | Yes | Gateway exceptions propagate unchanged. |
| `assert_reply_safety_enabled` helper | Yes | Deferred to P2-005 per docstring. |
| `__repr__` | Yes | Not defined; pydantic's `SecretStr` redaction on `EmailAccount` is the remaining safeguard. |
| Logging | Yes | No `logging` import; the gateway's own `safety.audit` logs stand. |

The result is slim: 91 lines including docstrings and blank lines; 7 async
methods + `__init__`; no dead surface.

### 11. Line count and method count — minimum viable — PASS

91 lines total. Method bodies are 1-3 lines each. The longest method
(`reply`) is ~20 lines only because of the branch and multi-line kwargs;
the actual logic is one `if/else`. No leftover ceremony: no `__repr__`, no
`__aenter__`, no properties, no helper functions, no module-level constants
beyond the import. This is the minimum viable seam.

## Edge Cases / Regressions

### 12. `in_reply_to=None` fallback — PASS

When `in_reply_to is None`, the seam calls `smtp.send_email(to=[to],
subject=subject, body=text_body, html_body=html_body)` — no `Re:` prefix
is added, no subject rewriting. Per §4.3 the `Re:` subject is the loop's
job (P2-007: "Fallback to `send_email` with `Re: <subject>`"). The seam
correctly does not encroach on that responsibility.

### 13. mypy strict — PASS

`uv run mypy src` reports no issues across 7 source files. The
`dict[str, Any]` return on `fetch()` is honestly typed (the gateway returns
the same shape); no false precision.

### 14. No regressions — PASS

Both existing tests pass:
- `tests/test_import_safety.py::test_package_imports` — PASS
- `tests/test_mailbox.py::test_mailbox_constructs_without_network` — PASS

The smoke test is the only new test; it exercises construction and method
presence without a network, so it cannot regress in CI environments.

## Notes for Downstream Tasks (non-blocking)

These are not P1-003 issues — they are consequences of the slim steer that
downstream tasks will need to handle. Recording them here so they are not
lost:

1. **P2-006 (handoff builder)** references "the `EmailMessage` dataclass
   defined in P1-003 (not a raw dict)". The slim version drops that
   dataclass; `fetch()` returns `dict[str, Any]`. P2-006 will need to
   either accept a dict (typed as a TypedDict or `dict[str, Any]`) or
   define its own dataclass at that point. The fetch() docstring lists the
   available keys (`id`, `folder`, `subject`, `from`, `to`, `date`, `body`,
   `attachments`, `read`, `message_id`, `references`) — that contract is
   preserved even though the dataclass is not.

2. **P3-003 (mailbox seam tests)** specifies "Stub clients injected via
   `Mailbox(..., imap_client=..., smtp_client=...)`". The DI kwargs are
   dropped per the slim steer. P3-003 will need to either monkeypatch the
   `_imap`/`_smtp` attributes, or reintroduce a DI surface at that point
   if the owner prefers DI over monkeypatching. This is a P3-003 decision,
   not a P1-003 defect — the prompt explicitly authorizes dropping the DI
   kwargs.

3. **P2-005 (the loop)** owns the startup whitelist-enabled assertion and
   the `Re:` subject prefix for the `send_email` fallback path. The seam's
   docstring makes this boundary explicit.

## Summary

The implementation is the minimum viable thin facade the owner asked for:
seven async methods, one branch in `reply()`, no ceremony. Both blocking
security items are satisfied (HTML routes through `html_body=` in both
branches; the env-var rename is present in both `.env.example` and
`README.md`). `make check` is green across format, lint, mypy strict, and
tests. The downstream consequences of the slim drops (EmailMessage
dataclass, DI kwargs) are noted for P2-006 and P3-003 to handle in their
own scope.