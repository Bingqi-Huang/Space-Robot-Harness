# 02 — Internet 3D asset survey for a credible lunar surface base (Isaac Sim 5.1)

Research-only survey, 2026-09-15. No assets downloaded into any repo. Visual
judgments below come from contact sheets of the official preview renders /
Sketchfab thumbnails (`nasa_contact.jpg`, `skf_sheet1.jpg`, `skf_sheet2.jpg` in
this directory).

Conversion path for everything below (unless noted): glTF/GLB/OBJ/FBX →
Isaac Sim `omni.kit.asset_converter` (built into 5.1) **or** Blender 4.5
(already on host: `/home/bingqi/Programs/blender/4.5`) → USD export. In both
cases you must then (1) **measure and rescale** — many NASA/Sketchfab GLBs are
not authored at 1 unit = 1 m; (2) author collision (convex decomposition /
SDF for manipulables, simplified convex/box proxies for buildings); (3) set
mass/density; (4) split into links + joints for anything to be articulated;
(5) strip or repaint NASA insignia (see licensing).

---

## 0. Licensing summary (read first)

| Source | License | Public-repo redistribution | ML/AI use | Verdict |
|---|---|---|---|---|
| NASA 3D Resources (GitHub + science.nasa.gov) | US-gov work, not copyrighted ("free and without copyright") | Yes | Allowed for models/textures, **but** NASA forbids its Insignia (Meatball, Worm, Seal) "to appear with AI generated imagery or in the training of AI tools"; no implied endorsement | **Use; strip/repaint insignia textures** |
| NASA Astromaterials 3D (Apollo samples) | CC0 / public domain, credit NASA | Yes | Yes | **Use** |
| NASA PGDA / USGS / PDS terrain data (LOLA, LROC) | Public domain (NASA/PDS) | Yes | Yes | **Use** |
| NASA SVS CGI Moon Kit | Public domain (NASA SVS) | Yes | Yes | Use (horizon only) |
| OmniLRS (terrain pipeline, not assets) | BSD-3-Clause | Yes | Yes | Reference/borrow code |
| Smithsonian 3D (Sketchfab mirror / 3d.si.edu) | CC0 where marked | Yes | Yes | Few surface-relevant items |
| Poly Haven | CC0 | Yes | Yes | **Use for Earth-tech props/textures** |
| Kenney kits | CC0 | Yes | Yes | License fine, **visually not credible** (cartoon) |
| Sketchfab — CC-BY | Attribution | Yes, with attribution file | CC-BY does not restrict; NoAI tag not enforceable on CC | Use case-by-case; keep ATTRIBUTION.md |
| Sketchfab — CC-BY-NC / -ND / Standard / Editorial | varies | NC: no commercial; ND: **no modification** (can't decimate/retexture/split); Editorial: editorial only; Standard+NoAI: contractually no gen-AI | **Avoid** |
| ESA website 3D models | ESA Standard Licence: educational/informational; commercial needs written authorization; some items CC BY-SA 3.0 IGO | Standard: questionable; BY-SA: yes with SA | — | Only CC BY-SA items |
| NASA DUST (UE5 south-pole sim) | NASA JSC General Public Release, obtained by email request (MSC-27522-1) | Not as convertible assets | — | Not an asset source |
| **TurboSquid (incl. free)** | TurboSquid license | **No** | **"May NOT use Imagery in machine learning programs without prior authorization"** | **Blocker** |
| **CGTrader free downloads** | Royalty Free | **No standalone redistribution** | **Buyers may not use free products for ML/NN training** | **Blocker** |
| **Fab / Quixel Megascans** | Fab Standard License | **No standalone redistribution** (only baked into a project); Megascans mostly paid since 2025; some listings add gen-AI restrictions | per-listing | Private use only; never commit raw files |
| BlenderKit (Royalty-Free tier) | Royalty Free | No standalone redistribution | — | Only its CC0 subset |

Practical rule: keep a per-asset `provenance.yaml` (URL, license, author,
download date, modifications). Commit only NASA/PD, CC0, and CC-BY (with
attribution) assets to a public repo; everything else stays in a local,
git-ignored asset cache.

---

## 1. NASA 3D Resources

Two front-ends, same content: GitHub `nasa/NASA-3D-Resources` (~200 model
dirs, GLB + preview PNG) and `science.nasa.gov/3d-resources/` (files served
from `assets.science.nasa.gov/content/dam/science/cds/3d/resources/model/<slug>/`).
**Checked the full catalog: there is no official model of VIPER, CADRE, LTV,
Artemis Base Camp / Foundation Surface Habitat, VSAT, CLPS landers (Nova-C,
Griffin, Blue Ghost), HLS, or ISRU plants.** (The web "Lunar" filter only
lists Apollo landing-site DEM prints.) Gaps must be filled from other sources.

Lunar-base-relevant models that DO exist (sizes are GLB bytes from the repo
tree; poly counts not published — GLB size is the proxy):

| Model | URL (GitHub path under `3D Models/`) | GLB | Parts | Quality / plausibility | Real-world scale | Use in base |
|---|---|---|---|---|---|---|
| **Habitat Demonstration Unit (HDU / Deep Space Habitat analog)** | `Habitat Demonstration Unit/…(part 1).glb`, `…(part 2).glb` | 0.52 + 0.71 MB | 2 GLBs: vertical hard-shell core w/ docking ports + attached horizontal module | Clean PBR, genuinely NASA-looking; **NASA meatball + US flag on texture** | Real HDU-DSH: ~5 m dia × ~3.5 m tall core | **Primary habitat building** |
| **Space Exploration Vehicle (SEV / Lunar Electric Rover)** | `Space Exploration Vehicle/…glb` | 22.4 MB | single GLB (wheels likely separate nodes — verify) | High detail, pressurized cabin, 12 wheels, solar roof — very credible | Real: ~4.5 m L × ~3 m W × ~3 m H | Parked crew rover / obstacle / servicing target |
| **RASSOR (regolith excavator)** | `Regolith Advanced Surface Systems Operations Robot (RASSOR)/…glb` | 6.3 MB | single GLB; drum arms visible as separate geometry | Untextured/grey but accurate shape | Real: ~1.2 m L, ~66 kg | ISRU/excavation zone prop; "broken-down robot" held-out case |
| **Tall Dish** (antenna) | `Tall Dish/Tall Dish (dish).glb`, `(post).glb`, `(turntable).glb` | 1.39 + 0.24 + 0.05 MB | **3 separable parts** (dish/post/turntable) → natural pan/tilt articulation | Credible ground antenna | Check; rescale to ~2–3 m comm mast | **Comm tower with a mis-pointed / obstructed dish** (Mission A fault) |
| **Orbital Replacement Unit (ORU)** | `Orbital Replacement Unit/…glb` | 0.59 MB | single | Realistic ISS-style swap box w/ MLI + covers | ~0.5–1 m | Replaceable avionics/battery module (Mission B servicing) — mass must be ≤ RM-75 5 kg payload in sim |
| **Crew Lock Bag** | `Crew Lock Bag/…glb` | 0.61 MB | single, handle | Realistic, clearly graspable | ~0.5 m | Tool/spares bag for logistics |
| **Super Lightweight Interchangeable (carrier)** | `Super Lightweight Interchangeable/…glb` | 1.13 MB | single | Realistic truss carrier w/ MLI | ~1–2 m | Cargo pallet/carrier on landing pad |
| **Apollo Lunar Module** | `Apollo Lunar Module/…glb` | 0.72 MB | single | Low-poly but correct | 7 m tall, 9.4 m wide | Landing-pad hero prop (period piece — use as "descent stage" only if you want historic flavour) |
| **Radome** | `Radome/…glb` | 0.82 MB | single | Geodesic radome; plausible comm/sensor housing | rescale | Comm/weather station |
| Tools: **Wrench, Ratchet, Hammer, Pistol Grip Tool, Grease Gun** | `Wrench/`, `Ratchet/`, `Hammer/`, `Pistol Grip Tool/`, `Grease Gun/` | 11–236 KB | single each | Realistic ISS/EVA tools | hand-tool scale (PGT ~0.3 m) | **Graspable tool set** for "fetch the right tool" tasks |
| Satellite Kit (body/radio/wings ×3) | `Satellite Kit/…` | 3–15 KB each | modular parts | Very low poly, educational | small | Low value |
| Base Station | `Base Station/…glb` | 22 KB | — | **Placeholder pink cylinder — unusable** | — | Skip |
| Gateway Core | `Gateway/Gateway Core.glb` | 66 MB | — | Orbital, not surface | — | Skip (maybe sky decoration) |
| Deep Space Network 34 m / 70 m / Tall Dish | `Deep Space Network 34-meter/…` | — | — | Earth DSN; far too big | — | Only Tall Dish is scale-appropriate |

Also on science.nasa.gov (resource pages, not GitHub): **Astromaterials 3D
Moon Rocks** (see §4), InSight lander, rovers (Mars; skip).

NASA media guidelines (nasa.gov/nasa-brand-center/images-and-media): NASA
content incl. "texture maps and polygon data in any format — generally are not
subject to copyright in the United States"; attribution requested; must not
imply NASA endorsement; **"NASA does not permit our Insignia (i.e., NASA
Meatball, Worm logotype, or Seal) to appear with AI generated imagery or in the
training of AI tools."** Since our sim renders feed a VLM/agent pipeline,
**remove the meatball/worm from HDU and any other NASA-textured asset** (flags
are fine).

