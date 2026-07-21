# P1-004 Cross-Domain Design Review — Consensus

## DESCOPE UPDATE

The owner challenged the `Assistant` wrapper class design during the
PR #4 plan review — the same over-engineering pattern as P1-003's
`Mailbox` wrapper. The descope drops the wrapper class entirely.

**The Wrapper Check.** The `Assistant` class adds no behavior beyond
`Persisted(...)` config in `__init__` and forwarding `process()` /
`setup()` unchanged to `Agent.process()`. It fails the check: the
class is pure pass-through with no added logic, no branching, no
state of its own.

**The descope.**

- No `Assistant` class.
- The loop (P2-005) constructs `Agent` directly with
  `Persisted(SimpleContextManager(), session_id="yoker-assistant")`.
- The one-time setup turn is
  `await agent.process(_INITIALIZE_PROMPT)` inlined in the loop.
- `agent.py` either disappears or shrinks to module-level constants
  (`_SESSION_ID`, `_INITIALIZE_PROMPT`) plus optionally a factory
  function `make_agent(agent_path) -> Agent` — no class, no
  forwarding methods.

**What still applies.** The security findings below — no guard
beyond owner's spec; two Medium architectural risks accepted by
design (F1 prompt-injection persistence, F2 on-disk session
persistence) — still apply to the descoped design. The
persistent-session architecture is unchanged (same `Agent` +
`Persisted` + fixed session id); only the wrapper class is gone.

**TODO.md state.** P1-004, P2-005, and P3-002 have been updated to
reflect the descope.

The analysis below is retained as the historical record of the
original cross-domain review of the `Assistant` wrapper design.

---

## Task

**P1-004 — Implement the agent seam module.** Create
`yoker_assistant/agent.py` wrapping yoker's `Agent`; expose
`Assistant(agent_path)` with `async def process(email_message) -> str`
and a one-time `setup()` step. The `Agent` is constructed ONCE at
startup with a persistent context manager; each `process()` call is the
next user message in that same session.

## Reviewers

- **api-architect** — invoked for the backend / SDK-API scope: verify
  the seam against yoker 0.8.0's actual public API surface, check the
  design against the owner's TODO.md spec, flag API mismatches.
- **security-engineer** — invoked for the security scope: threat-model
  the persistent-session seam, enumerate findings, recommend (or
  decline) additional guards.

Both reviewers were instructed by the harness not to write the `.md`
files themselves; their findings are persisted in
`analysis/api-agent-seam.md` and `analysis/security-agent-seam.md`.
This document is the consensus.

## Verdict

**APPROVED — proceed to implementation.**

Both reviewers converge on the same design. No disagreements to
reconcile. The owner's TODO.md spec is adopted as-is, with two
justified one-line additions required by the spec's own acceptance
criteria. No additional guard, wrapper, or indirection is warranted.

## Consensus on the design

1. **Owner's TODO.md spec adopted as-is.** `Assistant(agent_path)`
   class with `async def process(email_message: str) -> str` and
   `async def setup() -> None`. The `Agent` is constructed ONCE at
   startup with a persistent context manager; each `process()` call is
   the next user message in that session. No fresh `Agent`/context per
   email.

2. **Rename: use yoker 0.8.0's `Persisted` class** (not
   `PersistenceContextManager`). TODO.md's "or equivalent" language
   covers this. yoker 0.8.0 exports the class as `Persisted`; the
   older name in `functional.md` §2.3 is stale (see Erratum below).

3. **Fixed session id `"yoker-assistant"` required for persistence
   across restarts.** Justified addition — without it, the
   same-session-across-restarts acceptance criterion fails: yoker
   would generate a fresh persisted session each run. Implemented as a
   single module-level constant `_SESSION_ID = "yoker-assistant"`.

4. **`_INITIALIZE_PROMPT` as a class-level constant.** Justified —
   `setup()` needs a prompt to trigger the first turn. The agent
   definition (P2-001) owns the "read `PERSONAL.md`" behaviour; the
   seam only triggers the first turn with a one-line initialize
   message. This is NOT a `setup(prompt=)` parameter (that would
   re-introduce instructions-block leakage into the seam, the
   anti-pattern `functional.md` §4.1 rejects for per-email payloads).

