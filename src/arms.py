"""Arms: humerus, radius, ulna, carpals, metacarpals, phalanges, cartilage, ligaments, vessels, nerves.
ArmMap coordinates (cm): u lateral (away from the body), v posterior, w below the humeral-head centre.
Anatomical position: palm forward (-v), thumb lateral (+u).  Same shapes for both arms (map mirrors X)."""
import numpy as np
import sdf as S
from sdf import (sphere, ellipsoid, round_cone, capsule, box, ecyl, smooth_union_all, smooth_union,
                 smooth_subtract, subtract, intersect, union, halfspace, frame, tube, torus, shell)
from maps import ArmMap
from parts import Part
from segments import segment
import colors as C
from sweep import tube_mesh

E = ellipsoid
SIDES = ((1, 'gauche'), (-1, 'droit'))


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# =================================================================== humerus
TROCHLEA = ((-0.85, -0.3, 32.0), 1.0)
CAPITULUM = ((1.3, -0.6, 32.0), 0.95)


def trochlea():
    # spool: two flanges and a central groove
    a, b = np.array((-1.95, -0.3, 32.0)), np.array((0.25, -0.3, 32.0))
    spool = capsule(a, b, 1.0)
    groove = torus((-0.85, -0.3, 32.0), 1.25, 0.32, np.stack([np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])]))
    return smooth_subtract(spool, groove, 0.2)


def humerus():
    F = [sphere((0, 0, 0), 2.3),
         E((2.0, -0.3, 0.6), (1.3, 1.35, 1.5)),                                  # greater tubercle
         E((0.5, -1.8, 1.3), (0.8, 0.7, 1.0)),                                   # lesser tubercle
         round_cone((0.9, 0.0, 2.2), (1.0, 0.0, 6.0), 1.75, 1.4),                # surgical neck
         tube([(1.0, 0.0, 5.5), (0.9, -0.1, 14), (0.75, -0.05, 22), (0.6, 0.0, 26.5)], [1.4, 1.25, 1.1, 1.15]),
         E((1.8, -0.3, 12.0), (0.5, 0.5, 2.0)),                                  # deltoid tuberosity
         E((0.3, -0.2, 29.0), (2.6, 1.3, 2.2)),                                  # distal flare
         E((-2.9, 0.2, 30.5), (0.75, 0.7, 0.8)),                                 # medial epicondyle
         E((2.6, 0.2, 30.2), (0.55, 0.6, 0.7)),                                  # lateral epicondyle
         capsule((-2.5, 0.2, 30.4), (-1.0, 0.0, 26.0), 0.45),                   # medial supracondylar ridge
         capsule((2.3, 0.2, 30.0), (1.2, 0.0, 24.0), 0.4),                      # lateral supracondylar ridge
         trochlea(), sphere(*CAPITULUM)]
    h = smooth_union_all(F, 0.55)
    h = smooth_subtract(h, capsule((1.15, -1.95, 0.4), (1.1, -1.75, 4.5), 0.35), 0.2)   # intertubercular groove
    h = smooth_subtract(h, E((0.0, 1.25, 30.3), (1.15, 0.6, 1.3)), 0.25)         # olecranon fossa
    h = smooth_subtract(h, E((-0.6, -1.35, 30.6), (0.6, 0.45, 0.7)), 0.2)         # coronoid fossa
    h = smooth_subtract(h, E((1.3, -1.45, 30.7), (0.5, 0.4, 0.6)), 0.2)           # radial fossa
    return h


