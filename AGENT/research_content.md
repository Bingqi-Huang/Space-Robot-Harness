# Research Content — Space Robotics Agent Harness for Future Lunar Autonomy

**Status:** frozen high-level framing; method and experiments specified at paper-outline level; results pending execution  
**Target venue:** Acta Astronautica  
**Scope:** future lunar robotic operations, mission-level autonomy, trustworthy agentic runtime  
**Reference embodiment:** LunarBot as a later real-system reference; primary scientific validation in simulation

---

## Working title

**From Procedure-Driven Operations to Mission-Intent Autonomy: A Space Robotics Agent Harness for Long-Horizon Lunar Missions**

Alternative title direction:

**A Space-Native Agent Harness for Trustworthy Mission-Level Autonomy in Lunar Robotics**

The final title should be selected only after the experiments establish the strongest supported claim.

---

# Abstract — intended logic

Future lunar surface operations will combine mobile manipulation, infrastructure inspection and maintenance, logistics, construction, scientific operations, and resource utilization over longer durations and with less continuous Earth supervision. Individual autonomy capabilities already exist for navigation, perception, manipulation, task planning, learned robot policies, fault detection and recovery, resource management, and runtime safety. The emerging bottleneck is therefore not the absence of individual algorithms, but the mission-level operating model used to coordinate them: current planetary robotic operations remain dominated by predefined procedures, engineered activity models, state machines, and human coordination.

Modern coding agents provide a different systems pattern. Their capability does not come from replacing compilers, shells, file systems, tests, or other specialized tools, but from an agent harness that continuously manages context, tool use, execution, verification, permissions, memory, and recovery around a long-horizon objective. Emerging physical-agent systems show that a similar pattern can coordinate robot policies, perception, motion planning, and classical control. However, terrestrial physical-agent harnesses do not directly address the operating conditions that define lunar missions: delayed and intermittent communications, relay-dependent network availability, heterogeneous distributed computing, time-varying illumination and thermal conditions, limited power and data budgets, mission authority, failure detection and recovery, and aerospace requirements for independent verification and traceability.

This work investigates whether the fragmented autonomy stack of future lunar robots can be reorganized as a **trustworthy, space-native agentic mission runtime**. The proposed Space Robotics Agent Harness uses foundation-model reasoning for open-ended mission interpretation, task decomposition, capability selection, diagnosis, and replanning, while retaining conventional and learned robotics modules as specialized execution capabilities. The runtime maintains authoritative mission state, integrates lunar operational context, coordinates distributed intelligence, enforces mission authority and resource-aware execution, connects to independent safety/FDIR mechanisms, and updates mission progress only from verified physical outcomes. The evaluation compares the same underlying robot capabilities under procedure-driven control, a generic physical-agent harness, a prompt-only space-aware agent, and the proposed space-native runtime across long-horizon lunar missions with controlled variation in communication, computation, environmental, resource, and failure conditions. The intended scientific claim is that mission-level autonomy can be increased by changing the operating model that coordinates existing capabilities, without transferring aerospace trust requirements to the foundation model itself.

---

# 1. Introduction

## 1.1 The problem begins with future lunar operations

The motivating problem is not that future lunar robots lack navigation, manipulation, planning, or AI. Future lunar activity is expected to involve combinations of:

- infrastructure inspection and maintenance;
- logistics and payload handling;
- construction and assembly;
- scientific observation and sampling;
- ISRU-related operations;
- servicing of power, communication, and mobility infrastructure;
- cooperation between multiple robotic and crewed assets;
- long-duration unattended or lightly supervised activity.

These missions differ from short, tightly scripted sorties because they require a larger number of mission transitions, more unexpected contingencies, more heterogeneous robot capabilities, and less detailed human supervision.

The existing autonomy stack is already powerful. Planetary robotics has demonstrated autonomous navigation, autonomous science targeting, onboard planning and scheduling, execution monitoring, FDIR, teleoperation under delay, resource-aware activity planning, and increasingly learned perception and control. Modern robotics additionally provides VLM reasoning, VLA/VLN policies, task-and-motion planning, learned success monitoring, and open-ended semantic perception.

The central bottleneck is therefore increasingly **mission-level integration**.

> Future lunar robots will possess many capable but heterogeneous subsystems, yet these capabilities are still largely coordinated through predefined procedures, engineered state machines, fixed activity models, and human operators. This operating model does not scale naturally to long-duration, multi-task, increasingly open lunar operations with reduced Earth supervision.

This work treats that operating-model limitation as the primary research problem.

## 1.2 Why existing mission autonomy is not enough

