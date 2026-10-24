"""Clips du monstre : déplacement (repos, marche, course, saut, chute, atterrissage), hurlement, flairer, attaque.
Les mises à mort sont dans mon_morts.py. Voir mon_anim.py pour les conventions d'angles."""
import math
import numpy as np
import mon_anim as A
from mon_anim import Pose, euler, Rx, Ry, Rz, fk, leg_ik, finger_curl, merge, curve, cyc, smooth01, SGN, ANKLE

TAU = 2 * math.pi


def body(pelvis=(0, 0, 0), pel_rot=(0, 0, 0), spine=(0, 0, 0), chest=(0, 0, 0), upper=(0, 0, 0), neck=(0, 0, 0),
         head=(0, 0, 0), jaw=0.0, arms=None, hands=None, fingers=None):
    """Pose du haut du corps. pelvis : translation (x, y, z) du bassin ; *_rot / spine / chest / upper / neck / head :
    (pitch, yaw, roll) ; jaw : ouverture en plus du repos (+ = s'ouvre) ; arms[side] = (épaule pitch, yaw, roll,
    coude pitch, poignet pitch, poignet roll) ; fingers[side] = (flexion, écart)."""
    P = Pose()
    P['Pelvis'] = (euler(*pel_rot), np.array(pelvis, float))
    P['Abdomen'] = (euler(*spine), np.zeros(3))
    P['Chest'] = (euler(*chest), np.zeros(3))
    P['UpperChest'] = (euler(*upper), np.zeros(3))
    P['Neck'] = (euler(*neck), np.zeros(3))
    P['Head'] = (euler(*head), np.zeros(3))
    if jaw:
        # la mâchoire tourne autour de l'axe X de la tête : + = le menton descend (vers l'avant/bas)
        P['Jaw'] = (A.axis_angle(np.array([1.0, 0, 0]), -jaw), np.zeros(3))
    arms = arms or {}
    for side, v in arms.items():
        sp, sy, sr, el, wp, wr = (list(v) + [0, 0, 0, 0, 0, 0])[:6]
        s = SGN[side]
        P['UpperArm_' + side] = (euler(sp, sy * s, sr * s), np.zeros(3))
        P['Forearm_' + side] = (Rx(el), np.zeros(3))
        P['Hand_' + side] = (euler(wp, 0, wr * s), np.zeros(3))
    for side, v in (fingers or {}).items():
        cu, spd = (list(v) + [0, 0])[:2]
        P.update(finger_curl(side, cu, spd))
    return P


def legs_on(P, feet, foot_pitch=None, abd=None):
    """IK des deux jambes : feet[side] = position voulue de la cheville (repère modèle)."""
    W = fk(P)
    out = Pose(P)
    for side, tgt in feet.items():
        sol, _ = leg_ik(side, W['Pelvis'], tgt, (foot_pitch or {}).get(side, 0.0), (abd or {}).get(side, 0.0))
        out.update(sol)
    return out


# ------------------------------------------------------------------------------------------------ repos

def idle(t):
    T = 4.0
    ph = t / T
    br = math.sin(TAU * ph)                       # respiration
    br2 = math.sin(TAU * ph * 2 + 0.7)
    sway = math.sin(TAU * ph + 1.1)
    P = body(pelvis=(0.07 * sway, -0.06 - 0.03 * br, 0.0), pel_rot=(0, 1.5 * sway, -1.2 * sway),
             spine=(0.6 * br, 0, 0), chest=(1.2 * br, 0, 0), upper=(1.6 * br, -1.0 * sway, 0),
             neck=(-1.0 * br + 1.5 * math.sin(TAU * ph * 0.5), 2.5 * math.sin(TAU * ph * 0.5 + 0.4), 1.5 * br2),
             head=(1.0 * br2, 3.0 * math.sin(TAU * ph * 0.5 + 1.2), -1.5 * math.sin(TAU * ph * 0.5)),
             jaw=1.5 + 1.5 * max(0.0, math.sin(TAU * ph * 2 - 1.0)) ** 4,
             arms={'R': (1.5 * br - 1.0 * sway, 0, 1.0 + 0.8 * br, 3 + 2 * br2, -2, 0),
                   'L': (1.5 * br + 1.0 * sway, 0, 1.0 + 0.8 * br, 3 - 2 * br2, -2, 0)},
             fingers={'R': (6 + 7 * max(0.0, math.sin(TAU * ph * 3)) ** 3, 2),
                      'L': (6 + 7 * max(0.0, math.sin(TAU * ph * 3 + 2.0)) ** 3, 2)})
    return legs_on(P, {'R': ANKLE['R'], 'L': ANKLE['L']})


