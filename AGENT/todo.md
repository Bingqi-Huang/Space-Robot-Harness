# TODO

Goal: the Acta Astronautica paper. `docs/heldout_design.md` is the plan (§10 work order, §14 instances).
`docs/preregistration.md` fixes metrics, failure taxonomy, exclusion and statistics.

## Done (see docs/research_findings.md)

- F108-F139: site, scenarios, protocol, evaluator, baseline lock, run farm, steps 7-10, Qwen3.8-Max, prompts/ours,
  request kinds, scan_label built (F131), rows->tables, video/swimlane, retry budget, freeze-1.
- **Experiment I** (F140; rerun on the fixed shared layer = exp1b, F141/F142; tag `exp1b`): Ours covered 7/7,
  held-out 18/18, 0 re-authoring; PLEXIL / EUROPA covered 7/7, held-out 0/6 each. `artifacts/eval/exp1b/`,
  `artifacts/figures/exp1b/`. F143: PLEXIL retry budget N = 1/2/3/5 never changes the outcome; drop = a fall.
- **Experiment II** (F144-F147; tags `exp2-*`): all three extensions passed G3 on the first validation run (active
  54.5 / 46.3 / 53.4 min; 4.7 / 10.8 / 20.8 not waiting on the simulation); held-out before 0/6, after Ours 6/6,
  PLEXIL 2/2, EUROPA 2/2; fixes F145 (scan view), F147 (on-support fact, Ours' step budget), only decided runs rerun.
  `experiments/exp2/`, `artifacts/runs/exp2/`, `artifacts/eval/exp2/tables.md` (`python3 experiments/exp2/tables.py`).

## Next work

- [ ] §5.7 ablations, method B (user 2026-09-28): fault injection + offline counterfactual replay on recorded runs
      (from the `exp1b` system), live only where offline shows a difference. Variants (research_content §5.7):
      without authoritative facts, without internal effect verification, without the guard, without dynamic
      context reconstruction. F130 has the offline reading of what each would change.
- [ ] Re-authoring cost per held-out case for both baselines (heldout_design §8, authoring_spec "After the freeze";
      feeds H2): developer time and new plan / domain nodes to cover each of the six Exp I held-out cases.
- [ ] Swimlane label overlap (press/press, place/stow) before the paper figure.
- [ ] Paper results section from `artifacts/eval/exp1b/{tables,failures}.md` and `artifacts/eval/exp2/tables.md`;
      limitations: one engineer per method (Claude sessions in Exp II), category-level L2-B precedent, H2 held-out
      precedent off-ISS, AMCL bias, fixed 300 s ground decision, Ours' post-mission inspection tours, Ours' H1 search
      less systematic than PLEXIL's sweep, the held-out categories were in heldout_design §6.
- Not now (user): Exp II "plan B" (the user as engineer with Claude as assistant); push (waits for the user).

## Clean-up (user 2026-09-26: keep for now)

- `artifacts/runs/step10_final`, `.worktree/prefreeze` + branch `feat/prefreeze-infra`.

## Known limits

- Localization ~5 cm at bess_stand (map precision), 0.3-1.3 m transients round the habitat row's east end (F141).
- A carried item swings +-7 cm while lowered; the touchdown phase decides the set-down point (F141).
- The scan's plates are read only from a view the arm can take at a docked stand; the battery module's plates never
  read (domed lid) -- the scan then says something stands there (F147).

## Rules (user)

- Simplified Chinese replies, plain words, conclusion first. Decide defaults yourself; ask only design questions; when
  the user only asks, only answer. Plan changes, merges, pushes and experiments need the user's explicit go.
- Only fix the current blocker; offline check first, one decisive live test; rerun only the affected run, from a
  snapshot where possible; never rerun what already passed.
- Fixes found during a campaign are applied for all methods, recorded in findings and folded into that experiment's
  results (F141/F142, F145, F147) -- not reported as a separate round (user 2026-09-29).
- Ours: generic changes only, three tests (names no situation/place/serial; holds for every task; traceable), recorded
  in findings. Baselines locked: not strengthened, not patched beyond the lock's change control.
- No defensive code, no hash checks, minimal pytest. Contacts from truth + layout; never decide or navigate on truth.
- One simulation per GPU; kill only own containers; long runs watched by a Monitor, no polling. No freeze ceremony.
