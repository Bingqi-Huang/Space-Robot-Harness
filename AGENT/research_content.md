# Research Content — Space Robotics Agent Harness for Future Lunar Autonomy

**Status:** frozen high-level framing; method and experiments specified at paper-outline level; results pending execution  
**Target venue:** Acta Astronautica  
**Scope:** future lunar robotic operations, mission-level autonomy, trustworthy agentic runtime  
**Reference embodiment:** LunarBot as a later real-system reference; primary scientific validation in simulation

---

## Working title

**From Pre-Engineered Task Models to Mission-Intent Autonomy: A Trustworthy Agentic Runtime for Lunar Robots**

Alternative title direction:

**A Space-Native Agent Harness for Open-Ended, Trustworthy Mission Autonomy in Lunar Robotics**

The final title should be selected only after the experiments establish the strongest supported claim. The title must not imply that classical space autonomy lacks onboard planning or replanning; the distinction tested here is the boundary imposed by pre-engineered mission/task models and the engineering effort required to expand that boundary.

---

# Abstract — intended logic

Future lunar robots will increasingly combine autonomous navigation, manipulation, semantic perception, planning, fault management, and heterogeneous local/remote computation. Classical space autonomy has already demonstrated onboard planning, scheduling, execution monitoring, resource reasoning, and replanning. Systems such as CASPER, MEXEC, EUROPA-based planners, and PLEXIL therefore provide a strong starting point rather than a weak strawman. Their strength is explicit operational knowledge and disciplined execution; their practical boundary is that the task vocabulary, procedures, task networks, domain constraints, and recovery structure are predominantly engineered before deployment.

This work investigates a different operating model for long-horizon lunar robotics. A foundation-model agent is given responsibility for **mission strategy**: interpreting mission intent, understanding semantically novel situations, deciding what to observe next, forming and revising task decompositions, selecting and composing heterogeneous capabilities, diagnosing unexpected outcomes, and communicating with operators. The surrounding **Space Robotics Agent Harness** is intentionally thin at the mission-strategy level. It does not encode scenario-specific procedures or recovery graphs. Instead, it provides the execution substrate that mature coding agents rely on in another domain: typed tools, persistent state, bounded authority, hard execution invariants, tool availability, independent verification, evidence capture, context reconstruction, and auditable traces.

The design principle is **pre-engineer invariants, not mission solutions**. The harness may enforce facts that must never be violated — physical safety limits, explicit authority boundaries, hard capability/service availability, critical resource constraints, and verification requirements — but it does not decide whether the robot should inspect before manipulating, which recovery branch is appropriate, which capability ordering is best, or how a held-out servicing problem should be decomposed. Those mission-level choices remain with the foundation-model agent and can change online as observations arrive.

The scientific question is therefore not whether an LLM can call robot tools, nor whether onboard replanning is useful. It is whether this agent-harness operating model can **expand the autonomous mission envelope beyond fully pre-engineered task models, and make that envelope cheaper to extend**, while retaining the state integrity, hard authority boundaries, FDIR, low-level safety, independent effect verification, and traceability expected in aerospace systems.

The primary evaluation contains only two scientific experiments. **Experiment I** compares official PLEXIL, an EUROPA-to-PLEXIL planning/execution baseline, and the proposed runtime on the same LunarBot capability stack under model-covered and model-held-out mission situations. The main outcomes are mission success and autonomy measures grounded in the NIST ALFUS framework, including human intervention ratio, human planning/preplanning burden, interaction authority level, and the degree of mission variation handled without new preplanning. **Experiment II** freezes all three systems, introduces new mission capability or mission knowledge, and measures the engineering effort required to reach validated support and the resulting held-out mission performance. A later LunarBot hardware demonstration validates transfer of the runtime but is not treated as a third scientific experiment.

The intended claim is that foundation-model-driven agentic reasoning can broaden and simplify the expansion of mission-level lunar robotic autonomy when the harness protects **execution invariants and mission truth rather than encoding mission solutions**.

# 1. Introduction

## 1.1 The problem begins with future lunar operations

Future lunar activity is expected to involve infrastructure inspection and maintenance, logistics, payload handling, construction and assembly, scientific observation and sampling, ISRU-related operations, and servicing of power, communication, and mobility infrastructure. These activities increasingly require mobile manipulation over long durations with less continuous Earth supervision.

The relevant autonomy stack is already rich. Planetary robotics has demonstrated autonomous navigation, science targeting, onboard planning and scheduling, integrated planning and execution, execution monitoring, resource-aware activity management, and fault handling. Modern robotics adds open-vocabulary perception, VLM reasoning, learned manipulation policies, and general-purpose foundation models.

The emerging problem is therefore not simply a missing primitive algorithm. It is the **operating model used to turn many heterogeneous capabilities into persistent mission autonomy**.

## 1.2 Classical space autonomy is strong — but it has a modeling boundary

The paper must not frame classical space autonomy as fixed scripting. That would be technically incorrect and would weaken the contribution.

CASPER continuously repairs a working plan when goals or state change. MEXEC integrates planning, scheduling, execution monitoring, temporal/resource constraints, and replanning. The Mars 2020 On-Board Planner and CADRE demonstrate increasingly capable onboard autonomy. PLEXIL provides expressive reactive plan execution with explicit conditions, concurrency, loops, external state lookups, command execution, and resource arbitration. EUROPA provides a declarative plan database and solver for actions, states, resources, and constraints.

These systems establish an important baseline: **goal-based onboard autonomy, flexible execution, and replanning already exist**.

The remaining boundary is different. Their autonomous behavior is grounded in operational knowledge engineered ahead of time: PLEXIL plans and libraries; task networks and task templates; EUROPA/NDDL domain models; declared actions, state variables, resource models, constraints, and recovery logic. Even when the planner dynamically chooses or schedules activities, it reasons over a designed task/domain representation.

This is not merely a theoretical limitation. JPL's TaskNet work explicitly identifies spacecraft task-network specification as a largely manual, cumbersome, difficult-to-verify, and error-prone process, and motivates automated task-network generation to reduce plan-creation time. The broader automated-planning literature likewise treats domain-model creation and maintenance as a knowledge-engineering bottleneck.

The research opportunity is therefore not "replace NASA planning with an LLM." It is:

> **Use foundation models to extend mission autonomy into situations whose semantic interpretation and task decomposition were not exhaustively encoded before deployment, while retaining model-based and rule-based mechanisms where explicit operational semantics are required.**

## 1.3 What foundation models add

Foundation models provide capabilities that are qualitatively different from temporal scheduling or constraint propagation:

- interpretation of natural-language mission intent;
- semantic understanding of open visual scenes through a VLM;
- diagnosis of situations that were not represented as a complete symbolic state template;
- generation and revision of task decompositions from an existing capability repertoire;
- dynamic capability composition and substitution;
- deciding what additional observation is useful when the current state is ambiguous;
- online recovery strategy after unexpected outcomes;
- natural-language explanation, status reporting, and escalation.

The key methodological choice is that these are not merely advisory functions around a conventional handcrafted mission executive. **The foundation-model agent owns task-level strategy.** It may decide ordering, observation, decomposition, substitution, and recovery online. The harness does not duplicate those decisions in a second rule engine.

The model still does not own raw motor control, authoritative physical state, hard authority limits, FDIR, low-level safety, or the declaration that a physical effect has actually occurred.

## 1.4 Agent harnesses provide the systems pattern

Mature coding agents provide a useful systems precedent because they separate **agent reasoning** from **execution infrastructure** without encoding the solution to each coding task in the harness. Hermes Agent centers its loop on model-generated tool calls dispatched through a tool registry; its runtime manages tool schemas, dispatch, history, recovery, provider failover, and persistent agent state. Pi explicitly presents itself as a minimal harness whose core remains small and is extended through tools/skills/extensions. OpenAI Codex similarly separates the model's task strategy from sandboxing, approvals, network policy, tool execution, thread persistence, and telemetry.

The transferable design principle is not that lunar robots should imitate software-development workflows. It is that a capable agent harness should answer questions such as:

- **What tools exist and how are they called?**
- **What state and evidence are authoritative?**
- **What actions are technically or institutionally forbidden?**
- **What requires approval?**
- **What actually happened after a tool call?**
- **How is context reconstructed after interruption?**
- **How can the resulting behavior be audited?**

It should generally **not** answer the task-strategy question: *what sequence of domain actions is the correct solution to this particular mission situation?*

OpenRAL already provides much of the robotic analogue: an event-driven reasoner that emits typed tool calls, a capability-compatible rSkill palette, independent execution, world-state aggregation, observability, and a low-level safety boundary. This work therefore uses OpenRAL as the physical-agent substrate and adds only the mechanisms required for persistent, space-native mission operation.

The resulting loop is:

**mission intent → evidence-grounded context → model chooses observation/capability → invariant/authority check → execution → effect observation/verification → authoritative state update → next model decision.**

This paper tests whether that operating model changes the practical autonomous mission envelope relative to established plan-/model-driven approaches.

## 1.5 Why a generic physical-agent harness is insufficient

The space-native architecture is not motivated by adding lunar metadata to a terrestrial robot agent. It is derived from concrete lunar mission-operating conditions that change **where reasoning can occur, when ground support is available, which actions are operationally admissible, and what evidence must be preserved for mission control**.

### 1.5.1 Earth cannot remain synchronously inside every decision loop