# ------------------------------------------------------------------------------------------------ marche et course

class Gait:
    """Cycle de marche : pieds plantés (la cheville recule exactement à la vitesse du clip pendant l'appui),
    balancement soulevé, bassin qui descend aux doubles appuis."""

    def __init__(self, T, v, duty, lift, drop, bob, lean, arm_amp, elbow, sway=0.1, yaw=6.0, head_lift=0.0,
                 toe_down=-18.0, heel_kick=0.0):
        self.T, self.v, self.duty, self.lift, self.drop, self.bob = T, v, duty, lift, drop, bob
        self.lean, self.arm_amp, self.elbow, self.sway, self.yaw = lean, arm_amp, elbow, sway, yaw
        self.head_lift, self.toe_down, self.heel_kick = head_lift, toe_down, heel_kick
        self.stance = v * T * duty                 # distance parcourue pendant l'appui

    def foot(self, side, ph):
        """Cheville (repère modèle) et pitch du pied (monde) pour la phase ph (0 = attaque du talon de ce pied)."""
        a = ANKLE[side].copy()
        d, s = self.duty, self.stance
        if ph < d:                                  # appui : du devant (-Z) vers l'arrière, au sol
            u = ph / d
            z = -s / 2 + s * u
            y = a[1]
            # déroulé : talon au contact (pointe levée), pied à plat, talon qui se lève avant le décollage
            fp = 8.0 * (1 - smooth01(u / 0.15)) - 22.0 * smooth01((u - 0.78) / 0.22)
            y += 0.25 * smooth01((u - 0.78) / 0.22)
        else:                                       # balancement : de l'arrière vers l'avant, soulevé
            u = (ph - d) / (1 - d)
            e = smooth01(u)
            z = s / 2 - s * e
            y = a[1] + self.lift * math.sin(math.pi * min(1.0, u * 1.05)) ** 1.2 + 0.25 * (1 - smooth01(u / 0.2))
            z += self.heel_kick * math.sin(math.pi * u) * (1 - u)       # talon qui remonte derrière (course)
            fp = self.toe_down * math.sin(math.pi * u) + 8.0 * smooth01((u - 0.8) / 0.2)
        return np.array([a[0], y, a[2] + z]), fp

    def pose(self, t):
        ph = (t / self.T) % 1.0
        phR, phL = ph, (ph + 0.5) % 1.0
        c2 = math.cos(2 * TAU * ph)
        side_sh = math.sin(TAU * ph)                # > 0 : appui droit
        P = body(pelvis=(self.sway * side_sh, -self.drop - self.bob * c2, 0.0),
                 pel_rot=(self.lean * 0.25, self.yaw * math.cos(TAU * ph), -2.5 * side_sh),
                 spine=(self.lean * 0.3, -self.yaw * 0.4 * math.cos(TAU * ph), 1.0 * side_sh),
                 chest=(self.lean * 0.3, -self.yaw * 0.4 * math.cos(TAU * ph), 0.8 * side_sh),
                 upper=(self.lean * 0.15, -self.yaw * 0.3 * math.cos(TAU * ph), 0.5 * side_sh),
                 neck=(-self.lean * 0.45 + self.head_lift + 2.0 * c2, 2.0 * math.cos(TAU * ph), -1.0 * side_sh),
                 head=(-self.lean * 0.3 + self.head_lift * 0.6 + 1.5 * c2, 2.0 * math.cos(TAU * ph), 0),
                 jaw=2.0 + 2.0 * max(0.0, c2),
                 arms={'R': (self.arm_amp * math.cos(TAU * (ph + 0.5) - 0.35), 0, 3 + 1.5 * side_sh,
                             self.elbow + self.elbow * 0.6 * math.cos(TAU * (ph + 0.5) - 0.9), -4, 0),
                       'L': (self.arm_amp * math.cos(TAU * ph - 0.35), 0, 3 - 1.5 * side_sh,
                             self.elbow + self.elbow * 0.6 * math.cos(TAU * ph - 0.9), -4, 0)},
                 fingers={'R': (8 + 6 * math.sin(TAU * ph * 2), 3), 'L': (8 + 6 * math.sin(TAU * ph * 2 + 1.0), 3)})
        fR, pR = self.foot('R', phR)
        fL, pL = self.foot('L', phL)
        return legs_on(P, {'R': fR, 'L': fL}, {'R': pR, 'L': pL})


