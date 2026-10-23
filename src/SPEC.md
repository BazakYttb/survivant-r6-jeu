# Ultra-realistic anatomical R6 character — modelling spec

(Sections 1–6 describe the original 6-part R6 build; section 6b the current jointed rig.)

Goal: a Roblox **R6** character (6 blocky parts) whose semi-transparent "skin" boxes contain an
**ultra-realistic anatomy**: every bone, organs, joints (cartilage, discs, menisci, ligaments,
tendons), vessels and nerves. Each mesh is exported as one Roblox MeshPart, welded to the R6 part
it belongs to (so it moves with R6 animations). Colour is baked into **vertex colours** (Roblox
multiplies vertex colour by MeshPart.Color=white), so colours must be rich and realistic.

Quality bar: it must look like a high-end anatomy model, not a toy. Correct shapes, landmarks,
proportions (within the R6 compression), rich colour variation, crevices darkened. Check every
part visually with `preview.py` (you can Read the PNG) and iterate until it looks right.

## 1. Pipeline & files (all in `src/`, Python venv below)

```
PY=/tmp/claude-0/-home-user/2092e9f8-e949-58c1-b521-654f2950b698/scratchpad/venv/bin/python
cd /home/user/roblox_r6_anatomie/src
$PY build.py 'Torso_Rib_*' -j 2          # builds parts matching glob(s) -> ../build/parts/<name>.npz
$PY preview.py ../build/prev/x.png front 'Torso_*' '!Torso_Lung*' --res 800x800 --samples 16 [--elev 15] [--azim 30] [--skin]
```
views: front, back, left (character's left side), right, threeq, top, bottom; `--azim` overrides.
`preview.py` uses Cycles CPU; ~20-60 s. Keep `--samples` ≤ 16 and res ≤ 900 for checks.
The machine has only 4 cores shared by several agents: always pass `-j 2` to build.py, rebuild
only the parts you changed, and avoid needlessly huge grids.

Modules (each exposes `parts() -> list[Part]`): `head.py` (done, reference example),
`torso_skel.py`, `torso_thorax.py`, `torso_abdomen.py`, `torso_vessels.py`, `arms.py`, `legs.py`.
`build.py` imports whichever exist. **Only edit your own module** (+ new helper files you create
with a unique prefix). `sdf.py`, `sweep.py`, `maps.py`, `parts.py`, `colors.py`, `landmarks.py`,
`head.py` are shared: read them, don't modify them (you may add NEW colour functions inside
your own module instead of editing colors.py).

### sdf.py (shapes in **cm** of the region's real coordinate system)
Primitives: `sphere(c,r)`, `ellipsoid(c, r3, R=None)`, `round_cone(a,b,r1,r2)`, `capsule(a,b,r)`,
`tube(points, radii, k=0)` (chain of round cones), `box(c, half3, R=None, rnd=0)`,
`ecyl(c, rx, ry, hz, R=None, rnd=0)` (elliptic cylinder along local z), `torus(c,R,r,Rot,sx)`,
`capped_torus(c, Rr, r, half_angle_deg, R)` (arc symmetric about local +y),
`halfspace(origin, normal)` (negative on the side opposite to normal),
`plate(origin, R, poly2d, thick, rnd, bend=(cx,cy), thick_fn=None)` (2-D polygon in local x,y,
extruded ±thick along local z, optionally bent).
Rotations: `R` = 3x3 whose ROWS are the local axes in world coords. Helpers `rot_xyz(rx,ry,rz)`
(degrees) and `frame(z_dir, x_hint)`.
Ops: `union(*s)`, `smooth_union(a,b,k)`, `smooth_union_all(list,k)`, `subtract(a,*b)`,
`smooth_subtract(a,b,k)`, `intersect(a,*b)`, `smooth_intersect(a,b,k)`, `shell(a,t)`,
`a.offset(r)` (grow by r), `displace(a, fn, amp)` (d += fn(p), |fn|<=amp; fn gets (N,3) cm points),
`transformed(a, c, R, s)` (place a shape built in its own local frame), `flip_x(a)`, `mirror_x(a)`.
Noise: `perlin(p, seed)`, `fbm(p, octaves, lac, gain, seed)` → **(N,) arrays** (stack 3 calls
for a vector warp), `worley(p, seed)` → (F1, F2).
Culling margin is automatic (computed from the smoothing radii in the tree); evaluation is done
in blocks, far primitives are skipped. Many primitives with large smoothing radii = slower.

