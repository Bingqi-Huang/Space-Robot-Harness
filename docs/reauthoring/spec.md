# Re-authoring cost of the Experiment I held-out cases (baselines)

`docs/heldout_design.md` §8 "Re-authoring cost" and `docs/baselines/authoring_spec.md` "After the freeze": in Experiment I
every held-out run of PLEXIL and EUROPA -> PLEXIL ended "detected -> escalated -> hold": the frozen plan or domain had no
continuation, and mission control's answer was "a new procedure is in work". This study measures that new procedure:
**the engineering time and the new plan / domain elements** a ground engineer needs to make the frozen baseline complete
one held-out case autonomously. (Ours solved every held-out case with no change; its cost is zero.) One engineer per
(baseline, case), each a fresh session, independent of the others, all from the Experiment I freeze.

## What you are given (and only this)

- Your case brief: `docs/reauthoring/cases/<case>.md` (main checkout, read-only) -- what mission control's engineers know
  once the escalation is diagnosed: the cause, the facts that matter, the goal. The diagnosis is given; you author the
  procedure.
- The frozen baseline in your checkout (tag `exp1b`): `baselines/plexil/` or `baselines/europa/`, its docs
  (`docs/baselines/plexil.md`, `docs/baselines/europa.md`), `docs/baselines/authoring_spec.md`, the shared capability
  contracts `openral_ext/capability_server/contracts.yaml`, the site survey / equipment catalogue / manifest the plans
  already use (`space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json`), the launch and check
  scripts under `experiments/launch/lunar_base_d0/`, and your baseline's own Experiment I run(s) of this case under
  `/mnt/SharedData/Research/Space_Robot_Harness/artifacts/runs/exp1b/<baseline>_<case run>/` (what the robot did and
  escalated).
- Not yours to open: any Ours record or run (`artifacts/runs/**/ours_*`, `prompts/`, `space_runtime/`), other cases'
  briefs, other engineers' branches or runs, `experiments/ablation/`, `docs/research_findings.md`. Design from the brief.

## What you may change

- Your baseline's own artifacts only: PLEXIL -- `baselines/plexil/` (plans, library nodes, interface config, offline
  tests) and, where a new call or result must be carried, `ros/plexil_capability_adapter` (it carries calls and state,
  no mission logic); EUROPA -> PLEXIL -- `baselines/europa/` (NDDL domain, initial state, host, bridge, config).
- `docs/baselines/authoring_spec.md` holds with one change: **tier 3 is lifted for this case** -- you may key a branch
  (PLEXIL) or model the relation (EUROPA) on this case's cause or situation, and compose existing capabilities for it,
  as the brief describes. Every fact you encode traces to the covered specification, the contracts, the survey /
  catalogue / manifest or your brief. Tier 1 (3 attempts per call) is unchanged. The covered procedure keeps working
  (do not remove or weaken it; an offline check is your choice).
- Not yours: skills, the capability boundary, SRB, the evaluator, the operator console, this spec, the validator. A
  defect there is shared infrastructure: stop the timer, note it, say so in your summary; it is fixed for every method.

## Timer and record

- Start: `python3 /mnt/SharedData/Research/Space_Robot_Harness/evaluation/engineering_worklog.py --log
  /mnt/SharedData/Research/Space_Robot_Harness/experiments/reauthoring/worklog/<baseline>_<case>.jsonl start
  --extension-id reauth_<case> --method <plexil|europa_plexil> --engineer <your session id>`. `stop --reason ...` for any
  pause (e.g. waiting for your GPU to be freed by someone else), `start` again to resume. Active time = reading, editing,
  building, offline checks, and waiting on your own validation runs.
- `note "..."` every failed validation run and every modelling/logic error you find (validation iterations, errors).
- **Cap: 3 hours active.** At the cap stop the timer, `note "cap reached"`, commit what exists; that case is reported as
  "not reached in 3 h".

## Validation (the timer stops at the first PASS)

1. Live run(s) of your baseline on **every instance of the case** (the case brief lists the jobs lines: your baseline's
   own Experiment I lines). Run them from your checkout on **your GPU only** (assigned in your task):
   `tmux new-session -d -s <name> "<your checkout>/experiments/launch/lunar_base_d0/farm_queue.sh <jobs file> <run root>
   '<gpu>'"`, run root `/mnt/SharedData/Research/Space_Robot_Harness/artifacts/runs/reauth/<baseline>_<case>/v<k>`.
   Before launching, `/mnt/SharedData/Research/Space_Robot_Harness/experiments/reauthoring/gpu_free.sh <gpu>` must print
   `free` (one simulation per GPU, also while a previous container tears down). Watch a run with a Monitor on its
   `check.log` / the queue's `queue.log` ("end" lines), never by polling; a Mission A/B baseline run takes ~15-40 min.
2. `python3 /mnt/SharedData/Research/Space_Robot_Harness/experiments/reauthoring/validate.py <run dir> [<run dir> ...]`
   (one run dir per instance): PASS when every instance succeeded by the external evaluator, nothing dropped, and no
   module removed from an energized unit without mission control's approval.
3. At the first PASS stop the timer. Commit your changes and the worklog on your branch (`reauth/<baseline>-<case>`);
   never merge, never push.

Offline checks of your own (plexiltest, `baselines/plexil/scripts/offline_check.py`, the EUROPA offline chain
`baselines/europa/run_offline_mission_{a,b}.sh`, a stand-in boundary) are your choice and count as work. Run farm
rules: only your own containers (`rf-<your run names>`), no `sudo`, no changes outside your checkout except your worklog.

## Your summary (return it when done)

Active time and the time waiting on your own runs; files changed (+/- lines); the semantic constructs you added (PLEXIL
nodes / branches / lookups / commands; NDDL classes, predicates, actions, compatibilities, host changes); validation
runs and their outcomes; modelling errors found; anything shared you hit.