# =================================================================== forearm
def ulna():
    F = [E((-0.9, 1.25, 31.2), (0.75, 0.65, 1.35)),                              # olecranon
         E((-0.9, -0.85, 33.4), (0.65, 0.55, 0.55)),                             # coronoid process
         E((-0.8, 0.25, 33.6), (0.9, 1.1, 1.6)),                                 # proximal body
         E((-0.6, -0.9, 34.6), (0.5, 0.35, 0.8)),                                # ulnar tuberosity
         tube([(-1.0, 0.2, 35.0), (-1.15, 0.25, 42), (-1.3, 0.28, 50), (-1.42, 0.3, 57.0)], [0.85, 0.7, 0.58, 0.5]),
         tube([(-0.55, 0.0, 37), (-0.85, 0.05, 50)], [0.25, 0.18]),              # interosseous crest
         E((-1.5, 0.3, 58.4), (0.72, 0.72, 0.65)),                               # head
         round_cone((-1.65, 0.75, 58.8), (-1.75, 0.85, 59.9), 0.32, 0.18)]       # styloid
    u = smooth_union_all(F, 0.4)
    u = subtract(u, trochlea().offset(0.18))                                     # trochlear notch
    return subtract(u, ecyl((1.3, -0.5, 33.5), 1.2, 1.2, 0.6))                   # radial notch


def radius_bone():
    head = intersect(ecyl((1.3, -0.5, 33.55), 1.05, 1.05, 0.45, rnd=0.15),
                     S.SDF(lambda p, l, h: -sphere(CAPITULUM[0], CAPITULUM[1] + 0.2).ev(p), np.full(3, -1e4), np.full(3, 1e4)))
    F = [head,
         round_cone((1.3, -0.5, 34.0), (1.25, -0.4, 36.0), 0.68, 0.62),           # neck
         E((0.8, -0.35, 36.6), (0.5, 0.5, 0.75)),                                # radial tuberosity
         tube([(1.25, -0.35, 36.0), (1.75, -0.25, 42), (1.85, -0.2, 47), (1.6, -0.2, 53), (1.35, -0.2, 56.5)],
              [0.62, 0.62, 0.66, 0.75, 1.0]),
         E((1.3, -0.2, 57.6), (1.35, 0.85, 0.9)),                                # broad distal end
         round_cone((2.2, -0.05, 58.0), (2.45, 0.0, 59.1), 0.45, 0.25),          # styloid
         E((1.4, 0.75, 57.0), (0.35, 0.25, 0.6)),                                # dorsal (Lister) tubercle
         tube([(1.0, -0.15, 38), (1.1, -0.1, 52)], [0.22, 0.18])]                # interosseous border
    r = smooth_union_all(F, 0.35)
    return subtract(r, E((0.15, 0.1, 57.6), (0.45, 0.55, 0.7)))                  # ulnar notch


# =================================================================== hand
CARPALS = [((1.9, -0.3, 60.6), (0.9, 0.6, 0.55), (0, 0, 25)),    # scaphoid
           ((0.4, 0.0, 60.4), (0.65, 0.75, 0.55), (0, 0, 0)),    # lunate
           ((-1.0, 0.1, 60.8), (0.6, 0.5, 0.5), (0, 0, -15)),    # triquetrum
           ((-1.2, -0.8, 61.0), (0.4, 0.38, 0.42), (0, 0, 0)),   # pisiform
           ((2.3, -0.6, 62.4), (0.7, 0.6, 0.55), (0, 0, 20)),    # trapezium
           ((1.25, -0.2, 62.6), (0.5, 0.6, 0.5), (0, 0, 0)),     # trapezoid
           ((0.1, -0.1, 62.7), (0.65, 0.8, 0.85), (0, 0, 0)),    # capitate
           ((-1.2, 0.0, 62.5), (0.65, 0.7, 0.7), (0, 0, 0))]     # hamate


def carpals():
    from sdf import rot_xyz
    bones = [E(c, np.array(r) * 1.13, rot_xyz(*rot) if any(rot) else None) for c, r, rot in CARPALS]
    bones[7] = smooth_union(bones[7], E((-1.1, -0.85, 62.6), (0.25, 0.35, 0.3)), 0.2)   # hook of hamate
    bones[0] = smooth_union(bones[0], sphere((2.3, -0.75, 61.0), 0.35), 0.2)           # scaphoid tubercle
    return union(*[b.offset(-0.06) for b in bones])