Lunar operations retain much shorter delays than Mars, but they are already outside the assumptions of a continuously connected terrestrial robot. NASA's 2025 review of communication-delay research identifies approximately **3–14 s one-way operational communication delays** as relevant to lunar missions and explicitly notes that beyond-LEO delay challenges the traditional paradigm of real-time ground support and increases the need for greater local autonomy (Landon et al., 2025). The problem is not latency alone. LunaNet is being defined as a network-of-networks using both Direct-with-Earth and lunar relay services, while NASA's Delay/Disruption Tolerant Networking (DTN) architecture is designed for links with disconnections, delay, rate mismatch, and time-disjoint availability using store-and-forward delivery (NASA/ESA/JAXA, 2025; NASA SCaN, 2026).

The architectural consequence is that **mission execution must not require a synchronous Earth-side model or operator at every deliberative step**. Earth-side reasoning should be treated as valuable but intermittently available support. Mission continuity, critical state, execution authority, and immediate recovery therefore need an onboard/local representation that survives link interruption.

### 1.5.2 The strongest model cannot simply be assumed to run continuously onboard

The opposite extreme — placing the most capable foundation model permanently onboard and ignoring distributed computation — is also unrealistic as a general lunar architecture assumption. NASA's High Performance Spaceflight Computing (HPSC) program is explicitly driven by the combined need for much higher onboard compute, **power management, radiation tolerance/fault tolerance, and connectivity**. NASA notes that communication latency increases the need for real-time onboard autonomy, while the space radiation environment and power budgets make flight computing qualitatively different from terrestrial datacenter computing. HPSC is being developed to provide more than two orders of magnitude improvement over legacy space processors while retaining power-aware and fault-tolerant operation (NASA HPSC, 2024–2026).

This motivates a **heterogeneous intelligence hierarchy** rather than a single assumed model location:

- **onboard/local reasoning** is the continuity layer and must remain usable without Earth;
- **surface or nearby edge compute**, if a specific mission architecture provides it, may host stronger services with lower latency than Earth;
- **Earth-side compute and human expertise** can provide the highest-capability reasoning and mission support when the link is available.

The architecture does **not** assume that a lunar relay spacecraft automatically provides general-purpose foundation-model compute. Relay/edge reasoning is optional and mission-architecture dependent; LunaNet/LCRNS primarily establishes communication and navigation services, not a universal orbital AI-compute tier.

### 1.5.3 Energy, thermal state, and health change whether a semantically sensible action is executable

Lunar operating context is not merely descriptive prompt information. JPL's CADRE autonomy work provides a direct example: its MEXEC-based Strategic Planner monitors actual and predicted **temperature and energy levels** to decide when rovers should survey, sleep, cool, and recharge. NASA studies of uncrewed lunar surface operations likewise identify illumination/shadow, thermal management, battery pre-charging, load shedding, hibernation, and adaptive operation as determinants of what can be performed without crew or ground intervention (Lewis et al., 2022; Rabideau et al., 2025).

Therefore an LLM proposal such as "service the component now" is not automatically an executable command. Resource, health, communication, and authority state must be represented outside the model. **Hard limits** are enforced by an independent invariant/authority guard; noncritical tradeoffs remain visible to the agent so that it can decide mission strategy itself. The runtime must not turn these context variables into a hidden task planner.

### 1.5.4 Greater onboard autonomy increases, rather than removes, the need for state reconstruction and explanation

More autonomy does not make ground operations irrelevant. It changes the information ground operators need. JPL's *Operations for Autonomous Spacecraft* work identifies two complementary requirements: on uplink, operators must communicate **intent** to onboard autonomy rather than only detailed command sequences; on downlink, operators must reconstruct spacecraft state and understand **what autonomous decisions were made and why**, especially when autonomy has reacted to information unavailable to ground in real time (Castano et al., 2022).

This directly motivates three elements of the proposed system:

1. a structured **authoritative mission state** that is independent of model conversation history;
2. a **trace/evidence record** linking intent, observed state, decision, execution, and verification;
3. natural-language status and mission reports generated **from that structured record**, not treated as the record itself.

### 1.5.5 Architectural implication

The resulting design is therefore a consequence of lunar operations rather than a generic agent pattern with additional variables:

| Lunar operational reality | Mission-level consequence | Architectural response in this work |
|---|---|---|
| seconds-scale Earth delay plus relay/contact interruption | Earth cannot be required inside every decision loop | persistent local mission runtime; asynchronous use of remote intelligence |
| remote reasoning/service may disappear and later return | chat/session continuity is not a safe source of mission truth | authoritative mission state + context reconstruction after reconnection |
| flight compute is power-, radiation-, and fault-constrained | the strongest model cannot be assumed continuously onboard | heterogeneous/distributed reasoning with local continuity |
| illumination, energy, thermal and subsystem state alter activity feasibility | some actions cross hard operating limits while others require contextual tradeoffs | typed space context + thin invariant/authority guard; agent retains strategy |
| failures can occur while ground is delayed or disconnected | immediate safety/recovery cannot depend on Earth or an LLM | local independent safety + FDIR + bounded autonomous authority |
| higher onboard autonomy changes state without continuous ground observation | ground must reconstruct what happened and why | event-sourced state, evidence-linked trace, structured reporting |
| operations move toward communicating intent rather than complete action sequences | autonomy must interpret goals and unexpected semantic situations | LLM/VLM mission reasoning over a closed capability set |

These conditions should not become seven independent research topics. In this paper they are **design constraints and runtime semantics inside the same autonomy problem**, used to ensure that the increased mission envelope demonstrated in H1/H2 is genuinely compatible with lunar operations rather than obtained by assuming terrestrial connectivity, datacenter compute, unconstrained resources, or continuous human supervision.

## 1.6 Research question

> **Can foundation-model reasoning expand the autonomous mission envelope of a lunar robot beyond situations completely encoded in pre-engineered procedures and planning-domain models, and reduce the mission-specific engineering effort required to extend that envelope, while a thin space-native harness preserves authoritative state, hard execution/authority invariants, FDIR, independent verification, low-level safety, and traceability?**

This wording intentionally acknowledges that classical systems already support goal-based planning and replanning. The distinction is **where mission knowledge is pre-engineered**: classical systems encode substantial task/procedure/domain structure, whereas the proposed system pre-engineers capabilities and invariants but leaves mission decomposition and recovery strategy to the agent.

## 1.7 Hypotheses

### H1 — Autonomous mission-envelope expansion

With the same robot embodiment and primitive capabilities, the proposed runtime will complete a broader set of **model-held-out mission situations** without ground re-authoring than PLEXIL and EUROPA-to-PLEXIL baselines whose frozen mission/domain artifacts do not encode those situations.

### H2 — Lower mission-specific knowledge-engineering burden

When a new capability or mission situation is introduced after system freeze, the proposed runtime will require less mission-specific engineering effort to reach validated support while retaining comparable or better held-out mission performance.

### H3 — Open-ended reasoning can remain bounded without becoming rule-driven mission planning

The autonomy gains in H1/H2 should occur while hard physical/authority invariants, authoritative state, FDIR, and effect verification remain independently enforced. The harness should reject or stop actions that cross explicit boundaries, but it should **not** encode scenario-specific task order, observation policy, recovery branches, or mission decompositions. H3 is primarily an architectural requirement and failure-analysis target, not a third large experiment.

## 1.8 Intended contributions

The final paper should support four contributions, with wording narrowed to measured results:

1. **Problem formulation.** Reframe a key bottleneck in future lunar robotic autonomy as the dependence of existing onboard autonomy on pre-engineered procedures/task/domain models, together with the knowledge-engineering cost of extending those models to increasingly open missions.

2. **Agentic operating model for lunar robotics.** Introduce a mission-level agent loop in which an LLM/VLM owns semantic mission interpretation, task decomposition, observation choice, recovery, and capability composition over a closed set of trusted robot capabilities.

3. **Thin space-native harness for trustworthy execution.** Preserve authoritative state, hard authority/execution invariants, structured space-operational context, FDIR/safety separation, independent effect verification, distributed-intelligence reconciliation, and evidence-linked traces **without re-encoding mission solutions in the harness**.

4. **Experimental evidence for autonomy breadth and extensibility.** Compare against PLEXIL and EUROPA-to-PLEXIL using common robot capabilities, ALFUS-grounded autonomy measures, model-covered versus model-held-out situations, and a controlled knowledge-engineering extension study.

The paper should not claim novelty for generic tool calling, a new skill library, generic safety filtering, VLA architecture, temporal scheduling, resource optimization, or natural-language generation by itself.

# 2. Related Work

The related-work section should make the historical progression explicit: classical space autonomy already moved operations from command sequences toward onboard goals, planning, execution, and replanning; the new question is whether foundation models can expand the *semantic and task-model boundary* without abandoning that discipline.

## 2.1 Procedure and plan execution: PLEXIL

PLEXIL was developed by NASA/USRA as a language and executive for representing and executing automation plans. The current Release 6 documentation describes branches, loops, event- and time-driven activities, concurrency, sequencing, temporal constraints, pre/post/invariant conditions, external `Lookup`s, asynchronous `Command`s, and command-resource arbitration. The PLEXIL Executive is intended to connect to external systems through interface adapters.

This makes PLEXIL an appropriate strong procedural/reactive baseline for the present work. A fair comparison must therefore use the official executive, expose the same LunarBot capabilities through an adapter, and author competent recovery branches for all situations declared model-covered. The paper must not reduce PLEXIL to a naive state machine.

**Boundary relevant to this work:** PLEXIL executes plans and libraries that encode the procedural knowledge available to the system. It does not itself infer a new semantic task model from an unmodeled physical situation.

## 2.2 Model-based planning and scheduling: EUROPA, ASPEN/CASPER, MEXEC

