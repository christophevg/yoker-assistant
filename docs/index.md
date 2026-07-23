# yoker-assistant

A personal assistant that communicates by email, built on yoker-as-SDK.

Python owns the email loop (poll, fetch, reply, archive) and calls yoker as a
library for the reasoning half. The package is also a yoker plugin provider
(dual-mode): it exposes its own tools via `__YOKER_MANIFEST__` for any yoker
consumer to load.

This is one of two yoker 1.0 pet-store showcase packages. Its sister project
`yoker-writing-assistant` demonstrates yoker-as-runtime; this one demonstrates
yoker-as-SDK: the Python process owns the loop and imports yoker as a library.

## Contents

```{toctree}
:maxdepth: 2

installation
quickstart
tutorial
architecture
porting-map
security
configuration
api
changelog
```

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`