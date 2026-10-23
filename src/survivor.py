"""R6 'survivor' outfit: the visible body of the character, built around the anatomy.

Every limb keeps the R6 block silhouette (so R6 animations and Motor6D work unchanged) and
encloses the noob skin shapes of skin.py with a small margin, which is what guarantees that no
bone or organ ever shows through when the outfit is opaque.

Shapes are written directly in studs (Blender coords: X = character's left, Y = back, Z = up,
front = -Y). Each part is an assembly of components; a vertex takes the colour of the component
whose surface is nearest, so pockets, straps, laces... keep crisp colours on one mesh.
"""
import numpy as np
import sdf as S
from sdf import box, ecyl, sphere, ellipsoid, capsule, intersect, union, subtract, halfspace, smooth_union, \
    displace, fbm, perlin
from parts import Part
import colors as CL
import skin
from skin import StudMap, BEVEL, HEAD_C, HEAD_R, HEAD_HZ, HEAD_RND


def rgb(r, g, b):
    return np.array((r, g, b), float) / 255


SKIN = rgb(212, 156, 120)
SKIN_SHADOW = rgb(176, 122, 96)
STUBBLE = rgb(118, 92, 80)
JACKET = rgb(72, 80, 48)
JACKET_DARK = rgb(50, 56, 34)
JACKET_LIGHT = rgb(96, 102, 68)
SHIRT = rgb(158, 150, 132)
SHIRT_DARK = rgb(124, 116, 100)
DENIM = rgb(42, 54, 78)
DENIM_LIGHT = rgb(82, 96, 122)
THREAD = rgb(196, 150, 70)
BOOT = rgb(98, 64, 40)
BOOT_DARK = rgb(64, 42, 28)
SOLE = rgb(36, 33, 30)
LACE = rgb(172, 146, 104)
GLOVE = rgb(42, 42, 44)
BEANIE = rgb(102, 33, 35)
HAIR = rgb(58, 40, 28)
PACK = rgb(116, 102, 72)
PACK_DARK = rgb(84, 74, 52)
STRAP = rgb(44, 44, 40)
PLASTIC = rgb(30, 30, 30)
METAL = rgb(150, 150, 146)
BRASS = rgb(166, 140, 84)
BANDAGE = rgb(222, 214, 194)
BLOOD = rgb(112, 26, 22)
BELT = rgb(66, 44, 30)
BEDROLL = rgb(72, 86, 76)
CANTEEN = rgb(82, 90, 64)
DIRT = rgb(84, 70, 52)

R_FRONT = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)     # plate frame: local x=X, y=Z, normal=Y
R_SIDE = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float)      # plate frame: local x=Y, y=Z, normal=X


# ----------------------------------------------------------------------------------------------
# assembly: components with their own colour

class Comp:
    def __init__(self, name, node, color, cut=False):
        self.name, self.node, self.color, self.cut = name, node, color, cut


def const(c):
    c = np.asarray(c, float)
    return lambda P, N: np.tile(c, (len(P), 1))


def grime(P, base, amount=0.35, scale=2.2, seed=0, tint=DIRT):
    """Patchy dirt + gentle tone variation (no high frequencies: vertex colours are ~0.04 stud apart)."""
    n = fbm(P * scale, 3, seed=seed)
    fine = perlin(P * 7.0, seed + 3)
    t = np.clip(0.5 + 1.4 * n, 0, 1) ** 2 * amount
    col = CL.mix(base, tint, t)
    return np.clip(col * (1 + 0.06 * fine)[:, None], 0, 1)


def fabric(base, amount=0.3, seed=0, low=None):
    """Fabric colour: dirt patches, more dirt towards z=low (hem), fine weave noise."""
    def f(P, N):
        col = grime(P, base, amount, seed=seed)
        if low is not None:
            t = np.clip((low + 0.35 - P[:, 2]) / 0.35, 0, 1) * 0.35
            col = CL.mix(col, DIRT, t)
        return col
    return f


def assemble(adds, cuts=(), guard=None, ao_k=0.32, cav_k=0.28, light=0.10):
    """SDF of the part + colour function (nearest component wins)."""
    node = union(*[c.node for c in adds])
    if cuts:
        node = subtract(node, *[c.node for c in cuts])
    if guard is not None:
        node = union(node, guard.node)
    comps = list(adds) + list(cuts) + ([guard] if guard is not None else [])

    def color(ctx):
        P, N = ctx['ps'], ctx['n']
        D = np.stack([np.abs(c.node.ev(P)) for c in comps])
        idx = D.argmin(0)
        col = np.zeros((len(P), 3))
        for i, c in enumerate(comps):
            m = idx == i
            if m.any():
                col[m] = c.color(P[m], N[m])
        return CL.shade(col, ctx, ao_k, cav_k, light)
    return node, color


def obox(a, b, width, thick, normal, rnd=0.006):
    """Box from point a to point b (length axis), `width` across, `thick` along `normal` (full sizes)."""
    a, b, n = np.asarray(a, float), np.asarray(b, float), np.asarray(normal, float)
    x = b - a; L = np.linalg.norm(x); x /= L
    n = n - x * (n @ x); n /= np.linalg.norm(n)
    y = np.cross(n, x)
    R = np.stack([x, y, n])
    return box((a + b) / 2, (L / 2, width / 2, thick / 2), R=R, rnd=rnd)


def fplate(cx, cz, y, poly, thick, rnd=0.004):
    """Plate lying on a front/back face: poly in (x, z) relative to (cx, cz), centred at depth y."""
    return S.plate((cx, y, cz), R_FRONT, poly, thick / 2, rnd=rnd)


def splate(x, cy, cz, poly, thick, rnd=0.004):
    """Plate lying on a side face: poly in (y, z) relative to (cy, cz), centred at x."""
    return S.plate((x, cy, cz), R_SIDE, poly, thick / 2, rnd=rnd)


def rect(w, h):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


def wrinkles(node, region, amp, freq, axis=2, seed=0):
    """Fabric folds: soft creases along `axis` whose spacing, depth and direction drift with noise,
    inside region(P) (0..1)."""
    def fn(P):
        warp = 2.6 * fbm(P * 2.3, 3, seed=seed) + 0.9 * P[:, (axis + 1) % 3] * freq * 0.35 * np.sin(seed)
        ph = P[:, axis] * freq * 2 * np.pi + warp * np.pi
        depth = np.clip(0.55 + 0.9 * fbm(P * 4.1, 2, seed=seed + 5), 0, 1)
        crease = (0.5 + 0.5 * np.sin(ph)) ** 2
        return amp * region(P) * depth * crease
    return displace(node, fn, amp)


