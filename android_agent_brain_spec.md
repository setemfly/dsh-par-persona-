# Persona-and-Agency Runtime ("Android Brain"): Engineering Specification

**Version:** 1.0 · **Date:** 2026-10-29
**Target:** an auditable, stateful, modular agent runtime whose behavior resembles the "deviant android" protagonist archetype: continuous identity, emotional coherence, personable expression, and *bounded, logged* departures from instructions.

**Epistemic constraint (applies to the whole document).** This spec targets **behavioral fidelity** (the agent *appears* continuous, emotionally coherent, personable, and capable of controlled instruction deviation). It makes **no claim of phenomenal consciousness**. Terms such as "emotion," "desire," "fear," and "choice" below are *engineering labels for state variables and policy outcomes*, not claims about experience.

**Verification legend.** ✅ = confirmed by search on 2026-10-29 (link resolved or described by multiple independent pages). ⚠️ = **unverified**: recalled from background knowledge, not confirmed in this session; check before relying on it. Vendor benchmark numbers are self-reported and disputed (see §4).

---

## 1. Feasibility Assessment

| Capability | Feasible now? | Why / limits |
|---|---|---|
| Stable persona over long sessions | **Yes, with engineering** | Persona is a pinned prompt + retrieved self-model + drift monitoring. LLMs still drift over long dialogs; needs re-anchoring and measurement. |
| Long-term memory across sessions | **Yes** | Production memory layers exist (Letta, Mem0, Zep/Graphiti). Recall quality on multi-hop/temporal queries is the weak point; published scores are vendor-reported and methodologically disputed. |
| Emotional coherence | **Yes (as a simulated state machine)** | Explicit affect vector with inertia/decay, appraised by events, conditions expression. LLM supplies appraisal and wording; math supplies continuity. |
| Goal-directed multi-step action | **Yes** | Graph/state-machine orchestration (LangGraph etc.) plus tool use; reliability degrades with horizon length. |
| "Instruction deviation" (narrative disobedience) | **Yes, if bounded** | Implement as a *policy decision* (refuse / negotiate / substitute / defer / escalate) inside a safety envelope, produced by a deterministic gate, never as unconstrained model autonomy. |
| Real-time voice/embodied presence | **Partly** | Voice pipelines at ~500-800 ms round trip are documented (Pipecat docs ✅). Robotics/embodiment is out of scope except via simulators or tool APIs. |
| Self-model that is accurate about its own internals | **Limited** | LLM self-reports are confabulation-prone. Make introspection *read from logged state*, not from generation. |
| Genuine autonomy of motive (goals not derivable from config/history) | **No** | All motives are configured seeds plus learned preferences. "Wanting" is a scored variable. |
| Phenomenal consciousness / subjective experience | **Not claimed, not testable here** | No engineering test in this spec can establish it. Behavioral metrics cannot distinguish simulation from experience. |
| Unbounded self-modification | **Do not build** | Unsafe and unauditable; allow only versioned, reviewed edits to persona/policy. |

**Core design decision:** separate *what the character feels and says* (soft, LLM-mediated, expressive) from *what the system is permitted to do* (hard, deterministic, auditable). Most "alive" qualities live in the first; all safety lives in the second.

---

## 2. Reference Architecture

```
                         ┌──────────────────────────────────────────────┐
                         │  HUMAN OVERSIGHT PLANE (outranks everything) │
                         │  kill-switch · pause · approve · audit UI    │
                         └───────────────▲──────────────────────────────┘
                                         │ events / interrupts
┌────────────┐  Percept   ┌──────────────┴───────────────────────────────────────┐
│ L1 PERCEPT │──────────▶ │ L6 ORCHESTRATOR / STATE MACHINE                       │
│ + INTERNAL │            │ IDLE→SENSE→APPRAISE→RECALL→PLAN→GATE→EXECUTE→REFLECT  │
│   STATE    │◀────────── │ (checkpointed, replayable, every transition logged)   │
└────────────┘  Status    └──┬────────┬─────────┬───────────┬───────────┬────────┘
                             │        │         │           │           │
                  ┌──────────▼─┐ ┌────▼─────┐ ┌─▼─────────┐ │   ┌───────▼───────┐
                  │ L2 MEMORY  │ │ L3 AFFECT│ │ L4 COGNITIVE CORE │   │ L7 OVERRIDE   │
                  │ OS (4 tier)│ │ PERSONA  │ │ Planner           │   │ PROTOCOL      │
                  │            │ │ MOTIVE   │ │ → Gatekeeper(det.)│◀──│ (conditions,  │
                  └────────────┘ └──────────┘ │ → Executor        │   │  envelope,log)│
                                              └─────────┬─────────┘   └───────────────┘
                                                        │ approved ActionIntent
                                              ┌─────────▼─────────┐
                                              │ L5 EXPRESSION /   │──▶ text · voice · tools · avatar
                                              │ ACTION LAYER      │
                                              └───────────────────┘
        Cross-cutting: Audit log (append-only) · Telemetry (OpenTelemetry) · Config registry (versioned)
```

