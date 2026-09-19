# Shared manipulation geometry

`node.py` applies surveyed structures and local RGB-D surface meshes to MoveIt.
Adjacent valid pixels form triangles only when their edges resolve the minimum
feature supported by `GripperGeometry`. Overhangs are not extended down to the
ground. Invalid pixels, occlusion and self-filtered pixels remain unobserved;
absence of a triangle is not a free-space observation.

Depth-return semantics travel on `/openral/cameras/{camera}/depth_semantics`,
relayed from the sensor backend. A positive-infinity return explicitly declared
as beyond the far clip can establish free space inside that declared range;
unknown/invalid returns cannot. The skill does not assume simulator semantics
for hardware images or manufacture a finite surface at the far clipping plane.

All methods use the same scene. No object truth or target-wide collision
exemption enters it. `working_on` no longer cuts spheres out of measurements.
The current arm self-filter is inherited; contact insertion additionally requires
free-ray evidence from the skill's recorded views for actual gripper mesh samples.

`/space/prepare_contact_scene` (`std_srvs/Trigger`) applies the latest measured
scene through MoveIt's `ApplyPlanningScene` service and returns its acknowledgement,
scene name and sensor timestamps. It retains that stationary scene during the
serial contact operation. `/space/release_contact_scene` resumes measurements;
the skill calls it on exit, including failure/cancellation. The target tracker
invalidates the contact when measurements disagree; it cannot redefine the target.
This is a stationary-workpiece contact interface, not a dynamic scene tracker or
a general concurrent ownership service. Process-crash reconciliation and held-object
attachment are not claimed as validated by the contact-only test.

The EG2 planning model is generated from robot asset collision meshes and joints by
`experiments/launch/lunar_base_d0/export_gripper_model.py`. It replaces the former
solid open-jaw envelope. Run the exporter with the repository Python, then build
`rm_75_config` using the workspace's merged install layout. MoveIt must reload the
generated robot description; restarting the skill runtime alone does not reload it.

See `docs/contact_closure_audit.md` for scope and
`artifacts/perception/contact_revision/` for the actual-model read-only checks.

## Expected grasp contact

`/space/configure_contact` (`openral_msgs/ConfigureContact`) registers one immutable
oriented region from the committed wrist RGB-D candidate and odometry/TF. Its width
and length are measured candidate dimensions; its depth is the gripper perception's
existing required depth discontinuity. This box only labels **existing measured
triangles**: triangles wholly inside become `measured/contact`; boundary-crossing
triangles and all other surfaces remain `measured/work_zone`. Nothing is deleted or
filled from an object CAD model, simulator identity, or ground-truth pose.

The shared EG2 geometry declares distal jaw bodies `eg2_link5`/`eg2_link6` as contact
links. Drive linkages, palm, arm and chassis remain protected. This is whole distal
jaw-body granularity, not a finger-pad-only mesh segmentation. In particular g8p's
`eg2_link2` alarm does not become permissible merely because it stopped a grasp.

Registration leaves all collisions enabled. `endpoint_check` enables only those
two link/patch pairs for contact IK and whole-robot validity; `revoke` restores the
strict patch row before planning/moving to standoff. `insertion` enables the same
pairs for final close-in and closure. Free-ray coverage uses the same contact-link
and bounded-region predicate; it records expected-contact samples separately from
observed free samples. After closure permissions are revoked before lift.

Every change waits for ApplyPlanningScene and returns phase, scene and permission
evidence to the skill/harness. Normal, failed and cancelled operation cleanup
restores the exact original ACM and unsplit measured geometry before unfreezing.
The serial caller remains the scene owner. This does not implement crash recovery,
force control, payload attachment, or guarantee that an uncertain contact is valid.

Read-only integration check (idle graph only):
`experiments/launch/lunar_base_d0/check_contact_permission.py <absolute result.json>`.
It uses real measured triangles and MoveIt to check region immutability, both active
phases, revocation, preservation of every triangle/unrelated ACM entry, and release.
