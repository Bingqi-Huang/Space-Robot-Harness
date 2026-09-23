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

## Domain: skeleton only (2026-09-19; superseded by "Built to the lock")

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

## Domain: Mission B (2026-09-22; F105)

`domain/mission-b-model.nddl` adds `Posture`/`Jaws` timelines on `LunarBot` and an `Item`/`ItemLoc` class, plus
`arm_ready`/`stow`/`pick`/`place` actions, to the base timeline `skeleton-model.nddl` already had (kept as its own
file so the base-only regression, `run_offline.sh`, stays testable on its own). Given only the mission's own
outcomes as goals (`spare_oru` delivered, arm stowed, base at dock -- `--goal spare_oru@pdu_1_shelf/shelf --goal
stowed --final dock`), the solver derives the full 9-step plan itself: pick/place's own domain preconditions force
it to insert `navigate_to_feature`/`dock_at_feature`/`arm_ready`, the same way nasa/europa's own Rover example
derives `Go->Unstow->Place->TakeSample->PhoneHome` from the single goal `TakeSample(rock4)`. Getting a correct
derivation found one real domain-modelling bug (`met_by` used where `contained_by` was needed for a
cross-timeline precondition) and two bugs in EUROPA/`host.py` itself (a solver segfault on chained goals; a
condition slave's empty token-owner corrupting the next solve's NDDL) -- full account: F105,
`docs/research_findings.md`.

An item's natural-language description (`pick`'s `target`/`part`) and catalogue release constraint (`place`'s
`release_constraint`) are not NDDL parameters: the solver has no reason to search over them (there is exactly one
way to describe an item), so they are filled in by `host.py`'s `capability_call` from a small
`ITEM_DESCRIPTIONS` table, the same status as PLEXIL's plan-level `OruTarget`/`OruPart` constants
(`docs/baselines/plexil.md`). `NEAR_M`/`ATTEMPTS`/the jaw-holding band moved from hard-coded constants into
`config/host_config.json` (execution_plan §0 rule 11).

### Traceability (nominal path; superseded by "Built to the lock" below)

| Domain element | Fact encoded | Source | Rule |
|---|---|---|---|
| `Item`, `ItemLoc` (`On`/`Held`) | one movable item, on a surveyed support or in the jaws | Mission B's own object (`--item spare_oru:depot_stand/slot_0`); matches Ours'/PLEXIL's covered-instance item | (a) |
| `pick`/`place` contained_by `posture.Ready`/`base.At(support.work)` | the arm must be readied and docked first | Ours'/PLEXIL's covered-instance call order (research repo F92-F100, F104); not required by `pick`'s own contract, which plans its own way from wherever the arm is | (a) |
| `stow` contained_by `jaws.Empty` | folding a held item through the rover is refused | `openral_ext/capability_server/node.py`'s own hardware-limit refusal for `stow`/`arm_ready` | (b) |
| `arm_ready`/`stow`/`pick`/`place` duration bounds | 120 / 120 / 900 / 600 s | `contracts.yaml` `default_deadline_s` | (b) |
| `pick`'s `target`/`part`, `place`'s `release_constraint` | ORU / bail-neck description, `below_overhang` | Ours' own covered-instance calls (`R/artifacts/runs/g8d,e,s,t/ours/events.jsonl`); matches PLEXIL's `OruTarget`/`OruPart`/`release_constraint` | (a) |

