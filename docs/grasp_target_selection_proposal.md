# Choosing what to grasp: a proposal to replace candidate search with interface fitting

Date: 2026-09-20. Status: **proposal, nothing implemented, awaiting the user's decision.**
Prompted by the user's judgement on gb2: *"把绝对数字作为 gate 就是彻底错误的"* — using absolute numbers as
gates is fundamentally wrong. This document says why that is right, what the literature does instead, what was
measured on this repository's own data today, and what it would cost to change.

Related: `semantic_to_metric_manipulation_plan.md` (v4 principles), `manipulation_contracts_proposal.md` (r3,
which already loosened v4's ban on object models), `research_findings.md` F55-F91.

---

## 1. What the current scheme is, in one paragraph

`pick` puts the camera in front of the work, takes **one depth frame**, and runs a class-agnostic antipodal
detector (`grasp_perception.find_candidates`): scan the image at 12 angles, cut runs of similar depth, keep the
ones whose **measured** width, length, side clearance, depth step, axis obliquity and border distance all pass
**eleven absolute thresholds**; draw what survives as numbered marks; ask a vision-language model which mark is
the described part; servo the tool to that one 3-D point, re-associating it frame to frame by grayscale template
matching.

## 2. Four things wrong with it, in order of severity

**(a) Every gate is binary and its failure is silent.** The detector's output is a list or an empty list. When a
threshold rejects the part there is no number that says *how nearly* it passed, no second-best, nothing the agent
can weigh. gb2 attempt 3: the neck was measured at 12.9 mm across — correct to 0.9 mm — and discarded because its
*visible* length read 9.5 mm against a 14 mm floor. The operation reported "the view measured nothing the jaws
could close on". The part was in the middle of the picture.

**(b) The gates are on quantities that depend on where you look from, and are compared against constants that do
not.** The width the jaws close across is viewpoint-invariant only within a few degrees of the contact's own
normal; the visible length shortens with the cosine of the look and with whatever overhangs the part. Holding
both to fixed millimetre thresholds turns the viewing geometry into a hidden precondition — which is exactly what
the last three sessions have been paying for: the "level look" requirement, the stand search, the docking band.

**(c) The geometry is reasoned about at the tool while the measurement happens at the camera.** Measured from
gb2's own evidence: the view was taken at a tool pitch of 10 deg, and the handle's own vertical axis reads
`[-0.020, 0.872, 0.489]` in the camera frame, so **the optical axis was 29.3 deg below horizontal — 19.3 deg
below the tool axis it is bolted to.** The SRB mount agrees: `Link7/camera_wrist` is `rpy(0, -72, 90)`, 18 deg
off the link. So `work_stands`' `shallowest_look_deg_above_horizontal`, the "level look" that decided where the
rover parked three times in gb2, is the **tool's** elevation. A level look has never once been level.

**(d) It re-derives what the catalogue already states.** `interaction.json` declares the lifting interface
completely — `neck_thickness_m` 0.012, `neck_width_m` 0.030, `neck_height_m` 0.028, `head_width_m` 0.090,
`head_depth_m` 0.012, `collar_*`, `axis: X`, `standoff_m`. The perception uses **two** of those numbers, as
thresholds, and rediscovers the rest from one frame of depth noise.

## 3. What the literature does (two independent reviews, today)

### 3.1 Vision-language models and precise points

The consensus is unambiguous and it is not in our favour if we ask a VLM for millimetres:

- **No published work reports the pixel or millimetre error of a VLM-selected point.** Every pointing benchmark
  (PixMo-Points, Point-Bench/PointArena, Where2Place, RoboRefIt, RefSpatial) scores a binary "did the point land
  inside the object's segmentation mask". At 0.43 m and f=616 the neck's mask is 17 x 43 px; landing inside it
  proves nothing about the 3-8 px we need.
- **Part-level pointing is the documented weak spot.** Point-It-Out: strong models score below 0.5 on part
  localisation and below 0.4 on affordance. Our question — head, neck or collar of the same rigid handle — is
  precisely that class.
- **PIVOT** (iterative visual prompting, DeepMind) reports L2 errors of 0.17-0.21 of image width for in-view
  targets (≈70-90 mm here) and states that "performance decreases as the robot approaches the grasp".
- **Set-of-Mark's** effective granularity is the granularity at which marks stay visually distinguishable —
  20-50 px in practice. MOKA uses a 5x5 grid; SAGP uses 8 zones. Marks at 3-8 px spacing are not a thing.
- **The universal architecture is VLM-coarse + geometry-fine**, in every system that runs on real hardware: CoPa
  (VLM picks a part mask, GraspNet produces the pose), GraspMolmo (VLM *ranks* grasps that M2T2 generated),
  AffordGrasp (VLM gives a box, AnyGrasp samples in it), RoboPoint / Embodied-R1 (2-D point, then depth
  back-projection and a motion planner). SAGP states the division outright: VLMs "remain unreliable at predicting
  exact coordinates or dense part labels", so it gives them *zone-level categorical ratings* and leaves geometry
  to the planner.
- General-purpose hosted VLMs are not pointing models. GPT-4o scores 15.3% on RoboRefIt against RoboPoint's 49.8
  and Embodied-R1's 85.6; no DeepSeek model appears on any pointing leaderboard, and DeepSeek-VL2's own grounding
  reproducibility is an open issue. **Our VLM is being asked a question its family is measured to be bad at.**

**So: the current design's choice to make the VLM pick among marks rather than emit coordinates is right and
matches the field.** What is wrong is expecting the *candidates it chooses among* to be produced by threshold
tests, and expecting the chosen mark to be the millimetre-accurate target.

### 3.2 Six-DoF pose of a known object

- **The state of the art is not accurate enough for this grasp, and the benchmark cannot tell you so.** BOP's AR
  metric averages recall over 0.05d-0.5d of object diameter; for our 108 mm handle that is 5.4-54 mm, so our
  2-5 mm requirement sits at or below its tightest threshold. Joyce et al. (arXiv:2512.01856, Dec 2025) closed
  the loop to a simulated parallel gripper and measured, for RGB estimators with known CAD: median translation
  error 4-9 mm with 90th-percentile tails of 10-60 mm, and concluded that translation error drives grasp failure
  and that the parallel jaw "has become the limiting factor".
- **FoundationPose** (CVPR 2024) is the strongest general answer and the wrong tool here: NVIDIA non-commercial
  licence, ~7.5 GB VRAM, ~1.3 s per estimate on a 3090, needs an external 2-D detection, its released weights
  underperform its paper by the authors' own note, its Isaac ROS wrapper targets Jazzy while we are on Humble,
  and its stated failure case is "texture-less, severe occlusion, and limited edge cues" — a matte black handle
  against a black sky, i.e. our object exactly.
- **Point Pair Features** (Drost; `cv2.ppf_match_3d`) is documented to fail on precisely our shape class. MVTec's
  own technical note: surface-only matching "should not be applied on objects with reduced 3D information, such
  as flat objects", because the model "will be found in the background with high probability (as long as the
  background is flat)". **We reproduced this in ten minutes today** (§4).
- **What the literature recommends for a known, authored, plane-supported part** is the opposite of a general
  method: reduce the degrees of freedom using what you know, fit the analytic geometry, polish with ICP with the
  degenerate direction constrained, and read the residual as the confidence. This is standard industrial
  bin-picking practice.

## 4. What was measured today, on this repository's own data

On the two gb2 frames where `find_candidates` returned **zero candidates** — the frames that lost the mission.

**First, the negative result, which matters as much.** Fitting the four declared boxes with all six degrees of
freedom free converged to a pose lying the 90 mm bars flat against the stand's top surface: 2579 of 3575 covered
pixels agreeing to 3 mm at a mean 1.4 mm — an excellent fit to a completely wrong pose, and the exact failure
MVTec describes. A method that can be this confidently wrong must not be adopted without the constraint that
removes the ambiguity.

**The constraint is one the harness legitimately owns**: the interface stands upright on a surveyed support, so
its axis is that support's normal, which TF and the site survey both give. That leaves **four unknowns — x, y, z
and the yaw about that axis.** With it:

| gb2 view | camera look-down | current search | interface fit (coverage / mean residual) |
|---|---|---|---|
| attempt 2, 0.93 m stand | **39 deg** | 0 candidates | **12565 / 12902 px = 97%**, 0.9 mm |
| attempt 3, 1.035 m stand | **29 deg** | 0 candidates | **7673 / 8632 px = 89%**, 0.7 mm |

The overlays show the model's silhouette sitting on the head bar, the slot, the collar and the pedestal, with
disagreement only along the one-pixel silhouette edge. **The steeper view fits better**, because more of the
interface faces the camera — the exact inverse of the level-look premise the last three sessions were built on.

The scale this works at: 1 px = 0.70 mm at 0.43 m; the bars span 129 px so a 1 px edge error is 0.44 deg about
them; the slot spans 40 px, 1.43 deg; the neck spans 17 px, 3.33 deg — so rotation about the neck's own axis is
the weak direction, and it is exactly the one the upright constraint removes.

**How good the coarse stage has to be, measured rather than assumed.** The fit was re-run from seeds displaced
in random directions from the fitted pose, four seeds per distance, on attempt 3's frame:

| seed offset | slot-centre error (median of 4) | coverage | mean residual |
|---|---|---|---|
| 0 cm | 0.6 mm | 0.90 | 0.3 mm |
| 2 cm | 0.9 mm | 0.90 | 0.4 mm |
| 4 cm | 1.2 mm | 0.89 | 0.4 mm |
| 6 cm | 1.2 mm | 0.90 | 0.5 mm |
| 10 cm | 2.4 mm | 0.93 | 0.6 mm |
| **15 cm** | **193 mm** | **0.13** | 1.5 mm |

Two things follow. **The basin is about 10 cm** — far wider than a docking error, and inside what a region-level
VLM answer gives. And **the failure announces itself**: when the fit misses, coverage collapses from 0.90 to
0.13, a sevenfold separation. That is the property the current scheme does not have and cannot have. An earlier
run of this experiment did converge to a local optimum on the bars' top edges, which is what first suggested a
narrow basin; that seed was about 8 cm off *and* the restarts were drawn with a 3 cm spread, so the search never
covered the gap. With the seeds drawn properly the basin is as tabulated.

## 5. The proposal

Replace *detect candidates → threshold → VLM picks a mark → servo to a point* with:

1. **Locate (semantic, coarse).** The VLM answers, over the whole view, which item this is and roughly where —
   at region granularity, the thing it is measured to be good at. `find_regions` / `locate_region` already exist
   and are what `press` uses. Output: a seed point good to a few centimetres.
2. **Fit (geometric, fine).** Fit the interface the catalogue declares to the depth, over x, y, z and yaw, with
   the interface axis taken from the support's surveyed normal. Output: the interface's pose **and two numbers of
   evidence** — what fraction of its own projected area the depth agrees with, and the mean residual in
   millimetres.
3. **Take the grasp from the interface, not from the image.** The jaw axis, the approach direction and the seat
   depth are properties the catalogue declares (`axis`, the neck's two dimensions, the pads' band, and the
   support's surveyed outward normal). The only thing measured is *where the slot is*. This deletes the
   closing-axis SVD, the antipodal roll choice, and the width/length/clearance thresholds in one go.

   **No separate orientation check** (user's decision, 2026-09-20): an ORU sitting in its slot has no reason to
   be crooked unless the robot damaged it, so the declared approach direction stands. If something ever did put
   it askew, the fraction of the interface's surface that agrees would fall on its own — that one number already
   says it, and a second mechanism to say the same thing is a mechanism to maintain.
4. **Servo on the fit.** Re-fit each frame and drive the tool to the pose: pose-based visual servoing on a
   measured interface, rather than template-matching a grayscale patch. When the fingers cover the interface the
   coverage number falls and the last good pose carries the tool in — which is what `covered` already does.
5. **No gate anywhere.** "97% of the interface's surface agrees to 0.9 mm" and "the best fit agrees over 30% at
   8 mm, so this is not the declared interface" are both facts the agent can act on. Neither is an empty list.

### What this deletes

`find_candidates`' eleven thresholds and the whole candidate/mark apparatus; `refine_contact`; `PartTracker`'s
template matching and `associate`; `grasp_camera_sides` and the roll choice; the multi-view look search added
earlier today; `work_stands`' `shallowest_look_deg_above_horizontal` and `level_look`, and the contract text
about level looks; the stand-choice reasoning the model has to do about look angles. Roughly 600 lines.

### What it costs

No new dependency: four boxes, a ray-box intersection and an optimiser, in numpy with torch available for the
restarts — today's experiment is 120 lines. The boundary must pass the catalogue's whole `handle` block into the
pick goal instead of two numbers. Call it 300 lines net removed.

### Where this sits against the approved principles

v4's principle 1 is "no object models". **r3 already superseded it**, in the user-confirmed table of
`manipulation_contracts_proposal.md` §8: *"允许有来源的语义接口及文档几何先验，运行时必须验证"* — sourced
semantic interfaces and documented geometric priors are allowed, and must be verified at runtime — with the
limits *"不读取仿真物体真值、不要求 CAD mesh"*: no simulator ground truth, no CAD mesh required. This proposal is
inside that: the geometry is nine numbers from the equipment catalogue, not a mesh and not the simulator's pose;
the item's pose is measured from the camera every time; and the residual **is** the runtime verification r3 asks
for. What the harness gains is not knowledge of where the item is — it is knowledge of what a lifting interface
*is*, which is the same kind of fact as the gripper's jaw band or the site survey.

## 6. Decisions the user has to make

1. **Adopt interface fitting as the grasp perception?** If yes, today's uncommitted `pick` changes (the length
   gate, the multi-view search) should be reverted rather than built on — they are patches on the scheme being
   replaced. The `work_stands` docking-band change is about reach, not perception, and stands either way.
2. **What happens to an item with no declared interface?** Either the harness cannot grasp it and says so — a
   clean, statable limitation — or the old class-agnostic path stays as a fallback and we keep code we do not
   use. Recommendation: say so; no mission needs it.
3. **The paper's framing.** Is "the catalogue declares the interface, the robot measures where it is" a strength
   or does it weaken the autonomy claim? **The space-robotics literature answers this, and the answer is that
   class-agnostic grasping on an engineered interface is the thing nobody flies** — see §7.
4. **Real-robot transfer.** Isaac's depth is clean and complete. A real RealSense on a matte black handle is the
   documented failure case for active-IR depth. This belongs in the paper's limitations either way, but it is
   worse for a depth-only fit than for an RGB method. Do we care now, or at the LunarBot stage?

---

## 7. What flight practice actually does (and what it means for the paper)

This is the section that decides §6.3, and it is unambiguous.

**No flown space robotic system grasps an arbitrary feature of an arbitrary object.** Henshaw, Glassner, Naasz
and Roberts, *Grappling Spacecraft*, Annual Review of Control, Robotics, and Autonomous Systems 5 (2022),
NTRS 20210020506 — a NASA/NRL review — divides the whole problem by **whether the client was engineered to be
serviced**, and says of the two arms with more on-orbit hours than every other orbital robotics mission
combined:

> "the SRMS and SSRMS robotic arms … **interact solely with specialized grapple fixtures with optical fiducial
> alignment markers**"

> "machine vision systems designed for cooperative robotic grappling **rely primarily on optical fiducials** …
> fiducials designed to be compatible with orbital lighting conditions"

Even the "unprepared" case is not general grasping: it is a *different declared interface class* — the Marman
separation ring (three sizes cover most satellites) or the apogee engine nozzle, chosen because they are
"relatively uniform in shape and therefore provide an obvious target for visual servoing algorithms".

**The interface carries its own target, by standard.** ISS ORU grasp fixtures are co-located with a Modified
Truncated Cone target, which NASA's own payload-interface briefing calls "**the standard target type**"
(Callen, *Robotic Transfer and Interfaces for External ISS Payloads*, NTRS 20140008717). The international
standard (IERIIS, 2019) defines ORU "direct handling" as incorporating "**targets, alignment guides**" into the
equipment itself, and NASA's *ISAM State of Play 2025* (NTRS 20250008988) states that "**fiducial markers
integrated with the mechanical interface** … ensure spacecraft are prepared for future in-space servicing".
The Robotic Refueling Mission's lessons-learned puts it as a recommendation: "adding fiducials to key locations,
such as near potential grasp points … is a low cost and low mass modification".

**And the tolerance chain is three-stage, with perception carrying only the first stage.** NASA's own preferred
practice for robotically compatible handling (JSC DFE-1) gives the ISS ORU handle interfaces:

| interface | positional | angular |
|---|---|---|
| H-fixture (the ORU handle) | 12.7 mm | ±2° |
| micro-fixture | 7.6 mm | ±3° |
| micro-conical tool | 6.35 mm | ±1° |
| HOTDOCK (standard, lunar-capable) | ±15 mm | ±10° |
| ENVICON (DLR lunar analogue) | 20 mm | 20° |
| SSRMS end effector capture envelope | ⌀203 mm × 100 mm deep | — |

Perception's job is to put the tool inside the envelope; the envelope and force compliance do the rest. Dextre's
teleoperated positioning is 6 mm / 2.0°, and ORU insertion tolerates 5 cm / 8° of initial misalignment because
force-moment accommodation absorbs it — without which, its developers report, the task "is **not possible**".

**The lunar analogue work is the same, explicitly.** The ARCHES Mount Etna campaign (Wedler et al., IAC-2021,
54 authors) states that for manipulation, as distinct from navigation, "**Similar to already conducted space
missions this method is based on visual markers** … it enables a robust and highly precise detection as well as
pose estimation", and immediately after: "**For both presented methods, an existing model is assumed.**"
Markerless perception is used there for *rocks*. The companion result, in this paper's own target journal —
Prince et al., *Acta Astronautica* 212 (2023) 160-176 — reports ~200 payload-box dockings over 17 days at **95%
success** against a 20 mm / 20° interface tolerance, with failures attributed to arm orientation and load data,
not to perception.

### What follows for us

1. **This proposal is the faithful design, not a concession.** A harness that knows what a standardised lifting
   interface *is*, and measures where it is, is doing what every flown system does. The current scheme — a
   class-agnostic antipodal search over depth discontinuities, applied to an interface we engineered ourselves —
   has no flight analogue at all. The paper is stronger for saying so, and the autonomy claim is untouched:
   nothing here tells the agent which item to fetch, where it is, or what to do when something fails.
2. **Our interface already belongs to this tradition.** F83/F84 gave the T-handle form closure — a head above, a
   collar below, fingers captive in the slot — for exactly the reason the literature gives: the mechanical
   interface absorbs what perception and control cannot. That is a capture envelope, arrived at independently.
3. **An honest asymmetry to state in the limitations.** Flight practice has a third stage we do not: force
   compliance. Our simulated gripper closes at 3-4x its datasheet force (F84) and the skill has no force-guarded
   insertion, so perception and the interface's form closure carry the whole budget. That is a reason to want a
   measured pose with a residual rather than a thresholded candidate, and a reason to be careful about claiming
   the numbers transfer to hardware.
4. **A gap worth naming.** No lunar-surface work demonstrates interface-level docking without markers or a known
   model. Every real demonstration — ARCHES, LANDO, on-orbit servicing — stands on one or the other.

**Citation traps found while checking, to avoid repeating:** MultiSense/SXGA belongs to Valkyrie R5, not
Robonaut 2; "Tri-Tool" is not RRM terminology (the three-in-one tool is the WCT); OSAM-1's use of GNFIR-derived
markerless tracking has no first-hand source and NASA's own catalogue lists its misalignment tolerance as
*Unavailable*; the SPEC2021 "<11 cm / <4°" figure comes from an abstract and needs the original checked before
it is cited.