def band_mask(z0, z1, soft=0.04, axis=2):
    def m(P):
        z = P[:, axis]
        return np.clip((z - z0) / soft, 0, 1) * np.clip((z1 - z) / soft, 0, 1)
    return m


# ----------------------------------------------------------------------------------------------
# torso: open field jacket over a t-shirt, backpack shoulder straps, belt, dog tags

def gap_halfwidth(z):
    """Half width of the jacket opening (V-shaped neckline, narrower at the hem)."""
    return np.interp(z, [1.9, 3.55, 4.05], [0.235, 0.30, 0.40])


def torso_part():
    jacket_box = box((0, 0, 2.99), (1.03, 0.532, 1.03), rnd=0.11)
    body = wrinkles(jacket_box, lambda P: band_mask(2.05, 2.55)(P) * (P[:, 1] < 0) + 0.6 * band_mask(3.55, 3.95)(P)
                    * (np.abs(P[:, 0]) > 0.75), 0.006, 9.0, seed=11)
    gap_poly = [(-0.40, 1.1), (0.40, 1.1), (0.30, 0.55), (0.235, -1.12), (-0.235, -1.12), (-0.30, 0.55)]
    gap_cut = fplate(0, 3.0, -0.60, gap_poly, 0.19, rnd=0.0)

    def jacket_col(P, N):
        col = fabric(JACKET, 0.32, seed=1, low=1.96)(P, N)
        wear = np.clip(perlin(P * 9.0, 4) * 2.2 - 0.9, 0, 1) * 0.25
        return CL.mix(col, JACKET_LIGHT, wear)

    hem = box((0, 0, 2.01), (1.04, 0.542, 0.055), rnd=0.045)
    hem = subtract(hem, fplate(0, 3.0, -0.62, gap_poly, 0.2, rnd=0.0))
    comps = [Comp('jacket', subtract(body, gap_cut), jacket_col),
             Comp('hem', hem, fabric(JACKET_DARK, 0.4, seed=2, low=1.96))]

    # lapels folded over at the top of the opening
    for s in (1, -1):
        poly = [(s * 0.30, 3.47), (s * 0.41, 4.035), (s * 0.68, 4.035), (s * 0.49, 3.77)]
        if s < 0:
            poly = poly[::-1]
        comps.append(Comp('lapel', fplate(0, 0, -0.543, poly, 0.022, rnd=0.006), fabric(JACKET_LIGHT, 0.25, seed=3)))
    # rolled hood along the back of the collar
    ang = np.radians(np.linspace(-62, 62, 13))
    hood_pts = [(0.70 * np.sin(a), 0.10 + 0.46 * np.cos(a), 4.0 + 0.05 * np.cos(a)) for a in ang]
    hood_r = [0.07 + 0.065 * np.cos(a) ** 1.5 for a in ang]
    comps.append(Comp('hood', S.tube(hood_pts, hood_r, k=0.05), fabric(JACKET_LIGHT, 0.3, seed=4)))

    # zipper tapes along the opening + pull
    def zip_tape(s):
        zs = np.linspace(1.97, 3.47, 7)
        pts = [(s * (gap_halfwidth(z) + 0.022), -0.538, z) for z in zs]
        return S.tube(pts, 0.016, k=0.0)
    comps.append(Comp('zip', union(zip_tape(1), zip_tape(-1)), const(rgb(58, 58, 56))))
    comps.append(Comp('zip_pull', box((0.262, -0.552, 2.06), (0.016, 0.008, 0.035), rnd=0.006), const(METAL)))

    # slanted hand-warmer pockets: raised welt + dark slit
    for s in (1, -1):
        comps.append(Comp('welt', obox((s * 0.46, -0.534, 2.42), (s * 0.76, -0.534, 2.80), 0.035, 0.022,
                                       (0, -1, 0), rnd=0.008), fabric(JACKET_DARK, 0.3, seed=5)))
    cuts = [Comp('slit', union(*[obox((s * 0.47, -0.548, 2.40), (s * 0.77, -0.548, 2.78), 0.012, 0.03, (0, -1, 0),
                                      rnd=0.0) for s in (1, -1)]), const(rgb(24, 26, 18)), cut=True)]

    # backpack shoulder straps: front run, over the shoulder, adjuster, tail
    for s in (1, -1):
        x = s * 0.62
        front = box((x, -0.553, 3.33), (0.085, 0.018, 0.70), rnd=0.008)
        top = box((x, 0.0, 4.04), (0.085, 0.555, 0.02), rnd=0.012)
        comps.append(Comp('strap', smooth_union(front, top, 0.03), fabric(STRAP, 0.25, seed=6)))
        comps.append(Comp('adjuster', box((x, -0.575, 2.66), (0.06, 0.012, 0.03), rnd=0.006), const(PLASTIC)))
        comps.append(Comp('tail', box((x, -0.562, 2.50), (0.06, 0.01, 0.13), rnd=0.006), fabric(STRAP, 0.2, seed=7)))
    # sternum strap + buckle
    comps.append(Comp('sternum', box((0, -0.574, 3.30), (0.63, 0.010, 0.026), rnd=0.006), fabric(STRAP, 0.2, seed=8)))
    comps.append(Comp('buckle', box((0, -0.586, 3.30), (0.05, 0.012, 0.038), rnd=0.008), const(PLASTIC)))
    # flashlight clipped on the left strap
    comps.append(Comp('torch', capsule((0.62, -0.60, 3.30), (0.62, -0.60, 3.62), 0.045), const(rgb(26, 26, 26))))
    comps.append(Comp('torch_lens', S.ecyl((0.62, -0.60, 3.64), 0.05, 0.05, 0.022, rnd=0.012),
                      const(rgb(232, 220, 160))))
    # belt in the opening + buckle frame
    comps.append(Comp('belt', box((0, -0.512, 2.09), (0.33, 0.012, 0.06), rnd=0.006), fabric(BELT, 0.25, seed=9)))
    comps.append(Comp('belt_buckle', box((0, -0.526, 2.09), (0.065, 0.008, 0.05), rnd=0.008), const(METAL)))
    # dog tags on the shirt
    comps.append(Comp('tags', union(box((-0.025, -0.519, 3.40), (0.026, 0.008, 0.044), rnd=0.012),
                                    box((0.02, -0.523, 3.38), (0.026, 0.008, 0.044), rnd=0.012)), const(METAL)))

    def guard_col(P, N):
        """The shirt shows in the opening; elsewhere the guard is hidden under the jacket."""
        shirt = grime(P, SHIRT, 0.4, scale=3.0, seed=12)
        # crew neck, a stain, the dog-tag chain
        neck = np.clip((P[:, 2] - 3.90) / 0.03, 0, 1)
        shirt = CL.mix(shirt, SHIRT_DARK, neck * 0.9)
        st = np.exp(-(((P[:, 0] - 0.06) / 0.09) ** 2 + ((P[:, 2] - 2.72) / 0.12) ** 2))
        shirt = CL.mix(shirt, rgb(120, 100, 76), st * 0.6)
        chain = np.zeros(len(P))
        for s in (1, -1):
            a, b = np.array([s * 0.19, 3.99]), np.array([s * 0.004, 3.45])
            q = np.stack([P[:, 0], P[:, 2]], 1)
            t = np.clip(((q - a) @ (b - a)) / ((b - a) @ (b - a)), 0, 1)
            dist = np.linalg.norm(q - a - np.outer(t, b - a), axis=1)
            dots = 0.5 + 0.5 * np.sin(t * 130)
            chain = np.maximum(chain, (dist < 0.007) * dots)
        shirt = CL.mix(shirt, rgb(120, 120, 116), chain)
        jacket = fabric(JACKET, 0.32, seed=1)(P, N)
        in_gap = (np.abs(P[:, 0]) < gap_halfwidth(P[:, 2]) + 0.01) & (P[:, 1] < -0.3)
        return np.where(in_gap[:, None], shirt, jacket)

    guard = Comp('guard', box((0, 0, 3), (1.004, 0.506, 1.004), rnd=BEVEL + 0.004), guard_col)
    return assemble(comps, cuts, guard)


