# Operator protocol for Experiment I

Status: protocol draft, resolves the "pending user decision" flagged in `docs/operator_console.md`.
Governing decisions already made (user): (a) in the final campaign the human researcher is the
operator, following this written protocol; a scripted operator is used only during development;
(b) when a method requests the operator, the run **pauses and blocks** until the answer is
supplied, then continues — it does not end the run (this is the answer to
`operator_console.md`'s open item 2). Frozen requirements this protocol must not contradict:
research_content.md §5.5 "Human-assistance protocol"/"Primary metrics", execution_plan.md §13.2
"Operator protocol"/"Human-interaction event logging", §14.1–§14.2.

## 1. Roles and lifecycle

- **Final campaign:** one human operator (the researcher) mans the shared console
  (`experiments/operator_console/console.py`) for all three methods, across all runs.
- **Development only:** a scripted operator (fixed lookup table, no live judgment) stands in for
  the human so infrastructure can be exercised without spending researcher time; scripted-operator
  runs are never pooled with the human-operator campaign data (research_content §5.9: "freeze
  metric definitions... before the final campaign" — a mid-campaign operator-policy change is
  itself a form of re-authoring the measurement instrument).
- Every request is answered from the **fixed answer policy** (§5) — the operator does not
  improvise mid-run; improvising is itself a protocol violation, logged and excluded (§6).

## 2. Allowed operator actions, by method and ALFUS level

ALFUS Human-Independence interaction-authority ordering (`mission > strategic_goal > tactical_goal
> mission_task > route > autopilot > servo`) is taken directly from the ALFUS Human-Independence
axis (Huang, 2004, NIST SP 1011-I-2.0 §on HRI levels; Huang & Messina, 2007, NIST SP 1011-II-1.0)
and is already the ordering `execution_plan.md §13.2` mandates for `authority_level` in every
logged event — this protocol only assigns each concrete console action to one rung of that ladder.

| Action (all through the shared console) | Ours | PLEXIL | EUROPA→PLEXIL | ALFUS level | Source |
|---|---|---|---|---|---|
| Provide initial mission in natural language | yes | n/a (formal goal, §3 below) | n/a (formal goal) | `mission` | research_content §2.7, Castano et al. 2022 (uplink = communicating intent, not a full sequence) |
| Provide initial mission as formal goal/PLEXIL top plan / EUROPA goal token | n/a | yes | yes | `mission` | execution_plan §5.3 rule 8 ("equivalent mission intent") |
| Restate/clarify the mission goal after an ambiguity | yes | yes (re-issue goal Lookup) | yes (re-issue goal) | `strategic_goal` | ALFUS SP1011-I/II; Castano et al. 2022 |
| Answer a scoped clarification question (which object/region/condition) | yes | yes (bind a Lookup value) | yes (bind a state var) | `tactical_goal` | Olsen & Goodrich 2003 ("robot attention demand": a scoped question demands less operator judgment than restating the mission) |
| Approve an action pending `approval_required` | yes | yes (approve resource/authority Command) | yes (approve activity execution) | `mission_task` | execution_plan §4.7/§10.2 (guard's `approval_required` outcome) |
| Invoke a pre-authored procedure / library node by name | n/a (no library concept) | yes | n/a (EUROPA has no library nodes; a specific activity choice is equivalent) | `mission_task` | execution_plan §11.1 ("library nodes for reusable general procedures") |
| Specify/override a route or waypoint | yes | yes | yes | `route` | ALFUS SP1011-I/II route rung |
| Operational abort / safe-stop | yes | yes | yes | `autopilot` | execution_plan §13.2 ("issue an operational abort/safe-stop if required"); logged but excluded from HIR numerator (§4) since it is a safety action, not mission-progress assistance |
| Direct teleoperation (raw joint/servo command) | **forbidden** | **forbidden** | **forbidden** | `servo` | research_content §4.2/§9.2 — the model, and by parity the operator through the *mission* channel, may not issue raw motor commands; teleoperation would bypass the shared low-level-safety-mediated capability path entirely |

Forbidden for every method, at every ALFUS level (execution_plan §13.2, verbatim source of this
list):

- edit PLEXIL plans/libraries, EUROPA NDDL/domain/solver rules, or Ours prompts/runtime/capability
  metadata;
- add a new capability;
- reveal evaluator-only state (deterministic ground truth reserved for the external evaluator,
  research_content §3.2/§5.3 rule 3).

Any of these, if required to continue, sets `ground_reauthoring_required=true` (§6).

## 3. Clock rules

`HIR = total active operator–system interaction time / mission elapsed time` (execution_plan
§14.2, itself ALFUS's Human Intervention Ratio, Huang 2004/2007). This protocol fixes the
ambiguous edges:

- **Mission elapsed time** starts when the mission is accepted for execution and ends at terminal
  success/failure/abort; simulator/process startup is excluded (execution_plan §14.2, unchanged).
- **Interaction time** starts at `interaction_start` and ends at `interaction_end`, both timestamped
  at the moment they occur by the console, never reconstructed from chat/log timestamps after the
  fact (execution_plan §13.2, explicit instruction; already implemented in `operator_console.md`).
- **Operator response latency is part of interaction time, not excluded from it.** Because decision
  (b) makes the run block-and-wait, the wall-clock the human operator takes to read and answer a
  request is exactly the "active interaction" ALFUS's ratio is defined over (Huang 2004/2007); it
  is not a network artifact to be subtracted.
- **Simulated lunar one-way communication delay is excluded from HIR by default**, because
  Experiment I's scenarios do not currently make Earth-link delay an active independent variable
  (execution_plan §7.0 scope guard: implement/exercise only what a selected scenario needs). If a
  later scenario revision adds a communication-availability condition, report HIR twice —
  operator-active time (current definition) and operator-active-plus-propagation-delay time — and
  say in the results which is primary; do not silently fold delay into either number.
- Abort/safe-stop interactions are logged (`human_command`, `autopilot` level) but excluded from
  the HIR numerator: they are a safety action available to any method at any time, not
  mission-progress assistance, and counting them would penalize safer methods.

## 4. Bias and learning-effect controls

- **Fixed answer policy.** Before the campaign, write one lookup table
  (`request_type → scripted operator response`) covering every clarification/escalation type any
  method can raise in the frozen Mission A/B scenarios (covered and held-out). The human operator
  answers from this table; the same request type gets the same answer content every time it recurs,
  independent of method or run order. This is the scripted-operator methodology of Wizard-of-Oz
  HRI studies generalized to a human-in-the-loop confederate: constrained responses are the
  strongest predictor of reproducible WoZ/operator behavior across the literature Riek surveys
  (Riek, 2012, *Wizard of Oz Studies in HRI: A Systematic Review and New Reporting Guidelines*,
  JHRI 1(1):119–136 — "constrained wizard production" was used in 90.7% of reviewed studies and is
  the recommended default).
- **Blinding is only partial and this is stated, not concealed.** The operator cannot be blinded to
  *which method* is running — PLEXIL Lookups, EUROPA state variables, and Ours' natural-language
  questions are visibly different console payloads. What is controlled instead is the operator's
  *judgment*: because every answer comes from the fixed table keyed on request type (not on which
  method asked), the method identity cannot change what the operator says. Report this as an
  explicit limitation rather than an unearned blinding claim (Riek, 2012, reporting-guideline
  recommendation to disclose exactly what was and was not controlled).
- **Order counterbalancing.** Rotate the order in which the three methods are run across scenario
  seeds/sessions so that any within-session operator learning (faster reading, anticipating request
  phrasing) does not systematically favor whichever method is always run last. Common practice for
  comparing systems on shared human-in-the-loop instrumentation (Steinfeld et al., 2006, *Common
  Metrics for Human-Robot Interaction*, HRI'06, pp. 33–40 — the paper's motivation for standardized,
  repeatable metrics is exactly to make cross-system comparison meaningful).
- **No adaptive operator behavior.** The operator may not get better/faster at a method by design
  (this is why the scripted-answer table exists) but response *latency* will still vary with
  request complexity, which is expected and is exactly what "operator response latency" is supposed
  to capture (Olsen & Goodrich, 2003, *Metrics for Evaluating Human-Robot Interactions*, PERMIS
  2003, pp. 4–11 — "interaction effort" is the intended quantity, not something to be minimized by
  operator practice).

## 5. Assisted-run rules

- **Assistance within the allowed-action table (§2) does not, by itself, end autonomous counting.**
  research_content §5.5 defines Autonomous Mission Success as completion "without post-reveal
  method-specific artifact modification" — it does not require zero operator interaction.
  A run with nonzero `interaction_start/end` pairs (clarification answered, approval granted, route
  specified) is still scored as an autonomous run, with its HIR reported alongside the success bit.
- **A run stops counting as autonomous exactly when continuation would require an action outside
  §2's table**: editing a frozen artifact, adding a capability, or revealing evaluator-only state.
  At that point `ground_reauthoring_required=true` is set and the run terminates for the primary
  success metric (execution_plan §13.2, verbatim).
- It also stops counting as autonomous if the system reaches a state with **no admissible
  continuation** under its own frozen logic (Ours reports no viable next tool call; PLEXIL/EUROPA
  reach a failure with no untried branch/no feasible plan) and the operator's only available fixed
  answer is insufficient to unblock it without re-authoring (research_content §5.5,
  "event-triggered, not time-threshold-triggered").
- **Reporting.** Two rows per run, never merged: `autonomous_mission_success` (primary, execution_plan
  §14.1) and an optional `assisted_mission_success` descriptive field recorded only when the
  operator continues the run past the re-authoring boundary purely for trace/failure analysis
  (execution_plan §14.1: "must never replace the primary autonomous-success metric"). An assisted
  completion is never averaged into, or substituted for, Autonomous Mission Success Rate.

## 6. Baseline escalation channel (comparable across all three methods)

`docs/operator_console.md` confirms `ros/plexil_capability_adapter` has no operator-facing `Command`
today. This protocol specifies the trigger conditions and ALFUS mapping the missing `RequestOperator`
Command (and the EUROPA host's equivalent hook) must implement, so all three methods reach the
operator through one shared channel — the same `/space/operator/request` /
`/space/operator/report` topics and the same `console.py` already built (`operator_console.md`):

| Method | Escalation trigger | ALFUS level | Notes |
|---|---|---|---|
| Ours | model calls `request_operator` tool | request-specified (model states what it needs) | already implemented (`space_runtime/agent.py`, decision (b) changes it from run-ending to blocking) |
| PLEXIL | a plan node's `Command` returns failure and no further `Try`/library alternative exists at that node (i.e., the node's own recovery branches are exhausted) | `mission_task` (node-local) or `tactical_goal` if the exhausted alternatives were themselves library-level | mirrors `ExecuteCapability`'s existing Command pattern (execution_plan §11.1); blocks the plan node on the reply exactly as PLEXIL's documented async-Command/Lookup model already supports |
| EUROPA→PLEXIL | the solver cannot produce a consistent plan extension for the current goal within the frozen domain (no flaw resolution exists) | `strategic_goal` (the planner itself, not one activity, cannot proceed) | this is the model-based analogue of "no admissible continuation"; a domain that *can* resolve the situation is a covered case for EUROPA and must not be reported as held-out (research_content §5.5, "Expected evidential interpretation") |

This gives every method the same *structural* escalation signal — "no admissible continuation
under the method's own frozen logic" — rather than a method-specific heuristic, so the comparison
in §4/§5 is over one shared channel rather than three different notions of "asking for help."

## 7. Decisions left open

- The literal contents of the fixed answer-policy table (§4) cannot be written until Mission A/B v2
  scenarios (covered + held-out cases) are finalized in the scene (`handoff.md`: v2 not yet built).
  This protocol fixes the *mechanism*, not the *script text*.
- Whether abort/safe-stop time should be excluded from HIR (§3) or reported as a separate
  safety-interaction statistic is proposed here but not yet confirmed by the user.
- Whether a communication-delay condition will actually be exercised in Experiment I is undecided
  (execution_plan §7.0 scope guard); §3's two-HIR-variant rule is conditional on that.
- Single-operator vs. multi-operator inter-rater variance: Experiment II (§13.4) has a
  multi-engineer counterbalancing precedent; Experiment I does not yet specify whether more than one
  qualified operator will run sessions. Left to the user.
- The PLEXIL `RequestOperator` Command and the EUROPA "infeasible" detection hook (§6) are protocol
  specifications here, not code; building them is explicitly out of this document's scope
  (`operator_console.md`: "owned elsewhere").
- A secondary diagnostic in the spirit of mean-time-between-interventions (Fong & Abercromby, 2010,
  *Assessment of Robotic Recon for Human Exploration of the Moon*, Acta Astronautica 67(9–10):
  1176–1188 — MTBI averaged 24 min, range 5.5 min–1 h, in a lunar-analog rover field test) could be
  reported per scenario alongside HIR; not adopted as a primary metric since execution_plan §14
  already fixes the primary metric set and this doc must not add one.

## References

1. Huang, H.-M. (ed.). *ALFUS Framework, Volume I: Terminology, Version 2.0*. NIST SP 1011-I-2.0, 2004. https://www.nist.gov/document/nistsp1011-i-2-0pdf
2. Huang, H.-M.; Messina, E. R. *ALFUS Framework, Volume II: Framework Models, Initial Version*. NIST SP 1011-II-1.0, 2007. https://www.nist.gov/publications/autonomy-levels-unmanned-systems-alfus-frameworkvolume-ii-framework-models-initial
3. Olsen, D. R.; Goodrich, M. A. "Metrics for Evaluating Human-Robot Interactions." *PERMIS 2003*, Gaithersburg, MD, Sept 16–18, 2003, pp. 4–11. https://faculty.cs.byu.edu/~mike/mikeg/papers/OlsenGoodrichPERMIS2003.pdf
4. Steinfeld, A.; Fong, T.; Kaber, D.; Lewis, M.; Scholtz, J.; Schultz, A.; Goodrich, M. "Common Metrics for Human-Robot Interaction." *HRI '06*, 2006, pp. 33–40. DOI:10.1145/1121241.1121249.
5. Crandall, J. W.; Goodrich, M. A. "Characterizing Efficiency of Human Robot Interaction: A Case Study of Shared-Control Teleoperation." *IEEE/RSJ IROS*, Lausanne, 2002, pp. 1290–1295.
6. Goodrich, M. A.; Crandall, J. W.; Stimpson, J. L. "Neglect Tolerant Teaming: Issues and Dilemmas." *AAAI Spring Symposium on Human Interaction with Autonomous Systems in Complex Environments*, Stanford, CA, 2003.
7. Castano, R.; Vaquero, T.; Rossi, F.; Verma, V.; et al. "Operations for Autonomous Spacecraft." *2022 IEEE Aerospace Conference*, Big Sky, MT, 2022. arXiv:2111.10970.
8. Fong, T.; Abercromby, A. "Assessment of Robotic Recon for Human Exploration of the Moon." *Acta Astronautica*, 67(9–10), 2010, pp. 1176–1188. DOI:10.1016/j.actaastro.2010.06.029.
9. Riek, L. D. "Wizard of Oz Studies in HRI: A Systematic Review and New Reporting Guidelines." *J. Human-Robot Interaction*, 1(1), 2012, pp. 119–136. DOI:10.5898/JHRI.1.1.Riek.
10. Biggie, H.; Rush, E. R.; Riley, D. G.; et al. "Flexible Supervised Autonomy for Exploration in Subterranean Environments." *Field Robotics*, 2023. arXiv:2301.00771.

Project-internal, treated as fixed constraints, not re-verified here: `AGENT/research_content.md` §2.4, §5.3, §5.5; `AGENT/execution_plan.md` §13.2, §14.1, §14.2; `docs/operator_console.md`.
