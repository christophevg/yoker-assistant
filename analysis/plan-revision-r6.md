# Plan Revision R6 — Switch from bare `Agent` to `Session`

**Date:** 2026-07-23
**Author:** Functional Analyst
**Scope:** Per the owner's round-3 directive, switch the loop from
constructing a bare `yoker.Agent` to constructing a `yoker.session.Session`.
Session owns the agent registry, resolves the assistant by name from the
plugin system, and exposes the `agent` tool so the assistant can spawn
sub-agents. This is Option A from R5 §1.3, previously deferred as
"scope-creep" — now explicitly requested by the owner.

## Owner's instructions (quoted verbatim)

> Regarding theme 2: Yoker should handle this. Currently it is indeed not
> easy to create a single `Agent` from a plugin, because plugin agents are
> managed at the level of a `Session`. So today we should use `Session`.
> This also exposes the `agent` tool, so that the assistant can spawn other
> agents, in the session.

## Does the revision satisfy each quoted item?

1. **"Yoker should handle this."** YES. The agent-definition loading is
   delegated to yoker's Session + plugin loader. The manual
   `_load_assistant_definition` helper (R5's bridge code) is removed
   entirely. Session's `AgentRegistry` discovers the assistant agent from
   the `yoker_assistant` plugin manifest and resolves it by name.

2. **"plugin agents are managed at the level of a `Session`. So today we
   should use `Session`."** YES. The loop constructs a `Session` instead of
   a bare `Agent`. Session owns the registry, constructs the primary agent
   from the resolved definition, and manages the context-manager lifecycle.

3. **"This also exposes the `agent` tool, so that the assistant can spawn
   other agents, in the session."** PARTIAL. Session injects the `agent`
   tool onto every agent it owns (gated by `config.tools.agent.enabled`,
   which defaults to True). The tool is present and visible to the
   assistant. HOWEVER, the assistant's `AgentDefinition.agents` allowlist
   (the `agents:` frontmatter field in `assistant.md`) is currently empty
   (`()`), which means the `agent` tool's description shows "(none
   allowed)" and any spawn attempt raises "no allowed spawns." For the
   assistant to actually spawn sub-agents, the `assistant.md` frontmatter
   needs an `agents:` field listing the agents it may spawn (e.g.
   `agents: [yoker:researcher]`). This is a separate, additive change — the
   tool is available by switching to Session; populating the allowlist is a
   configuration choice the owner makes later. See §6.3.

No deviations from the owner's proposal. The switch to Session is
implemented as-is. The `agent` tool availability is a bonus that comes
for free; populating its allowlist is noted as a follow-up, not a
deviation.

---

## 1. Session API findings

### 1.1 Constructor

```python
Session(
  config: Config,
  *,
  session_id: str | None = None,
  extra_plugins: tuple[str, ...] = (),
  agent_definition: AgentDefinition | None = None,
  agent_path: str | Path | None = None,
  plugins: tuple[str, ...] | None = None,
  thinking_mode: ThinkingMode | None = None,
  console_logging: bool = CONSOLE_LOGGING,
)
```

Source: `/Users/xtof/Workspace/agentic/yoker/src/yoker/session/__init__.py:56-98`.

Key points:
- **`config` is required** (not optional, unlike `Agent` which auto-loads
  it). The loop must load config via `get_yoker_config()` and pass it.
- **`session_id`** stamps onto `config.context.session_id` (line 70) —
  single source of truth for persistence. Passing
  `session_id="yoker-assistant"` makes the session id
  `"yoker-assistant"`.
- **`agent_definition` / `agent_path`** are optional. When both are None,
  Session falls back to `config.agent` or `config.agents.definition` to
  resolve the primary agent by name (see §1.4).
- **`extra_plugins`** adds plugin packages on top of
  `config.plugins.packages`. The yoker.toml already lists
  `["yoker_assistant"]`, so `extra_plugins` is not needed for normal
  operation.

### 1.2 Lifecycle — async context manager

Session is an async context manager:

```python
async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent  # the primary Agent
    await agent.process("Initialize")
    # ... loop ...
```