No row cites a held-out run or scenario name. Recovery beyond replan-on-failure (the same `facts_from_result` ->
replan loop the skeleton uses, extended to read `evidence.arm` for `arm_ready`/`stow`/`pick`/`place`'s own
posture/jaws state on failure -- every capability's evidence carries it, no extra query needed) is deferred the
same way PLEXIL's predefined recovery set is: pick/place's failure kinds are settled (F92-F100) but a *frozen*
recovery policy is not yet written for either baseline.

## Live run (2026-09-22): first attempt, full success

`experiments/launch/lunar_base_d0/d0_europa_mission_b_check.py` (modelled on the PLEXIL live check script) starts
`host.py` against the real boundary in place of `sim_boundary.py`. Ran the identical 9-step derivation live on the
corrected-arm graph with no live-specific issues -- every offline fix held. Evaluator `delivered: true,
success: true`, 368 s sim time, video recorded (`artifacts/runs/europa_mission_b_success_20260922`); a dedicated
overlay panel (`experiments/video/europa_mission_video.py`) shows the mission's fixed goals alongside the solver's
current derived plan, replaced whole on every replan. Full account: F105, `docs/research_findings.md`.

## Domain: Mission A (2026-09-22)

`domain/mission-a-model.nddl`: "PDU-2 reported a fault: restore it, verify, return the rover to the dock with the
arm stowed." Reuses the same `Base`/`Posture`/`Jaws` timelines and `navigate_to_feature`/`dock_at_feature`/
`navigate_to_pose`/`stow` rules `mission-b-model.nddl` already has and already validated live (F105) -- duplicated
here, not shared, a deliberate short-term trade-off (`todo.md`: consolidate into one frozen capability model before
the artifact freeze, not before). New: a `Panel` timeline (`Faulted`/`Restored`) and a `Unit` class pairing a panel
with the `Feature` that presses its reset; `press`'s own rule constrains `feature` to actually be `unit.button`
(the same reason `pick`/`place` keep `support` alongside `item` -- not left for the solver to pick freely), needs
the base docked at the button, and transitions `Posture` `Stowed -> Ready` (matching `contracts.yaml`: press's tool
withdraws afterward but does not return to travel posture, which is what leaves `stow` something real to do) and
the unit's own `Panel` `Faulted -> Restored`. Given only the mission's own outcomes as goals (`--goal
pdu_2@restored --goal stowed --final dock`), the solver derives `navigate_to_feature -> dock_at_feature -> press`
itself from `press`'s own precondition, the same way Mission B's domain derives its plan from `pick`/`place`.
Offline-verified end to end (`run_offline_mission_a.sh`) before any live time.

## Live run: Mission A (2026-09-22)

`experiments/launch/lunar_base_d0/d0_europa_mission_a_check.py` (mirrors the Mission B live check script) ran the
3-step derivation (`navigate_to_feature, dock_at_feature, press`) live, then `stow, navigate_to_pose` toward the
second goal. The return-to-dock `navigate_to_pose` hit a generic Nav2 `STATUS_ABORTED` (no error code/message --
"typically an unreachable goal, an unpopulated/too-small costmap, or the controller failing to make progress"),
not a domain or host.py bug -- confirmed by PLEXIL's independently-implemented Mission A run hitting the identical
failure, on the identical leg, in the same time window (F106). `host.py`'s existing replan-on-failure loop (no
code change needed) reissued the same goal; it solved and completed on the second attempt. Evaluator `RESULT`:
`success: true`, PDU-2's fault cleared, dock error 0.23 m / -10.3 deg, video recorded
(`artifacts/runs/europa_mission_a_success_20260922`). Panel extended with `pdu_2_panel/press` in the mini-map's
`PLACES` label table (`europa_mission_video.py`) -- purely cosmetic, applies to any future mission touching PDU-2's
panel. Full account: F106, `docs/research_findings.md`.

## Open

- The plan is ordered by earliest start; concurrency between activities is not exploited (one capability at a time).
- (2026-09-24) The two mission domains are consolidated; see "Built to the lock".

## Competent covered procedure (2026-09-23; F108, heldout_design §7)

`host.py --power-field` (Mission A): the serviced units are the site's three PDUs; which are faulted comes from their
own telemetry, each tripped one gets a restore goal held to the horizon, and every panel fact is re-read from
telemetry after each activity and before each goal check -- a press that "succeeded" on a unit still reading tripped
is off-plan and replanned; a restore that relapses counts as a failure, and 3 of them hand the run to the operator
(`sim_boundary.py --tripped UNIT [--no-hold]` for offline checks). The capability call gets the catalogue item name;
the domain keeps its object ids. Offline: nominal (pdu_3), no-hold (pdu_2 -> operator after 3), Mission B regression.

