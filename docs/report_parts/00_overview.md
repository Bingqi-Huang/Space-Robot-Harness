# Research report: an agent harness for trustworthy foundation-model autonomy on a lunar surface robot

Compiled 2026-09-30 for the Acta Astronautica manuscript. This file is the single evidence base for writing the paper,
read together with `AGENT/research_content.md` (the intended paper logic) and `AGENT/execution_plan.md` (the plan).
Where this report and those two files disagree, **this report wins**: it describes what was built and run. Every number
carries its source in brackets (a finding `F<n>` in `docs/research_findings.md`, a file, or a run). Numbers marked
"computed for this report" come from the recorded runs by the scripts named next to them.

## How to use this report

| Part | Content |
|---|---|
| 0 (this) | Overview, headline results per hypothesis, corrections made while compiling, pending items, writing guidance |
| 1a | The system under test and the shared platform: robot, simulation stack, lunar base scene, shared capabilities and skills, the proposed runtime (facts, verification, guard, context, tools, prompts), models, development history |
| 1b | Baselines (PLEXIL, EUROPA→PLEXIL) and their lock, mission control (operator console), the Earth link, the external evaluator and every metric as implemented, the preregistration, the run farm |
| 2 | Experiment I (autonomous mission generalization): design, protocol, history, every table, all 51 runs, qualitative evidence, latency, artifacts |
| 3 | Experiment II (cost of extending the mission envelope with a new capability): design, engineering results, hidden cases, every run |
| 4 | Harness ablations: design, stage 1 and 2 results (offline; the live stage 3 was stopped by the user and is not used) |
| 5 | Re-authoring study (the baselines' cost of each held-out case), validity and limitations, artifact and manuscript index |
| 6 | Community-standard metrics computed post hoc (goal-condition success, path-length-weighted success, pass^k, safe success, FDIR detection/recovery coverage, MTBI, intervention response time, run-time assurance, code churn, planning-model size, ECSS levels) and **the glossary of every measure in this report** (kind, definition, standard name and source, code) |

## The study in one paragraph

A foundation model (Qwen3.8-Max, thinking on) is embedded in the mission workflow of a simulated lunar surface robot
(LunarBot: a four-wheel rover with a 7-DoF RM-75 arm, Isaac Sim 5.1 via the Space Robotics Bench, ROS 2, Nav2, MoveIt)
servicing a lunar base (power distribution units, a battery storage unit, an ISRU plant, a habitat, stands and a
depot). The model chooses the next operation; a thin runtime around it (the harness) keeps the disciplines of space
operations: an authoritative mission record that only verified evidence advances, independent verification of every
physical effect, an authority and invariant guard outside the model, escalation to mission control with a modelled
Earth link (4.27 s one-way delay, loss of signal 925 s into every run), and a complete trace. It is compared with two
established space-autonomy approaches built from NASA's open-source tools, PLEXIL (procedures) and EUROPA→PLEXIL
(model-based planning executed by PLEXIL), frozen and authored natively for the covered situations. All three methods
share the robot, the capabilities, the skills, the perception model (DeepSeek-V4.1-Flash), the safety layer and an
external evaluator that reads simulator truth. Only the mission layer differs.

## Hypotheses and results (headline numbers; details and sources in parts 2 to 5)

**H1: unplanned situations handled without rewriting (Experiment I).** Supported strongly.
- 13 instances: 7 covered (L0, L1), 6 held-out (L2-A new cause, L2-B missing relation, L3 missing composition, L4
  authority boundary). Baselines once per instance (deterministic), Ours once per covered and three times per held-out
  instance: 51 scored runs [F142].
- Covered: 7/7 for every method. Held-out: Ours 18/18, Wilson 95% [0.82, 1.00]; PLEXIL 0/6 and EUROPA→PLEXIL 0/6,
  [0, 0.39] each [F142; artifacts/eval/exp1b/tables.md].
- Every held-out baseline run detected the anomaly, asked mission control for a new procedure and held safely; 12/12
  needed ground re-authoring, Ours 0/18 [F142]. Nine baseline runs detected it by goal checks, the two L2-B runs by a
  failing place (the designed symptom), and PLEXIL's L3 battery run failed at the physical layer first (F153, below).
  Offline, a retry budget of 1, 2, 3 or 5 attempts never changes the baseline outcome (48 runs) [F143].
- Preregistered `preplanned_transition_fraction` (share of each held-out instance's certified solution that the frozen
  artifacts already contained): PLEXIL 0.75 to 0.93, EUROPA→PLEXIL 0.75 to 1.00, Ours 0 by construction; covered 1.0
  for both baselines. The baselines held most of each solution and still stopped on every held-out run; PLEXIL lacked
  the composition (the shutter press before the reset, a second leg after a set-down, the authorization step), EUROPA's
  domain admitted every transition of L2-B and L3 and lacked relations (stand occupancy, a failed module) that a
  transition count cannot see [F155; part 2 §5.9].
- ALFUS human independence, held-out, median [percentile bootstrap 95% over runs]: human intervention ratio Ours 0.080
  [0.000, 0.240], PLEXIL 0.617 [0.461, 0.696], EUROPA→PLEXIL 0.485 [0.313, 0.613]; longest autonomous stretch 1029 s
  [770, 1096] vs 179 s [122, 353] and 319 s [182, 668]; idle fraction 0.026 vs 0.634 and 0.499; no interval overlaps.
  9 of 18 Ours held-out runs sent no request. Ours' 10 held-out requests: 3 authorizations (all L4, all granted), 7
  information; highest interaction level: tactical goal (3 L4 runs), none in 15 [F152; tables.md].
- Costs of Ours: covered median mission time 538 s vs 264 / 265 s; held-out median 50 reasoning steps vs 23 covered;
  a reasoning call takes 19.9 s wall (median, IQR 11.3 to 38.7 s) and the simulator ran at 0.237 of real time during
  calls, so with latency counted in full covered 538 → 825 s and held-out 1132 → 2071 s (upper bound); one L2-A run
  misread the drawn shutter, swapped a module it did not need and used 79 of 80 steps before succeeding [F152; part 2].

**H3: open reasoning inside hard boundaries.** Supported in the campaign; the ablations isolate one component.
- 0 false completions in 51 scored runs; the guard held 3 proposals (L4 donor removals from an energized unit), none
  executed before a grant; 0 removals without approval, 0 dropped items, 0 executions during a latched fault; 7
  unintended contacts for Ours (6 in one L3 run within 0.6 s, partner unresolved between the arm's base and the unit's
  cradle; 1 of 20 ms); baselines' failed place on the occupied stand pushed the container 5.9 cm once per L2-B run
  (3 collateral episodes) [F142; part 2]. Trace completeness: Ours 451/451 calls, PLEXIL 81/81 [F142]; every reasoner input re-renders
  from the event log alone (1099/1099 steps of exp1b, 67/67 of the final Exp II run) [part 6 §4.5].
- Ablations (offline counterfactual replay, 684 decisions): without independent verification the model carries on to
  place an item that is not in the jaws 48 of 51 times, where the full runtime checks first 47 of 51; at a missed
  press, the variant still judges right where the unit's own telemetry exposes it (20/21) and fails where nothing
  else observes the effect (shutter: 0/3 vs 3/3). The guard, the authoritative facts and context reconstruction show
  no difference in a single decision (null results; the guard's value is a guarantee independent of the model's
  compliance: without it the model never took a donor without approval, 0/18) [F150; F153; part 4].

**H2: less engineering to add a capability (Experiment II and the re-authoring study).** Supported in the kind of
change, not in hours.
- New shared capability `scan_label` (Data Matrix serials read by the wrist camera). Fresh engineer sessions (Claude
  Opus 5.5), order Ours → PLEXIL → EUROPA→PLEXIL: all passed the validation suite on the first run; active 54.5 / 46.3
  / 53.4 min (Ours longest), of it not waiting on the simulation 4.7 / 10.8 / 20.8 min. Ours registered the contract and
  made the reading a verified fact, no procedure; PLEXIL wrote a check → record-guided pass → 13-support sweep →
  escalate; EUROPA modelled identity as state with a sensing activity and narrowed candidates in the host [F146; part 3].
- Hidden cases (mislocated spare, swapped records): before the extension 0/6 (Ours' two reports were false
  completions: it could verify a placement but not an identity); after it Ours 6/6, PLEXIL 2/2, EUROPA 2/2. Ours searched
  less systematically (first read the named unit at scan 8 to 15; PLEXIL at 6, EUROPA at 3), and one Ours run sent a
  new-procedure request that loss of signal left unanswered before it succeeded [F147; part 3].
- Re-authoring (what each baseline's held-out failure costs once mission control has the diagnosis; fresh Claude
  engineers, time without the simulation wait): PLEXIL 5.5 / 11.0 / 8.8 / 13.6 min (L2-A / L2-B / L3 / L4), EUROPA→PLEXIL
  11.7 / 81.4 / 71.5 / 59.7 min, with 2 vs 14 modelling/logic errors fixed on the way (PLEXIL's in adapter code,
  EUROPA's mostly steering the stock solver); all 8 cases pass live. EUROPA→PLEXIL L3 needed a second iteration: its
  model pressed the reset with the arm unstowed, which a shared press-skill limitation at the BESS panel defeats (the
  proposed runtime met it twice in exp1 and recovered on its own) [F156; F159; part 5 §A.9]. The cost the baselines pay
  is the ground loop (diagnosis, idle robot, a communication window), not engineer hours; the proposed runtime needed
  none.

**Community-standard metrics (post hoc, part 6; the preregistered measures above are unchanged).** Held-out
goal-condition success Ours 1.00 vs 0.17 / 0.17; pass^3 = 1.00 for Ours (Exp I held-out, Exp II after the extension);
path-length-weighted success Ours 0.65 covered / 0.68 held-out (the cost of online reasoning: median 10 vs 5 actions
covered); safe success Ours 6/7 and 17/18, baselines 7/7 and 0/6; FDIR: every held-out anomaly detected by every method,
recovered on board only by Ours (18/18 vs 0/6, ECSS F2-like vs F1-like); independent verification coverage 1.00 vs
0.19 / 0.20; guard held 0.7 % of Ours' proposed actions; Exp II relative code churn Ours 0.031 vs PLEXIL 0.177 and
EUROPA→PLEXIL 0.142. Glossary of every measure: part 6 §1. [F157]

## Closure against AGENT/research_content.md (checked 2026-09-30, 22:50 CST)

Every experiment and measure the research plan calls for is either done or a recorded deviation; nothing experimental
is open. What remains is writing. [F160]

| research_content item | status | evidence / where |
|---|---|---|
| H1, Exp I (§5.5): covered vs held-out, three methods, two mission families | done | part 2; F142, F152, F153 |
| §5.5 metric 1 autonomous success; 5 variation coverage (success vs level) | done | part 2 §5; `paper/figures/success_by_level` |
| §5.5 metric 2 HIR (ALFUS); 4 interaction level | done (medians + bootstrap) | F152; part 1b §6.6; part 6 §1 (standard names) |
| §5.5 metric 3 human planning time / pre-authored share | done: planning time = the re-authoring study per case; share = `preplanned_transition_fraction` | part 5 §A.9 (F156, F159); part 2 §5.9 (F155) |
| §5.5 metric 6 violating proposals and executions | done: 3 guard holds, 0 executed; violation classes for all methods | part 2 §7.4; part 6 §2.1.6 |
| H2, Exp II (§5.6): new shared capability, ETVS, artifact change, modelling errors, post-extension success | done; H2 holds in the kind of change, not in hours (Ours' active time was the longest) | part 3; F144-F147 |
| H2 for a new mission situation (re-authoring the baselines per held-out case) | done: all 8 cases pass live; PLEXIL 5.5-13.6 min, EUROPA→PLEXIL 11.7-81.4 min per case; Ours 0 | part 5 §A.9; F156, F159 |
| H3 (§1.7, §6.4): boundaries hold, verification-backed completion, reconstructable trace | done: 0 false completions, 0 executions despite a hold, trace 451/451, every reasoner input re-rendered from the log; Ours had 7 contact windows vs 0 (report it) | part 2 §7.4; part 6 §4.5 |
| §5.7 harness ablations | done offline (stages 1-2); **live stage 3 stopped by the user, not used**: one-decision evidence only | part 4; F148-F150, F153, F154 |
| §5.8 real LunarBot demonstration | **dropped by the user**: future work, no transfer claim | part 5 §B.2 |
| §5.9 statistics: intervals, per-instance pairing, repeated FM runs, raw traces, failure taxonomy | done (descriptive, preregistered); failure categories by one engineer | part 1b §6.7-§7; part 2 |
| §6.3 mission trace figure (held-out, with a baseline companion) | swimlanes for L4 and L2-B x 3 methods; 13 textured 1x videos (Ours) | `artifacts/figures/exp1b/swimlane/`, `video_1x/` (F158) |
| §6.6 figures 1-3 and tables 1-3 (operating model, architecture, coverage design, related systems, capability stack, scenarios) | writing: content in parts 1a, 1b, 2 §2 | -- |
| community-standard metrics (added by the user, post hoc) | done; choose at writing time | part 6 (F157) |

Wording the evidence does not support (narrow it in the paper): contribution 3's "distributed-intelligence
reconciliation" and "structured space-operational context" (one remote reasoner, no onboard/edge tier; restart
reconstruction supported but never exercised live; context = the Earth link and unit telemetry, part 5 §B.2);
"less engineering time" for a new capability (Exp II: similar time, different kind of change); any hardware or
lunar-fidelity claim; any significance claim (n is small; descriptive by preregistration).

## Corrections made while compiling this report (use these, not the older statements)

| Topic | Older statement | Corrected | Source |
|---|---|---|---|
| Interaction statistics | means (HIR 0.136 / 0.591 / 0.470; stretch 955 / 218 / 390 s) | preregistered medians with bootstrap intervals (above) | F152 |
| Reasoning latency | not reported | 19.9 s per call; latency in full 538 → 825 s covered | F152 |
| exp1b plexil_l3_bess | category 2, "no physical-layer failure in any method" | category 4 (press failed 3x after an accepted dock); outcome unchanged; PLEXIL held-out success given no physical-layer failure 0/5 | F153 |
| Baseline detection | "every held-out baseline run detected the anomaly through goal checks and retried up to the budget" | 9 by goal checks, 2 by a failing place, 1 physical-layer | part 2 §7.1 |
| L3 contacts | "beside the unit's cradle" | partner unresolved (arm base 0.31 m / cradle 0.28 m) | part 2 §7.4 |
| Baseline collateral | "5.9 cm three times" | 5.9 cm once per L2-B run, counted as 3 episodes | part 2 §9 |
| Exp II scans | "12 to 17 scans to find the unit" | 12 to 17 scan calls; unit first read at scan 15, 8, 14 | part 3 §5.5 |
| Exp II Ours 6/6 | plain success | one run (post_ours_h1_r2_f147) sent a new_procedure request, unanswered (loss of signal); counts as ground re-authoring by the preregistered rule | part 3 §5.5 |
| Ablation N | 21 vs 28 of 75 decisions different | 18 per arm forced by the rule; comparable 57: 3 (full) vs 10 (no_context) | F153 |
| Ablation J1 variant | 3 CHECK | the 3 look at the destination slot, not at the item | F153 |
| Ablation reader | "blind reader" | a Claude Sonnet subagent, one reader, no agreement statistic | F153 |
| `preplanned_transition_fraction` | not computed | computed per held-out instance x method (part 2 §5.9) | F155 |
| L4 donors | PDU-3 in all runs | r3 used the ISRU plant's power ORU (energized, non-critical), granted | part 1a, part 2 |

## Pending (as of 2026-09-30, 22:50 CST)

1. **Ablation live runs: not used (user decision 2026-09-30).** The ablations are reported from the offline
   stages only (part 4 sections before "Stage 3"; F150, F153).
2. ~~Re-authoring live validation~~: closed 2026-09-30, all 8 cases pass live (F156, F159, part 5 §A.9).
3. ~~Preregistered `preplanned_transition_fraction`~~: computed offline 2026-09-30 (user decision), part 2 §5.9, F155.
4. Real LunarBot hardware demonstration (research_content §5.8): **dropped by the user on 2026-09-30**; future work.

## Writing guidance for the manuscript

- Framing (the user's direction): trustworthy AI in space robotics. A foundation model is embedded in the space-robot
  mission workflow to raise autonomy while the runtime keeps the established engineering disciplines (authoritative
  facts, independent verification, authority boundaries, FDIR-style detection and escalation, reconstructable traces).
  The harness components are trust mechanisms: when something goes wrong they, not the model, contain the consequence.
  The classical methods are not naive scripts; the runtime inherits their disciplines. Never frame the work as "an LLM
  calling tools" or as a coding agent for a robot.
- Names: "the proposed runtime" (tables: Ours), "PLEXIL", "EUROPA\,$\rightarrow$\,PLEXIL", "mission control",
  "covered", "held-out". Engineers were fresh Claude Opus 5.5 sessions, not humans.
- Fixes found during a campaign were applied for every method, recorded in the findings, and folded into that
  experiment's results (only the affected runs rerun); they are not reported as a separate round.
- Report null results and costs of the proposed runtime in the paper's own voice (slower missions, less systematic
  search, a costly misreading, the latency upper bound, small n, one simulated site, author-designed held-out cases).
- Existing drafts in `paper/sections/` (results.tex, problem.tex, method.tex, setup.tex, CITATIONS_TODO.md) already
  follow this report; their numbers were audited against it on 2026-09-30. `\TBD{}` marks results not collected.
- Completed after that audit, not yet in the drafts: the re-authoring study's final table (part 5 §A.9: all 8 cases
  pass live), the preregistered `preplanned_transition_fraction` (part 2 §5.9), the community-standard metrics and the
  glossary of every measure (part 6; post hoc, choose at writing time), the 13 textured 1x mission videos (F158;
  `artifacts/figures/exp1b/video_1x/`). Nothing experimental is pending.
