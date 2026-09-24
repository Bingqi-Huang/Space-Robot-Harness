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
   STATUS 2026-09-25: 1-7c done (F115); pre-step-10 items (F116); step 10 round 1 4/6 (F117). Next: round 2.
   1-7b. DONE (F115): step-9 results classified, READY' posture, labels + scan_label's view, raw-data record, EUROPA
      start race, live checks check1/check2.
   7c. DONE (F115): (a) place onto an occupied stand no longer reports success (settle: nothing between the fingers);
      (b) the shared 1.5 m (approach point, dock corridor entry, inserted undock, PLEXIL plans, EUROPA domain) -> 1.2 m;
      offline over 28 docking features 1 hit -> 0. The audit's other items stay as they are (user decision).
   8. [x] B6 closed.
10. [ ] **Ours development on the held-out ladder** (paper §4, §6.3 trace figure). Generic changes only (§13.1), each
        in `research_findings.md`; development runs never count. §14's six held-out instances.
        Ready (F116): Earth sets 925 s after the start; queued escalation = re-authoring; held-out places replay
        clean; Ours' starting point audited (observe example removed); `max_steps` 80 kept (~40 expected).
        Round 1 (F117): 4/6; L2-B + L4 failed on Ours' harness (place verifier, link context), fixed; round 2 =
        `jobs/step10_r2.txt` (L2-B, L4). Round 1 = `jobs/step10_r1.txt`: Ours x6. Then diagnose
        (pictures first), fix generically (prompt/playbook edits allowed if they name no unit, cause, object or
        ordering and hold for every mission; each recorded), rerun only what failed; at most 3 rounds (user goal).
        Watch: reset reported done before the L2-A re-trip (30 s); L4 request vs Earth-set (925 s);
        per-request wall-clock time (pre-registration §3).
10b. [ ] **`docs/preflight_checklist.md` all lines closed** (created 2026-09-24 after the label defect): every paper
        output's needs -> a check. Nothing is frozen while a line is open. Open now: B4, C5, C6, D2, D3, E2, E7, F2, F3, G1-G3, R2.
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
