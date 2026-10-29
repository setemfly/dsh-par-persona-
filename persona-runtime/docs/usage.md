# 使用手册（v0.2）

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

另有一个 DSH 插件把同一运行时暴露成 `par_chat / par_status / par_tools / par_audit_verify` 四个工具，见 `../../dsh-par-persona/README.md`。它和这三种入口共用同一个 `data/<agent>.db`，所以从 DSH 聊过的内容，`par chat` 里也记得。

`serve` 同时提供：

- `GET /` 内置聊天页（含朗读按钮）
- `GET /health`、`GET /v1/models`
- `POST /v1/chat/completions` — OpenAI 兼容，可直接接 OpenAI SDK、DeepSeek Harness 之类客户端
- `POST /api/chat` — `{message}` → `{reply, labels, memories, audit_seq, verifier_ok, intent, gate_verdict, executed, deviation}`
- `GET /api/state` — 人格版本、情绪通道、轮数、审计链头
- `GET /api/tools` — 当前注册的内置工具（名称、副作用等级）
- `GET /api/audit/verify` — 重算哈希链；链坏时返回 409
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

## 4.1 工具、评估与记忆维护

```bash
par tools list                 # 当前工具与副作用等级
par eval --file evals/scenarios.yaml   # 9 条离线场景；有失败返回退出码 2
par memory stats               # 记忆条数
par memory consolidate         # 把相似 episode 聚成 semantic/reflection
```

内置工具只有三个，全部只读：

| 工具 | 副作用 | 说明 |
|---|---|---|
| `time.now` | none | 本地时间（可传 `tz`） |
| `calc.eval` | none | 四则/幂运算，AST 白名单，指数 ≤64 |
| `fs.read` | read | 只读 `<workspace>` 内文件，最多 64 KiB、返回前 4000 字符 |

请求进入编排时先由确定性路由判断意图（时间/算术/读文件/对话），再走门控（`PolicyEngine`）与执行器（幂等、超时、kill switch）。未获批准的计划只会有 `denied`，不会执行。场景说明见 `docs/evals.md`。

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
