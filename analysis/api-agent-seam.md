> **DESCOPE NOTE (per owner feedback during PR #4 plan review):** The `Assistant` wrapper class design reviewed below was dropped — it fails the Wrapper Check (adds no behavior beyond `Persisted(...)` config and forwarding `process()`/`setup()` unchanged to `Agent`). The loop (P2-005) now constructs `Agent` directly. The content below is the historical review of the original design. The verified yoker 0.8.0 API surface (`Agent` constructor, `Persisted` rename, `async process()`) and the §2.3 erratum still apply. See `reporting/p1-004/consensus.md` for the descope update.

# API Architect Review — P1-004: Implement the agent seam module

Scope: the `yoker_assistant/agent.py` seam that wraps yoker's `Agent` and
exposes the `Assistant` class used by the loop (P2-005). This review
verifies the seam against yoker 0.8.0's actual public API surface and
checks the design against the owner's TODO.md spec for P1-004.

## 1. Verified yoker 0.8.0 public API surface

Confirmed against `yoker/src/yoker/core/__init__.py`,
`yoker/examples/library_usage.py`, and the 0.8.0 release notes
(2026-07-15).

### 1.1 `Agent` constructor

```python
from yoker import Agent

Agent(
    config=None,               # discovered from ./yoker.toml then ~/.yoker.toml
    agent_definition=None,     # inline markdown string
    agent_path=None,           # path to a markdown agent-definition file
    context_manager=None,      # context manager instance (e.g. Persisted)
    plugins=(),                # programmatic plugin override (NOT used here)
    ...                        # additional kwargs forwarded to config
)
```

- `agent_path` is the correct entry point for the ported
  `agents/assistant.md` (P2-001).
- `context_manager` accepts any object implementing yoker's context-manager
  protocol; for persistence across `process()` calls this is `Persisted`
  (see §2.1).
- `config=None` is the right call for this package: yoker resolves config
  from `./yoker.toml` and `~/.yoker.toml`, which is exactly the
  deployment model (the user's `~/.yoker.toml` carries backend, model,
  plugins, and `[plugins.trusted]`). No programmatic config injection.

### 1.2 `Agent.process`

```python
async def process(self, message: str) -> str
```

- **Async.** Returns the agent's final text response after all internal
  tool calls complete.
- Tool calls (including `yoker:read`, `yoker_assistant:md_to_html`, etc.)
  happen inside `process`; the seam does not orchestrate them.
- Returns the agent's reply **as a string** — for this package, the HTML
  string produced by the agent's `yoker_assistant:md_to_html` tool call.
  The seam forwards it verbatim to the loop; no re-rendering.

### 1.3 `Persisted` context manager (renamed from `PersistenceContextManager`)

```python
from yoker import Persisted, SimpleContextManager

# 0.8.0 public name: Persisted
context = Persisted(SimpleContextManager(), session_id="yoker-assistant")
```

- The class is exposed as **`Persisted`** in yoker 0.8.0. The earlier name
  `PersistenceContextManager` appears in pre-0.8 code and in
  `analysis/functional.md` §2.3; it is **stale**. See §6 (Erratum).
- Wraps a base context manager (`SimpleContextManager()` is the
  in-memory base) and persists conversation turns keyed by `session_id`.
- The fixed `session_id` is what makes the "same session across restarts"
  acceptance criterion achievable — without a stable id, yoker would
  create a new persisted session each run.

## 2. API mismatches with the TODO.md / functional.md text

### 2.1 `PersistenceContextManager` → `Persisted`

TODO.md P1-004 says "yoker's `PersistenceContextManager` or equivalent".
The "or equivalent" language covers the rename, but the primary name in
the implementation MUST be `Persisted` — that is what 0.8.0 exports.
Functional.md §2.3 still shows `PersistenceContextManager(...)` and is
stale (see §6).

### 2.2 `setup()` must be async

TODO.md P1-004 says "Expose a `setup()` step run once at startup: the
agent reads `PERSONAL.md` (via `yoker:read`) and initializes identity".

The setup step issues a `process()` call (the one-time initialize
message) so the agent can run its first turn. Because `Agent.process` is
async, `setup()` MUST be `async def setup(self) -> None`. The loop
(P2-005) awaits it once before entering the poll loop. A synchronous
`setup()` would require running the async event loop synchronously at
module import — an unjustified indirection for a demo. Slim default:
make it async and await it.

### 2.3 Initialize-prompt ownership split

The initialize prompt is a **seam-owned constant**, NOT an
agent-definition-owned behaviour and NOT a `setup(prompt=)` parameter.

- The **agent definition** (`agents/assistant.md`, P2-001) owns the
  "read `PERSONAL.md` at session start and initialize identity"
  behaviour — that is prose in the definition that the agent follows on
  the first turn.
- The **seam** owns the trigger: a one-line initialize message that
  kicks off the first turn. The seam does NOT tell the agent what to do
  on that turn; it just sends a minimal "initialize" user message and
  the definition's own instructions take over.

This split mirrors the owner's spec: setup is a step, not a parameter;
identity is in the definition, not in the seam. Putting the prompt in a
`setup(prompt=)` parameter would re-introduce instructions-block leakage
into the seam — the same anti-pattern §4.1 of functional.md rejects for
per-email payloads.

### 2.4 Mockability via monkeypatch — no DI

yoker's `Agent` is constructed by direct import. There is no
dependency-injection seam in yoker's design (no `AgentFactory`, no
`agent_provider` callable). Tests mock by monkeypatching
`yoker.Agent` or by substituting a fake `Assistant` at the loop level
(P3-002 fakes `Assistant` directly).

