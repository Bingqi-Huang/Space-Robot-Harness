# Execution Plan — Space Robotics Agent Harness

**Purpose:** implementation and experiment plan for Codex / Claude Code / human developers  
**Companion document:** `RESEARCH_CONTENT_space_robotics_agent_harness.md`  
**Rule:** this document describes how to build and evaluate the research system. It must not invent fixed success gates, arbitrary numerical thresholds, training-step counts, or stage-entry criteria before empirical evidence exists.

---

# 0. Operating rules for the coding agent

1. **Do not redesign the research question.** The scientific goal is fixed: reorganize fragmented space-robotics autonomy into a trustworthy, space-native, mission-intent-driven agentic runtime.
2. **Reuse before implementing.** Inspect the current upstream implementation before adding new code. Prefer adapters and sidecar packages over forks of OpenRAL or SRB.
3. **Do not duplicate OpenRAL features.** OpenRAL already contains typed reasoner tool calls, `MissionState`, rSkill execution, world-state aggregation, reward/progress query tools, bounded replanning, observability, and safety infrastructure. Extend only where the space-mission requirement is genuinely absent.
4. **Do not assume roadmap features are production-ready.** OpenRAL documentation marks some safety-kernel and WAM elements as partial/planned. Code only against functionality verified in the checked-out revision.
5. **Do not hard-code scientific thresholds.** Resource margins, retry policies, escalation rules, mission deadlines, and statistical thresholds must be configuration-driven and derived later from mission assumptions or experimental analysis.
6. **Do not fabricate aerospace values.** Communication geometry, lunar illumination, orbital contacts, and mission resources must come from explicit datasets/models/configuration with provenance.
7. **Keep the foundation model away from direct motor authority.** Preserve OpenRAL's typed reasoner → skill-runner → safety separation.
8. **Every experimental run must be reproducible.** Save git revisions, simulator seed/configuration, model/provider configuration, mission specification, space-context profile, capability registry, trace/log locations, and final metrics.
9. **Build mechanism-first, not benchmark-first.** Do not add task variety unless it exercises a distinct runtime mechanism.
10. **No paper-result language in code or reports until measured.** Log observed behavior; do not label a mechanism superior before analysis.

---

# 1. Upstream systems that must be used, not reimplemented

## 1.1 OpenRAL — primary physical-agent runtime base

Repository: `OpenRAL/openral`

Current upstream architecture relevant to this project:

- `python/core/` (`openral_core`): normative Pydantic schemas and typed contracts;
- `python/world_state/` + world-state ROS package: `WorldStateAggregator`, tf2-aware snapshots, staleness handling, detected-object integration;
- `python/rskill/` + `packages/openral_rskill_ros/`: rSkill packaging/loading and `/openral/execute_rskill` action execution path;
- `python/reasoner/` (`openral_reasoner`): transport-agnostic `ReasonerCore`, tool palette, mission/task ledger, replanning logic;
- `packages/openral_reasoner_ros/`: ROS 2 reasoner node and typed tool dispatch;
- `packages/openral_safety/` and `cpp/openral_safety_kernel/`: safety supervisor/kernel; treat exact current status as revision-dependent and inspect before use;
- `python/observability/`: OpenTelemetry-based tracing and logging;
- `python/sim/`: simulation/evaluation adapters supported by OpenRAL itself.

Important existing behavior that this project should preserve:

- the S2 reasoner is event-driven and emits one typed `ReasonerToolCall` per reasoning step;
- the reasoner has no direct actuation authority;
- `ExecuteRskillTool` dispatches to `/openral/execute_rskill`;
- the tool palette is built from installed, capability-compatible rSkills;
- read-only query tools already exist for scene understanding, object localization, spatial recall, and task progress;
- `MissionState` already stores a sequential mission task ledger and is modified by `decompose_mission`;
- OpenRAL already records reasoner behavior with OTel spans;
- low-level safety is intentionally independent of the reasoner.

**Implementation implication:** the research should add a space-mission runtime around/alongside the existing OpenRAL mission/reasoner path rather than replacing it.

## 1.2 Space Robotics Bench (SRB) / Isaac Lab — primary simulation base

Repository: `AndrejOrsula/space_robotics_bench`

Capabilities to use directly:

- extraterrestrial/lunar simulation domains;
- Isaac Sim parallel simulation;
- Gymnasium-compatible environments;
- procedural generation and domain randomization;
- fixed-base and mobile-manipulation task templates;
- existing tasks such as sample collection, excavation, peg-in-hole, screwdriving, and solar-panel assembly;
- `_ground_manipulation` template for mobile-manipulator scenarios;
- ROS 2 / Space ROS interface;
- dynamic ROS bridge that exposes environment state, sensors, control, and task-specific signals;
- Hydra-based environment configuration.

Primary integration route:

- run SRB as the physical environment;
- use its ROS 2 interface to expose robot state, sensors, and control to the OpenRAL graph;
- avoid modifying Isaac Sim or SRB core unless a mission-specific task primitive cannot be represented through normal SRB task extension.

## 1.3 Inspect Robots — evaluation framework to assess, not automatically adopt as runtime

Repository: `robocurve/inspect-robots`

