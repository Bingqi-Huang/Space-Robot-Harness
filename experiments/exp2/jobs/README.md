# Experiment II validation runs (docs/exp2/extension_spec.md §5)

One line per jobs file: the method on the visible case V1. Each attempt gets its own run root (never reuse one):

    tmux new-session -d -s <name> "experiments/launch/lunar_base_d0/farm_queue.sh experiments/exp2/jobs/<method>_v1.txt artifacts/runs/exp2_val/<method>_<n> '<gpu>'"

The run is `artifacts/runs/exp2_val/<method>_<n>/<line name>/`; it is over when its `check.log` has `CHECK_EXIT`
(`RESULT` lines carry the evaluator's verdict). Then:

    python3 experiments/exp2/g3_validate.py --method <ours|plexil|europa_plexil> artifacts/runs/exp2_val/<method>_<n>/<line name>

Validation runs are development runs of the extension, never scored. GPUs 3-5 are the validation runs'.
