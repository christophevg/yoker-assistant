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
make env-dev        # install all dependencies (local path deps for dev)
make test           # run the test suite
python -m yoker_assistant   # entry point stub (exits cleanly until wired)
```

Configuration:

- `yoker.toml` — backend, model, permissions, plugins, skills.
- `.env` (from `.env.example`) — email account credentials via simple-email-gw.

## License

MIT