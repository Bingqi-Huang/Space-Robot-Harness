# Handoff

Updated 2026-09-30 17:30 CST. Experiments are done; this session is closing the last items (AGENT/todo.md). The
manuscript is written by another agent from `docs/report.md` (+ research_content, execution_plan); this agent runs
experiments and records them; it never edits `paper/` (user). Nothing pushed: research main is ahead of origin (42+).

Read `AGENT/research_content.md`, `AGENT/execution_plan.md`, `docs/heldout_design.md`, `docs/baselines/authoring_spec.md`,
`docs/preregistration.md`, `AGENT/todo.md`, `docs/research_findings.md` F140-F157, then `docs/report.md` (the evidence
base: overview + parts 1a, 1b, 2, 3, 4, 5, 6). Goal: the Acta Astronautica paper (H1 no rewrite for unplanned situations,
H2 less engineering to add a capability, H3 open reasoning inside hard boundaries). Framing (user): trustworthy AI --
a foundation model embedded in a space robot's mission workflow raises autonomy while the harness keeps safety and the
established engineering disciplines; never "an LLM calling tools" or "Claude Code for the Moon".

## Results (all in docs/report.md; numbers there are sourced)

- Experiment I = exp1b (F142, F152, F153): Ours covered 7/7, held-out 18/18, 0 ground re-authoring; PLEXIL and
  EUROPA->PLEXIL covered 7/7, held-out 0/6 each (detected -> escalated -> safe hold). 0 false completions; guard held 3.
- Experiment II (F144-F147): new shared capability `scan_label`; fresh Claude engineers; hidden cases 0/6 before,
  Ours 6/6, PLEXIL 2/2, EUROPA 2/2 after. Ours changed no procedure (a contract + a verified fact).
- Ablations (F148-F150, F153): offline only (684 decisions); live runs stopped by the user, not reported.
- F155: preregistered `preplanned_transition_fraction` computed offline (report part 2 §5.9): PLEXIL 0.75-0.93,
  EUROPA 0.75-1.00, Ours 0 by construction.
- F157: community-standard metrics computed post hoc (report part 6: glossary of every measure, GC, PLW, pass^k, safe
  success, FDIR coverage, MTBI, intervention response time, run-time assurance, code churn, planning-model size, ECSS
  levels, references). Which enter the paper is decided at writing time (user). Scripts `evaluation/standard_metrics.py`,
  `evaluation/engineering_metrics.py`.
- Re-authoring study (F149, F151, F154; F156 to write): engineering time = timer minus overlap with own validation runs
  (`experiments/reauthoring/cost_table.py`). PLEXIL 5.5 / 11.0 / 8.8 / 13.6 min (L2-A/L2-B/L3/L4), EUROPA 11.7 / 81.4 /
  63.3+ / 59.7 min. 7 of 8 PASS. PLEXIL L2-B: v1 stalled (the engineer's new Lookup never re-asked after a lost
  response), v2 PASS 16:12. EUROPA L3: v1 ISRU PASS; v1 BESS = PLEXIL executive SIGSEGV 10 s after start (infrastructure,
  1 in 46 exec starts), rerun `artifacts/runs/reauth/europa_plexil_l3/v1_rerun` running on GPU 1 (tmux
  `reauth-europa-l3-rerun`), then `validate.py v1_rerun/europa_l3_bess v1/europa_l3_isru`.

## In progress right now (do not disturb)

- **1x videos of the 13 Ours exp1b runs** re-rendering WITH body textures (the 16:xx render lacked the texture mount:
  second time this happened). Workers: tmux `vid-gpu{0,2,3,4,5}-{1..6}` running `experiments/video/render_1x.sh <gpu>
  <slot>`; they claim chunks from `artifacts/figures/exp1b/video_1x/chunks.txt` (made by `experiments/video/plan_chunks.py`),
  render with `.worktree/ablation/experiments/video/replay_render.py --only a,b` and compose when a run's frames are
  complete. The texture mount comes from `RUNFARM_ARGS` (render_1x.sh -> docker/runfarm/runfarm.sh). ETA ~18:15.
  Never delete `.worktree/ablation` or edit its `replay_render.py` while a worker runs (each chunk reloads it).
