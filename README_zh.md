# EDKG-DL

[English](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/README.md) | 简体中文

融合因果关系的内分泌干扰知识图谱深度学习框架（**D**eep **L**earning framework with causality-integrated **E**ndocrine **D**isruption **K**nowledge **G**raph）。基于化合物 SMILES，结合机器学习/深度学习与AOP网络，预测内分泌干扰物（EDC）、应用域（AD）、敏感有害结局以及敏感通路。

流程：PaDEL 2D 描述符/分子指纹 → 定性/定量事件-终点模型 → EDC预测模型 → 敏感事件与 AOP 通路推断，输出 JSON / Excel 报告。结果仅用于科研辅助，不能替代实验或监管结论。

## 安装

从 PyPI 安装（Python ≥ 3.10）：

```bash
pip install edkg-dl
# 或
uv add edkg-dl
```

可选 extras：`pip install "edkg-dl[api]"`（HTTP 服务）、`pip install "edkg-dl[plots]"`（适用域绘图）。详见[安装文档](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/installation.md)，包括 PaDEL 所需 Java 的自动下载说明。

模型资产（约 930 MB）首次使用时自动从 [Hugging Face](https://huggingface.co/HaoyueTan/edkg-dl-models) 获取——无需手动配置。

## 快速开始

命令行：

```bash
edkg-dl-predict "CCO"                                   # JSON 输出到标准输出
edkg-dl-predict "CCO" -o runs/example --ad-plots        # 报告 + PCA 适用域图
edkg-dl-predict batch molecules.txt -o runs/batch       # 从文本文件批量预测
```

Python：

```python
from edkg_dl import Predictor

predictor = Predictor.from_assets("./models")
result = predictor.predict("CCO")
```

## 文档

| 主题 | 链接 |
| --- | --- |
| 安装 | [installation.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/installation.md) |
| 模型资产 | [assets.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/assets.md) |
| 命令行用法 | [cli.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/cli.md) |
| Python API | [python-api.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/python-api.md) |
| HTTP API | [http-api.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/http-api.md) |
| 输出格式 | [output.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/output.md) |
| 开发 | [development.md](https://github.com/haoyuejudy/EDKG-DL-Software/blob/main/docs/zh/development.md) |

## 免责声明

结果仅用于科研辅助，不能替代实验或监管结论。