5. **Slim per owner's spec.** No sync wrapper around `Agent.process`
   (async-native is the clean fit). No DI parameter
   (`agent_factory=`) — yoker has no DI seam; tests mock by
   monkeypatching `yoker.Agent` or by substituting a fake `Assistant`
   at the loop level (P3-002). No `EmailMessage` dataclass —
   `process()` takes a `str` per yoker's own contract; the loop
   (P2-005) builds the string via `handoff.build_message(msg_dict)`
   (P2-006). No `setup(prompt=)` parameter. No `close()` / context
   manager protocol — yoker's `Agent` does not expose a lifecycle
   close in 0.8.0; the loop does not need one.

6. **No email/IMAP leakage.** The seam module references no
   `simple_email_gw`, `IMAPClient`, `SMTPClient`, `reply_email`, or
   `send_email` symbols. This is an explicit acceptance criterion in
   the owner's spec and in the security review (AC-S6).

### Recommended API surface (from api-architect)

```python
from yoker import Agent, Persisted, SimpleContextManager

_SESSION_ID = "yoker-assistant"
_INITIALIZE_PROMPT = (
    "Initialize this session: read PERSONAL.md via yoker:read and set up "
    "your identity for the ongoing session."
)


class Assistant:
    def __init__(self, agent_path: str) -> None:
        context = Persisted(SimpleContextManager(), session_id=_SESSION_ID)
        self._agent = Agent(agent_path=agent_path, context_manager=context)

    async def setup(self) -> None:
        await self._agent.process(_INITIALIZE_PROMPT)

    async def process(self, email_message: str) -> str:
        return await self._agent.process(email_message)
```

## Security consensus

**No guard beyond the owner's spec.** The security-engineer review
states this explicitly with a 5-point justification (seam is a
pass-through; input trust is a loop concern; persistence is yoker's
responsibility; the agent's tool surface is bounded by yoker; the
showcase depends on the persistent-session property).

**Two Medium architectural risks accepted by design:**

- **F1 — Prompt-injection persistence across emails.** A malicious
  email's content persists in the session and can affect the agent's
  behaviour on later emails. Inherent to the persistent-session design
  the owner chose. Clean mitigation: loop-level sender allowlist
  (P2-005), already on the backlog, if the owner wants it later.
- **F2 — On-disk session persistence across restarts.** The full
  conversation (every email body + reply) is persisted to disk under
  the fixed session id. Single-user host model; yoker's `Persisted`
  file hygiene is the underlying control. Clean mitigation:
  documentation in P4-001.

Three Low/Informational findings also accepted: full `yoker:git` on
untrusted content (demo beat), `PERSONAL.md` writes (owner's P2-001
decision), `load_dotenv` in `Agent.__init__` (not a P1-004 concern).

yoker 0.8.0's existing guardrails provide the underlying safety layer
the seam relies on: `PathGuardrail`, git arg sanitization, `Persisted`
file hygiene, `process()` serialization, self-trust documentation,
and the reply-safety boundary at `simple-email-gw`'s recipient
whitelist.

## Additional acceptance criteria (non-blocking, from security review)

The following six criteria are checkable by inspection or test and
should be verified at implementation review. They are in addition to
the owner's functional acceptance criteria in TODO.md.

- [ ] **AC-S1:** No credentials (api_key, email password, IMAP/SMTP
  host, username) appear as literals, constants, or env reads inside
  `yoker_assistant/agent.py`. The seam is credential-free.
- [ ] **AC-S2:** No new plugin-trust surface is introduced. The seam
  does not call `Agent(plugins=...)`, does not register tools, and does
  not modify `__YOKER_MANIFEST__`. The seam only consumes yoker's
  already-trusted plugin surface.
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
  `agent.py`. The seam is email-transport-agnostic and shell-free.

## Erratum noted

`analysis/functional.md` §2.3 currently shows:

```python
agent = Agent(agent_path="agents/assistant.md",
              context_manager=PersistenceContextManager(...))
```

This is **stale** — yoker 0.8.0 exports the class as **`Persisted`**,
not `PersistenceContextManager`. The correct form:

```python
from yoker import Agent, Persisted, SimpleContextManager

agent = Agent(agent_path="agents/assistant.md",
              context_manager=Persisted(SimpleContextManager(),
                                        session_id="yoker-assistant"))
```

**Disposition:** this can ride the P1-004 PR's commit (natural — the
PR touches the seam area) OR be deferred to P2-001's errata pass
(P2-001 also touches the seam area and already carries the
`pkgq:find_package` → `pkgq:find` errata). Implementer's choice, as
long as it does not stay stale past P2-001.

## Implementation plan reference

The implementation plan (module layout, test points, commit sequence)
will be posted as a PR comment after the P1-004 branch is created.
This document records the design consensus only; the PR comment will
record the execution plan.