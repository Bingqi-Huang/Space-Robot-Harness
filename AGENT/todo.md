# TODO

Order: `execution_plan` §21 -- the proposed method before the external baselines. Sequence in force (user): Mission B reliable,
Mission A, then baselines / freeze / experiments. **Both done (2026-09-22) -- see handoff.md.** One graph per GPU. Experiments
record video (`D0_VIDEO`).

## Now

- [ ] **Baselines / freeze / experiments** -- the next item in the user's stated order, not yet started. `execution_plan` §21 has
      the shape of it; nothing here has been scoped yet.
- [ ] Servo gains, ramps and margins were tuned against the soft arm (F95/F96/F98): re-check a stall or a dip only if a run shows
      one. Do not retune preemptively.
- [ ] Killing a check script mid-navigate leaves Nav2's own goal running: cancel it (`/navigate_to_pose/_action/cancel_goal`,
      all-zero goal_id) before any restore, or the robot fights its own snapshot restore for as long as it takes to notice.

## Design items not yet built

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, the claim ledger (a place that failed while the item sits on the shelf, gc3).
- [ ] Dock error band from the localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class; the press/place `interface` schema already agrees.
- [ ] `lower`'s stall is read as contact without checking `stopped_above_expected_m` against a bound first: a joint-limited stall
      during lower would currently look like contact too. Not yet observed to happen -- watch for it, do not pre-empt it.
- [ ] G5 held-out situations; Mission A's ready/stand deadlock (F62 section 3); baselines; the freeze; the campaign.

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the posture pull's 0.05/s.