## Built to the lock (2026-09-24; docs/baselines/authoring_spec.md "Changes to the current artifacts")

Supersedes the earlier domain sections and traceability tables in this file (`skeleton-model.nddl`,
`mission-a-model.nddl`, `mission-b-model.nddl` and `--power-field` are gone).

- **One domain**, `domain/lunar-base-model.nddl`: Base, Posture, Jaws (`Holding{item}`), every `Item`'s `ItemLoc`, every
  `Unit`'s `Panel`; activities navigate_to_feature, dock_at_feature, navigate_to_pose, arm_ready, stow, pick, place,
  press -- the union of the two mission domains, rules unchanged. Both missions have pick/place and press.
- **Instance = the site as the boundary reports it** (`host.py`): every `site_map` feature; every item of the
  inventory record (`manifest`) as an `Item` named by serial, on its recorded support; every unit reporting in
  `power_status` as a `Unit` with its `<unit>_panel/press` button, its panel fact read from its breaker. `--item`,
  `--unit`, `--power-field` deleted.
- **Goals**: `--goal restored` = every unit's panel `Restored`, held to the horizon (Mission A: the solver presses
  whichever unit's telemetry reads tripped); `--goal delivered` = the launcher's `MISSION_GOAL` (item X, source S,
  destination D; the same variable the PLEXIL plan reads): the inventory entry of X recorded at S `On` D (Mission B);
  then `stowed`, final `dock`. Every panel fact is re-read from telemetry after each activity; the relapse monitor
  (a reached restore lost again counts as a failure) and `facts_from_result` are unchanged; the same call failing, or
  a restore relapsing, `attempts` = 3 times asks mission control, and any answer but "continue" ends the run with the
  rover where it is.
- **Stated limitations (kept)**: one goal per solve and a fresh plan database per replan (the solver segfaults on
  `precedes`-chained goals, F105); a dropped item is unrepresentable; conditions can be met by a new token with no
  activity behind it (e.g. a re-press planned from `Ready` without a stow: harmless, `press` works from any posture).
- `item_descriptions.json` (shared with PLEXIL) replaces `host.py`'s own ORU entry; `sim_boundary.py` now serves all
  five units, the manifest, positional (PLEXIL) arguments checked against the contracts, and answers operator requests
  with the protocol's HOLD reply.

**Offline (run_offline_mission_{a,b}.sh, run_offline.sh):** Mission A covered at every unit (pdu_1..3, bess, isru):
`navigate_to_feature -> dock_at_feature -> press(<unit>) -> stow -> navigate_to_pose`, done (covered_misreport is the
same run: the report is not an input). Reset does not hold (bess, `--no-hold`): 3 presses, then mission control, hold.
press failing 2x: the 3rd press completes the mission; 3x: mission control, hold. navigate_to_feature failing 3x (far):
mission control, hold. Return failing 2x: completes. Base-only regression (`run_offline.sh --fail
dock_at_feature:1:far`): replans, completes.

**Blocker -- Mission B does not solve.** With the locked instance (12 inventoried items, 5 units) the `europa_plan`
process segfaults (exit 139, inside EUROPA's search on backtracking -- the same retraction path as F105's chained-goal
crash) on most Mission B problems. Removing either the extra items or the units made a sample problem solve; even the
old one-item, no-unit instance crashes on 3 of 15 combinations (e.g. spare ORU -> PDU-2 shelf), so the pre-existing
domain was only ever verified on ORU -> PDU-1. A `TotallyContained` horizon filter "solves" by filtering the flaws away
(a one-activity `place` plan) -- not a fix, not used.

