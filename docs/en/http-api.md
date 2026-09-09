# HTTP API

Requires the `api` extra: `pip install "edkg-dl[api]"`.

## Starting the service

```bash
EDKG_DL_ASSET_DIR=./models edkg-dl-api   # defaults to 127.0.0.1:8000
edkg-dl-api --host 0.0.0.0 --port 8000   # bind address and port via CLI flags
```

Configuration:

| Type | Name | Default | Description |
| --- | --- | --- | --- |
| CLI flag | `--host` | `127.0.0.1` | Bind address |
| CLI flag | `--port` | `8000` | Bind port |
| Variable | `EDKG_DL_ASSET_DIR` | — | Asset directory (see [assets](assets.md) for the full resolution order) |

Run `edkg-dl-api -v` to print the version.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness probe, independent of model inference |
| GET | `/ready` | Configuration readiness and cached model count |
| GET | `/v1/model-info` | Event scale and causal-chain policy |
| POST | `/v1/predictions` | Single-molecule prediction |
| POST | `/v1/predictions/batch` | Batch prediction, at most 100 items per request |

## Examples

Single prediction:

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CCO"}'
```

Batch prediction (`smiles` is a list of 1–100 items, `max_workers` 1–8):

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions/batch \
  -H "Content-Type: application/json" \
  -d '{"smiles": ["CCO", "CCN"], "max_workers": 4}'
```

Responses use the same structure as the JSON report ([output formats](output.md)). Prediction failures return 422 with `{"detail": {"code", "message"}}`; oversized batches return 413. Interactive docs are available at `/docs` (FastAPI default).
