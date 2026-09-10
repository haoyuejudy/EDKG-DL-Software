# EDKG-DL

English | [简体中文](https://github.com/haoyuejudy/EDKG-DL/blob/main/README_zh.md)

**D**eep **L**earning framework with causality-integrated **E**ndocrine **D**isruption **K**nowledge **G**raph. Predicts endocrine-disrupting chemicals (EDCs), applicability domain (ADs), biological entities, and sensitive pathways from compound SMILES using machine learning and graph deep learning algorithmes.

Pipeline: PaDEL 2D descriptors/fingerprints → biological entity-specific qualitative/quantitative models → causality-integrated EDC classification → sensitive adverse outcome (AO) and adverse outcome pathway (AOP) inference, producing JSON / Excel reports.

## Installation

Install from PyPI (Python ≥ 3.10):

```bash
pip install edkg-dl
# or
uv add edkg-dl
```

Optional extras: `pip install "edkg-dl[api]"` (HTTP service) and `pip install "edkg-dl[plots]"` (applicability-domain plots). See [installation docs](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/installation.md) for details, including the automatic Temurin JRE download for PaDEL.

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
| Installation | [installation.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/installation.md) |
| Model assets | [assets.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/assets.md) |
| CLI usage | [cli.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/cli.md) |
| Python API | [python-api.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/python-api.md) |
| HTTP API | [http-api.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/http-api.md) |
| Output formats | [output.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/output.md) |
| Development | [development.md](https://github.com/haoyuejudy/EDKG-DL/blob/main/docs/en/development.md) |
