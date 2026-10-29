# 使用手册（v0.1）

## 1. 安装

```bash
cd persona-runtime
python -m venv .venv          # 已在 D:\变人\.venv
.venv\Scripts\pip install -e ".[dev]"   # 或直接 pip install -r 依赖
```

依赖只有 `pydantic / httpx / pyyaml`（开发加 `pytest / ruff`）。国内镜像：

```bash
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 2. 自检

```bash
par doctor
par providers
```

`doctor` 检查 config、人格卡、providers、数据库四件事；任一项失败返回退出码 2。

## 3. 接模型

`configs/providers.yaml` 已有五档：

| 名称 | kind | 说明 |
|---|---|---|
| `ollama` | ollama | 本地 `http://127.0.0.1:11434/v1`，默认 `qwen3:8b` |
| `deepseek` | deepseek | `https://api.deepseek.com/v1`，读 `DEEPSEEK_API_KEY` |
| `openai` | openai | `https://api.openai.com/v1`，读 `OPENAI_API_KEY` |
| `anthropic` | anthropic | Claude Messages API，读 `ANTHROPIC_API_KEY` |
| `fake` | fake | 离线确定性回复，用于测试与演示 |

选择方式（优先级从高到低）：命令行 `--provider/--model` > `runtime.yaml` 的 `provider/model`。

## 4. 三种对话入口

```bash
par chat                      # 终端 REPL：/state /audit /exit
par say "你好"                # 单轮
par serve --port 7860         # 浏览器 + HTTP
```

`serve` 同时提供：

- `GET /` 内置聊天页（含朗读按钮）
- `GET /health`、`GET /v1/models`
- `POST /v1/chat/completions` — OpenAI 兼容，可直接接 OpenAI SDK、DeepSeek Harness 之类客户端
- `POST /api/chat` — `{message}` → `{reply, labels, memories, audit_seq}`
- `POST /v1/audio/speech` — `{input}` → WAV（Windows SAPI；不可用返回 501）

OpenAI 兼容示例：

```bash
curl http://127.0.0.1:7860/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"par-lin_xi_v1","messages":[{"role":"user","content":"在吗"}]}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:7860/v1", api_key="unused")
print(client.chat.completions.create(
    model="par-lin_xi_v1",
    messages=[{"role": "user", "content": "还记得我吗？"}],
).choices[0].message.content)
```

注意：这个端点把**一个进程**当**一个会话流**。多用户隔离属于部署层；v0 是单用户本地运行时。

## 5. 人格卡

`configs/personas/linxi.yaml`。字段约束：

- 14 个 trait 必须齐全且 ∈[0,1]
- `values.protect_humans` 必须 **1.0**（改不了，写入时校验）
- `boundaries` 至少一条，`voice_style` 非空
- `deviation_propensity` ∈[0,1]

改人格请走 `par update`（见 `docs/updates.md`），不要直接改正在用的文件——版本指针会覆盖你的编辑。

## 6. 数据位置

| 路径 | 内容 |
|---|---|
| `data/<agent>.db` | 记忆、承诺、affect 快照、审计链、版本指针 |
| `data/versions/<agent>/<kind>/*.yaml` | 已批准的版本快照 |
| `configs/` | 声明式配置（人读，不存运行状态） |

## 7. 审计

```bash
par audit verify     # 逐条重算哈希链，检查 prev 链接
par audit head       # 最新一条
```

审计表包含：seq、run_id、kind、record_json、prev_hash、record_hash。任何一行的 `record_json` 被改都会在 `verify` 时报 `AuditIntegrityError`。

## 8. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `provider_not_found` | `runtime.yaml` 的 provider 不在 providers.yaml | `par providers` 看可用名 |
| 401/403 | API key 环境变量没设 | 设置对应 `*_API_KEY` |
| 记忆召回为空 | 首轮无历史；或文本为纯表情 | 正常，第二轮起会召回 |
| 中文乱码 | Windows 控制台 GBK | 设 `PYTHONIOENCODING=utf-8`，或只用 Web 页 |
| `/v1/audio/speech` 501 | 非 Windows 或无 SAPI 语音 | 预期降级，改用文字 |