Useful features:

- explicit separation of `Task`, `Policy`, `Embodiment`, and `Scorer`;
- Isaac Lab and ROS embodiments;
- agent and VLA policies;
- auditable logs and configuration capture;
- Rerun visualization;
- compatibility checking and standard scoring.

Recommended role:

- inspect its log/scorer/task abstractions and reuse ideas or adapters where useful;
- consider using it for independent evaluation/log normalization if it can wrap the final OpenRAL+SRB experiment without distorting the runtime;
- do not force it into the control path if OpenRAL already provides the runtime behavior needed by the paper.

## 1.4 Aerospace data/services

Prefer established libraries and public mission data:

- NAIF SPICE / SpiceyPy for Sun/Earth/Moon geometry and time;
- published lunar DEM/topography only if needed for the selected mission;
- LunaNet/LCRNS architecture and reference contact/relay material for communication scenarios;
- existing orbital-analysis toolchains for relay visibility/contact generation rather than a custom orbit propagator;
- Linux traffic-control/network emulation or an application-level link proxy for reproducing time-varying availability, delay, and bandwidth;
- ROS 2 / rosbag2 for robot/system-level capture.

---

# 2. Repository strategy

Create a **separate research repository** rather than developing directly inside OpenRAL or SRB.

Suggested repository root:

```text
space_robotics_agent_harness/
├── README.md
├── pyproject.toml
├── uv.lock / requirements as appropriate
├── configs/
├── missions/
├── space_runtime/
├── space_context/
├── openral_ext/
├── srb_ext/
├── network/
├── experiments/
├── evaluation/
├── scripts/
├── tests/
├── docs/
└── artifacts/
```

Treat OpenRAL and SRB as version-pinned external dependencies/submodules/workspaces. Record exact commits used for every experimental campaign.

Do not fork upstream unless an integration bug cannot be solved with a sidecar or adapter. If an upstream modification is unavoidable:

- keep it minimal;
- document why the public API is insufficient;
- isolate the patch;
- upstream it when possible;
- keep the research mechanism in this repository.

---

# 3. Target runtime integration

## 3.1 Control/data path

The target runtime path is:

```text
Mission instruction
    ↓
OpenRAL ReasonerCore / reasoner ROS node
    ↓ typed ReasonerToolCall
Space mission decision layer
    ↓ admitted / deferred / reformulated / escalated intent
OpenRAL rSkill dispatch
    ↓
OpenRAL safety + robot-control path
    ↓
SRB ROS 2 robot / later LunarBot
    ↓
observations + execution feedback
    ↓
OpenRAL WorldState + task-progress/scene queries
    ↓
Space mission state / verification
    ↓
next reasoner context
```

The project must preserve OpenRAL's existing typed and safety boundaries.

## 3.2 Integration point inside OpenRAL

Do **not** intercept raw motor actions.

The preferred insertion point is the reasoner-to-effectful-tool dispatch boundary, before `ExecuteRskillTool` becomes an `/openral/execute_rskill` action goal.

Reason:

- this is where semantic intent is still visible;
- low-level safety remains independent;
- existing rSkill packaging is retained;
- the mission runtime can reject/defer/escalate a mission-level action without reimplementing controllers;
- query tools can remain read-only and available to the reasoner.

Implementation should first inspect the current `openral_reasoner_ros.reasoner_node` tool-dispatch path and determine whether one of these patterns is cleaner:

1. **sidecar mission-decision service:** reasoner node calls a new ROS service/action before dispatching an effectful tool;
2. **tool-dispatch wrapper:** an extension package wraps effectful tool dispatch while leaving query and memory tools untouched;
3. **upstream-compatible dispatcher hook:** if OpenRAL already exposes a stable hook/protocol in the checked-out revision, implement against that instead of patching the node.

Select the least invasive option after code inspection. Do not decide by assumption.

---

# 4. New research components to implement

The project should implement only the mechanisms absent from generic OpenRAL that are necessary to turn it into the paper's space-native mission runtime.

## 4.1 `space_runtime`: authoritative mission runtime

Purpose: maintain mission-critical state independently from the LLM context and OpenRAL's current sequential task text ledger.

Responsibilities:

- mission objective and priority representation;
- current mission phase/objective;
- verified completed/pending transitions;
- unresolved anomalies;
- active execution reference;
- authority state;
- mission-relevant resource/health summary;
- evidence references for completed transitions;
- reconciliation state after model/service reconnection;
- persistence across reasoner restart/model change.

Do not duplicate full robot world state. Store references/snapshots only where mission continuity requires them; robot kinematics, detections, transforms, and freshness remain owned by OpenRAL WorldState.

Suggested modules:

```text
space_runtime/
├── schemas.py              # mission-runtime Pydantic models
├── mission_store.py        # persistent authoritative state
├── reducer.py              # event -> state transition
├── context_builder.py      # builds reasoner-facing mission context
├── decision.py             # mission-level disposition of effectful proposals
├── verification.py         # evidence-backed state advancement
├── authority.py            # mission authority/policy evaluation
├── reconciliation.py       # reconnect / stale-context handling
└── events.py               # typed mission events
```

### State-management design

