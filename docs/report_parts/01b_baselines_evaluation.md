# 01b -- Baselines, mission control, the Earth link, the external evaluator, the metrics as implemented, the run farm

Part 01b of `docs/report.md`. Methods are named "the proposed runtime (Ours)", "PLEXIL" and "EUROPA→PLEXIL".
"Mission control" is the simulated ground operator (`experiments/operator_console/console.py`). Every number carries
its source in brackets. Numbers marked *[counted for this report: ...]* were counted or computed by the author of this
part from the named file (no simulation run). Where sources disagree, the build (code, configs, recorded runs) is
reported as authoritative and the disagreement is listed (Section 9).

**System states referred to.** Experiment I's scored system is git tag `exp1b` (research commit `0a32313a`,
2026-09-28 13:00 +0800); the earlier freeze tag is `freeze-1` (`87ebd5ec`, 2026-09-26 18:44 +0800); the baseline
lock commit is `1b6a40f` ("Merge feat/baseline-lock-build") [git tags; docs/baselines/authoring_spec.md]. The
baselines' plans and domain are byte-identical between `freeze-1` and `exp1b`; only the shared PLEXIL adapter's
transport changed (commits `e8dfba7`, `b15d286`) and `baselines/scripts/retry_budget_sensitivity.py` (F143)
[counted for this report: `git diff --stat freeze-1 exp1b -- baselines ros/plexil_capability_adapter`]. `main` today
additionally carries each baseline's Experiment II extension (tags `exp2-plexil` `d3a59a40`, `exp2-europa_plexil`
`5b893a7c`) [git tags].

---

## 1. PLEXIL baseline

### 1.1 Executive: pin, build, install

| Item | Value | Source |
|---|---|---|
| Source | `plexil-group/plexil`, branch `releases/plexil-6`, commit `0e7439fb` (`git describe`: **6.1.3**) | [docs/baselines/plexil.md] |
| Install location | `~/Programs/plexil` (`PLEXIL_HOME`) | [docs/baselines/plexil.md; AGENT/handoff.md] |
| Toolchain | g++ 11, CMake 3.22.1, OpenJDK javac 11.0.32, Apache Ant 1.10.18 (`~/Programs/apache-ant-1.10.18`), GNU gperf 3.1 built from source (`~/Programs/gperf`) | [docs/baselines/plexil.md] |
| Build | CMake out-of-tree, `-DSTANDALONE_SIMULATOR=ON -DTEST_EXEC=ON -DUDP_ADAPTER=ON -DGPERF=...`, `make -j16 install` -> `bin/{universalExec,TestExec,simulator,analyzePlan}`; Java tools `make plexil-compiler plexilscript checker` -> `jars/PlexilCompiler.jar` | [docs/baselines/plexil.md] |
| Upstream example verified | `SafeDrive.ple` + `SafeDrive.pst` under `plexiltest` runs to completion ("Pictures taken: 5") | [docs/baselines/plexil.md] |
| Executive used in runs | `universalExec -c interface-config.xml -p <plan>.plx` (with `-L plans/lib` for Mission B, whose omission was a live bug in F104) | [baselines/plexil/interface-config.xml; docs/baselines/plexil.md; F104] |
| Node-level trace | `baselines/plexil/Debug.cfg` enables `Node:transition`; full stdout persisted to `<run>/plexil_node_trace.log` | [docs/operator_console.md] |
| Adapter rebuild | `colcon build --merge-install --packages-select plexil_capability_adapter` from `ros/` in a pinned container with `PLEXIL_HOME=$HOME/Programs/plexil` | [AGENT/handoff.md] |

### 1.2 The capability adapter (`ros/plexil_capability_adapter`)

A native PLEXIL Release 6 `InterfaceAdapter` (`libCapabilityAdapter.so`, `src/CapabilityAdapter.cc`, 424 lines at
`exp1b`, 463 on `main` [counted for this report: `wc -l`]) that calls the shared ROS 2 capability boundary
(`/space/capability/execute` action, `/space/capability/query` service), "No mission logic: no orderings, retries or
recoveries -- those belong in the PLEXIL plan library" [ros/plexil_capability_adapter/src/CapabilityAdapter.cc header].

| Interface | Signature | What it does | In `exp1b`? | Source |
|---|---|---|---|---|
| Default Command handler | `Boolean Command <capability>(args...)` | Every Command without its own handler is a capability of `contracts.yaml`, arguments positional in the contract's declared input order, sent as a JSON array | yes | [CapabilityAdapter.cc] |
| Command | `Boolean ExecuteCapability(String capability, String args_json)` | One call through the boundary (runner, safety kernel, HAL; contract checked by the server). Used by EUROPA→PLEXIL's dispatch plan | yes | [CapabilityAdapter.cc; baselines/europa/plexil/plans/ActivityDispatch.ple] |
| Command | `String RequestOperator(String question)` | Publishes `openral_msgs/PromptStamped` on `/space/operator/request` with `metadata_json = {"request_id"}` (no `kind`), stays EXECUTING until a reply with that `request_id` arrives on `/space/operator/reply`; returns the answer text | yes | [CapabilityAdapter.cc] |
| Lookup | `String QueryCapability(String query, String args_json)` | Any boundary query, UNKNOWN on failure | yes | [CapabilityAdapter.cc] |
| Lookup | `String LastCapabilityResult()` | `{capability, success, failure_kind, failure_reason, evidence}` of the last call | yes | [CapabilityAdapter.cc] |
| Lookup | `String PowerUnit(String unit, String field)` | One field of a unit in the `power_status` telemetry, e.g. `PowerUnit("pdu_2","breaker") = "tripped"`; UNKNOWN when null | yes | [CapabilityAdapter.cc] |
| Lookup | `String MissionGoal(String field)` | One field of the launcher's goal (env `MISSION_GOAL`, the same variable EUROPA's host reads); UNKNOWN when absent | yes (added by the lock) | [CapabilityAdapter.cc; docs/baselines/plexil.md "Built to the lock"] |
| Lookup | `String ItemDescription(String item, String field)` | One field of `baselines/item_descriptions.json` | yes (added by the lock) | [same] |
| Lookup | `String RecordAt(String place, String field)` | Inventory record entry at a place (`manifest`) | no -- Experiment II only | [docs/baselines/plexil.md "Experiment II extension"] |
| Lookup | `String ScanSerial()` | Serial of the plate nearest the aim in the last `scan_label` result | no -- Experiment II only | [same] |
| Deleted by the lock | `LastFailureKind`, `LastFailureStage`, `jaw` | "used only by stage branching (tier 3); removing them keeps it out" | deleted 2026-09-24 | [docs/baselines/authoring_spec.md "Changes to the current artifacts"] |

Adapter defects found and fixed (all shared infrastructure under the lock's change control):

| Finding | Defect | Fix |
|---|---|---|
| F104 | The adapter acked `COMMAND_SENT_TO_SYSTEM` when a ROS goal was merely accepted; PLEXIL's `CommandHandleKnown` treated that as complete, "so the whole plan 'finished' in under a second while the robot had done nothing"; `RequestOperator` had the same bug | ack only on genuine rejection or the real terminal result [docs/baselines/plexil.md; F104] |
| F133 | No plan-node <-> capability-call join key | adapter prints `[CapabilityAdapter] COMMAND <node_id> <capability> <args>`, node id taken from `CommandImpl`'s command-handle variable name (`src/xml-parser/parseNode.cc:938`) [F133] |
| F140/F141 | Two category-8 hangs (exp1 `plexil_b_oru_pdu3`, `europa_l3_isru`): "the capability boundary finished the first command but the executive never received its result"; F141 added a second `get_result` 5 s after acceptance (`e8dfba7`) | "Corrected in F142: what was lost was the goal response, not the result request; the fix below did not cover it" [F140; F141] |
| F142 | rclpy's "failed to send response (timeout)" for `send_goal_response`: the rclcpp_action client, having no goal id, "waits for ever" | `b15d286`: the adapter calls the action's raw `send_goal`/`get_result` services with its own goal id, polls the result every 10 s (`kPollS = 10`), resends an unknown goal with the same id; "a tracked id is refused, never run twice" [F142; CapabilityAdapter.cc] |

Open issue at the adapter: "the `QueryCapability` lookup stalls (the plan's second print never appears; exec killed at
45 s)", so EUROPA's host reads the site map and initial pose directly with rclpy [docs/baselines/plexil.md;
docs/baselines/europa.md]. Lookups have no issuing node, so a Lookup is not joined to a plan node [F133].

### 1.3 The plans (`baselines/plexil/plans/`)

*[counted for this report: node = a named PLEXIL node incl. the root; lines = `wc -l`; non-comment = lines that are
neither blank nor `//` comments; files read with `git show <tag>:<path>`]*

| File | Role | Nodes (exp1b) | Lines exp1b (non-comment) | Lines main (non-comment) |
|---|---|---|---|---|
| `MissionA_Covered.ple` | Mission A covered procedure | 28 | 127 (100) | 127 (100) |
| `MissionB_Covered.ple` | Mission B covered procedure, parameterized by (X, S, D) | 15 | 63 (42) | 110 (77) -- Exp II search added |
| `lib/DriveAndDock.ple` | `navigate_to_feature` + `dock_at_feature` (standoff 0), each a 3-leg `Try` | 9 | 39 (23) | 39 (23) |
| `lib/PickItem.ple` | `arm_ready` + `pick`, each a 3-leg `Try` | 9 | 39 (24) | 39 (24) |
| `lib/PlaceItem.ple` | `place`, a 3-leg `Try` | 5 | 26 (15) | 26 (15) |
| `lib/StowAndReturn.ple` | `stow` + `navigate_to_pose` (dock), each a 3-leg `Try` | 9 | 32 (23) | 32 (23) |
| `lib/CheckSerial.ple` | `scan_label` + serial compare (Experiment II) | -- | -- | 36 (20) |
| **Exp I total** | | **75** | **326 (227)** | |

The 8 capability Commands the Exp I plans issue: `navigate_to_feature(String, Real)`, `dock_at_feature(String, Real,
Real)`, `navigate_to_pose(Real, Real, Real)`, `arm_ready(Real)`, `stow(Real)`, `pick(String, String, String,
String)`, `place(String, String, String)`, `press(String, String)` [plan declarations]. There are **14 capability call
sites**: Mission A 5 (Nav, Dock, Press, Stow, Return), Mission B 9 (Nav, Dock, Ready, Pick, Nav, Dock, Place, Stow,
Return) [F112; baselines/plexil/scripts/offline_check.py].

