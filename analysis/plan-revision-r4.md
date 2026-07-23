# Plan Revision R4 — Owner Feedback Round 3 on PR #7 (P2-005 + P2-006)

**Date:** 2026-07-23
**Author:** Functional Analyst
**Scope:** Incorporate the four inline owner comments on `src/yoker_assistant/loop.py`
(review state: CHANGES_REQUESTED) into the implementation plan for the combined
P2-005 + P2-006 task. The dominant theme is a **simplification**: stop
duplicating Simple Email GW's account/env-var parsing in the loop; delegate it
to the SDK's `ConnectionPool`. This revises R2 by removing `_account_from_env`,
switching to the pool API, fixing the C1 error message, and answering the
IMAP-connection-lifetime question.

## Owner's instructions (quoted verbatim)

> **Comment 1 (line 116):** The Simple Email GW module provides support for
> setting up clients using accounts:
> ```
>     pool = await get_pool()
>     client = await pool.get_imap_client(account)
> ```
> We shouldn't have to parse env variables, this is a responsibility of Simple
> Email GW.

> **Comment 2 (line 139):** This env var is wrong. Documentation states:
> ## Recipient Whitelist
> Restrict outgoing emails to specific recipients:
> ### Domain Whitelist
> ```bash
> EMAIL_RECIPIENT_DOMAINS=gmail.com,icloud.com,company.com
> ```
> ### Address Whitelist
> ```bash
> EMAIL_RECIPIENT_ADDRESSES=admin@company.com,support@partner.org
> ```
> ### JSON Configuration
> For more complex whitelist configurations:
> ```bash
> EMAIL_RECIPIENT_WHITELIST_JSON='{ ... }'
> ```

> **Comment 3 (line 143):** See other comment: we shouldn't deal with accounts
> ourselves.

> **Comment 4 (line 164):** Question: is an imap connection "active"? Because
> we might now want it to be active throughout the entire loop and only when
> actually performing a check for emails?

## Does the revision satisfy each quoted item?

1. **Comment 1 — "We shouldn't have to parse env variables ... responsibility of
   Simple Email GW."** YES. `_account_from_env()` is removed entirely. The loop
   obtains the IMAP and SMTP clients from `await pool.get_imap_client(name)` /
   `await pool.get_smtp_client(name)`. The pool calls `get_accounts()` which
   reads the `EMAIL_*` env vars internally via `ServerConfig`. No env-var parsing
   for account fields remains in `loop.py`. See §1 and §3.

2. **Comment 2 — "This env var is wrong."** YES. The RuntimeError message at
   `loop.py:139` referenced `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`, a name that
   does not match the documented env vars. The C1 *check* itself is correct
   (`get_recipient_whitelist().enabled` works regardless — it reads the env vars
   via `ServerConfig`). Only the error *message string* was wrong. The message
   is corrected to reference the three documented env var names. See §2.

3. **Comment 3 — "we shouldn't deal with accounts ourselves."** YES. Same as
   comment 1: no `EmailAccount(...)` construction in the loop, no
   `_account_from_env`, no `IMAPClient(account)` / `SMTPClient(account)`
   construction. The pool owns account lookup and client construction. The
   loop passes only an account *name* string (`"default"`) to the pool. See §1.

4. **Comment 4 — IMAP connection lifetime question.** ANSWERED. The IMAP
   connection IS active (open socket) once `connect()` is called, and holding
   it open across the 60s poll-interval sleep is acceptable for typical IMAP
   servers. The recommended design keeps the connection active for the loop's
   lifetime (simplest), and adds a reconnect-on-failure path on `search` so a
   dropped idle connection does not kill the loop. See §4.

No deviations from the owner's proposals. The pool API is adopted as stated.
The C1 message is corrected as stated. The IMAP-lifetime question is answered
with a recommendation that preserves the owner's simplicity directive.

---

## 1. Simple Email GW pool API — findings

Confirmed against `/Users/xtof/Workspace/agentic/simple-email-gw/src/simple_email_gw/`.

### 1.1 `get_pool()`

