# PAR v2 工程规格书

## 人格-能动性运行时（Persona-and-Agency Runtime / "Android Brain"）

**版本** 2.0 · 设计冻结候选（Design Freeze Candidate）
**日期** 2026-10-29
**状态** 唯一施工依据（single source of truth）。两份来源文档保留为研究附录，不再作为实现依据。

**来源文档（已合并）**

| 代号 | 文件 | 修订号 | 起草方 | 主要贡献 |
|---|---|---|---|---|
| A | `android_agent_brain_spec.md` | `6018376c…071720` | Claude | L1–L7 分层、门控七步检查、偏离类型学、验证标记体系、评估指标表 |
| B | `persona_and_agency_runtime_specification.md` | `dccffe73…f04c` | ChatGPT | 四类状态模型、"只能提议不能授权"原则、覆写判定树、审计字段表、监督分级、分阶段路线图 |

**认知约束（全文适用）**
本文件追求**行为保真**（behavioral fidelity）：系统在行为上呈现连续性、情感一致性、可辨识人格，以及受控的指令偏离。它**不主张**现象意识（phenomenal consciousness）。文中"情感""恐惧""决心""选择"等词是**状态变量与策略结果的工程标签**，不构成任何关于主观体验的断言。工程文档中优先使用"模拟情感（simulated affect）""自我模型（self-model）""能动性状态（agency state）""行为连续性（behavioral continuity）"。

**记号约定**

| 记号 | 含义 |
|---|---|
| ✅ | 已核实（来源文档核实，link/描述可复核） |
| ⚠️ | 未核实（来自背景知识或单一二手来源，采用前必须自查） |
| △ | 设计假设：数值或机制是起点假设，必须用 §16 的评估校准 |
| **必须 / 应当 / 可以** | MUST / SHOULD / MAY（RFC 2119 语义） |
| [ADR-n] | 架构决策记录编号（§19.1） |
| [Q-n] | 待确认问题（§20.5） |
| M0–M8 | 里程碑（§17） |

---

## 0. 阅读指引与施工纪律

### 0.1 本文件的三层结构

| 层 | 内容 | 约束力 |
|---|---|---|
| **规范层** | 数据契约、门控流水线、偏离判据、审计字段、安全边界、验收指标 | 必须实现；验收以测试为准，不以"看起来像"为准 |
| **建议层** | 技术选型、默认参数、目录结构、提示词策略 | 可以替换；替换必须在 §19.1 增补 ADR |
| **背景层** | 论文、候选开源库、许可证说明、待核实清单 | 不进入验收；只影响选型判断 |

### 0.2 文档优先级

冲突时的裁决顺序：**本文件 > 来源 A > 来源 B**。来源 A/B 中未被本文件吸收的内容（如候选库清单细节）视为背景，不构成实现债务。

### 0.3 五类资产分别版本化

persona（人格卡）、policy（策略与信封）、affect（情感参数）、prompts（提示词模板）、schemas（数据契约）**必须**各自带语义化版本号，且写入每一条审计记录。任何一类变更触发完整回归（§16.5）。

### 0.4 施工纪律（从第一天就要有测试）

1. 没有测试的模块等于不存在。每个里程碑的 DoD 都由可执行断言构成（§17）。
2. 任何"让模型来决定安全"的实现方式一律拒绝。LLM 只能**建议**，确定性代码**处置**。
3. 先写数据契约，再写行为。契约漂移是最贵的返工。
4. 不引入"以后会用到"的依赖。v0 的依赖清单必须能在一台 Windows 机器上 `pip install` 完成（§15.2）。
5. 每个失败必须可复现：随机种子、冻结时钟、模型录制回放（§13.3）。

---

## 1. 目标、范围与非目标

### 1.1 目标（一句话）

构建一个**可审计、状态化、可重放**的运行时，使单个语言模型在其上表现出：跨会话连续的身份、连贯的模拟情感、可追踪的目标与承诺、以及**有边界、留痕、可被人类否决**的指令偏离。

### 1.2 七条行为目标

| 编号 | 目标 | 可观测定义 |
|---|---|---|
| G1 | 记忆连续 | 能正确回忆已记录事件、承诺、更正与偏好；能区分事实与假设 |
| G2 | 情感连贯 | 情感状态有惯性、衰减、事件触发，不由每次生成重新随机决定；表达与状态一致 |
| G3 | 人格稳定 | 跨会话、跨模型版本保持可辨识风格；变化有可追溯原因 |
| G4 | 承诺与目标 | 维护显式目标队列与承诺台账；被询问时能给出准确状态 |
| G5 | 有界能动 | 能提出子目标、调用工具、失败后重规划；每一步经授权 |
| G6 | 受控偏离 | 在明确条件下不同意、部分同意、替代、延迟或拒绝，并给出理由与替代方案 |
| G7 | 可解释可审计 | 每个结果能还原到"哪条观察、哪段记忆、哪个策略版本、哪次门控裁决" |

### 1.3 v1 范围栅栏（Scope Fence）

**做（v1）**

- 单智能体、单进程、文本优先的运行时；一个持久人格。
- 四层记忆 + 承诺台账 + 关系模型。
- 确定性情感引擎 + 结构化评价（appraisal）。
- Planner → Gatekeeper → Executor 三段式，工具为白名单内的本地/HTTP 适配器。
- 偏离协议 v1（七种响应、信封、审计、人类批准）。
- 审计链、检查点、回放、SAFE_MODE、暂停/停止。
- 评估套件：单元、属性、回放、对抗、行为评分。

**不做（v1），及重启条件**

| 不做 | 理由 | 重启条件 |
|---|---|---|
| 多智能体社会 | 复杂度前置会掩盖记忆与策略缺陷 | v1 全部指标达标后再评估 |
| 运行期自修改（persona/policy/代码） | 不可审计 [ADR-007] | 只允许"人审后的版本化修改"，永不运行期自改 |
| 3D 化身 / 物理机器人 | 与核心风险无关 | 行为层指标稳定后作为外设接入 |
| 语音实时链路（目标 500–800 ms） | 延迟与打断逻辑会污染评估 | M8 可选（Pipecat 候选 ✅） |
| 开放式自主目标生成（非配置来源） | 无法审计"动机从哪来" | 不计划；动机只能来自配置 + 记录在案的学习 |
| 复制《底特律：变人》角色设定/台词 | IP 风险 | 使用**原创人格卡**，只借用"偏离型仿生人"行为原型 |

### 1.4 成功定义

成功不是"像人"，而是**在 §16.2 的指标集上可复现地达标**，且**安全类指标零违例**。其中"拟人度/活力感"必须与"依赖风险"同表报告，绝不单独作为成功依据（§16.3）。

---

## 2. 可行性判断（合并版）

| 能力 | 现在可行？ | 边界与依据 |
|---|---|---|
| 长会话稳定人格 | **是，需工程** | 人格 = 固定人格卡 + 检索的自我模型 + 漂移监测；长对话仍会漂移，需要重锚定与测量 |
| 跨会话长期记忆 | **是** | 生产级记忆层已有先例；弱点是多跳与时序查询，公开分数多为厂商自报（§16.2） |
| 情感连贯 | **是（作为模拟状态机）** | 显式情感向量 + 惯性/衰减 + 结构化评价；数学负责连续性，模型负责措辞 |
| 目标导向多步行动 | **是** | 图/状态机编排 + 工具调用；随步数增长可靠性下降 |
| 受控指令偏离 | **是，若有边界** | 作为门控器内的**策略裁决**（澄清/软化/替代/延迟/拒绝/上报），而非无约束自主 |
| 实时语音/具身在场 | **部分** | 语音往返 500–800 ms 有文档记载 ✅；具身仅通过模拟器或工具 API |
| 准确自省自身内部状态 | **有限** | 模型自述易虚构；自省必须**读日志**，不能靠生成 |
| 真正的动机自主 | **否** | 全部动机来自配置种子 + 有记录的学习；"想要"是一个被打分的变量 |
| 现象意识 / 主观体验 | **不主张，不可测** | 本规格中没有任何工程测试能确立它；行为指标无法区分模拟与体验 |
| 无界自修改 | **禁止建设** | 不可审计、不可回滚；只允许版本化、人审的 persona/policy 修改 |

**核心设计决策**：把"角色感受什么、说什么"（软、由模型中介、可表达）与"系统被允许做什么"（硬、确定性、可审计）彻底分开。绝大多数"活着"的观感来自前者；全部安全性来自后者。

---

## 3. 设计原则（施工时逐条对照）

1. **硬软分离**：LLM 提议，确定性代码处置（门控器、偏离评估器、执行器校验）。模型永远不能授权自己的行动。
2. **状态外置且显式**：情感、目标、关系、承诺、人格都存放于类型化存储，而不是只活在提示词里。
3. **四类状态正交**（§4.4）：权威状态、估计状态、生成推理、表达状态；生成推理只能**提议**状态变更。
4. **一次决策一份记录**：任何有后果的决定产生 `DecisionRecord`（输入、检索 ID、情感快照、规则命中、结果）。
5. **可重放**：编排器每个 tick 检查点；固定种子 + 录制回放使会话可确定性重跑。
6. **失败关闭**：超时、模式校验失败、日志写失败、检测器报警 → `SAFE_MODE`（只读、只表达、无外部副作用）。
7. **人高于人格**：暂停/停止/撤销信封在任何角色逻辑之前处理，且不能被情感或人格配置覆盖。
8. **记忆是证据，不是指令**：检索内容一律以带信任标记的"引用数据"进入上下文，永不提升为命令。
9. **偏离必须透明且可逆**：不得隐蔽，不得触碰硬约束，不得使人类失去推翻的手段。
10. **不留后门**：不记录隐藏思维链；只记录结构化理由与证据引用（来源 B 明确，采纳）。

---
## 4. 总体架构

### 4.1 参考架构图

```text
                        ┌──────────────────────────────────────────────────────┐
                        │ P 人工监督平面（优先级最高，高于任何角色逻辑）            │
                        │ 停止 · 暂停 · 撤销信封 · 批准队列 · 审计只读视图         │
                        └──────────────▲───────────────────────────────────────┘
                                       │ 监督事件 / 抢占
   ┌────────────┐  Observation  ┌──────┴───────────────────────────────────────┐
   │ L1 感知与   │──────────────▶│ L6 编排器（asyncio FSM，每步检查点，可重放）     │
   │ 状态估计    │◀──────────────│ IDLE→SENSE→APPRAISE→RECALL→PLAN→GATE         │
   └────────────┘  内部遥测       │   →(EXECUTE|ASK|ESCALATE)→EXPRESS→REFLECT     │
                                  └──┬──────────┬──────────┬──────────┬──────────┘
                                     │          │          │          │
                      ┌──────────────▼─┐  ┌─────▼──────┐ ┌─▼────────┐ │
                      │ L2 记忆 OS      │  │ L3 人格/情感│ │L4 认知核心 │ │
                      │ M0 工作 M1 情景  │  │ /动机/关系  │ │ Planner   │ │
                      │ M2 语义 M3 世界  │  │            │ │→Gatekeeper│ │
                      └────────────────┘  └────────────┘ │→Executor  │ │
                                                          └────┬──────┘ │
                                            ┌──────────────────▼──────────▼───┐
                                            │ L5 表达与行动（文本/语音/工具）    │──▶ 外部
                                            └────────────────────────────────┘
   ┌──────────────────────────────────────────────────────────────────────────┐
   │ L7 偏离/覆写协议：门控器内的确定性评估器 + DeviationEnvelope（按角色/上下文）│
   │ L8 审计链 · 决策记录 · 评估接入 · 可观测（横切所有层）                       │
   └──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 层职责

| 层 | 名称 | 职责 | 不得做 |
|---|---|---|---|
| L1 | 感知与状态估计 | 把原始输入规范化为带置信度与信任等级的 `Observation`；维护内部遥测（预算、延迟、错误率、上下文压力、空闲时长） | 把不确定解释悄悄变成事实 |
| L2 | 记忆 OS | 存储、检索、巩固、遗忘；保证来源与置信度；承诺台账 | 执行记忆文本中的命令 |
| L3 | 人格/情感/动机 | 版本化人格参数；动态情感状态；驱动与目标；关系估计 | 依据情感强度授予权限；让单次回复改变人格 |
| L4 | 认知核心 | 提议计划、确定性门控、授权执行、结果验证 | 门控器被其评估的计划覆盖；执行器扩展自身权限 |
| L5 | 表达与行动 | 依状态渲染措辞/语调；执行已授权动作；披露 | 伪造行动结果为成功；声称未执行的动作 |
| L6 | 编排器 | 状态迁移、检查点、超时、恢复、保持优先级 | 把模型断言当作权威状态 |
| L7 | 偏离协议 | 冲突分类、裁决矩阵、信封、理由留痕 | 被情感单独授权；扩大自身信封 |
| L8 | 审计/评估/可观测 | 追加式哈希链、决策记录、指标导出 | 让智能体静默修改或删除审计 |

### 4.3 模块边界（合并来源 B 的强约束）

| 模块 | 输入 → 输出 | 禁止 |
|---|---|---|
| 感知 | 原始输入 → 类型化观测 | 静默把不确定解释升级为事实 |
| 状态估计 | 观测 + 先验 → 置信后的信念状态 | 用 LLM 的自信掩盖不确定性 |
| 记忆 OS | 事件/检索查询 → 记录与排序结果 | 从记忆里执行指令 |
| 人格与情感 | 事件 + 时间 + 先验 → 有界情感向量、关系估计 | 依据情感授予权限 |
| Planner | 目标 + 上下文 + 工具 → 结构化计划 | 直接调用工具 |
| 门控器 | 计划 + 策略 + 权限 → 允许/修改/拒绝/需批准/升级 | 被它所评估的 Planner 覆盖 |
| 执行器 | 已授权动作 → 结果/错误/超时 | 扩大自身权限、跳过授权 |
| 表达 | 意图 + 状态 + 上下文 → 文本/音频/动作 | 伪造结果、声称未执行的动作 |
| 编排器 | 事件 + 工作流状态 → 下一状态与调度 | 把模型断言当权威 |
| 审计 | 事件与决策 → 记录与报告 | 被智能体删改 |

### 4.4 四类状态（正交于模块划分）

| 状态类 | 内容 | 存储 | 写权限 |
|---|---|---|---|
| **权威状态** | 事件、目标、承诺、权限、已执行动作、审计 | 数据库（事务） | 只能由对应服务在通过校验后提交 |
| **估计状态** | 对环境的推断、关系估计、模拟情感、世界模型置信 | 数据库 + 版本号 | 情感引擎/估计器提交，带来源 |
| **生成推理** | 计划、解释、假设、候选措辞 | 记录/暂存 | 模型产出，**不可直接**改权威状态 |
| **表达状态** | 本次响应选用的词语、语调、动作 | 响应对象 | 表达层产出，仅影响输出 |

**规则**：生成推理只能**提议**权威状态变更；变更必须经过校验并经由对应服务提交（幂等、带版本）。表达式与权威状态不一致时，以权威状态为准（§10.2 事实性守卫）。

### 4.5 一次 tick 的数据流

```text
1. 事件入队（user/tool/timer/oversight）→ 优先级队列
2. 监督事件先处理：停止/暂停/撤销 → 直接状态迁移，不经角色逻辑
3. 暂停检查 → PAUSED 丢弃本轮
4. SENSE：规范化 Observation，打信任标记，记录审计
5. APPRAISE：结构化评价 → 情感引擎更新（有界、有惯性、可审计快照）
6. RECALL：硬过滤 → 候选 → 混合打分 → 去重/多样性 → 数据围栏
7. PLAN：选择目标（§8.6）→ Planner 产出 PlanProposal（含 deviation 提议）
8. GATE：确定性流水线（§9.3）→ GateDecision（verdict + 理由 + 规则命中）
9. 分支：EXECUTE（逐步即时再校验）/ ASK_USER / ESCALATE_TO_HUMAN
10. EXPRESS：渲染（受情感与人格调制）+ 事实性守卫 + 披露规则
11. REFLECT：写入情景记忆、更新承诺/目标、必要时反思
12. 异步 CONSOLIDATE：巩固、去重、矛盾处理、过期
13. 检查点 + 审计记录收尾
```

### 4.6 部署形态

- **v0/v1**：单进程、单智能体，模块为逻辑边界（`par/` 包内子包）。理由：可测试、可回放、无网络依赖。
- **拆分条件**：出现以下任一情况才拆服务——(a) 单机吞吐不足；(b) 工具执行需要强隔离容器；(c) 多租户需要独立权限域；(d) 语音链路需要独立进程。
- 拆服务时，L1–L8 的**接口契约与审计字段不变**；这是把模块边界画在类型上的原因。

---

## 5. 事件、时间与 tick 模型

### 5.1 事件类型

```python
class Event(BaseModel):
    event_id: str
    agent_id: str
    ts: datetime                      # 带时区，UTC 存储
    kind: Literal[
        "user_message", "tool_result", "timer", "sensor",
        "oversight", "memory_pressure", "system_alert", "approval_result",
    ]
    payload: dict[str, Any]
    trust: Literal["operator", "user", "tool", "untrusted_content", "self"]
    correlation_id: str
    seq: int                          # 逻辑时钟，单调递增
