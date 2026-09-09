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

Reads SMILES from a text file — one per line; blank lines and `#` comments are ignored — and writes a single JSON with per-item outcomes and `total` / `succeeded` / `failed` counts. Failed items do not abort the batch.

```bash
edkg-dl-predict batch molecules.txt --asset-dir ./models
edkg-dl-predict batch molecules.txt -o runs/batch --max-workers 4   # 1-8 workers
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
- Results keep the input order; the top level contains `total` / `succeeded` / `failed` and per-item `items`
- A failed item gets `ok: false` with an `error` (`code` + `message`); other items continue
- Batch mode writes JSON only (`batch_prediction.json`), no Excel
- No valid SMILES in the file, a missing file, or an encoding error exits with code 2

## Asset download

```bash
edkg-dl-predict download                 # to the user cache directory
edkg-dl-predict download --asset-dir ./models
edkg-dl-predict download --repo-id <repo>   # override the Hugging Face repository
```

See [model assets](assets.md) for resolution order and offline use.
