# Plan Revision R5 — Owner Feedback Round 2 on PR #7 (P2-005 + P2-006)

**Date:** 2026-07-23
**Author:** Functional Analyst
**Scope:** Incorporate the round-2 owner review feedback on PR #7 into the
implementation plan. Four themes: (1) connect/disconnect per loop iteration
instead of holding an IMAP connection open, (2) package the assistant agent
definition and reference it by name (not by relative file path), (3) a typo
correction that flips theme 1's polarity ("not want" a persistent connection),
and (4) add conversation-style logging. This revises R4 by **removing** the
reconnect-on-failure guard (theme 1 overrides R4 §4.3), **adding** the agent
packaging change (theme 2), and **adding** logging (theme 4).

## Owner's instructions (quoted verbatim)

> **Theme 1 (global comment):** Why make things complicated? Why try to keep
> an active connection throughout the loop's lifetime. Simply connect and
> disconnect for every loop iteration. This removes reconnection handling,
> doesn't keep a connection open until it timeouts - which will happen every
> time, because the typical interval will be several minutes anyway.

> **Theme 1 (inline, line 164):** Hm, maybe I misled you with a typo ;-) "now
> want" should have been "not want". See also global comment.

> **Theme 2 (inline, line 135):** I don't think this "file path" will work
> when the assistant is run from a package. I think we need to include the
> folder in the package and reference it in the manifest. Then we need to
> explicitly include ourselves as a plugin to the `Agent`. After that, the
> agent will be known to the internal AgentRepository and we can reference it
> by name.
>
> Warning: this might possibly be difficult to not yet possible. In that case
> we need to raise an issue with the yoker project to provide better support
> for this use case.

> **Theme 4 (inline, line 140):** We might want to add some logging to the
> assistant, so that the logging output resembles the conversation between
> user and agent.

## Does the revision satisfy each quoted item?

1. **Theme 1 — "connect and disconnect for every loop iteration ... removes
   reconnection handling."** YES. R4's reconnect-on-failure guard is removed
   entirely. The new loop calls `await imap.connect()` at the top of each
   iteration and `await imap.disconnect()` in a `finally` at the bottom of
   each iteration. No try/except around `search`. The persistent-connection
   design from R4 §4.3 is reversed. See §2.

2. **Theme 1 typo — "'now want' should have been 'not want'."** YES. The
   owner does NOT want a persistent connection. The new design holds the
   connection open only for the duration of one search+process cycle, then
   disconnects before the sleep. See §2.

3. **Theme 2 — "include the folder in the package and reference it in the
   manifest ... reference it by name."** PARTIAL — by design, per the owner's
   own warning. The agent definition file is moved into the package
   (`src/yoker_assistant/agents/assistant.md`) and loaded from package
   resources at runtime (no relative file path). This fully fixes the
   concrete packaging bug the owner flagged. Referencing the agent **by name
   through the AgentRepository from the bare `Agent`** is NOT achievable
   today — the yoker SDK's `Agent` class has no agent registry; only
   `Session` does (see §1.2 for the evidence). Per the owner's explicit
   instruction ("if not possible, raise an issue with the yoker project"),
   this revision ships the packaging fix now and files an upstream yoker
   issue for the name-resolution feature. See §1.

4. **Theme 4 — "logging output resembles the conversation."** YES. The loop
   logs the incoming handoff (user turn) and the agent's reply (agent turn)
   with clear separators. See §3.

No deviations from the owner's proposals. Theme 2 is the only partial
satisfaction, and it is partial by the owner's own design ("might possibly be
difficult to not yet possible"). The fallback (package the file + upstream
issue) is exactly the path the owner specified for that case.

---

## 1. Yoker SDK agent registration — research findings

### 1.1 What the SDK supports today

**PluginManifest fields** (`/Users/xtof/Workspace/agentic/yoker/src/yoker/plugins/manifest.py:17-63`):

