# TODO

Goal: the Acta Astronautica paper. Another agent writes the manuscript from `docs/report.md`; this agent runs
experiments and records them (findings, report); it does not edit `paper/` (user 2026-09-30). A separate session builds
a public project website (GitHub Pages, `.worktree/site`, branch `gh-pages`); it reads research files, never changes them.

## Done (docs/research_findings.md)

- Experiment I = exp1b (F142, F152, F153); Experiment II (F144-F147); ablations offline (F148-F150, F153).
- F155 preplanned_transition_fraction (report part 2 §5.9). F157 community-standard metrics + glossary (report part 6).
- F156 re-authoring study closed: 7 of 8 live PASS; engineering times in report part 5 §A.9.
- F158 13 textured 1x videos with the occlusion-aware camera, checked (`artifacts/figures/exp1b/video_1x/`).
- feat/ablation merged into main (full method re-renders the final Exp II run 67/67 identical); worktrees of the
  ablation and the 8 re-authoring engineers removed (branches kept).

## Open -- decisions for the user

1. EUROPA->PLEXIL L3, BESS instance: its reset press is blocked by a shared press-skill limitation (arm arriving
   unstowed at the BESS panel: 4/4 first presses fail). Options: (a) report as is (current record: not passed,
   engineering time 63.3 min); (b) a fresh engineer session adds a stow before the reset (counted engineering, one
   ~80 min validation run on one GPU); (c) fix the shared skill after the campaigns (shared-layer change: record it,
   rerun only this validation).
2. Push research main to origin (50+ commits ahead) -- only on the user's go.
3. Optional clean-up: `artifacts/figures/exp1b/video_1x/replay/` (259 GB of rendered frames; the mp4s are final).

## Not now (user)

- Exp II "plan B" (human engineers); real LunarBot demo (dropped, future work).
- Kept: `artifacts/runs/step10_final`, unused live ablation dirs `artifacts/runs/ablation/{j1,j1b,j3,j3b,j1c,j3c,j1d}`,
  `.worktree/prefreeze` + `feat/prefreeze-infra`.

## Rules (user)

- **Simplified Chinese replies, plain words, conclusion first. Never report with internal codes** (J1, F153, ...).
- Decide defaults yourself; ask only design questions; when the user only asks, only answer.
- Simulation time means nothing for the research: engineering cost = active time minus waiting on the simulation.
- Only fix the current blocker; offline check first; rerun only the affected run, from a snapshot where possible.
- Ours: generic changes only; baselines locked. No defensive code, no hash checks, minimal pytest.
- One simulation per GPU (lock); renders may share GPUs; kill only own containers; Monitor for long runs.
- Videos: always mount the textures and compare a frame's rover with a textured reference before accepting.
- Report build: `docs/report.md` = report_parts 00, 01a, 01b, 02, 03, 04, 05, 06 joined by "\n\n---\n\n".
- Key: first `sk-` in `AGENT/VLM_provider.md`, never printed or written anywhere.