- **Next for the videos (camera occlusion fix, developed and checked offline)**: in 5 videos the ISRU tank skid (5.7 m)
  or the radome hid the rover (some frames black). `.worktree/ablation/experiments/video/replay_render_next.py` picks,
  per occluded stretch, the least-occluded of 8 camera positions, blends it in, lifts the camera over an occluder it
  would enter; bounds in `lunar_base_asset_bounds.json` (made by `asset_bounds.py` with Isaac's pxr on CPU). Offline:
  only ours_a_isru, ours_b_cons_habitat, ours_l2a_bess_r1, ours_l2b_habitat_r1, ours_l3_isru_r1 change (~5300 frames),
  eye never inside an occluder, residual partial occlusion 3-6 s. After the render: move _next over replay_render.py,
  delete exactly the changed frames (compare old vs new `camera_path`), remove those runs' `replay/<run>.composing` and
  mp4, re-plan chunks, re-render, check (textures: 0 "can not be found" + a side-by-side frame; black frames; duration).

## Videos, general

- Output `artifacts/figures/exp1b/video_1x/<run>.mp4` (1600x900, 10 fps = 1x simulated time, all panels, label
  "THIRD-PERSON VIEW"); earlier 6x textured videos of six runs (3 methods, L4 + L2-B) in `artifacts/figures/exp1b/video/`;
  swimlanes `artifacts/figures/exp1b/swimlane/`; success figure `paper/figures/success_by_level.png`.
- LunarBot's USD points at textures on the dev machine's absolute path; on pro6000 they are mounted from
  `/mnt/SharedData/Research/lunarbot_textures/textures` (memory: feedback-video-textures-mount).

## Heads

- Tags: `freeze-1`, `exp1b` (Exp I), `exp2-*` (Exp II bases/results). Branches: research `main`, `feat/ablation`
  (`.worktree/ablation`; merge approved by the user after the videos), `reauth/<baseline>-<case>` (8, committed;
  worktrees `.worktree/reauth-*` to remove after the merge), `feat/prefreeze-infra` + `.worktree/prefreeze` (keep, user).
- Reasoner Qwen3.8-Max, VLM DeepSeek-V4.1-Flash, paratera gateway; key = first `sk-` in `AGENT/VLM_provider.md`
  (gitignored; never print it or write it anywhere).
- Report build: `docs/report.md` = parts 00, 01a, 01b, 02, 03, 04, 05, 06 of `docs/report_parts/` joined by
  "\n\n---\n\n" (a loop over the eight files; the result must equal the join exactly).

## Run farm (pro6000, host astroeng, uid 1007)

- Repo `/mnt/SharedData/Research/Space_Robot_Harness`. One simulation per GPU through the lock
  (`experiments/reauthoring/gpu_run.sh`, `gpu_free.sh`); replay renders (no ROS) may share a GPU (user 2026-09-30).
- Batches: `farm_queue.sh`; never touch a run root's `.next`/`.lock` or move its runs before "queue done".
- Throwaway containers: no GPU, `--cpuset-cpus 30,31,62,63`, `nice -n 19`. Isaac's pxr works on CPU with
  `PYTHONPATH=LD_LIBRARY_PATH=.../extscache/omni.usd.libs-*` and `kit/python/bin/python3`.

## Rules (user)

- Simplified Chinese, plain words, conclusion first; no internal codes (J1, F153, ...) when talking to the user.
- Decide defaults yourself; ask only design questions; plan changes, experiments, merges, pushes need the user's go.
- Only fix the current blocker; offline check first, one decisive live test; rerun only the affected run.
- No defensive code, no hash checks, minimal pytest. Truth only for evaluation, never for decisions or navigation.
- Kill only own containers; long runs watched by a Monitor; state the token budget before a large model batch.
- Keep this file and todo.md <= 150 lines, overwrite at milestones.