Implication for P1-004: do NOT add a DI parameter to `Assistant.__init__`
(e.g. `agent_factory=`). That would be speculative flexibility — yoker
itself does not require it, the loop does not require it, and tests
already have a clean mock point (the `Assistant` class itself). Slim
default: construct `yoker.Agent` directly inside `Assistant.__init__`.

## 3. Recommended API surface

Adopted as-is from the owner's TODO.md spec, with the two justified
additions from §2 (async `setup`, fixed session id).

### 3.1 Module: `yoker_assistant/agent.py`

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
        # One-time session-setup step. The agent definition owns the
        # read-PERSONAL.md behaviour; this just triggers the first turn.
        await self._agent.process(_INITIALIZE_PROMPT)

    async def process(self, email_message: str) -> str:
        # Each email is the next user message in the SAME session.
        return await self._agent.process(email_message)
```

### 3.2 Constants

- `_SESSION_ID = "yoker-assistant"` — fixed session id for `Persisted`.
  Without this, the "same session across restarts" acceptance criterion
  fails: yoker would generate a fresh persisted session each run.
- `_INITIALIZE_PROMPT` — the one-line initialize message. Class-level
  constant (not a `setup(prompt=)` parameter). The prompt is a trigger,
  not an instructions block; the agent definition owns the actual
  startup behaviour.

### 3.3 What is deliberately NOT here

- No `close()` / `__aenter__` / `__aexit__` — yoker's `Agent` does not
  expose a lifecycle close in 0.8.0; the loop does not need to close
  the seam. Slim default.
- No `setup(prompt: str = "")` parameter — see §2.3.
- No `EmailMessage` dataclass — P1-003 dropped it; `process()` takes a
  `str` (yoker's own contract). The loop (P2-005) builds the string via
  `handoff.build_message(msg_dict)` (P2-006) and hands it to
  `Assistant.process`.
- No sync wrapper around `Agent.process` — async-native is the clean
  fit; a sync wrapper would run a second event loop or thread it, which
  is unjustified complexity for a demo.
- No DI / `agent_factory` parameter — see §2.4.

## 4. Integration shape with yoker's persistence API

```
loop (P2-005)
  │
  ├── once at startup:
  │     assistant = Assistant(agent_path="agents/assistant.md")
  │     await assistant.setup()         # triggers the initialize turn
  │
  └── per email:
        reply_html = await assistant.process(message)  # next turn, same session
        # loop sends reply_html via smtp.reply_email(...)
