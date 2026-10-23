"""Shared anatomical landmarks (READ-ONLY for region modules: import, don't edit).

Torso coordinates are real cm for a 175 cm adult in anatomical position:
x = lateral (+ = character's LEFT), y = posterior (+ = back, - = front), z = height above floor.
Map to studs with maps.TorsoMap (or TorsoMap(girdle=True) for shoulder girdle / anything that
must reach the arms: it pushes |x| > 8 cm outwards so the glenoid meets the humerus)."""
import numpy as np

# ---------------------------------------------------------------- spine (vertebral body centres)
SPINE = {
    # name: (y, z)  body centre
    'C3': (1.8, 157.9), 'C4': (1.6, 155.8), 'C5': (1.4, 153.7), 'C6': (1.3, 151.6), 'C7': (1.3, 149.5),
    'T1': (1.5, 146.0), 'T2': (1.9, 143.1), 'T3': (2.3, 140.2), 'T4': (2.6, 137.3), 'T5': (2.8, 134.4),
    'T6': (3.0, 131.5), 'T7': (3.1, 128.6), 'T8': (3.1, 125.7), 'T9': (2.9, 122.8), 'T10': (2.5, 119.9),
    'T11': (2.0, 117.0), 'T12': (1.4, 114.1),
    'L1': (0.6, 110.6), 'L2': (-0.2, 107.4), 'L3': (-0.8, 104.2), 'L4': (-1.0, 101.0), 'L5': (-0.5, 97.8),
}
# disc thickness (cm) between consecutive bodies (upper name -> disc below it)
def disc_thickness(name):
    return {'C': 0.55, 'T': 0.6, 'L': 1.0}[name[0]] + (0.25 if name in ('T10', 'T11', 'T12') else 0.0)


SPINE_ORDER = ['C3', 'C4', 'C5', 'C6', 'C7'] + [f'T{i}' for i in range(1, 13)] + [f'L{i}' for i in range(1, 6)]

# typical dimensions (cm): body width, body depth, body height, canal rx, canal ry
def vertebra_dims(name):
    r, i = name[0], int(name[1:])
    if r == 'C':
        t = (i - 3) / 4
        return dict(bw=1.8 + 0.5 * t, bd=1.5 + 0.2 * t, bh=1.35 + 0.15 * t, crx=1.2, cry=0.75)
    if r == 'T':
        t = (i - 1) / 11
        return dict(bw=2.6 + 1.3 * t, bd=2.0 + 1.0 * t, bh=1.8 + 0.5 * t, crx=0.8, cry=0.75)
    t = (i - 1) / 4
    return dict(bw=4.2 + 0.8 * t, bd=3.0 + 0.4 * t, bh=2.5 + 0.2 * t, crx=1.1, cry=0.8)


def canal_centre(name):
    """Centre of the vertebral canal (x=0, y, z) for a vertebra."""
    y, z = SPINE[name]
    d = vertebra_dims(name)
    return np.array([0.0, y + d['bd'] / 2 + d['cry'] + 0.1, z])


SACRUM = [  # (y, z) centre line S1..S5 then coccyx tip
    (1.2, 94.3), (2.8, 92.5), (4.1, 90.8), (5.0, 89.4), (5.5, 88.3), (4.8, 86.6)]

# ---------------------------------------------------------------- ribs
# k: (a half-width, b half-depth, yc centre-y, z_post (=T_k body z), z_costochondral, theta_c, cartilage end)
# rib path in the horizontal-ish plane: x = a*sin(t), y = yc + b*cos(t), t from ~0.3 (back) to theta_c
RIBS = {
    1: (6.5, 5.5, -2.5, 146.0, 145.0, 2.71, (2.2, -9.4, 144.3)),
    2: (9.5, 7.0, -1.8, 143.1, 139.5, 2.55, (1.8, -9.8, 141.0)),
    3: (11.0, 8.0, -1.5, 140.2, 135.5, 2.45, (1.7, -10.0, 138.0)),
    4: (12.2, 8.4, -1.3, 137.3, 132.0, 2.35, (1.7, -10.1, 135.0)),
    5: (13.0, 8.6, -1.2, 134.4, 128.5, 2.25, (1.8, -10.1, 132.0)),
    6: (13.5, 8.7, -1.2, 131.5, 125.0, 2.15, (1.9, -10.0, 129.0)),
    7: (13.8, 8.7, -1.2, 128.6, 121.5, 2.05, (1.7, -9.8, 126.2)),
    8: (13.9, 8.6, -1.0, 125.7, 118.5, 1.95, (4.5, -9.0, 122.5)),   # joins rib-7 cartilage
    9: (13.7, 8.4, -0.8, 122.8, 115.0, 1.85, (7.5, -8.0, 118.0)),   # joins rib-8 cartilage
    10: (13.2, 8.0, -0.5, 119.9, 112.0, 1.75, (10.0, -6.5, 113.5)),  # joins rib-9 cartilage
    11: (12.0, 7.4, 0.0, 117.0, 110.5, 1.75, None),                  # floating
    12: (10.0, 6.8, 0.5, 114.1, 110.5, 1.30, None),                  # floating
}
STERNUM = dict(manubrium=(141.0, 146.0), body=(126.0, 141.0), xiphoid=(121.0, 126.0), y_front=-11.0, y_back=-9.8)


