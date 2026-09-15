# `panel_remount_v2` mission-logic plan (Phase C, execution_plan.md §6.4)

**Status: implemented and live-verified, 2026-09-15.** Items 1-6 of the
checklist (§6) are done; item 7 (full reasoner/kernel graph run) stays
gated on F37 as planned; item 8 (covered-case route obstruction, Mission B)
is follow-on work, not started. See `docs/research_findings.md` F40 for a
real spawn-position bug found and fixed while implementing this (the
panel's documented spawn offset had silently doubled since v1 due to an
Isaac Lab `pose_range` semantics mismatch) and F39/F40 for the live
verification trail (all three `scenario_variant` values, numeric spawn
poses read from simulator state, clean 60 s/3000-frame recorded runs).

Original design decisions (2026-09-15):

1. The covered case's true/decoy discrimination must require a real
   inspection/observation step, not just "which pedestal has an object
   called panel" (a trivial geometric shortcut). → **adopted**.
2. Of the three held-out categories in research_content.md §5.5, implement
   **movable-object access block** + **semantically inconsistent state**
   (not capability-substitution). → **adopted**.

## 0. Prerequisite fix (unrelated to the design questions, do regardless)

`openral_ext/mission_verifier/panel_remount_logic.py` still has v1's
target constants (`PANEL_TARGET_POS = (1.5, 0.0, 0.5)`); v2 moved the
cluster to `(3.5, 0.0, 0.5)` (`task.py` `_PANEL_TARGET_POS`). Hasn't
caused a live failure yet only because v2 has never been driven through
the full kernel/reasoner graph. Fix the constants (and point the module
docstring's file reference at `panel_remount_v2/task.py`) before any
live verification run against v2.

## 1. Covered-case discrimination signal

Add a second `SolarPanel` RigidObject (`panel_decoy`), lying flat (same
pose family as the real panel: `roll=π/2`, small pos/yaw randomization),
near `pedestal_decoy_a` (`IndustrialPedestal25`, the 25 cm one).

Effect: a naive "find the panel-class object that isn't on its pedestal"
check now returns two candidates — geometry/object-class alone can't
disambiguate. The real discriminator is **mount compatibility**: the
`SolarPanel` asset's physical footprint fits `IndustrialPedestal50` (the
true pedestal); it does not fit the 25 cm decoy. This is a deterministic
geometric fact, exposed identically to all three methods through the
existing scene-query/object-localization path (or a `Lookup` for
PLEXIL/EUROPA) — not a hidden coordinate, and not VLM-only. Ours is
expected to use its VLM/inspect step here (exercises §3.4.2/§9.4 before
held-out B reuses the same muscle); PLEXIL/EUROPA are allowed to encode
"check both candidates, prefer the mount-compatible one" in their frozen
covered plan/domain — that is exactly what "model-covered" means.