### parts.py
```python
Part(name, mapping, sdf=callable_returning_SDF | None, tubes=callable_returning_list | None,
     color=callable(ctx)->(N,3) sRGB, target=tri_count, h=voxel_size_in_studs|None(auto),
     far=1.5, cat='bone', base=(r,g,b), smooth=4, min_faces=60, ao_scale=None, info='texte FR')
```
* SDF parts: marching cubes on a **stud-space** grid of spacing `h`, then Taubin smoothing,
  decimation to `target` (pyfqmr), normals, AO (sampled from the SDF) and cavity.
  Pick `h` ≈ 1/60–1/150 of the part's size in studs (studs = cm × map scale, see §2); thin
  features need ≥ 2–3 voxels across. Raw tris ≈ 3–15× target is ideal.
* Tube parts: `tubes()` returns a list of `(verts_studs, faces, params, color_fn)`; build with
  `sweep.tube_mesh(points_cm, mapping, r_cm, ds=..., sides=..., r_end_cm=..., rb_cm=...,
  mod=fn(s01,phi)->factor, rprofile=fn(t01)->r_cm, normal_fn=fn(points_studs)->(N,3))`
  (Catmull-Rom spline through cm points, mapped to studs, swept). Tube meshes are not decimated:
  control tris with `ds` (stud spacing along the path) and `sides`. Tri count ≈ 2·sides·L/ds.
* `ctx` passed to colour functions: `pc` (cm points), `ps` (stud points), `n` (normals), `ao` (0..1),
  `cav` (concavity −1..1), `prm` (tubes: columns s01 along path, phi around), `node` (SDF), `mp`.
* `project(points_cm, node, offset)` moves points onto a surface (e.g. coronary arteries on the heart).
* `stud_shape(node_in_studs, mapping)` embeds a stud-space shape in a cm tree (sockets that must
  match a bone of another region, e.g. acetabulum ↔ femoral head, glenoid ↔ humeral head).

### colors.py
`bone(ctx, tint, seed)`, `teeth`, `cartilage`, `disc`, `ligament`, `artery`, `vein`, `nerve`,
`spinal_cord`, `muscle(ctx, base)`, `brain(ctx, groove)`, `lung`, `liver`, `simple(base, var, freq,
dark)`, `lobulated(base, freq)`, helpers `C(r,g,b)`, `mix(a,b,t)`, `shade(col, ctx, ao_k, cav_k,
light)`. Write your own richer functions where useful (heart with epicardial fat in the grooves,
taeniae on the colon, tracheal rings, vessels painted on organ surfaces, etc.).

## 2. Coordinates, R6 layout, mappings (`maps.py`)
Stud space = Blender: **X = character's LEFT**, **Y = BACK** (front = −Y), **Z = up**, floor Z=0.
R6 boxes (studs): Torso x[−1,1] y[−0.5,0.5] z[2,4]; Head ≈ sphere-ish 1.2 cube centred (0,0,4.5);
Left Arm x[1,2] z[2,4]; Right Arm x[−2,−1]; Left Leg x[0,1] z[0,2]; Right Leg x[−1,0].
R6 joint pivots: neck (0,0,4); shoulders (±1,0,3.5); hips (±1,0,2) (R6 standard, keep in mind).
Anatomy may slightly cross box faces where unavoidable, but stay inside the skin overall.

| map | real coords (cm) | to studs |
|---|---|---|
| `HeadMap()` | origin porion, x left, y back, z up | X=0.0497x, Y=0.02+0.046y, Z=4.52+0.046z |
| `TorsoMap()` | x left, y back, z height above floor (175 cm adult) | X=0.046x, Y=0.040y, Z=1.95+0.0335(z−91) (z≥91) / +0.024(z−91) below |
| `TorsoMap(girdle=True)` | same, but \|x\|>8 pushed outwards (+0.32 stud at \|x\|≥17) | for clavicle, scapula, vessels/nerves reaching the arms |
| `ArmMap(+1/−1)` | u lateral (away from body), v back, w = cm BELOW humeral-head centre | X=s(xaxis(w)+0.031u), Y=0.031v, Z=3.66−0.0208w ; xaxis: w0→1.20, 32→1.30, 59→1.47, 80→1.50 |
| `LegMap(+1/−1)` | u lateral, v back, w = cm below femoral-head centre (floor at w=91) | X=s(xaxis+0.034u), Y=yaxis+0.029v, Z=1.95−0.0214w ; xaxis 0→0.42, 43.5→0.50 ; yaxis 0→−0.10, 43.5→0, 82→0.10 |

