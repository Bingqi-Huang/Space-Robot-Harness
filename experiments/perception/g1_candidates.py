"""G1 (plan v4 §7): classical grasp candidates on the G0 wrist RGB-D views, scored against the simulator's handle.

For every view: `find_candidates` on the depth image, the numbered candidate image (what the VLM will see), and whether
a correct handle grasp is among the candidates -- a candidate whose part centre lies within `--tol` of the handle neck
point (truth, evaluator-only) and whose closing axis is horizontal (the neck is vertical). Views where the handle is
outside the image or hidden by the gripper are reported separately.

    openral/.venv/bin/python experiments/perception/g1_candidates.py artifacts/perception/g0 [--tol 0.02]
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from openral_rskill.grasp_perception import find_candidates, render_candidates

ap = argparse.ArgumentParser()
ap.add_argument("data", type=Path)
ap.add_argument("--tol", type=float, default=0.02)
a = ap.parse_args()
truth = json.loads((a.data / "truth.json").read_text())
out = a.data / "g1"
out.mkdir(exist_ok=True)
rows = []
for d in sorted(p for p in a.data.iterdir() if (p / "meta.json").exists()):
    meta = json.loads((d / "meta.json").read_text())
    K = np.array(meta["K"]).reshape(3, 3)
    depth = np.load(d / "depth.npy")
    bgr = cv2.imread(str(d / "rgb.png"))
    t0 = time.time()
    cands = find_candidates(depth, K)
    dt = time.time() - t0
    R_bc = np.array(meta["T_base_camera"])[:3, :3]
    up = R_bc.T @ np.array([0.0, 0.0, 1.0])
    item = "spare_oru" if d.name.startswith("oru") else "spare_crate"
    hc = np.array(truth[d.name][item]["handle_camera"])
    u, v = K[0, 0] * hc[0] / hc[2] + K[0, 2], K[1, 1] * hc[1] / hc[2] + K[1, 2]
    in_image = hc[2] > 0 and 0 <= u < meta["width"] and 0 <= v < meta["height"]
    visible = in_image and np.isfinite(depth[int(v), int(u)]) and abs(depth[int(v), int(u)] - hc[2]) < 0.03
    hits = [c.id for c in cands if np.linalg.norm(np.array(c.p_cam) - hc) <= a.tol and abs(np.dot(c.axis_cam, up)) < 0.4]
    near = min((float(np.linalg.norm(np.array(c.p_cam) - hc)) for c in cands), default=None)
    rows.append(dict(view=d.name, n=len(cands), hits=hits, nearest_m=None if near is None else round(near, 3), handle_px=[round(u), round(v)],
                     handle_visible=bool(visible), seconds=round(dt, 2)))
    img = render_candidates(bgr, cands, up)
    cv2.imwrite(str(out / f"{d.name}.jpg"), img)
    (out / f"{d.name}.json").write_text(json.dumps([c.as_dict() for c in cands], indent=1))
    print(json.dumps(rows[-1]))
vis = [r for r in rows if r["handle_visible"]]
print(json.dumps(dict(views=len(rows), handle_visible=len(vis), hit_when_visible=sum(bool(r["hits"]) for r in vis),
                      mean_candidates=round(float(np.mean([r["n"] for r in rows])), 1),
                      mean_seconds=round(float(np.mean([r["seconds"] for r in rows])), 2))))
(out / "summary.json").write_text(json.dumps(rows, indent=1))
