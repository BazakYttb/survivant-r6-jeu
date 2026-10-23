"""Legs: femur, patella, tibia, fibula, tarsals, metatarsals, phalanges, cartilage, menisci, ligaments,
tendons, vessels and nerves.  LegMap coordinates (cm): u lateral, v posterior, w below the femoral-head
centre (floor at w = 91).  The same shapes serve both legs (the map mirrors X)."""
import numpy as np
import sdf as S
from sdf import (sphere, ellipsoid, round_cone, capsule, box, ecyl, smooth_union_all, smooth_union,
                 smooth_subtract, subtract, intersect, union, halfspace, rot_xyz, frame, tube, torus, capped_torus, shell)
from maps import LegMap
from parts import Part
from segments import segment
import colors as C
from sweep import tube_mesh

E = ellipsoid
SIDES = ((1, 'Left', 'gauche'), (-1, 'Right', 'droite'))


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# =================================================================== femur
COND_M = ((-1.8, 0.8, 42.0), (1.6, 2.6, 2.0))
COND_L = ((2.5, 0.8, 41.8), (1.6, 2.6, 2.0))
FOVEA_DIR = nrm((-0.9, 0.12, 0.4))


def femur():
    F = [sphere((0, 0, 0), 2.4),
         round_cone((0.8, -0.2, 0.6), (4.0, 0.2, 2.6), 1.6, 1.5),
         E((5.2, 0.6, 2.0), (1.6, 1.8, 2.2)),                                   # greater trochanter
         E((1.8, 1.3, 6.5), (0.9, 0.85, 1.05)),                                 # lesser trochanter
         capsule((5.0, 1.4, 1.5), (2.3, 1.5, 6.3), 0.55),                       # intertrochanteric crest
         capsule((5.0, -1.0, 1.8), (2.6, -1.2, 6.0), 0.32),                     # intertrochanteric line
         tube([(3.6, 0.0, 6.5), (2.9, -0.55, 15), (2.3, -0.65, 24), (1.7, -0.45, 32), (1.2, -0.2, 36)],
              [1.5, 1.38, 1.35, 1.42, 1.6]),
         tube([(2.8, 1.0, 12), (2.3, 1.2, 22), (1.8, 1.0, 31)], [0.35, 0.42, 0.35]),   # linea aspera
         E((3.6, 1.0, 9.0), (0.45, 0.45, 1.5)),                                 # gluteal tuberosity
         E((0.6, 0.15, 38.5), (3.0, 2.2, 3.2)),                                 # distal metaphysis
         E(*COND_M), E(*COND_L),
         E((-3.2, 0.4, 40.6), (0.6, 0.8, 0.8)), E((3.5, 0.6, 40.8), (0.5, 0.7, 0.7)),   # epicondyles
         sphere((-3.0, 0.6, 38.8), 0.45)]                                       # adductor tubercle
    fe = smooth_union_all(F, 0.6)
    fe = smooth_subtract(fe, E((0.35, 2.3, 42.7), (1.0, 2.0, 1.6)), 0.3)        # intercondylar notch
    fe = smooth_subtract(fe, capsule((0.35, -2.3, 37.8), (0.35, -1.9, 41.2), 0.62), 0.4)   # patellar groove
    fe = smooth_subtract(fe, E((4.2, 1.5, 1.6), (0.6, 0.55, 0.75)), 0.2)        # trochanteric fossa
    return subtract(fe, sphere(FOVEA_DIR * 2.4, 0.38))                          # fovea capitis


def patella():
    p = smooth_union(E((0.6, -3.35, 39.4), (2.2, 0.95, 2.3)), E((0.6, -3.25, 41.3), (1.15, 0.75, 0.95)), 0.6)
    p = smooth_subtract(p, E((0.6, -1.55, 39.4), (2.6, 0.75, 2.7)), 0.3)        # posterior articular surface
    return subtract(p, capsule((0.6, -2.2, 37.6), (0.6, -2.2, 41.0), 0.25))      # median ridge groove


# =================================================================== tibia / fibula
TALUS_BODY = ((0.5, 0.6, 84.2), (1.7, 1.8, 1.2))
TALUS_DOME = ((0.5, 0.4, 83.4), (1.5, 1.8, 0.7))