Representative stud/cm (`mp.spc`): head 0.046, torso 0.040, arm 0.028, leg 0.031 — tube radii in
cm are multiplied by it. Use **s=+1 for LEFT, −1 for RIGHT**, build both sides.

## 3. Naming, categories, budgets
* Name = `<Region>_<Structure>[_L|_R|_NN]`, Region ∈ `Head, Torso, LeftArm, RightArm, LeftLeg,
  RightLeg` (must equal `mapping.region`). ASCII only, no spaces, unique. Examples:
  `Torso_Vertebra_T07`, `Torso_Rib_L03`, `LeftLeg_Femur`, `RightArm_Nerves`.
* `cat` ∈ bone, tooth, cartilage, disc, ligament, organ, brain, eye, vessel, nerve, muscle, gland.
  `base` = representative sRGB colour (fallback if vertex colours are disabled in Roblox).
* `info` = short French description (shown in the README).
* **Hard limit: ≤ 19 000 triangles per Part** (Roblox mesh limit is 20 000). Split big
  structures into several Parts (by lobe, side, segment).
* Budget guide (whole body ≈ 1.2 M tris): long bone 8–12k, vertebra 3.5–5k, rib 2–2.5k, large
  organ 12–19k, small organ 3–8k, vessel/nerve groups ≤ 15k each.

## 4. Lessons learned (head.py)
* `fbm`/`perlin` return (N,) — use `np.stack([fbm(...,seed=s+k) for k in range(3)],1)` for warps.
* Bones look best as smooth unions of anatomically placed ellipsoids / round cones / plates
  (smoothing k ≈ 0.2–0.8 cm), with sharp subtractions for foramina, fossae, notches.
* Hollow organs/shells: `subtract(outer, inner)` or `shell`. Cut caps (intersect with halfspace)
  get sharp normals automatically at export.
* Vessels/nerves: `tube_mesh` with `C.artery/C.vein/C.nerve`; branch tubes simply overlap.
* Colour: always end with `C.shade(...)` so AO/cavity darken crevices; add low+high frequency
  variation; paint landmarks (fat in grooves, vessels, sutures, rings...).

## 5. Region specs (cm, see landmarks.py for shared numbers — import them, don't copy-edit)

### 5.1 Torso skeleton (`torso_skel.py`, TorsoMap; girdle map for clavicle & scapula)
* Vertebrae C3–C7, T1–T12, L1–L5: body centres/curvature in `landmarks.SPINE`, dims in
  `vertebra_dims`. Orient each by the local spine tangent (spline through centres). Anatomy:
  body (elliptic cylinder, concave waist, rounded rims), pedicles, laminae, spinous process
  (cervical short & bifid C3–C6, C7 long "prominens"; thoracic long, steep, overlapping, tip
  ~2–3 levels lower at T5–T8; lumbar horizontal hatchet), transverse processes (cervical with
  foramen transversarium + ant/post tubercles; thoracic long angled back with costal facets;
  lumbar long thin), superior/inferior articular processes, vertebral canal (subtract), uncinate
  lips on cervical bodies, mammillary processes on lumbar. One Part per vertebra
  (`Torso_Vertebra_C3` … `Torso_Vertebra_L5`), 3.5–5k tris, h≈0.0015–0.002.
* Intervertebral discs between all bodies C3/C4 … L5/S1 (+ C2/C3 top disc can be omitted),
  annulus rings in colour, slightly bulging: `Torso_Discs_Cervical/Thoracic/Lumbar` (cat disc).
* Sacrum (`landmarks.SACRUM` centre line): curved triangular wedge, alae, auricular surfaces,
  promontory, 4 pairs anterior & posterior sacral foramina, median sacral crest, sacral canal,
  hiatus. Coccyx: 4 small fused nodules. Sacrum bottom falls below the torso box (Z≈1.84): fine.
* Ribs 1–12 both sides from `landmarks.RIBS` (+ `thoracic_cavity`): head at the vertebral body
  side, neck, tubercle at the transverse process tip, angle, shaft sweeping laterally then
  forward and DOWN to the costochondral junction at `theta_c`, z descending from z_post to
  z_costochondral. Flattened cross-section (≈1.4 cm tall × 0.6 cm thick; rib 1 broad and flat
  horizontally), costal groove hint. Use `sweep.sweep` with a normal hint (outward horizontal)
  for the profile. One Part per rib `Torso_Rib_L01`…`R12` (≤2.5k tris).