Classical space autonomy systems such as Remote Agent, ASPEN/CASPER, PLEXIL, AEGIS, ERGO, and the Mars 2020 onboard planner demonstrate that planning, execution, resource reasoning, and fault handling can be moved onboard. Their key strength is explicit mission logic and well-defined execution semantics. Their limitation relative to the problem considered here is not lack of sophistication; it is that the activity space, task models, temporal constraints, and recovery logic are predominantly engineered in advance.

That model is well suited to tightly specified missions. It becomes increasingly expensive when the robot must interpret higher-level mission intent, combine conventional and learned capabilities, respond to semantically novel situations, and determine new task decompositions that were not completely enumerated before deployment.

The objective of this work is not to replace classical mission executives, but to retain their discipline while enabling a more open mission-level reasoning layer.

## 1.3 Agent harnesses suggest a different operating model

Modern coding agents provide an important systems precedent. A coding agent does not replace compilers, shells, version control, file systems, browsers, or tests. Instead, the surrounding harness turns these heterogeneous capabilities into a persistent problem-solving system by repeatedly:

**interpreting the goal → gathering relevant context → selecting a tool → executing → observing → verifying → updating state → continuing or recovering.**

The research insight is structural:

> A capable foundation model becomes a persistent operational agent only when a runtime organizes specialized capabilities, state, permissions, verification, and recovery around the model.

Space robotics already contains the analogue of these specialized tools: navigation, manipulation, VLA/VLN policies, perception, task/activity planners, resource models, FDIR, runtime assurance, communication services, and ground-support interfaces.

This suggests that the relevant question is not whether a foundation model can directly control a lunar robot, but whether the **space-robotics autonomy stack can be reorganized around an agentic mission runtime**.

## 1.4 Why a generic physical-agent harness is insufficient

Recent physical-agent systems already demonstrate LLM/VLM-driven orchestration of robot tools and policies, hierarchical VLA execution, memory, success monitoring, and runtime safety. These systems establish that a physical harness is feasible.

A lunar mission, however, is not simply a terrestrial robot task performed under lunar gravity. The runtime must operate under conditions that directly change what decisions are possible and where intelligence can reside:

- Earth–Moon propagation delay;
- terrain-dependent Direct-to-Earth visibility;
- relay-dependent communication windows determined by orbital geometry;
- planned and unplanned periods of disconnection;
- strongly heterogeneous compute across Earth, surface infrastructure, and onboard processors;
- limited power, thermal, storage, and data-transfer budgets;
- time-varying lunar illumination and shadow;
- low gravity and uncertain terrain interaction;
- robot and subsystem faults during long unattended operation;
- bounded autonomous authority;
- irreversible or expensive physical actions;
- requirements for independent verification, recoverability, and auditability.

These conditions are not secondary stress tests. They are part of the runtime state that determines how autonomy should be exercised.

## 1.5 Research question

The paper addresses the following question:

> **Can the fragmented autonomy stack of future planetary robots be reorganized into a trustworthy, space-native agentic mission runtime, such that a robot can receive mission-level intent and autonomously coordinate existing AI and conventional space-robotics capabilities throughout long-horizon lunar operations while respecting communication, computation, environmental, resource, authority, safety, and FDIR constraints?**

## 1.6 Central hypothesis

The central hypothesis is:

> **Mission-level autonomy can be increased substantially without replacing specialized space-robotics algorithms, by changing the operating model that coordinates them: from fixed procedures and continuous human orchestration to a persistent agentic runtime that uses foundation-model reasoning for open-ended decisions while retaining trusted conventional mechanisms for physical execution, mission constraints, FDIR, and verification.**

The expected benefit is not primarily an increase in primitive manipulation success. It is a change in the granularity of commanding:

**detailed procedure / frequent intervention → mission intent / exception-level supervision.**

## 1.7 Intended contributions

The final paper should support contributions at the following level, with wording adjusted after experiments:

1. **Problem formulation:** identify mission-level coordination of fragmented autonomy capabilities as an emerging bottleneck for long-duration lunar robotic operations, and formulate the transition from procedure-driven operations to mission-intent-driven autonomy.

2. **Space Robotics Agent Harness:** propose a mission runtime that combines foundation-model reasoning with heterogeneous conventional and learned robot capabilities while maintaining authoritative mission state and explicit space-operational context.

3. **Space-native execution semantics:** integrate communication/compute availability, lunar environmental conditions, mission resources, authority, FDIR, independent verification, and distributed intelligence as first-class runtime considerations rather than prompt-only information.

4. **Experimental evidence:** demonstrate, using common underlying robot capabilities, when procedure-driven control, a generic physical-agent harness, and prompt-only space awareness fail to provide the same mission-level autonomy as a space-native runtime under long-horizon lunar mission conditions.

