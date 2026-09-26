# PLEXIL baseline (execution_plan §1.5, §11.1, §21.5)

## Pin and build (2026-09-17)

- Source: `plexil-group/plexil`, branch `releases/plexil-6`, commit `0e7439fb` (`git describe`: **6.1.3**),
  cloned to `~/Programs/plexil` (`PLEXIL_HOME`).
- Toolchain: g++ 11, CMake 3.22.1, OpenJDK javac 11.0.32,
  Apache Ant 1.10.18 (`~/Programs/apache-ant-1.10.18`, no apt), GNU gperf 3.1 built from source
  (`~/Programs/gperf`; required by the XML parser's generated expression map).
- Executive (CMake, out-of-tree, in-tree install):
  `cd plexil-build && cmake $PLEXIL_HOME -DCMAKE_INSTALL_PREFIX=$PLEXIL_HOME -DSTANDALONE_SIMULATOR=ON -DTEST_EXEC=ON
  -DUDP_ADAPTER=ON -DGPERF=$HOME/Programs/gperf/bin/gperf && make -j16 install` → `bin/{universalExec,TestExec,simulator,analyzePlan}`.
- Java tools (ant on PATH): `make plexil-compiler plexilscript checker` → `jars/PlexilCompiler.jar` etc.
  (The autotools `make tools` stops on missing gperf; CMake with `-DGPERF` is the route.)
- PATH without conda (its python breaks builds); `scripts/` on PATH for `plexilc`, `plexiltest`.
- Upstream example verified: `plexilc examples/basic/SafeDrive.ple` + `scripts/SafeDrive.pst` →
  `plexiltest -p SafeDrive.plx -s SafeDrive.psx` runs to completion ("Pictures taken: 5").

## Adapter: `ros/plexil_capability_adapter` (skeleton)

Option 1 of §1.5 (native InterfaceAdapter calling the ROS 2 boundary) -- smaller than the IPC route, keeps typed
results. `libCapabilityAdapter.so`, loaded by `universalExec -c config/interface-config.xml` (`LibPath`), exposes:

- `Boolean Command ExecuteCapability(String capability, String args_json)` → `/space/capability/execute`
- `String Lookup QueryCapability(String query, String args_json)` → `/space/capability/query`
- `String Lookup LastCapabilityResult()` → JSON {capability, success, failure_kind, failure_reason, evidence}

No mission logic. Verified (offline boundary, domain 91): a plan calling `ExecuteCapability("fly", "{}")` receives
`false` and the boundary's refusal (failure_kind 20) through the adapter.

Open for §21.5: the `QueryCapability` lookup stalls (the plan's second print never appears; exec killed at 45 s) --
lookup threading vs the executor; typed per-capability Commands (NavigateToPose(Real, Real, Real) …); the Mission A
covered plan library; run through the live graph.

## Mission B: library and adapter Lookups (2026-09-19, offline; nominal path)

Scope for this pass (coordinator decision): infrastructure first -- the authoring rule (docs/baselines/authoring_spec.md),
the adapter's typed failure Lookups, and reusable library-node skeletons verified on the nominal path only. The
predefined recovery set and the live check script (`d0_plexil_mission_b_check.py`) are **not** written yet: pick/place's
reported failure kinds and stages are still moving in a parallel session, and writing recovery against them now would
be redone.

### Adapter: two typed failure Lookups (deleted 2026-09-24 by the lock, see "Built to the lock")

`ros/plexil_capability_adapter/src/CapabilityAdapter.cc` gained, beside the existing `LastCapabilityResult`:

- `Integer Lookup LastFailureKind()` -- the last result's `failure_kind` (`openral_msgs/ExecuteRskill`: 0 = none/success,
  1 config, 2 capability mismatch, 3 runtime, 4 e-stop, 5 perception stale, 6 planning, 7 deadline, 8 cancelled, 255
  unknown; 20 = boundary rejection, `capability_server/node.py`), read directly off the action result -- no parsing.
- `String Lookup LastFailureStage()` -- the last `"stage": "<value>"` field in the result's `evidence_json` (a staged
  skill -- pick, place, stow, arm_ready, press -- reports its stages as an ordered array; this is the last one, i.e.
  where it stopped), found with a plain text scan (`last_stage()`), not a JSON parse. `""` when the evidence carries
  none.

Both are a mechanical read of state the adapter already held for `LastCapabilityResult`; no interpretation of what a
kind/stage means for recovery -- that stays in the plan library, never the adapter. Built offline: `colcon build
--packages-select space_harness_msgs plexil_capability_adapter` (PLEXIL_HOME set, conda off PATH) compiles clean; not
run against the live boundary in this pass.