- `__aenter__` emits `SESSION_START` and returns `self`.
- `__aexit__` cancels outstanding spawned-agent tasks, emits
  `SESSION_END`, and calls `agent.context.close()` on every registered
  agent.

**The Session must stay open for the loop's lifetime.** The entire loop
body (Initialize turn, pool setup, poll loop, signal handlers) lives
inside the `async with Session:` block. This is a structural change — the
loop body is indented one level deeper — but not a complexity increase.

### 1.3 Processing messages — `session.agent.process()`

Session does NOT have a `process()` method. The primary agent is
`session.agent` (an `Agent` instance constructed in `__init__` via
`_create_agent`). You call it directly:

```python
reply = await session.agent.process(message)
```

**Session is constructed once and reused across all `process()` calls.**
The primary agent persists for the Session's lifetime. This matches the
current loop's "construct once, reuse across messages" pattern — just via
Session instead of bare Agent.

### 1.4 Agent resolution by name

`Session._resolve_definition` (lines 362-390) resolves the primary agent
in this order:

1. Explicit `agent_definition` parameter.
2. Explicit `agent_path` parameter.
3. `config.agent` (a string — a name or file path).
4. `config.agents.definition` (a string — a name or file path).

When the reference is a string that is not a file path, Session looks it
up in the `AgentRegistry` via `self.agents.resolve(reference)`. The
registry is populated in `__init__` by `self.agents.load(config,
extra_plugins)`, which loads agents from:

- `config.agents.directories` (filesystem directories).
- Plugin packages (via `load_plugins(config, extra_plugins)`).

For yoker-assistant, the `yoker_assistant` plugin's manifest declares
`agents_dir="agents"`, so the plugin loader discovers
`src/yoker_assistant/agents/assistant.md` and registers it as
`yoker_assistant:assistant` in the registry.

Setting `config.agent = "yoker_assistant:assistant"` makes Session
resolve the assistant by name from the registry. This is the
name-resolution the owner asked for — no manual `_load_assistant_definition`
helper, no fragile file path.

### 1.5 Persistence — configured via `config.context`, not a constructor param

Session does NOT accept a `context_manager` parameter. Instead, it
constructs a per-agent context manager in `_create_agent` via:

```python
cm = create_context_manager(self.config, agent_id)
```

Source: `/Users/xtof/Workspace/agentic/yoker/src/yoker/session/__init__.py:340`.

`create_context_manager` (factory.py:16-46) reads `config.context`:

| Config field | Default | Effect |
|---|---|---|
| `persist_after_turn` | `True` | If False → bare `SimpleContextManager()` (no persistence). If True → `Persisted(SimpleContextManager(), ...)`. |
| `storage_path` | `"./context"` | Directory for JSONL files. |
| `session_id` | `"auto"` | Stamped by Session.__init__ to the Session's `session_id` (e.g. `"yoker-assistant"`). |
| `filename` | `"{session_id}-{agent_id}"` | JSONL filename pattern. |
| `fresh` | `False` | If True, deletes existing JSONL on construction. |

The per-agent `agent_id` is generated by `_generate_agent_name` from the
definition's `simple_name`. For the first (primary) agent named
`assistant`, `agent_id = "assistant"`.

So with `session_id="yoker-assistant"` and the default filename pattern,
the JSONL file is `yoker-assistant-assistant.jsonl` in the
`storage_path` directory.

**Migration concern:** the current loop produces `yoker-assistant.jsonl`
in `~/.cache/yoker/sessions/` (via `Persisted(SimpleContextManager(),
session_id="yoker-assistant")`). Switching to Session produces
`yoker-assistant-assistant.jsonl` — a different filename. The existing
persisted context is orphaned. Two options:

- **(a) Accept the new filename.** The old `yoker-assistant.jsonl` is
  orphaned; the assistant starts a fresh session. Simplest, one-time
  cost.
- **(b) Set `config.context.filename = "{session_id}"`** to produce
  `yoker-assistant.jsonl` — same filename as before. But this pattern
  means ALL agents in the session share one file, which is wrong for
  multi-agent sessions. Since the assistant is the only primary agent
  and sub-agents get their own `agent_id`s (e.g. `researcher-2`), the
  pattern `{session_id}` would collide for sub-agents. Not recommended.