EUROPA provides a reusable NASA framework for planning, scheduling, and constraint programming. Its plan database represents actions, states, objects, resources, and constraints; its solver detects and resolves flaws to generate or refine valid plans. ASPEN/CASPER demonstrates iterative-repair planning in which changing goals/state continuously update a working plan. MEXEC integrates task-network planning, scheduling, execution monitoring, temporal/resource reasoning, and replanning, and has been applied to the Mars 2020 On-Board Planner, ASTERIA demonstrations, Europa-related studies, and CADRE.

These systems invalidate any weak claim that "traditional autonomy cannot replan" or "traditional autonomy cannot accept goals." They can.

**Boundary relevant to this work:** their reasoning is grounded in explicit task/domain knowledge engineered before operation. Europa Lander work, for example, constructs hierarchical task networks from domain knowledge and dependency structure. CADRE's strategic-planning work similarly operates over a task network and resource/state models. The system may choose and schedule tasks dynamically, but the space of task semantics is represented beforehand.

## 2.3 The knowledge-engineering bottleneck

The construction and maintenance of planning-domain knowledge is a recognized research problem. JPL's **Efficient Task Network Generation** project states that specifying spacecraft tasks, dependencies, and ordering remains largely manual, cumbersome, challenging to verify, and error-prone; its stated impact is reducing plan-creation time and increasing confidence in spacecraft commanding. Automated-planning research similarly describes domain-model creation as time-consuming and error-prone and evaluates knowledge-engineering tools using task-completion time and model/debugging errors.

Recent work on knowledge engineering in the LLM era is especially relevant: LLMs may reduce acquisition/formulation effort, but explicit validators and human domain expertise remain important in safety-related applications. This directly supports the architecture adopted here: foundation models provide semantic flexibility; independent structured mechanisms retain correctness-critical responsibilities.

This literature motivates **Experiment II**. The paper does not claim a universal cost model for autonomy engineering; it measures concrete time-to-valid-support and artifact changes under a controlled extension protocol.

## 2.4 Autonomy measurement: ALFUS and human–robot interaction

The NIST **Autonomy Levels for Unmanned Systems (ALFUS)** framework characterizes autonomous capability along Mission Complexity, Environmental Complexity, and Human Independence rather than equating autonomy with low human contact alone. For the Human Independence axis, ALFUS explicitly includes:

- ratio of human intervention time to mission time;
- ratio of human planning time to mission time;
- level of human interaction/authority, from assigning a mission through strategic/tactical goals, mission tasks, route, autopilot, and servo-level interaction;
- human workload.

For dynamic planning, ALFUS proposes the degree of mission variation handled and the percentage of a mission performed without preplan.

These measures are unusually well aligned with this paper. The primary autonomy result should therefore be reported as a **vector of interpretable measures**, not a new scalar "autonomy score."

Goodrich/Olsen HRI work on neglect tolerance and robot attention demand provides supporting context for operator-attention burden. NASA-TLX is a well-established subjective workload instrument, but it should only be used if the study includes a proper operator experiment; it is not required for the core paper.

## 2.5 Agent harnesses, foundation-model robotics, and OpenRAL

Coding-agent systems clarify an important architectural distinction. Hermes Agent exposes model-facing tools through a central self-registering registry and dispatch loop while the harness handles prompt assembly, history, recovery, provider switching, and persistent agent state. Pi deliberately keeps the core harness minimal and moves customization into tools, extensions, skills, and prompt templates. Codex similarly treats sandboxing, approvals, constrained execution, thread persistence, tool integration, and telemetry as harness responsibilities while the model chooses how to solve the coding task.

These systems are not robotics baselines, but they motivate the design principle used here: **the harness should bound execution and maintain state; it should not contain the domain solution to each task.**

OpenRAL provides the closest robotic substrate for this pattern. Its reasoner emits typed `ReasonerToolCall`s, its tool palette is constructed from installed capability-compatible rSkills, effectful calls are dispatched through a separate execution path, world state is aggregated outside the LLM, and low-level safety is intentionally independent. The present work therefore extends OpenRAL rather than building another agent loop from scratch.

The research gap is not generic tool use. It is whether this thin-harness pattern can be made compatible with aerospace requirements — delayed/intermittent communication, bounded authority, persistent mission truth, FDIR, independent outcome verification, and evidence-based ground reconstruction — while retaining the model's ability to form task structure online.

## 2.6 Trustworthy autonomy without a handcrafted mission executive

Aerospace autonomy literature correctly emphasizes explicit safety, execution monitoring, verification, and operational authority. The proposed method preserves these properties but narrows what is encoded as deterministic mission logic.

The paper should distinguish four responsibilities:

- **agent strategy:** what to observe, how to decompose the mission, which capability to call next, and how to recover;
- **hard invariant/authority enforcement:** whether a proposed action crosses a predeclared non-negotiable boundary or requires approval;
- **physical safety:** whether the robot/controller can execute the command safely;
- **effect verification:** what physically happened and which facts may enter authoritative state.

Only the latter three are enforced outside the model. The invariant layer must not contain scenario-specific task ordering, recovery trees, or hidden predicates that amount to a second planner. This separation is central to H3 and to the scientific distinction from procedure-/domain-driven autonomy.

## 2.7 Operations interaction and explanation

JPL's "Operations for Autonomy" work identifies intent capture, prediction of autonomous behavior, reconstruction of onboard decisions, and explanation of generated schedules as operational challenges for future autonomous missions. This supports two secondary design choices in the proposed system:

1. operators may provide mission-level natural-language intent rather than manually enumerating every subtask;
2. the system produces a natural-language report **from structured mission state and evidence**, rather than treating free-form model narration as the authoritative record.

Natural-language interaction is therefore an operational benefit demonstrated in mission traces and the real-robot demo, not a standalone novelty claim.

## 2.8 Lunar operating context and distributed intelligence

The space-operational assumptions in this work are grounded in current lunar-communications, flight-computing, and autonomous-operations literature rather than arbitrary stress conditions.

**Communication.** The LunaNet Interoperability Specification defines interoperable lunar networking across Direct-with-Earth and relay services, and the current architecture explicitly anticipates an evolving network of government, international, and commercial providers. DTN is a core networking mechanism because space links may be disconnected, delayed, asymmetric, rate-mismatched, or available only at different times; store-and-forward operation is therefore a normal design principle rather than an exceptional fault mode (NASA/ESA/JAXA, 2025; NASA SCaN, 2026). NASA's communication-delay review further identifies 3–14 s one-way delays as a relevant lunar regime and argues that beyond-LEO missions require increasing independence from continuous real-time ground support (Landon et al., 2025).

**Computing.** HPSC demonstrates the direction of future spaceflight compute: much greater onboard performance, but still under explicit power-management, radiation, fault-tolerance, reliability, and connectivity requirements. This supports increased onboard AI/autonomy while arguing against the assumption that flight computing is equivalent to an unconstrained terrestrial GPU server (NASA HPSC, 2024–2026).

**Environment and resources.** CADRE and uncrewed lunar surface-operations studies show that energy, temperature, illumination, and subsystem state directly influence activity scheduling, sleep/recharge, and survivability. These quantities are therefore operational constraints, not merely descriptive context (Lewis et al., 2022; Rabideau et al., 2025).

**Mission operations.** Increasing onboard autonomy shifts the ground role from continuous low-level commanding toward communicating intent, predicting likely autonomous behavior, reconstructing onboard state, and explaining decisions after execution. JPL's *Operations for Autonomous Spacecraft* work treats these as explicit future mission-operations requirements (Castano et al., 2022).

Together, these sources motivate a runtime in which local mission continuity is mandatory, remote reasoning is opportunistic, operational context is structured and authoritative, and every consequential state transition is reconstructable. However, the paper should still avoid becoming a communications, processor, or resource-optimization study. Only the variables exercised by the selected mission scenarios should enter the first-paper experiments.

## 2.9 Synthesis of the gap

The literature already contains:

**strong plan execution + strong onboard planning/replanning + modern physical-agent orchestration + aerospace safety/FDIR + lunar operational models.**

The unresolved intersection investigated here is:

> **Can a lunar robot pre-engineer only capabilities, hard invariants, authoritative state interfaces, and verification — while allowing a foundation-model agent to form mission strategy online — and thereby handle mission situations not exhaustively encoded into a task/procedure/domain model with lower extension cost?**

This is the paper's research gap. It is deliberately stronger and more precise than "LLM for space robotics" and avoids the false claim that existing space autonomy is merely scripted.

# 3. Problem Setting and Design Requirements

## 3.1 Mission setting

The target is a long-horizon lunar mobile-manipulation mission in which the operator provides a mission objective rather than a complete action procedure.

Representative instruction:

> Inspect the designated lunar service site, identify the condition preventing normal operation, restore the system if the required action is within autonomous authority, verify the result, and leave the robot in an operationally safe condition.

The exact execution sequence is not supplied by the operator. Some mission instances are deliberately within a pre-engineered task model; others require a decomposition or capability composition that is not encoded as a scenario-specific procedure/task network before the run.

## 3.2 Shared capability assumption

All compared systems receive the same closed set of primitive capabilities and the same physical/world observations. Candidate capabilities include:

- localization and mapping;
- navigation/path planning;
- RGB/RGB-D/LiDAR sensing;
- semantic scene query and object localization;
- manipulator planning/control;
- grasp/release and end-effector motion;
- optional learned policies where already available;
- the same raw robot-observable capability results and signals;
- resource/health services;
- FDIR events;
- low-level runtime safety;
- operator communication.

No baseline receives an easier robot, better perception, or stronger manipulation stack. The independent variable is the **complete mission-level operating system** above this substrate: for Ours, the agent together with its harness.

