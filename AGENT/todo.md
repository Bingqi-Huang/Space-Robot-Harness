# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.
**Sequence in force (user): Mission B done → `press` live → Mission A.** One simulation at a time.

## Done — Mission B end to end (ga8, F87)

- [x] `RESULT {"oru_on": "pdu_1_shelf/shelf", "delivered": true, "success": true}`, `CHECK_EXIT 0`.
      pick 179.52 (jaw 0.170, first attempt) → carry (`item_still_held`, jaw 0.171) → place 332.92
      (`item_placed`, jaw 0.82) → stow → dock, map error 0.019 m.
- [x] The carry: `hold = True` for every action term. A `cmd_vel` rebuilt the whole action vector through the
      teleoperation mapping and only the Bool gripper was protected, so the first cmd_vel of every drive zeroed
      the arm's targets (F81). This was the cause of six lost payloads.
- [x] The grasp seats at the middle of the pads, from the gripper's own meshes, with a tolerance that is a
      different measurement from the target (F81).
- [x] `held_item` returns the boundary's record of the pick it dispatched beside the camera's answer (F82).
- [x] The lifting handle is captive: a collar below the slot, sized to the gripper's finger height and its
      reach across the jaws (F83/F84). Bars shallower than the neck so the slot reads from any angle (F86).
- [x] `place` receives the support's surveyed outward normal and steps along it until its own collision check
      passes, capped at half the item's depth (F85).
- [x] Props are boxed where they are, not where their height would put them; the shelf takes the payload
      (0.6 → 0.75 m, back clearance 58 → 158 mm); all computed offline (F86).
- [x] An orphaned contact-scene freeze is reclaimed instead of refusing every later operation.

## Now — close what ga8 did not exercise

- [ ] **A carried pivot.** ga8's route never turned in place with the load, so the collar has not met the 23.7 deg
      roll that lost ga4. Drive a deliberate heading change while carrying and measure the roll about the approach
      axis (the instrument is in F83's analysis; `see_drop.py` + the TF decomposition).
- [ ] **`CARRY_SUSTAINED_YAW_RAD_S = 0.15`** is a separation read off one failure and two successes. With the
      collar in place, measure whether it is needed at all; remove it or give it a second measurement.
- [ ] **`press` with the PDU panel's corrected box** (0..0.52 → 0..1.12, its real extent). That is a new obstacle
      in front of Mission A's press, which has not run since.
- [ ] Mission B covered from the start, twice, for a repeatable result rather than one run.

## Then

- [ ] G5 held-out situations: destination_occupied, spare_swapped, cover_obstruction, status_mismatch, route_block.
- [ ] `press` live (never pressed a button), then Mission A's ready/stand deadlock (F62 §3).
- [ ] Baselines (PLEXIL, EUROPA→PLEXIL) on the frozen boundary, then the experiment campaign.

## Numbers still owed a measured source

- `bring_in` sag margin 5 cm (`held_drop_m`); posture margin 0.10 rad; `CARRY_SUSTAINED_YAW_RAD_S`.
- The IK branch jump (1.2 rad), the held pivot (16 deg), the seat depth and the slot both have one.
