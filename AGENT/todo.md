# TODO

Goal: the Acta Astronautica paper. Another agent writes the manuscript from `docs/report.md` +
`AGENT/research_content.md` + `AGENT/execution_plan.md`. **This agent only runs experiments and records them
faithfully** (findings, report); it does not write or edit the paper (user 2026-09-30).

## Done (see docs/research_findings.md)

- Experiment I = exp1b (F142, F152 statistics, F153 corrections); Experiment II (F144-F147); ablations stage 1-2
  offline (F148-F150, F153); re-authoring authoring (F149, F151); 6 of 8 re-authoring cases live PASS (F154).
- `docs/report.md` (overview + six parts in `docs/report_parts/`, every number sourced) for the manuscript agent.
- Real LunarBot demonstration: dropped by the user (future work). Live ablation runs: stopped by the user, not used,
  not written into the report.

## Open (in order)

1. **Re-authoring study, last two cases** (F154). Engineer sessions of the previous session may still be running; if
   they are gone, finish by hand from the worktrees, following docs/reauthoring/spec.md:
   - EUROPA->PLEXIL L3: queue `reauth-europa-l3-v1` on GPU 1 (BESS done, ISRU running) -> `validate.py` on
     `artifacts/runs/reauth/europa_plexil_l3/v1/*`, stop the worklog timer at PASS, commit on `reauth/europa-l3`.
   - PLEXIL L2-B: v1 stalled after PLAN (no capability call for 4.5 h; cause not yet reported); v2 queued on GPU 1
     (`reauth-plexil-l2b-v2`) -> validate, diagnose v1's stall (plan defect or platform), commit on `reauth/plexil-l2b`.
   Then one table baseline x case: engineering time = active time minus waiting on the simulation (user rule),
   validation runs, modelling errors, files and +/- lines, constructs added. Record in findings, fill the re-authoring
   table in `docs/report_parts/05_*`, rebuild `docs/report.md` (cat 00, 01a, 01b, 02, 03, 04, 05 joined by `---`).
2. **Videos (user-approved):** 13 Ours runs of Experiment I, one per instance, all panels, 1x simulated time, 10
   frames per simulated second, label "THIRD-PERSON VIEW". Running since 14:40 CST: `experiments/video/render_1x.sh
   <gpu>` in tmux `vid-gpu{0,2,3,4,5}`, shared list `artifacts/figures/exp1b/video_1x/runs.txt`, log
   `.../video_1x/render.log`, output `.../video_1x/<run>.mp4`, frames `.../video_1x/replay/<run>/`; ~3-4 h. Add a
   worker on GPU 1 (`tmux new-session -d -s vid-gpu1 "experiments/video/render_1x.sh 1"`) when the re-authoring runs
   end. Replay uses `.worktree/ablation` (SRB pinned to exp1b): keep that worktree until the videos are done. Check
   each finished video (video seconds = simulated seconds; panels present).
3. Merge `feat/ablation` into main after the videos (needs the user's go; switches default off, render_check
   1099/1099). Then remove `.worktree/ablation` and the 8 `.worktree/reauth-*` once their branches are committed.
4. Preregistered `preplanned_transition_fraction` never computed: ask the user (compute offline, or state deviation).
- Not now (user): Exp II "plan B"; push (waits for the user); the wrist-camera render artefact (user: forget it).

## Clean-up (keep for now)

- `artifacts/runs/step10_final`, `.worktree/prefreeze` + branch `feat/prefreeze-infra` (user 2026-09-26).
- Unused live ablation dirs `artifacts/runs/ablation/{j1,j1b,j3,j3b,j1c,j3c,j1d}` (records only).

## Rules (user)

- **Simplified Chinese replies, plain words, conclusion first. Never report with internal codes** (J1, F153, stage 2,
  ...): say what the experiment is and what it means for the paper, from the paper's purpose and first principles.
- Decide defaults yourself; ask only design questions; when the user only asks, only answer. Plan changes,
  experiments, merges and pushes need the user's explicit go. When the user says stop or do not record, obey exactly.
- This agent runs experiments and records them; it does not edit the manuscript (`paper/`).
- Simulation time means nothing for the research: engineering cost = active time minus waiting on the simulation.
- Only fix the current blocker; offline check first, one decisive live test; rerun only the affected run, from a
  snapshot where possible; never rerun what already passed. Campaign fixes: all methods, findings, folded in.
- Ours: generic changes only (names no situation/place/serial; holds for every task; traceable). Baselines locked.
- No defensive code, no hash checks, minimal pytest. Contacts from truth + layout; never decide or navigate on truth.
- One Isaac instance per GPU (lock: `experiments/reauthoring/gpu_run.sh`); kill only own containers; long runs
  watched by a Monitor, no polling; no freeze ceremony. State the model-token budget before any large offline batch.
- Key: first `sk-` in `AGENT/VLM_provider.md`, never printed or written anywhere.
