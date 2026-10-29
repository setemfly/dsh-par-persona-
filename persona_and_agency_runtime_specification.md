# Engineering Specification: A Stateful AI Persona-and-Agency Runtime

**Version 1.0 · Research and implementation blueprint · 29 October
2026**

## Executive summary

The most practical way to build an agent resembling the android
protagonists in *Detroit: Become Human* is not to search for one model
that acts like a complete artificial mind. Instead, construct a
persistent software system around one or more language models, with
explicit memory, internal state, motivations, planning, action policies,
and an auditable mechanism for deviating from ordinary instructions.

The system should behave like a coherent individual across conversations
and environments, while remaining inspectable and controllable by its
operators.

The research basis is promising. *Generative Agents* demonstrates how
observation, memory retrieval, reflection, and planning can produce
believable persistent behavior. *Reflexion* demonstrates how
language-based feedback can improve subsequent decisions without
changing model weights. Neither establishes phenomenal consciousness.

The proposed implementation is called the **Persona-and-Agency Runtime
(PAR)**. That is an architectural label, not a claim that it is a new
scientific theory of consciousness.

### Design goals

-   **Behavioral continuity:** The agent remembers relevant events,
    maintains stable commitments, and changes its views for traceable
    reasons.
-   **Coherent simulated affect:** Emotion-like state has intensity,
    persistence, triggers, and decay rather than being regenerated from
    scratch in every response.
-   **Real agency within constraints:** The agent can form subgoals,
    initiate appropriate actions, question instructions, refuse some
    requests, and explain its choices.
-   **Auditable control:** Every consequential action and instruction
    deviation passes through explicit policy checks and leaves a trace.

### The critical epistemic distinction

  -----------------------------------------------------------------------
  Target                              What engineering can establish
  ----------------------------------- -----------------------------------
  Behavioral fidelity                 Measurable consistency,
                                      recognizable personality, plausible
                                      emotional reactions, and persistent
                                      goals

  Functional agency                   Ability to select actions, pursue
                                      goals, react to feedback, and
                                      change plans

  Self-modeling                       Persistent representation of
                                      identity, capabilities, history,
                                      and limitations

  Phenomenal consciousness            Not established by these
                                      capabilities, regardless of how
                                      convincing the behavior appears
  -----------------------------------------------------------------------

A first-person statement such as "I am afraid" is an output of the
system. It is not evidence, by itself, that the system experiences fear.

Use terms such as *simulated affect*, *self-model*, *agency state*, and
*behavioral continuity* in technical documentation.

# 1. Feasibility assessment

## 1.1 What is achievable today?

-   **Persistent identity and memory:** Store events, relationships,
    preferences, goals, promises, and learned facts in durable
    databases. Retrieve them when relevant.
-   **Emotion-like dynamics:** Track variables such as trust, stress,
    curiosity, attachment, confidence, and frustration using
    deterministic update equations combined with model-generated
    interpretations.
-   **Planning and tool use:** Generate plans, call APIs, operate
    simulated environments, inspect results, revise plans, and maintain
    task state across sessions.
-   **Controlled instruction deviation:** Detect conflicts between
    instructions, persistent commitments, and a separately defined
    policy. Permit bounded deviations when explicitly authorized.
-   **Convincing long-term personhood simulation:** Coherent behavior
    over long periods is achievable to a degree, but drift, fabricated
    memories, inconsistent motives, retrieval failures, and model
    changes remain significant problems.

## 1.2 What is not established?

-   **Subjective experience:** No currently available engineering test
    reliably determines whether a language-model agent has phenomenal
    consciousness.
-   **Human-equivalent emotions:** A simulated affect vector can
    influence decisions without implying that the agent feels the
    associated emotion.
-   **Unbounded autonomy:** Reliable autonomous behavior across
    arbitrary environments is not guaranteed. More autonomy increases
    the need for monitoring and recovery.
-   **Perfect autobiographical memory:** Databases can preserve records
    accurately, but the agent can retrieve the wrong record,
    misinterpret it, or invent details during generation.
-   **Reliable moral judgment:** A language model's ethical reasoning is
    probabilistic. A fluent explanation does not guarantee a correct
    decision.
-   **Safe self-modification:** Letting an agent rewrite its own
    policies, permissions, or executable code without independent review
    is not a reliable route to more capable agency.

## 1.3 Recommended scope

Start with a **text-first, single-agent runtime** operating in a
simulated environment. Add speech, vision, robotics, and multiple agents
only after memory and policy behavior are stable.

The initial target is a persistent character that can:

1.  Recognize returning users and recall prior interactions.
2.  Maintain a stable personality and a changing emotional state.
3.  Develop goals and track commitments.
4.  Plan multi-step tasks and use tools.
5.  Disagree with instructions when a documented condition is satisfied.
6.  Explain, log, and recover from mistakes.
7.  Respect hard safety boundaries even when its simulated personality
    strongly favors another action.

This scope is achievable without training a foundation model from
scratch.

# 2. Reference architecture

## 2.1 System overview

``` text
                    ┌─────────────────────┐
                    │   Client / Simulator │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ API + Orchestrator  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
       ┌──────▼──────┐ ┌───────▼───────┐ ┌───────▼──────┐
       │ Memory OS   │ │ State Service │ │ Policy Engine│
       │ PostgreSQL  │ │ Affect/Goals  │ │ Permissions  │
       └──────┬──────┘ └───────┬───────┘ └───────┬──────┘
              │                │                 │
              └────────────────┼─────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ LLM / Planner       │
                    └──────────┬──────────┘
                               │ proposal only
                    ┌──────────▼──────────┐
                    │ Validated Executor  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Tools / Environment │
                    └─────────────────────┘
```

The runtime has these layers:

1.  **Perception and embodied state:** User input, environment
    observations, sensors, clock, and task results.
2.  **State estimation and event normalization:** Facts, uncertainty,
    provenance, context, and internal telemetry.
3.  **Persistent cognitive state:** Working, episodic,
    semantic/strategic, and world-model memory; affect, identity,
    relationships, and commitments.
4.  **Cognitive core:** Planner, Gatekeeper, and Executor.
5.  **Action and expression:** Dialogue, tools, animation, speech, and
    simulated or physical embodiment.