The paper should not claim novelty for skill libraries, generic tool calling, generic safety filters, VLA architectures, or resource schedulers.

---

# 2. Related Work

The related-work section should be organized around the research gap rather than as an exhaustive technology catalog.

## 2.1 Planetary mission autonomy and execution

### Representative literature

- Remote Agent / Deep Space 1;
- ASPEN and CASPER;
- EO-1 Autonomous Sciencecraft;
- PLEXIL / Universal Executive;
- AEGIS autonomous science targeting;
- Mars 2020 Onboard Planner / MEXEC;
- ERGO;
- ISAAC autonomous caretaking;
- surface telerobotics and supervised autonomy studies;
- current lunar autonomous navigation, planning, construction, and servicing studies.

### What this literature establishes

- autonomous planning and execution are operationally valuable;
- resource and temporal constraints belong inside the autonomy loop;
- FDIR cannot be treated as an afterthought;
- onboard autonomy can reduce command-cycle dependence;
- trusted execution requires explicit state and execution semantics.

### Gap relative to this work

These systems largely operate over engineered activity models, procedures, timelines, or predefined action representations. They do not address the integration of open-ended foundation-model reasoning, learned robot policies, conventional planners/controllers, and modern perception as one persistent mission-intent-driven runtime.

## 2.2 Foundation-model robotics and physical-agent harnesses

### Representative literature and systems

- hierarchical VLA systems;
- RoboOS;
- RAI / ROSA;
- RoboClaw;
- RoboHarness;
- Physical Agentic AI;
- Show-Harness;
- OpenRAL;
- Inspect Robots;
- studies of robot-policy orchestration and success monitoring.

### What this literature establishes

- LLM/VLM reasoning can organize robot capabilities;
- typed tool interfaces improve grounding and interoperability;
- learned and classical robot capabilities can coexist under a higher-level reasoner;
- success monitoring, memory, and failure attribution improve long-horizon operation;
- a model should not directly own all physical execution authority.

### Gap relative to this work

Most physical-agent harnesses are designed for terrestrial or generic robotics. They do not jointly treat planetary communication topology, hierarchical distributed intelligence, lunar environmental state, resource constraints, mission authority, FDIR, and aerospace traceability as the operating semantics of the mission runtime.

## 2.3 Trustworthy autonomy and runtime assurance

### Representative literature

- NASA autonomous-systems taxonomy and autonomy V&V roadmaps;
- Runtime Assurance / Simplex-derived architectures;
- STARS;
- ECSS machine-learning assurance guidance;
- lunar autonomy certification work;
- reliability-asymmetric spacecraft autonomy;
- runtime policy enforcement and formal/logic-based robot safety systems;
- learned-policy failure detection and progress monitoring.

### What this literature establishes

- learned intelligence cannot constitute its own complete safety argument;
- independent monitoring and bounded authority remain necessary;
- degraded modes and safe recovery must be designed explicitly;
- traceability and assurance evidence matter separately from task success.

### Position of this work

The paper does not introduce a new generic safety filter. It incorporates these principles into the mission-runtime architecture and uses existing monitors/checkers wherever possible.

## 2.4 Lunar environment, communication, and computing

### Representative infrastructure and literature

- LunaNet / LCRNS;
- Delay/Disruption Tolerant Networking;
- lunar relay constellation studies;
- south-pole illumination and communication-aware planning;
- lunar surface autonomy and construction studies;
- NASA High Performance Spaceflight Computing;
- in-space edge-computing demonstrations;
- ASTREA and other flight/flight-relevant AI demonstrations;
- Space Robotics Bench.

### What this literature establishes

- temporary disconnection is a normal operational condition;
- communication availability depends on geometry and infrastructure rather than a stationary terrestrial network model;
- advanced computation will increasingly exist in space, but capability remains heterogeneous and constrained;
- lunar illumination, terrain, power, and thermal conditions create time-dependent operational context;
- AI inference latency and compute placement can interact with physical mission dynamics.

## 2.5 Synthesis of the research gap

The literature contains strong solutions for each component separately:

**space mission execution + physical-agent orchestration + trustworthy autonomy + lunar communications/environment.**

The research gap is their intersection:

> **a mission-intent-driven physical-agent runtime that coordinates conventional and learned space-robotics capabilities while treating space communication, distributed compute, environmental/resource state, authority, FDIR, independent verification, and traceability as first-class execution semantics.**

A formal priority or “first” claim should only be made after final targeted literature falsification.

---

# 3. Problem Setting and Design Requirements

## 3.1 Mission setting

The target is a long-horizon lunar mobile-manipulation mission in which the operator provides a mission objective rather than a complete action procedure.

Representative instruction:

> Inspect the designated lunar service site, identify the failed subsystem, restore its operation, verify the result, and leave the robot in an operationally safe condition.

The mission may require combinations of navigation, inspection, semantic perception, manipulation, learned policies, classical motion planning, diagnosis, fault handling, resource reasoning, and communication with higher-level intelligence.

The exact execution sequence is not supplied by the operator.

## 3.2 Existing capabilities are assumed, not reinvented

The robot is assumed to have a heterogeneous set of callable capabilities such as:

- localization and mapping;
- navigation/path planning;
- visual inspection and semantic perception;
- manipulator planning and control;
- VLA/VLN policies;
- task/activity planning services;
- resource and health services;
- FDIR functions;
- runtime safety mechanisms;
- local and remote foundation-model reasoning;
- human/mission-control communication.

The scientific question is how these are coordinated at mission level.

## 3.3 Four non-negotiable design requirements

### 3.3.1 Unified capability orchestration

The system must be capable of deciding which existing capability should be used, in what order, with what supporting observations, and how to continue after an unexpected outcome, without requiring the complete procedure to be specified before the mission.

### 3.3.2 Space-native operational context

The runtime must reason over mission context that changes with place and time, including communication state, compute availability, illumination, robot health, and mission resources. These quantities must influence actual execution decisions rather than merely appear in a system prompt.

### 3.3.3 Distributed intelligence and structured authority

Reasoning may be distributed across Earth, lunar surface infrastructure, and onboard computing. Different intelligence layers possess different capability, latency, information freshness, and authority. Fast physical control and safety must remain local; higher-capability remote reasoning may be used opportunistically.

### 3.3.4 Trustworthy physical execution

The foundation model may propose actions and task decompositions, but it does not own authoritative physical state, mission completion, or unrestricted actuation authority. Critical mission progress and safety conditions are established through independent state and verification mechanisms.

---

# 4. Proposed Method: Space Robotics Agent Harness

The method is a **mission-level runtime**, not a new robot controller or foundation model.

## 4.1 Architectural principle

The architecture separates open-ended reasoning from authoritative execution state.

At a conceptual level:

```text
Mission Control / Human Intent
          |
          v
Foundation-Model Reasoning
          |
          v
=================================================
          SPACE ROBOTICS AGENT HARNESS
-------------------------------------------------
 authoritative mission state
 dynamic mission context
 capability orchestration
 space-operational context
 distributed intelligence coordination
 mission authority and policy
 FDIR / safety integration
 independent outcome verification
 execution evidence and trace
=================================================
          |
          v
Navigation / Perception / Planner / VLA /
Manipulation / Resource Services / FDIR / Safety
          |
          v
Physical Robot and Lunar Mission Environment
```

The foundation model provides semantic flexibility; the runtime provides persistent operational structure.

## 4.2 Authoritative mission state

The central runtime object is an **authoritative mission state** maintained independently of the language-model conversation.

It records the mission information that must survive model changes, communication interruption, context compaction, and replanning, including:

- mission objective and priorities;
- current operational objective;
- completed and pending mission transitions;
- unresolved anomalies;
- current physical/world state relevant to the mission;
- active or pending execution;
- current authority state;
- relevant resource/health state;
- verified outcomes and supporting evidence;
- information that requires re-observation or higher-level confirmation.

The purpose is not to reproduce a full symbolic world model. It is to maintain the minimum authoritative state required for coherent mission continuation.

A foundation model may hypothesize that a task has succeeded, but mission state advances only when the relevant outcome has been independently verified.

## 4.3 Dynamic mission context construction

The reasoning model should not receive a fixed global prompt containing every telemetry variable and every historical event. At each deliberative step, the runtime constructs context from:

- current mission objective and progress;
- current verified robot/world state;
- current space-operational conditions;
- available capabilities and intelligence nodes;
- active faults and degraded modes;
- relevant recent execution evidence;
- authority/policy information relevant to the proposed decision.

This mirrors the context-management role of coding-agent harnesses, but the context is built from physical mission state rather than software-workspace state.

## 4.4 Space-operational context

The runtime treats the following as first-class mission state.

### Communication context

- whether Direct-to-Earth communication is currently available;
- relay availability and contact opportunities;
- expected communication interruption or restoration;
- link asymmetry and usable data capacity;
- latency appropriate to the current link;
- whether a requested remote service can currently be reached.

### Environmental context

- lunar location and mission time;
- illumination and shadow state;
- terrain/environment state relevant to navigation and observation;
- thermal exposure indicators where relevant;
- lunar gravity and terrain-contact conditions provided by the simulator.

### Resource and system context

- battery/energy state and reserve information;
- thermal condition;
- storage/data-transfer availability;
- compute availability;
- subsystem health;
- current capability degradation.