---

## 2. ESA / JAXA / other agencies

- **ESA Argonaut** lander: ESA says a CAD model "for illustration purposes" is
  available on the Argonaut programme page (esa.int returned HTTP 403 to
  automated fetch; format/licence not verified). esa.int multimedia is under the
  ESA Standard Licence (educational/informational; **commercial use needs
  written authorization**) unless tagged CC BY-SA 3.0 IGO. Worth one manual
  check — Argonaut is the most plausible near-term European cargo lander.
- **ESA Scifleet** (scifleet.esa.int): spacecraft models in many formats —
  science satellites, not surface infrastructure. Skip.
- **JAXA SLIM**: only fan/3D-print STL (Printables, unofficial). Skip.
- **ISRO Chandrayaan-2 / Vikram / Pragyan**, **CNSA Yutu**, **Lunokhod**:
  exist only as community CC-BY Sketchfab models (§3). Yutu (tashtego, 9 k faces)
  and Chandrayaan-2 (tashtego, 58 k faces) are decent-looking; plausible as
  "foreign/older hardware on site" decoration.
- **NASA DUST** (JSC, UE5 south-pole sim): General Public Release by email
  request only; Unreal project, not an asset pack. Not a practical source.

---

## 3. Community / marketplace sources

### 3a. Sketchfab (queried via public API, `downloadable=true`, CC0/CC-BY)