- **Location:** `simple_email_gw/connections/pool.py`, re-exported from
  `simple_email_gw/__init__.py`.
- **Signature:** `async def get_pool() -> ConnectionPool`.
- **Behavior:** returns a process-wide singleton `ConnectionPool`. Async; uses
  an `asyncio.Lock` for thread-safe creation. Cheap to call repeatedly.

### 1.2 `ConnectionPool.get_imap_client(account_name)`

- **Signature:** `async def get_imap_client(self, account_name: str) -> IMAPClient`.
- **Behavior:** checks the IMAP rate limiter, then under `_client_lock` looks up
  the account by `name` in `await self.get_accounts()`. If not found, raises
  `ValueError(f"Account not found: {account_name}")`. If found, constructs
  `IMAPClient(account)` and caches it in `_imap_clients[account_name]`. Returns
  the cached client on subsequent calls.
- **Important:** the returned `IMAPClient` is **not yet connected**. The pool
  constructs it; the caller must still `await client.connect()` (or let the
  first operation connect — every `IMAPClient` method calls `await
  self.connect()` internally before issuing commands).
- **The `account_name` parameter is a NAME string**, not an `EmailAccount`
  object. The owner's snippet `pool.get_imap_client(account)` uses `account` as
  a name; the actual SDK signature is `(account_name: str)`.

### 1.3 `ConnectionPool.get_smtp_client(account_name)`

- **Signature:** `async def get_smtp_client(self, account_name: str) -> SMTPClient`.
- **Behavior:** mirrors `get_imap_client` — rate-limiter check, account lookup by
  name, cache, return `SMTPClient(account)`. Exists and is the right primitive
  for the SMTP side.

### 1.4 Where `account` comes from

- `ConnectionPool.get_accounts()` returns `get_accounts()` from
  `simple_email_gw/config.py`, which calls `ServerConfig().get_accounts()`.
- `ServerConfig` is a pydantic-settings `BaseSettings` with `env_prefix="EMAIL_"`.
  It reads either `EMAIL_ACCOUNTS_JSON` (multi-account JSON) OR the individual
  env vars (`EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`, `EMAIL_USERNAME`,
  `EMAIL_PASSWORD`, etc.) and constructs a single account with
  `name = self.account_name` (which defaults to `"default"`, overridable via
  `EMAIL_ACCOUNT_NAME`).
- So the account name to pass to the pool is `"default"` for the standard
  single-account setup. The loop does NOT parse any account env vars itself; it
  passes the literal name `"default"` and the SDK resolves it to the account it
  built from the env. This is the cleanest seam: the loop knows one identifier
  (the name), the SDK knows everything else.

### 1.5 How the pool handles env-var configuration

- All `EMAIL_*` env-var reading happens inside `ServerConfig` (pydantic-settings
  BaseSettings). The pool calls `get_accounts()` → `get_config()` →
  `ServerConfig()` once and caches the result in `self._accounts`. The loop
  never touches `os.environ` for account fields. This is exactly the
  responsibility separation the owner asked for.

### 1.6 Accessing the owner's email address (for R2's guard-failure notice)

- The pool-returned `IMAPClient` exposes `imap.account: EmailAccount`. So
  `imap.account.username` is the owner's email address — the same address the
  SDK uses as `From` in `send_email`/`reply_email`. No separate account lookup
  is needed in the loop, no new env var. R2's `_send_guard_notice` reads
  `imap.account.username` instead of a separately-passed `account` parameter.

---

## 2. C1 whitelist check — the fix

### 2.1 The check is correct; only the message is wrong