* Costal cartilages (ribs 1–10, bluish-white, cat cartilage) from the costochondral junction to
  the sternum (1–7) or to the cartilage above (8–10, forming the costal margin):
  `Torso_CostalCartilage_L/R`.
* Sternum (`landmarks.STERNUM`): manubrium with jugular & clavicular notches, sternal angle,
  body with costal notches, xiphoid. `Torso_Sternum`.
* Clavicles (S-curve through `landmarks.CLAVICLE`, girdle map), scapulae (girdle map, from
  `landmarks.SCAPULA`: thin triangular body curved on the rib cage, spine ridge, acromion
  overhanging the humeral head, coracoid hook, shallow glenoid cavity facing laterally). The
  glenoid must meet the arm's humeral head (arm map: head centre studs (±1.20, 0, 3.66), radius
  ≈2.3 cm × 0.026 = 0.06 stud): use `stud_shape` for the socket.
* Hip bones (os coxae) L/R from `landmarks.PELVIS`: ilium wing (fan, iliac fossa concave
  medially, gluteal surface, crest thickened), ASIS/AIIS/PSIS/PIIS, greater sciatic notch,
  ischial spine & tuberosity, ischiopubic ramus, superior pubic ramus, pubic body, obturator
  foramen (hole), acetabulum cup (lunate surface, notch) EXACTLY around the femoral head of the
  leg map: femoral head centre in studs (±0.42, −0.10, 1.95), radii ≈ (0.072, 0.062, 0.051)
  → build the socket with `stud_shape`. Sacroiliac contact with the sacrum alae.
* Joints (cat cartilage/disc/ligament): glenoid labrum (stud_shape ring), acetabular labrum,
  pubic symphysis disc, sternoclavicular & acromioclavicular discs, sacroiliac cartilage.
  Group sensibly (`Torso_Labra`, `Torso_JointDiscs` …).

### 5.2 Thorax organs (`torso_thorax.py`, TorsoMap)
* Heart (`landmarks.HEART`): right & left ventricles (apex left-anterior-inferior), right atrium,
  left atrium (posterior), both auricles, coronary sulcus & interventricular grooves filled with
  yellow epicardial fat, coronary arteries (RCA, LAD, circumflex) & cardiac veins as tubes
  projected on the surface (`Torso_CoronaryVessels`). Ascending aorta root, pulmonary trunk +
  L/R pulmonary arteries, SVC, IVC stub, 4 pulmonary veins (`Torso_GreatVessels`, short, up to
  the arch). Aortic arch + its 3 branches belong to torso_vessels (see 5.4), stop the heart's
  aorta at the arch start (0.0, −3.0, 133).
* Lungs: thoracic cavity (`landmarks.thoracic_cavity` + spine indentation) ∩ side ∩ above the
  diaphragm domes − mediastinum (heart+0.4 cm, great vessels, trachea, esophagus, spine).
  Apex ~2–3 cm above the clavicle, hilum (5.5, 0.5, 129), cardiac notch & lingula on the left.
  Right: 3 lobes (oblique + horizontal fissures), left: 2 lobes (oblique fissure) — one Part per
  lobe (`Torso_Lung_R_Upper/Middle/Lower`, `Torso_Lung_L_Upper/Lower`), real fissure gaps.
  Pink/grey mottled colour, lobular polygons, anthracotic specks.