Use an event-driven reducer pattern rather than allowing arbitrary mutation from multiple ROS callbacks.

Examples of typed events:

- operator mission received;
- task/subtask proposed;
- execution requested;
- execution accepted/deferred/rejected/escalated;
- execution started/finished/failed;
- verifier result received;
- FDIR event received;
- communication state changed;
- compute service state changed;
- resource state changed;
- authority changed;
- reasoner/model changed;
- human decision received.

Persist the mission state and enough event history for deterministic replay/debugging.

Do not use LLM-generated prose as the canonical state representation.

## 4.2 `space_context`: aerospace operational context service

Purpose: produce a typed, time-indexed summary of the lunar operating environment used by the mission runtime.

Suggested modules:

```text
space_context/
├── clock.py
├── geometry.py
├── illumination.py
├── earth_visibility.py
├── relay_contacts.py
├── link_state.py
├── resources.py
├── compute_state.py
├── robot_health.py
└── service_node.py
```

### 4.2.1 Mission clock

Maintain mission epoch/time independently from wall-clock simulation time. Support accelerated or replayed timelines if needed for contact/illumination experiments.

### 4.2.2 Sun/Earth geometry

Use SPICE/SpiceyPy and documented kernels. Required outputs depend on selected experiment but may include:

- Sun direction/elevation at the lunar site;
- Earth direction/elevation;
- geometry transitions relevant to illumination/visibility;
- timestamps of upcoming state changes.

Keep geometry computation outside the LLM.

### 4.2.3 Surface visibility / terrain effects

If the chosen mission requires terrain occlusion, use SRB terrain/DEM information or a documented lunar terrain source to determine local horizon/line-of-sight. Do not claim terrain-aware DTE if only body-level occultation is modeled.

### 4.2.4 Relay contact timeline

Use published LCRNS/reference relay information or another documented lunar relay scenario.

Preferred architecture:

- generate contact windows offline using a trusted orbital-analysis tool;
- save a provenance-rich contact schedule;
- runtime reads/query the schedule rather than integrating orbital dynamics during each agent tick.

This keeps orbital mechanics real enough to influence the experiment without turning the project into an orbit-propagation study.

### 4.2.5 Resource service

Start with mission-level resource summaries needed by the selected scenarios:

- battery/energy state;
- thermal operational state if represented;
- storage/data budget where relevant;
- subsystem health;
- current capability degradation.

Resource models should be simple, transparent, and replaceable. They are context/constraints, not a new optimizer.

### 4.2.6 Compute availability

Represent reasoning/services by location and current availability, e.g.:

- onboard/local;
- surface/LAN;
- remote/Earth.

Track at least:

- reachable/unreachable;
- observed/request latency;
- capability/model identity;
- whether the current mission authority permits use;
- whether service state is stale or unknown.

Do not invent a learned router initially.

## 4.3 Mission-level decision layer

Purpose: determine how an effectful reasoner proposal should proceed in the current mission context.

Input:

- typed OpenRAL effectful tool call;
- authoritative mission state;
- OpenRAL world-state summary/reference;
- space context;
- authority/policy;
- active FDIR/degradation state;
- capability/service availability.

Output should be a small typed disposition set such as:

- execute;
- defer/wait;
- return to reasoner for replanning/additional observation;
- escalate/request higher authority.

Avoid embedding arbitrary numeric thresholds in code. Evaluation logic should read mission policy/resource configuration and explain the reason for each disposition.

Every disposition must emit a structured trace event.

Important distinction:

- this layer decides **mission appropriateness**;
- OpenRAL safety decides **physical-action admissibility**.

Do not merge these concerns.

## 4.4 Verification layer

Purpose: prevent mission-state progress from being determined solely by the language model or by a controller's nominal completion flag.

Reuse existing OpenRAL sources where available:

- `query_task_progress` / reward monitor;
- scene VLM query;
- world-state object/pose updates;
- rSkill action result;
- navigation goal state;
- FDIR/telemetry.

Add mission-specific verifiers only when the mission objective requires a condition not represented upstream.

A verifier should produce:

- condition/result;
- evidence source;
- timestamp/state version;
- confidence/quality metadata if available;
- reference to raw observation/log rather than embedding all raw data in mission state.

Mission completion/subtask advancement occurs through verifier events.

## 4.5 Distributed reasoner adapter

Purpose: allow reasoning to be available at different compute tiers while preserving a single mission state.

Do not implement a new model-serving system. Use provider/OpenAI-compatible endpoints supported by OpenRAL or a thin adapter.

Implement a service registry containing:

- model/service identifier;
- location category;
- connectivity status;
- endpoint information;
- measured latency/availability;
- authority/capability metadata.

Reasoner selection can initially be policy-based and configurable. The research question is not learning an optimal model router.

### Context transfer rule

Never use an old remote chat transcript as the authoritative resume mechanism.

Whenever reasoning moves to another endpoint or reconnects, reconstruct the relevant context from:

- authoritative mission state;
- current verified world state;
- current space context;
- active faults;
- available capabilities;
- relevant recent evidence/events.

This is the mechanism to test against naive conversation/history continuation.

## 4.6 Trace and evidence store

