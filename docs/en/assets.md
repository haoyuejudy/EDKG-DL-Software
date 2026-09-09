# Model Assets

Model assets (~930 MB) are distributed through the public Hugging Face model [`HaoyueTan/edkg-dl-models`](https://huggingface.co/HaoyueTan/edkg-dl-models).

## Download

```bash
edkg-dl-predict download                 # to the user cache directory
edkg-dl-predict download --asset-dir ./models
```

The download is resumable and integrity-checked. When no assets are found, a prediction automatically downloads them to the user cache directory (for example `~/.cache/edkg-dl/models` on Linux).

## Resolution order

1. `--asset-dir` argument (Python API: the `asset_dir` parameter)
2. `EDKG_DL_ASSET_DIR` environment variable
3. user cache directory — downloaded automatically when missing

## Offline use

Set `HF_HUB_OFFLINE=1` to reuse an existing download without network access.

## Directory layout

```text
models/
├── settings.json
├── manifest.json          # SHA-256 digests for integrity verification
├── qualitative_models/    # per-event CSV + PKL
├── quantitative_models/   # quantitative event CSV + PKL
├── edc_models/            # 903-EDCs-2.csv + model_11.pkl
├── gnn_models/            # model_state.pt
└── padel_runs_cache/      # descriptors.xml
```

A `manifest.json` with SHA-256 digests is included, and every file digest is verified against it before the models load.

## Security note

PKL/Joblib files execute code when deserialized; only load assets from trusted sources.