# ----------------------------------------------------------------------------------------------
# arms: rolled-up sleeves, forearm (bandage on the right, watch on the left), fingerless gloves

ELBOW_Z = 3.0                 # elbow pivot (rig_spec: Blender Z of the elbow line, y = 0)
KNEE_Z = 1.05                 # knee pivot (femoral condyle axis)
HINGE_INSET = 0.012           # hinge discs stay just inside the side faces: no coplanar overlap at rest


def hinge(x0, hw, zp, r, below):
    """Half cylinder around the joint axis (along X through y = 0, z = zp): the rounded end of a limb segment.
    The two segments of a limb share the same circle, so the joint stays closed at any bend angle."""
    lo, hi = (x0 - hw, -r - 0.01, zp - r - 0.01), (x0 + hw, r + 0.01, zp + r + 0.01)
    cyl = S.SDF(lambda p, l, h, zp=zp, r=r: np.sqrt(p[:, 1] ** 2 + (p[:, 2] - zp) ** 2) - r, lo, hi)
    slab = box((x0, 0, zp), (hw - HINGE_INSET, r + 0.05, r + 0.05))
    side = halfspace((0, 0, zp), (0, 0, 1)) if below else halfspace((0, 0, zp), (0, 0, -1))
    return intersect(cyl, slab, side)


def segment_box(c, half, rnd, zp, upper):
    """Rounded box cut flat at the joint plane (no rounded edge there: the hinge closes the end)."""
    return intersect(box(c, half, rnd=rnd), halfspace((0, 0, zp), (0, 0, -1)) if upper else halfspace((0, 0, zp), (0, 0, 1)))


def arm_parts(s):
    """Upper arm (sleeve, elbow patch, shoulder patch) and lower arm (rolled sleeve, cuff, bare forearm,
    bandage or watch, mitten), hinged at the elbow."""
    x0 = s * 1.5
    xs = x0 + s * 0.008
    folds = lambda P: band_mask(2.95, 3.40)(P) + 0.5 * band_mask(2.84, 2.95)(P)
    sleeve_col = fabric(JACKET, 0.3, seed=21 + s)
    # ---- upper arm
    up_box = segment_box((xs, 0, 3.165), (0.512, 0.524, 0.865), 0.10, ELBOW_Z, True)      # rounded top at z = 4.03
    sleeve_u = union(wrinkles(up_box, folds, 0.008, 8.0, seed=20 + s), hinge(xs, 0.512, ELBOW_Z, 0.524, True))
    comps_u = [Comp('sleeve', sleeve_u, sleeve_col)]
    comps_u.append(Comp('elbow_patch', fplate(x0 + s * 0.06, 3.24, 0.532, [(np.cos(a) * 0.24, np.sin(a) * 0.15)
                        for a in np.linspace(0, 2 * np.pi, 20, endpoint=False)], 0.016, rnd=0.008),
                        fabric(JACKET_DARK, 0.4, seed=24 + s)))
    if s > 0:
        patch = splate(s * 2.021, -0.02, 3.52, rect(0.30, 0.26), 0.012, rnd=0.012)

        def patch_col(P, N):
            u, v = P[:, 1] + 0.02, P[:, 2] - 3.52
            col = np.tile(rgb(60, 60, 44), (len(P), 1))
            border = (np.abs(u) > 0.125) | (np.abs(v) > 0.105)
            mountain = (v < 0.06 - 1.4 * np.abs(u + 0.03)) & (v > -0.09)
            peak = (v < 0.03 - 1.6 * np.abs(u - 0.06)) & (v > -0.09)
            col[mountain | peak] = rgb(200, 180, 120)
            col[border] = rgb(150, 130, 80)
            return col
        comps_u.append(Comp('patch', patch, patch_col))
    guard_u = Comp('guard', union(segment_box((x0, 0, 3.0), (0.504, 0.504, 1.004), BEVEL + 0.004, ELBOW_Z, True),
                                  hinge(x0, 0.504, ELBOW_Z, 0.504, True)), sleeve_col)
    upper = assemble(comps_u, (), guard_u)

    # ---- lower arm
    lo_box = segment_box((xs, 0, 2.5), (0.512, 0.524, 0.5 + 0.25), 0.10, ELBOW_Z, False)
    lo_box = intersect(lo_box, halfspace((0, 0, 1.996), (0, 0, -1)))
    sleeve_l = intersect(union(wrinkles(lo_box, folds, 0.008, 8.0, seed=20 + s), hinge(xs, 0.512, ELBOW_Z, 0.524, False)),
                         halfspace((0, 0, 2.80), (0, 0, -1)))
    comps_l = [Comp('sleeve', sleeve_l, sleeve_col)]
    comps_l.append(Comp('cuff', box((x0 + s * 0.009, 0, 2.775), (0.524, 0.538, 0.068), rnd=0.05),
                        fabric(JACKET_LIGHT, 0.35, seed=22 + s)))
    comps_l.append(Comp('glove', box((x0 + s * 0.004, 0, 2.27), (0.509, 0.512, 0.155), rnd=0.04),
                        fabric(GLOVE, 0.2, seed=23 + s)))
    comps_l.append(Comp('glove_tab', splate(s * 2.013, 0.0, 2.33, rect(0.30, 0.06), 0.014, rnd=0.004),
                        const(rgb(70, 70, 72))))
    cuts = []
    for dx in (-0.25, 0.0, 0.25):
        cuts.append(Comp('finger_gap', box((x0 + dx, -0.508, 2.055), (0.007, 0.012, 0.062), rnd=0.003),
                         const(SKIN_SHADOW), cut=True))
    if s > 0:
        comps_l.append(Comp('watch_strap', box((x0 + s * 0.004, 0, 2.452), (0.512, 0.514, 0.022), rnd=0.012),
                            const(rgb(40, 34, 28))))
        comps_l.append(Comp('watch_case', box((s * 2.022, 0.0, 2.452), (0.014, 0.075, 0.055), rnd=0.012),
                            const(rgb(60, 60, 62))))
        comps_l.append(Comp('watch_glass', box((s * 2.034, 0.0, 2.452), (0.004, 0.055, 0.038), rnd=0.003),
                            const(rgb(170, 190, 180))))
    else:
        wraps = []
        for i, (z, tilt) in enumerate(((2.50, 6), (2.555, -5), (2.61, 4), (2.645, -3))):
            r = 0.5135 + 0.0025 * i
            wraps.append(box((x0, 0, z), (r, r, 0.034), R=S.rot_xyz(tilt, 0, 0), rnd=0.018))

        def bandage_col(P, N):
            col = grime(P, BANDAGE, 0.12, scale=4.0, seed=30)
            st = np.exp(-(((P[:, 1] + 0.18) / 0.16) ** 2 + ((P[:, 2] - 2.57) / 0.06) ** 2)) * (P[:, 0] < -1.6)
            st = np.maximum(st, 0.6 * np.exp(-(((P[:, 1] + 0.05) / 0.10) ** 2 + ((P[:, 2] - 2.50) / 0.04) ** 2))
                            * (P[:, 1] < -0.3))
            return CL.mix(col, BLOOD, np.clip(st * 1.3, 0, 0.92))
        comps_l.append(Comp('bandage', union(*wraps), bandage_col))

    def guard_col(P, N):
        skin_col = grime(P, SKIN, 0.18, scale=3.0, seed=31 + s, tint=rgb(150, 110, 84))
        return np.where((P[:, 2] < 2.73)[:, None], skin_col, sleeve_col(P, N))
    guard_l = Comp('guard', union(segment_box((x0, 0, 3.0), (0.504, 0.504, 1.004), BEVEL + 0.004, ELBOW_Z, False),
                                  hinge(x0, 0.504, ELBOW_Z, 0.504, False)), guard_col)
    lower = assemble(comps_l, cuts, guard_l)
    return upper, lower


