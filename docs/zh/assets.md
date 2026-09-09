# 模型资产

模型资产（约 930 MB）通过公开的 Hugging Face 模型仓库 [`HaoyueTan/edkg-dl-models`](https://huggingface.co/HaoyueTan/edkg-dl-models) 分发。

## 下载

```bash
edkg-dl-predict download                 # 下载到用户缓存目录
edkg-dl-predict download --asset-dir ./models
```

下载支持断点续传并做完整性校验。未找到资产时，预测命令会自动将其下载到用户缓存目录（Linux 下例如 `~/.cache/edkg-dl/models`）。

## 解析顺序

1. `--asset-dir` 参数（Python API：`asset_dir` 参数）
2. `EDKG_DL_ASSET_DIR` 环境变量
3. 用户缓存目录——缺失时自动下载

## 离线使用

设置 `HF_HUB_OFFLINE=1` 可在无网络环境下复用已有下载。

## 目录结构

```text
models/
├── settings.json
├── manifest.json          # 用于完整性校验的 SHA-256 摘要
├── qualitative_models/    # 各事件 CSV + PKL
├── quantitative_models/   # 定量事件 CSV + PKL
├── edc_models/            # 903-EDCs-2.csv + model_11.pkl
├── gnn_models/            # model_state.pt
└── padel_runs_cache/      # descriptors.xml
```

仓库自带包含 SHA-256 摘要的 `manifest.json`，加载模型前会始终校验所有文件摘要。

## 安全提示

PKL/Joblib 文件在反序列化时会执行代码；请仅加载来自可信来源的资产。
