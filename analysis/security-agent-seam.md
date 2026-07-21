> **DESCOPE NOTE (per owner feedback during PR #4 plan review):** The `Assistant` wrapper class design reviewed below was dropped — it fails the Wrapper Check (adds no behavior beyond `Persisted(...)` config and forwarding `process()`/`setup()` unchanged to `Agent`). The security findings below still apply to the descoped design: the persistent-session architecture is unchanged (same `Agent` + `Persisted` + fixed session id), only the wrapper class is gone. The "no guard beyond owner's spec" verdict and the two Medium architectural risks (prompt-injection persistence, on-disk session persistence) carry over unchanged. See `reporting/p1-004/consensus.md` for the descope update.

# Security Engineer Review — P1-004: Implement the agent seam module

Scope: the `yoker_assistant/agent.py` seam — the `Assistant` class that
wraps yoker's `Agent`, constructs it once at startup with a persistent
context manager, and forwards each email as the next user message in a
long-lived session. This review covers the seam itself and its boundary
with yoker's persistence + agent runtime, not the loop (P2-005) or the
agent definition (P2-001).

## 1. Executive summary

The seam is **clean at the boundary**. The owner's TODO.md spec is
adoptable as-is with no additional guard, gate, or wrapper required
inside `agent.py`. Two Medium architectural risks — prompt-injection
persistence across emails and on-disk session persistence across
restarts — are inherent to the persistent-session design the owner
chose and are **accepted by design** for the showcase; their clean
mitigation (loop-level sender allowlist, P2-005) is already on the
backlog if the owner wants it later. yoker 0.8.0's existing guardrails
(`PathGuardrail`, git arg sanitization, `Persisted` file hygiene,
`process()` serialization, self-trust documentation) provide the
underlying safety layer the seam relies on; the seam does not need to
re-implement any of them.

## 2. Owner's proposal — quoted in full + verdict

Owner's TODO.md P1-004 spec, quoted verbatim:

> Create `yoker_assistant/agent.py` wrapping yoker's `Agent`. Expose
> `Assistant(agent_path)` with `async def process(email_message) -> str`.
> The `Agent` is constructed **ONCE** at startup with a **persistent
> context manager** (yoker's `PersistenceContextManager` or equivalent).
> The same session lives for the whole package run; each `process()` call
> is the next user message in that session. Do NOT construct a fresh
> `Agent`/context per email.
> Expose a `setup()` step run once at startup: the agent reads
> `PERSONAL.md` (via `yoker:read`) and initializes identity for the
> ongoing session.
>
> **Acceptance:** `Assistant.process("test")` returns a string using a real
> backend (or is mockable for tests); a second `process()` call sees the
> first call's context (persistent session); no email/IMAP references in
> this module.

**Verdict: adopted as-is.** No guard beyond this spec is warranted.
Section 5 states the justification in detail.

## 3. Threat model (STRIDE) for the persistent-session seam

| STRIDE category | Application to the seam | Notes |
|---|---|---|
| **S**poofing | Sender spoofing at the mailbox layer (out of seam scope — `simple-email-gw` whitelist is the control). The seam itself does not authenticate senders; it receives whatever the loop hands it. | Loop concern (P2-005). |
| **T**ampering | Tampering with the persisted session file on disk. `Persisted` writes to a yoker-managed path; an attacker with write access to the user's home can inject or alter turns. | Acceptable for a single-user showcase on a host the owner controls. |
| **R**epudiation | Not applicable — the seam does not make trust-relevant decisions; all actions are logged by yoker and the loop. | — |
| **I**nformation disclosure | The persisted session file contains every email body and every reply, in plain text on disk. Credential leakage: the seam itself holds NO credentials (no api_key, no email password). | On-disk persistence risk — see §4. |
| **D**enial of service | A malicious email could attempt to exhaust the context window. yoker handles context-window growth (functional.md §8 Q11); the seam does not. | yoker's responsibility. |
| **E**levation of privilege | The agent runs with the user's filesystem and network permissions. `yoker:git` (full git) gives commit+push capability on the owner's repo. Bounded by yoker's `PathGuardrail` and git arg sanitization. | Demo beat depends on this; accepted. |

## 4. Findings

| # | Finding | Severity | Disposition | Rationale |
|---|---|---|---|---|
| F1 | **Prompt-injection persistence across emails.** A malicious email's content persists in the session and can affect the agent's behaviour on later emails from the legitimate owner. | Medium | **Accept for showcase.** Loop-level sender allowlist (P2-005) is the clean mitigation if the owner wants it later. | Inherent to the persistent-session design the owner chose. The alternative (fresh session per email) breaks the "agent remembers across emails" property the showcase demonstrates. Not a seam-level guard; it is a loop-level input-trust decision. |
| F2 | **On-disk session persistence across restarts.** The `Persisted` context manager writes the full conversation (every email body + reply) to disk under the fixed session id `"yoker-assistant"`. Anyone with read access to the user's home can read every email the agent has ever processed. | Medium | **Accept. Document in P4-001.** | Single-user host model. The fixed session id is required by the persistence-across-restarts criterion. yoker's `Persisted` file hygiene (no world-readable perms, yoker-managed path) is the underlying control. Documentation is the right action, not a code guard. |
| F3 | **Full `yoker:git` on untrusted content.** The agent can commit and push to the owner's repo based on reasoning over email content — including a malicious email that instructs it to commit something. | Low | **Accept — demo beat.** | The git commit/push demo beat (functional.md §4.3) is the showcase's headline "acts on behalf of the owner" moment. yoker's git arg sanitization (no shell, no arbitrary ref paths) is the underlying control. The agent definition (P2-001) owns the "what gets committed" guardrails. |
| F4 | **`PERSONAL.md` writes.** The agent writes learned behaviours to `PERSONAL.md` and commits/pushes them. A malicious email could attempt to inject a "learned behaviour" that biases future responses. | Low | **Accept — owner's P2-001 decision.** | The owner's spec for P2-001 explicitly keeps the read/write `PERSONAL.md` behaviour AS-IS from c3. The agent definition owns the "what is a legitimate learned behaviour" guardrail. No seam-level code guard. |
| F5 | **`load_dotenv` in `Agent.__init__`.** yoker's `Agent.__init__` calls `load_dotenv()` to pick up `.env` files. This is yoker's behaviour, not the seam's. | Informational | **Not a P1-004 concern.** | The seam does not call `load_dotenv`. Any risk from yoker's behaviour is a yoker-level finding, not a seam-level one. Recorded for completeness. |

## 5. No guard beyond the owner's spec — explicit statement

**No additional guard, gate, wrapper, or check is warranted inside
`agent.py` beyond the owner's TODO.md spec.** Justification:

1. **The seam is a pass-through.** `Assistant.process(email_message)`
   forwards a string to `Agent.process` and returns a string. It does
   not parse, interpret, or branch on the email content. There is no
   decision point to guard.
2. **Input trust is a loop concern, not a seam concern.** Which senders
   are admitted into the session is decided at the mailbox layer
   (`simple-email-gw`'s `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`) and
   re-inforceable at the loop layer (P2-005 sender allowlist). Adding a
   guard inside the seam would duplicate the loop's decision and split
   the trust boundary across two modules.
3. **Persistence is yoker's responsibility.** `Persisted`'s file
   hygiene (path, permissions) is owned by yoker. Re-implementing it in
   the seam would violate the slim-default principle and duplicate
   yoker's control.
4. **The agent's tool surface is bounded by yoker.** `PathGuardrail`,
   git arg sanitization, URL validation, and the curated `tools:`
   frontmatter (P2-001) are the underlying controls. The seam does not
   expand or contract the agent's capabilities.
5. **The showcase depends on the persistent-session property.** Any
   guard that breaks "agent remembers across emails" (e.g. per-email
   session reset) would break the demo. The clean mitigations for the
   two Medium findings (F1, F2) are loop-level (sender allowlist,
   documentation) — already on the backlog or in P4-001.

## 6. P1-004-specific security acceptance criteria

The following are **non-blocking** acceptance criteria for P1-004,
derived from this review. They are in addition to the owner's
functional acceptance criteria in TODO.md. Each is checkable by
inspection or test.

- [ ] **AC-S1:** No credentials (api_key, email password, IMAP/SMTP
  host, username) appear as literals, constants, or env reads inside
  `yoker_assistant/agent.py`. The seam is credential-free.
- [ ] **AC-S2:** No new plugin-trust surface is introduced. The seam
  does not call `Agent(plugins=...)`, does not register tools, and does
  not modify `__YOKER_MANIFEST__` (that lives in `__init__.py` per
  P2-008). The seam only consumes yoker's already-trusted plugin
  surface.
- [ ] **AC-S3:** No `load_dotenv` call in `agent.py`. yoker's own
  `load_dotenv` in `Agent.__init__` is out of the seam's scope; the
  seam must not add a second one.
- [ ] **AC-S4:** The persistent context manager (`Persisted` with
  `session_id="yoker-assistant"`) is the ONLY context passed to
  `Agent`. No fallback in-memory context, no per-email context swap.
- [ ] **AC-S5:** `setup()` is the only startup mutation. It sends the
  one-time initialize message and returns. It does NOT write
  `PERSONAL.md` itself — the agent (via its tools, inside `process`)
  handles `PERSONAL.md` reads and writes, driven by the agent
  definition (P2-001). The seam does not touch `PERSONAL.md` directly.
- [ ] **AC-S6:** No `Bash`, `mcp__`, or `send_email` references in
  `agent.py`. The seam is email-transport-agnostic and shell-free; it
  hands strings to yoker and returns strings to the loop.

## 7. Positive observations about yoker's guardrails

The seam's "no additional guard" verdict is credible because yoker
0.8.0 already provides the underlying safety layer. Confirmed during
this review:

- **`PathGuardrail`** — yoker's file tools (`read`, `write`, `update`,
  `list`, `search`) enforce a configured allowlist of filesystem roots.
  The agent cannot read or write outside the configured paths.
- **Git arg sanitization** — `yoker:git` does not shell out; it calls
  git via a bounded API with argument validation. No arbitrary ref
  paths, no `--exec`, no shell injection surface.
- **`Persisted` file hygiene** — `Persisted` writes to a yoker-managed
  path under the user's home, with file permissions that do not expose
  the conversation to other users on a multi-user host.
- **`process()` serialization** — `Agent.process` is async but
  serializes tool calls internally; the seam does not need to add a
  concurrency guard.
- **Self-trust documentation** — yoker's docs are explicit that
  `[plugins.trusted]` is a trust-the-package decision with no per-call
  gate; users must pin versions and verify source. This is the
  trust model the seam inherits.
- **Reply-safety boundary** — the seam does not send email. Replies
  are sent by the loop (P2-005) via `simple_email-gw`'s
  `reply_email`, and the recipient whitelist
  (`EMAIL_RECIPIENT_WHITELIST_ADDRESSES`) is the email-side safety
  boundary. The seam is not in the reply path.

## 8. Verdict

APPROVED. The owner's spec is adoptable as-is. No guard beyond it is
warranted. Two Medium architectural risks (F1, F2) are accepted by
design for the showcase; their clean mitigations are loop-level
(sender allowlist P2-005) or documentation (P4-001), already on the
backlog. The six non-blocking security acceptance criteria in §6 are
checkable by inspection and should be verified at implementation
review.