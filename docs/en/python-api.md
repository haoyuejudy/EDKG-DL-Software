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

You can also export the result to files with the writers in `edkg_dl.reporting`, producing the same artifacts as the CLI `--output`:

```python
from edkg_dl.reporting import write_ad_plots, write_excel_report, write_json_report

write_json_report(result, "runs/example/prediction.json")
write_excel_report(result, "runs/example/prediction.xlsx")  # multi-sheet Excel report
```

Both report writers return the absolute path of the published file and raise `OutputExistsError` when the target exists; pass `overwrite=True` to allow replacing it.

For applicability-domain PCA plots, obtain the PaDEL features with `predict_with_features` first, then call `write_ad_plots` (requires the `plots` extra: `pip install "edkg-dl[plots]"`):

```python
result, features = predictor.pipeline.predict_with_features("CCO")
write_ad_plots(
    result,
    features,
    predictor.pipeline.model_registry.paths,
    "runs/example/AD",
)
```

Images are written to `qualitative/<event_id>.png` and `quantitative/<event_id>.png`, matching the CLI `--ad-plots` output.