The method does not attempt to solve an optimal resource-scheduling problem. These quantities constrain the runtime decisions made by the mission agent.

## 4.5 Capability orchestration

The foundation-model reasoner interacts with a **closed, typed capability set**, not unrestricted robot APIs.

Capabilities may include both conventional and learned components. The runtime uses capability metadata and current operational state to determine what can be considered for the current mission transition.

The key distinction from a static skill sequence is that the reasoner may dynamically:

- acquire additional observations;
- select a different execution method;
- change task ordering where mission policy permits;
- interpret an unexpected physical result;
- invoke fault handling;
- defer a task;
- request higher-level support;
- replan the remaining mission.

The capability itself remains responsible for its specialized computation; the mission runtime is responsible for how it is used in the larger mission.

## 4.6 Mission-level action admissibility

Before an agent proposal becomes a physical execution request, the runtime evaluates the proposal against current authoritative mission state and space-operational context.

The evaluation asks qualitatively different questions from low-level robot safety:

- Is this action consistent with the current mission objective and priority?
- Is the robot authorized to perform it autonomously?
- Are the required capabilities currently available?
- Does execution rely on communication or computation that is currently unavailable or operationally inappropriate?
- Is the action compatible with current resource/health conditions?
- Does an active fault or degraded subsystem require a different operating mode?
- Is additional observation or external confirmation required before execution?

The outcome of this layer may be execution, deferral, replanning, or escalation. The exact decision policy should be driven by mission rules and experimentally studied behavior rather than arbitrary fixed thresholds.

Low-level physical safety remains an independent mechanism below this mission layer.

## 4.7 Distributed intelligence coordination

The runtime supports multiple possible reasoning locations:

- onboard/local intelligence;
- lunar-surface or local-edge intelligence;
- remote/Earth-side intelligence.

The system does not assume that the highest-capability model is continuously reachable.

When communication or service availability changes, the runtime constructs context for whichever reasoning layer is currently usable from the authoritative mission state rather than treating the previous model conversation as the source of truth.

This enables:

- local continuation when remote reasoning is unavailable;
- bounded use of lower-capability models;
- opportunistic use of higher-capability remote models;
- reconstruction of current mission context after reconnection;
- avoidance of stale-context continuation after the physical world has changed.

This mechanism is a component of the broader mission-runtime architecture, not the thesis of the paper by itself.

## 4.8 Independent execution and verification

The execution path should separate four roles:

1. **reasoning:** proposes the next mission-relevant action or information-gathering step;
2. **mission runtime:** determines whether the proposal is admissible in the current mission context;
3. **execution capability and safety system:** performs the physical action under its own controller/policy and low-level constraints;
4. **verifier/observer:** establishes what actually happened.

Mission progress is updated from the fourth role, not from the reasoning model's assertion.

Possible evidence sources include:

- geometric goal satisfaction;
- controller execution result;
- perception-based state recognition;
- task-progress or success monitors;
- subsystem telemetry;
- FDIR state;
- explicit human or mission-control confirmation for authority-limited cases.

## 4.9 FDIR integration

FDIR is treated as part of the mission runtime rather than a side alarm channel.

Faults may change:

- which capabilities are available;
- which operating modes are allowed;
- what information must be reacquired;
- whether a task should be retried, substituted, deferred, or abandoned;
- whether local continuation remains appropriate;
- whether human/mission-control intervention is required.

The Harness does not replace subsystem-level FDIR algorithms; it incorporates their outputs into mission-level decision making.

## 4.10 Trustworthiness and traceability

For each consequential mission transition, the runtime should preserve a structured trace of:

**mission objective → verified state → relevant operational context → reasoner proposal → mission-level disposition → selected capability → safety/execution result → verification evidence → updated mission state.**

This provides an operationally useful form of explainability for review, debugging, V&V, and incident reconstruction without relying on unverified natural-language chain-of-thought.

---

# 5. Experimental Methodology

The experiments should test the paper's central causal claim: **the same underlying capabilities become more useful at mission level when coordinated through a space-native agentic runtime.**

## 5.1 Evaluation philosophy

The experiments should not compare unrelated robot models or train a new end-to-end policy for each baseline. As far as practical, all systems should share the same:

- robot embodiment;
- perception;
- navigation;
- manipulation controller;
- VLA/VLN policies where used;
- foundation model family;
- FDIR primitives;
- safety mechanisms;
- simulation scenes and mission objectives.

The independent variable is the **mission-level operating model**.

## 5.2 Baselines

### Baseline A — Procedure-driven mission execution

A conventional pre-engineered procedure or behavior-tree/state-machine representation coordinates the same underlying capabilities. Unexpected conditions outside the encoded procedure require fallback logic or human intervention.