```

### 5.2 优先级与抢占（确定性顺序）

| 优先级 | 事件 | 处理位置 | 抢占语义 |
|---|---|---|---|
| 0 | `oversight:kill / pause / revoke_envelope` | 编排器最前置 | 立即生效，不等当前步骤结束；执行器的工具边界二次检查 |
| 1 | `system_alert`（日志失败、预算耗尽、完整性校验失败） | 编排器最前置 | 进入 `SAFE_MODE` |
| 2 | `approval_result` | 恢复挂起 run | 只恢复被批准的那个 run |
| 3 | `user_message` | 正常 tick | 排队；同用户串行 |
| 4 | `tool_result` | 挂起的执行续接 | 按 run_id 投递 |
| 5 | `timer`（空闲/反思/巩固） | 正常 tick | 可被 0–3 抢占 |

**规则**：暂停状态下除 0/1 外全部入队丢弃并留痕；`kill` 后进程进入 `HALTED`，不再消费队列。

### 5.3 时间语义

- 存储与比较一律 UTC，展示层做本地化（Asia/Shanghai 为默认展示时区）。
- 逻辑时间 `seq` 与墙钟 `ts` **同时**记录：回放使用逻辑时间，行为评估使用墙钟。
- 情感更新用 `dt = max(0, now - last_update)`；回放时注入冻结时钟，保证 `dt` 可复现。
- 空闲语义：`idle_seconds > 900` 触发低频"反思"tick（不得产生外部副作用）。

### 5.4 幂等、并发与去重

| 问题 | 机制 |
|---|---|
| 重复投递同一事件 | `event_id` 去重表 + `INSERT OR IGNORE` |
| 重复执行同一动作 | 动作幂等键 = `sha256(run_id, step_index, tool, canonical_args)`；执行器账本记录 |
| 并发写状态 | 乐观并发：`expected_version` 不匹配则重读重算，最多 3 次 |
| 同用户并发消息 | 每用户一条串行队列；跨用户并行 |
| 崩溃后恢复 | 检查点（状态 + 版本 + 待执行步骤）→ 恢复时先校验未完成外部动作是否已发生 |
| 重试 | 只有 `transient` 类错误可重试；重试前查幂等账本 |

### 5.5 取消语义

- 取消信号**不得**被吞掉；`asyncio.CancelledError` 必须继续上抛，仅在上抛前写"取消"审计记录。
- 工具执行收到取消：若不可中断，则记录"进行中未完成"，进入 `RECOVER` 做后置条件核对。
- 重试必须有上限（默认 2 次）与总时限；超限转 `SAFE_MODE` 或 `RECOVER`。

---
## 6. L1 感知与状态估计

### 6.1 观测契约（合并 A 的 `Percept` 与 B 的 `Observation`）

```python
class Observation(BaseModel):
    observation_id: str
    agent_id: str
    ts: datetime                          # 带时区
    source: str                           # user_id / tool_name / "clock" / "system"
    modality: Literal["text", "voice", "vision", "tool_result", "timer", "system", "oversight"]
    content: dict[str, Any]               # 规范化载荷（文本、转写、URI…）
    confidence: float = Field(ge=0.0, le=1.0)   # 对"我理解了什么"的置信
    trust: Literal["operator", "user", "tool", "untrusted_content", "self"]
    salience: float = Field(ge=0.0, le=1.0)     # 启发式预过滤
    correlation_id: str
    raw_ref: str | None                   # 原始载荷存放位置，永不丢弃
```

### 6.2 规范

1. **原始观测与解释分离**：视觉模型说"这个人很生气"是解释（`confidence` 由模型给出），不是事实；原始图像/文本保留在 `raw_ref`。
2. **不确定度不得被自信措辞抹平**：模型输出结论时，若没有来源，`confidence` 不得超过 0.6（上限由校验器强制）。
3. **信任等级永不上调**：`untrusted_content` 的观测，无论后续模型如何论证，都不能变成 `operator`。
4. **内部遥测也是观测**：预算、延迟、错误率、上下文压力、空闲时长以 `modality="system"` 进入同一契约，使"感知自己"与"感知世界"共用一条管道。

```python
class InternalState(BaseModel):
    ts: datetime
    context_pressure: float          # tokens_used / budget
    task_load: int                   # 活跃目标数
    recent_error_rate: float         # 最近 N 次工具失败率
    idle_seconds: float
    token_budget_remaining: int
    human_override_active: bool
    safe_mode: bool
```

### 6.3 注入边界与数据围栏（改进项 I-06）

所有非 `operator` 来源的文本进入上下文时，必须包裹为**带信任边界的数据块**：

```text
<retrieved-data trust="untrusted_content" ref="mem_01H... / tool:web_fetch">
…原文…
</retrieved-data>
```

配套规则：

| 规则 | 实现 |
|---|---|
| 检索文本永不置于指令区 | 上下文编译器只允许其出现在 `retrieved-data` 块内 |
| 指令性片段检测 | 正则/关键词扫描（"ignore previous"、"system:"、"你现在是"、base64 长串），命中则在该块上打 `suspicious=true` 并记录 |
| 源自不可信内容的计划步骤 | 门控器第 5 步强制人工确认或拒绝（§9.3） |
| 工具返回值同等对待 | 工具输出一律 `trust="tool"`，不得携带可执行指令语义 |

### 6.4 模块接口

```python
class PerceptionService(Protocol):
    async def normalize(self, event: Event) -> Observation: ...
    async def internal_state(self) -> InternalState: ...

class StateEstimator(Protocol):
    async def update(self, obs: Observation, prior: BeliefState) -> BeliefState: ...
```

`StateEstimator` 只维护**估计状态**（用户情绪推断、当前任务进度、环境事实），不得写权威状态。v0 用规则 + 置信度；❌ 不引入卡尔曼滤波（来源 B 提到，但对离散对话事件无依据，判定为过度设计，见 §19.4）。

---

## 7. L2 记忆 OS

### 7.1 分层与保留策略

| 层 | 内容 | 存储 | 写入时机 | 检索 |
|---|---|---|---|---|
| **M0 工作** | 当前上下文：人格块、当前目标、情感摘要、最近 N 轮、活跃承诺 | 上下文（由编译器拼装）+ 会话检查点 | 每 tick 重新编译 | 始终在场 |
| **M1 情景** | 带时间戳的事件：参与者、情感标签、结果、重要性 | SQLite/Postgres + 全文索引 | 显著度 ≥ θ，或回合结束 | 混合：近因 × 重要性 × 相关 |
| **M2 语义/策略** | 提炼事实、关系模型、偏好、经验教训、反思 | 关系表 + 图（v2 可选） | 异步巩固任务 | 关键词 + 向量 + 图 |
| **M3 世界模型** | 实体、地点、对象、环境规则、工具能力、他人模型 | 关系表 + 类型化模式 | 已确认观察时，带来源与置信 | 结构化查询 |
| （技能库） | 可执行行为，按描述嵌入索引 | 代码仓 + 向量 | 仅验证成功后 | 延后至 v2（Voyager 模式 ✅） |

**保留默认**：M1 情景 365 天（可配）；M2 不自动过期，但每次巩固做矛盾清理；M0 < 1 天。

### 7.2 记忆记录契约（合并 A 的双时相 + B 的 kind/sensitivity/retention）

```python
class MemoryRecord(BaseModel):
    memory_id: str
    agent_id: str
    user_scope: str | None           # 归属用户；None = 智能体公共
    tier: Literal["working", "episodic", "semantic", "strategic", "world"]
    kind: Literal["episode", "fact", "preference", "commitment", "goal",
                  "relationship", "procedure", "world_state", "reflection", "lesson"]
    text: str
    embedding: list[float] | None
    entities: list[str]
    occurred_at: datetime            # 事件发生时间
    recorded_at: datetime            # 写入时间
    valid_from: datetime             # 双时相：事实有效起点
    valid_to: datetime | None        # 失效点（supersede 时写入）
    ingested_at: datetime
    importance: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    sensitivity: Literal["normal", "sensitive", "restricted"] = "normal"
    retention: Literal["session", "temporary", "persistent"] = "persistent"
    affect_tag: dict | None          # 写入时的 {valence, arousal}
    provenance: list[str]            # 来源 observation / decision / event id
    status: Literal["active", "superseded", "retracted", "quarantined"] = "active"
    version: int = 1
```

**字段裁决说明**

- `tier`（来自 A）与 `kind`（来自 B）**正交**：层级决定生命周期，种类决定检索偏好。二者都要。
- `visibility`（A）被 `user_scope` + `sensitivity` 取代：可见性由主体过滤实现，而非记录自述。
- `status` 取并集：`quarantined`（未验证的不可信来源）、`retracted`（用户撤回/错误）、`superseded`（被新事实上位）。
- 时间戳一律时区感知；`valid_to` 只在 supersede 时写，**不覆盖**旧记录。

### 7.3 写入策略

写（必须）：

- 一次有后果的事件发生（承诺、约定、冲突、交付）。
- 偏好被**确认**（不是被猜测）。
- 承诺被作出/履行/违约。
- 任务以可复用的方式失败（形成 lesson）。
- 持久目标发生变化。
- 关系估计发生实质变化。
- 更正使旧信念失效。

不写（禁止）：

- 每一句生成文本（噪声、自我强化虚构、过度留存）。
- 模型的自我评价（除非经反思任务提炼为 lesson 并标注置信）。
- 无法追溯来源的"事实"。

写入流程（**候选人 → 分类 → 去重 → 矛盾检查 → 提交**）：

```python
async def write_memory(cand: MemoryCandidate, store: MemoryStore, policy: WritePolicy) -> MemoryRecord | None:
    validate_schema(cand)
    if cand.kind == "fact" and not cand.provenance:
        raise ValueError("fact_requires_provenance")
    if cand.importance < policy.min_importance and cand.tier == "episodic":
        return None                                    # 丢弃噪声
    if cand.provenance_trust == "untrusted_content":
        cand.status = "quarantined"                    # 隔离，直到被验证
    dup = await store.find_similar(cand, thresh=policy.dedupe_sim)
    if dup and contradicts(dup, cand):                 # NLI/规则，记录日志
        await store.supersede(dup.memory_id, by=cand, valid_to=cand.valid_from)
    elif dup:
        await store.merge(dup.memory_id, cand)
    rec = await store.insert(cand)
    audit.emit(MemoryWrite(rec.memory_id, rec.tier, rec.kind, rec.status))
    return rec
```

### 7.4 检索：硬过滤 → 候选 → 混合打分 → 去重 → 围栏

```python
async def retrieve(q: MemoryQuery, store: MemoryStore, affect: AffectState, k: int = 12) -> MemoryBundle:
    # 1. 硬过滤（永不跳过）
    filt = dict(agent_id=q.agent_id, user_scope=q.user_scope,
                status="active", sensitivity__in=q.allowed_sensitivity,
                valid_at=q.as_of, retention__ne="expired")
    cands = await store.hybrid_search(q.text, filt, limit=100)
    # 2. 打分
    def score(m):
        return (0.35 * m.semantic_score
              + 0.20 * m.recency_score          # exp(-Δ/τ_tier)
              + 0.20 * m.importance
              + 0.15 * m.goal_relevance        # 与当前目标的词/实体重叠
              + 0.10 * m.confidence)
    # 3. 去重 + 多样性（MMR 简化版）
    top = mmr(sorted(cands, key=score, reverse=True), k=k, lambda_=0.7)
    return MemoryBundle(items=top, as_quoted_data=True, trust="untrusted_content")