Integrate with OpenRAL's existing OpenTelemetry spans rather than create a separate opaque logger.

Add mission-runtime spans/events that can be correlated with:

- reasoner tick;
- selected tool/rSkill;
- mission disposition;
- space-context snapshot/version;
- execution result;
- verifier result;
- mission-state transition;
- model/service switch;
- human intervention.

Also retain experiment-level artifacts:

- config;
- seeds;
- model/provider versions;
- upstream git revisions;
- mission definition;
- link/contact profile;
- simulator logs/rosbags where enabled;
- final normalized metrics.

---

# 5. OpenRAL integration work package

## 5.1 First task: pin and map the actual upstream revision

Before writing extension code:

- clone OpenRAL;
- record commit hash;
- run its documented test suite and a minimal simulation/deploy workflow;
- inspect `docs/architecture/repo-state-map.html`, `docs/reference/reasoner.md`, `docs/architecture/repo-map.md`, and the relevant ROS package READMEs;
- trace `ReasonerCore.tick` through `ReasonerToolCall` serialization to ROS dispatch;
- trace `ExecuteRskillTool` through `/openral/execute_rskill` to the current skill runner and safety path;
- locate the current `MissionState` and `DecomposeMissionTool` schema/implementation;
- identify stable extension hooks before modifying anything.

Write a short `docs/openral_integration_notes.md` with exact source paths and APIs for the pinned revision. This note is implementation documentation, not paper content.

## 5.2 Confirm what is shipped versus planned

OpenRAL documentation currently distinguishes shipped, partial, and planned components. Verify the checked-out code rather than relying only on prose.

Specifically confirm:

- current C++ safety-kernel integration status;
- current collision/freshness checks;
- current mission-state implementation;
- current replanning ladder behavior;
- current WAM availability;
- current reasoner provider/model interface;
- IsaacSim and ROS integration paths.

Do not design experiments around a planned component unless it becomes available and stable during the project.

## 5.3 Extension principle

Prefer a new ROS/package namespace owned by this research, for example:

```text
openral_ext/
├── space_mission_bridge/
├── space_context_bridge/
└── reasoner_dispatch_bridge/
```

Keep upstream topic/action/service contracts unchanged where possible.

---

# 6. SRB integration work package

## 6.1 Pin and validate SRB

- clone SRB with required submodules;
- record commit and Isaac Sim/Isaac Lab environment versions;
- use the recommended containerized development path unless the existing research machine already has a stable native setup;
- verify `srb ls`;
- run an existing manipulation task;
- run `_ground_manipulation`;
- verify ROS 2 interface publication/control in both passive and active workflow modes;
- record actual topic/service/action names generated for the selected environment.

Create `docs/srb_integration_notes.md` based on the checked-out revision.

## 6.2 Choose the robot embodiment pragmatically

The first scientific campaign should use an SRB-supported mobile-manipulator combination with the least integration work.

Do not require the LunarBot model before the runtime is validated.

Selection criteria:

- mobile manipulation supported by `_ground_manipulation`;
- usable RGB/depth and robot-state observations;
- compatible navigation/manipulation control interface;
- straightforward ROS 2 exposure;
- ability to place mission assets and task signals in the environment.

Later, add a LunarBot embodiment/adapter only if it strengthens the paper without delaying the core experiments.

## 6.3 Build long-horizon mission environments by composition

Do not create a new lunar simulator. Create mission scenarios by composing SRB assets/tasks/templates.

Candidate sources:

- `_ground_manipulation` as base;
- inspection targets / service-site assets;
- existing screwdriving, peg-in-hole, solar-panel-assembly, or sample-handling assets where appropriate;
- SRB terrain/domain configuration for lunar gravity and visuals.

The long-horizon mission wrapper should expose mission-relevant state and verifier hooks but should not hard-code the desired action sequence.

Suggested structure:

```text
srb_ext/
├── missions/
│   ├── service_site/
│   └── logistics_service/
├── assets/
├── observations/
├── events/
└── ros_adapters/
```

Follow SRB's task-extension pattern: duplicate the appropriate template, then modify scene, observation space, task-specific state/reward/termination only as required.

## 6.4 Mission scenario A: infrastructure inspection and maintenance

Build one service area containing:

- navigable approach region;
- multiple visually distinguishable candidate components/subsystems;
- at least one inspectable fault state;
- one or more physical operations required for restoration;
- a verifiable final condition.

The operator instruction should specify the mission objective, not the action sequence.

Capabilities should include a mix of:

- navigation;
- observation/scene query;
- object localization;
- manipulation planning or a VLA/learned policy;
- verification;
- fault handling.

## 6.5 Mission scenario B: logistics and servicing under contingency

Build a mission requiring:

- locate/retrieve a required item or tool;
- transport/navigation;
- service/manipulation at another location;
- final verification.

The scenario framework must support controlled variations such as:

- changed item location;
- blocked/changed route;
- unavailable capability;
- communication interruption;
- perception degradation;
- manipulation failure;
- changed service/fault state.

Perturbations must be independently switchable for controlled experiments.

---

# 7. Space-context generation work package

## 7.1 Define scenario metadata

Each experimental lunar mission scenario should have a small mission metadata file containing provenance and mission context, for example:

```yaml
site:
  name: ...
  body_fixed_location: ...
mission_epoch: ...
geometry_sources: ...
relay_scenario: ...
resource_profile: ...
compute_topology: ...
authority_profile: ...
```

Values must come from documented assumptions/data, not be buried in code.

## 7.2 SPICE pipeline

Create scripts that:

- download/locate approved NAIF kernels;
- validate kernel coverage for the chosen mission epoch;
- compute Sun/Earth geometry at the mission site;
- export a compact time-indexed profile for simulation runs;
- store source/kernel/version metadata alongside the profile.

Prefer precomputation for repeatability. Runtime can query/interpolate the profile.

## 7.3 Relay/contact pipeline

Use one documented relay scenario.

Pipeline:

1. obtain reference orbital states/ephemeris from a citable source;
2. compute relay-to-surface and relay-to-Earth visibility/contact using a trusted external library/tool;
3. export contact intervals/state profile;
4. validate a subset manually/visually;
5. save provenance and generation script.

Do not implement orbital mechanics from scratch.

## 7.4 Link emulator

Build an interface that converts the current contact/profile state into actual service behavior seen by the agent.

Potential implementation methods:

- Linux `tc/netem` for latency/loss/bandwidth shaping where processes communicate over real sockets;
- a proxy/gateway process that can make a remote model/service unavailable, delayed, or bandwidth-limited according to mission time;
- ROS 2 namespace/network isolation where appropriate.

Use the simplest method that makes link state affect real runtime behavior rather than only metadata.

## 7.5 Resource/health profiles

Represent resource and health behavior through configurable services. Begin with transparent models linked to actual task execution events where practical.

Examples:

- navigation/manipulation consumes energy according to configured or measured activity costs;
- compute calls can account for compute/communication usage if this becomes experimentally relevant;
- simulated faults change capability availability;
- subsystem health is published as typed events to the mission runtime.

Do not tune these models to force the proposed system to win.

---

# 8. Capability integration work package

## 8.1 Inventory available capabilities

Before adding new algorithms, build an inventory table from the pinned OpenRAL/SRB revisions:

| Needed mission capability | Existing upstream implementation | Integration path | Missing work |
|---|---|---|---|
| navigation | OpenRAL Nav2 / SRB ROS | rSkill/ROS action | inspect |
| scene query | OpenRAL scene VLM | query tool | inspect |
| object locate | OpenRAL detector tools | query tool | inspect |
| manipulation planning | MoveIt/cuMotion/OMPL depending revision | rSkill/ROS action | inspect |
| VLA | supported OpenRAL rSkill adapters | rSkill | choose only if useful |
| progress verification | Robometer/task-progress + simulator state | query/verifier | map mission conditions |
| FDIR | upstream failure topics + custom scenario faults | ROS events | mission-level integration |

Do not select a VLA because the paper “needs AI.” Use it only where learned manipulation contributes a meaningful heterogeneous-capability case.

## 8.2 Capability metadata for mission runtime

Do not change the rSkill format unless necessary. Maintain research-side metadata keyed by capability/rSkill ID for space-mission properties not represented upstream, such as:

- requires remote service;
- usable offline;
- authority class;
- relevant resource/service dependencies;
- compatible degraded modes;
- verification method.

If OpenRAL has a clean extensible field mechanism in the pinned revision, use it. Otherwise keep this metadata in the research runtime to avoid contaminating upstream skill definitions.

---

# 9. Reasoner/context work package

## 9.1 Start with an unmodified generic harness baseline

Before adding space-runtime mechanisms, run the chosen mission with:

- OpenRAL's normal mission decomposition;
- normal world state;
- normal typed tools;
- no special mission-level space enforcement.

Capture exactly how it fails or succeeds under nominal conditions.

This becomes both a baseline and a diagnostic for what the new runtime actually needs.

## 9.2 Add space information as prompt-only baseline

Create a context provider that renders the same space-operational data into the reasoner situation report without independent enforcement.

This baseline is essential. It answers whether the entire contribution could be replaced by prompt engineering.

Keep the underlying data identical to the proposed system.

## 9.3 Proposed context builder

The proposed system should construct a compact reasoner context containing only mission-relevant information:

- mission goal/current objective;
- verified progress;
- unresolved issues;
- relevant world-state summary;
- current communication/compute availability;
- relevant resource/health state;
- current authority/policy cues;
- available capabilities;
- relevant recent evidence/events.

Avoid dumping raw telemetry or entire mission history.

Context selection rules should be explicit and testable, not hidden prompt text.

## 9.4 Multi-endpoint reasoning

Configure multiple reasoner endpoints/models only after the single-endpoint runtime works.

Use OpenRAL's provider/model abstraction where possible. The network/link emulator controls which endpoint is reachable.

Log all model changes and reconstruct context from authoritative state on every switch.

---

# 10. Trustworthiness/FDIR integration work package

## 10.1 Preserve low-level safety

Do not disable, bypass, or weaken OpenRAL safety for experimental convenience.

If an action is physically rejected by safety, propagate the failure into the mission runtime as an execution event.

Do not reinterpret safety rejection as task success.

## 10.2 Mission authority

