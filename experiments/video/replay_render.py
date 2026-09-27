"""A third-person follow view of a finished run, replayed from its bag: every body of the robot and every item of the
site posed where the simulator had them, rendered with RTX. No physics and no re-simulation -- a kinematic replay.

    docker run --rm --name vid-replay --device nvidia.com/gpu=5 --cpuset-cpus 52-61,116-125 --cpuset-mems 2,3 \
        --shm-size 8g -v /home/bingqi/Programs:/home/bingqi/Programs -v /home/bingqi/.cache:/home/bingqi/.cache \
        -v /home/bingqi/.local/share/ov:/home/bingqi/.local/share/ov -v /home/bingqi/.nv:/home/bingqi/.nv \
        -v /home/bingqi/.nvidia-omniverse:/home/bingqi/.nvidia-omniverse -v /mnt/SharedData:/mnt/SharedData \
        runfarm:22.04 /home/bingqi/Programs/isaac-sim/python.sh \
        /mnt/SharedData/Research/Space_Robot_Harness/experiments/video/replay_render.py <run> <out dir> \
        [--fps 1] [--from-sim 0 --to-sim 1e9] [--res 1600,900] [--eye 2.5,-4.5,2.8] [--smooth-s 4] [--fill 150]

Runs record no third-person view (the live follow stream, `D0_VIDEO`, costs the run wall time and was only turned on
for runs already known to pass). They all record a bag whose /tf is simulator truth at every tick
(`srb/interfaces/interface/ros.py` `_broadcast_transforms`): `srb/env0/robot` (the articulation root) and every body
`srb/env0/robot/<link>` relative to it, and every item `srb/env0/lb_<name>` in the env frame, which is the scenery's
frame (`srb/env0` is the world origin, /tf_static). That is everything the picture needs. The scene is assembled as
`space_robotics_bench/assets/lunar_base/scene/render_review.py` assembles it (scenery, LunarBot, the interaction
layer's items, its sun and fill light), once per run; then per output frame the robot's bodies and the items are
set from /tf at that sim time, the units' panel lamps and radiator shutters from the evaluator's `mission_state`,
and a follow camera is placed and rendered. Frames are named by sim time like the run's own `frames/`
(`0000123.40.png`), so `mission_video.py` pairs them with the cameras and the record by stamp.

The camera: `--eye` is its offset in the rover's own frame (x forward, y left) from a look-at point halfway between
the rover's body and its gripper, so both the rover and what the arm is working at stay in frame. The arm is
mounted aft and the rover backs up to what it works at, so the default looks from ahead and to the right, back over
the rover at the unit or stand: a camera behind a rover backed up to a PDU is inside the PDU (the first try, from
aft-right, was), and on a drive the same offset is a leading shot of the rover coming on. Heading and look-at are
smoothed with a centred Gaussian over sim time (`--smooth-s`): the replay knows the future, so the camera glides
through a turn instead of lagging it.

The bag is read with sqlite3 and a TFMessage CDR decoder of its own: Isaac's Python (3.11) cannot import Humble's
rclpy (3.10). SRB's broadcast is the only /tf message carrying every body at once (~5 kB; odom/AMCL/map->odom
messages are ~0.1 kB), so the full set at time t is the latest message over 2 kB received at or before t -- the
recorder runs on the sim clock, so a message's bag timestamp is sim time.
"""
import argparse
import bisect
import glob
import json
import math
import sqlite3
import struct
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LB = REPO / "space_robotics_bench/assets/lunar_base"
SCENE = LB / "usd/scene/lunar_base"
ROBOT_USD = REPO / "space_robotics_bench/assets/srb_assets/robot/mobile_manipulation/lunarbot/lunarbot.usdc"
LAMP_RED, LAMP_GREEN = (1.0, 0.0, 0.0), (0.1, 1.0, 0.2)  # srb/tasks/mobile_manipulation/lunar_base/site.py


def tf_message(buf: bytes) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """tf2_msgs/TFMessage (little-endian CDR) -> {child frame: (xyz, quaternion xyzw)}. Alignment counts from the end
    of the 4-byte encapsulation header."""
    o = 4

    def align(n: int) -> None:
        nonlocal o
        o += -(o - 4) % n

    def u32() -> int:
        nonlocal o
        align(4)
        o += 4
        return struct.unpack_from("<I", buf, o - 4)[0]

    def string() -> str:
        nonlocal o
        n = u32()
        o += n
        return buf[o - n:o - 1].decode()

    def f64(k: int) -> np.ndarray:
        nonlocal o
        align(8)
        o += 8 * k
        return np.array(struct.unpack_from(f"<{k}d", buf, o - 8 * k))

    out = {}
    for _ in range(u32()):
        u32(), u32(), string()  # stamp, parent frame
        child = string()
        out[child] = (f64(3), f64(4))
    return out