def tibia():
    F = [E((-1.8, 0.4, 45.2), (2.0, 2.4, 1.4)), E((2.2, 0.4, 45.2), (1.9, 2.3, 1.4)),
         E((0.3, 0.3, 46.9), (3.2, 2.4, 1.8)),
         E((0.5, -2.0, 48.5), (0.9, 0.6, 1.3)),                                  # tuberosity
         tube([(0.6, 0.1, 47.5), (0.6, 0.1, 55), (0.6, 0.05, 65), (0.55, 0.0, 75), (0.4, 0.0, 79)],
              [2.0, 1.5, 1.25, 1.15, 1.5]),
         tube([(0.5, -1.6, 49.5), (0.6, -1.35, 60), (0.5, -1.2, 72)], [0.42, 0.36, 0.3]),   # anterior crest
         tube([(1.8, 0.2, 50), (1.7, 0.3, 72)], [0.3, 0.25]),                    # interosseous border
         E((0.3, 0.0, 80.0), (1.8, 1.6, 1.6)),
         E((-1.6, 0.2, 82.4), (0.6, 0.9, 1.1))]                                  # medial malleolus
    tb = smooth_union_all(F, 0.6)
    tb = subtract(tb, E(COND_M[0], np.array(COND_M[1]) + 0.18), E(COND_L[0], np.array(COND_L[1]) + 0.18))
    tb = union(tb, round_cone((0.0, 0.3, 44.5), (0.0, 0.3, 43.6), 0.42, 0.12),
               round_cone((0.65, 0.45, 44.5), (0.65, 0.45, 43.7), 0.38, 0.12))  # intercondylar eminence
    tb = subtract(tb, E(TALUS_DOME[0], np.array(TALUS_DOME[1]) + 0.15), E((2.15, 0.6, 80.0), (0.55, 0.8, 1.6)))
    return tb


def fibula():
    F = [E((4.0, 1.2, 47.5), (1.1, 1.0, 1.1)), sphere((4.3, 1.5, 46.6), 0.4),
         tube([(3.9, 1.15, 48.8), (3.8, 1.0, 58), (3.7, 0.9, 70), (3.6, 0.85, 79)], [0.62, 0.55, 0.55, 0.66]),
         E((3.6, 0.8, 83.3), (0.65, 0.9, 1.25))]
    return smooth_union_all(F, 0.4)


# =================================================================== foot
def talus():
    return smooth_union_all([E(*TALUS_BODY), E(*TALUS_DOME),
                             round_cone((0.3, -1.0, 84.6), (-0.3, -2.6, 84.9), 1.0, 1.15),
                             sphere((0.6, 2.3, 84.6), 0.45)], 0.35)


def calcaneus():
    c = smooth_union_all([round_cone((0.5, 4.6, 88.1), (1.4, -1.8, 87.3), 1.9, 1.35),
                          E((0.5, 5.2, 88.6), (1.5, 1.2, 1.6)),
                          E((-1.0, 0.6, 85.9), (0.9, 1.0, 0.5)),                  # sustentaculum tali
                          E((2.5, 1.0, 87.6), (0.4, 0.6, 0.4))], 0.45)            # peroneal trochlea
    return subtract(c, talus().offset(0.12))


TARSALS = None


def tarsals():
    bones = [talus(), calcaneus(),
             smooth_union(E((-0.8, -3.9, 85.6), (1.35, 0.75, 1.15)), sphere((-2.0, -3.6, 86.2), 0.5), 0.3),   # navicular
             E((2.0, -3.4, 87.6), (1.15, 1.45, 1.0)),                               # cuboid
             E((-1.2, -5.6, 86.6), (0.7, 1.1, 1.15)),                               # medial cuneiform
             E((0.0, -5.4, 86.3), (0.55, 0.9, 0.9)),                                # intermediate cuneiform
             E((1.1, -5.3, 86.7), (0.6, 1.0, 0.95))]                                # lateral cuneiform
    return union(*[b.offset(-0.07) for b in bones])


MT = [((-1.2, -6.8, 87.0), (-1.5, -12.8, 89.6), 0.95, 0.55, 0.82),
      ((0.1, -6.9, 87.0), (-0.1, -14.0, 90.0), 0.62, 0.34, 0.52),
      ((1.0, -6.7, 87.4), (1.0, -13.5, 90.1), 0.6, 0.33, 0.5),
      ((1.9, -6.3, 88.0), (2.0, -12.8, 90.2), 0.58, 0.32, 0.48),
      ((2.9, -5.3, 88.7), (3.2, -11.8, 90.3), 0.6, 0.32, 0.48)]