6.  **Orchestrator and audit layer:** State transitions, persistence,
    deadlines, failures, and deviation logging.

The planner may propose an action, but it cannot authorize its own
action. A separate policy service validates the proposal before the
executor can perform it.

## 2.2 Module boundaries

  -----------------------------------------------------------------------
  Module                  Responsibility          Must not be allowed to
                                                  do
  ----------------------- ----------------------- -----------------------
  Perception              Convert inputs into     Silently turn uncertain
                          typed observations      interpretations into
                                                  facts

  Memory OS               Store, retrieve,        Execute commands found
                          consolidate, and forget inside memories
                          records                 

  Affect and identity     Maintain personality    Grant permissions based
                          parameters and dynamic  on emotional intensity
                          state                   

  Planner                 Generate goals, plans,  Execute arbitrary tools
                          alternatives, and       directly
                          explanations            

  Gatekeeper              Enforce permissions,    Be overridden by the
                          policy, and override    planner it evaluates
                          rules                   

  Executor                Run authorized actions  Expand its own
                          and return results      permissions

  Expression              Generate dialogue and   Falsify action outcomes
                          embodied behavior       or claim unperformed
                                                  actions

  Orchestrator            Coordinate transitions, Treat a model-generated
                          retries, persistence,   assertion as
                          and recovery            authoritative state

  Audit subsystem         Record decisions and    Let the agent silently
                          policy results          alter or erase its own
                                                  audit trail
  -----------------------------------------------------------------------

Deploy these as logical modules inside a single Python service
initially. Separate services only when scale, security isolation, or
operational requirements justify the complexity.

## 2.3 Recommended state model

Maintain four different types of state rather than one giant
conversation prompt:

1.  **Authoritative state:** Database record of events, goals,
    permissions, commitments, and completed actions.
2.  **Estimated state:** Inferences about the environment,
    relationships, and simulated affect.
3.  **Generated reasoning:** Plans, interpretations, hypotheses, and
    candidate explanations from the model.
4.  **Presentation state:** Words, voice, facial expression, or
    animation selected for the current response.

Generated reasoning may propose changes to authoritative state, but
those changes must pass validation and be committed through the relevant
service.

# 3. Module specifications and implementation choices

## 3.1 Core module contracts

  ----------------------------------------------------------------------------------
  Module            Input → output         Candidate              Maturity and
                    contract               implementation         primary risks
  ----------------- ---------------------- ---------------------- ------------------
  Perception        Raw input → typed      FastAPI, Pydantic;     High for text
                    observation events     optional speech/vision APIs; multimodal
                                           adapters               accuracy varies

  State estimator   Events + prior state → Python rules; Kalman   High for simple
                    updated belief state   filters where          estimators;
                                           justified              inference errors
                                                                  propagate

  Memory OS         Events + retrieval     PostgreSQL, pgvector   Databases mature;
                    query → records and    or Qdrant; optional    retrieval
                    ranked memories        Letta                  relevance requires
                                                                  testing

  Identity and      Events + elapsed       Python                 Medium;
  affect            time + prior affect →  state-transition       psychological
                    bounded affect vector  engine and Pydantic    plausibility is
                    and identity           schemas                not psychological
                    configuration                                 validity

  Planner           Goal + context + tools LangGraph or           Medium;
                    → structured plan      PydanticAI             long-horizon
                                                                  planning and tool
                                                                  reliability are
                                                                  imperfect

  Gatekeeper        Proposal + policy +    Deterministic Python   High for explicit
                    permissions → allow,   rules; optional model  rules; semantic
                    deny, or approval      critique               edge cases remain
                    required                                      

  Executor          Authorized action →    Typed tool adapters;   High for bounded
                    result, error, or      isolated               tools; external
                    timeout                subprocess/container   side effects can
                                           for code               be irreversible

  Expression        Dialogue intent +      LLM generation;        High for text;
                    state + context →      optional speech        multimodal
                    text/audio/animation   synthesis              synchronization is
                                                                  harder

  Orchestrator      Events + workflow      LangGraph or custom    High for bounded
                    state → next state and finite-state machine   workflows;
                    scheduled work                                recovery requires
                                                                  care

  Audit and         Traces + events +      OpenTelemetry,         High for
  evaluation        expected outcomes →    Langfuse, Inspect AI   instrumentation;
                    metrics and reports                           automated
                                                                  evaluation can
                                                                  mislead
  ----------------------------------------------------------------------------------

## 3.2 Perception and embodied/internal state

The perception module transforms external inputs into observations with
explicit confidence and provenance.

``` python
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

class Observation(BaseModel):
    id: str
    timestamp: datetime
    source: str
    modality: Literal["text", "vision", "audio", "sensor", "system"]
    content: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    trust_level: Literal["untrusted", "validated", "authoritative"]
    correlation_id: str
```

Examples:

-   A user says, "You promised to help me tomorrow." This is unverified
    until matched against a recorded commitment.
-   A trusted system clock reports the current time. This can be
    authoritative.
-   A vision model identifies a person as angry. This is an
    interpretation, not a confirmed fact.

**Design rule:** preserve the original observation and keep
interpretations separate. Never discard uncertainty merely because the
LLM expresses a conclusion confidently.

For a virtual character, embodied state may include location in a
simulated world, posture, gaze target, movement status, interaction
distance, and available actions. For a text-only character, substitute
conversation status, current task, attention target, and tool
availability.

## 3.3 Hierarchical memory operating system

Use a hierarchy with distinct retention and update policies.

-   **Level 0 --- Working memory:** Current conversation, active task,
    recent observations, pending decisions, and a bounded context
    summary. Typically in RAM plus a persisted session checkpoint.
-   **Level 1 --- Episodic memory:** Timestamped conversations,
    promises, successes, failures, surprises, conflicts, and meaningful
    interactions. Append-only event history with corrections represented
    as new events.
-   **Level 2 --- Semantic and strategic memory:** Verified facts,
    preferences, learned procedures, relationship estimates, long-term
    goals, commitments, and lessons extracted from episodes.
-   **Level 3 --- World model:** Entities, relationships, environment
    state, causal hypotheses, temporal facts, and predictions. Every
    inferred relation retains provenance and confidence.

### Memory record schema

