# Space Robotics Agent Harness

Research code for a trustworthy, space-native, mission-intent-driven agentic
runtime for long-horizon lunar robotic operations.

- Research framing and paper structure: `AGENT/research_content.md`
- Implementation and experiment plan: `AGENT/execution_plan.md`
- Current work: `AGENT/todo.md`, `AGENT/handoff.md`

## Layout

| Path | Contents |
|---|---|
| `space_runtime/` | Authoritative mission state, reducer, context builder, decision layer, verification (plan §4.1) |
| `space_context/` | Lunar operational context service — clock, geometry, illumination, link/contact state, resources (§4.2) |
| `openral_ext/` | Adapters and bridge packages against OpenRAL; no upstream forks (§5.3) |
| `srb_ext/` | Mission scenes and ROS adapters composed from Space Robotics Bench (§6.3) |
| `network/` | Link emulation driven by the contact profile (§7.4) |
| `missions/` | Mission specifications and verification mappings (§10.4) |
| `experiments/` | One configurable runner for all baselines (§12) |
| `evaluation/` | Metric extraction and analysis over run artifacts (§14) |
| `configs/`, `scripts/`, `docs/`, `artifacts/` | Configuration, tooling, notes, run outputs |

## Upstream

| Project | Role | Tracking |
|---|---|---|
| [OpenRAL](https://github.com/DsslRobot/openral) | Physical-agent runtime — reasoner, rSkill dispatch, world state, safety | git submodule at `openral/` |
| [Space Robotics Bench](https://github.com/DsslRobot/space_robotics_bench) | Lunar simulation on Isaac Sim / Isaac Lab | **not tracked here** — externally managed; pin recorded in `docs/upstream_pins.md` |

## Environment

Ubuntu 22.04 · ROS 2 Humble · Python 3.10 (OpenRAL side) · Isaac Sim 5.1 with
Python 3.11 (SRB side, separate process, meets OpenRAL only on the DDS bus).

The reasoning behind that target is `docs/upstream_pins.md` — read it before
changing any version pin.