**Method boundary (revised 2026-09-17).** Fairness means the same problem and the same robot, not giving the baselines
the proposed method's mechanisms. Shared by all methods: robot embodiment, sensors, primitive physical capabilities
behind one typed capability contract, perception sources/services, environment, mission objective, initial state, the
same raw robot-observable capability results and signals, low-level hardware safety (joint/actuator limits, emergency
stop, collision-critical kernel), and the **external experiment evaluator** (mission success, fault cleared, docked,
object at the target; it also counts constraint violations for every method). Method-specific: how the raw evidence is
interpreted and acted on. Ours' authoritative mission facts, dynamic context reconstruction, thin invariant/authority
guard, internal effect verification and evidence-linked traces are parts of the proposed method; PLEXIL and
EUROPA→PLEXIL use their own plan/domain, execution and recovery semantics, and encode mission/authority constraints in
their own artifacts. The contribution of each Ours component is established by Ours-internal ablations (§5.7), not by
copying components into the baselines.

## 3.3 Model-covered versus model-held-out mission situations

This distinction is central to the paper and must be defined before experiments.

### Model-covered

A mission situation is model-covered for a baseline when the baseline's frozen artifacts explicitly contain the task/procedure/domain knowledge needed to form a valid solution. Examples include a PLEXIL recovery branch, an EUROPA action/state/constraint model, or a predefined task-network expansion that represents the required response.

### Model-held-out

A mission situation is model-held-out when:

1. every primitive capability needed for a valid solution already exists and is available to all methods;
2. the physical state is observable with the shared sensor/perception stack;
3. the required **mission-level decomposition, semantic interpretation, or capability composition** is not encoded as a scenario-specific solution in the frozen PLEXIL plan library or EUROPA domain/task artifacts;
4. the proposed method is not given a hidden hard-coded solution either — it receives only generic mission instructions, typed capability descriptions, current evidence, and frozen hard invariant/authority configuration;
5. no method-specific artifact is modified after the held-out scenario is revealed during an autonomous run.

Examples should involve semantic/task-structure novelty rather than merely numeric variation that a model-based planner already handles well. A suitable example is discovering that access to a failed component is blocked by another movable object, requiring the system to inspect, diagnose the obstruction, relocate it, re-access the target, perform the repair, and verify the result even though that decomposition was not pre-authored.

## 3.4 Five non-negotiable design requirements derived from lunar operations

The requirements below are not generic software preferences. They follow from the operational constraints summarized in §1.5 and §2.8 and from the agent-harness distinction in §2.5–2.6.

### 3.4.1 Agent-owned mission strategy over a closed physical capability set

The foundation-model agent owns mission-level decomposition, ordering, information gathering, substitution, and recovery. It may revise these online as evidence changes. Physical action remains limited to a closed typed capability set. This broadens **task-level semantic reasoning** without broadening raw motor authority.

The harness must not contain a parallel scenario-specific task graph for the proposed method. If a held-out solution is recoverable only because the harness already encodes its task sequence or recovery relation, that case is invalid evidence for H1.

### 3.4.2 Semantic observation, not only symbolic predicates

The system must be able to ask a VLM/semantic perception service what is present, what appears abnormal, or what additional observation may be useful when the situation has not been fully enumerated into a symbolic predicate set. Deterministic geometry/state should still be used wherever available. The VLM expands what can be *interpreted* but does not replace deterministic telemetry or verification where those sources exist.

### 3.4.3 Space-native operational context and distributed intelligence

Communication, compute, resource, health, and relevant lunar environmental conditions must enter the agent context as structured runtime facts rather than prompt folklore. The system must remain capable of mission continuation with Earth unavailable while allowing stronger remote reasoning to be used when reachable.

The implementation should distinguish at least:

- **onboard/local:** continuity-critical state, capability execution, safety/FDIR, verification interfaces, and sufficient reasoning for continued operation;
- **optional surface/nearby edge service:** stronger reasoning if the selected mission architecture explicitly provides such compute;
- **Earth/ground:** high-capability reasoning and human expertise when communication permits.

No generic orbital-compute tier is assumed merely because a relay exists.

### 3.4.4 Pre-engineer invariants, not mission solutions

The deterministic guard around the agent must be intentionally thin. It may enforce only explicit, auditable boundaries such as:

- capability/tool existence and typed argument validity;
- hard autonomous-authority limits and approval requirements;
- hard service/capability unavailability;
- critical FDIR states that prohibit an operation;
- physical safety constraints enforced by the robot safety layer;
- hard resource/health limits whose violation is explicitly disallowed by mission policy;
- evidence requirements for accepting a physical effect into authoritative state.

It must **not** encode whether inspection should precede manipulation, which object should be moved first, which recovery sequence should be attempted, which capability ordering is mission-optimal, or whether an additional observation is strategically useful. Those are agent decisions.

### 3.4.5 Reconstructable mission truth separated from agent working plans

Mission continuity must survive model restart, context loss, endpoint switching, and communication interruption. A structured state/evidence record, not chat history, is the authoritative source for physical and operational facts.

The agent may maintain a mutable working task ledger or plan, including OpenRAL's existing `MissionState`/decomposition mechanisms, but that working plan is **not mission truth**. It may be rewritten whenever new evidence arrives. Authoritative state contains mission intent, verified effects, active execution, capability/FDIR/resource facts, authority state, and evidence references; it does not turn the agent's current decomposition into a fixed procedure.

# 4. Proposed Method: Space Robotics Agent Harness

The proposed method is a **thin mission-agent harness built on OpenRAL**. It is not a new foundation model, navigation algorithm, manipulator controller, temporal scheduler, or handcrafted mission planner.

Its central design rule is:

> **Pre-engineer invariants, not mission solutions.**

## 4.1 Architectural principle

The method combines a model-owned mission strategy with a small set of independently enforced execution semantics:

```text
Mission Control / Mission-Level Intent
                 |
                 v
      evidence-grounded context
                 |
                 v
         LLM/VLM Mission Agent
   (decompose / observe / choose / recover)
                 |
                 v
        typed capability/tool call
                 |
                 v
============================================================
             SPACE ROBOTICS AGENT HARNESS
------------------------------------------------------------
 authoritative mission facts + evidence history
 dynamic context construction
 typed capability registry + availability
 THIN invariant / authority guard
 space-operational context
 FDIR / capability degradation state
 distributed-reasoner reconciliation
 independent effect verification
 structured trace + report evidence
============================================================
                 |
                 v
       OpenRAL rSkill execution
                 |
                 v
      independent low-level safety
                 |
                 v
 Physical Robot + Lunar Environment
                 |
                 v
      observations / verified effects
                 +---------------------> next agent step
```

The foundation model supplies mission strategy. The harness supplies **bounded execution, persistent truth, and evidence**. There is no second handcrafted planner between them.

## 4.2 The agent owns mission strategy

The LLM/VLM agent is responsible for the mission-level choices that classical approaches usually encode in procedures or domain models:

1. interpret mission-level natural-language intent;
2. form and revise task decomposition;
3. choose which observation or semantic query is useful next;
4. interpret semantic observations and diagnose unexpected situations;
5. select, order, substitute, and compose registered capabilities;
6. decide recovery strategy after execution failure or changed evidence;
7. decide when clarification or escalation is semantically warranted;
8. generate operator-facing explanations and reports from structured evidence.

The harness does not duplicate these choices with `if mission_state == ... then action ...` logic.

The agent may not issue raw joint/base commands, create unregistered physical capabilities, falsify authoritative facts, override hard authority/safety boundaries, or declare an unverified physical effect as fact.

## 4.3 VLM and semantic observation

The VLM is used where a fixed detector/predicate interface is insufficient for semantic scene understanding. Example queries include:

- which of several infrastructure components appears abnormal;
- whether a component is visually obstructed or inaccessible;
- what region/component should be inspected more closely;
- whether an observed configuration appears inconsistent with a named expected configuration.

A VLM answer is an observation available to the agent, not automatically authoritative truth. Where simulator truth, geometry, controller result, or deterministic telemetry can establish a condition, the verifier should prefer those sources.

## 4.4 Authoritative mission facts versus agent working state

The runtime deliberately separates two kinds of state.

### Authoritative mission facts

These survive model changes and are updated only by typed events/evidence:

- original mission intent and operator-imposed hard constraints;
- verified physical/world effects relevant to the mission;
- active execution reference and tool result;
- unresolved factual anomalies or unknowns;
- hard authority/approval state;
- resource/health/FDIR facts relevant to current operation;
- capability/service availability and degradation;
- stale/unknown data markers;
- evidence references and timestamps;
- current reasoning endpoint/reconciliation status.

### Agent working state

The agent may maintain a current objective, tentative decomposition, todo/task ledger, hypotheses, and preferred recovery strategy. This state is useful for continuity and can be persisted, but it is **advisory and revisable**. It is not allowed to promote an unverified claim into mission truth.

OpenRAL's existing `MissionState` and `decompose_mission` mechanism can be used for this working task ledger. The research runtime should not convert it into a manually authored fixed task graph.

## 4.5 Dynamic context construction

At each deliberative step, the harness assembles a compact context from authoritative facts, the current agent working state, and the relevant tool palette. It should include only information useful for the next decision:

- mission intent and current working objective;
- verified progress/effects;
- current robot/world state;
- relevant semantic observations;
- available/degraded capabilities and their schemas;
- active FDIR/health state;
- communication/compute/resource facts;
- hard authority/approval boundaries;
- recent execution evidence/failures;
- unresolved questions/hypotheses.

The context builder **selects and formats facts; it does not choose the next mission action**. The same context can be reconstructed for another reasoning endpoint after disconnection or restart.