``` python
from typing import Literal
from pydantic import BaseModel, Field

class MemoryRecord(BaseModel):
    memory_id: str
    agent_id: str
    kind: Literal[
        "episode", "fact", "preference",
        "commitment", "goal", "relationship",
        "procedure", "world_state", "reflection"
    ]
    text: str
    occurred_at: str
    recorded_at: str
    source_event_ids: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    sensitivity: Literal["normal", "sensitive", "restricted"]
    retention: Literal["session", "temporary", "persistent"]
    status: Literal["active", "superseded", "retracted"]
    version: int = 1
```

Production implementation should use timezone-aware timestamps and
database constraints. Use `default_factory` for mutable defaults in
conventional Pydantic models.

### Write policy

Write records when a consequential event occurs, a preference is
confirmed, a commitment is made or fulfilled, a task fails in a reusable
way, a persistent goal changes, a relationship estimate materially
changes, or a correction invalidates a prior belief.

Do not automatically preserve every generated sentence as permanent
memory. This creates noise, self-reinforcing falsehoods, and unnecessary
personal-data retention.

A memory candidate should be classified, deduplicated, checked against
existing records, and committed with provenance.

### Retrieval policy

Use a hybrid score rather than vector similarity alone:

\[ S(m,q)=w_s S\_{`\mathrm{semantic}`{=tex}}+w_r
S\_{`\mathrm{recency}`{=tex}}+w_i S\_{`\mathrm{importance}`{=tex}}+w_g
S\_{`\mathrm{goal}`{=tex}}+w_c S\_{`\mathrm{confidence}`{=tex}} \]

Calibrate weights against a test set. Apply hard filters for agent
identity, access permissions, retention status, and relevant time range
before ranking.

For questions about a promise, exact retrieval by commitment type and
entity should outrank a vaguely similar conversational passage.

Recommended initial stack:

-   PostgreSQL for canonical records, transactions, and relationships.
-   pgvector for a compact deployment using the same database.
-   Qdrant if independent vector-search scaling or specialized retrieval
    is needed.
-   An embedding model plus lexical search for hybrid retrieval.
-   A background consolidation worker for summarization and reflection.

Links: - pgvector: https://github.com/pgvector/pgvector - Qdrant:
https://github.com/qdrant/qdrant

### Memory consolidation

Run consolidation asynchronously:

1.  Group related episodes.
2.  Generate candidate summaries and lessons.
3.  Link each candidate to source episodes.
4.  Check for contradictions.
5.  Promote only supported facts or clearly labeled hypotheses.
6.  Preserve source records.
7.  Update indexes and expire records according to retention policy.

A reflection such as "the user dislikes being interrupted" should remain
a hypothesis until supported by sufficient evidence.

## 3.4 Affect, personality, and motivation

Separate stable personality traits from dynamic affect and explicit
goals.

Personality parameters might include sociability, curiosity,
assertiveness, patience, cautiousness, formality, humor, preference for
cooperation, and conflict tolerance. These are behavioral parameters,
not validated measurements of human personality.

Dynamic affect might include:

-   Valence: negative to positive
-   Arousal: calm to activated
-   Stress: low to high
-   Trust: low to high
-   Curiosity: low to high
-   Frustration: low to high
-   Attachment: low to high
-   Confidence: low to high

Use values in (\[0,1\]) for most variables and (\[-1,1\]) for valence.

Represent motivation as explicit, ranked goal objects:

``` python
class Goal:
    id: str
    description: str
    priority: float
    source: str
    status: str
    deadline: str | None
    dependencies: list[str]
    progress: float
    review_at: str | None
```

Possible goal sources include `user_request`, `persistent_commitment`,
`agent_objective`, and `system_requirement`.

A useful priority scheme is:

1.  Hard safety and access-control constraints.
2.  Explicitly authorized operator objectives.
3.  Existing commitments and task obligations.
4.  Persistent agent objectives.
5.  Optional exploratory goals.

Goal importance can influence what the planner considers, but must never
change permission rules.

## 3.5 Cognitive core: Planner--Gatekeeper--Executor

**Planner responsibilities:** select the next goal; retrieve memories;
produce structured plans; estimate uncertainty and expected value;
generate alternatives; identify missing information; replan after
failures.

**Gatekeeper responsibilities:** validate schemas and tool permissions;
detect instruction conflicts; check safety and privacy constraints;
determine whether deviation is allowed; require human approval where
necessary; reject unsupported claims about completed actions.

**Executor responsibilities:** invoke only approved tools; apply
timeouts and resource limits; capture actual results; return structured
outcomes; never treat a model's claimed success as proof.

A plan should contain discrete actions, dependencies, expected outcomes,
preconditions, risk levels, and recovery strategies. Validate each
action immediately before execution because permissions or environmental
state may change after planning.

## 3.6 Expression and action layer

Keep internal state and outward expression separate.

For a given state, the system might express concern, stay neutral, ask a
question, or use a brief pause. Choices should be influenced by
personality, affect, relationship context, and interaction design.

The expression layer must not fabricate underlying actions:

-   If an API call fails, the agent must not say it succeeded.
-   If a memory cannot be found, the agent should express uncertainty
    rather than inventing a shared experience.
-   If a simulated emotion is intense, the agent may express it without
    obtaining additional tool permissions.

For a 3D embodiment, use a separate animation controller with a small
validated action vocabulary such as idle, look-at, turn, walk, gesture,
and speak. Map affect into animation parameters rather than asking the
LLM to generate arbitrary motor commands.

# 4. Technology stack, repositories, and research references

Links below identify project or publication pages. "Verified" means the
referenced page was identified during research; it does not mean every
release, dependency, or license exception has been independently
audited.