# ----------------------------------------------------------------------------------------------
# legs: worn jeans (cargo pocket, torn knee / repair patch), leather boots with laces

def leg_parts(s):
    """Thigh (jeans with cargo pocket, torn or patched knee, rounded hip) and shin (jeans, laced leather boot),
    hinged at the knee."""
    x0 = s * 0.5
    xp = x0 + s * 0.0095
    knee_back = lambda P: band_mask(0.92, 1.18)(P) * (P[:, 1] > 0.1)
    stack = band_mask(0.60, 0.80)
    fold = lambda P: knee_back(P) + 0.8 * stack(P)

    def denim_base(P, N):
        col = grime(P, DENIM, 0.25, scale=2.5, seed=41 + s)
        twill = 0.5 + 0.5 * np.sin((P[:, 1] + P[:, 2]) * 260 + (P[:, 0]) * 260)
        fade = np.exp(-(((P[:, 2] - 1.12) / 0.32) ** 2)) * np.clip(-P[:, 1] * 2.5, 0, 1)
        fade = np.maximum(fade, 0.6 * np.exp(-(((P[:, 2] - 1.6) / 0.25) ** 2)) * np.clip(-P[:, 1] * 2, 0, 1))
        col = CL.mix(col, DENIM_LIGHT, np.clip(fade * 0.75 + 0.06 * twill, 0, 1))
        dirt = np.clip((0.95 - P[:, 2]) / 0.35, 0, 1) * 0.3
        return CL.mix(col, DIRT, dirt)
    denim = denim_base
    # ---- thigh
    up_box = segment_box((xp, 0, 1.52), (0.5115, 0.522, 0.60), 0.06, KNEE_Z, True)
    up_box = intersect(up_box, halfspace((0, 0, 2.0), (0, 0, 1)))
    pants = union(wrinkles(up_box, fold, 0.009, 11.0, seed=40 + s), hinge(xp, 0.5115, KNEE_Z, 0.522, True))
    # rounded hip: a half cylinder on the hip axis (Roblox Hip pivot line, z = 2, y = 0) fills the gap under the
    # jacket whenever the leg swings; it turns in place, so it never sticks out of the torso
    hip_x0, hip_x1 = (-0.002, 1.02) if s > 0 else (-1.02, 0.002)
    hip = intersect(S.SDF(lambda p, l, h: np.sqrt(p[:, 1] ** 2 + (p[:, 2] - 2.0) ** 2) - 0.522,
                          (hip_x0, -0.53, 1.45), (hip_x1, 0.53, 2.53)),
                    box(((hip_x0 + hip_x1) / 2, 0, 2.0), ((hip_x1 - hip_x0) / 2, 0.53, 0.53), rnd=0.05))
    pants = smooth_union(pants, hip, 0.02)
    cuts_u = [Comp('side_seam', box((s * 1.021, 0.0, 1.80), (0.008, 0.006, 0.19), rnd=0.003), const(rgb(36, 46, 66)),
                   cut=True)]
    comps_u = [None]
    comps_u.append(Comp('cargo', splate(s * 1.031, 0.0, 1.40, rect(0.34, 0.34), 0.026, rnd=0.012), denim_base))
    comps_u.append(Comp('cargo_flap', splate(s * 1.047, 0.0, 1.585, rect(0.36, 0.10), 0.03, rnd=0.012),
                        const(rgb(40, 52, 76))))
    comps_u.append(Comp('cargo_button', sphere((s * 1.066, 0.0, 1.555), 0.018), const(BRASS)))
    KZ = 1.17                                                     # knee cap (front of the thigh's lower end)
    if s > 0:
        hole = S.plate((x0, -0.53, KZ), R_FRONT, [(np.cos(a) * 0.15, np.sin(a) * 0.09)
                                                  for a in np.linspace(0, 2 * np.pi, 24, endpoint=False)], 0.03, rnd=0.0)
        cuts_u.append(Comp('tear', hole, const(SKIN), cut=True))
        threads = union(*[S.tube([(x0 - 0.15, -0.517, z), (x0 - 0.02, -0.511, z + 0.008), (x0 + 0.15, -0.517, z - 0.006)],
                                 0.0105) for z in (KZ - 0.05, KZ - 0.005, KZ + 0.04)])
        comps_u.append(Comp('threads', threads, const(rgb(222, 218, 204))))

        def denim(P, N):
            col = denim_base(P, N)
            e = np.sqrt(((P[:, 0] - x0) / 0.15) ** 2 + ((P[:, 2] - KZ) / 0.09) ** 2)
            fray = np.clip(1 - np.abs(e - 1.08) / 0.12, 0, 1) * (P[:, 1] < -0.4)
            return CL.mix(col, rgb(190, 192, 196), fray * 0.85)
    else:
        def patch_col(P, N):
            col = grime(P, rgb(70, 86, 112), 0.2, seed=44)
            u, v = P[:, 0] - x0, P[:, 2] - KZ
            edge = (np.abs(np.abs(u) - 0.105) < 0.008) | (np.abs(np.abs(v) - 0.085) < 0.008)
            stitch = edge & ((np.sin((u + v) * 160) > 0))
            col[stitch] = THREAD
            return col
        comps_u.append(Comp('knee_patch', fplate(x0, KZ, -0.528, rect(0.24, 0.19), 0.016, rnd=0.008), patch_col))
    comps_u[0] = Comp('pants', pants, denim)
    guard_u = Comp('guard', intersect(union(segment_box((x0, 0, 1.6), (0.504, 0.504, 0.55 + 0.25), BEVEL + 0.004, KNEE_Z, True),
                                            hinge(x0, 0.504, KNEE_Z, 0.504, True)),
                                      halfspace((0, 0, 2.0), (0, 0, 1))), denim)
    upper = assemble(comps_u, cuts_u, guard_u)

    # ---- shin
    lo_box = segment_box((xp, 0, 0.80), (0.5115, 0.522, 0.30 + 0.25), 0.06, KNEE_Z, False)
    lo_box = intersect(lo_box, halfspace((0, 0, 0.50), (0, 0, -1)))
    pants_l = union(wrinkles(lo_box, fold, 0.009, 11.0, seed=40 + s), hinge(xp, 0.5115, KNEE_Z, 0.522, False))
    comps_l = [Comp('pants', pants_l, denim_base)]
    cuts_l = [Comp('side_seam', box((s * 1.021, 0.0, 0.835), (0.008, 0.006, 0.165), rnd=0.003), const(rgb(36, 46, 66)),
                   cut=True)]
    xb = x0 + s * 0.0085
    shaft = box((xb, -0.006, 0.345), (0.515, 0.534, 0.285), rnd=0.065)
    shaft = wrinkles(shaft, lambda P: band_mask(0.22, 0.34)(P) * (P[:, 1] < -0.2), 0.006, 14.0, seed=45 + s)

    def leather(P, N):
        col = grime(P, BOOT, 0.3, scale=3.0, seed=46 + s, tint=rgb(60, 48, 36))
        scuff = np.clip(perlin(P * 14.0, 47) * 2.0 - 0.8, 0, 1) * 0.35
        return CL.mix(col, rgb(140, 104, 70), scuff)
    comps_l.append(Comp('boot', shaft, leather))
    comps_l.append(Comp('collar', box((xb, 0.0, 0.605), (0.526, 0.546, 0.04), rnd=0.036), const(BOOT_DARK)))
    comps_l.append(Comp('toe', ellipsoid((x0, -0.45, 0.13), (0.47, 0.15, 0.13)), leather))
    comps_l.append(Comp('heel', box((xb, 0.36, 0.06), (0.514, 0.19, 0.06), rnd=0.02), const(SOLE)))

    def sole_col(P, N):
        col = np.tile(SOLE, (len(P), 1))
        mid = (P[:, 2] > 0.064) & (P[:, 2] < 0.088)
        col[mid] = rgb(70, 60, 50)
        return col
    comps_l.append(Comp('sole', box((xb, -0.04, 0.044), (0.528, 0.575, 0.044), rnd=0.024), sole_col))
    comps_l.append(Comp('tongue', fplate(x0, 0.40, -0.541, rect(0.27, 0.40), 0.02, rnd=0.012), const(BOOT_DARK)))
    eyelets, laces = [], []
    zs = [0.24, 0.32, 0.40, 0.48, 0.56]
    for z in zs:
        for dx in (-0.165, 0.165):
            eyelets.append(sphere((x0 + dx, -0.541, z), 0.017))
    for z0, z1 in zip(zs[:-1], zs[1:]):
        laces.append(S.tube([(x0 - 0.165, -0.552, z0), (x0 + 0.165, -0.552, z1)], 0.011))
        laces.append(S.tube([(x0 + 0.165, -0.552, z0), (x0 - 0.165, -0.552, z1)], 0.011))
    laces.append(S.tube([(x0 - 0.165, -0.552, 0.56), (x0 - 0.05, -0.565, 0.63), (x0 + 0.03, -0.566, 0.58),
                         (x0 + 0.165, -0.552, 0.56)], 0.011))
    comps_l.append(Comp('eyelets', union(*eyelets), const(BRASS)))
    comps_l.append(Comp('laces', union(*laces), const(LACE)))
    comps_l.append(Comp('pull_tab', fplate(x0, 0.63, 0.553, rect(0.10, 0.12), 0.016, rnd=0.008), const(BOOT_DARK)))

    def guard_col(P, N):
        return np.where((P[:, 2] < 0.62)[:, None], leather(P, N), denim_base(P, N))
    guard_l = Comp('guard', union(segment_box((x0, 0, 0.6), (0.504, 0.504, 0.604), BEVEL + 0.004, KNEE_Z, False),
                                  hinge(x0, 0.504, KNEE_Z, 0.504, False)), guard_col)
    lower = assemble(comps_l, cuts_l, guard_l)
    return upper, lower


