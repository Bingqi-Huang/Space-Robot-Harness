"""World-aligned bounds of every asset of the lunar base scene (the children of <scene>/assets), for the replay
render's camera: run with Isaac's pxr on the CPU (omni.usd.libs on PYTHONPATH / LD_LIBRARY_PATH).

    kit/python/bin/python3 experiments/video/asset_bounds.py <lunar_base.usda> experiments/video/lunar_base_asset_bounds.json
"""
import json, sys
from pxr import Usd, UsdGeom
scene = sys.argv[1]
st = Usd.Stage.Open(scene)
root = st.GetDefaultPrim() or next(iter(st.GetPseudoRoot().GetChildren()))
assets = st.GetPrimAtPath(root.GetPath().AppendChild("assets"))
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
out = {}
for p in assets.GetChildren():
    r = cache.ComputeWorldBound(p).ComputeAlignedRange()
    if r.IsEmpty(): continue
    out[p.GetName()] = [list(r.GetMin()), list(r.GetMax())]
print(root.GetPath(), len(out), file=sys.stderr)
json.dump(out, open(sys.argv[2], "w"), indent=0)
