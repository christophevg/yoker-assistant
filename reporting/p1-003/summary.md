# P1-003 — Implement the mailbox seam module (Task Summary)

- **Task:** P1-003 Implement the mailbox seam module
- **Branch:** `feature/p1-003-mailbox-seam`
- **PR:** #3 — https://github.com/christophevg/yoker-assistant/pull/3
- **Status:** pending review (implementation complete, all review stages approved, `make check` green; awaiting owner merge)

## What was implemented

- `src/yoker_assistant/mailbox.py` — a slim async seam (`Mailbox` class) over `simple_email_gw`'s `IMAPClient` + `SMTPClient`. Seven async methods, each a one-line delegation to one gateway call: `connect`, `close`, `unread_ids`, `fetch`, `reply`, `mark_read`, `archive`. `reply()` branches on `in_reply_to` (→ `reply_email` or `send_email` fallback) — transport routing, not business logic. `fetch()` returns the raw gateway dict (no `EmailMessage` dataclass).
- `tests/test_mailbox.py` — a minimal smoke test (`test_mailbox_constructs_without_network`) + a regression test (`test_reply_routes_html_through_html_body_kwarg`) asserting `reply()` routes HTML through `html_body=` (not `body=`) in both branches, using a recording stub for the SMTP client. No network.
- P1-002 errata (in the analysis commit): `.env.example` + `README.md` rename `EMAIL_RECIPIENT_ADDRESSES` → `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (the documented env var silently disabled the reply-safety whitelist).
- functional.md §2.4 + §4.3 errata (in the analysis commit + this commit): corrected the `async with IMAPClient(...)` snippet (simple_email_gw 0.3.0 clients are not async context managers); recorded that `Mailbox` uses explicit `connect()`/`close()` (no `__aenter__`/`__aexit__` — slimness decision); clarified HTML content-type lives in simple_email_gw (`html_body=`).
- TODO.md updates: P1-003 consensus contract; P2-007 (send() method redundant — slim reply() folds both paths); P2-006 (build_message accepts the raw dict, not an EmailMessage dataclass); P3-003 (DI approach to be decided; html_body= regression test required); P4-001 (correct env var name); S-03 backlog (upstream simple-email-gw docs issue).

## Owner directive honored

The owner approved the plan with a binding steer: "keep it slim — a demo/tutorial; avoid over-engineering." The implementation trimmed the planned design: dropped the `EmailMessage` dataclass (fetch returns the raw dict), DI kwargs, `__aenter__`/`__aexit__`, `MailboxError` exception wrapping, `assert_reply_safety_enabled` helper (deferred to P2-005), custom `__repr__` (EmailAccount.password is a pydantic SecretStr that redacts by default), and logging. 91 lines → trimmed further by L1 (dropped `self._account` dead state) and L2 (collapsed `fetch()` to a one-liner).

## Key decisions

- **Slim facade** — one `Mailbox` class holding one `IMAPClient` + one `SMTPClient`; each method is a one-line delegation. The seam earns its place (one object instead of two clients + the reply branch + the security-load-bearing `html_body=` parameter name); using `simple_email_gw` directly would push the two-client pairing and reply routing into the loop — the "two halves bleed" §2.2 forbids.
- **`reply(to, subject, html_body, in_reply_to=None, *, text_body="")`** — HTML routes through `html_body=` (the blocking security requirement); `text_body` is the optional plain-text alternative (intentionally empty in the first pass). Branches on `in_reply_to` → `reply_email` or `send_email` fallback.
- **Loop owns ordering + §7 error policy** — the seam propagates exceptions without retry/wrapping; the loop (P2-005) owns send→mark-read→archive ordering and backoff/skip.
- **Reply-safety boundary stays in `simple_email_gw`** (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`); the seam does NOT reinvent the allowlist. The startup whitelist assertion is deferred to P2-005 (the whitelist is enforced at send time regardless; the assertion is defense-in-depth).
- **TLS inherited** from `simple_email_gw` (the seam takes `EmailAccount` from the caller unchanged; no hand-built downgraded account).

## Files modified

- `src/yoker_assistant/mailbox.py` (slim seam)
- `tests/test_mailbox.py` (smoke + html_body regression test)
- `TODO.md` (P1-003 contract + downstream scope updates + env-var fixes + S-03)
- `analysis/functional.md` (§2.4 + §4.3 errata + M1 reconciliation)
- `.env.example` + `README.md` (P1-002 env-var rename errata — in the analysis commit)

## Review cycle

| Stage | Result |
|-------|--------|
| functional-analyst | approved |
| api-architect | approved |
| security-engineer | approved |
| code-reviewer | approved (L1/L2 applied; M1 spec reconciled) |
| testing-engineer | approved (html_body regression test added) |
| end-user-documenter | approved |

`make check` passed (format, lint, typecheck, 3 tests).

## Follow-ups recorded

- **P2-005:** owns the startup whitelist assertion (`get_recipient_whitelist().enabled is True` and non-empty — fail closed) and the `Mailbox` lifecycle (explicit `connect()`/`close()`).
- **P2-006:** `build_message` accepts the raw `simple_email_gw` dict (not an `EmailMessage` dataclass).
- **P2-007:** no new `Mailbox.send()` method (slim `reply()` folds both paths); remaining job is loop-side `Re:` subject + Message-ID handling.
- **P3-003:** decides DI vs monkeypatching for seam tests; expands the html_body= routing regression test; must land before P2-007 wires live replies (satisfied in part by the P1-003 regression test).
- **S-03:** file upstream issue against `simple-email-gw` for wrong env var name in its README.
- **pkgq tool name:** `pkgq:find` (not `pkgq:find_package`) — noted in P2-001; functional.md §3.2/§3.3 errata when P2-001 lands.

## Lessons learned

- The owner's slimness steer is a first-class acceptance criterion for demo/tutorial projects. The planned design (EmailMessage dataclass, DI kwargs, __aenter__/__aexit__, MailboxError, assert helper, __repr__, logging) was over-engineered for a thin facade over `simple_email_gw`. The trim did not go too far — every dropped abstraction was sanctioned by the owner and broke nothing the loop needs.
- A `type: ignore[no-any-return]` was needed on the collapsed `fetch()` one-liner because `simple_email_gw` is untyped (`ignore_missing_imports`) and mypy strict flags the `Any` return; `warn_unused_ignores` will catch it if the gateway ever ships stubs.
