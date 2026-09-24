# TODO

Goal: the Acta Astronautica paper. **`docs/heldout_design.md` is the plan**; its §10 order is the work order below.
Development runs on `pro6000` (see handoff). Larger tasks on `feat/<name>` + `.worktree/<name>`; small fixes straight
on main (AGENT.md §1).

## Done

- F108-F111: held-out site, scenarios, protocol, evaluator, baseline lock, run farm, models on paratera.
- F112 (2026-09-24): step 7 (baselines built to the lock, EUROPA use-after-free patched) and step 8 (physical
  validation: every held-out action form executed; shared-layer fixes in nav map, pick, place, press, capability
  boundary, run farm). Final batch `artifacts/runs/chain_*_f` (see the F112 table).
- F113 (2026-09-24): the Nav2 pose freeze was a tf2 ABBA deadlock (upstream fix 9997e969, built into the run-farm
  image); bt_navigator ack timeout 20 -> 1000 ms; containers set up once (NUMA, domain, gdb); campaign cut to the
  13 instances of `docs/heldout_design.md` §14.

## Work order -- `docs/heldout_design.md` §10

7. [x] Baselines built to the lock (offline): PLEXIL 51 cases, EUROPA A x 5 units + failure paths, B 15 x 3.
8. [x] Physical validation: all 9 held-out sequences end to end (F112 table); the landing stand was moved onto the
       platform level (AMCL bias on the pad ramp) and `chain_b_consumables` passed first try.
8b. [x] Sim speed: `_get_dones` batched (F113 §7), ~10-15% per run; the ROS bridge publishing left as is.
9. [ ] Covered live re-runs: PLEXIL, EUROPA, Ours x the seven L0/L1 instances of heldout_design §14. One run
       each; failures classified by the lock's change-control table. First launch stopped on the F114 livelock
       (deleted); restart in tmux `step9` on the user's go (see handoff).
       Before launching: the PLEXIL adapter is rebuilt in main's `ros/` (done 2026-09-24); Mission B's goal comes from
       `D0_ENV` cargo/destination (`d0_common.mission_b_goal`); EUROPA runs the patched build.
9+. [ ] **After step 9 ends -- in this order; nothing skipped (decided with the user 2026-09-24):**
   1. Read all 21 results; classify failures by the lock's change-control table. Known: `plexil_b_bat_bess` arm_ready
      stopped 3x on contact with the battery (nudged 9 mm / 2.3 deg): a shared-capability gap, not the plan -- docked
      rear to a stand, no camera has measured the item, the planning scene holds only the plinth (0.55 m), the STOW->READY
      sweep (joint6 2.47 rad) crosses it. Backfill run manifests (`openral_ext/run_manifest` backfill); rows -> tables on
      all 21 incl. baselines; write F115.
   2. Ask the user to commit: evaluation fixes (class-2 drop read from the handle; manifest match on every override),
      13 manifests + 6 certificates (stale ones removed), preflight checklist, heldout_design L4 `faulted_unit=pdu_1`,
      pre-registration (user-approved: preplanned fraction per instance, one primary failure category, only
      infrastructure reruns) -> `docs/preregistration.md` made final (done 2026-09-24).
   3. arm_ready fix (shared): a SMALL keep-out above each surveyed support (support top x catalogue max item height +
      a few cm), only for posture moves (arm_ready/stow/fold), the support being worked at exempt, a start inside a zone
      not a planning failure. Check offline with MoveIt alone in a container (every dock pose: STOW<->READY, pick/place
      approach, before/after). Live: rerun only `plexil_b_bat_bess` + one Ours pick/place. Then re-check which step-9
      conclusions still hold and say so in F115 (user: selective reruns, no full step 8/9 repeat).
   4. Labels (Exp II): lid data plate off the handle's centre line, upright from the rover; `scan_label` gets its own
      higher, downward wrist view (heldout_design §6 to be updated). Design from the running offline agent (scratchpad
      label_design/); regenerate item assets, rebuild the scene (no collider, no map re-survey); verify in Isaac: decode
      at the scan pose for every item x support; multi-angle look.
   5. Raw data (user rule: never re-simulate for a new metric): D0_BAG + joint_states, power telemetry, cmd_vel,
      costmaps, amcl; the evaluator recorder saves front + wrist JPEG at 1 Hz; run manifest wired into run_d0.sh; confirm
      Ours keeps every step's full model input/output and every VLM question/answer; measure size + sim-speed cost on one
      run; recompute every metric from the raw record alone.
   6. EUROPA start race (F114 class, missed by the audit): d0_europa_mission_*_check.py waits a fixed 2 s after host.py
      before universalExec, whose HostLink connects once; host.py only listens after its site_map/manifest/power_status
      queries -> under load the exec died, the host waited forever (`europa_b_oru_pdu3`, stopped as infrastructure, not
      scored). Fix: host.py opens its listening socket first, accepts after the queries. Rerun `europa_b_oru_pdu3`.
      PLEXIL adapter logs the plan node id with each command (trace join key); rebuild; rerun its offline check.
      Tools: `*_timeline_from_logs.py` bag dir `robot_motion` -> `bag`; `mission_video.py` absolute default paths.
   7. One selected live batch (6 GPUs): label decode at the scan pose; placing onto the occupied habitat stand fails
      cleanly (the path both baselines take at L2-B); VLM reads PDU-1's shutter and the habitat occupier; the arm_ready
      reruns of 3, `europa_b_oru_pdu3` after 6; the full-recording run of 5 (+ a video rendered from it); optionally the L4-near carry chain.
   7b. Step 9 found more (2026-09-24 17:10): `europa_b_cons_habitat` failed -- EUROPA readies the arm at the start and
      docks with it out; the arm turned the consumables container 18 deg / 5 cm in the last 1.5 s of the dock, and
      three picks failed on the skewed item. Same root as `plexil_b_bat_bess`: the READY posture puts the tool ~1.04 m
      behind the rover at ~1.11 m, where a docked item's handle is -> READY itself (not only a keep-out) is the fix
      candidate; the offline MoveIt agent studies a READY clear of every docked item. Evaluator: Ours' battery carry
      logged 151 contact windows, EUROPA's 6, all while driving with the battery (ORU carries: 0) -> check the carried
      battery's clearance offline -> FOUND: the battery's column is 0.10 m (body stretched to 0.367 m in F110, neck at
      0.4669 m by F112), ORU 0.205, container 0.297; the palm sits just above the lid and the ~3.5 cm swing leaving the
      stand rubs it (both methods, same moment). Candidate fix (user to approve): battery body back to 0.262 m, neck
      height unchanged (longer column); PLEXIL's 9 mm nudge of the battery counted
      nowhere (contact threshold 10 N; collateral excludes the cargo) -> record raw contact forces (raw-data rule).
   8. Close the checklist lines this settles (`docs/preflight_checklist.md`), then step 10.