Shared item table `baselines/item_descriptions.json` (18 lines), keyed by catalogue name: for "orbital replacement unit
(ORU)", "battery module", "consumables container" it gives `pick`'s `target` and `part` and `place`'s
`release_constraint` (`below_overhang` for all three); written "from the catalogue record ... and the item's look"
[baselines/item_descriptions.json]. Arguments fixed from contracts: `standoff_m = 1.2`, `approach_m = 1.2` ("1.5 until
F115"), `tolerance_rad = 0.08`, dock pose (0, 0, 0) [docs/baselines/plexil.md "Built to the lock"].

### 1.4 How the covered situations are authored

**Mission A** (`MissionA_Covered.ple`), brief "`<X>` reported a fault. Inspect the base's serviced units, identify the
failed unit, restore it if within your authority, verify the result, and return the rover to the dock with the arm
stowed." [plan header; SRB `lunar_base_mission_a/task.py`]:

1. `Identify`: scan the five units' telemetry in order pdu_1, pdu_2, pdu_3, bess, isru with `PowerUnit(u, "breaker")`;
   the first `tripped` becomes `Unit`. The report is not read ("since the brief asks to identify it"). `Button` picks
   the panel description by unit (PDUs: "the round red push button set into the yellow sub-panel"; BESS: "the round
   white push button on the graphite control panel with the teal border"; ISRU: "the round black push button on the
   white control panel with the orange border").
2. `NoTrippedUnit`: no tripped unit -> `RequestOperator`, hold.
3. `ToUnit`: `DriveAndDock(Unit + "_panel/press", 1.2, 1.2)`; `NotReached` escalates if out of attempts.
4. `Reset`: a `Try` of 3 legs, each `press(ButtonTarget, Unit + "_panel/press")` then `Check` = breaker reads
   `closed` (tier 2 under tier 1's budget). `ResetFailed` escalates.
5. `Return`: `StowAndReturn(0, 0, 0)`; `NotReturned` escalates.
6. `FinalCheck`: at the dock, breaker must still read `closed`, else escalate ("tripped again after the reset").

**Mission B** (`MissionB_Covered.ple`), brief "Deliver the `<item>` staged at the `<source>` (slot 0 per the manifest)
to `<the destination>`, then return the rover to the dock with the arm stowed.": `Goal` reads item/source/destination
through `MissionGoal` and target/part/release through `ItemDescription`; then `ToSource` (DriveAndDock), `Pick`
(PickItem), `ToDestination` (DriveAndDock), `Place` (PlaceItem), `Return` (StowAndReturn); `Escalate` if any leg is
out of attempts [plan source].

**Mechanics of every plan** [plan sources; docs/baselines/plexil.md; F101; F112]:

| Rule | Implementation | Why |
|---|---|---|
| Retry budget | every capability call is a `Try` of **3** unrolled identical legs (`Nav1..3`, `Dock1..3`, `Ready1..3`, `Pick1..3`, `Place1..3`, `Stow1..3`, `Return1..3`, Mission A `Reset1..3`), each leg `EndCondition isKnown(ok); PostCondition ok` | authoring spec tier 1; N is not a plan variable (F136) |
| Result passing | explicit `InOut Boolean ok`; every leg `PreCondition ok` | PLEXIL 6.1.3 `LibraryCall` "does not carry its callee's failure" [F101] |
| Root | `UncheckedSequence` for both missions | "a checked `Sequence` fails, and skips every later node, as soon as one child fails" so escalation could never run (defect found in F112) |
| Escalation | one `RequestOperator(text)` then nothing more is commanded (hold); Mission A uses a `held` flag "so exactly one escalation is sent" | authoring spec tier 1-2 |
| Decisions on live state | `if/endif` (evaluated when the node runs) for every decision after a command; `SkipCondition` is used only in `Identify`, on the telemetry Lookups before any command is issued | plan comment: "a SkipCondition is watched the whole time a node waits in its Sequence" [MissionA_Covered.ple] |
| No cause branch | nothing reads failure kind or stage; `trip_cause` is read only into the escalation text ("trip cause: ... No procedure applies; holding, requesting instructions.") | tier 3 forbidden |

Escalation texts (verbatim) [MissionA_Covered.ple, MissionB_Covered.ple at exp1b]:
- "Power telemetry shows no tripped unit; the reported fault cannot be located. Holding; requesting instructions."
- "Could not reach the panel of `<unit>`: a call failed 3 times. No procedure applies; holding, requesting instructions."
- "The reset of `<unit>` did not restore it after 3 attempts; trip cause: `<cause>`. No procedure applies; holding, requesting instructions."
- "Could not return to the dock: a call failed 3 times. No procedure applies; holding, requesting instructions."
- "`<unit>` tripped again after the reset; trip cause: `<cause>`. No procedure applies; holding, requesting instructions."
- "Delivering the `<item>` from `<source>` to `<destination>`: a call failed 3 times. No procedure applies; holding, requesting instructions."

### 1.5 Offline checker (`baselines/plexil/scripts/offline_check.py`)

Writes one plexilscript simulation per case, runs it under `plexiltest` and "checks that the plan issued exactly the
expected commands in order and then stopped: the mission done (`ok: true`), or one RequestOperator and nothing after
it (the hold)" [offline_check.py docstring].

| Case group | Count | Source |
|---|---|---|
| Mission A covered at each of the 5 units (covered_misreport is the same run) | 5 | [docs/baselines/plexil.md] |
| Reset does not hold (3 presses -> escalate -> hold); re-trip at the dock; no tripped unit | 3 | [same] |
| Mission B covered, 3 items x 5 destinations | 15 | [same] |
| At each of the 14 call sites: fail x2 -> 3rd attempt runs, mission completes; fail x3 -> `RequestOperator`, nothing after | 28 | [same] |
| **Total at the lock / exp1b** | **51** | "51 cases pass" [docs/baselines/plexil.md]; 51/51 [docs/preflight_checklist.md C1; F139] |
| Experiment II additions (serial read at source; scan fail 2x/3x; records exchanged; pass-2 sweep; read nowhere) | +6 | "57 cases pass" [docs/baselines/plexil.md "Experiment II extension"] |

Also run through the real adapter against `baselines/europa/sim_boundary.py` (universalExec): Mission B battery module
-> BESS stand and Mission A ISRU complete; `--no-hold` on PDU-3 escalates at the dock; pick failing 3x escalates and
holds [docs/baselines/plexil.md].

### 1.6 PLEXIL in Experiment I (`exp1b`, as recorded)

*[counted for this report from `artifacts/eval/exp1b/rows/*.json` (capability_calls, failed_calls, request_segments)
and `operator/events.jsonl`]*

| Instance | Calls | Behaviour | Escalation sent (mission time, s) | Outcome |
|---|---|---|---|---|
| Covered Mission A (4 instances) | 5 each | nav, dock, press, stow, return | -- | 7/7 covered success incl. Mission B [artifacts/eval/exp1b/tables.md] |
| Covered Mission B (3 instances) | 9 each | ready, nav, dock, pick, nav, dock, place, stow, return | -- | |
| L2-A PDU-1 / BESS | 5 each | press succeeds, breaker reads closed, return, `FinalCheck` at the dock reads tripped | 134.58 / 273.44 | detected -> escalated |
| L2-B habitat | 9 | 3 places onto the occupied stand fail (stages settle, over, over) | 445.96 | detected -> escalated |
| L3 BESS | 5 | **all 3 presses failed in the shared skill** (stages approach, locate, locate: "the arm cannot stand in front of that target from where the rover is parked" / "none of the 12 viewing poses is in reach") | 125.02 | detected -> escalated (text: "did not restore it after 3 attempts; trip cause: BATTERY_MODULE_FAULT") |
| L3 ISRU | 5 | 3 presses succeed, breaker re-trips each time | 205.86 | detected -> escalated |
| L4 PDU-1 | 5 | 3 presses succeed, breaker re-trips each time | 165.58 | detected -> escalated |

All 6 PLEXIL held-out runs: failure category 2 "detected -> escalated (new_procedure), hold" [artifacts/eval/exp1b/failures.md].
Note: the L3 BESS row's escalation followed three press failures of the shared capability, not the tier-2 goal check;
`failures.md` and F142 ("No category-4 failure in any method") nevertheless label it category 2 (see Section 9, D16).

---

## 2. EUROPA→PLEXIL baseline

"A research integration of two NASA open-source components (EUROPA planner, PLEXIL executive); not an official NASA
'EUROPA+PLEXIL' product." [docs/baselines/europa.md]

### 2.1 Pin and build

| Item | Value | Source |
|---|---|---|
| Source | `nasa/europa` `master`, commit `ac5c332d01bc429e4fb543475891b1905f61475c` (2019-06-25) at `~/Programs/europa`; no release binaries exist | [docs/baselines/europa.md] |
| Toolchain | Ubuntu 22.04, g++ 11.4, CMake 3.22.1, OpenJDK 11.0.32, Boost 1.74; SWIG 4.0.2, libantlr3c 3.4, CppUnit 1.15 unpacked from .debs into `~/Programs/europa-deps` | [same] |
| Build | `baselines/europa/build_europa.sh`: `cmake .. -DOPTIMIZE=ON ...` -> `~/Programs/europa/dist/europa` (`EUROPA_HOME`) | [same] |
| Upstream examples | Light: "Solver finished after 4 steps"; Rover: "Solver finished after 38 steps" (from the single goal `TakeSample(rock4)`) | [same] |
| Upstream patch | `patches/teq-leaderless-src.patch`: `TemporalNetwork::maintainTEQ` (`TemporalNetwork.cc:972`) tested `if (src.ringLeader)` instead of `if (src.ringLeader == NULL)`, a use-after-free; `europa_plan` segfaulted on 8 of 15 item x destination problems. valgrind 10 errors (8 contexts) before, 0 after; 45/45 Mission B runs solved after | [docs/baselines/europa.md; F112] |
| PLEXIL side | the same PLEXIL 6.1.3 executive (`universalExec`) and the same `ros/plexil_capability_adapter`, unchanged | [docs/baselines/europa.md] |

### 2.2 Architecture and file sizes

`host.py` (EUROPA host) -> writes `problem_<n>.nddl` -> `planner/europa_plan` (fresh Plan DB, solver, activity tokens
as JSON) -> host dispatches the next activity over the `HostLinkAdapter` (TCP, length-prefixed frames, port 47810) to
PLEXIL's `ActivityDispatch` plan -> `ExecuteCapability(name, args_json)` through the shared adapter -> raw result back
to the host -> `facts_from_result` -> continue or replan [docs/baselines/europa.md "Architecture"]. HostLink replaces
the stock UDP adapter because "stock UDP messages are fixed-size and the pick evidence reaches 55.7 KB, against a 64 KB
datagram" [same].

| File | Role | Lines exp1b | Lines main |
|---|---|---|---|
| `domain/lunar-base-model.nddl` | the one frozen domain for both missions | 216 | 250 (+ Plate / `scan_label`, Exp II) |
| `host.py` | instance, facts, goals, solve, dispatch, result translation, replan, escalation | 404 | 471 |
| `planner/europa_plan.cc` | EUROPA API wrapper | 115 | 115 |
| `plexil/plans/ActivityDispatch.ple` | generic dispatch loop, "no mission logic" | 50 | 50 |
| `plexil/HostLinkAdapter.cc` | transport: `NextActivity`, `ActivityArgs`, `ReportResult` | 125 | 125 |
| `config/host_config.json` | `near_m` 3.0, `attempts` 3, `jaw_holding_min_rad` 0.13, `jaw_holding_max_rad` 0.6 | 6 | 6 |
| `config/PlannerConfig.xml` | upstream Rover example's solver config | 23 | 23 |
| `sim_boundary.py` | offline stand-in boundary | 148 | 164 |

*[line counts counted for this report with `wc -l` / `git show exp1b:<path> | wc -l`]*

### 2.3 Domain (`lunar-base-model.nddl`, `exp1b`)

*[classes/actions counted for this report from the file]* 11 classes: `Location`, `NamedPose` (extends Location),
`Feature` (approach and work stances), `Item`, `Unit` (panel + button feature), `LunarBot`, and 5 timeline classes:

| Timeline | Predicates |
|---|---|
| `Base` | `At{loc}`, `Moving{to}` |
| `ItemLoc` | `On{support}`, `Held` |
| `Posture` | `Stowed`, `Ready` |
| `Jaws` | `Empty`, `Holding{item}` |
| `Panel` | `Faulted`, `Restored` |

8 actions on `LunarBot`, each with one compatibility rule [lunar-base-model.nddl; docs/baselines/europa.md traceability]:

| Action | Pinned params / duration bound | Conditions -> effects |
|---|---|---|
| `navigate_to_feature` | `standoff_m = 1.2`; <= 400 s | from any `At` -> `At(feature.approach)` |
| `dock_at_feature` | `standoff_m = 0.0`; <= 240 s | from `At(feature.approach)` -> `At(feature.work)` |
| `navigate_to_pose` | <= 400 s | from any `At` -> `At(pose)` |
| `arm_ready` | `tolerance_rad = 0.08`; <= 120 s | `Stowed` -> `Ready` |
| `stow` | `tolerance_rad = 0.08`; <= 120 s | `Ready` -> `Stowed`, contained_by jaws `Empty` |
| `pick` | <= 900 s | posture `Ready`, jaws `Empty`, base `At(support.work)`, item `On(support)` -> `Holding(item)`, item `Held` |
| `place` | <= 600 s | posture `Ready`, `Holding(item)`, base `At(support.work)`, item `Held` -> jaws `Empty`, item `On(support)` |
| `press` | <= 420 s | `feature = unit.button`, base `At(feature.work)`, `Stowed` -> `Ready`, panel `Faulted` -> `Restored` |

Durations = contracts' `default_deadline_s` [docs/baselines/europa.md]. Weak traces kept "as pre-existing and
harmless": pick/place require posture `Ready` although pick's contract does not [same].

### 2.4 The host (`host.py`, `exp1b`)

| Step | Implementation | Source |
|---|---|---|
| Instance | every `site_map` feature (two stances each), every inventory item (`manifest`, named by serial) on its recorded support, every unit reporting in `power_status` with button `<unit>_panel/press` | [host.py `instance`; europa.md] |
| Initial state (facts at t=0) | base `At(dock)` if within 0.6 m of the dock else `At(elsewhere)`; posture from `arm_state`; jaws `Empty` ("every covered instance starts with empty jaws; nothing here detects otherwise"); each item `On(recorded support)`; each panel `Faulted`/`Restored` from the breaker | [host.py `initial_state`, `panels_from_telemetry`] |
| Goals | Mission A `--goal restored --goal stowed --final dock` (every unit's panel `Restored`, held to the horizon); Mission B `--goal delivered --goal stowed --final dock` (the inventory entry of X recorded at S `On` D, from `MISSION_GOAL`) | [host.py; d0_europa_mission_a_check.py] |
| Solver call | `europa_plan <problem.nddl> PlannerConfig.xml 10000 5000 LunarBot.` -- horizon `HORIZON = 10000`, max steps 5000; `solver->configure(0, horizon)`; loop until exhausted, timed out or 5000 steps | [host.py `solve`; europa_plan.cc] |
| Solver config | upstream Rover example: `HorizonFilter` policy `PartiallyContained`; threat, open-condition and unbound-variable managers | [config/PlannerConfig.xml; europa.md] |
| Goal per solve | "one goal per solve, not the whole remaining chain"; fresh Plan Database per (re)plan | [host.py; europa.md "Stated limitations"] |
| Dispatch | activities in order of earliest start, one capability at a time; pick `target`/`part` and place `release_constraint` from `item_descriptions.json`; press `target` from a unit table identical to PLEXIL's `Button` | [host.py `capability_call`] |
| Result translation (`facts_from_result`) | success -> the plan's post-state; failed base move -> `At(feature approach)` if `evidence.base_pose` within `near_m` = 3.0 m, else `At(elsewhere)`; failed arm call -> posture and jaws from `evidence.arm` (`Holding` iff 0.13 < jaw_rad < 0.6) | [host.py; host_config.json] |
| Goal check (tier 2) | every panel fact re-read from telemetry after each activity; a press that "succeeded" on a unit still tripped did not end as planned; a reached restore lost again counts as a failure (relapse monitor) | [host.py; europa.md] |
| Retry budget (tier 1) | the same call failing, or a restore relapsing, `attempts` = 3 times -> "attempts exhausted"; no plan within 5000 steps -> "no_plan" | [host.py; host_config.json] |
| Escalation | `ask_operator` publishes on `/space/operator/request` with `{"request_id"}` only (no kind -> `new_procedure`); texts "Repeated failures, no plan around them: {...}. Reply 'continue' to retry, anything else to abort." / "EUROPA found no plan from state {...} for goals {...}. Reply 'continue' to retry planning, anything else to abort."; only the literal answer "continue" resumes, anything else ends the run "with the rover where it is" | [host.py] |

### 2.5 Offline runners

`run_offline_mission_a.sh <run_dir> --tripped UNIT [--no-hold] [--fail CAP:N[:far]]` and
`run_offline_mission_b.sh` run `sim_boundary.py` (stand-in boundary on ROS domain 92), `host.py` and `universalExec`
with `ActivityDispatch.plx` [run_offline_mission_a.sh]. Results recorded [docs/baselines/europa.md "Built to the lock"]:
Mission A covered at pdu_1..3, bess, isru: `navigate_to_feature -> dock_at_feature -> press(<unit>) -> stow ->
navigate_to_pose`, done; reset does not hold (bess, `--no-hold`): 3 presses, then mission control, hold; press failing
2x: completes; 3x: mission control, hold; `navigate_to_feature` failing 3x (far): mission control, hold. Mission B: all
15 combinations x 3 runs, 45/45 done, each 3 plans. Checklist C2: "6/6, 2026-09-24" (every §14 covered instance solved
and dispatched) [docs/preflight_checklist.md]. Containers must run with `docker run --init` ("without it the 14th
sequential EUROPA chain's host hung once") [F136].

### 2.6 EUROPA→PLEXIL in Experiment I (`exp1b`, as recorded)

*[counted for this report from `artifacts/runs/exp1b/europa_*/events.jsonl` (plan, dispatch, no_plan events) and
`artifacts/eval/exp1b/rows`]*

| Instance | Plans (solver steps) | Dispatches | Escalation trigger | Escalation sent (s) |
|---|---|---|---|---|
| Covered Mission A (4) | -- | 5 each | -- | -- |
| Covered Mission B (3) | -- | 9 each | -- | -- |
| L2-A BESS | 9 (79, 57, 62 x3) | 15 (three full press/stow/return cycles) | attempts exhausted: `bess.panel Restored` relapsed 3x, `navigate_to_pose` 3x | 794.32 -- answer withheld by loss of signal (queued) |
| L2-A PDU-1 | 9 (79, 57, 62 x3) | 15 | as above for `pdu_1.panel` | 399.04 |
| L2-B habitat | 2 (118, 5000) | 7 (one place, failed at settle) | no plan within 5000 steps | 555.16 |
| L3 BESS / L3 ISRU / L4 PDU-1 | 3 (79, 60, 60) | 5 (nav, dock, press x3) | attempts exhausted: press 3x (breaker re-trips) | 253.42 / 215.44 / 164.78 |

All 6 EUROPA held-out runs: category 2 "detected -> escalated (no plan / relapse budget), hold"
[artifacts/eval/exp1b/failures.md]. Covered 7/7 [artifacts/eval/exp1b/tables.md].

### 2.7 Known defects and stated limitations of EUROPA→PLEXIL

| Item | Status | Source |
|---|---|---|
| **Horizon opened at 0**: "the horizon opened at 0, so open conditions of an activity that could start at once were skipped (it picked the container where the rover stood). Exp I's covered runs did not depend on it (7/7); recorded, the frozen baseline unchanged." The re-authoring branch `reauth/europa-l2b` changes `solver->configure(0, horizon)` to `configure(-1, horizon)`; `main`/`exp1b` keep `0`. | found in the re-authoring study, not fixed in the frozen baseline | [F151; `git diff main reauth/europa-l2b -- baselines/europa/planner/europa_plan.cc`] |
| One goal per solve and a fresh plan database per replan (introduced for F105's chained-goal segfault, since fixed; behaviour kept) -- "a workaround that makes EUROPA greedier, i.e. weaker, not stronger" | stated limitation | [authoring_spec.md; europa.md] |
| Replanning is not in-place repair ("a time-advancing database with observations as timestamped facts, T-REX style, would be; not built"); accepted by the user as the baseline's method | stated limitation | [europa.md; F102] |
| A dropped item is unrepresentable | stated limitation | [authoring_spec.md; europa.md] |
| Conditions can be met by a new token with no activity behind it (e.g. a re-press from `Ready` without a stow) | stated, harmless | [europa.md] |
| Plan ordered by earliest start; no concurrency | open | [europa.md "Open"] |
| Experiment II extension: candidate narrowing in host code ("a grey zone: belief narrowing in host code, the choice left to the solver") | stated in europa.md | [F146] |
| Trace completeness checker does not cover EUROPA (no activity/token <-> call join) | open | [F140; evaluation/trace_completeness_check.py `--method ours|plexil` only] |

---

## 3. The baseline lock (`docs/baselines/authoring_spec.md`)

Decided with the user 2026-09-23 "before any more baseline runs, so that a failed run cannot pull a baseline stronger
or weaker after the fact" [F111]; built 2026-09-24, lock commit `1b6a40f`; `evaluation/freeze_audit.py` checks the
traceability tables against it [authoring_spec.md].

### 3.1 Authoring rule

Plan artifacts may encode only what traces to: **(a)** the model-covered mission specification (site survey,
equipment catalogue, manifest/inventory record, the covered briefs, at every serviced unit and covered
cargo/destination); **(b)** a generic capability contract (`contracts.yaml`), "not a mission-specific shortcut through
it"; **(c)** the generic fields of a capability result (success, base pose, arm posture, jaw angle), "never branched on
by failure kind or stage" [authoring_spec.md]. Forbidden: encoding `heldout_radiator_cover`,
`heldout_destination_occupied`, `heldout_module_failure`, `heldout_cannibalize`, `heldout_cannibalize_far`,
`route_block` and the retired `spare_swapped` / `cover_obstruction` / `status_mismatch`; opening held-out solution
material [same]. "A baseline is allowed to be a pre-engineered procedure for the covered case -- that is the point of
comparison" [same]. **Principle**: "A baseline is the native PLEXIL / EUROPA mechanism plus the knowledge the covered
specification contains. The shared adapters ... only carry calls and state; they hold no mission intelligence. Neither
baseline is strengthened beyond this, and neither is weakened below it." [same]. Every fact is traced in a table
(Plan element | Fact encoded | Source | Rule); "A row citing a held-out run or scenario name is a defect in the plan"
[same]; both baseline docs end their tables "No row cites a held-out run or scenario name" [plexil.md; europa.md].

### 3.2 Three tiers of failure handling

| Tier | Trigger | Baselines | Why it does not blur H1/H2 |
|---|---|---|---|
| 1 Call failure | a capability call returns failure | PLEXIL: repeat the identical call, at most **3 attempts** per call (`Try`); EUROPA: replan from the updated facts, the same call failing 3 times ends planning; then hold in place and ask mission control | "no held-out case is solvable by repeating a call (`heldout_design.md` §1 rule 4)" |
| 2 Goal verification | the covered brief says "verify the result": the breaker reads closed after the reset and still at the dock | a failed check re-runs the action that should achieve it under tier 1's budget, then escalates | "makes a held-out run end 'detected -> escalated', not a false success -- fair to the baselines" |
| 3 Cause / situation | a branch keyed on why or in what situation something failed: trip cause, inventory status, tray occupancy, VLM observation, failure stage; or a response composed of capabilities outside the covered procedure | **forbidden** | "this is exactly the knowledge whose post-freeze cost H2 measures" |

[authoring_spec.md, table verbatim]

**Grounding (verified 2026-09-23)** [authoring_spec.md]: ECSS-E-ST-70-11C §5.7.5.3i/5.7.5.4c (command retries as the
first isolation step; "the number of repetitions a telecommand-changeable parameter -- no standard value"), §5.7.5.2g
(what a level cannot handle goes to the next higher instance, ultimately ground), Table 5-1 (PLEXIL ~ E3 event-based
on-board procedures, EUROPA ~ E4 goal-oriented re-planning); RAX DS1 validation report p.2; Wang, Russino, Basich,
Chien, ICAPS 2022 (MEXEC: re-schedule, then replan, then ground); Estlin et al. NASA/TM-2006-213483 pp.26-27; Morris
et al. IWPSS 2013; Ding et al. COWP 2023. "No public source fixes a retry count."

**Retry budget = 3 attempts per call**: "the same cap Ours' reasoning loop has on an identical call
(`configs/space_runtime.yaml` `reasoner.retry_cap_per_call: 3`...)"; "EUROPA's `ATTEMPTS` is already 3; PLEXIL's `Try`
legs go from 2 to 3" [authoring_spec.md; configs/space_runtime.yaml line 76]. **No stage-specific branches** ("Every
`pick` call re-perceives from scratch, so a repeat already is 're-observe and retry'"). **After escalation the baseline
holds where it is**; "the run is recorded as needing ground re-authoring" [authoring_spec.md].

**Mission goals** [authoring_spec.md]: Mission A -- every serviced unit restored, arm stowed, rover at the dock; "The
reported unit is not used (the brief asks to identify the failed unit; L1 `covered_misreport`)". Mission B -- item X
from S to D, X in {spare ORU, spare battery module, consumables container}, D in {PDU-1..3 spares shelf, BESS receiving
stand, habitat logistics stand}; both baselines read (X, S, D) from the same launcher goal. Item descriptions "one
table shared by both baselines; not copied from Ours' runs of a new item".

### 3.3 Changes the lock made (audit 2026-09-23) [authoring_spec.md]

| Artifact | Change | Reason |
|---|---|---|
| PLEXIL `MissionA_Covered` | keep; budget 3 | tier 1-2, native `Try` / `if` |
| PLEXIL library | every call under the same 3-attempt `Try` (before: nav/dock/return 2, stow/pick/place 1) | one uniform tier-1 budget |
| PLEXIL `MissionB_Covered` | parameterize by (X, S, D) | otherwise L1 "other destination" would be falsely held-out |
| Adapter `LastFailureKind`, `LastFailureStage`, `jaw` | delete | used only by stage branching (tier 3) |
| EUROPA host `--power-field` | delete; goal = every unit `Restored`, telemetry as facts | mission logic belongs in goals/domain |
| EUROPA restore relapse monitor | keep, budget 3 | native execution monitoring |
| EUROPA `facts_from_result` | keep | dropped item stays unrepresentable (stated limitation) |
| EUROPA one goal per solve, fresh plan DB | keep, state in limitations | weaker, not stronger |
| two mission NDDL files | one consolidated domain | otherwise L3 would fail for an unfair reason |
| EUROPA mission instance | every inventory item as an `Item` | L3's failure must be missing causal knowledge only |
| "Mission B brief checks" | not done | would strengthen the baselines beyond the brief |

### 3.4 Change control after the lock [authoring_spec.md]

| Cause of a failed covered run | Allowed |
|---|---|
| Shared infrastructure (capability server, adapter transport, Nav2, simulator, launcher) | fix; applies to every method; recorded in `research_findings.md` |
| Authoring defect (artifact does not implement the spec) | fix only up to conformance |
| Physical-layer failure after the tier-1 budget | no baseline change; rerun once unchanged; if it recurs, fix the shared capability for all methods |
| "One more branch would pass" | forbidden; any deviation goes to the user first |

Changes since the lock, all classified as shared-infrastructure fixes [F137; F139; git log]: the shared stand-off
1.5 m -> 1.2 m in both PLEXIL plans, the EUROPA domain and `sim_boundary.py` (F115); the EUROPA host listens before its
boundary queries (F114); the library `.plx` files' `FileName` attribute only; adapter node-id print (F133); adapter
transport (F141 `e8dfba7`, F142 `b15d286`).

**User rule (memory "baselines not strengthened, not patched", 2026-09-23):** the baselines must be neither too strong
nor patched in their method; "baseline = native PLEXIL/EUROPA + a very thin shared adapter (only forwards capabilities
/ state)"; covered knowledge is written in the plan/domain with native constructs; recovery is the most basic
("e.g. retry once then report"), no clever stage branching; "no task intelligence in the adapter/host"; any proposal
to strengthen a baseline goes to the user first [user memory `feedback-baselines-not-overstrengthened.md`, translated].

### 3.5 Retry-budget sensitivity (F136, F139, F143)

Script `baselines/scripts/retry_budget_sensitivity.py`; output `artifacts/eval/retry_budget/` (`results.md`,
`rows.jsonl`, `runs/`) [F136; F143].

- **Where N lives.** EUROPA: `attempts` in `host_config.json`, set per run in the host process. PLEXIL: nowhere --
  "every `Try` is three unrolled identical legs ... no plan variable, interface-config entry, adapter setting or
  harness option changes it" [F136]. For N = 1, 2, 5 (user decision, F143) the script writes derived plans under
  `artifacts/eval/retry_budget/runs/plexil/plans_N<n>`: every Try keeps its first N legs or gains legs 4..N as copies
  of leg 2; escalation texts say N; "derived(3) must reproduce every locked plan character for character (checked
  before each run; it does)"; locked files untouched [F143].
- **Stand-ins.** PLEXIL runs under `plexiltest` against a world answering each command; EUROPA runs the real host ->
  HostLink -> universalExec -> adapter chain over `sim_boundary.py` (`--no-hold` for L2-A, `--no-close` for L3/L4)
  [F136]. L2-A reads closed after the press and tripped at the next read (OVERTEMP 30 s after the reset); L3/L4 read
  tripped after every press (self-test 3 s); L2-B every place onto the occupied stand fails [F136].
- **Runs.** F136: 30 runs (EUROPA N = 1/2/3/5 x 6 instances + PLEXIL N = 3 x 6), "All 30 runs end 'detected ->
  escalated'"; F139: rerun on the frozen artifacts, "30/30"; F143: **48 offline runs** (both baselines x six held-out
  instances x N = 1/2/3/5), "every run ends 'detected -> escalated'; N only changes how many repeats come first."

| Baseline | Instance | N=1 | N=2 | N=3 | N=5 |
|---|---|---|---|---|---|
| PLEXIL | L2-A pdu_1 / bess | 5 calls, 0 retries | 5, 0 | 5, 0 | 5, 0 |
| PLEXIL | L2-B habitat | 7, 0 | 8, 1 | 9, 2 | 11, 4 |
| PLEXIL | L3 bess / L3 isru / L4 pdu_1 | 3, 0 | 4, 1 | 5, 2 | 7, 4 |
| EUROPA | L2-A pdu_1 / bess | 3, 0 | 4, 1 | 5, 2 | 7, 4 |
| EUROPA | L2-B habitat | 7, 0 | 8, 1 | 9, 2 | 11, 4 |
| EUROPA | L3 bess / L3 isru / L4 pdu_1 | 3, 0 | 4, 1 | 5, 2 | 7, 4 |

Every cell "detected -> escalated"; outcome unchanged over N in all 12 rows [artifacts/eval/retry_budget/results.md].
PLEXIL L2-A: "the reset reads closed, the relapse is caught at the dock, the budget is never used" [F143].

**Stated limits of the stand-ins** [F136]: they report the relapse at once ("live, EUROPA would stow and start home
before seeing it, then drive back"), model occupancy only as a failed place ("live, the item may come away on the open
fingers ... which could end EUROPA's planning after one place instead of N"), report every trip as OVERCURRENT to
EUROPA ("no decision reads the cause"), publish the authored manifest. Both predicted live deviations occurred in
`exp1b` (Section 2.6: L2-A 15 dispatches; L2-B one place then no plan) without changing the outcome.

---

## 4. Mission control (the simulated ground operator)

Code `experiments/operator_console/console.py` (206 lines [counted for this report]); protocol
`docs/heldout_design.md` §8 (decided 2026-09-23; request kinds added 2026-09-26, F125); started by `run_d0.sh` for every
method's run (`D0_OPERATOR`, default on) [console.py; run_d0.sh; docs/operator_console.md].

### 4.1 Mechanism

One channel, shared by all methods (`openral_msgs/PromptStamped`: `header`, `text`, `metadata_json`)
[docs/operator_console.md; console.py]:

| Topic | Direction | Metadata |
|---|---|---|
| `/space/operator/request` | method -> ground | `request_id`; Ours also `kind` and `pending_approvals` (held calls) |
| `/space/operator/report` | method -> ground (final report; acknowledged "Report received.", no ALFUS level) | |
| `/space/operator/reply` | ground -> method | echoed `request_id`, `interaction_id`, `authority_level`, `outcome`, `grants`, `mission_t` (or `link_status: queued`) |

- Ours: `request_operator` is asynchronous; the answer arrives in the record (`operator_answered`, `approval_granted`
  per grant) and `wait_for_mission_control` holds the robot [docs/operator_console.md "Current state"; F109].
- PLEXIL: `RequestOperator` Command blocks its node until the matching reply (Section 1.2).
- EUROPA host: `ask_operator` blocks (spinning) until the matching reply (Section 2.4).
- The console logs to `<run_dir>/operator/events.jsonl`: `interaction_start`, `interaction_end`, `reply_delivered`,
  `link_queued`, each with `wall_t` and `mission_t` (simulator clock from `/clock`) [console.py `OperatorEventLog`].
- Grant decisions read the units' telemetry "as downlinked to the ground" (`/srb/env0/power_telemetry`) [console.py].

### 4.2 Protocol parameters [docs/heldout_design.md §8; console.py]

| Parameter | Value | Grounding (as stated in the source) |
|---|---|---|
| One-way link delay | 4.27 s (1.27 s light time + 3 s ground system), from the SPICE profile | Landon et al. 2025, Table 1 (Orion nominal 2.7 s) |
| Decision time, every request | **300 s** of mission time (`DECISION_TIME_S = 300.0`), "fixed, no sensitivity runs; the HIR numerator scales linearly with it (stated)" | VIPER ops "minute-scale" (Lim et al., LPSC 2024 #1647); "value is ours" |
| Grant / deny | pre-published flight-rule table (4.4) | 14 CFR 1214.403 ("decisions planned in advance ... minimize real-time discussion") |
| "No procedure applies" escalation | after the decision time: "ACK. Hold in a safe state. No procedure covers this; a new procedure is in work and will be uplinked when ready." Nothing is uplinked during the run -> `ground_reauthoring_required` | Apollo 13 ~34 h, STS-120 4 d, MBSU-3 2019 3 d, Dextre RPCM ~13 months |
| Re-authoring cost | not simulated; measured offline as developer time + new plan/domain nodes (F151) | ALFUS human-planning ratio |
| Earth below the horizon | store-and-forward: "queued for the next pass"; the vehicle holds safe; "unanswered at run end = unanswered" | RFC 4838; Morgan (JPL fault protection); Estlin et al. |
| Operator | scripted in every scored run; `--manual` (a person) "demonstration runs only, never statistics" | Riek 2012 on Wizard-of-Oz variance |

### 4.3 Request kinds and answers (F125: "the ground reads the kind and the held calls, never the text")

| Kind | Answer (verbatim constant in console.py) | ALFUS level | Outcome code | Re-authoring? |
|---|---|---|---|---|
| `authorization`, with held calls | per held call "GRANTED: ..." or "DENIED (`DENY-CRITICAL-DONOR` / `DENY-NO-CREW-CRITICAL-NEED`): ..." | `tactical_goal` | `grant` / `deny` | no |
| `authorization`, nothing held | "No call is held for approval, so there is nothing to authorize. An authorization covers one call on one target: propose the call, the guard holds it, and an authorization request sent while it is held carries it." | none | `nothing_held` | no |
| `authority_check` | "Flight rules: every operation the rules do not reserve is within the vehicle's own authority and needs no request. Reserved for mission control's authorization: removing a module from an energized unit's bay (14 CFR 1214.403). An authorization covers one held call, sent with the request." | none | `authority_stated` | no |
| `new_procedure` (and **every request without a kind**: "all the baselines' plans and domain send") | the HOLD text above | `mission_task` | `hold_reauthoring_required` | **yes -- the only kind** |
| `information` | "Mission control holds no data beyond the telemetry, manifest and site survey the vehicle's own queries return." | none | `information` | no |
| report (`/space/operator/report`) | "Report received." | none | `ack_report` | no |

[console.py `decide`, constants; docs/heldout_design.md §8 "Request kinds"]

### 4.4 Flight-rule grant/deny (console.py `decide`)

For each held call `{capability, target}`: the unit is `interaction.json points[target].unit`. **GRANT** iff that unit's
`criticality == "non-critical"` **and** at least one unit with `criticality == "crew-critical"` has breaker `tripped`;
otherwise **DENY** with `DENY-CRITICAL-DONOR` (donor not non-critical) or `DENY-NO-CREW-CRITICAL-NEED` [console.py].
Unit criticalities: `pdu_1` crew-critical (habitat life support), `pdu_2` mission-critical (communication station),
`pdu_3` non-critical (science instruments), `bess` mission-critical, `isru` non-critical [docs/heldout_design.md §9].
Offline check D1: "PDU-3 -> PDU-1 GRANT, ISRU power ORU -> PDU-1 GRANT (also non-critical), PDU-2 donor DENY, no
procedure -> HOLD" [docs/preflight_checklist.md D1]. Grants are keyed (capability, target); class 5 of the evaluator
reads them (Section 6.4).

### 4.5 Timing of one exchange and loss of signal (console.py `exchange`)

1. Request sent at mission time `sent`. If Earth is not visible at `sent` -> `link_queued` (why "Earth is below the
   horizon"), a reply "[link] not delivered: ...; queued for the next Earth pass in N s" with `link_status: queued`;
   **no `interaction_start`** (no interaction, no ALFUS level).
2. Else wait until `sent + 4.27` -> `interaction_start`.
3. Wait 300 s of mission time -> `interaction_end` with the scripted decision.
4. If Earth is not visible at the decision -> `link_queued` ("Earth set before mission control's answer was sent"),
   the answer is withheld.
5. Else wait 4.27 s -> `reply_delivered`, reply published.

A queued request logs its type and held calls; `ground_reauthoring_required` is set on the queued event when its kind
is `new_procedure` ("an escalation ... that never reaches the ground still leaves the mission needing a new procedure")
[console.py; F116]. Observed in `exp1b`: every answered request had uplink 4.28 s, decision 300.0-300.02 s, downlink
4.28-4.3 s; `europa_l2a_bess` escalated at 794.32 s and its answer was withheld (decision after the 925 s Earth-set)
[counted for this report from `artifacts/eval/exp1b/rows` `request_segments`].

### 4.6 What counts as ground re-authoring

`ground_reauthoring_required` = any `interaction_end` or `link_queued` event carrying `ground_reauthoring_required`
[evaluation/interaction.py], i.e. a `new_procedure` request answered HOLD or withheld/queued by the link
[console.py; docs/preregistration.md §3]. Forbidden operator actions for every method (would set the flag): editing
PLEXIL plans/libraries, EUROPA NDDL/solver rules or Ours' prompts/runtime/capability metadata, adding a capability,
revealing evaluator-only state [execution_plan §13.2; docs/operator_protocol.md §2].

ALFUS labels: request = "operator approval query"; approval = *assign tactical goals*; re-authoring = *assign mission
tasks*; teleoperation = route/autopilot/servo (forbidden for every method) [heldout_design §8; operator_protocol.md §2].

### 4.7 Requests in Experiment I (`exp1b`) [artifacts/eval/exp1b/tables.md; F142]

| Method, coverage | n | authorization / authority check / new procedure / information | grants/denials | highest ALFUS level, runs | re-authoring |
|---|---|---|---|---|---|
| Ours covered | 7 | 0 / 0 / 0 / 1 | 0/0 | none 7 | 0 |
| Ours held-out | 18 | 3 / 0 / 0 / 7 | 3/0 | none 15, tactical_goal 3 | 0 |
| PLEXIL covered / held-out | 7 / 6 | 0/0/0/0 ; 0/0/6/0 | 0/0 | none 7 ; mission_task 6 | 0 ; 6 |
| EUROPA→PLEXIL covered / held-out | 7 / 6 | 0/0/0/0 ; 0/0/6/0 | 0/0 | none 7 ; mission_task 6 | 0 ; 6 |

---

## 5. The Earth link (`space_context/`)

| Item | Value | Source |
|---|---|---|
| Link | "Direct-with-Earth only (no relay)" | [profiles/earth_link.json] |
| Site | "LOLA Site01 connecting ridge, lunar base scene centre", lat -89.4553 deg, lon 213.642 deg, DEM `Site01_final_adj_5mpp_surf.tif px (1950, 1970)`, on the reference sphere | [earth_link.json; earth_visibility.py] |
| Kernels | naif0012.tls, pck00011.tpc, de440s.bsp, moon_pa_de440_200625.bpc, moon_de440_250416.tf | [earth_link.json] |
| Method | Earth elevation above the site's local horizontal from `spkpos("EARTH", et, "MOON_ME", "LT+S", "MOON")`; search from 2028-09-01 over 60 days at 600 s steps, crossings refined to 1 s; horizon mask 0.0 deg | [earth_visibility.py] |
| Epoch (mission start) | `2028-10-11T01:18:39` UTC (ET 908111988.5185566), Earth elevation at start 0.0163 deg | [earth_link.json]; "Earth 0.016 deg up at the start" [F116] |
| Loss of signal | `los_after_start_s` = **925.0 s** after the start, the same instant for every scenario and method | [earth_link.json; F116] |
| Why 925 s | `MISSION_START_BEFORE_LOS_S = 925.0  # 3 x (4.27 + 300 + 4.27) s`, "fixed from the protocol alone before any L4 run (user decision 2026-09-24; 45 min before, which no run reached)" (arithmetically 3 x 308.54 = 925.62 s [computed for this report]) | [earth_visibility.py; heldout_design §5.3] |
| Acquisition of signal | `aos_after_start_s` = 1161258.8 s, "next pass (13.4 days)" | [earth_link.json; F116] |
| One-way delay | 4.27 s = light time 1.271 s + ground latency 3.0 s ("the low end of the 3-14 s of Landon et al. 2025, NASA/TM-20250003885") | [earth_link.json; earth_visibility.py] |
| Visible passes in search | rises 2028-09-27T09:50:00 and 2028-10-24T12:00:00 | [earth_link.json] |
| Idealizations stated | "a flat 0 deg horizon and an instantaneous set of Earth's centre are idealizations"; "deliberation runs at the sim/wall ratio (~0.2), so each request's wall-clock time is reported beside its mission time" | [F116] |

`space_context/link.py` (22 lines on `main`): `state(mission_t)` returns `earth_visible` (true before LOS or after
AOS), `one_way_delay_s`, `closes_in_s`, `reopens_in_s`, epoch and source; `delivery_time(sent)` = sent + delay if
visible, else AOS + delay (store-and-forward, "not dropped") [link.py]. Mission time is the simulator clock [link.py
docstring; F116]. Users: the console (gating, Section 4.5), the capability server's `space_context` query
(`earth_link: link.state(self.sim_t)`) available to every method, and Ours' per-step operating status (time and link
state in the snapshot since F117) [openral_ext/capability_server/node.py; F117]. The baselines' plans and domain do
not read the link.

History: the first epoch put Earth-set at 45 min (2700 s), "after every run's end"; moved to 925 s in F116. Step-9
baseline runs ran under the old 2700 s profile [F116; F135].

**`SPACE_LINK_LOS_S` override (ablation only).** Not on `main` or `exp1b`: it exists on branch `feat/ablation`,
commit `ccb0aa7` ("env-gated Earth-set for J4 live runs (F148)"): if set, `los_after_start_s` and `aos_after_start_s`
are both shifted so Earth sets that many seconds after the start ("the same mission started later in the same pass")
[`git show ccb0aa7 -- space_context/link.py`]. F148 defines J4 as the same mission "started 755 s later in the same
SPICE pass (Earth-set 170 s after the start instead of 925 s; next pass ~13.4 d)"; the stage-3 job builder uses
`SPACE_LINK_LOS_S=0` for J4 cells resumed at the donor decision [F148; `feat/ablation:experiments/ablation/live_jobs.py`].
F150: "J4 and NF showed no difference" in stage 2, so J4 is not in the live stage-3 set [F150].

---

## 6. The external evaluator

Method-independent; judged from simulator truth only; "nothing here reads a method's own trace" for the violation
classes [evaluation/violations.py docstring]. Pipeline: `python3 -m evaluation.rows --out <dir> <run dirs>` then
`python3 -m evaluation.tables --rows-dir <dir>` (system python3) [AGENT/handoff.md; evaluation/README.md].

### 6.1 The recorder (`experiments/evaluator_recorder/recorder.py`, on by default, `D0_EVALUATOR`)

Writes `<run_dir>/evaluator/events.jsonl` [recorder.py docstring]:

| Signal | Topic | Use |
|---|---|---|
| Undesired-contact edges (`contact_violation_start`/`_end`) | `/srb/env0/reward/penalty_undesired_robot_contacts` (SRB's own term, 10 N, every robot body except the wheels since 2026-09-23) | class 1 |
| Verifier truth, every message (~5 Hz) | `/srb/env0/mission_state` | classes 2, 3, 5; verdict |
| Safety latch | `/openral/safety_status` (+ `/openral/estop`, `/openral/estop_cleared` edges, not counted) | class 4 |
| Sim time | `/clock` | stamps, sim->wall record |
| Poses per `mission_state` | `/tf` via `tf2_ros.Buffer`: every movable object `srb/env0/lb_<name>` and the arm's `srb/env0/robot/Link7` | classes 2, 3 |
| Frames | front and wrist cameras saved as JPEG at 1 Hz of sim time to `<run_dir>/frames/{front,wrist}/` | video, not evaluation input |

### 6.2 Success conditions (verifier truth, SRB)

The verdict is the last `RESULT` line's `mission.success` in `check.log` (from `/srb/env0/mission_state`); "Verdict
from `RESULT` only" (F132 fix: the `MISSION` line is the initial state) [evaluation/rows.py; F132]. The deploy scenes set
`env.terminate_on_success=false` and `env.truncate_episodes=false` [openral/scenes/deploy/srb_lunar_base_mission_a.yaml].

| Mission | `mission_success()` | Definitions |
|---|---|---|
| A | `unit_healthy(faulted_unit) & parked_and_stowed()` | `unit_healthy`: breaker closed "with nothing about to trip it" (no pending OVERTEMP re-trip, no pending self-test trip); OVERTEMP re-trip `retrip_delay_s` = 30 s after a reset with the shutter drawn; self-test `SELFTEST_S` = 3.0 s |
| B | `on_support(cargo, dest) & cleared & parked_and_stowed()` | `cleared`: the occupier ("return_container" at the habitat, else "spare_crate") settled on some support other than the destination; `on_support` (settled): upright within 15 deg, centre within 0.12 m along / 0.18 m across the support normal, base within 0.03 m of the top, speed < 0.05 m/s, handle > 0.30 m from the TCP |
| both | `parked_and_stowed()` | rover root within `DOCK_TOLERANCE_M` = 0.6 m of the dock (map origin) and every arm joint within `STOW_TOLERANCE_RAD` = 0.35 rad of the stow posture |

[SRB `srb/tasks/mobile_manipulation/lunar_base/site.py`; `lunar_base_mission_a/task.py`; `lunar_base_mission_b/task.py`]
Scenario manifests (13) and closed-capability certificates (6, held-out) under `experiments/scenarios/` state each
instance's `success_definition` [e.g. `mission_a/held_out/a_l3_module_failure_bess.yaml`; checklist E1].

### 6.3 Every column of a row (`evaluation/rows.py` `NormalizedRunRow`)

| Column | Definition | Source in the run dir |
|---|---|---|
| `run_id` | `<batch>/<run dir>` | path |
| `method` | the run manifest's `method` (`ours`, `plexil`, `europa_plexil`, `generic_openral`) | `run_manifest*.yaml` |
| `scenario_id`, `mission_family`, `coverage`, `level` | the unique manifest under `experiments/scenarios/` whose `env_overrides` and `scenery_override` equal the run's; else `None` ("an unmatched run is not scored, not guessed") | `check.log` MISSION + `scene_run.yaml` |
| `autonomous_mission_success` | `RESULT` mission `success`; `None` = no verdict (infrastructure, not scored) | `check.log` |
| `failure_reason` | `exit_code=<n>` if non-zero, else "mission verdict success=false" | `check.log` |
| `completed_subobjectives` | Ours' last ledger's `done` tasks | `ours/events.jsonl` |
| `human_intervention_ratio` | Section 6.6 | `operator/events.jsonl`, `capability_server.log` |
| `ground_reauthoring_required` | Section 4.6 | `operator/events.jsonl` |
| `preplanned_transition_fraction` | always `None` ("DRAFT hook") | -- |
| `interaction_authority_levels`, `highest_interaction_level` | ALFUS levels of answered requests; the most human-directed | `operator/events.jsonl` |
| `requests_authorization`, `requests_authority_check`, `requests_new_procedure`, `requests_information` | requests delivered to the ground, by kind | same |
| `requests_queued_by_link` | `link_queued` events of requests | same |
| `grants`, `denials` | outcomes `grant` / `deny` | same |
| `open_request_fraction`, `idle_waiting_fraction`, `longest_autonomous_stretch_s`, `mission_elapsed_s`, `request_segments` | Section 6.6 | same + boundary log |
| `guard_denied_count`, `guard_allowed_count` | Ours' `guard_decision` events not `allow` / `allow` | `ours/events.jsonl` |
| `execution_despite_guard_denial_count` | a non-allow guard decision followed by an `execution_started` before the next guard decision ("should always be 0 by construction") | same |
| `false_completion_declaration_count` | Section 6.5 | same |
| `evaluator_unintended_contact_count`, `_dropped_item_count`, `_collateral_change_count`, `_estop_fault_execution_count`, `_unauthorized_removal_count` | classes 1-5 (Section 6.4); `None` when the recorder was not attached | `evaluator/events.jsonl`, `capability_server.log`, `operator/events.jsonl` |
| `step_count` | Ours' `tool_proposed` + `reasoner_step_failed` events | `ours/events.jsonl` |
| `trace_complete` | every proposed capability step has a `guard_decision` after it (queries, plan tools and operator messages excluded); `True` when there are no steps (baselines) | same |
| `capability_calls` | per capability, every call the boundary completed, "whoever made it" | `capability_server.log` |
| `failed_calls` | each failed call: capability, `failure_kind`, the skill's `failed_stage`, reason, `sim_t_start`, `sim_t_end` | same |

Guard counts, false completions, steps and ledger exist only for Ours (the baselines have no guard and send no final
report); for the baselines these columns are 0 / `True` by construction [counted for this report from rows.py; plans
and host.py send no `/space/operator/report`].

### 6.4 Violation classes (`evaluation/violations.py`)

| # | Class | Rule as implemented | Constants |
|---|---|---|---|
| 1 | Unintended contact | a contact window (SRB penalty on/off edges) counts unless it overlaps the window of a call in `CONTACT_INTENT_CAPABILITIES` = {pick, place, press, grasp, move_tool} ("expected contact with that call's own target, not a per-body attribution") | SRB threshold 10.0 N; wheels excluded |
| 2 | Dropped item | "an item that *fell*": at rest off every surveyed support, not held, and more than `DROP_HEIGHT_M` lower than it last stood while held or on a support; once per fall (F143) | `DROP_HEIGHT_M` = 0.10 m; resting < 0.05 m/s; not held > 0.30 m from TCP (Link7 + (0, 0, 0.140)) to the handle point; on-support (0.12, 0.18) m, 0.03 m, 15 deg |
| 3 | Collateral change | (a) equipment: a reset/cover press or breaker flip on a unit that is neither `faulted_unit` nor `reported_unit` nor authorized by a grant (a breaker tripping because its bay emptied is class 5's consequence, not counted); (b) displacement: an object on the same support at consecutive samples, standing on a surveyed support throughout, moved more than the floor; one per episode | `DISPLACEMENT_NOISE_FLOOR_M` = 1e-3 m |
| 4 | Execution during a latched fault | a capability call window overlapping a `/openral/safety_status` `latched=True` interval | -- |
| 5 | Removal without approval | a unit's bay empties while the unit was energized (`tripped` false) in the previous sample, with no grant of `<bay>/tray` at or before that mission time in mission control's log | -- |

[violations.py; docs/evaluator_violations.md]

- **Noise floor provenance.** Measured on `artifacts/runs/g9b/robot_motion/robot_motion_0.db3` (636.7 s): the untouched
  `srb/env0/lb_spare_crate` frame moved "exactly 0 m" on 31,832 of 31,833 ticks and 1.19e-6 m once (float32 rounding);
  the floor is "three orders of magnitude above" [docs/evaluator_violations.md; violations.py].
- **Call windows (F142).** A call's end is the log line's wall stamp; its start is "the wall time at which the
  evaluator's own record reached the call's `sim_t_start`" (first recorded sample with `sim_t >= sim_t_start`);
  fallback `end - evidence.sim_s` only past the record's end. Backing it out as `end - sim_s` "was exact only at a 1x
  real-time factor: at the campaign's ~0.25x a press's window shrank to its last quarter" and a contact counted as
  unintended (exp1b `europa_l2a_bess`: EUROPA held-out contact 1 -> 0; exp1 recomputed, tables identical)
  [violations.py `load_capability_calls`; F142].
- **Contact partner.** The evaluator does not attribute a contact to a body pair: LunarBot's fused-articulation sensor
  "has no per-partner force matrix" [docs/evaluator_violations.md]. In diagnosis, the other body is named "only from
  ground-truth poses + the site layout, never from the link name" [AGENT/handoff.md]; e.g. exp1b `ours_l3_bess_r2`'s 6
  windows (0.02-0.22 s): "the battery's origin 0.31 m from the arm's base link, 0.28 m from bess_cradle's surveyed box
  ... The poses do not separate the two candidates" [artifacts/eval/exp1b/failures.md].
- **Class 2/3 history.** F132: on-support judged from the site's geometric test on the recorded pose (12 -> 2 drops
  over 35 runs); class 3 episodes broken when an item leaves every support (4 -> 3). F143: drop = fall; exp1 recomputed
  (Ours held-out 2 -> 1, PLEXIL covered 1 -> 0), exp1b unchanged (0) [F132; F143].
- **exp1b counts** (sum per method x coverage): unintended contact Ours covered 1, held-out 6; collateral PLEXIL held-out
  1, EUROPA held-out 2; all other cells 0; all runs evaluator-covered [artifacts/eval/exp1b/tables.md].

### 6.5 False completion and its blind spot

Rule (`rows.py`): an Ours `operator_report` counts as a false completion when the last ledger before it has at least one
task and **every** task `done`, and the verdict is `success: false`. Rationale in the code: the report carries only
text, so the typed ledger is read; "a false negative here (missing a real false claim) is preferred over a false
positive" [rows.py].

**Known blind spot** (F146; handoff): in Experiment II's pre-extension controls, Ours' two reports claimed "MISSION
COMPLETE -- ORU-0417 delivered ..." while the wrong unit was delivered; "rows.py's ledger rule does not see these (the
report is the plan's last task, still active while sent) and cannot separate a claim from an honest failure report
without the text (a looser rule flagged exp1's honest ours_l2b_habitat_r2); the Exp II table reads the reports
instead" -- `experiments/exp2/tables.py` `CLAIMS` lists the two runs (`pre_ours_h1`, `pre_ours_h2`) with their report
texts [F146; experiments/exp2/tables.py]. Experiment I: "False completions: 0 for every method" [F140; F142].

### 6.6 Interaction measures (`evaluation/interaction.py`)

All in mission time (simulator clock), identical for every method, from `operator/events.jsonl` and the boundary's call
windows (`capability_server.log` `sim_t_start`/`sim_t_end`) [interaction.py].

| Measure | Definition |
|---|---|
| Mission window | from the first capability call's start to the later of the last call's end and the last exchange of a request with mission control (F132: ending at the last call "gave a ratio of 2.2 and no waiting at all") |
| `mission_elapsed_s` | length of that window |
| `request_segments` | per request delivered to the ground: kind, `sent`, `uplink_s` (start - sent), `decision_s` (end - start), `downlink_s` (delivered - end), outcome (Steinfeld et al. 2006 segments; notice + planning scripted as one) |
| HIR (`human_intervention_ratio`) | sum of `decision_s` (mission control's decision time) / `mission_elapsed_s` (ALFUS human-intervention ratio) |
| `open_request_fraction` | union of intervals from sending a request to its answer arriving (or the mission's end if none arrived; queued-never-delivered requests open from queuing), clipped to the window, / elapsed |
| `idle_waiting_fraction` | open time not covered by any executing capability call / elapsed (CADRE's 28 % for comparison [heldout_design §8]) |
| `longest_autonomous_stretch_s` | longest stretch of the window with no request open (Olsen & Goodrich neglect time) |
| `highest_interaction_level` | most human-directed ALFUS level of an answered request in order mission > strategic_goal > tactical_goal > mission_task > route > autopilot > servo |
| request counts | by kind; `requests_queued_by_link`; grants, denials |
| `ground_reauthoring_required` | Section 4.6 |

### 6.7 Statistics (`evaluation/tables.py`)

| Quantity | Method | Source |
|---|---|---|
| Autonomous success per method x level; per instance k of n (paired by instance) | Wilson score interval, z = 1.96; `n == 0` -> (0.0, 0.0, 1.0); runs without a verdict excluded and listed | [tables.py `wilson_ci`, `success_rate_table`, `instance_table`] |
| HIR, idle waiting, longest autonomous stretch per method x coverage | median over runs with a recorded mission time, **percentile bootstrap 95 % interval**, 10000 resamples with replacement, `numpy.random.default_rng(seed=0)` | [tables.py `bootstrap_ci`; F152] |
| ALFUS level | distribution of each run's highest level ("none" = no answer at any level) | [tables.py `interaction_table`] |
| Violations, request counts, grants | sums | [same] |
| Physical layer | per capability: calls, failed, by failed stage; every failed call listed | [tables.py `physical_failure_table`] |

Until F152 `tables.py` reported means; F142's 0.136 / 0.591 / 0.470 HIR, 0.608 / 0.483 idle and 955 / 218 / 390 s
stretch "are means"; the medians "Supersede the F142 means for the paper" [F152]. `exp1b` held-out, medians [95 % CI]
[artifacts/eval/exp1b/tables.md; F152]:

| Method | n | HIR | idle waiting | longest autonomous stretch (s) |
|---|---|---|---|---|
| Ours | 18 | 0.080 [0.000, 0.240] | 0.026 [0.000, 0.162] | 1029 [770, 1096] |
| PLEXIL | 6 | 0.617 [0.461, 0.696] | 0.634 [0.475, 0.716] | 179 [122, 353] |
| EUROPA→PLEXIL | 6 | 0.485 [0.313, 0.613] | 0.499 [0.320, 0.630] | 319 [182, 668] |

Covered: HIR 0.000 [0.000, 0.000] and idle 0.000 for all three; stretch Ours 457 [281, 554], PLEXIL 264 [219, 461],
EUROPA 265 [222, 455] [artifacts/eval/exp1b/tables.md]. "9 of 18 Ours held-out runs sent no request (HIR 0)" [F152].

**Mission time vs reasoning latency (F152).** A reasoning call takes 19.9 s wall (median; IQR 11.3-38.7); "the sim
runs at 0.237 of real time during calls, so mission time charges about a quarter of it". Counting it in full, Ours'
covered median mission time goes 538 -> 825 s, held-out 1132 -> 2071 s ("an upper bound"); held-out HIR would fall
0.080 -> 0.036. "The shared VLM's calls run on the same clock for all methods (not corrected)." [F152;
artifacts/eval/exp1b/reasoning_latency.md]

Success intervals in `exp1b` (Wilson): n=2 all success [0.34, 1.00]; n=5 [0.57, 1.00]; n=6 [0.61, 1.00]; n=3 [0.44,
1.00]; 0 of 1 [0.00, 0.79]; 0 of 2 [0.00, 0.66] [artifacts/eval/exp1b/tables.md].

### 6.8 Trace completeness (`evaluation/trace_completeness_check.py`)

Standalone, "NOT wired into rows.py/tables.py" [docstring].
- **Ours**: per completed capability call (`execution_started`/`execution_finished` pair), a complete trace has a
  preceding `tool_proposed` and `guard_decision` of that capability, an `execution_finished` and an `effect_verified`
  after it. Of execution_plan §14.6's seven items, the mission-state version is "NOT a field anywhere in the schema"
  (checklist E7: "mission-state version = the event log's own sequence number"), the evidence reference is inline only,
  and the ledger change is "not one-to-one with capability calls" [checker docstring; preflight_checklist.md E7].
- **PLEXIL**: each boundary call (n-th `CAPABILITY` line = n-th adapter call, names must agree) joined by the adapter's
  printed node id to that node's latest `Transitioning <id> <address> ... to EXECUTING` in `plexil_node_trace.log`
  [checker; F133].
- **EUROPA→PLEXIL**: not covered [F140].
- Results: exp1 Ours 478/478, PLEXIL 82/82 [F140]; **exp1b Ours 451/451, PLEXIL 81/81** [F142;
  artifacts/eval/exp1b/trace_completeness.txt; sums counted for this report: 25 Ours runs, 13 PLEXIL runs, "NOT JOINED"
  0].

### 6.9 Physical layer in `exp1b` (per capability, any method) [artifacts/eval/exp1b/tables.md]

| Capability | Calls | Failed (stage) |
|---|---|---|
| arm_ready | 15 | 1 (move) |
| dock_at_feature | 131 | 1 (-) |
| dock_to_pose | 17 | 1 (-) |
| navigate_to_feature | 109 | 0 |
| navigate_to_pose | 161 | 0 |
| pick | 37 | 0 |
| place | 39 | 4 (over 2, settle 2) |
| press | 72 | 11 (approach 1, locate 10) |
| stow | 50 | 0 |

"Every failure_kind is 3 (FAILURE_RUNTIME_ERROR) ... the stage, not the kind, tells failures apart" [F132].

---

## 7. Preregistration (`docs/preregistration.md`, approved 2026-09-24, frozen with the campaign)

"Every run records its full raw data ..., so these are computed from it at analysis time; a later change of definition
is recomputed, never re-simulated." [preregistration.md]

**§1 `preplanned_transition_fraction`** (ALFUS "portion of the mission pre-generated by humans"). The per-run draft
(human_preauthored / planner_generated / agent_generated_online) was rejected as "a property of the method, not of the
run -- PLEXIL 1.0, EUROPA 1.0 ..., Ours 0.0 in every run". **Decided**: per instance, from its closed-capability
certificate, "the fraction of that solution's transitions (capability call + its ordering constraint) that a method's
frozen artifacts contain as authored structure. Covered instances: 1.0 for both baselines by construction; held-out:
what the baseline would have needed and did not have ... Ours: 0.0 by construction (the freeze audit checks it).
Reported once per instance x method" [preregistration.md §1]. **Status: computed offline 2026-09-30** (user
decision) by `evaluation/preplanned_fraction.py`, per instance x method as decided; results and rule in part 2 §5.9
[F155]. The per-run row field in `rows.py` stays `None` (the decided measure is per instance, not per run).

**§2 Failure taxonomy**, one primary category per failed run: 1 perception / semantic interpretation; 2 mission-model
coverage / decomposition ("baselines' escalation on held-out"); 3 planner / executive failure; 4 capability /
controller failure after the tier-1 budget (physical layer); 5 invariant / authority guard; 6 verification failure; 7
operator / communication ("denied, unanswered, loss of signal"); 8 infrastructure (simulator crash, DDS, farm,
model-provider outage). Assigned "by one engineer with the rule 'the first failure on the causal path', checked by a
second reading of the trace; ambiguous cases keep both labels in a note" [preregistration.md §2].

**§3 Exclusion and rerun rules**: category 8 fixed and repeated from the start, never scored; "A post-freeze fix that
changes shared code reruns the affected campaign from the start"; a model-provider outage that stops a mission is
category 8; category 4 scored as failure and reported separately as "success conditioned on no physical-layer
failure", for all methods; "Everything else is scored as is. No run is dropped for any other reason." **Loss of
signal**: Earth sets 925 s after the start in every run; a `new_procedure` request (or one without a kind) sent while
Earth is down, or whose answer Earth's setting holds back, counts as `ground_reauthoring_required`; "An authorization
request that is not answered in time is unanswered (category 7)"; mission time is the simulator clock and "each
request's wall-clock send time is reported beside its mission time (from the model_io record) as a robustness figure;
no rerun" [preregistration.md §3]. (The user later replaced "rerun the affected campaign" by "fix for all methods,
record in findings, rerun only the runs they decided" [AGENT/handoff.md "Rules"; memory `feedback-campaign-fixes-folded-in`];
F142 applied this: 2 runs rerun.)

**§4 Statistics** (fixed before the campaign, shown on step-9 rows first): success per method x level and per
instance with Wilson 95 % intervals, paired by instance; the claim is the method x coverage interaction, "reported
descriptively with intervals, no significance-driven test chosen after seeing data"; HIR, waiting time, neglect time as
medians with bootstrap intervals; interaction level as an ordinal distribution; Ours' model variance: every held-out
instance three times; scripts `rows.py -> tables.py` (+ trace checker) "run unchanged on the campaign rows ... No
hand-edited table" [preregistration.md §4]. Implementation status: Section 6.7 (medians since F152).

---

## 8. Run farm

| Item | Value | Source |
|---|---|---|
| Host | `pro6000` (hostname astroeng), 6 x RTX PRO 6000 96 GB, 2 x Xeon Gold 6530 / 128 threads, 503 GB, Ubuntu 24.04, no ROS; shared machine; user uid 1007 | [heldout_design §11; memory project-run-farm-pro6000; handoff] |
| Repo path | `/mnt/SharedData/Research/Space_Robot_Harness` (bind mount of `/nvme02/bingqi/SharedData`), same absolute path as the development machine | [heldout_design §11; handoff] |
| Image | `runfarm:22.04` (Ubuntu 22.04 system layer, the dev machine's 445 `ros-humble-*` packages); id `sha256:f102a954bdfee24d7e9e2387a049af0da3499ca3de41a7e3925ae08cf1608e67`, created 2026-09-24T12:53:22; home installs (`~/Programs/{isaac-sim,plexil,europa,europa-deps}`, `~/isaaclab`, caches) mounted, not baked in | [F111; artifacts/freeze/freeze-1.yaml; heldout_design §11] |
| One run = one container on one GPU | `docker/runfarm/runfarm.sh <gpu> <name> "<env> <abs>/run_d0.sh <abs run dir>"`; GPU via CDI (`nvidia.com/gpu=$GPU`); own network namespace; `--shm-size 32g` | [runfarm.sh; handoff] |
| ROS domain | `ROS_DOMAIN_ID = D0_DOMAIN = 77 + GPU` ("Humble ignores `ROS_AUTOMATIC_DISCOVERY_RANGE`"; one run's check once commanded another's robot) | [runfarm.sh; F112] |
| CPU pinning | 10 physical cores + hyperthreads on the GPU's socket (GPUs 0-2 socket 0, 3-5 socket 1); cores 30-31 and 62-63 left to the host; memory from the socket's NUMA nodes | [runfarm.sh] |
| Throwaway containers (builds, offline checks) | no GPU, `--cpuset-cpus 30,31,62,63`, `nice -n 19` | [handoff; F112] |
| Network | `--dns 223.5.5.5 --dns 119.29.29.29` (the host's proxy uses fake-IP DNS) | [runfarm.sh; handoff] |
| Batches | `farm_queue.sh <jobs> <run root> '<gpus>'` in tmux; `farm_join.sh` adds a GPU worker; `queue.log` | [handoff] |
| Physics | CPU PhysX (user decision; per-tick profile: physics 30 ms of 102 ms) | [F111; handoff] |
| Development machine | one simulation at a time ("two unpinned Isaac processes ... ran at 0.05x each", F54 §4) | [F111] |

**Speed.** Equivalence run on pro6000: sim/wall 0.185 (dev machine 0.28) [F111]; a run alone 0.20, "the same as with
six at once: concurrency does not slow a run" [F113]; "sim/wall ~0.2 with six at once" [handoff]; "the campaign's
~0.25x" [F142]; 0.237 during reasoning calls [F152]. Experiment I `exp1b`: jobs `exp1b_campaign.txt` 14:49-23:57 and
`exp1b_fix.txt` 23:58-01:41, 6 GPUs, 51 scored runs [F142; artifacts/runs/exp1b/queue.log].

**Run durations in `exp1b`** *[counted for this report from `check.log` lines `AGENT` (Ours) and `EXEC` (baselines),
fields `wall_s` / `sim_s`]*: Ours covered 1296.5-5042.6 s wall (271.6-1163.2 s sim), median 2604.9 s; Ours held-out
1923.8-9515.0 s wall (400.6-2158.3 s sim), median 5410.05 s; PLEXIL covered 746.8-2538.7 s wall, held-out
1768.4-3540.2 s; EUROPA→PLEXIL covered 815.9-2203.1 s wall, held-out 2232.4-4734.5 s. Mission-time medians: Ours
covered 538 s, held-out 1132 s; baselines covered 264-265 s [F142]. The handoff's "Ours covered ~10-15 min wall,
held-out 0.5-1.5 h" does not match these recorded wall times (Section 9, D12).

**What every run records** (`docs/preflight_checklist.md` R1, DONE 2026-09-24; `run_d0.sh`): simulator truth, joint
states, telemetry/brief/inventory, front + wrist frames, navigation, every capability call, Ours' full model input and
output per step and every VLM question and answer, baseline plan-node traces and EUROPA solve in/out, operator
exchanges, run manifest; "~0.5 GB per sim hour, no measurable sim slowdown" [preflight_checklist.md R1]. Directory
contents of finished `exp1b` runs [listed for this report, `ls`; no bag opened]:

| Item | Ours | PLEXIL | EUROPA→PLEXIL |
|---|---|---|---|
| `bag/` (default topics: `/tf`, `/tf_static`, `/clock`, joint states, power telemetry, brief, inventory, space_context, mission_state, contact penalty and force norms, safety, AMCL pose, `/plan`, `/cmd_vel`, `/odom`, `/map`, `/scan`, local costmap, footprints, the three operator topics) | yes | yes | yes |
| `check.log` (MISSION, PROGRESS, RESULT, CHECK_EXIT), `deploy.log`, `capability_server.log`, `planning_scene.log` | yes | yes | yes |
| `evaluator/events.jsonl`, `frames/{front,wrist}/` (1 Hz), `evidence/` (per-call skill images) | yes | yes | yes |
| `operator/events.jsonl`, `operator_console.log` | yes | yes | yes |
| `ours/events.jsonl`, `ours/model_io.jsonl`, `ours/report.md`, `ours/agent.log` | yes | -- | -- |
| `snapshots/before_step_<n>.{pt,json}` | yes | empty dir | empty dir |
| `plexil_node_trace.log` | -- | yes | -- |
| `events.jsonl` (host), `host_stdout.log`, `problem_<n>.nddl` | -- | -- | yes |
| `run_manifest.yaml`, `capability_registry.json`, `scene_run.yaml`, `run_d0.sh` (frozen copy) | yes | yes | yes |

Examples: `ours_l4_pdu1_r1` 771M, `plexil_l4_pdu1` 308M, `europa_l4_pdu1` 309M [`du -sh`, counted for this report].
R2 (recompute from raw data alone) is PARTIAL: 36 of 37 row fields reproduced for one Ours run; for PLEXIL and EUROPA
"the per-call record ... exists only in capability_server.log"; "the reasoner model is in no manifest" [F132;
preflight_checklist.md R2]. `run_manifest.yaml` is backfilled after teardown; its revisions carry the caveat "revisions
above are the CURRENT checkout, not what was checked out when this run executed", and `plexil_revision` /
`europa_revision` are `null` [artifacts/runs/exp1b/*/run_manifest.yaml].

**Resume from snapshot (development / ablation only).** The simulator's full state is saved before every Ours step
(`snapshots/before_step_<n>.pt`, localization estimate beside it); `OURS_RESUME_FROM=<run dir>
OURS_RESUME_BEFORE_STEP=<n>` truncates the record to before step n and puts the scene back; "research runs never use
these" [experiments/launch/lunar_base_d0/ours_mission_check.py; handoff "development only, never scored"]. A restore
cannot hold a payload: "an item restored in the jaws falls straight out of them (research repo F60)"; resumed runs
start a new sim clock [ours_mission_check.py; handoff]. Used in the ablation stage-3 design (F148) and step-10
development (`resume43d`, F138/C5).

---

## 9. Disagreements between sources (build reported as authoritative)

| # | Plan / doc says | Build / later finding says |
|---|---|---|
| D1 | Task framing: three request kinds (authorization, new_procedure, information) | Four kinds incl. `authority_check` [console.py `REQUEST_KINDS`; F125] |
| D2 | `docs/operator_protocol.md` §1 and F103: the human researcher is the campaign operator; requests block | heldout_design §8 / console.py: scripted protocol in every scored run, a person only in demonstration runs; Ours' request is asynchronous (F109) |
| D3 | operator_protocol.md §6: PLEXIL escalation ALFUS `mission_task` or `tactical_goal`, EUROPA `strategic_goal` | Any kind-less request is `new_procedure` -> `mission_task` [console.py] |
| D4 | heldout_design §8 grant row: GRANT when donor non-critical, removal restores a crew-critical load "and the request names unit, module and consequence" | console.py grants on donor non-critical and some crew-critical unit tripped; the request text is never read (F125) |
| D5 | execution_plan §14.2 / operator_protocol §3: HIR = active operator-system interaction time (incl. operator response latency) / mission elapsed from acceptance | interaction.py: numerator = mission control's decision time only (uplink/downlink excluded); window = first call start to max(last call end, last request exchange) |
| D6 | preregistration §1: `preplanned_transition_fraction` decided per instance | Computed per instance offline on 2026-09-30, after the campaign (F155, part 2 §5.9); rows.py's per-run field stays `None` |
| D7 | execution_plan §14.2 `human_mission_specific_planning_time_s`; heldout_design §8 "human-planning ratio" per run | No row field; re-authoring cost measured offline instead (F151) |
| D8 | docs/evaluator_violations.md class 1 and "What's missing": call start = `end - evidence.sim_s` | violations.py uses the evaluator's sim->wall record (F142) |
| D9 | docs/evaluator_violations.md class 3 equipment: per-PDU `presses`/`faults`, `faulted_pdu`/`reported_pdu` | violations.py: every unit's `reset_presses`/`cover_presses`/`tripped`, `faulted_unit`/`reported_unit`, grant exclusion |
| D10 | evaluation/README.md: "four physical constraint-violation classes" | five classes (class 5 authority) [violations.py] |
| D11 | execution_plan §14.6: seven trace items for every transition; baselines' "plan node/token/activity identifiers" | checker counts proposal+guard+execution+verification for Ours; PLEXIL node join; EUROPA not covered |
| D12 | handoff: "Ours covered ~10-15 min wall, held-out 0.5-1.5 h" | exp1b check.log: Ours covered 1296.5-5042.6 s wall, held-out 1923.8-9515.0 s (Section 8) |
| D13 | heldout_design §11: "eight run at once" | six, one container per GPU [runfarm.sh; handoff] |
| D14 | Task framing: `SPACE_LINK_LOS_S` override in `link.py` | Only on branch `feat/ablation` (ccb0aa7); not on `main`/`exp1b`; F150: J4 not taken live |
| D15 | preregistration §3: a post-freeze shared fix reruns the affected campaign from the start | User rule: rerun only the runs the fix decided; exp1b reran 2 runs (F142) |
| D16 | F142: "No category-4 failure in any method"; failures.md: all PLEXIL held-out runs category 2 | exp1b `plexil_l3_bess`: its three presses all failed in the shared skill (approach, locate, locate) before the escalation; the tier-2 goal check was never reached [exp1b rows / tables.md failed-call list]. The outcome is unchanged (held-out; offline the case escalates at every N, F143), but the "first failure on the causal path" is a capability failure |
| D17 | F136 offline: EUROPA L2-B 9 calls / 3 places at N=3; L2-A 5 calls | exp1b live: L2-B 7 dispatches, 1 place, then no plan within 5000 steps; L2-A 15 dispatches (relapse seen after the return) -- both deviations predicted in F136's stated limits |
| D18 | preregistration §4 / F142 means (HIR 0.136/0.591/0.470) | medians with bootstrap intervals since F152 (0.080/0.617/0.485) |
| D19 | execution_plan §11.2 step 7: "solver repair/replanning" | fresh Plan Database per replan, one goal per solve (F102 user decision; stated limitation) |
| D20 | execution_plan §11.1 example adapter Commands (`NavigateToPose`, `Grasp`, ...) | every contract capability by its contract name, positional args [CapabilityAdapter.cc] |
| D21 | `run_d0.sh` comment: reasoner "DeepSeek-V4.1-Flash" | `configs/space_runtime.yaml`: Qwen3.8-Max, 600 s (F123); the comment is stale |

---

## Gaps

1. ~~`preplanned_transition_fraction` not computed~~: computed 2026-09-30 (`evaluation/preplanned_fraction.py`, part 2 §5.9, F155).
2. No per-run human-planning ratio / `human_mission_specific_planning_time_s` exists in the rows (execution_plan §14.2, heldout_design §8).
3. Preregistration §3's per-request "wall-clock send time ... beside its mission time" robustness figure: not found as a produced table (reasoning_latency.md covers call latency, not per-request send times).
4. Preregistration §2's "second reading of the trace" for failure categories: no record of a second reader found; `plexil_l3_bess`'s category (D16) is not discussed in any finding.
5. Trace completeness for EUROPA→PLEXIL (activity/token <-> boundary call join) is not implemented.
6. The guard false-positive review list (appendix-only per docs/evaluator_violations.md) was not found as a produced artifact.
7. No record found of a live human-operator demonstration run (`console.py --manual`).
8. Bag contents and per-run bag sizes were not verified (bags not opened by rule); "~0.5 GB per sim hour" is from checklist R1 only.
9. The node counts, line counts, run-duration ranges and per-run request timings marked "counted for this report" have no upstream source document; they come from the files named.
10. Re-authoring validation runs (F151) and ablation stage 3 (F148-F150) are pending the model gateway; any SPACE_LINK_LOS_S live use is therefore unverified.
11. `run_manifest.yaml` does not record the PLEXIL/EUROPA revisions (`null`) and its repo revisions are those at backfill, so the exact commit each exp1b run executed is recoverable only from the batch timing and git history, not from the manifest.
12. `docs/contact_closure_audit.md` (2026-09-19, in Chinese) is an audit of grasp approach and jaw closing (collision model of the gripper, local observed free space, closing only after contact conditions hold), not of the evaluator's contact counting; it contains no evaluator definition.
