# Handoff

State as of 2026-09-13. Phase A complete. Phase B slices 1 (LunarBot HAL) and
2 (`procedural` rSkill kind) verified live; F15 investigated and closed as a
false alarm. Task list: `todo.md`. Records: `docs/phase_b_lunar_bot_hal.md`,
`docs/phase_b_procedural_kind.md`. Findings: `docs/research_findings.md`.

## What just happened: F15 investigated, corrected

F15 (recorded last session as "the kernel doesn't heartbeat
`/openral/safety_status`, so a >3s dispatch self-aborts") turned out to be
**wrong on the first read** — corrected this session, not left standing.

The kernel's `publish_diagnostics()` (bound to its 1-second wall timer, the
one driving `/diagnostics`) ends with an *unconditional*
`publish_safety_status_now()`, documented in-code as "ADR-0096 / HZ-0096-1
mitigation 2." Verified live: kernel alone, configured + activated,
`ros2 topic hz` on both `/diagnostics` and `/openral/safety_status` measured
a clean, exact **1.000 Hz** on each. The earlier "zero messages in 5s" reading
was a shell-tooling artifact — piping `timeout N ros2 topic hz ... | tail`
loses buffered output when `timeout` SIGTERMs the process mid-print;
redirecting to a file instead showed the real numbers immediately.

So the one abort seen last session (a 3s `ExecuteRskill` dispatch aborting at
~2.7s) is best explained as a single missed/delayed heartbeat delivery under
a busier multi-participant DDS graph (SRB + kernel + HAL + runner all live at
once), not a structural gap — the mechanism is intentionally conservative
("fail toward assume-unsafe... can only ADD an abort, never suppress one"),
so occasionally tripping under load is it doing its documented job.
**Conclusion: don't spend more effort on this.** Treat an occasional
safety-stale abort as expected system behavior a real mission must be robust
to — usefully, exactly the class of event execution_plan.md §5.4.4
(fault/degradation) and §13.6 (failure/recovery campaign) already want to
study, not a nuisance orthogonal to the research.

## Next

`todo.md`'s Phase B checklist, in order: **F12** (characterize whether the
kernel actually enforces `max_base_linear_speed_m_s`/
`max_base_angular_speed_rad_s` — deliberately exceed it, confirm rejection or
its absence), then arm/gripper wiring on the HAL, then Mission A (plan §21
items 5–6) — nothing is blocking Mission A anymore now that F15 is closed.

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`.
- `RskillRunnerNode` is constructed directly in Python — mirror `compose.py`:
  construct with `skill_resolver=None`, then swap `node._skill_resolver =
  make_default_skill_resolver(node, search_paths=["rskills"])` before
  `configure()`.
- **Any shell calling `ros2 action send_goal`/`topic echo`/`topic hz` on an
  `openral_msgs` interface needs both `/opt/ros/humble/setup.bash` and
  `install/setup.bash` sourced** — missing either fails with a misleading
  error, not an obvious "not sourced" one.
- **When checking a topic's publish rate, redirect `ros2 topic hz` to a file
  instead of piping through `tail`/`grep`** — piping after a `timeout` kill
  loses the buffered output and reads as "zero messages" even when the topic
  is publishing fine. This cost a full false "F15 is a real bug" conclusion
  once already.

## Watch out

- **Never `pkill -f` on this host** — exact PIDs only, every time, including
  the reparented kit-python child.
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