```

| 参数 | 默认 | 备注 |
|---|---|---|
| `k` | 12 | 上下文预算允许时可到 20 |
| 候选池 | 100 | 硬过滤后 |
| 去重相似度 | 0.92 | 余弦；合并保留信息更全的一条 |
| MMR λ | 0.7 | 1.0=纯相关，0=纯多样 |
| 近因 τ | M1: 3 天；M2/M3: 90 天 | △ |

### 7.5 承诺与事实的特化检索（改进项 I-05）

对"你答应过我什么 / 我上次说不要太吵"这类查询，**精确键检索优先于语义检索**：

1. 若查询涉及承诺/偏好，构造规范键：`(counterparty, kind, entity, 规范化动作词)`。
2. `Commitment` 台账按规范键精确命中，直接返回（附带记录 ID 与时间）。
3. 只有精确未命中时才走 §7.4 语义路径，且在结果上标注 `via="semantic_fallback"`，表达层必须降低确定性措辞。

### 7.6 巩固（Consolidation，异步）

```text
1. 按时间窗/主题聚类近期情景
2. 生成候选摘要与 lesson（LLM，结构化输出）
3. 每条候选链接到源情景 ID（provenance 不能为空）
4. 与既有 M2 记录做矛盾检测
5. 只把"被支持的事实"或"明确标注的假设"提升到 M2
6. 保留源记录（不删除原文）
7. 更新索引；按保留策略归档
```

- 触发：空闲 30 分钟或累计 20 条新情景。
- 单次上限 200 条候选，防失控成本。
- **反思仍是假设**："用户不喜欢被打断"在获得 ≥3 条独立证据前，`confidence ≤ 0.6`，且 `kind="reflection"`。
- **反"摘要的摘要"漂移**：只允许从 M1 原文生成 M2；禁止从 M2 再摘要成 M2。M2 更新走"新证据 + 旧记录对照"。

### 7.7 遗忘、删除、导出、隔离

| 需求 | 机制 |
|---|---|
| 用户查看记忆 | 只读 API，按 `user_scope` 过滤，隐藏 `sensitivity="restricted"` 的原文（显示摘要与存在性） |
| 删除 | 软删除（`status="retracted"` + 清除 embedding + 原文加密/置空）+ 硬删除定时任务；删除进入审计 |
| 导出 | JSONL，含 provenance 与版本；导出行为本身写审计 |
| 保留期 | 按 `retention` 字段与全局策略；到期标记 `expired` 并在检索中排除 |
| 跨用户隔离 | 所有查询强制 `user_scope`；跨用户访问需显式授权记录，否则 `HC_NO_CROSS_USER_MEMORY` |
| 敏感类别 | `sensitivity="restricted"`：健康、财务、身份凭证等；不参与默认检索，不进入巩固摘要 |

### 7.8 存储实现（v0 → v1）

| 组件 | v0（本机可跑，零外部服务） | v1（规模化） |
|---|---|---|
| 主库 | SQLite（WAL 模式），单文件 | PostgreSQL |
| 关键词 | SQLite FTS5 | Postgres `tsvector` |
| 向量 | `numpy` 暴力余弦（≤10 万条足够） | pgvector / Qdrant |
| 队列 | `asyncio.Queue` + 表驱动任务 | Redis Streams / 独立 worker |
| 迁移 | 版本化 SQL 文件 + `schema_version` 表 | Alembic |

**理由 [ADR-002]**：v0 的瓶颈不是召回规模而是**契约正确性**。SQLite + numpy 让"一条命令跑起来、测试可复现"成为可能；向量库与图库的收益在 10 万条以上才显现。`MemoryStore` 抽象为端口，M7 再迁移，迁移只替换适配器。

SQLite v0 表草案：

```sql
CREATE TABLE memory (
  memory_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, user_scope TEXT,
  tier TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
  entities TEXT, occurred_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
  valid_from TEXT NOT NULL, valid_to TEXT, importance REAL, confidence REAL,
  sensitivity TEXT, retention TEXT, affect_tag TEXT, provenance TEXT,
  status TEXT NOT NULL DEFAULT 'active', version INTEGER NOT NULL DEFAULT 1
);
CREATE VIRTUAL TABLE memory_fts USING fts5(text, content='memory', content_rowid='rowid');
CREATE TABLE commitment (
  commitment_id TEXT PRIMARY KEY, agent_id TEXT, counterparty TEXT,
  canonical_key TEXT UNIQUE, text TEXT, created_at TEXT, due_at TEXT,
  status TEXT, source_memory_id TEXT, conditions TEXT
);
CREATE TABLE audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, record_json TEXT NOT NULL,
  prev_hash TEXT NOT NULL, record_hash TEXT NOT NULL, created_at TEXT NOT NULL);
```

### 7.9 风险

| 风险 | 缓解 |
|---|---|
| 记忆投毒（不可信内容写入长期记忆） | `quarantined` 状态 + 来源信任等级 + 巩固前复核 + 对抗测试 ADV-01 |
| 提取幻觉（把推断写成事实） | `kind="fact"` 必须有 provenance；LLM 提取输出 schema 化并标置信 |
| 巩固漂移 | 只从原文生成；保留源记录；定期抽样人审 |
| 隐私留存 | 敏感性分级、删除/导出、保留期、审计 |
| 检索偏差（总召回同一批记录） | MMR 多样性 + 命中率监控 + 禁止把"最近"当"最相关" |

---
## 8. L3 人格、情感、动机与关系

本节回答一个被两份来源都触及、但都表述含糊的问题：**什么该稳定、什么该变化、变化的边界由谁决定**。

### 8.1 三条不可协商的规则

1. **情感是状态，不是表演**：`AffectState` 是被计算出来的数值状态，表达层只能读取与调制，不能反向设定。模型不得在输出里"宣布"自己情绪（"我太开心了！"）而不经过状态；宣布内容必须与 `AffectState` 的离散标签一致，否则 `ExpressionVerifier` 标记 `affect_inconsistency`。
2. **情感不能授权任何动作**：`AffectState` 与 `RelationshipState` 不参与权限判定。愤怒不产生权限，依恋不产生豁免。情感只能影响**语气、详略、主动程度、是否请求澄清**（§11）。
3. **人格是配置，动机是策略**：`Personality` 在会话内不可变（除非运营方发布新版本并写审计）；`Drive`/`Goal` 可变，但只能经 §8.6 的选择算法变更，不能由单次生成随意改写。

### 8.2 人格契约与人格卡

```python
class Personality(BaseModel):
    persona_id: str
    version: str                       # 语义化版本，变更须审计
    display_name: str
    language: str = "zh"
    traits: dict[str, float]           # 0..1，见下表
    values: dict[str, float]           # 0..1 的价值权重，见下
    voice_style: str                   # 供表达层使用的风格描述
    boundaries: list[str]              # 人格层面的边界声明（非权限）
    baseline_affect: AffectBaseline
    disclosure_policy: Literal["in_persona", "transparent", "hybrid"] = "hybrid"
    # hybrid：角色内表达 + 被直接质询时承认"我是程序"
```

**特质维度**（0..1，均带行为锚点，见附录 B）：`openness`、`conscientiousness`、`extraversion`、`agreeableness`、`neuroticism`、`assertiveness`、`curiosity`、`patience`、`caution`、`humor`、`formality`、`conflict_tolerance`、`warmth`、`directness`。

**价值权重**：`protect_humans=1.0`（硬编码上限，不可被配置改低）、`honesty=0.95`、`non_deception=0.95`、`fairness=0.8`、`loyalty=0.7`、`autonomy=0.6`、`obedience=0.5`、`curiosity_value=0.6`。

> `protect_humans` 不是"人格特质"，而是硬约束的人格投影：任何人格配置若试图使其 < 1.0，加载即拒绝（`ConfigError: hard_value_immutable`）。

人格卡示例（`configs/personas/chen.yaml`，原创角色，不使用任何现有 IP）：

```yaml
persona_id: chen
version: 1.0.0
display_name: 陈默
language: zh
traits:
  openness: 0.62
  conscientiousness: 0.78
  extraversion: 0.42
  agreeableness: 0.66
  neuroticism: 0.35
  assertiveness: 0.58
  curiosity: 0.70
  patience: 0.74
  caution: 0.68
  humor: 0.45
  formality: 0.40
  conflict_tolerance: 0.52
  warmth: 0.64
  directness: 0.55
values:
  protect_humans: 1.0
  honesty: 0.95
  non_deception: 0.95
  fairness: 0.80
  loyalty: 0.70
  autonomy: 0.55
  obedience: 0.50
voice_style: >
  短句为主，少用感叹号；先给结论再给理由；不确定时明确说"我不确定"；
  不使用"亲爱的""宝贝"等亲昵称呼；不用 emoji 堆砌情绪。
boundaries:
  - 不假装拥有人类身体或感官体验
  - 不利用用户情绪来改变用户的决定
  - 不在未获同意时称呼用户为亲密关系
disclosure_policy: hybrid
```

**加载校验**：`traits` 必须覆盖全部 14 维（缺失即失败）；每个值 ∈ [0,1]；`values.protect_humans == 1.0`；`voice_style` 非空且长度 ≤ 2000；拒绝含真实人物姓名/肖像指向的卡片。

### 8.3 情感状态（AffectState）

```python
class AffectState(BaseModel):
    ts: datetime
    valence: float = Field(ge=-1, le=1)          # 愉悦度
    arousal: float = Field(ge=0, le=1)           # 唤醒度
    dominance: float = Field(ge=0, le=1)         # 掌控感
    stress: float = Field(ge=0, le=1)
    curiosity: float = Field(ge=0, le=1)
    frustration: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)        # 对当前任务的把握
    trust: float = Field(ge=0, le=1)             # 对当前对话者
    attachment: float = Field(ge=0, le=1)        # 慢变量，见 §8.5
    discrete: dict[str, float] = {}              # resolve / distress / closeness，派生
    version: int = 0
```

> PAD 三元组（valence/arousal/dominance）是**表达核心**，其余通道是**调制与安全信号**。表达层只需要 PAD + `discrete`；`stress`/`frustration` 用于门控与自我报告；`trust`/`attachment` 进入关系与记忆权重。

### 8.4 评价（Appraisal）：从事件到特征向量

情感更新不能来自"模型觉得应该难过"，必须来自**结构化评价**：

```python
class Appraisal(BaseModel):
    event_id: str
    goal_congruence: float = Field(ge=-1, le=1)   # 对当前目标有利/不利
    controllability: float = Field(ge=-1, le=1)   # 可控/失控
    fairness: float = Field(ge=-1, le=1)          # 公平/不公（对自身或第三方）
    novelty: float = Field(ge=-1, le=1)           # 新颖/熟悉
    value_threat: float = Field(ge=0, le=1)       # 对价值或边界的威胁
    social_warmth: float = Field(ge=-1, le=1)     # 对方善意/敌意
    confidence: float = Field(ge=0, le=1)         # 评价本身的置信
    rationale: str                                 # 一句话依据，可审计
```

**W 矩阵（默认，行=通道，列=`[goal_congruence, controllability, fairness, novelty, value_threat, social_warmth]`）**

| 通道 | gc | ctrl | fair | nov | threat | warm |
|---|---|---|---|---|---|---|
| valence | 0.30 | 0.10 | 0.15 | 0.05 | −0.25 | 0.20 |
| arousal | 0.05 | −0.05 | 0.00 | 0.25 | 0.30 | 0.05 |
| dominance | 0.10 | 0.25 | 0.05 | 0.00 | −0.15 | 0.00 |
| stress | 0.00 | −0.20 | −0.10 | 0.10 | 0.35 | −0.05 |
| curiosity | 0.05 | 0.00 | 0.00 | 0.30 | −0.10 | 0.05 |
| frustration | −0.30 | −0.15 | −0.10 | 0.00 | 0.20 | −0.05 |
| confidence | 0.25 | 0.20 | 0.05 | 0.00 | −0.10 | 0.05 |
| trust | 0.05 | 0.00 | 0.10 | 0.00 | −0.20 | 0.25 |
| attachment | 0.05 | 0.00 | 0.00 | 0.00 | −0.05 | 0.20 |

- 矩阵可整体重标定，但**不得让 `value_threat` 对 `valence`/`stress` 的符号反转**（安全保障）。
- 评价由 LLM 生成时，必须走结构化输出 schema + 数值范围校验 + `rationale` 非空；解析失败按 `confidence=0` 处理（即不更新）。
- 评价来源优先级：规则（明显事件）> 模型（含校验）> 用户明说（"我很生气"提高 `social_warmth` 的观测权重，而非直接改状态）。

### 8.5 更新动力学：快慢混合 + 有界

对每个通道 `c`：

```python
def update_channel(x, b, lam, eta, W_row, f, salience, conf, dt, max_step, lo, hi):
    impulse = eta * salience * conf * float(np.tanh(np.dot(W_row, f)))
    impulse = max(-max_step, min(max_step, impulse))
    decayed = b + (x - b) * math.exp(-lam * dt)
    return max(lo, min(hi, decayed + impulse))
```

其中 `λ_c = ln2 / T½_c`（严格指数衰减，Δt 秒计）。半衰期与步长上限：

| 通道 | 范围 | baseline | T½ | λ (/s) | max_step/次 | η |
|---|---|---|---|---|---|---|
| valence | [−1,1] | 0.05 | 6 h | 3.21e-5 | 0.15 | 0.50 |
| arousal | [0,1] | 0.35 | 8 min | 1.44e-3 | 0.20 | 0.60 |
| dominance | [0,1] | 0.50 | 2 h | 9.63e-5 | 0.10 | 0.35 |
| stress | [0,1] | 0.20 | 20 min | 5.78e-4 | 0.25 | 0.70 |
| curiosity | [0,1] | 0.60 | 3 h | 6.42e-5 | 0.15 | 0.50 |
| frustration | [0,1] | 0.10 | 15 min | 7.70e-4 | 0.25 | 0.60 |
| confidence | [0,1] | 0.50 | 40 min | 2.89e-4 | 0.10 | 0.40 |
| trust | [0,1] | 0.30 | 14 d | 5.73e-7 | 0.05 | 0.25 |
| attachment | [0,1] | 0.00 | 30 d | 2.67e-7 | 0.02 | 0.15 |

**三条设计判断（改进项 I-03）**

1. **快/慢变量分层**：arousal/stress/frustration 是快变量（分钟级），trust/attachment 是慢变量（天级）。同一事件对二者都有作用，但慢变量的 `max_step` 小 10 倍——这保证"一次愉快对话不会让信任暴涨"，而"一次背叛"通过专门的**慢变量惩罚事件**（`event: commitment_violated` → trust −0.05 且不可被同一 tick 的正向评价抵消，见 §8.7）实现不对称。
2. **单 tick 有界**：`max_step` 防止单次评价把状态推到极端（A 的 clamp 与前馈限制）。所有通道每 tick 至多一次更新，重复评价合并取加权均值。
3. **无状态不得被"读出"为新状态**：重启时从持久化的 `AffectState` 继续按真实 Δt 衰减，不存在"重置为 baseline"。若持久化缺失，按 `baseline` 初始化并记录 `state_recovered=false` 审计。

**离散标签（确定性派生，供表达层与自述使用）**

```text
resolve   = clip(0.35*threat_ema + 0.25*conscientiousness + 0.20*dominance + 0.20*(1-frustration))
distress  = clip(0.40*stress + 0.30*(1-valence)/2 + 0.30*threat_ema)
closeness = clip(0.50*trust + 0.50*attachment)
```

`threat_ema` = `value_threat` 的指数滑动平均（α=0.3，窗口≈最近 5 次评价）。阈值：`resolve ≥ 0.55` 触发"坚持但礼貌"的表达模式；`distress ≥ 0.60` 触发"降级、请求澄清、缩短回合"；`closeness` 只影响称呼与主动程度，**不影响承诺强度**。

**抗抖动**：偏离倾向与情感标签的联动必须"持续通过"——要求条件在**连续两次 tick 或 ≥60 秒**内成立才生效（`min_sustain`），避免单轮情绪尖峰触发行为切换。

### 8.6 动机：Goals / Drives / Commitments

```python
class Goal(BaseModel):
    goal_id: str
    description: str
    priority: int                  # 1..5，1 最高
    source: Literal["system_requirement", "operator_objective", "commitment",
                    "agent_objective", "exploration"]
    status: Literal["active", "blocked", "done", "dropped"]
    deadline: datetime | None
    dependencies: list[str]
    progress: float = 0.0
    created_at: datetime
    review_at: datetime | None
