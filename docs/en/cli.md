# CLI Usage

The `edkg-dl-predict` command handles single prediction, batch prediction, and asset download.

## Single prediction

```bash
edkg-dl-predict "CCO" --asset-dir ./models
edkg-dl-predict "CCO" --asset-dir ./models --output runs/example --format both
edkg-dl-predict "CCO" --output runs/example --ad-plots   # assets resolve automatically
```

Without `--output`, the result JSON is printed to stdout.

Options:

| Option | Description |
| --- | --- |
| `--asset-dir DIR` | Runtime asset directory (see [assets](assets.md)) |
| `-o, --output DIR` | Write reports to a directory instead of stdout |
| `--format {json,xlsx,both}` | Report format when `--output` is given (default: `json`) |
| `--ad-plots` | Write PCA applicability-domain plots (requires `--output`, [details](output.md#applicability-domain-plots)) |
| `--overwrite` | Replace report files that already exist |
| `--max-paths N` | Maximum AOP paths to report (default: 1000) |
| `--max-path-length N` | Cap AOP path length |

## Batch prediction

Reads SMILES from a text file — one per line; blank lines and `#` comments are ignored — and always writes a summary JSON (`batch_prediction.json`) with per-item outcomes and `total` / `succeeded` / `failed` counts. With `--output`, `--format` additionally writes one report per succeeded SMILES. Failed items do not abort the batch.

```bash
edkg-dl-predict batch molecules.txt --asset-dir ./models
edkg-dl-predict batch molecules.txt -o runs/batch --max-workers 4        # 1-8 workers
edkg-dl-predict batch molecules.txt -o runs/batch --format both          # one JSON + one Excel per SMILES
edkg-dl-predict batch molecules.txt -o runs/batch --format xlsx --overwrite
```

Input file example (`molecules.txt`, UTF-8):

```text
# comments and blank lines are ignored
CCO
CCN
c1ccccc1
```

Batch-specific behavior:

- `--max-workers`: concurrent prediction workers, 1–8, default 1
- `--format {json,xlsx,both}`: with `--output`, writes one `prediction_<index>.json` and/or `prediction_<index>.xlsx` per **succeeded** SMILES (default `json`); the index is the zero-based input line number, zero-padded to 4 digits (e.g. `prediction_0000`)
- Failed items produce no per-molecule report; they get `ok: false` with an `error` (`code` + `message`) recorded in `batch_prediction.json`, and other items continue
- `batch_prediction.json` is always written regardless of `--format`; existing target files are only replaced with `--overwrite`
- No valid SMILES in the file, a missing file, or an encoding error exits with code 2

## Asset download

```bash
edkg-dl-predict download                 # to the user cache directory
edkg-dl-predict download --asset-dir ./models
edkg-dl-predict download --repo-id <repo>   # override the Hugging Face repository
```

See [model assets](assets.md) for resolution order and offline use.
