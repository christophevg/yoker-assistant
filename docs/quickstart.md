# Quickstart

This page walks through the first run end-to-end. You should have already
finished [Installation](installation.md) — `~/.yoker.toml` configured with a
backend, `.env` with mailbox credentials and the recipient whitelist, and
`make env-dev` green. Plugin registration is automatic — the package
injects `enabled` and `packages` at startup; you confirm trust
interactively on first run.

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

## The PERSONAL.md bootstrap flow

On the very first run, `PERSONAL.md` does not exist yet in the working
directory. The agent detects this on its `Initialize` turn (it tries
`yoker:read PERSONAL.md` and the read fails) and enters its bootstrap flow: it
replies with a welcome message and a set of questions about you (name,
preferred address, project context, tone, goals). You answer by replying to
that email; the agent iterates with you over email until it has enough to
write the initial `PERSONAL.md`. Once written, the agent optionally commits
and pushes it via `yoker:git` — that commit is the visible "acts on behalf
of the owner" moment in the demo beat (see the [Tutorial](tutorial.md) §10).

After bootstrap, every subsequent email is the next user message in the SAME
session. The agent remembers the running conversation; you do not re-introduce
yourself each time.

## A worked example: teaching the assistant a preference

Once the bootstrap is done, the assistant is ready to act on your behalf.
Here is what happens when you email it a preference — the showcase's
headline demo beat.

### 1. You send an email

Send an email to the assistant's mailbox:

> From: owner@example.com
> Subject: new rule for deploy emails
>
> From now on, always CC me on replies to staging-deploy emails.

### 2. Python picks it up

The loop polls IMAP, finds the message as `UNSEEN`, fetches it, and builds
the handoff payload:

```
From: owner@example.com
Subject: new rule for deploy emails
Date: Wed, 23 Jul 2026 10:15:02 +0000

From now on, always CC me on replies to staging-deploy emails.
```

Python hands this to `session.agent.process(handoff)`.

### 3. The agent reasons

The agent reads the email, categorizes it as a learned behaviour (not a
one-off action), and decides what to do:

1. **Update `PERSONAL.md`** — adds the new rule to the `## Behaviors`
   section via `yoker:update`.
2. **Commit and push** — commits the `PERSONAL.md` change via `yoker:git`
   and pushes to the configured remote.
3. **Compose a reply** — acknowledges the change in markdown, then converts
   it to HTML via the `yoker_assistant:md_to_html` tool.

### 4. The reply arrives in your inbox

The agent's HTML reply is emailed verbatim by Python. It looks something
like this (rendered as HTML in your email client):

> **Done**
>
> I've added the following rule to PERSONAL.md:
>
> - Always CC the owner on replies to staging-deploy emails.
>
> The change has been committed and pushed to the repository.
>
> **Actions Taken:**
>
> | Action | Detail |
> |--------|--------|
> | Updated PERSONAL.md | Added behaviour rule |
> | Git commit + push | `chore: add CC rule for deploy emails` |

### 5. What happened behind the scenes

The agent used **bounded tools** — no shell, no arbitrary commands:

- `yoker:read` to read the current `PERSONAL.md`
- `yoker:update` to add the new behaviour
- `yoker:git` to commit and push
- `yoker_assistant:md_to_html` to convert the markdown reply to HTML

Python then sent the HTML as the reply email, marked the original message
read, and archived it. The whole loop took one iteration.

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
