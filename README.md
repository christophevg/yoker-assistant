# yoker-assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)][python]
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)][uv]
[![Yoker](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/christophevg/yoker/master/media/badge/v0.json)][yoker]
[![Docs](https://img.shields.io/readthedocs/yoker-assistant)][docs]
[![License](https://img.shields.io/github/license/christophevg/yoker-assistant.svg)][license]
[![Agentic](https://img.shields.io/badge/workflow-agentic-blueviolet?style=flat-square)][agentic]

> A personal assistant that communicates by email, built on yoker-as-SDK.

This is a Yoker showcase package. It demonstrates the **yoker-as-SDK**
mode: Python owns the process and calls Yoker as a library for the
reasoning half. The package is also a Yoker plugin provider (dual-mode):
it exposes its own tools via `__YOKER_MANIFEST__` for any Yoker consumer
to load.

**Full documentation** is published at
**[yoker-assistant.readthedocs.io](https://yoker-assistant.readthedocs.io)** —
including a [tutorial](https://yoker-assistant.readthedocs.io/en/latest/tutorial.html)
that tells the build story end-to-end, a [quickstart](https://yoker-assistant.readthedocs.io/en/latest/quickstart.html)
with a worked example, and a per-page [reference](https://yoker-assistant.readthedocs.io/en/latest/architecture.html)
for architecture, security, and configuration.

## Status

Initial release candidate. The loop, the agent seam, the mailbox seam,
the bounded tool set, the custom md→html tool, the tests, and
`SECURITY.md` are all in place. All quality gates green. See
[`TODO.md`](TODO.md) for the remaining backlog (HTML styling polish,
attachment handling, batch processing, `make run-demo`).

## What It Does

The assistant is a **personal assistant that communicates by email**.
You email it; it reasons about the email, acts on your behalf using a
curated set of safe tools, and emails back. The inbox is the entire UI —
no TUI, no CLI prompts, no web.

### How it works

1. **Python owns the email loop.** It polls an IMAP inbox for `UNSEEN`
   messages, fetches each one, and hands it to the agent as a simple
   From/Subject/Date/body payload.
2. **The agent reasons.** It categorizes the email, decides what actions
   to take, uses its bounded tools (read, write, web search, git, etc.),
   and composes a reply in markdown.
3. **The agent converts the reply to HTML** via a custom `md_to_html`
   tool (the showcase's "create your own bounded tool" example).
4. **Python sends the reply.** It emails the HTML verbatim, marks the
   original read, and archives it.

### The bootstrap flow

On first run, `PERSONAL.md` does not exist. The agent detects this and
replies with a welcome message and questions about you (name, preferred
address, project context, tone, goals). You answer by replying over
email. The agent iterates with you until it has enough to write the
initial `PERSONAL.md` — and optionally commits and pushes it via
`yoker:git`. After bootstrap, every subsequent email is the next message
in the same session.

### The git demo beat

The visible "acts on behalf of the owner" moment: the agent
autonomously maintains its own `PERSONAL.md` learned-behaviours file in
version control. When you email a preference ("from now on, always CC me
on deploy-related replies"), the agent updates `PERSONAL.md`, commits,
and pushes — all via bounded git tools, not a shell.

## Quick Start

```bash
make env-dev                              # install all dependencies
make test                                 # run the test suite
python -m yoker_assistant --once          # one poll iteration, then exit
```

`--once` is the demo/test mode: one poll iteration and exit. Drop `--once`
for the long-running mode (polls every 60 seconds until `SIGINT`/`SIGTERM`).

A Yoker backend is a prerequisite — either a local
[Ollama](https://ollama.com) install or a cloud LLM provider API key. If
you do not already have one, run `uv run yoker init` once to write
`~/.yoker.toml` with a backend of your choice.

See [Installation](https://yoker-assistant.readthedocs.io/en/latest/installation.html)
for the full setup guide, including email account configuration. Plugin
registration is automatic — the package self-injects it at startup.

## Architecture

This package demonstrates **yoker-as-SDK**: Python owns the email loop
(poll, fetch, reply, archive) and calls Yoker as a library for the
reasoning half. The package is also a Yoker plugin provider (dual-mode):
it exposes its own `md_to_html` tool via `__YOKER_MANIFEST__` for any
Yoker consumer to load — including itself.

The sister project
[`yoker-writing-assistant`](https://github.com/christophevg/yoker-writing-assistant)
demonstrates the complementary mode — **yoker-as-runtime** — where Yoker
is the entry point and the package runs under it as a plugin.

Both projects share a common quality bar documented in
[STANDARDS.md](STANDARDS.md).

## Documentation

Full documentation lives in `docs/` and is published to ReadTheDocs:

**https://yoker-assistant.readthedocs.io**

The [Tutorial](https://yoker-assistant.readthedocs.io/en/latest/tutorial.html)
tells the build story end-to-end — why this package exists, the two halves
(Python loop vs agent reasoning), the seams (Yoker SDK seam +
simple-email-gw seam), the handoff contract (payload format + four-way
branch), the bounded tool set and the safety model, the persistent-session
architecture, the custom md→html tool story, the dual-mode architecture,
the git commit/push demo beat, recipient safety, and what is out of scope.

Supporting pages: [Installation](https://yoker-assistant.readthedocs.io/en/latest/installation.html),
[Quickstart](https://yoker-assistant.readthedocs.io/en/latest/quickstart.html),
[Architecture](https://yoker-assistant.readthedocs.io/en/latest/architecture.html),
[Security](https://yoker-assistant.readthedocs.io/en/latest/security.html),
[Configuration](https://yoker-assistant.readthedocs.io/en/latest/configuration.html),
[API](https://yoker-assistant.readthedocs.io/en/latest/api.html),
[Changelog](https://yoker-assistant.readthedocs.io/en/latest/changelog.html).

The [AGENTS.md](AGENTS.md) file provides the project guide for agents
working on this codebase. [PACKAGE.md](PACKAGE.md) provides AI-optimized
package documentation for consumers.

## License

[MIT](LICENSE)

[python]: https://python.org/
[uv]: https://docs.astral.sh/uv/
[yoker]: https://yoker.dev
[docs]: https://yoker-assistant.readthedocs.io
[license]: https://github.com/christophevg/yoker-assistant/blob/master/LICENSE
[agentic]: https://christophe.vg/about/Agentic-Workflow