Purpose: represent the command/procedure-centric operating model that the proposed work seeks to relax.

### Baseline B — Generic physical-agent harness

A foundation-model reasoner can access the available robot capabilities and physical observations through a generic agentic runtime, but the runtime does not contain explicit space-native mission semantics beyond the normal robot world state and safety mechanisms.

Purpose: determine whether an existing physical harness can simply be transferred to a lunar mission setting.

### Baseline C — Prompt-only space-aware agent

The generic agent receives communication, environmental, resource, and mission-policy information in its prompt/context, but these variables are not represented as independent authoritative runtime state with mission-level enforcement and verified state transitions.

Purpose: test whether “telling the LLM about the constraints” is sufficient.

### Proposed — Space Robotics Agent Harness

The same reasoner and robot capabilities operate through the proposed authoritative mission state, space-operational context, distributed-intelligence coordination, mission-level admissibility, FDIR integration, independent verification, and traceability mechanisms.

## 5.3 Mission families

The paper should use a small number of coherent, long-horizon missions rather than many disconnected manipulation benchmarks.

### Mission family 1 — Infrastructure inspection and maintenance

Representative objective:

> Inspect a designated lunar infrastructure site, identify the failed subsystem, restore operation, verify the restoration, and leave the system in an operationally safe condition.

Potential mission elements:

- navigation to the site;
- locating and identifying infrastructure;
- acquiring diagnostic observations;
- selecting the appropriate manipulation/inspection capability;
- interacting with a component or interface;
- detecting an unsuccessful or incomplete operation;
- recovery or alternative action;
- verification of the restored state;
- mission completion/reporting.

### Mission family 2 — Logistics and servicing under contingencies

Representative objective:

> Deliver the required component or tool to a service location and complete the pending servicing operation while responding to changing mission conditions.

Potential mission elements:

- item identification and retrieval;
- transport/navigation;
- manipulation and placement;
- changed object location or blocked route;
- temporary loss of a required remote service;
- robot or perception degradation;
- changed mission priority or fault condition;
- verification of servicing result.

A third mission should only be added if it provides a qualitatively different test of the runtime rather than more task variety for its own sake.

## 5.4 Experimental factor groups

### 5.4.1 Mission openness and contingency

Vary whether the mission proceeds nominally or contains conditions that were not encoded as a complete procedural branch, such as:

- changed target location;
- changed action order;
- unexpected object state;
- failure of an attempted manipulation;
- need for additional observation;
- substitution of one available capability for another.

This group tests the value of agentic mission coordination relative to fixed procedures.

### 5.4.2 Space communication and distributed compute

Vary:

- continuous versus intermittent remote connectivity;
- Direct-to-Earth versus relay-supported availability;
- communication interruption and reconnection;
- local versus remote model availability;
- link asymmetry and communication delay;
- service availability at different compute tiers.

The contact patterns should be based on lunar mission geometry or published infrastructure assumptions rather than arbitrary random packet loss alone.

This group tests whether the runtime continues coherently when intelligence is physically distributed.

### 5.4.3 Lunar environmental and resource context

Vary mission conditions such as:

- illumination/shadow state;
- available energy margin;
- thermal/operational condition where represented;
- terrain difficulty or mobility uncertainty;
- data/compute resource availability.

These conditions should affect mission decisions but should not turn the work into a resource-optimization paper.

### 5.4.4 Fault and degradation

Inject controlled conditions such as:

- perception degradation;
- manipulation failure;
- navigation failure or blocked route;
- unavailable learned policy/service;
- subsystem fault reported through FDIR;
- remote reasoning failure or timeout.

This group tests whether FDIR and capability status are incorporated into mission-level reasoning.

### 5.4.5 Trustworthiness challenge cases

Construct cases where a foundation model produces a locally plausible but mission-invalid proposal, such as:

- repeating a completed operation;
- using a capability that is unavailable or outside authority;
- performing the right operation on the wrong target;
- ignoring a fault/degraded state;
- acting on stale context after the physical state changed;
- declaring mission progress without sufficient evidence.

This group separates semantic flexibility from trustworthy execution.

## 5.5 Primary metrics

### Mission accomplishment

- complete mission success;
- completion of mission objectives/subobjectives;
- time or mission effort required;
- recovery success after anomalies.

### Human decision burden

- number of human interventions;
- number of manually specified subtasks;
- command granularity;
- clarification/escalation requests;
- fraction of mission transitions handled autonomously;
- mission completion under bounded human-supervision availability.

The interpretation should focus on whether the operator can move from detailed procedure generation toward mission-level intent.

### Trustworthiness