# ----------------------------------------------------------------------------------------------
# hat: knitted beanie (ribbed cuff, slouch) + hair showing under it

BEANIE_N = np.array([0.0, 0.0985, 1.0]) / np.linalg.norm([0.0, 0.0985, 1.0])


def beanie_cut_level(P):
    return P[:, 2] + 0.0985 * P[:, 1] - 4.765


def hat_part():
    dome = ecyl(HEAD_C, HEAD_R + 0.032, HEAD_R + 0.032, HEAD_HZ + 0.032, rnd=HEAD_RND + 0.032)
    slouch = ellipsoid((0, 0.24, 5.08), (0.46, 0.36, 0.17))
    dome = smooth_union(dome, slouch, 0.09)
    above = S.SDF(lambda p, l, h: -(beanie_cut_level(p) - 0.0) * 0.995, np.full(3, -1e4), np.full(3, 1e4))
    dome = intersect(dome, above)
    knit = lambda P: 0.004 * (0.5 + 0.5 * np.cos(40 * np.arctan2(P[:, 1], P[:, 0]))) \
        * (0.6 + 0.4 * np.sin(P[:, 2] * 90))
    dome = displace(dome, knit, 0.004)
    cuff = S.smooth_intersect(ecyl(HEAD_C, HEAD_R + 0.058, HEAD_R + 0.058, 0.6, rnd=0.0),
                              S.SDF(lambda p, l, h: np.abs(beanie_cut_level(p) - 0.068) - 0.068, np.full(3, -1e4),
                                    np.full(3, 1e4)), 0.03)
    cuff = displace(cuff, lambda P: 0.007 * (0.5 + 0.5 * np.cos(52 * np.arctan2(P[:, 1], P[:, 0]))), 0.007)

    def knit_col(P, N):
        col = grime(P, BEANIE, 0.22, scale=3.0, seed=50, tint=rgb(70, 30, 30))
        rib = 0.5 + 0.5 * np.cos(52 * np.arctan2(P[:, 1], P[:, 0]))
        return np.clip(col * (0.88 + 0.16 * rib)[:, None], 0, 1)
    comps = [Comp('beanie', dome, knit_col), Comp('cuff', cuff, knit_col)]
    # small leather tag on the cuff, front left
    a = np.radians(32)
    nrm = np.array([np.sin(a), -np.cos(a), 0.0])
    tan = np.array([np.cos(a), np.sin(a), 0.0])
    tag_c = nrm * (HEAD_R + 0.064)
    tag_c[2] = 4.765 - 0.0985 * tag_c[1] + 0.068
    comps.append(Comp('tag', obox(tag_c - 0.05 * tan, tag_c + 0.05 * tan, 0.072, 0.016, nrm, rnd=0.005),
                      const(rgb(120, 86, 56))))
    # hair: a ragged mass under the cuff (sides and back) + irregular clumps
    rs = np.random.RandomState(7)

    def hair_mass(p, l, h):
        ang = np.degrees(np.arctan2(p[:, 0], -p[:, 1]))
        side = np.clip((np.abs(ang) - 58) / 18, 0, 1)                       # none at the front
        depth = (0.06 + 0.10 * side + 0.04 * fbm(np.stack([ang / 9, p[:, 2] * 0, ang * 0], 1), 2, seed=52)) * side
        lev = beanie_cut_level(p)
        band = np.maximum(lev - 0.03, -(lev + depth))                       # from just inside the cuff down to depth
        shellr = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - (HEAD_R + 0.014)
        return np.maximum(np.maximum(shellr, band), -side + 0.02)
    mass = S.SDF(hair_mass, (-0.7, -0.7, 4.3), (0.7, 0.7, 4.95))
    clumps = []
    angs = np.r_[rs.uniform(64, 125, 7), rs.uniform(-125, -64, 7), rs.uniform(135, 225, 9)]
    for ang in np.radians(angs):
        d = np.array([np.sin(ang), -np.cos(ang), 0.0])          # ang measured from the front (-Y), towards +X
        ztop = 4.765 - 0.0985 * d[1] * HEAD_R - 0.02
        length = rs.uniform(0.06, 0.17)
        sweep = rs.uniform(-0.04, 0.04)
        tang = np.array([np.cos(ang), np.sin(ang), 0.0])
        a0 = d[:2] * (HEAD_R - 0.01)
        a1 = d[:2] * (HEAD_R + 0.03 + rs.uniform(0, 0.02)) + tang[:2] * sweep
        clumps.append(S.round_cone((a0[0], a0[1], ztop), (a1[0], a1[1], ztop - length), rs.uniform(0.035, 0.055),
                                   rs.uniform(0.010, 0.018)))
    hair = S.smooth_union(mass, S.smooth_union_all(clumps, 0.035), 0.03)

    def hair_col(P, N):
        col = grime(P, HAIR, 0.15, scale=6.0, seed=51, tint=rgb(30, 22, 16))
        streak = 0.5 + 0.5 * np.sin(np.arctan2(P[:, 1], P[:, 0]) * 70)
        return CL.mix(col, rgb(96, 70, 48), streak * 0.3)
    comps.append(Comp('hair', hair, hair_col))
    return assemble(comps, ao_k=0.3, cav_k=0.35)