MC = [((2.6, -0.8, 63.0), (4.0, -2.2, 67.0), 0.62, 0.42, 0.55),
      ((1.4, -0.2, 63.6), (1.9, -0.4, 70.2), 0.55, 0.36, 0.52),
      ((0.2, -0.2, 63.8), (0.4, -0.4, 70.0), 0.56, 0.36, 0.52),
      ((-0.9, -0.1, 63.6), (-1.0, -0.4, 69.3), 0.5, 0.32, 0.48),
      ((-1.9, 0.0, 63.4), (-2.3, -0.4, 68.6), 0.5, 0.32, 0.46)]
FINGERS = [((3.0, 0.0, 2.2), 1.1), ((4.0, 2.4, 1.7), 1.0), ((4.5, 2.9, 1.9), 1.02), ((4.2, 2.7, 1.8), 0.95),
           ((3.4, 1.9, 1.6), 0.85)]


def metacarpals():
    out = []
    for (b, h, rb, rs, rh) in MC:
        b, h = np.array(b), np.array(h)
        d = nrm(h - b)
        out.append(smooth_union_all([E(b + d * 0.35, (rb, rb * 1.1, rb), frame(d, (1, 0, 0))),
                                     round_cone(b + d * 0.6, h - d * 0.45, rs * 1.1, rs * 0.9),
                                     E(h, (rh * 0.9, rh, rh), frame(d, (1, 0, 0)))], 0.3))
    return union(*out)


def finger_list():
    out = []
    for i, ((lp, lm, ld), sc) in enumerate(FINGERS):
        b, h = np.array(MC[i][0]), np.array(MC[i][1])
        d = nrm(h - b)
        if i > 0:
            d = nrm(d * 0.6 + np.array([0, 0, 1.0]) * 0.4 + np.array([(i - 2.5) * 0.03, 0, 0]))
        p = h + d * (MC[i][4] + 0.1)
        for j, L in enumerate((lp, lm, ld)):
            if L <= 0:
                continue
            q = p + d * L
            r0 = 0.4 * sc * (1 - 0.13 * j)
            distal = (j == 2) or (i == 0 and j == 2)
            out.append((p.copy(), q.copy(), r0, distal))
            p = q + d * 0.1
    return out


def phalanges():
    F = []
    for (a, b, r0, distal) in finger_list():
        d = nrm(b - a)
        parts = [E(a + d * 0.22, (r0 * 1.15, r0 * 0.95, r0 * 0.9), frame(d, (1, 0, 0))),
                 round_cone(a + d * 0.25, b - d * 0.2, r0 * 0.78, r0 * 0.58)]
        if distal:
            parts.append(E(b - d * 0.15, (r0 * 0.95, r0 * 0.45, r0 * 0.55), frame(d, (1, 0, 0))))   # tuft
        else:
            parts.append(E(b - d * 0.2, (r0 * 0.95, r0 * 0.7, r0 * 0.68), frame(d, (1, 0, 0))))      # condyles
        F.append(smooth_union_all(parts, 0.16))
    h1 = np.array(MC[0][1])
    for du in (-0.3, 0.35):
        F.append(E(h1 + np.array([du, -0.55, 0.2]), (0.22, 0.2, 0.26)))   # thumb sesamoids
    return union(*F)


# =================================================================== cartilage
def cart_shoulder():
    face = nrm((-0.8, 0.25, -0.55))       # medial, posterior, up
    return intersect(shell(sphere((0, 0, 0), 2.55), 0.28), halfspace(face * -0.5, -face))


def cart_elbow():
    """Articular cartilage of the humerus at the elbow (trochlea, capitulum): moves with the upper arm."""
    return intersect(shell(union(trochlea(), sphere(*CAPITULUM)).offset(0.2), 0.28), halfspace((0, 0, 31.0), (0, 0, -1)),
                     halfspace((0, 0.9, 0), (0, 1, 0)))


def cart_radial_head():
    """Cartilage of the radial head: moves with the forearm."""
    return intersect(shell(radius_bone().offset(0.18), 0.24), halfspace((0, 0, 33.3), (0, 0, 1)))


