# TODO

## Phase A–C — ✅ COMPLETE (2026-09-13 … 09-16)

Upstream verification, generic OpenRAL on SRB (LunarBot HAL + capabilities, F11–F38), lunar base scene +
Mission A/B tasks with covered/held-out cases and verifier truth (F39–F49). The oracle's job is done.

---

## Phase D0: the shared capability stack on Mission A/B — CORE PASSED (F50, F51)

`execution_plan` §21.4 + §13.2. Realistic localization: wheel-inertial `/odom` + AMCL on the lidar-surveyed
map (SLAM off), navigation and docking in `map`, errors against `/openral/pose_truth`.

- [x] Localization: base 0.02–0.09 m from work poses (truth), AMCL 0.01–0.15 m, odom drift 0.4 m / 34 m.
- [x] **Mission A `covered` end to end** (a5, av2): verifier success.
- [x] **Mission B `covered` end to end** (b7, bv1): ORU clamped (jaw 0.17 rad) the whole carry, on PDU-1's
      shelf upright, rover docked, verifier success.
- [x] Held-out `route_block`: Nav2 detours round the unmapped rover, AMCL 0.074 m.
- [x] Videos (success runs av2, bv2): `artifacts/videos/mission_{a,b}_covered.mp4`.
- [ ] Payload sag while carrying: handle drops 4.5 cm over the Nav2 carry at 0.2× (b7) but 15 cm in a rendering run
      at 0.06× (bv1, "servo over shelf" stalled; bv2 passed). Arm zero-twist hold under 1 kg — isolate render vs rate.
- [ ] **World-aware arm planning** (blocks `heldout_cover_obstruction` and makes every grasp fragile): MoveIt
      knows only the rover; plans nudged the ORU 5 cm (b5) and knocked the service cover 0.21 m (ac1); the servo
      alone cannot reach the cover from READY (ac4). Needs perceived collision objects / octomap in the planning
      scene, through the shared stack (same for all methods).
- [ ] Held-out primitives not yet run through D0 (closed-capability rule, F51 §6): observe a component's state
      from a view pose (status_mismatch lamps, destination_occupied shelf, spare_swapped identity) — Phase E
      perception; crate grasp/carry/place onto a stand slot (destination_occupied); cover grasp/carry/place.
- [ ] Wedged-with-spinning-wheels localization: AMCL follows odometry when the rover is physically stuck
      (b1: 4.5 m). Slip detection in the estimator (not by restricting manoeuvres).
- [ ] Nav2/MPPI cut the charging station's corner (b1); Mission B uses the east-leg road point. Tune costmap /
      critics near structures rather than routing around the defect.
- [ ] Silence the bridge's per-tick camera TF lookups when a scene has no cameras.

**BLOCKER BEFORE THE EXPERIMENT-I FREEZE:** arm targets come from simulator truth — `locate_feature` in the
capability boundary (and `to_rover` in `d0_common.py`) is a stand-in for Phase E relative perception. It is
evaluator-only state reaching a method (§13.2) and must be replaced before any campaign run.

---

## §21.4 common capability boundary — DONE (F51 §5)

- [x] `space_harness_msgs` (ExecuteCapability action, QueryCapability service), `openral_ext/capability_server`
      (contracts.yaml: 8 effects, 4 queries; one call → one ExecuteRskill; off-contract refused; verifier never
      crosses). Offline refusals verified.
- [x] Live proof (cm2): Mission A `covered` through the boundary only — verifier success, same as direct (a5).
- [ ] Mission B through the boundary.
- [ ] Ours' tool palette rendered from contracts.yaml (same names/args).

## After §21.4 (execution_plan §21, in order)

- [x] §21.5 start: PLEXIL 6.1.3 pinned and built (`docs/baselines/plexil.md`), SafeDrive example runs;
      `ros/plexil_capability_adapter` skeleton: ExecuteCapability command path verified through universalExec.
- [ ] §21.5: fix the QueryCapability lookup stall; typed Commands per capability; Mission A covered plan library;
      one covered Mission A instance end to end through PLEXIL on the live graph.
- [ ] §21.6 EUROPA → PLEXIL bridge; replanning inside the encoded domain on the same case.
- [ ] §21.7 scenario manifests, evaluator-only annotations, freeze manifest, closed-capability validator.
- [ ] §21.8 thin `space_runtime` for Mission A (facts/evidence, context, guard, playbook audit).
- [ ] Phase D space context only for variables the final scenarios exercise.
- [ ] Phase E: semantic query / relative perception (replaces the truth stand-in); terminal precision =
      manipulation rSkill with visual servoing (user decision).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream suites; pure-Python offline checks before one decisive live run.
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **Do not restrict LunarBot's manoeuvres to avoid slip**; fix estimation. **Carry payloads clamped** (check the jaw).
- **No third-party research code that needs adapting** unless the in-house route is shown insufficient.
- **Never navigate on truth.** Truth is for measuring and for the declared perception stand-in only.
- Kill only your own run's processes (run tag / explicit PIDs); never `pkill -f` a pattern.
- Never edit a script a live run is executing (runs execute frozen copies of `run_d0.sh`; checks load at start).
- Measure motion in sim time, never wall time — including check-script deadlines.
