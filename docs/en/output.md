# Output Formats

Predictions can be written as JSON, Excel, and optional applicability-domain plots.

## JSON

The top level contains:

- **Dual-model EDC classification** with the overall final verdict (1 when either the Original (graph) or Extended (tabular) model predicts EDC, 0 otherwise)
- **Qualitative / quantitative applicability domains**
- **Sensitive events** with causal-chain validation status
- **Qualitative and quantitative predictions per event**
- **AOP relations** with weight of evidence

## Excel

The workbook shows the EDC predictions as EDC/no-EDC labels on the Summary sheet and contains the Events, AO Predicted Results, and Causal Chains worksheets.

## Applicability-domain plots

With `--ad-plots` (requires `--output`, and the `plots` extra: `pip install "edkg-dl[plots]"`), a PCA scatter plot is written for every endpoint that took part in the prediction. Each image shows the training samples projected onto the first two PCA components plus the predicted molecule marked with `x`, with the title stating whether the molecule lies inside the applicability domain. Images go to `AD/qualitative/<event_id>.png` and `AD/quantitative/<event_id>.png` under the output directory; existing images are only replaced with `--overwrite`.

```bash
edkg-dl-predict "CCO" --asset-dir ./models --output runs/example --ad-plots
```

## Disclaimer

Results are for research support only and must not replace experimental or regulatory conclusions.