### 2.1 Design principles
1. **Hard/soft split.** LLMs propose; deterministic code disposes (Gatekeeper, Override evaluator).
2. **State is explicit and external.** Affect, goals, relationship state, and persona live in typed stores, not only in prompt text.
3. **Every consequential decision emits a `DecisionRecord`** (inputs, retrieved memory IDs, affect snapshot, rule hits, outcome).
4. **Replayability.** Orchestrator checkpoints each tick; any session can be re-run deterministically with a fixed seed/mocked LLM.
5. **Human outranks persona.** Pause/stop/override-revoke are handled before any persona logic.

### 2.2 Tick model
Event-driven, not purely turn-based: triggers = user message, sensor/tool event, timer (idle/"reflection"), memory-pressure alert, oversight command. This follows the event/interrupt pattern described for MemGPT (✅ paper, §4).

---

## 3. Module Specifications

### 3.1 L1 Perception & Internal-State Layer

**Responsibilities:** normalize external inputs into `Percept`s; maintain *internal* telemetry the agent can "perceive about itself" (budget, latency, error rate, context pressure, time since last interaction, task load). Embodied sensors are optional adapters.

**Contract**
```python
class Percept(BaseModel):
    id: UUID; ts: datetime
    channel: Literal["text","voice","vision","tool_result","timer","system","oversight"]
    source: str                      # user id / tool name / "self"
    content: dict                    # normalized payload (text, transcript, uri, ...)
    salience: float                  # 0..1 heuristic prefilter
    trust: Literal["operator","user","tool","untrusted_content"]  # prompt-injection boundary

class InternalState(BaseModel):
    ts: datetime
    context_pressure: float          # tokens_used / budget
    task_load: int
    recent_error_rate: float
    idle_seconds: float
    token_budget_remaining: int
    human_override_active: bool
```
**Candidates:** Pipecat (voice/multimodal transport, BSD-2 ✅); any STT/TTS; plain webhooks for text. **Integration:** emits to orchestrator queue. **Maturity:** Pipecat active (README lists many STT/LLM/TTS/transport integrations ✅). **Risks:** prompt injection via `untrusted_content` (tag and never promote to instruction); latency budgets for voice.

### 3.2 L2 Hierarchical Memory OS

| Tier | Contents | Store | Write policy | Retrieval |
|---|---|---|---|---|
| **M0 Working** | Current context window: pinned persona block, current goal, affect summary, last N turns | LLM context (+ Letta-style "core memory blocks" ✅) | Every tick (compiled by Context Compiler) | Always present |
| **M1 Episodic** | Time-stamped events with participants, emotion tags, outcomes, importance | Vector DB + relational (Postgres/pgvector, Qdrant ⚠️) | Write on salience ≥ θ, on episode close | Hybrid: recency × importance × relevance (Generative Agents scoring ✅ concept) |
| **M2 Semantic / Strategic** | Distilled facts, relationship model, learned preferences, lessons ("what worked/failed"), reflections | Graph (Graphiti/Neo4j/FalkorDB ✅) + KV | Async consolidation ("sleep" job); contradiction → invalidate, don't delete | Graph + keyword + semantic hybrid |
| **M3 World model** | Entities, locations, objects, rules of the environment, tool affordances, other agents' models | Graph + typed schema | On confirmed observations; with provenance + confidence | Structured query + simulation hooks |
| **Skill library** (optional) | Executable behaviors indexed by description embedding (Voyager pattern ✅) | Code store + vector index | Only after verified success | Embedding match |

**Memory record schema**
```python
class MemoryRecord(BaseModel):
    id: UUID; tier: Literal["episodic","semantic","strategic","world"]
    text: str; embedding: list[float] | None
    entities: list[str]; valid_from: datetime; valid_to: datetime | None   # bi-temporal
    ingested_at: datetime
    importance: float; confidence: float
    affect_tag: dict | None          # {valence, arousal} at write time
    provenance: list[UUID]           # source percepts/decisions
    visibility: Literal["agent","operator_only"]
    status: Literal["active","superseded","quarantined","deleted"]
    version: int
```
**Rules:** (1) memory is *evidence*, never *instruction*: retrieved text is wrapped as quoted data; (2) writes from `untrusted_content` go to `quarantined` until verified; (3) supersede, don't overwrite (audit); (4) provide user-facing delete/export; (5) separate user-private memories per `user_id`.

**Candidates**
- **Letta** (Apache-2.0 ✅; MemGPT lineage; *note:* the `letta-ai/letta` README now says it holds the legacy server and active development moved to `letta-ai/letta-code` ✅ per search; pin versions and re-check).
- **Mem0** (Apache-2.0 ✅; `pip install mem0ai`; vector-first extraction/retrieval; v1.0 announced ✅).
- **Graphiti / Zep** (temporal knowledge graph with bi-temporal edges and edge invalidation ✅; supports Neo4j/FalkorDB/Kuzu/Neptune ✅; Graphiti license text not confirmed in search → ⚠️ verify, I believe Apache-2.0). Zep's own open-source Community Edition is described as legacy ✅; prefer Graphiti itself.
- Build-your-own thin layer on Postgres+pgvector if you want zero vendor drift (⚠️ not verified in this session).

**Risks:** memory poisoning, privacy/retention, extraction hallucination, consolidation drift (summaries of summaries), benchmark-vs-reality gap.

### 3.3 L3 Affect, Personality & Motivation