**Recommendation: accept the new filename (option a).** The migration is
a one-time orphaning of the old context. The assistant re-initializes on
the next run. This is acceptable for a first-pass system.

**Storage path concern:** the current loop uses
`~/.cache/yoker/sessions/` (Persisted's `DEFAULT_STORAGE_PATH`). But
`ContextConfig.storage_path` defaults to `"./context"` (relative to cwd).
To avoid the context files landing in an unexpected location, the loop
should set `config.context.storage_path` explicitly. The cleanest: use
the same default as Persisted:

```python
from yoker.context import DEFAULT_STORAGE_PATH
config.context.storage_path = str(DEFAULT_STORAGE_PATH)
```

Or, if the user's `~/.yoker.toml` configures `[context] storage_path`,
that value is used and the loop does not override it. The loop should only
set it as a fallback when the config has the default value. Actually, the
simplest approach: let the user's yoker.toml control it, and document that
`[context] storage_path` should be set. If the user doesn't configure it,
`./context` is used — a reasonable default for a project-local assistant.

### 1.6 The `agent` tool — how it works

Session injects two tools onto every agent it owns (via `inject_tools`,
lines 412-439):

1. **`yoker:agent`** (the spawn tool) — gated by
   `config.tools.agent.enabled` (default True). Calls
   `session._spawn_internal(name, requester=<calling agent>)`, runs the
   spawned agent's `process(prompt)` with a timeout, and
   `session.release(child)` in a finally block. The available agent names
   are baked into the tool description from the calling agent's
   `AgentDefinition.agents` allowlist intersected with
   `session.agents.names`.

2. **`yoker:send_message`** — always injected. Enables inter-agent
   messaging via `session.send(to=, from_=, content=)`.

The `agent` tool is registered AFTER `_filter_tools_by_definition` runs
during Agent construction. So the `yoker:agent` entry in the assistant.md
`tools:` list is not needed for the tool to be available — Session injects
it regardless. Having it in the `tools:` list is harmless (it documents
intent but doesn't affect the filter, since the tool isn't registered at
filter time).

**The allowlist gate:** the `agent` tool bakes available names from
`requester.definition.agents`. If `definition.agents` is `()` (empty), the
tool description shows "(none allowed)" and any spawn attempt raises
"Agent 'assistant' has no allowed spawns." (See `_create_agent` lines
314-320 and `make_spawn_agent_tool` lines 71-77.)

The current `assistant.md` frontmatter does NOT have an `agents:` field, so
`definition.agents = ()`. The `agent` tool will be present but cannot
spawn. This is the "PARTIAL" in §"Does the revision satisfy each quoted
item." Populating the allowlist is a follow-up configuration change, not
part of the Session switch itself.

### 1.7 Config loading — the loop must load config explicitly

The current loop constructs `Agent(...)` which auto-loads config
internally via `get_yoker_config()`. Session requires a `Config` object
explicitly. The loop must:

```python
from yoker.config import get_yoker_config

config = get_yoker_config()
config.agent = "yoker_assistant:assistant"
```

The yoker.toml (user's `~/.yoker.toml` or repo's `./yoker.toml`) provides
the `[plugins]` block (enabled, packages, trusted) and the `[backend]`
block (provider, model). The loop sets `config.agent` programmatically —
the loop knows which agent it wants; this is not a user-config concern.

---

## 2. The updated loop

### 2.1 The new `run()` skeleton

```python
import asyncio
import logging
import re
from email.utils import parseaddr
from signal import SIGINT, SIGTERM
from typing import Any

from simple_email_gw import IMAPClient, SMTPClient, get_pool
from simple_email_gw.config import get_recipient_whitelist
from yoker.config import get_yoker_config
from yoker.session import Session

logger = logging.getLogger(__name__)

NO_REPLY_SENTINEL = "{{NO_REPLY}}"
_INITIALIZE_PROMPT = "Initialize"
_POLL_INTERVAL = 60
_INBOX_FOLDER = "INBOX"
_ARCHIVE_FOLDER = "Archive"
_ACCOUNT_NAME = "default"

_UNSAFE_TAGS = (...)
_UNSAFE_HANDLER = re.compile(...)


def _contains_unsafe_html(html: str) -> bool: ...  # unchanged


def build_message(email_message: dict[str, Any]) -> str: ...  # unchanged


async def _process_one(imap, smtp, agent, message_id) -> None: ...  # unchanged


async def run(once: bool = False) -> None:
    # C1 BLOCKING FIX: refuse to run if the recipient whitelist is disabled.
    if not get_recipient_whitelist().enabled:
        raise RuntimeError(...)

    config = get_yoker_config()
    config.agent = "yoker_assistant:assistant"

    async with Session(config, session_id="yoker-assistant") as session:
        agent = session.agent

        # One-time session-setup turn (§4.1).
        await agent.process(_INITIALIZE_PROMPT)

        # The pool reads the EMAIL_* env vars via ServerConfig.
        pool = await get_pool()
        imap = await pool.get_imap_client(_ACCOUNT_NAME)
        smtp = await pool.get_smtp_client(_ACCOUNT_NAME)

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (SIGINT, SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass

        while not stop.is_set():
            await imap.connect()
            try:
                uids = await imap.search(_INBOX_FOLDER, "UNSEEN")
                for mid in uids:
                    if stop.is_set():
                        break
                    try:
                        await _process_one(imap, smtp, agent, mid)
                    except Exception:
                        logger.exception(
                            "per-message failure; leaving UNSEEN",
                            extra={"message_id": mid},
                        )
                        continue
            finally:
                try:
                    await imap.disconnect()
                except Exception:
                    logger.exception("imap disconnect failed")

            if once:
                break
            if not uids:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL)
                except asyncio.TimeoutError:
                    pass
```

### 2.2 What is removed

- **`_load_assistant_definition`** — removed entirely. Session resolves
  the agent by name from the plugin registry. No manual
  `find_package_subdirectory` + `load_agent_definitions` filtering.
- **`from yoker.agents import AgentDefinition, load_agent_definitions`** —
  removed (no longer needed).
- **`from yoker.resources import find_package_subdirectory`** — removed.
- **`from yoker import Agent, Persisted, SimpleContextManager`** — removed.
  The loop no longer constructs an Agent or a context manager directly;
  Session handles both.
- **The `Agent(agent_definition=..., context_manager=...)` construction**
  — replaced by `Session(config, session_id=...)`.

### 2.3 What is added

- **`from yoker.config import get_yoker_config`** — the loop now loads
  config explicitly (Session requires it).
- **`from yoker.session import Session`** — the new construction entry
  point.
- **`config = get_yoker_config()` / `config.agent = "yoker_assistant:assistant"`**
  — two lines to load config and set the agent name.
- **`async with Session(config, session_id="yoker-assistant") as session:`**
  — the Session construction and context-manager block. The loop body is
  indented one level deeper inside this block.
- **`agent = session.agent`** — one line to get the primary Agent from
  the Session.

### 2.4 What is unchanged

- `build_message`, `_contains_unsafe_html`, the four-way branching in
  `_process_one`, the `{{NO_REPLY}}` sentinel, the Initialize turn, the
  `--once` flag, the signal handlers, `_POLL_INTERVAL`, the graceful
  shutdown, the per-iteration connect/disconnect pattern (from R5).
- The `yoker.toml` plugin configuration (no change needed — it already
  has `[plugins] enabled = true; packages = ["yoker_assistant"];
  [plugins.trusted] yoker_assistant = true`).
- The `__YOKER_MANIFEST__` in `__init__.py` (already has
  `agents_dir="agents"` from R5).
- The `assistant.md` agent definition (no change needed for the Session
  switch itself; the `agents:` allowlist is a separate follow-up).

---

## 3. Impact on `__init__.py` (manifest)

**No change.** The manifest from R5 already declares
`agents_dir="agents"`:

```python
__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)
```

Session's plugin loader uses this to discover `assistant.md` inside the
installed package. The agent is registered as `yoker_assistant:assistant`
in the `AgentRegistry`. No manifest change is needed for the Session
switch.

---

## 4. Impact on tests (`tests/test_loop.py`)

### 4.1 `_load_assistant_definition` tests — REMOVED

The two tests `test_load_assistant_definition_raises_when_directory_missing`
and `test_load_assistant_definition_returns_assistant` are deleted. The
helper they test no longer exists. Name resolution is delegated to
yoker's Session + AgentRegistry, which is tested in yoker's own test
suite.

### 4.2 `run()` tests — mock Session instead of Agent

The current tests mock `yoker_assistant.loop.Agent`:

```python
monkeypatch.setattr("yoker_assistant.loop.Agent", lambda **kwargs: agent)
```

With Session, the tests mock `yoker_assistant.loop.Session` and
`yoker_assistant.loop.get_yoker_config`:

```python
config = MagicMock()
monkeypatch.setattr("yoker_assistant.loop.get_yoker_config", lambda: config)

session = MagicMock()
session.agent = agent
session.__aenter__ = AsyncMock(return_value=session)
session.__aexit__ = AsyncMock(return_value=None)
monkeypatch.setattr("yoker_assistant.loop.Session", lambda *a, **kw: session)
```

Where `agent` is the same `MagicMock()` with `agent.process = AsyncMock(...)`
as before. The `_process_one` tests are unchanged (they take `agent` as a
parameter directly — no Session mock needed).

### 4.3 Specific test adjustments

- **`test_run_proceeds_when_whitelist_enabled`**: replace the `Agent`
  mock with the Session mock pattern (§4.2). The `agent.process` mock
  behavior is unchanged.

- **`test_run_continues_after_process_one_exception`**: same Session mock
  pattern. The `side_effect` list for `agent.process` is unchanged
  (Initialize + 2 messages). The test asserts `agent.process.await_count
  == 3` — this still holds because `session.agent` is the same mock.

- **`test_run_connects_and_disconnects_per_iteration`**: same Session
  mock pattern. The per-iteration connect/disconnect assertions are
  unchanged.

- **`test_run_refuses_to_start_when_whitelist_disabled`**: unchanged —
  the whitelist check fires before Session construction.

- **`_process_one` tests**: unchanged — they call `_process_one` directly
  with a mock `agent` parameter, no Session involvement.

- **`test_process_one_logs_conversation_turns`**: unchanged.

### 4.4 Net test count change

- Remove 2 tests (`_load_assistant_definition` tests).
- No new tests needed for the Session switch itself (Session is a yoker
  SDK class tested in yoker's suite; the loop tests verify the loop
  behavior, which is unchanged).
- Net: -2 tests. The test file shrinks.

### 4.5 Test complexity assessment

The Session mock is slightly more verbose than the Agent mock (3 extra
lines for `__aenter__`/`__aexit__`/`config`), but it replaces the
`_load_assistant_definition` test setup (which required mocking
`find_package_subdirectory` and creating temp agent-definition files).
Net test complexity is lower — fewer lines, fewer mocks, no
package-resource mocking.

---

## 5. Is this simpler or more complex?

**Simpler.** The switch to Session removes more code than it adds:

| Removed | Added |
|---|---|
| `_load_assistant_definition` helper (15 lines) | `config = get_yoker_config()` (1 line) |
| `from yoker.agents import ...` (1 line) | `config.agent = "yoker_assistant:assistant"` (1 line) |
| `from yoker.resources import ...` (1 line) | `from yoker.config import get_yoker_config` (1 line) |
| `from yoker import Agent, Persisted, SimpleContextManager` (1 line) | `from yoker.session import Session` (1 line) |
| `Agent(agent_definition=..., context_manager=Persisted(...))` (3 lines) | `async with Session(config, session_id=...) as session:` + `agent = session.agent` (2 lines) |
| 2 `_load_assistant_definition` tests (~25 lines) | 0 (Session mock replaces Agent mock, same 5 lines) |

Net: ~47 lines removed, ~6 lines added. The loop is shorter, the
agent-definition loading is delegated to yoker, and the persistence is
configured declaratively via `config.context` instead of a manually
constructed `Persisted(SimpleContextManager(), ...)` wrapper.

The only structural change is the one-level-deeper indentation from the
`async with Session:` block. This is not complexity — it is the correct
expression of the Session's lifecycle scope.

---

## 6. Concerns and gotchas

### 6.1 Persisted-context filename change

As noted in §1.5, the JSONL filename changes from `yoker-assistant.jsonl`
to `yoker-assistant-assistant.jsonl` (because Session uses the
`{session_id}-{agent_id}` pattern). The existing persisted context is
orphaned. This is a one-time migration cost — the assistant starts a fresh
session on the next run. Acceptable for a first-pass system.

If the owner wants to preserve the old filename, set
`config.context.filename = "{session_id}"` — but this breaks for
multi-agent sessions (sub-agents would collide on the same file). Not
recommended.

### 6.2 Storage path defaults differ

The current loop uses `~/.cache/yoker/sessions/` (Persisted's
`DEFAULT_STORAGE_PATH`). Session uses `config.context.storage_path`, which
defaults to `"./context"` (relative to cwd). If the user's `~/.yoker.toml`
does not configure `[context] storage_path`, the context files land in
`./context/` instead of `~/.cache/yoker/sessions/`.

The loop should either:
- Set `config.context.storage_path = str(DEFAULT_STORAGE_PATH)` to
  preserve the current location, OR
- Document that the user should set `[context] storage_path` in their
  `~/.yoker.toml`, OR
- Accept `./context/` as the new default (simplest, project-local).

**Recommendation:** accept `./context/` as the new default. It is
project-local, visible, and does not require special config. If the owner
prefers the old location, it is a one-line addition:
`config.context.storage_path = str(DEFAULT_STORAGE_PATH)`.

### 6.3 The `agent` tool allowlist is empty

The assistant's `AgentDefinition.agents` allowlist is `()` (the
`assistant.md` frontmatter has no `agents:` field). The `agent` tool is
injected by Session but cannot spawn anything — the tool description
shows "(none allowed)" and spawn attempts raise.

