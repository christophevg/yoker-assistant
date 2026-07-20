# yoker-assistant

A personal assistant that communicates by email, built on yoker-as-SDK.

This is a yoker 1.0 pet-store showcase package. Python owns the email loop
(poll, fetch, reply, archive) and calls yoker as a library for the reasoning
half. The package is also a yoker plugin provider (dual-mode): it exposes its
own tools via `__YOKER_MANIFEST__` for any yoker consumer to load.

## Status

Skeleton (P1-001). The loop, agent seam, mailbox seam, and tools land in
subsequent tasks. See `TODO.md` for the build plan and `STANDARDS.md` for the
quality bar.

## Quick start

```bash
make env-dev        # install all dependencies (PyPI)
make test           # run the test suite
python -m yoker_assistant   # entry point stub (exits cleanly until wired)
```

## Configuration

Two config files are required at runtime; **neither is committed** (`.env`
is gitignored; `~/.yoker.toml` lives in the user home and never enters the
repo). Reference templates live in this repo.

### `~/.yoker.toml` — yoker runtime

yoker resolves project config from `~/.yoker.toml` (user) and `./yoker.toml`
(cwd), **not** from the package install location. A repo-level `./yoker.toml`
is only read during local dev and would clobber the user's backend/model
config — so plugin registration belongs in `~/.yoker.toml`. The required
lines (see `yoker.toml.example` for the full reference):

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
gate rejects untrusted plugins in non-interactive mode. The blast radius is
that all tool code from a trusted package runs with no per-call gate — pin
the installed versions and verify the source
(`uv pip install yoker-assistant==<version>`).

Backend and model settings (provider, base_url, api_key, model) also live
in `~/.yoker.toml`; `yoker.toml.example` shows a local Ollama shape (no key).
A full tutorial is in P4-001.

### `.env` — email account (simple-email-gw)

Copy `.env.example` to `.env` and fill in the mailbox credentials the
assistant polls:

```
EMAIL_IMAP_HOST=imap.example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_USERNAME=assistant@example.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_RECIPIENT_ADDRESSES=owner@example.com
```

`EMAIL_RECIPIENT_ADDRESSES` is the **primary reply-safety boundary**: the
assistant may only reply to addresses in this whitelist. Set it to the
single owner address; leaving it broad allows the agent to reply to
arbitrary senders. This is a `simple-email-gw` config concern, not package
code.

## License

MIT