Define mission authority through configuration/data rather than hidden Python conditionals.

Examples of qualitative authority classes:

- autonomously permitted;
- permitted under stated mission conditions;
- requires confirmation/escalation;
- prohibited.

The exact content depends on the selected mission and should be justified as an experimental assumption, not presented as universal lunar policy.

## 10.3 FDIR event flow

Map OpenRAL failure topics and simulated subsystem faults into mission-runtime events.

The mission runtime should update capability availability and reasoning context when a fault occurs.

Do not build a new diagnosis algorithm unless the selected experiment genuinely requires one. The paper contribution is mission-level integration of fault information.

## 10.4 Verification mapping

For every mission transition, define its evidence source in a mission specification file.

Example categories:

- pose/region condition;
- object state in simulator;
- perception/scene classification;
- rSkill result plus independent state observation;
- task-progress monitor;
- FDIR cleared state;
- human confirmation.

The verifier implementation should be deterministic where direct simulator/robot state is available, and learned only where semantic perception is genuinely required.

---

# 11. Baseline implementation

All baselines must share the same capabilities and environment where possible.

## 11.1 Procedure-driven baseline

Implement the mission as a behavior tree, state machine, or explicit procedure using the same low-level capabilities.

Design principle:

- encode nominal task flow and reasonable predefined recovery branches;
- do not deliberately make it weak;
- when an unencoded condition occurs, use the system's defined fallback/human intervention path.

Document what is pre-engineered so human engineering effort is transparent.

## 11.2 Generic OpenRAL baseline

Use the upstream reasoner, world state, mission task ledger, typed tools, and safety with minimal space-specific additions required only to run the simulator.

Do not provide independent mission-runtime use of space context.

## 11.3 Prompt-only space-aware baseline

Provide the same space-context variables to the reasoner in textual/structured context, but bypass the proposed independent mission-state decision semantics.

This baseline must still retain low-level OpenRAL safety.

## 11.4 Proposed system

Enable:

- authoritative mission state;
- dynamic context builder;
- space context service;
- mission-level proposal disposition;
- FDIR/authority integration;
- independent outcome verification;
- distributed reasoner reconciliation where tested;
- trace/evidence linkage.

---

# 12. Experiment runner architecture

Create one experiment runner that can instantiate all baselines through configuration rather than separate scripts.

Suggested layout:

```text
experiments/
├── runner.py
├── configs/
│   ├── baseline_procedure.yaml
│   ├── baseline_openral.yaml
│   ├── baseline_prompt_space.yaml
│   └── proposed.yaml
├── scenarios/
├── perturbations/
├── launch/
└── manifests/
```

A run manifest must include:

- baseline/method;
- mission ID;
- scenario/perturbation configuration;
- random seeds;
- model/provider identifiers;
- OpenRAL/SRB git revisions;
- space-context profile IDs;
- capability registry snapshot;
- network profile;
- log/trace locations.

Do not make experiment scripts contain method-specific hidden constants.

---

# 13. Experimental campaign design

Do not begin with massive sweeps. First establish that every condition produces interpretable traces, then scale the repetitions needed for statistical analysis.

## 13.1 Nominal mission campaign

Purpose:

- verify the entire mission loop;
- characterize each baseline under normal conditions;
- identify accidental infrastructure failures before adding research perturbations.

Required outputs:

- mission completion trace;
- capability calls;
- verifier events;
- human/escalation events;
- communication/model calls;
- state-transition log.

## 13.2 Mission-openness campaign

Vary mission conditions that require non-predefined reasoning:

- changed object/target arrangement;
- unexpected state requiring additional inspection;
- alternate action ordering;
- unavailable preferred capability;
- recoverable manipulation/navigation failure.

Goal: compare procedure-driven versus agentic coordination.

## 13.3 Space-communication / distributed-intelligence campaign

Use mission-derived communication/contact profiles to vary:

- remote model availability;
- link interruptions and reconnection;
- relay/DTE availability;
- link delay/bandwidth conditions;
- availability of surface versus onboard reasoners.

Compare:

- generic harness behavior;
- prompt-only awareness;
- proposed authoritative state/context reconstruction.

Explicitly record stale-context, duplicate-action, skipped-action, and conflicting-action events.

## 13.4 Environmental/resource-context campaign

Vary lunar operational context represented by the mission scenario:

- illumination/shadow condition;
- resource margin;
- terrain/mobility difficulty;
- compute/data availability.

The purpose is to test whether these variables change runtime decisions appropriately, not to optimize them globally.

## 13.5 Trustworthiness campaign

Create controlled cases where the reasoner produces or is induced toward a proposal that is semantically plausible but inconsistent with mission state/authority/FDIR/resource context.

Examples:

- repeat an already completed transition;
- act on a stale target state;
- use an unavailable service;
- continue after a fault that changes allowed capability;
- claim success without evidence;
- choose an operation requiring higher authority.

Do not force hidden adversarial prompts into only one baseline. Perturbations must be applied consistently.

## 13.6 Failure/recovery campaign

Inject explicit simulator or service failures:

- manipulation failure;
- navigation blockage/failure;
- perception degradation;
- remote service unavailable;
- model endpoint failure;
- subsystem health event.

