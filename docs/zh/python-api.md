# Python API

```python
from edkg_dl import Predictor

predictor = Predictor.from_assets("./models")
result = predictor.predict("CCO")
```

`from_assets` 的资产解析方式与命令行一致：显式目录，或传 `None` 时依次回退到 `EDKG_DL_ASSET_DIR` 环境变量和用户缓存目录（缺失时自动下载）。可选参数 `max_paths`、`max_path_length` 与命令行参数含义相同。

## 批量预测

```python
batch = predictor.predict_batch(["CCO", "invalid", "CCN"], max_workers=4)
print(batch.succeeded, batch.failed)
```

结果按输入顺序排列；失败条目附带 `error`，且不会中断整批。

## 处理结果

`result.to_dict()` 返回与 JSON 报告相同的结构，见[输出格式](output.md)。

也可以调用 `edkg_dl.reporting` 中的导出函数，把结果写成文件，得到与命令行 `--output` 相同的产物：

```python
from edkg_dl.reporting import write_ad_plots, write_excel_report, write_json_report

write_json_report(result, "runs/example/prediction.json")
write_excel_report(result, "runs/example/prediction.xlsx")  # 多工作表 Excel 报告
```

两个报告函数都返回发布文件的绝对路径；目标文件已存在时默认抛出 `OutputExistsError`，传入 `overwrite=True` 才允许替换。

如需适用域 PCA 图，先用 `predict_with_features` 获取 PaDEL 特征，再调用 `write_ad_plots`（需要安装 `plots` extra：`pip install "edkg-dl[plots]"`）：

```python
result, features = predictor.pipeline.predict_with_features("CCO")
write_ad_plots(
    result,
    features,
    predictor.pipeline.model_registry.paths,
    "runs/example/AD",
)
```

图片写入 `qualitative/<event_id>.png` 与 `quantitative/<event_id>.png`，内容与命令行 `--ad-plots` 一致。
