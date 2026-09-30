"""Engineering-effort metrics under community names (user decision 2026-09-30), for Experiment II (extension by the new
scan capability) and the re-authoring study (each baseline x held-out case): code churn and relative churn (Nagappan &
Ball 2005), planning-model size before -> after (the IPC / KEPS convention of counting a domain's elements), from git.
Engineering time and validation runs come from experiments/exp2/tables.py and experiments/reauthoring/cost_table.py.

    python3 evaluation/engineering_metrics.py > artifacts/eval/engineering_metrics.md

A method's source artifacts: Ours -- contracts.yaml, prompts/ours, space_runtime, configs/space_runtime.yaml; PLEXIL --
the .ple plans and the capability adapter (it carries new Lookups / Commands), not the generated .plx; EUROPA -> PLEXIL --
the NDDL domain, host, planner, configs, its PLEXIL dispatcher; plus the baselines' shared item table. Offline tests and
stand-ins (offline_check.py, sim_boundary.py) are counted separately.
"""
import re
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parents[1]
SRC = {"ours": ["openral_ext/capability_server/contracts.yaml", "prompts/ours", "space_runtime", "configs/space_runtime.yaml"],
       "plexil": ["baselines/plexil/plans", "ros/plexil_capability_adapter/src", "baselines/item_descriptions.json"],
       "europa_plexil": ["baselines/europa/domain", "baselines/europa/host.py", "baselines/europa/planner", "baselines/europa/config",
                         "baselines/europa/plexil", "baselines/item_descriptions.json"]}
TESTS = {"ours": [], "plexil": ["baselines/plexil/scripts/offline_check.py"], "europa_plexil": ["baselines/europa/sim_boundary.py"]}
SKIP = re.compile(r"\.plx$")


def git(*a):
    return subprocess.run(["git", "-C", str(R), *a], capture_output=True, text=True).stdout


def numstat(base, head, paths):
    rows = [l.split("\t") for l in git("diff", "--numstat", base, head, "--", *paths).splitlines() if l]
    rows = [r for r in rows if r[0] != "-" and not SKIP.search(r[2])]
    return len(rows), sum(int(r[0]) for r in rows), sum(int(r[1]) for r in rows)


def files(ref, paths):
    return [f for f in git("ls-tree", "-r", "--name-only", ref, "--", *paths).splitlines() if not SKIP.search(f)]


def loc(ref, paths):
    return sum(len(git("show", f"{ref}:{f}").splitlines()) for f in files(ref, paths))


def size(method, ref):
    """The planning model's elements at a ref."""
    if method == "plexil":
        ple = "\n".join(git("show", f"{ref}:{f}") for f in files(ref, ["baselines/plexil/plans"]) if f.endswith(".ple"))
        ple = re.sub(r"//.*", "", ple)
        return {"library nodes": sum(1 for f in files(ref, ["baselines/plexil/plans/lib"]) if f.endswith(".ple")),
                "nodes": len(re.findall(r"^\s*\w+\s*:\s*(?:\{|Sequence|UncheckedSequence|Try|Concurrence|CheckedSequence)", ple, re.M)),
                "if branches": len(re.findall(r"\bif\s*\(", ple)),
                "command calls": len(re.findall(r"\b(?:navigate_to_feature|dock_at_feature|navigate_to_pose|arm_ready|stow|pick|place|press|scan_label|Request\w+)\s*\(", ple)),
                "lookups": len(re.findall(r"\bLookup\s*\(", ple))}
    if method == "europa_plexil":
        nddl = "\n".join(git("show", f"{ref}:{f}") for f in files(ref, ["baselines/europa/domain"]) if f.endswith(".nddl"))
        nddl = re.sub(r"//.*", "", nddl)
        return {"classes": len(re.findall(r"^\s*class\s+\w+", nddl, re.M)),
                "timelines": len(re.findall(r"^\s*class\s+\w+\s+extends\s+Timeline", nddl, re.M)),
                "predicates": len(re.findall(r"\bpredicate\s+\w+", nddl)),
                "actions": len(re.findall(r"\baction\s+\w+", nddl)),
                "compatibility rules": len(re.findall(r"^\s*\w+::\w+\s*$", nddl, re.M))}
    c = git("show", f"{ref}:openral_ext/capability_server/contracts.yaml")
    sec, n = None, {"effect contracts": 0, "query contracts": 0}
    for line in c.splitlines():
        if re.match(r"^(effects|queries):", line):
            sec = line.split(":")[0]
        elif re.match(r"^\S", line):
            sec = None
        elif sec and re.match(r"^  [a-z_]+:\s*$", line):
            n["effect contracts" if sec == "effects" else "query contracts"] += 1
    return n | {"prompt lines": sum(len(git("show", f"{ref}:{f}").splitlines()) for f in files(ref, ["prompts/ours"]))}


def row(label, method, base, head):
    nf, a, d = numstat(base, head, SRC[method])
    tf, ta, td = numstat(base, head, TESTS[method]) if TESTS[method] else (0, 0, 0)
    base_loc = loc(base, SRC[method])
    s0, s1 = size(method, base), size(method, head)
    delta = ", ".join(f"{k} {s0[k]}→{s1[k]}" for k in s0 if s0[k] != s1[k]) or "none"
    print(f"| {label} | {nf} | +{a}/-{d} | {a + d} | {base_loc} | {(a + d) / base_loc:.3f} | {tf} files +{ta}/-{td} | {delta} |")


HEAD = "| study / method / case | source files changed | lines | churn (added + deleted) | source size before (lines) | relative churn | offline tests / stand-ins | planning-model size before → after |\n|---|---|---|---|---|---|---|---|"
print("# Engineering-effort metrics (community names), computed from git\n")
print("Generated by `evaluation/engineering_metrics.py`; rule in its docstring. Generated .plx excluded.\n")
print("## Experiment II: adding the scan capability\n")
print(HEAD)
for m, base, head in (("ours", "exp2-base", "exp2-ours"), ("plexil", "exp2-base-plexil", "exp2-plexil"),
                      ("europa_plexil", "exp2-base-europa", "exp2-europa_plexil")):
    row({"ours": "Ours", "plexil": "PLEXIL", "europa_plexil": "EUROPA→PLEXIL"}[m], m, base, head)
print("\n## Re-authoring study: each baseline x held-out case (exp1b → reauth/<baseline>-<case>)\n")
print(HEAD)
for m, b in (("plexil", "plexil"), ("europa_plexil", "europa")):
    for case in ("l2a", "l2b", "l3", "l4"):
        row(f"{'PLEXIL' if m == 'plexil' else 'EUROPA→PLEXIL'} {case.upper()}", m, "exp1b", f"reauth/{b}-{case}")
print("\nPlanning-model size at exp1b (the frozen baselines):", {m: size(m, "exp1b") for m in ("plexil", "europa_plexil")})