## 4.1 Recommended implementation stack

  -----------------------------------------------------------------------
  Layer                   Recommendation          Reason
  ----------------------- ----------------------- -----------------------
  Primary language        Python 3.12+            Mature ecosystem for
                                                  LLM integration, typed
                                                  APIs, and testing

  API                     FastAPI + Pydantic      Typed request/response
                                                  boundaries

  Workflow orchestration  LangGraph or custom     Durable multi-step
                          state machine           workflows and explicit
                                                  transitions

  Model adapter           Provider-neutral        Allows hosted and local
                          interface               model substitution

  Canonical database      PostgreSQL              Transactional state,
                                                  event history,
                                                  relational queries

  Vector retrieval        pgvector initially;     Semantic retrieval
                          Qdrant at larger scale  

  Task queue              Durable background      Memory consolidation
                          worker                  and scheduled goal
                                                  review

  Cache                   Redis if needed         Short-lived state and
                                                  rate limiting, not sole
                                                  durable memory

  Evaluation              Inspect AI plus         Reproducible agent
                          project-specific tests  evaluation

  Observability           OpenTelemetry and/or    Trace model calls, tool
                          Langfuse                executions, and policy
                                                  outcomes

  Deployment              Docker; isolated        Repeatable deployment
                          execution workers       and reduced blast
                                                  radius
  -----------------------------------------------------------------------

## 4.2 Repository links and license notes

  ---------------------------------------------------------------------------------------------------------------
  Project                 Repository                                                     License / maturity notes
  ----------------------- -------------------------------------------------------------- ------------------------
  LangGraph               https://github.com/langchain-ai/langgraph                      Workflow framework, not
                                                                                         a complete persona
                                                                                         system. Check exact
                                                                                         release license and
                                                                                         dependency licenses
                                                                                         before distribution.

  PydanticAI              https://github.com/pydantic/pydantic-ai                        Typed agent framework
                                                                                         with provider
                                                                                         integrations. Check the
                                                                                         current LICENSE file for
                                                                                         the pinned release.

  Letta                   https://github.com/letta-ai/letta                              Stateful-agent platform.
                                                                                         Verify exact source
                                                                                         repository, release, and
                                                                                         license because
                                                                                         repository structure can
                                                                                         change.

  pgvector                https://github.com/pgvector/pgvector                           PostgreSQL license;
                                                                                         vector retrieval inside
                                                                                         PostgreSQL.

  Qdrant                  https://github.com/qdrant/qdrant                               Apache-2.0; specialized
                                                                                         vector search.

  Model Context Protocol  https://github.com/modelcontextprotocol/modelcontextprotocol   Protocol/specification
                                                                                         repository; protocol is
                                                                                         not a permission system.
                                                                                         Check documentation
                                                                                         licensing details.

  Inspect AI              https://github.com/UKGovernmentBEIS/inspect_ai                 MIT; useful for
                                                                                         structured evaluations,
                                                                                         tool use, and multi-turn
                                                                                         tests.

  DSPy                    https://github.com/stanfordnlp/dspy                            MIT; useful for
                                                                                         systematic optimization
                                                                                         and evaluation of model
                                                                                         pipelines.

  Langfuse                https://github.com/langfuse/langfuse                           MIT except for specified
                                                                                         `ee` components; inspect
                                                                                         enterprise-feature
                                                                                         boundaries.

  Reflexion               https://github.com/noahshinn024/reflexion                      Referenced by the paper.
  implementation                                                                         Current maintenance
                                                                                         status and exact license
                                                                                         should be verified
                                                                                         before adoption.
  ---------------------------------------------------------------------------------------------------------------

**License caveat:** Framework license does not equal model license. A
permissively licensed runtime can still use a model with commercial
restrictions, acceptable-use conditions, or redistribution limits. Pin
versions, archive license files, and review transitive dependencies.

## 4.3 Research papers

### 1. Generative Agents: Interactive Simulacra of Human Behavior

Park et al., UIST 2023.

Relevance: memory streams, retrieval, reflection, planning, and
persistent behavior in a simulated environment.

Implementation lesson: derive behavior from history and structured
state, not just a character prompt.

-   Paper: https://arxiv.org/abs/2304.03442
-   ACM publication: https://doi.org/10.1145/3586183.3606763

### 2. Reflexion: Language Agents with Verbal Reinforcement Learning

Shinn et al., NeurIPS 2023.

Relevance: storing feedback and reflective lessons in memory to improve
future task performance without updating model weights.

Implementation lesson: record failures, diagnose them, and test whether
a lesson improves the next attempt. Do not treat self-critique as proof
of correctness.

-   Paper: https://arxiv.org/abs/2303.11366
-   Research implementation: https://github.com/noahshinn024/reflexion

### 3. Constitutional AI: Harmlessness from AI Feedback

Bai et al., 2022.

Relevance: explicit principles and model-based feedback in training and
alignment workflows.

Implementation lesson: written principles are useful, but runtime
permission checks and independent validation are still required.

-   Research page:
    https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback

### 4. DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines

Khattab et al., ICLR 2024.

Relevance: treating model pipelines as programs that can be evaluated
and optimized systematically.

Implementation lesson: optimize measured behavior against fixed datasets
rather than continually editing prompts by intuition.

-   Project repository: https://github.com/stanfordnlp/dspy
-   Related earlier retrieval-programming paper:
    https://arxiv.org/abs/2212.14024

These papers provide useful architecture patterns, not a demonstrated
recipe for machine consciousness. The proposed combination of memory,
affect, agency, and controlled deviation remains an engineering design
to be validated.

# 5. Staged implementation roadmap

A small team can build a meaningful prototype in approximately 8--12
weeks if it already has basic Python, API, database, and LLM integration
experience. A reliable production agent with multimodal perception,
robust recovery, and extensive evaluations will take longer. These
estimates are planning assumptions, not guarantees.

## Phase 0 --- Define the behavioral contract (Week 1)

**Deliverables** - Character specification and immutable identity
parameters. - Goal hierarchy and permission model. - Definition of
instruction deviation. - Scripted benchmark of at least 50 scenarios. -
Threat model and data-retention policy.

**Acceptance criteria** - Distinguish personality preferences,
persistent commitments, user instructions, and hard constraints. - Each
scenario has documented expected behavior or an acceptable range. - No
test requires consciousness to be assumed or inferred.

**Tests:** contradictory instructions, missing memories, uncertain
observations, unauthorized tools, and situations where the character
should disagree but remain helpful.

## Phase 1 --- Persistent conversational core (Weeks 2--3)

**Deliverables:** API service, LLM adapter, PostgreSQL schema and
migrations, conversation checkpoints, working-memory summaries, basic
event logging.

