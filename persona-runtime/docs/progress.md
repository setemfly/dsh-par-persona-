# 进度与范围（v0.1）

对应规格 §17 里程碑。**诚实标注**：哪些是真的，哪些是骨架。

## 已可运行

| 里程碑 | 内容 | 状态 | 位置 |
|---|---|---|---|
| M0 | 配置、schema、审计哈希链、CLI、测试 | ✅ | `config/` `schemas/` `audit/` `__main__.py` |
| M1 | 人格卡 + 工作/情景记忆 + 检索（语义/近因/重要性/目标/置信） | ✅ 词法版 | `identity/` `memory/store.py` |
| M2 | 情感引擎（9 通道衰减+冲量+抗抖动）与启发式评估 | ✅ | `affect/` |
| M3 | 单轮编排 SENSE→RECALL→APPRAISE→EXPRESS→AUDIT→CONSOLIDATE | ✅ | `orchestrator/agent.py` |
| M3' | 表达校验（无依据行动声称/内部状态泄漏）+ 一次纠正重试 | ✅ | `expression/` |
| M4 | 计划/门控/执行 schema + 门控九检 + 审批绑定 plan_hash | ✅ 门控；执行器 v0 空转 | `policy/` `execution/` |
| M5 | 偏离协议枚举/信封/冲突分类 | ✅ schema；判定器未接 turn | `schemas/core.py` |
| M6 | 审计读、回放锚点、自述 | ✅ 哈希链 + verify；replay 未做 | `audit/log.py` |
| M7 | 本地 Web 聊天 + OpenAI 兼容端点 + 语音 TTS | ✅ | `server/` `voice/` |
| M8 | 受治理版本化更新（propose→approve→apply→rollback） | ✅ | `updates/` |

测试：30 个，`pytest` 全绿；离线 `FakeProvider` 覆盖编排、记忆、审计、策略、更新、HTTP。

## 骨架（有接口，未接线）

- **Planner/Executor**：schema 与门控完整，`Agent.turn` 目前只走"回复"单步。接工具执行是 M4 剩余部分。
- **偏离判定器**：七值枚举与信封在 schema 层，`PersonaDeviation` 尚未在 turn 中产出决策。
- **STT**：接口 + 可选 faster-whisper，未接 Web 录音。
- **嵌入检索**：v0 用 FTS5 词法；`embedding` 字段与评分位已留，接向量库是 v1。
- **自我更新**：仅 CLI 人工路径，无模型可调用的写入口（设计如此）。

## 明确不做（v0 范围栅栏）

- 不做代码自修改、不做自建模型、不做多智能体。
- 不做云 TTS/云 STT 默认路径。
- 不做多用户隔离（单进程 = 单会话流）。
- 不主张意识/主观体验；情感是计算状态，不是感受。

## DSH 插件（已完成）

[`../dsh-par-persona/`](../dsh-par-persona/README.md) 把运行时接进 DeepSeek Harness，已安装进 `web` profile 并实测：

- 三个工具：`par_chat` / `par_status` / `par_audit_verify`；首次调用 spawn `python -m par serve`，dispose 时关闭。
- provider 走 `configs/providers.local.yaml`（不入库）→ DeepSeek `deepseek-chat`；本机 ollama 只有 embedding 模型，故从 ollama 切到 DeepSeek。
- 记忆写入加了幂等强化：同 `(agent, kind, text)` 的 active 记录只 `version+1` 不新增行（长会话会重放相似回合）。

## 下一会话建议顺序

1. M4 执行器：`execution/executor.py` + 内置只读工具（时间、计算、文件读），全部过 `PolicyEngine.check`。
2. M5 偏离判定器：`persona_deviation.py`，消费 `DeviationEnvelope` 与 `Appraisal`。
3. 记忆巩固：`consolidate()` 把 episode 聚类成 semantic（离线批处理，先按实体/关键词）。
4. 向量检索：`MemoryStore` 端口后接 sqlite-vec 或 pgvector，评分公式不变。
5. 评估场景：`evals/` + 场景 YAML，跑 §16 的回归门禁。
