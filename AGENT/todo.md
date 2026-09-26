# TODO

Goal: the Acta Astronautica paper. `docs/heldout_design.md` is the plan (§10 work order, §14 instances).
`docs/preflight_checklist.md` is the acceptance list: nothing is frozen while a line is open.

## Done (see docs/research_findings.md)

- F108-F116: site, scenarios, protocol, evaluator, baseline lock, run farm, step 7-9 (covered live 18/21, shared fixes).
- F117-F123: step 10 rounds 1-4 with DeepSeek (4/6); model comparison; reasoner = Qwen3.8-Max (user).
- F124: every text Ours' reasoner reads is in `prompts/ours/` (system.md, step.md, tools.yaml).
- F125: request kinds (authorization / authority_check / new_procedure / information); console answers by kind.
- F130-F131 (session B): ablations -> user decides later; `scan_label` built, unregistered.
- F132: rows -> tables on 35 runs, per-leg failure table, raw-record recompute (E2, B4 done; R2 partial).
- F133: PLEXIL adapter logs the issuing node id (E7); live `ros/install` NOT rebuilt yet.
- F135: mission video + swimlane figures (H1, H3). F136: retry-budget sensitivity (EUROPA N=1/2/3/5; PLEXIL N by
  argument, decided). F137: freeze audit + tag tools (F2, F3 tools ready).
- F138: step 10 with Qwen: 5/6 solved live; L2-B false completion -> verifier `holds: null` fix + place retreat by base.

## Step 10 -- closing

- [ ] **L2-B verification** `artifacts/runs/step10_qwen/ours_q_l2b_resume43c` (resume before the re-pick, base
      withdrawal). Accept: the container stays on habitat_stand/slot_0 upright (evaluator truth, z 0.55, tilt ~0),
      item_placed holds true or null (never a false "holds" with the item elsewhere), no drag in the wrist frames.
      If it passes: L2-B solved -> 6/6 -> close C5 in the checklist (cite F138), step 10 done.
      If the base withdrawal fails: record, do NOT invent a new retreat; report to the user.
- [ ] Clean up after closing: tmux/containers none; `artifacts/runs/step10_final` (stopped, incomplete) can be deleted
      with the user's OK; `artifacts/runs/step10_qwen/l2b_r3_resume_src` is a derived resume source (keep).

## Freeze (step 11) -- in order

1. Rebuild the PLEXIL adapter into `ros/install` (E7 node id; no run may be live): `colcon build --merge-install
   --packages-select plexil_capability_adapter` in a pinned container, `PLEXIL_HOME=$HOME/Programs/plexil`; rerun
   `baselines/plexil/scripts/offline_check.py` (51/51 must stay).
2. Shared-layer changes since step 9 touch all methods (place withdrawal by base, F138): run ONE covered place per
   baseline offline/live only if a line of the checklist needs it (B1/B5 wording) -- do not rerun step 9.
3. `python3 -m evaluation.freeze_audit` on the freeze commit; read the report (F137); all hunks traced.
4. `python3 -m evaluation.freeze_tag <tag> --tag` (all three repos clean), then the retry-budget script on the frozen
   artifacts (`baselines/scripts/retry_budget_sensitivity.py`, docker `--init`).
5. Checklist lines still open at the freeze: R2 PARTIAL (baseline per-call record only in capability_server.log --
   accepted or add a topic), C8/G2/G3 DEFERRED past Experiment I (user).

## Campaign (step 12)

- Experiment I: §14's 13 instances x 3 methods; Ours x3 on held-out; 6 GPUs via `farm_queue.sh`; daytime gateway.
- Then ablations (§5.7, method decided then), scan_label registration + Experiment II, re-authoring cost.
- Figures: `experiments/video/swimlane.py`, `mission_video.py`; tables: `evaluation/rows.py` -> `tables.py`.

## Paper drafting (parallel)

- Intro, related work, problem setting, method: writable now. Limitations list: see F138 "not fixed" + earlier ones
  (one engineer, look-alike masses, category-level L2-B precedent, AMCL bias, fixed 300 s ground decision).

## Rules (user)

- Simplified Chinese replies, plain words, conclusion first. Decide defaults yourself; ask only design questions.
- Only fix the current blocker; offline check first, one decisive live test; never rerun what already passed
  (resume from a snapshot: `OURS_RESUME_FROM` + `OURS_RESUME_BEFORE_STEP`, jaws must be empty at that snapshot).
- No defensive code, no hash checks, pytest only if essential. Never edit openral rskill modules while a run is live.
- Contacts from truth + layout; never navigate on truth; generic changes only for Ours (three checks, recorded).