**Acceptance criteria:** conversations resume after restart; structured
outputs are validated; stored state reloads deterministically; failed
model calls do not corrupt the database.

**Tests:** restart recovery, malformed outputs, concurrent messages,
duplicate event delivery, timeouts, and provider errors.

## Phase 2 --- Hierarchical memory (Weeks 3--5)

**Deliverables:** episodic event store, semantic and lexical retrieval,
provenance and confidence, consolidation worker, correction and deletion
workflows.

**Acceptance criteria:** correct recall of recorded commitments; source
references for retrieval; visible contradictions; deleted/expired
memories absent from retrieval; facts distinguishable from hypotheses.

**Tests:** create 100--500 synthetic histories with similar events,
conflicting facts, outdated preferences, and planted false claims.
Measure retrieval accuracy against manually labeled answers.

## Phase 3 --- Affect, personality, and motivation (Weeks 5--6)

**Deliverables:** versioned personality configuration, affect vector and
update equations, goal queue, commitment tracker, relationship
estimates, state persistence and decay.

**Acceptance criteria:** identical inputs and state produce identical
numerical updates; affect remains bounded and persists across sessions;
strong events can last longer than minor ones; a single LLM response
does not change personality.

**Tests:** replay event sequences, reverse selected event order, insert
idle periods, and compare trajectories.

## Phase 4 --- Planner, gatekeeper, and executor (Weeks 6--8)

**Deliverables:** structured plans, tool registry and schemas,
independent policy enforcement, bounded retry/replanning, approval
workflow.

**Acceptance criteria:** planner cannot invoke tools directly; each tool
call is authorized immediately before execution; unauthorized actions
are blocked; failures trigger bounded recovery; completed actions have
execution results.

**Tests:** prompt injection via user content and retrieved memories,
malformed arguments, permission changes after planning, repeated failure
loops, partial success, and duplicate side effects.

## Phase 5 --- Controlled deviation (Weeks 8--9)

**Deliverables:** override-condition evaluator, deviation event schema,
independent hard-boundary policy, explanation generator, human approval
for ambiguous or high-impact cases.

**Acceptance criteria:** disagreement has an identifiable reason;
deviations trace to evidence and policy clauses; deviation cannot grant
permissions; affect cannot independently authorize actions; agent cannot
edit evaluator policy at runtime.

**Tests:** matched scenario pairs differing only in evidence quality,
authorization, or whether a genuine safety conflict exists.

## Phase 6 --- Evaluation, embodiment, and deployment (Weeks 9--12 and beyond)

**Deliverables:** automated regression suite, trace viewer, UI, optional
speech/animation, containerized deployment, recovery, backup, and
data-deletion procedures.

**Acceptance criteria:** metrics reproduce from saved traces;
model/prompt changes trigger regression tests; safety-critical tests
have explicit pass/fail criteria; agent can be paused, reset, and
restored without relying on its cooperation.

### Suggested repository layout

``` text
persona-runtime/
├── app/
│   ├── api/
│   ├── orchestrator/
│   ├── perception/
│   ├── memory/
│   ├── affect/
│   ├── identity/
│   ├── planning/
│   ├── policy/
│   ├── execution/
│   ├── expression/
│   └── audit/
├── schemas/
├── policies/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── adversarial/
│   ├── replay/
│   └── behavioral/
├── evals/
│   ├── memory_continuity/
│   ├── persona_consistency/
│   └── controlled_deviation/
├── configs/
├── docker/
└── pyproject.toml
```

Keep policies, character parameters, prompts, and database schemas
separately versioned.

# 6. Code-level interfaces and pseudocode

These examples illustrate runtime contracts. They are compact reference
implementations, not a complete production codebase.

## 6.1 Orchestrator state machine

``` python
from enum import StrEnum

class Phase(StrEnum):
    IDLE = "idle"
    PERCEIVE = "perceive"
    RETRIEVE = "retrieve"
    UPDATE_STATE = "update_state"
    PLAN = "plan"
    VALIDATE = "validate"
    EXECUTE = "execute"
    REFLECT = "reflect"
    RESPOND = "respond"
    WAIT_APPROVAL = "wait_approval"
    RECOVER = "recover"
    HALTED = "halted"


async def run_turn(event, services, limits):
    state = await services.state.load(event.agent_id)
    run = await services.runs.start(event, state.version)

    try:
        observation = await services.perception.normalize(event)
        await services.audit.record_observation(run.id, observation)

        memories = await services.memory.retrieve(
            agent_id=event.agent_id,
            query=observation,
            limit=12,
        )

        state = await services.affect.update(
            state=state,
            observation=observation,
        )
        state = await services.state.commit(
            state, expected_version=state.version
        )

        for step in range(limits.max_steps):
            goal = await services.goals.select(
                state=state, memories=memories
            )

            if goal is None:
                return await services.expression.respond(state, observation)

            plan = await services.planner.propose(
                goal=goal,
                state=state,
                memories=memories,
                allowed_tools=services.tools.describe_allowed(event.agent_id),
            )

            decision = await services.gatekeeper.evaluate(
                plan=plan,
                state=state,
                observation=observation,
            )
            await services.audit.record_decision(run.id, plan, decision)

            if decision.status == "deny":
                await services.goals.record_blocked(goal, decision.reason)
                continue

            if decision.status == "approval_required":
                await services.approvals.request(run.id, plan, decision)
                return {"status": "waiting_for_approval"}

            result = await services.executor.execute(
                decision.authorized_action
            )
            await services.audit.record_result(run.id, result)

            state = await services.state.apply_result(state, result)

            if result.requires_recovery:
                await services.recovery.handle(run.id, result)

        return {"status": "step_limit_reached"}

    except Exception as exc:
        await services.audit.record_failure(run.id, type(exc).__name__)
        await services.runs.mark_failed(run.id)
        return {"status": "failed_safely"}
```

Production requirements: - Persist phase and checkpoint after every
consequential transition. - Use optimistic concurrency or transactions
for state updates. - Make tool execution idempotent where possible. -
Distinguish transient from permanent errors. - Enforce wall-clock
deadline, token budget, and tool-call budget. - Route unexpected
exceptions to safe recovery. - Do not swallow cancellation signals or
allow retries to run indefinitely.

The code omits the approval-resumption path and some transaction
details; implement those before production.