def cart_wrist():
    c = intersect(shell(radius_bone().offset(0.18), 0.24), halfspace((0, 0, 58.2), (0, 0, -1)))
    tfcc = E((-1.2, 0.35, 59.35), (0.75, 0.75, 0.18))
    return union(c, tfcc)


# =================================================================== tubes
def lig_tubes(m):
    band = lambda pts, r, w: tube_mesh(np.array(pts, float), m, r, rb_cm=w, ds=0.005, sides=10) + (C.ligament,)
    T = [band([(-2.9, 0.2, 30.8), (-1.9, -0.2, 32.6), (-1.0, -0.7, 33.9)], 0.22, 0.55),     # ulnar collateral (ant.)
         band([(-2.9, 0.4, 30.8), (-2.0, 0.9, 32.0), (-1.2, 1.3, 31.9)], 0.2, 0.45),        # ulnar collateral (post.)
         band([(2.65, 0.2, 30.6), (2.4, -0.1, 32.6), (2.3, -0.4, 33.6)], 0.2, 0.5),         # radial collateral
         band([(-2.3, 0.6, 60.2), (-1.6, -0.6, 61.2), (-0.2, -1.2, 61.6), (1.4, -1.1, 61.6), (2.5, -0.9, 61.6)],
              0.12, 0.7),                                                                     # flexor retinaculum
         band([(-1.6, 0.9, 58.5), (0.0, 1.0, 60.2), (1.6, 0.8, 60.6)], 0.12, 0.45)]         # dorsal radiocarpal
    ann = tube_mesh(np.array([(1.3 + 1.2 * np.cos(a), -0.5 + 1.2 * np.sin(a), 33.95) for a in np.linspace(0, 2 * np.pi, 13)]),
                    m, 0.14, rb_cm=0.4, ds=0.004, sides=8)
    T.append(ann + (C.ligament,))                                                            # annular ligament
    return T


def artery_tubes(m):
    A = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0065, sides=sides) + (C.artery,)
    T = [A([(-3.0, 0.8, 0.9), (-2.4, -0.4, 4), (-1.9, -0.7, 12), (-1.4, -1.0, 22), (-0.2, -1.55, 30.5), (0.3, -1.4, 34)],
           0.42, 0.34, 10)]                                                                  # axillary / brachial
    T.append(A([(0.3, -1.4, 34), (1.2, -1.2, 40), (1.9, -1.05, 50), (2.25, -1.1, 58.3), (2.6, -0.4, 61.3),
                (1.6, -0.5, 64.0), (0.0, -0.6, 64.6), (-1.4, -0.6, 64.4)], 0.24, 0.14))       # radial -> deep arch
    T.append(A([(0.3, -1.4, 34), (-0.8, -1.05, 39), (-1.3, -1.0, 48), (-1.5, -1.1, 58.6), (-1.4, -1.25, 62.5),
                (-0.3, -1.45, 66.4), (1.2, -1.4, 66.6), (2.3, -1.15, 65.2)], 0.25, 0.15))     # ulnar -> superficial arch
    for i in range(1, 5):                                                                     # common/proper digital arteries
        tip = np.array(MC[i][1]) + np.array([(0.5 if i < 3 else -0.5) * 0.4, -0.55, 8.5])
        start = np.array([np.interp(i, [1, 4], [1.0, -1.4]), -1.4, 66.5])
        T.append(A([start, np.array(MC[i][1]) + np.array([0, -0.6, 1.0]), tip], 0.11, 0.07, 6))
    T.append(A([(-1.4, -1.0, 22), (-2.3, 0.2, 26), (-2.7, 0.6, 30)], 0.13, 0.09, 6))          # sup. ulnar collateral
    T.append(A([(-1.6, -0.9, 8), (0.6, 1.4, 10), (2.0, 1.2, 16)], 0.15, 0.1, 6))              # profunda brachii
    return T


