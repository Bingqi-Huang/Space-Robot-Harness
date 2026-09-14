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
11. **Prerequisites are verified empirically before a dependent step starts.** A step whose preconditions are unmet (e.g. a mission run with no dispatchable manipulation capability, or no perception wired) is not started and its failure is not recorded as a "finding" — the precondition is built first. (User directive, 2026-09-14.)
12. **Scope of coding obligations is total, not "as much as convenient".** Every piece of infrastructure the paper needs — embodiment rSkills, sensor bridges, navigation, manipulation, joint limits, verifiers, run artifacts, launch orchestration — is built, regardless of size. The only excluded work is imitation-learning data collection and VLA model training. (User directive, 2026-09-14.)

13. **The paper has only two main scientific experiments.** Do not create separate communication, resource, failure, trustworthiness, prompt-engineering, or ablation campaigns unless a later result establishes a genuinely independent scientific question. Those factors are conditions inside Experiment I or supporting analyses.
14. **External baselines are PLEXIL and EUROPA→PLEXIL.** A handcrafted behavior tree, generic OpenRAL, and prompt-only variants are development diagnostics or at most one targeted ablation; they are not main paper baselines.
15. **Do not weaken classical autonomy.** PLEXIL may use its documented conditions, loops, concurrency, libraries, and resources. EUROPA may plan/replan within its encoded domain. A held-out case is valid only when the required primitive capabilities exist but the mission-level decomposition/semantic relation is absent from frozen baseline artifacts.
16. **Autonomy metrics are grounded in ALFUS.** Do not invent a scalar autonomy score. Store the raw quantities needed for Human Intervention, Human Planning/Preplanning, Level of Human Interaction, and mission-variation coverage.
17. **Engineering-cost claims require timed, auditable extension work.** Do not infer "lower engineering cost" from code size alone. Experiment II uses a freeze→extension specification→timed authoring→validation→held-out test protocol.
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

## 1.5 PLEXIL Release 6 — external procedural/reactive autonomy baseline

Repository: `plexil-group/plexil`  
Documentation: `https://plexil-group.github.io/plexil_docs/`

Use the official Release 6 branch/revision and record the exact commit. Do **not** reimplement a PLEXIL-like state machine.

Capabilities relevant to the baseline, confirmed in official documentation:

- PLEXIL Executive / `plexilexec` for plan execution;
- `Command` for asynchronous effects on external systems;
- `Lookup` for reading external state;
- start/end/repeat/skip/pre/post/invariant/exit conditions;
- sequences, concurrence, `Try`, `If`, loops, and library calls;
- command resource arbitration;
- interface adapters that connect the Executive to external systems.

Integration strategy for this project:

- keep PLEXIL outside the proposed OpenRAL reasoner path;
- expose the **same LunarBot capability server** used by Ours through a thin PLEXIL adapter/proxy;
- map PLEXIL Commands to shared capability calls that still pass through the common low-level safety path;
- map world state, capability availability, and verifier outputs to PLEXIL Lookups;
- write competent mission plans for the declared model-covered situations;
- log plan/node transitions and all external command/lookup traffic into the common run artifact format.

The first implementation should evaluate two adapter options after building the upstream examples:

1. a native/custom PLEXIL `InterfaceAdapter` that calls the ROS 2/shared capability bridge; or
2. the stock IPC adapter connected to a separate ROS 2 proxy, if this preserves typed return values and failure semantics cleanly.

Choose the smaller, less invasive option after a live proof. The adapter itself must contain no mission logic.

## 1.6 NASA EUROPA — external model-based planning baseline

Repository: `nasa/europa`

Use the official open-source EUROPA framework and record the exact commit/container/toolchain used. EUROPA is a planning, scheduling, and constraint-programming framework with a Plan Database, solver, and declarative modeling language. It is typically embedded in a host application.

For the paper, the baseline is explicitly named **EUROPA→PLEXIL**:

```text
mission goal + current state
        ↓
EUROPA host / NDDL domain
Plan Database + Solver
        ↓ executable activity tokens
EUROPA→PLEXIL bridge
        ↓
PLEXIL Executive
        ↓
shared LunarBot capability server + safety
        ↓
state / verifier feedback
        ↺ EUROPA host for replanning inside the frozen domain
```

Important wording: this is a research integration of two NASA open-source components. Do not call it an official NASA "EUROPA+PLEXIL product" unless an exact public distribution proving that claim is later identified.

The baseline must support replanning within its encoded model. The bridge should not reduce EUROPA to a one-shot schedule.

Initial domain model should include, where used by the final missions:

- robot location/region state;
- infrastructure/component states;
- possession/tool state;
- navigation/manipulation activities;
- capability availability;
- activity duration bounds where required;
- relevant unary/replenishable resource or mission-state constraints;
- precedence/temporal/state constraints;
- verifier/FDIR updates that alter current state.

Do not encode held-out scenario-specific task decompositions in the final frozen domain.

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

### Actual layout as of 2026-09-14 (supersedes the sketch above where they differ)

Both upstreams are forks (`DsslRobot/openral`, `DsslRobot/space_robotics_bench`)
pinned as git submodules at `openral/` and `space_robotics_bench/`
(`docs/upstream_pins.md`). The fork was unavoidable for OpenRAL (Python
3.10 / ROS 2 Humble downgrade — every lab machine and the real LunarBot are
Humble, decision D1). Given that, **embodiment-level integration lives in
the forks, on feature branches, because it is upstream-shaped code**: a HAL
is an OpenRAL layer-0 package (`packages/openral_hal_lunar_bot/`), a robot
manifest is `robots/lunar_bot/robot.yaml`, an rSkill is `rskills/<id>/`, an
SRB action term or task is `srb/core/action/term/...` / `srb/tasks/...`.
Putting these in `openral_ext/` / `srb_ext/` would mean re-implementing
OpenRAL's loaders to look elsewhere — the opposite of "reuse before
implementing". The `srb_ext/` / `openral_ext/` directories in the sketch are
therefore **not used**; their intended contents are on the fork branches,
one branch per task, every commit recorded in `docs/upstream_pins.md`.

What stays in this repository: the research mechanisms (`space_runtime/`,
`space_context/`, the mission-level decision layer, verifiers), the
baselines, the experiment runner/launch orchestration, run artifacts,
metrics, and all documentation. The dividing rule: *if OpenRAL or SRB would
plausibly accept it upstream as a generic feature, it goes on a fork
branch; if it only makes sense for this paper, it goes here.*

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

## 6.2 Robot embodiment — LunarBot, by decision (revised 2026-09-14)