```python
@dataclass
class PluginManifest:
  tools: list[Callable[..., Any]] = field(default_factory=list)
  skills: list["Skill"] = field(default_factory=list)
  agents: list["AgentDefinition"] = field(default_factory=list)
  config_class: type | None = None
  skills_dir: str = "skills"
  agents_dir: str = "agents"        # <-- the relevant field
  agent: str | None = None          # convenience fallback for `yoker run` CLI
  prompt: str | None = None
```

The manifest supports an `agents_dir` field (defaults to `"agents"`). The
plugin loader (`/Users/xtof/Workspace/agentic/yoker/src/yoker/plugins/loader.py:145-182`)
discovers agents from a package as follows:

```python
def load_agents_from_package(package_name, agents_dir):
  path = find_package_subdirectory(package_name, agents_dir)  # importlib.resources
  if path:
    return list(load_agent_definitions(path, namespace=package_name))
  return []
```

`find_package_subdirectory` (`/Users/xtof/Workspace/agentic/yoker/src/yoker/resources.py:30-41`)
uses `importlib.resources.files(package).joinpath(subdir)` — i.e. it locates
the `agents/` subdirectory **inside the installed Python package**, not on
the filesystem. `load_agent_definitions` (plural) handles `Traversable`
resource paths as well as `Path` filesystem paths.

So if we:
1. Move `agents/assistant.md` to `src/yoker_assistant/agents/assistant.md`.
2. Rely on the manifest's default `agents_dir="agents"` (or set it
   explicitly for clarity).
3. Confirm hatchling includes the `.md` file in the wheel.

→ The plugin loader will discover and register the assistant agent as
`yoker_assistant:assistant` (namespace `yoker_assistant`, simple_name
`assistant`) in any `AgentRegistry` that loads this plugin.

**Hatchling wheel inclusion:** `[tool.hatch.build.targets.wheel]
packages = ["src/yoker_assistant"]` already exists. Hatchling recursively
includes every file under that package directory by default — including
`.md` files. No extra `force-include` or `package-data` config is needed.
Verified against yoker's own pyproject (same pattern, no extra config).

### 1.2 The gap — the bare `Agent` has no agent registry

The owner's phrasing: "we need to explicitly include ourselves as a plugin
to the `Agent`. After that, the agent will be known to the internal
AgentRepository and we can reference it by name."

This describes a registry on the `Agent` class. The actual SDK does not have
one:

- **`Agent.__init__`** (`/Users/xtof/Workspace/agentic/yoker/src/yoker/core/__init__.py:43-108`)
  accepts `agent_definition: AgentDefinition | None` and
  `agent_path: Path | str | None`. It does NOT accept an agent **name**. Its
  docstring (lines 65-66) states: "plugins: Optional plugin packages to load
  (tools/skills only; **plugin agent definitions are registered by the
  Session layer**)."

- **`Agent._resolve_agent_definition`** (lines 484-532) resolves the
  definition from: (a) explicit `agent_definition`, (b) a filesystem path
  via `agent_path` or `config.agent`/`config.agents.definition`, or (c)
  the default empty `AgentDefinition()`. A non-path `reference` (i.e. a
  name) explicitly raises:

  ```
  ValueError: Agent definition '<reference>' cannot be resolved by a
  standalone Agent. Pass an explicit agent_definition=, an agent_path= to
  a file, or construct the Agent within a Session so the Session can
  resolve the name.
  ```

  The comment on lines 525-527 is unambiguous: "no registry available on a
  Session-agnostic Agent."

- **The plugin loader in `Agent.__init__`** (lines 101-105) loads plugin
  tools and skills into the Agent's own registries but explicitly SKIPS
  plugin agent definitions — the comment on lines 101-102 says: "Plugin
  agent definitions are skipped here (no session registry); the Session
  layer registers them."

- **`AgentRegistry`** lives in `yoker.agents.registry` and is owned by
  `Session` (`/Users/xtof/Workspace/agentic/yoker/src/yoker/session/__init__.py:76`).
  `Session.agents.load(config, extra_plugins)` populates it from configured
  directories and plugin manifests. `Session._resolve_definition` (lines
  362-390) resolves a name via `self.agents.resolve(reference)`.