```

Persistence flow:

- `Assistant.__init__` constructs `Persisted(SimpleContextManager(),
  session_id="yoker-assistant")` and passes it to `Agent`.
- Every `process()` call — including the one inside `setup()` — appends
  a turn to the persisted session under `_SESSION_ID`.
- On restart, `Assistant.__init__` re-constructs `Persisted` with the
  SAME `_SESSION_ID`; yoker rehydrates the persisted conversation so
  the agent remembers prior emails across restarts.
- The fixed session id is the ONLY addition not literally in the
  owner's spec. It is justified: without it, the persistence
  acceptance criterion ("a second `process()` call sees the first
  call's context") is satisfied within a single run, but the stronger
  "same session across restarts" property implied by TODO.md's "the
  same session lives for the whole package run" is not. One constant,
  one line — minimal complexity.

## 5. Simplicity-principle check

Owner's TODO.md spec for P1-004, quoted verbatim:

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

Each item satisfied:

| Owner's spec item | Design here | Satisfied? |
|---|---|---|
| `yoker_assistant/agent.py` wrapping `Agent` | §3.1 | Yes |
| `Assistant(agent_path)` | §3.1 `__init__(self, agent_path: str)` | Yes |
| `async def process(email_message) -> str` | §3.1 `async def process(self, email_message: str) -> str` | Yes |
| Agent constructed ONCE at startup | §4 — `__init__` runs once; loop holds the instance | Yes |
| Persistent context manager | `Persisted(SimpleContextManager(), session_id=_SESSION_ID)` | Yes |
| `PersistenceContextManager` "or equivalent" | `Persisted` (0.8.0 rename; "or equivalent" covers it) | Yes |
| Same session lives for the whole run | `_SESSION_ID` constant | Yes |
| Each `process()` is the next user message | §3.1 forwards `email_message` to `self._agent.process` | Yes |
| Do NOT construct fresh Agent/context per email | `__init__` only; `process` does not re-construct | Yes |
| `setup()` step run once at startup | `async def setup(self) -> None` | Yes |
| Agent reads `PERSONAL.md` via `yoker:read` on setup | Triggered by `_INITIALIZE_PROMPT`; behaviour in agent definition (P2-001) | Yes |

**No deviations from the owner's spec.** The two additions —
`_SESSION_ID` constant and `_INITIALIZE_PROMPT` constant — are
justified by the spec's own acceptance criteria (persistent session
across restarts; setup triggers the first turn) and add one line each.
No sync wrapper, no DI parameter, no `EmailMessage` dataclass, no
`setup(prompt=)` parameter, no `close()`/context-manager protocol.

## 6. Erratum

`analysis/functional.md` §2.3 currently shows:

```python
agent = Agent(agent_path="agents/assistant.md",
              context_manager=PersistenceContextManager(...))
```

This is **stale**. yoker 0.8.0 exports the class as **`Persisted`**, not
`PersistenceContextManager`. The correct form:

```python
from yoker import Agent, Persisted, SimpleContextManager

agent = Agent(agent_path="agents/assistant.md",
              context_manager=Persisted(SimpleContextManager(),
                                        session_id="yoker-assistant"))
```

**Action:** update functional.md §2.3 when P2-001 (agent definition
port) or P1-004 (this task) lands. Both touch the seam area; either PR
is a natural home for the errata pass. This can ride this PR's commit
or be deferred to P2-001's errata pass — implementer's choice, as long
as it does not stay stale past P2-001.

## 7. Verdict

APPROVED. The owner's spec is adoptable as-is; the two justified
additions (`_SESSION_ID`, `_INITIALIZE_PROMPT`) are minimal and required
by the spec's own persistence criterion. No API mismatch blocks
implementation. The single stale name (`PersistenceContextManager` →
`Persisted`) is a documentation errata, not an implementation blocker —
the implementer writes `Persisted` directly.