WALK = Gait(T=1.6, v=5.5, duty=0.62, lift=0.85, drop=0.55, bob=0.1, lean=-6.0, arm_amp=12.0, elbow=6.0, sway=0.12,
            yaw=6.0, head_lift=2.0)
RUN = Gait(T=0.84, v=20.0, duty=0.36, lift=1.7, drop=0.85, bob=0.22, lean=-26.0, arm_amp=34.0, elbow=28.0, sway=0.08,
           yaw=9.0, head_lift=16.0, toe_down=-35.0, heel_kick=1.2)


# ------------------------------------------------------------------------------------------------ saut, chute, atterrissage

def jump(t):
    """Saut (0,5 s, la dernière pose est tenue) : jambes repliées, bras levés en arrière, tête en avant."""
    k = smooth01(t / 0.35)
    P = body(pelvis=(0, 0.2 * k, 0), pel_rot=(6 * k, 0, 0), spine=(-6 * k, 0, 0), chest=(-4 * k, 0, 0),
             upper=(6 * k, 0, 0), neck=(4 * k, 0, 0), head=(6 * k, 0, 0), jaw=10 * k,
             arms={'R': (-25 * k, 0, 28 * k, 25 * k, -10 * k, 0), 'L': (-25 * k, 0, 28 * k, 25 * k, -10 * k, 0)},
             fingers={'R': (-8 * k, 10 * k), 'L': (-8 * k, 10 * k)})
    feet = {s: ANKLE[s] + np.array([0, 1.9 * k, -0.4 * k]) for s in ('R', 'L')}
    return legs_on(P, feet, {'R': -25 * k, 'L': -25 * k})


def fall(t):
    """Chute (boucle 0,9 s) : bras écartés qui battent, jambes pendantes un peu en avant, gueule ouverte."""
    ph = t / 0.9
    w = math.sin(TAU * ph)
    P = body(pelvis=(0, 0.1, 0), pel_rot=(3, 0, 0), spine=(-3, 0, 0), chest=(-2, 0, 0), upper=(4, 0, 0),
             neck=(6 + 2 * w, 0, 0), head=(5, 0, 0), jaw=16 + 4 * w,
             arms={'R': (10 + 12 * w, 0, 42 + 10 * w, 30 - 10 * w, -15, 0),
                   'L': (10 - 12 * w, 0, 42 - 10 * w, 30 + 10 * w, -15, 0)},
             fingers={'R': (-10, 14), 'L': (-10, 14)})
    feet = {'R': ANKLE['R'] + np.array([0.1, 0.5 + 0.15 * w, -0.7]), 'L': ANKLE['L'] + np.array([-0.1, 0.5 - 0.15 * w, -0.4])}
    return legs_on(P, feet, {'R': -30, 'L': -30})


def land(t):
    """Atterrissage (0,45 s) : genoux qui amortissent, bras vers l'avant, puis retour vers le repos."""
    a = curve(t, [(0, 0), (0.12, 1.0), (0.45, 0.0)])
    P = body(pelvis=(0, -1.4 * a, -0.2 * a), pel_rot=(8 * a, 0, 0), spine=(-8 * a, 0, 0), chest=(-6 * a, 0, 0),
             upper=(-3 * a, 0, 0), neck=(6 * a, 0, 0), head=(4 * a, 0, 0), jaw=6 * a,
             arms={'R': (20 * a, 0, 10 * a, 20 * a, -10 * a, 0), 'L': (20 * a, 0, 10 * a, 20 * a, -10 * a, 0)},
             fingers={'R': (15 * a, 4), 'L': (15 * a, 4)})
    return legs_on(P, {'R': ANKLE['R'], 'L': ANKLE['L']})


# ------------------------------------------------------------------------------------------------ hurlement, flairer, attaque

def roar(t):
    """Hurlement (2,6 s) : se redresse, poitrine en avant, bras écartés, gueule grande ouverte, tremblements."""
    a = curve(t, [(0, 0), (0.5, 1.0), (2.1, 1.0), (2.6, 0.0)])
    tr = a * math.sin(TAU * t * 11) * smooth01((t - 0.5) / 0.2)
    P = body(pelvis=(0, 0.25 * a, 0.2 * a), pel_rot=(-3 * a, 0, 0), spine=(6 * a, 0, 0.6 * tr),
             chest=(7 * a + 0.5 * tr, 0, 0), upper=(9 * a, 0, 0), neck=(11 * a + 1.2 * tr, 0, 0),
             head=(10 * a + 1.5 * tr, 1.5 * tr, 0), jaw=30 * a + 2 * tr,
             arms={'R': (-18 * a, 0, 38 * a + tr, 25 * a, -15 * a, 0), 'L': (-18 * a, 0, 38 * a - tr, 25 * a, -15 * a, 0)},
             fingers={'R': (-12 * a + 4 * tr, 16 * a), 'L': (-12 * a - 4 * tr, 16 * a)})
    return legs_on(P, {'R': ANKLE['R'] + np.array([0.1 * a, 0, 0]), 'L': ANKLE['L'] - np.array([0.1 * a, 0, 0])})


