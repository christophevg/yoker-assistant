# Installation

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- A yoker backend: either a local [Ollama](https://ollama.com) install or a
  cloud LLM provider API key (OpenAI, Anthropic, Google Gemini, or any of the
  100+ providers yoker supports via LiteLLM)
- An IMAP/SMTP mailbox the assistant can poll (Gmail with an app password
  works; any provider that exposes standard IMAP/SMTP works)

## Install the package

```bash
git clone https://github.com/christophevg/yoker-assistant.git
cd yoker-assistant
make env-dev        # uv sync --all-extras (runtime + dev + docs)
make test           # sanity check
```

## Backend prerequisite

yoker needs a configured backend before the assistant can reason. The
backend (provider, base URL, API key, model) lives in `~/.yoker.toml`. If you
do not already have one, run yoker's bootstrap wizard once:

```bash
uv run yoker init    # writes ~/.yoker.toml with a backend of your choice
```

The `yoker.toml.example` in this repo shows a local Ollama shape (no API key
required) and a cloud shape (API key). Either works; pick one and put it in
`~/.yoker.toml`, not in the repo.

## Plugin registration — automatic

yoker-assistant is a yoker plugin provider, but you do **not** need to add
plugin registration to your `~/.yoker.toml`. The package injects plugin
configuration programmatically at startup (in `loop.py`):

- `plugins.enabled = True`
- `yoker_assistant` and `pkgq` added to `plugins.packages`

On first run, yoker's standard trust prompt asks you to confirm loading
each plugin ("Load this plugin? [y/N]"). After confirmation the plugin is
session-trusted. For permanent trust across sessions, you can optionally
add `[plugins.trusted] yoker_assistant = true` (and `pkgq = true`) to
your `~/.yoker.toml` — this skips the interactive prompt on subsequent
runs.

See [Security](security.md) for the blast-radius implication and
version-pinning advice.

> **External consumers:** if you want to use `yoker_assistant:md_to_html`
> as a plugin in your own yoker project (not running the email loop), you
> still need manual plugin registration. See [PACKAGE.md](../PACKAGE.md)
> for those lines. The automatic injection only applies when running
> yoker-assistant's own email loop.

## Email account (`.env`)

Copy `.env.example` to `.env` and fill in the mailbox credentials the assistant
polls:

```
EMAIL_IMAP_HOST=imap.example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_USERNAME=assistant@example.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com
```

`.env` is gitignored; `~/.yoker.toml` lives in your home directory and never
enters the repo. Neither file is ever committed. See
[Security](security.md) for why.

`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is the **primary reply-safety
boundary**: the assistant may only reply to addresses in this whitelist. Set
it to the single owner address; leaving it broad allows the agent to reply to
arbitrary senders. See [Security](security.md).

## Verify the install

```bash
python -m yoker_assistant --once    # one poll iteration, then exit
```

On an empty inbox the assistant connects, searches `UNSEEN`, finds nothing,
logs nothing at WARN level, and exits cleanly. On a seeded unread email it
hands the email to the agent, gets a reply, sends it, and archives the
original. See [Quickstart](quickstart.md) for what to watch for in the logs.