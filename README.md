# yoker-assistant

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)][python]
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)][uv]
[![CI](https://img.shields.io/github/actions/workflow/status/christophevg/yoker-assistant/ci.yml.svg)][ci]
[![License](https://img.shields.io/github/license/christophevg/yoker-assistant.svg)][license]
[![Agentic](https://img.shields.io/badge/workflow-agentic-blueviolet?style=flat-square)](https://christophe.vg/about/Agentic-Workflow)

> A personal assistant that communicates by email, built on yoker-as-SDK.

This is a yoker 1.0 pet-store showcase package. Python owns the email loop
(poll, fetch, reply, archive) and calls yoker as a library for the reasoning
half. The package is also a yoker plugin provider (dual-mode): it exposes its
own tools via `__YOKER_MANIFEST__` for any yoker consumer to load.

## Status

First pass implemented (P1–P3). The loop, the agent seam, the mailbox seam,
the bounded tool set, the tests, and `SECURITY.md` have landed. See
[`TODO.md`](TODO.md) for the remaining backlog (HTML styling polish,
attachment handling, batch processing, `make run-demo`, Phase B bounded
tools).

## Quick start

```bash
make env-dev                              # install all dependencies (PyPI)
make test                                 # run the test suite
python -m yoker_assistant --once          # one poll iteration, then exit
```

`--once` is the demo/test mode: one poll iteration and exit. Drop `--once`
for the long-running mode (polls every 60 seconds until `SIGINT`/`SIGTERM`).

A yoker backend is a prerequisite — either a local
[Ollama](https://ollama.com) install or a cloud LLM provider API key. If
you do not already have one, run `uv run yoker init` once to write
`~/.yoker.toml` with a backend of your choice.

## Configuration

Two config files are required at runtime; **neither is committed** (`.env`
is gitignored; `~/.yoker.toml` lives in the user home and never enters the
repo). Reference templates live in this repo.

### `~/.yoker.toml` — yoker runtime + plugin registration

The required lines (see [`yoker.toml.example`](yoker.toml.example) for the
full reference):

```toml
[plugins]
enabled = true
packages = ["yoker_assistant", "pkgq"]

[plugins.trusted]
yoker_assistant = true
pkgq = true

[skills]
directories = ["./skills"]
```

Self-trust (`[plugins.trusted] yoker_assistant = true; pkgq = true`) is
**required** for unattended operation: with no TTY to prompt, yoker's trust
gate rejects untrusted plugins in non-interactive mode. Backend and model
settings (provider, `base_url`, `api_key`, `model`) also live in
`~/.yoker.toml`; `yoker.toml.example` shows a local Ollama shape (no key)
and a cloud shape (API key). See the [Configuration page](https://yoker-assistant.readthedocs.io/en/latest/configuration.html)
for the full reference.

### `.env` — email account (simple-email-gw)

Copy [`.env.example`](.env.example) to `.env` and fill in the mailbox
credentials the assistant polls:

```
EMAIL_IMAP_HOST=imap.example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_USERNAME=assistant@example.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com
```

`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is the **primary reply-safety
boundary**: the assistant may only reply to addresses in this whitelist.
Set it to the single owner address; leaving it broad allows the agent to
reply to arbitrary senders. This is a `simple-email-gw` config concern, not
package code. The env var name is `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`
(NOT `EMAIL_RECIPIENT_ADDRESSES`); the wrong name silently disables the
whitelist. See [Security configuration](#security-configuration) below.

## Security configuration

Marking `[plugins.trusted] yoker_assistant = true` admits ALL tool code
from this package as trusted with no per-call gate — pin the installed
version (`uv pip install yoker-assistant==<version>`) and verify the
source. The blast radius includes `yoker:git` (full git — read, commit,
push). Adding a new tool to `__YOKER_MANIFEST__`, or making a
capability-changing edit to an existing tool, is a security-relevant
change; see [`SECURITY.md`](SECURITY.md) for the review process
contributors must follow before such a change.

`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is the primary reply-safety boundary
(see [.env](#env--email-account-simple-email-gw) above). `~/.yoker.toml`
and `.env` are NEVER committed — `.env` is gitignored; a user who
snapshots `~/.yoker.toml` into a repo must gitignore it too.
[`make pre-publish`](Makefile) guards against local-path dependencies
leaking into published metadata. See the [Security page](https://yoker-assistant.readthedocs.io/en/latest/security.html)
for the full discussion.

## Running it

```bash
python -m yoker_assistant              # long-running loop
python -m yoker_assistant --once        # one iteration, then exit (demo/test)
```

The long-running mode polls every 60 seconds. `SIGINT` (Ctrl-C) and
`SIGTERM` both trigger a clean exit: the in-flight message finishes, the
IMAP connection disconnects, and the process exits 0. There is no forced
kill mid-iteration.

The first time the assistant runs, `PERSONAL.md` does not exist in the
working directory. The agent detects this on its `Initialize` turn and
enters a bootstrap flow: it replies with a welcome message and a set of
questions about you (name, preferred address, project context, tone,
goals); you answer by replying over email; the agent iterates with you
until it has enough to write the initial `PERSONAL.md` (and optionally
commits + pushes it via `yoker:git`). After bootstrap, every subsequent
email is the next user message in the SAME session.

## Documentation

Full documentation lives in `docs/` and is published to ReadTheDocs:

**https://yoker-assistant.readthedocs.io/**

The [Tutorial](https://yoker-assistant.readthedocs.io/en/latest/tutorial.html)
tells the build story end-to-end — why this package exists (c3 heritage,
the email-loop-into-Python insight), the two halves (Python loop vs agent
reasoning), the seams (yoker SDK seam + simple-email-gw seam), the handoff
contract (payload format + four-way branch), the bounded tool set and the
safety model, the c3 → yoker-assistant porting map, the persistent-session
architecture, the custom md→html tool story, the dual-mode architecture,
the git commit/push demo beat, recipient safety, and what is out of scope
for the first pass.

Supporting pages: [Installation](https://yoker-assistant.readthedocs.io/en/latest/installation.html),
[Quickstart](https://yoker-assistant.readthedocs.io/en/latest/quickstart.html),
[Architecture](https://yoker-assistant.readthedocs.io/en/latest/architecture.html),
[Porting Map](https://yoker-assistant.readthedocs.io/en/latest/porting-map.html),
[Security](https://yoker-assistant.readthedocs.io/en/latest/security.html),
[Configuration](https://yoker-assistant.readthedocs.io/en/latest/configuration.html),
[API](https://yoker-assistant.readthedocs.io/en/latest/api.html),
[Changelog](https://yoker-assistant.readthedocs.io/en/latest/changelog.html).

## License

[MIT](LICENSE)

[python]: https://python.org/
[uv]: https://docs.astral.sh/uv/
[ci]: https://github.com/christophevg/yoker-assistant/actions
[license]: https://github.com/christophevg/yoker-assistant/blob/master/LICENSE