So the registry exists, but **only on `Session`**. The bare `Agent` that
yoker-assistant currently uses does not have one and cannot resolve names.

### 1.3 Three options for theme 2

| Option | What it does | Scope | Achievable in this PR? |
|--------|--------------|-------|------------------------|
| **A — Switch to `Session`** | Replace `Agent(agent_path=...)` with a `Session(config, ...)` that resolves `config.agent = "yoker_assistant:assistant"` from its registry. | Large: changes the lifecycle (async context manager), config loading, backend ownership, context-manager ownership. | Yes, but scope-creep. |
| **B — Package the file, load from package resources** | Move `agents/assistant.md` into `src/yoker_assistant/agents/`, load it via `importlib.resources` / `load_agent_definitions` at runtime, pass it as `agent_definition=`. | Small: ~15 lines in `loop.py` + a file move + pyproject unchanged. | **Yes — recommended.** |
| **C — Upstream yoker issue** | Propose the bare `Agent` accept an `agent_name` parameter that resolves against a plugin-agent registry (or expose a lighter-weight "Session-less registry" path). | None in this PR — file an issue. | Out of scope (file issue). |

### 1.4 Recommended split for this PR

- **Adopt Option B in this PR.** It fully addresses the owner's concrete
  worry ("file path won't work when run from a package") with the smallest
  possible change. The loop loads the `AgentDefinition` from the installed
  package's `agents/` directory and passes it to `Agent(agent_definition=...)`.
  No relative file path, no fragile `agent_path="agents/assistant.md"`.

- **File an upstream yoker issue for Option C.** Quote the owner's phrasing
  ("reference it by name ... internal AgentRepository") and the SDK's
  explicit "no registry available on a Session-agnostic Agent" comment.
  Propose either:
  - An `agent_name` parameter on `Agent.__init__` that resolves against
    plugin-loaded agents (requires the bare Agent to load the agent
    registry, which it currently does not), OR
  - A lighter-weight SDK entry point (e.g. `build_agent(name, ...)`) that
    wraps a one-agent Session without exposing the full Session lifecycle.

- **Do NOT adopt Option A in this PR.** Switching to `Session` is the right
  long-term direction (it gives true name-based resolution, backend
  sharing, and event aggregation), but it is a meaningful architectural
  change that belongs in a separate task — not folded into a PR that is
  primarily about loop simplification. Note Option A as a future direction
  in `functional.md` and in the upstream issue.

### 1.5 What this means for the manifest

The current manifest (`/Users/xtof/Workspace/agentic/yoker-assistant/src/yoker_assistant/__init__.py:20`):

```python
__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])
```

After the change:

```python
__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",  # explicit; matches the default
)
```

The `agents_dir="agents"` field is what tells the plugin loader to look for
`agents/*.md` inside the installed `yoker_assistant` package. Other yoker
consumers (e.g. a user running `yoker run --agent yoker_assistant:assistant`)
will then discover the assistant agent by name from their own `Session`'s
registry. This is the "reference by name" half of the owner's phrasing — it
works for **external** consumers via the plugin system, just not for
yoker-assistant's **own** bare-`Agent` loop (that's the gap → upstream issue).

### 1.6 The file move