For the assistant to actually spawn sub-agents, the `assistant.md`
frontmatter needs:

```yaml
---
name: assistant
...
agents:
  - yoker:researcher  # or whatever agents the owner wants to allow
---
```

This is a separate, additive change — the owner decides which agents to
allow. The Session switch makes the `agent` tool AVAILABLE; populating the
allowlist is a follow-up. I note this here so the owner is not surprised
that the tool is present but non-functional until the allowlist is
populated.

### 6.4 Config must have plugins enabled and trusted

Session's `AgentRegistry.load(config, extra_plugins)` only loads plugin
agents when `config.plugins.enabled = True` and the plugin package passes
the trust check (`config.plugins.trusted["yoker_assistant"] = True`). The
yoker.toml in the repo already has this configured, and the
`yoker.toml.example` documents it for users. If the user's
`~/.yoker.toml` does not have the `[plugins]` block, Session will not find
the assistant agent and will raise:

```
ValueError: Agent definition 'yoker_assistant:assistant' could not be
resolved: not a file path and not a registered agent. If it comes from a
plugin, ensure plugins are enabled ([plugins] enabled = true) and the
plugin package is listed in [plugins] packages.
```

This is an explicit, actionable error message from the SDK. No silent
failure. The loop does not need to add its own check — the SDK's error is
sufficient.

