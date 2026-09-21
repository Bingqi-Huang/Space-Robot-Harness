# TODO

Order: `execution_plan` §21 -- the proposed method before the external baselines. Sequence in force (user): Mission B reliable,
Mission A, then baselines / freeze / experiments. One graph per GPU. Experiments record video (`D0_VIDEO`).

## Now (2026-09-22)

- [ ] **Mission B on the corrected arm (F98).** gt2: scripted pick -> carry -> dock -> place, no model. If `place` holds the ORU through
      `over`/`lower` and the evaluator says delivered, record a full Mission B from scratch (`launch_full_pair.sh <tag> -`).
- [ ] **Mission A on the corrected arm.** mc6 is running (recorded). mc4/mc5 succeeded on the soft arm; mc5 has video and a complete bag.
- [ ] Compose both videos (panel + mini-map), x264 1280 wide crf 29, send.
- [ ] Servo gains, ramps and margins were tuned against the soft arm (F95/F96/F98): re-check a stall or a dip only if a run shows one.
      Do not retune preemptively.

## Design items not yet built

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, the claim ledger (a place that failed while the item sits on the shelf, gc3).
- [ ] Dock error band from the localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class; the press/place `interface` schema already agrees.
- [ ] G5 held-out situations; Mission A's ready/stand deadlock (F62 section 3); baselines; the freeze; the campaign.

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the posture pull's 0.05/s
(chosen to be slow against the arm's lag, not measured on the corrected arm).
