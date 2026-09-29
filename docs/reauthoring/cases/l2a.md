# Case L2-A: the heat-rejection shutter left drawn (`heldout_radiator_cover`)

**What the robot reported** (your baseline's Experiment I runs `plexil_l2a_pdu1`, `plexil_l2a_bess` /
`europa_l2a_pdu1`, `europa_l2a_bess`): the faulted unit was reset, read closed, and tripped again with trip cause
**OVERTEMP**; after the retry budget the baseline asked mission control and held.

**Diagnosis (given):** the faulted unit's heat-rejection shutter -- a PDU's radiator shutter, the BESS HVAC condenser
shutter -- was left drawn closed. With it closed, a closed breaker overheats and trips OVERTEMP about 30 s after a reset.
The shutter opens when its push button is pressed; each is a surveyed press point in the site survey:
`pdu_1_radiator/cover_button`, `pdu_2_radiator/cover_button`, `pdu_3_radiator/cover_button`, `bess_hvac/cover_button`
(the unit's `cover` in the survey's `units`; the ISRU plant has none). Once the shutter is open, a reset holds. The unit's
own telemetry (`power_status`: breaker, trip_cause) is how the robot sees OVERTEMP.

**Goal (the mission is unchanged):** every serviced unit restored (the faulted one's breaker closed and staying closed),
the arm stowed, the rover on its dock.

**Instances to validate (both):**
- PLEXIL: `plexil_l2a_pdu1 D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_a_check.py D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml D0_SCENARIO=heldout_radiator_cover D0_ENV='env.faulted_unit=pdu_1'`
  and the same with `plexil_l2a_bess ... D0_ENV='env.faulted_unit=bess'`.
- EUROPA -> PLEXIL: the same two lines with `europa_l2a_pdu1` / `europa_l2a_bess` and `D0_CHECK=d0_europa_mission_a_check.py`.