* Trachea (`landmarks.TRACHEA`, r≈1.0 cm, 16–20 C-shaped cartilage rings + posterior membranous
  wall), carina, main bronchi (right shorter, wider, more vertical) + lobar + segmental bronchi
  going into the lungs (`Torso_Bronchi`). Larynx: thyroid cartilage (Adam's apple), cricoid,
  epiglottis tip at the top (z≈149–152, Z≈3.89–3.99). Thyroid gland (2 lobes + isthmus around
  tracheal rings 2–4). Esophagus (`landmarks.ESOPHAGUS`, behind trachea, through the hiatus).
* Diaphragm (`landmarks.DIAPHRAGM_DOMES`): two domes (right higher), central tendon (white),
  muscular periphery (red), crura down to L1–L3, hiatuses for aorta/esophagus/IVC.

### 5.3 Abdominal & pelvic organs (`torso_abdomen.py`, TorsoMap)
Starting positions (adjust to avoid interpenetration; check against landmarks AORTA/IVC/spine,
the diaphragm domes and the rib cage):
* Liver: right lobe E((−7.5,−2.5,113),(6.8,6.5,7.0)), left lobe E((1.5,−5.5,114),(5.5,3.5,3.0)),
  tip E((5.5,−5,115),(2.2,2.5,1.5)); domed superior surface under the diaphragm, sharp inferior
  border, falciform ligament & round ligament notch, caudate lobe, impressions (kidney, colon,
  stomach), IVC groove. Gallbladder in its fossa (fundus (−4.5,−8.5,105.5) → neck (−3.5,−4.5,108.5))
  + cystic/common bile duct to the duodenum.
* Stomach: cardia (3.8,−3,110), fundus under the left dome, body, greater/lesser curvature,
  antrum, pylorus (−2,−6.5,103.5). Duodenum C-loop: bulb (−3,−5.5,104.5) → descending
  (−4.6,−3.5,103 → −4.8,−3.6,99.5) → horizontal ANTERIOR to aorta/IVC (y≈−6.3, z≈99) → ascending
  → duodenojejunal flexure (3.5,−5.5,102.5). Gastroepiploic vessels / omental fat painted.
* Pancreas: head in the duodenal C (−3,−5,101.5), neck, body crossing anterior to aorta (y≈−5.6),
  tail to the splenic hilum (9,1.5,110); lobulated yellowish.
* Spleen (left, under ribs 9–11, ≈ (9.5,2,111), 12×7×4 cm, hilum medial, purple).
* Kidneys L (6,0.2,105) / R (−6,0.2,103), 11×6×3 cm, upper pole medial & posterior, hilum
  anteromedial; renal pelvis, ureters down along psoas, crossing the pelvic brim to the bladder;
  adrenal glands as yellow-orange caps on the upper poles.
* Bladder (0,−4.5,88.5) behind the pubic symphysis (lumbar spine & sacrum were raised: L4 at z 101, S1 at 94.3, iliac crest top 103); rectum along the sacrum.
* Small intestine (jejunum/ileum): long tightly packed coils (≥ 250 cm of tube, r≈1.2 cm) in the
  central/lower abdomen x[−7,7] y[−10,−1.5] z[89,104] from the DJ flexure to the ileocecal
  junction (−6.5,−5.5,94): generate with a self-avoiding relaxation (springs + repulsion +
  confinement); split into ≥3 Parts ≤19k tris. Glossy pink, mesenteric vessels painted.
* Large intestine: cecum (−7.5,−5.5,93) + appendix, ascending (x≈−9.5), hepatic flexure,
  transverse colon drooping anteriorly (y≈−9.5), splenic flexure (10,−3.5,113, highest),
  descending (x≈10.5), sigmoid, rectum, anal canal. Haustra (sacculations) + 3 taeniae coli +
  epiploic appendages (small fat tags). ≥2 Parts.

### 5.4 Torso vessels & nerves (`torso_vessels.py`; TorsoMap, girdle map for the parts that go
to the arms)
* Arteries (`Torso_Arteries_*`): aortic arch from (0.0,−3.0,133) following `landmarks.AORTA`
  (descending thoracic, abdominal) to the bifurcation; brachiocephalic trunk, R/L common carotids
  up to `HANDOFF.neck_carotid` (z 156 — the head continues them), R/L subclavian → axillary to
  `HANDOFF.axilla_artery` (girdle map), vertebral arteries up through the C6–C3 transverse
  foramina to `HANDOFF.neck_vertebral`, intercostal arteries along the lower rib borders,
  celiac trunk (+ hepatic, splenic, left gastric), SMA (+ fan into the mesentery), IMA, renal
  arteries, gonadal (thin), common/internal/external iliacs to `HANDOFF.groin_femoral_artery`.
  Radius: aorta 1.1–1.3, carotids 0.35, subclavian 0.45, iliacs 0.5–0.6, renal 0.3.
* Veins (`Torso_Veins_*`): SVC, brachiocephalic veins, internal jugulars to `neck_jugular`,
  subclavian/axillary veins, IVC along `landmarks.IVC`, renal veins (left one crosses anterior to
  the aorta), hepatic veins (short), common/external iliac veins to `groin_femoral_vein`,
  azygos/hemiazygos along the spine, intercostal veins.
* Nerves (`Torso_Nerves_*`, cat nerve; `Torso_SpinalCord` cat nerve): spinal cord in the canal
  (`landmarks.canal_centre`) from `HANDOFF.neck_cord` down to the conus at L1/L2, cauda equina
  strands down the sacral canal, filum terminale; spinal nerve roots (dorsal root ganglia
  bulges) exiting every intervertebral foramen, intercostal nerves under each rib, brachial
  plexus (C5–T1 trunks/divisions/cords) to the axilla (girdle map), lumbar plexus → femoral
  nerve under the inguinal ligament (lateral to the femoral artery), sacral plexus → sciatic
  nerve leaving through the greater sciatic notch (`HANDOFF.sciatic_exit`), phrenic & vagus
  nerves down the mediastinum, sympathetic chains with ganglia along the vertebral bodies.