### 6.5 Session and the email pool — no interaction

Session and `simple_email_gw`'s `ConnectionPool` are independent. The
pool is constructed inside the `async with Session:` block, after the
Initialize turn. No interaction, no conflict. The pool's lifecycle (per-
iteration connect/disconnect from R5) is unchanged.

### 6.6 Session `__aexit__` closes agent contexts

When the loop exits the `async with Session:` block (on shutdown or
exception), `__aexit__` calls `agent.context.close()` on every registered
agent. This appends a `session_end` marker to the JSONL file — clean
shutdown. The current bare-Agent loop does not do this (the `Persisted`
wrapper is never explicitly closed). This is a minor improvement: the
persisted context gets a clean `session_end` marker on shutdown.

### 6.7 No `agent.py` module needed

The `agent.py` module is already a placeholder (one docstring, no code).
With the Session switch, it remains unnecessary — the Session
construction lives in `loop.py`. `agent.py` can be left as-is or removed
(it is empty either way). No change needed.

---

## 7. Concrete change description for the python-developer

### 7.1 `src/yoker_assistant/loop.py`

1. **Imports:** remove `from yoker import Agent, Persisted,
   SimpleContextManager`, `from yoker.agents import AgentDefinition,
   load_agent_definitions`, `from yoker.resources import
   find_package_subdirectory`. Add `from yoker.config import
   get_yoker_config` and `from yoker.session import Session`.

