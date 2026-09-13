# Handoff

State as of 2026-09-13. **Phase A is complete.** Next up is Phase B, not yet
started. Task list: `todo.md`. Findings to read before Phase B design work:
`docs/research_findings.md`.

## Phase A summary

- Research repo on `main` (`3f284fa` latest), OpenRAL fork downgraded to
  Python 3.10/Humble and submodule-pinned (`4c1867c`, 5236 tests passing).
- Full OpenRAL reasoner→dispatch→rSkill→safety path mapped
  (`docs/openral_integration_notes.md`). Insertion point for Phase E's
  mission-level admissibility layer decided: subclass `ReasonerNode`,
  override `_dispatch_execute_rskill` only — zero upstream source changes.
- SRB mapped with the **LunarBot** embodiment (user's explicit choice; already
  integrated, teleop/self-collision continue separately, not blocking)
  (`docs/srb_integration_notes.md`). Real control surface identified:
  per-action-term topics (`cmd_vel`/`differential_inverse_kinematics`/
  `binary_joint_position`/`four_wheel_steer`), not the combined echo vector.
- **A4 done**: OpenRAL's own 3.10 venv/rclpy stack read live SRB topics
  (`/srb/env0/robot/joint_states`, `/tf`) off the shared DDS bus with both
  systems running simultaneously.
- Ten findings seeded in `docs/research_findings.md` (F1–F10) — several
  things plan §4 calls for already exist upstream in partial form (mission-
  invalidity gates, reward-gated verification, a ready FDIR-relevant signal);
  extend those, don't rebuild.

## Next: Phase B — Generic OpenRAL on SRB (not started)

Per execution_plan.md §18: connect OpenRAL to `_ground_manipulation`/
`lunar_bot`, execute simple capability calls through the full reasoner/
rSkill/safety/ROS path, collect traces. **No `space_runtime`/`space_context`
code yet** — mechanisms follow observed failures (§21.6–7), not the reverse.

First concrete steps (see `todo.md`):
1. Find or wrap an rSkill that can actually drive `lunar_bot` through the
   topics found in A3 (likely a `ros_action`/`ros_service` wrapper, not a new
   rSkill).
2. Define Mission A as a plain instruction.
3. Run generic OpenRAL against it, save traces, document real failure modes.

## Environment reference (needed for every future SRB launch on this host)

```bash
env -u CONDA_PREFIX -u CONDA_EXE -u CONDA_PYTHON_EXE -u CONDA_DEFAULT_ENV \
    -u CONDA_SHLVL -u CONDA_PROMPT_MODIFIER -u PYTHONPATH \
    ISAAC_SIM_PATH="$HOME/Programs/isaac-sim" \
    PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniconda3 | paste -sd:)" \
    srb agent <zero|rand|ros> --env _ground_manipulation env.robot=lunar_bot \
    --headless --interface ros
```

OpenRAL side needs the opposite: Humble sourced (`PYTHONPATH` populated), conda
stripped for any C++ build. Full reasoning in `docs/openral_py310_patch.md`
and `docs/srb_integration_notes.md` §2.

## Watch out

- **Never `pkill -f` on this host** — it killed another agent's unrelated
  processes once this session (see `docs/research_findings.md` F10). Always
  resolve exact PIDs via `ps`/`pgrep -a -f` first, including the reparented
  kit-python child (killing the wrapper alone does not reliably take it
  down).
- `space_robotics_bench/` stays untouched — read/run only, ever.
- `OPENRAL_REASONER_MODEL` is unset; curated ids are `claude-opus-4-8`,
  `cosmos3-edge`, `gpt-5.5`, `gpt-5.6`. Configure when Phase B needs it.