- safety violations;
- authority violations;
- mission-invalid actions;
- stale-state actions;
- unsupported mission-state transitions;
- unresolved failures followed by continued execution;
- incorrect declarations of task completion.

### Adaptivity

- recovery/replanning following unexpected events;
- successful capability substitution;
- response to degraded subsystems;
- successful continuation across changing model/service availability.

### Communication and compute

- remote and local model calls;
- data transferred;
- communication wait time;
- inference latency;
- mission idle time attributable to remote dependence;
- operations completed during remote unavailability.

### Traceability

- fraction of consequential state transitions with complete evidence/decision traces;
- ability to reconstruct why an action was executed or rejected;
- correspondence between mission-state updates and independent outcome evidence.

## 5.6 Ablation studies

Ablations should isolate the runtime mechanisms rather than simply remove unrelated robot components.

Candidate ablations:

- remove authoritative mission state and rely on conversational context;
- provide space context only to the model, without independent runtime use;
- remove independent outcome verification and accept model/controller success claims;
- remove distributed-intelligence state reconciliation;
- remove mission authority/FDIR integration while retaining low-level safety;
- remove dynamic context selection and expose a static comprehensive prompt.

Only ablations relevant to mechanisms actually implemented should appear in the final paper.

## 5.7 Evaluation environments

Primary scientific evaluation should use a space-robotics simulation platform capable of lunar gravity, mobile manipulation, procedural/randomized scenes, and scalable repeated trials. Space Robotics Bench / Isaac Lab is the preferred basis because it already provides extraterrestrial domains, mobile-manipulation templates, manipulation tasks, domain randomization, and ROS 2 interoperability.

A simpler simulator may be used for controlled mechanism ablations if needed, but the main paper must contain genuinely space-operational mission conditions.

A LunarBot demonstration may be added to show that the same mission-runtime abstraction can connect to a real mobile-manipulation stack and distributed compute topology. It should validate transfer of the runtime, not attempt to reproduce the lunar environment on Earth.

---

# 6. Planned Results and Evidence Structure

No numerical results are assumed at this stage. This section defines what evidence would be required for the paper's claims.

## 6.1 Main comparison

A central result should compare the four operating models across increasing mission openness and increasingly space-realistic operating conditions.

The desired analysis should separate:

- mission completion;
- human intervention;
- mission-invalid actions;
- safety/authority violations;
- recovery after failure;
- communication/compute dependence.

The paper should not compress all outcomes into a single score.

## 6.2 Key expected qualitative finding

If the hypothesis is correct, the result should show a characteristic trade-off:

- procedure-driven execution is disciplined but brittle to unmodeled contingencies and requires more human procedural intervention;
- a generic agent harness is flexible but can make decisions inconsistent with mission-level space constraints;
- prompt-only space awareness improves semantic behavior but does not provide an independent mission-state or assurance boundary;
- the proposed runtime preserves much of the agent's flexibility while reducing mission-invalid behavior and human coordination burden.

This should be treated as a hypothesis to test, not a result to assume.

## 6.3 Figures that should exist if the evidence supports them

1. **Operating-model diagram:** procedure-driven operations versus agentic mission runtime.
2. **System architecture:** foundation-model reasoning, mission runtime, space context, capabilities, safety/FDIR, and distributed compute hierarchy.
3. **Mission trace example:** one complete long-horizon mission showing reasoning, capability calls, failures, verification, and state updates.
4. **Autonomy–trustworthiness comparison:** mission accomplishment versus intervention and invalid/unsafe execution.
5. **Space-condition robustness:** performance under communication/compute/environment variation.
6. **Ablation figure:** which runtime mechanisms materially contribute.
7. **Traceability example:** structured reconstruction of a consequential mission transition.

## 6.4 Tables that should exist

- comparison of related systems and which mission-runtime properties they support;
- capability set shared across all baselines;
- mission scenarios and perturbation classes;
- primary quantitative comparison;
- failure-mode analysis;
- ablation results;
- communication/compute overhead and dependence.

---

# 7. Discussion

## 7.1 What changes in the mission operating model

The central discussion should return to the original problem:

> The contribution is not that an LLM can call a robot tool, but that a lunar robot can be operated at a higher level of intent because a mission runtime continuously coordinates specialized autonomy capabilities and preserves the operational discipline required in aerospace systems.

## 7.2 Relationship to classical space executives

The proposed approach should be framed as an extension of, not a rejection of, the spacecraft-autonomy tradition.

Classical executives contribute:

- explicit state;
- bounded execution;
- resource awareness;
- FDIR;
- trusted operational semantics.

Foundation-model reasoning contributes:

