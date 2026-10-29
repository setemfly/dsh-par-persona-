# par — persona runtime

把 `PAR-v2-spec.md` 落成可运行的本地人格运行时。**单进程、单会话、离线优先**。

```bash
cd persona-runtime
par doctor                 # 配置 / 人格卡 / providers / 数据库自检
par providers              # 看已配置的模型后端
par chat                   # 终端对话（REPL）
par serve --port 7860      # 浏览器聊天 + OpenAI 兼容端点
```

## 它是什么

| 层 | 目录 | 说明 |
|---|---|---|
| 状态契约 | `src/par/schemas/core.py` | 全部 Pydantic 模型，`extra="forbid"`，`protect_humans` 不可改 |
| 模型接入 | `src/par/llm/` | OpenAI 兼容 / Anthropic / Fake；`par.providers` entry point 可装插件 |
| 记忆 | `src/par/memory/store.py` | SQLite + FTS5（CJK 逐字分词），五因子排序 |
| 情感 | `src/par/affect/` | 9 通道指数衰减 + 单步有界；启发式评估 |
| 表达 | `src/par/expression/` | 系统提示构建 + 事实性校验（无依据行动 / 隐藏状态泄漏） |
| 门控 | `src/par/policy/engine.py` | 九项检查、fail-closed、审批绑定 plan_hash |
| 编排 | `src/par/orchestrator/agent.py` | 单轮 SENSE→…→CONSOLIDATE |
| 审计 | `src/par/audit/log.py` | SHA-256 哈希链 + 锚点，`verify()` 逐条重算 |
| 服务 | `src/par/server/` | stdlib HTTP，内置页面，`/v1/chat/completions` |
| 语音 | `src/par/voice/` | Windows SAPI TTS；STT 可选 faster-whisper |
| 更新 | `src/par/updates/` | 版本化 propose→approve→apply→rollback（无代码自改） |

## 接入其他程序

任何能说 OpenAI 协议的东西都可以直接指过来：

```python
from openai import OpenAI
c = OpenAI(base_url="http://127.0.0.1:7860/v1", api_key="unused")
c.chat.completions.create(model="par-lin_xi_v1", messages=[{"role":"user","content":"在吗"}])
```

DeepSeek Harness / ChatGPT 类前端同理：填 base URL + 任意 key，模型名用 `/v1/models` 返回的 `par-<persona>`。

## 测试

```bash
pytest -q          # 30 passed，全部离线（FakeProvider）
par audit verify   # 审计链自检
```

## 文档

- [`docs/usage.md`](docs/usage.md) — 安装、provider、三种入口、排错
- [`docs/updates.md`](docs/updates.md) — 受治理自我更新
- [`docs/voice.md`](docs/voice.md) — 语音边界与降级
- [`docs/progress.md`](docs/progress.md) — 里程碑实现状态与下一步

## 边界（先说清楚）

- 不做代码自修改：更新是 persona/policy/config 的版本替换，人工批准。
- 不主张意识：情感是计算状态，不是主观感受。
- 单进程单会话：不做多用户隔离，那是部署层的事。
- 词法检索优先于向量：`embedding` 字段留好，v1 再接。

> 纪律：没有测试的模块等于不存在；LLM 只提议，确定性代码处置。
