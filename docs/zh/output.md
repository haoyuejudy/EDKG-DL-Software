# 输出格式

预测结果可输出为 JSON、Excel 以及可选的适用域图。

## JSON

顶层包含：

- **EDC 分类**及总体最终判定
- **定性/定量适用域**
- 带因果链校验状态的**敏感事件**
- 各事件的**定性与定量预测**
- 带证据权重的 **AOP 关系**

## Excel

工作簿在 Summary 表中将 EDC 预测显示为 EDC/no-EDC 标签，并包含 Events、AO Predicted Results、Causal Chains 工作表。

## 适用域绘图

使用 `--ad-plots`（需要配合 `--output`，并安装 `plots` extra：`pip install "edkg-dl[plots]"`）时，会为实际参与预测的每个终点生成一张 PCA 散点图。每张图展示训练样本在前两个主成分上的投影，并用 `x` 标出待预测分子的位置，标题注明该分子是否位于适用域内。图片写入输出目录下的 `AD/qualitative/<event_id>.png` 与 `AD/quantitative/<event_id>.png`；已存在的图片仅在 `--overwrite` 时才会被替换。

```bash
edkg-dl-predict "CCO" --asset-dir ./models --output runs/example --ad-plots
```

## 免责声明

结果仅用于科研辅助，不能替代实验或监管结论。
