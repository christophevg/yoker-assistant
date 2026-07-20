# Security Analysis — Task P1-003 (Mailbox Seam Module)

Scope: cross-domain design review (security-engineer perspective) of P1-003 as
scoped in `TODO.md` and described in `analysis/functional.md` §2.4, §4.3, §4.4,
§5.1, §7. The task introduces `yoker_assistant/mailbox.py`, a thin async seam
wrapping `simple_email_gw`'s `IMAPClient`/`SMTPClient` around an `EmailAccount`
built from `.env`.

This is a design/code-shape review — no code is executed against live servers,
no fixes are applied. Findings are recommendations for the implementer
(python-developer) and the functional-analyst. The review reads the installed
`simple_email_gw` 0.3.0 package to verify how the gateway actually handles
credentials, TLS, and the recipient whitelist, so recommendations rest on
observed behavior, not assumptions.

## Executive Summary

The seam design (pure wrapping, delegate reply-safety to the gateway, no
business logic) is correct. One **Critical** finding breaks the reply-safety
boundary the whole architecture relies on: the env var name yoker-assistant
documents for the recipient whitelist (`EMAIL_RECIPIENT_ADDRESSES`) is **not**
the env var `simple_email_gw`'s pydantic config actually reads
(`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`). Verified empirically: with
`EMAIL_RECIPIENT_ADDRESSES=owner@example.com` set, `get_recipient_whitelist()`
returns `enabled=False, addresses=[]` — the whitelist is silently disabled and
the agent can reply to arbitrary senders. This must be fixed before the seam's
`reply()` can be considered safe-to-ship.

The remaining findings are hardening recommendations: a redacting `__repr__`
on the seam, exception wrapping to strip host/PII context, passing the HTML
reply as `html_body=` (not `body=`) so the gateway sets `text/html`, a logging
posture of counts-not-bodies, and refusing to let the seam downgrade TLS. None
of these are blocking on their own; the env-var finding is.

## Trust Boundaries (for context)

1. **`.env` → `EmailAccount` → seam** — credentials in cleartext local config
   (accepted for local dev; documented in P1-002 analysis). The seam must not
   re-export them.
2. **Inbox → agent session** — untrusted sender-controlled headers/body. The
   seam fetches and hands off; input-validation concerns live in P2-006.
3. **Seam → IMAP/SMTP server** — credentials transmitted over TLS. The gateway
   enforces TLS 1.2+ with cert verification by default; the seam must not
   disable it.
4. **Seam → reply recipient** — the reply-safety boundary. Enforced by
   `simple_email_gw`'s `RecipientWhitelist`, **gated on the correct env var
   being set** (see Finding 1).

## Findings

### 1. Reply-safety boundary silently disabled by env-var name mismatch — Critical
(OWASP A01 Broken Access Control / A05 Injection-adjacent: bypass of safety
gate; CWE-665 Insecure Default / CWE-1188 Insecure Default)

**Context.** functional.md §5.3 and §8.7 place the reply-safety boundary in
`simple-email-gw` via `EMAIL_RECIPIENT_ADDRESSES`. `.env.example` and
`README.md` (P1-002 deliverables) both instruct the user to set
`EMAIL_RECIPIENT_ADDRESSES=owner@example.com`. P1-003's `reply()` is designed
to delegate to `SMTPClient.reply_email()`, which calls
`get_recipient_whitelist().is_allowed(to)` and raises `WhitelistError` if the
recipient is not whitelisted.

**Observed behavior (verified against installed `simple_email_gw` 0.3.0).**
`ServerConfig` uses pydantic-settings with `env_prefix="EMAIL_"` and field
`recipient_whitelist_addresses`. The env var pydantic binds is
`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`, NOT `EMAIL_RECIPIENT_ADDRESSES`.

Empirical check run against the installed package:

```
EMAIL_RECIPIENT_ADDRESSES=owner@example.com      -> enabled=False, addresses=[]
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com -> enabled=True, addresses=['owner@example.com']
```