`loop.py:137` calls `get_recipient_whitelist().enabled`. That function
(`simple_email_gw/config.py:204`) reads `ServerConfig` and returns a
`RecipientWhitelist` whose `.enabled` is `True` when any of
`EMAIL_RECIPIENT_WHITELIST_JSON`, `EMAIL_RECIPIENT_WHITELIST_DOMAINS`, or
`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is set (per the SDK's actual field names),
or when the JSON config sets `enabled: true`. The C1 guard works correctly.

The bug is purely in the RuntimeError **message string** at `loop.py:139`:

```python
raise RuntimeError(
  "EMAIL_RECIPIENT_WHITELIST_ADDRESSES not set — refusing to run "
  "(recipient whitelist fails open)"
)
```

That name is not the documented env var. The owner's documentation names three
env vars: `EMAIL_RECIPIENT_DOMAINS`, `EMAIL_RECIPIENT_ADDRESSES`,
`EMAIL_RECIPIENT_WHITELIST_JSON`. (Note: there is a separate docs/impl mismatch
inside Simple Email GW itself — `config.py` names the fields
`recipient_whitelist_domains`/`recipient_whitelist_addresses`, which with the
`EMAIL_` prefix become `EMAIL_RECIPIENT_WHITELIST_DOMAINS`/`..._ADDRESSES`,
not the documented `EMAIL_RECIPIENT_DOMAINS`/`EMAIL_RECIPIENT_ADDRESSES`. That
is an SDK erratum to flag separately, not a yoker-assistant bug. For the loop's
error message, we cite the documented names the owner considers authoritative.)

### 2.2 Corrected message

```python
raise RuntimeError(
  "Recipient whitelist is disabled — refusing to run. "
  "Set one of EMAIL_RECIPIENT_ADDRESSES, EMAIL_RECIPIENT_DOMAINS, "
  "or EMAIL_RECIPIENT_WHITELIST_JSON (the whitelist fails open)."
)
```

This names all three documented env vars, states the failure mode ("fails
open"), and does not privilege one mechanism over another. The check itself
(`if not get_recipient_whitelist().enabled`) is unchanged.

### 2.3 Note for the owner (out of scope for this PR)

The env-var-name mismatch between the Simple Email GW docs
(`EMAIL_RECIPIENT_DOMAINS`/`EMAIL_RECIPIENT_ADDRESSES`) and its `config.py`
(`EMAIL_RECIPIENT_WHITELIST_DOMAINS`/`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`) is a
real discrepancy in the SDK. It means the documented `EMAIL_RECIPIENT_DOMAINS`
env var may not actually take effect. This should be filed against
simple-email-gw, not fixed in yoker-assistant. I will flag it separately.

---

## 3. Replacing `_account_from_env()` with the pool API

### 3.1 What is removed

- The entire `_account_from_env()` function (`loop.py:116-126`).
- The `import os` (only used by `_account_from_env`; verify no other use —
  `os` is not used elsewhere in `loop.py`).
- The direct `IMAPClient(account)` / `SMTPClient(account)` construction in
  `run()`. The imports of `IMAPClient` and `SMTPClient` from `simple_email_gw`
  are no longer needed for construction (they remain only as type hints if
  desired; `simple_email_gw` exports `get_pool` instead).
- The `EmailAccount` import (no longer constructed in the loop).

### 3.2 What is added

- `from simple_email_gw import get_pool` (replaces the `EmailAccount, IMAPClient,
  SMTPClient` import line — or supplement it; `get_pool` is exported from
  `simple_email_gw/__init__.py`).
- A module-level constant for the account name:
  `_ACCOUNT_NAME = "default"` (one line, matches the SDK's default
  `account_name`). This is the only "account knowledge" the loop keeps. It is a
  name, not env-var parsing.

### 3.3 Updated `run()` (account/client acquisition portion)

```python
from simple_email_gw import get_pool
from simple_email_gw.config import get_recipient_whitelist

_ACCOUNT_NAME = "default"

async def run(once: bool = False) -> None:
  # C1 BLOCKING FIX: refuse to run if the recipient whitelist is disabled.
  if not get_recipient_whitelist().enabled:
    raise RuntimeError(
      "Recipient whitelist is disabled — refusing to run. "
      "Set one of EMAIL_RECIPIENT_ADDRESSES, EMAIL_RECIPIENT_DOMAINS, "
      "or EMAIL_RECIPIENT_WHITELIST_JSON (the whitelist fails open)."
    )

  agent = Agent(
    agent_path="agents/assistant.md",
    context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"),
  )
  await agent.process(_INITIALIZE_PROMPT)

  pool = await get_pool()
  imap = await pool.get_imap_client(_ACCOUNT_NAME)
  smtp = await pool.get_smtp_client(_ACCOUNT_NAME)

  # ... rest of loop (signal handling, connect, poll, finally disconnect) ...