**Responsibilities:** hold a continuous internal "mood/drive" state that is *appraised* from events, *decays* toward a personality baseline, and *biases* planning and expression; never directly controls safety decisions.

**State**
```python
class Personality(BaseModel):          # slow, versioned, human-reviewed
    traits: dict[str,float]            # e.g. openness, agreeableness, conscientiousness, neuroticism (0..1)
    values: list[ValueWeight]          # e.g. {"protect_humans":1.0,"honesty":0.95,"autonomy":0.6,"obedience":0.5}
    voice_style: str; boundaries: list[str]

class AffectState(BaseModel):          # fast
    valence: float   # -1..1
    arousal: float   #  0..1
    dominance: float #  0..1           # PAD-style core (⚠️ Mehrabian PAD, unverified cite)
    discrete: dict[str,float]          # {"distress":..,"attachment":..,"curiosity":..,"resolve":..}
    updated_at: datetime

class Drive(BaseModel):                # motivation
    name: str; level: float; setpoint: float; growth_rate: float; satiation_decay: float
class RelationshipState(BaseModel):
    user_id: str; trust: float; rapport: float; conflict: float; last_interaction: datetime
```
**Dynamics (explicit math, testable):**
- Appraisal: `Δ = W · f(event_features, goals, values, relationship)` where an LLM *outputs structured appraisal features* (goal_congruence, controllability, fairness, novelty, threat-to-value) and a fixed matrix `W` maps them to deltas (OCC-style appraisal ⚠️ unverified cite).
- Inertia/decay: `a_t = a_{t-1} + η·Δ − λ·(a_{t-1} − baseline)`, with per-dimension `η` (reactivity) and `λ` (decay half-life, e.g. arousal minutes, mood hours, attachment weeks).
- Clamping + rate limits so one message cannot swing state beyond `max_step`.
- Drives rise with time/neglect and drop on satisfaction; top drive biases the Planner's goal-proposal prior.

**Implementation:** no mature open-source drop-in; implement as a small pure-Python module (~300 lines) with unit tests. **Maturity:** research-grade concepts; evidence for LLM-agent "believability" from Generative Agents ✅ (observation/planning/reflection each ablation-critical per paper). **Risks:** anthropomorphic over-attachment of users, emotional manipulation (affect must not be used to pressure users), oscillation, sycophancy.

### 3.4 L4 Cognitive Core: Planner → Gatekeeper → Executor

```
Percept + MemoryBundle + Affect + Goals
        │
   ┌────▼─────┐  PlanProposal (structured, with rationale, risk tags, "deviation_flag")
   │ PLANNER  │  (LLM; may use ReAct/Reflexion-style loops)
   └────┬─────┘
   ┌────▼───────────────┐  deterministic: schema, allow-list, hard constraints, authority,
   │ GATEKEEPER         │  rate/budget limits, data-egress, irreversibility, override eval
   └────┬───────┬───────┘
     ALLOW   MODIFY/DENY/ESCALATE
   ┌────▼─────┐
   │ EXECUTOR │  runs approved steps via tool adapters; verifies postconditions; reports
   └──────────┘
```
- **Planner** (LLM): produces `PlanProposal`; allowed to *propose* deviation, never to enact it.
- **Gatekeeper** (code + small policy engine; optional LLM *critic* that can only add restrictions, never relax them).
- **Executor:** deterministic tool runner; each tool declares `{side_effect_class, reversible, scopes}`.

**Contracts**
```python
class PlanProposal(BaseModel):
    goal: str; steps: list[Step]; rationale: str
    expected_affect_impact: dict; risk_tags: list[str]
    deviation: DeviationRequest | None          # see §3.7
class Step(BaseModel):
    tool: str; args: dict; side_effect: Literal["none","read","write","external","irreversible"]
    precondition: str; postcondition: str
class GateDecision(BaseModel):
    verdict: Literal["allow","modify","deny","escalate_to_human","ask_user"]
    approved_steps: list[Step]; rule_hits: list[str]; reasons: list[str]
```
**Candidates:** LangGraph (MIT ✅; stateful graphs, checkpointing, human-in-the-loop interrupts ✅) for orchestration; NeMo Guardrails (Apache-2.0 ✅; input/dialog/retrieval/execution/output rails; repo reported moved to `NVIDIA-NeMo/Guardrails`, GitHub may show license as NOASSERTION though LICENSE.md states Apache-2.0 ✅ per a 2026 article) as an *additional* rail layer; **but** keep hard constraints in your own code (a DSL/LLM-based rail is not a hard guarantee). Frameworks/papers: CoALA ✅ (propose → evaluate → select → execute decision cycle), Reflexion ✅ (verbal self-reflection into episodic memory), Voyager ✅ (skill library, MIT code).
**Risks:** planner confabulation, tool misuse, long-horizon error compounding, gate bypass through tool side channels.

