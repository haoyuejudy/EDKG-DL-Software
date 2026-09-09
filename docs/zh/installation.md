# 安装

EDKG-DL 已发布到 PyPI（包名 `edkg-dl`），要求 Python ≥ 3.10。

## pip

```bash
pip install edkg-dl
```

## uv

```bash
uv add edkg-dl          # 作为项目依赖
uv pip install edkg-dl  # 安装到当前激活的环境
```

## 仅安装命令行工具

希望在不污染项目环境的情况下使用 `edkg-dl-predict` 与 `edkg-dl-api` 命令：

```bash
uv tool install edkg-dl
```

## 可选 extras

```bash
pip install "edkg-dl[api]"    # FastAPI HTTP 服务（edkg-dl-api）
pip install "edkg-dl[plots]"  # 适用域绘图（matplotlib）
pip install "edkg-dl[api,plots]"
```

以上 extras 同样适用于 `uv add`、`uv pip install` 与 `uv tool install`。

## 运行时依赖：PaDEL 所需的 Java

描述符计算使用 PaDEL，需要 Java 8+。当 PATH 中找不到 `java` 时，会按操作系统和架构自动下载匹配的 Temurin 17 JRE 到用户缓存目录——无需手动配置。

## 后续步骤

- [模型资产](assets.md)——约 930 MB 模型权重，首次使用时自动下载
- [命令行用法](cli.md)——命令行单条与批量预测
