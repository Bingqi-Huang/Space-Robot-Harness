# Pre-freeze work order (2026-09-25)

Everything that must exist before the freeze (step 11) besides step 10 itself. Derived from `docs/preflight_checklist.md`
(each item names its lines); nothing is frozen while a line is open. Two sessions work in parallel:

- **Session A (main checkout)**: step 10 -- the reasoner model comparison (Kimi-K3, Qwen3.8-Max vs DeepSeek-V4.1-Flash,
  F119-F121), the model decision with the user, D3's approval path live. Owns GPUs 0-3 and every run under
  `artifacts/runs/step10_*`.
- **Session B (worktree `.worktree/prefreeze`, branch `feat/prefreeze-infra`)**: items 1-6 below. Owns GPUs 4-5 for
  live checks.

## Rules for session B (on top of AGENT.md and the user's standing rules in AGENT/handoff.md)

- Read first: `AGENT/research_content.md`, `docs/heldout_design.md` (§6 Exp II, §14 instances), `docs/baselines/authoring_spec.md`,
  `docs/preflight_checklist.md`, `docs/preregistration.md`, `AGENT/handoff.md`, `docs/research_findings.md` F108-F121.
- Replies to the user in concise Simplified Chinese, plain words. Each item: offline first, then at most one decisive live
  run; report before starting the next item if a hypothesis fails. No defensive code, no hash checks, pytest only if
  essential. Record each item's result in `docs/research_findings.md` (next free F number, coordinate with session A by
  pulling main before writing) and tick its checklist line.
- **What the live stack runs**: every simulation (run farm, `run_d0.sh`) imports openral from the main checkout's
  `openral/.venv` (editable installs of `/mnt/SharedData/Research/Space_Robot_Harness/openral`) and SRB from the main
  checkout. openral / SRB edits made in the worktree are therefore checked **offline** in the worktree and exercised
  live only after they are merged to main -- and a merge that touches openral rskill modules or SRB assets/scenes waits
  until no `rf-*` container is running (lazy imports and Isaac's file watcher: F112, F115). Research-repo code (space_runtime,
  evaluation, experiments, openral_ext, configs) runs from wherever the run is launched: launch live checks from the
  worktree path (`/mnt/SharedData/Research/Space_Robot_Harness/.worktree/prefreeze/experiments/launch/...`).
- GPUs 4 and 5 only; one simulation per GPU; kill only your own containers (`rf-pf-*` names).
- Baselines are locked (authoring_spec change control): only the infrastructure items below touch the PLEXIL adapter.
- Ours gets no situation-specific content; the ablation switches remove mechanisms, they add no knowledge.
- Merge: rebase on main, offline checks pass, then ask the user to merge; delete the worktree and branch after.

## Order

**0. Decisions held by the user (session A brings them):** the reasoner model (step 10); who the "engineer" is in
Experiment II and the re-authoring cost (the user, or Claude Code -- changes what H2's time measures, research_content
§5.6). Items 1-4 do not depend on them; item 3's timed authoring does, its infrastructure does not.

**1. Ablation switches -- checklist C8 (H3, research_content §5.7).** Wait for `feat/prompt-text` (docs/prompt_text_design.md,
session A) to be merged: the context variant builds on the reorganized snapshot, and `space_runtime/`, `console.py` and
every model-facing text belong to that task until then. Design the switches meanwhile. Four variants of Ours, each one configuration switch
in `configs/space_runtime.yaml` (or a variant file) read by `space_runtime`: (a) no authoritative facts -- the agent's
own claims advance state; (b) no internal effect verification -- the skill's success flag is taken as the effect;
(c) no invariant/authority guard -- every call dispatched; (d) no dynamic context reconstruction -- plain accumulated
history instead of the rebuilt snapshot. Offline: each variant driven through a recorded run's events (the
`experiments/reasoner_replay` pattern) shows the intended difference and nothing else. Live: one smoke run per
variant on a covered instance (4 runs, GPUs 4-5) after the code is final. The run manifest records the variant.

