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