def metatarsals():
    out = []
    for (b, h, rb, rs, rh) in MT:
        b, h = np.array(b), np.array(h)
        d = nrm(h - b)
        bone = smooth_union_all([E(b + d * 0.3, (rb, rb * 1.1, rb * 1.05), frame(d, (0, 0, 1))),
                                 round_cone(b + d * 0.6, h - d * 0.5, rs * 1.15, rs),
                                 E(h, (rh * 0.85, rh, rh), frame(d, (1, 0, 0)))], 0.35)
        out.append(bone)
    out.append(E((3.6, -5.0, 89.2), (0.55, 0.55, 0.45)))   # MT5 tuberosity
    return smooth_union(union(*out[:-1]), out[-1], 0.3)


TOES = [  # lengths prox, mid, dist ; radius scale
    ((2.7, 0.0, 2.1), 1.45), ((2.6, 1.1, 0.9), 1.0), ((2.3, 1.0, 0.8), 0.95), ((2.1, 0.9, 0.8), 0.9),
    ((1.8, 0.7, 0.7), 0.88)]


def phalanx_list():
    out = []
    for i, ((lp, lm, ld), sc) in enumerate(TOES):
        b, h = np.array(MT[i][0]), np.array(MT[i][1])
        d = nrm(h - b)
        p = h + d * (MT[i][4] + 0.12)
        for j, L in enumerate((lp, lm, ld)):
            if L <= 0:
                continue
            dj = nrm(d + np.array([0, 0, 0.18 * (j + 1)]))
            q = p + dj * L
            r0 = 0.42 * sc * (1 - 0.12 * j)
            out.append((p.copy(), q.copy(), r0, j == 2 or (i == 0 and j == 1)))
            p = q + dj * 0.12
    return out


def phalanges():
    F = []
    for (a, b, r0, distal) in phalanx_list():
        d = nrm(b - a)
        bone = [E(a + d * 0.22, (r0 * 1.1, r0 * 1.15, r0 * 0.95), frame(d, (1, 0, 0))),
                round_cone(a + d * 0.25, b - d * 0.2, r0 * 0.8, r0 * 0.6)]
        if distal:
            bone.append(E(b - d * 0.18, (r0 * 0.95, r0 * 0.5, r0 * 0.6), frame(d, (1, 0, 0))))   # tuft
        else:
            bone.append(E(b - d * 0.18, (r0 * 0.85, r0 * 0.75, r0 * 0.7), frame(d, (1, 0, 0))))
        F.append(smooth_union_all(bone, 0.18))
    h1 = np.array(MT[0][1])
    for du in (-0.45, 0.4):                                     # hallux sesamoids
        F.append(E(h1 + np.array([du, 0.25, 0.75]), (0.32, 0.4, 0.28)))
    return union(*F)


# =================================================================== cartilage & menisci
def cart_hip():
    up = nrm((-0.75, -0.15, -0.55))
    return subtract(intersect(shell(sphere((0, 0, 0), 2.62), 0.26), halfspace(up * -0.6, -up)),
                    sphere(FOVEA_DIR * 2.4, 0.45))


def cart_knee():
    fe = femur()
    fem = intersect(shell(fe.offset(0.22), 0.3), halfspace((0, 0, 40.2), (0, 0, -1)))
    groove = intersect(shell(fe.offset(0.2), 0.28), halfspace((0, -1.2, 0), (0, 1, 0)),
                       halfspace((0, 0, 41.0), (0, 0, 1)), halfspace((0, 0, 37.2), (0, 0, -1)),
                       ecyl((0.4, -2.0, 39.0), 2.1, 1.6, 3.0))
    tb = tibia()
    plateau = intersect(shell(tb.offset(0.2), 0.27), halfspace((0, 0, 44.75), (0, 0, 1)),
                        halfspace((0, -1.9, 0), (0, -1, 0)))
    pat = intersect(shell(patella().offset(0.2), 0.26), halfspace((0, -2.75, 0), (0, -1, 0)))
    return union(fem, groove, plateau, pat)


