# Handoff

State as of 2026-09-13. Phase A (upstream verification), A2 just finished.
Task list: `todo.md`. Decisions: `docs/upstream_pins.md`.
Fork patch record: `docs/openral_py310_patch.md`.
Execution-path map: `docs/openral_integration_notes.md`.

## Done: A0, A1, A2

**A0/A1** — research repo (`main` @ `48021dc`) with `openral/` pinned as a
submodule to the fork branch `feat/py310-humble` (pushed, commit `4c1867c`).
`space_robotics_bench/` is **not tracked** — another agent owns it; never
touch/commit/branch it.

A1's Python-3.10/Humble downgrade is fully verified: rclpy loads from the venv
and creates a live node, 9 ROS packages build (incl. the C++ safety kernel,
which runs and registers on the graph), `openral doctor` is clean, and the
unit suite went from 0 useful signal to **5236 passed / 4 failed / 120 skipped
/ 2 errors** — the 4 remaining are individually verified pre-existing and
unrelated to the Python-version target (documented in
`docs/openral_py310_patch.md` §6, not fixed by design).

**A2** — traced the full reasoner → skill → safety path and wrote it up in
`docs/openral_integration_notes.md`. Highlights that change how later phases
should be built:

- `_dispatch_execute_rskill` **already refuses** several mission-invalid
  proposals (collective target, busy double-dispatch, VLA/VRAM-unfit pair) —
  plan §5.4.5's trustworthiness cases partially exist already; don't
  reinvent, extend.
- `MissionState` + `evaluate_task_verdict` is a **reward-gated** verification
  mechanism (Robometer progress/success heads via `QueryTaskProgress.srv`),
  not LLM self-report — plan §4.8's verifier role is partially filled.
  Ladder-state persistence exists (`ReasonerLadderState`, atomic JSON,
  crash-resume) but is single-process/file-based with no space context —
  that gap is what `space_runtime.mission_store` should extend, not rebuild.
- `WorldState`'s only resource field is `battery_pct` — confirmed nothing
  else to duplicate; `space_context` adds entirely new ground.
- **Safety: build against the C++ kernel**, not the Python passthrough
  (explicitly a "Day-1... stub" in its own docstring). The kernel is shipped,
  runs, and does force/workspace/controller/collision with fail-closed
  staleness handling.
- **WAM is not shipped** — Protocol + `NullWorldModel` stub only.
- **Insertion point decided**: subclass `ReasonerNode`, override
  `_dispatch_execute_rskill` only. `_dispatch` is a plain method call with no
  hook system — this needs zero upstream source changes, just a new
  `openral_ext/reasoner_dispatch_bridge` package. Caveat: private method
  surface, re-verify after every rebase.

## Next: A3 (SRB, read-only) then A4

- `srb ls`; run one manipulation task + `_ground_manipulation`; launch the ROS
  interface both passive/active; record real topic/service/action
  names+types+QoS; confirm a control command moves the robot.
- Decide the Phase-B embodiment (least integration work wins, §6.2) —
  LunarBot is not a prerequisite.
- **Do not modify anything under `space_robotics_bench/`** — another agent is
  actively working there. Read/run only.
- A4: both OpenRAL and SRB alive at once, one SRB topic readable from the
  OpenRAL side (keep SRB on `distro="humble"` — Isaac bundles its own
  cpython-311 rclpy for both distros, so this is a same-process-family
  wire-format match, not a real dependency). Clear stale
  `/dev/shm/fastrtps_*` first.

## Watch out

- Upstream `CLAUDE.md` says "Python 3.12 only" — the deviation is deliberate
  and fully recorded. Re-run the linenos refresh
  (`tools/refresh_methods_linenos.py`) **last**, after any further source
  edit — it drifts again if you edit a tracked file afterward (this bit us
  once mid-session).
- The grep/AST scan for 3.11+ syntax only covered `python/`/`packages/`;
  `tools/` and `tests/` needed a second pass (`datetime.UTC`, `tomllib`) found
  only by actually running the suite. Don't trust a static scan alone again.
- `OPENRAL_REASONER_MODEL` is unset; curated ids are `claude-opus-4-8`,
  `cosmos3-edge`, `gpt-5.5`, `gpt-5.6`. Configure in Phase B, not now.
- No `space_runtime` / `space_context` code until Phase A is finished —
  mechanisms follow observed failures (plan §21.6–7).