So with the package's documented configuration, `RecipientWhitelist.enabled`
is `False`, `is_allowed()` returns `True` for every address, and
`reply_email()` never raises `WhitelistError`. The agent replies to whoever
emailed it — including spoofed senders, mailing lists, spam — with no gate.
The safety property the design relies on is silently absent.

This is also a documentation bug upstream: `simple-email-gw/README.md` lines
212-213 document `EMAIL_RECIPIENT_ADDRESSES` / `EMAIL_RECIPIENT_DOMAINS`, which
do not bind either. But yoker-assistant ships the `.env.example` and README
that propagate it, so the fix is actionable here now.

**Impact.** The assistant replies to arbitrary senders. An attacker who sends
inbound mail causes the assistant to send outbound mail (and agent reasoning,
and any PII it puts in replies) to attacker-controlled addresses. This is the
highest-severity finding because it defeats the only reply-side safety control
and does so silently — no error, no log, no indication the whitelist is off.

**Confidence:** High (verified by direct execution against the installed
package; pydantic-settings binding is deterministic).

**Remediation (recommend, do not apply):**

- **Fix yoker-assistant's documented config to use the env var the gateway
  actually reads.** In `.env.example` and `README.md`, rename
  `EMAIL_RECIPIENT_ADDRESSES` to `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (and
  `EMAIL_RECIPIENT_DOMAINS` to `EMAIL_RECIPIENT_WHITELIST_DOMAINS` if/where
  domains are documented). Keep the comment stressing this is the primary
  reply-safety boundary and must be the single owner address.
- **Add a startup assertion in the seam (or the loop) that fails fast if the
  whitelist is not enabled.** Because the silent-disabled state is the
  dangerous one, the seam should call `get_recipient_whitelist()` at
  `connect()` time and raise/log a loud error if `enabled is False` or the
  address list is empty — refuse to enter the loop in a configuration that
  cannot enforce reply safety. This is defense in depth: even if a future
  env-var rename or upstream field change re-breaks the binding, the seam
  catches it instead of running open-loop. (Recommend the functional-analyst
  decide whether this is "fail closed" or "warn loudly" — for an unattended
  assistant, fail-closed is the safer default.)
- **Report the upstream doc bug to `simple-email-gw`** (README documents the
  wrong env var names). Out of scope for this package to fix upstream, but
  worth filing so the footgun is removed at the source.

**Reference:** OWASP A01:2025 (Broken Access Control — safety gate bypass),
CWE-665 (Insecure Default — configuration does not enforce the documented
control), CWE-1188 (Insecure Default).

### 2. Seam `__repr__` must redact credentials — Low (OWASP A02 Security Misconfiguration / A09 Logging Failures; CWE-532 Information Leak in Logs)

**Context.** `EmailAccount.password` is a pydantic `SecretStr`, so its
`repr` is `SecretStr('**********')` — good. But the seam holds the
`EmailAccount` and may surface it in a stack trace, a debug log, or a
`repr(Mailbox)` call in a test. If the seam ever prints `account.__dict__` or
formats `account` with `str()` on the wrong attribute, the password can leak.
`SecretStr.get_secret_value()` is the only way to read it; the seam must
never call it except to pass to the gateway (the gateway already does this
internally for auth).

**Assessment.** Low risk because pydantic does the heavy lifting, but the
seam should add an explicit redaction layer so a future contributor cannot
accidentally widen the surface.

**Remediation (recommend):**

- Give `Mailbox` a `__repr__` that includes only `account.name`,
  `imap_host`, `smtp_host` — NOT `username`, NOT `password`, NOT
  `oauth2_token`. Example:
  `f"Mailbox(name={self.account.name!r}, imap={self.account.imap_host!r}, smtp={self.account.smtp_host!r})"`.
- Never log the `EmailAccount` object directly; log `account.name` only.
- Never serialize the `EmailAccount` to JSON/YAML/TOML in the seam. If config
  debugging is needed, log a redacted dict built explicitly.

**Reference:** CWE-532 (Insertion of Sensitive Information into Log File),
OWASP A09:2025 (Security Logging Failures), A02:2025.

### 3. HTML reply body must be passed as `html_body=`, not `body=` — High
(OWASP A05 Injection / Content-Type confusion; CWE-79 adjacent, CWE-94 Code
Injection - rendering context mismatch)

**Context.** functional.md §4.2/§4.3: the agent's reply is HTML (output of
`md_to_html`), and Python sends it verbatim. `SMTPClient.reply_email()` and
`send_email()` accept both `body` (plain text, `text/plain`) and `html_body`
(`text/html`, added via `msg.add_alternative(html_body, subtype="html")`).
If the seam passes the HTML string as `body=`, the gateway sets
`Content-Type: text/plain` and the recipient sees raw HTML source — and worse,
the `make_msgid` / header sanitization still applies but the body is not
declared as HTML, so any HTML-escape assumptions downstream break.

This is the seam's responsibility: the agent returns HTML; the seam must map
it to the gateway's `html_body` parameter, not `body`. There is also a
plain-text fallback question: `reply_email` requires `body` (plain text) as a
positional arg even when `html_body` is set — the seam should pass a minimal
plain-text fallback (e.g., a short note, or a stripped version) so
non-HTML-capable clients still render something. The §4.2 line "Python does
not interpret it or re-render it" means the seam must NOT sanitize or
re-render the HTML — but it MUST label it as HTML via the correct parameter.

**Impact.** Wrong `Content-Type` breaks rendering for the owner and, in mixed
multipart/alternative constructions, can cause the HTML to be displayed as
text or dropped. It is not an XSS vector against the owner's mail client
(the owner's client renders the assistant's own HTML), but it IS a
correctness/security-posture bug: the seam claims to send HTML replies and
silently sends mislabeled content.

**Confidence:** High that the parameter name matters; Medium that a
plain-text fallback is required (gateway accepts `body=""` — the
functional-analyst should decide what the plain-text part should contain;
recommend a one-line "This reply is HTML; view in a client that supports
HTML." or a stripped-text version produced by the agent, NOT a Python-side
HTML-stripping step, to keep the seam pure).

**Remediation (recommend):**

- In `Mailbox.reply(...)`, call `smtp.reply_email(to=..., subject=...,
  body=<plain-text-fallback>, html_body=<the agent's HTML>,
  in_reply_to=..., ...)` — never pass the HTML as `body=`.
- Do NOT add an HTML-sanitization step in the seam. Per §4.2, the HTML is
  sent verbatim; sanitization is the agent's responsibility (it authored the
  HTML via a bounded tool). The seam should only set the correct
  `Content-Type` by routing through `html_body=`.
- Document in the seam's module docstring that `body` (plain text) is a
  required gateway parameter and what the seam supplies for it.

**Reference:** OWASP A05:2025 (Injection — content-type / rendering context),
CWE-94 (Improper Control of Generation of Code — rendering context mismatch),
CWE-79 (Contextual output encoding — the seam's job is labeling, not
encoding).

### 4. TLS / transport security — enforce, do not downgrade — Medium
(OWASP A02 Security Misconfiguration / A04 Cryptographic Failures; CWE-295
Improper Certificate Validation, CWE-327 Use of Broken Crypto)

**Observed (verified in the installed package).** The gateway enforces TLS by
default and does not expose a "disable TLS" knob through the seam's call
path:

- `EmailAccount.use_ssl` defaults to `True`; `imap_port` defaults to 993
  (implicit TLS); `smtp_port` defaults to 587 with `use_starttls` derived as
  `smtp_port == 587`.
- `IMAPClient.connect()` builds `ssl.create_default_context()` with
  `minimum_version = TLSVersion.TLSv1_2` and uses `IMAP4_SSL` (cert
  verification on). There is no plaintext IMAP path.
- `SMTPClient._send()` builds the same TLS 1.2+ context and uses STARTTLS for
  587, implicit TLS otherwise. There is no plaintext SMTP path.

So the seam inherits strong transport defaults. The risk is that a user (or
future contributor) constructs an `EmailAccount` with `use_ssl=False` or
non-TLS ports (143/25/587-without-starttls) and the seam happily uses it. The
gateway does not appear to refuse plaintext credentials over unencrypted
transports for IMAP (port 143 would not be `IMAP4_SSL`); for SMTP, port 587
forces STARTTLS, but port 25 would fall through to implicit-TLS-on-a-plaintext
-port and fail — not silently downgrade, but not a clean refusal either.

**Remediation (recommend):**

- The seam should construct `EmailAccount` from env via the gateway's own
  `ServerConfig`/`get_accounts()` (so the gateway's defaults apply) rather
  than building it by hand with user-supplied ports. If the seam does build
  it by hand, assert at construction: `imap_port in (993, 143)` is NOT
  enough — prefer requiring `use_ssl=True` and refusing to construct an
  account that would authenticate over a plaintext transport. At minimum,
  log a WARNING if `use_ssl is False` or `imap_port not in (993,)` /
  `smtp_port not in (465, 587)`.
- Do NOT add a `verify=False` / cert-verification-bypass path. If a
  contributor ever needs self-signed certs for local testing, that belongs in
  an explicit test fixture, not the seam's surface.

**Reference:** OWASP A02:2025, A04:2025 (Cryptographic Failures), CWE-295,
CWE-327.

### 5. Connection lifecycle / reconnect — Medium (OWASP A06 Insecure Design; CWE-400 Resource Exhaustion, CWE-362 Concurrent Execution)

**Context.** `IMAPClient` holds a single `_client` with connect/operation
locks and reconnects on demand if `_client is None`. `SMTPClient` is
stateless per-send (`_send` opens and closes the connection each call via
`aiosmtplib.send`). So the IMAP connection is long-lived; the SMTP connection
is per-reply. Credentials are re-transmitted on each reconnect (login happens
in `connect()`), but always inside TLS — acceptable.

**Risks:**

- **Stale IMAP auth.** A long-lived IMAP connection can drop server-side
  (idle timeout, server restart). The next operation will raise; the seam
  must catch it, set `_client = None` (or call `disconnect()`), and reconnect
  rather than crash. The gateway wraps most drops into `RuntimeError`, so the
  seam's job is to catch `RuntimeError`/`aioimaplib.Abort` and reconnect once
  before re-raising.
- **Reconnect storm.** If the server is down, the loop per §7 must back off
  (double the interval up to a cap), not spin reconnecting every iteration.
  This is the loop's job (P2-005), but the seam should expose a clear
  `connect()` that is idempotent and a `close()` that is safe to call
  repeatedly, so the loop's backoff can call them cleanly.
- **No credential re-transmission over plaintext on reconnect** — covered by
  Finding 4; reconnect uses the same TLS path.
- **Connection pooling.** The gateway ships a `ConnectionPool` but the seam
  does not need it for the single-account, single-loop first pass. Using
  `IMAPClient(account)` directly is correct; do not pool across iterations
  (one connection, reconnect-on-drop).

**Remediation (recommend):**

- `Mailbox.connect()` should be idempotent (return existing client if
  connected; reconnect if dropped).
- `Mailbox.close()` should be safe to call when already closed.
- On any `RuntimeError`/`aioimaplib.Abort`/`aioimaplib.Error` from an IMAP
  operation, the seam should call `disconnect()` so the next operation
  triggers a fresh `connect()` — do not retry inside the seam (the loop owns
  backoff per §7).
- Do NOT cache the SMTP client across replies; it is cheap to construct and
  stateless per-send. Construct `SMTPClient(account)` per `reply()` call, or
  hold one instance but rely on its per-send connect semantics.

**Reference:** OWASP A06:2025 (Insecure Design — reconnect/backoff strategy),
CWE-400 (Uncontrolled Resource Consumption — reconnect storm), CWE-362.

### 6. Error handling / information leakage — Low (OWASP A09 Logging Failures / A05; CWE-209 Information Exposure Through an Error Message)

**Observed.** The gateway wraps most exceptions into `RuntimeError` with
messages like `"Connection lost: {e}"`, `"TLS error: {e}. Check server
certificate."`, `"Network error: {e}"`, and `"An unexpected error occurred:
{type(e).__name__}: {e}"`. These can include the hostname, a DNS name, or an
IMAP protocol snippet. They do NOT include the password (it is only read via
`get_secret_value()` inside the auth call; auth failure is wrapped as
`"Authentication failed. Check server logs for details."` — good, the gateway
already strips credentials from the auth-failure path). Username is not
deliberately leaked but could appear in an IMAP protocol error snippet in
principle.

