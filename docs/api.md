# API Reference

yoker-assistant has a thin public API surface: a single async loop entry
point, a manifest that exposes one tool, and a CLI. Most users interact
with the package via the CLI (`python -m yoker_assistant`) or as a yoker
plugin (loading `yoker_assistant:md_to_html` from their own yoker
consumer). The functions below are the programmatic surface.

## `yoker_assistant.loop.run(once=False)`

The main async loop. Constructs the `Session` once, runs the one-time
`Initialize` turn, polls IMAP for `UNSEEN` messages, hands each to the
agent via `session.agent.process`, and branches on the reply (see
[Architecture](architecture.md) for the four-way branch).

```{eval-rst}
.. autofunction:: yoker_assistant.loop.run
```

## `yoker_assistant.loop.build_message(email_message)`

Pure function that builds the handoff payload (From/Subject/Date + body)
from a raw `simple_email_gw` message dict. No I/O. CR/LF is collapsed in
header values to prevent handoff-format injection; the body is passed
through verbatim.

```{eval-rst}
.. autofunction:: yoker_assistant.loop.build_message
```

## `yoker_assistant.tools.md_to_html(markdown)`

The custom yoker tool. Converts a markdown string to an HTML body fragment
(no `<html>` wrapper). Handles headers, bold, tables, lists, horizontal
rules, and paragraphs. Cell content is HTML-escaped before wrapping so
the agent cannot inject arbitrary HTML through the table converter.

```{eval-rst}
.. autofunction:: yoker_assistant.tools.md_to_html
```

## `yoker_assistant.__YOKER_MANIFEST__`

The yoker plugin manifest. Exposed at the package top level so yoker's
plugin loader discovers it. Declares the `md_to_html` tool and the
`agents/` directory.

```python
__YOKER_MANIFEST__ = PluginManifest(
  tools=[md_to_html],
  agents_dir="agents",
)
```

The `__init__.py` is import-safe: importing it does NOT trigger any Agent
construction, email logic, or loop logic. The manifest only declares tool
functions — no side effects at import time.

## CLI

The package is started as a module or console script:

```bash
python -m yoker_assistant              # long-running loop
python -m yoker_assistant --once       # one iteration, then exit (demo/test)
# or, after install:
yoker-assistant
yoker-assistant --once
```

`--once` processes a single poll iteration and exits. It is the demo/test
mode: on an empty inbox it connects, searches, finds nothing, and exits
cleanly; on a seeded unread email it processes the email end-to-end and
exits. Drop `--once` for the long-running mode (polls every 60 seconds
until `SIGINT`/`SIGTERM`).

## Configuration

See [Configuration](configuration.md) for the full `~/.yoker.toml` and
`.env` reference. See [Security](security.md) for the trust model and
the manifest-addition review process.