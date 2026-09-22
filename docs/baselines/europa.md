# EUROPA→PLEXIL baseline (execution_plan §1.6, §11.2)

A research integration of two NASA open-source components (EUROPA planner, PLEXIL executive); not an official NASA
"EUROPA+PLEXIL" product.

## Pin and build (2026-09-19)

- Source: `nasa/europa` `master`, commit `ac5c332d01bc429e4fb543475891b1905f61475c` (2019-06-25, "Adding NDDL files to
  the installation"), cloned to `~/Programs/europa`. No release binaries: the GitHub releases page lists none, and the
  wiki's 2.x downloads point at Google Code (gone).
- Toolchain: native Ubuntu 22.04, g++ 11.4, CMake 3.22.1, OpenJDK 11.0.32, Boost 1.74 (system). No Docker needed:
  the legacy C++ builds on gcc 11 with warnings only. The build-time dependencies apt would install -- SWIG 4.0.2,
  libantlr3c 3.4, CppUnit 1.15 -- are `apt-get download`ed and unpacked with `dpkg -x` into `~/Programs/europa-deps`
  (no root). Jam and Ant are not used (the CMake build replaced them).
- Everything is in `baselines/europa/build_europa.sh`:
  `cmake .. -DOPTIMIZE=ON -DCMAKE_PREFIX_PATH=$DEPS -DSWIG_EXECUTABLE=$DEPS/bin/swig4.0 && make && make install`
  (with `SWIG_LIB=$DEPS/share/swig4.0`) → `~/Programs/europa/dist/europa` (`EUROPA_HOME`): `lib*_o.so`, headers,
  `PSEngine.jar`, `Europa2.cmake`.
- Upstream examples (interpreted NDDL, `<Ex>-planner_o_rt <Ex>-initial-state.nddl PlannerConfig.xml`, run from the
  example directory):
  - Light: `Solver finished after 4 steps` -- `LightSwitch.turnOff` inserted to reach the `Off` goal.
  - Rover: `Solver finished after 38 steps` -- `Rover.Go(rock4)` via path `p1`, `Instrument.Unstow`, `Place`,
    `TakeSample`, `PhoneHome`, with battery consumption, from the single goal `TakeSample(rock4)`.
- Not run: the CppUnit regression suites (`ctest`), the Java PSDesktop UI.

## Architecture

```
host.py  (EUROPA host)                    plexil/plans/ActivityDispatch.plx  (PLEXIL universalExec 6.1.3)
  site map, state facts, goals              loop: NextActivity() ──┐
  → problem_<n>.nddl                              ExecuteCapability(name, args_json)  → ros/plexil_capability_adapter
  → planner/europa_plan (fresh Plan DB,           ReportResult(LastCapabilityResult)      → /space/capability/execute
     solver, activity tokens as JSON)      ◄── HostLink adapter (TCP, length-prefixed frames) ──┘
  → dispatch next activity, read result → facts_from_result → continue or replan
```

- `planner/europa_plan.cc` (EUROPA API used): `PSEngine::makeInstance/start`, `executeScript("nddl", file, true)`,
  `createSolver(PlannerConfig.xml)`, `PSSolver::configure/step/getFlaws/isExhausted/isConstraintConsistent`,
  `getTokens()`, `PSToken::{isFact, getTokenState, getFullTokenType, getPredicateParameters, getStart, getEnd,
  getSlaves, getActive, getOwner}`, `PSVariable::{isSingleton, getSingletonValue, getLowerBound, getUpperBound}`.
  Output: the active non-fact tokens of the activity class, earliest start first, each with its slaves (the
  conditions/effects its rule put on timelines). The solver is upstream's default configuration
  (`config/PlannerConfig.xml` = the Rover example's: horizon filter, threat/open-condition/unbound-variable managers).
- `host.py`: steps 1–7 of §11.2. Each (re)plan instantiates a fresh Plan Database from the current facts (at t=0) and
  the open goals; the plan is kept while activities end as planned, and replanned from the updated facts when one
  does not. It is not in-place repair of the previous database (a time-advancing database with observations as
  timestamped facts, T-REX style, would be; not built). A plan's post-state per timeline is read off the
  activity's latest-starting slave; an intermediate goal leaves the goal set once reached, the final goal must hold at
  the horizon. The same call failing `ATTEMPTS`=3 times, or no plan, ends the run (operator assistance required).
- `facts_from_result` in `host.py` is the baseline's result→fact translation (success, failure_kind,
  failure_reason, evidence → plan-database facts). Skeleton rules: success → the plan's post-state; a failed base
  move → `At(feature approach)` if `evidence.base_pose` is within 3 m of the feature (dock can close in), else
  `At(elsewhere)`; an empty result (call never accepted) changes nothing.
- `plexil/HostLinkAdapter.cc` (own adapter, not the stock UDP one: stock UDP messages are fixed-size and the pick
  evidence reaches 55.7 KB, against a 64 KB datagram): `String Command NextActivity()`, `String Lookup
  ActivityArgs()`, `Boolean Command ReportResult(String)`. `plans/ActivityDispatch.ple` holds no mission logic.
  The capability call itself goes through the PLEXIL baseline's `ros/plexil_capability_adapter`, unchanged.
- The host reads the mission instance (`site_map`) and initial `base_pose` from `/space/capability/query` directly
  (rclpy); PLEXIL's `QueryCapability` Lookup stalls (docs/baselines/plexil.md).

## Domain: skeleton only (2026-09-19)

`domain/skeleton-model.nddl`: `Base` timeline (`At{loc}`, `Moving{to}`), activities `navigate_to_feature`,
`dock_at_feature`, `navigate_to_pose` with durations bounded by the contracts' `default_deadline_s`. The Mission B
domain (arm, jaws, item locations, pick/place/stow/arm_ready/release) is deferred until the manipulation contracts
settle. Traceability (authoring rule: mission instance / generic contract / observed failure kinds):

| Domain element | Source |
|---|---|
| Features, their `approach`/`work` stances, the dock | `site_map` query (mission instance); contracts of navigate_to_feature / dock_at_feature |
| navigate_to_feature / navigate_to_pose from any location | contracts.yaml (Nav2 to a pose / approach point) |
| dock_at_feature only from the feature's approach point | contracts.yaml dock_at_feature ("close onto the pose", entered along the axis after navigate) |
| duration ≤ 400 / 240 / 400 s | contracts.yaml `default_deadline_s` |
| failed base move → approach (≤ 3 m) or elsewhere | dock_at_feature failure_kind 3 "no progress" (run ma2); navigate_to_feature failures kinds 0/1 (g8b, g4m) |

## Offline verification (2026-09-19)

`baselines/europa/run_offline.sh <run_dir> [--fail CAP:N[:far]]` runs the whole chain on ROS domain 92 (localhost),
with `sim_boundary.py` standing in for the capability server (same action/service, symbolic base, scripted failures).
Goals: reach `depot_stand/slot_0@work`, end at `dock`.

- nominal: plan 1 = navigate_to_feature(slot_0) → dock_at_feature(slot_0) → navigate_to_pose(0,0,0); all three
  dispatched through PLEXIL; `done`; exec "Plan complete, Exec exited without errors".
- `--fail dock_at_feature:1:far` (base left 5 m off): fact `At(elsewhere)`; plan 2 inserts navigate_to_feature
  before the dock again; completes.
- `--fail dock_at_feature:1..3` (base stays at approach): plans 2 and 3 = dock_at_feature → navigate_to_pose; after
  the third failure `no_plan (attempts exhausted)`; the host ends PLEXIL's loop cleanly.

## Open

- Mission B domain and its result translation; the live launch/check script (modelled on
  `experiments/launch/lunar_base_d0/d0_plexil_mission_a_check.py`).
- The plan is ordered by earliest start; concurrency between activities is not exploited (one capability at a time).