def thoracic_cavity(z):
    """Inner rib-cage outline at height z: (half-width a, half-depth b, centre y)."""
    zs = [146, 140, 130, 120, 112, 104]
    return (float(np.interp(z, zs, [6.0, 9.5, 12.6, 13.4, 13.4, 12.5])),
            float(np.interp(z, zs, [4.5, 6.6, 8.0, 8.5, 8.5, 8.0])),
            float(np.interp(z, zs, [-2.5, -1.8, -1.2, -1.0, -0.8, -0.5])))


# ---------------------------------------------------------------- shoulder girdle (use TorsoMap(girdle=True))
CLAVICLE = [(2.4, -9.6, 145.5), (6.0, -9.8, 146.2), (10.0, -8.6, 146.8), (13.5, -6.0, 146.6),
            (16.5, -2.5, 145.6), (18.5, 0.0, 144.8)]          # left side, mirror x for right
SCAPULA = dict(sup_angle=(8.0, 6.0, 145.5), notch=(12.5, 3.5, 144.0), glenoid=(16.8, -0.3, 140.8),
               inf_angle=(10.0, 7.5, 128.0), medial_spine_root=(7.5, 7.8, 140.5),
               spine=[(7.8, 7.7, 141.0), (12.0, 6.0, 142.3), (16.5, 3.5, 144.0)],
               acromion=(18.4, 0.6, 144.6), coracoid=[(14.0, 1.0, 143.0), (14.6, -4.5, 142.0)])

# ---------------------------------------------------------------- pelvis (TorsoMap)
HIP_CENTRE = (9.0, -2.5, 91.0)   # = femoral head centre of the leg (leg map origin)
PELVIS = dict(asis=(11.5, -8.0, 97.0), aiis=(10.5, -6.5, 94.5),
              crest=[(11.5, -8.0, 97.0), (13.0, -5.0, 101.0), (13.0, -1.0, 103.0), (11.5, 2.5, 102.5),
                     (8.5, 4.5, 100.8), (5.0, 5.5, 98.0)],
              psis=(5.0, 5.5, 98.0), piis=(5.5, 5.0, 95.5), sciatic_notch=(7.2, 3.0, 92.3),
              ischial_spine=[(6.5, 1.5, 88.0), (4.5, 2.5, 88.0)], ischial_tuberosity=(6.0, 0.0, 84.0),
              ischiopubic=[(6.0, 0.0, 84.0), (5.0, -3.0, 83.5), (2.5, -6.5, 85.0), (0.8, -8.3, 88.0)],
              sup_pubic=[(0.8, -8.3, 89.0), (2.5, -8.4, 89.2), (6.0, -6.0, 90.0), (8.0, -4.0, 90.0)],
              obturator=(5.0, -4.5, 86.5), symphysis=(0.0, -8.3, 88.5))

# ---------------------------------------------------------------- key vessels (centre lines, TorsoMap)
AORTA = [(0.5, -3.5, 128.0), (0.0, -3.0, 133.0), (1.0, -1.0, 136.0), (2.5, 1.5, 136.0), (2.8, 3.0, 133.0),
         (2.5, 2.0, 125.0), (1.8, 0.2, 118.0), (1.0, -0.8, 114.0), (1.0, -3.0, 107.0), (0.5, -3.9, 100.5)]
AORTA_R = 1.1
IVC = [(-2.5, -2.0, 122.0), (-2.5, -0.5, 116.0), (-2.2, -2.5, 108.0), (-1.8, -3.0, 101.5), (-0.6, -3.4, 99.0)]
IVC_R = 1.2
HEART = dict(base=(-1.0, -1.5, 129.0), apex=(7.0, -7.5, 118.5), centre=(1.5, -4.5, 124.0))
TRACHEA = [(0.0, -3.4, 149.0), (0.0, -2.6, 141.0), (0.0, -1.2, 135.0), (0.0, -0.6, 133.0)]
ESOPHAGUS = [(0.3, -0.4, 151.0), (0.5, 0.2, 140.0), (1.0, 1.0, 128.0), (1.6, 0.0, 117.0), (2.0, -1.2, 113.0),
             (3.8, -3.0, 110.0)]
DIAPHRAGM_DOMES = dict(right=((-6.0, -0.5, 112.0), (8.0, 8.5, 10.0)), left=((6.0, -0.5, 110.0), (8.0, 8.5, 10.0)))

# ---------------------------------------------------------------- R6 boundary hand-offs (studs, Blender coords)
# Vessels / nerves crossing between R6 parts should end/start near these points.
HANDOFF = dict(
    neck_carotid=(2.2, -0.1, 156.0),     # torso cm (both sides +/-x); head continues upward
    neck_jugular=(2.8, 0.15, 156.0),
    neck_vertebral=(2.2, 2.6, 157.3),
    neck_cord=(0.0, 3.5, 157.5),
    axilla_artery=(17.5, 0.5, 141.5),    # torso cm, use TorsoMap(girdle=True); arm brachial starts here
    groin_femoral_artery=(8.8, -6.0, 89.5),
    groin_femoral_vein=(8.3, -5.6, 89.5),
    sciatic_exit=(7.0, 2.5, 91.0),
)
