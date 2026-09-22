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

### Adapter: two typed failure Lookups

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

### Traceability (nominal path; format: docs/baselines/authoring_spec.md)

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| `ToDepot`: `feature` | `depot_stand/slot_0` | site_knowledge, `R/artifacts/runs/g4a/ours/events.jsonl:3` (`points`) | (a) |
| `ToShelf`: `feature` | `pdu_1_shelf/shelf` | site_knowledge, same event; mission brief names PDU-1 | (a) |
| `Return`: `dock_x/y/yaw` | `(0.0, 0.0, 0.0)` | site_knowledge `dock`, same event; matches `MissionA_Covered`'s `ReturnToDock` | (a) |
| `DriveAndDock`: `standoff_m` / `approach_m` defaults | `1.5` | `contracts.yaml` `navigate_to_feature.standoff_m` / `dock_at_feature.approach_m` documented defaults | (b) |
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
now unblocked) and Mission A still waits on a live `press` (§21).
