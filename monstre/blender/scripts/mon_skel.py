"""Squelette du monstre (repère Roblox, studs) et description du rig rigide.

Repris du prototype (dictionnaire J, repère de tête FH/UH, rig_spec) avec un dos plus rond et une tête plus basse
et plus penchée, comme sur la référence, puis mis à l'échelle (SCALE) pour une hauteur d'environ 11 studs.
Les mains sont construites pour la main droite puis symétrisées (pouce et index vers l'avant et l'intérieur).
"""
import math
import numpy as np
from mon_common import unit, rot

SCALE = 1.32            # unités du prototype -> studs (prototype : 9,0 studs de haut)

# pivots en unités du prototype (côté droit = +X)
_J0 = {
    'Pelvis': (0.0, 5.40, 0.22),
    'SpineLow': (0.0, 5.95, 0.24),
    'SpineMid': (0.0, 6.68, 0.12),
    'SpineHigh': (0.0, 7.28, -0.22),
    'NeckBase': (0.0, 7.80, -0.70),
    'HeadJoint': (0.0, 7.64, -1.20),
    'Hip_R': (0.50, 5.20, 0.22),
    'Knee_R': (0.72, 3.02, -0.62),
    'Ankle_R': (0.86, 0.66, 0.22),
    'Shoulder_R': (0.98, 7.42, -0.44),
    'Elbow_R': (1.50, 5.36, -0.78),
    'Wrist_R': (1.86, 3.46, -1.04),
}


def mirror(p):
    p = np.asarray(p, float)
    return np.array([-p[0], p[1], p[2]])


def _scaled(p):
    return np.asarray(p, float) * SCALE


J = {k: _scaled(v) for k, v in _J0.items()}
for _k in list(J):
    if _k.endswith('_R'):
        J[_k[:-2] + '_L'] = mirror(J[_k])

# tête : penchée de 48° vers le bas, crâne allongé vers l'avant
HEAD_PITCH = math.radians(50)
FH = np.array([0.0, -math.sin(HEAD_PITCH), -math.cos(HEAD_PITCH)])      # avant de la tête
UH = np.array([0.0, math.cos(HEAD_PITCH), -math.sin(HEAD_PITCH)])       # haut de la tête
XH = np.array([1.0, 0.0, 0.0])                                          # droite de la tête
HEAD_C = J['HeadJoint'] + (UH * 0.26 + FH * 0.56) * SCALE               # centre du crâne
JAW_HINGE = HEAD_C + (-FH * 0.30 - UH * 0.20) * SCALE                   # charnière de la mâchoire
JAW_OPEN = math.radians(14)                                            # mâchoire entrouverte (repos)

# ----------------------------------------------------------------------------------------------------------------
# mains (construites à droite, symétrisées à gauche)

FINGERS = ['Index', 'Middle', 'Ring', 'Pinky', 'Thumb']
_FINGER_LEN = {'Index': (0.68, 0.58), 'Middle': (0.78, 0.66), 'Ring': (0.72, 0.61), 'Pinky': (0.60, 0.52),
               'Thumb': (0.56,)}
_FINGER_OFF = {'Index': 0.20, 'Middle': 0.07, 'Ring': -0.065, 'Pinky': -0.19}     # le long du côté pouce
_FINGER_FAN = {'Index': -8.0, 'Middle': -2.0, 'Ring': 4.0, 'Pinky': 10.0}          # degrés (+ = vers l'auriculaire)
_FINGER_CURL = {'Index': (30, 46, 34), 'Middle': (28, 48, 36), 'Ring': (32, 50, 36), 'Pinky': (36, 52, 38),
                'Thumb': (24, 36)}
PALM_LEN = 0.62


