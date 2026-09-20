# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
**Sequence in force (user): Mission B reliable → `press` live → Mission A → baselines/freeze/experiments.**
One simulation at a time. Experiments from here on record video (`D0_VIDEO`).

## Blocking — nothing has run since ga8; the next thing is a run

gb2's three `pick` failures are answered (F91) and the answer is proven offline on the run's own data, not live.
The pick, the carry, the place, the stow and the video panel all now stand on offline evidence alone.

- [ ] **Three clean runs of Mission B from the start, with video.** Watch for, in this order: the 3-minute stall at
      the start (F90) is gone; `find` takes more than one view and says which; `pick` succeeds without the model
      having to re-dock; the carry survives a turn with the load (F83/F84, never met); `place` steps along the
      normal if it has to (F85, never triggered).

## Changed but never run — nothing below has a successful run behind it

ga8 is the only end-to-end success (F87) and it predates all of this.

- [ ] `find` takes the views the arm can reach instead of one (F91), and the declared contact length is no longer
      re-certified from the image. Only the offline replay on gb2's two failed views: 0 candidates → 5, the neck
      at 12.9 mm.
- [ ] `work_stands` answers each promise at the end of the docking band where it is hardest (F91). Computed on the
      arm's model, not asked of the live boundary — check the answer is not empty on the first run.
- [ ] The handle: slot 28 mm, bars 12 mm deep (F86). Only the offline replay on ga8's depth.
- [ ] The shelf 0.6 → 0.75 m, prop boxes at their real height (F86). Only the offline geometry.
- [ ] `place` steps along the support's outward normal when its own collision check refuses (F85). Never triggered.
- [ ] The arm holds its posture from step 0 (`hold_action`), and stow is level and rearward (F89). Never run.
- [ ] Non-model queries resend after 4 s instead of 180 (F90) — **the 3-minute stall at the start of every run.**
- [ ] An orphaned contact-scene freeze is reclaimed instead of refusing everything after it. Never triggered.
- [ ] The video panel: four things, at four sizes, in one accent and two verdicts. Rendered on gb2's frames only.

## Then

- [ ] A carried pivot: ga8's route never turned in place with the load, so the collar has not met the 23.7 deg
      roll that lost ga4 (F83/F84).
- [ ] `press` against the PDU panel's corrected box (0..0.52 → 0..1.12, its real extent) — a new obstacle in
      front of Mission A's press, which has not run since.
- [ ] G5 held-out situations; Mission A's ready/stand deadlock (F62 §3); baselines; the freeze; the campaign.

## Numbers still owed a measured source

`bring_in`'s 5 cm sag margin (`held_drop_m`); the 0.10 rad posture margin; `max_views` = 6, which is a deadline on
the search and not a measurement. Everything else in the carry and the grasp now has one.
