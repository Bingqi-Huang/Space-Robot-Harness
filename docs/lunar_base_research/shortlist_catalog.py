import base64, glob, io, json, os
from PIL import Image

R = "/tmp/phase_c_investigation"
SKF_DIRS = [f"{R}/skf_prev", f"{R}/skf3", f"{R}/r2/thumbs"]


def skf(prefix):
    for d in SKF_DIRS:
        hits = glob.glob(f"{d}/{prefix}*.jpg")
        if hits:
            return hits[0]
    raise FileNotFoundError(prefix)


def art(name):
    hits = sorted(glob.glob(f"{R}/artvip_thumbs/*{name}*"))
    if not hits:
        raise FileNotFoundError(name)
    return hits[0]


P = lambda p: f"{R}/{p}"

# (id, name, source, license, thumb_path_or_None, note, tags, primary)
ZONES = [
    ("Z1", "Habitat & airlock staging", "Mission B destination. Crew habitat, airlock hatch, staging bench with ORU cradle and tool tray.", [
        ("Habitat modules", [
            ("Z1-01", "“Mars One” mission base", "Sketchfab · admone", "CC-BY", skf("83ced347"), "30 separate white modules on lander legs, airlock stairs. Unit-less (≈986 wide) — rescale.", ["30 parts"], True),
            ("Z1-02", "Habitat Demonstration Unit", "NASA 3D Resources", "PD", P("nasa_prev/Habitat_Demonstration_Unit.png"), "Most NASA-authentic module. Paint out meatball insignia.", ["2 parts"], False),
            ("Z1-03", "Halley VI Antarctic dorm pod", "Sketchfab · lages.miguel", "CC-BY", skf("88dbccb1"), "Module on ski legs with stairs — logistics module analog. Repaint blue → white.", [], False),
            ("Z1-04", "Moon base dome", "Gazebo Fuel · OpenRobotics", "CC-BY", P("06_gazebo_moonbase_dome.png"), "Geodesic dome with gated airlock entry; door is its own mesh.", ["36 parts", "door"], False),
        ]),
        ("Airlock hatch", [
            ("Z1-05", "International Docking System (IDSS)", "Sketchfab · arcturusvfx", "CC-BY", skf("678890a8"), "Real hatch, petals and latches as parts; real scale 1.52 m. CC0 copy on BlenderKit.", ["15 parts", "hatch"], True),
        ]),
        ("Staging bench & tools", [
            ("Z1-06", "Drawer kit 10", "ArtVIP", "Apache-2.0", art("drawer_kit_10"), "Isaac Sim USD, 5 prismatic drawers + colliders. Retexture to aerospace finish.", ["5 joints", "Isaac-ready"], True),
            ("Z1-07", "Ratchet wrench", "Poly Haven", "CC0", P("ph/ratchet_wrench.png"), "Photoreal hand tool, rigged.", ["graspable"], False),
            ("Z1-08", "Adjustable wrench", "Poly Haven", "CC0", P("ph/adjustable_wrench.png"), "Photoreal hand tool.", ["graspable"], False),
            ("Z1-09", "HYTORC electric torque wrench", "Sketchfab", "CC-BY", skf("bcc47ca2"), "Pistol-grip power tool; 1.09 M faces — decimate.", ["graspable"], False),
            ("Z1-10", "Retro multimeter", "Poly Haven", "CC0", P("ph/retro_multimeter.png"), "Hand-held inspection instrument.", ["graspable"], False),
        ]),
    ]),
    ("Z2", "Power field", "Mission A primary site. Solar array masts feeding a row of identical distribution cabinets with visible, operable faults.", [
        ("Distribution cabinet (PDU body)", [
            ("Z2-01", "Utility box 02", "Poly Haven", "CC0", P("ph/utility_box_02.png"), "Outdoor cabinet 0.92 × 0.43 × 1.12 m, door handles, vents. Split doors into links.", ["real scale"], True),
            ("Z2-02", "Power box 01", "Poly Haven", "CC0", P("ph/power_box_01.png"), "Photoreal breaker board; door is a separate node → one hinge joint.", ["door node"], False),
            ("Z2-03", "Electrical distribution cabinet", "Sketchfab · fdgasd7", "CC-BY", skf("5dd2ce8a"), "Clean white panel face with switches and lamps.", [], False),
            ("Z2-04", "Electric distribution box", "Sketchfab · avadhootnb11", "CC-BY-SA", skf("b5e233fb"), "Open door over breaker rows; animated door is a separate node.", ["door node"], False),
            ("Z2-05", "Distribution box (knife switches)", "Sketchfab · ESobolev", "CC-BY", skf("18b306c3"), "Realistic box, open door, knife switches.", [], False),
        ]),
        ("Breakers & switches", [
            ("Z2-06", "Solar inverter + isolator switches", "Sketchfab · avredu", "CC-BY", skf("aa2ec0ed"), "Rotary isolator handle is a natural graspable switch.", [], True),
            ("Z2-07", "Portable generator", "Poly Haven", "CC0", P("ph/portable_generator.png"), "Dial, switch and toggle are separate nodes.", ["3 control nodes"], False),
        ]),
        ("ORU / battery module", [
            ("Z2-08", "Orbital Replacement Unit", "NASA 3D Resources", "PD", P("nasa_prev/Orbital_Replacement_Unit.png"), "ISS-style swap box with MLI and covers. Re-mass ≤ 1 kg, fit a 25 mm handle.", [], True),
            ("Z2-09", "Sci-fi power battery", "Sketchfab", "CC-BY", skf("4663e0ac"), "Swappable battery look with handles.", ["18 parts"], False),
            ("Z2-10", "Integrated box energy storage", "Sketchfab · mrdt.club", "CC-BY", skf("4b2d126e"), "White battery racks and heat exchangers — already near aerospace white.", [], False),
        ]),
        ("Solar array (compose a VSAT-style mast)", [
            ("Z2-11", "Photovoltaic panels", "Sketchfab · mfb64", "CC-BY", skf("cc9b7d59"), "Framed module, front and back — tile into an array blanket.", [], True),
            ("Z2-12", "PV racks & trackers collection", "Sketchfab · mrdt.club", "CC-BY", skf("5f71fce4"), "Pole-mounted single-axis trackers; 1.42 M faces — decimate.", [], False),
            ("Z2-13", "Solar module on mast", "Sketchfab · M8ZA", "CC-BY", skf("b2b6dbc3"), "Mast-mounted power module — lattice mast component.", ["6 parts"], False),
            ("Z2-14", "Lattice telecom tower", "Sketchfab", "CC-BY", skf("103135f8"), "Mast body for a vertical array.", [], False),
            ("Z2-15", "ISS roll-out solar array (iROSA)", "Printables", "CC0", P("r2/pr_prev/958363.jpg"), "Real iROSA blanket and boom geometry; untextured STL.", [], False),
            ("Z2-16", "SRC solar array", "NASA Space Robotics Challenge", "Apache-2.0", P("render_g/g__ex__src__solar_array__meshes__solar_array.obj.png"), "Ground array with a cable socket. Geometry render (textures not loaded).", ["socket"], False),
        ]),
        ("Harness & switchgear", [
            ("Z2-17", "Modular electric cables", "Poly Haven", "CC0", P("ph/modular_electric_cables.png"), "Conduits, junction boxes, connectors kit.", [], True),
            ("Z2-18", "10 kV ring main unit", "Sketchfab · mrdt.club", "CC-BY", skf("630e2c58"), "White multi-door switch cabinets on a railed platform.", [], False),
        ]),
    ]),
    ("Z3", "Comm station", "Mission A secondary site and the physical face of link availability. Dish, relay mast, comm cabinet with a connector.", [
        ("Dish antenna", [
            ("Z3-01", "Industrial antenna", "Sketchfab · RickPG001", "CC-BY", skf("001970c2"), "Realistic large dish on pedestal, PBR.", [], True),
            ("Z3-02", "Satellite comms", "Sketchfab · duanesmind", "CC-BY", skf("4be56951"), "Base, arm and dish already separate → pan/tilt joints.", ["3 parts"], False),
            ("Z3-03", "SRC satellite dish", "NASA Space Robotics Challenge", "Apache-2.0", P("render_g/g__ex__src__satellite_dish__meshes__satellite_dish.obj.png"), "Yaw/pitch revolute joints driven by handwheels — a ready maintenance task. Geometry render.", ["2 joints", "handwheels"], False),
            ("Z3-04", "Radome", "NASA 3D Resources", "PD", P("nasa_prev/Radome.png"), "Geodesic comm/sensor housing.", [], False),
        ]),
        ("Relay masts", [
            ("Z3-05", "BTS antennas", "Sketchfab", "CC-BY", skf("5e7feb9b"), "Microwave dish + sector antenna for a relay terminal.", [], True),
            ("Z3-06", "5G telecom mast", "Sketchfab", "CC-BY", skf("c9ea1b7b"), "Slim mast with base cabinet.", [], False),
        ]),
        ("Comm cabinet interior", [
            ("Z3-07", "Server rack", "Sketchfab · Crysis007-94", "CC-BY", skf("5320622f"), "Avionics rack look.", [], True),
            ("Z3-08", "Comms room assets", "Sketchfab", "CC-BY", skf("566a5b11"), "Racks, consoles, radio units.", [], False),
            ("Z3-09", "Wet-mate plugs & socket / SRC cable plug", "Gazebo Fuel · NASA SRC", "CC-BY · Apache-2.0", None, "Human-scale connectors with T-handle (Fuel) or Ø34 mm body (SRC). Functional but plain — retexture.", ["plug/socket"], False),
        ]),
    ]),
    ("Z4", "Landing pad & cargo depot", "Mission B source. Commercial lander, carrier, racks of spares, cases and a locker.", [
        ("Landers", [
            ("Z4-01", "Resilience / Peregrine / Vikram", "Space Robotics Bench (already local)", "CC0 · attributed", None, "Real CLPS-class landers already in srb_assets as USDZ. Nova-C via OmniLRS IM-2 Athena (BSD-3).", ["local"], True),
            ("Z4-02", "Apollo Lunar Module (detailed)", "Sketchfab · CMFDesign", "CC-BY", skf("d5eea68f"), "451 k faces; far better than NASA's low-poly LM.", [], False),
            ("Z4-03", "Starship S25 & Booster 9", "Sketchfab · clarence365", "CC-BY", skf("f76be07d"), "Distant HLS backdrop only.", [], False),
        ]),
        ("Cargo carrier", [
            ("Z4-04", "Super Lightweight Interchangeable carrier", "NASA 3D Resources", "PD", P("nasa_prev/Super_Lightweight_Interchangeable.png"), "Truss carrier with MLI — cargo pallet on the pad.", [], True),
        ]),
        ("Graspable cases", [
            ("Z4-05", "Clamshell tool box 1", "ArtVIP", "Apache-2.0", art("clamshell_tool_box_1__.thumbs__256x256__model_clamshell_tool_box_1"), "Isaac Sim USD, lid + latch revolute joints, colliders. 0.60 × 0.45 × 0.25 m.", ["2 joints", "Isaac-ready"], True),
            ("Z4-06", "Sci-fi crate (1)", "Sketchfab · ul1tka", "CC-BY", skf("69fe3211"), "Clean white case with handles and latches; rescale.", [], False),
            ("Z4-07", "Sci-fi crate (2)", "Sketchfab · ul1tka", "CC-BY", skf("342efe4d"), "Smaller variant.", [], False),
            ("Z4-08", "Pelican 472-style case", "Sketchfab", "CC-BY", skf("d4b448ff"), "Hard equipment case with handles; retexture white.", [], False),
            ("Z4-09", "Crew Lock Bag", "NASA 3D Resources", "PD", P("nasa_prev/Crew_Lock_Bag.png"), "Realistic spares bag with handle.", [], False),
        ]),
        ("Racks & locker", [
            ("Z4-10", "Server racking system", "Sketchfab · Crysis007-94", "CC-BY", skf("6fe2cacf"), "Open-frame rack reads as a spares rack; slots still to model.", [], True),
            ("Z4-11", "Modular metal shelving", "Sketchfab · Webster", "CC-BY", skf("6a1f7193"), "Clean metal shelving.", [], False),
            ("Z4-12", "Lab / poison cabinet", "ArtVIP", "Apache-2.0", art("poison_cabinet"), "Isaac Sim USD, 8 revolute doors; use lower modules as a locker.", ["8 joints", "Isaac-ready"], False),
        ]),
        ("Handling & access", [
            ("Z4-13", "Industrial AGV trolley", "Sketchfab", "CC-BY", skf("016a0664"), "Clean white AGV with cage cart — cargo cart.", [], True),
            ("Z4-14", "Scaffold stairs (steel)", "Sketchfab · dchant", "CC-BY", skf("d2230c56"), "Stair tower for lander and habitat access.", [], False),
        ]),
    ]),
    ("Z5", "ISRU & excavation yard", "Visual depth plus the pool of movable obstructions and alternate routes.", [
        ("Processing & excavation", [
            ("Z5-01", "RASSOR excavator", "NASA 3D Resources", "PD", P("nasa_prev/Regolith_Advanced_Surface_Systems_Operations_Robot.png"), "Only realistic lunar excavator; untextured grey.", [], True),
            ("Z5-02", "Chemical tank skid", "Sketchfab · ixMkc1", "CC-BY", skf("63c001e7"), "Twin process vessels — oxygen extraction plant stand-in.", [], False),
            ("Z5-03", "Large storage tanks", "Sketchfab · duanesmind", "CC-BY", skf("bd3ac970"), "Spherical tanks with stairs — propellant farm after white retexture.", [], False),
        ]),
        ("Valves & piping", [
            ("Z5-04", "Hand-wheel valve", "Gazebo Fuel · DRC", "CC0", P("render_g/g__ex__gz__drc_practice_handle_wheel_valve__meshes__handle_wheel_valve.dae.png"), "SDF with revolute joint; wheel + crank handle.", ["joint"], True),
            ("Z5-05", "Modular industrial pipes", "Poly Haven", "CC0", P("ph/modular_industrial_pipes_01.png"), "Flanges and a handwheel valve.", [], False),
            ("Z5-06", "Gas bottles set", "Sketchfab", "CC-BY", skf("d671d935"), "O2/N2 bottle look.", [], False),
        ]),
        ("Work-site dressing & obstructions", [
            ("Z5-07", "Cable reels", "Sketchfab · thesidekick", "CC-BY", skf("53d00d26"), "Photogrammetry reels — movable obstruction candidates.", [], True),
            ("Z5-08", "Light tower", "Sketchfab · krambulini", "CC-BY", skf("9addea6a"), "Trailer floodlight tower, real scale.", [], False),
        ]),
    ]),
    ("Z0", "Rover dock", "Start pose and the verifiable “operationally safe” end pose.", [
        ("Charger", [
            ("Z0-01", "Sci-fi electrical charger", "Sketchfab · JonParrish", "CC-BY", skf("f09b75dc"), "High-quality charger column; tone down the glow strips.", [], True),
            ("Z0-02", "EV charging station A", "Sketchfab · khekwei", "CC-BY", skf("aa2af6b5"), "Canopy + charger post.", [], False),
            ("Z0-03", "Charging station set", "Sketchfab · mrdt.club", "CC-BY", skf("1930fe67"), "Charger posts and cabinets; plug and holster geometry.", [], False),
        ]),
    ]),
    ("V", "Vehicles around the base", "Parked rovers for realism, blocked routes and a broken-robot situation.", [
        ("Rovers", [
            ("V-01", "Space Exploration Vehicle (MMSEV)", "Sketchfab · MarcoRomero", "CC-BY", skf("d2f3b528"), "4K PBR, real scale 3.1 × 4.0 × 4.5 m — crew rover.", [], True),
            ("V-02", "ESA ExoMars rover", "Sketchfab · marian42", "CC-BY / CC0", skf("4148a592"), "77 named parts (wheels, bogies, steering).", ["77 parts"], False),
            ("V-03", "Lunar Roving Vehicle (museum scan)", "Sketchfab · Deutsches Museum", "CC-BY-SA", skf("acb3f864"), "Museum-grade Apollo LRV.", [], False),
            ("V-04", "Space Exploration Vehicle", "NASA 3D Resources", "PD", P("nasa_prev/Space_Exploration_Vehicle.png"), "NASA's own SEV, 12 wheels.", [], False),
        ]),
    ]),
]


def thumb(path):
    im = Image.open(path).convert("RGB")
    im.thumbnail((520, 390))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


out = []
for zid, zname, zdesc, groups in ZONES:
    gs = []
    for gname, items in groups:
        its = []
        for (iid, name, src, lic, tp, note, tags, primary) in items:
            its.append(dict(id=iid, name=name, src=src, lic=lic, img=thumb(tp) if tp else None,
                            note=note, tags=tags, primary=primary))
        gs.append(dict(name=gname, items=its))
    out.append(dict(id=zid, name=zname, desc=zdesc, groups=gs))

json.dump(out, open("/mnt/SharedData/Research/Space_Robot_Harness/.artifact_build/catalog.json", "w"))
print(sum(len(g["items"]) for z in out for g in z["groups"]), "items")
print(os.path.getsize("/mnt/SharedData/Research/Space_Robot_Harness/.artifact_build/catalog.json") // 1024, "KB")