# ----------------------------------------------------------------------------------------------
# head: classic R6 head shape (exact, analytic) painted with skin, stubble and dirt

def head_colors(V):
    P = V
    col = grime(P, SKIN, 0.12, scale=3.5, seed=60, tint=rgb(160, 112, 86))
    ang = np.degrees(np.arctan2(P[:, 0], -P[:, 1]))                     # 0 = front, +90 = character's left
    front = np.clip(1 - np.abs(ang) / 95, 0, 1)
    # cheeks
    for sx in (1, -1):
        ch = np.exp(-(((ang - sx * 42) / 18) ** 2 + ((P[:, 2] - 4.43) / 0.07) ** 2))
        col = CL.mix(col, rgb(214, 136, 112), ch * 0.35)
    # stubble: jaw, chin, upper lip
    stub = np.clip((4.43 - P[:, 2]) / 0.06, 0, 1) * np.clip((P[:, 2] - 3.95) / 0.05, 0, 1) * np.clip(1 - np.abs(ang) / 105, 0, 1)
    speck = np.clip(perlin(P * 95.0, 61) * 1.6 + 0.4, 0, 1)
    col = CL.mix(col, STUBBLE, stub * (0.35 + 0.35 * speck))
    # dirt smudges (left cheek, forehead)
    sm = np.exp(-(((ang - 55) / 16) ** 2 + ((P[:, 2] - 4.52) / 0.06) ** 2)) + \
        0.6 * np.exp(-(((ang + 20) / 20) ** 2 + ((P[:, 2] - 4.78) / 0.04) ** 2))
    sm *= np.clip(0.6 + fbm(P * 9, 2, seed=62), 0, 1)
    col = CL.mix(col, rgb(110, 86, 64), np.clip(sm, 0, 1) * 0.45 * front)
    return col


def head_mesh():
    v, f, cn = skin.revolved_head(nseg=160, k=24)
    return v, f, head_colors(v), cn


# ----------------------------------------------------------------------------------------------
# face: layered decal slabs on the head front (eyes, brows, mouth, band-aid, scratch)