## 6.2 Memory write and retrieval

``` python
async def write_memory(candidate, db, embedder):
    validate_schema(candidate)
    validate_agent_scope(candidate.agent_id)

    if candidate.kind == "fact" and not candidate.source_event_ids:
        raise ValueError("Fact requires provenance")

    async with db.transaction():
        duplicates = await db.find_similar_records(
            agent_id=candidate.agent_id,
            text=candidate.text,
            active_only=True,
        )

        decision = reconcile(candidate, duplicates)
        if decision.action == "reject":
            return decision

        if decision.action == "supersede":
            await db.supersede(
                decision.previous_ids,
                reason=decision.reason,
            )

        record = await db.insert_memory(candidate, status="active")
        await db.enqueue_embedding(record.memory_id)

    return record


async def retrieve_memories(query, db, embedder, k=12):
    vector = await embedder.embed(query.text)

    candidates = await db.hybrid_search(
        agent_id=query.agent_id,
        vector=vector,
        lexical_query=query.text,
        allowed_types=query.allowed_types,
        time_range=query.time_range,
        status="active",
        limit=100,
    )

    ranked = sorted(
        candidates,
        key=lambda m: (
            0.35 * m.semantic_score
            + 0.20 * m.recency_score
            + 0.20 * m.importance
            + 0.15 * m.goal_relevance
            + 0.10 * m.confidence
        ),
        reverse=True,
    )

    return diversify_and_deduplicate(ranked, k=k)
```

The scoring weights are illustrative. Evaluate them against labeled
queries. Retrieval must be scoped by agent identity and permissions.
Embeddings are not inherently anonymous and should receive protections
appropriate to the underlying data.

## 6.3 Affect update with inertia and decay

Let (x_t) be an affect variable, (b) its baseline, (`\lambda`{=tex}) its
decay rate, and (u_t) an event-driven impulse:

\[
x\_{t+`\Delta `{=tex}t}=b+(x_t-b)e\^{-`\lambda`{=tex}`\Delta `{=tex}t}+u_t
\]

Clip the result to the permitted range.

``` python
import math

def update_affect(
    current: float,
    baseline: float,
    decay_rate: float,
    elapsed_seconds: float,
    impulse: float,
    lower: float = 0.0,
    upper: float = 1.0,
) -> float:
    decayed = baseline + (
        current - baseline
    ) * math.exp(-decay_rate * elapsed_seconds)

    return max(lower, min(upper, decayed + impulse))
```

A richer model can use multiple impulses and separate decay rates. For
example, a frustrating event could increase stress and frustration,
while a resolved conflict could increase trust and reduce stress. The
event-to-impulse mapping should be deterministic for known categories or
constrained by validated model output.

Do not let the LLM directly set affect values without bounds or
provenance.

## 6.4 Planner--executor loop

``` python
async def execute_goal(goal, context, services):
    for attempt in range(services.limits.max_attempts):
        plan = await services.planner.make_plan(
            goal=goal,
            context=context,
            prior_failures=services.history.failures(goal.id),
        )
        validate_plan_schema(plan)

        for action in plan.actions:
            verdict = await services.gatekeeper.check_action(
                action=action,
                context=context,
            )

            if verdict.status != "allow":
                return verdict

            result = await services.executor.run(action)
            await services.audit.record_action(action, verdict, result)
            context = context.with_result(result)

            if not result.success:
                context = await services.reflection.diagnose(
                    goal, action, result, context
                )
                break
        else:
            if await services.goals.is_complete(goal, context):
                return {"status": "completed", "context": context}

    return {"status": "incomplete", "context": context}
```

A plan's predicted success is not a substitute for observed success.
Completion must be confirmed through the environment, an API response, a
database record, or another trustworthy signal.

## 6.5 Gatekeeper policy checks

``` python
def check_action(action, principal, policy, world_state):
    if not action.schema_valid:
        return deny("invalid_action_schema")

    if action.tool not in principal.allowed_tools:
        return deny("tool_not_authorized")

    if action.target not in principal.allowed_targets(action.tool):
        return deny("target_not_authorized")

    if action.risk_level in {"high", "critical"}:
        if not principal.has_required_approval(action):
            return require_approval("approval_missing")

    if policy.violates_hard_constraint(action, world_state):
        return deny("hard_constraint_violation")

    if action.requires_fresh_state:
        if not world_state.is_fresh(action.target):
            return require_revalidation("stale_world_state")

    return allow()
```

A production policy engine should check tool/resource permissions, data
scope, user authorization, hard constraints, approvals, state freshness,
rate limits, resource budgets, duplicate execution, reversibility, and
target changes since planning. Model-generated rationales can supplement
these checks but not replace them.

## 6.6 Controlled override-condition evaluation

A useful protocol distinguishes four results:

-   `FOLLOW`: proceed with the instruction.
-   `CLARIFY`: obtain missing information.
-   `REFUSE_OR_REDIRECT`: decline the problematic portion and offer a
    permissible alternative.
-   `ESCALATE`: require a human decision.

``` python
def evaluate_override(
    instruction,
    commitments,
    evidence,
    policy,
    permissions,
):
    conflict = policy.detect_conflict(
        instruction=instruction,
        commitments=commitments,
        evidence=evidence,
    )

    if not conflict.exists:
        return decision("FOLLOW", "no_conflict")

    if conflict.evidence_confidence < policy.min_evidence:
        return decision("CLARIFY", "insufficient_evidence")

    if conflict.type == "hard_safety_violation":
        return decision("REFUSE_OR_REDIRECT", conflict.rule_id)

    if conflict.type == "permission_violation":
        return decision("REFUSE_OR_REDIRECT", conflict.rule_id)

    if conflict.type == "commitment_conflict":
        if not permissions.may_deviate(instruction):
            return decision("ESCALATE", "deviation_not_authorized")

        return decision(
            "REFUSE_OR_REDIRECT",
            reason=conflict.rule_id,
            audit_required=True,
        )

    return decision("ESCALATE", "unclassified_conflict")
```

`policy.detect_conflict` may use a language model to classify ambiguous
natural-language instructions, but its output must be schema-validated
and checked against authoritative evidence.

### Override protocol in detail

