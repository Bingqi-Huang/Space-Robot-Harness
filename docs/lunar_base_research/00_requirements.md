# Scene requirements derived from research_content.md / execution_plan.md

Source-of-truth sections: research_content §3.1–3.4, §4.3, §4.8, §5.2–5.6;
execution_plan §6.3–6.5, §7.0, §10, §13.2–13.3, §18 Phase C/D, §21.

## R1. The scene is the shared stage for three methods
- PLEXIL, EUROPA→PLEXIL, Ours run the same scene/seed/capabilities (§5.3 rules 1–3).
- Every covered and held-out situation must be solvable with the *same closed capability set*
  (§3.3, closed-capability validator §13.2). So manipulable props must fit LunarBot's real
  envelope (RM-75 610 mm reach, 5 kg payload, EG2-4C2 gripper) — no case may need a new controller.
- Deterministic simulator truth must exist for every effect the evaluator/verifier checks
  (§4.10, §10.4): object poses, articulation joint states (door/latch/valve/switch), contact/seat state.

## R2. Mission A — infrastructure inspection & maintenance (§5.4, exec §6.4)
Needs:
- a navigable service site, not spawn-next-to-target (real approach, obstacles, corridors);
- **multiple visually distinguishable infrastructure components** of the same class so
  "which one is faulty" requires observation (e.g. several power/comm units along a row);
- **a semantic fault state observable only by looking** (§3.4.2, §4.3): e.g. an open/ajar
  access panel, a disconnected cable/plug, a dust-covered sensor/radiator, a tripped
  indicator, a displaced module — visible in camera, not a hidden predicate;
- one or more general-purpose physical operations that restore it (close/latch a panel,
  reseat a module/connector, swap a replaceable unit, clear an obstruction);
- covered examples (baseline authors see them): known fault + nominal restore; a manipulation
  retry branch; a known route obstruction with an encoded alternate route;
- held-out categories (hidden until freeze): (a) access blocked by a movable object;
  (b) observed state inconsistent with the expected fault template → needs closer inspection;
  (c) preferred capability/route unavailable → substitute composition. ≥2 must be substantive.

## R3. Mission B — logistics & servicing (§5.4, exec §6.5)
Needs, compositionally distinct from A:
- a storage/depot area (lander cargo, racks, containers) holding several candidate items
  (tools / spare units / sample containers) — item identification by observation;
- retrieval → transport over real distance → delivery/placement/service at a second location
  (e.g. insert spare unit into a receptacle, deliver tool to a work station, stow samples);
- ≥1 covered and ≥1 held-out condition under the same closed-capability rule.

## R4. Space-native context hooks (only if exercised — exec §7.0, Phase D)
The scene should make at most 1–2 operational variables *physically meaningful*, e.g.
- a power element (solar array / charging dock) whose state gates activity or recharge;
- a comm element (antenna / relay terminal) whose availability changes remote-reasoner access.
They are context facts, not rules; do not build a digital twin.

## R5. Visual credibility (user requirement 2026-09-15, Acta Astronautica figures)
- recognizable near-term lunar surface base: habitat/logistics modules, landers, solar
  arrays, comm mast, power/distribution units, cargo, lighting, regolith terrain, rocks, craters;
- NASA/ESA-plausible engineering look, correct scale, low-sun-angle lighting typical of
  south-pole sites; used in paper figures (§6.6 Fig. 5 mission trace, Table 3 scenarios).

## R6. Physical sanity (lessons F18/F40 + rejected v2)
- every static structure snapped to actual terrain height or sits on a flattened/built pad;
- mounts make engineering sense (connectors/latches/receptacles, not a panel on a pillar top);
- manipulables within reach/payload; spawn poses collision-free; settle checked per-tick;
- verified by multi-angle visual inspection + per-tick pose traces before any "done" claim.

## R7. Perception/nav realism
- camera sees semantic fault cues at the approach distance used by inspect capabilities;
- lidar (RayCaster) must include new structure meshes, otherwise Nav2 can't avoid them;
- corridors wide enough for 4WIS base + Nav2 inflation.

## R8. Repro/perturbation control
- scenario manifest per instance (seed, covered/held-out, evaluator-only success, perturbations)
  → scene must expose parameterized switches (which unit faulty, which fault type, obstruction
  on/off, route blocked, capability unavailable) without changing asset topology per variant.
