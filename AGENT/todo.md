# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
**Sequence in force (user): Mission B reliable → `press` live → Mission A → baselines/freeze/experiments.**
One simulation at a time. Experiments from here on record video (`D0_VIDEO`).

## Blocking -- `pick` was rebuilt on 2026-09-21 and has not run

gb2 lost `pick` three times with the handle in plain view: the candidate search filtered measured dimensions
through eleven absolute thresholds, took one frame, and returned an empty list (F91). The user's ruling: gates on
absolute numbers are wrong; the handle is a declared affordance, so how to grasp it is declared and vision only
has to say where it is.

- [ ] **Run Mission B with the rebuilt pick.** `find` takes one view, the VLM names the item's region, the
      catalogue's interface shape is fitted to the depth (`openral_rskill/interface_fit.py`), the tool servos in
      re-fitting every frame in the declared orientation (approach along the support normal, jaws across the
      neck). Offline on gb2's two failed frames: slot centre to 0.8-1.6 mm, agreement 0.89-0.98, ~30 ms a frame.
      Unproven live: the fit under the fingers' occlusion, the servo on a moving camera, the agreement floor (0.5).
- [ ] Then three clean runs of Mission B from the start, with video, before anything else.

## Changed but never run — nothing below has a successful run behind it

ga8 is the only end-to-end success (F87) and it predates all of this.

- [ ] The handle: slot 28 mm, bars 12 mm deep (F86). Only the offline replay on ga8's depth.
- [ ] The shelf 0.6 → 0.75 m, prop boxes at their real height (F86). Only the offline geometry.
- [ ] `place` steps along the support's outward normal when its own collision check refuses (F85). Never triggered.
- [ ] The arm holds its posture from step 0 (`hold_action`), and stow is level and rearward (F89). Never run.
- [ ] Non-model queries resend after 4 s instead of 180 (F90) — **this is the 3-minute stall at the start of
      every run**. Never run.
- [ ] An orphaned contact-scene freeze is reclaimed instead of refusing everything after it. Never triggered.
- [ ] The video panel rewrite (`c5ce88d`). Rendered on gb2's frames only.

## Then

- [ ] A carried pivot: ga8's route never turned in place with the load, so the collar has not met the 23.7 deg
      roll that lost ga4 (F83/F84).
- [ ] `press` against the PDU panel's corrected box (0..0.52 → 0..1.12, its real extent) — a new obstacle in
      front of Mission A's press, which has not run since.
- [ ] G5 held-out situations; Mission A's ready/stand deadlock (F62 §3); baselines; the freeze; the campaign.

## Numbers still owed a measured source

`bring_in`'s 5 cm sag margin (`held_drop_m`); the 0.10 rad posture margin; the fit's agreement floor of one half. Everything else in the carry and the
grasp now has one. `CARRY_SUSTAINED_YAW_RAD_S` was removed rather than left undeclared.