def poses_at(bag: Path, times: list[float]) -> list[dict]:
    db = sqlite3.connect(glob.glob(str(bag / "*.db3"))[0])
    tid = db.execute("select id from topics where name='/tf'").fetchone()[0]
    q = "select data from messages where topic_id=? and timestamp<=? and length(data)>2000 order by timestamp desc limit 1"
    return [tf_message(db.execute(q, (tid, int(t * 1e9))).fetchone()[0]) for t in times]


def quat_mat(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def gauss(values: np.ndarray, sigma: float) -> np.ndarray:
    """Centred Gaussian along axis 0, edges held."""
    if sigma <= 0:
        return values
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.concatenate([np.repeat(values[:1], r, 0), values, np.repeat(values[-1:], r, 0)])
    return np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(values.shape[1])], axis=1)


def camera_path(frames: list[dict], eye: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """(eyes, targets), one per frame, in the scenery frame."""
    look, yaw = [], []
    for f in frames:
        p, q = f["srb/env0/robot"]
        r = quat_mat(q)
        grip = p + r @ f["srb/env0/robot/eg2_base"][0]
        look.append(0.5 * (p + np.array([0.0, 0.0, 0.8])) + 0.5 * grip)
        yaw.append(np.arctan2(r[1, 0], r[0, 0]))
    look = gauss(np.array(look), sigma)
    yaw = gauss(np.unwrap(np.array(yaw))[:, None], sigma)[:, 0]
    c, s = np.cos(yaw), np.sin(yaw)
    eyes = look + np.stack([c * eye[0] - s * eye[1], s * eye[0] + c * eye[1], np.full_like(c, eye[2])], axis=1)
    return eyes, look


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fps", type=float, default=1.0, help="rendered frames per simulated second")
    ap.add_argument("--from-sim", type=float, default=0.0)
    ap.add_argument("--to-sim", type=float, default=1e9)
    ap.add_argument("--res", default="1600,900")
    ap.add_argument("--eye", default="2.5,-4.5,2.8", help="camera offset from the look-at point, rover frame")
    ap.add_argument("--smooth-s", type=float, default=4.0)
    ap.add_argument("--fill", type=float, default=150.0, help="dome fill light: the sun is 12 deg up, so a stand in a "
                    "structure's shadow is near black at render_review's 40; 150 reads in the shadow and still looks lunar")
    ap.add_argument("--focal", type=float, default=18.0, help="mm, on a 20.955 mm aperture (render_review's lens)")
    a = ap.parse_args()
    width, height = (int(v) for v in a.res.split(","))

    # -- the record, before Kit starts: which frames, where everything was, what the lamps showed
    db = sqlite3.connect(glob.glob(str(a.run / "bag" / "*.db3"))[0])
    tid = db.execute("select id from topics where name='/tf'").fetchone()[0]
    t0, t1 = (v / 1e9 for v in db.execute("select min(timestamp), max(timestamp) from messages where topic_id=? and length(data)>2000", (tid,)).fetchone())
    db.close()
    lo, hi = math.ceil(max(a.from_sim, t0) * a.fps) / a.fps, min(a.to_sim, t1)  # on the 1/fps grid
    times = [round(lo + i / a.fps, 2) for i in range(int((hi - lo) * a.fps) + 1)]
    frames = poses_at(a.run / "bag", times)
    eyes, looks = camera_path(frames, np.array([float(v) for v in a.eye.split(",")]), a.smooth_s * a.fps)
    states = [(e["sim_t"], e["state"]["units"]) for e in map(json.loads, (a.run / "evaluator/events.jsonl").read_text().splitlines())
              if e["kind"] == "mission_state"]
    state_t = [s[0] for s in states]
    print(f"{len(times)} frames, sim {times[0]:.1f}-{times[-1]:.1f} s, {len(states)} mission states", flush=True)

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "width": width, "height": height})
    import carb  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import omni.usd  # noqa: E402
    from PIL import Image  # noqa: E402
    from pxr import Gf, Usd, UsdGeom, UsdLux, UsdPhysics  # noqa: E402

    carb.settings.get_settings().set("/app/player/playSimulations", False)  # a replay: nothing may fall or drive
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.DefinePrim("/World/lunar_base", "Xform").GetReferences().AddReference(str(SCENE / "lunar_base.usda"))
    stage.DefinePrim("/World/lunarbot", "Xform").GetReferences().AddReference(str(ROBOT_USD))
    ix = json.loads((SCENE / "interaction.json").read_text())
    items = {}
    for name, o in ix["objects"].items():
        prim = stage.DefinePrim(f"/World/objects/lb_{name}", "Xform")
        prim.GetReferences().AddReference(str(LB / o["usd"][o["usd"].index("usd/"):]))
        UsdGeom.Xformable(prim).ClearXformOpOrder()
        items[f"srb/env0/lb_{name}"] = UsdGeom.Xformable(prim).AddTransformOp()
    sun = UsdLux.DistantLight.Define(stage, "/World/sun")
    sun.CreateIntensityAttr(3000)
    sun.CreateAngleAttr(0.53)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(90 - 12, 0, 180 - 200))
    UsdLux.DomeLight.Define(stage, "/World/fill").CreateIntensityAttr(a.fill)

    # the robot's bodies by name; each is set in its parent's frame (the flat links sit under /World/lunarbot, the
    # gripper's under /World/lunarbot/gripper; neither parent moves), keeping the body's authored scale
    cache = UsdGeom.XformCache()
    bodies = {}
    for prim in Usd.PrimRange(stage.GetPrimAtPath("/World/lunarbot")):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            xf = UsdGeom.Xformable(prim)
            scale = Gf.Transform(xf.GetLocalTransformation()).GetScale()
            xf.ClearXformOpOrder()
            bodies[f"srb/env0/robot/{prim.GetName()}"] = (xf.AddTransformOp(), Gf.Matrix4d().SetScale(scale),
                                                          cache.GetLocalToWorldTransform(prim.GetParent()).GetInverse())
    missing = [k for k in frames[0] if k.startswith("srb/env0/robot/") and k not in bodies]
    print(f"{len(bodies)} bodies posed from /tf; in /tf but not in the USD: {missing}", flush=True)

    lamps = {u: stage.GetPrimAtPath(f"/World/lunar_base/assets/{s['panel']}/_materials/StatusLamp/Principled_BSDF")
             for u, s in ix["units"].items()}
    covers = {u: [c for c in stage.GetPrimAtPath(f"/World/lunar_base/assets/{s['cover']}").GetChildren()
                  if c.GetName().startswith("cover_closed")] for u, s in ix["units"].items() if s["cover"]}

    def mat(p, q) -> Gf.Matrix4d:
        return Gf.Matrix4d().SetTransform(Gf.Rotation(Gf.Quatd(q[3], q[0], q[1], q[2])), Gf.Vec3d(*p))

    cam = UsdGeom.Camera.Define(stage, "/World/follow_cam")
    cam.CreateFocalLengthAttr(a.focal)
    cam.CreateHorizontalApertureAttr(20.955)
    cam.CreateVerticalApertureAttr(20.955 * height / width)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.05, 2000.0))
    cam_op = UsdGeom.Xformable(cam).AddTransformOp()
    rp = rep.create.render_product("/World/follow_cam", (width, height))
    rgb = rep.AnnotatorRegistry.get_annotator("rgb")
    rgb.attach(rp)
    a.out.mkdir(parents=True, exist_ok=True)

    shown = {}
    start = time.time()
    for i, (t, f) in enumerate(zip(times, frames)):
        root = mat(*f["srb/env0/robot"])
        for name, (op, scale, parent_inv) in bodies.items():
            op.Set(scale * mat(*f[name]) * root * parent_inv)  # row vectors: body-in-root, then root-in-world
        for name, op in items.items():
            op.Set(mat(*f[name]))
        units = states[max(bisect.bisect_right(state_t, t) - 1, 0)][1]
        for u, s in units.items():
            key = (s["tripped"], s["cover_closed"])
            if shown.get(u) != key:
                shown[u] = key
                colour = Gf.Vec3f(*(LAMP_RED if s["tripped"] else LAMP_GREEN))
                lamps[u].GetAttribute("inputs:diffuseColor").Set(colour)
                lamps[u].GetAttribute("inputs:emissiveColor").Set(colour * 1.5)
                for c in covers.get(u, []):
                    (UsdGeom.Imageable(c).MakeVisible if s["cover_closed"] else UsdGeom.Imageable(c).MakeInvisible)()
        eye, look = Gf.Vec3d(*eyes[i]), Gf.Vec3d(*looks[i])
        cam_op.Set(Gf.Matrix4d().SetLookAt(eye, look, Gf.Vec3d(0, 0, 1)).GetInverse())
        for _ in range(60 if i == 0 else 1):  # the first frame streams the scene's textures in
            rep.orchestrator.step(rt_subframes=4)
        Image.fromarray(np.asarray(rgb.get_data())[..., :3]).save(a.out / f"{t:010.2f}.png")
        if i % 50 == 0:
            print(f"frame {i + 1}/{len(times)} sim {t:.1f} s, {(time.time() - start) / (i + 1):.2f} s/frame", flush=True)
    print(f"RENDERED {len(times)} frames in {time.time() - start:.0f} s -> {a.out}", flush=True)
    app.close()


if __name__ == "__main__":
    main()