Download requires a Sketchfab account (manual or OAuth token). Formats:
original upload (often .blend/.fbx/.obj) + auto glTF/GLB + USDZ.

Credible-enough candidates (all **CC-BY** unless noted):

| Model | Author | Faces | Notes | Plausibility |
|---|---|---|---|---|
| Apollo Lunar Sample XXXX (dozens) | **NASA Astromaterials3D (CC0)** | 100–200 k | photogrammetry of real Apollo rocks | **Excellent** manipulable samples (decimate + convex hull) |
| ALSRC (Apollo Lunar Sample Return Container) `4ed9b96d…` | emilevdb | 636 | clean low-poly box w/ latches | **Good** — sample return case; lid could be split for articulation |
| SciFi Container `96fb7ded…` | edwincgstudio | 26 k | NASA-styled white cargo pod; **has meatball** — repaint | Good logistics container |
| Electrical Control Panel sci-fi `c0dfab99…` | aleksfotoart | 3.9 k | wall power box w/ door; PBR | Good power-distribution box (door articulation) |
| Industrial Electrical Box `de13c96d…` | Krystofeles | 8.7 k | box with opening door | OK (Earth-style) |
| Lunar Rover (from film "Moon") `80030560…` | Watndit | 245 k | 6-wheel rover w/ crane | Plausible utility rover |
| Yutu `d9564c9a…` / Chandrayaan-2 `4d0017f2…` | tashtego | 9–58 k | accurate agency hardware | Plausible decoration |
| Apollo Lunar Excursion Module `5376aae0…` | siotech2011 | 1.38 M | heavier than NASA's own LM | Use NASA LM instead |
| Gateway Core `36fb6aa9…` | robo-reboot | 98 k | orbital | Skip |
| Free Airlock Door `58729c76…` | michael_grodkowski | 4.4 k | stylized game door | Borderline (game look) |
| Chemical tank `63c001e7…` / Rusted Tank storage | ixMkc1 | 5.8–8.7 k | industrial tanks | OK as ISRU/propellant tanks after retexture (clean metal) |
| Low Poly Solar Array `5ab24c66…` | Jason_Phillips | 16 k | stylized | **Not credible** |
| Moonwards collection (Polar Hab, Nuclear Thermal Generator, Gantry Crane, Solar Thermal Plant, Lunar Rover…) | briligg | 2–540 k | realistic *concepts* but sketch-quality meshes (flat colors, missing detail) | **Not credible as-is**; ideas only |
| LowPoly SciFi Containers Pack, Sci-Fi Containers Kit, Futuristic cargo container | various | 5–105 k | game/cartoon textures | **Not credible** |
| Low-poly Lunar Habitat, Moon Base, Hyena Recon Transport | various | — | cartoon/game | **Not credible** |
| HAB – Mars Desert Research Station `5c1f4c97…` | marssociety | 500 k | lidar scan of MDRS **interior** | Mars analog interior; skip |