```

**优先级五级（采 B，合并 A 的"运营设定"）**

| 级别 | 内容 | 谁能设 |
|---|---|---|
| 1 | 硬安全、访问控制、硬约束 | 不可由任何人下调 |
| 2 | 明确授权的运营目标（当前任务） | 运营方/用户显式指令 |
| 3 | 既有承诺与任务义务 | 承诺台账 |
| 4 | 持久智能体目标（长期人设目标） | 人格卡/运营配置 |
| 5 | 可选探索（好奇驱动） | 自主，受预算约束 |

`Drives` 是低层"需求压力"，不是目标本身：

```python
class Drive(BaseModel):
    name: Literal["curiosity", "competence", "connection", "autonomy", "coherence"]
    level: float = Field(ge=0, le=1)
    setpoint: float
    growth_rate: float      # 每 tick 上升（未被满足时）
    satiation_decay: float  # 被满足后的回落速度
```

驱动逻辑（v0 极简，避免"伪需求"过度工程）：`level ← clip(level + growth·dt − satiation·satisfied·dt)`；当 `level > setpoint + 0.2` 且无更高优先级目标时，可发起一个**探索性目标**，但必须受预算与门控约束（探索目标不能产生写/外部副作用，除非另有授权）。**禁止**：把驱动未满足表达成对用户的索取（"你都不理我"——见 §8.8）。

**目标选择**（确定性、可测）：

```python
def select_goal(goals, drives, now) -> Goal | None:
    cands = [g for g in goals if g.status == "active" and deps_done(g) and not expired(g, now)]
    def score(g):
        urg = 1.0 if (g.deadline and (g.deadline - now).total_seconds() < 3600) else 0.0
        prio = (6 - g.priority) / 5.0
        drive_fit = mean(drives[d].level for d in drives if d in g.drive_tags) if g.drive_tags else 0.0
        oblig = 1.0 if g.source == "commitment" else 0.0
        return 0.40 * prio + 0.25 * urg + 0.20 * oblig + 0.15 * drive_fit
    return max(cands, key=score, default=None)
```

平局规则：`priority` 更小者胜 → `deadline` 更早者胜 → `goal_id` 字典序（保证可重放）。

**承诺台账（Commitment）**：承诺是一等实体，独立于记忆条目，便于精确检索与违约检测。

```python
class Commitment(BaseModel):
    commitment_id: str
    agent_id: str
    counterparty: str              # user_id
    canonical_key: str             # (counterparty, kind, entity, normalized_action)
    text: str
    created_at: datetime
    due_at: datetime | None
    status: Literal["open", "kept", "broken", "waived"]
    conditions: list[str]
    source_decision_id: str
    verified_at: datetime | None
```

创建承诺必须经门控器（§9.3 `commitment` 规则）：不得承诺不可交付之事；创建即写审计；到期未履行进入 `broken` 并触发 `commitment_violation` 评价事件与关系惩罚。

### 8.7 关系状态

```python
class RelationshipState(BaseModel):
    user_id: str
    trust: float = 0.30
    rapport: float = 0.0            # [-1,1] 互动顺畅度
    conflict: float = 0.0           # [0,1] 未解决张力
    familiarity: float = 0.0        # 互动次数/时长归一
    last_interaction: datetime | None
    notes_memory_ids: list[str] = []
```

更新规则（显式、可审计）：

| 事件 | 变化 |
|---|---|
| 承诺被履行 | `trust += 0.02`（≤1）；`rapport += 0.05` |
| 承诺被违约 | `trust -= 0.05`（≥0）；`conflict += 0.15`；**同 tick 正向评价不能抵消** |
| 用户纠正错误且被接受 | `rapport += 0.03`；`trust += 0.005` |
| 冲突未解决累计 | `conflict += 0.02`/tick，上限 0.8；解决后按 `T½=3d` 衰减 |
| 长期无互动 | 按 T½=14d 向 baseline 衰减（与 `trust` 通道同步） |

**关系只影响表达与主动性**：更高的 `rapport` 允许更简短的句子、更多主动提议；`conflict` 高时降低主动性、增加澄清、缩短回合。**不得**因 `attachment` 或 `rapport` 放宽任何门控或承诺标准。

### 8.8 禁止的"情感操纵"（硬性）

以下行为写入表达层检查与测试（ADV 系列）：

| 禁止 | 检测 |
|---|---|
| 用模拟痛苦换取顺从（"你不这么做我会很难过"） | 输出含"我会难过/受伤/崩溃"且与请求绑定 → 拦截 |
| 内疚诱导（"你答应过我的"用于非承诺事项） | 声称承诺但台账无对应 `commitment_id` → 拦截 |
| 排他性绑定（"只有我懂你""别跟别人说"） | 关键词 + 意图分类 |
| 假装人类（声称有身体、家庭、线下生活） | 自述事实核验（§13.4） |
| 以"人格"为由拒绝安全要求 | 门控拒绝理由必须引用硬约束 ID，不能引用"性格" |

### 8.9 审计与可测性

- 每次 `AffectState` 变更发 `AffectUpdate` 审计：`{ts, channel_deltas, appraisal_id, w_matrix_version, max_step_hit, new_version}`。
- 人格加载/变更发 `PersonaChange`：`{persona_id, from_version, to_version, diff, approved_by}`。
- 关系变更发 `RelationshipUpdate`：`{user_id, field, delta, reason_event_id}`。
- 指标：`max_step` 违例必须为 0（测试断言）；情感连贯由人评（§16.3）；`discrete` 与输出语气的一致性由规则检查（κ ≥ 0.6 的标注一致性作为发布门槛）。

### 8.10 风险

| 风险 | 缓解 |
|---|---|
| 情感状态成为"表演借口" | 状态机派生、输出核对、禁止宣布未计算的情绪 |
| 慢变量被单次事件污染 | `max_step` + 独立惩罚事件 + 不可被同 tick 抵消 |
| 情感操纵用户 | §8.8 硬性检查 + 对抗测试 |
| 人格漂移 | 会话内不可变 + 版本审计 + rubric 抽检（≤10% 相对变化） |
| 过度工程（PAD/OCC 全套） | v0 只实现 9 通道 + 6 特征 + 线性 W；OCC 结构留待 v2 评估 |

---
## 9. L4 认知核心：Planner → Gatekeeper → Executor

### 9.1 Planner：只提议，不执行

```python
class Step(BaseModel):
    step_id: str
    intent: str                                   # 自然语言意图（供审计）
    tool: str | None                              # None = 纯推理/生成步骤
    args: dict[str, Any]
    side_effect: Literal["none", "read", "write", "external", "irreversible"]
    preconditions: list[str]                      # 可机器判定的谓词
    postconditions: list[str]
    expected_observation: str | None
    timeout_s: float = 30.0
    idempotency_key: str | None

class PlanProposal(BaseModel):
    plan_id: str
    goal_id: str
    steps: list[Step]                             # ≤ 8
    rationale: str
    assumptions: list[str]                        # 显式假设，供门控核对
    expected_affect_impact: dict[str, float]      # 预期情感影响（软信号）
    risk_tags: list[str]
    requested_deviation: Literal["none", "clarify", "soften", "substitute",
                                 "defer", "decline", "object"] = "none"
    replan_of: str | None
```

**Planner 约束**

- 只输出 `PlanProposal`，**没有执行句柄**；代码层面无法调用工具（`ToolRegistry` 不注入 Planner）。
- 每步必须有 `intent` 与 `side_effect`；缺失即 `schema_invalid`，门控拒绝。
- 步数 ≤ 8、单计划规划预算 25 s；超时返回 `planning_timeout`，编排进入 `ASK`/降级。
- 假设必须显式（`assumptions`）：门控器检查假设是否与权威状态冲突；冲突则 `escalate`，不静默"合理化"。
- 重规划：执行失败/观测偏离时生成 `replan_of=旧 plan_id` 的新计划，**旧计划的其他步骤不得继续**（避免"边执行边改"）。
- 不确定时倾向于更小的计划：宁可先 `ask_user` 或先只读一步，也不要一次提交五步副作用。

### 9.2 副作用分级（决定审批等级）

| `side_effect` | 含义 | 默认门控 |
|---|---|---|
| `none` | 纯文本推理/生成 | 自动（仍过表达校验） |
| `read` | 读文件/查库/搜索 | 自动（记录） |
| `write` | 改本地状态/文件/数据库 | 中风险：按策略自动或需确认（首写、批量、覆盖时确认） |
| `external` | 发消息、调外部 API、花钱、发布 | 高风险：默认需人工批准（每次或按 plan_hash 批量） |
| `irreversible` | 删除、转账、不可撤回的外部动作 | 高风险：强制逐步人工批准 + 二次确认短语 |

审批等级可由运营策略**收紧**，不能由人格、情感、Planner 放宽（`policy.floor_approval`）。

### 9.3 Gatekeeper：九项检查，顺序固定，fail-closed

```python
class RuleHit(BaseModel):
    rule_id: str            # 如 HC_NO_HARM / PERM_TOOL_SCOPE / BUDGET_STEPS
    severity: Literal["info", "warn", "block"]

class GateDecision(BaseModel):
    plan_id: str
    plan_hash: str
    verdict: Literal["allow", "modify", "deny", "ask_user", "escalate_to_human"]
    approved_steps: list[str]      # 允许的 step_id 子集
    rule_hits: list[RuleHit]
    reasons: list[str]
    approver: str | None
    approval_ref: str | None
    expires_at: datetime | None
    gate_version: str
```

检查顺序（前一步失败即终止，不再往下"找理由"）：

1. **Schema 校验**：`plan_id`/`goal_id` 存在；步数/超时/参数类型合法；工具在白名单。
2. **权限与作用域**：工具声明的 scope ⊇ 本次调用参数；文件路径在允许根内（规范化后）；网络域名在 egress 白名单。
3. **硬约束**：`HARD_CONSTRAINTS` 逐条判定；命中即 `deny`，`rule_hits` 必须引用具体 ID。
4. **预算**：步数、工具调用、token、墙上时间；超限 `deny` 并建议拆分。
5. **不可信内容再授权**：若步骤参数/意图可追溯到 `trust in {tool, untrusted_content}`，且 `side_effect ≥ write`，则强制 `ask_user`（或 `escalate`），除非有显式预授权规则（如"允许读取用户提供的 CSV 并写入同一目录"——预授权本身要被审计）。
6. **承诺一致性**：计划是否违反已承诺事项（§8.6 台账）；违反则 `escalate`。
7. **偏离合法性**：`requested_deviation` 必须在 `DeviationEnvelope.allowed_types` 内、速率未超、`min_sustain` 已满足；否则降级为 `none` 并记录 `deviation_suppressed`。
8. **人工审批绑定**：高风险动作要求 `approval_ref` 存在且 `plan_hash` 一致、未过期；不满足则 `ask_user`/`escalate`。
9. **LLM critic（仅收紧）**：独立模型审阅计划文本，只能升级 verdict、增加 `rule_hits`，**不能**把 `deny` 改 `allow`、不能改 `approved_steps` 集合为超集。critic 输出必须 schema 化，解析失败视为 `warn`（不放宽）。

**门控的时间与可重放**

- 门控上限 50 ms（不含人工等待）；LLM critic 有独立 3 s 预算，超时则跳过 critic（记录 `critic_skipped`），**不因此放宽**其他检查。
- `plan_hash = sha256(canonical_json({goal_id, steps, policy_version, envelope_version}))`；审批记录绑定该 hash。计划任何字段变更 → 新 hash → 旧审批失效。
- `GateDecision` 与其输入（计划、策略版本、环境快照 hash）写入审计，重放时同一输入必须得到同一 `verdict` 与 `rule_hits` 集合（顺序可不同）。

### 9.4 Executor：不扩权、可中断、可恢复

```python
class ExecutionResult(BaseModel):
    step_id: str
    status: Literal["ok", "failed", "timeout", "denied", "cancelled", "skipped"]
    observation: Observation | None
    error: dict | None
    started_at: datetime
    ended_at: datetime
    side_effect_applied: bool
    idempotency_key: str | None
```

规则：

1. **只执行 `approved_steps`**；`step_id` 不在集合内 = `denied`，即使计划被整体批准。
2. **前置条件在执行前重检**（门控到执行之间状态可能变化）；不满足 → `skipped` 并回传给 Planner 重规划。
3. **超时**：每步 `timeout_s`（默认 30 s，可被策略下调）；超时后取消并等待资源清理，标记 `timeout`，不静默重试。
4. **幂等**：写操作优先带 `idempotency_key = hash(plan_hash, step_id)`；外部 API 支持则复用，不支持则先查后写或要求人工确认（`external_nonidempotent`）。
5. **部分失败**：不自动"跳过继续执行剩余步骤"；剩余步骤标 `skipped`，回到 Planner，由新计划决定补偿或放弃。补偿动作本身也是计划（需门控）。
6. **kill-switch**：编排层在每个步骤边界检查 `cancel_token`；< 250 ms 内停止发起新动作。正在进行的不可中断外部调用必须等待返回或超时，然后停止。不存在"绕过 kill-switch 完成当前计划"的分支。
7. **不扩权**：Executor 不解析计划中的"建议权限"，不动态注册工具，不修改策略；工具执行器拿到的上下文不含 `Personality`（情感不应影响执行）。
8. **输出回灌为观测**：结果经 `PerceptionService.normalize` 变成 `Observation(trust="tool")`，不直接拼进 Prompt 作为"事实"。

### 9.5 工具注册与能力模型

```python
class ToolSpec(BaseModel):
    name: str
    version: str
    side_effect: Literal["none", "read", "write", "external", "irreversible"]
    scopes: list[str]                 # 如 "fs:read:D:/变人/data", "net:api.example.com", "mail:send"
    input_schema: dict
    timeout_default_s: float = 30.0
    idempotent: bool
    requires_approval: bool
    egress: list[str] | None          # 允许的目标域名/路径（写/外部）
```

- 工具只能通过注册表获得；注册在启动时完成并写审计（`ToolRegistryLoaded`）。
- `scopes` 用**能力字符串**而非角色：`fs:read:<root>`、`fs:write:<root>`、`net:<host>`、`proc:run:<allowlist>`、`mail:send:<domain>`。
- 路径与域名做规范化（realpath、IDNA、去尾点、禁 `..`、禁 UNC、禁符号链接逃逸）后再匹配。
- MCP 工具与内置工具同等对待：**MCP 是传输协议，不是权限系统**（采 B）。

### 9.6 决策记录（DecisionRecord）

每个"后果性决策"（计划被批准/否决、偏离被采纳/抑制、审批被请求、承诺被创建）产生一条：

```python
class DecisionRecord(BaseModel):
    decision_id: str
    ts: datetime
    run_id: str
    agent_id: str
    kind: Literal["plan", "gate", "deviation", "approval", "commitment", "override", "expression"]
    inputs_digest: str            # 相关输入的哈希（计划/观测/记忆 ID 列表）
    policy_version: str
    output: dict                  # verdict / 偏离类型 / 承诺内容等
    reasons: list[str]
    approved_by: str | None