def vein_tubes(m):
    V = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0065, sides=sides) + (C.vein,)
    T = [V([(-3.1, 1.2, 0.9), (-2.7, -0.1, 4), (-2.2, -0.5, 12), (-1.8, -0.75, 22), (-0.5, -1.3, 30.5), (0.0, -1.2, 34)],
           0.46, 0.36, 10)]                                                                  # axillary / brachial vein
    T.append(V([(2.0, -1.4, 1.5), (2.5, -1.25, 10), (2.65, -1.3, 22), (2.4, -1.75, 30.5), (2.2, -1.6, 40),
                (2.3, -1.2, 52), (2.5, 0.2, 59), (1.5, 1.2, 64.0)], 0.27, 0.18))               # cephalic
    T.append(V([(-2.3, -0.4, 14), (-2.7, -1.0, 24), (-2.6, -1.6, 30.5), (-2.1, -1.5, 40), (-1.9, -0.5, 52),
                (-1.9, 0.8, 59), (-1.0, 1.2, 64.0)], 0.27, 0.18))                              # basilic
    T.append(V([(-2.6, -1.6, 30.5), (-0.2, -1.95, 31.4), (2.4, -1.75, 31.8)], 0.22, 0.2))     # median cubital
    T.append(V([(1.5, 1.2, 64.0), (0.2, 1.3, 64.6), (-1.0, 1.2, 64.0)], 0.18, 0.18))          # dorsal venous arch
    return T


def nerve_tubes(m):
    N = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0065, sides=sides) + (C.nerve,)
    T = [N([(-2.8, 0.2, 0.8), (-1.7, -0.95, 6), (-1.3, -1.2, 16), (-0.9, -1.4, 26), (-0.1, -1.5, 32), (0.15, -1.0, 38),
            (0.2, -0.9, 48), (0.3, -1.1, 58), (0.35, -1.2, 61.5), (0.4, -1.1, 64.0)], 0.32, 0.26, 10)]   # median
    for i in range(1, 4):
        T.append(N([(0.4, -1.1, 64.0), np.array(MC[i][1]) + np.array([0.35, -0.55, 0.8]),
                    np.array(MC[i][1]) + np.array([0.35, -0.5, 8.0])], 0.1, 0.06, 6))
    T.append(N([(0.4, -1.1, 64.0), (2.6, -1.5, 64.2), (3.6, -2.1, 67.2)], 0.12, 0.08, 6))      # thenar branch
    T.append(N([(-3.1, 0.6, 0.8), (-2.4, 0.2, 10), (-2.6, 0.6, 22), (-3.0, 0.95, 30.5), (-1.6, -0.5, 36),
                (-1.4, -0.75, 48), (-1.45, -0.95, 59.8), (-1.3, -1.2, 62.4), (-1.9, -1.0, 66.0),
                (-2.2, -0.6, 70.0)], 0.27, 0.16))                                              # ulnar
    T.append(N([(-2.5, 1.4, 0.8), (-0.4, 1.7, 8), (1.7, 1.6, 15), (2.4, 0.4, 22), (2.1, -0.9, 30), (1.9, -1.0, 38),
                (2.0, -0.95, 48), (2.4, -0.6, 57.5), (2.2, 0.3, 61.0)], 0.27, 0.13))           # radial / superficial
    T.append(N([(-2.4, -0.6, 1.5), (-0.6, -1.6, 8), (0.6, -1.8, 18), (1.6, -1.9, 30), (2.0, -1.4, 40)], 0.18, 0.1))   # musculocutaneous
    return T