def _hand_right():
    el, wr = J['Elbow_R'], J['Wrist_R']
    Tf = unit(wr - el)
    D = unit(rot([1.0, 0, 0], math.radians(-12)) @ Tf)                  # direction des doigts (un peu vers l'avant)
    n0 = np.array([-0.62, 0.0, 0.78])                                   # paume vers l'arrière et l'intérieur
    n = unit(n0 - D * (n0 @ D))
    t = unit(np.cross(D, n))                                            # côté du pouce (avant-intérieur)
    s = SCALE
    knuck = wr + D * PALM_LEN * s
    fingers = {}
    for name in FINGERS[:4]:
        base = knuck + t * _FINGER_OFF[name] * s + D * (0.03 if name in ('Middle', 'Ring') else -0.02) * s
        d0 = unit(rot(n, math.radians(_FINGER_FAN[name])) @ D)
        cax = unit(np.cross(d0, n))                                     # axe de flexion (vers la paume)
        c = _FINGER_CURL[name]
        d = rot(cax, math.radians(c[0])) @ d0
        a = base.copy()
        segs = []
        for j, L in enumerate(_FINGER_LEN[name]):
            b = a + d * L * s
            segs.append((a.copy(), b.copy(), d.copy()))
            a = b
            d = rot(cax, math.radians(c[j + 1])) @ d
        fingers[name] = dict(segs=segs, axis=cax, tip_dir=d)
    tb = wr + D * 0.16 * s + t * 0.17 * s + n * 0.05 * s
    dt = unit(D * 0.85 + t * 0.32 + n * 0.42)
    cax = unit(np.cross(dt, n + t * 0.3))
    a = tb.copy()
    d = rot(cax, math.radians(_FINGER_CURL['Thumb'][0])) @ dt
    b = a + d * _FINGER_LEN['Thumb'][0] * s
    fingers['Thumb'] = dict(segs=[(a.copy(), b.copy(), d.copy())], axis=cax,
                            tip_dir=rot(cax, math.radians(_FINGER_CURL['Thumb'][1])) @ d)
    return dict(D=D, N=n, T=t, wrist=wr, knuckles=knuck, fingers=fingers)


def _mirror_hand(h):
    M = np.diag([-1.0, 1.0, 1.0])
    out = dict(D=M @ h['D'], N=M @ h['N'], T=M @ h['T'], wrist=M @ h['wrist'], knuckles=M @ h['knuckles'])
    fingers = {}
    for name, f in h['fingers'].items():
        fingers[name] = dict(segs=[(M @ a, M @ b, M @ d) for a, b, d in f['segs']],
                             axis=-(M @ f['axis']), tip_dir=M @ f['tip_dir'])
    out['fingers'] = fingers
    return out


HAND = {'R': _hand_right()}
HAND['L'] = _mirror_hand(HAND['R'])

# ----------------------------------------------------------------------------------------------------------------
# rig : pièce -> (parent, pivot, nom de l'articulation)


def rig_spec():
    R = {'Pelvis': ('HumanoidRootPart', J['Pelvis'], 'Root'),
         'Abdomen': ('Pelvis', J['SpineLow'], 'SpineLow'),
         'Chest': ('Abdomen', J['SpineMid'], 'SpineMid'),
         'UpperChest': ('Chest', J['SpineHigh'], 'SpineHigh'),
         'Neck': ('UpperChest', J['NeckBase'], 'NeckBase'),
         'Head': ('Neck', J['HeadJoint'], 'HeadJoint'),
         'Jaw': ('Head', JAW_HINGE, 'JawHinge')}
    for side in ('R', 'L'):
        R['Thigh_' + side] = ('Pelvis', J['Hip_' + side], 'Hip_' + side)
        R['Shin_' + side] = ('Thigh_' + side, J['Knee_' + side], 'Knee_' + side)
        R['Foot_' + side] = ('Shin_' + side, J['Ankle_' + side], 'Ankle_' + side)
        R['UpperArm_' + side] = ('UpperChest', J['Shoulder_' + side], 'Shoulder_' + side)
        R['Forearm_' + side] = ('UpperArm_' + side, J['Elbow_' + side], 'Elbow_' + side)
        R['Hand_' + side] = ('Forearm_' + side, J['Wrist_' + side], 'Wrist_' + side)
        for name in FINGERS:
            segs = HAND[side]['fingers'][name]['segs']
            for j, (a, b, d) in enumerate(segs):
                part = '%s%d_%s' % (name, j + 1, side)
                parent = 'Hand_' + side if j == 0 else '%s%d_%s' % (name, j, side)
                R[part] = (parent, a, '%s%dJoint_%s' % (name, j + 1, side))
    return R


PIECES = list(rig_spec().keys())

if __name__ == '__main__':
    R = rig_spec()
    print(len(R), 'pièces')
    for k, (p, piv, jn) in R.items():
        print('%-12s %-12s %-16s %s' % (k, p, jn, np.round(piv, 3)))
    print('HEAD_C', HEAD_C.round(3), 'JAW', JAW_HINGE.round(3))
