"""Figure: autonomous mission success against novelty level, Experiment I (exp1b), the three methods.

Read from the evaluator's rows (artifacts/eval/exp1b/rows, `python3 -m evaluation.rows`); Wilson 95 % intervals as in
evaluation/tables.py (preregistration §4). Writes paper/figures/success_by_level.{pdf,png}.

    python3 paper/figures/success_by_level.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))
from evaluation.tables import LEVELS, wilson_ci  # noqa: E402

# categorical slots 1-3 of the dataviz reference palette, validated (CVD, normal-vision floor); markers and direct labels
# carry identity as well, so print and colour-blind readers do not depend on hue
METHODS = [("ours", "Ours", "#2a78d6", "o"), ("plexil", "PLEXIL", "#eb6834", "s"),
           ("europa_plexil", "EUROPA→PLEXIL", "#1baf7a", "^")]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"

rows = [json.loads(p.read_text()) for p in sorted((R / "artifacts/eval/exp1b/rows").glob("*.json"))]
fig, ax = plt.subplots(figsize=(3.5, 2.5))  # one journal column
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
x = range(len(LEVELS))
ax.axvspan(1.5, len(LEVELS) - 0.5, color="#f0efec", zorder=0, lw=0)
ax.text(0.5, 1.1, "covered", ha="center", va="center", fontsize=6.5, color=MUTED)
ax.text(3.5, 1.1, "held-out", ha="center", va="center", fontsize=6.5, color=MUTED)
for k, (m, label, colour, marker) in enumerate(METHODS):
    dx = (k - 1) * 0.14
    pts = []
    for i, level in enumerate(LEVELS):
        grp = [r for r in rows if r["method"] == m and r["level"] == level and r["autonomous_mission_success"] is not None]
        succ = sum(r["autonomous_mission_success"] for r in grp)
        p, lo, hi = wilson_ci(succ, len(grp))
        pts.append((i + dx, p))
        ax.plot([i + dx] * 2, [lo, hi], color=colour, lw=0.9, alpha=0.8, zorder=2, solid_capstyle="round")
        ax.plot(i + dx, p, marker=marker, ms=5, color=colour, mec=SURFACE, mew=1.0, zorder=3, ls="none",
                label=label if i == 0 else None)
    ax.plot(*zip(*pts), color=colour, lw=1.0, alpha=0.6, zorder=1)
    ax.text(len(LEVELS) - 0.45, {"ours": 1.0, "plexil": 0.15, "europa_plexil": 0.04}[m], label,
            ha="left", va="center", fontsize=6.5, color=INK)
ax.set_xticks(list(x), LEVELS, fontsize=7, color=INK)
ax.set_xlim(-0.5, len(LEVELS) + 1.1)
ax.set_ylim(-0.06, 1.16)
ax.set_yticks([0, 0.5, 1], ["0", "0.5", "1"], fontsize=7, color=INK)
ax.set_ylabel("autonomous mission success", fontsize=7, color=INK)
ax.set_xlabel("novelty level (what the frozen baseline model lacks)", fontsize=7, color=INK)
ax.grid(axis="y", color=GRID, lw=0.6)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color(MUTED)
ax.tick_params(colors=MUTED, length=2)
ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, fontsize=6.5, frameon=False, handletextpad=0.3,
          columnspacing=1.0, labelcolor=INK)
fig.tight_layout(pad=0.3)
out = R / "paper/figures/success_by_level"
fig.savefig(out.with_suffix(".pdf"))
fig.savefig(out.with_suffix(".png"), dpi=300)
print("wrote", out.with_suffix(".pdf"))