### 5.5 Arms (`arms.py`, ArmMap(+1) LeftArm and ArmMap(−1) RightArm; anatomical position:
palms forward, thumb lateral = +u, palm faces −v)
Landmarks (u, v, w) cm:
* Humerus: head sphere r2.3 at (0,0,0) (articular surface faces medially/up/back), anatomical &
  surgical neck, greater tubercle (2.0,−0.3,0.5) r1.3, lesser tubercle (0.5,−1.8,1.2) r0.8,
  intertubercular groove, shaft (1.0,0,3.5) r1.35 → (0.6,0,26) r1.05, deltoid tuberosity
  (1.8,−0.3,12), radial groove, medial epicondyle (−2.9,0.2,30.5) r0.7 (prominent), lateral
  epicondyle (2.6,0.2,30.2), trochlea (spool along u from −1.9 to 0.2 at v −0.3, w 32, r1.0),
  capitulum (1.3,−0.6,32) r0.95, olecranon fossa (posterior), coronoid & radial fossae.
* Ulna: olecranon (−0.9,1.2,31.0), trochlear notch hugging the trochlea, coronoid process
  (−0.9,−0.9,33.5), radial notch, tuberosity, shaft (−1.0,0.2,35) r0.85 → (−1.4,0.3,57) r0.5,
  head (−1.5,0.3,58.5) r0.75, styloid (−1.7,0.8,59.8).
* Radius: head disc (1.3,−0.5,33.5) r1.05 h0.9 concave top under the capitulum, neck, radial
  tuberosity (0.9,−0.3,36.5), bowed shaft (1.2,−0.3,36) → (1.8,−0.2,46) → (1.3,−0.2,57.5) widening
  to a broad distal end (2.6 × 1.6), styloid (2.4,0,58.8), ulnar notch, dorsal (Lister) tubercle.
* Carpals (w 59.5–63.5): scaphoid (1.9,−0.3,60.6), lunate (0.4,0,60.4), triquetrum (−1.0,0.1,60.8),
  pisiform (−1.2,−0.8,61.0); trapezium (2.3,−0.6,62.4), trapezoid (1.25,−0.2,62.6), capitate
  (0.1,−0.1,62.7), hamate (−1.2,0,62.5) + hook (−1.1,−0.9,62.6). Real shapes, small gaps.
* Metacarpals base→head: MC1 (2.6,−0.8,63.0)→(4.0,−2.2,67.0); MC2 (1.4,−0.2,63.6)→(1.9,−0.4,70.2);
  MC3 (0.2,−0.2,63.8)→(0.4,−0.4,70.0); MC4 (−0.9,−0.1,63.6)→(−1.0,−0.4,69.3); MC5 (−1.9,0,63.4)→
  (−2.3,−0.4,68.6). Phalanges (prox/mid/dist cm): index 4.0/2.4/1.7, middle 4.5/2.9/1.9, ring
  4.2/2.7/1.8, little 3.4/1.9/1.6, thumb 3.0/–/2.2 (continues MC1). Fingertip ≈ w 79.3 (Z≈2.01).
  Distal tufts, condyles at heads, concave bases, sesamoids at MC1 head.
* Joints: humeral head cartilage, elbow cartilage (trochlea, capitulum, radial head, trochlear
  notch), annular ligament, ulnar & radial collateral ligaments, wrist TFCC + cartilage, flexor
  retinaculum, MCP/IP cartilage caps. The glenoid is in the torso (5.1).
* Vessels (connect at the top to torso `HANDOFF.axilla_artery` ≈ stud (±1.125, 0.02, 3.64) →
  arm local ≈ (−3.0, 0.8, 0.9)): axillary/brachial artery (medial arm) → cubital fossa → radial &
  ulnar arteries → superficial & deep palmar arches → common/proper digital arteries;
  brachial veins, cephalic (lateral superficial), basilic (medial), median cubital vein, dorsal
  venous network of the hand.
* Nerves: median (with brachial artery → carpal tunnel → thenar + digital branches), ulnar
  (behind the medial epicondyle → Guyon canal → hand), radial (spiral groove → lateral elbow →
  superficial branch), musculocutaneous.