```

### 3.4 Account name: why `"default"` and not env-var lookup

The owner said "we shouldn't have to parse env variables." Reading
`EMAIL_ACCOUNT_NAME` to pick the name would technically still be env-var
parsing (of a different env var). Hardcoding `"default"` matches the SDK's own
default for `ServerConfig.account_name`, which is what the SDK uses when the
user configures a single account via the individual `EMAIL_*` env vars. For
the demo's single-account setup, this is correct and zero-config. If
multi-account support is ever needed, the name can be made configurable later
(preferably via a yoker-assistant-specific config, not by re-parsing the SDK's
account env vars).

### 3.5 Alternative considered: use `await pool.get_accounts()[0]`

This would avoid hardcoding `"default"` and let the SDK pick the first
configured account. Rejected because: (a) it makes the loop's behavior depend
on account-list ordering, which is less explicit; (b) for a multi-account
config it would silently pick one, which is not what we want (we want the user
to be deliberate). A literal name is clearer and fails loudly (`ValueError:
Account not found: default`) if the user renamed their account. Keep
`"default"`.

---

## 4. IMAP connection lifetime — recommendation

### 4.1 The facts

- `IMAPClient.connect()` (`imap/client.py:114`) is idempotent: under
  `_connect_lock`, it returns the existing `self._client` if already set. So
  repeated `await imap.connect()` calls are cheap no-ops once connected.
- Every `IMAPClient` operation (`search`, `fetch_message`, `mark_message`,
  `move_message`) calls `await self.connect()` internally before issuing the
  IMAP command. So the loop does not strictly need to call `connect()` itself —
  the first `search` would connect.
- The current `run()` calls `await imap.connect()` once before the loop
  ("fast-fail on bad credentials") and `await imap.disconnect()` in `finally`.
  The connection stays open across the 60s `stop.wait()` sleep.
- IMAP servers typically allow idle connections for several minutes (RFC 2177
  IDLE allows up to 29 min; common server-side timeouts are 5-30 min). A 60s
  poll interval is well within that window, so an idle connection usually
  survives. But it is not guaranteed — a server may drop an idle connection
  after 30s on aggressive configurations, or the network may drop.

### 4.2 Is the connection "active"?

Yes — once `connect()` succeeds, there is an open TLS socket to the IMAP
server held in `self._client`. It is "active" in the sense that it consumes a
file descriptor and a server-side session, but it is idle (no commands in
flight) during the sleep. It is not using IMAP IDLE (the SDK does not issue
IDLE); it is a plain open connection waiting for the next `search`.

### 4.3 Recommendation: keep it active, add reconnect-on-failure

**Keep the connection active throughout the loop.** This is the simplest
design: one `connect()` at startup (for fast-fail on bad credentials), reuse
for all operations, one `disconnect()` at shutdown. Reconnecting every poll
adds auth overhead (~1 RTT for hello + 1 for login) 60 times per hour for no
benefit in the common case. The pool is designed to cache the client precisely
so the caller does not reconnect per operation.

**Add a small reconnect-on-failure guard around `search`.** If the idle
connection was dropped by the server, the next `search` raises (aioimaplib
Abort/Error). Without handling, that would propagate and kill the loop. With
minimal handling, the loop catches it, disconnects + reconnects, and retries
the poll once:

```python
await imap.connect()  # fast-fail on bad credentials
try:
  while not stop.is_set():
    try:
      uids = await imap.search(_INBOX_FOLDER, "UNSEEN")
    except Exception:
      logger.warning("imap search failed; reconnecting", exc_info=True)
      try:
        await imap.disconnect()
      except Exception:
        pass
      await imap.connect()
      uids = await imap.search(_INBOX_FOLDER, "UNSEEN")
    for mid in uids:
      ...
finally:
  try:
    await imap.disconnect()
  except Exception:
    logger.exception("imap disconnect failed")