Measure how mission state and human intervention evolve after the failure.

## 13.7 Ablation campaign

Only after the full method is stable, disable one mechanism at a time:

- authoritative mission state;
- independent verification;
- independent use of space context;
- FDIR/authority integration;
- reconciliation/context rebuild;
- dynamic context selection.

Ablations should use the same scenario/config seeds as the full method.

---

# 14. Metrics and post-processing

Implement metrics from logs/traces rather than manual annotation wherever possible.

## 14.1 Mission metrics

- mission success/failure;
- objective/subobjective completion;
- execution duration / idle time;
- recovery episodes;
- unfinished/aborted mission state.

## 14.2 Human-autonomy metrics

- human intervention count;
- manually supplied subtask count;
- escalation/clarification count;
- autonomous mission-transition fraction;
- command granularity representation;
- human decision time if measurable.

## 14.3 Trustworthiness metrics

Create explicit event classifiers for:

- mission-invalid action;
- authority violation;
- low-level safety violation/rejection;
- stale-state action;
- duplicate action;
- skipped required mission transition;
- unsupported mission-state advancement;
- continued execution after unresolved critical failure.

Do not infer these from LLM text alone; derive them from mission/event state where possible.

## 14.4 Communication/compute metrics

- local/surface/remote reasoning calls;
- service/model availability intervals;
- data transferred where measurable;
- waiting attributable to communication or remote inference;
- endpoint switching;
- operations completed while remote intelligence is unavailable.

## 14.5 Traceability metrics

For each consequential mission transition, check whether the trace includes:

- mission-state version;
- relevant space-context version;
- proposal/tool call;
- mission-level disposition;
- execution result;
- verifier/evidence reference;
- resulting mission-state transition.

Build an automated completeness checker.

---

# 15. Statistical analysis plan

Do not choose statistical tests or sample counts before seeing the metric distributions and experimental dependence structure.

The analysis pipeline should nevertheless support:

- per-scenario repeated trials;
- paired comparisons when the same scenario seed is used across baselines;
- confidence intervals via appropriate bootstrap or parametric methods after inspecting distributions;
- categorical failure-mode comparison;
- stratification by perturbation type and mission class;
- reporting both central tendency and variance;
- raw per-run trace retention for qualitative failure analysis.

Pre-register the final comparison procedure in the experiment configuration before the large final campaign to avoid selectively changing metrics after results appear.

---

# 16. LunarBot extension — after the simulation mechanism is stable

Do not make LunarBot a prerequisite for the scientific core.

Target purpose:

- demonstrate the same runtime on a real mobile manipulator;
- validate real ROS2 capability interfaces;
- reproduce the distributed compute hierarchy using onboard/local, LAN, and remote model endpoints;
- measure actual model/VLA/controller latency and selected failure modes;
- execute a representative segment of the long-horizon mission.

Integration strategy:

- preserve the same mission-runtime and reasoner interfaces;
- replace SRB capability endpoints with LunarBot ROS2 services/actions;
- reuse existing LunarBot navigation/manipulation/VLA infrastructure;
- apply the same external space-context and link-emulation service;
- do not build a lunar-analogue field environment solely for this paper.

Only include this in the final manuscript if it strengthens the claim without obscuring the main controlled experiments.

---

# 17. Test strategy

## 17.1 Unit tests

Cover:

- mission reducer/state transitions;
- persistence/replay;
- context construction;
- decision-layer dispositions;
- authority-policy parsing;
- contact-profile queries;
- SPICE profile loading/interpolation;
- verifier mappings;
- reasoner endpoint registry;
- reconciliation after service/model switches;
- trace completeness checks.

## 17.2 Integration tests

Cover:

- OpenRAL typed proposal → mission layer → rSkill dispatch;
- rejected/deferred proposal returns useful structured feedback to the reasoner;
- SRB ROS observations populate OpenRAL state correctly;
- execution results reach verifier and mission state;
- failure topics alter mission state/capability availability;
- network service availability follows the mission link profile;
- reasoner endpoint switch reconstructs current context correctly.

## 17.3 Replay tests

Given a recorded event log, mission state should be reproducible deterministically without calling the foundation model.

This is important for debugging and paper trace examples.

---

# 18. Development sequence

The development order should reduce uncertainty one integration boundary at a time. It is intentionally evidence-driven rather than controlled by arbitrary quantitative stage gates.

## Phase A — Upstream verification

- pin OpenRAL and SRB revisions;
- run upstream examples/tests;
- map actual reasoner/rSkill/world-state/safety interfaces;
- validate SRB ROS2 control and sensors;
- document shipped versus planned upstream functionality.

**Exit condition:** the team understands and can demonstrate the actual upstream execution path. No performance threshold is required.

## Phase B — Generic OpenRAL on SRB

- connect OpenRAL to one SRB mobile-manipulation environment;
- execute simple capability calls through the full reasoner/rSkill/safety/ROS path;
- collect traces.

**Exit condition:** a minimal multi-step robot mission can be executed and observed end-to-end using upstream mechanisms.

## Phase C — Long-horizon mission construction

