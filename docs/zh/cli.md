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

从**文本文件**读取输入：每行一个 SMILES，空行和以 `#` 开头的注释行会被忽略；输出单个 JSON，包含逐条结果与 `total` / `succeeded` / `failed` 统计。单条失败不影响其他条目。

```bash
edkg-dl-predict batch molecules.txt --asset-dir ./models
edkg-dl-predict batch molecules.txt -o runs/batch --max-workers 4   # 1-8 线程
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
- 结果按输入顺序排列，顶层包含 `total` / `succeeded` / `failed` 统计与逐条结果 `items`
- 失败条目的 `ok` 为 `false`，并附带 `error`（含 `code` 与 `message`），其余条目继续
- 批量模式仅输出 JSON（`batch_prediction.json`），不生成 Excel
- 文件中无有效 SMILES、文件不存在或编码错误时，命令报错并以退出码 2 结束

## 资产下载

```bash
edkg-dl-predict download                 # 下载到用户缓存目录
edkg-dl-predict download --asset-dir ./models
edkg-dl-predict download --repo-id <repo>   # 覆盖 Hugging Face 仓库
```

解析顺序与离线使用见[模型资产](assets.md)。