**Assessment.** Low risk — the gateway already does most of the sanitization.
The seam should add one more layer so that anything escaping the seam into
the loop's logs does not carry host/protocol detail that a log forwarder
might ship to a third-party logging service.

**Remediation (recommend):**

- Wrap gateway exceptions in a seam-specific exception (e.g.,
  `MailboxError(RuntimeError)`) carrying a sanitized message and the original
  chained via `from e` (so debug mode can still see it). Surface messages
  like `"IMAP connect failed"` / `"SMTP send failed"` / `"mailbox fetch
  failed"` to INFO; keep the `{e}` detail for DEBUG only.
- Never include `account.username`, `account.password`, or the full
  `EmailAccount` in an exception message or log line. Use `account.name`.
- Do not log full message bodies at INFO when `fetch()` or `reply()` fails —
  log the message id and a subject prefix at most (the gateway already
  follows this pattern in `log_email_sent`).

**Reference:** CWE-209 (Information Exposure Through an Error Message),
OWASP A09:2025.

### 7. Logging posture — Low (OWASP A09; CWE-532)

**Recommendation.** The seam's logger should record connection events and
counts, never bodies or credentials:

- INFO: `"mailbox.connect ok host={imap_host} account={name}"`,
  `"mailbox.unread count={n}"`, `"mailbox.fetched id={id}"`,
  `"mailbox.replied to={recipient} subject_prefix={...}"`,
  `"mailbox.mark_read id={id}"`, `"mailbox.archived id={id}"`,
  `"mailbox.close"`.
