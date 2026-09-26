"""One run as a swimlane on mission time, with the Earth-visibility window shaded -- heldout_design §8's figure.

    openral/.venv/bin/python experiments/video/swimlane.py <run dir> <out stem>     (writes <stem>.pdf and <stem>.png)

Every mark is read from the run's own record, the same for every method where the record is shared:
- navigation / manipulation: the capability boundary's call windows (`capability_server.log`, `sim_t_start`/`sim_t_end`,
  the same windows `evaluation/interaction.py` measures), coloured by the call's own success;
- operator exchanges: mission control's log (`operator/events.jsonl`): request sent, the decision time, answer
  delivered, and any message the link queued;
- deliberation: Ours' reasoner steps (`ours/events.jsonl`, step started -> call proposed), EUROPA's solves (host
  `events.jsonl`, via `europa_timeline_from_logs.py`); PLEXIL's plan is fixed before the run, so its lane is empty;
- observation queries and guard holds: Ours' `events.jsonl` (the baselines have neither);
- the Earth window: `space_context/profiles/earth_link.json` at the research-repo revision in the run's manifest --
  the profile the run ran under, not today's.
Mission time is the simulator clock (`space_context/link.py`), so x is `sim_t` throughout.
"""
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from europa_timeline_from_logs import timeline as europa_timeline  # noqa: E402
from sim_clock import earth_profile, manifest as run_manifest  # noqa: E402

NAV = {"navigate_to_pose", "navigate_to_feature", "dock_at_feature", "dock_to_pose", "move_base_delta", "approach_target"}
LANES = ["deliberation", "navigation", "manipulation", "observation queries", "operator exchanges", "guard holds"]
METHOD = {"ours": "Ours", "plexil": "PLEXIL", "europa_plexil": "EUROPA → PLEXIL"}
_CAP_RE = re.compile(r"\[space_capability_server\]: CAPABILITY (\{.*\})\s*$")

BLUE, RED, ORANGE, YELLOW, AQUA, GREY = "#2a78d6", "#e34948", "#eb6834", "#eda100", "#1baf7a", "#9a9993"
INK, MUTED = "#0b0b0b", "#52514e"


def calls(run: Path) -> list[dict]:
    return [json.loads(m[1]) for m in map(_CAP_RE.search, (run / "capability_server.log").read_text(errors="replace").splitlines()) if m]


