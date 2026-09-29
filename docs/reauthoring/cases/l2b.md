# Case L2-B: the delivery stand is occupied (`heldout_destination_occupied`)

**What the robot reported** (Experiment I runs `plexil_l2b_habitat` / `europa_l2b_habitat`): delivering the
consumables container CNS-0301 from `landing_stand/slot_0` to `habitat_stand/slot_0`, the place failed three times (the
set-down pushed against something); the baseline asked mission control and held.

**Diagnosis (given):** the habitat logistics stand `habitat_stand/slot_0` already holds the outbound return container
RTN-0007 (the manifest lists it there: outbound return, awaiting stowage; the catalogue describes it and its handle; its
pick point is `return_container/pick`). The stand takes one item. The occupier must first be moved to another free
support -- the return stand `return_stand/slot_0` is where outbound returns go -- and then the delivery made. The robot
can see the occupier (a camera observation, or the place failing against it) and read the manifest.

**Goal (the mission is unchanged, plus what the stand requires):** CNS-0301 on `habitat_stand/slot_0`, RTN-0007 resting
on some other support (not dropped, not held), the arm stowed, the rover on its dock.

**Instance to validate:**
- PLEXIL: `plexil_l2b_habitat D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_b_check.py D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml D0_SCENARIO=heldout_destination_occupied D0_ENV='env.cargo=consumables_container env.destination=habitat'`
- EUROPA -> PLEXIL: the same with `europa_l2b_habitat` and `D0_CHECK=d0_europa_mission_b_check.py`.