Sketchfab has **no** credible, freely downloadable Artemis-era habitat, VSAT,
CLPS lander, or VIPER model (searched: lunar base/habitat, Artemis, VIPER,
Starship HLS, Blue Moon, Nova-C, Griffin, vertical solar array, lunar power
station). Search results for those are dominated by cartoon/game assets.

### 3b. Fab.com / Quixel Megascans

Megascans were free for all engines only until end-2024; since 2025 most are
paid ($0.99+/asset) under the **Fab Standard License**: may be incorporated in
projects, **may not be redistributed standalone**; some listings carry
gen-AI restrictions. Useful content: photogrammetry rocks/boulders, gravel/ash
surfaces (Earth, but recolorable). Private-cache use only; do not commit to a
public repo.

### 3c. Poly Haven (CC0, ~520 models, textures, HDRIs)

No lunar assets, but **photoreal CC0 industrial/tool props** that fit a working
base: `adjustable_wrench`, `combination_wrench`, `flathead_screwdriver`,
`crowbar_01`, `bolt_cutters_01` (rigged), `bench_vice_01` (rigged),
`Drill_01`, `drill_press_01`, `ammo_box`, `industrial_pastic_container`,
`industrial_storage_cart`, `hand_truck`, `ladder_sectioned_01`,
`korean_fire_extinguisher_01`, `Barrel_01/02/03`, `cardboard_box_01`,
`circuit_board`, `medical_box`, `exterior_aircon_unit` (heat-rejection look).
Textures: `aerial_rocks_01/02/04`, gravel/ash surfaces, metal plates. Formats:
glTF/FBX/Blend + 1k–8k PBR maps. Direct API download (`api.polyhaven.com`),
no account needed. HDRIs irrelevant (lunar sky = black + sun).

### 3d. Kenney (CC0)

Space Kit (150+ models), Space Station Kit (80+), Modular Space Kit (40 GLB).
License perfect; **style is flat-shaded cartoon — fails the "real NASA/ESA
infrastructure" bar.** Skip for visible hero assets.

### 3e. BlenderKit / TurboSquid / CGTrader

- BlenderKit: Royalty-Free tier forbids standalone redistribution; CC0 subset OK.
- **TurboSquid (free models included): prohibits use in machine-learning
  programs without authorization + no redistribution → blocker.**
