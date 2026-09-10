# 开发

## 环境搭建

```bash
git clone https://github.com/haoyuejudy/EDKG-DL-Software.git
cd EDKG-DL
uv sync --all-extras
```

`--all-extras` 包含 `cpu` extra，torch 会从 PyTorch CPU 轮子镜像（`mirror.nju.edu.cn/pytorch/whl/cpu`）安装；本地需要 CUDA 版 torch 时，改用 `uv sync --extra api --extra plots` 即可回到默认索引。

## HTTP API docker 镜像构建

构建时通过 BuildKit secret 传入 Hugging Face token——只在模型下载层临时挂载，不会写入镜像层或缓存：

```bash
docker build --secret id=hf_token,src=$HOME/.cache/huggingface/token -t edkg-dl .
```

模型已在构建时下载进镜像，运行时无需挂载资产：

```bash
docker run --rm -p 8000:8000 edkg-dl
```

HTTP 接口用法见 [HTTP API](http-api.md)。

## 测试

使用 pytest 运行测试套件：

```bash
uv run pytest                # 完整套件；模型资产未缓存时端到端测试自动跳过
uv run pytest -m "not slow"  # 跳过真实资产端到端测试
```

## 代码检查与格式化

```bash
uv run ruff check .
uv run ruff format .
```

## 依赖策略

依赖版本已锁定，与使用 scikit-learn 1.6.1、XGBoost 3.0.2、Joblib 1.5.1 训练的资产保持一致——请勿升级这些包。Torch 使用 CPU 版本：`cpu` extra 借助 `pyproject.toml` 中的 `[tool.uv.sources]` 将 torch 路由到 CPU 镜像（Docker 镜像与上述安装命令均已启用）。