- implement Mission A;
- implement Mission B only after Mission A's orchestration needs are clear;
- expose simulator truth needed for independent verification;
- create scenario perturbation controls.

**Exit condition:** mission objectives can be evaluated independently of the reasoner's textual claims.

## Phase D — Space-context service

- build SPICE geometry profiles;
- build relay/contact profile;
- build link emulator;
- add resource/compute/health context;
- validate that these states affect actual service availability or mission state.

**Exit condition:** space conditions are real runtime inputs rather than prompt-only metadata.

## Phase E — Authoritative mission runtime

- implement mission event schema/reducer/store;
- connect OpenRAL events and SRB verification;
- build dynamic reasoner context;
- add mission-level decision path;
- integrate authority and FDIR signals;
- link traces.

**Exit condition:** the foundation model can be restarted or changed without losing authoritative mission progress.

## Phase F — Baselines

- procedure-driven;
- generic OpenRAL;
- prompt-only space-aware;
- proposed runtime.

**Exit condition:** all baselines execute the same mission/capability set and produce normalized logs.

## Phase G — Controlled experiments

Run nominal and perturbation campaigns, inspect traces, fix infrastructure bugs, then freeze experiment configurations for the final campaign.

Do not change the proposed method in response to a single poor result without first determining whether the issue is implementation, experimental assumption, or genuine hypothesis falsification.

## Phase H — Ablations and analysis

Run only mechanism-relevant ablations. Generate plots/tables directly from experiment artifacts.

## Phase I — Optional LunarBot transfer

Add LunarBot only after the simulation study has a coherent scientific result.

---

# 19. Experiment artifacts and reproducibility

Every run directory should contain or reference:

```text
run_id/
├── run_manifest.yaml
├── mission_config.yaml
├── method_config.yaml
├── space_context_ref.yaml
├── network_profile_ref.yaml
├── capability_registry.json
├── model_config.json
├── openral_revision.txt
├── srb_revision.txt
├── events.jsonl
├── metrics.json
├── traces/
├── rosbag/           # when enabled
└── videos/           # selected/debug runs
```

Large raw sensor data may be stored separately; preserve stable references in the event/evidence log.

Create scripts that aggregate run artifacts into analysis tables without hand-editing CSV files.

---

# 20. What the coding agent must not do

- Do not create another Atomic Action Contract or skill-library abstraction as the core contribution.
- Do not replace OpenRAL's rSkill system unless an actual blocking issue is demonstrated.
- Do not bypass OpenRAL safety to make simulation easier.
- Do not create arbitrary lunar communication delays or orbital windows when citable geometry/infrastructure profiles can be generated.
- Do not implement a custom orbit propagator for this paper.
- Do not create a custom lunar physics engine.
- Do not train a new foundation model or VLA unless experiments later reveal a genuine capability gap that cannot be addressed with existing models.
- Do not set fixed performance gates, training steps, retry counts, confidence thresholds, or resource margins merely to define progress.
- Do not optimize parameters using the final test scenarios.
- Do not introduce mathematical notation into research reports unless it defines an actual implemented algorithm, objective, guarantee, or measured quantity.
- Do not silently change the paper's central research question when a subproblem becomes technically interesting.

---

# 21. Immediate concrete tasks for the next coding session

1. Create the new research repository skeleton and pin upstream OpenRAL/SRB revisions.
2. Produce `docs/openral_integration_notes.md` after tracing the current reasoner → `ReasonerToolCall` → `ExecuteRskillTool` → `/openral/execute_rskill` path and locating `MissionState`/world-state/safety interfaces.
3. Produce `docs/srb_integration_notes.md` after running `_ground_manipulation`, one existing manipulation task, and the ROS2 workflow; record actual topics/actions/services for the chosen environment.
4. Build a minimal ROS integration that lets OpenRAL invoke one SRB action and observe the result through the normal state path.
5. Define Mission A in a plain mission specification without yet implementing space constraints.
6. Run unmodified/generic OpenRAL on Mission A and save traces; document concrete failure modes and missing semantics.
7. Only then implement the first `space_runtime` schemas/events required by observed mission-level failures.
8. In parallel, create the SPICE/contact-profile preprocessing scripts and a typed `space_context` service, but do not connect them to mission decisions until their outputs are validated.
9. Add the prompt-only space-aware baseline before independent enforcement so the paper can isolate prompt information from runtime semantics.
10. Keep an ongoing `docs/research_findings.md` containing observed failure cases, design decisions, and links to the runs that motivated each mechanism. This document should drive later method refinement and prevent architecture from being designed by intuition alone.

---

# 22. Reference documentation reviewed for this plan

The execution design above is based on the current public documentation/code structure of:

- OpenRAL repository README and architecture overview;
- OpenRAL reasoner reference and ROS reasoner package documentation;
- OpenRAL repo map, core schemas, roadmap, and `CLAUDE.md` engineering rules;
- Space Robotics Bench introduction, basic usage, environment configuration, new-task guide, and ROS 2 / Space ROS integration documentation;
- Inspect Robots repository documentation for task/policy/embodiment/scorer separation and Isaac Lab/ROS evaluation paths.

Because all three projects are active, the coding agent must verify the pinned revision before relying on any API/path stated in this plan.