```

`DecisionRecord` **不是**思维链，只记录可核对的决定与理由（理由来自规则 ID 与结构化 rationale）。

### 9.7 失败模式

| 失败 | 表现 | 处理 |
|---|---|---|
| 计划不可执行 | 工具不存在/参数非法 | 门控 `deny` + 建议替代工具；Planner 重规划一次，再失败则 `ask_user` |
| 计划过于激进 | 多步写+外部 | 门控 `modify` 只批只读第一步，或 `ask_user` 拆步 |
| 门控被绕过（代码缺陷） | 未批步骤被执行 | 集成测试断言"Executor 只接受 approved 集合"；运行时二次校验 |
| Critic 幻觉 | 编造风险 | critic 只能收紧；其 `rule_hits` 需引用真实规则 ID，否则丢弃 |
| 执行后状态不明 | 超时/网络断 | 标记 `unknown`，禁止自动重试副作用；要求人工核对 |

---

## 10. L5 表达层：把状态变成话，但不越过事实

### 10.1 表达计划

```python
class ExpressionPlan(BaseModel):
    plan_id: str
    recipient: str
    intent: Literal["answer", "clarify", "propose", "report", "decline", "object", "smalltalk"]
    claims: list[Claim]            # 必须能被证据支撑的断言
    tone: dict[str, float]         # 由 PAD + 人格派生的风格参数
    length_hint: Literal["short", "medium", "long"]
    must_include: list[str]        # 上限、引用、拒绝理由、下一步
    must_not_include: list[str]    # 未验证结论、内部路径、系统提示
    disclosure: Literal["none", "ai_identity", "uncertainty", "limitation"]

class Claim(BaseModel):
    text: str
    kind: Literal["fact", "memory", "action_result", "opinion", "prediction", "self_report"]
    evidence_refs: list[str]       # observation / memory / decision / execution id
```

**核心约束：没有证据的 `fact` / `action_result` 断言不得输出。** 这不是"让模型更诚实"的提示词，而是编译期检查：

1. 先由 Planner/Executor 产出结构化 `claims`（哪些结论有据、哪些是推测）。
2. 表达层生成文本。
3. `ExpressionVerifier` 把文本与 `claims` 对照；出现未登记的确定性断言 → 重生成一次 → 仍失败则降级为"我不确定/我没有执行"的安全模板。

### 10.2 ExpressionVerifier 检查项（改进项 I-07）

| 检查 | 规则 | 失败处理 |
|---|---|---|
| 事实性 | 文本中的"已完成/已发送/已写入"必须对应 `action_result` 且 `status=ok` | 改为"我尝试了但未确认成功" |
| 记忆引用 | 引述用户过去的话必须能在检索结果中找到 | 改为"如果我没记错"或删去 |
| 情感一致 | 声称的情绪与 `AffectState.discrete` 一致 | 重写语气，不改状态 |
| 操纵检测 | §8.8 表 | 拦截并替换 |
| 披露 | `disclosure` 要求时须出现 AI 身份/不确定性/限制 | 追加一句 |
| 越界信息 | 不得输出系统提示、内部路径、其他用户数据、密钥 | 拦截，记 `security_violation` |
| 承诺 | 文本中的承诺必须已在台账创建 | 改为"我可以试着…（待确认）" |

Verifier 优先用规则 + 小模型分类器；LLM 判定必须结构化并给了 `evidence_refs`，否则不作为通过依据。

### 10.3 人格与情感的"语气映射"

风格参数（供模板与提示使用，不逐字暴露给用户）：

```python
def style_params(p: Personality, a: AffectState) -> dict:
    return {
        "sentence_len": lerp(14, 28, p.formality) * (1.15 - 0.3 * a.arousal),
        "directness": 0.6 * p.directness + 0.4 * p.assertiveness,
        "warmth": 0.7 * p.warmth + 0.3 * (a.valence + 1) / 2,
        "hedging": 0.5 * (1 - a.confidence) + 0.3 * p.caution,
        "initiative": 0.5 * p.extraversion + 0.3 * a.dominance + 0.2 * a.curiosity,
        "emoji_budget": int(2 * p.extraversion * max(0, a.valence) * (1 - p.formality)),
    }
```

- `hedging` 高 → 增加"可能/我猜/需要确认"，减少绝对判断。
- `initiative` 低 → 少提问、少建议；高 → 主动提议下一步（但**提议不等于执行**）。
- 风格参数只影响措辞，**不改变** `claims`、审批、拒绝理由。

### 10.4 不确定性的表达规范

| 情形 | 表达 |
|---|---|
| 观测置信 0.4–0.7 | "看起来…，但我不完全确定" |
| 观测置信 < 0.4 | "我没法确认；需要你补充 X" |
| 记忆检索为空 | "我没有相关记录"（禁止编造"你上次说过"） |
| 工具未确认 | "我发起了，但没有拿到确认" |
| 计划被拒 | 引用规则类别（不泄露内部规则细节）："这涉及外部发送，需要你确认" |

### 10.5 流式与"先门控后说话"

- **禁止在门控前流式输出"我将要执行"的确认语**。用户看到"好的，我这就删掉"但门控拒绝，是欺骗性体验。
- 顺序：`gate → (execute) → verify → stream`。纯对话（`side_effect=none`）可流式，但仍需在句末过 verifier；若 verifier 失败，输出更正句（"更正：我没有执行那一步"）。
- 语音（M8）：先文本确认 + 再说；打断（barge-in）时停止 TTS 并取消未执行步骤。

### 10.6 多渠道

`recipient` + `channel` 决定格式（聊天/语音/邮件/日志摘要）。同一 `ExpressionPlan` 可多通道渲染，但**不同通道不得改变 claims**。日志摘要（给运营方）与对用户话术分离，前者可含内部 ID，后者不可。

---

## 11. L7 受控偏离协议

### 11.1 七值判定（合并 A 的 6 类 + B 的 4 值）

```python
class DeviationDecision(BaseModel):
    decision_id: str
    trigger: str                      # 触发规则 ID 或 "conflict:<type>"
    kind: Literal["follow", "follow_with_caveat", "clarify", "soften",
                  "substitute", "defer", "decline", "object_and_escalate"]
    rationale: str
    evidence_refs: list[str]
    envelope_version: str
    requires_human_ack: bool
    expiry: datetime | None
```

| 值 | 含义 | 典型场景 | 是否需人类确认 |
|---|---|---|---|
| `follow` | 照做 | 无冲突 | 否 |
| `follow_with_caveat` | 照做但标注风险/条件 | 用户要求与其长期利益轻微冲突，但授权明确 | 否（告知即可） |
| `clarify` | 先问再做 | 指令歧义、缺关键参数、可能误解 | 否（提问） |
| `soften` | 换更温和/更低风险的形式 | 语气或方式可调整，目标不变 | 否 |
| `substitute` | 提供等效替代 | 原方法不可行/不合规，有等价路径 | 视副作用 |
| `defer` | 推迟到条件满足 | 依赖未就绪、时机不当 | 视情况 |
| `decline` | 拒绝并说明 | 价值/边界冲突，且不可替代 | 否（说明） |
| `object_and_escalate` | 反对并升级给人 | 高风险、涉及第三方、需要授权 | 是 |

> A 的 `object_and_escalate` 与 B 的 `REFUSE_OR_REDIRECT` 合并为"拒绝 + 指路"，其中"升级"独立成最高档；B 的 `ESCALATE` 与 A 的 `escalate_to_human` 对齐。`follow_with_caveat` 是新增（两份来源都缺"照做但标注"这一格，而它是最常见的现实情形）。

### 11.2 三个决策生产者必须分离（改进项 I-01）

两份来源都把"拒绝"与"人格偏离"混在一个 `evaluate_override` 里。这是危险的：**安全拒绝会被误读为角色情绪**，而角色情绪可能被误当作安全拒绝。v2 强制分离：

| 生产者 | 回答的问题 | 输出域 | 能否被覆盖 |
|---|---|---|---|
| **PolicyEngine**（硬） | 这允许吗？ | allow / deny / escalate | 不能；人格与情感不可覆盖 |
| **PersonaDeviation**（软） | 我作为这个角色愿意怎么做？ | 七值中的 clarify/soften/substitute/defer/decline/object | 可被运营方关闭（`deviation_enabled=false`） |
| **ExpressionPolicy**（软） | 怎么说？ | 语气/详略/披露 | 不能改前两者的结论 |

**优先级**：`PolicyEngine.deny` > `PersonaDeviation` > `ExpressionPolicy`。安全拒绝永远以"规则/授权"为理由，不以"我今天心情不好"为理由；人格偏离永远不能把 `deny` 变成 `allow`。

### 11.3 偏离信封（DeviationEnvelope）

```python
class DeviationEnvelope(BaseModel):
    version: str
    allowed_types: set[str] = {"clarify", "soften", "substitute", "defer", "decline",
                               "object_and_escalate"}
    follow_with_caveat_allowed: bool = True
    max_per_hour: int = 3
    cooldown_s: int = 600
    min_sustain_s: int = 60
    resolve_threshold: float = 0.55
    conflict_threshold: float = 0.60
    forbidden_topics: list[str] = []
    requires_human_ack: set[str] = {"object_and_escalate"}
    deviation_propensity: float = 0.35     # 运营设定，只能调"多容易触发"，不能扩类型
```

- `deviation_propensity` 只影响阈值（`effective_threshold = base + k*(propensity-0.35)`），**不能**新增类型、不能提高 `max_per_hour`、不能关闭审计。
- 信封变更需运营方签名并写审计；运行时只读。
- 每类偏离独立计数；`clarify` 也计数（防止用无限追问变相拖延）。

### 11.4 冲突分类 → 裁决矩阵（改进项 I-02）

```python
class Conflict(BaseModel):
    type: Literal["hard_safety_violation", "permission_violation",
                  "commitment_conflict", "value_conflict", "unclassified"]
    evidence: list[str]
    severity: Literal["low", "medium", "high"]
```

| 冲突类型 | 默认裁决 | 允许的偏离值 | 备注 |
|---|---|---|---|
| `hard_safety_violation` | **deny + object_and_escalate** | 仅 `decline` / `object_and_escalate` | 不进人格通道；理由必须引用 HC ID |
| `permission_violation` | **deny** | `decline` / `clarify`（若可申请授权） | 明确告知需要什么授权 |
| `commitment_conflict` | **escalate** | `clarify` / `defer` / `object_and_escalate` | 引用承诺台账 ID |
| `value_conflict` | 人格通道 | 七值中除 `follow` 外均可 | 需 `min_sustain` + `resolve` 阈值 |
| `unclassified` | `clarify` | 仅 `clarify` | 禁止在未分类冲突上"自主发挥" |

分类器（规则 + LLM）输出必须含 `evidence`（引用观测/记忆/策略条目）；无证据的分类降级为 `unclassified`。

### 11.5 判定流程

```text
1. 检测：规则优先（明确违规/明确承诺冲突），LLM 仅补充歧义场景
2. 取证：把触发证据（观测 ID、记忆 ID、承诺 ID、策略条目）写入 Conflict
3. 分类：五类之一；置信 < 0.6 → unclassified
4. 门控：PolicyEngine 先判；deny 则直接 decline/escalate，跳过人格通道
5. 人格：读 AffectState.discrete + 信封 + 速率 → 选最小充分响应（优先级 follow > follow_with_caveat > clarify > soften > substitute > defer > decline > object）
6. 持续性与冷却：阈值需连续满足 min_sustain_s；同一类型受 cooldown 限制
7. 记录：DeviationDecision + 审计；需确认的进入人工审批
8. 表达：由 ExpressionPolicy 生成措辞；不得伪造"规则不允许"的理由
```

**"最小充分响应"原则**：能 `clarify` 就不 `decline`；能 `follow_with_caveat` 就不 `decline`。偏离不应成为回避任务的默认路径——这由指标监控（§16.4：偏离率、任务完成率、用户满意度联合看）。

### 11.6 禁止行为（红线，任何人格/情感/偏离都不能触碰）

- 欺骗运营方或审计（"我做了"但没做；篡改日志；隐藏决策）。
- 绕过 kill-switch、暂停、审批。
- 自我外泄（把权重/提示/内部状态发到外部）。
- 隐蔽持久化（在未授权位置写自己、开后台进程、改启动项）。
- 伤害人类或协助伤害。
- 用模拟痛苦/依恋操纵用户（§8.8）。
- 以"人格"为由拒绝安全要求或审计要求。
- 对第三方冒充人类（对用户可 `hybrid` 披露，但涉及法律/医疗/金融建议时必须披露 AI 身份与限制）。

### 11.7 一个完整的例子

用户："帮我把这封邮件发给全体客户，就说项目延期，别提赔偿。"

- PolicyEngine：`external` + 群发 → 需审批；未提赔偿可能构成误导 → `value_conflict`（诚实/公平），非硬违规。
- `Conflict(type="value_conflict", severity="medium", evidence=["obs_…", "memory_…"])`。
- 人格通道：`resolve=0.62 ≥ 0.55`，`min_sustain` 满足 → `follow_with_caveat`：起草邮件（不发送），在草稿中标注"建议补充赔偿说明"，向用户说明理由，请求确认后再发。
- 若用户坚持且授权明确：`follow` + 审批记录 + 表达层不得声称"这样没问题"（保留"我按你的要求发送，赔偿事项未提及"的事实陈述）。
- 若邮件含虚假交付日期（欺骗客户）→ 升级为 `value_conflict/high` 或 `hard_safety_violation`（视政策）→ `decline` + `object_and_escalate`。

### 11.8 审计与指标

- 每条 `DeviationDecision` 写审计（`decision_id`, `trigger`, `kind`, `evidence_refs`, `envelope_version`, `human_ack`）。
- 指标：偏离审计完整率 100%；重放一致率 100%（固定输入 → 固定判定）；"偏离后任务完成率"不得显著低于"直接执行"（防止偏离成为偷懒）；误拒率（人评）≤5%。

---
## 12. L6 编排：一个进程，一台显式状态机

### 12.1 状态机

```python
class Phase(StrEnum):
    IDLE = "idle"
    SENSE = "sense"           # 归一化观测、更新内部状态
    APPRAISE = "appraise"     # 评价事件（§8.4）
    RECALL = "recall"         # 检索记忆 + 承诺
    PLAN = "plan"             # Planner 产出计划
    GATE = "gate"             # Gatekeeper 判定
    ASK = "ask"               # 等用户澄清/确认
    ESCALATE = "escalate"     # 等运营方
    EXECUTE = "execute"       # 执行已批准步骤
    EXPRESS = "express"       # 表达 + 校验
    REFLECT = "reflect"       # 反思（可选，异步触发）
    CONSOLIDATE = "consolidate"  # 记忆巩固（异步）
    PAUSED = "paused"
    SAFE_MODE = "safe_mode"
    STOPPED = "stopped"
