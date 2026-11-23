# PACKAGE.md

> AI-optimized package documentation for `yoker-assistant`.

## What This Package Provides

A Yoker SDK showcase: a personal assistant that communicates by email.
Python owns the email loop (poll IMAP, fetch, reply, archive) and calls
Yoker as a library for the reasoning half. The package is also a Yoker
plugin provider (dual-mode): it exposes a custom `md_to_html` tool via
`__YOKER_MANIFEST__` for any Yoker consumer to load.

The core design principle: **Python owns the loop; the agent owns the
reasoning.** No agent cost is spent on structured work; no Python is
spent on reasoning. The two halves do not bleed.

## Installation

```bash
pip install yoker-assistant
# or
uv add yoker-assistant
```

Requires `yoker>=0.13`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2`, and
Python 3.11+.

## Plugin Manifest

```python
from yoker_assistant import __YOKER_MANIFEST__

# PluginManifest(
#   tools=[md_to_html],
#   agents_dir="agents",
# )
```

## Loading as a Yoker Plugin

### Running the email loop (automatic)

When running yoker-assistant's own email loop, plugin registration is
automatic: `loop.py` injects `config.plugins.enabled = True` and adds
`yoker_assistant` and `pkgq` to `config.plugins.packages` at startup.
No `[plugins]` config is needed in `~/.yoker.toml`. On first run, yoker's
standard trust prompt asks you to confirm loading each plugin. After
confirmation the plugin is session-trusted. For permanent trust across
sessions, optionally add `[plugins.trusted]` to `~/.yoker.toml`.

### Via `~/.yoker.toml` (external consumers)

If you want to use `yoker_assistant:md_to_html` as a plugin in your own
yoker project (not running the email loop), add manual registration:

```toml
[plugins]
enabled = true
packages = ["yoker_assistant"]

[plugins.trusted]
yoker_assistant = true
```

Adding `[plugins.trusted] yoker_assistant = true` skips yoker's
interactive trust prompt on subsequent runs. Without it, yoker asks
"Load this plugin? [y/N]" on first run. Pin the installed version and
verify the source — once trusted, all tool code runs with no per-call
gate.

### Via CLI

```bash
yoker --with yoker_assistant --agent yoker_assistant:assistant
```

## Provided Tools

| Tool | Namespace | Description |
|------|-----------|-------------|
| `md_to_html` | `yoker_assistant:md_to_html` | Convert markdown to an HTML body fragment (headers, bold, tables, lists, hr, paragraphs). Cell content is HTML-escaped. |

## Provided Agents

| Agent | Namespace | Description |
|-------|-----------|-------------|
| `assistant` | `yoker_assistant:assistant` | Personal assistant: categorizes email, acts with bounded tools, composes HTML reply, maintains PERSONAL.md in git |

## CLI Entry Point

```bash
yoker-assistant                # long-running email loop
yoker-assistant --once         # one poll iteration, then exit (demo/test)
```

Registered as `[project.scripts]` in `pyproject.toml`, pointing to
`yoker_assistant.__main__:main`. Parses `--once` and calls
`asyncio.run(run(once=...))`.

## Public API Surface

| Symbol | Description |
|--------|-------------|
| `yoker_assistant.__YOKER_MANIFEST__` | Plugin manifest (tools, agents_dir) |
| `yoker_assistant.__version__` | Package version string |
| `yoker_assistant.loop.run(once=False)` | Main async loop: poll, handoff, reply, archive |
| `yoker_assistant.loop.build_message(email_message)` | Pure function: builds handoff payload from raw message dict |
| `yoker_assistant.tools.md_to_html(markdown)` | Custom tool: markdown → HTML body fragment |

The package is import-safe: importing it does not trigger Agent
construction, email logic, or loop logic.

## Configuration

Three configuration concerns, kept strictly separate:

### `.env` — email account (simple-email-gw)

```
EMAIL_IMAP_HOST=imap.example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_USERNAME=assistant@example.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com
```

`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is the **primary reply-safety
boundary**. The env var name is `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`
(NOT `EMAIL_RECIPIENT_ADDRESSES`); the wrong name silently disables
the whitelist.

### `~/.yoker.toml` — Yoker runtime

Backend, model, and permissions. Created by `uv run yoker init`. Plugin
`enabled` and `packages` are auto-injected when running the email loop
(in `loop.py`); trust is confirmed interactively on first run.
External consumers need manual `[plugins]` config — see "Loading as a
Yoker Plugin" above. See `yoker.toml.example` for the backend config
reference shape.

### `PERSONAL.md` — assistant personalization

Lives in the working directory. The agent reads it at session startup
and writes learned behaviours to it. On first run, the agent bootstraps
it interactively over email.

## How the Loop Works

1. **Poll** — connect to IMAP, search `INBOX` for `UNSEEN`.
2. **Fetch** — for each unseen message, fetch the full content.
3. **Handoff** — build a From/Subject/Date/body string and pass it to
   `session.agent.process(message)`.
4. **Branch** — four ways on the reply:
   - `{{NO_REPLY}}` sentinel → mark read + archive (intentional silence)
   - empty/whitespace → leave `UNSEEN` (transient problem, retry)
   - unsafe HTML → mark read + send plain-text notice (guard failure)
   - valid HTML → send reply + mark read + archive
5. **Sleep** — if no messages, sleep 60s and repeat.

## Further Documentation

Full documentation lives in `docs/` and is published to ReadTheDocs.

- [Tutorial](docs/tutorial.md) — how this package was built
- [Architecture](docs/architecture.md) — seam-by-seam reference
- [Security](docs/security.md) — trust model and review process
- [Configuration](docs/configuration.md) — full config reference
- [API](docs/api.md) — public API surface

## License

MIT — see [LICENSE](LICENSE).