def cart_knee_femur():
    """Cartilage of the femoral condyles, trochlear groove and patella: moves with the thigh."""
    fe = femur()
    fem = intersect(shell(fe.offset(0.22), 0.3), halfspace((0, 0, 40.2), (0, 0, -1)))
    groove = intersect(shell(fe.offset(0.2), 0.28), halfspace((0, -1.2, 0), (0, 1, 0)),
                       halfspace((0, 0, 41.0), (0, 0, 1)), halfspace((0, 0, 37.2), (0, 0, -1)),
                       ecyl((0.4, -2.0, 39.0), 2.1, 1.6, 3.0))
    pat = intersect(shell(patella().offset(0.2), 0.26), halfspace((0, -2.75, 0), (0, -1, 0)))
    return union(fem, groove, pat)


def cart_tibial_plateau():
    """Cartilage of the tibial plateau: moves with the shin."""
    return intersect(shell(tibia().offset(0.2), 0.27), halfspace((0, 0, 44.75), (0, 0, 1)),
                     halfspace((0, -1.9, 0), (0, -1, 0)))


def cart_ankle():
    return intersect(shell(talus().offset(0.16), 0.24), halfspace((0, 0, 83.95), (0, 0, 1)),
                     halfspace((0, 2.1, 0), (0, 1, 0)))


def menisci():
    Rm = np.stack([np.array([0, 1.0, 0]), np.array([-1.0, 0, 0]), np.array([0, 0, 1.0])])
    Rl = np.stack([np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0])])
    med = capped_torus((-1.8, 0.4, 44.15), 1.45, 0.42, 150, Rm)
    lat = capped_torus((2.2, 0.4, 44.15), 1.25, 0.4, 165, Rl)
    m = union(med, lat)
    m = subtract(m, union(E(COND_M[0], np.array(COND_M[1]) + 0.24), E(COND_L[0], np.array(COND_L[1]) + 0.24)))
    return intersect(m, halfspace((0, 0, 44.5), (0, 0, 1)))


# =================================================================== tubes (ligaments, tendons, vessels, nerves)
def lig_tubes(m):
    T = []
    band = lambda pts, r, w, cf=C.ligament, sides=10: tube_mesh(np.array(pts, float), m, r, rb_cm=w, ds=0.005, sides=sides) + (cf,)
    T.append(band([(1.0, 1.5, 42.0), (0.6, 0.6, 43.2), (0.0, -0.6, 44.3)], 0.32, 0.42))     # ACL
    T.append(band([(-0.5, 0.2, 41.5), (-0.1, 1.0, 43.4), (0.3, 1.8, 45.1)], 0.36, 0.45))     # PCL
    T.append(band([(-3.3, 0.3, 40.4), (-3.4, 0.2, 44.0), (-2.6, 0.0, 50.0)], 0.18, 0.75))    # MCL
    T.append(band([(3.65, 0.6, 40.8), (4.2, 0.85, 44.0), (4.4, 1.0, 46.8)], 0.27, 0.3))      # LCL
    T.append(band([(-1.7, 0.4, 82.0), (-1.8, 0.0, 84.0), (-1.4, -2.0, 85.4)], 0.18, 0.55))   # deltoid (ant.)
    T.append(band([(-1.7, 0.4, 82.5), (-1.6, 0.9, 85.0), (-1.0, 0.8, 86.3)], 0.18, 0.55))    # deltoid (tibiocalc.)
    T.append(band([(3.4, -0.2, 83.0), (2.4, -1.2, 84.0), (1.6, -1.8, 84.5)], 0.18, 0.45))    # ATFL
    T.append(band([(3.6, 0.9, 84.2), (3.2, 1.3, 85.8), (2.6, 1.5, 87.0)], 0.2, 0.35))        # CFL
    T.append(band([(3.7, 1.7, 83.4), (2.4, 2.4, 84.3), (1.0, 2.5, 84.6)], 0.18, 0.4))        # PTFL
    # interosseous membrane: thin wide sheet between tibia and fibula
    T.append(tube_mesh(np.array([(2.6, 0.55, 50.0), (2.6, 0.5, 62.0), (2.55, 0.45, 76.0)]), m, 0.06,
                       rb_cm=lambda t: 0.75 - 0.15 * t, ds=0.01, sides=8, normal_fn=lambda ps: np.tile([0, 1.0, 0], (len(ps), 1)))
             + (C.ligament,))
    # plantar fascia: from calcaneus to the five metatarsal heads
    root = np.array((0.4, 4.0, 90.45))
    for i in range(5):
        h = np.array(MT[i][1]) + np.array([0, 0.4, 0.75])
        mid = root * 0.55 + h * 0.45 + np.array([0, 0, 0.15])
        T.append(tube_mesh(np.array([root, mid, h]), m, 0.12, rb_cm=lambda t: 0.6 - 0.3 * t, ds=0.008, sides=8,
                           normal_fn=lambda ps: np.tile([0, 0, 1.0], (len(ps), 1))) + (C.ligament,))
    return T