## 4.6 Capability registry as the robot analogue of an agent tool registry

The reasoner sees a closed, typed capability registry. Each capability should expose the minimum generic information needed for model-directed use:

- identifier and semantic description;
- typed arguments;
- typed result/error schema;
- current availability/degradation;
- intrinsic execution dependencies;
- authority class where intrinsically required;
- evidence/result interface;
- execution endpoint.

Capability metadata must remain **mission-agnostic**. It may say that a capability requires a reachable remote service or that an arm action is unavailable under a declared fault; it must not say “use this capability after inspecting panel A” or encode held-out task order. The reasoner may dynamically choose ordering, observations, alternatives, and recovery composition but may not synthesize an unregistered motor primitive.

## 4.7 Thin invariant and authority guard

Before an effectful tool call is dispatched, a thin guard checks only explicit execution boundaries. Its job is analogous to a coding-agent sandbox/approval layer, not a mission planner.

The guard may evaluate:

- whether the capability exists and arguments satisfy the typed contract;
- whether the capability is currently hard-unavailable or degraded beyond use;
- whether the action exceeds the robot's current autonomous authority or requires human approval;
- whether an active FDIR state explicitly prohibits the operation;
- whether a hard resource/health limit explicitly forbids the operation;
- whether required safety-critical input is too stale to legally execute the capability;
- whether the call must pass to the independent low-level safety layer.

The guard returns a minimal outcome such as **allow**, **deny**, **approval-required**, or **unavailable**, with a structured reason that becomes new agent context.

The guard must not determine:

- whether the proposal is the best next mission step;
- whether the agent should inspect first;
- whether another capability would be strategically preferable;
- how to recover from a tool failure;
- which task decomposition is correct;
- whether a scenario-specific procedure has been followed.

Those decisions belong to the agent. Guard rules are generic, auditable, and frozen before held-out evaluation.

## 4.8 Space-operational context: facts for reasoning, invariants only where necessary

The space-context service represents only variables that can change capability availability, hard execution limits, or mission strategy. It is intentionally not a complete lunar digital twin.

The runtime can represent:

- current/upcoming Direct-with-Earth or relay communication availability;
- reachable reasoning/external-service tiers and measured/request latency;
- energy/resource state relevant to current activities;
- subsystem health and capability degradation;
- mission-relevant illumination/thermal/environment state where exercised;
- authority mode and any condition-dependent hard autonomy limits.

These values are typed runtime facts. **Most are presented to the agent for contextual reasoning rather than converted into handcrafted mission rules.** For example, a moderate battery level may influence the agent's choice of activity, while only a documented critical limit would be enforced as a hard invariant. A remote service disappearing simply changes tool availability; the agent decides how to continue.

For the first paper, the selected mission should exercise a small, defensible subset. Communication/contact profiles should be based on documented LunaNet/LCRNS assumptions or trusted tools such as SPICE; resource/thermal models should be transparent and traceable to stated assumptions.

## 4.9 Distributed intelligence and reconciliation

The architecture treats intelligence as heterogeneous and intermittently reachable rather than assigning all reasoning permanently to Earth or to the robot.

- **Onboard/local:** retains authoritative mission facts, execution access, safety/FDIR, verification interfaces, and sufficient reasoning for continuity.
- **Optional surface/nearby compute:** may host stronger reasoning/perception if the selected architecture provides it.
- **Earth/ground:** may host the most capable models and human experts, but is not assumed synchronously available.

A relay is not assumed to be a general-purpose compute node. Compute placement is represented explicitly as service capability/availability.

When the active reasoning endpoint changes, the new endpoint receives reconstructed context from authoritative facts, current verified world state, current space context, unresolved anomalies/FDIR state, available capabilities, and recent evidence. Old chat history is never the authoritative resume mechanism.

## 4.10 Independent execution and effect verification

The execution path separates four responsibilities:

1. **agent:** chooses the next mission action/information step;
2. **invariant/authority guard:** checks only non-negotiable execution boundaries;
3. **capability + low-level safety:** executes under specialized control;
4. **verifier:** establishes the physical effect/fact that actually resulted.

Evidence sources may include deterministic simulator truth, geometric conditions, action results, world-state updates, perception/VLM observations, task-progress monitors, FDIR state, or explicit human confirmation where policy requires it.

Verification should answer questions such as “did the object move?”, “did the robot reach the region?”, “is the component mounted?”, or “did the capability fail?”. It should not encode the hidden mission strategy by checking whether the agent followed a predetermined action sequence.

The model's statement “task succeeded” is never sufficient by itself.

## 4.11 FDIR integration

FDIR changes authoritative facts and capability availability. A critical FDIR state may hard-block a class of actions; otherwise the fault/degradation information is exposed to the agent, which decides how to adapt the mission. The harness does not contain mission-specific fault-recovery trees and does not replace subsystem diagnosis or safety algorithms.

## 4.12 Natural-language commanding and reporting

The operator-facing interface accepts mission-level intent in natural language and returns concise mission status/reporting derived from structured state. This follows the operations shift identified in JPL's *Operations for Autonomous Spacecraft*: higher onboard autonomy requires ground teams to express intent and later reconstruct autonomous decisions and resulting spacecraft state.

Reports summarize what objective was assigned, what was observed, what actions were executed, what effects were independently verified, what remains unresolved, which actions were denied/required approval, and relevant evidence references.

Natural language is not the authoritative record. Reports must be regenerable from structured mission facts/evidence; if prose and evidence disagree, evidence wins.

## 4.13 Traceability and behavioral explainability

Every consequential transition should be reconstructable as:

**mission intent → authoritative facts/context → model tool proposal → guard outcome → capability call → safety/execution result → verification evidence → updated facts → next agent decision.**

This trace provides **behavioral/evidence-level explainability** without requiring a handcrafted task graph or exposure of private chain-of-thought. Ground can reconstruct what the robot knew, what the agent attempted, which hard boundary affected execution, what physically happened, and why the authoritative state changed. It supports post-contact mission reconstruction, anomaly investigation, experiment scoring, and future V&V workflows.

# 5. Experimental Methodology

The experimental section should be intentionally small. The paper asks two scientific questions and runs two main experiments. Communication, resources, FDIR, and semantic anomalies appear *inside* these missions as controlled conditions; they are not expanded into separate campaigns unless later evidence shows a distinct scientific question.

## 5.1 Claim-to-evidence map

| Scientific claim | Primary evidence |
|---|---|
| The proposed system expands autonomous mission capability beyond fully pre-engineered task models. | Experiment I: model-covered vs. model-held-out missions, compared with PLEXIL and EUROPA-to-PLEXIL. |
| The increased autonomy reduces dependence on detailed ground planning/commanding. | ALFUS-grounded Human Independence measures in Experiment I. |
| The system is more extensible and requires less mission-specific knowledge engineering. | Experiment II: controlled post-freeze capability/mission extension. |
| Open-ended FM reasoning does not replace trusted execution semantics. | Common low-level safety and external evaluator; constraint violations and false success/effect declarations counted for all methods; structured traces; Ours-internal ablations of the harness components (§5.7). |
| The architecture transfers beyond simulation. | LunarBot integrated demonstration; not a third scientific experiment. |

## 5.2 Compared methods

The main paper should contain **three methods only**.

### Baseline 1 — PLEXIL

Use the official PLEXIL Release 6 executive and language, not a reimplementation. A LunarBot PLEXIL interface adapter exposes the same capabilities used by all methods as PLEXIL `Command`s and exposes relevant state/verifier signals as `Lookup`s.

For model-covered scenarios, the PLEXIL plan must include competent nominal logic and reasonable predefined recovery branches. It may use PLEXIL conditions, sequences, concurrency, loops, library calls, and resource arbitration as appropriate. Engineering effort and plan artifacts are retained for Experiment II analysis.

### Baseline 2 — EUROPA → PLEXIL

Use NASA's open-source EUROPA framework as the planner/scheduler and official PLEXIL as the executor. This is **our integration of two NASA open-source components**, not a claim that NASA distributes a single official "EUROPA+PLEXIL" product.

EUROPA receives a frozen declarative domain model containing the actions, states, resources, and constraints available to the baseline. Its solver constructs/refines the activity plan. A documented bridge translates the resulting executable activity tokens into PLEXIL-executable activity invocations while state/execution feedback returns through the common adapter.

The baseline must be allowed to replan within its encoded model. It must not be artificially restricted to a one-shot schedule.

### Proposed — Space Robotics Agent Harness

Use the same LunarBot capabilities, perception sources, raw robot-observable evidence, low-level safety and external evaluator as the baselines. Mission decomposition, observation choice, recovery, and capability composition are formed online by the LLM/VLM agent. Outside the model, as parts of the proposed method, remain authoritative facts, dynamic context reconstruction, the thin invariant/authority guard, internal effect verification, and evidence-linked traces — not a second mission planner. Execution runs through the shared OpenRAL rSkills and low-level safety.

### Not main baselines

Generic OpenRAL and prompt-only variants remain useful during development and possibly as a single targeted ablation, but they should not occupy space in the main comparison unless required to explain a specific mechanism. A separate handcrafted behavior-tree baseline is unnecessary once PLEXIL is present.

## 5.3 Fairness and freeze protocol

The comparison is only valid if the following rules are enforced:

1. **Same embodiment and primitive capabilities.** Navigation, perception, manipulation, VLM service, FDIR primitives/signals, raw capability results, and low-level safety are shared. Method mechanisms (Ours' facts, context, guard, internal verification, traces; the baselines' plans/domains and execution semantics) are not.
2. **Same physical scenario.** Methods run the same simulator state/seed and mission objective.
3. **Same available evidence.** No method receives privileged simulator truth for reasoning; deterministic truth is used only by the external experiment evaluator, which scores all methods with the same criteria, including constraint violations.
4. **Strong baseline authoring.** PLEXIL/EUROPA artifacts are authored using their documented strengths and validated on model-covered development cases.
5. **Artifact freeze.** Before the campaign, PLEXIL plans/libraries, EUROPA domain/solver configuration, proposed generic prompts/playbooks, capability descriptions, hard invariant/authority configuration, and all shared capabilities are frozen.
6. **No hidden solution in Ours.** Capability descriptions, prompts/playbooks, guard rules, verifier logic, and state schemas must be mission-generic and cannot encode the held-out task sequence, scenario-specific recovery graph, or required action ordering.
7. **No online code/model editing during autonomous runs.** If continuing a mission would require editing a PLEXIL plan, EUROPA domain/task model, or proposed runtime code, that autonomous run is recorded as requiring ground re-authoring.
8. **Equivalent mission intent.** Ours may receive natural-language mission intent; baselines receive the semantically equivalent formal mission goal required by their execution model. The difference in operator command abstraction is recorded rather than disguised.

## 5.4 Mission families

Use two coherent mission families inside Experiment I, not as separate papers or independent experiments.

### Mission A — Infrastructure inspection and maintenance

Representative objective:

> Inspect the designated service site, identify the failed or obstructed subsystem, restore operation if permitted, verify the result, and leave the robot in a safe state.

The environment should contain multiple visually distinguishable components and at least one semantic state that must be identified through observation. The mission can require navigation, inspection, diagnosis, manipulation, and verification.

### Mission B — Logistics and servicing

Representative objective:

> Deliver the required component or tool to the service location and complete the servicing objective while respecting current mission constraints.

The environment can require item identification, retrieval, transport, placement/service, and verification.

The two families are sufficient if they exercise different task compositions. A third family should be added only if it tests a qualitatively different mechanism.

## 5.5 Experiment I — Autonomous Mission Generalization

### Question

**Can the system autonomously complete mission situations beyond the task/procedure/domain model that was engineered before deployment?**

### Independent variable

Mission-model coverage:

- **Covered:** required task/decomposition is representable by the frozen PLEXIL/EUROPA artifacts.
- **Held-out:** all required primitive capabilities exist, but the scenario-specific semantic diagnosis/decomposition/composition was not encoded in those artifacts.

### Held-out situation design

Held-out cases should be few but substantive. Candidate categories:

1. **semantic obstruction/access problem:** a target is physically present but cannot be serviced until another observed condition is understood and resolved;
2. **unexpected component state requiring additional inspection:** the visible state does not match the nominal task template and the system must gather evidence before choosing an action;
3. **capability substitution/composition:** the preferred route or operation is unavailable, but a valid solution exists through a different combination of already registered capabilities.

The final paper does not need all three categories if two produce a sufficiently clear and repeatable test.

### Human-assistance protocol

The autonomous run begins with the standardized mission input and no operator assistance. Human interaction is event-triggered, not time-threshold-triggered. Assistance is recorded when the system explicitly requests operator input/escalation, reaches a state in which it reports no admissible continuation, or the mission terminates under a declared mission deadline/constraint.

During the autonomous run the operator may only use the common operational interface; source code/domain/plan artifacts remain frozen. A need to author/upload new mission logic is recorded as **ground re-authoring required**, not silently folded into normal intervention.

### Primary metrics

The study should report the following separately rather than combine them into a scalar score:

1. **Autonomous Mission Success Rate** — fraction of runs satisfying all required final mission conditions without post-reveal method-specific artifact modification.
2. **Human Intervention Ratio (ALFUS)** — total operator–system interaction time divided by mission elapsed time.
3. **Human Planning / Preplanning Burden (ALFUS-grounded)** — record the human mission-specific planning time and the fraction of required mission transitions whose scenario-specific structure was pre-authored. ALFUS explicitly treats human planning time and the portion of the mission pre-generated by humans as Human-Independence factors; report the raw quantities and any ratio used, rather than inventing a synthetic autonomy score. Offline plan/domain authoring effort is measured separately in Experiment II.
4. **Level of Human Interaction (ALFUS)** — highest/typical authority level of operator input, using the ALFUS ordering: mission → strategic goal → tactical goal → mission task → route → autopilot → servo.
5. **Mission Variation Coverage / Held-out Success** — success rate over held-out situation classes, directly operationalizing ALFUS's "degree of mission variations handled" concept.
6. **Invariant-/Authority-Violating Proposal and Execution Rate** — proposals that cross explicit frozen hard boundaries, and the subset (ideally zero) that actually execute despite those boundaries. This metric must not classify an unconventional but valid task strategy as “invalid” merely because it differs from a pre-authored sequence.

Mission duration and low-level skill success should be reported as supporting diagnostics, not headline autonomy metrics.

### Expected evidential interpretation

If PLEXIL and EUROPA perform strongly on covered cases but degrade when the required semantic/task structure is absent from frozen artifacts, while Ours maintains higher autonomous success with lower human-planning/intervention burden, H1 is supported. If EUROPA solves a held-out case within its existing domain model, that is a valid success for the baseline and the case should not be described as beyond model-based autonomy.

## 5.6 Experiment II — Autonomy Extensibility / Knowledge-Engineering Cost

### Question

**How much mission-specific engineering is required to expand the autonomous mission envelope after deployment requirements change?**

### Protocol

1. Freeze the three systems at the end of Experiment I development.
2. Reveal a new extension specification to all methods at the same time.
3. The shared low-level implementation of the new capability, if one is involved, is supplied identically to all methods; the measured work begins at the point where each mission-level system must learn/represent how that capability can be used.
4. Engineers modify only method-specific mission artifacts until a predefined validation suite passes.
5. Freeze again.
6. Evaluate on held-out mission instances that require the extension but were not visible during authoring.

Use a small number of high-quality extension cases. Suitable examples are:

- adding a new general-purpose inspection/manipulation capability with typed inputs/results;
- adding support for a newly specified mission situation that requires a new task relationship but no new low-level controller.

### Primary metrics

1. **Engineering Time-to-Valid-Support** — active engineering time from release of the extension specification until the method passes the common validation suite. Time-on-task is a standard dependent variable in knowledge-engineering tool evaluations; it is reported directly, not converted to a synthetic cost score.
2. **Mission-Specific Artifact Change** — descriptive delta in the artifacts that encode mission knowledge: PLEXIL plans/libraries/conditions, EUROPA NDDL/domain/solver artifacts, or proposed capability metadata/policy/runtime configuration. Report semantic constructs/files and optionally line deltas, but do not compare raw LOC as if languages were equivalent.
3. **Validation/Modeling Error Count** — number of failed validation iterations attributable to incorrect/incomplete mission modeling, when reliably observable.
4. **Post-Extension Held-out Mission Success** — autonomous mission success on unseen instances requiring the extension.

If only one engineer performs all authoring, engineering-time results should be treated as controlled case-study evidence rather than a population-level human-factors claim. If multiple qualified engineers are available, authoring order should be counterbalanced and inter-engineer variation reported.

### Expected evidential interpretation

H2 is supported if Ours reaches valid extension support with substantially less mission-specific artifact engineering while retaining successful held-out execution. For a new capability, the strongest result is that Ours primarily adds/updates a generic capability contract or hard dependency metadata rather than a central mission-specific rule or workflow. A result in which Ours requires less authoring but produces unreliable execution does not support the hypothesis.

## 5.7 Targeted trustworthiness ablation / failure analysis

Do not create a third large ablation campaign. Because Experiment I compares complete systems, the contribution of the harness components is shown by focused Ours-internal ablations on a subset of Experiment I cases:

