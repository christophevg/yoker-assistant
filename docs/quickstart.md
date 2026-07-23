# Quickstart

This page walks through the first run end-to-end. You should have already
finished [Installation](installation.md) — `~/.yoker.toml` configured with a
backend and the plugin block, `.env` with mailbox credentials and the
recipient whitelist, and `make env-dev` green.

## Run one iteration

```bash
python -m yoker_assistant --once
```

`--once` runs exactly one poll iteration and exits. It is the demo/test mode:
on an empty inbox it connects, searches, finds nothing, and exits cleanly; on
a seeded unread email it processes the email end-to-end (reply, mark read,
archive) and exits. Use it for first-run verification and for the showcase
demo beat.

Drop `--once` for the long-running mode:

```bash
python -m yoker_assistant    # polls every 60s until SIGINT/SIGTERM
```

## What to watch for in the logs

The loop logs at INFO level with `===` separators framing the conversation
between user and agent. Each processed email produces two blocks:

```
INFO: === Incoming message (user turn) ===
INFO: From: owner@example.com
INFO: Subject: retry the deploy
INFO: Date: Wed, 23 Jul 2026 10:15:02 +0000
INFO:
INFO: can you retry the deploy on staging?
INFO: === Agent reply ===
INFO: <h1>Done</h1><p>...</p>
```

The first block is the handoff payload (what Python delivered to the agent).
The second is the agent's reply. An empty reply is logged explicitly as
`(empty — no reply)` so a silent agent turn is still visible. The one-time
`Initialize` setup turn is NOT logged — it is a session-setup handshake, not
an incoming message.

## The PERSONAL.md bootstrap flow

On the very first run, `PERSONAL.md` does not exist yet in the working
directory. The agent detects this on its `Initialize` turn (it tries
`yoker:read PERSONAL.md` and the read fails) and enters its bootstrap flow: it
replies with a welcome message and a set of questions about you (name,
preferred address, project context, tone, goals). You answer by replying to
that email; the agent iterates with you over email until it has enough to
write the initial `PERSONAL.md`. Once written, the agent optionally commits
and pushes it via `yoker:git` — that commit is the visible "acts on behalf of
the owner" moment in the demo beat (see the [Tutorial](tutorial.md) §10).

After bootstrap, every subsequent email is the next user message in the SAME
session. The agent remembers the running conversation; you do not re-introduce
yourself each time.

## Graceful shutdown

`SIGINT` (Ctrl-C) and `SIGTERM` both trigger a clean exit: the in-flight
message finishes, the IMAP connection disconnects, and the process exits 0.
There is no forced kill mid-iteration — a message that has been pulled but not
yet archived stays `UNSEEN` (or marked-read-but-not-archived) and is tidied on
the next run.

## Next

Read the [Tutorial](tutorial.md) for the full build story — why this package
exists, the two halves, the seams, the handoff contract, the bounded tool set,
the persistent session, the dual-mode architecture, and the git demo beat.