def tendon_tubes(m):
    T = []
    up = lambda ps: np.tile([0, 1.0, 0], (len(ps), 1))
    T.append(tube_mesh(np.array([(0.6, -3.25, 41.9), (0.55, -2.9, 45.0), (0.5, -2.35, 48.2)]), m, 0.3,
                       rb_cm=lambda t: 1.25 - 0.35 * t, ds=0.006, sides=10, normal_fn=up) + (C.ligament,))   # patellar lig.
    T.append(tube_mesh(np.array([(0.5, -2.85, 34.6), (0.55, -3.1, 36.0), (0.6, -3.4, 37.4)]), m, 0.3,
                       rb_cm=lambda t: 1.5 + 0.3 * t, ds=0.006, sides=10, normal_fn=up) + (C.ligament,))    # quadriceps stub
    T.append(tube_mesh(np.array([(0.5, 4.8, 62.0), (0.5, 4.7, 72.0), (0.5, 5.2, 82.0), (0.5, 6.1, 87.6)]), m, 0.4,
                       rb_cm=lambda t: 1.6 - 0.75 * t ** 0.7, ds=0.008, sides=10,
                       normal_fn=lambda ps: np.tile([0, 1.0, 0], (len(ps), 1))) + (C.ligament,))             # Achilles
    return T


def artery_tubes(m):
    A = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0075, sides=sides) + (C.artery,)
    fem = [(-0.6, -5.5, 1.7), (-1.0, -4.6, 8), (-1.6, -3.0, 18), (-2.2, -1.5, 26), (-1.4, 1.2, 33), (-0.2, 3.0, 38),
           (0.3, 3.2, 42), (0.5, 2.9, 48), (0.7, 2.6, 50.5)]
    T = [A(fem, 0.48, 0.38, 10)]
    T.append(A([(0.7, 2.6, 50.5), (2.2, 0.8, 51.5), (2.2, -0.9, 55), (1.9, -1.2, 66), (1.2, -1.6, 80),
                (0.6, -3.0, 84.2), (0.2, -4.8, 85.6), (-0.4, -8.0, 87.6)], 0.25, 0.15))          # ant. tibial / dorsalis pedis
    T.append(A([(0.7, 2.6, 50.5), (-0.2, 2.4, 58), (-0.8, 2.1, 70), (-2.0, 1.7, 82.5), (-2.0, 0.4, 86.5),
                (-1.2, -2.5, 89.6), (-0.6, -7.5, 90.0)], 0.26, 0.15))                            # post. tibial / plantar
    T.append(A([(0.2, 2.5, 53), (2.6, 2.0, 58), (3.1, 1.5, 70), (3.2, 1.3, 79)], 0.18, 0.12))  # fibular
    T.append(A([(-1.0, -4.6, 8), (1.0, -2.8, 9), (3.0, -2.2, 12)], 0.22, 0.15))              # lateral circumflex
    T.append(A([(-1.2, -4.2, 6), (-0.2, 0.5, 6.5), (2.0, 2.0, 7)], 0.2, 0.14))               # deep femoral branch
    return T


