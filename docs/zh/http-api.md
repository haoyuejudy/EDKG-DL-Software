# HTTP API

需要安装 `api` extra：`pip install "edkg-dl[api]"`。

## 启动服务

```bash
EDKG_DL_ASSET_DIR=./models edkg-dl-api   # 默认监听 127.0.0.1:8000
edkg-dl-api --host 0.0.0.0 --port 8000   # 通过 CLI 参数指定监听地址与端口
```

配置项：

| 类型 | 名称 | 默认值 | 说明 |
| --- | --- | --- | --- |
| CLI 参数 | `--host` | `127.0.0.1` | 监听地址 |
| CLI 参数 | `--port` | `8000` | 监听端口 |
| 环境变量 | `EDKG_DL_ASSET_DIR` | — | 资产目录（完整解析顺序见[模型资产](assets.md)） |

`edkg-dl-api -v` 查看版本号。

## 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 存活探针，不依赖模型推理 |
| GET | `/ready` | 配置就绪状态与已缓存模型数 |
| GET | `/v1/model-info` | 事件规模与因果链策略 |
| POST | `/v1/predictions` | 单分子预测 |
| POST | `/v1/predictions/batch` | 批量预测，每批最多 100 条 |

## 示例

单条预测：

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CCO"}'
```

批量预测（`smiles` 为 1–100 条的列表，`max_workers` 取值 1–8）：

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions/batch \
  -H "Content-Type: application/json" \
  -d '{"smiles": ["CCO", "CCN"], "max_workers": 4}'
```

响应结构与 JSON 报告一致（见[输出格式](output.md)）。预测失败返回 422，附带 `{"detail": {"code", "message"}}`；超出批量上限返回 413。交互式文档位于 `/docs`（FastAPI 默认）。
