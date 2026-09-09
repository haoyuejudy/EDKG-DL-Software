# Development

## Setup

```bash
git clone https://github.com/haoyuejudy/EDKG-DL.git
cd EDKG-DL
uv sync --all-extras
```

## Tests

Run the test suite with pytest:

```bash
uv run pytest                # full suite; end-to-end tests skip when model assets are not cached
uv run pytest -m "not slow"  # skip the real-asset end-to-end tests
```

## Lint and formatting

```bash
uv run ruff check .
uv run ruff format .
```

## Dependency policy

Dependencies are pinned to match assets trained with scikit-learn 1.6.1, XGBoost 3.0.2, and Joblib 1.5.1 — do not upgrade these packages. Torch uses the CPU build.
