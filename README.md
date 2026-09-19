# tv-agent

面向 TV 客户端的影视元数据解析服务。项目使用 Python、uv 和 FastAPI，后续将承载
Douban 查询、确定性匹配以及通过 OpenAI-compatible DeepSeek 模型完成的受限智能补救。

## 当前状态

当前提供可运行的服务骨架和健康检查。Douban 与模型解析 API 将按领域边界逐步接入，
避免在初始化阶段把网络提供方、Agent 编排和 HTTP 协议耦合在一起。

## 本地运行

```bash
cp .env.example .env
uv sync --locked --dev
uv run tv-agent
```

访问：

- 健康检查：`http://127.0.0.1:8000/healthz`
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

## 仓库集成

主 TV 项目通过 `services/tv-agent` Git submodule 引用此仓库。首次拉取主项目后执行：

```bash
git submodule update --init --recursive
```
