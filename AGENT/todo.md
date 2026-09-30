# TODO

Goal: the Acta Astronautica paper. Another agent writes the manuscript from `docs/report.md`; this agent runs
experiments and records them (findings, report); it does not edit `paper/` (user 2026-09-30). A separate session builds
a public project website (GitHub Pages) from the report and figures (user 2026-09-30); it reads, it does not change
research files.

## Done (docs/research_findings.md)

- Experiment I = exp1b (F142, F152, F153); Experiment II (F144-F147); ablations offline (F148-F150, F153).
- F155 preplanned_transition_fraction (report part 2 §5.9). F157 community-standard metrics + glossary (report part 6).
- Re-authoring: 7 of 8 cases PASS live (PLEXIL L2-B v2 PASS 2026-09-30 16:12).

## Open (in order; all approved by the user)

1. **Re-authoring, last case**: when `artifacts/runs/reauth/europa_plexil_l3/v1_rerun/queue.log` says "queue done",
   `python3 experiments/reauthoring/validate.py .../v1_rerun/europa_l3_bess .../v1/europa_l3_isru`; close the worklog
   `europa_plexil_l3.jsonl` (session from the v1 start 13:49:19 CST to the rerun end: all simulation wait; note the
   v1 BESS executive SIGSEGV = infrastructure, repeated) and commit it on `reauth/europa-l3`; run
   `experiments/reauthoring/cost_table.py`; write F156 (all 8 cases: engineering time, validation runs, errors by kind,
   churn, model size); replace part 5 §A.9 ("PENDING") with the final table, fix part 5 header/Gaps 1-2; rebuild
   report.md; commit.
2. **Videos**: textured render ends ~18:15 -> occlusion fix (handoff "Next for the videos") -> check all 13 (0 missing
   textures, rover decals visible, no black main view, duration = simulated seconds) -> record in findings (with the
   texture incident) and report part 5 §C.2 -> commit.
3. **Merge `feat/ablation` into main** (user: after everything is done): it carries the ablation code (switches default
   off), the chunked renderer, the camera fix, `asset_bounds.py`. Then remove `.worktree/ablation` and the 8
   `.worktree/reauth-*` worktrees (branches stay). Keep `.worktree/prefreeze` + `feat/prefreeze-infra`.
4. Overwrite handoff/todo, final commit, report to the user (Chinese, plain).

## Not now (user)

- Push (waits for the user); Exp II "plan B" (human engineers); real LunarBot demo (dropped, future work).
- Clean-up kept: `artifacts/runs/step10_final`, unused live ablation dirs `artifacts/runs/ablation/{j1,j1b,j3,j3b,j1c,j3c,j1d}`.

## Rules (user)

- **Simplified Chinese replies, plain words, conclusion first. Never report with internal codes** (J1, F153, ...).
- Decide defaults yourself; ask only design questions; when the user only asks, only answer.
- Simulation time means nothing for the research: engineering cost = active time minus waiting on the simulation.
- Only fix the current blocker; offline check first; rerun only the affected run, from a snapshot where possible.
- Ours: generic changes only; baselines locked. No defensive code, no hash checks, minimal pytest.
- One simulation per GPU (lock); renders may share GPUs; kill only own containers; Monitor for long runs.
- Videos: always mount the textures and compare a frame's rover with a textured reference before accepting.
- Key: first `sk-` in `AGENT/VLM_provider.md`, never printed or written anywhere.