- WARNING: connection drops, reconnects, backoff events, whitelist-disabled
  startup state (see Finding 1).
- DEBUG: gateway exception detail (sanitized), IMAP capabilities. Never
  bodies, never passwords, never full headers.
- Do NOT log the `From`/`Subject`/`body` of fetched messages at INFO. The
  handoff to the agent carries them; the seam's logs should be operational,
  not content.

The gateway's own `safety.audit` module already logs account name,
subject prefix, recipients, and success/failure — not bodies or passwords.
The seam should align with that posture.

**Reference:** CWE-532, OWASP A09:2025.

### 8. No business logic / no shell / no file ops — Positive observation (no finding)

The seam must be pure wrapping: no `subprocess`, no `open()` of local files
(the gateway's attachment path reads files, but the seam must NOT pass
`attachments=` — attachments are out of scope per functional.md §8.6), no
agent/reasoning logic, no interpretation of message bodies. Confirmed against
the task spec: each method maps 1:1 to a gateway call. Recommend the
implementer add a module-level comment asserting this contract so a future
contributor does not drift it.

## STRIDE Threat Model (mailbox seam)

- **Spoofing:** The mailbox authenticates to IMAP/SMTP with credentials from
  `.env`. Mitigation: TLS 1.2+ with cert verification (gateway default); the
  seam must not downgrade (Finding 4). Inbound spoofed senders are an
  agent-side concern (P2-006), but the reply-safety boundary (Finding 1) is
  what prevents the assistant from replying to spoofed senders.
