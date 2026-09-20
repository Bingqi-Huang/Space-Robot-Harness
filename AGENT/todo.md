# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
**Sequence in force (user): Mission B reliable → `press` live → Mission A → baselines/freeze/experiments.**
One simulation at a time. Experiments from here on record video (`D0_VIDEO`).

## Blocking — `pick` is not reliable, and this is the only thing that matters now

`pick` succeeded first try in ga8 and failed three times in gb2 with the same code and the same target. It is not
a perception problem and not a reach problem: it is a hard gate on a measurement that scales with distance.

- [ ] **The candidate search rejects the part for being short in the image.**
      `grasp_perception.find_candidates` drops any candidate whose *measured* length along the part is under
      `geom.pad_height_m` (14 mm). The ORU's slot is 28 mm and the catalogue says so — `held_item.neck_height_m`
      is already in the pick skill's goal — but the image has to prove it again, and at 1.035 m the neck reads
      **11.6 mm**. gb2 attempt 3: the search found the neck at exactly 12 mm wide with clear air on both sides
      and threw it away. Same handle at 1.08 m in ga8: 22.4 mm, accepted.
      The width already takes the honest route (`contact_width_m` declared, image confirms). The length does not.
      **Do the same for length: pass the declared contact length and let the image locate the part rather than
      re-certify what the catalogue states.** Then check the other two failures go with it.
- [ ] gb2's other two: at 1.08 m the approach stalled 2.6 cm short (`work_stands` now checks reach at the seat,
      `9bbb981`, unverified); at 0.93 m the gripper's own body covered the slot in its own camera.
- [ ] After the gate: three clean runs of Mission B from the start, with video, before anything else.

## Changed but never run — nothing below has a successful run behind it

ga8 is the only end-to-end success (F87) and it predates all of this.

- [ ] The handle: slot 28 mm, bars 12 mm deep (F86). Only the offline replay on ga8's depth.
- [ ] The shelf 0.6 → 0.75 m, prop boxes at their real height (F86). Only the offline geometry.
- [ ] `place` steps along the support's outward normal when its own collision check refuses (F85). Never triggered.
- [ ] The arm holds its posture from step 0 (`hold_action`), and stow is level and rearward (F89). Never run.
- [ ] Non-model queries resend after 4 s instead of 180 (F90) — **this is the 3-minute stall at the start of
      every run**. Never run.
- [ ] An orphaned contact-scene freeze is reclaimed instead of refusing everything after it. Never triggered.
- [ ] The video panel rewrite (`747e68c`). Never rendered.

## Then

- [ ] A carried pivot: ga8's route never turned in place with the load, so the collar has not met the 23.7 deg
      roll that lost ga4 (F83/F84).
- [ ] `press` against the PDU panel's corrected box (0..0.52 → 0..1.12, its real extent) — a new obstacle in
      front of Mission A's press, which has not run since.
- [ ] G5 held-out situations; Mission A's ready/stand deadlock (F62 §3); baselines; the freeze; the campaign.

## Numbers still owed a measured source

`bring_in`'s 5 cm sag margin (`held_drop_m`); the 0.10 rad posture margin. Everything else in the carry and the
grasp now has one. `CARRY_SUSTAINED_YAW_RAD_S` was removed rather than left undeclared.