2. **Remove** the `_load_assistant_definition` function (lines 47-61) and
   the `_ASSISTANT_AGENT_NAME` constant (line 44).

3. **Rewrite `run()`:** replace the `Agent(agent_definition=...,
   context_manager=...)` construction with the config-load + Session
   pattern from §2.1. The entire loop body (Initialize turn, pool setup,
   signal handlers, while loop) moves inside the `async with Session:`
   block.

4. **Do NOT touch** `build_message`, `_contains_unsafe_html`,
   `_process_one`, the four-way branching, the sentinel, the
   `--once` flag, the signal handlers, `_POLL_INTERVAL`, or the per-
   iteration connect/disconnect pattern.

### 7.2 `src/yoker_assistant/__init__.py`

**No change.** The manifest already declares `agents_dir="agents"`.

### 7.3 `src/yoker_assistant/agents/assistant.md`

**No change for the Session switch.** The `agents:` allowlist is a
separate follow-up (§6.3) — the owner decides which agents to allow.

### 7.4 `tests/test_loop.py`

1. **Remove** `test_load_assistant_definition_raises_when_directory_missing`
   and `test_load_assistant_definition_returns_assistant` (lines 356-379).

2. **Remove** the import of `_load_assistant_definition` from the
   `from yoker_assistant.loop import (...)` block.