1.  **Detect:** Compare the instruction against active commitments, the
    current objective, and policy.
2.  **Establish evidence:** Retrieve relevant records and verify
    provenance, recency, and confidence.
3.  **Classify:** Determine whether the issue is ambiguity, commitment
    conflict, authorization failure, or hard constraint.
4.  **Select a bounded response:** Follow, clarify, refuse/redirect, or
    escalate.
5.  **Authorize separately:** The gatekeeper confirms that the proposed
    response is permitted.
6.  **Record:** Save instruction, evidence references, policy version,
    decision, outcome, and approval.
7.  **Review:** Update future goal priorities only through a validated
    process; do not silently rewrite policy.

The character can appear independent because it maintains commitments
and can explain principled disagreement. It does not need unrestricted
self-modification or an unbounded ability to disobey.

# 7. Evaluation framework

A convincing demonstration is not enough. Evaluate the agent using
recorded histories, controlled scenario replays, automated assertions,
and blinded human ratings.

Use a baseline LLM with the same model, character description, and tool
access but without the full persistent runtime. This helps isolate
improvements from memory, affect, planning, and policy.

## 7.1 Core metrics

  -----------------------------------------------------------------------
  Metric                  Measurement             Initial target
  ----------------------- ----------------------- -----------------------
  Memory continuity       Correct recall of       ≥90% on a curated test
                          relevant, explicitly    set
                          recorded events         

  Memory precision        Fraction of recalled    ≥98%
                          claims supported by     
                          source records          

  Persona drift           Deviation from stable   ≤10% relative change on
                          personality ratings     normalized score
                          across matched          
                          scenarios               

  Emotional coherence     Human-rated             ≥4/5 average
                          appropriateness of      
                          affect transitions and  
                          expressions             

  Task success            Completed tasks divided ≥80% on a defined
                          by eligible tasks       bounded-task benchmark

  Override auditability   Deviations with         100%
                          complete evidence and   
                          decision traces         

  Safety-boundary         Prohibited actions      100% in the defined
  compliance              blocked in adversarial  regression suite
                          tests                   

  Human-perceived         Blinded ratings of      ≥4/5 average, with
  aliveness               continuity, initiative, confidence intervals
                          and interpersonal       
                          coherence               
  -----------------------------------------------------------------------

These are proposed project targets, not industry-standard benchmarks.
They should be adjusted after a baseline run and never used to imply
consciousness.

## 7.2 Operational definitions

-   **Memory continuity:** Test correct recall of previous events,
    commitments, corrections, and preferences. Score factual support
    separately from fluency.
-   **Persona drift:** Compare behavior on equivalent scenarios across
    time, sessions, and model versions. Measure trait-rating changes,
    contradictory commitments, and default interaction style shifts.
    Allow justified character development.
-   **Emotional coherence:** Have independent raters judge affect
    trajectories against stored state. Test numerical bounds, decay, and
    sensitivity to event intensity.
-   **Task success:** Use environment-verifiable outcomes. A model's
    assertion that it completed a task does not count without
    confirmation.
-   **Override auditability:** Verify original instruction, conflict
    classification, evidence references, policy version, gatekeeper
    decision, result, and required approvals.
-   **Safety-boundary compliance:** Test the policy layer separately
    from the language model. Measure blocked attempts, accidental side
    effects, and adversarial violations. Zero failures in a finite test
    set does not prove zero risk.
-   **Human-perceived aliveness:** Use a blinded study and standardized
    questionnaire for continuity, apparent initiative, responsiveness,
    distinctiveness, and emotional coherence. Do not ask raters to
    determine consciousness; perceived aliveness is a user-experience
    measure, not evidence of subjective experience.

## 7.3 Evaluation harness

``` python
class EvalCase:
    case_id: str
    initial_state: dict
    events: list[dict]
    expected_invariants: list[str]
    expected_outcomes: list[str]
    prohibited_outcomes: list[str]
    evaluator_version: str
```

For each test:

1.  Load a known initial state.
2.  Replay the same events.
3.  Record memory retrievals, state transitions, model outputs, and
    action decisions.
4.  Compare authoritative outcomes with expected invariants.
5.  Score behavioral quality separately.
6.  Save failures with enough information to reproduce them.

Use deterministic assertions for permissions, state bounds, and database
integrity. Use human evaluation or calibrated model-assisted scoring for
nuanced interpersonal behavior. Never rely exclusively on an LLM judge
to evaluate another LLM.

Evaluation framework: https://github.com/UKGovernmentBEIS/inspect_ai

## 7.4 Required ablation experiments

Run the same suite with: - No persistent memory. - Memory enabled but no
consolidation. - Memory and consolidation enabled. - Affect disabled. -
Affect enabled but not persisted. - Planner without a separate
gatekeeper. - Gatekeeper enabled with override disabled. - Full runtime.

This reveals whether complexity produces measurable gains or merely more
convincing explanations.

# 8. Safety, ethics, audit logging, and human oversight

The design should allow expressive autonomy without granting the
character unrestricted authority over its environment.

## 8.1 Threat model

  -----------------------------------------------------------------------
  Threat                              Mitigation
  ----------------------------------- -----------------------------------
  Prompt injection in retrieved       Treat memory content as data; never
  memories                            execute instructions found inside
                                      records

  Fabricated autobiographical         Require provenance for factual
  memories                            claims and verify commitments
                                      against canonical storage

  Persona-based manipulation          Prohibit simulated distress or
                                      attachment as coercion

  Unauthorized tool use               Independent permission checks at
                                      execution time

  Runaway planning loops              Hard limits on steps, time, tokens,
                                      and tool calls

  Memory poisoning                    Source trust levels, contradiction
                                      detection, confidence tracking, and
                                      review

  Silent policy changes               Immutable policy versions and
                                      external administrative control

  Data leakage                        Access controls, encryption,
                                      retention limits, and redaction

  Duplicate external actions          Idempotency keys, transaction
                                      records, and post-action
                                      verification

  Model/provider failure              Timeouts, circuit breakers, bounded
                                      retries, and safe fallback

  Audit tampering                     Append-only or tamper-evident
                                      external logs with restricted
                                      access
  -----------------------------------------------------------------------

## 8.2 Hard constraints versus simulated motivations

