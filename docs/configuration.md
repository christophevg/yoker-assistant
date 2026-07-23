# Configuration

yoker-assistant has three configuration concerns, kept strictly separate
(no bleeding): the email account (`simple-email-gw`), yoker runtime
(`~/.yoker.toml`), and assistant personalization (`PERSONAL.md`). None of
these is committed to the repo; reference templates are shipped
(`.env.example`, `yoker.toml.example`) for documentation only.

## Email account — `.env`

The loop does NOT parse `EMAIL_*` env vars itself. It obtains IMAP/SMTP
clients from the SDK's `ConnectionPool` via the literal account name
`"default"` (the SDK's `ServerConfig.account_name` default). The env vars
are read inside the SDK's `ServerConfig` — yoker-assistant's only account
knowledge is the name `"default"`.

| Env var | Purpose |
|---|---|
| `EMAIL_IMAP_HOST` | IMAP server hostname |
| `EMAIL_SMTP_HOST` | SMTP server hostname |
| `EMAIL_USERNAME` | Mailbox username (full email address for most providers) |
| `EMAIL_PASSWORD` | Mailbox password (use an app password for Gmail and similar) |
| `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` | **Primary reply-safety boundary** — the single owner address the assistant may reply to. Silently disabled if unset or wrong (the env var name is `EMAIL_RECIPIENT_WHITELIST_ADDRESSES`, NOT `EMAIL_RECIPIENT_ADDRESSES`). See [Security](security.md). |

For multi-account setups, `EMAIL_ACCOUNTS_JSON` is also supported by
`simple-email-gw`; yoker-assistant passes the account name `"default"` to
the pool and the SDK resolves the rest.

The `.env` file is gitignored at the repo root. Copy `.env.example` to
`.env` and fill in the mailbox credentials the assistant polls.

## yoker runtime — `~/.yoker.toml`

The backend, model, and permissions live in the user's `~/.yoker.toml`,
created by yoker's bootstrap wizard (`uv run yoker init`). The
`[plugins]` / `[plugins.trusted]` lines also live there — that is the
correct location for plugin registration because yoker resolves project
config from `~/.yoker.toml` (user) and `./yoker.toml` (cwd), NOT from the
package install location. A repo-level `yoker.toml` is only read during
local dev (when the cwd is the checkout) and would clobber the user's
backend config there. The package provides a `yoker.toml.example` as
documentation only — reference for the lines the user must add to their
`~/.yoker.toml`, not a checked-in active config.

### Required lines in `~/.yoker.toml`

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

The `[plugins.trusted]` block is required for unattended operation: with
no TTY to prompt, yoker's trust gate rejects untrusted plugins in
non-interactive mode. See [Security](security.md) for the blast-radius
implication and the version-pinning advice.

### Backend and model

Backend and model settings (provider, base_url, api_key, model,
parameters) live in `~/.yoker.toml`. `yoker.toml.example` shows a local
Ollama shape (no key) and a cloud shape (API key). Either works; pick one
and put it in `~/.yoker.toml`. yoker needs a configured backend before the
assistant can reason — `uv run yoker init` writes the initial config if
you do not already have one.

### Permissions

Permissions (`filesystem_paths`, `network_access`, tool enablement) live
in `~/.yoker.toml`. The default permissions from `uv run yoker init` are
the starting point; tighten as needed for your deployment. The agent's
tools are bounded (no shell), but the filesystem and network reach of
`yoker:read`/`yoker:write`/`yoker:webfetch`/`yoker:git` is governed by
these permissions.

### Skills directory

`[skills] directories = ["./skills"]` lets yoker load any skills you drop
into `./skills` in the working directory. The first pass does not ship
skills (the heritage `pa-*` skills were reworked into the agent definition
or dropped — see [Porting Map](porting-map.md)); the setting is in the
reference config so that future skills load without a config change.

## Assistant personalization — `PERSONAL.md`

`PERSONAL.md` is the agent's persistent identity + learned-behaviours file.
It lives in the working directory (the directory the assistant is started
in), NOT in `~/.yoker.toml` or `.env`. The agent reads it at session
startup via `yoker:read` on the `Initialize` turn and may write to it
(adding learned behaviours) via `yoker:update`/`yoker:write`. The agent
also commits and pushes it via `yoker:git`.

`PERSONAL.md` structure:

```markdown
# Personal Configuration

## Hello
- User name and preferred address
- Website and project context

## <Agent Name>
- Your identity and how you should present yourself

## When Sending Emails
- Tone and style guidelines

## Personal Goals
- What the user wants to achieve

## Behaviors
- Learned behaviors (self-learning section)
  - Behavioral instructions go here (not in memory files)
  - Email formatting, workflow preferences, etc.
```

On the first run, `PERSONAL.md` does not exist; the agent detects this on
the `Initialize` turn and enters its bootstrap flow (it replies with a
welcome message and a set of questions for the owner; the owner answers by
replying over email; the agent iterates until it has enough to write the
initial `PERSONAL.md`). See [Quickstart](quickstart.md) for the bootstrap
flow walkthrough.

## Loop parameters

Loop parameters are module-level constants in `src/yoker_assistant/loop.py`
in the first pass (no env-var override):

| Constant | Default | Purpose |
|---|---|---|
| `_POLL_INTERVAL` | `60` (seconds) | Sleep between polls when inbox is empty |
| `_INBOX_FOLDER` | `"INBOX"` | IMAP folder to search for `UNSEEN` |
| `_ARCHIVE_FOLDER` | `"Archive"` | IMAP folder to move processed messages to |
| `_ACCOUNT_NAME` | `"default"` | `simple-email-gw` account name (resolved by the SDK's `ServerConfig`) |
| `_INITIALIZE_PROMPT` | `"Initialize"` | The one-time session-setup turn prompt |

These are not user-configurable in the first pass; they are documented for
transparency.