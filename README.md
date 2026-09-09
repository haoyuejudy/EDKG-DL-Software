# EDKG-DL

English | [简体中文](README_zh.md)

**D**eep **L**earning framework with causality-integrated **E**ndocrine **D**isruption **K**nowledge **G**raph. Predicts endocrine-disrupting effects (EDC), applicability domain (AD), and sensitive event pathways from compound SMILES using machine learning and an AOP network.

Pipeline: PaDEL 2D descriptors/fingerprints → qualitative/quantitative event-endpoint models → dual-track EDC classification (tabular model + graph neural network, GCN) → sensitive event and AOP pathway inference, producing JSON / Excel reports. Results are for research support only and must not replace experimental or regulatory conclusions.

## Installation

Install from PyPI (Python ≥ 3.10):

```bash
pip install edkg-dl
# or
uv add edkg-dl
```

Optional extras: `pip install "edkg-dl[api]"` (HTTP service) and `pip install "edkg-dl[plots]"` (applicability-domain plots). See [installation docs](docs/en/installation.md) for details, including the automatic Temurin JRE download for PaDEL.

Model assets (~930 MB) are fetched automatically from [Hugging Face](https://huggingface.co/HaoyueTan/edkg-dl-models) on first use — no manual setup required.

## Quick start

CLI:

```bash
edkg-dl-predict "CCO"                                   # JSON to stdout
edkg-dl-predict "CCO" -o runs/example --ad-plots        # reports + PCA plots
edkg-dl-predict batch molecules.txt -o runs/batch       # batch from a text file
```

Python:

```python
from edkg_dl import Predictor

predictor = Predictor.from_assets("./models")
result = predictor.predict("CCO")
```

## Documentation

| Topic | Link |
| --- | --- |
| Installation | [docs/en/installation.md](docs/en/installation.md) |
| Model assets | [docs/en/assets.md](docs/en/assets.md) |
| CLI usage | [docs/en/cli.md](docs/en/cli.md) |
| Python API | [docs/en/python-api.md](docs/en/python-api.md) |
| HTTP API | [docs/en/http-api.md](docs/en/http-api.md) |
| Output formats | [docs/en/output.md](docs/en/output.md) |
| Development | [docs/en/development.md](docs/en/development.md) |