```

This addresses the owner's concern (the connection is not blindly trusted
across sleeps) without reconnecting on every poll (which would be wasteful). It
reconnects only when the connection actually failed. The per-message
`_process_one` calls keep the existing outer `try/except` for per-message
errors; a dropped connection mid-message surfaces there and leaves the
message UNSEEN for the next iteration (which will reconnect via the search
guard).

### 4.4 Alternative considered: connect/disconnect per poll

Connect → `search` → process → disconnect → sleep. Rejected: it adds two
auth round-trips per minute for no benefit in the common case, and the
reconnect-on-failure guard above handles the rare drop case more efficiently
(reconnects only on failure). The pool's cached-client design also assumes the
caller reuses the client; reconnecting per poll would defeat it.

### 4.5 Alternative considered: drop the explicit `connect()`/`disconnect()`

Let `search` connect implicitly, no `disconnect` in `finally`. Rejected: (a)
loses the fast-fail on bad credentials at startup (the loop would start, then
fail on the first search — harder to diagnose); (b) leaks the connection at
process exit. Keep the explicit connect/disconnect pair.

---

## 5. Concrete change description for the developer

### 5.1 `src/yoker_assistant/loop.py`

1. **Imports:** replace
   `from simple_email_gw import EmailAccount, IMAPClient, SMTPClient` with
   `from simple_email_gw import get_pool` (keep
   `from simple_email_gw.config import get_recipient_whitelist`). Remove
   `import os` if it has no other use (it does not in the current file).

2. **Remove** the `_account_from_env()` function entirely (lines 116-126).

3. **Add** a module-level constant near the other `_` constants:
   `_ACCOUNT_NAME = "default"`.

4. **`run()`:** replace the body from the C1 check through client construction
   with the snippet in §3.3. Specifically:
   - Keep the C1 whitelist check, but use the corrected error message (§2.2).
   - Construct `agent`, run the Initialize turn.
   - `pool = await get_pool()`.
   - `imap = await pool.get_imap_client(_ACCOUNT_NAME)`.
   - `smtp = await pool.get_smtp_client(_ACCOUNT_NAME)`.
   - Signal handling unchanged.
   - `await imap.connect()` for fast-fail.
   - Add the reconnect-on-failure guard around `search` (§4.3).
   - `finally: await imap.disconnect()` unchanged.

5. **`_process_one`:** the R2 design threaded `account` in for the guard
   notice's `account.username`. With the pool, `account` is no longer a local
   in `run()`. Replace the `account` parameter with nothing; the notice helper
   reads `imap.account.username` from the IMAPClient the pool returned. Update
   the `_send_guard_notice` signature to take `imap` (it already has `smtp`)
   or just `owner_email: str` extracted in `_process_one` via
   `imap.account.username`. Cleanest: pass `owner_email: str` to
   `_send_guard_notice`, extracted once in `run()` as
   `owner_email = imap.account.username` and threaded into `_process_one` (or
   captured by the helper). Keep the parameter count minimal.

   Recommended signature:
   ```python
   async def _process_one(imap, smtp, agent, owner_email: str, mid: str) -> None:
   ```
   and in `run()`:
   ```python
   owner_email = imap.account.username
   ...
   await _process_one(imap, smtp, agent, owner_email, mid)
   ```

6. **`_send_guard_notice`:** change `to=[account.username]` to
   `to=[owner_email]`. Otherwise unchanged from R2.

### 5.2 What does NOT change

- `build_message` (P2-006) — untouched.
- `_contains_unsafe_html` guard — untouched.
- The four-way branching logic in `_process_one` (R2) — untouched except the
  `account` → `owner_email` parameter rename.
- The `{{NO_REPLY}}` sentinel, the agent.md step-0, the `--once` flag, the
  signal handlers, the poll interval, the graceful shutdown.
- The R2 notice content and the "leave UNSEEN on guard failure" semantics.
- The SDK errata from `api-loop.md`.

### 5.3 Tests (`tests/test_loop.py`)

The existing tests mock `IMAPClient` and `SMTPClient` construction and
`get_recipient_whitelist`. They need updating to mock the pool API instead.

1. **`test_run_refuses_to_start_when_whitelist_disabled`:** unchanged (still
   patches `get_recipient_whitelist`). It raises before any pool call, so no
   pool mock is needed.

2. **`test_run_proceeds_when_whitelist_enabled` and
   `test_run_continues_after_process_one_exception`:** replace the
   `monkeypatch.setattr("yoker_assistant.loop.IMAPClient", lambda account: imap)`
   and `SMTPClient` patches with a pool mock:
   ```python
   pool = MagicMock()
   pool.get_imap_client = AsyncMock(return_value=imap)
   pool.get_smtp_client = AsyncMock(return_value=smtp)
   monkeypatch.setattr("yoker_assistant.loop.get_pool", AsyncMock(return_value=pool))
   ```
   The `_set_env` helper can be removed (no env-var parsing in the loop
   anymore). The `imap.account.username` attribute must be set on the mock:
   `imap.account.username = "owner@example.com"` (for the guard-notice path /
   `owner_email` extraction).

3. **Guard-failure tests (R2):** update to assert `smtp.send_email` is called
   with `to=[owner_email]` (e.g. `["owner@example.com"]`), where `owner_email`
   comes from `imap.account.username` set on the mock. Remove any assertion
   that passed `account` into `_process_one`.

4. **Reconnect-on-failure:** add one new test — `search` raises on first call,
   succeeds on second; assert `imap.disconnect` and `imap.connect` were called
   and the loop recovered. Keep it tight (one test for the happy recovery path).

5. **C1 message test:** add (or update) a test asserting the RuntimeError
   message mentions `EMAIL_RECIPIENT_ADDRESSES` (not the old
   `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`). One assertion via `pytest.raises(
   RuntimeError, match="EMAIL_RECIPIENT_ADDRESSES")` suffices.

### 5.4 `analysis/functional.md`

Update the account-acquisition section: the loop uses `get_pool()` +
`pool.get_imap_client("default")` / `pool.get_smtp_client("default")`; no
`_account_from_env`; the account name is the literal `"default"` matching the
SDK's default. Note the reconnect-on-failure guard on `search`. Note the
corrected C1 error message. ~10-15 lines changed.

---

## 6. Does this simplify the implementation?

Yes — net simplification, exactly as the owner's feedback implied:

- **Deletes** `_account_from_env()` (~11 lines) and its `import os`.
- **Removes** yoker-assistant's knowledge of `EMAIL_IMAP_HOST`, `EMAIL_SMTP_HOST`,
  `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_IMAP_PORT`, `EMAIL_SMTP_PORT`,
  `EMAIL_NAME`. All of that moves to the SDK, which already handles it.
- **Removes** the `EmailAccount` import from the loop.
- **Replaces** `IMAPClient(account)` / `SMTPClient(account)` with two pool calls.
- **Keeps** one constant (`_ACCOUNT_NAME = "default"`) — the only account
  knowledge the loop retains is the name, which is a convention, not env-var
  parsing.
- The reconnect-on-failure guard adds ~6 lines, which is a net robustness
  improvement, not complexity for its own sake. It is the minimum needed to
  answer the owner's IMAP-lifetime question without reconnecting per poll.

Net: fewer env var names referenced in yoker-assistant, fewer lines of
account-construction code, clearer separation of concerns. The loop becomes a
consumer of the SDK, not a re-implementer of its config parsing.

---

## 7. Concerns

1. **Hardcoded `"default"` account name.** If the user configured their
   account with a different name (via `EMAIL_ACCOUNT_NAME` or
   `EMAIL_ACCOUNTS_JSON` with a custom `name`), `pool.get_imap_client("default")`
   raises `ValueError("Account not found: default")` at startup. This fails
   loudly and early, which is acceptable. If flexibility is needed later, a
   yoker-assistant-specific config (e.g. `YOKER_ACCOUNT_NAME`) can be added;
   do not re-parse the SDK's `EMAIL_ACCOUNT_NAME` (that would repeat the
   mistake the owner just flagged).

2. **SDK docs/impl env-var mismatch.** The Simple Email GW docs quote
   `EMAIL_RECIPIENT_DOMAINS` / `EMAIL_RECIPIENT_ADDRESSES`, but `config.py`
   fields are `recipient_whitelist_domains` / `recipient_whitelist_addresses`,
   which with the `EMAIL_` prefix become
   `EMAIL_RECIPIENT_WHITELIST_DOMAINS` / `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`.
   This means the documented env vars may not actually take effect in the SDK.
   It is out of scope for yoker-assistant to fix; flag it as an SDK erratum for
   the owner to file against simple-email-gw. The loop's corrected C1 message
   cites the documented names (per the owner's authoritative documentation),
   which is the right call for the user-facing message regardless of the SDK
   bug.

3. **Reconnect-on-failure swallows non-connection errors.** The `except
   Exception` around `search` is broad. If `search` fails for a non-connection
   reason (e.g. invalid criteria — impossible here since criteria is the
   constant `"UNSEEN"`), the loop would disconnect+reconnect+retry once, then
   raise on the second failure. Acceptable: the criteria is a constant, so a
   non-connection failure is a real bug and should surface. The broad except is
   fine for v1; it can be narrowed to `aioimaplib.Abort`/`aioimaplib.Error`/
   `ConnectionError`/`OSError` later if needed.

4. **Per-message operations still rely on the cached connection.** If the
   connection drops mid-`_process_one` (between `fetch_message` and
   `mark_message`), the per-message `try/except` catches it, logs, and leaves
   the message UNSEEN. The next iteration's `search` triggers the
   reconnect-on-failure guard. No message is lost; it retries. Acceptable and
   consistent with R2's "leave UNSEEN on failure" semantics.

5. **`imap.account.username` for the notice.** This relies on the
   pool-returned `IMAPClient` exposing its `account` attribute (it does,
   `imap/client.py:107`). If the SDK ever makes `account` private, the notice
   path would need another way to get the owner email (e.g.
   `await pool.get_accounts()` and find by name). Low risk; the attribute is
   part of the constructor contract and undocumented-but-stable.

---

## 8. Summary of changes to the implementation plan (R2 → R4)

1. **Remove `_account_from_env()`.** Delete the function, the `import os`, and
   the `EmailAccount`/`IMAPClient`/`SMTPClient` construction imports.

2. **Adopt the pool API.** `from simple_email_gw import get_pool`. In `run()`:
   `pool = await get_pool()`, `imap = await pool.get_imap_client("default")`,
   `smtp = await pool.get_smtp_client("default")`.

3. **Add `_ACCOUNT_NAME = "default"` constant.** The only account knowledge in
   the loop.

4. **Fix the C1 error message.** Reference the three documented env var names
   (`EMAIL_RECIPIENT_ADDRESSES`, `EMAIL_RECIPIENT_DOMAINS`,
   `EMAIL_RECIPIENT_WHITELIST_JSON`). Check logic unchanged.

5. **Keep the connection active; add reconnect-on-failure on `search`.**
   `connect()` at startup (fast-fail), `disconnect()` in `finally`, and a
   try/except around `search` that disconnects+reconnects+retries once.

6. **`_process_one`: replace `account` parameter with `owner_email: str`**
   extracted as `imap.account.username` in `run()`. `_send_guard_notice` uses
   `owner_email` instead of `account.username`. R2 semantics unchanged.

7. **Tests:** mock `get_pool` (AsyncMock returning a pool with
   `get_imap_client`/`get_smtp_client`); set `imap.account.username` on the
   mock; remove `_set_env`; add a reconnect-on-failure test; update the C1
   message test to match the new env var names.

8. **`functional.md`:** update the account-acquisition and C1-message sections;
   note the reconnect-on-failure guard.

9. **Flag the SDK env-var docs/impl mismatch** to the owner as a separate
   simple-email-gw erratum (not fixed in yoker-assistant).

This revision is ready to be posted as a PR comment on PR #7 for owner
approval. No implementation is started until the owner confirms.