# 进度与范围（v0.2）

对应规格 §17 里程碑。**诚实标注**：哪些是真的，哪些仍是骨架。

## 已可运行

| 里程碑 | 内容 | 状态 | 位置 |
|---|---|---|---|
| M0 | 配置、schema、审计哈希链、CLI、测试 | ✅ | `config/` `schemas/` `audit/` `__main__.py` |
| M1 | 人格卡 + 工作/情景记忆 + 混合检索（词法+嵌入+近因+重要性+目标+置信） | ✅ | `identity/` `memory/` |
| M2 | 情感引擎（9 通道衰减+冲量+抗抖动）与启发式评估 | ✅ | `affect/` |
| M3 | 单轮编排 SENSE→RECALL→APPRAISE→PLAN→GATE→EXECUTE→DEVIATE→EXPRESS→AUDIT→CONSOLIDATE | ✅ | `orchestrator/agent.py` |
| M3' | 表达校验（无依据行动声称/内部状态泄漏）+ 一次纠正重试 | ✅ | `expression/` |
| M4 | 计划（确定性路由）/ 门控九检 / 执行器（幂等、超时、kill switch、部分失败） | ✅ v0：三个内置只读工具 | `planning/` `policy/` `execution/` |
| M5 | 偏离判定器（七值、冲突分类、节流、硬安全立即生效） | ✅ | `policy/deviation.py` |
| M6 | 审计哈希链、verify、锚点、自述口径 | ✅ 哈希链 + verify；重放未做 | `audit/log.py` |
| M7 | 本地 Web 聊天 + OpenAI 兼容端点 + `/api/tools` + 语音 TTS | ✅ | `server/` `voice/` |
| M8 | 受治理版本化更新（propose→approve→apply→rollback） | ✅ | `updates/` |
| M9 | 离线评估场景（9 条 YAML，`par eval`） | ✅ | `evals/` |

测试：60 个，`pytest` 全绿；`ruff` 全绿。离线 `FakeProvider` 覆盖编排、路由、执行器、偏离、巩固、审计、策略、更新、HTTP、评估。

## 设计取舍（为什么这样接）

- **规划器是确定性的**：时间/算术/读文件三类意图用正则路由，其余走对话。理由：先用最小实现证明「计划 → 门控 → 执行 → 审计」契约，而不是把工具选择交给模型自由发挥。
- **工具只读、白名单**：`time.now` / `calc.eval`（AST 白名单，禁用属性与名称调用）/ `fs.read`（工作区沙箱，64 KiB 上限）。没有 shell、没有网络、没有写操作。
- **偏离判定在门控之后**：先判断"能不能做"，再判断"我愿不愿意、要不要设边界"。硬安全冲突立即生效，不受 `min_sustain_s` 约束（否则危险请求会先被执行一次）。
- **嵌入是本地哈希向量**（256 维 char tri/bi-gram 符号桶），不依赖模型服务，可重放；`W_SEMANTIC=0.30` 与词法分数混合。
- **记忆巩固按需触发**：每 `consolidate_every_turns`（默认 20）轮把相似 episode 聚成 `semantic/reflection`，源记忆保留，可追溯。

## 仍是骨架

- **STT**：接口 + 可选 faster-whisper，未接 Web 录音。
- **重放**：审计可校验完整性，尚无「按 cassette 重跑一回合」的工具。
- **多步计划**：schema 允许 1–8 步，路由只产出单步；多步编排留给 M4 后续。
- **自我更新**：仅 CLI 人工路径（propose→approve→apply），模型无写入口（设计如此）。

## 明确不做（v0 范围栅栏）

- 不做代码自修改、不做自建模型、不做多智能体。
- 不做云 TTS/云 STT 默认路径。
- 不做多用户隔离（单进程 = 单会话流）。
- 不主张意识/主观体验；情感是计算状态，不是感受。

## DSH 插件（v0.2.0）

[`../../dsh-par-persona/`](../../dsh-par-persona/README.md) 把运行时接进 DeepSeek Harness，已安装进 `web` profile 并实测：

- 四个工具：`par_chat` / `par_status` / `par_tools` / `par_audit_verify`；首次调用 spawn `python -m par serve`，dispose 时关闭。
- `par_chat` 的渲染带 `[pipeline]` 行：`intent` / `gate` / `steps` / `deviation`，便于在 DSH 里看到这一轮是否真的调用了工具。
- provider 走 `configs/providers.local.yaml`（不入库）→ DeepSeek `deepseek-chat`；本机 ollama 只有 embedding 模型，故从 ollama 切到 DeepSeek。
- 记忆写入幂等强化：同 `(agent, kind, text)` 的 active 记录只 `version+1` 不新增行。

## 下一步建议

1. 多步计划：把路由扩展到「读文件 → 计算 → 总结」这类两步链，验证部分失败与重规划。
2. 重放：用审计里的 `inputs_digest` + cassette 记录，支持 `par replay --seq N`。
3. 向量检索升级：`MemoryStore` 端口不动，后端换 sqlite-vec 或 pgvector。
4. 评估扩展：把 §16 的 8 组消融（A0–A7）落成 `par eval --ablation`。
5. 语音：Web 录音 → STT → 同一编排入口。