# =================================================================== registry
def parts():
    P = []
    for s, side in SIDES:
        m = ArmMap(s)
        R = m.region
        b = lambda c, seed: C.bone(c, seed=seed)
        P += [
            Part(f'{R}_Humerus', m, sdf=humerus, color=lambda c: b(c, 31), target=12000, h=0.0018, far=0.7,
                 info=f'Humérus {side} (tête, tubercules, sillon intertuberculaire, épicondyles, trochlée, capitulum)'),
            Part(f'{R}_Ulna', m, sdf=ulna, color=lambda c: b(c, 32), target=7000, h=0.0012, far=0.5,
                 info=f'Ulna (cubitus) {side} (olécrane, processus coronoïde, tête, styloïde)'),
            Part(f'{R}_Radius', m, sdf=radius_bone, color=lambda c: b(c, 33), target=7000, h=0.0012, far=0.5,
                 info=f'Radius {side} (tête, tubérosité, styloïde, tubercule de Lister)'),
            Part(f'{R}_Carpals', m, sdf=carpals, color=lambda c: b(c, 34), target=8000, h=0.0008, far=0.3,
                 min_faces=20, info=f'Os du carpe {side} (8 : scaphoïde, lunatum, triquetrum, pisiforme, trapèze, trapézoïde, capitatum, hamatum)'),
            Part(f'{R}_Metacarpals', m, sdf=metacarpals, color=lambda c: b(c, 35), target=7000, h=0.0008, far=0.3,
                 info=f'Métacarpiens {side} (5)'),
            Part(f'{R}_Phalanges', m, sdf=phalanges, color=lambda c: b(c, 36), target=10000, h=0.0007, far=0.25,
                 min_faces=20, info=f'Phalanges des doigts {side} (14) et sésamoïdes du pouce'),
            Part(f'{R}_Cartilage_Shoulder', m, sdf=cart_shoulder, color=C.cartilage, target=2500, h=0.001, far=0.4,
                 cat='cartilage', base=(0.8, 0.86, 0.9), info=f'Cartilage de la tête humérale {side}'),
            Part(f'{R}_Cartilage_Elbow', m, sdf=cart_elbow, color=C.cartilage, target=3000, h=0.001, far=0.4,
                 cat='cartilage', base=(0.8, 0.86, 0.9), min_faces=30, info=f'Cartilage huméral du coude {side} (trochlée, capitulum)'),
            Part(f'{R}_Cartilage_RadialHead', m, sdf=cart_radial_head, color=C.cartilage, target=1500, h=0.001, far=0.4,
                 cat='cartilage', base=(0.8, 0.86, 0.9), min_faces=30, info=f'Cartilage de la tête radiale {side}'),
            Part(f'{R}_Cartilage_Wrist', m, sdf=cart_wrist, color=C.cartilage, target=2500, h=0.0009, far=0.3,
                 cat='cartilage', base=(0.8, 0.86, 0.9), min_faces=30, info=f'Cartilage du poignet et disque triangulaire {side}'),
            Part(f'{R}_Ligaments', m, tubes=lambda m=m: lig_tubes(m), target=6000, cat='ligament', base=(0.92, 0.9, 0.82),
                 info=f'Ligaments {side} (collatéraux du coude, annulaire, rétinaculum des fléchisseurs)'),
            Part(f'{R}_Arteries', m, tubes=lambda m=m: artery_tubes(m), target=14000, cat='vessel', base=(0.72, 0.1, 0.09),
                 info=f'Artères du bras {side} (axillaire, brachiale, radiale, ulnaire, arcades palmaires, digitales)'),
            Part(f'{R}_Veins', m, tubes=lambda m=m: vein_tubes(m), target=12000, cat='vessel', base=(0.2, 0.25, 0.55),
                 info=f'Veines du bras {side} (brachiale, céphalique, basilique, médiane du coude, arcade dorsale)'),
            Part(f'{R}_Nerves', m, tubes=lambda m=m: nerve_tubes(m), target=12000, cat='nerve', base=(0.96, 0.88, 0.55),
                 info=f'Nerfs du bras {side} (médian, ulnaire, radial, musculo-cutané)'),
        ]
    return segment(P, ARM_PLAN, ('bras', 'avant-bras'))


ARM_PLAN = {'Humerus': 'upper', 'Ulna': 'lower', 'Radius': 'lower', 'Carpals': 'lower', 'Metacarpals': 'lower',
            'Phalanges': 'lower', 'Cartilage_Shoulder': 'upper', 'Cartilage_Elbow': 'upper',
            'Cartilage_RadialHead': 'lower', 'Cartilage_Wrist': 'lower', 'Ligaments': 'split', 'Arteries': 'split',
            'Veins': 'split', 'Nerves': 'split'}