- **Tampering:** IMAP flags (`\Seen`) and archive move are the idempotency
  mechanism (§4.4). Mitigation: order reply → mark read → archive; on send
  failure do not mark read. This is the loop's job (P2-005), but the seam's
  methods must be callable in that order without hidden state.
- **Repudiation:** The gateway's `safety.audit` logs sends/auth attempts with
  account name and subject prefix. The seam should not duplicate this but
  should not suppress it either — let gateway audit logs stand.
- **Information Disclosure:** Credentials in `.env` (accepted, documented);
  credential leakage via `__repr__`/exceptions (Findings 2, 6). Mitigated by
  `SecretStr` + redacting `__repr__` + exception wrapping.
- **Denial of Service:** Reconnect storm on server down (Finding 5).
  Mitigation: loop-level backoff per §7; idempotent `connect()`/`close()`.
- **Elevation of Privilege:** Not applicable — the seam runs as the same
  user as the package; no privilege boundary is crossed. The self-trust
  blast radius from P1-002 is the relevant EoP surface and is unchanged by
  this task.

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Reply-safety whitelist silently disabled by env-var name mismatch | **Blocking** | Fix `.env.example` + `README.md` to use `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`; add seam startup assert that whitelist is enabled. |
| HTML reply passed as `body=` instead of `html_body=` | **Blocking** | Seam must route the agent's HTML through `html_body=`; pass a plain-text fallback as `body=`. |
| TLS downgrade allowed by hand-built `EmailAccount` | Related | Construct `EmailAccount` via the gateway's `ServerConfig`/`get_accounts()`; refuse/log plaintext-credential configs. |
| Redacting `Mailbox.__repr__` | Related | Add `__repr__` with `name`/hosts only; never log the `EmailAccount` object. |
| Connection lifecycle / reconnect / backoff | Related | Idempotent `connect()`/`close()`; on drop, `disconnect()` and let the loop reconnect with backoff. |
| Exception wrapping to strip host/PII | Related | Wrap gateway errors in `MailboxError` with sanitized message; chain original via `from e`. |
| Logging posture (counts, not bodies) | Related | INFO counts/events; DEBUG sanitized detail; never bodies/credentials. |
| Upstream doc bug in `simple-email-gw` README | New | File upstream issue; out of scope for this package to fix. |

