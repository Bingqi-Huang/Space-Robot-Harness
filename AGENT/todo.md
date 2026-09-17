# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.

## Done (Phase A–D0, F1–F52)

- LunarBot capability stack on SRB (HAL, kernel, Nav2 + AMCL on the lidar-surveyed map, MoveIt with a
  world-aware planning scene, gripper, sensors).
- Lunar base scene; Mission A and Mission B `covered` end to end, verifier success; `route_block` and
  `cover_obstruction` capabilities pass.
- Common capability boundary (`openral_ext/capability_server`, `contracts.yaml`); Mission A through it (cm2).
- PLEXIL 6.1.3 built, adapter; `MissionA_Covered.ple` live, verifier success (p1).

---

## 1. Ground the tasks in future lunar mission literature (§6.3) — IN PROGRESS

- [ ] `docs/lunar_task_catalog.md`: literature survey of candidate tasks/situations with sources (running).
- [ ] Review the 7 existing situations (A covered, cover_obstruction, status_mismatch; B covered,
      destination_occupied, spare_swapped; route_block) against the catalog; choose the Experiment-I set.
- [ ] Change the scenes only where a chosen situation is missing or unsupported.

## 2. Ours: thin `space_runtime` + LLM/VLM path, Mission A (§21.8, Phase E)

- [ ] Tool palette rendered from `contracts.yaml` (same names/args as PLEXIL).
- [ ] Authoritative facts/evidence: event schema, reducer, store; `MissionState` = working state only.
- [ ] Context builder; thin invariant/authority guard at effectful dispatch.
- [ ] Generic playbook + audit (no Mission A/B solution hints).
- [ ] FDIR/capability availability; endpoint reconciliation; trace linkage; report from structured record.
- [ ] Space-context variables only if the chosen scenarios exercise them.
- [ ] Exit: model restart/switch keeps facts; decomposition/recovery change online without rule edits;
      guard has no mission-specific logic; Ours succeeds on Mission A `covered`.

## 3. Shared perception (all methods)

- [ ] VLM semantic observation as a registered capability.
- [ ] Relative perception replaces the truth stand-ins: `locate_feature`, arm feature targets
      (`plan_ee_to_feature`/`move_ee_to_feature`), movable objects in the planning scene, `to_rover` in `d0_common.py`.

## 4. Ours on covered, then held-out situations

- [ ] Mission A/B covered; then the held-out situations. Failures → mission-generic changes only (§13.1).

## 5–6. Baselines

- [ ] PLEXIL: Mission B covered plan; plan library (library nodes); predefined recovery set (§11.1).
- [ ] EUROPA: pin/build, NDDL domain, host, EUROPA→PLEXIL bridge, replanning inside the domain.

## 7–9. Framework, covered runs, freeze, Experiment I

- [ ] Scenario manifests, evaluator-only annotations, freeze by git commits/tags, closed-capability validator,
      ALFUS operator events, metrics aggregation.
- [ ] All three methods on covered development cases until infrastructure defects are gone.
- [ ] Freeze → Experiment I. Then Experiment II (§13.3–13.4).

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL (fix estimation, don't restrict manoeuvres).
- Nav2/MPPI cuts the charging station's corner (Mission B uses the east-leg road point).
- Bridge's per-tick camera TF lookups when a scene has no cameras.

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream suites; pure-Python offline checks before one decisive live run.
- No defensive coding, no corner-case guards (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Tasks must match documented future lunar mission needs (§6.3); choose from the catalog.
- **Do not restrict LunarBot's manoeuvres to avoid slip**; fix estimation. **Carry payloads clamped** (check the jaw).
- **No third-party research code that needs adapting** unless the in-house route is shown insufficient.
- **Never navigate on truth.** Truth is for measuring and for the declared perception stand-in only.
- Kill only your own run's processes (run tag / explicit PIDs); never `pkill -f` a pattern.
- Never edit a script a live run is executing (runs execute frozen copies of `run_d0.sh`; checks load at start).
- Measure motion in sim time, never wall time — including check-script deadlines.