def vein_tubes(m):
    V = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0075, sides=sides) + (C.vein,)
    fem = [(-1.5, -5.3, 1.7), (-1.6, -4.4, 8), (-2.1, -2.8, 18), (-2.7, -1.2, 26), (-1.8, 1.6, 33), (-0.6, 3.5, 38),
           (-0.1, 3.6, 42), (0.1, 3.3, 48), (0.3, 3.0, 50.5)]
    T = [V(fem, 0.55, 0.45, 10)]
    T.append(V([(-1.8, -5.0, 2.5), (-2.6, -3.2, 12), (-3.3, -1.6, 24), (-3.9, 0.7, 36), (-3.9, 0.9, 42),
                (-3.3, -0.1, 52), (-3.0, -0.7, 66), (-2.5, -1.3, 79), (-2.2, -1.9, 83), (-1.2, -4.5, 86.0),
                (0.6, -7.2, 86.6), (2.6, -6.4, 87.4)], 0.3, 0.2))                               # great saphenous
    T.append(V([(0.3, 3.7, 42.5), (0.4, 4.6, 52), (0.8, 4.4, 66), (2.4, 2.9, 79), (3.8, 2.1, 83.4), (3.4, -1.5, 87.5)],
               0.22, 0.15))                                                                   # small saphenous
    T.append(V([(0.3, 3.0, 50.5), (2.0, 1.0, 52), (2.0, -1.2, 56), (1.6, -1.5, 70), (1.0, -1.8, 80)], 0.2, 0.14))
    T.append(V([(0.3, 3.0, 50.5), (-0.5, 2.7, 60), (-1.1, 2.3, 72), (-2.3, 1.9, 82.7)], 0.21, 0.14))
    return T


def nerve_tubes(m):
    N = lambda pts, r, r1=None, sides=8: tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=0.0075, sides=sides) + (C.nerve,)
    sci = [(1.4, 6.2, 0.0), (1.6, 4.6, 4), (1.3, 3.8, 14), (1.0, 3.7, 26), (0.8, 3.7, 36), (0.6, 3.6, 39)]
    T = [N(sci, 0.6, 0.52, 10)]
    T.append(N([(0.6, 3.6, 39), (0.3, 3.5, 47), (-0.3, 2.6, 58), (-0.9, 2.3, 70), (-2.15, 1.95, 83),
                (-1.7, 0.6, 86.8), (-1.0, -2.2, 89.8), (-0.2, -7.0, 90.2)], 0.38, 0.2))          # tibial / plantar
    T.append(N([(0.6, 3.6, 39), (2.4, 3.0, 43), (4.0, 2.0, 47), (4.5, 0.4, 49.5), (3.6, -0.6, 51)], 0.3, 0.26))   # common fibular
    T.append(N([(3.6, -0.6, 51), (2.3, -0.9, 56), (1.9, -1.1, 66), (1.1, -1.8, 81), (0.3, -4.6, 85.5),
                (-0.6, -9.0, 88.0)], 0.2, 0.12))                                                 # deep fibular
    T.append(N([(3.6, -0.6, 51), (4.2, -0.3, 60), (3.8, -0.9, 72), (3.0, -1.7, 80), (2.2, -5.0, 86.5),
                (2.0, -9.0, 88.0)], 0.18, 0.11))                                                 # superficial fibular
    T.append(N([(0.3, -5.7, 1.0), (0.9, -5.0, 5.0), (1.6, -4.2, 9.0)], 0.32, 0.22))           # femoral nerve
    T.append(N([(0.3, -5.7, 1.0), (-0.5, -4.6, 7.0), (-1.2, -3.3, 14.0)], 0.22, 0.16))
    T.append(N([(-0.4, -5.2, 2.0), (-2.0, -2.6, 20), (-3.6, 0.2, 38), (-3.6, 0.6, 46), (-3.1, -0.4, 60),
                (-2.4, -1.4, 80), (-2.1, -2.2, 84)], 0.14, 0.1))                                 # saphenous nerve
    return T


