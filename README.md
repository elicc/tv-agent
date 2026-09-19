# tv-agent

面向 TV 客户端的影视元数据解析服务。项目使用 Python、uv 和 FastAPI，后续将承载
Douban 查询、确定性匹配以及通过 OpenAI-compatible DeepSeek 模型完成的受限智能补救。

## 当前状态

当前提供 Douban 查询、确定性匹配、DeepSeek 受限解析循环、SQLite 缓存和
可选 Bearer 认证。模型仅在普通匹配无结果或存在歧义时参与，且不能选择 Douban
未真实返回过的 ID。

## 本地运行

```bash
cp .env.example .env
uv sync --locked --dev
uv run tv-agent
```

访问：

- 健康检查：`http://127.0.0.1:8000/healthz`
- 元数据解析：`POST http://127.0.0.1:8000/api/v1/metadata/resolve`
- OpenAPI：`http://127.0.0.1:8000/docs`

未配置 API Key 时服务仍可启动，健康检查会将对应能力标记为未配置。

## 验证

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

## 配置

所有运行配置使用 `TV_AGENT_` 前缀，参考 `.env.example`。真实 `.env` 已被 Git 忽略，
不得提交任何 Douban、模型或客户端认证密钥。

`TV_AGENT_SERVICE_API_KEY` 为空时允许无认证的局域网调用；公网部署时应配置该值，
客户端通过 `Authorization: Bearer <key>` 传递。HTTP 与 HTTPS 共用同一 API 契约。

## 请求示例

```bash
curl http://127.0.0.1:8000/api/v1/metadata/resolve \
  -H 'Content-Type: application/json' \
  -d '{
    "sourceInstanceId": "site-key",
    "sourceVodId": "vod-id",
    "title": "逃出绝命街（臻彩）",
    "year": "2023",
    "allowAgent": true
  }'
```

## 仓库集成

主 TV 项目通过根目录 `tv-agent` Git submodule 引用此仓库。首次拉取主项目后执行：

```bash
git submodule update --init --recursive
```
