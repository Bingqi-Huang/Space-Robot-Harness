# TODO

Goal: the Acta Astronautica paper. `docs/heldout_design.md` is the plan (§10 work order, §14 instances).
`docs/preflight_checklist.md` is the acceptance list.

## Done (see docs/research_findings.md)

- F108-F116: site, scenarios, protocol, evaluator, baseline lock, run farm, step 7-9 (covered live 18/21, shared fixes).
- F117-F125: step 10 with DeepSeek (4/6), model comparison, reasoner = Qwen3.8-Max, texts in `prompts/ours/`,
  request kinds.
- F130-F137: ablations deferred (user), scan_label built, rows -> tables, PLEXIL node id, video + swimlane,
  retry-budget sensitivity, freeze tooling.
- F138: step 10 closed 6/6 with Qwen3.8-Max (L2-B: r3 + resume43d); place withdrawal by the base; a short lift after
  it is not a failure (openral 971f2ea); B5 rechecked live (clean failure). C5 closed.
- F139: freeze (step 11): PLEXIL adapter rebuilt (offline 0 failed), freeze audit clean, tag `freeze-1`.

## Campaign (step 12) -- running

- [ ] Experiment I: `experiments/launch/lunar_base_d0/jobs/exp1_campaign.txt` (51 runs) -> `artifacts/runs/exp1/`
      in tmux `exp1` (farm_queue.sh, 6 GPUs). Order: Ours held-out x3, Ours covered, PLEXIL, EUROPA.
      Watch: `artifacts/runs/exp1/queue.log` (one start/end line per run with CHECK_EXIT).
      Night gateway: if Qwen steps slow to minutes, note the affected runs (model_io.jsonl wall times) and tell the
      user; slowness is not an outage (preregistration §3), do not rerun on your own.
- [ ] Retry-budget sensitivity on the frozen artifacts: `baselines/scripts/retry_budget_sensitivity.py` (docker
      `--init`, pinned CPUs 30,31,62,63) -> compare with F136.
- [ ] After the campaign: `evaluation/rows.py` -> `tables.py` on `artifacts/runs/exp1`; failure taxonomy per failed
      run (preregistration §2); swimlanes + one video per method on a held-out instance.
- [ ] Push: research main, openral master (971f2ea) and the `freeze-1` tags are local -- ask the user.
- Then: ablations (§5.7, method decided by the user), scan_label registration + Experiment II, re-authoring cost.

## Clean-up (ask the user)

- `artifacts/runs/step10_final` (stopped, incomplete) can be deleted; `step10_qwen/l2b_r3_resume_src` keep.
- Worktree `.worktree/prefreeze` + its branch (merged at c6e677d) can go.

## Paper drafting (parallel)

- Intro, related work, problem setting, method: writable now. Limitations: F138 "not fixed" + earlier ones (one
  engineer, look-alike masses, category-level L2-B precedent, AMCL bias, fixed 300 s ground decision, L2-B's step-10
  solve spans a resume).

## Rules (user)

- Simplified Chinese replies, plain words, conclusion first. Decide defaults yourself; ask only design questions.
- Only fix the current blocker; offline check first, one decisive live test; never rerun what already passed.
- Frozen: no change to any method artifact or shared skill during the campaign; a post-freeze shared fix reruns the
  affected campaign from the start (preregistration §3) -- the user decides.
- Contacts from truth + layout; never navigate on truth; one simulation per GPU; kill only own containers.