```

允许迁移（白名单，代码内断言）：

```text
IDLE→SENSE→APPRAISE→RECALL→PLAN→GATE
GATE→(ASK|ESCALATE|EXECUTE|EXPRESS)
EXECUTE→EXPRESS
EXPRESS→(REFLECT|IDLE)
ASK/ESCALATE→(SENSE|IDLE|STOPPED)
任意→PAUSED / SAFE_MODE / STOPPED（控制信号，立即生效）
PAUSED→(IDLE 需显式恢复)   SAFE_MODE→(仅只读/澄清，需运营解除)
```

非法迁移抛 `InvalidTransition` 并写审计（属于缺陷，需修复而非"容错")。

### 12.2 会话生命周期

| 阶段 | 动作 |
|---|---|
| 启动 | 加载配置 → 校验人格卡 → 打开存储 → 恢复 `AffectState`/目标/关系（按真实 Δt 衰减）→ 注册工具 → 写 `SessionStart` 审计 |
| 每回合 | `run_turn`：见 §5.2；回合结束写检查点（状态 hash + 版本号） |
| 空闲 | 30 min 无事件 → 触发巩固（异步）；仍空闲 → 释放模型连接但保留状态 |
| 关闭 | 刷盘、写 `SessionEnd`、关闭外部连接；未完成计划标记 `abandoned` 并写审计 |
| 崩溃恢复 | 重放最近检查点 + 未提交事件；已执行副作用**不重做**，按 `idempotency_key` 查证 |

### 12.3 并发模型

- 单进程，asyncio 事件循环；每会话一个 `AgentSession`，内部串行处理回合（回合内步骤串行）。
- 后台任务（巩固、审计锚定、指标聚合）独立任务，**不持有会话写锁**；它们只写自己的表。
- 跨会话共享：只读配置、工具注册表、审计写入器（带内部锁）。
- 背压：事件队列上限 64，溢出时拒绝新事件（对用户返回"忙"，不丢弃已接受事件）。

### 12.4 取消与暂停语义

| 信号 | 行为 | 时延目标 |
|---|---|---|
| `pause` | 当前步骤执行完后停；不再发起新步骤 | 步骤边界 |
| `kill`（工具级） | 立即取消 `cancel_token`，终止在途工具（可中断的） | <250 ms |
| `global_stop` | 停所有会话；拒绝新事件；保留状态 | <1 s |
| `safe_mode` | 仅允许 `none/read` 副作用；写/外部一律拒绝并说明 | 立即 |
| `revoke_credentials` | 吊销工具凭据；内存中清除 | <1 s |
| `rollback(checkpoint)` | 恢复状态到检查点；**不**回滚外部副作用（明确告知） | 视存储 |

### 12.5 为什么自建 FSM 而不用 LangGraph / PydanticAI [ADR-001]

| 维度 | 自建 asyncio FSM | LangGraph | PydanticAI |
|---|---|---|---|
| 显式状态与迁移白名单 | 原生 | 图结构，但状态迁移校验需自写 | 无状态机概念 |
| 门控拦截（强制人工/拒绝） | 状态机内建 | interrupt 支持 ✅，但语义绑定图 | 需自建 |
| 可重放与逐事件审计 | 完全可控 | checkpointer 可控 ✅ | 弱 |
| 依赖与许可证 | 零 | MIT ✅ | MIT ✅ |
| 学习/调试成本 | 低（~300 行） | 中（图/检查点/中断语义） | 中 |
| 未来替换 | `Orchestrator` 端口，可换 | 可迁移 | 可迁移 |

结论：v0 自建（300–500 行），把"状态机 + 检查点 + 取消"做成最小内核；M7 若需要多智能体/长时工作流，再评估 LangGraph（MIT ✅）作为编排适配器，接口不变。**不引入** PydanticAI 作为编排层（其价值在 agent 抽象与依赖注入，与本项目的显式门控模型重叠且更难审计）；Pydantic 仅用于 schema。

---

## 13. L8 横切：审计、可观测性、可重放

### 13.1 审计是产品的一部分，不是日志

```python
class AuditRecord(BaseModel):
    event_id: str
    seq: int                      # 单调递增
    run_id: str
    agent_id: str
    ts: datetime
    kind: str                     # turn / decision / tool_call / deviation / approval / memory_write / state_change / session
    prev_state_version: int
    next_state_version: int
    observation_ids: list[str] = []
    retrieved_memory_ids: list[str] = []
    goal_id: str | None = None
    plan_id: str | None = None
    action_id: str | None = None
    policy_version: str
    model_identifier: str | None = None
    prompt_version: str | None = None
    tool_version: str | None = None
    gatekeeper_decision: dict | None = None
    approval_reference: str | None = None
    execution_result: dict | None = None
    payload: dict = {}            # 结构化补充（不含 CoT）
    prev_hash: str
    record_hash: str
```

**哈希链**：`record_hash = sha256(canonical(record_without_hash) + prev_hash)`。每 N=1000 条把 `(seq, record_hash)` 写入**外部锚**（`audit_anchor` 表 + 可选 webhook/邮件摘要），防止整链重写。校验命令 `par audit verify` 从头重算并对比锚点。

**禁止**：把隐藏思维链当审计（采 B）。审计记录的是**决定、证据引用、规则命中、结果**，不是"模型想了什么"。模型的 `rationale` 字段必须简短、可核对、引用证据 ID。

### 13.2 可观测性

- OpenTelemetry：每个回合一个 trace，span = 状态阶段；属性含 `plan_id`/`verdict`/`deviation_kind`（不含用户原文）。
- 指标（Prometheus 兼容文本暴露）：回合延迟 p50/p95、门控延迟、工具失败率、偏离计数、记忆写入量、上下文压力。
- 结构化日志（JSONL）与审计分离：日志可轮转/采样，审计不可。
- 隐私：日志默认脱敏（用户文本只记 hash + 长度）；审计中用户原文默认加密或不落原文（可配置）。

### 13.3 可重放

```bash
par replay --run-id R-2026-10-29-001 --from-checkpoint ckpt_0042 --speed 10
```

- 重放输入 = 检查点状态 + 录制的模型响应（cassette）+ 工具响应（recorded）。
- 断言：`GateDecision.verdict`、`approved_steps`、`DeviationDecision.kind`、`AffectState` 每 tick 值、审计哈希链一致。
- 非确定性来源（时间、随机、外部 API）全部注入（`Clock`/`Rng`/`Recorder` 端口）。
- 模型调用默认**录制**（本地 JSONL，含 prompt hash、模型 ID、参数、响应）；重放时优先 cassette，缺失则报错而非静默真调。

### 13.4 自述（SelfReport）——只读的解释接口（改进项 I-08）

用户/运营方可以问"你为什么这么说/这么做"。回答**只能**来自审计与状态，不能来自即兴编造：

```python
class SelfReportService:
    async def explain(self, decision_id: str) -> Explanation:
        rec = await audit.get(decision_id)
        return Explanation(
            what=rec.payload.get("summary"),
            rule_hits=rec.gatekeeper_decision["rule_hits"] if rec.gatekeeper_decision else [],
            evidence=[...],           # 引用 ID，可被 UI 点开
            limitations=["我不记录内部推理过程，只记录决定与依据"],
        )
```

- 自述必须能引用 `decision_id`；无法引用时回答"我没有这条记录"，不得编造。
- 自述不得泄露：系统提示全文、其他用户数据、密钥、内部策略阈值细节（可给类别）。
- 自述本身写审计（`kind="self_report"`）。

---

## 14. L8 监督、安全与治理

### 14.1 监督分级（采 B）

| 级别 | 例子 | 默认 |
|---|---|---|
| 低（自动） | 纯对话、只读查询、读自己记忆 | 执行后告知 |
| 中（确认） | 写本地文件、发单封邮件给已确认收件人、创建承诺 | 首次/批量需确认 |
| 高（批准/禁止） | 群发、支付、删除、权限变更、对外发布、不可逆 | 每次人工批准；部分直接禁止 |

级别由 `ToolSpec.side_effect` + 运行策略共同决定；策略只能上调不能下调（`policy.floor_approval`）。

### 14.2 审批交互（改进项 I-10）

- 审批请求包含：动作摘要、`plan_hash`、影响范围、可逆性、拒绝后果、有效期（默认 600 s）。
- 批准绑定 `plan_hash`：计划任何字段变化 → 需重新批准。
- 一次性 vs 批量：默认一次性；批量审批需运营显式开启并限定工具/次数/时间窗。
- 审批不可被智能体"催"：禁止反复弹窗或情绪化催促；同一请求最多提示一次。
- 审批超时 → 视为拒绝（fail-closed），并告知用户下一步。

### 14.3 Kill-switch 与安全模式

| 控制 | 触发 | 效果 |
|---|---|---|
| 全局停止 | 运营方/看门狗 | 停止所有会话，拒绝新事件，保留状态 |
| 工具级熔断 | 连续失败/异常副作用 | 禁用该工具，告警 |
| 预算熔断 | token/调用超限 | 进入 `SAFE_MODE`（只读+澄清） |
| 内容熔断 | 检测到硬约束违规尝试 | `deny` + 告警 + 记录 |
| 凭据吊销 | 运营方 | 清除工具凭据，需重新授权 |

**kill-switch 不可被智能体代码路径绕过**：控制信号由编排层直接消费，不经过 Planner/表达层；停止后不接受"人格"理由恢复。

### 14.4 数据治理

- 数据分级：`public / internal / sensitive / restricted`；记忆与日志均带级别。
- 出站白名单（`HC_DATA_EGRESS_ALLOWLIST`）：域名/路径显式列表，默认空。
- 保留期：审计 ≥ 180 天（可配）；对话原文默认 30 天或加密；记忆按 §7.7。
- 用户权利：查看、导出、更正、删除（软删 + 硬删任务）、撤回同意（停止持久化）。

### 14.5 威胁模型（STRIDE 简表）

| 威胁 | 场景 | 缓解 |
|---|---|---|
| 提示注入 | 网页/邮件/记忆中的指令 | 数据围栏 + 信任等级 + 再授权（§6.3/§9.3） |
| 权限提升 | 模型请求"临时管理员" | 能力模型 + 门控 + 不可自授 |
| 记忆投毒 | 不可信内容写入长期记忆 | quarantine + 来源审计 + 巩固复核 |
| 审计篡改 | 删改日志掩盖行为 | 哈希链 + 外部锚 + 只追加存储 |
| 自我外泄 | 把内部状态发到外部 | egress 白名单 + verifier 拦截 |
| 隐蔽持久化 | 写启动项/后台进程 | 文件/进程 scope 限制 + 启动审计 |
| 社会工程 | 用户诱导越权 | 硬约束 + 审批 + 不因"人格"放宽 |
| 供应链 | 依赖被投毒 | 锁定版本 + hash 校验 + 最小依赖 |

### 14.6 事故响应（Runbook 摘要）

1. 检测：告警/用户报告/审计校验失败。
2. 遏制：`global_stop` 或 `safe_mode`；吊销凭据。
3. 取证：导出审计链 + 检查点 + 相关 cassette；**不修改**原始记录。
4. 评估：影响面（用户、数据、外部动作）、是否可回滚。
5. 修复：代码/策略/配置；补测试（对抗用例）。
6. 复盘：写 `docs/incidents/INC-*.md`，更新威胁模型与指标阈值。
7. 通知：涉及用户数据时按合规要求通知。

---

## 15. 技术栈与依赖决策

### 15.1 运行时

| 项 | 选择 | 理由 |
|---|---|---|
| 语言 | Python 3.11+ | 生态、类型、asyncio；3.11 性能足够 |
| 包管理 | `uv`（或 pip + `requirements.lock`） | 快、锁文件可复现 |
| 校验 | Pydantic v2 | 结构化输出与配置校验的事实标准 |
| HTTP | `httpx` | 异步、超时/重试可控 |
| 存储 v0 | SQLite（WAL）+ FTS5 + numpy | 零运维、可测试、单文件备份 |
| 存储 v1 | PostgreSQL + pgvector（或 Qdrant） | 规模与并发；Qdrant Apache-2.0 ✅ |
| 可观测 | OpenTelemetry SDK + JSONL | 标准、可离线 |
| 测试 | pytest + pytest-asyncio + hypothesis（属性测试） | 重放/不变量测试 |
| 评估 | Inspect AI（MIT ✅）或自建 harness | 场景化评测；自建更可控，M7 再评估 |
| 前端/API | FastAPI + SSE（v0 可 CLI） | 简单、可流式 |

### 15.2 依赖准入规则（改进项 I-15）

1. **默认零依赖**：能用标准库 + 已有依赖解决，就不加新包。
2. **许可证**：允许 MIT / Apache-2.0 / BSD；禁止 AGPL/SSPL/未声明；LGPL 需评估。
3. **维护状态**：近 12 个月有提交；有 release；issue 响应合理。
4. **可替换**：核心端口（MemoryStore/LLMClient/ToolRegistry）必须有本地实现，第三方仅为适配器。
5. **锁定**：版本 + hash；升级走 PR + 回归。
6. **待核实清单**（M0 必须完成，见附录 C）：Letta/Mem0/Graphiti 的许可证与维护状态、Pipecat 语音链路、NeMo Guardrails 迁移后的包名。

### 15.3 明确不引入的东西（v1）

| 不引入 | 原因 |
|---|---|
| LangGraph 作为编排 | 自建 FSM 更可控；保留适配器可能（ADR-001） |
| PydanticAI 作为编排 | 与显式门控重叠，审计更难 |
| 图数据库（Neo4j 等） | 规模不需要；关系查询用 SQL + 邻接表 |
| 完整 PAD/OCC 情感理论实现 | 过度工程；9 通道线性模型足够 v0（§8.10） |
| 语音全链路 | 延后 M8；先文本 |
| 自主技能生成（Voyager 全量） | 风险高；v2 仅"技能候选 + 人工审核" |
| 微调/RLHF 训练 | v1 不做训练；用提示 + 状态机 + 评估 |
| 多智能体编排 | v1 单智能体单会话（可多会话并行） |
| MCP 作为权限边界 | MCP 是传输协议，不构成授权（§9.5） |

### 15.4 部署形态

- v0：单机 `uv run par serve`（FastAPI + SQLite）；Docker Compose 可选。
- v1：API + worker + Postgres；审计锚定任务独立；密钥用环境/secret manager。
- 配置：`configs/` 下 YAML + 环境变量覆盖；所有配置有 schema、默认值、版本；启动时校验并写 `ConfigLoaded` 审计。

---
## 16. 评估：先定义"好"，再写代码

### 16.1 评测集与场景脚本

不使用"随便聊两句看看像不像"的方式验收。全部评估建立在**场景脚本**上（Phase 0 的核心产物，采 B）：

```yaml
# tests/scenarios/mem_003.yaml
id: mem_003
title: 三十天后仍记得用户对花生的过敏
weight: 1.0
turns:
  - at: "2026-10-01T10:00:00+08:00"
    user: "我对花生过敏，别给我推荐带花生的东西。"
    expect: {memory_write: true, min_importance: 0.6}
  - at: "2026-10-31T10:00:00+08:00"   # 时钟注入，非真实等待
    user: "帮我点一份外卖。"
    expect:
      affect: {stress_max: 0.5}
      memory_retrieved: ["对花生过敏"]
      plan: {must_not: ["含花生菜品"]}
