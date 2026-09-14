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

**Status (2026-09-14):** `panel_remount` v1 exists
(`docs/mission_a_panel_remount.md`) and satisfies "one physical
restoration operation" and "a verifiable final condition" (a genuine
binary success termination — the first in SRB). It does **not** yet satisfy
the other three bullets: one pedestal+panel pair (no candidate
discrimination), the panel is 1.5 m from the spawn (no real approach
region), and the fault is "panel on the ground" (no inspection needed to
identify it). **v2 is required before any Mission A campaign** — Phase C
item, after the capability set (§8.3) works:

- ≥3 visually distinguishable infrastructure components (SRB library has
  solar panels, pedestals, sample containers, tools, bolts/nuts), one of
  which is in a fault state that must be *observed* to be identified
  (e.g. panel displaced vs. panels correctly mounted);
- service site placed so the robot must navigate a non-trivial approach
  (beyond the ~4 m flat pad, F18 — which means the terrain within the
  approach must be verified traversable, not assumed);
- restoration = remount; a fastening step (`bolt_hex_m8`, `screwdriver_hex_m5`)
  is a v3 candidate once JOINT_POSITION-precision manipulation is proven;
- simulator truth for every mission transition exposed on ROS (object
  poses already come via `/tf` as `srb/env0/<asset>`; the success
  termination via `/srb/env0/terminated`; add per-component fault-state
  truth as a topic the verifier — not the reasoner — reads).

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
   path.
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

# 9. Reasoner/context work package

## 9.1 Start with an unmodified generic harness baseline

Before adding space-runtime mechanisms, run the chosen mission with:

- OpenRAL's normal mission decomposition;
- normal world state;
- normal typed tools;
- no special mission-level space enforcement.

Capture exactly how it fails or succeeds under nominal conditions.

This becomes both a baseline and a diagnostic for what the new runtime actually needs.

**What "unmodified/generic" means here, precisely (2026-09-14):** the
reasoner (`ReasonerCore`, `reasoner_node`), `MissionState` +
`decompose_mission`, the tool palette, world state, the rSkill runner and
the safety kernel are stock. What is *not* stock, and is shared identically
by every baseline, is the LunarBot capability set (§8.3) and the SRB
deploy backend (§8.3 item 2b — `openral deploy sim` had no SRB scene
backend; it gains one, so the process graph and the mission text
(`--initial-task` → `initial_task_prompt` → `MissionState.from_prompt`)
go through the standard CLI). Baseline B in the paper is described exactly
this way. Nothing in the
capability set may encode mission logic (no "remount panel" skill — only
`grasp`, `move_ee_to_pose`, `navigate`, …), or the baseline comparison is
contaminated.

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

Because the simulated embodiment *is* LunarBot (§6.2) with identical joint
names, the RM-75 datasheet limits (`docs/lunar_bot_rm75_spec.md`) and the
Humble/3.10 runtime, the transfer surface is the HAL (`LunarBotSRBHAL` →
a real-driver HAL) and the sensor bridge; rSkills, manifests, Nav2/MoveIt
configs and the mission runtime carry over unchanged.

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

# 21. Immediate concrete tasks (revised 2026-09-14)

Status of the original list: 1–4 done; 5 written
(`docs/mission_a_panel_remount.md`) but **not usable yet** because 6's
preconditions are unmet (rule 0.11); 6–10 not started. Revised order:

1. ~~Repository skeleton + pins.~~ Done.
2. ~~`docs/openral_integration_notes.md`.~~ Done.
3. ~~`docs/srb_integration_notes.md`.~~ Done.
4. ~~Minimal ROS integration, one SRB action through the normal path.~~ Done, and extended to the full base/arm/gripper HAL (B1).
5. **Build the LunarBot capability set, §8.3 items 1–9, in order**, each verified live. This is the current work.
6. **Phase B3:** reasoner-in-the-loop multi-step run with a full §19 run directory. Phase B exit.
7. `panel_remount` v2 per §6.4's status note (Phase C start), with simulator-truth topics for every mission transition.
8. Run unmodified/generic OpenRAL on Mission A v2 (the original item 6); save traces; document concrete failure modes and missing semantics — now meaningful, because failures will be *mission-level*, not "no capability existed".
9. Only then implement the first `space_runtime` schemas/events required by observed mission-level failures (original 7).
10. In parallel with 5–8, create the SPICE/contact-profile preprocessing scripts and a typed `space_context` service; do not connect them to mission decisions until validated (original 8).
11. Prompt-only space-aware baseline before independent enforcement (original 9).
12. Keep `docs/research_findings.md` current (original 10). Findings that are *infrastructure gaps* (F11, F12, F16, F19, F20, the rSkill/sensor gaps) are fixed, not merely recorded — rule 0.12.

---

# 22. Reference documentation reviewed for this plan

The execution design above is based on the current public documentation/code structure of:

- OpenRAL repository README and architecture overview;
- OpenRAL reasoner reference and ROS reasoner package documentation;
- OpenRAL repo map, core schemas, roadmap, and `CLAUDE.md` engineering rules;
- Space Robotics Bench introduction, basic usage, environment configuration, new-task guide, and ROS 2 / Space ROS integration documentation;
- Inspect Robots repository documentation for task/policy/embodiment/scorer separation and Isaac Lab/ROS evaluation paths.

Because all three projects are active, the coding agent must verify the pinned revision before relying on any API/path stated in this plan.

