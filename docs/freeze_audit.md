# Freeze audit checklist

execution_plan.md §9.3 "forbidden mission logic" + §13.1 step 6 ("freeze all
method-specific artifacts by recording and tagging their git commits"). Run this
checklist by hand against `openral_ext.run_manifest.freeze.list_method_artifacts`'s
output for each method, before `plan_freeze(..., dry_run=False)` is ever called.
No tag exists yet -- this file records what to check, not a result.

## Per artifact, before tagging

- [ ] **No scenario-specific solution hint.** For Ours: `prompts/ours/` (every text the reasoner reads), `space_runtime/context.py`,
      `configs/space_runtime.yaml` (guard rules), `space_runtime/guard.py`,
      `space_runtime/verification.py`, and `openral_ext/capability_server/contracts.yaml`
      contain no string naming a held-out scenario's object, PDU id, or fix sequence
      (§13.1: "a prompt/playbook hint, guard rule, verifier rule, or capability hint
      that encodes the solution of a particular situation is forbidden").
- [ ] **No held-out situation drove the change.** For every diff touching a listed
      artifact since the last freeze (or since project start, for the first freeze):
      was it written or reviewed after an Ours run on a held-out case exposed a
      failure there? If yes, it is a generic fix (capability description, shared
      perception, context-builder information, reasoning-loop mechanism) or it does
      not belong in this freeze (§13.1: "Failures are answered only with
      mission-generic changes").
- [ ] **PLEXIL/EUROPA parity.** A PLEXIL plan branch or EUROPA domain element added
      after a held-out situation was seen makes that situation `covered` for that
      baseline, not `held_out` -- reclassify the scenario manifest's `coverage` field
      accordingly, do not leave it misreported as held-out.
- [ ] **Artifact set matches `METHOD_ARTIFACTS`.** `list_method_artifacts(method,
      repo_root)` returns every file that should be frozen and nothing extra; if a
      new file was added to the method's mechanism, add it to
      `openral_ext/run_manifest/freeze.py`'s `METHOD_ARTIFACTS` first.
- [ ] **Working tree clean.** `plan_freeze(...).dirty_artifacts` is empty -- an
      uncommitted change under a listed artifact means the tag would not describe
      what actually ran.

## After tagging (once `dry_run=False` is actually used)

- [ ] Tag name and commit recorded in the run manifest's frozen-artifact-commit
      fields for every subsequent campaign run.
- [ ] `docs/freeze_audit.md` (this file) updated with the date, method, and tag name
      under "History" below -- do not silently re-tag without a note here.
- [ ] Any post-freeze infrastructure fix is applied identically to all three methods
      and the affected campaign is rerun from the start (§13.1); a method-specific
      change that adds missing task knowledge is NOT an infrastructure fix -- it
      invalidates the freeze and counts as re-authoring (§13.1, §14.2
      `ground_reauthoring_required`).

## History

(none yet -- no freeze has been run)