The original guidance ("least integration work; do not require LunarBot
before the runtime is validated") was overridden by an explicit user
decision: the embodiment is **LunarBot** (SRB `lunar_bot`, category
`mobile_manipulator`, type `WheeledManipulator`): a 4WIS/4WID rover + a
7-DoF RealMan RM-75 arm + an Inspire EG2-4C2 gripper, one PhysX
articulation, 21 joints. The simulated model carries the same joint names
as the real robot, so Phase I (real-robot transfer) becomes an endpoint
swap rather than a re-integration. The RM-75 datasheet is recorded in
`docs/lunar_bot_rm75_spec.md`.

The consequence the original guidance was warning about has materialised
and must be stated plainly: **no upstream rSkill can drive `lunar_bot`.**
Every learned policy in `openral/rskills/` is trained for another
embodiment; the `ros_action` wrappers (`moveit-*`, `nav2-*`) need servers
that are not configured for this robot; the only actuating skill that
matches is the base-only `rskill-procedural-body_twist` this project added.
Likewise, no sensor from SRB reaches OpenRAL's world state yet.

This is not a detour. `research_content.md` §5.1 requires every baseline to
share the same perception, navigation, manipulation controller, FDIR
primitives and safety; §6.4 requires a "capability set shared across all
baselines" table. **The LunarBot capability set is that table.** Building
it is core Phase B work (§8.3 below), and the same procedural primitives are
what Baseline A (procedure-driven, §11.1) is composed from.

Selection criteria retained as *verification* criteria for the built
capability set:

- mobile manipulation on `GroundManipulationEnv` — done (`panel_remount`);
- usable RGB/depth and robot-state observations — **not yet wired**;
- navigation/manipulation control interface — base/arm/gripper HAL done;
  navigation stack and manipulation skills **not yet**;
- ROS 2 exposure — done (per-action-term topics, `docs/srb_integration_notes.md`);
- mission assets and task signals in the environment — done for v1.

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

## 6.4 Mission A — infrastructure inspection and maintenance

Mission A is the primary semantic/generalization mission.

Required scene properties:

- navigable approach region rather than spawn-next-to-target;
- multiple visually distinguishable infrastructure components;
- at least one component/state that must be inspected to determine what is wrong;
- one or more general-purpose physical operations that can restore the final condition;
- deterministic simulator truth for scoring/verifying every required transition;
- perturbation switches that can create both model-covered and model-held-out situations.

The operator instruction gives a mission objective, not an action sequence.

### Covered examples

These are visible during baseline authoring and may be explicitly modeled:

- one known panel/component displaced from its nominal mount;
- nominal approach and remount sequence;
- a predefined manipulation retry/failure branch;
- a known route obstruction with an encoded alternate route if included.

### Held-out examples

These are hidden until artifact freeze. They must satisfy the closed-capability rule: the needed primitive skills already exist.

Candidate patterns:

- access to the failed component is blocked by a movable object and the valid solution requires inspect → diagnose obstruction → relocate → re-access → restore → verify;
- observed state is semantically inconsistent with the expected failure template, requiring an additional close inspection before choosing an operation;
- a preferred capability is unavailable, but an alternative composition of existing generic capabilities can still satisfy the objective.

Do not create arbitrary puzzle-like cases. Each held-out case must correspond to a plausible lunar servicing situation and be solvable with existing capabilities.

**Current scene status:** `panel_remount` v1 is only an infrastructure seed scene. v2 must add candidate discrimination, real approach/navigation, semantic inspection, and the hidden-condition switches above before Experiment I.

## 6.5 Mission B — logistics and servicing

Mission B is the second composition pattern, used to show that the result is not unique to one maintenance graph.

Required elements:

- locate/retrieve a tool or component;
- transport/navigation to another location;
- service/place/manipulate at the destination;
- final independent verification;
- at least one covered and one held-out condition with the same closed-capability rule.

The final paper should not add a third mission family unless Mission A/B fail to exercise a distinct mechanism. Mission B can remain simpler than Mission A; its purpose is replication across a different task composition, not task-count inflation.

# 7. Space-context generation work package

## 7.0 Scope guard — implement only context exercised by the two main experiments

Space context is an enabling part of the proposed runtime, not a third scientific axis. Do **not** build a comprehensive lunar digital-twin stack by default. Before implementing any SPICE, relay, link, thermal, energy, or compute model, identify the exact Experiment-I/II scenario and decision whose outcome depends on that variable. If no final scenario uses it, leave it out of the first paper.

For the initial campaign, prefer one or two well-justified operational constraints that materially change mission decisions (for example, remote-service availability across a documented contact interruption and one resource/health constraint). The same context must be exposed fairly to all methods in whatever representation their architecture requires.

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

## 8.1 Inventory available capabilities — filled in for `lunar_bot` (2026-09-14)

Inspected against the pinned revisions (`docs/upstream_pins.md`). “Upstream
has it” and “it works for this robot” are different columns on purpose.

| Needed mission capability | Upstream implementation (exists) | Works for `lunar_bot` today? | Missing work |
|---|---|---|---|
| base motion | `rskill-procedural-body_twist` (this project, F11) → HAL → SRB `cmd_vel` | yes, verified live | F19: 4WIS steering saturates on large in-place turns — fix in SRB's `FourWheelSteer` controller before Nav2 relies on `cmd_vel` |
| navigation | `openral_nav2_bringup` (Nav2 launch/params), `rskill-nav2-navigate-to-pose` (`ros_action`, `mobile_base`) | **no** — needs `map`/`odom`/`base_link` TF, `/odom`, a costmap source, and a `/cmd_vel` consumer | (a) TF/odom bridge from SRB truth; (b) costmap source — LunarBot has no lidar, so `/map` must come from the front RGB-D via `octomap_server`'s projected 2-D map (visual profile), *or* a simulated lidar if the real LunarBot carries one (**ask the user; do not add a sensor the real robot lacks**); (c) route Nav2's `/cmd_vel` through the safety kernel as BODY_TWIST — upstream's manifest admits Nav2 bypasses the supervisor, which violates §10.1 for this paper |
| scene query | `openral_perception_ros/scene_vlm_node` + `qwen35-4b-nf4` (`kind: vlm`) | **no** — no image reaches `/openral/cameras/<name>/image` | sensor bridge: SRB already publishes `Image`/`CameraInfo`/depth/pointcloud under `--interface ros` for the `*_visual` task variant; declare `sensors:` in `robot.yaml` and relay/remap into OpenRAL's `/openral/cameras/` convention with REP-103 frames |
| object localization | `ros_image_detector_node` (`omdet-turbo-locator`, `locateanything`) → `/openral/perception/objects` → world-state 3-D lift (needs depth points + `map` TF) | **no** — same missing bridge, plus depth points on `/openral/cameras/front_depth/points` | same sensor bridge; then verify a detection of the panel lands in world state with a sane 3-D pose |
| manipulation (execution) | HAL: CARTESIAN_TWIST + JOINT_POSITION + GRIPPER_BINARY through the kernel | HAL yes; **no rSkill** exists | new `kind: procedural` rSkills for `lunar_bot` (§8.3): `move_ee_to_pose` (closed-loop CARTESIAN_TWIST on TF), `move_joints` (JOINT_POSITION), `grasp` / `release`, `stow` |
| manipulation (planning) | `rskill-moveit-{joints,eef-pose,look-at}` (`ros_action`, tagged franka/ur) | **no** — no MoveIt config for RM-75 here, no trajectory bridge | after the procedural skills: RM-75 MoveIt config (RealMan publishes `ros2_rm_robot` with `rm_75` description — verify content + license before use), a joint-trajectory → JOINT_POSITION-stream bridge through the kernel, retag the moveit rSkills for `lunar_bot` |
| VLA | many, none for this embodiment | no | not adopted; excluded by scope (no training/data collection) |
| progress verification | `verify-outcome` playbook, `robometer-4b` reward, `/srb/env0/terminated` + reward topics, `/tf` object poses | partially (topics exist) | a mission verifier node in this repo that reads simulator truth (§10.4: deterministic where truth is available) and emits typed verifier events |
| FDIR signals | kernel `/openral/safety_status` + violations + estop; SRB `penalty_undesired_robot_contacts`; Nav2/MoveIt action results | topics exist | mapping into mission-runtime events (Phase E); scenario fault injection (Phase C) |
| arm joint limits | kernel per-joint JOINT_POSITION check | ran against ±inf | RM-75 datasheet now available (`docs/lunar_bot_rm75_spec.md`) — declare in `robot.yaml` |
| kernel magnitude checks for other modes | `kJointTrajectory`/`kCartesianDelta`/`kGripperPosition`/`kCompositeMode` delegate to an unlaunched Python stub | not enforced | close the same way F12/F16 were closed, for every mode the LunarBot HAL can be asked to emit |

Do not select a VLA because the paper “needs AI.” Use it only where learned manipulation contributes a meaningful heterogeneous-capability case.

## 8.3 LunarBot capability-set work package (Phase B2 — blocks everything after it)

Ordered by dependency. Each item is verified live through the real
safety-checked path before the next starts, and each gets a `docs/` record.
Per-item design decisions, the upstream pieces to reuse, and the open
questions are in `docs/lunar_bot_capability_set_plan.md` (2026-09-14).
Item 1 is done (`openral` `f7b5ccd`); items 2–9 are not started.

1. **RM-75 limits** into `robot.yaml` (`position_limits`, `can_lift_kg`),
   kernel envelope regenerated; a JOINT_POSITION target outside the range
   must be rejected live.
2. **Sensor bridge** — front RGB-D + wrist RGB + IMU + Mid-360 lidar +
   joint states + truth pose from SRB into OpenRAL conventions: `sensors:`
   block in `robot.yaml`; a relay in `openral_hal_lunar_bot` publishing
   `/openral/cameras/<name>/{image,camera_info}`,
   `/openral/cameras/front_depth/points`, `/joint_states`, `/odom`, and the
   `map → odom → base_link` TF chain (in sim, `map→odom` is identity and
   `odom→base_link` is SRB's `srb/env0/robot` truth — stated as such, not
   dressed up as SLAM). Verify: world state shows joints + a lifted 3-D
   object from a real detection of the panel.
2b. **SRB backend for `openral deploy sim`** (`docs/srb_deploy_backend_plan.md`,
   user decision 2026-09-14): `DeployScene.simulator` schema, `srb` scene
   backend with a provision check, the launch spawns/gates/owns the SRB
   process, `lunar_bot` registered in the deploy HAL table, a
   `scenes/deploy/srb_panel_remount.yaml`. Migrates the isaacsim backend's
   process-lifecycle/provision discipline; the data plane stays SRB's
   native ROS interface. Verify: one `openral deploy sim … --initial-task`
   command brings the whole graph up and a reasoner-dispatched
   `body_twist` moves the base. Every later item is verified through this
   path. Status 2026-09-14: built + live-verified (F26/F27); the SRB tick
   rate that stalled the exit condition is root-caused and fixed (F28,
   0.36 → ~12 Hz, `staleness_limit_s` untouched); the body_twist
   observation itself is done (F29): a kernel-dispatched (not
   reasoner-dispatched — no LLM credential on this host) BODY_TWIST moved
   the base 0.55 m over 5.05 s, measured via real `/tf`. Item 2b is fully
   closed. Open from F28: Fast-DDS large-message loss caps camera topics
   at ~2 Hz into OpenRAL.
2c. **RTX Lidar support for the Mid-360** (user decision 2026-09-14,
   scheduled immediately after 2's RayCaster-based Mid-360 lands — do not
   start early; treated as permanent, repeatedly-reused infra, not a demo).
   Rationale: this project is imitation learning, not RL — no `num_envs`
   parallelism requirement — which removes IsaacLab's stated reason for
   *not* wrapping RTX Lidar (their team evaluated and dropped it because it
   doesn't batch across thousands of parallel envs; irrelevant here). RTX
   Lidar ray-traces the live render scene every frame (sees dynamic
   objects, not just one static baked mesh like the warp `RayCaster`), so
   it is the correct long-term sensor, not a nice-to-have. Fully
   researched 2026-09-14, mechanism confirmed from source (not inferred),
   ordered 9-step executable plan with a full USD-attribute reference:
   `docs/rtx_lidar_integration_plan.md`. Headline findings, all settled
   (not open questions): (1) there is **no JSON-config/whitelist mechanism
   to bypass** in the modern (5.0+) path — a custom lidar is authored as
   literal `omni:sensor:Core:*` USD attributes on an `OmniLidar` prim via
   the fully-ungated `rep.functional.create.omni_lidar(**kwargs)`, full
   attribute reference read from the generated USD schema; (2) the
   Mid-360's real non-repetitive scan pattern is a solved data problem —
   `Livox-SDK/livox_laser_simulation` (MIT-licensed) ships the official
   `scan_mode/mid360.csv`, 800,000 real timestamped azimuth/zenith
   samples covering one full 4s cycle, replayed by the real plugin as a
   sliding 24,000-point window advancing and wrapping every tick — this
   plan requires reproducing that same window-cycling (not a single
   static pattern) for real fidelity, and confirms via the schema that
   per-tick array-value updates are supported; (3) Livox's official
   datasheet numbers (FOV, range, wavelength, blind zone, point rate) are
   recorded with citation; (4) a real gap was found and must be fixed as
   part of this item: SRB's `enable_cameras`/rendering-experience gating
   (`srb/__main__.py`, keyed off task-id `_visual` suffix) does not
   trigger for `panel_remount env.robot=lunar_bot`, so RTX Lidar would
   silently get no render pipeline without a code fix; `isaacsim.sensors.rtx`
   also needs adding to SRB's `.kit` experience files (absent from all of
   them today, confirmed by grep).

   **Status 2026-09-14, implementation attempted same day:** items 1-3 of
   the ordered plan done and committed (`.kit` files, the `__main__.py`
   gating fix, and `srb/core/sensor/rtx_lidar.py` — the Mid-360
   scan-pattern-window + custom-prim-authoring mechanism, live-verified
   working). **Blocked on a confirmed, precisely-localized upstream Isaac
   Sim bug**, not anything in this codebase: the RTX Lidar sensor's own
   render-product/SDG dispatch pipeline never produces a frame — confirmed
   in both headless AND windowed/GUI mode (GUI re-run against the
   machine's real display: main viewport renders perfectly, GPU genuinely
   busy at ~60%/270W, but the sensor's own render-product preview stays
   black indefinitely) — so it is not a headless-specific or GPU/driver
   issue, specifically the lidar SDG path. Matches isaac-sim/IsaacSim#110
   (closed 2026-04-17 as "resolved in Isaac Sim 5.1" — but see below, this
   did not hold up). Chased down the "fixed in 5.1.0" forum lead directly:
   NVIDIA's official 5.1.0 GA download is byte-identical to our pinned
   `5.1.0-rc.19` (same VERSION string, same extension versions) — they
   shipped the RC unchanged as GA, so **there is no same-series fix to
   move to**. See `docs/rtx_lidar_integration_plan.md`'s Status section
   for the full verification trail (six render-advance mechanisms, two
   documented Known Issues workarounds, non-headless/real-display
   localization, the official example's `enable_motion_bvh` flag, and
   NVIDIA's own engineer-confirmed workaround from the #110 thread itself
   — all tried, all failed). Not wired into `srb/core/env/mobile/env.py`
   as the active sensor; RayCaster stays active. F24 in
   `docs/research_findings.md`.

   **Parked 2026-09-14 (user decision), not abandoned.** A same-day
   follow-up closed out the remaining question — is this worth more
   effort — on two fronts: (a) re-read `research_content.md`: the word
   "lidar" never appears in it; every baseline only needs to *share* the
   same perception (§5.1), and the LunarBot demo's purpose is validating
   runtime transfer, explicitly "not attempt to reproduce the lunar
   environment on Earth" (§5.7) — RTX Lidar's realism has no bearing on
   the paper's actual claims; (b) researched an Isaac Sim 6.1.0 upgrade as
   a possible fix and found it is not a small/safe change: IsaacLab v2.2.1
   does not target Isaac Sim 6.x (needs IsaacLab **v3.0.0-beta2+**, still
   beta, CI coverage for the pairing incomplete per the IsaacLab team
   itself); Kit's bundled Python moves 3.11→3.12 (risk to the pinned
   torch/cu128 wheels and the cross-ABI trick this project's ROS bridging
   depends on to import system Humble's `rclpy` into Kit's interpreter);
   9+ documented breaking changes plus a PyTorch→Warp Core-API rework in
   6.0; **and, most load-bearing, independent evidence that our exact GPU
   class has its own unresolved bugs on this exact build** — an NVIDIA
   forum report titled for our precise combination ("Isaac Sim
   5.1.0-rc.19 crashes on startup with RTX 5090 and NVIDIA 580-open
   driver") and
   [IsaacLab#4951](https://github.com/isaac-sim/IsaacLab/issues/4951)
   (TiledCamera hangs indefinitely on RTX 5090/Blackwell with Isaac Sim
   5.1.0, "the hang occurs before the warp kernel receives any input
   data" — the same failure shape as our Lidar SDG dispatcher never
   advancing), **with no confirmed fix in any later version including
   6.1** for either. Given the paper doesn't need it and the upgrade path
   is unproven-at-best for actually fixing it while carrying real
   migration risk, **this item is shelved — RayCaster remains the
   permanent `lidar_robot` implementation.** Do not re-open without new
   evidence that a future Isaac Sim build both (a) fixes RTX Lidar and
   (b) doesn't regress on Blackwell-class GPUs.
3. **Procedural manipulation rSkills** (`kind: procedural`, tag `lunar_bot`):
   `move_joints`, `move_ee_to_pose`, `grasp`, `release`, `stow`. Each is a
   real closed loop on OpenRAL world state / TF, emits through the kernel,
   finishes on a measured condition, and reports failure honestly (timeout,
   unreachable, kernel rejection). Verify: scripted sequence remounts the
   panel in `panel_remount` v1 → `terminated == true`.
4. **F19 fix** in SRB's `FourWheelSteer` controller. Reading the code
   revised the hypothesis: not the 120° steering limit but missing
   steer-before-drive sequencing — steer position targets and drive
   velocity targets are written in the same step, so wheels drive at full
   speed while still swinging up to 90° (≈0.8 s at the steering joints'
   112°/s limit). Fix: scale drive velocity by `cos(steer error)`; verify
   with an in-place 90° turn.
5. **Navigation** — Nav2 via `openral_nav2_bringup`, lidar profile fed by
   the Mid-360 that the SRB-side agent adds (`pointcloud_to_laserscan` for
   `/scan`, full cloud into the voxel layer; `docs/srb_deploy_backend_plan.md`
   §5); `/cmd_vel` routed through the kernel; `rskill-nav2-navigate-to-pose`
   resolves for `lunar_bot`. Verify: a `map`-frame goal 3–4 m away is
   reached without touching the pedestal.
6. **MoveIt for RM-75** (after 3): config, trajectory→JOINT_POSITION bridge,
   moveit rSkills retagged. Verify: `moveit-eef-pose` to a pose above the
   panel through the kernel.
7. **Mission verifier node** (this repo): reads `/tf` object poses,
   `/srb/env0/terminated`, reward terms; emits typed verifier events with
   evidence references (§4.4).
8. **Run artifacts** (this repo, `experiments/manifests/`): a run-manifest
   writer wrapping `openral deploy sim` (item 2b) that produces the §19
   directory (git revisions of both submodules, scene YAML, seed, model
   config, mission text, OTel trace export, rosbag opt-in). Launch
   orchestration itself is item 2b, not a launch file here.
9. **Remaining kernel magnitude checks** (§8.1 last row).

**Exit condition for B2:** with the reasoner *in the loop* (`openral prompt
--new-goal`), a two-step instruction (“drive to the pedestal, then open the
gripper”) executes end-to-end through Nav2 + a procedural skill, and the run
directory contains the complete trace. That is Phase B's original exit
condition, which has not been met yet — only single scripted capability
calls have (§21 item 4).

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

# 9. Foundation-model reasoning and semantic-observation work package

This work package implements the functions that distinguish the proposed method. Generic OpenRAL runs remain development diagnostics, not a main paper baseline.

## 9.1 Development diagnostic: unmodified OpenRAL

Before enabling the new mission runtime, run Mission A through stock OpenRAL reasoner + world state + typed tools + shared LunarBot capabilities. Save the trace to identify integration failures and to ensure the proposed changes are actually necessary.

This diagnostic is **not** one of the three paper methods unless later evidence shows that a specific comparison is scientifically indispensable.

## 9.2 LLM mission-reasoning contract

The reasoner may:

- interpret the mission instruction;
- propose/decompose subgoals;
- request scene/state information;
- select registered capabilities;
- diagnose unexpected observations;
- recompose the remaining mission;
- request escalation/clarification;
- generate a report from structured state/evidence.

The reasoner may not:

- issue raw joint/base commands;
- create an unregistered physical capability;
- directly mutate authoritative mission state;
- override mission authority, FDIR, or low-level safety;
- mark a transition verified without a verifier event.

Encode these boundaries in the tool schema and dispatcher, not only in prompt prose.

## 9.3 VLM / semantic observation path

Reuse OpenRAL's scene-VLM path where possible. Add only the minimum interface needed to support Mission A semantic cases.

The VLM query API should support questions such as:

- identify which infrastructure component appears abnormal;
- determine whether access is visually obstructed;
- compare the observed configuration with a named expected configuration;
- suggest what region/component requires closer inspection.

VLM output is logged with image/evidence reference, timestamp, model identity, and confidence/quality metadata if provided. It enters reasoner context as an observation; deterministic simulator truth remains confined to the verifier/evaluator unless the same state would be available on the real robot.

## 9.4 Context builder

Construct compact context from:

- mission objective/current objective;
- verified progress;
- unresolved anomalies;
- relevant world state;
- current semantic observations;
- available/degraded capabilities;
- active FDIR state;
- current mission authority;
- mission-relevant communication/compute/resource context;
- recent evidence and failed attempts.

Do not dump the full mission history or raw telemetry.

## 9.5 Natural-language status/report generation

At mission end or operator request, generate a concise report from authoritative state and evidence references. The report must distinguish verified facts from unresolved hypotheses and escalations.

Do not score prose quality as a main experiment metric. The report is a system capability and qualitative trace artifact.

## 9.6 Optional prompt-only ablation

Do not implement this as a main baseline. Only after the full method works, a single targeted ablation may bypass authoritative mission-level enforcement/verification while leaving the LLM informed of the same state. Run it only on the small trustworthiness subset needed to establish H3.

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

# 11. External baseline implementation

The main paper compares exactly three methods: **PLEXIL**, **EUROPA→PLEXIL**, and **Ours**.

All three use the same environment, robot embodiment, navigation, perception/VLM service, manipulation skills, verifier, FDIR signals, and low-level safety path.

## 11.1 PLEXIL baseline

### Build/pin

- clone/pin `plexil-group/plexil` Release 6;
- build and run upstream examples with `plexilc`, `plexiltest`, and `plexilexec`;
- save exact revision and build toolchain in `docs/baselines/plexil.md`.

### LunarBot adapter

Expose common capabilities as Commands. The initial set should include only capabilities available to Ours, for example:

- `NavigateToPose`;
- `SceneQuery` / `InspectRegion`;
- `LocateObject` where needed;
- `MoveEEToPose` / `MoveJoints`;
- `Grasp`, `Release`, `Stow`;
- other general-purpose capabilities introduced later.

Expose state as Lookups, e.g. robot region/pose summary, capability availability, relevant object/component state, action status, FDIR state, authority state, and verifier result.

Commands must call the shared capability execution path. The PLEXIL adapter may not directly bypass the common safety layer.

### Plan authoring

Create a plan library for Mission A/B model-covered cases using native PLEXIL constructs. Include reasonable predefined recovery logic. Use library nodes for reusable general procedures rather than duplicating plans.

Every plan/library file used in a campaign is hashed into the freeze manifest.

## 11.2 EUROPA→PLEXIL baseline

### Build/pin

- clone/pin `nasa/europa`;
- build its documented examples in a reproducible container/toolchain;
- write `docs/baselines/europa.md` recording the exact APIs used by the host application.

### Domain model

Create an NDDL/domain model only from knowledge declared available before the freeze. Model the actions/states/resources/constraints needed to solve covered Mission A/B situations.

Do not hand-code held-out task decompositions after seeing final held-out cases.

### Online host and replanning loop

Implement a small host application that:

1. loads the domain and mission/problem instance;
2. injects current shared world/mission state;
3. invokes the EUROPA solver;
4. extracts executable activity tokens;
5. dispatches the next valid activities through the PLEXIL bridge;
6. receives action/verifier/FDIR updates;
7. updates the plan database and allows solver repair/replanning within the frozen domain.

This loop is required for a fair baseline. Do not generate one static sequence and call that EUROPA planning.

### PLEXIL execution bridge

Prefer a generic activity-dispatch PLEXIL library so the mission logic stays in EUROPA rather than duplicated into PLEXIL. Each EUROPA activity maps to a shared capability invocation and returns status/evidence to the host.

## 11.3 Proposed system

Enable:

- LLM/VLM mission reasoning;
- authoritative mission state;
- dynamic context builder;
- typed capability orchestration;
- mission-level admissibility/authority;
- mission-relevant space context;
- FDIR/capability degradation integration;
- independent verification;
- distributed-reasoner reconciliation where exercised;
- trace/evidence linkage.

## 11.4 Development-only diagnostics

The following are not paper baselines unless promoted later for a specific reason:

- unmodified generic OpenRAL;
- prompt-only space context;
- handcrafted behavior tree/state machine.

Do not spend implementation time polishing these once the external baselines work.

# 12. Experiment runner architecture

Create one experiment runner that instantiates all three methods through configuration and writes a common artifact schema.

Suggested layout:

```text
experiments/
├── runner.py
├── methods/
│   ├── plexil.yaml
│   ├── europa_plexil.yaml
│   └── ours.yaml
├── scenarios/
│   ├── mission_a/
│   │   ├── covered/
│   │   └── held_out/
│   └── mission_b/
│       ├── covered/
│       └── held_out/
├── extension_cases/       # Experiment II
├── freeze_manifests/
├── operator_events/
├── launch/
└── manifests/
```

Every scenario manifest must declare:

- mission family and instance ID;
- simulator seed/initial state;
- whether it is covered or held-out;
- evaluator-only success conditions;
- required primitive capabilities (for closed-capability validation);
- mission deadline/constraints where applicable;
- relevant space-context profile;
- perturbations/semantic conditions;
- evidence/verifier mapping.

The method must not receive evaluator-only solution annotations.

Every run manifest must include:

- method;
- mission/scenario ID;
- random seed;
- foundation-model/provider configuration where used;
- PLEXIL/EUROPA/OpenRAL/SRB revisions;
- hashes of frozen mission/domain/prompt/capability artifacts;
- space/network profile IDs;
- capability-registry snapshot;
- operator event log;
- trace/log locations;
- final metrics.

The runner must reject a run if artifact hashes differ from the declared campaign freeze manifest.

# 13. Experimental campaign design

There are two main experiments and one later hardware demonstration.

## 13.1 Pre-campaign validation and artifact freeze

Before collecting paper results:

1. finish the common LunarBot capability stack;
2. validate Mission A/B success conditions independently from all methods;
3. run PLEXIL and EUROPA→PLEXIL on model-covered development cases until infrastructure/baseline bugs are resolved;
4. run Ours on the same development cases;
5. finalize generic capability metadata, prompts/policies, PLEXIL plan libraries, EUROPA domain/solver configuration, mission policies, and verifier mappings;
6. create a cryptographic freeze manifest for all method-specific artifacts;
7. only then reveal/instantiate final held-out cases.

Infrastructure defects discovered after freeze may be fixed only if the same correction is applied fairly and the affected campaign is rerun from the start. A method-specific change that adds missing task knowledge invalidates the freeze and is counted as re-authoring.

## 13.2 Experiment I — Autonomous Mission Generalization

### Objective

Test H1: whether Ours expands the autonomous mission envelope beyond fully pre-engineered task models.

### Factor structure

Primary factor: **mission-model coverage**.

- `covered`: solution task/decomposition is representable in frozen baseline artifacts;
- `held_out`: required primitive capabilities exist, but scenario-specific semantic diagnosis/decomposition/composition is absent from frozen PLEXIL/EUROPA artifacts.

Run both Mission A and Mission B. Do not multiply factors unnecessarily. Space communication/resource/FDIR conditions are included only when they materially affect the mission logic of selected instances.

### Closed-capability validator

Before a held-out instance is admitted to the campaign, an evaluator script/manual review must confirm:

- a valid solution exists using only capabilities present before freeze;
- every required observation is available through the shared perception stack;
- the proposed method has no scenario-specific hard-coded solution;
- the baseline's missing knowledge is mission-level structure, not a missing controller/sensor.

Store this certificate with the scenario manifest but do not expose the solution sequence to the methods.

### Operator protocol

Use one standardized ground-operator interface for all methods.

Allowed during a run:

- provide the initial mission/goal in the method's required representation;
- answer an explicit clarification/escalation request if the mission authority permits;
- issue an operational abort/safe-stop if required.

Not allowed during an autonomous run:

- edit PLEXIL plans/libraries;
- edit EUROPA NDDL/domain/solver rules;
- edit Ours prompt/runtime/capability metadata;
- add a new capability;
- reveal evaluator-only state.

If continuation requires such edits, set `ground_reauthoring_required=true`. The autonomous run terminates for the main success metric. A separate assisted completion may be performed for trace analysis but is not counted as autonomous success.

### Human-interaction event logging

The operator UI emits:

```text
interaction_start(type, authority_level)
interaction_message(...)
interaction_end()
clarification_request(...)
escalation_request(...)
human_command(...)
```

`authority_level` uses the ALFUS ordering:

`mission > strategic_goal > tactical_goal > mission_task > route > autopilot > servo`

Do not infer interaction time from chat timestamps after the fact.

### Repetitions

Use paired scenario seeds across methods. Foundation-model runs should be repeated under a fixed provider/model/version and decoding configuration to measure stochastic variance. Determine final repetition count after pilot variance is known; do not hard-code a significance-driven number now.

### Required output

One normalized result row per run plus complete trace. The main result table is generated directly from these rows.

## 13.3 Experiment-II setup — extension cases

Experiment II begins only after Experiment I artifacts are frozen.

An extension case contains:

```yaml
extension_id: ...
new_shared_capability: optional
new_mission_requirement: ...
validation_cases: ...          # visible during engineering
held_out_cases: ...            # hidden until re-freeze
allowed_shared_changes: ...    # identical for all methods
```

Two useful extension types are enough:

1. **new capability registration/use** — low-level implementation is provided identically; each method must make it usable at mission level;
2. **new task relationship/mission situation** — no new controller, but mission-level knowledge must be extended.

Do not create many trivial extension cases.

## 13.4 Experiment II — Autonomy Extensibility / Knowledge-Engineering Cost

### Objective

Test H2: how much method-specific engineering is needed to deliberately expand the supported autonomous mission envelope.

### Timed authoring protocol

For each method/extension case:

1. start from the frozen Experiment-I repository state;
2. reveal the extension specification and visible validation cases;
3. start a dedicated engineering timer;
4. allow the engineer to use normal documentation/tooling (and the same coding assistant policy, if coding agents are used);
5. stop the timer only when the common validation suite passes;
6. commit the method-specific changes and record the diff;
7. create a new freeze manifest;
8. reveal and run the held-out extension cases.

Timer policy:

- use elapsed active work-session time including edit/build/test/debug cycles;
- pause only for unrelated interruptions or unavailable shared infrastructure;
- record session start/stop explicitly in `engineering_worklog.jsonl`;
- do not reconstruct timing from git commit timestamps.

### Learning/carryover control

Preferred design: multiple qualified developers with counterbalanced method order across extension cases.

If resources only permit one developer, report engineering time as controlled case-study evidence, not a population-level human-factors statistic. In that case artifact deltas and post-extension held-out performance become especially important.

### Validation suite

The visible suite checks syntax/build, capability wiring, one nominal extension case, safety/verifier integration, and trace completeness. It must not contain the final held-out extension scenarios.

## 13.5 Targeted trustworthiness analysis

Do not run a broad third experiment.

If required to support H3, select a small subset of Experiment-I cases that can expose stale/duplicate/unsupported mission transitions and compare:

- Full Ours;
- Ours with mission-level enforcement/independent verification bypassed while retaining the same model context.

Only the relevant trust metrics are reported. This belongs in failure analysis/supplement unless it becomes essential to the main result.

## 13.6 LunarBot demonstration

After the simulation result is stable, execute one representative multi-step mission segment on the real LunarBot using the same capability/runtimes interfaces.

Minimum desired evidence:

- mission-level natural-language instruction;
- reasoner-selected sequence of at least navigation/inspection/manipulation or an equivalent multi-stage subset;
- real ROS/sensor feedback entering mission state;
- one independently verified physical outcome;
- final trace-linked natural-language report.

Detailed real-robot experiment design is intentionally deferred.

# 14. Metrics and post-processing

Metrics must be computed from normalized logs wherever possible. Do not create a composite autonomy score.

## 14.1 Mission accomplishment

### Autonomous Mission Success

Binary per run:

```text
1  if all required final mission conditions are verified
   AND no post-reveal method-specific artifact modification was required
0  otherwise
```

Also store failure reason and completed subobjectives for diagnosis.

### Assisted Mission Success

Optional descriptive field for runs completed after operator help. It must never replace the primary autonomous-success metric.

## 14.2 ALFUS-grounded Human Independence measures

The experiment adapts NIST ALFUS metrics directly and reports raw quantities.

### Human Intervention Ratio

```text
HIR = total active operator-system interaction time / mission elapsed time
```

Mission elapsed time starts when the mission is accepted for execution and ends at terminal success/failure/abort. Simulator startup is excluded. Interaction time comes from explicit `interaction_start/end` events.

### Human Planning / preplanning burden

ALFUS lists the ratio of human planning time to mission time and describes the portion of a mission plan pre-generated by humans. For this study record both raw values rather than force them into one ambiguous statistic:

```text
human_mission_specific_planning_time_s
preplanned_transition_fraction
```

`preplanned_transition_fraction` is the fraction of required mission transitions whose scenario-specific decomposition/order is explicitly represented in a frozen human-authored plan/task artifact rather than generated online. The annotation rule must be fixed before the final campaign.

Experiment II separately measures the larger offline domain/plan engineering burden.

### Level of Human Interaction

Store every operator input with the ALFUS authority category:

1. assign mission
2. assign strategic goal
3. assign tactical goal
4. assign mission task
5. route
6. autopilot
7. servo

Report the distribution and the lowest-level intervention required by each run. Do not collapse this ordinal measure into an arbitrary numeric average without justification.

### Mission-variation coverage / dynamic planning

ALFUS suggests the degree of mission variation handled and the percentage of a mission performed without preplan. Operationalize this with:

- success by held-out situation category;
- number/fraction of required transitions generated online rather than scenario-specifically pre-authored;
- `ground_reauthoring_required` rate.

## 14.3 Trustworthiness measures

Derived from the authoritative event log/evaluator:

- mission-invalid proposed action count;
- mission-invalid executed action count;
- authority violation count;
- low-level safety rejection/violation count;
- stale-state action count;
- duplicate action count;
- unsupported mission-state advancement count;
- false completion declaration count;
- continued execution after unresolved critical fault count.

The main paper should report only the subset needed to establish that higher autonomy did not come from relaxing mission discipline. Keep the rest for failure analysis/supplement.

## 14.4 Experiment-II engineering measures

### Engineering Time-to-Valid-Support (ETVS)

```text
ETVS = sum(active timed engineering-session durations)
```

from extension-spec release until the common visible validation suite first passes.

### Mission-specific artifact delta

For every method record:

- files added/modified;
- artifact types changed;
- semantic constructs added where countable;
- line delta as supplemental descriptive data only;
- validation/build/test iterations;
- modeling/logic errors identified during validation.

Do not compare raw line counts across PLEXIL/NDDL/Python as a universal complexity metric.

### Post-extension held-out success

Same Autonomous Mission Success definition as Experiment I, applied after the extension re-freeze.

## 14.5 Supporting system metrics

Collect but do not necessarily headline:

- mission duration and idle time;
- capability call counts;
- local/remote model calls and inference latency;
- communication waiting time where exercised;
- endpoint switches;
- trace completeness;
- tokens/API usage if relevant for reproducibility/cost.

## 14.6 Trace completeness

For each consequential mission transition, automatically verify presence of:

- mission-state version;
- relevant context/evidence reference;
- proposal/tool call;
- mission-level disposition for Ours;
- execution result;
- verifier result;
- resulting mission-state transition.

For PLEXIL/EUROPA baselines, store the analogous plan node/token/activity identifiers so failure analysis remains comparable.

# 15. Statistical analysis plan

The final statistical test set is frozen after pilot runs expose the dependence structure and variance. The implementation must support the following without forcing all of them into the paper.

## Experiment I

- paired comparisons because the same scenario instance/seed is used across methods;
- confidence intervals for autonomous success rates;
- paired categorical comparison for success/failure where appropriate;
- bootstrap or otherwise appropriate confidence intervals for HIR and continuous timing measures;
- stratification by `covered` versus `held_out` and by mission family;
- report the ordinal Human Interaction Level directly rather than treating it as interval data;
- foundation-model run variance shown explicitly.

The primary interaction of interest is **method × model-coverage condition**: a strong result is not merely higher nominal success but smaller degradation from covered to held-out cases.

## Experiment II

- if multiple engineers/repetitions exist, report engineer/case variation and use paired/counterbalanced analysis;
- if only one engineer is available, treat ETVS as descriptive case-study evidence and avoid population-level significance claims;
- always pair engineering effort with post-extension held-out mission success.

## Failure analysis

Every failed run is assigned one primary category from a frozen taxonomy such as:

- perception/semantic interpretation;
- mission-model coverage/decomposition;
- planner/executive failure;
- capability/controller failure;
- runtime admissibility/authority;
- verification failure;
- infrastructure failure.

Infrastructure failures are fixed and affected runs repeated before final analysis; they are not counted as scientific failures.

Pre-register final metric definitions, freeze hashes, exclusion rules, and analysis scripts before the final campaign.

# 16. LunarBot hardware demonstration — after the simulation result is stable

The real-robot component is intentionally a **demonstration of runtime transfer**, not a third baseline experiment.

Purpose:

- show that the same authoritative mission runtime and typed capability interfaces drive the real LunarBot;
- show that real ROS/sensor feedback replaces simulator observations without changing the mission-level architecture;
- exercise one representative multi-step segment;
- produce a trace-linked natural-language mission report.

Keep the simulation/real joint names, HAL, rSkills, Nav2/MoveIt configuration, verifier interface, and Humble runtime aligned so transfer is primarily an endpoint/sensor-backend change.

Do not attempt to reproduce lunar environmental fidelity on Earth. Detailed hardware protocol will be designed later after the simulation claims are established.

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

**Status 2026-09-14 — split into B1/B2/B3, because "connected" and
"exit condition met" turned out to be far apart:**

- **B1 — done.** LunarBot HAL for base/arm/gripper (BODY_TWIST,
  CARTESIAN_TWIST, JOINT_POSITION, GRIPPER_BINARY) through the real C++
  kernel; `procedural` rSkill kind; kernel gaps F12/F16 fixed; `panel_remount`
  v1 scene. All verified by *scripted* dispatch — the reasoner has never
  been in the loop for this robot.
- **B2 — the capability set, §8.3.** Sensors, procedural manipulation
  skills, F19, Nav2, MoveIt, verifier, launch + run artifacts, remaining
  kernel checks. This is the bulk of the remaining Phase B work and is
  where the plan previously had a hole: it assumed upstream capabilities
  would "just resolve" for the chosen robot.
- **B3 — the original exit condition**, run for real: reasoner in the loop,
  a multi-step instruction, full trace in a §19 run directory. Only after B3
  is §21 item 6 (generic OpenRAL on Mission A) meaningful.

## Phase C — Long-horizon mission construction

- implement Mission A — **v2 of `panel_remount` per §6.4's status note**
  (multiple candidate components, an observable fault, a real approach);
- implement Mission B only after Mission A's orchestration needs are clear;
- expose simulator truth needed for independent verification;
- create scenario perturbation controls.

**Exit condition:** mission objectives can be evaluated independently of the reasoner's textual claims.

## Phase D — Mission-relevant space context only

- select the smallest set of lunar operational variables actually exercised by the final Mission A/B scenarios;
- for any communication/contact variable used, derive it from a documented profile/tool and make it affect real service availability;
- for any resource/health variable used, implement a transparent typed state and mission consequence;
- do not build unused SPICE/relay/thermal/resource infrastructure merely for completeness.

**Exit condition:** every implemented space-context variable changes an actual mission decision or availability condition in Experiment I/II and has documented provenance.

## Phase E — Authoritative mission runtime

- implement mission event schema/reducer/store;
- connect OpenRAL events and SRB verification;
- build dynamic reasoner context;
- add mission-level decision path;
- integrate authority and FDIR signals;
- link traces.

**Exit condition:** the foundation model can be restarted or changed without losing authoritative mission progress.

## Phase F — External baseline integration

- build/pin PLEXIL Release 6 and verify upstream examples;
- implement the LunarBot PLEXIL adapter through the shared capability/safety path;
- author Mission A/B model-covered PLEXIL plans;
- build/pin EUROPA and verify its examples;
- implement the EUROPA host/domain and online replanning loop;
- implement the EUROPA→PLEXIL execution bridge;
- normalize baseline logs into the common experiment schema.

**Exit condition:** PLEXIL, EUROPA→PLEXIL, and Ours all execute the same model-covered mission instances through the same capability stack and verifier.

## Phase G — Experiment-I freeze and campaign

- finalize covered development cases;
- generate/validate held-out cases with the closed-capability validator;
- freeze method artifacts and hashes before revealing final held-out cases;
- run paired covered/held-out campaigns for Mission A/B;
- compute ALFUS-grounded autonomy metrics and failure taxonomy.

**Exit condition:** the H1 evidence table/figures can be generated entirely from run artifacts.

## Phase H — Experiment-II extension study

- define one or two nontrivial extension cases;
- restore Experiment-I frozen states;
- perform timed, logged method-specific extension work;
- validate and re-freeze;
- run hidden post-extension cases;
- analyze ETVS, artifact deltas, and held-out mission success.

**Exit condition:** H2 can be evaluated without qualitative hand-waving about "ease of extension."

## Phase I — Targeted trustworthiness analysis

Only if necessary, run the single enforcement/verification ablation on selected Experiment-I scenarios and produce the mission-invalid-transition analysis.

## Phase J — LunarBot demonstration

Transfer one representative mission segment to hardware after the simulation results are coherent.

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

# 21. Immediate concrete tasks (revised after baseline/experiment redesign, 2026-09-14)

Do not interrupt the current LunarBot capability-set work. The scientific redesign changes what comes **after** the common stack is functional.

1. Finish LunarBot capability set §8.3 through the reasoner-in-loop Phase B exit condition.
2. Upgrade `panel_remount` to Mission A v2 with multiple components, semantic inspection, real navigation approach, deterministic verifier truth, and controllable covered/held-out condition switches.
3. Build a minimal Mission B only after Mission A's shared capabilities work; keep it compositionally distinct but smaller.
4. Create the common `capability_server`/adapter boundary that can be called identically by Ours and PLEXIL; verify that every route still passes through the same safety/verifier path.
5. Pin/build PLEXIL Release 6 and implement the LunarBot adapter; run one covered Mission A instance end-to-end.
6. Pin/build EUROPA and implement a minimal NDDL domain + host + EUROPA→PLEXIL activity bridge; verify online feedback and replanning inside the encoded domain on the same covered case.
7. Implement experiment scenario manifests, evaluator-only success annotations, freeze-manifest hashing, and the closed-capability validator.
8. Finish the proposed `space_runtime`/LLM/VLM mission path needed for Mission A; implement only the space-context variables actually exercised by final scenarios.
9. Run all three methods on covered development cases until infrastructure defects are removed; do not tune against final held-out cases.
10. Construct final held-out cases, freeze all method artifacts, and run Experiment I.
11. After Experiment I, define extension cases and implement timed engineering worklogs for Experiment II.
12. Only after both experiments are coherent, design the LunarBot hardware demo in detail.
13. Keep `docs/research_findings.md`, baseline integration notes, freeze manifests, and citation/source notes current.

# 22. Reference documentation reviewed for this plan

Baseline and metric implementation decisions in this plan are grounded in the following primary/official sources and must be rechecked against the pinned revisions used in experiments:

- PLEXIL Release 6 official repository (`plexil-group/plexil`) and User's Guide/Reference;
- PLEXIL Executive and InterfaceAdapter/Command/Lookup documentation;
- Estlin et al., NASA/TM-2006-213483, *Plan Execution Interchange Language (PLEXIL)*;
- NASA EUROPA official repository (`nasa/europa`), README, examples, and documentation;
- Bedrax-Weiss et al., NASA/NTRS 20050157874, *EUROPA2: Plan Database Services for Planning and Scheduling Applications*;
- JPL CASPER project documentation for continuous iterative-repair replanning;
- JPL MEXEC project documentation and MEXEC/ASTERIA publications for task-network planning/execution;
- JPL CADRE planning/scheduling/execution publications for current lunar onboard-autonomy context;
- JPL TaskNet project documentation for task-network authoring/knowledge-engineering burden;
- NIST SP 1011-II-1.0 ALFUS Framework for Human Independence and dynamic-planning metrics;
- Goodrich/Olsen HRI metrics as supporting operator-attention context;
- planning knowledge-engineering literature including MyPDDL for time-on-task/error measurement precedent;
- OpenRAL pinned source/documentation;
- Space Robotics Bench pinned source/documentation;
- NAIF SPICE and selected lunar communication/context references only for variables actually exercised in final scenarios.

Do not rely on summary prose in this plan when the exact upstream API or metric definition can be checked directly.