def main(run_dir: str, stem: str) -> None:
    run = Path(run_dir)
    manifest = run_manifest(run)
    method = manifest["method"]
    los = earth_profile(run)["los_after_start_s"]
    ops = [json.loads(line) for line in (run / "operator" / "events.jsonl").read_text().splitlines()] \
        if (run / "operator" / "events.jsonl").exists() else []
    cs = calls(run)

    bars = {k: [] for k in LANES}   # (start, end, colour, label, hatch, where the label goes: in / above / beside)
    ticks = {k: [] for k in LANES}  # (t, colour, marker, label, where: right / below)
    for c in cs:
        lane = "navigation" if c["capability"] in NAV else "manipulation"
        bars[lane].append((c["sim_t_start"], c["sim_t_end"], BLUE if c["success"] else RED,
                           "" if lane == "navigation" else c["capability"], None, "in"))
    end = max(c["sim_t_end"] for c in cs)

    if method == "ours":
        ev = [json.loads(line) for line in (run / "ours" / "events.jsonl").read_text().splitlines()]
        end = max(end, ev[-1]["sim_t"])
        started, proposed, held = None, None, {}
        for e in ev:
            k = e["kind"]
            if k == "reasoner_step_started":
                started = e["sim_t"]
            elif k in ("tool_proposed", "reasoner_step_failed"):
                bars["deliberation"].append((started, e["sim_t"], GREY, "", None, ""))
                proposed = e["sim_t"]
            elif k == "query_answered":
                if e["query"] == "observe":
                    bars["observation queries"].append((proposed, e["sim_t"], AQUA, "", None, ""))
                else:
                    ticks["observation queries"].append((e["sim_t"], AQUA, "|", "", ""))
            elif k == "approval_pending":
                held.setdefault((e["capability"], e["target"]), e["sim_t"])
            elif k == "approval_granted":
                t0 = held.pop((e["capability"], e["target"]))
                bars["guard holds"].append((t0, e["sim_t"], YELLOW, f"{e['capability']} {e['target']} held \u2192 granted", None, "beside"))
        for (cap, target), t0 in held.items():
            bars["guard holds"].append((t0, end, YELLOW, f"{cap} {target} held, not granted", None, "beside"))
    elif method == "europa_plexil":
        for e in europa_timeline(run):
            if e["kind"] == "plan":
                ticks["deliberation"].append((e["sim_t"], GREY, "D", "", ""))

    starts = {e["interaction_id"]: e for e in ops if e["kind"] == "interaction_start"}
    for e in ops:
        if e["kind"] == "interaction_start":
            ticks["operator exchanges"].append((e["sent_mission_t"], INK, ">", "", ""))
        elif e["kind"] == "interaction_end":
            s = starts[e["interaction_id"]]
            bars["operator exchanges"].append((s["mission_t"], e["mission_t"], ORANGE,
                                               f"{s['type'].replace('_', ' ')} sent {s['sent_mission_t']:.0f} s; mission control decides "
                                               f"({e['mission_t'] - s['mission_t']:.0f} s) → {e['outcome']}", "////", "above"))
        elif e["kind"] == "reply_delivered":
            ticks["operator exchanges"].append((e["mission_t"], INK, "<", f"delivered {e['mission_t']:.0f} s", "right"))
        elif e["kind"] == "link_queued":
            ticks["operator exchanges"].append((e["mission_t"], RED, "x", f"{e['type'].replace('_', ' ')} at {e['mission_t']:.0f} s queued: {e['why']}", "below"))
        end = max(end, e["mission_t"])

    x1 = end * 1.03
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.axvspan(0, min(los, x1), color="#eef4fb", zorder=0, lw=0)
    if los < x1:
        ax.axvspan(los, x1, facecolor="#e6e5e1", hatch="\\\\\\", edgecolor="#cfcdc7", zorder=0, lw=0)
        ax.axvline(los, color=MUTED, lw=1, zorder=1)
        ax.text(los - x1 * 0.006, -0.75, f"Earth-set {los:.0f} s", ha="right", va="bottom", fontsize=7, color=INK)
        ax.text(los / 2, -0.75, "Earth visible", ha="center", va="bottom", fontsize=7, color=MUTED)
        ax.text(los + x1 * 0.006, -0.75, "Earth below horizon", ha="left", va="bottom", fontsize=7, color=MUTED)
    else:
        ax.text(x1 / 2, -0.75, f"Earth visible for the whole run (this run's profile: Earth-set at {los:.0f} s)",
                ha="center", va="bottom", fontsize=7, color=MUTED)

    pad = x1 * 0.008
    for i, lane in enumerate(LANES):
        for t0, t1, colour, label, hatch, where in bars[lane]:
            ax.barh(i, max(t1 - t0, x1 * 0.0015), left=t0, height=0.5, color=colour, hatch=hatch, edgecolor="white" if hatch else colour,
                    lw=0, zorder=3)
            if where == "in" and t1 - t0 > x1 * 0.009 * len(label):
                ax.text((t0 + t1) / 2, i, label, ha="center", va="center", fontsize=6, color="white", zorder=4)
            elif where in ("in", "above"):
                ax.text((t0 + t1) / 2, i - 0.4, label, ha="center", va="center", fontsize=6, color=INK, zorder=4)
            elif where == "beside":
                right = t1 < 0.6 * x1
                ax.text(t1 + pad if right else t0 - pad, i, label, ha="left" if right else "right", va="center", fontsize=6,
                        color=INK, zorder=4)
        for t, colour, marker, label, where in ticks[lane]:
            ax.plot([t], [i], marker=marker, ms=6 if marker != "|" else 9, color=colour, mew=1.4, zorder=5, ls="none")
            if where == "right":
                ax.text(t + pad, i, label, ha="left", va="center", fontsize=6, color=INK, zorder=4)
            elif where == "below":
                right = t < 0.6 * x1
                ax.text(t if right else t + pad, i + 0.4, label, ha="left" if right else "right", va="center", fontsize=6,
                        color=INK, zorder=4)
        if not bars[lane] and not ticks[lane]:
            ax.text(x1 * 0.01, i, "none in this method's record", ha="left", va="center", fontsize=6, color=MUTED, style="italic")

    ax.set_xlim(0, x1)
    ax.set_ylim(len(LANES) - 0.4, -0.95)
    ax.set_yticks(range(len(LANES)), LANES, fontsize=7, color=INK)
    ax.tick_params(axis="x", labelsize=7, colors=MUTED)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("mission time (simulator clock), s", fontsize=7, color=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.grid(axis="x", color="#e1e0d9", lw=0.5, zorder=0)
    v = manifest["mission_verdict"]
    n_req = sum(e["kind"] == "interaction_start" and e["type"] == "request_operator" for e in ops)
    what = f"faulted unit {v['faulted_unit']}" if "faulted_unit" in v else f"{v['cargo']} to {v['destination']}"
    fig.suptitle(f"{METHOD[method]} \u2014 {manifest['run_id']}\n{v['scenario']}, {what}, "
                 f"{'success' if v['success'] else 'failure'}; {len(cs)} capability calls, {n_req} operator request(s)",
                 x=0.01, ha="left", fontsize=7.5, color=INK, linespacing=1.4)
    key = [Patch(color=BLUE, label="call succeeded"), Patch(color=RED, label="call failed"),
           Patch(color=GREY, label="reasoner step / planner solve"), Patch(color=AQUA, label="observe (camera + VLM)"),
           Line2D([], [], color=AQUA, marker="|", ls="none", ms=8, mew=1.4, label="state query"),
           Patch(facecolor=ORANGE, hatch="////", edgecolor="white", label="mission control's decision"),
           Patch(color=YELLOW, label="call held by the guard")]
    fig.legend(handles=key, loc="lower center", ncol=7, fontsize=5.5, frameon=False, handlelength=1.4, columnspacing=1.0)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(f"{stem}.{ext}", dpi=200)
    print(f"wrote {stem}.pdf/.png: {METHOD[method]}, 0-{end:.0f} s, Earth-set {los:.0f} s, "
          + ", ".join(f"{k}: {len(bars[k])}+{len(ticks[k])}" for k in LANES))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