* Parts per arm: Humerus, Radius, Ulna, Carpals, Metacarpals, Phalanges, Cartilage, Ligaments,
  Arteries, Veins, Nerves (e.g. `LeftArm_Humerus`).

### 5.6 Legs (`legs.py`, LegMap(+1) LeftLeg and LegMap(−1) RightLeg)
Landmarks (u, v, w) cm, floor at w = 91:
* Femur: head sphere r2.4 at (0,0,0) with fovea, neck (0.8,−0.2,0.6) r1.6 → (4.0,0.2,2.6) r1.5
  (≈125°), greater trochanter E((5.2,0.6,2.0),(1.6,1.8,2.2)), lesser trochanter (1.8,1.3,6.5) r0.9,
  intertrochanteric line/crest, shaft (3.4,0,7) r1.45 → (1.4,−0.3,36) r1.35 with anterior bow,
  linea aspera (posterior ridge), distal flare, medial condyle E((−1.8,0.8,42.0),(1.6,2.6,2.0)),
  lateral condyle E((2.5,0.8,41.8),(1.6,2.6,2.0)), intercondylar notch (posterior), patellar
  groove (anterior), epicondyles, adductor tubercle.
* Patella (0.6,−3.3,39.5) ~ (4.4 × 2.0 × 4.8), apex down, posterior facets.
* Tibia: condyles medial E((−1.8,0.4,45.2),(2.0,2.4,1.4)) / lateral E((2.2,0.4,45.2),(1.9,2.3,1.4)),
  plateau top w≈44, intercondylar eminence, tuberosity (0.5,−2.0,48.5), triangular shaft with
  anterior crest (0.6,0.1,47) r2.0 → (0.6,0,77) r1.1, distal end, medial malleolus (−1.6,0.2,82.2)
  down to w 83.3, fibular notch.
* Fibula: head (4.0,1.2,47.5) r1.1, thin shaft (3.9,1.1,49) → (3.6,0.8,80) r0.55, lateral malleolus
  (3.6,0.8,83.3) (lower than the medial one).
* Tarsals: talus (body (0.5,0.5,84.0) with trochlear dome under the tibial plafond, neck/head →
  (−0.2,−2.6,84.8)), calcaneus (heel (0.5,4.5,88.0) r1.9 → (1.3,−2.0,87.2), tuberosity near the
  floor, sustentaculum tali medial), navicular (−0.8,−3.8,85.5), cuboid (2.0,−3.4,87.6),
  cuneiforms medial (−1.2,−5.6,86.5) / intermediate (0,−5.4,86.2) / lateral (1.1,−5.3,86.6).
  Longitudinal & transverse arches.
* Metatarsals base→head: MT1 (−1.2,−6.8,87)→(−1.5,−12.8,89.6) thick; MT2 (0.1,−6.9,87)→(−0.1,−14.0,90.0);
  MT3 (1.0,−6.7,87.4)→(1.0,−13.5,90.1); MT4 (1.9,−6.3,88.0)→(2.0,−12.8,90.2); MT5 (2.9,−5.3,88.7)→
  (3.2,−11.8,90.3) + tuberosity. Toe phalanges: hallux prox 2.7 / dist 2.1; toes 2–5 prox
  2.6/2.3/2.1/1.8, mid 1.1/1.0/0.9/0.7, dist 0.9/0.8/0.8/0.7; sesamoids under MT1 head. Lowest
  bone points ≈ w 90.4–90.6.
* Joints: femoral head cartilage (the acetabulum is in the torso), femoral condyle & patellar
  groove cartilage, tibial plateau cartilage, patellar cartilage, menisci (medial C, lateral ≈O,
  wedge section), ACL (1.0,1.5,42.0)→(0.0,−0.6,44.2), PCL (−0.5,0.2,41.5)→(0.3,1.8,45.0),
  MCL (flat band −3.2,0.3,40.5 → −2.4,0,50), LCL (3.6,0.6,40.8)→ fibular head, patellar ligament
  (patella apex → tuberosity), quadriceps tendon stub, talar dome cartilage, deltoid ligament,
  ATFL/CFL, Achilles tendon (calcaneus → w≈62), plantar fascia, interosseous membrane.
* Vessels: femoral artery starts ≈ (−0.6,−5.5,1.7) (meets torso), → adductor canal (−2.2,−1.5,26) →
  popliteal (0.3,3.2,40) → anterior tibial (through the membrane → dorsalis pedis), posterior
  tibial (behind the medial malleolus → plantar arteries), fibular artery; femoral & popliteal
  veins, great saphenous (superficial medial, from the dorsal venous arch in front of the medial
  malleolus to the groin), small saphenous (behind lateral malleolus → popliteal).