# =================================================================== registry
def parts():
    P = []
    for s, tag, side in SIDES:
        m = LegMap(s)
        R = m.region
        b = lambda c, seed: C.bone(c, seed=seed)
        P += [
            Part(f'{R}_Femur', m, sdf=femur, color=lambda c: b(c, 21), target=13000, h=0.0024, far=0.8,
                 info=f'Fémur {side} (tête, col, trochanters, ligne âpre, condyles)'),
            Part(f'{R}_Patella', m, sdf=patella, color=lambda c: b(c, 22), target=3000, h=0.0011, far=0.5,
                 info=f'Rotule {side}'),
            Part(f'{R}_Tibia', m, sdf=tibia, color=lambda c: b(c, 23), target=12000, h=0.0022, far=0.8,
                 info=f'Tibia {side} (plateau, tubérosité, crête, malléole médiale)'),
            Part(f'{R}_Fibula', m, sdf=fibula, color=lambda c: b(c, 24), target=5000, h=0.0013, far=0.5,
                 info=f'Fibula (péroné) {side}'),
            Part(f'{R}_Tarsals', m, sdf=tarsals, color=lambda c: b(c, 25), target=11000, h=0.0012, far=0.5,
                 info=f'Os du tarse {side} (talus, calcanéus, naviculaire, cuboïde, 3 cunéiformes)'),
            Part(f'{R}_Metatarsals', m, sdf=metatarsals, color=lambda c: b(c, 26), target=7000, h=0.001, far=0.4,
                 info=f'Métatarsiens {side} (5)'),
            Part(f'{R}_Phalanges', m, sdf=phalanges, color=lambda c: b(c, 27), target=8000, h=0.0008, far=0.3,
                 min_faces=20, info=f'Phalanges des orteils {side} (14) et sésamoïdes'),
            Part(f'{R}_Cartilage_Hip', m, sdf=cart_hip, color=C.cartilage, target=2500, h=0.0011, far=0.4, cat='cartilage',
                 base=(0.8, 0.86, 0.9), info=f'Cartilage de la tête fémorale {side}'),
            Part(f'{R}_Cartilage_Knee', m, sdf=cart_knee_femur, color=C.cartilage, target=4500, h=0.0012, far=0.4,
                 cat='cartilage', base=(0.8, 0.86, 0.9), min_faces=30,
                 info=f'Cartilages du genou {side} (condyles fémoraux, trochlée, rotule)'),
            Part(f'{R}_Cartilage_TibialPlateau', m, sdf=cart_tibial_plateau, color=C.cartilage, target=2000, h=0.0012,
                 far=0.4, cat='cartilage', base=(0.8, 0.86, 0.9), min_faces=30, info=f'Cartilage du plateau tibial {side}'),
            Part(f'{R}_Cartilage_Ankle', m, sdf=cart_ankle, color=C.cartilage, target=2000, h=0.0011, far=0.4, cat='cartilage',
                 base=(0.8, 0.86, 0.9), info=f'Cartilage du dôme du talus {side}'),
            Part(f'{R}_Menisci', m, sdf=menisci, color=lambda c: C.cartilage(c, seed=5), target=3000, h=0.001, far=0.4,
                 cat='cartilage', base=(0.85, 0.87, 0.86), info=f'Ménisques médial et latéral {side}'),
            Part(f'{R}_Ligaments', m, tubes=lambda m=m: lig_tubes(m), target=9000, cat='ligament', base=(0.92, 0.9, 0.82),
                 info=f'Ligaments {side} (croisés, collatéraux, cheville, fascia plantaire, membrane interosseuse)'),
            Part(f'{R}_Tendons', m, tubes=lambda m=m: tendon_tubes(m), target=5000, cat='ligament', base=(0.92, 0.9, 0.82),
                 info=f'Tendons {side} (rotulien, quadricipital, calcanéen d\'Achille)'),
            Part(f'{R}_Arteries', m, tubes=lambda m=m: artery_tubes(m), target=14000, cat='vessel', base=(0.72, 0.1, 0.09),
                 info=f'Artères de la jambe {side} (fémorale, poplitée, tibiales, fibulaire, pédieuse)'),
            Part(f'{R}_Veins', m, tubes=lambda m=m: vein_tubes(m), target=14000, cat='vessel', base=(0.2, 0.25, 0.55),
                 info=f'Veines de la jambe {side} (fémorale, grande et petite saphènes, tibiales)'),
            Part(f'{R}_Nerves', m, tubes=lambda m=m: nerve_tubes(m), target=12000, cat='nerve', base=(0.96, 0.88, 0.55),
                 info=f'Nerfs de la jambe {side} (sciatique, tibial, fibulaires, fémoral, saphène)'),
        ]
    return segment(P, LEG_PLAN, ('cuisse', 'jambe'))


LEG_PLAN = {'Femur': 'upper', 'Patella': 'upper', 'Tibia': 'lower', 'Fibula': 'lower', 'Tarsals': 'lower',
            'Metatarsals': 'lower', 'Phalanges': 'lower', 'Cartilage_Hip': 'upper', 'Cartilage_Knee': 'upper',
            'Cartilage_TibialPlateau': 'lower', 'Cartilage_Ankle': 'lower', 'Menisci': 'lower', 'Ligaments': 'split',
            'Tendons': 'split', 'Arteries': 'split', 'Veins': 'split', 'Nerves': 'split'}