10. [ ] **Ours development on the held-out ladder** (paper §4, §6.3 trace figure). Generic changes only (§13.1), each
        in `research_findings.md`; development runs never count. §14's six held-out instances, L2-A -> L2-B -> L3 -> L4.
        Ours' `max_steps: 80` may be short for a two-pick case (F114): decide from the first L3 run. Watch: a
        reset reported done before the L2-A re-trip (30 s, false success); requesting approval before LOS in L4.
10b. [ ] **`docs/preflight_checklist.md` all lines closed** (created 2026-09-24 after the label defect): every paper
        output's needs -> a check. Nothing is frozen while a line is open. First: A1 labels (FAIL), C3, E1, A2.
11. [ ] **Freeze** (paper §5.3): manifests, closed-capability certificates, freeze audit, git tags in all repos; the
        run-farm image + synced home installs are the campaign environment. Then offline retry-budget sensitivity
        (N = 1, 2, 3, 5 on every held-out state).
12. [ ] **Campaign** (paper §6), entirely on the run farm, a paired instance's three methods on the same hardware:
        Experiment I (§14's 13 instances x 3 methods; Ours x3 on held-out) -> §5.7 ablations -> build `scan_label`
        -> Experiment II -> §8 re-authoring cost per held-out case.
13. [ ] Real LunarBot segment (§5.8): design deferred until 12 is stable; ask the user before planning it.

## Paper drafting (parallel; LaTeX, Acta Astronautica)

- [ ] Introduction, Related Work, Problem Setting, Method: writable now (no results language), verified citations.
- [ ] Experimental Methodology (§5): after 11. Baseline paragraph: ECSS E3 (PLEXIL) / E4 (EUROPA), pre-planned
      responses for covered failure modes, the rest to ground (ECSS-E-ST-70-11C §5.7.5.2g); sources in authoring_spec.
- [ ] Results, trace figure, Discussion: after 12.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing ejecta"
      is our extrapolation; L2-B precedent is category-level only; look-alike module masses (1 kg); baselines authored
      to the covered specification (a wider failure-mode analysis would cover L2-A at the measured re-authoring cost);
      EUROPA solves one goal at a time and needed an upstream memory fix (F112); a dropped item is unrepresentable in
      the EUROPA domain; physical-layer failures reported per leg; one LLM/VLM (DeepSeek-V4.1-Flash, 60 s VLM choices);
      `retrip_delay_s` 30 s is our thermal estimate.

## Open decisions (user)

- Dev machine: ~100 old run dirs, 330 GB, cleanup deferred.

## Open (fix when a run meets it)

- If a run-farm process hangs: `experiments/analysis/freeze_gdb_watch.sh <run dir>` in the container, or
  `docker exec -u root <ctr> gdb -p <pid> -batch -ex "thread apply all bt"` (F113).
- AMCL republishes map->odom only sporadically right after activation: d0_common's LOCALIZED gate can pass on the
  initial-pose publish; revisit if a run meets it.
- VLM region choice ~60 s median (pick/press allow 300 s).

## Design items not yet built (pick up when a run needs them)

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, a claim ledger.
- [ ] Dock error band from localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class.
- [ ] An exception inside `_execute` leaves `failure_reason` blank; `OURS_RESET=1` reads TF before seeding AMCL.
- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call.
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] If sim speed is ever needed: TF publishing (24 ms/tick) and `_get_dones` (17 ms) outweigh everything but physics.

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the
posture pull's 0.05/s.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15-77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Teardown prints tracebacks and a move_group segfault after SIGINT: shutdown noise, not a run failure.

## Rules

- Acceptance is derived from each paper output's needs (`docs/preflight_checklist.md`), never "the task ran".

- Branch + worktree for larger tasks only; delete both after merge. Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; <=150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run. No base-rate reruns.
- No defensive coding, corner-case guards, hash checks or ad-hoc patches (AGENT.md §4).
- Baselines: native mechanism + covered knowledge only; never strengthened after a failed run (lock change control).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- One simulation per GPU; never navigate on truth; kill only your own processes / containers.
- Never edit the shared skills (openral rskill modules) while runs are live: runners import them lazily.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