### Blocking / Related Findings (detail)

**Blocking — env-var mismatch (Finding 1).** Until `.env.example` and
`README.md` use `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` (and the seam asserts at
startup that the whitelist is enabled), the seam's `reply()` is unsafe to
ship: it will send replies to arbitrary senders with no error. This is the
single most important fix in this review. It is a P1-002 deliverable that
P1-003's safety depends on, so fix it as part of landing P1-003.

**Blocking — `html_body=` routing (Finding 3).** The seam's `reply(to,
subject, body, in_reply_to)` signature in the task spec takes `body` as the
HTML. The implementer must map that to `smtp.reply_email(...,
body=<plain-text-fallback>, html_body=<the HTML>, ...)`. If the signature
naming is ambiguous, recommend renaming the seam's parameter to `html_body`
to make the routing unambiguous at the call site.

### New Backlog Items

- **S-03:** File an upstream issue/PR against `simple-email-gw`: its README
  documents `EMAIL_RECIPIENT_ADDRESSES` / `EMAIL_RECIPIENT_DOMAINS`, but the
  pydantic config binds `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` /
  `EMAIL_RECIPIENT_WHITELIST_DOMAINS`. The mismatch silently disables the
  whitelist for anyone following the README. Low effort, high value.
- **S-04 (carries forward from P1-002):** `SECURITY.md` for
  `__YOKER_MANIFEST__` additions — unchanged by this task.

## TODO.md Recommendations for the Functional-Analyst

I do not edit `TODO.md` directly. Recommendations to integrate:

1. **P1-003 acceptance criteria — add two blocking checks.** Suggested
   wording to append to the acceptance line:
   - "the seam's `reply()` passes the agent's HTML through the gateway's
     `html_body=` parameter (not `body=`), so the reply is sent as
     `text/html`;"
   - "the seam (or the loop at startup) asserts that
     `simple_email_gw.get_recipient_whitelist().enabled` is `True` and the
     address list is non-empty, and fails closed (or warns loudly, per owner
     decision) otherwise."

2. **P1-002 errata / fix — `.env.example` and `README.md` use the wrong env
   var name.** Recommend the functional-analyst open a follow-up to rename
   `EMAIL_RECIPIENT_ADDRESSES` → `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` in
   `.env.example` and `README.md` (Configuration section). This is a
   P1-002 deliverable correction but blocks P1-003's reply-safety
   guarantee, so it should land alongside P1-003. Add a note to the P1-003
   entry referencing this dependency.

3. **P1-003 scope note — seam contract.** Recommend adding to the P1-003
   scope note: "The seam is pure wrapping. It must NOT (a) reinvent the
   recipient whitelist — it delegates to `simple-email-gw`'s
   `RecipientWhitelist`; (b) sanitize or re-render the HTML reply — it sends
   the agent's HTML verbatim via `html_body=`; (c) call
   `SecretStr.get_secret_value()` except where required to pass credentials
   to the gateway (the gateway already does this internally, so the seam
   should not need to); (d) add `subprocess`, file I/O, or business logic."

4. **P1-003 scope note — TLS.** Recommend adding: "The seam must not
   downgrade transport security. Construct `EmailAccount` via the gateway's
   `ServerConfig`/`get_accounts()` so TLS 1.2+ defaults apply. If the seam
   builds `EmailAccount` directly, it must refuse or loudly warn on any
   configuration that would authenticate over a plaintext transport."

5. **P1-003 scope note — logging.** Recommend adding: "The seam logs
   connection events and counts (unread count, fetched id, replied recipient
   subject prefix, mark_read id, archived id) at INFO; it never logs message
   bodies, credentials, or full headers."

6. **P4-001 (tutorial README) — reply-safety subsection.** When the tutorial
   is written, the "Security configuration" subsection (already requested in
   P1-002 analysis) must use the correct env var name
   `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` and explicitly call out that the
   whitelist is the primary reply-safety boundary and is silently disabled
   if the env var is wrong or unset.

7. **New backlog item S-03** (upstream doc bug in `simple-email-gw`) —
   recommend the functional-analyst add this to the backlog as a low-effort,
   high-value cross-project contribution.

## Positive Observations

- `EmailAccount.password` and `oauth2_token` are pydantic `SecretStr`, so
  their default `repr` is redacted — the gateway gets credential hygiene
  right at the data layer.
- The gateway enforces TLS 1.2+ with certificate verification on both IMAP
  and SMTP by default, and exposes no "disable TLS" knob through the seam's
  call path. Transport security is inherited for free as long as the seam
  does not hand-build a downgraded `EmailAccount`.
- The gateway sanitizes all email headers against CRLF injection
  (`sanitize_subject`, `sanitize_message_id`, `sanitize_references`,
  `validate_email` rejects CR/LF) inside `reply_email`/`send_email` — so
  the seam does not need to reinvent header sanitization, and must not
  bypass it by constructing raw MIME itself.
- The gateway's `reply_email` calls `get_recipient_whitelist().is_allowed(to)`
  and raises `WhitelistError` before sending — the enforcement point is
  correct. The only gap is that the whitelist is silently disabled by the
  env-var mismatch (Finding 1), not that enforcement is missing.
- The gateway's `safety.audit` module logs account name, subject prefix,
  recipients, and success/failure — not message bodies or passwords. The
  seam's logging posture can align with this.
- The seam design keeps reply-safety in the gateway (no package-level
  allowlist), consistent with functional.md §5.3/§8.7. This is the right
  architectural call; the blocking issue is configuration, not architecture.

## References

- OWASP Top 10:2025 — A01 (Broken Access Control), A02 (Security
  Misconfiguration), A04 (Cryptographic Failures), A05 (Injection),
  A06 (Insecure Design), A09 (Security Logging Failures).
- CWE-209 (Information Exposure Through an Error Message), CWE-295 (Improper
  Certificate Validation), CWE-327 (Use of a Broken or Risky Crypto
  Algorithm), CWE-400 (Uncontrolled Resource Consumption), CWE-532 (Insertion
  of Sensitive Information into a Log File), CWE-665 (Improper Initialization
  — insecure default), CWE-1188 (Insecure Default).
- STRIDE: Spoofing (TLS), Tampering (IMAP flag ordering), Repudiation
  (gateway audit), Information Disclosure (credentials/exceptions/logs),
  Denial of Service (reconnect storm), Elevation of Privilege (unchanged —
  P1-002 self-trust surface).
- Verified against installed `simple_email_gw` 0.3.0
  (`.venv/lib/python3.12/site-packages/simple_email_gw/`): `config.py`
  (pydantic `ServerConfig` env binding), `imap/client.py` (`connect()` TLS),
  `smtp/client.py` (`reply_email`/`send_email` whitelist enforcement and
  `html_body` routing), `safety/audit.py` (logging posture).