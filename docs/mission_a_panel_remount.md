# Mission A's SRB task — `panel_remount`

Built 2026-09-13 directly inside `space_robotics_bench/srb/tasks/
mobile_manipulation/panel_remount/` (now a proper submodule of this research
repo — see `docs/upstream_pins.md`). This is the scene/task execution_plan.md
§21 item 5 needs before Mission A's plain-language instruction (item 5) and
generic-OpenRAL run (item 6) can happen.

## Why a new task, not an existing one

Investigated first (see `AGENT/todo.md`/`handoff.md` for the short version):
no existing SRB task fits. `_ground_manipulation` is a bare scaffold with no
objects, fault, or success condition. Every task with real objects/rewards
(`solar_panel_assembly`, `screwdriving`, `peg_in_hole_assembly`,
`sample_collection`, `excavation`) is built on `ManipulationEnv`
(`robot: Manipulator`) — fixed-base arms only, type-incompatible with
LunarBot's `WheeledManipulator`. The one mobile-manipulator task,
`mobile_debris_capture`, is built on `OrbitalManipulationEnv` — a
free-flying orbital arm, not a ground rover.

## The mission, per execution_plan.md §6.4

> Inspect a designated lunar infrastructure site, identify the failed
> subsystem, restore operation, verify the restoration, and leave the
> system in an operationally safe condition. (research_content.md §5.3,
> Mission family 1)

Concretely: a solar panel has come loose from its mount on an industrial
pedestal and is lying nearby. The robot must locate it, pick it up, and
place it back on the pedestal within tolerance — the same "component has
come dislodged, put it back" story §6.4 asks for, using assets already in
SRB's library (`solar_panel.usdz`, `industrial_pedestal_50cm.usdz`) rather
than anything invented for this.

**Deliberate v1 simplification, stated plainly**: a single pedestal+panel
pair, not the "multiple visually distinguishable candidate components"
§6.4 also asks for (which would need a genuine identify-the-faulty-one step
across several instances). Same "prove the simplest version first" pattern
this project used for BODY_TWIST before adding the arm — a natural, cheap
follow-up once this is proven, not attempted here.

## Design

- Base class: `GroundManipulationEnv`/`GroundManipulationEnvCfg` (the same
  base `_ground_manipulation` uses) — robot picked via `env.robot=lunar_bot`
  like every other SRB task, not hardcoded.
- `pedestal`: `IndustrialPedestal50` (static `AssetBaseCfg`, not a queryable
  physics asset — its position is a fixed, known constant, not something
  read back at runtime).
- `panel`: `SolarPanel` (`RigidObjectCfg`), spawned lying flat
  (`roll=π/2`) near the pedestal, position randomized per-reset within a
  small radius so the exact start pose isn't memorizable.
- Success condition — **the genuinely new part**: position (< 0.1 m) AND
  orientation (relative-quaternion `|w| > 0.9`, i.e. within ~51° — loose on
  purpose for a first version) of the panel relative to the pedestal's
  mount pose, checked every step as a real `torch.jit.script` boolean
  tensor, not a shaped reward. No existing SRB task has a genuine success
  termination (checked: `debris_capture`/`landing` have failure
  terminations only; everything else is `termination = torch.zeros(...)`,
  always). This project's own verification layer (plan §4.4) was always
  going to need to supply this regardless of which scene got picked.
- Rewards are intentionally lean (distance EE→panel, distance panel→target
  at two scales, a success bonus, the usual action-rate/contact penalties)
  — this project dispatches missions through the agentic harness, not RL
  training, so reward shaping is secondary; the scene, the fault, and the
  termination signal are what matter.
- Registered via the standard `register_srb_tasks` → `gymnasium.register`
  pattern (`__init__.py`), plus a `task_visual.py` variant (camera
  observations via `VisualExt`) mirroring every other task's convention —
  needed since Mission A's capability mix includes "observation/scene
  query" and "object localization" (§6.4), which need image observations.

## A real bug found and fixed during first live validation

First attempt placed the pedestal/panel 2.4–3.0 m from the env origin. Live
test (`agent zero --interface ros`, no HAL/kernel needed — this is a
pure-SRB scene check): the panel fell to `z = -40` after ~1s and `z = -2637`
a few seconds later, still falling, never hitting anything.

Root cause: SRB's procedural moon terrain (`env_cfg.py`'s
`flat_area_size = 0.8 * (_dyn_res ** 1.2)`) only guarantees a flat, reliable
landing surface within roughly a 4 m-wide area centred on the env origin —
this task's `env_spacing=32.0` computes `_dyn_res=4`, `flat_area_size≈4.2`.
Outside that pad the terrain is genuinely uneven (the same procedural
generation that makes the rest of the environment interesting). A rigid
object spawned outside the pad can end up embedded in a bump; PhysX's
depenetration solver then ejects it with a large velocity spike, and in the
Moon's weak gravity that translates to falling/flying indefinitely instead
of settling — exactly what was observed.

**Fixed** by moving both the pedestal (now at `(1.5, 0, 0)`) and the panel's
spawn region (`(1.1, 0.3, 0.3) ± 0.2` in x/y) well inside the ~4 m pad.
Re-verified live: the panel now settles to a stable resting pose
(`(1.781, 0.304, 0.104)`, unchanged across a further 8 s of simulation) —
physically sane, not falling. Documented in the task file's own header
comment so the next person placing an object in a ground-manipulation scene
doesn't rediscover this by watching something fall through the world.

## Verified live

- `srb agent zero --env panel_remount env.robot=lunar_bot --headless
  --perf --perf_duration 10` — registers, parses `TaskCfg`, runs the full
  duration, shuts down cleanly. (One `torch.jit.script` fix needed first:
  the success-tolerance constants had to be local variables inside
  `_compute_step_return`, not module-level globals — TorchScript cannot
  close over a plain Python `float` defined outside the scripted function,
  only over locals/arguments; every other constant in this codebase's
  reward functions is already local for this exact reason, which is how
  the fix was found — matching precedent, not guessing.)
- `srb agent zero --env panel_remount env.robot=lunar_bot --headless
  --interface ros` — panel settles physically (see above); robot spawns
  and publishes `joint_states` normally, unaffected by the new scene
  objects; reward topics (`reward_distance_ee_to_panel`,
  `reward_distance_panel_to_target[_gradual]`, `reward_success`) all
  publish sane, non-degenerate values; `terminated` correctly stays `false`
  with the panel far from its target.
- Not yet exercised: an actual attempt to grasp and remount the panel
  through OpenRAL's dispatch path (that's execution_plan.md §21 item 6,
  the next step — define Mission A's plain-language instruction, then run
  generic OpenRAL against this scene and observe real failure modes).

## What this does NOT cover

- Only one pedestal+panel pair (see "Deliberate v1 simplification" above).
- No bolt/nut/screwdriver mechanics — remounting is "place the panel back
  in roughly the right pose," not "thread and tighten a fastener." The
  asset library has `bolt_hex_m8`/`nut_hex_m8` (with a "tight" variant) and
  `screwdriver_hex_m3/m5` ready for a follow-up that adds a fastening step,
  once the arm has a precision control mode (JOINT_POSITION/CARTESIAN_DELTA)
  beyond today's CARTESIAN_TWIST velocity surface.
- Grasp detection has no dedicated reward term — LunarBot has no separate
  end-effector contact sensor (`GroundManipulationEnv` clears
  `contacts_end_effector` to `None` for any `WheeledManipulator`, unlike a
  fixed-base arm), so `solar_panel_assembly`'s contact-force-based grasp
  reward doesn't carry over cleanly; not attempted for v1.
