# experiments/scenarios

Scenario manifests, execution_plan.md §12: one YAML per mission instance under
`mission_{a,b}/{covered,held_out}/<id>.yaml`, plus `<id>.certificate.yaml` for every
held-out instance (§13.2 "Closed-capability validator"). Evaluator-only content
(`evidence_verifier_mapping`, every certificate) is never read by a method -- no
prompt, contract, playbook, guard or verifier code loads this directory.

Only instances that exist today are covered here: Mission A/B `covered`, plus the
held-out `env.scenario=` switches SRB's task classes already implement
(`space_robotics_bench/srb/tasks/mobile_manipulation/lunar_base_mission_{a,b}/task.py`),
and the `route_block` scenery switch (marked OPEN -- see its manifest notes, the
scenery has never been run under a mission task variant). `capability_substitution`
(catalog A5) and the dust-obscured fusion (A3+A4) are cataloged as recommendations in
`docs/lunar_task_catalog.md` §5 but have no `scenario=` value in SRB code yet -- no
manifest for them.

`evaluation/scenario_schema.py` loads and minimally validates these files (required
§12 fields present); it is the schema `evaluation/rows.py` reads `scenario_id` and
`success_condition` from when building a normalized run row.

Certificate `status` values: `OPEN` (needs user/scene confirmation before campaign
admission) or `CONFIRMED` (validated live, with a note citing the evidence). None are
`CONFIRMED` yet -- no freeze has happened (execution_plan §13.1 step 6, not run).
