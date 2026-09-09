# Installation

EDKG-DL is available on PyPI as `edkg-dl` and supports Python ≥ 3.10.

## pip

```bash
pip install edkg-dl
```

## uv

```bash
uv add edkg-dl          # as a project dependency
uv pip install edkg-dl  # into an active environment
```

## CLI-only install

To use the `edkg-dl-predict` and `edkg-dl-api` commands without polluting a project environment:

```bash
uv tool install edkg-dl
```

## Optional extras

```bash
pip install "edkg-dl[api]"    # FastAPI HTTP service (edkg-dl-api)
pip install "edkg-dl[plots]"  # applicability-domain plots (matplotlib)
pip install "edkg-dl[api,plots]"
```

The same extras work with `uv add`, `uv pip install`, and `uv tool install`.

## Runtime dependency: Java for PaDEL

Descriptor calculation uses PaDEL, which requires Java 8+. When no `java` is found on PATH, a Temurin 17 JRE matching the OS and architecture is downloaded automatically into the user cache directory — no manual setup needed.

## Next steps

- [Model assets](assets.md) — ~930 MB of model weights, downloaded automatically on first use
- [CLI usage](cli.md) — single and batch prediction from the command line