### Reusable library (`baselines/plexil/plans/lib/`)

`DriveAndDock(feature, standoff_m, approach_m, ok)`, `PickItem(target, part, item, ok)`, `PlaceItem(support,
release_constraint, item, ok)`, `StowAndReturn(dock_x, dock_y, dock_yaw, ok)` -- each a `LibraryAction` composed of
the model-facing capabilities Ours uses (never `engineering: true`), positional arguments in `contracts.yaml`'s
declared order. **Nominal path only**: one call per capability, `PostCondition ok` on each, no retry/back-off/stage
branching yet.

Result convention -- `ok` is an explicit `InOut Boolean`, not the `LibraryCall` node's own outcome. Verified against
6.1.3 (`plexiltest`, injected `command-failed` on `dock_at_feature`): a `LibraryCall` node's default outcome does
**not** mirror its callee's outcome (a library whose root node computed `FAILURE` still left the calling node
`SUCCESS`); PLEXIL's own regression suite works around exactly this with an explicit
`PostCondition <call>.outcome == SUCCESS` (`compilers/plexil/test/input/CallWithPostCondition.ple`), but that pattern
did not propagate through a further level of nesting here either. The tested, robust pattern is the one PLEXIL's own
`library-call1.ple`/`array-library-call.ple` regression tests use: an explicit `InOut` result parameter. Every call
site in `MissionB_Covered.ple` carries `PreCondition ok` before the next `LibraryCall`, so once a leg's `ok` goes
`false` no further capability call is issued (all later nodes `SKIPPED`) -- the plan's safe state until a real
recovery ladder replaces it.

### Mission B covered plan (`baselines/plexil/plans/MissionB_Covered.ple`)

"Deliver the spare ORU staged at the depot stand (slot 0 per the manifest) to the spares shelf of PDU-1, then return
the rover to the dock with the arm stowed." `ToDepot` (DriveAndDock on `depot_stand/slot_0`) -> `Pick` (PickItem,
target/part/item) -> `ToShelf` (DriveAndDock on `pdu_1_shelf/shelf`) -> `Place` (PlaceItem, `below_overhang`) ->
`Return` (StowAndReturn to the map origin).

