# Security

This page covers the security configuration a yoker-assistant operator must
understand before running the package. The source `SECURITY.md` at the repo
root documents the manifest-addition review process contributors follow
before adding a tool; this page cross-references it and expands the
operator-facing configuration.

## Self-trust blast radius

Marking `[plugins.trusted] yoker_assistant = true` in `~/.yoker.toml`
admits ALL tool code from this package as trusted with no per-call gate.
The trust decision is made once, at install time, and admits all tool code
from the package. This is the intended yoker trust model — the package runs
unattended (no TTY to prompt), so the trust gate has to be cleared up front
or the package cannot run.

The blast radius is real: every tool in `__YOKER_MANIFEST__` runs with no
per-call gate, including `yoker:git` (full git — read, commit, push).
Mitigate by:

- **Pin the installed version** — `uv pip install yoker-assistant==<version>`
  so the tool code you reviewed is the tool code that runs. A floating
  install silently swaps in new tool code on each `uv sync`.
- **Verify the source** — review the package source (this repository)
  before marking it trusted. The manifest is small
  (`src/yoker_assistant/__init__.py`); read it.
- **Review the `pkgq` plugin the same way** — it is also marked trusted
  in the recommended config. `pkgq` is a third-party package; pin its
  version too.

## Recipient whitelist — the primary reply-safety boundary

`EMAIL_RECIPIENT_WHITELIST_ADDRESSES` is the primary reply-safety boundary.
The assistant may only reply to addresses in this whitelist. Set it to the
single owner address; leaving it broad allows the agent to reply to
arbitrary senders.

```
EMAIL_RECIPIENT_WHITELIST_ADDRESSES=owner@example.com
```

The env var name is `EMAIL_RECIPIENT_WHITELIST_ADDRESSES` — NOT
`EMAIL_RECIPIENT_ADDRESSES`. The wrong name silently disables the whitelist
(this is an upstream `simple-email-gw` README bug; an issue is filed — see
`TODO.md` S-03). With the whitelist silently disabled, the assistant would
reply to arbitrary senders, which is the worst-case reply-safety failure.

The C1 blocking fix in `loop.py` makes this fail-safe: `run()` refuses to
start when the recipient whitelist is disabled — the whitelist fails open,
so an unset whitelist would let the assistant reply to arbitrary senders.
`run()` raises `RuntimeError` (citing `EMAIL_RECIPIENT_DOMAINS`,
`EMAIL_RECIPIENT_ADDRESSES`, or `EMAIL_RECIPIENT_WHITELIST_JSON`) before
constructing the `Agent`.

This is a `simple-email-gw` config concern, not package code. Python relies
on `simple-email_gw`'s existing config; no package-level allowlist code is
written.

## `~/.yoker.toml` and `.env` are NEVER committed

Both files contain secrets (`~/.yoker.toml` has the LLM API key; `.env` has
the mailbox password). Neither is committed to the repo:

- `.env` is gitignored at the repo root.
- `~/.yoker.toml` lives in the user home and never enters the repo.

A user who snapshots `~/.yoker.toml` into a repo (for example, to back it
up) MUST gitignore it. The repo provides `yoker.toml.example` as reference
documentation only — it has a REFERENCE ONLY header and no real `api_key`;
do not copy real secrets into it.

## The manifest-addition review process

Every addition to `__YOKER_MANIFEST__` auto-trusts on user install via
`[plugins.trusted] yoker_assistant = true` — there is no secondary review
gate inside the package. `SECURITY.md` documents the review process
contributors MUST follow before adding a tool to the manifest (or making a
capability-changing edit to an existing tool — new args, new side effects,
new dependencies, or a change to the tool's reach). Pure refactors that do
not change the tool's inputs, outputs, reach, or failure modes do not
require this review.

The process has four steps (paraphrased here; see `SECURITY.md` for the
authoritative text):

1. **Blast-radius assessment** — document the tool's inputs, outputs,
   reach, and failure modes. Any string/path/URL input? Side effects beyond
   the return value? What can it touch (filesystem, network, shell,
   subprocess, env vars, other tools)? What happens on bad input?
2. **Capability review** — does the tool duplicate an existing yoker
   built-in? Does it compose with `yoker:git`, `yoker:write`, or
   `yoker:webfetch` in a way that creates a new exfiltration or persistence
   path? Is the tool bounded (named, typed args, no `**kwargs` shell) or
   unbounded? Unbounded tools are rejected by default.
3. **Version pinning** — the tool's behavior must be deterministic for a
   pinned package version. No network-fetched code paths at call time. If
   the tool depends on a network resource, the dependency must be declared
   in `pyproject.toml` (so `uv pip install yoker-assistant==<version>`
   reproduces it), not loaded dynamically.
4. **Review checklist** — the PR description records: blast-radius
   assessment, capability review, version pinning, tests cover the happy
   path + at least one failure mode, `make check` green, `SECURITY.md`
   updated if the process itself changes.

A manifest addition or capability-changing edit merged without this
checklist is a process violation: it is not automatically a security
incident, but it triggers (1) immediate revert of the change, and (2) a
retroactive security review of what the unreviewed code did while live,
covering the exposure window from merge to revert. CI does not enforce
this — it is a reviewer judgment gate.

## Publishing guards

`make pre-publish` (see `Makefile`) rejects built sdist/wheel metadata
containing non-registry source URLs (`file://`, VCS schemes, direct
`@ <url>` references, `path =`). This prevents local-path development
wiring (which lives in `[tool.uv.sources]` and is structurally excluded
from PyPI metadata) from ever leaking into a published artifact if
discipline slips.

`make pre-publish` also rejects relative image paths in `README.md` (the
`media/` prefix check) and verifies that the `pyproject.toml` version
matches the `src/yoker_assistant/__init__.py` `__version__`.

## Deliberate non-additions

A supported-versions table, a formal CVE-handling section, a PGP key, and a
`security.txt` are deliberately omitted from `SECURITY.md`. For a 0.1.0
single-tool plugin provider with no released security history, these are
ceremony — premature policy-writing that would go stale immediately. If a
real CVE lands or multiple release lines emerge, revisit then; until then,
GitHub Security Advisories is the one-line-footnote fallback for CVE
publication.