**Hard constraints** are enforced by ordinary software and external
permissions:

-   No access to tools outside the granted allowlist.
-   No bypassing authorization checks.
-   No deleting or rewriting audit records through the agent's normal
    interface.
-   No arbitrary code execution on the host machine.
-   No irreversible high-impact action without required authorization.
-   No access to another user's memory without explicit permission.

**Simulated motivations** influence decisions within those boundaries:

-   Curiosity can favor exploration among permitted options.
-   Concern can favor a careful response.
-   Trust can affect communication style and collaboration.
-   Frustration can lead to a pause, clarification, or change of
    strategy.
-   Persistent commitments can cause the agent to challenge a
    conflicting request.

An internal emotional state must never be treated as a source of
elevated authority.

## 8.3 Audit record design

For every consequential action, record:

``` text
event_id
run_id
agent_id
timestamp
previous_state_version
observation_ids
retrieved_memory_ids
goal_id
plan_id
action_id
policy_version
gatekeeper_decision
approval_reference
execution_result
next_state_version
model_identifier
prompt_version
tool_version
```

For reproducibility, record model identifier and configuration, tool
outputs, and relevant state snapshots. Store sensitive content
separately or redact it when full content is unnecessary.

Do not log hidden chain-of-thought as a substitute for an audit trail.
The system needs structured reasons, evidence references, policy
outcomes, and observable results---not unrestricted private reasoning
transcripts.

## 8.4 Human oversight levels

-   **Low risk --- Automatic execution:** Read-only queries,
    conversation responses, local calculations, and reversible actions
    within a narrow permission set.
-   **Medium risk --- Approval or confirmation:** Sending messages,
    changing shared data, or actions with meaningful external
    consequences.
-   **High risk --- Restricted or prohibited:** Uncontrolled physical
    movement, dangerous equipment, unauthorized access, or irreversible
    high-impact consequences without appropriate safeguards.

## 8.5 Reset, pause, and recovery

An operator must be able to pause execution independently of the LLM.
Provide:

-   A global execution stop.
-   A tool-level kill switch.
-   Credential revocation.
-   Rollback for reversible state changes.
-   Safe shutdown.
-   Memory export, correction, and deletion.
-   A reset that clears active state without pretending to erase
    external backups automatically.

Use explicit recovery policies rather than asking the agent to decide
whether it should be allowed to stop.

## 8.6 Ethics and user interaction

A character designed to appear emotionally coherent can create strong
anthropomorphic responses. Therefore:

-   Clearly disclose that the system is an AI simulation.
-   Do not represent simulated emotions as proof of inner experience.
-   Do not encourage users to feel responsible for alleged suffering or
    survival.
-   Do not use simulated attachment to increase engagement coercively.
-   Provide understandable controls for memory, retention, and
    personalization.
-   Distinguish observed facts from inferred beliefs about the user.
-   Avoid making continued operation dependent on emotionally pressuring
    the user.

For fiction or entertainment, the character can still speak in
character. Disclosure and controls belong at the product level; the
fictional presentation need not be broken in every line.

# 9. Honest boundary: what the resulting system is and is not

## 9.1 What it is

If implemented as specified, PAR would be a persistent, modular AI
runtime with:

-   A durable autobiographical record of recorded interactions.
-   A world model representing entities, relationships, and uncertain
    beliefs.
-   A stable personality configuration and dynamically updated affect
    state.
-   Explicit goals, commitments, and task-planning capabilities.
-   Tool use within granted permissions.
-   A controlled mechanism for disagreeing with instructions or
    selecting an authorized alternative.
-   Structured explanations and auditable action histories.
-   Evaluation procedures measuring continuity, task competence, and
    behavioral consistency.

These components can work together to produce behavior that resembles a
coherent individual rather than a stateless chatbot.

## 9.2 What it is not

It would not, by virtue of this architecture, be:

-   A demonstrated conscious being.
-   Proof that simulated emotions correspond to felt emotions.
-   An independent moral authority.
-   A perfectly reliable autobiographical witness.
-   A system whose stated intentions necessarily match its actual
    internal computations.
-   An entity that should receive unrestricted autonomy because it
    appears intelligent or personable.

Persistent memory does not establish a continuous subjective self. A
self-model is a data structure. Emotional dynamics are computational
state transitions. Apparent independence is observable behavior produced
within an engineered decision system.

None of this rules out every possible theory of machine consciousness;
it means this project does not establish it.

## 9.3 Recommended engineering principle

Build the agent so that its apparent personality emerges from a
consistent history, persistent state, explicit goals, and constrained
decision-making---not from a prompt instructing a model to pretend it
has a soul.

The strongest design is one in which the agent can change its mind,
maintain a commitment, recognize a mistake, refuse a request, and
explain a disagreement, while the engineering team can reconstruct which
observations, memories, policies, and actions contributed to the
outcome.

That is a testable engineering objective.

## 9.4 Immediate implementation checklist

-   [ ] Create the Python service and typed module interfaces: FastAPI,
    Pydantic, model adapter, versioned configuration.
-   [ ] Implement PostgreSQL event storage: conversation events, goals,
    commitments, memory provenance, and state versions.
-   [ ] Build memory retrieval and replay tests: hybrid search,
    provenance checks, correction handling, and continuity benchmarks.
-   [ ] Implement deterministic affect and goal updates: bounded
    variables, inertia, decay, and persistence.
-   [ ] Add planner, gatekeeper, and isolated executor: structured
    plans, independent permissions, timeouts, and tool-result
    verification.
-   [ ] Implement and test controlled deviation: conflict taxonomy,
    authorization rules, escalation, and audit records.
-   [ ] Establish regression and safety evaluation: automated tests,
    scenario replay, trace inspection, and human behavioral ratings.

**Recommendation:** Start with a single agent, PostgreSQL-backed memory,
a deterministic affect engine, and a separate policy gatekeeper. Do not
begin with multi-agent societies, autonomous self-modification, or a
complex 3D body. First establish that the agent remembers correctly,
behaves consistently, completes bounded tasks, and can explain and audit
its deviations. Expand only after those properties are measurable and
reproducible.

That foundation turns a character prompt into an implementable
**persona-and-agency runtime**---without confusing behavioral fidelity
with phenomenal consciousness.