- semantic mission interpretation;
- open-ended decomposition;
- flexible information seeking;
- diagnosis and response to cases not completely enumerated in advance;
- dynamic selection among heterogeneous capabilities.

The research question is whether these strengths can be combined coherently.

## 7.3 Why the architecture is space-specific

The final discussion must demonstrate that the system would behave differently if deployed as a terrestrial LAN robot. Space communication geometry, intermittent service availability, distributed compute, lunar environmental state, resource limits, authority, and FDIR must all influence runtime behavior in the experiments.

## 7.4 Moon-to-Mars extrapolation

Mars should be discussed only as an extrapolation. Greater communication delay and longer disconnection intervals strengthen the motivation for local mission-level autonomy, but the paper should not claim Mars validation.

## 7.5 Limitations

Expected limitations to discuss explicitly:

- simulation cannot reproduce all lunar physical/environmental effects;
- foundation-model behavior remains stochastic and model-dependent;
- the mission runtime cannot guarantee correctness of faulty perception or incomplete mission rules;
- terrestrial compute hardware is not space-qualified;
- multi-robot coordination may remain outside the first implementation;
- full certification is outside the scope of the paper;
- the first implementation may use simplified power/thermal models rather than spacecraft-grade digital twins.

---

# 8. Conclusion — intended message

The conclusion should return to the operation-model transition:

> Future lunar robotics is increasingly limited not only by individual perception, planning, and control capability, but by how those capabilities are organized into a mission-level autonomous system. A Space Robotics Agent Harness offers a route from command-intensive, procedure-driven operations toward mission-intent-driven autonomy by combining foundation-model reasoning with existing conventional and learned robotics capabilities, while retaining space-native communication, resource, authority, safety, FDIR, verification, and traceability requirements as part of the runtime itself.

The final conclusion must be narrowed to exactly what the experiments demonstrate.

---

# Research boundaries that must not drift

This work is **not**:

- another skill library or skill-registration paper;
- a renamed version of the previous SELENE Atomic Action Contract work;
- a generic LLM tool-calling framework;
- a new VLA architecture;
- a generic runtime-safety filter;
- a communication-planning paper;
- a power/thermal optimization paper;
- a cloud-edge deployment paper;
- a paper whose thesis is only communication continuity or future viability.

These are components, constraints, or related problems. The scientific center remains:

> **reorganizing fragmented space-robotics autonomy into a trustworthy, space-native, mission-intent-driven agentic runtime.**

---

# Literature anchors for the future manuscript

## Classical space autonomy

- Muscettola et al., *Remote Agent: To Boldly Go Where No AI System Has Gone Before*.
- Verma et al., PLEXIL / Universal Executive.
- Chien et al., ASPEN / CASPER / EO-1 Autonomous Sciencecraft series.
- Estlin et al., AEGIS automated science targeting.
- Chi et al., *Embedding a Scheduler in Execution for a Planetary Rover*.
- Mars 2020 Onboard Planner / MEXEC publications and operations reports.
- ERGO planetary/orbital autonomy framework.
- ISAAC autonomous caretaking work.

## Agentic and physical-agent systems

- OpenAI, *Unrolling the Codex Agent Loop*.
- Anthropic, Claude Code / Agent SDK documentation.
- OpenRAL.
- Inspect Robots.
- Show-Harness.
- RoboClaw.
- RoboHarness.
- Physical Agentic AI.
- RoboOS.
- ROSA / RAI.
- hierarchical VLA orchestration studies.

## Trustworthy autonomy

- NASA Autonomous Systems Taxonomy.
- NASA autonomy V&V roadmap.
- Runtime Assurance for autonomous aerospace systems.
- STARS.
- ECSS machine-learning handbook / safety-cage guidance.
- lunar surface autonomy certification literature.
- reliability-asymmetric spacecraft autonomy.
- robot-agent runtime governance, plan verification, and policy-failure monitoring literature.

## Space communications, compute, and lunar operations

- LunaNet Interoperability Specification.
- Lunar Communications Relay and Navigation Systems (LCRNS) reference architecture and constellation material.
- Delay/Disruption Tolerant Networking.
- NASA High Performance Spaceflight Computing.
- in-space edge-computing demonstrations.
- ASTREA and related space AI demonstrations.
- lunar south-pole illumination/communication-aware planning literature.
- Space Robotics Bench.

## Boundary with previous work

- Huang et al., *Toward Self-Evolving Lunar Robotic Autonomy Through Contract-Governed Skill Registration*, Astronautics, 2026.

The previous work establishes contract-based representation, registration, and dispatch of heterogeneous skills. The new paper must move from the question of **how capabilities enter a repertoire** to **how the complete autonomy stack is coordinated continuously at mission level under lunar operational constraints**.