def _ellipse(cx, cz, rx, rz):
    return lambda x, z: (np.sqrt(((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2) - 1) * min(rx, rz)


def _segs(pts, w):
    pts = np.asarray(pts, float)

    def f(x, z):
        q = np.stack([x, z], 1)
        d = np.full(len(x), 1e9)
        for a, b in zip(pts[:-1], pts[1:]):
            ba = b - a
            t = np.clip(((q - a) @ ba) / (ba @ ba), 0, 1)
            d = np.minimum(d, np.linalg.norm(q - a - np.outer(t, ba), axis=1) - w)
        return d
    return f


def _rrect(cx, cz, w, h, ang, r):
    ca, sa = np.cos(np.radians(ang)), np.sin(np.radians(ang))

    def f(x, z):
        u = (x - cx) * ca + (z - cz) * sa
        v = -(x - cx) * sa + (z - cz) * ca
        qx, qz = np.abs(u) - (w / 2 - r), np.abs(v) - (h / 2 - r)
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - r
    return f


def _union2(*fs):
    return lambda x, z: np.min([f(x, z) for f in fs], axis=0)


def _inter2(*fs):
    return lambda x, z: np.max([f(x, z) for f in fs], axis=0)


EYE_X, EYE_Z = 0.165, 4.60


def face_layers():
    """(offset above the head surface, [(region(x,z) sdf, colour), ...]) from bottom to top."""
    eyes, lids, irises, pupils, highs = [], [], [], [], []
    for s in (1, -1):
        cx = s * EYE_X
        white = _ellipse(cx, EYE_Z, 0.062, 0.072)
        lid_line = lambda x, z, cx=cx, s=s: (z - (EYE_Z + 0.040 - 0.10 * s * (x - cx)))       # tired, slanted lid
        eyes.append(_inter2(white, lid_line))
        lids.append(_inter2(_ellipse(cx, EYE_Z, 0.072, 0.082), lambda x, z, lf=lid_line: np.abs(lf(x, z)) - 0.010))
        irises.append(_inter2(_ellipse(cx - s * 0.006, EYE_Z - 0.006, 0.040, 0.044), lid_line))
        pupils.append(_inter2(_ellipse(cx - s * 0.006, EYE_Z - 0.008, 0.020, 0.022), lid_line))
        highs.append(_ellipse(cx - s * 0.006 + 0.013, EYE_Z + 0.008, 0.008, 0.008))
    brows = [_segs([(s * 0.075, 4.715), (s * 0.15, 4.735), (s * 0.255, 4.752)], 0.017) for s in (1, -1)]
    mouth = _segs([(-0.10, 4.355), (-0.03, 4.366), (0.05, 4.364), (0.105, 4.348)], 0.0085)
    under_eye = [_segs([(s * 0.12, 4.515), (s * 0.165, 4.507), (s * 0.21, 4.515)], 0.004) for s in (1, -1)]
    bandaid = _rrect(-0.30, 4.43, 0.16, 0.055, 28, 0.022)
    pad = _rrect(-0.30, 4.43, 0.055, 0.045, 28, 0.008)
    scratch = _union2(_segs([(0.20, 4.84), (0.27, 4.80)], 0.0045), _segs([(0.215, 4.825), (0.285, 4.79)], 0.0035))
    dark = rgb(34, 24, 20)
    return [
        (0.003, [(_union2(*eyes), rgb(236, 232, 222)), (bandaid, rgb(214, 176, 138)), (scratch, rgb(150, 40, 34))]),
        (0.007, [(_union2(*irises), rgb(92, 64, 40)), (_union2(*brows), rgb(48, 32, 24)), (mouth, rgb(96, 46, 40)),
                  (_union2(*under_eye), rgb(150, 104, 86)), (pad, rgb(236, 220, 196))]),
        (0.011, [(_union2(*pupils), rgb(16, 12, 10))]),
        (0.015, [(_union2(*highs), rgb(250, 250, 250)), (_union2(*lids), dark)]),
    ]


def face_mesh():
    """Each decal region is meshed on its own small grid as a thin slab hugging the head front."""
    import meshops as M
    hd = skin.head()
    V, F, Cs, raw = [], [], [], []
    off = 0
    gx = np.linspace(-0.42, 0.42, 421)
    gz = np.linspace(4.22, 4.92, 351)
    GX, GZ = np.meshgrid(gx, gz, indexing='ij')
    for level, regions in face_layers():
        for reg, col in regions:
            inside = reg(GX.ravel(), GZ.ravel()).reshape(GX.shape) < 0.004
            if not inside.any():
                continue
            xs, zs = GX[inside], GZ[inside]
            lo = np.array([xs.min() - 0.01, -0.68, zs.min() - 0.01])
            hi = np.array([xs.max() + 0.01, -0.40, zs.max() + 0.01])

            def f(p, l, h, level=level, reg=reg):
                layer = np.abs(hd.ev(p) - level) - 0.0017
                return np.maximum(np.maximum(layer, reg(p[:, 0], p[:, 2])), p[:, 1] + 0.3)
            node = S.SDF(f, lo, hi)
            v, fa = S.mesh_sdf(node, lambda q: q, 0.0012, lo, hi, 1.0, far=0.02)
            if len(fa):
                raw.append((v, fa, col))
    budget = 14000                                  # Roblox: 20 000 triangles max per MeshPart
    total = sum(len(fa) for _, fa, _ in raw)
    for v, fa, col in raw:
        v, fa = M.finalize(v, fa, max(80, int(len(fa) * budget / total)), 1, 4)
        V.append(v); F.append(fa + off); Cs.append(np.tile(col, (len(v), 1))); off += len(v)
    v, f, c = np.concatenate(V), np.concatenate(F), np.concatenate(Cs)
    n = M.vertex_normals(v, f)
    return v, f, c, n[f]


# ----------------------------------------------------------------------------------------------
# backpack: main bag, lid, front pocket with webbing, side canteen, bedroll on top

def backpack_part():
    main = box((0, 0.835, 3.02), (0.70, 0.29, 0.78), rnd=0.14)
    bulge = lambda P: -0.035 * np.clip(1 - (P[:, 0] / 0.7) ** 2, 0, 1) * np.clip(1 - ((P[:, 2] - 3.02) / 0.78) ** 2, 0, 1) \
        * np.clip((P[:, 1] - 0.85) / 0.2, 0, 1)
    main = displace(main, bulge, 0.035)
    main = wrinkles(main, lambda P: band_mask(2.3, 3.7)(P) * (np.abs(P[:, 0]) > 0.55), 0.007, 7.0, seed=70)
    comps = [Comp('bag', main, fabric(PACK, 0.3, seed=71, low=2.24))]
    comps.append(Comp('pocket', box((0, 1.20, 2.74), (0.52, 0.11, 0.42), rnd=0.08), fabric(PACK_DARK, 0.3, seed=72)))
    webbing = union(*[box((0, 1.313, z), (0.42, 0.008, 0.018), rnd=0.004) for z in (2.62, 2.74, 2.86)])
    comps.append(Comp('webbing', webbing, const(STRAP)))
    comps.append(Comp('lid', box((0, 0.85, 3.80), (0.715, 0.315, 0.075), rnd=0.06), fabric(PACK_DARK, 0.3, seed=73)))
    comps.append(Comp('lid_front', box((0, 1.136, 3.66), (0.56, 0.022, 0.20), rnd=0.03), fabric(PACK_DARK, 0.3, seed=74)))
    for s in (1, -1):
        comps.append(Comp('lid_strap', box((s * 0.32, 1.175, 3.36), (0.045, 0.014, 0.36), rnd=0.006), const(STRAP)))
        comps.append(Comp('lid_buckle', box((s * 0.32, 1.19, 3.14), (0.06, 0.018, 0.042), rnd=0.008), const(PLASTIC)))
        # shoulder straps entering the top of the bag
        comps.append(Comp('strap_top', obox((s * 0.62, 0.50, 4.035), (s * 0.55, 0.60, 3.86), 0.17, 0.035,
                                            (0, 1, 1), rnd=0.008), const(STRAP)))
    # bedroll strapped on top
    roll = capsule((-0.62, 0.84, 4.02), (0.62, 0.84, 4.02), 0.165)

    def roll_col(P, N):
        col = fabric(BEDROLL, 0.25, seed=75)(P, N)
        ends = np.clip((np.abs(P[:, 0]) - 0.70) / 0.05, 0, 1)
        r = np.sqrt((P[:, 2] - 4.02) ** 2 + (P[:, 1] - 0.84) ** 2)
        rings = 0.5 + 0.5 * np.sin(r * 120)
        return CL.mix(col, rgb(52, 64, 56), ends * rings * 0.8)
    comps.append(Comp('bedroll', roll, roll_col))
    for x in (-0.36, 0.36):
        comps.append(Comp('roll_strap', S.torus((x, 0.84, 4.02), 0.172, 0.02, R=np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float)),
                          const(STRAP)))
    # canteen in a side pouch (left) + compression straps (right)
    comps.append(Comp('canteen', S.ecyl((0.80, 0.84, 2.66), 0.125, 0.125, 0.22, rnd=0.06), fabric(CANTEEN, 0.25, seed=76)))
    comps.append(Comp('canteen_cap', S.ecyl((0.80, 0.84, 2.92), 0.05, 0.05, 0.04, rnd=0.012), const(METAL)))
    comps.append(Comp('pouch', box((0.775, 0.84, 2.56), (0.11, 0.15, 0.14), rnd=0.05), const(rgb(70, 64, 46))))
    for z in (2.62, 3.32):
        comps.append(Comp('compress', box((-0.705, 0.84, z), (0.012, 0.27, 0.025), rnd=0.006), const(STRAP)))
    return assemble(comps)


# ----------------------------------------------------------------------------------------------

def parts():
    P = [
        Part('Survivor_Head', StudMap('Head'), mesh=head_mesh, cat='skin', base=SKIN,
             info='Survivant : tête (peau, barbe de trois jours, saleté)'),
        Part('Survivor_Face', StudMap('Head'), mesh=face_mesh, cat='skin', base=rgb(34, 24, 20),
             info='Survivant : visage (yeux, sourcils, bouche, pansement, égratignure)'),
    ]
    def lazy(builder):
        cache = {}

        def get():
            if 'v' not in cache:
                cache['v'] = builder()
            return cache['v']
        return get
    ARM = {sd: lazy(lambda sd=sd: arm_parts(sd)) for sd in (1, -1)}
    LEG = {sd: lazy(lambda sd=sd: leg_parts(sd)) for sd in (1, -1)}

    for name, region, builder, target, h, cat, base, info in (
            ('Survivor_Hat', 'Head', hat_part, 15000, 0.0045, 'gear', BEANIE,
             'Survivant : bonnet en laine et cheveux'),
            ('Survivor_Torso', 'Torso', torso_part, 19000, 0.0065, 'skin', JACKET,
             'Survivant : veste de terrain ouverte, t-shirt, sangles, ceinture, plaques militaires'),
            ('Survivor_Backpack', 'Torso', backpack_part, 16000, 0.008, 'gear', PACK,
             'Survivant : sac à dos, sac de couchage, gourde'),
            ('Survivor_LeftUpperArm', 'LeftUpperArm', lambda: ARM[1]()[0], 7000, 0.0055, 'skin', JACKET,
             'Survivant : bras gauche (manche de veste, coudière, écusson)'),
            ('Survivor_LeftLowerArm', 'LeftLowerArm', lambda: ARM[1]()[1], 7000, 0.0055, 'skin', SKIN,
             'Survivant : avant-bras gauche (manche retroussée, montre, mitaine)'),
            ('Survivor_RightUpperArm', 'RightUpperArm', lambda: ARM[-1]()[0], 7000, 0.0055, 'skin', JACKET,
             'Survivant : bras droit (manche de veste, coudière)'),
            ('Survivor_RightLowerArm', 'RightLowerArm', lambda: ARM[-1]()[1], 7000, 0.0055, 'skin', SKIN,
             'Survivant : avant-bras droit (manche retroussée, bandage taché de sang, mitaine)'),
            ('Survivor_LeftUpperLeg', 'LeftUpperLeg', lambda: LEG[1]()[0], 8500, 0.0055, 'skin', DENIM,
             'Survivant : cuisse gauche (jean usé déchiré au genou, poche cargo)'),
            ('Survivor_LeftLowerLeg', 'LeftLowerLeg', lambda: LEG[1]()[1], 9000, 0.0055, 'skin', BOOT,
             'Survivant : jambe gauche (jean, botte lacée)'),
            ('Survivor_RightUpperLeg', 'RightUpperLeg', lambda: LEG[-1]()[0], 8500, 0.0055, 'skin', DENIM,
             'Survivant : cuisse droite (jean usé rapiécé au genou, poche cargo)'),
            ('Survivor_RightLowerLeg', 'RightLowerLeg', lambda: LEG[-1]()[1], 9000, 0.0055, 'skin', BOOT,
             'Survivant : jambe droite (jean, botte lacée)')):
        get = lazy(builder)
        P.append(Part(name, StudMap(region), sdf=lambda get=get: get()[0], color=lambda ctx, get=get: get()[1](ctx),
                      target=target, h=h, far=0.04, cat=cat, base=base, smooth=1, min_faces=12, info=info,
                      refine=0.55))
    return P