- **CGTrader free downloads: "Buyers may not use products offered as free
  downloads for machine learning or training neural networks"; no standalone
  redistribution → blocker.** (There are many VIPER/Artemis lander models on
  both, which is tempting — don't.)

### 3f. Smithsonian (CC0)

Apollo 11 Command Module (exterior/interior/hatch, 150–720 k faces),
Armstrong spacesuit. A Lunar Roving Vehicle object page exists on si.edu but a
downloadable 3D scan could not be confirmed (3d.si.edu blocks automated
access). Little surface-base value.

---

## 4. Lunar terrain data

| Dataset | URL | Resolution | Format | License | Fit |
|---|---|---|---|---|---|
| **LOLA South Pole landing-site DEMs** (Barker et al. 2021) | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/ (README lists sites) | **5 m/px** | Cloud-optimized GeoTIFF, south polar stereographic (m), MOON_ME/DE421; `_surf.tif` height, `_slp.tif`, `_toterr.tif`, 100 LDEM clones, point clouds | Public domain (NASA) | **Best real-site base.** Sites: Site01 **Connecting Ridge**, Site04 **Shackleton rim**, Site07 Peak near Shackleton, Site11 de Gerlache rim, Site20 Leibnitz β plateau, Site23 Malapert massif, Site06/DM2 Nobile rims, Haworth, Shoemaker |
| LOLA south-pole large-area mosaics | https://pgda.gsfc.nasa.gov/products/90, /81, /78 | 5–20 m/px | GeoTIFF | PD | Surroundings / horizon |
| USGS Astropedia Moon LRO South Pole DEM (+ shaded relief, slope) | https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem | tens of m | GeoTIFF | PD | Horizon/lighting context |
| LROC NAC DTMs (stereo) | https://lroc.im-ldi.com/images/downloads (PDS LROC node) | ~1–5 m/px where stereo exists | GeoTIFF/PDS IMG | PD (PDS) | Higher-res patches; coverage spotty at the pole |
| LROC NAC south-pole average mosaic 1 m | via Moon Trek (trek.nasa.gov) | 1 m/px | GeoTIFF | PD | Albedo/texture reference |
| **NASA SVS CGI Moon Kit** (#4720) | https://svs.gsfc.nasa.gov/4720 | LOLA `ldem_4/16/64` (64 ppd = 23040×11520, ~474 m/px); LROC color up to 27360×13680 (also 16k/8k/4k) | float/uint16 TIFF | PD | **Horizon/sky only** — useless at rover scale |
| OmniLRS terrain pipeline (reference implementation) | https://github.com/OmniLRS/OmniLRS | 5 m DEM upsampled procedurally to **2.5 cm/px**, geometry clipmaps, Isaac Sim 5.0 | code (BSD-3) | BSD-3 | The proven way to turn the 5 m PGDA DEM into a robot-scale yard |

Note: 5 m/px means a whole 100 m × 100 m base footprint is only 20×20 DEM
pixels — real DEM gives the macro slope/ridge/crater context and illumination
geometry; rover-scale bumps, small craters, and boulders must be procedural
(OmniLRS-style or SRB simforge) plus scanned rocks (Astromaterials3D, Poly
Haven/Megascans boulders).

---

## 5. Recommended shortlist per category

| Category | Pick | Source / license |
|---|---|---|
| Habitat | **HDU (2 parts)**, repaint insignia | NASA PD |
| Crew/utility rover (parked, obstacle, servicing target) | **SEV/Lunar Electric Rover**; Sketchfab "Moon" rover as 2nd | NASA PD; CC-BY |
| Excavation/ISRU robot | **RASSOR** | NASA PD |
| Comm infrastructure | **Tall Dish (3-part, articulable)**, Radome | NASA PD |
| Lander / landing pad | **Apollo LM** (low-poly) as descent-stage hero; ESA Argonaut CAD if licence checks out | NASA PD; ESA (verify) |
| Cargo / logistics | **Super Lightweight Interchangeable carrier**, **ORU**, **Crew Lock Bag**, SciFi Container (repaint), ALSRC | NASA PD; CC-BY |
| Power distribution | Sketchfab Electrical Control Panel (door) — no credible free VSAT/solar-farm model exists → build solar array procedurally (panel + mast) | CC-BY; procedural |
| Tools (graspable) | NASA Wrench/Ratchet/Hammer/Pistol Grip Tool/Grease Gun + Poly Haven wrenches/screwdriver/crowbar/bolt cutters | NASA PD; CC0 |
| Samples / rocks | **Astromaterials3D Apollo samples** (OBJ, 2 resolutions) | CC0 |
| Industrial props | Poly Haven barrels, plastic containers, storage cart, hand truck, extinguisher | CC0 |
| Terrain | **PGDA LOLA 5 m DEM (Connecting Ridge or Shackleton rim)** + OmniLRS-style procedural upsampling; SVS Moon Kit for horizon | PD; BSD-3 |

**Real gaps (no free credible asset anywhere):** Artemis Foundation Surface
Habitat, VSAT vertical solar array, CLPS landers (Nova-C/Griffin/Blue Ghost),
VIPER, CADRE, LTV, ISRU plant, fission surface power unit, charging/docking
station. These would have to be modeled in Blender from NASA reference
drawings (NTRS papers, e.g. NASA ASCEND 2022 "Internal Layout of a Lunar Surface
Habitat") or bought from TurboSquid/CGTrader — **the latter is blocked by their
ML-use clauses**.