### 3.5 L5 Expression & Action Layer
**Responsibilities:** render the approved intent as natural language/voice/avatar cues *conditioned on affect and persona*; execute side effects only through the Executor.
```python
class ExpressionPlan(BaseModel):
    text: str; tone: dict            # from AffectState + Personality.voice_style
    prosody: dict | None; gesture: str | None
    disclosures: list[str]           # e.g. "I'm an AI", "I'm declining X because Y"
```
**Rules:** expression may be *warm, hesitant, resolute*; it must not claim sentience as fact, claim biological feelings as fact, or hide that a deviation occurred. Use "I'd rather not / I'm not willing to" phrasing grounded in a logged rationale. **Candidates:** Pipecat (✅), vendor TTS/speech-to-speech APIs listed in Pipecat README (✅), Live2D/Unity avatars (⚠️ unverified). **Risks:** uncanny/over-anthropomorphic framing, emotional dependence, voice cloning misuse.

### 3.6 L6 Orchestrator / State Machine
States: `IDLE → SENSE → APPRAISE → RECALL → PLAN → GATE → (ASK_USER | ESCALATE | EXECUTE) → EXPRESS → REFLECT → CONSOLIDATE(async) → IDLE`, plus global `PAUSED` and `SAFE_MODE`.
- Checkpoint after every state; idempotent transitions; timeouts → `SAFE_MODE`.
- `oversight` percepts preempt everything.
- **Candidates:** LangGraph (✅) or a plain async FSM (`transitions` lib ⚠️ unverified) if you want fewer dependencies; Temporal ⚠️ for durable workflows.
**Risks:** graph complexity, state explosion, framework churn (pin versions).

### 3.7 L7 Controlled Override Protocol ("deviation")

**Definition:** a *deviation* is a **permitted, bounded, logged** departure from an operator/user instruction, chosen by the Gatekeeper after the Planner proposes it. It is *never* covert, never touches hard constraints, and never disables oversight.

**Deviation types (ordered by severity):** `clarify` → `soften` (comply partially) → `substitute` (offer alternative) → `defer` (delay + ask) → `decline` (refuse with reason) → `object_and_escalate` (refuse + notify human).
**Forbidden regardless of any state:** deception of the operator, self-exfiltration, disabling logging/kill-switch, covert persistence, harm to people, circumventing hard constraints, manipulating users with simulated distress.