- **Full Ours** versus Ours without **authoritative facts** (the agent's own claims advance state), without **internal effect verification** (skill success flags are trusted), without the **thin invariant/authority guard**, and without **dynamic context reconstruction** (plain accumulated history).

The purpose is to show that semantic flexibility alone is not the paper's contribution. Relevant outcomes are mission success, hard-boundary violations, unsupported authoritative-state advancement, stale/duplicate execution, false effect/success declarations, and recovered failures. The ablations must not introduce or remove mission-specific task knowledge.

## 5.8 Real LunarBot demonstration

A later hardware demonstration should execute one representative mission segment with the same mission-runtime abstraction, typed capability interfaces, safety path, harness (including its internal effect verification), and natural-language mission/reporting interface.

Its purpose is deployment feasibility and transfer, not another baseline campaign. Detailed design is intentionally deferred until the simulation experiments and real LunarBot capability stack are stable.

## 5.9 Statistical principles

- use the same scenario seeds/initial states across methods wherever possible;
- repeat stochastic foundation-model runs sufficiently to characterize variance;
- retain raw per-run traces and classify failure modes;
- report confidence intervals for success and ratio metrics;
- use paired analyses where the same scenario instance is evaluated by multiple methods;
- do not choose sample counts or final hypothesis tests solely to obtain significance;
- freeze metric definitions and exclusion rules before the final campaign.

No single scalar autonomy score should be created.

# 6. Planned Results and Evidence Structure

No numerical result is assumed. This section defines what the eventual paper must show for each claim to be defensible.

## 6.1 Main result — autonomous mission envelope

The central figure/table should compare **PLEXIL, EUROPA→PLEXIL, and Ours** under model-covered and model-held-out situations across the two mission families.

The table should include at minimum:

- autonomous mission success;
- human intervention ratio;
- human interaction authority level;
- held-out mission success/variation coverage;
- hard-invariant/authority violations and blocked proposals.

The strongest valid result would not be "Ours wins everywhere." A scientifically plausible and useful pattern is:

- PLEXIL is highly reliable when the needed procedure/recovery branch is encoded;
- EUROPA→PLEXIL handles dynamic scheduling/replanning well inside its domain model;
- Ours matches these methods reasonably on covered cases and degrades less when the required semantic/task structure is outside the frozen model;
- increased flexibility does not produce hard-boundary violations or unsupported state advancement because guard/safety/verification remain independent, despite the absence of a handcrafted mission procedure in Ours.

## 6.2 Second result — cost of expanding autonomy

The second main table should compare extension cases using:

- engineering time-to-valid-support;
- mission-specific artifacts changed;
- validation/modeling errors where measurable;
- held-out mission success after extension.

The important interpretation is not that symbolic planning is obsolete. It is whether the foundation-model runtime reduces the amount of mission-specific knowledge engineering needed to make an existing capability useful in a new operational context.

## 6.3 Mission trace figure

Include one complete trace from a held-out situation showing:

**mission intent → semantic observation → agent diagnosis/decomposition → capability call → invariant/authority guard → physical execution → effect verification → authoritative-fact update → next agent decision → final operator report.**

A companion trace from a classical baseline should show where the frozen model ceases to provide a continuation or requires ground re-authoring.

## 6.4 Trustworthiness evidence

The paper should show that the proposed method's success is not achieved by relaxing mission constraints. Suitable evidence includes:

- no increase in low-level safety violations;
- zero or acceptably bounded execution across explicit hard invariants/authority limits;
- examples of agent proposals blocked only by a frozen hard boundary or approval requirement, not by a hidden task rule;
- verification-backed rather than model-asserted completion;
- deterministic reconstruction of the mission trace from event logs.

## 6.5 Real-system evidence

A short LunarBot section should show:

- the same mission/runtime interface controlling real hardware;
- real sensor/ROS feedback entering the authoritative state;
- at least one reasoner-driven multi-step sequence;
- independent verification of a physical outcome;
- a trace-linked natural-language report.

No claim about lunar-environment fidelity should be made from the ground demo.

## 6.6 Figures and tables expected in the manuscript

**Figures**

1. Procedure/model-driven autonomy versus agentic mission-runtime operating model.
2. Proposed architecture and trust boundaries.
3. Experiment-I coverage design: model-covered versus model-held-out situations.
4. Main autonomy/generalization results.
5. Representative held-out mission trace.
6. Experiment-II engineering-effort/extension result.
7. LunarBot demonstration image/trace if included.

**Tables**

1. Related-system capability boundary: PLEXIL / EUROPA / CASPER-MEXEC / physical-agent harnesses / Ours.
2. Shared LunarBot capability stack and baseline interfaces.
3. Mission scenarios and which knowledge is covered versus held out.
4. Primary Experiment-I metrics.
5. Experiment-II extension effort and post-extension performance.
6. Failure-mode/trustworthiness summary.

# 7. Discussion

## 7.1 The intended operating-model transition

The paper should return to one central shift:

> **from autonomous execution/planning inside a predominantly pre-engineered mission model, toward a system that can also interpret semantically novel mission situations and compose existing trusted capabilities online.**

This is a progression within the space-autonomy tradition, not a rejection of it.

## 7.2 What classical space autonomy continues to do better

PLEXIL/EUROPA/MEXEC-style systems provide explicit, inspectable task/state/resource semantics, deterministic or bounded execution behavior, and strong verification/V&V properties. Where the operational domain can be comprehensively modeled in advance, these properties are major strengths.

The proposed work should therefore avoid the claim that foundation models are universally superior planners. Its advantage is expected specifically where mission semantics, diagnosis, or task composition cannot be exhaustively enumerated at acceptable engineering cost.

## 7.3 What foundation models contribute

The experimental results should support only those capabilities actually observed, but the intended advantages are:

- broader semantic interpretation of mission situations;
- dynamic task decomposition using an existing capability repertoire;
- lower marginal effort to make newly available capabilities operationally useful;
- mission-level natural-language commanding;
- natural-language explanation/reporting grounded in structured evidence.

## 7.4 Why the runtime remains space-native

The architecture should behave differently from a generic terrestrial agent when communication, compute, resources, mission authority, or FDIR state change. These variables enter structured runtime state; only explicit hard boundaries are enforced deterministically, while the model remains responsible for mission strategy. Space-native trustworthiness therefore comes from bounded execution and persistent truth, not from reintroducing a handcrafted mission executive.

Only context exercised by the final scenarios should appear as a major manuscript claim.

## 7.5 Engineering scalability

If Experiment II supports H2, the discussion should distinguish **runtime generalization** from **development-time extensibility**:

- runtime generalization asks whether a frozen system handles a new situation;
- extensibility asks how much engineering is needed to deliberately expand the supported mission envelope.

These are related but distinct properties, and conflating them would weaken the paper.

## 7.6 Human–autonomy interaction

The desired operational effect is not "remove humans." It is to shift operator effort upward in abstraction:

**servo/route/task-level intervention → mission/goal-level intent + exception handling.**

ALFUS Human Independence metrics provide a defensible way to describe this change. Natural-language mission input/reporting supports this shift but should not be used to claim reduced workload without a proper human-subject study.

## 7.7 Moon-to-Mars extrapolation

Mars should remain an extrapolation. Longer delay and disconnection strengthen the motivation for onboard mission-level autonomy, but the experiments validate lunar scenarios only.

## 7.8 Limitations

The final manuscript should explicitly discuss:

- held-out cases are designed within a closed capability set and therefore do not constitute unrestricted open-world intelligence;
- success still depends on perception quality and the completeness/correctness of genuinely hard safety, authority, and verification interfaces;
- foundation-model outputs remain stochastic and model-dependent;
- engineering-time measurements can be developer-dependent, especially with a small authoring sample;
- simulation does not reproduce all lunar physical/environmental effects;
- the EUROPA→PLEXIL baseline is an integration built for this study from official open-source components, not an official NASA product distribution;
- real LunarBot validation demonstrates interface/runtime transfer, not lunar environmental fidelity;
- multi-robot autonomy and full certification remain outside the first paper.

# 8. Conclusion — intended message

The final conclusion should be narrower than the vision statement and exactly match measured evidence.

Intended form:

> Classical space autonomy has already shown that onboard planning, scheduling, execution monitoring, and replanning can reduce dependence on detailed ground command sequences. The next limitation for increasingly open lunar robotic operations is the engineering boundary of the task/procedure/domain models in which that autonomy operates. This work investigates a Space Robotics Agent Harness that lets a foundation-model agent own mission strategy while pre-engineering only typed capabilities, authoritative mission facts, hard authority/execution invariants, FDIR, independent effect verification, low-level safety, and evidence traces. If supported by the experiments, the principal result is that this operating model expands the set of mission situations a lunar robot can handle without ground re-authoring and reduces the effort required to extend that set without reverting to a handcrafted mission executive.

# Research boundaries that must not drift

This work is **not**:

- another skill-library or skill-registration paper;
- a renamed version of the previous SELENE Atomic Action Contract work;
- a generic LLM tool-calling framework;
- a new VLA architecture;
- a claim that classical space autonomy cannot plan or replan;
- a generic runtime-safety filter or a handcrafted mission rule engine;
- a communication-planning paper;
- a power/thermal optimization paper;
- a cloud-edge deployment paper;
- a human-factors paper unless a properly designed operator study is later added;
- a paper whose main novelty is natural-language reporting.

The scientific center is:

> **expanding the autonomous mission envelope beyond fully pre-engineered task models by letting the foundation-model agent own mission strategy, while a thin space-native harness pre-engineers only capabilities, hard invariants, authoritative truth, execution, and verification.**

---

# Literature anchors for the future manuscript

The final manuscript should use peer-reviewed papers where available and official NASA/NIST technical material for implementation/system facts. The list below is intentionally more specific than the previous version so that future writing does not rely on memory.

## Autonomy measurement and human interaction

1. **Huang, H.-M., Messina, E., and Albus, J.** *Autonomy Levels for Unmanned Systems (ALFUS) Framework, Volume II: Framework Models, Version 1.0.* NIST Special Publication 1011-II-1.0, 2007. DOI: `10.6028/NIST.SP.1011-II-1.0`. Key use: Mission Complexity / Environmental Complexity / Human Independence framing; human intervention ratio; human planning ratio; level of human interaction; dynamic-planning variation coverage.
2. **Huang, H.-M.** *Autonomy Levels for Unmanned Systems (ALFUS) Framework, Volume I: Terminology.* NIST SP 1011-I-2.0. Key use: terminology for autonomy and human independence.
3. **Goodrich, M. A. and Olsen, D. R. Jr.** *Metrics for Evaluating Human-Robot Interactions.* PerMIS, 2003. Key use: neglect tolerance, robot attention demand, interaction effort.
4. **Hart, S. G. / NASA Ames.** *NASA Task Load Index (TLX).* Key use only if a formal operator workload study is later added.

## PLEXIL and plan execution

5. **Estlin, T., Jonsson, A., Pasareanu, C., Simmons, R., Tso, K., and Verma, V.** *Plan Execution Interchange Language (PLEXIL).* NASA/TM-2006-213483, 2006. NTRS ID 20060019246.
6. **PLEXIL Group.** *PLEXIL Release 6 User's Guide and Reference.* `https://plexil-group.github.io/plexil_docs/`. Key implementation facts: conditions, loops, concurrency, Commands, Lookups, resources, executive configuration.
7. **PLEXIL Group.** Official open-source repository: `https://github.com/plexil-group/plexil`.
8. **NASA Langley / PLEXIL-V.** Formal verification environment for PLEXIL, `https://github.com/nasa/PLEXIL5`. Optional supporting reference for plan verification; not required for the main contribution.

## EUROPA and model-based planning

9. **Bedrax-Weiss, T., Frank, J., Jonsson, A., and McGann, C.** *EUROPA2: Plan Database Services for Planning and Scheduling Applications.* NASA/NTRS 20050157874, 2004. Key use: plan database, action/state/resource/constraint modeling, integration into NASA planning applications.
10. **NASA Ames.** EUROPA open-source repository: `https://github.com/nasa/europa`. Key implementation facts: Plan Database, Problem Solver, declarative domain modeling, embedded host-application design.
11. **Bresina, J., Jonsson, A., Morris, P., and Rajan, K.** *Activity Planning for the Mars Exploration Rovers.* ICAPS-era MER/MAPGEN publication, 2004/2005. Key use: mixed-initiative constraint-based planning and mission-operations context.

## Continuous replanning and onboard integrated planning/execution

12. **JPL Artificial Intelligence Group.** *CASPER — Continuous Activity Scheduling Planning Execution and Replanning.* Official project description and linked publications. Key use: iterative repair, current goals/state/plan, continuous replanning.
13. **Verma, V., Gaines, D., Rabideau, G., Schaffer, S., and Joshi, R.** *Autonomous Science Restart for the Planned Europa Mission with Lightweight Planning and Execution.* IWPSS 2017 / NTRS 20210008204. Key use: MEXEC, state monitoring, conflict detection, plan revision after reset/fault.
14. **JPL Artificial Intelligence Group.** *MEXEC — Onboard Task Planning and Execution.* Official project description. Key use: task networks, planner/executive/timeline architecture, Mars 2020, CADRE, Europa/ASTERIA applications.
15. **Campuzano et al.** *MEXEC: An Onboard Integrated Planning and Execution Approach for Spacecraft Commanding.* JPL/NTRS 20220001521, 2020. Key use: goal-based task-network commanding and ASTERIA experiments.
16. **Rabideau, G. et al.** *Planning, Scheduling, and Execution on the Moon: The CADRE Technology Demonstration Mission.* AAMAS 2025. Key use: strong contemporary lunar onboard planning/scheduling/execution comparison point.
17. **JPL Artificial Intelligence Group.** *Europa Lander planning and execution research.* Key use: hierarchical task-network construction from domain knowledge, flexible execution, periodic replanning, online model update.

## Knowledge engineering and extensibility

18. **JPL Artificial Intelligence Group.** *Efficient Task Network Generation (TaskNet).* Key use: explicit statement that task-network specification is manual/cumbersome/error-prone and that reducing plan-creation time is an autonomy-operations goal.
19. **Strobel, V. and Kirsch, A.** *MyPDDL: Tools for Efficiently Creating PDDL Domains and Problems.* 2020. Key use: planning-model engineering is time-consuming/error-prone; user-study metrics include task completion time and error detection.
20. **McCluskey, T. L., Vaquero, T. S., and Vallati, M.** *Engineering Knowledge for Automated Planning: Towards a Notion of Quality.* K-CAP 2017. Key use: domain-model knowledge engineering as a substantive part of planning applications.
21. **Vallati, M., Barták, R., Chrpa, L., McCluskey, T. L., and Petrick, R. P. A.** *Knowledge Engineering for Planning and Scheduling in the LLM Era.* ICAPS 2025. Key use: LLM assistance can streamline knowledge engineering, but external validation/domain expertise remain necessary in safety-related applications.

## Foundation-model and physical-agent runtime context

22. **OpenRAL** — official repository/documentation, especially the `ReasonerToolCall` contract, rSkill/tool palette, `MissionState`, world state, execution, observability, and safety path. `https://docs.openral.com/reference/reasoner/`. Used as implementation substrate, not primary scientific baseline.
23. **Space Robotics Bench (SRB)** — extraterrestrial/lunar robotics simulation and ROS/Isaac Lab interface. Used as the main simulation substrate.
24. **Inspect Robots** — evaluation/logging concepts where useful; not a required control-path component.

## Agent-harness design references (systems precedents, not aerospace evidence)

25. **Nous Research.** *Hermes Agent — Agent Loop Internals; Tools Runtime; Skills System.* Official documentation, 2026. `https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop`, `https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime`. Key use: model-directed tool loop; self-registering tool schemas/handlers; harness ownership of history, dispatch, recovery, provider switching, and agent state rather than domain task solutions.
26. **Pi.** *Pi Coding Agent / Documentation.* `https://pi.dev/` and `https://pi.dev/docs/latest`. Key use: minimal-harness design; customization through extensions, tools, skills, and prompt templates rather than a large fixed workflow engine.
27. **OpenAI.** *Unrolling the Codex agent loop* (2026) and *Running Codex safely at OpenAI* (2026). `https://openai.com/index/unrolling-the-codex-agent-loop/`, `https://openai.com/index/running-codex-safely/`. Key use: model/tool agent loop plus sandbox, approvals, constrained execution, thread persistence, and telemetry as execution boundaries rather than task-specific solution logic.

## Operations, intent, and explanation

28. **Castano, R., Vaquero, T., Rossi, F., Verma, V., Van Wyk, E., Allard, D., et al.** *Operations for Autonomous Spacecraft.* IEEE Aerospace Conference, 2022. JPL Artificial Intelligence Group. `https://ai.jpl.nasa.gov/public/documents/papers/castano-etal-AERO2022.pdf`. Key use: future autonomy changes both uplink and downlink operations; ground must convey intent, predict likely autonomy effects, reconstruct onboard state, and explain autonomous decisions.
29. **JPL Artificial Intelligence Group.** *Operations for Autonomy* project. `https://ai.jpl.nasa.gov/public/projects/ops-for-autonomy/`. Key use: intent capture, state estimation/propagation, decision reconstruction, and explanation as operational requirements for autonomous spacecraft.
30. **JPL Artificial Intelligence Group.** Mars 2020 On-Board Planner / Simple Planner publications and V&V reports. Key use: operational precedent for trusted onboard planning rather than a claim that goal-level autonomy is new.

## Space-native context

31. **Landon, L. B., Karasinski, J. A., Morissette, L. G., McTigue, K. R., Parisi, M. E., Wu, S.-C., and Panontin, T. L.** *Assessment of the State of Communication Delay Research in Preparation for Missions Beyond Low Earth Orbit.* NASA/TM-20250003885, 2025. `https://ntrs.nasa.gov/citations/20250003885`. Key use: 3–14 s one-way lunar communication-delay regime; limits of the traditional real-time ground-support paradigm and increased need for local autonomy.
32. **NASA / ESA / JAXA.** *LunaNet Interoperability Specification, Version 5.* 2025. `https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/`. Key use: interoperable lunar network-of-networks; Direct-with-Earth and lunar relay services; current lunar communication architecture assumptions.
33. **NASA Space Communications and Navigation (SCaN).** *Delay/Disruption Tolerant Networking Overview.* `https://www.nasa.gov/reference/delay-disruption-tolerant-networking-overview/`. Key use: disconnections, delay, data-rate mismatch, store-and-forward operation, time-disjoint links, and DTN as a core mechanism for lunar networking/LunaNet.
34. **NASA Space Communications and Navigation (SCaN).** *Lunar Communications Relay and Navigation Systems (LCRNS)* reference material and Reference Constellation 3.1. `https://www.nasa.gov/goddard/esc/lcrns/`. Key use: relay-supported lunar communication/navigation infrastructure. Important boundary: relay availability does not imply general-purpose onboard foundation-model compute.
35. **NASA.** *High Performance Spaceflight Computing (HPSC).* 2024–2026 project documentation and white paper. `https://www.nasa.gov/game-changing-development-projects/high-performance-spaceflight-computing-hpsc/`. Key use: radiation environment, power management, fault tolerance, connectivity, and the growing need for high-performance onboard AI/autonomy; evidence that spaceflight compute is improving but remains resource- and assurance-constrained.
36. **Lewis, M. E., McCleskey, C. M., Alvarez, V. R., Gomez, J. D. Jr., Latorella, K. A., Gill, T. R., Perotti, J. M., and Zeitlin, N. P.** *Uncrewed Lunar Surface Operations and Support Activities.* ASCEND 2022; NASA NTRS 20220013667. `https://ntrs.nasa.gov/citations/20220013667`. Key use: increased independence from Earth/surface crews; illumination/shadow, thermal management, battery pre-charging, load shedding, hibernation, and adaptive uncrewed operation.
37. **Rabideau, G. et al.** *Planning, Scheduling, and Execution on the Moon: The CADRE Technology Demonstration Mission.* AAMAS 2025; plus JPL CADRE project documentation. `https://ai.jpl.nasa.gov/public/projects/cadre/`. Key use: MEXEC-based strategic planning with predicted/actual temperature and energy levels; scheduling survey, sleep, cooling, and recharge within lunar operational limits.
38. **NAIF SPICE / SpiceyPy documentation.** Key use: Sun/Earth/Moon geometry and mission-time profiles when the selected experiment requires geometry-derived context.

## Boundary with previous work

39. **Huang et al.** *Toward Self-Evolving Lunar Robotic Autonomy Through Contract-Governed Skill Registration*, Astronautics, 2026.

The previous work addresses how heterogeneous capabilities are represented, registered, and dispatched. The present paper asks a different question: **how a complete autonomy stack can reason and operate continuously at mission level when the required task structure is not fully pre-authored, and how that autonomy can be extended with lower mission-specific knowledge-engineering effort.**