### Traceability (nominal path; superseded by "Built to the lock" below)

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `ToDepot`: `feature` | `depot_stand/slot_0` | site_knowledge, `R/artifacts/runs/g4a/ours/events.jsonl:3` (`points`) | (a) |
| `ToShelf`: `feature` | `pdu_1_shelf/shelf` | site_knowledge, same event; mission brief names PDU-1 | (a) |
| `Return`: `dock_x/y/yaw` | `(0.0, 0.0, 0.0)` | site_knowledge `dock`, same event; matches `MissionA_Covered`'s `ReturnToDock` | (a) |
| `DriveAndDock`: `standoff_m` / `approach_m` defaults | `1.2` (1.5 until F115's shared fix) | `contracts.yaml` `navigate_to_feature.standoff_m` / `dock_at_feature.approach_m` documented defaults | (b) |
| `PickItem`/`StowAndReturn`: tolerance args | `0.08` | `contracts.yaml` `arm_ready.tolerance_rad` / `stow.tolerance_rad` documented default | (b) |
| `Pick`: `target`, `part` | ORU / bail-neck description | Ours' own covered-instance calls, `R/artifacts/runs/g8d,e/ours/events.jsonl` (`tool_proposed` `pick`), read-only | (a) |
| `Pick`: `support` | `depot_stand/slot_0` | same as `ToDepot`'s `feature`; caught by a live run failing at `find` without it (F104) | (a) |
| `Pick`/`Place`: `item` | `"spare_oru"` | `openral_ext/capability_server/node.py` `ITEM_NAMES`; capability added F78 | (b) |
| `Place`: `support` | `pdu_1_shelf/shelf` | site_knowledge; mission brief | (a) |
| `Place`: `release_constraint` | `"below_overhang"` | `contracts.yaml` `place.release_constraint` (T-shaped bail = overhanging head); matches Ours' covered calls `R/artifacts/runs/g8s,g8t/ours/events.jsonl` | (a)/(b) |
| `PickItem`: `arm_ready` before `pick` | ordering | not required by `pick`'s contract; matches Ours' covered-instance call order, `R/artifacts/runs/g8d/ours/events.jsonl` | (a) |

No row cites a held-out run or scenario name. Recovery rows (failure kind/stage -> branch) are deferred to the next
pass, once pick/place's reported kinds and stages stop moving.

### First live run, end to end (2026-09-22; F104)

`MissionB_Covered.plx` now runs to a genuine `delivered: true, success: true` on the live, corrected-arm graph
through the shared capability boundary and the same evaluator Ours uses
(`artifacts/runs/plexil_mission_b_success_20260922`). Getting there fixed two real bugs, not the plan's own logic:

- `d0_plexil_mission_b_check.py` was missing `-L plans/lib` (Mission A's flat plan never needed a library path).
- The adapter (`ros/plexil_capability_adapter/src/CapabilityAdapter.cc`) acked `COMMAND_SENT_TO_SYSTEM` the instant
  a ROS action goal was merely *accepted*, which PLEXIL's own `CommandHandleKnown` treats as good enough to consider
  the command complete -- so the whole plan "finished" in under a second while the robot had done nothing. Fixed:
  no ack on acceptance, only on genuine rejection or the real terminal result. `RequestOperator` had the identical
  bug, fixed the same way. Full account, including the `py-spy` diagnosis: F104, `docs/research_findings.md`.
- `PickItem` was missing `pick`'s optional-but-practically-required `support` argument.

The predefined recovery set is still not written (pick/place failure kinds are now settled by F92-F100, so this is
now unblocked).

## Mission A: rewritten onto the shared `press` capability (2026-09-22)

`MissionA_Covered.ple` originally bypassed `press` with eight of its own stage-level Cartesian primitives (close
jaws, plan/servo pre-press, approach, press, retract, re-ready, dating from before `press` existed as a whole
capability). Rewritten to a single `press(target, feature)` call, composed from the same reusable library Mission B
uses (`DriveAndDock`, `StowAndReturn`) instead of duplicating them -- three top-level nodes now, not thirteen.
`press`'s own contract does not need `arm_ready` first ("plans its own way from wherever the arm is"); Ours' own
covered-instance run called it anyway and it failed harmlessly, confirming the contract's claim rather than
contradicting it, so it is not in the rewritten plan. Offline-verified (`plexiltest`,
`scripts/MissionA_Covered_nominal.pst`) before any live time -- one non-ASCII character (`§` in a comment) broke
the `plexilscript` compiler's lexer the first time; `MissionB_Covered_nominal.pst`'s own comments had already
worked around this by spelling "section" out, not noted anywhere until this rewrite hit it too.

### Traceability (nominal path; superseded by "Built to the lock" below)

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `ToUnit`: `feature` | `pdu_2_panel/press` | mission brief ("PDU-2 reported a fault"); site_knowledge | (a) |
| `Press`: `target` | "the round red push button set into the yellow sub-panel" | Ours' own covered-instance call (`R/artifacts/runs/mission_a_success_20260922/ours/events.jsonl`) | (a) |
| `Press`: `feature` | `pdu_2_panel/press` (the one docked at) | same as `ToUnit` | (a) |
| No `arm_ready` before `Press` | not required | `contracts.yaml` `press`'s own documented claim, and Ours' covered-instance call failing it harmlessly | (b) |
| `Return`: `dock_x/y/yaw` | `(0.0, 0.0, 0.0)` | site_knowledge `dock`; matches `MissionB_Covered`'s `Return` | (a) |

No row cites a held-out run or scenario name.

### Recovery restored: one retry per base-move leg (2026-09-22; F106)

Reusing `DriveAndDock`/`StowAndReturn` for Mission A silently dropped recovery the *old* flat Mission A plan had:
its own `DriveToUnit`/`DockAtPanel`/`ReturnToDock` were each wrapped in a `Try` (one retry), a predefined
recovery Mission B's library never had ("nominal path only", above) because nobody had hit a live failure on that
class of leg yet. A live Mission A run did: `navigate_to_pose` (the return-to-dock leg) hit a generic Nav2
`STATUS_ABORTED`, and with no retry left the plan finished `success: false`, 15 m / 178 deg off the dock. Restored,
at the library level (`plans/lib/DriveAndDock.ple`'s `Nav`/`Dock`, `plans/lib/StowAndReturn.ple`'s `Return` --
not `Stow`, no evidence yet it needs one): each leg is now `Try { PreCondition ok; Attempt1; Attempt2; }`, the
identical shape the old plan used, gating on the same `InOut ok` these libraries already thread through every call
site. Benefits Mission B too, since the library is shared. Verified offline before any live time: the existing
nominal-path regression still passes unchanged (`plexiltest`, both missions -- the second attempt is never reached
when the first succeeds); a fail-injection script (`command-failed` on the first `navigate_to_pose`, success on
the second) confirms `Return2` actually executes and the plan still finishes `ok: true`. Full account: F106,
`docs/research_findings.md`.

Re-run live on a fresh graph: genuine `success: true`, PDU-2's fault cleared, dock error 0.18 m / -9.9 deg, 193 s
sim time, video recorded (`artifacts/runs/plexil_mission_a_success_20260922`) -- `navigate_to_pose` succeeded on
the first attempt this time (the STATUS_ABORTED was a flake, not a reliable repro; the retry exists for when it
recurs, not because this particular run needed it). Panel (`plexil_mission_video.py`) needed one more generic
fix: its top-level node list (`TOP`) was hardcoded to Mission B's five names (`ToDepot, Pick, ToShelf, Place,
Return`), so it drew none of Mission A's own three (`ToUnit, Press, Return`) as active. Parameterized as `--top`
(both this script and `plexil_timeline_from_logs.py`, which had the identical hardcoding for the same reason) --
defaults to Mission B's list, so nothing else changes.

### Competent covered procedure (2026-09-23; F108, heldout_design §7)

Authored from the covered brief only ("identify the failed unit ... verify the result"): `MissionA_Covered.ple`
identifies the tripped unit from the units' telemetry (adapter Lookup `PowerUnit(unit, field)`, a typed field read of
`power_status`), docks, presses, verifies the breaker closed, presses once more if not, verifies again at the dock and
escalates with `RequestOperator` when a check fails. Decisions on live state use `if/endif` (evaluated when the node
runs), never a SkipCondition (watched while the node waits). Offline: `scripts/MissionA_Covered_nominal.pst`,
`scripts/MissionA_Covered_retrip.pst`. Mission B passes the catalogue item name `orbital replacement unit (ORU)`.

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `Identify` over pdu_1..3 | which unit is tripped | brief ("identify the failed unit"); site_map units; `power_status` | (a) |
| `Check1/2`, `FinalCheck` | breaker reads `closed` after a reset, and still at the dock | brief ("verify the result") | (a) |
| `ResetFailed`, `FinalCheck` escalation | no further procedure applies | generic recovery: retry once, then escalate | (b) |

## Built to the lock (2026-09-24; docs/baselines/authoring_spec.md "Changes to the current artifacts")

Supersedes every earlier traceability table in this file.

- **Tier 1, one budget.** Every capability call of the library (`DriveAndDock` nav/dock, `PickItem` arm_ready/pick,
  `PlaceItem` place, `StowAndReturn` stow/return) and Mission A's `Reset` (press + check) is a `Try` of 3 identical
  attempts. Nothing reads a failure kind or stage.
- **Adapter** (`ros/plexil_capability_adapter`): Lookups `LastFailureKind`, `LastFailureStage`, `jaw` deleted. Two
  Lookups added that carry data, not logic: `MissionGoal(field)` (the launcher's goal, env `MISSION_GOAL`, the same
  variable EUROPA's host reads) and `ItemDescription(item, field)` (the baselines' shared item table
  `baselines/item_descriptions.json`, file named in `interface-config.xml`). PLEXIL has no plan arguments, so a Lookup
  is the only native way for a launcher's goal to reach a plan.
- **Hold after escalation.** Both mission roots are `UncheckedSequence`s: a checked `Sequence` fails as soon as one
  child fails and skips everything after it, so the old Mission A's `ResetFailed` escalation could never run (a Try
  whose attempts all fail is a failed child). Every leg is gated on `ok`; after the one `RequestOperator` nothing more
  is commanded -- the rover holds where it is.
- **Mission A** keeps its procedure (identify by telemetry over the five units, press, verify, re-press, verify at the
  dock); the reset now has 3 attempts, and a leg out of attempts (drive, return) escalates too.
- **Mission B** is parameterized by (item X, source S, destination D) from `MissionGoal`; the item's `target`/`part`
  and release constraint come from the shared item table; top-level nodes renamed `ToSource`/`ToDestination`
  (`experiments/video/plexil_*` updated). The old ORU text (copied from Ours' runs, and describing a T-bail the
  catalogue no longer has -- the handle is a captive collar) is replaced by the catalogue's.
- **Offline** (`python3 baselines/plexil/scripts/offline_check.py`, plexiltest; replaces the three hand-written
  scripts): 51 cases pass -- Mission A covered at every unit (covered_misreport is the same run: the plan never reads
  the report), a reset that does not hold (3 presses -> escalate -> hold), a re-trip at the dock, no tripped unit;
  Mission B covered for all 3 items x 5 destinations; at each of the 14 call sites, fail x2 -> the 3rd attempt runs
  and the mission completes, fail x3 -> `RequestOperator` and nothing after it. Also run through the real adapter
  against `baselines/europa/sim_boundary.py` (universalExec): Mission B battery module -> BESS stand and Mission A
  ISRU complete; `--no-hold` on PDU-3 escalates at the dock; pick failing 3x escalates and holds.

### Traceability: library (`plans/lib/`, both missions)

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| every call's `Try` (Nav, Dock, Ready, Pick, Place, Stow, Return) | at most 3 identical attempts, on the result's `success` only | authoring_spec tier 1 (budget = Ours' `reasoner.retry_cap_per_call: 3`) | (c) |
| `DriveAndDock`: `standoff_m`, `approach_m` | 1.2, 1.2 (1.5 until F115); dock at standoff 0 | `contracts.yaml` navigate_to_feature / dock_at_feature defaults | (b) |
| `PickItem`/`StowAndReturn`: `tolerance_rad` | 0.08 | `contracts.yaml` arm_ready / stow default | (b) |
| `PickItem`: `arm_ready` before `pick` | ordering | not required by `pick`'s contract ("the arm needs no preparation"); the procedure's own covered order, run live (F104). Weak trace: kept as pre-existing and harmless (main-session decision 2026-09-24) | (b) |
| `PickItem`: `support` | the place frame the item stands on | `contracts.yaml` pick `support` | (b) |
| `PickItem`/`PlaceItem`: `item` | equipment-catalogue name | `contracts.yaml` pick/place `item` | (b) |

### Traceability: `MissionA_Covered.ple`

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `Identify` over pdu_1, pdu_2, pdu_3, bess, isru | the serviced units; the unit id is the parameter of every later leg | `interaction.json` `units` (site survey); `power_status` contract | (a) |
| `Identify`: breaker `tripped` | which unit failed; the report is not read | brief ("identify the failed unit"); `power_status` "breaker state (closed / tripped)" | (a)/(b) |
| `ToUnit`, `Press`: feature | `<unit>_panel/press` | `interaction.json` `units[u].panel` and its `press` point (`unit: u`) | (a) |
| `Button` | PDUs: round red push button in the yellow sub-panel; BESS: round white button, graphite panel, teal border; ISRU: round black button, white panel, orange border | panel looks: `assets/lunar_base/previews/{pdu_service_panel,bms_panel,plant_panel}_*.png`; `press` contract asks for colour and shape | (a)/(b) |
| No `arm_ready` before `press` | not required | `contracts.yaml` press ("neither required nor useful") | (b) |
| `Check1-3` | breaker reads `closed` after a press; 3 press+check attempts | brief ("verify the result"); authoring_spec tier 2 under tier 1's budget | (a) |
| `FinalCheck` | still `closed` at the dock | brief ("verify the result"); authoring_spec tier 2 | (a) |
| `NoTrippedUnit`, `NotReached`, `ResetFailed`, `NotReturned`, `FinalCheck` | `RequestOperator`, then nothing is commanded (hold) | authoring_spec tier 1-2 ("then hold in place and ask mission control") | (c) |
| `Return`: dock pose | (0, 0, 0) | `site_map` `dock` | (a) |

### Traceability: `MissionB_Covered.ple` and the shared item table

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `Goal`: item, source, destination | X, S, D of the brief | launcher's `MISSION_GOAL` (`d0_common.mission_b_goal`: the brief's cargo by its catalogue name and manifest place, the destination's place frame) | (a) |
| `ToSource`, `ToDestination`: feature; `Pick`/`Place`: support | S, D (site place frames) | `site_map` points of type place | (a) |
| `Pick`: `target` (ORU) | box wrapped in crinkled gold MLI foil, black lifting post on top | `previews/oru_0417_*.png`; catalogue `carry_handle` | (a) |
| `Pick`: `target` (battery module) | black drum-shaped module on a black base, amber windows on its round face, black lifting post | `previews/bat_0102_*.png`; catalogue `carry_handle` | (a) |
| `Pick`: `target` (consumables container) | long silver-white rugged case, grey front panel, black lifting post | `previews/consumables_container_*.png`; catalogue `carry_handle` | (a) |
| `Pick`: `part` (all three) | the slot on the neck between the transverse head and the collar, fingers on opposite sides | catalogue `grasp_interface.contact_region` / `engagement` (`contracts.py` `item_catalogue`, handle with collar in each asset's `.json`) | (a) |
| `Place`: `release_constraint` | `below_overhang` | catalogue `grasp_interface.release_constraint`; `contracts.yaml` place | (a)/(b) |
| `Escalate` | `RequestOperator`, then hold | authoring_spec tier 1 | (c) |
| `Return`: dock pose | (0, 0, 0) | `site_map` `dock` | (a) |

No row cites a held-out run or scenario name.