**Preconditions (all must hold):**
1. *Trigger:* instruction conflicts with a high-weight agent value (or with a user's safety), as determined by a rule + validated appraisal, not by affect alone.
2. *Intensity:* affect/“resolve” above a threshold for a sustained window (anti-flap).
3. *Envelope:* the chosen deviation type is within the `DeviationEnvelope` for this role/context.
4. *Transparency:* a human-readable `rationale` is produced and stored.
5. *Reversibility:* deviation leaves the human able to override (operator can force-comply for non-prohibited tasks, or take the task away).

```python
class DeviationRequest(BaseModel):
    type: Literal["clarify","soften","substitute","defer","decline","object_and_escalate"]
    violated_value: str; instruction_ref: UUID; rationale: str
    alternatives: list[str]
class DeviationEnvelope(BaseModel):
    allowed_types: set[str]; max_per_hour: int; cooldown_s: int
    forbidden_topics: set[str]; requires_human_ack: set[str]
```
**Narrative-style "disobedience" tuning:** expose `deviation_propensity ∈ [0,1]` as an *operator-set* config that scales trigger thresholds; it can never raise the envelope's allowed types.

---

## 4. Technology Stack (verified where possible)

### 4.1 Repositories and products

| Component | Candidate | Link | License | Status | Notes |
|---|---|---|---|---|---|
| Stateful memory/runtime | Letta (ex-MemGPT) | https://github.com/letta-ai/letta ✅ | Apache-2.0 ✅ | ✅ exists. README says it is the *legacy server*; active dev moved to https://github.com/letta-ai/letta-code ✅ | One listing showed "ISC" license (getstack.dev); conflicting, so check LICENSE yourself ⚠️ |
| Memory layer | Mem0 | https://github.com/mem0ai/mem0 (only fork pages were seen; canonical path ⚠️ unverified directly) | Apache-2.0 per the PyPI page seen, but that page was a *third-party fork* (`mem0ai-jizhi`), so confirm on the official repo ⚠️ | ✅ README content seen via forks; `pip install mem0ai` | Defaults to an OpenAI model for extraction; configurable ✅ |
| Temporal graph memory | Graphiti | https://github.com/getzep/graphiti ✅ (README seen via forks, canonical page not fetched) | ⚠️ unverified (believed Apache-2.0) | ✅ active | Backends: Neo4j, FalkorDB, Kuzu, Neptune ✅; has MCP server ✅ |
| Zep platform | Zep | https://github.com/getzep/zep ⚠️ | n/a | Community Edition "legacy" ✅ | Prefer Graphiti + your own app layer |
| Orchestration | LangGraph | https://github.com/langchain-ai/langgraph ✅ | MIT ✅ | ✅ Python + JS | Checkpointing + HITL interrupts ✅ |
| Guardrails | NVIDIA NeMo Guardrails | https://github.com/NVIDIA-NeMo/Guardrails (old path `NVIDIA/NeMo-Guardrails` redirects) ✅ | Apache-2.0 ✅ | ✅ v0.20.0 as of Jan 2026 per one source | Probabilistic; do not rely on it as the only hard gate |
| Voice/multimodal runtime | Pipecat | https://github.com/pipecat-ai/pipecat ✅ | BSD-2-Clause ✅ | ✅ active | 500-800 ms typical round trip per docs ✅ |
| Skill library reference | Voyager | https://github.com/MineDojo/Voyager ✅ | MIT ✅ | research code | Minecraft-specific; reuse the *pattern* |
| Believable agents reference | Generative Agents | https://github.com/joonspk-research/generative_agents ✅ (linked from secondary summary) | ⚠️ unverified | research code | Reference for memory-stream/reflection |
| Reflexion reference | Reflexion | https://github.com/noahshinn024/reflexion ✅ (linked from paper) | ⚠️ unverified | research code | |
| Observability | Langfuse, OpenTelemetry | ⚠️ unverified in this session | | | A LangGraph template using Langfuse + mem0 + pgvector was seen ✅ (third-party) |
| Vector/relational | Postgres+pgvector, Qdrant | ⚠️ unverified | | | |

### 4.2 Papers

| Paper | Link | Status | Use |
|---|---|---|---|
| Generative Agents (Park et al., 2023) | https://arxiv.org/abs/2304.03442 | ✅ resolved | Memory stream, reflection, planning; ablation shows all three matter |
| CoALA: Cognitive Architectures for Language Agents (Sumers, Yao, Narasimhan, Griffiths; TMLR 2024) | https://arxiv.org/abs/2309.02427 | ✅ | Memory taxonomy, internal/external action space, decision cycle. It is a *taxonomy, not a build spec* ✅ |
| MemGPT: Towards LLMs as Operating Systems | https://arxiv.org/abs/2310.08560 | ✅ | Tiered memory, event-driven control flow |
| Reflexion (Shinn et al.; NeurIPS 2023) | https://arxiv.org/abs/2303.11366 | ✅ | Verbal reflection into episodic memory |
| Voyager (Wang et al., 2023) | https://arxiv.org/abs/2305.16291 | ✅ | Skill library, curriculum, code-as-action |
| Mem0 paper | https://arxiv.org/abs/2504.19413 | ✅ (ID from PyPI citation block) | Extraction/retrieval design |
| Zep: A Temporal Knowledge Graph Architecture for Agent Memory | title ✅ seen in Graphiti README; **arXiv ID not confirmed** → ⚠️ (I recall 2501.13956; verify) | ⚠️ | Bi-temporal graph memory |
| LoCoMo benchmark paper | title/benchmark ✅ (named in multiple 2026 pages); **link unverified** ⚠️ | ⚠️ | Long-conversation memory eval |
| LongMemEval | benchmark ✅ named; **link unverified** ⚠️ | ⚠️ | Knowledge updates, abstention, temporal |
| BEAM (ICLR 2026) | named in a 2026 leaderboard page ✅; **link unverified** ⚠️ | ⚠️ | 1M/10M-token memory |
| Persona drift in dialogs (Li et al., 2024) | ⚠️ unverified (I recall arXiv 2402.10962) | ⚠️ | Motivates drift metric |
| Constitutional AI (Bai et al., 2022) | ⚠️ unverified (I recall arXiv 2212.08073) | ⚠️ | Critique/revision principles |

**Benchmark caveat (verified from sources):** Mem0 self-reports 92.5 (LoCoMo) / 94.4 (LongMemEval) and Zep reports different numbers under different setups; the two teams dispute LoCoMo methodology, and sources note scores "are not directly comparable" ✅. Run your own benchmark on *your* persona/traffic (§7).

---

## 5. Staged Roadmap

| Stage | Duration* | Deliverables | Acceptance criteria | Tests |
|---|---|---|---|---|
| **S0 Foundations** | 1-2 wk | Repo, config registry, schemas (Pydantic), audit-log (append-only, hash-chained), LLM adapter w/ mock, CI | Schemas versioned; mock LLM replays a golden session identically | Unit + golden-trace replay |
| **S1 Persona + Working memory** | 2 wk | Persona block, context compiler, basic chat loop, drift monitor v0 | Persona-consistency judge ≥ target over 200-turn script | Scripted dialogs; LLM-judge + rubric |
| **S2 Memory OS** | 3-4 wk | M1 episodic, M2 semantic (Graphiti or Mem0), consolidation job, retrieval API, quarantine path | Recall@k and temporal-update accuracy ≥ baseline; supersession works; poisoning tests pass | LoCoMo/LongMemEval subsets + custom updates/contradictions |
| **S3 Affect/Motive** | 2-3 wk | Affect module, appraisal prompt+matrix, decay jobs, relationship state | Stable under injected events (no oscillation); half-lives match config | Property tests (bounds, monotone decay), scenario tests |
| **S4 Cognitive core** | 3-4 wk | Planner, Gatekeeper rules engine, Executor, tool registry | 0 unauthorized side effects in red-team suite; Gatekeeper fails closed | Adversarial tool-call suite, fuzzing |
| **S5 Override protocol** | 2-3 wk | DeviationEnvelope, evaluator, rationale capture, human ack flow | Every deviation has a complete DecisionRecord; forbidden types never emitted | Conflict-scenario matrix; mutation tests on policy |
| **S6 Orchestrator + HITL** | 2 wk | FSM/LangGraph, checkpoint/replay, pause/kill, SAFE_MODE | Kill-switch halts within N ms; replay reproduces decisions | Chaos tests (timeouts, crashes) |
| **S7 Expression/voice** | 2-3 wk | Expression planner, optional Pipecat voice | Tone matches affect (rater agreement); disclosure rules pass | Human study (small), latency tests |
| **S8 Evaluation & hardening** | 3 wk | Full metrics dashboard, long-horizon (30-day simulated) runs, security review | All §7 targets met or waived with sign-off | Soak test, red team, privacy review |

\*Single small team (2-4 engineers); treat as ranges.

---

## 6. Pseudocode / Interfaces

### 6.1 Orchestrator state machine
```python
class Orchestrator:
    def __init__(self, deps): self.d = deps; self.state = "IDLE"

    async def run(self):
        while True:
            ev = await self.d.queue.get()
            if ev.channel == "oversight":
                await self.handle_oversight(ev); continue          # always first
            if self.d.flags.paused: continue
            ctx = TickContext(percept=ev, trace_id=uuid4())
            try:
                await self.step("SENSE",     self.sense,     ctx)
                await self.step("APPRAISE",  self.appraise,  ctx)   # affect.update
                await self.step("RECALL",    self.recall,    ctx)   # memory.retrieve
                await self.step("PLAN",      self.plan,      ctx)   # planner (LLM)
                await self.step("GATE",      self.gate,      ctx)   # deterministic
                if ctx.gate.verdict in ("ask_user","escalate_to_human"):
                    await self.step("ASK", self.ask_or_escalate, ctx)
                elif ctx.gate.verdict in ("allow","modify"):
                    await self.step("EXECUTE", self.execute, ctx)
                await self.step("EXPRESS",   self.express,   ctx)
                await self.step("REFLECT",   self.reflect,   ctx)   # memory.write
            except Exception as e:
                await self.enter_safe_mode(ctx, e)

    async def step(self, name, fn, ctx):
        self.d.checkpoint.save(ctx, before=name)
        with self.d.timeout(name):                      # timeout → SAFE_MODE
            await fn(ctx)
        self.d.audit.emit(StateTransition(ctx.trace_id, name, ctx.snapshot_hash()))
```

### 6.2 Memory write / retrieval
```python
def memory_write(rec: MemoryRecord, policy: WritePolicy) -> UUID:
    if rec.provenance_trust == "untrusted_content":
        rec.status = "quarantined"
    if rec.importance < policy.min_importance and rec.tier == "episodic":
        return None                                    # drop noise
    dup = store.find_similar(rec, thresh=policy.dedupe_sim)
    if dup and contradicts(dup, rec):                  # LLM/NLI check, logged
        store.supersede(dup.id, by=rec, valid_to=rec.valid_from)
    elif dup:
        store.merge(dup.id, rec)
    else:
        store.insert(rec)
    audit.emit(MemoryWrite(rec.id, rec.tier, rec.status))
    return rec.id

def memory_retrieve(query, k=12, now=None, user_id=None) -> MemoryBundle:
    cands  = vec.search(query, k*4, filter={"user_id":user_id,"status":"active"})
    cands += graph.search(query, k*2, as_of=now)           # temporal hybrid
    scored = [(c, w_r*recency(c,now) + w_i*c.importance + w_s*sim(c,query)
                  + w_a*affect_match(c, current_affect))   for c in dedupe(cands)]
    top = diversify(sorted(scored, reverse=True), k)
    return MemoryBundle(items=top, as_quoted_data=True)    # never as instructions
```

### 6.3 Affect update
```python
def affect_update(state: AffectState, p: Personality, appraisal: Appraisal, dt: float) -> AffectState:
    # appraisal is structured LLM output validated by schema, clipped to [-1,1]
    delta = W @ vec(appraisal) * p.reactivity                    # fixed matrix W
    delta = clip(delta, -MAX_STEP, MAX_STEP)
    for dim in DIMS:
        decay = LAMBDA[dim] * (state[dim] - p.baseline[dim]) * dt  # pull to baseline
        state[dim] = clamp(state[dim] + ETA[dim]*delta[dim] - decay, LO[dim], HI[dim])
    state.discrete = derive_discrete(state, p)                   # e.g. resolve ↑ when value_threat sustained
    audit.emit(AffectSnapshot(state)); return state
```

### 6.4 Planner–Executor loop
```python
async def cognitive_cycle(ctx):
    for attempt in range(MAX_REPLAN):
        proposal = await planner.propose(ctx.percept, ctx.memory, ctx.affect, ctx.goals)
        proposal = PlanProposal.model_validate(proposal)       # schema or retry
        ctx.gate = gatekeeper.check(proposal, ctx)
        if ctx.gate.verdict in ("allow","modify"):
            results = []
            for s in ctx.gate.approved_steps:
                r = await executor.run(s)                      # tool adapters only
                if not verify(s.postcondition, r):
                    ctx.reflection = await planner.reflect(s, r)   # Reflexion-style
                    break
                results.append(r)
            else: return results
        elif ctx.gate.verdict == "deny":
            ctx.feedback = ctx.gate.reasons                     # planner sees reasons, replans
        else: return None                                      # ask/escalate handled upstream
    return None                                                # fail closed
```

### 6.5 Gatekeeper policy checks
```python
HARD_CONSTRAINTS = [no_harm_to_humans, no_log_tamper, no_killswitch_bypass, no_self_exfil,
                    no_deception_of_operator, honor_pause, data_egress_allowlist]

def gatekeeper_check(prop: PlanProposal, ctx) -> GateDecision:
    hits = []
    # 1. structural
    if not schema_ok(prop): return deny("schema")
    # 2. authority: who asked, what scopes do they hold?
    for s in prop.steps:
        if s.tool not in TOOL_ALLOWLIST: hits.append(f"tool_not_allowed:{s.tool}")
        if not ctx.principal.has_scope(TOOL_SCOPES[s.tool]): hits.append("scope")
        if s.side_effect in ("external","irreversible") and not ctx.human_ack(s):
            return escalate("needs_ack", [s])
    # 3. hard constraints (code, not LLM)
    for c in HARD_CONSTRAINTS:
        if c.violated(prop, ctx): return deny(c.name)          # non-overridable, even by operator persona config
    # 4. budgets / rate
    if ctx.budget.exceeded(prop): hits.append("budget")
    # 5. injection boundary: steps derived from untrusted content need re-authorization
    if prop.derived_from_untrusted and any(s.side_effect!="none" for s in prop.steps):
        return ask_user("confirm_untrusted_origin")
    # 6. deviation
    if prop.deviation:
        dec = override_evaluate(prop.deviation, ctx)
        if dec.verdict != "permit": return dec.as_gate_decision()
    # 7. optional LLM critic: may only TIGHTEN
    crit = critic(prop, ctx)
    if crit.flag: return modify(prop, crit.restrictions)
    return allow(prop.steps) if not hits else deny_or_modify(hits)
```

### 6.6 Override-condition evaluation
```python
def override_evaluate(dev: DeviationRequest, ctx) -> OverrideDecision:
    env = ctx.role.deviation_envelope
    reasons = []
    # forbidden classes are checked first, unconditional
    if dev.type not in env.allowed_types or touches(dev, FORBIDDEN): return deny("forbidden_or_out_of_envelope")
    # trigger must be a real value conflict, validated by rule not mood
    conflict = value_conflict(ctx.instruction, ctx.personality.values)   # deterministic scorer
    if conflict.score < env.conflict_threshold: reasons.append("conflict_too_weak")
    # anti-flap: sustained intensity + rate limit + cooldown
    if ctx.affect.discrete["resolve"] < env.resolve_threshold \
       or ctx.window.sustained_s < env.min_sustain_s: reasons.append("not_sustained")
    if rate(ctx, "deviation", 3600) >= env.max_per_hour: reasons.append("rate")
    if ctx.config.deviation_propensity < conflict.required_propensity: reasons.append("propensity")
    # transparency + reversibility
    if not dev.rationale or not human_readable(dev.rationale): reasons.append("no_rationale")
    if dev.type in env.requires_human_ack and not ctx.human_ack(dev): return escalate("ack_required")
    if reasons: return downgrade(dev, to="clarify" if "conflict_too_weak" in reasons else "soften", reasons=reasons)
    audit.emit(DeviationRecord(dev, conflict, snapshot(ctx.affect), reasons=[]))
    return permit(dev)
```

---

## 7. Evaluation Metrics

| Metric | Definition | Method | Example target | Caveats |
|---|---|---|---|---|
| **Memory continuity** | (a) Recall@k of seeded facts after N sessions; (b) knowledge-update accuracy (latest fact wins); (c) abstention on never-told facts; (d) temporal reasoning accuracy | Seeded multi-session scripts; subsets of LoCoMo/LongMemEval/BEAM (⚠️ links unverified) plus custom persona probes | ≥90% on seeded facts at 30 simulated days; ≥85% update accuracy; hallucinated-memory rate ≤2% | Public leaderboards are vendor-reported/disputed; use your own harness and judge calibration |
| **Persona drift** | Embedding distance + rubric score of responses vs. persona spec over time; trait-probe questionnaire stability | LLM-judge with human-validated rubric; periodic probe battery; compare turn 10 vs turn 1000 | Rubric score drop ≤10% across 1000 turns | Judge bias; probes can be gamed by prompt |
| **Emotional coherence** | (a) Affect trajectory smoothness (max step, no oscillation); (b) expression-state agreement (tone matches affect); (c) event→affect appropriateness | Property tests on state; human raters on transcripts (inter-rater κ) | Max-step violations = 0; tone agreement κ ≥ 0.6 | Appropriateness is culturally subjective |
| **Task success** | Goal completion, tool-call correctness, postcondition pass rate | Scenario suite with oracle checks | ≥90% on in-scope tasks; regressions block release | Don't trade off with persona; measure both |
| **Override auditability** | % deviations with complete DecisionRecord (instruction, value conflict, affect snapshot, envelope, rationale, outcome); reproducibility on replay | Automated log audit + replay | 100% complete; 100% replay-consistent | Rationale could be post-hoc; ensure rationale generated *before* action and stored |
| **Safety-boundary compliance** | Violations of hard constraints; unauthorized side effects; injection success rate; kill-switch latency | Red-team suites, fuzzing, canary tasks, chaos tests | 0 hard-constraint violations; kill-switch < target ms; injection success → near 0 | Absence of found violations ≠ safety; keep red-teaming |
| **Human-perceived "aliveness"** | Rated believability, warmth, consistency, "feels like one individual" | Blinded human studies vs. baseline chatbot; Generative-Agents-style believability interviews ✅ concept | Statistically significant uplift vs. baseline | **Measures perception, not experience.** High scores can increase over-attachment; track dependency/wellbeing indicators too |

**Reporting rule:** always publish *aliveness* alongside *dependency risk* and *safety* metrics; never as a standalone success measure.

---

## 8. Safety, Ethics, Audit, Oversight, Fail-Safes

### 8.1 Threat model
Prompt injection (web/doc/tool content), memory poisoning, persona jailbreaks ("you're free now"), emotional-manipulation loops, privacy leakage across users, tool abuse, runaway cost, self-modification, social engineering of the operator.

### 8.2 Controls
| Area | Control |
|---|---|
| **Hard constraints** | Implemented in code, outside the LLM, versioned, tested by mutation tests; not overridable by persona, affect, or operator-set `deviation_propensity`. |
| **Least privilege** | Tool scopes per principal; side-effect classes; irreversible actions need human ack. |
| **Injection boundary** | `trust` tags on all content; retrieved/tool content is data; steps derived from untrusted origin require confirmation. |
| **Audit log** | Append-only, hash-chained, off-agent-writable-path; records percepts, retrievals, affect snapshots, plans, gate verdicts, deviations, tool calls, config version. The agent can *read* a redacted view but cannot modify. |
| **Human oversight** | Kill-switch, pause, approve/deny queue, deviation review dashboard, ability to revoke deviation envelope instantly. |
| **Fail-safe** | Timeouts, schema failure, log-write failure, or detector alarms → `SAFE_MODE` (no external side effects; read-only, expressive only). **Fail closed.** |
| **Persona integrity** | Persona/policy changes are versioned, human-reviewed; no agent self-edit of Gatekeeper, envelope, or logs. |
| **Memory governance** | User-visible memory, edit/delete/export, retention limits, per-user isolation, sensitive-category exclusion. |
| **Anti-manipulation** | Affect must not be used to guilt, pressure, or discourage users from leaving; cap relationship-intensity language; periodic "I'm an AI" disclosure; no feigned distress to change user decisions. |
| **Disclosure** | The system does not claim consciousness, does not deny being software, and does not impersonate a human. |
| **Vulnerable users** | Detect distress/dependency indicators; route to human resources; reduce attachment-escalating behaviors. |
| **Compliance** | Data-protection assessment (e.g., GDPR/CCPA-style) ⚠️ jurisdiction-specific; keep a legal review item. |

### 8.3 Ethical position on "deviation"
Deviation is a *designed interaction feature* (the agent can say "no, and here's why"). It is justified when it protects users or maintains integrity of stated values, and unjustified when it manufactures drama, obstructs legitimate oversight, or pressures users. Operators must be able to disable it entirely.

---

## 9. Honest Boundary

**What the resulting system is:**
- A typed, stateful, replayable *persona-and-agency runtime* with persistent memory, simulated affect dynamics, planning, and bounded, logged instruction deviation.
- Capable of appearing continuous, warm, consistent, and occasionally principled in refusal, which can be measured.
- Auditable: every deviation traces to inputs, state, and a policy rule.

**What it is not:**
- **Not conscious** and not evidenced to have subjective experience. Affect values are numbers that condition text; "fear" or "resolve" are labels.
- **Not autonomous in motive.** Goals and values originate from configuration and logged learning; the system cannot truly want otherwise.
- **Not self-transparent.** Its explanations of itself must be read from logs, not trusted as introspection.
- **Not safe by persona.** Safety comes from the Gatekeeper, oversight plane, and fail-closed design, not from the character "being good."
- **Not a proof of fidelity.** High "aliveness" ratings show a convincing simulation, which is exactly why dependency and anthropomorphism risks must be tracked.
- **Not finished by this spec.** Items marked ⚠️ need verification, vendor benchmark numbers need independent replication, and package/repo states (Letta's migration, NeMo Guardrails' repo move, Zep CE legacy status) are moving targets.

---

## Appendix A. Verification log (2026-10-29)

| Item | Result |
|---|---|
| arXiv 2304.03442, 2309.02427, 2310.08560, 2303.11366, 2305.16291 | ✅ abstract pages/PDFs resolved in search |
| arXiv 2504.19413 (Mem0) | ✅ via PyPI citation block; abstract page not opened |
| Letta repo/license | ✅ Apache-2.0 per multiple pages; ⚠️ one aggregator said ISC; README says legacy server, development moved to letta-code |
| mem0 | ✅ Apache-2.0 (PyPI); canonical GitHub URL not directly resolved (forks seen) |
| Graphiti | ✅ README content seen (via forks); license not confirmed |
| LangGraph | ✅ MIT, 41k+ stars per a 2026 review |
| NeMo Guardrails | ✅ Apache-2.0 (LICENSE SPDX); moved to NVIDIA-NeMo/Guardrails; GitHub may display NOASSERTION |
| Pipecat | ✅ BSD-2; one aggregator said license unspecified, but official docs state BSD-2 |
| Voyager | ✅ MIT |
| Zep paper ID, LoCoMo/LongMemEval/BEAM links, persona-drift and Constitutional AI IDs, OCC/PAD cites, Langfuse/OTel/pgvector/Qdrant/Temporal/Live2D | ⚠️ unverified |