* Nerves: sciatic (posterior thigh from (1.5,4.0,3)) → tibial & common fibular (around the
  fibular neck → deep & superficial fibular), femoral nerve (anterior, short branches) +
  saphenous, plantar nerves.
* Parts per leg: Femur, Patella, Tibia, Fibula, Tarsals, Metatarsals, Phalanges, Cartilage,
  Menisci, Ligaments, Tendons, Arteries, Veins, Nerves.

## 6. Export & Roblox (for the Roblox-script and integration work)
* `export.py` (Blender) loads every built part, adds 4 tiny alignment marker cubes and exports
  one FBX + one GLB (`../dist/`). Markers (Blender studs → expected Roblox rig space relative to
  the R6 Torso centre, Roblox axes): `REF_A` (0,0,3) → (0,0,0); `REF_B` (0,0,5.2) → (0,2.2,0);
  `REF_C` (1.5,0,3) → (−1.5,0,0); `REF_D` (0,−0.6,3) → (0,0,−0.6). General point mapping
  Blender (bx,by,bz) → Roblox rig (−bx, bz−3, by) (character faces −Z, its left = −X).
* After File ▸ Import 3D the user runs a command-bar script that, for each imported model,
  solves the similarity transform from the 4 markers (so unit scale / axis settings / placement
  of the import do not matter), builds a standard R6 rig (HumanoidRootPart, Torso, Head with
  SpecialMesh Head 1.25, Left/Right Arm, Left/Right Leg, Humanoid RigType R6, standard Motor6Ds),
  makes the skin parts semi-transparent, moves/scales every anatomy MeshPart into place, welds it
  to its R6 part (by name prefix, fallback by position), sets Massless/CanCollide=false etc.
* `build/manifest.json`: name → {region, cat, base, tris, info} for every part.

## 6b. Jointed rig ("R6 articulé", current version)
The look stays R6 but each limb is split at the elbow / knee: 10 body parts and 10 Motor6Ds,
all defined once in `rig_spec.py` (parts, centres, sizes, pivots, C0/C1, the RightHand grip, the
Lua `RIG` table that `make_lua.py` injects into the Roblox scripts). Pivots (Roblox rig space):
shoulders (±1.2, 0.66, 0) on the humeral heads, elbows (±1.5, 0, 0) on the trochlea axis, hips
(±0.5, −1, 0), knees (±0.5, −1.95, 0) on the condyle axis; split planes Blender Z = 3.0 (elbow) and
1.05 (knee). Humanoid RigType R15, HipHeight 2; limb joints use identity C0/C1 rotations, RootJoint
and Neck keep the R6 ones.
* Regions are the part names (`Head`, `Torso`, `RightUpperArm`, `RightLowerArm`, …). `arms.py` /
  `legs.py` give every structure its segment through `segments.segment(parts, plan, labels)`:
  bones and joint cartilages go to one segment, structures that cross the joint (ligaments,
  vessels, nerves, tendons) are duplicated and cut by `meshops.clip_plane` at the split plane
  (`Part.clip`), with capped cut faces.
* `survivor.py` builds each sleeve / trouser leg as two pieces with a half-cylinder hinge around
  the elbow / knee axis, so bending never opens a gap.
* `anim.py`: kinematic model of the jointed rig; walk / run / crouch walk are planted-foot gaits
  (heel-to-toe rocker contact moving at the clip speed, knee profile + hidden thigh telescoping
  solved per frame), crouch walk and climbing use 2-bone IK, prone / crawl poses were solved
  offline (least squares) so forearms and knees rest on the ground. `export_luau_table` writes
  Motor6D.Transform keyframes per part (`parts` lists the keyed parts: `tool` is a right-arm
  overlay), `export_json` the world poses for the web viewer.

## 7. IMPORTANT fix (lead, during the run)
A face-winding bug in the shared mesher made every SDF mesh inside-out (normals inward). It is
fixed in `sdf.mesh_sdf` / `meshops.orient_outward` (meshes are now oriented by signed volume).
Consequences: (1) any part built before the fix has inverted normals AND too-dark baked colours
(AO was sampled inside the shape) — it must be rebuilt; (2) colours judged on renders made before
the fix looked ~40% too dark, do not "compensate" by brightening palettes. Roblox MeshParts are
single-sided, so outward winding is mandatory for tubes too (`parts.build_part` now orients them).