**2. Evaluation and trace infrastructure -- E2, E7, R2, B4.**
- E2: rows -> tables end to end on step 9's baseline runs and the step-10 runs (all three methods in one table).
- E7: the PLEXIL adapter logs the plan node id with each capability call (join key for trace completeness); rebuild in
  `ros/` (`colcon build --merge-install --packages-select plexil_capability_adapter`, PLEXIL_HOME set, pinned
  throwaway container); offline check with `baselines/plexil/scripts/offline_check.py` (51/51 must stay).
- R2: recompute rows / violations / interaction measures of one run from its raw record only (bag, 1 Hz frames,
  model_io, operator log, run manifest) without the run's derived logs; list anything missing from the raw record.
- B4: the per-leg physical-failure table from rows.py on real runs (step 10 has failed press / place / release calls).

**3. Experiment II infrastructure -- G1, G2, G3 (heldout_design §6).**
- G1: `scan_label` shared low-level implementation, **not registered** in any method's artifacts (no contract entry
  visible to the methods, no PLEXIL Command, no EUROPA activity): one whole operation at a surveyed support the rover
  is docked at -- raise the wrist camera to its scan view (0.45 m from the item's column foot, along the approach, 70 deg
  below horizontal), decode Data Matrix with zxing-cpp on the 2x-upscaled frame, return serials + evidence frame.
  Offline: decodes on the A1 renders of every ORU view. Live: one call per §14 support an ORU sits on (GPUs 4-5, after
  merge if it lives in openral).
- G2: the hidden cases as scenario configs (SRB task + manifests): the serviceable spare recorded at the depot but
  sitting in another PDU's tray/shelf; two identical ORUs with swapped records. Boot check as A2 (initial state from the
  site model's own functions), physically solvable (supports free, work stands exist), labels decode at every candidate
  location. Hidden: not in any artifact the methods or the extension author sees before the extension is frozen.
- G3: the visible validation suite for the extension (build, wiring, one nominal case "scan and confirm the depot
  spare", trace completeness).

**4. Figures and video -- H1, H3.**
- H1: render a mission video from a finished run's raw record (1 Hz front/wrist frames, map + path, events, the
  agent's own rationale) with `experiments/video/`; fix the silent mini-map drop (relative default paths).
- H3: the §8 swimlane per method with the Earth-visibility window shaded, from the event logs (the
  `*_timeline_from_logs.py` scripts still look for the old bag dir `robot_motion`, now `bag`).

**5. Offline analyses due at the freeze.** Retry-budget sensitivity (N = 1, 2, 3, 5 on every held-out state, both
baselines; authoring_spec "After the freeze") -- script ready and run once now, rerun on the frozen artifacts.
   PARTIAL 2026-09-26 (F136): `baselines/scripts/retry_budget_sensitivity.py` run once (run-farm image, `docker run --init`).
   EUROPA: 6 held-out instances x N = 1/2/3/5 all detected -> escalated, only the number of repeats changes. PLEXIL's N is
   plan structure (every Try expanded three times), not a parameter: N = 3 only, 6/6 escalated; N != 3 waits for the
   user (derived plan / argument / change the lock). Rerun on the frozen artifacts.
   DECIDED 2026-09-26: PLEXIL N != 3 by argument, no derived plan: every held-out fault persists (L2-A re-trips 30 s after
   the reset, L3/L4 at the reset, L2-B's place fails every time), so repeating the same call cannot change the outcome;
   EUROPA's N = 1/2/3/5 table is the empirical support. The locked plans stay untouched.

**6. Freeze tooling -- F2, F3.** A freeze-audit script: lists every Ours artifact (`prompts/ours/`, contract texts,
guard config, verifier, context builder) and diffs it against the step-10 starting point (F116's audit), each change
with its F-number; checks the baselines against the lock's traceability tables. F3: tag script for all three repos + the
run-farm image digest + model id / decoding config into the manifests. Run at the freeze, not before.