3. **Update** `test_run_proceeds_when_whitelist_enabled`,
   `test_run_continues_after_process_one_exception`, and
   `test_run_connects_and_disconnects_per_iteration`: replace the
   `monkeypatch.setattr("yoker_assistant.loop.Agent", lambda **kwargs:
   agent)` pattern with the Session mock pattern (§4.2). Add a
   `get_yoker_config` mock returning a `MagicMock()` config.

4. **Do NOT touch** the `_process_one` tests, the
   `test_run_refuses_to_start_when_whitelist_disabled` test, or the
   logging smoke test — they are unaffected.

### 7.5 `analysis/functional.md`

Update the agent-seam section: the loop now constructs a `Session`
instead of a bare `Agent`. The agent is resolved by name
(`yoker_assistant:assistant`) from the Session's `AgentRegistry`, which
discovers it via the plugin system. The `_load_assistant_definition`
helper is removed. Persistence is configured via `config.context` and
the `session_id` parameter to Session. The `agent` tool is available
(pending the `agents:` allowlist in `assistant.md`).

---

## 8. Summary of changes (R5 → R6)

1. **Loop:** replace `Agent(agent_definition=_load_assistant_definition(),
   context_manager=Persisted(...))` with `Session(config,
   session_id="yoker-assistant")`. The loop loads config via
   `get_yoker_config()` and sets `config.agent =
   "yoker_assistant:assistant"`.

2. **Remove** `_load_assistant_definition` and its imports. The helper is
   no longer needed — Session resolves the agent by name from the plugin
   registry.

3. **Remove** the two `_load_assistant_definition` tests.

4. **Update** the three `run()` tests to mock `Session` and
   `get_yoker_config` instead of `Agent`.

5. **No change** to the manifest, the agent definition, the handoff
   builder, the branching logic, the per-iteration connect/disconnect, or
   the logging.

6. **Follow-up (not in this revision):** populate the `agents:` allowlist
   in `assistant.md` so the `agent` tool can actually spawn sub-agents.

This revision is ready for the owner's confirmation. The primary
question for the owner: accept the persisted-context filename change
(§6.1) and the storage-path default change (§6.2), or override with
explicit config?