def sniff(t):
    """Flairer (boucle 3 s) : tête basse qui balaie, petits coups de gueule, accroupi."""
    ph = t / 3.0
    sc = math.sin(TAU * ph)
    sn = max(0.0, math.sin(TAU * ph * 6)) ** 6
    P = body(pelvis=(0, -0.45, -0.1), pel_rot=(4, 3 * sc, 0), spine=(-6, 3 * sc, 0), chest=(-5, 3 * sc, 0),
             upper=(-3, 3 * sc, 0), neck=(-9 + 2 * sn, 5 * sc, 2 * sc), head=(-6 + 3 * sn, 6 * sc, 2 * sc), jaw=3 + 4 * sn,
             arms={'R': (8, 0, 4, 12, -6, 0), 'L': (8, 0, 4, 12, -6, 0)},
             fingers={'R': (18 + 6 * sn, 3), 'L': (18 + 6 * sn, 3)})
    return legs_on(P, {'R': ANKLE['R'], 'L': ANKLE['L']})


def attack(t):
    """Attaque (1,1 s) : prise d'élan (bras en arrière, accroupi), bond avec les deux bras qui fauchent, retour."""
    w = curve(t, [(0, 0), (0.3, 1.0), (0.42, 1.0), (0.55, 0.0)])         # élan
    s = curve(t, [(0.38, 0), (0.55, 1.0), (0.75, 1.0), (1.1, 0.0)])      # frappe
    P = body(pelvis=(0, -0.5 * w - 0.3 * s, 0.3 * w - 1.6 * s), pel_rot=(6 * w - 8 * s, 0, 0),
             spine=(-4 * w - 8 * s, 0, 0), chest=(-4 * w - 7 * s, 0, 0), upper=(5 * w - 4 * s, 0, 0),
             neck=(6 * w + 4 * s, 0, 0), head=(4 * w + 6 * s, 0, 0), jaw=8 * w + 26 * s,
             arms={'R': (-35 * w + 70 * s, 0, 25 * w + 8 * s, 35 * w + 10 * s, -10 * w + 15 * s, 0),
                   'L': (-35 * w + 70 * s, 0, 25 * w + 8 * s, 35 * w + 10 * s, -10 * w + 15 * s, 0)},
             fingers={'R': (-10 * w + 30 * s, 14 * w), 'L': (-10 * w + 30 * s, 14 * w)})
    return legs_on(P, {'R': ANKLE['R'] + np.array([0, 0, -1.2 * s]), 'L': ANKLE['L'] + np.array([0, 0, 0.6 * s])})


CLIPS = {
    'idle': A.Clip('idle', 'Monstre_Repos', 4.0, idle, loop=True, priority='Idle', label='Repos'),
    'walk': A.Clip('walk', 'Monstre_Marche', WALK.T, WALK.pose, loop=True, priority='Movement', speed=WALK.v,
                   label='Marche'),
    'run': A.Clip('run', 'Monstre_Course', RUN.T, RUN.pose, loop=True, priority='Movement', speed=RUN.v, label='Course'),
    'jump': A.Clip('jump', 'Monstre_Saut', 0.5, jump, loop=False, priority='Action', label='Saut'),
    'fall': A.Clip('fall', 'Monstre_Chute', 0.9, fall, loop=True, priority='Action', label='Chute'),
    'land': A.Clip('land', 'Monstre_Atterrissage', 0.45, land, loop=False, priority='Action', label='Atterrissage'),
    'roar': A.Clip('roar', 'Monstre_Hurlement', 2.6, roar, loop=False, priority='Action', label='Hurlement',
                   markers=[(0.45, 'Son', 'hurlement')]),
    'sniff': A.Clip('sniff', 'Monstre_Flairer', 3.0, sniff, loop=True, priority='Idle', label='Flairer'),
    'attack': A.Clip('attack', 'Monstre_Attaque', 1.1, attack, loop=False, priority='Action', label='Attaque',
                     markers=[(0.5, 'Coup', ''), (0.45, 'Son', 'grognement')]),
}