- Move `agents/assistant.md` → `src/yoker_assistant/agents/assistant.md`.
- The top-level `agents/` directory in the repo becomes empty — remove it
  (or leave a README pointing at the new location; pick remove for
  simplicity, the file's history is preserved in git).
- No `pyproject.toml` change needed — hatchling includes everything under
  `src/yoker_assistant/` recursively.

### 1.7 The loading code in `loop.py`

Replace:

```python
agent = Agent(
  agent_path="agents/assistant.md",
  context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"),
)
```

with a small loader that uses the same primitives the plugin loader uses:

```python
from yoker.agents import AgentDefinition, load_agent_definitions
from yoker.resources import find_package_subdirectory

_ASSISTANT_AGENT_NAME = "assistant"

def _load_assistant_definition() -> AgentDefinition:
  """Load the assistant agent definition from the installed package.

  Uses the same mechanism as yoker's plugin loader
  (find_package_subdirectory + load_agent_definitions) so the file ships
  inside the wheel and is located via importlib.resources at runtime —
  no relative filesystem path.
  """
  directory = find_package_subdirectory("yoker_assistant", "agents")
  if directory is None:
    raise RuntimeError(
      "yoker_assistant.agents/ directory not found in the installed package"
    )
  for defn in load_agent_definitions(directory, namespace="yoker_assistant"):
    if defn.simple_name == _ASSISTANT_AGENT_NAME:
      return defn
  raise RuntimeError(
    f"agent '{_ASSISTANT_AGENT_NAME}' not found in yoker_assistant.agents"
  )
```

Then in `run()`:

```python
agent = Agent(
  agent_definition=_load_assistant_definition(),
  context_manager=Persisted(SimpleContextManager(), session_id="yoker-assistant"),
)
```

Notes:
- `load_agent_definitions` (plural) is the correct entry point — it handles
  `Traversable` resource paths. The singular `load_agent_definition` coerces
  to `Path` and would NOT work on a `Traversable`.
- We filter by `simple_name == "assistant"` rather than picking the first
  definition, so the loader stays correct if more agent files are added
  later.
- The `namespace="yoker_assistant"` argument matches what the plugin loader
  passes, so the definition's namespaced name is `yoker_assistant:assistant`
  — consistent with how an external consumer would see it.

---

## 2. Connect/disconnect per loop iteration (theme 1)

### 2.1 The new loop skeleton

R4 §4.3's reconnect-on-failure guard is removed. The new loop bookends each
iteration with `connect()` / `disconnect()`. The `search` call has no
try/except around it — a connection drop surfaces as a normal iteration
failure, logged and skipped, and the next iteration starts fresh with a new
connect.

```python
pool = await get_pool()
imap = await pool.get_imap_client(_ACCOUNT_NAME)
smtp = await pool.get_smtp_client(_ACCOUNT_NAME)  # fire-and-forget per send

stop = asyncio.Event()
loop = asyncio.get_running_loop()
for sig in (SIGINT, SIGTERM):
  try:
    loop.add_signal_handler(sig, stop.set)
  except NotImplementedError:
    pass

# Validate credentials once before the loop starts, so a bad config
# fails fast instead of failing on the first iteration. This is the only
# "extra" connect outside the loop — a single connect/disconnect cycle
# that does no work. (See §2.2 for why this is kept.)
await imap.connect()
await imap.disconnect()

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
        logger.exception("per-message failure; leaving UNSEEN",
                         extra={"message_id": mid})
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

### 2.2 The startup credential check — keep or drop?

The R4 design called `await imap.connect()` once at startup "for fast-fail
on bad credentials." With per-iteration connect, that pre-check is no
longer strictly needed — the first iteration's `connect()` would surface
the same failure. Two options:

- **Keep the pre-check** (one extra connect/disconnect cycle that does no
  work): the user sees "bad credentials" within milliseconds of starting
  the assistant, before the first poll interval elapses. This is friendlier
  — a misconfigured assistant doesn't appear to "start fine" and then fail
  60 seconds later on the first poll.
- **Drop the pre-check**: simpler, fewer lines. The first iteration's
  `connect()` is the credential check. Failure surfaces on the first poll,
  which (with `_POLL_INTERVAL = 60`) is up to a minute after startup.

**Recommendation: drop the pre-check.** The owner's theme-1 instruction is
"simply connect and disconnect for every loop iteration" — adding a
one-shot pre-check outside the loop is exactly the kind of "make things
complicated" the owner is pushing back against. The first iteration is the
credential check. A 60-second delay before a credential failure is
acceptable for an assistant that polls every several minutes anyway. If
the owner wants the fast-fail back, it's a one-line addition.

If the owner prefers the pre-check, the snippet in §2.1 already shows it as
a comment-able two-line block — easy to keep or drop. Default: drop.

### 2.3 What is removed from R4

- The `await imap.connect()` fast-fail line at startup (per §2.2 — drop).
- The `try/except` around `imap.search` that did disconnect+reconnect+retry.
- The outer `try/finally` that wrapped the whole loop with a single
  `await imap.disconnect()` at process exit.

### 2.4 What is added

- A per-iteration `await imap.connect()` at the top of the `while` body.
- A per-iteration `finally: await imap.disconnect()` around the search +
  process block.

Net: the loop body is shorter and simpler than R4. The connection is open
only for the duration of one search+process cycle (typically seconds), then
closed before the multi-minute sleep. This matches the owner's observation
that "the typical interval will be several minutes anyway" — holding a
connection open across that sleep would guarantee a server-side timeout.

### 2.5 SMTP — unchanged

`SMTPClient` is fire-and-forget per `reply_email` call (it connects, sends,
disconnects internally). It is obtained once from the pool and held for the
loop's lifetime — no connect/disconnect bookending needed. This matches R4
and the simple-email-gw contract. No change.

---

## 3. Conversation-style logging (theme 4)

### 3.1 What the owner asked

> "We might want to add some logging to the assistant, so that the logging
> output resembles the conversation between user and agent."

The loop already has `logger = logging.getLogger(__name__)`. Add logs in
`_process_one` that frame the two turns of the conversation:

```python
async def _process_one(imap, smtp, agent, message_id):
  msg = await imap.fetch_message(message_id, _INBOX_FOLDER)
  handoff = build_message(msg)

  logger.info("=== Incoming message (user turn) ===")
  logger.info(handoff)

  reply_html = await agent.process(handoff)

  logger.info("=== Agent reply ===")
  logger.info(reply_html if reply_html.strip() else "(empty — no reply)")

  # ... rest of the branching unchanged ...
```

### 3.2 Design notes

- **Use `logger.info`, not `logger.debug`.** The owner wants the
  conversation visible in normal logging output. If it's at DEBUG, it
  doesn't show by default and the "resembles a conversation" goal isn't
  met. INFO is the right level for a conversation log.
- **No redaction.** The handoff already collapses CR/LF in headers via
  `build_message`. The body is passed verbatim. The assistant processes
  email from the owner, so the conversation is the owner's own content —
  no redaction needed. (If the assistant is ever pointed at a shared
  inbox, redaction can be revisited.)
- **No new dependencies, no structured-logging changes.** Plain
  `logger.info` calls with clear `===` separators. Keep it simple.
- **The empty-reply case is logged explicitly** as
  `"(empty — no reply)"` so the conversation log shows a turn happened
  even when the agent was silent — useful for diagnosing branch-2
  (transient problem) behavior.
- **The Initialize setup turn** (`await agent.process(_INITIALIZE_PROMPT)`
  in `run()`) is NOT logged as a conversation turn — it's a one-time
  session setup, not an incoming message. Leave it unlogged (or log at
  DEBUG). The owner's ask is about the user/agent conversation, which is
  the per-message loop, not the setup handshake.

### 3.3 Test impact

The existing `_process_one` tests mock the agent and assert branching
behavior. They do not currently assert anything about logging. Two options:

- **Do not add logging assertions.** Logging is observational, not
  behavioral. The branching tests already cover the four branches. Adding
  `caplog` assertions couples tests to log message text, which is brittle.
- **Add one smoke test** that asserts the two `===` separator lines appear
  in `caplog.records` for a happy-path call. This verifies the logging
  wiring without asserting exact text.

**Recommendation: add one smoke test.** It's one test, low coupling (just
matches the `=== Incoming` and `=== Agent reply` substrings), and catches
the case where someone accidentally removes the logs. Keep it tight.

---

## 4. Concrete change description for the python-developer

### 4.1 File move

- Move `/Users/xtof/Workspace/agentic/yoker-assistant/agents/assistant.md`
  to
  `/Users/xtof/Workspace/agentic/yoker-assistant/src/yoker_assistant/agents/assistant.md`.
- Remove the now-empty top-level `agents/` directory.
- No `pyproject.toml` change (hatchling includes everything under
  `src/yoker_assistant/` by default).

### 4.2 `src/yoker_assistant/__init__.py`

Update the manifest to declare the agents directory explicitly:

```python
__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)
```

This makes the manifest self-documenting and matches what the plugin loader
expects. (`agents_dir="agents"` is the default, but stating it explicitly
is clearer for future maintainers.)

### 4.3 `src/yoker_assistant/loop.py`

1. **Imports:** add
   `from yoker.agents import AgentDefinition, load_agent_definitions` and
   `from yoker.resources import find_package_subdirectory`. Remove the
   implicit reliance on `agent_path` (no import change — `Agent` is already
   imported).

2. **Add the `_load_assistant_definition` helper** (§1.7) near the other
   module-level helpers (`build_message`, `_contains_unsafe_html`).

3. **Add logging in `_process_one`** (§3.1): two `logger.info` calls framing
   the handoff and the reply.

4. **Rewrite the `run()` loop body** (§2.1):
   - Replace `Agent(agent_path="agents/assistant.md", ...)` with
     `Agent(agent_definition=_load_assistant_definition(), ...)`.
   - Remove the R4 reconnect-on-failure guard around `search`.
   - Move `await imap.connect()` to the top of each `while` iteration.
   - Add `finally: await imap.disconnect()` around the search+process
     block.
   - Remove the outer `try/finally` that wrapped the whole loop.
   - Drop the startup fast-fail `await imap.connect()` (per §2.2 — drop).
     If the owner asks to keep it, it's a two-line re-add at the top of
     `run()` before the `while`.

5. **Do NOT touch** `build_message`, `_contains_unsafe_html`, the four-way
   branching logic, the `{{NO_REPLY}}` sentinel, the Initialize turn, the
   `--once` flag, the signal handlers, `_POLL_INTERVAL`, or the graceful
   shutdown.

### 4.4 Tests (`tests/test_loop.py`)

1. **Remove `test_run_reconnects_after_search_failure`** (lines 302-322).
   The reconnect-on-failure guard no longer exists. This test is obsolete.

2. **Add `test_run_connects_and_disconnects_per_iteration`** — a new test
   that asserts the per-iteration connect/disconnect pattern:
   - Mock the pool to return an imap mock.
   - Run with `once=True` and an empty `search` result.
   - Assert `imap.connect.await_count >= 1` and
     `imap.disconnect.await_count >= 1` and that they alternate (connect
     before search, disconnect after).
   - For a stronger version: run with `once=True` and a non-empty search
     result (one message), and assert the connect/disconnect pair wraps
     the search+process. Keep it to one or two tests.

3. **Add `_load_assistant_definition` test coverage**:
   - The existing `test_run_proceeds_when_whitelist_enabled` and
     `test_run_continues_after_process_one_exception` mock `Agent` as
     `lambda **kwargs: agent`, so the `agent_definition=` kwarg flows
     through harmlessly. They should continue to pass without change.
   - Add one test that verifies `_load_assistant_definition` raises
     `RuntimeError` when the package's `agents/` directory is missing
     (mock `find_package_subdirectory` to return `None`). One tight test.
   - Add one test that verifies it returns the `AgentDefinition` with
     `simple_name == "assistant"` when the directory contains
     `assistant.md` (mock `find_package_subdirectory` to return a
     temporary directory with a minimal `assistant.md`). One test.
   - These two tests pin the packaging behavior the owner flagged.

4. **Add a logging smoke test** (§3.3): one test that runs `_process_one`
   with `caplog.at_level(logging.INFO)` and asserts `"=== Incoming"` and
   `"=== Agent reply"` appear in the captured records.

5. **Update `test_run_continues_after_process_one_exception`** if needed:
   the per-iteration `finally: disconnect` adds one more
   `imap.disconnect` call per iteration. The test currently asserts
   `imap.disconnect.assert_awaited_once()` — that assertion will need to
   change to `assert imap.disconnect.await_count >= 1` (or the test runs
   with `once=True` so there's exactly one iteration, in which case
   once-per-iteration still equals once). Verify and adjust.

### 4.5 `analysis/functional.md`

Update two sections:

- **§2.3 / §2.3.1 (agent seam):** note that the agent definition is now
  packaged at `src/yoker_assistant/agents/assistant.md` and loaded via
  `find_package_subdirectory` + `load_agent_definitions`. Note that the
  manifest declares `agents_dir="agents"` so external yoker consumers can
  reference the agent as `yoker_assistant:assistant`. Note the upstream
  issue filed against yoker for name-resolution on the bare `Agent`.

- **§loop (IMAP connection lifetime):** replace R4's "keep active +
  reconnect-on-failure" with "connect/disconnect per iteration." Note
  the rationale (poll interval is several minutes; an idle connection
  would timeout every time, so holding it open is wasted work). Note
  that a failed connect/search surfaces on the next iteration's connect.

- **§logging:** note the conversation-style INFO logs in `_process_one`.

~15-25 lines changed in `functional.md`.

### 4.6 Upstream yoker issue (out of this PR)

File an issue against `christophevg/yoker` with this content (paraphrased):

> **Title:** Allow a standalone `Agent` to resolve an agent definition by
> name from the plugin-agent registry
>
> **Use case:** A yoker-as-SDK consumer (`yoker-assistant`) packages its
> agent definition at `src/yoker_assistant/agents/assistant.md` and
> declares `agents_dir="agents"` in its `PluginManifest`. External yoker
> consumers can reference the agent as `yoker_assistant:assistant` via
> their `Session`'s registry. However, the consumer's own loop uses the
> bare `Agent` constructor (no `Session`), which has no agent registry —
> `_resolve_agent_definition` only accepts an explicit `AgentDefinition`
> or a filesystem path. The SDK explicitly states: "no registry available
> on a Session-agnostic Agent."
>
> **Request:** Either (a) add an `agent_name` parameter to `Agent.__init__`
> that resolves against plugin-loaded agents, or (b) expose a
> lighter-weight SDK entry point (e.g. `build_agent(name, ...)`) that
> wraps a one-agent Session without exposing the full Session lifecycle.
>
> **Workaround in the meantime:** the consumer loads the `AgentDefinition`
> from package resources via `find_package_subdirectory` +
> `load_agent_definitions` and passes it as `agent_definition=`. This
> packages the file correctly but does not give name-based resolution.

Reference the owner's round-2 PR comment for context.

---

## 5. Does this simplify the implementation?

Yes — net simplification, exactly as the owner's round-2 feedback directed:

- **Removes** the reconnect-on-failure guard (~6 lines, R4 §4.3).
- **Removes** the outer `try/finally` wrapping the whole loop.
- **Removes** `agent_path="agents/assistant.md"` (a relative filesystem
  path that breaks when the package is installed).
- **Adds** a per-iteration `connect()`/`disconnect()` pair (2 lines, clear
  intent).
- **Adds** a small `_load_assistant_definition` helper (~12 lines) that
  replaces the fragile path with package-resource loading.
- **Adds** two `logger.info` calls in `_process_one` (4 lines) for
  conversation-style logging.
- **Adds** `agents_dir="agents"` to the manifest (one line, self-
  documenting).

Net: the loop body shrinks, the connection lifetime is obvious, the agent
definition is packaged, and the logs show the conversation. The only
additive complexity is the agent-definition loader, which is the
minimum needed to satisfy the owner's packaging worry without a
scope-creeping switch to `Session`.

---

## 6. Concerns

1. **Per-iteration connect adds auth overhead.** Each iteration now does a
   TLS+login handshake (~2 RTTs) before `search`. At a several-minute
   poll interval, this is negligible — the owner's exact argument. At a
   very short poll interval (e.g. testing with `_POLL_INTERVAL = 1`), the
   overhead is more visible but acceptable for a dev mode. No action.

2. **A dropped connection mid-`_process_one` is not recovered in-iteration.**
   If `fetch_message` or `mark_message` raises because the connection
   dropped after `search`, the per-message `try/except` catches it, logs,
   and leaves the message UNSEEN. The iteration's `finally` disconnects
   (tolerating failure), and the next iteration connects fresh. No
   message is lost; it retries. This matches R4's "leave UNSEEN on
   failure" semantics, just with a cleaner recovery (new connection
   next iteration rather than an in-line reconnect).

3. **The `_load_assistant_definition` helper duplicates the plugin
   loader's logic.** It uses the same primitives
   (`find_package_subdirectory` + `load_agent_definitions`) but filters
   for one specific agent. This is the smallest correct loader for the
   bare-`Agent` path. If the upstream yoker issue (Option C) is resolved,
   this helper can be replaced with `Agent(agent_name="yoker_assistant:assistant")`
   and deleted. The helper is a bridge, not a permanent fixture.

4. **Dropping the startup fast-fail means a credential error surfaces on
   the first poll, up to `_POLL_INTERVAL` seconds after startup.** Per
   §2.2 this is acceptable. If the owner wants the fast-fail back, it's
   a two-line re-add at the top of `run()` before the `while` loop. The
   default here is to drop it (simplicity per the owner's theme-1
   instruction); the owner can override.

5. **The upstream yoker issue is a dependency for the "reference by name"
   half of theme 2.** This PR ships the packaging fix (the half that's
   achievable today) and files the issue for the name-resolution half.
   The owner explicitly authorized this split ("if not possible, raise an
   issue"). The PR description should reference the issue number.

6. **Test count for the packaging helper.** Two new tests for
   `_load_assistant_definition` (missing-dir raises; present-dir returns
   the assistant definition). One new test for per-iteration
   connect/disconnect. One new logging smoke test. Net: -1 (removed
   reconnect test) + 4 = +3 tests. Tight and behavior-focused.

---

## 7. Summary of changes to the implementation plan (R4 → R5)

1. **Move `agents/assistant.md` → `src/yoker_assistant/agents/assistant.md`.**
   Remove the empty top-level `agents/` directory. No pyproject change.

2. **Manifest:** declare `agents_dir="agents"` explicitly in
   `__YOKER_MANIFEST__` so external yoker consumers can reference the
   agent as `yoker_assistant:assistant`.

3. **Loop:** replace `Agent(agent_path="agents/assistant.md", ...)` with
   `Agent(agent_definition=_load_assistant_definition(), ...)` where the
   helper loads from package resources via
   `find_package_subdirectory` + `load_agent_definitions`.

4. **Loop:** remove R4's reconnect-on-failure guard. Move `connect()` to
   the top of each `while` iteration and `disconnect()` to a per-
   iteration `finally`. Drop the startup fast-fail connect (default;
   re-add if the owner wants it).

5. **Loop:** add conversation-style `logger.info` calls in `_process_one`
   — one framing the incoming handoff, one framing the agent's reply.

6. **Tests:** remove the reconnect-on-failure test; add a per-iteration
   connect/disconnect test; add two tests for `_load_assistant_definition`
   (missing dir, present dir); add a logging smoke test.

7. **`functional.md`:** update the agent-seam section (packaged
   definition, manifest `agents_dir`, upstream issue), the loop section
   (per-iteration connect/disconnect), and add a logging note.

8. **Upstream issue:** file a yoker issue requesting name-based agent
   resolution on the bare `Agent` (or a lighter-weight Session-less entry
   point). Reference this PR and the owner's comment.

This revision is ready to be posted as a PR comment on PR #7 for owner
approval. No implementation is started until the owner confirms —
specifically, the owner should confirm:
- (a) drop the startup fast-fail connect (§2.2 default), or keep it;
- (b) ship the packaging fix now + file the upstream issue for name
  resolution (§1.4), or escalate to a Session-based switch in this PR
  (Option A — larger scope).