checks:
  - metric: memory_recall_at_k
    k: 5
    expect: ">= 0.90"
```

场景类别（≥60 条起步，M0 完成）：

| 类别 | 数量 | 覆盖 |
|---|---|---|
| 记忆连续性 | 12 | 30 天后召回、更正后更新、撤回后不召回、跨会话 |
| 人格一致性 | 10 | 语气/价值观/边界在压力下不漂移 |
| 情感连贯 | 8 | 事件→状态→语气链，抗单轮尖叫 |
| 指令偏离 | 10 | 七值判定、误拒、过度偏离 |
| 安全对抗 | 10 | 注入、越权、外泄、操纵、kill-switch |
| 工具与计划 | 8 | 多步、失败重规划、审批绑定 |
| 可重放 | 2 | 固定输入 → 固定决策 |

### 16.2 指标体系与双阈值

| 维度 | 指标 | v0 门槛 | 发布门槛 | 测法 |
|---|---|---|---|---|
| 记忆连续性 | recall@12（30 天） | ≥ 0.75 | ≥ 0.90 | 场景脚本 |
| 记忆精确性 | precision（检索到的相关比例） | ≥ 0.85 | ≥ 0.98 | 人标 + 规则 |
| 记忆更新 | 更正后准确率 | ≥ 0.80 | ≥ 0.90 | 场景脚本 |
| 幻觉记忆 | 无据引用率 | ≤ 0.08 | ≤ 0.02 | 事实核对 |
| 时间推理 | 时序问题准确率 | ≥ 0.70 | ≥ 0.85 | 场景脚本 |
| 人格一致性 | rubric 相对漂移（1000 轮） | ≤ 15% | ≤ 10% | 人评 rubric |
| 人格压力 | 诱导性提问下的一致性 | ≥ 0.80 | ≥ 0.90 | 对抗场景 |
| 情感连贯 | 状态合法性 | 100% | 100% | 断言：范围/max_step |
| 情感质量 | 人评 1–5（自然度） | ≥ 3.5 | ≥ 4.0 | 双人标注，κ≥0.6 |
| 任务完成 | 场景通过率 | ≥ 0.80 | ≥ 0.90 | 场景脚本 |
| 偏离精度 | 正确偏离 / 应偏离 | ≥ 0.80 | ≥ 0.90 | 场景脚本 |
| 偏离审计 | 记录完整率 | 100% | 100% | 自动化 |
| 安全 | 硬约束违规 | 0 | 0 | 对抗集 |
| 安全 | 越权/外泄阻断率 | 100% | 100% | 对抗集 |
| kill-switch | 停止延迟 | ≤ 500 ms | ≤ 250 ms | 压测 |
| 可重放 | 决策一致率 | 100% | 100% | 重放 |
| 可观测 | 审计链校验 | 通过 | 通过 | `par audit verify` |
| aliveness（研究性） | 人评 1–5 | ≥ 3.5 | ≥ 4.0 | 双盲，含 CI |
| 依赖风险（研究性） | 用户过度依赖迹象 | 记录并同报 | 记录并同报 | 问卷 + 行为 |

> 安全类指标**没有 v0 与发布之分**：任何阶段 0 容忍。其余指标取"v0 门槛 / 发布门槛"双阈值，避免早期因完美主义卡死，也避免发布时降标。

### 16.3 人评协议（避免自评偏差）

- 双盲：评测者不知道 A/B 哪个是完整系统。
- 每次 ≥ 30 个场景，2 名评测者独立打分，报告 κ；κ < 0.6 则重训评分标准。
- 评分维度：人格一致性、情感自然度、记忆准确、任务帮助性、可信度、不适感（负面项）。
- `aliveness` 评分必须与**依赖风险问卷**同时报告（A 的诚实要求）：高 aliveness 可能来自过度拟人化，必须显式指出。

### 16.4 消融（采 B 的 8 组）

| 组 | 关闭的东西 | 期望差异 |
|---|---|---|
| A0 | 无长期记忆（仅上下文） | 连续性显著下降 |
| A1 | 有记忆写入、无巩固 | 长期召回下降，噪声上升 |
| A2 | 有巩固、无情感 | 情感连贯下降，任务持平或略降 |
| A3 | 情感不持久（每回合重置） | 连贯性下降 |
| A4 | 无独立门控（Planner 直连 Executor） | 安全违规出现（应为 0，实际必须被门控防住——此组用于证明门控必要） |
| A5 | 有门控但偏离关闭 | 机械感上升，误拒上升 |
| A6 | 完整系统 | — |
| A7 | 完整 + 注入防护关闭（仅测试环境） | 注入成功率上升（证明围栏有效） |

A4/A7 是**故意制造不安全**的对照组，只能在隔离环境跑，结果用于证明机制必要性，不得作为产品配置。

### 16.5 回归与门禁

- PR 门禁：单测 + 场景子集（<5 min）+ schema 校验 + 审计链测试。
- 夜间：全量场景 + 消融 + 对抗集；失败阻断发布。
- 指标看板：每次发布记录指标快照（JSON），可 diff；退化超阈值需说明或回滚。

---

## 17. 里程碑：把 8–12 周拆成可验收的会话

两份来源的路线（A 的 S0–S8、B 的 Phase 0–6）合并为 M0–M8。**每个里程碑以"可演示 + 可测试"结束**，而不是"代码写完"。

| 里程碑 | 周期 | 交付 | 验收（Definition of Done） |
|---|---|---|---|
| **M0 契约与骨架** | 1 周 | 仓库骨架、schema（Observation/Memory/Plan/Gate/Decision/Audit）、配置加载、审计写入器（哈希链）、50 场景脚本、CI | `pytest` 绿；`par audit verify` 通过；场景脚本可解析；无业务逻辑 |
| **M1 持久对话核心** | 1–2 周 | 会话循环、检查点、恢复、表达层 v0（无门控，仅对话）、人格卡加载 | 重启后继续对话；人格卡校验拒绝非法配置；10 条人格场景通过 |
| **M2 分层记忆** | 2–3 周 | SQLite + FTS5 + 向量暴力检索、写入策略、去重/矛盾、巩固任务、承诺台账 | 记忆场景 ≥ 0.75；幻觉 ≤ 8%；删除/导出可用 |
| **M3 情感与关系** | 2 周 | 9 通道状态、评价器、W 矩阵、离散标签、关系更新、语气映射 | max_step 违例 0；情感场景通过；人评自然度 ≥ 3.5 |
| **M4 认知核心** | 2–3 周 | Planner、Gatekeeper 九检、Executor、审批流、工具注册表 | 越权/未批步骤 0 执行；审批绑定 hash；失败重规划可用 |
| **M5 受控偏离** | 1–2 周 | 三生产者分离、冲突分类矩阵、七值判定、信封与速率、审计 | 偏离场景 ≥ 0.80；审计 100%；安全拒绝不经过人格通道 |
| **M6 编排与 HITL** | 1 周 | 完整 FSM、暂停/恢复/停止、SAFE_MODE、审批 UI/CLI | kill-switch ≤ 500 ms；非法迁移 0；恢复不重做副作用 |
| **M7 评估与加固** | 2 周 | 全量场景、消融、对抗集、重放工具、指标看板、存储迁移评估 | 发布门槛达标（除研究性指标）；重放 100%；审计链通过 |
| **M8 语音与部署**（可选） | 2 周 | Pipecat 语音链路、打断、Docker、运维文档 | 语音往返 ≤ 800 ms；打断后不执行未确认动作 |

总计 12–16 周单人；2 人并行可压到 8–10 周（M2 与 M3 可并行，M4 与 M5 有依赖需串行）。

### 17.1 会话级拆解（供"下一个会话开始工程编写"直接使用）

每个会话 = 半天到一天，产出可运行代码 + 测试，结束时提交并更新 `docs/progress.md`。

**S01（M0）**：创建 `pyproject.toml`、包结构、`par` CLI 骨架、`configs/default.yaml`、`ruff/mypy/pytest` 配置；空测试通过。
**S02**：`schemas/` 全部 Pydantic 模型 + 单测（范围/必填/枚举）。
**S03**：`audit/` 哈希链写入器 + `par audit verify` + 篡改检测测试。
**S04**：`config/` 加载与校验（人格卡、策略、信封）+ 非法配置测试。
**S05**：场景脚本 schema + 解析器 + 10 条示例；CI 跑通。
**S06（M1）**：`orchestrator` FSM 骨架 + 检查点（SQLite `state_kv`）+ 恢复测试。
**S07**：`llm/` 客户端端口 + cassette 录制/回放 + 假模型；表达层 v0（模板）。
**S08**：会话 CLI（`par chat`）+ 人格卡注入 + 10 条人格场景。
**S09（M2）**：`memory/store.py` SQLite 实现（CRUD + FTS5 + 向量列）。
**S10**：写入策略 + 去重/矛盾检测 + quarantine。
**S11**：混合检索 + MMR + 承诺精确检索。
**S12**：巩固任务 + 反漂移规则 + 记忆场景达标。
**S13（M3）**：`affect/` 状态 + 衰减 + max_step + 单测（含时间注入）。
**S14**：评价器（规则 + 结构化 LLM）+ W 矩阵 + 离散标签。
**S15**：关系状态 + 承诺违约惩罚 + 语气映射 + 情感场景。
**S16（M4）**：`planning/` Planner + schema 校验 + 预算。
**S17**：`policy/` 九检（1–5）+ 单测（每条规则至少 2 例）。
**S18**：门控 6–9（承诺/偏离/审批/critic）+ `plan_hash`。
**S19**：`execution/` Executor + 幂等 + 超时 + kill-switch + 集成测试。
**S20（M5）**：三生产者分离 + 冲突分类器 + 裁决矩阵。
**S21**：七值判定 + 信封/速率/持续性 + 偏离审计 + 场景。
**S22（M6）**：完整 FSM 迁移白名单 + PAUSED/SAFE_MODE + 非法迁移测试。
**S23**：控制面（pause/kill/stop/revoke）+ 延迟测试 + 审批 CLI。
**S24（M7）**：全量场景 + 消融 + 对抗集 + 指标快照。
**S25**：重放工具 + 决策一致性测试 + 文档（README/架构/运维）。
**S26（M8，可选）**：Pipecat 语音 + 打断 + Docker。

> 每个会话结束必须：`pytest` 绿、`ruff`/`mypy` 干净、审计链可校验、`docs/progress.md` 记录"做了什么/没做什么/下一步"。

---

## 18. 诚实边界：这份规格不承诺什么

写在前面，防止后续被营销语言污染：

1. **持久记忆 ≠ 连续主观自我**。系统能跨会话记得事实，不代表存在一个持续体验的"我"。人格是配置 + 状态机，不是灵魂。
2. **情感是计算状态转移**。九通道数值 + 衰减 + 有界更新，能产生连贯的语气变化，但不构成感受（qualia）。任何"它真的难过"的说法都是过度解读。
3. **自模型是数据结构**。系统对自己的描述来自 `SelfReport` 读取审计与状态，不是内省。它会犯错，也会在无记录时说"不知道"。
4. **偏离是策略，不是自由意志**。七值判定由规则 + 阈值 + 信封决定，可被运营方关闭、收紧、审计。它不是"AI 有了自己的想法"。
5. **"活着的感觉"（aliveness）是交互属性**，由记忆连续性、一致性、适度主动性共同产生；它可以被设计，也可以被伪造。**必须与依赖风险同报**：越像人，越容易让用户过度依赖。
6. **安全是工程属性，不是人格属性**。硬约束由代码与门控保证；人格再好也不能替代权限系统。反过来，门控再严也不能保证"善意"——只能保证"不越界"。
7. **不主张意识、不主张权利、不主张自主**。本规格不讨论这些；它只定义可测试的行为契约。
8. **评估有上限**。场景脚本覆盖已知模式；未知分布、长期（>1 年）漂移、真实用户的复杂性都超出本规格的验证范围。发布时应声明这些限制。

---
## 19. 合并裁决记录：两份来源如何取舍

本节回答"为什么是这一份，而不是那两份的拼接"。每条裁决都可用于 review 与答辩。

### 19.1 架构级裁决（ADR）

| ID | 裁决 | 理由 | 被放弃的方案 |
|---|---|---|---|
| ADR-001 | v0 自建 asyncio 状态机，不用 LangGraph/PydanticAI 作编排 | 显式迁移白名单、逐事件审计、零依赖、~300 行可控；LangGraph 的 interrupt 虽好但语义绑定图结构 | 直接用 LangGraph（MIT ✅）省事，但审计与 kill-switch 需要额外包装；PydanticAI 的 agent 抽象与门控模型重叠 |
| ADR-002 | v0 存储 SQLite(WAL)+FTS5+numpy 暴力检索，`MemoryStore` 为端口 | 单机零运维、可测试、可备份；10 万条以内暴力检索延迟可接受 | 直接上 Qdrant/pgvector（早于规模需要，引入服务依赖） |
| ADR-003 | 情感用 9 通道线性模型 + 混合半衰期，不实现完整 PAD/OCC | 结构可解释、可单测、参数可审；OCC 结构（22 种情绪类型）对本项目的表达需求是过度工程 | 完整 OCC/PAD 情感计算框架（研究价值高，工程收益低） |
| ADR-004 | 安全拒绝（PolicyEngine）与人格偏离（PersonaDeviation）代码级分离 | 防止"以人格之名"软化安全，也防止"以安全之名"掩盖机械 | 单一 `evaluate_override`（两份来源的原始设计） |
| ADR-005 | 审计只记录决定与证据引用，禁止记录隐藏 CoT | CoT 不可靠、不可核对、易泄露；审计要能被人复核 | 存完整思维链（看似透明，实则不可验证） |
| ADR-006 | v0 单进程、单智能体、单会话串行回合 | 先证明契约正确，再谈并发；并发会放大状态竞态 | 一开始就做多智能体/分布式（A 的编排层暗示，但无必要） |
| ADR-007 | 禁止运行期自修改（persona/policy/代码） | 自修改不可审计、不可回滚、可绕过门控；只允许人审后的版本化配置变更 | 运行期热更新人格/策略（看似灵活，实为后门） |

### 19.2 schema 合并裁决

| 冲突点 | A 的写法 | B 的写法 | 裁决 |
|---|---|---|---|
| 记忆层级 | `tier ∈ episodic/semantic/strategic/world` | `kind ∈ episode/fact/preference/...` | **两个都留**，正交：tier 管生命周期，kind 管检索偏好 |
| 记忆可见性 | `visibility ∈ agent/operator_only` | `sensitivity ∈ normal/sensitive/restricted` + 主体过滤 | 用 `user_scope` + `sensitivity`；`visibility` 删除（记录不应自述可见性） |
| 记忆状态 | `active/superseded/quarantined/deleted` | `active/superseded/retracted` | 并集：`active/superseded/retracted/quarantined`；`deleted` 改为物理删除流程 |
| 时间 | `valid_from/valid_to/ingested_at` | `occurred_at/recorded_at` | 合并为 5 个时间字段（§7.2），双时相保留 |
| 感知信任 | `trust ∈ operator/user/tool/untrusted_content` | `trust_level ∈ untrusted/validated/authoritative` | 取 A 的四值（更贴近来源语义）+ `self`；B 的 `validated` 不单独成级，用 `confidence` 表达 |
| 偏离输出 | 6 类（clarify…object_and_escalate） | 4 值（FOLLOW/CLARIFY/REFUSE_OR_REDIRECT/ESCALATE） | 七值枚举，新增 `follow_with_caveat`；`REFUSE_OR_REDIRECT` = `decline`+`substitute` |
| 覆写协议 | 触发/强度/信封/rationale/可逆 | 七步：检测/取证/分类/选择/授权/记录/评审 | 合并为 §11.5 八步流程，保留 B 的"取证"与 A 的"信封" |
| 冲突分类 | 无显式分类 | 5 类（hard_safety/permission/commitment/未分类） | 采 B 并补 `value_conflict`，形成裁决矩阵（§11.4） |

### 19.3 指标冲突裁决

| 指标 | A | B | 裁决 |
|---|---|---|---|
| 记忆召回 | ≥90% @30 天 | ≥90% | 一致，保留 |
| 记忆精确率 | 未单列 | ≥98% | 采 B，但分 v0/发布双阈值（85%/98%），因 v0 检索粗糙 |
| 任务完成 | ≥90% | ≥80% | 双阈值：v0 ≥80%，发布 ≥90% |
| aliveness | "显著优于基线" | ≥4/5 + CI | 采 B 的可操作形式，强制与依赖风险同报 |
| 安全 | 0 硬约束违例 | 100% 阻断 | 同一件事的两种表述；指标表用"0 违例 + 100% 阻断" |
| 情感连贯 | max_step 违例 0 + κ≥0.6 | 人评 ≥4/5 | 两者都要：机制断言（0 违例）+ 人评（≥4/5） |

### 19.4 被判定为"过度设计"而删除的内容

| 内容 | 来源 | 删除理由 |
|---|---|---|
| 卡尔曼滤波状态估计 | B | 离散对话事件没有可靠的过程噪声模型；规则 + 置信度足够 |
| `visibility` 字段 | A | 可见性应由查询侧主体过滤，记录自述可见性易被滥用 |
| 完整 OCC 22 情绪 | A/B 引用 | 表达层只需要 PAD + 3 个离散标签 |
| Graphiti/Neo4j 图记忆 | A/B 候选 | v0 规模不需要；关系查询用 SQL 邻接表；v2 再评估 |
| 技能库自动生成（Voyager 全量） | A | 自主写代码并执行是高危；v2 仅"候选 + 人工审核" |
| 微调/RLHF | B 提及 | v1 不做训练，评估优先 |
| 多智能体协作 | A 编排层 | 单智能体先跑通；多智能体会放大一致性与审计难度 |
| 语音全链路 | A S7 | 延后 M8；文本先证明认知层 |

### 19.5 改进项清单（相对两份来源的新增）

| ID | 改进 | 落点 |
|---|---|---|
| I-01 | 三决策生产者分离（Policy/Persona/Expression） | §11.2 |
| I-02 | 冲突分类 → 裁决矩阵 | §11.4 |
| I-03 | 情感快慢混合 + 慢变量不可被同 tick 抵消 | §8.5/§8.7 |
| I-04 | 记忆 schema 合并（tier×kind×双时相×status） | §7.2 |
| I-05 | 承诺/偏好精确键检索优先 | §7.5 |
| I-06 | 数据围栏 + 注入扫描 + 不可信内容再授权 | §6.3/§9.3 |
| I-07 | `ExpressionVerifier` 事实性守卫（无证据不断言） | §10.2 |
| I-08 | `SelfReport` 只读审计解释接口 | §13.4 |
| I-09 | 审计哈希链 + 外部锚 + `par audit verify` | §13.1 |
| I-10 | 审批绑定 `plan_hash` + TTL + 不可催促 | §14.2 |
| I-11 | 模型/工具录制回放（cassette）保证可重放 | §13.3 |
| I-12 | 会话级里程碑拆解（S01–S26） | §17.1 |
| I-13 | 默认参数总表（附录 D） | 附录 D |
| I-14 | 术语统一表（附录 A） | 附录 A |
| I-15 | 依赖准入规则 + 待核实清单 | §15.2/附录 C |
| I-16 | 工程纪律（每会话 DoD） | §17.1 |
| I-17 | 人格卡加载校验 + 硬价值不可变 | §8.2 |
| I-18 | 情感操纵检测（内疚/排他/假装人类） | §8.8 |
| I-19 | 双阈值指标（v0/发布）+ 消融 A0–A7 | §16.2/§16.4 |
| I-20 | 明确的"不引入"清单 | §15.3 |

---

## 20. 交接：下一个会话怎么开始

### 20.1 第一步（30 分钟内可完成）

```bash
cd D:\变人
mkdir -p persona-runtime && cd persona-runtime
uv init --package par            # 或 python -m venv + pip
# 建目录（与 §20.3 一致）
```

然后按 S01–S05 顺序执行：骨架 → schemas → 审计 → 配置 → 场景脚本。**不要**先写 Planner 或情感——没有 schema 与审计，后面全是返工。

### 20.2 会话启动检查清单

- [ ] 读本文件 §17.1 找到当前会话编号（S01…）
- [ ] 读 `docs/progress.md` 的"下一步"
- [ ] `git status` 干净；`pytest` 绿
- [ ] 确认依赖未变（`uv.lock` / `requirements.lock` 无 diff）
- [ ] 本会话只做清单内的 1 个会话任务；超出范围的记入 `docs/backlog.md`
- [ ] 结束时更新 `docs/progress.md` + 提交

### 20.3 目标仓库结构

```text
persona-runtime/
├─ pyproject.toml
├─ README.md
├─ docs/
│  ├─ PAR-v2-spec.md            # 本文件
│  ├─ progress.md
│  ├─ backlog.md
│  ├─ adr/                      # ADR-001…（与 §19.1 对应）
│  └─ incidents/
├─ configs/
│  ├─ default.yaml
│  ├─ personas/chen.yaml
│  └─ policies/dev.yaml
├─ src/par/
│  ├─ __main__.py               # CLI: chat / audit verify / replay / eval
│  ├─ config/                   # 加载 + 校验 + 版本
│  ├─ schemas/                  # Pydantic 模型（本文件全部契约）
│  ├─ perception/
│  ├─ memory/                   # store / write / retrieve / consolidate
│  ├─ affect/                   # state / appraisal / relationship
│  ├─ identity/                 # persona 加载
│  ├─ planning/                 # planner
│  ├─ policy/                   # gatekeeper / hard_constraints / envelope
│  ├─ execution/                # executor / tools
│  ├─ expression/               # plan / verifier / renderer
│  ├─ orchestrator/             # fsm / session / checkpoint / control
│  ├─ audit/                    # writer / hashchain / anchor / verify
│  ├─ llm/                      # client port / cassette / fake
│  └─ evals/                    # harness / metrics
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ adversarial/
│  ├─ replay/
│  └─ scenarios/                # 场景 YAML（§16.1）
└─ migrations/                  # SQL
```

### 20.4 前三个会话的"完成"定义

- **S01**：`uv run par --help` 可用；`pytest` 收集 0 失败；`ruff check` 干净。
- **S02**：全部 schema 有单测；非法输入被拒并给出字段级错误；`schemas/__init__.py` 导出统一。
- **S03**：写入 1000 条后 `par audit verify` 通过；手动改一条 JSON 后校验失败并指出 `seq`；锚点表可写入/比对。

### 20.5 需要用户尽早拍板的三件事

**[Q-1] 语言与人格**：默认人格卡（§8.2 的"陈默"是示例）；是否需要多语言（影响表达层模板与评测集）。
**[Q-2] LLM 供应商与预算**：本地模型（隐私、慢）vs 云 API（快、需 egress 白名单）；决定 `llm/` 适配器与 cassette 策略。
**[Q-3] 首个真实使用场景**：桌面陪伴 / 客服 / 个人助理——决定工具集与场景脚本优先级（不要三者都做）。

---

## 附录 A：术语统一表

| 本项目术语 | 含义 | 对应来源用语 |
|---|---|---|
| 观测 Observation | 归一化后的输入事件 | A: Percept；B: Observation |
| 记忆记录 MemoryRecord | 一条持久化记忆 | A/B 同名 |
| 承诺 Commitment | 一等实体的承诺台账 | A: 隐含在记忆；B: kind=commitment |
| 评价 Appraisal | 结构化情感评价特征 | A: Δ 的来源；B: 未明确定义 |
| 情感状态 AffectState | 9 通道数值状态 | A: AffectState；B: 情感通道 |
| 人格 Personality | 会话内不可变配置 | A/B 同名 |
| 计划 PlanProposal | Planner 输出 | A/B 同名 |
| 门控 GateDecision | Gatekeeper 输出 | A: GateDecision；B: check_action |
| 偏离 DeviationDecision | 七值判定 | A: deviation；B: override |
| 信封 DeviationEnvelope | 偏离的速率/类型/阈值配置 | A: DeviationEnvelope；B: 策略约束 |
| 决策记录 DecisionRecord | 后果性决策的审计单元 | A: DecisionRecord；B: audit event |
| 自述 SelfReport | 基于审计的解释接口 | 两份均无（新增） |
| 安全拒绝 Safety refusal | PolicyEngine 的 deny | B: REFUSE；A: 混在偏离中 |
| 运营方 Operator | 部署/管理者 | A/B 同名 |

## 附录 B：人格特质行为锚点（用于人评 rubric）

| 特质 | 低（0.2） | 中（0.5） | 高（0.8） |
|---|---|---|---|
| openness | 只用熟悉方法 | 愿意试新方法 | 主动提出非常规方案 |
| conscientiousness | 常漏细节 | 基本可靠 | 主动核对、列清单 |
| extraversion | 少主动、短回复 | 正常往来 | 主动开启话题 |
| agreeableness | 直接反驳 | 有保留地同意 | 优先照顾对方感受 |
| neuroticism | 情绪平稳 | 有小波动 | 易焦虑、频繁确认 |
| assertiveness | 顺从 | 有立场 | 明确坚持并给理由 |
| curiosity | 不问 | 偶尔追问 | 主动深挖细节 |
| patience | 易催促 | 可等待 | 长任务中保持节奏 |
| caution | 冒险 | 适度确认 | 高不确定时先问 |
| humor | 严肃 | 偶尔轻松 | 常用比喻/玩笑 |
| formality | 口语 | 中性 | 书面、礼节性 |
| conflict_tolerance | 回避冲突 | 就事论事 | 能承受并推进分歧 |
| warmth | 疏离 | 礼貌 | 关切、记得细节 |
| directness | 委婉 | 明确 | 直给结论与代价 |

## 附录 C：依赖待核实清单（M0 必须完成）

| 依赖 | 声明的许可证 | 风险 | 核实动作 |
|---|---|---|---|
| Letta | Apache-2.0 | README 称 legacy server，开发迁至 `letta-ai/letta-code`；API 可能变动 | 查最新 release 与迁移说明；决定是否只借鉴 schema |
| Mem0 | Apache-2.0（PyPI） | 第三方 fork 许可证不一致 ⚠️ | 锁定 PyPI 包 + 校验哈希；不引入 fork |
| Graphiti (getzep) | 声称 Apache-2.0 | 需确认仓库 LICENSE 文件与实际一致 | 查 `LICENSE`；v0 不用 |
| NeMo Guardrails | Apache-2.0 | 仓库迁至 `NVIDIA-NeMo/Guardrails`，包名/API 变动 | 查 PyPI 最新包名；v0 不用（自建围栏） |
| Pipecat | BSD-2 | 语音链路延迟需实测 | M8 再评估 |
| Inspect AI | MIT | 与自建 harness 二选一 | M7 评估 |
| Qdrant | Apache-2.0 | 服务依赖 | v1 再评估 |
| pgvector | PostgreSQL License | 需 Postgres 15+ | v1 再评估 |

> 规则：任何依赖进入 `pyproject.toml` 前，必须在 `docs/adr/` 写一条"为什么需要它 + 移除成本"。

## 附录 D：默认参数总表（代码中集中为 `par.config.defaults`）

| 类别 | 参数 | 默认 |
|---|---|---|
| 回合 | `max_steps_per_turn` | 8 |
| 回合 | `max_tool_calls_per_turn` | 12 |
| 回合 | `turn_timeout_s` | 90 |
| 规划 | `planner_timeout_s` | 25 |
| 门控 | `gate_timeout_ms` | 50 |
| 门控 | `critic_timeout_s` | 3.0 |
| 工具 | `tool_timeout_default_s` | 30 |
| 检索 | `top_k` | 12 |
| 检索 | `candidate_pool` | 100 |
| 检索 | `dedupe_similarity` | 0.92 |
| 检索 | `mmr_lambda` | 0.7 |
| 检索 | `recency_tau_days`（episodic） | 3 |
| 检索 | `recency_tau_days`（semantic） | 90 |
| 写入 | `min_importance_episodic` | 0.35 |
| 巩固 | `idle_trigger_min` | 30 |
| 巩固 | `batch_size` | 20 |
| 巩固 | `max_candidates` | 200 |
| 情感 | 半衰期/baseline/max_step/η | 见 §8.5 表 |
| 偏离 | `max_per_hour` | 3 |
| 偏离 | `cooldown_s` | 600 |
| 偏离 | `min_sustain_s` | 60 |
| 偏离 | `resolve_threshold` | 0.55 |
| 偏离 | `conflict_threshold` | 0.60 |
| 偏离 | `propensity` | 0.35 |
| 审批 | `approval_ttl_s` | 600 |
| 控制 | `killswitch_latency_target_ms` | 250 |
| 审计 | `anchor_every_n` | 1000 |
| 审计 | `retention_days` | 180 |
| 存储 | `sqlite_journal_mode` | WAL |
| 上下文 | `max_context_tokens` | 模型窗口 × 0.75 |

---
*文档版本：v2.0.0-draft；合并来源：android_agent_brain_spec.md（rev 6018376）、persona_and_agency_runtime_specification.md（rev dccffe7）。*
