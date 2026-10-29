# PAR v2 · 人格-能动性运行时

整合 Claude 版 `android_agent_brain_spec.md` 与 ChatGPT 版 `persona_and_agency_runtime_specification.md` 后的**唯一施工依据**。

| 文件 | 说明 |
|---|---|
| [`PAR-v2-spec.md`](PAR-v2-spec.md) | 合并 + 改进后的完整规格（v2.0，约 1900 行，20 章 + 4 附录） |
| [`persona-runtime/`](persona-runtime/README.md) | 按规格实现的可运行工程（v0.2：CLI / Web / OpenAI 兼容端点 / 审计链 / 受治理更新 / 工具执行 / 偏离判定 / 评估场景） |
| `android_agent_brain_spec.md` | 来源 A（保留，仅作研究附录，不再作为实现依据） |
| `persona_and_agency_runtime_specification.md` | 来源 B（同上） |

## 这份规格解决了什么

两份来源各自的强项被保留，冲突处给出裁决与理由（§19）：

- **分层**：A 的 L1–L8 模块分层 + B 的"权威/估计/生成/表达"四类状态（正交维度）。
- **记忆**：A 的 `tier` 与 B 的 `kind` 合并，加入双时相、敏感级、隔离状态；承诺升为一等实体（精确键检索优先）。
- **情感**：PAD 作表达核心 + 9 通道状态，统一指数衰减 `λ=ln2/T½`，快慢变量分层，单次步长有界。
- **偏离**：六类 → 七值（新增 `follow_with_caveat`），并把"安全拒绝 / 人格偏离 / 表达政策"拆成三个独立生产者——安全拒绝不再被误读为角色情绪。
- **门控**：九项检查、固定顺序、fail-closed；审批绑定 `plan_hash` + TTL；LLM critic 只能收紧。
- **审计**：哈希链 + 外部锚 + 可重放（cassette）+ 只读自述接口；明确禁止记录隐藏思维链。
- **裁剪**：删掉卡尔曼滤波、完整 OCC、图数据库、技能自动生成等过度设计（§19.4），并给出重启条件。

## DSH 插件

[`dsh-par-persona/`](dsh-par-persona/README.md) 把运行时接进 DeepSeek Harness：四个工具 `par_chat`（对话，带 intent/gate/step 流水线）、`par_status`（人格/情绪/审计头）、`par_tools`（内置工具清单）、`par_audit_verify`（校验审计链）。插件只做生命周期与 HTTP 转发，首次调用时自动拉起 `python -m par serve` 子进程；已安装进 `web` profile 并实测通过（DeepSeek provider）。

## 工程进度

工程已开工，位置 [`persona-runtime/`](persona-runtime/README.md)：

- 已跑通：配置/人格卡、记忆（SQLite+FTS5+本地哈希嵌入混合检索）、情感引擎、单轮编排（SENSE→…→CONSOLIDATE）、表达校验、门控九检、工具执行器（time.now / calc.eval / fs.read）、偏离判定、记忆巩固、审计哈希链、CLI、Web 聊天、OpenAI 兼容端点、Windows TTS、受治理版本化更新、9 条离线评估场景。
- 测试：`pytest -q` 60 passed，`ruff` 全绿，全部离线（FakeProvider）；另有 `par eval` 场景与真实 DeepSeek 冒烟。
- 仍为骨架：多步计划、审计重放、STT 接线、向量库后端（见 [`persona-runtime/docs/progress.md`](persona-runtime/docs/progress.md)）。

下一步按 `docs/progress.md` 末尾的顺序推进：多步计划 → 重放 → 向量库后端 → 消融评估 → 语音闭环。

> 纪律：没有测试的模块等于不存在；LLM 只提议，确定性代码处置。