Infrastructure workaround (main-session decision 2026-09-24, lock change control: a solver defect, not baseline
knowledge): `host.py` `solve()` re-runs the identical solve in a fresh process when `europa_plan` dies on a signal, at
most `solves_per_plan` = 5 per planning call, then counts it as no plan (the existing escalation). **It does not help**:
all 15 item x destination combinations x 3 runs offline (45 runs, 87 planning calls): 63 calls solved on the 1st solve,
24 crashed all 5 times; per combination the outcome is the same in all 3 runs. Solved (21 runs, 7 combinations: battery
module -> PDU-1/2/3 and habitat, consumables container -> BESS and PDU-3, ORU -> PDU-3): every plan is the full correct
one (arm_ready, navigate/dock at the source, pick the item there, navigate/dock at the destination, place it there,
stow, return), 3 solves per run, done. Crashed 5/5 in every run (8 combinations: ORU -> PDU-1, PDU-2, BESS, habitat;
battery module -> BESS; consumables container -> PDU-1, PDU-2, habitat): no plan -> mission control -> hold. The
crash is deterministic for identical input, ASLR on: the same problem solves or crashes depending only on the byte
string of the solver's arguments (the config file given by its absolute path solves 3/3, the same file by a relative
path crashes 3/3) -- a memory-layout-dependent defect, so an identical re-solve cannot change the outcome. Mission A
(5 units, no-hold, press x3): unchanged, all 21 planning calls solved on the 1st solve.

### Traceability: `lunar-base-model.nddl` and `host.py`

| Domain element | Fact encoded | Source | Rule |
|---|---|---|---|
| `Feature` objects, `approach`/`work` stances, `dock` | surveyed points and the two base stances | `site_map`; navigate_to_feature / dock_at_feature contracts | (a)/(b) |
| `Item` objects on their supports | every inventory entry (serial) at its recorded location | `manifest.inventory` | (a) |
| `Unit` objects, `button` | units reporting in `power_status`; `<unit>_panel/press` | `power_status`; `interaction.json` `units[u].panel` | (a) |
| `Panel` facts `Faulted`/`Restored`, re-read after every activity | breaker tripped / closed | `power_status` contract | (a)/(b) |
| goal `restored` | every unit `Restored`, held to the horizon | brief (identify, restore, verify); authoring_spec "Mission goals" | (a) |
| goal `delivered` | the inventory entry of X at S `On` D | launcher `MISSION_GOAL`; `manifest.inventory` | (a) |
| navigate_to_feature from anywhere; dock_at_feature only from the approach stance | base moves | contracts.yaml (Nav2 to an approach point; dock "entered along the axis") | (b) |
| pick/place `contained_by` base at the support's work stance | dock first | contracts.yaml pick/place ("dock at the item's work pose first") | (b) |
| pick/place `contained_by` posture `Ready` | arm readied first | not required by pick's contract; the covered procedure's own verified order (F104, F105). Weak trace: kept as pre-existing and harmless | (b) |
| stow `contained_by` jaws `Empty` | no folding with a load | contracts.yaml stow ("the jaws must be empty"); node.py refusal | (b) |
| press: `feature = unit.button`, base at its work stance, `Stowed -> Ready`, `Faulted -> Restored` | the unit's own reset; press leaves the arm out | contracts.yaml press ("dock at the feature's work pose first", "withdraws") | (b) |
| durations | 400 / 240 / 400 / 120 / 120 / 900 / 600 / 420 s | contracts.yaml `default_deadline_s` | (b) |
| `capability_call`: pick `target`/`part`, place `release_constraint` | per catalogue item | `baselines/item_descriptions.json` (rows in docs/baselines/plexil.md) | (a) |
| `capability_call`: press `target` | per unit's panel look | as PLEXIL's `Button` (`previews/{pdu_service_panel,bms_panel,plant_panel}_*.png`) | (a)/(b) |
| `facts_from_result` | failed base move: `approach` if `base_pose` within 3 m, else `elsewhere`; arm/jaws/`Held` from `arm` evidence | the result's evidence (`base_pose`, `arm.posture`, `arm.jaw_rad`) | (c) |
| replan on a result off the plan; same call or relapse 3 times -> mission control, then hold | attempts = 3 | authoring_spec tier 1-2 | (c) |

No row cites a held-out run or scenario name.
