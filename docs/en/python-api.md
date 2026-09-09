# Python API

```python
from edkg_dl import Predictor

predictor = Predictor.from_assets("./models")
result = predictor.predict("CCO")
```

`from_assets` accepts the same resolution as the CLI: an explicit directory, `None` to fall back to `EDKG_DL_ASSET_DIR` or the user cache directory (downloading automatically when missing). Optional `max_paths` and `max_path_length` mirror the CLI arguments.

## Batch prediction

```python
batch = predictor.predict_batch(["CCO", "invalid", "CCN"], max_workers=4)
print(batch.succeeded, batch.failed)
```

Results keep the input order; failed items carry an `error` and do not abort the batch.

## Working with results

`result.to_dict()` returns the same structure as the JSON report — see [output formats](output.md).
