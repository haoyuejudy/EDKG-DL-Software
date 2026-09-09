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

## Torch variants (CPU / CUDA)

The `torch` wheels on PyPI already vary by OS: macOS and Windows wheels are CPU-only, while Linux wheels bundle the CUDA runtime — for most users `pip install edkg-dl` just works.

To pick a specific torch variant or version on Linux/Windows, install torch first, then `edkg-dl` (the installed torch is reused as long as it satisfies `>=2.0.0`):

```bash
pip install torch --index-url https://mirror.nju.edu.cn/pytorch/whl/cu130   # pass e.g. torch==2.13.0+cu130 for an exact version
pip install edkg-dl
```

## Runtime dependency: Java for PaDEL

Descriptor calculation uses PaDEL, which requires Java 8+. When no `java` is found on PATH, a Temurin 17 JRE matching the OS and architecture is downloaded automatically into the user cache directory — no manual setup needed.

## Next steps

- [Model assets](assets.md) — ~930 MB of model weights, downloaded automatically on first use
- [CLI usage](cli.md) — single and batch prediction from the command line
