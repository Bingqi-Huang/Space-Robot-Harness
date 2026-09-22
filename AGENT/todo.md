# TODO

Order: `execution_plan` §21 -- the proposed method before the external baselines. Sequence in force (user): Mission B reliable,
Mission A, then baselines / freeze / experiments. One graph per GPU. Experiments record video (`D0_VIDEO`).

## Now (2026-09-22)

- [x] **Mission B pick+place, on the corrected arm, verified.** gt2c8: scripted pick -> navigate -> dock -> place, no model, no
      video, from the pre-pick snapshot. `delivered: true`. Found and fixed along the way (F98-F100): the arm's drive gains were
      applied per degree (57x soft); `over`/`retreat` had no escape from a joint pinned at its own stop (both now share one, pure
      joint-space, no IK); `plan_to` never told the planner about a carried item; retreat's distance cleared the evaluator's
      "not held" check only in the nominal case, not the worst case with servo tolerance. Full run with video next.
- [ ] **Full Mission B from scratch, with video.** `launch_full_pair.sh <tag> -`.
- [x] **Mission A on the corrected arm.** mc6, evaluator success, video sent (trimmed to the active 8:20, the rest was the
      reasoner sitting still on repeated lamp-verification observes).
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
