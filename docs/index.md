# yoker-assistant

A personal assistant that communicates by email, built on yoker-as-SDK.

Python owns the email loop (poll, fetch, reply, archive) and calls Yoker as a
library for the reasoning half. The package is also a Yoker plugin provider
(dual-mode): it exposes its own tools via `__YOKER_MANIFEST__` for any Yoker
consumer to load.

This is one of two Yoker 1.0 showcase packages. Its sister project
[`yoker-writing-assistant`](https://github.com/christophevg/yoker-writing-assistant)
demonstrates yoker-as-runtime; this one demonstrates yoker-as-SDK: the
Python process owns the loop and imports Yoker as a library.

## What You'll Find Here

- **[Tutorial](tutorial.md)** — the build story, end-to-end. Why this
  package exists, the two halves, the seams, the handoff contract, the
  bounded tool set, the persistent session, the dual-mode architecture,
  and the git demo beat.
- **[Quickstart](quickstart.md)** — a worked example showing the
  assistant in action, from first email to PERSONAL.md commit.
- **[Architecture](architecture.md)** — seam-by-seam reference for the
  loop, the SDK integration, and the email gateway.
- **[Design Decisions](design-decisions.md)** — what was kept, reworked,
  removed, and added when building for the Yoker SDK context.
- **[Security](security.md)** — the trust model, reply-safety boundary,
  and the manifest review process.
- **[Configuration](configuration.md)** — the full `~/.yoker.toml`,
  `.env`, and `PERSONAL.md` reference.
- **[API](api.md)** — the public API surface.
- **[Changelog](changelog.md)** — release history.

## Contents

```{toctree}
:maxdepth: 2

installation
quickstart
tutorial
architecture
design-decisions
security
configuration
api
changelog
```

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`