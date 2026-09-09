# 开发

## 环境搭建

```bash
git clone https://github.com/haoyuejudy/EDKG-DL.git
cd EDKG-DL
uv sync --all-extras
```

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

依赖版本已锁定，与使用 scikit-learn 1.6.1、XGBoost 3.0.2、Joblib 1.5.1 训练的资产保持一致——请勿升级这些包。Torch 使用 CPU 版本。
