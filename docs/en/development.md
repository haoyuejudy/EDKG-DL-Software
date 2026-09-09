# Development

## Setup

```bash
git clone https://github.com/haoyuejudy/EDKG-DL.git
cd EDKG-DL
uv sync --all-extras
```

`--all-extras` includes the `cpu` extra, so torch is installed from the PyTorch CPU wheel mirror (`mirror.nju.edu.cn/pytorch/whl/cpu`). If you need a CUDA build of torch locally, use `uv sync --extra api --extra plots` instead to fall back to the default index.

## HTTP API docker image build

Pass the Hugging Face token via a BuildKit secret — it is mounted only for the model-download layer and never baked into image layers or cache:

```bash
docker build --secret id=hf_token,src=$HOME/.cache/huggingface/token -t edkg-dl .
```

Model assets are baked into the image at build time, so no volume mounts are needed at runtime:

```bash
docker run --rm -p 8000:8000 edkg-dl
```

See [HTTP API](http-api.md) for endpoint usage.

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

Dependencies are pinned to match assets trained with scikit-learn 1.6.1, XGBoost 3.0.2, and Joblib 1.5.1 — do not upgrade these packages. Torch uses the CPU build: the `cpu` extra routes torch to the CPU mirror via `[tool.uv.sources]` in `pyproject.toml` (enabled both in the Docker image and by the setup command above).