`panel_decoy` is inert scenery: not part of reward/termination, not
touched by the mission verifier's success predicate. Per §8.2, the scene
may encode this fixed fact; what to do about it stays the reasoner's
(or the baseline plan author's) call.

Optional, lower priority, can follow later: §6.4's covered-example list
also names "a known route obstruction with an encoded alternate route."
If added, use a `MoonRock` on the default nav path with a mapped detour —
deliberately a *navigation-level* detour, kept distinct in mechanism from
held-out A's *manipulation-level* block below so the covered instance
doesn't leak the held-out pattern.

## 2. Held-out A — movable object blocks access (manipulation-level)

New asset: `MoonRock` (already in SRB's library, `srb/assets/object/
rock.py`), spawned directly in the true panel's grasp/reach envelope —
between the robot's expected stand-off pose and the panel's resting
spot — only when the held-out-A variant is selected.

Expected valid solution (not encoded anywhere): attempt to reach/grasp
the panel fails or is geometrically blocked → agent recognizes the rock
as a movable obstruction → grasps and relocates it using the *already
existing* generic `grasp`/`move_ee_to_pose`/`release` procedural rSkills
(closed-capability rule: no new capability needed) → re-approaches →
remounts the panel → verifies. The verifier adds one new effect
predicate, mirroring the panel's existing `DISPLACEMENT_THRESHOLD_M`
pattern: rock displaced from its spawn pose beyond a threshold. It checks
only the *effect* (rock moved, panel restored), never the order of
operations.

## 3. Held-out B — semantically inconsistent state (no new verifier code)

Variant where the true pedestal's panel is not simply "lying flat
nearby" (the nominal template every covered plan is authored against).
Instead it starts already resting near/on the pedestal but off the
correct pose — offset beyond `SUCCESS_POS_TOLERANCE_M` and/or rotated
away from `SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE` — i.e. it *looks*
roughly mounted from a distance but still fails the existing strict
tolerance check.

A frozen covered plan that includes a reasonable "skip remount if panel
already looks placed" shortcut will misjudge this as done. The valid
solution requires a closer/second observation (finer pose check or a
VLM "is this actually seated correctly?" query) before deciding, then
the same generic reposition capability already used for the covered
case. **No new verifier logic**: the existing pose/orientation check
already fails this state correctly — the entire challenge is behavioral
(does the agent/baseline re-check before declaring done), exactly what
§4.10 means by verifying effects, not strategy.

## 4. Perturbation-switch mechanism

One task id (`panel_remount_v2`), one new `TaskCfg` field, same override
pattern already used for `env_spacing`/`episode_length_s`:

```python
scenario_variant: Literal["covered", "heldout_access_block", "heldout_state_mismatch"] = "covered"
```

Read once in `__post_init__` to decide which optional objects/pose
families get instantiated (rock present/absent, panel start-pose
family). Invoked as `env.scenario_variant=...` on the CLI, no new
registered gym ids. Process discipline, not code: the switch and the
`"covered"` value are visible pre-freeze; baseline authors do not see or
tune against the `heldout_*` values before the freeze point.

## 5. Open question to resolve during implementation

Whether "query mount compatibility between a panel and a pedestal" is
already expressible through the existing scene-query/object-localization
capability output, or needs a small metadata addition. Check
`openral_perception_ros/scene_vlm_node` and the object-localization →
world-state path before deciding; if it needs new metadata, it must stay
mission-generic per §8.2 (e.g. an asset dimension/footprint field usable
for *any* object/pedestal pair, not a `panel_decoy`-specific rule).

## 6. Ordered implementation checklist

1. [x] Fix mission_verifier's stale v1 constants (§0).
2. [x] Scene: add `panel_decoy` near `pedestal_decoy_a` (§1).
3. [x] Scene: `scenario_variant` field + conditional rock / panel-pose family (§4).
4. [x] mission_verifier: add the rock-displacement effect predicate (§2) --
   reused the existing generic `panel_displaced` function as-is, no new
   predicate code needed; `node.py` now also looks up `srb/env0/rock`.
5. [~] §5's open question (mount-compatibility query capability) not
   resolved -- deferred to the perception/capability-registry work that
   Phase E's baseline adapters will need anyway; not required to
   live-verify the scene/harness mechanism itself.
6. [x] Live-verified all three `scenario_variant` values two ways: (a)
   numeric -- a temporary debug print of simulator ground truth in
   `_reset_idx`, confirming exact spawn poses match design intent, removed
   after use; (b) full-episode video (`srb agent rand -e
   panel_remount_v2_visual ... --headless --video`, ~170 s wall time each,
   F39's SIGINT-to-mux pattern) with clean logs (no NaN/depenetration/
   exception) and clean GPU teardown. Found+fixed F40 (stale pose_range
   semantics, see `docs/research_findings.md`) along the way and
   re-verified after the fix, including moving `_ROCK_BLOCKING_POS` to
   keep clearance from the panel's corrected jitter range.
7. [ ] Full end-to-end reasoner run is separately gated on F37 (Nav2
   lifecycle wedge / sensor-bridge launch wiring) if the held-out cases
   are to be exercised through the complete live path rather than the
   scene check alone. Not attempted this session -- out of scope for the
   scene/harness-mechanism verification above.
8. [ ] Covered-case route obstruction (§1's optional item) and Mission B
   stay after this, in that order, per handoff.md.
