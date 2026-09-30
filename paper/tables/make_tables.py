"""The paper's tables, rendered from the generated result tables (never typed by hand): Experiment I
(artifacts/eval/exp1b/tables.md, from `evaluation.tables` over the evaluator rows) and Experiment II
(artifacts/eval/exp2/tables.md, from experiments/exp2/tables.py). Writes paper/tables/*.tex.

    python3 paper/tables/make_tables.py
"""
from pathlib import Path

R = Path(__file__).resolve().parents[2]
OUT = R / "paper/tables"
NAME = {"ours": "Ours", "plexil": "PLEXIL", "europa_plexil": "EUROPA\\,$\\rightarrow$\\,PLEXIL"}
COV = {"covered": "covered", "held_out": "held-out"}


def md_tables(path: Path) -> list[list[dict]]:
    """Every markdown table in the file, as a list of {header: cell} rows."""
    tables, cur, head = [], None, None
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            cur = head = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:  # a repeated column name keeps its place: the second "x" is "x#2"
            head, cur = [c if c not in cells[:i] else f"{c}#{cells[:i].count(c) + 1}" for i, c in enumerate(cells)], []
            tables.append(cur)
        elif set(line.replace("|", "").strip()) <= {"-"}:
            continue
        else:
            cur.append(dict(zip(head, cells)))
    return tables


def write(name: str, cols: str, header: str, lines: list[str]) -> None:
    (OUT / f"{name}.tex").write_text("\\begin{tabular}{" + cols + "}\n\\toprule\n" + header + " \\\\\n\\midrule\n"
                                     + " \\\\\n".join(lines) + " \\\\\n\\bottomrule\n\\end{tabular}\n")


exp1 = md_tables(R / "artifacts/eval/exp1b/tables.md")
success, _, violations, independence = exp1[0], exp1[1], exp1[2], exp1[3]
order = ("ours", "plexil", "europa_plexil")

# Table: Experiment I, human independence (ALFUS) per method and coverage
lines = []
for m in order:
    for c in ("covered", "held_out"):
        r = next(x for x in independence if x["method"] == m and x["coverage"] == c)
        k = sum(int(x["successes"]) for x in success if x["method"] == m and x["coverage"] == c)
        n = sum(int(x["n"]) for x in success if x["method"] == m and x["coverage"] == c)
        req = r["requests: authorization / authority check / new procedure / information"].split(" / ")
        lines.append(f"{NAME[m] if c == 'covered' else ''} & {COV[c]} & {k}/{n} & {r['human intervention ratio, median [95% CI]']} & "
                     f"{req[0]} / {req[2]} / {req[3]} & {r['highest ALFUS level, runs'].replace('_', ' ')} & "
                     f"{r['ground re-authoring']} & {r['idle waiting, median [95% CI]']} & "
                     f"{r['longest autonomous stretch (s), median [95% CI]']}")
write("exp1_independence", "llrrcccrr",
      "method & coverage & success & HIR & requests A / N / I & highest level (runs) & re-authoring & idle & stretch (s)", lines)

# Table: Experiment I, constraint violations counted by the external evaluator
lines = []
for m in order:
    for c in ("covered", "held_out"):
        r = next(x for x in violations if x["method"] == m and x["coverage"] == c)
        lines.append(f"{NAME[m] if c == 'covered' else ''} & {COV[c]} & {r['n']} & {r['unintended contact']} & "
                     f"{r['dropped item']} & {r['collateral change']} & {r['execution during fault']} & {r['removal without approval']}")
write("exp1_violations", "llrrrrrr",
      "method & coverage & runs & unintended contact & dropped item & collateral change & execution in fault & removal w/o approval",
      lines)

# Table: Experiment II, engineering effort and held-out success
exp2 = md_tables(R / "artifacts/eval/exp2/tables.md")
eng, cases = exp2[0], exp2[1]
lines = []
for m in order:
    r = next(x for x in eng if x["method"] == m)
    after = [x["after the extension"] for x in cases if x["method"] == m]
    k, n = sum(int(a.split("/")[0]) for a in after), sum(int(a.split("/")[1]) for a in after)
    kb = sum(int(x["before the extension"].split("/")[0]) for x in cases if x["method"] == m)
    nb = sum(int(x["before the extension"].split("/")[1]) for x in cases if x["method"] == m)
    lines.append(f"{NAME[m]} & {r['active (min)']} & {r['waiting on own validation runs (min)']} & {r['other work (min)']} & "
                 f"{r['validation runs to G3 PASS']} & {r['lines (+/-)']} & {r['lines (+/-)#2']} & {kb}/{nb} & {k}/{n}")
write("exp2_engineering", "lrrrrrrrr",
      "method & active (min) & waiting on validation (min) & other work (min) & validation runs & mission artifacts (+/$-$) & "
      "supporting files (+/$-$) & held-out before & held-out after", lines)
print("wrote", sorted(p.name for p in OUT.glob("*.tex")))
