# 命令行用法

`edkg-dl-predict` 命令覆盖单条预测、批量预测与资产下载。

## 单条预测

```bash
edkg-dl-predict "CCO" --asset-dir ./models
edkg-dl-predict "CCO" --asset-dir ./models --output runs/example --format both
edkg-dl-predict "CCO" --output runs/example --ad-plots   # 资产按解析顺序自动获取
```

不带 `--output` 时，结果 JSON 打印到标准输出。

参数：

| 参数 | 说明 |
| --- | --- |
| `--asset-dir DIR` | 运行时资产目录（见[模型资产](assets.md)） |
| `-o, --output DIR` | 将报告写入目录而非标准输出 |
| `--format {json,xlsx,both}` | 指定 `--output` 时的报告格式（默认 `json`） |
| `--ad-plots` | 生成 PCA 适用域图（需配合 `--output`，[详见输出格式](output.md#适用域绘图)） |
| `--overwrite` | 替换已存在的报告文件 |
| `--max-paths N` | 最多报告的 AOP 通路数（默认 1000） |
| `--max-path-length N` | 限制 AOP 通路长度 |

## 批量预测

从**文本文件**读取输入：每行一个 SMILES，空行和以 `#` 开头的注释行会被忽略；始终输出汇总 JSON（`batch_prediction.json`，包含逐条结果与 `total` / `succeeded` / `failed` 统计），并可按 `--format` 为每条成功的 SMILES 追加单分子报告。单条失败不影响其他条目。

```bash
edkg-dl-predict batch molecules.txt --asset-dir ./models
edkg-dl-predict batch molecules.txt -o runs/batch --max-workers 4        # 1-8 线程
edkg-dl-predict batch molecules.txt -o runs/batch --format both          # 每条 SMILES 一个 JSON + 一个 Excel
edkg-dl-predict batch molecules.txt -o runs/batch --format xlsx --overwrite
```

输入文件示例（`molecules.txt`，UTF-8 编码）：

```text
# 注释行与空行会被忽略
CCO
CCN
c1ccccc1
```

批量专属行为：

- `--max-workers`：并发预测线程数，取值 1–8，默认 1
- `--format {json,xlsx,both}`：配合 `--output` 时，为每条**成功**的 SMILES 输出一个 `prediction_序号.json` 和/或 `prediction_序号.xlsx`（默认 `json`）；序号为 4 位输入行号（如 `prediction_0000`）
- 失败条目不生成单分子报告，其 `ok` 为 `false` 并附带 `error`（含 `code` 与 `message`），记录在 `batch_prediction.json` 中，其余条目继续
- 汇总文件 `batch_prediction.json` 始终输出，不受 `--format` 影响；所有目标文件已存在时需 `--overwrite` 才会替换
- 文件中无有效 SMILES、文件不存在或编码错误时，命令报错并以退出码 2 结束

## 资产下载

```bash
edkg-dl-predict download                 # 下载到用户缓存目录
edkg-dl-predict download --asset-dir ./models
edkg-dl-predict download --repo-id <repo>   # 覆盖 Hugging Face 仓库
```

解析顺序与离线使用见[模型资产](assets.md)。
