# OpenRAL integration notes — pinned revision

Traced against the `feat/py310-humble` fork (openral `fa7f445`, off upstream
`4700c7a`). Source paths and line numbers below; re-check after any rebase.
This is implementation documentation (execution_plan §5.1), not paper content.

---

## 1. The reasoner → skill → safety path

### 1.1 `ReasonerCore.tick` (transport-agnostic)

`python/reasoner/src/openral_reasoner/core.py` (623 lines). No rclpy import —
fully unit-testable. Three-phase split (`prepare_tick` → `run_prepared_llm` →
`finish_tick`), because the ROS node runs the LLM call on a worker thread so a
blocking `select_tool` never starves the rclpy executor (issue #21).

`prepare_tick` runs four suppression gates, in order, **before** any LLM call
or OTel span (`core.py:337-455`):

1. `min_interval` — hard 0.1 s floor between ticks.
2. `retry_cap_hold` — after a `retry_cap` trip, held at the same `renderer.seq`
   so an unchanged context never re-pays for an LLM call that would repeat the
   capped call.
3. `mission_finished` — a terminal `MissionState` stops ticking even if
   world-state keeps changing `seq`.
4. `heartbeat_idle` — unchanged `seq` and no in-flight skill → suppressed
   (skipped while a skill is in flight, since a tick is the only chance to
   poll `query_task_progress` mid-execution).

`finish_tick` applies the **retry-cap ladder**: consecutive identical calls
(full argument payload minus `rationale`, JSON-canonicalised —
`_call_identity`, `core.py:130`) are capped at `retry_cap_per_kind` (default 3,
"matches CLAUDE.md §7.6"). Read-only search tools (`recall_object`,
`resolve_place`, `locate_in_view`) and `wait` are exempt — they carry their own
bounded budgets and must reach an explicit human-handoff, never a silent hold.

### 1.2 `ReasonerToolCall` — the discriminated union

`python/core/src/openral_core/schemas.py:11304`. Thirteen variants, one
`Literal["..."]` discriminator (`tool`) each, all `frozen=True,
extra="forbid"` so the LLM cannot smuggle ad-hoc fields:

| Variant | Dispatch target | Authority |
|---|---|---|
| `ExecuteRskillTool` | action goal → `/openral/execute_rskill` | **indirect actuation** — see §1.3 |
| `LifecycleTransitionTool` | `<node>/change_state` service | reconfigure a peer node |
| `ReloadGstPipelineTool` | *(planned — see §4)* | — |
| `EmitPromptTool` | publish on `target_topic` | none (re-prompt) |
| `RecallObjectTool` / `ResolvePlaceTool` | spatial-memory query | read-only |
| `LocateInViewTool` | `LocateInView.srv` | read-only |
| `QuerySceneTool` | `QueryScene.srv` | read-only |
| `QueryTaskProgressTool` | `QueryTaskProgress.srv` | read-only |
| `MemoryWriteTool` / `MemorySearchTool` | reasoner memory archive | read-only / write memory only |
| `DecomposeMissionTool` | mutates `MissionState` (§1.4) | edits the task ledger only, never actuates |
| `WaitTool` | none | deliberate no-op |

Class docstring (`schemas.py:10774`): *"the reasoner never publishes
`ActionChunk` itself... `ExecuteRskillTool` is indirect — it sends an action
goal to `rskill_runner_node` which in turn produces the chunk and gates it
through `safety_node`."* This is upstream's own statement of the actuation
boundary the plan (§4.8, §10.1) requires us to preserve.

### 1.3 `ExecuteRskillTool` → `/openral/execute_rskill` → safety

Dispatch: `packages/openral_reasoner_ros/openral_reasoner_ros/reasoner_node.py`
(5115 lines, single `ReasonerNode(LifecycleNode)` class).

`_handle_tick_result` (line 2769) is the seam between a completed tick and
dispatch — a plain method call, no indirection:

```python
self._dispatched_calls.append(result.tool_call)
self._dispatch(result.tool_call, traceparent=result.traceparent)
```

`_dispatch` (line 2803) is a flat `isinstance` table routing each of the 13
variants to its own `_dispatch_*` method. `ExecuteRskillTool` →
`_dispatch_execute_rskill` (line 4222) → `_send_execute_rskill_goal` (line
4384), which sends the `ExecuteRskill.Goal` action to
`/openral/execute_rskill`.

**`_dispatch_execute_rskill` already refuses several classes of mission-invalid
proposal before the goal is sent** — this matters directly for plan §5.4.5:

- **Grounding gate**: refuses a collective target ("put ALL the objects...")
  and instead self-prompts an enumeration invite. No attempt recorded.
- **Busy gate**: refuses a second dispatch while a goal is already in flight
  (the runner serves one goal at a time) — logged, fed back to the LLM as a
  reflection, no attempt recorded.
- **VLA/VRAM-fit gate** (`_refuse_unfittable_vla`): refuses a dispatch that
  cannot co-reside on the GPU with its paired reward model.
- **Server-availability check**: a short, non-blocking
  `wait_for_server` probe; if `/openral/execute_rskill` is not on the graph,
  emits a `KIND_CONTROLLER` `FailureTrigger` instead of hanging the tick.

Only after these pass does the node latch a busy flag, arm a dispatch
watchdog, evict VRAM-lifecycle peers if needed, and send the goal.

Execution path from there (`packages/openral_rskill_ros/rskill_runner_node.py`,
3455 lines): the resolved rSkill runs its own step loop, and each waypoint is
replayed through `self._hal.send_action` onto **`/openral/candidate_action`**
— checked by the safety layer every step — which republishes onto
**`/openral/safe_action`** for the HAL/controller to actually execute. So the
full chunk path is:

```
ExecuteRskillTool
  → /openral/execute_rskill (action)
    → rskill_runner_node (F1) — resolves + steps the rSkill
      → /openral/candidate_action  (every step)
        → safety layer  — §2 below
          → /openral/safe_action
            → HAL / ros2_control
```

### 1.4 `MissionState` — the existing task ledger

`python/reasoner/src/openral_reasoner/mission.py` (602 lines). Plain
dataclasses, **no rclpy, no Pydantic** — "reasoner-internal... fully
unit-testable" (module docstring). This is the sequential task ledger the
plan (§1.1) says already exists.

- `TaskState`: `task_id`, `text`, `status` (`pending → active → verifying →
  done|abandoned`, terminal states never re-queued), `attempts`,
  `last_rskill_id`, `last_trace_id`, `last_verdict`, `depth`.
- `MissionState`: ordered queue, **at most one active task**. Mutators
  (`record_attempt`, `mark_verifying`, `complete_active`, `abandon_active`,
  `rearm_active`, `subdivide_active`) all return the newly-active task (or
  `None` when finished) so the caller re-injects the next goal.
- `DecomposeMissionTool` (schemas.py:11241) is the typed write path: *populate*
  (build a fresh queue, only before the mission has started) or *subdivide*
  (flat-splice a blocked task's children in place, bounded by
  `DEFAULT_MAX_SUBDIVIDE_DEPTH = 2` — past the bound the node hands off
  instead of subdividing forever).

**Verification is reward-gated, not LLM self-report.** `evaluate_task_verdict`
(`mission.py:156`) is a pure function consuming the `QueryTaskProgress.srv`
response (Robometer reward-model `progress`/`success` heads, gated on
*progress* — empirically cleaner-separated than *success*):

| `progress_now` band | Verdict | Meaning |
|---|---|---|
| `>= success_threshold` (0.8) | `complete` | auto-pass |
| `[check_floor, success_threshold)` (0.5–0.8) | `vlm_check` | ambiguous — a `describe_image`/VLM call adjudicates |
| `< check_floor`, attempts < max | `retry` | keep active |
| `< check_floor`, attempts >= max (default 3) | `abandon` | ladder exhausted → human-handoff |

This already satisfies a meaningful slice of plan §4.8's "verifier/observer"
role and §14.3's "incorrect declarations of task completion" concern — our
verification layer should **add** evidence sources this doesn't cover
(communication/resource/authority conditions), not rebuild task-completion
verification from scratch.

**Persistence exists, but is narrower than what plan §4.1 asks for.**
`python/reasoner/src/openral_reasoner/persistence.py`: `ReasonerLadderState`
(Pydantic, `schema_version`) snapshots `MissionState` + every ladder bound
(subdivide-offered set, collective-decompose nudge counts, locate budget) to a
JSON file, atomically (tmp file + `os.replace`), on every ledger mutation.
Restored at `on_configure` (crash resume) —
`_persist_ladder_state`/`_maybe_restore_ladder_state`
(`reasoner_node.py:1915,1941`). **Gaps relative to plan §4.1**: single-process,
file-based (no distributed reconciliation), carries no space-operational
context, no authority state, no resource/health summary, and no verified-
evidence references beyond `last_verdict`/`last_trace_id` strings. This is the
concrete thing `space_runtime.mission_store` extends — not replaces.

### 1.5 World state

`python/world_state/src/openral_world_state/aggregator.py` —
`WorldStateAggregator`: injectable-callback snapshot producer for joint state,
base pose/twist, EE poses, contact forces, sensor topic refs, detected
objects, **`battery_pct: float | None`**, and per-component `diagnostics`
(`"ok"|"stale"|"error"`, **latched** — once stale, stays stale until a fresh
update arrives, so the reasoner sees it across snapshot boundaries).

`WorldState` schema (`schemas.py:3570`) — the **only** resource/health field is
`battery_pct`. No communication state, no compute-availability state, no
illumination/environmental field, no authority field exist anywhere in this
schema. This is the precise, verified gap `space_context` fills — there is
nothing to duplicate here, only to add alongside.

### 1.6 Read-only query tools

Three services, all under `packages/msgs/srv/`, all documented as read-only,
all already wired to their own `_dispatch_*`/`_on_*_response` pairs in
`reasoner_node.py`:

- `QueryScene.srv` — open-ended scene-state question to a VLM
  (`kind: "vlm"`), dispatch at `reasoner_node.py:3308`.
- `LocateInView.srv` — live open-vocabulary detection ("is X in view now"),
  dispatch at `reasoner_node.py:3175`.
- `QueryTaskProgress.srv` — the Robometer reward-monitor window query behind
  §1.4's verdict evaluation, dispatch at `reasoner_node.py:3391`.

### 1.7 Reasoner provider/model interface

`python/core/src/openral_core/schemas.py:10563` — `ReasonerModel` /
`REASONER_MODELS` (ADR-0088). Curated registry: `id`, `dialect`
(`anthropic`|`openai`), **`hosting`** (`cloud`|`managed_local`|`byo_local`),
`served_model_id`, `default_endpoint`, `auth_required`, `tool_choice`,
`min_gpu_vram_gb`/`required_dtype` for local fit. `OPENRAL_REASONER_MODEL`
selects the model; `OPENRAL_REASONER_ENDPOINT` is the orthogonal location
override (named endpoint or bare URL). `openral doctor` currently reports
`OPENRAL_REASONER_MODEL` unset on this machine.

This `hosting` axis is a genuine head start on plan §4.5's "distributed
reasoner adapter" — location category, endpoint, auth already modeled. Our
work is the overlay: whether the *current mission authority* permits using a
given endpoint, and whether the *current communication state* can reach it —
neither exists here today.

### 1.8 Observability

`python/observability/src/openral_observability/` (`tracing.py`,
`semconv.py`). `start_reasoner_span` opens one OTel span per tick carrying
`reasoner.tick.idx`, `reasoner.tool`, `reasoner.rskill_id`,
`reasoner.suppressed_reason`, `reasoner.error_kind`, `reasoner.llm_s`,
`reasoner.prompt_tokens`, `reasoner.mission_json` (the whole task queue,
stamped even on a suppressed tick). `safety_span` covers the safety boundary
(`safety.kernel` = `"passthrough"` or the C++ kernel's label). rSkill spans
carry per-phase timing (`rskill.inference_ms`, `rskill.safety_ms`,
`rskill.hal_ms`, ...) plus `rskill.reward`/`rskill.terminated`. A
`W3C traceparent` is captured while the tick span is open and threaded through
to the dispatch, so a mission-runtime span can correlate cleanly (plan §4.10)
by attaching to the same trace rather than opening a parallel one.

---

## 2. Safety: shipped vs planned

**Two implementations exist on the identical topic surface**
(`/openral/candidate_action` in, `/openral/safe_action` +
`/openral/estop` + `/openral/failure/*` + `/openral/safety_status` out) — they
are alternatives, not layers; you run one.

- **`openral_safety` (Python, `packages/openral_safety/supervisor_node.py`)**
  — explicitly a "Day-1 passthrough". Module docstring: *"envelope checks are
  deliberately minimal so the C++ kernel that lands later can replace
  internals behind the same topic surface."* Checks: `n_dof` mismatch and
  first-row joint-position limits only. Velocity/force/workspace are
  "stubbed... land when the C++ kernel does."
- **`openral_safety_kernel` (C++, `cpp/openral_safety_kernel/`)** — **shipped
  and the more capable of the two**, confirmed by us: it built cleanly under
  Python 3.10/Humble and, when run, registered on the ROS graph as
  `/openral_safety_kernel`, a live lifecycle node. Its allocation-free
  validator (`validator.hpp`) reports `kForce`, `kWorkspace`, `kController`
  (dim-mismatch / NaN / n_dof-mismatch / envelope-unconfigured /
  invalid-scale sub-kinds); a separate geometric path checks
  self/world collision against a voxel/world model and **fails closed** on an
  unknown or stale link (source comment: *"(unknown-link, or stale) is
  fail-closed: we do not know what the robot is doing"*).

**Conclusion for our work: treat the C++ kernel as the safety boundary to
build against.** It is not "partial/planned" as the plan's caution generically
suggested we verify — it is running, more capable than the Python fallback,
and matches plan §10.1 ("do not weaken safety for convenience").

**Replanning ladder — code-enforced parts vs LLM-guided parts.** The plan
(§0.5) describes retry → param-tweak → substitute-skill → goal-replan →
human-handoff. What's actually code-enforced: the per-identical-call retry
cap (§1.1), the per-task attempts cap feeding `abandon` (§1.4), and the
subdivision-depth cap feeding human-handoff. **"Param-tweak" and
"substitute-skill" are not separately coded rungs** — they are system-prompt
guidance (`tool_use.py:224-226`: *"tweak the goal params, substitute a
different skill, or re-plan the approach — rather than re-issuing the same
call"*) left to the LLM's free choice of the next `rskill_id`/
`goal_params_json`. This is a partial implementation relative to the plan's
description, not a gap in our understanding — it should not be presented as
more code-enforced than it is.

**WAM — planned, not shipped.** `python/wam/src/openral_wam/`: a `Protocol`
seam (`WorldModel`, one method `(WorldState, ActionChunk, horizon) ->
Rollout`) plus `NullWorldModel`, an identity stub. Its own docstring: *"not a
fallback to be silently used in production... replace with a concrete adapter
before relying on the gating signal."* No Cosmos Predict / UnifoLM-WMA-0 /
IRASim adapter exists in this revision — confirmed absent, matching
CLAUDE.md's "v0.3+" framing and the plan's instruction not to design
experiments around a planned component.

**`ReloadGstPipelineTool` — planned.** `_dispatch` (reasoner_node.py:2856)
logs a warning and acknowledges; the F6 sensor-package service IDL it would
call does not exist on disk yet (tracked as GH-126).

---

## 3. Insertion point (plan §3.2)

Plan offered three candidate patterns. Evidence from §1.3 above settles which
is least invasive:

1. **Sidecar mission-decision service** — would require editing
   `_dispatch_execute_rskill` itself to call out before proceeding. That is a
   source change to a private method in a 5115-line upstream file.
2. **Tool-dispatch wrapper (chosen)** — `ReasonerNode` is a plain Python class
   and the dispatch seam is a **plain method call**
   (`self._dispatch(result.tool_call, ...)` in `_handle_tick_result`, no ROS
   indirection). A subclass overriding only `_dispatch_execute_rskill` (and,
   if needed, `_dispatch_lifecycle_transition` — the other variant with real
   physical/configuration effect) can insert the mission-level admissibility
   check before calling `super()._dispatch_execute_rskill(...)`, leaving every
   read-only/mission-editing variant (`_dispatch_spatial_query`,
   `_dispatch_query_scene`, `_dispatch_query_task_progress`,
   `_dispatch_memory_*`, `_dispatch_decompose_mission`, `_dispatch_emit_prompt`)
   completely untouched. `reasoner_node.main()` (line 5091) is a 15-line
   function that only does `configure_observability` →
   `rclpy.init` → `rclpy.spin(ReasonerNode())` → cleanup — trivially
   reimplemented in our own entrypoint spinning our subclass instead, so this
   requires **zero upstream source modification**, only a new
   `openral_ext/reasoner_dispatch_bridge` package.
3. **Existing stable hook** — does not exist today. There is no
   plugin/callback registration point for tool-call dispositioning; `_dispatch`
   is a private, unstable-by-convention method.

**Decision: option 2.** Caveat to carry into Phase E: subclassing a private
method surface is not a public contract — upstream could rename or restructure
`_dispatch_execute_rskill`'s signature or the gates inside it across versions.
Re-verify this seam after every OpenRAL rebase, the same way
`docs/openral_py310_patch.md` is re-verified.

---

## 4. Test suite on this revision

`just test` (`uv run pytest tests/unit/ ...`) on Python 3.10/Humble, commit
`4c1867c`: **5236 passed, 4 failed, 120 skipped, 2 errors** (0 useful signal on
the first attempt — a mass collection failure). Every fix was a genuine 3.10
gap the earlier grep/AST-based scan missed because it only covered `python/`
and `packages/`, not `tools/` or `tests/` — most notably `datetime.UTC`
(3.11+), present in seven places including `reasoner_node.py`'s own
`_memory_now`. Full accounting — what was fixed and, separately, the four
remaining non-passes verified as pre-existing and orthogonal to the
Python-version target — is in `docs/openral_py310_patch.md` §6.
