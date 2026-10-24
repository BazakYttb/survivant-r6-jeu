"""Mises à mort du monstre (animations appariées) : clip du monstre (avec la piste VictimeAncre qui porte la victime)
et clip de la victime sur le rig du survivant R6 articulé (src/anim.py du projet, en lecture seule).

Chaque mise à mort = une ou plusieurs phases (clips) jouées par le script serveur, avec des marqueurs
(KeyframeMarker) qui déclenchent caméra, sang et sons côté Roblox :
  Morsure / Coup / Impact / Retrait (valeur : endroit), Eclaboussure (valeur : endroit du sang), Coupure (valeur :
  durée de l'écran noir), Camera (valeur : plan), Tremble (valeur : force), Lacher, Silence (valeur : durée),
  Infection, Son (valeur : nom du son), Ecran (sang sur l'écran), Flaque (flaque sous le corps).

Repère : celui du monstre (mon_anim). Victime : son HumanoidRootPart est soudé à la pièce VictimeAncre ; au repos
elle est debout 4 studs devant le monstre, tournée vers lui (rotation de 180 degrés autour de Y).
Canaux de l'ancre : p, y, r (rotation autour du pivot), x, ty, z (translation) ; poids : wb (point collé à la
gueule), wa / wm (point collé à une paume), wd (traînée : cheville dans la main, tête au sol), sol (le point le plus bas
de la victime posé au sol), wiR / wiL (paumes du monstre sur des points de la victime).
Canaux du monstre en plus de ceux de body() : turn (lacet du bassin autour de l'axe du HumanoidRootPart),
footR / footL (a : angle du pied autour de cet axe, x / ty / z : décalage de la cheville, p : pitch du pied),
ikR / ikL (w : poids, x / y / z : point visé par la paume (repère modèle, ou décalage depuis la gueule si m = 1), px / py / pz : direction du coude
(repère du corps, tourne avec turn))."""
import sys
import math
import numpy as np
import mon_anim as A
import mon_clips as C
from mon_anim import Pose, euler, Rx, Ry, fk, point, Track, smooth01, ANKLE, HRP_C, leg_ik
from mon_skel import HEAD_C, FH, UH, SCALE

from mon_common import src_survivant

sys.path.insert(0, src_survivant())
import anim as SA                                    # rig du survivant (victime), lecture seule

TAU = 2 * math.pi
SIDES = ('R', 'L')
MOUTH = HEAD_C + (FH * 0.6 - UH * 0.3) * SCALE * 0.98          # avant de la gueule (pièce Head)
R180 = Ry(180.0)
PIV_A = A.PIV['VictimeAncre']

# points de la victime : (pièce du survivant, point dans le repère centré de la pièce)
VPTS = {'cou': ('Torso', (-0.38, 1.02, -0.08)),                 # côté gauche du cou (à droite du monstre)
        'nuque': ('Torso', (0.0, 1.0, 0.25)),
        'poitrine': ('Torso', (0.0, 0.35, -0.5)), 'ventre': ('Torso', (0.0, -0.4, -0.52)),
        'epauleD': ('Torso', (0.82, 0.88, 0.0)), 'epauleG': ('Torso', (-0.82, 0.88, 0.0)),
        'hancheD': ('Torso', (0.6, -0.85, 0.0)), 'dos': ('Torso', (0.0, 0.2, 0.5)),
        'chevilleD': ('RightLowerLeg', (0.0, -0.3, 0.0)), 'chevilleG': ('LeftLowerLeg', (0.0, -0.3, 0.0)),
        'brasG': ('LeftLowerArm', (0.0, 0.05, 0.0)), 'brasD': ('RightLowerArm', (0.0, 0.05, 0.0)),
        'cuisseD': ('RightUpperLeg', (0.0, 0.0, 0.0)), 'tete': ('Head', (0.0, 0.0, 0.0))}


def vpoint(world, name):
    part, loc = VPTS[name]
    return (world[part] @ np.array([*loc, 1.0]))[:3]


def victim_build(v):
    """Pose du survivant depuis les canaux : root (x, y, z, lean, yaw, tilt), head (pitch, yaw, roll),
    armR/armL (pitch, abd, twist, elbow), legR/legL (pitch, abd, twist, knee)."""
    arms = {'Right': v.get('armR', {}), 'Left': v.get('armL', {})}
    legs = {'Right': v.get('legR', {}), 'Left': v.get('legL', {})}
    return SA.build(v.get('root', {}), v.get('head', {}), arms, legs, clamp=False)


def add(d, extra):
    """Additionne des canaux (dict de dicts) : superpositions (secousses, lutte)."""
    out = {k: dict(v) for k, v in d.items()}
    for k, v in extra.items():
        o = out.setdefault(k, {})
        for c, x in v.items():
            o[c] = o.get(c, 0.0) + x
    return out


def anchor_frame(R_a, t_a):
    """Repère de la victime (son HRP) dans le repère modèle du monstre."""
    return A.T4(PIV_A) @ A.M4(R_a, t_a) @ A.M4(R180)


def victim_low(F, wv):
    return min(SA.lowest(F @ wv[p], p) for p in SA.PARTS)


def attach_t(R_a, pv, target):
    """Translation de l'ancre qui met le point pv de la victime (repère de son HRP) sur target."""
    return np.asarray(target, float) - PIV_A - R_a @ (R180 @ pv)


def euler_of(R):
    """R = Ry(y) Rz(r) Rx(p) -> (p, y, r) en degrés."""
    r = math.asin(max(-1.0, min(1.0, R[1, 0])))
    p = math.atan2(-R[1, 2], R[1, 1])
    y = math.atan2(-R[2, 0], R[0, 0])
    return math.degrees(p), math.degrees(y), math.degrees(r)


def drag_solve(palm, wv, pt, psi, theta_pref=-100.0):
    """Victime tenue par le point pt dans la paume, tête vers la direction horizontale (sin psi, 0, cos psi)
    (psi = 0 : vers +Z, derrière le monstre ; 180 : vers -Z) : tangage choisi pour que son point le plus bas touche
    le sol (racine la plus proche de theta_pref)."""
    pv = vpoint(wv, pt)

    def at(th):
        R_a = euler(th, psi + 180.0, 0.0)
        t_a = attach_t(R_a, pv, palm)
        return R_a, t_a, victim_low(anchor_frame(R_a, t_a), wv)

    ths = np.arange(-175.0, -24.0, 2.5)
    lows = [at(th)[2] for th in ths]
    roots = []
    for i in range(len(ths) - 1):
        if (lows[i] > 0) != (lows[i + 1] > 0):
            a, b, la = ths[i], ths[i + 1], lows[i]
            for _ in range(22):
                mid = (a + b) / 2
                lm = at(mid)[2]
                if (lm > 0) == (la > 0):
                    a, la = mid, lm
                else:
                    b = mid
            roots.append((a + b) / 2)
    th = min(roots, key=lambda r: abs(r - theta_pref)) if roots else float(ths[int(np.argmin(np.abs(lows)))])
    R_a, t_a, _ = at(th)
    return R_a, t_a


def monster_body(m):
    """Haut du corps du monstre depuis les canaux de la piste."""
    def g(k):
        v = m.get(k, {})
        return tuple(v.get(c, 0.0) for c in ('p', 'y', 'r'))
    pel = m.get('pel', {})
    arms = {s: tuple(m.get('arm' + s, {}).get(c, 0.0) for c in ('sp', 'sy', 'sr', 'el', 'wp', 'wr')) for s in SIDES}
    fing = {s: (m.get('fin' + s, {}).get('c', 8.0), m.get('fin' + s, {}).get('s', 2.0)) for s in SIDES}
    return C.body(pelvis=(pel.get('x', 0.0), pel.get('ty', 0.0), pel.get('z', 0.0)),
                  pel_rot=(pel.get('p', 0.0), pel.get('y', 0.0), pel.get('r', 0.0)),
                  spine=g('spine'), chest=g('chest'), upper=g('upper'), neck=g('neck'), head=g('head'),
                  jaw=m.get('jaw', {}).get('a', 0.0), arms=arms, fingers=fing)


def turn_pose(P, deg):
    """Tourne tout le corps (bassin) autour de l'axe vertical du HumanoidRootPart."""
    R, t = P.get_rt('Pelvis')
    P['Pelvis'] = (Ry(deg) @ R, Ry(deg) @ t)
    return P


def turn_anchor(R_a, t_a, deg):
    """Même rotation appliquée à l'ancre de la victime (enfant du HumanoidRootPart)."""
    Q = A.T4(HRP_C) @ A.M4(Ry(deg)) @ A.T4(-HRP_C)
    M = A.T4(-PIV_A) @ Q @ A.T4(PIV_A) @ A.M4(R_a, t_a)
    return M[:3, :3], M[:3, 3]


def arm_to(P, W, side, target, w, pole):
    sol = A.arm_ik(side, W, target, pole)
    for n, (R, tr) in sol.items():
        R0, _ = P.get_rt(n)
        P[n] = (A.slerp_R(R0, R, min(1.0, w)), tr)
    return P


def normalize(keys, hold=()):
    """Complète les clés : un canal absent d'une clé vaut 0 à cette clé (sinon il garderait la valeur des clés
    voisines), sauf les groupes / canaux de `hold` (cibles d'IK...), interpolés entre les clés qui les donnent."""
    allch = {}
    for _, d in keys:
        for g, v in d.items():
            allch.setdefault(g, set()).update(v.keys())
    out = []
    for t, d in keys:
        d2 = {g: dict(v) for g, v in d.items()}
        for g, chs in allch.items():
            if g in hold:
                continue
            gd = d2.setdefault(g, {})
            for c in chs:
                if (g, c) not in hold:
                    gd.setdefault(c, 0.0)
        out.append((t, d2))
    return out


class Kill:
    """Une phase de mise à mort. monster / victim / anchor : clés (temps, canaux) pour Track (voir l'en-tête).
    attach : {point de la victime: ('bouche' | 'mainR' | 'mainL', canal de poids)} ;
    ik : {côté: (point de la victime, canal de poids, pôle)} : la paume va sur ce point ;
    feet : t -> {turn, footR, footL} (remplace ces canaux : demi-tours, pas) ;
    drag : (point de la victime, côté de la main, canal de poids, canal du lacet de la tête ou None) ;
    over_m / over_v / over_a : t -> canaux ajoutés au monstre / à la victime / à l'ancre (secousses, lutte). Les clés d'ancre avec snap=1 prennent la position que
    donnent les attaches à cet instant (pour lâcher la victime sans saut)."""

    def __init__(self, key, name, label, length, monster, victim, anchor, loop=False, attach=None, ik=None,
                 drag=None, over_m=None, over_v=None, markers=(), priority='Action4', vname=None, vloop=None,
                 feet=None, over_a=None):
        self.key, self.name, self.label, self.length, self.loop = key, name, label, length, loop
        self.feet = feet
        self.over_a = over_a or (lambda t: {})
        monster = normalize(monster, hold=('ikR', 'ikL'))
        victim = normalize(victim)
        anchor = normalize(anchor, hold=(('ancre', 'hd'), ('ancre', 'snap')))
        self.mt, self.vt = Track(monster), Track(victim)
        self.attach = attach or {}
        self.ik = ik or {}
        self.drag = drag
        self.over_m = over_m or (lambda t: {})
        self.over_v = over_v or (lambda t: {})
        self.markers = sorted(markers)
        self.priority = priority
        self.vname = vname or name.replace('Monstre_', 'Victime_')
        self.vloop = loop if vloop is None else vloop
        self.at = Track(anchor)
        if any(d.get('ancre', {}).get('snap') for _, d in anchor):
            keys = []
            for t, d in anchor:
                d = {k: dict(v) for k, v in d.items()}
                if d.get('ancre', {}).pop('snap', None):
                    _, tr = self(t)['VictimeAncre']
                    d['ancre'].update(x=float(tr[0]), ty=float(tr[1]), z=float(tr[2]))
                keys.append((t, d))
            self.at = Track(keys)

    def victim(self, t):
        return victim_build(add(self.vt.at(t), self.over_v(t)))

    def monster_pose(self, t):
        m = add(self.mt.at(t), self.over_m(t))
        if self.feet:                                       # demi-tour / pas : remplace turn, footR, footL
            m.update(self.feet(t))
        P = monster_body(m)
        turn = m.get('turn', {}).get('a', 0.0)
        if abs(turn) > 1e-6:
            turn_pose(P, turn)
        W = fk(P)
        for s in SIDES:
            f = m.get('foot' + s, {})
            a = f.get('a', 0.0)
            v = ANKLE[s] + np.array([f.get('x', 0.0), f.get('ty', 0.0), f.get('z', 0.0)]) - HRP_C
            sol, _ = leg_ik(s, W['Pelvis'], HRP_C + Ry(a) @ v, f.get('p', 0.0), 0.0, a)
            P.update(sol)
        return P, m

    def anchor_rt(self, av):
        R_a = euler(av.get('p', 0.0), av.get('y', 0.0), av.get('r', 0.0))
        t_a = np.array([av.get('x', 0.0), av.get('ty', 0.0), av.get('z', 0.0)])
        return R_a, t_a

    def __call__(self, t):
        P, m = self.monster_pose(t)
        W = fk(P)
        for s in SIDES:                                     # paumes vers des points fixes
            ik = m.get('ik' + s)
            if ik and ik.get('w', 0.0) > 1e-4:
                tgt = np.array([ik.get('x', 0.0), ik.get('y', 0.0), ik.get('z', 0.0)])
                if ik.get('m', 0.0) > 0.5:                  # cible relative à la gueule (main portée à la bouche)
                    tgt = tgt + point(W, 'Head', MOUTH)
                pole = Ry(m.get('turn', {}).get('a', 0.0)) @ np.array([ik.get('px', 0.0), ik.get('py', -1.0),
                                                                        ik.get('pz', 0.6)])     # pôle : repère du corps
                arm_to(P, W, s, tgt, ik['w'], pole)
                W = fk(P)
        av = add({'ancre': self.at.at(t).get('ancre', {})}, {'ancre': self.over_a(t)})['ancre']
        R_a, t_a = self.anchor_rt(av)
        wv = self.victim(t)
        for pt_name, (where, wch) in self.attach.items():  # point de la victime collé à la gueule / une paume
            w = min(1.0, av.get(wch, 0.0))
            if w <= 1e-4:
                continue
            target = point(W, 'Head', MOUTH) if where == 'bouche' else point(W, 'Hand_' + where[-1], A.PALM[where[-1]])
            t_a = t_a * (1 - w) + attach_t(R_a, vpoint(wv, pt_name), target) * w
        if self.drag:                                       # traînée : cheville dans la main, tête au sol
            pt, s, wch, ych = self.drag
            w = min(1.0, av.get(wch, 0.0))
            if w > 1e-4:
                palm = point(W, 'Hand_' + s, A.PALM[s])
                if ych and ych in av:
                    psi = av[ych]
                else:
                    d = palm - HRP_C
                    psi = math.degrees(math.atan2(d[0], d[2]))
                R_d, t_d = drag_solve(palm, wv, pt, psi)
                R_a = A.slerp_R(R_a, R_d, w)
                t_a = t_a * (1 - w) + t_d * w
        low = victim_low(anchor_frame(R_a, t_a), wv)
        sol = min(1.0, av.get('sol', 0.0))
        if sol > 1e-4:
            t_a = t_a + np.array([0.0, -low * sol, 0.0])
            low *= (1 - sol)
        if low < -0.02:
            t_a = t_a + np.array([0.0, -low - 0.02, 0.0])
        P['VictimeAncre'] = (R_a, t_a)
        F = anchor_frame(R_a, t_a)
        for s, spec in self.ik.items():                     # paumes du monstre sur des points de la victime
            pt_name, wch = spec[0], spec[1]
            pole = spec[2] if len(spec) > 2 else (0.0, -1.0, 0.6)
            w = av.get(wch, 0.0)
            if w <= 1e-4:
                continue
            arm_to(P, W, s, (F @ np.append(vpoint(wv, pt_name), 1.0))[:3], w, pole)
            W = fk(P)
        return P


def K(t, **ch):
    """Clé : K(0.5, armR=dict(sp=60), jaw=dict(a=20))."""
    return (t, ch)


def shake(t, t0, t1, freq, amp):
    """Secousse sinusoïdale entre t0 et t1 (enveloppe douce)."""
    if t < t0 or t > t1:
        return 0.0
    e = smooth01((t - t0) / 0.08) * smooth01((t1 - t) / 0.12)
    return amp * e * math.sin(TAU * freq * (t - t0))


def jit(t, seed, freq=7.0):
    """Bruit lisse (somme de sinus) pour la lutte."""
    r = np.random.default_rng(seed)
    ph = r.uniform(0, TAU, 3)
    return float(np.sin(TAU * freq * t + ph[0]) * 0.6 + np.sin(TAU * freq * 1.7 * t + ph[1]) * 0.3
                 + np.sin(TAU * freq * 2.9 * t + ph[2]) * 0.1)


def env(t, t0, t1, fade=0.15):
    """1 entre t0 et t1, fondu doux aux bords."""
    return smooth01((t - t0) / fade) * (1 - smooth01((t - t1) / fade))


M_REPOS = dict(pel=dict(), spine=dict(), chest=dict(), upper=dict(), neck=dict(), head=dict(), jaw=dict(a=2),
               armR=dict(sp=0, el=3), armL=dict(sp=0, el=3), finR=dict(c=8, s=2), finL=dict(c=8, s=2),
               footR=dict(), footL=dict(), turn=dict(a=0))


def M(rot=0.0, **kw):
    """Canaux du monstre partant du repos (copie) ; rot : corps et pieds tournés de rot degrés autour de l'axe du
    HumanoidRootPart (les clés d'un clip doivent toutes donner l'angle des pieds)."""
    out = {k: dict(v) for k, v in M_REPOS.items()}
    out['turn'] = dict(a=rot)
    out['footR'] = dict(a=rot)
    out['footL'] = dict(a=rot)
    for k, v in kw.items():
        out[k] = dict(out.get(k, {}), **v)
    return out


def V(base, **kw):
    """Pose de la victime : copie de base avec des canaux remplacés."""
    out = {k: dict(v) for k, v in base.items()}
    for k, v in kw.items():
        out[k] = dict(out.get(k, {}), **v)
    return out


# --- poses de la victime réutilisées ---------------------------------------------------------------------
V_DEBOUT = dict(root=dict(), head=dict(), armR=dict(pitch=4, abd=4, elbow=10), armL=dict(pitch=4, abd=4, elbow=10),
                legR=dict(), legL=dict())
V_PEUR = dict(root=dict(lean=-6), head=dict(pitch=6), armR=dict(pitch=105, abd=12, twist=10, elbow=95),
              armL=dict(pitch=100, abd=10, twist=10, elbow=100), legR=dict(pitch=8, knee=14), legL=dict(pitch=-6, knee=8))
V_RECUL = dict(root=dict(lean=-14), head=dict(pitch=18), armR=dict(pitch=70, abd=35, elbow=40),
               armL=dict(pitch=60, abd=40, elbow=30), legR=dict(pitch=20, knee=30), legL=dict(pitch=-10, knee=10))
V_SOULEVEE = dict(root=dict(lean=-8), head=dict(pitch=10, roll=-10), armR=dict(pitch=80, abd=20, elbow=60),
                  armL=dict(pitch=85, abd=20, elbow=55), legR=dict(pitch=25, knee=40), legL=dict(pitch=-5, knee=55))
V_MOU = dict(root=dict(lean=8), head=dict(pitch=-35, roll=25, yaw=10), armR=dict(pitch=8, abd=6, elbow=14),
             armL=dict(pitch=4, abd=8, elbow=10), legR=dict(pitch=6, knee=12), legL=dict(pitch=2, knee=18))
V_MORT_DOS = dict(root=dict(), head=dict(pitch=-12, yaw=40), armR=dict(pitch=3, abd=70, twist=90, elbow=30),
                  armL=dict(pitch=2, abd=40, twist=-90, elbow=55), legR=dict(pitch=3, abd=10, knee=8),
                  legL=dict(pitch=22, abd=4, knee=42))
V_MORT_COTE = dict(root=dict(lean=25), head=dict(pitch=-25, roll=15), armR=dict(pitch=45, abd=-10, elbow=100),
                   armL=dict(pitch=60, abd=5, elbow=90), legR=dict(pitch=55, knee=85), legL=dict(pitch=40, knee=70))
V_SOL_LUTTE = dict(root=dict(), head=dict(pitch=-25), armR=dict(pitch=100, abd=20, elbow=50),
                   armL=dict(pitch=85, abd=25, elbow=70), legR=dict(pitch=10, knee=20), legL=dict(pitch=40, knee=70))
V_TOMBE = dict(root=dict(lean=-25), head=dict(pitch=30), armR=dict(pitch=120, abd=50, elbow=30),
               armL=dict(pitch=130, abd=40, elbow=20), legR=dict(pitch=20, knee=30), legL=dict(pitch=5, knee=10))


def lutte(t, seed, t0, t1, amp=1.0, freq=5.0, parts=('armR', 'armL', 'legR', 'legL')):
    """Agitation de la victime (bras et jambes) entre t0 et t1."""
    e = env(t, t0, t1, 0.2) * amp
    if e <= 0:
        return {}
    out = {}
    for i, p in enumerate(parts):
        out[p] = {'pitch': 22 * e * jit(t, seed + 10 * i, freq),
                  ('knee' if p.startswith('leg') else 'elbow'): 25 * e * jit(t, seed + 10 * i + 1, freq)}
    return out


# =========================================================================================================
# 1. Morsure au cou : le monstre saisit la victime par les épaules, la soulève et la plaque contre lui, mord le cou ;
#    coupe noire, éclaboussures ; il secoue la tête, puis laisse tomber le corps
MORSURE_COU = Kill(
    'k_cou', 'Monstre_MorsureCou', 'Morsure au cou', 3.6,
    monster=[
        K(0.0, **M(pel=dict(ty=-0.3), jaw=dict(a=4))),
        K(0.3, **M(pel=dict(ty=-0.9, z=-1.1, p=-6), spine=dict(p=-8), chest=dict(p=-8), upper=dict(p=-4),
                   neck=dict(p=4), head=dict(p=6), jaw=dict(a=16), finR=dict(c=-5, s=12), finL=dict(c=-5, s=12),
                   footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(0.75, **M(pel=dict(ty=-0.45, z=-0.7, p=-2), spine=dict(p=-3), chest=dict(p=-2), upper=dict(p=3),
                    neck=dict(p=-4), head=dict(p=-2), jaw=dict(a=24), finR=dict(c=45), finL=dict(c=45),
                    footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(0.95, **M(pel=dict(ty=-0.45, z=-0.7, p=-3), spine=dict(p=-5), chest=dict(p=-4), upper=dict(p=-1),
                    neck=dict(p=-10, y=-8), head=dict(p=-10, y=-10, r=8), jaw=dict(a=32), finR=dict(c=50), finL=dict(c=50),
                    footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(1.05, **M(pel=dict(ty=-0.5, z=-0.75, p=-3), spine=dict(p=-6), chest=dict(p=-5), upper=dict(p=-2),
                    neck=dict(p=-12, y=-8), head=dict(p=-12, y=-10, r=8), jaw=dict(a=5), finR=dict(c=55), finL=dict(c=55),
                    footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(1.9, **M(pel=dict(ty=-0.5, z=-0.75, p=-3), spine=dict(p=-6), chest=dict(p=-5), upper=dict(p=-2),
                   neck=dict(p=-11, y=-6), head=dict(p=-11, y=-8, r=6), jaw=dict(a=7), finR=dict(c=55), finL=dict(c=55),
                   footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(2.35, **M(pel=dict(ty=-0.9, z=-0.6, p=-6), spine=dict(p=-9), chest=dict(p=-7), upper=dict(p=-3),
                    neck=dict(p=-6), head=dict(p=-6), jaw=dict(a=12), finR=dict(c=20, s=6), finL=dict(c=20, s=6),
                    footR=dict(z=-1.3), footL=dict(z=0.2))),
        K(3.6, **M(pel=dict(ty=-0.25, z=-0.2), neck=dict(p=-8, y=6), head=dict(p=-10, y=8), jaw=dict(a=9),
                   footR=dict(z=-0.7), footL=dict(z=0.1))),
    ],
    victim=[
        K(0.0, **V_PEUR), K(0.4, **V_SOULEVEE), K(0.95, **V_SOULEVEE),
        K(1.1, root=dict(lean=-14), head=dict(pitch=24, roll=-35), armR=dict(pitch=70, abd=40, elbow=30),
          armL=dict(pitch=60, abd=45, elbow=25), legR=dict(pitch=30, knee=60), legL=dict(pitch=10, knee=30)),
        K(1.9, **V_MOU), K(2.4, **V_MOU), K(2.85, **V_MORT_DOS), K(3.6, **V_MORT_DOS),
    ],
    anchor=[
        K(0.0, ancre=dict(wb=0.0, wiR=0.0, wiL=0.0)),
        K(0.25, ancre=dict(z=0.3, wb=0.0, wiR=0.0, wiL=0.0)),
        K(0.42, ancre=dict(ty=0.3, z=0.9, wb=0.0, wiR=1.0, wiL=1.0)),
        K(0.8, ancre=dict(ty=3.5, z=1.6, wb=0.7, wiR=1.0, wiL=1.0)),
        K(0.95, ancre=dict(ty=4.0, z=1.8, wb=1.0, wiR=1.0, wiL=1.0)),
        K(2.3, ancre=dict(ty=4.0, z=1.8, wb=1.0, wiR=1.0, wiL=1.0, snap=1)),
        K(2.42, ancre=dict(ty=3.2, z=1.8, wb=0.0, wiR=0.0, wiL=0.0)),
        K(2.75, ancre=dict(ty=0.0, z=0.2, p=-80, sol=1.0)),
        K(2.95, ancre=dict(ty=0.0, z=-0.6, p=-90, sol=1.0)),
        K(3.6, ancre=dict(ty=0.0, z=-0.6, p=-90, sol=1.0)),
    ],
    attach={'cou': ('bouche', 'wb')},
    ik={'R': ('epauleG', 'wiR', (0.6, -1.0, 0.3)), 'L': ('epauleD', 'wiL', (-0.6, -1.0, 0.3))},
    over_m=lambda t: {'neck': {'y': shake(t, 1.1, 1.9, 3.2, 6.0)}, 'head': {'y': shake(t, 1.1, 1.9, 3.2, 5.0),
                                                                             'r': shake(t, 1.1, 1.9, 3.2, 4.0)},
                      'upper': {'y': shake(t, 1.1, 1.9, 3.2, 3.0)}},
    over_v=lambda t: add(lutte(t, 1, 0.35, 1.15, 1.0, 5.5), lutte(t, 50, 1.1, 1.6, 0.5, 9.0, ('legR', 'legL'))),
    markers=[(0.0, 'Camera', 'victime'), (0.2, 'Son', 'grognement'), (0.42, 'Son', 'saisie'), (1.05, 'Morsure', 'cou'),
             (1.05, 'Coupure', '0.4'), (1.06, 'Son', 'morsure'), (1.08, 'Eclaboussure', 'cou'), (1.45, 'Camera', 'face'),
             (1.45, 'Ecran', 'sang'), (1.5, 'Eclaboussure', 'cou'), (1.75, 'Son', 'dechirure'), (1.8, 'Eclaboussure', 'cou'),
             (2.42, 'Lacher', ''), (2.8, 'Son', 'chute_corps'), (2.82, 'Flaque', 'cou'), (3.0, 'Camera', 'cadavre')])


# --- pas et demi-tours -------------------------------------------------------------------------------------

def bump(x):
    return math.sin(math.pi * x) if 0.0 < x < 1.0 else 0.0


def pulse(t, tc, rise=0.1, fall=0.14):
    """0 -> 1 (en tc) -> 0, montée en rise, descente en fall."""
    if t <= tc - rise or t >= tc + fall:
        return 0.0
    return smooth01((t - tc + rise) / rise) if t < tc else 1.0 - smooth01((t - tc) / fall)


def foot_step(t, t0, t1, p0, p1, lift=0.5):
    """Un pied qui passe de p0 à p1 (dict a, x, z, p...) entre t0 et t1, soulevé de lift au milieu."""
    u = smooth01((t - t0) / (t1 - t0))
    out = {k: p0.get(k, 0.0) + (p1.get(k, 0.0) - p0.get(k, 0.0)) * u for k in set(p0) | set(p1)}
    out['ty'] = out.get('ty', 0.0) + lift * bump((t - t0) / (t1 - t0))
    return out


def turning(t0, t1, a0, a1, lift=0.6, oR=((0, 0), (0, 0)), oL=((0, 0), (0, 0))):
    """Demi-tour en quatre pas (droit, gauche, droit, gauche) : pieds en arcs autour de l'axe du HumanoidRootPart ;
    oR / oL : décalages (x, z) du pied (repère du corps) au début et à la fin."""
    def fn(t):
        u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        sR = 0.5 * (smooth01(u / 0.3) + smooth01((u - 0.5) / 0.3))
        sL = 0.5 * (smooth01((u - 0.25) / 0.3) + smooth01((u - 0.75) / 0.25))
        hR = lift * (bump(u / 0.3) + bump((u - 0.5) / 0.3))
        hL = lift * (bump((u - 0.25) / 0.3) + bump((u - 0.75) / 0.25))

        def f(s, h, o):
            return dict(a=a0 + (a1 - a0) * s, x=o[0][0] + (o[1][0] - o[0][0]) * s, z=o[0][1] + (o[1][1] - o[0][1]) * s,
                        ty=h, p=-12.0 * h / max(lift, 1e-6))
        return {'turn': {'a': a0 + (a1 - a0) * smooth01((u - 0.05) / 0.9)}, 'footR': f(sR, hR, oR), 'footL': f(sL, hL, oL)}
    return fn


def rot_pt(p, deg):
    """Point (repère modèle) tourné autour de l'axe vertical du HumanoidRootPart."""
    return HRP_C + Ry(deg) @ (np.asarray(p, float) - HRP_C)


def ikd(p, w=1.0, pole=(0.0, -1.0, 0.6), m=0.0):
    """Canaux d'IK de paume vers le point p (repère modèle ; décalage depuis la gueule si m = 1)."""
    return dict(w=w, x=float(p[0]), y=float(p[1]), z=float(p[2]), px=pole[0], py=pole[1], pz=pole[2], m=m)


# --- traîner : marche du monstre penché, la victime tenue par la cheville, tête au sol ---------------------
DRAG = C.Gait(T=1.5, v=4.2, duty=0.64, lift=0.7, drop=1.5, bob=0.08, lean=-20.0, arm_amp=8.0, elbow=10.0, sway=0.1,
              yaw=5.0, head_lift=10.0)
DRAG_VITE = C.Gait(T=1.0, v=8.0, duty=0.52, lift=1.0, drop=1.6, bob=0.14, lean=-26.0, arm_amp=16.0, elbow=20.0,
                   sway=0.08, yaw=7.0, head_lift=16.0, toe_down=-25.0, heel_kick=0.5)
DRAG_TGT = np.array([1.6, 2.7, 1.2])          # paume droite, derrière le corps (repère du corps non tourné)
DRAG_POLE = (0.3, 0.0, 1.0)
DRAG_TGT_ROT = rot_pt(DRAG_TGT, 180.0)


class DragKill(Kill):
    """Boucle de traînée : marche (gait) avec le bassin tourné de 180 degrés (le corps regarde vers +Z du
    HumanoidRootPart, qui avance donc à reculons, AutoRotate coupé), main droite derrière, cheville de la victime dans
    la paume, tête de la victime au sol vers -Z."""

    def __init__(self, key, name, label, gait, ncyc, victim, pt='chevilleG', over_v=None, markers=(), tgt=DRAG_TGT):
        self.gait, self.pt, self.tgt = gait, pt, np.asarray(tgt, float)
        super().__init__(key, name, label, gait.T * ncyc, monster=[K(0, **M())], victim=victim,
                         anchor=[K(0, ancre=dict())], loop=True, over_v=over_v, markers=markers)

    def __call__(self, t):
        G = self.gait
        P = G.pose(t)
        ph = (t / G.T) % 1.0
        W = fk(P)
        tgt = self.tgt + np.array([0.0, 0.12 * math.sin(TAU * 2 * ph), 0.15 * math.cos(TAU * ph)])
        arm_to(P, W, 'R', tgt, 1.0, DRAG_POLE)
        P['Hand_R'] = (euler(-25, 0, 0), np.zeros(3))
        P.update(A.finger_curl('R', 62, 0))
        W = fk(P)
        wv = self.victim(t)
        R_a, t_a = drag_solve(point(W, 'Hand_R', A.PALM['R']), wv, self.pt, 0.0)
        turn_pose(P, 180.0)
        P['VictimeAncre'] = turn_anchor(R_a, t_a, 180.0)
        return P


CROUCH_DRAG = dict(pel=dict(ty=-1.5, p=-5), spine=dict(p=-6), chest=dict(p=-6), upper=dict(p=-3), neck=dict(p=9),
                   head=dict(p=6))
V_TRAINE_MORT = dict(root=dict(), head=dict(pitch=20, yaw=25), armR=dict(pitch=165, abd=30, elbow=25),
                     armL=dict(pitch=170, abd=20, elbow=30), legR=dict(pitch=25, abd=15, knee=35), legL=dict(pitch=70, knee=4))
V_TRAINE_VIVE = dict(root=dict(tilt=5), head=dict(pitch=-28), armR=dict(pitch=150, abd=35, elbow=40),
                     armL=dict(pitch=160, abd=25, elbow=55), legR=dict(pitch=35, knee=60), legL=dict(pitch=70, knee=4))


def two_pass(build):
    """build(None) -> Kill provisoire ; build(k) -> Kill final (k : le provisoire, pour lire des positions)."""
    return build(build(None))


def saisie_cheville(key, name, label, length, vive, markers):
    """Renverse la victime (sur le dos, pieds vers le monstre), s'accroupit, saisit sa cheville gauche de la main
    droite, se relève et fait demi-tour (180 degrés) en la tenant : fin = pose de départ de la traînée."""
    t_hit, t_down, t_grab, t0 = 0.42, 0.85, 1.45, 1.6
    t1 = length - 0.15
    crouch = dict(pel=dict(ty=-2.7, z=-0.9, p=-10), spine=dict(p=-16), chest=dict(p=-14), upper=dict(p=-8),
                  neck=dict(p=6), head=dict(p=2), jaw=dict(a=12))
    vpose = V_TRAINE_VIVE if vive else V_TRAINE_MORT

    def build(k0):
        grab = point(fk(k0(t_grab)), 'Hand_R', A.PALM['R']) if k0 else DRAG_TGT_ROT
        gpole = (0.5, 0.0, 1.0)
        monster = [
            K(0.0, **M(pel=dict(ty=-0.3), ikR=ikd(grab, 0.0, gpole))),
            K(0.25, **M(pel=dict(ty=-0.6, z=-0.3, y=-12), spine=dict(p=-4, y=-8), chest=dict(y=-8), jaw=dict(a=18),
                        armR=dict(sp=-35, sr=40, el=50), finR=dict(c=-10, s=14))),
            K(t_hit, **M(pel=dict(ty=-0.8, z=-0.9, y=14), spine=dict(p=-8, y=10), chest=dict(p=-6, y=10),
                         armR=dict(sp=48, sr=-22, el=14), finR=dict(c=20, s=8), jaw=dict(a=24))),
            K(t_down, **M(pel=dict(ty=-1.6, z=-0.7, p=-6), spine=dict(p=-10), chest=dict(p=-8), upper=dict(p=-4),
                          jaw=dict(a=14), armR=dict(sp=30, el=30), finR=dict(c=20, s=6))),
            K(t_grab, **M(**crouch, armR=dict(sp=60, el=20), finR=dict(c=55), ikR=ikd(grab, 0.0, gpole))),
            K(t_grab + 0.12, **M(**crouch, armR=dict(sp=60, el=20), finR=dict(c=62), ikR=ikd(grab, 1.0, gpole))),
            K(t0, **M(**crouch, finR=dict(c=62), ikR=ikd(grab, 1.0, gpole))),
            K(t0 + 0.35, **M(**CROUCH_DRAG, finR=dict(c=62), jaw=dict(a=8))),
            K(t1, **M(**CROUCH_DRAG, finR=dict(c=62), jaw=dict(a=6), ikR=ikd(DRAG_TGT_ROT, 1.0, DRAG_POLE))),
            K(length, **M(**CROUCH_DRAG, finR=dict(c=62), jaw=dict(a=6), ikR=ikd(DRAG_TGT_ROT, 1.0, DRAG_POLE))),
        ]
        victim = [K(0.0, **V_PEUR), K(t_hit, **V_RECUL), K(t_down - 0.1, **V_TOMBE), K(t_down + 0.15, **V_SOL_LUTTE),
                  K(t_grab - 0.25, **V(V_SOL_LUTTE, legL=dict(pitch=10, knee=12))),
                  K(t_grab + 0.15, **V(V_SOL_LUTTE, legL=dict(pitch=8, knee=8))), K(t1, **vpose), K(length, **vpose)]
        anchor = [K(0.0, ancre=dict(hd=180.0)),
                  K(t_hit, ancre=dict(z=-0.2)),
                  K(t_down - 0.1, ancre=dict(z=-0.6, p=-55, sol=0.6)),
                  K(t_down + 0.1, ancre=dict(z=-0.9, p=-90, sol=1.0)),
                  K(t_grab - 0.35, ancre=dict(z=-0.9, p=-90, sol=1.0)),
                  K(t_grab, ancre=dict(z=-0.9, p=-90, sol=1.0, wiR=1.0)),
                  K(t_grab + 0.12, ancre=dict(z=-0.9, p=-90, sol=1.0, wd=1.0)),
                  K(length, ancre=dict(z=-0.9, p=-90, wd=1.0))]
        feet_turn = turning(t0, t1, 0.0, 180.0, 0.7, oR=((0.0, -1.2), (0.0, 0.0)), oL=((0.0, 0.3), (0.0, 0.0)))

        def feet(t):
            if t < t0:
                R = foot_step(t, 0.25, t_hit + 0.05, dict(), dict(z=-0.7), 0.4)
                if t > t_down:
                    R = foot_step(t, t_down, t_down + 0.35, dict(z=-0.7), dict(z=-1.2), 0.4)
                L = foot_step(t, t_down + 0.1, t_down + 0.4, dict(), dict(z=0.3), 0.3)
                return {'turn': {'a': 0.0}, 'footR': R, 'footL': L}
            return feet_turn(t)

        if vive:
            over_v = lambda t: add(lutte(t, 31, t_down, length + 1, 1.0, 4.0, ('armR', 'armL', 'legR')),
                                   {'head': {'yaw': 15 * jit(t, 39, 2.0) * env(t, t_down, length + 1)}})
        else:
            over_v = lambda t: lutte(t, 33, t_down, t_grab, 0.5, 3.0, ('armR', 'armL'))
        return Kill(key, name, label, length, monster, victim, anchor, feet=feet,
                    ik={'R': ('chevilleG', 'wiR', (0.5, 0.0, 1.0))}, drag=('chevilleG', 'R', 'wd', 'hd'),
                    over_v=over_v, markers=markers)
    return two_pass(build)


# =========================================================================================================
# 2. Morsure répétée : prise d'une main par l'épaule, quatre morsures rapides (la victime est tirée vers la gueule à
#    chaque fois), puis le corps est jeté sur le côté
_REP_BITES = (0.85, 1.2, 1.55, 1.9)


def _rep_build(k0):
    if k0:
        P = k0(_REP_BITES[0])
        _, tr = P['VictimeAncre']
        hold = dict(x=float(tr[0]), ty=float(tr[1]) - 0.15, z=float(tr[2]) - 0.35)
    else:
        hold = dict(ty=2.4, z=1.3)
    held = M(pel=dict(ty=-0.5, z=-0.6, p=-3, y=8), spine=dict(p=-6, y=4), chest=dict(p=-6, y=4), upper=dict(p=-2, y=4),
             neck=dict(p=-6), head=dict(p=-6), jaw=dict(a=10), finR=dict(c=50), footR=dict(z=-1.0))
    monster = [
        K(0.0, **M(pel=dict(ty=-0.3))),
        K(0.3, **M(pel=dict(ty=-0.8, z=-0.9, p=-5, y=6), spine=dict(p=-6), chest=dict(p=-6), neck=dict(p=2), jaw=dict(a=16),
                   finR=dict(c=-5, s=10), footR=dict(z=-1.0))),
        K(0.62, **held), K(2.05, **held),
        K(2.3, **M(pel=dict(ty=-0.4, z=-0.4, p=-2, y=-16), spine=dict(p=-4, y=-10), chest=dict(p=-4, y=-8),
                   upper=dict(y=-6), neck=dict(p=-4), head=dict(p=-4), jaw=dict(a=14), armR=dict(sp=40, sr=60, el=20),
                   finR=dict(c=-10, s=14), footR=dict(z=-1.0))),
        K(3.4, **M(pel=dict(ty=-0.2), neck=dict(p=-5, y=-12), head=dict(p=-6, y=-14), jaw=dict(a=6), footR=dict(z=-0.4))),
    ]
    victim = [K(0.0, **V_PEUR), K(0.45, **V_SOULEVEE), K(0.9, **V_SOULEVEE),
              K(1.6, root=dict(lean=-10), head=dict(pitch=20, roll=-30), armR=dict(pitch=50, abd=40, elbow=40),
                armL=dict(pitch=40, abd=45, elbow=30), legR=dict(pitch=10, knee=30), legL=dict(pitch=-5, knee=20)),
              K(2.05, **V_MOU), K(2.4, **V(V_TOMBE, root=dict(lean=10))), K(2.75, **V_MORT_COTE), K(3.4, **V_MORT_COTE)]
    anchor = [K(0.0, ancre=dict()),
              K(0.18, ancre=dict(z=0.2)),
              K(0.35, ancre=dict(ty=0.3, z=0.8, wiR=1.0)),
              K(0.62, ancre=dict(wiR=1.0, **hold)),
              K(2.05, ancre=dict(wiR=1.0, **hold)),
              K(2.28, ancre=dict(wiR=1.0, x=hold.get('x', 0.0) + 1.0, ty=hold['ty'] + 0.5, z=hold['z'] - 0.2, r=-25)),
              K(2.36, ancre=dict(x=hold.get('x', 0.0) + 1.8, ty=hold['ty'] + 0.4, z=hold['z'] - 0.4, r=-50)),
              K(2.68, ancre=dict(x=4.2, ty=-1.0, z=0.4, r=-90, y=-25, sol=1.0)),
              K(3.4, ancre=dict(x=4.2, ty=-1.0, z=0.4, r=-90, y=-25, sol=1.0))]

    def over_m(t):
        jaw = sum(26 * pulse(t, tb - 0.1, 0.12, 0.06) - 8 * pulse(t, tb, 0.05, 0.1) for tb in _REP_BITES)
        th = sum(pulse(t, tb, 0.12, 0.16) for tb in _REP_BITES)
        return {'jaw': {'a': jaw}, 'head': {'p': -8 * th}, 'neck': {'p': -5 * th},
                'upper': {'y': shake(t, 0.7, 2.1, 5.0, 2.0)}}

    def over_a(t):
        return {'wb': sum(pulse(t, tb, 0.12, 0.16) for tb in _REP_BITES)}

    def over_v(t):
        jolt = sum(pulse(t, tb, 0.04, 0.2) for tb in _REP_BITES)
        out = {'root': {'tilt': 10 * jolt, 'lean': -6 * jolt}, 'head': {'roll': -14 * jolt}}
        return add(out, lutte(t, 7, 0.3, 1.7, 1.0, 6.0))

    return Kill('k_repetee', 'Monstre_MorsureRepetee', 'Morsure répétée', 3.4, monster, victim, anchor,
                attach={'cou': ('bouche', 'wb')}, ik={'R': ('epauleG', 'wiR', (0.8, -1.0, 0.2))},
                over_m=over_m, over_v=over_v, over_a=over_a,
                markers=[(0.0, 'Camera', 'epaule_victime'), (0.25, 'Son', 'grognement'), (0.35, 'Son', 'saisie')]
                + [m for tb in _REP_BITES for m in ((tb, 'Morsure', 'cou'), (tb + 0.01, 'Son', 'morsure'),
                                                    (tb + 0.02, 'Eclaboussure', 'cou'), (tb + 0.02, 'Tremble', '0.6'))]
                + [(1.2, 'Ecran', 'sang'), (2.3, 'Lacher', ''), (2.3, 'Camera', 'suivre'), (2.68, 'Son', 'chute_corps'),
                   (2.7, 'Eclaboussure', 'sol'), (2.72, 'Flaque', 'cou'), (3.0, 'Camera', 'cadavre')])


MORSURE_REPETEE = two_pass(_rep_build)


# =========================================================================================================
# 3. Dévoration : renverse la victime, la saisit par la cheville, la traîne dans l'obscurité (boucle de traînée),
#    se retourne, s'agenouille, la soulève jusqu'à sa gueule et la dévore (boucle) ; caméra à distance
DEV_SAISIE = saisie_cheville('k_dev_saisie', 'Monstre_DevorationSaisie', 'Dévoration (saisie)', 2.9, False,
                             [(0.0, 'Camera', 'distance'), (0.2, 'Son', 'grognement'), (0.42, 'Coup', 'renverse'),
                              (0.45, 'Son', 'impact'), (0.8, 'Son', 'chute_corps'), (1.5, 'Son', 'saisie')])
DEV_TRAINER = DragKill('k_dev_trainer', 'Monstre_DevorationTrainer', 'Dévoration (traîner)', DRAG, 2,
                       [K(0, **V_TRAINE_MORT), K(DRAG.T * 2, **V_TRAINE_MORT)],
                       over_v=lambda t: {'head': {'yaw': 10 * math.sin(TAU * t / DRAG.T)},
                                         'armR': {'abd': 6 * math.sin(TAU * t / DRAG.T + 1)},
                                         'armL': {'abd': 6 * math.sin(TAU * t / DRAG.T + 2)}},
                       markers=[(0.0, 'Son', 'trainer'), (0.0, 'Trace', 'trainee'), (DRAG.T, 'Son', 'trainer')])

KNEEL = dict(pel=dict(ty=-3.25, z=-0.2, p=-8), spine=dict(p=-8), chest=dict(p=-6), upper=dict(p=-4))
KNEEL_FEET = dict(R=dict(x=0.25, z=2.6, ty=-0.45, p=-55), L=dict(x=-0.25, z=2.7, ty=-0.45, p=-55))


def _dev_eat_target():
    """Où se trouve la victime à la fin de la traînée (après le demi-tour du corps) : ancre de DEV_TRAINER(0)."""
    R, tr = DEV_TRAINER(0.0)['VictimeAncre']
    p, y, r = euler_of(R)
    return dict(p=p, y=y, r=r, x=float(tr[0]), ty=float(tr[1]), z=float(tr[2]))


DEV_FIN_TRAINE = _dev_eat_target()
V_ASSISE_MOLLE = dict(root=dict(lean=6), head=dict(pitch=-38, roll=22), armR=dict(pitch=12, abd=18, elbow=22),
                      armL=dict(pitch=6, abd=14, elbow=30), legR=dict(pitch=14, abd=6, knee=28), legL=dict(pitch=6, knee=40))


def _dev_tourner_build(k0):
    a0 = DEV_FIN_TRAINE
    if k0:
        P = k0(1.85)
        _, tr = P['VictimeAncre']
        lift = dict(x=float(tr[0]), ty=float(tr[1]), z=float(tr[2]))
    else:
        lift = dict(x=a0['x'], ty=1.0, z=a0['z'] + 1.0)
    monster = [
        K(0.0, **M(180.0, **CROUCH_DRAG, finR=dict(c=62), ikR=ikd(DRAG_TGT_ROT, 1.0, DRAG_POLE))),
        K(0.3, **M(180.0, **CROUCH_DRAG, finR=dict(c=62), ikR=ikd(DRAG_TGT_ROT, 1.0, DRAG_POLE))),
        K(0.55, **M(180.0, **CROUCH_DRAG, finR=dict(c=10, s=6), ikR=ikd(DRAG_TGT_ROT + np.array([0, 0.8, 0.3]), 0.0, DRAG_POLE))),
        K(1.25, **M(0.0, pel=dict(ty=-2.0, z=-0.3, p=-8), spine=dict(p=-8), chest=dict(p=-8), upper=dict(p=-4),
                    neck=dict(p=-4), head=dict(p=-4), jaw=dict(a=16), finR=dict(c=-5, s=10), finL=dict(c=-5, s=10))),
        K(1.85, **M(0.0, **KNEEL, neck=dict(p=-14, y=6), head=dict(p=-10, y=8), jaw=dict(a=26), finR=dict(c=55), finL=dict(c=55))),
        K(2.2, **M(0.0, **KNEEL, neck=dict(p=-16, y=6), head=dict(p=-12, y=8), jaw=dict(a=6), finR=dict(c=55), finL=dict(c=55))),
    ]
    victim = [K(0.0, **V_TRAINE_MORT), K(0.3, **V_TRAINE_MORT), K(0.75, **V_MORT_DOS), K(1.25, **V_MORT_DOS),
              K(1.85, **V_ASSISE_MOLLE), K(2.2, **V_ASSISE_MOLLE)]
    anchor = [K(0.0, ancre=dict(wd=1.0, hd=180.0)),
              K(0.3, ancre=dict(wd=1.0, snap=1)),
              K(0.55, ancre=dict(wd=0.0, sol=1.0, p=-90, y=a0['y'], x=a0['x'], z=a0['z'])),
              K(1.25, ancre=dict(sol=1.0, p=-90, y=a0['y'], x=a0['x'], z=a0['z'], wiR=0.0, wiL=0.0)),
              K(1.6, ancre=dict(sol=0.5, p=-60, y=a0['y'], x=a0['x'], z=a0['z'] + 0.5, wiR=1.0, wiL=1.0)),
              K(1.85, ancre=dict(p=-15, y=a0['y'], wiR=1.0, wiL=1.0, wb=1.0, **lift)),
              K(2.2, ancre=dict(p=-15, y=a0['y'], wiR=1.0, wiL=1.0, wb=1.0, **lift))]
    tf = turning(0.55, 1.35, 180.0, 0.0, 0.7)

    def feet(t):
        if t < 1.4:
            return tf(t)
        out = {'turn': {'a': 0.0}}
        for s in SIDES:
            out['foot' + s] = foot_step(t, 1.4, 1.8, dict(), KNEEL_FEET[s], 0.2)
        return out

    return Kill('k_dev_tourner', 'Monstre_DevorationTourner', 'Dévoration (se retourner)', 2.2, monster, victim, anchor,
                feet=feet, drag=('chevilleG', 'R', 'wd', 'hd'), attach={'cou': ('bouche', 'wb')},
                ik={'R': ('epauleG', 'wiR', (0.8, -1.0, 0.0)), 'L': ('epauleD', 'wiL', (-0.8, -1.0, 0.0))},
                markers=[(0.45, 'Son', 'chute_corps'), (1.0, 'Son', 'grognement'), (1.85, 'Son', 'morsure'),
                         (1.9, 'Eclaboussure', 'cou')])


DEV_TOURNER = two_pass(_dev_tourner_build)


def _dev_manger():
    P = DEV_TOURNER(2.2)
    R, tr = P['VictimeAncre']
    p, y, r = euler_of(R)
    held = dict(p=p, y=y, r=r, x=float(tr[0]), ty=float(tr[1]), z=float(tr[2]))
    base = M(0.0, **KNEEL, neck=dict(p=-16, y=6), head=dict(p=-12, y=8), jaw=dict(a=6), finR=dict(c=55), finL=dict(c=55))
    for s in SIDES:
        base['foot' + s] = dict(KNEEL_FEET[s], a=0.0)

    def over_m(t):
        ph = t / 1.2
        tear = max(0.0, math.sin(TAU * ph)) ** 2               # arrache : tête en arrière
        chew = max(0.0, math.sin(TAU * t / 0.42)) ** 2
        return {'neck': {'p': 7 * tear, 'y': 5 * math.sin(TAU * t / 2.4)}, 'head': {'p': 9 * tear, 'r': 6 * tear},
                'jaw': {'a': 12 * chew + 8 * pulse(t % 1.2, 0.15, 0.1, 0.2)}, 'upper': {'p': 3 * tear}}

    return Kill('k_dev_manger', 'Monstre_DevorationManger', 'Dévoration (manger)', 2.4, [K(0, **base), K(2.4, **base)],
                [K(0, **V_ASSISE_MOLLE), K(2.4, **V_ASSISE_MOLLE)],
                [K(0, ancre=dict(wiR=1.0, wiL=1.0, wb=0.92, **held)), K(2.4, ancre=dict(wiR=1.0, wiL=1.0, wb=0.92, **held))],
                loop=True, attach={'cou': ('bouche', 'wb')},
                ik={'R': ('epauleG', 'wiR', (0.8, -1.0, 0.0)), 'L': ('epauleD', 'wiL', (-0.8, -1.0, 0.0))},
                over_m=over_m, over_v=lambda t: {'head': {'roll': 8 * max(0.0, math.sin(TAU * t / 1.2)) ** 2},
                                                 'armR': {'pitch': 6 * math.sin(TAU * t / 1.2)},
                                                 'armL': {'pitch': 6 * math.sin(TAU * t / 1.2 + 0.5)}},
                markers=[(0.1, 'Son', 'mastication'), (0.3, 'Eclaboussure', 'cou'), (1.2, 'Son', 'dechirure'),
                         (1.3, 'Eclaboussure', 'cou'), (1.6, 'Son', 'mastication')])


DEV_MANGER = _dev_manger()


# =========================================================================================================
# 4. Attaque au ventre : élan, griffes plantées dans le ventre (la victime est soulevée), torsion, retrait ; la
#    victime se plie, tombe à genoux puis sur le côté (rien de l'intérieur du corps n'est montré)
V_PLIEE = dict(root=dict(lean=34), head=dict(pitch=-24), armR=dict(pitch=48, abd=-24, twist=20, elbow=105),
               armL=dict(pitch=52, abd=-26, twist=20, elbow=105), legR=dict(pitch=24, knee=34), legL=dict(pitch=14, knee=28))
V_GENOUX = dict(root=dict(lean=30), head=dict(pitch=-30), armR=dict(pitch=45, abd=-22, twist=20, elbow=110),
                armL=dict(pitch=50, abd=-24, twist=20, elbow=110), legR=dict(pitch=-4, knee=95), legL=dict(pitch=4, knee=100))
VPTS['ventre_in'] = ('Torso', (0.05, -0.4, -0.2))

ATTAQUE_VENTRE = Kill(
    'k_ventre', 'Monstre_AttaqueVentre', 'Attaque au ventre', 3.3,
    monster=[
        K(0.0, **M(pel=dict(ty=-0.3))),
        K(0.42, **M(pel=dict(ty=-0.8, z=0.3, y=-16), spine=dict(p=-4, y=-10), chest=dict(y=-10), upper=dict(y=-6),
                    armR=dict(sp=-40, sr=35, el=70, wp=-20), finR=dict(c=-10, s=12), jaw=dict(a=16), footL=dict(z=0.3))),
        K(0.56, **M(pel=dict(ty=-1.2, z=-1.3, y=12, p=-8), spine=dict(p=-8, y=10), chest=dict(p=-6, y=8), upper=dict(y=6),
                    armR=dict(sp=72, sr=-10, el=6, wp=10), finR=dict(c=-6, s=6), jaw=dict(a=28), footR=dict(z=-1.5),
                    footL=dict(z=0.3))),
        K(1.25, **M(pel=dict(ty=-1.1, z=-1.2, y=10, p=-7), spine=dict(p=-8, y=10), chest=dict(p=-6, y=8), upper=dict(y=6),
                    armR=dict(sp=78, sr=-10, el=12, wp=10), finR=dict(c=30, s=4), jaw=dict(a=20), footR=dict(z=-1.5),
                    footL=dict(z=0.3))),
        K(1.5, **M(pel=dict(ty=-0.8, z=-0.8, y=-4, p=-4), spine=dict(p=-5, y=-3), chest=dict(y=-3), armR=dict(sp=38, sr=8, el=28),
                   finR=dict(c=35, s=6), jaw=dict(a=14), footR=dict(z=-1.2), footL=dict(z=0.3))),
        K(2.0, **M(pel=dict(ty=-0.6, z=-0.5, p=-3), spine=dict(p=-4), armR=dict(sp=16, sr=6, el=22), finR=dict(c=30, s=4),
                   jaw=dict(a=10), neck=dict(p=-6), head=dict(p=-8), footR=dict(z=-1.0), footL=dict(z=0.3))),
        K(3.3, **M(pel=dict(ty=-0.3), neck=dict(p=-8), head=dict(p=-10), jaw=dict(a=6), armR=dict(sp=8, el=10),
                   finR=dict(c=20), footR=dict(z=-0.4))),
    ],
    victim=[K(0.0, **V_PEUR), K(0.5, **V_RECUL), K(0.62, **V(V_PLIEE, root=dict(lean=22))), K(1.25, **V_PLIEE),
            K(1.55, **V(V_PLIEE, root=dict(lean=40))), K(1.95, **V_GENOUX), K(2.6, **V_MORT_COTE), K(3.3, **V_MORT_COTE)],
    anchor=[K(0.0, ancre=dict()),
            K(0.45, ancre=dict(z=-0.1)),
            K(0.56, ancre=dict(z=0.5, wiR=0.6)),
            K(0.66, ancre=dict(ty=1.1, z=0.7, wiR=1.0)),
            K(1.25, ancre=dict(ty=1.0, z=0.7, wiR=1.0)),
            K(1.45, ancre=dict(ty=0.8, z=0.4, wiR=0.0)),
            K(1.95, ancre=dict(z=0.0, sol=1.0)),
            K(2.6, ancre=dict(z=-0.3, r=88, x=-0.3, sol=1.0)),
            K(3.3, ancre=dict(z=-0.3, r=88, x=-0.3, sol=1.0))],
    ik={'R': ('ventre_in', 'wiR', (0.9, -0.8, 0.4))},
    over_m=lambda t: {'upper': {'p': shake(t, 0.56, 0.9, 9.0, 2.5)}, 'armR': {'sr': shake(t, 0.65, 1.25, 6.0, 4.0)},
                      'head': {'r': shake(t, 0.6, 1.25, 4.0, 5.0)}},
    over_v=lambda t: {'root': {'lean': shake(t, 0.56, 1.25, 8.0, 5.0), 'tilt': shake(t, 0.6, 1.25, 5.0, 4.0)},
                      'head': {'pitch': shake(t, 0.56, 1.25, 7.0, 8.0)}},
    markers=[(0.0, 'Camera', 'face'), (0.35, 'Son', 'grognement'), (0.56, 'Impact', 'ventre'), (0.57, 'Son', 'impact'),
             (0.58, 'Tremble', '1.0'), (0.6, 'Eclaboussure', 'ventre'), (0.95, 'Eclaboussure', 'ventre'),
             (1.4, 'Retrait', 'ventre'), (1.42, 'Son', 'dechirure'), (1.45, 'Eclaboussure', 'ventre'),
             (1.95, 'Son', 'chute_corps'), (2.55, 'Son', 'chute_corps'), (2.6, 'Flaque', 'ventre'), (2.8, 'Camera', 'cadavre')])


# =========================================================================================================
# 5. Traînée : la créature renverse la victime, l'attrape par la cheville et la tire hors de la pièce (traînée de sang)
TRAINEE_SAISIE = saisie_cheville('k_trainee_saisie', 'Monstre_TraineeSaisie', 'Traînée (saisie)', 2.7, True,
                                 [(0.0, 'Camera', 'victime'), (0.25, 'Son', 'grognement'), (0.42, 'Coup', 'renverse'),
                                  (0.45, 'Son', 'impact'), (0.8, 'Son', 'chute_corps'), (1.45, 'Son', 'saisie'),
                                  (1.5, 'Son', 'cri_victime'), (1.6, 'Camera', 'trainee')])
TRAINEE_TRAINER = DragKill('k_trainee_trainer', 'Monstre_TraineeTrainer', 'Traînée (tirer)', DRAG_VITE, 2,
                           [K(0, **V_TRAINE_VIVE), K(DRAG_VITE.T * 2, **V_TRAINE_VIVE)],
                           over_v=lambda t: add(lutte(t, 41, -1.0, 10.0, 1.0, 3.0, ('armR', 'armL', 'legR')),
                                                {'head': {'pitch': 10 * jit(t, 47, 1.5), 'yaw': 20 * jit(t, 48, 1.0)}}),
                           markers=[(0.0, 'Son', 'trainer'), (0.0, 'Trace', 'trainee'), (DRAG_VITE.T, 'Son', 'trainer'),
                                    (0.5, 'Eclaboussure', 'trainee')])


# =========================================================================================================
# 6. « Extraction » suggérée : la victime plaquée au sol (main gauche sur la poitrine), le monstre s'acharne penché
#    sur elle (caméra derrière son épaule), coupe noire, puis il se relève, la main portée à la gueule
V_PLAQUEE = dict(root=dict(), head=dict(pitch=-30, yaw=-15), armR=dict(pitch=95, abd=30, elbow=60),
                 armL=dict(pitch=80, abd=35, elbow=75), legR=dict(pitch=20, knee=35), legL=dict(pitch=45, knee=80))


def _extraction():
    dig = M(**KNEEL, neck=dict(p=-10), head=dict(p=-12), jaw=dict(a=18), finL=dict(c=45), finR=dict(c=30, s=6))
    for s in SIDES:
        dig['foot' + s] = dict(KNEEL_FEET[s], a=0.0)

    def digp(t):                                           # main droite qui fouille (plonge et tire), point dans la victime
        u = env(t, 1.3, 3.7, 0.2)
        ph = TAU * 2.6 * (t - 1.3)
        return u * (0.45 + 0.45 * math.sin(ph)), u * 0.25 * math.sin(ph * 0.5)

    def over_a(t):
        return {}

    def over_m(t):
        u = env(t, 1.3, 3.7, 0.2)
        ph = TAU * 2.6 * (t - 1.3)
        return {'upper': {'y': 6 * u * math.sin(ph * 0.5), 'p': 3 * u * math.sin(ph)},
                'head': {'p': 5 * u * math.sin(ph + 0.8)}, 'chest': {'r': 2 * u * math.sin(ph * 0.5)}}

    VPTS['fouille'] = ('Torso', (0.0, 0.0, -0.1))
    monster = [
        K(0.0, **M(pel=dict(ty=-0.3))),
        K(0.3, **M(pel=dict(ty=-0.7, z=-0.6, y=10), spine=dict(p=-6, y=6), chest=dict(y=6), jaw=dict(a=20),
                   armL=dict(sp=60, sr=-10, el=10), finL=dict(c=-5, s=12))),
        K(0.6, **M(pel=dict(ty=-1.6, z=-0.6, p=-6), spine=dict(p=-8), chest=dict(p=-8), jaw=dict(a=14), finL=dict(c=35))),
        K(1.2, **dig), K(3.75, **dig),
        K(4.3, **M(pel=dict(ty=-1.4, z=-0.4, p=-4), spine=dict(p=-4), chest=dict(p=-2), upper=dict(p=2), neck=dict(p=4),
                   head=dict(p=4), jaw=dict(a=22), finR=dict(c=45), ikR=ikd((0.25, -0.35, 0.35), 1.0, (0.6, -0.6, 0.4), 1.0))),
        K(5.4, **M(pel=dict(ty=-0.6, z=-0.3, p=-3), neck=dict(p=6), head=dict(p=8), jaw=dict(a=24), finR=dict(c=50),
                   ikR=ikd((0.25, -0.3, 0.3), 1.0, (0.6, -0.6, 0.4), 1.0))),
    ]
    monster[0][1]['ikR'] = ikd((0.25, -0.35, 0.35), 0.0, (0.6, -0.6, 0.4), 1.0)
    monster[3][1]['ikR'] = ikd((0.25, -0.35, 0.35), 0.0, (0.6, -0.6, 0.4), 1.0)
    monster[4][1]['ikR'] = ikd((0.25, -0.35, 0.35), 0.0, (0.6, -0.6, 0.4), 1.0)

    def feet(t):
        out = {'turn': {'a': 0.0}}
        for s in SIDES:
            kf = KNEEL_FEET[s]
            f0 = foot_step(t, 0.15, 0.45, dict(), dict(z=-0.6 if s == 'L' else 0.2), 0.4)
            f1 = foot_step(t, 0.7, 1.15, dict(z=-0.6 if s == 'L' else 0.2), kf, 0.2)
            f2 = foot_step(t, 3.9, 4.4, kf, dict(z=-0.4 if s == 'L' else 0.1), 0.4)
            out['foot' + s] = f0 if t < 0.7 else (f1 if t < 3.9 else f2)
        return out

    class Extraction(Kill):
        def __call__(self, t):
            P = Kill.__call__(self, t)
            u = env(t, 1.3, 3.7, 0.2)
            if u > 1e-3:                                    # main droite qui fouille dans le ventre (IK)
                W = fk(P)
                R_a, t_a = P['VictimeAncre']
                F = anchor_frame(R_a, t_a)
                wv = self.victim(t)
                depth, side = digp(t)
                base = (F @ np.append(vpoint(wv, 'fouille'), 1.0))[:3]
                up = F[:3, :3] @ np.array([0.0, 0.0, -1.0])     # vers l'avant de la victime (vers le ciel)
                tgt = base + up * (depth - 0.2) + F[:3, :3] @ np.array([side, 0.3, 0.0])
                arm_to(P, W, 'R', tgt, u, (0.9, 0.6, 0.6))
            return P

    return Extraction(
        'k_extraction', 'Monstre_Extraction', 'Extraction (suggérée)', 5.4, monster,
        victim=[K(0.0, **V_PEUR), K(0.3, **V_RECUL), K(0.55, **V_TOMBE), K(0.85, **V_PLAQUEE), K(3.2, **V_PLAQUEE),
                K(3.75, **V_MORT_DOS), K(5.4, **V_MORT_DOS)],
        anchor=[K(0.0, ancre=dict()), K(0.3, ancre=dict(z=0.2, wiL=0.5)), K(0.55, ancre=dict(z=0.4, p=-55, sol=0.6, wiL=1.0)),
                K(0.85, ancre=dict(z=0.8, p=-90, sol=1.0, wiL=1.0)), K(3.8, ancre=dict(z=0.8, p=-90, sol=1.0, wiL=1.0)),
                K(4.2, ancre=dict(z=0.8, p=-90, sol=1.0, wiL=0.0)), K(5.4, ancre=dict(z=0.8, p=-90, sol=1.0))],
        ik={'L': ('poitrine', 'wiL', (-0.9, 0.3, 0.6))}, feet=feet, over_m=over_m,
        over_v=lambda t: add(lutte(t, 61, 0.9, 3.3, 1.2, 6.0), {'root': {'tilt': 6 * jit(t, 64, 5.0) * env(t, 1.0, 3.5)},
                                                                'head': {'yaw': 25 * jit(t, 65, 3.0) * env(t, 0.9, 3.3)}}),
        markers=[(0.0, 'Camera', 'face'), (0.25, 'Son', 'grognement'), (0.4, 'Coup', 'plaque'), (0.85, 'Son', 'chute_corps'),
                 (1.2, 'Camera', 'epaule_monstre'), (1.4, 'Son', 'dechirure'), (1.6, 'Eclaboussure', 'poitrine'),
                 (2.2, 'Son', 'craquement'), (2.4, 'Eclaboussure', 'poitrine'), (3.0, 'Son', 'dechirure'),
                 (3.2, 'Eclaboussure', 'poitrine'), (3.8, 'Coupure', '1.0'), (3.8, 'Flaque', 'poitrine'),
                 (4.0, 'Camera', 'retour'), (4.4, 'Son', 'mastication'), (5.0, 'Son', 'mastication')])


EXTRACTION = _extraction()


# =========================================================================================================
# 7. Frénésie : coups de griffes et morsures extrêmement rapides, caméra qui tremble, puis silence soudain
_FR_HITS = tuple(0.62 + 0.16 * i for i in range(12))


def _frenesie():
    crouch = M(**KNEEL, neck=dict(p=-8), head=dict(p=-8), jaw=dict(a=14), armR=dict(sp=95, sr=12, el=70),
               armL=dict(sp=95, sr=12, el=70), finR=dict(c=-8, s=14), finL=dict(c=-8, s=14))
    frozen = M(**KNEEL, neck=dict(p=-2), head=dict(p=0), jaw=dict(a=10), armR=dict(sp=40, sr=10, el=40),
               armL=dict(sp=40, sr=10, el=40), finR=dict(c=25), finL=dict(c=25))
    for d in (crouch, frozen):
        for s in SIDES:
            d['foot' + s] = dict(KNEEL_FEET[s], a=0.0)
    VPTS['ventreG'] = ('Torso', (-0.45, -0.3, -0.45))
    VPTS['poitrineD'] = ('Torso', (0.45, 0.4, -0.45))

    def over_a(t):
        out = {'wiR': 0.0, 'wiL': 0.0, 'wb': 0.0}
        for i, th in enumerate(_FR_HITS):
            k = pulse(t, th, 0.07, 0.08)
            if i % 3 == 2:
                out['wb'] += 0.85 * k
            elif i % 2 == 0:
                out['wiR'] += k
            else:
                out['wiL'] += k
        return out

    def over_m(t):
        out = {'upper': {'y': 0.0}, 'head': {'p': 0.0}, 'jaw': {'a': 0.0}}
        for i, th in enumerate(_FR_HITS):
            k = pulse(t, th, 0.07, 0.08)
            if i % 3 == 2:
                out['jaw']['a'] += 22 * pulse(t, th - 0.06, 0.06, 0.04) - 10 * k
            else:
                out['upper']['y'] += (-7 if i % 2 == 0 else 7) * k
        out['spine'] = {'r': shake(t, 0.55, 2.6, 13.0, 1.5)}
        return out

    def over_v(t):
        jolt = sum(pulse(t, th, 0.03, 0.12) * (1 if i % 2 else -1) for i, th in enumerate(_FR_HITS))
        return add({'root': {'tilt': 7 * jolt}, 'head': {'yaw': 12 * jolt}},
                   lutte(t, 71, 0.5, 1.9, 1.2, 8.0, ('armR', 'armL')))

    hits = []
    for i, th in enumerate(_FR_HITS):
        bite = i % 3 == 2
        hits += [(th, 'Morsure' if bite else 'Coup', 'frenesie'), (th + 0.01, 'Son', 'morsure' if bite else 'impact'),
                 (th + 0.02, 'Eclaboussure', 'frenesie')]
    return Kill(
        'k_frenesie', 'Monstre_Frenesie', 'Frénésie', 3.8,
        monster=[K(0.0, **M(pel=dict(ty=-0.3))),
                 K(0.22, **M(pel=dict(ty=0.1, z=0.2, p=3), spine=dict(p=6), chest=dict(p=6), upper=dict(p=8), neck=dict(p=12),
                             head=dict(p=10), jaw=dict(a=32), armR=dict(sp=-10, sr=40, el=30), armL=dict(sp=-10, sr=40, el=30),
                             finR=dict(c=-12, s=16), finL=dict(c=-12, s=16))),
                 K(0.42, **M(pel=dict(ty=-1.4, z=-0.8, p=-8), spine=dict(p=-10), chest=dict(p=-8), jaw=dict(a=20),
                             armR=dict(sp=70, el=20), armL=dict(sp=70, el=20))),
                 K(0.62, **crouch), K(2.6, **crouch), K(2.72, **frozen), K(3.8, **frozen)],
        victim=[K(0.0, **V_PEUR), K(0.4, **V_RECUL), K(0.55, **V_TOMBE), K(0.75, **V_SOL_LUTTE), K(1.9, **V_SOL_LUTTE),
                K(2.4, **V_MORT_DOS), K(3.8, **V_MORT_DOS)],
        anchor=[K(0.0, ancre=dict()), K(0.42, ancre=dict(z=0.2)), K(0.55, ancre=dict(z=0.5, p=-60, sol=0.6)),
                K(0.72, ancre=dict(z=0.9, p=-90, sol=1.0)), K(3.8, ancre=dict(z=0.9, p=-90, sol=1.0))],
        ik={'R': ('ventreG', 'wiR', (0.9, 0.4, 0.5)), 'L': ('poitrineD', 'wiL', (-0.9, 0.4, 0.5))},
        attach={'cou': ('bouche', 'wb')},
        feet=lambda t: {'turn': {'a': 0.0}, **{('foot' + s): foot_step(t, 0.42, 0.68, dict(), KNEEL_FEET[s], 0.3) for s in SIDES}},
        over_m=over_m, over_v=over_v, over_a=over_a,
        markers=[(0.0, 'Camera', 'victime'), (0.15, 'Son', 'hurlement_court'), (0.42, 'Coup', 'renverse'),
                 (0.55, 'Camera', 'tremble'), (0.6, 'Son', 'chute_corps')] + hits
                + [(1.4, 'Ecran', 'sang'), (2.65, 'Silence', '2.5'), (2.65, 'Camera', 'fige')])


FRENESIE = _frenesie()


# =========================================================================================================
# 8. Victime contaminée : morsure à l'avant-bras, la victime est jetée au sol, face contre terre, et laissée vivante ;
#    elle se relève (animation du survivant) et l'infection commence quelques secondes plus tard
V_PRONE = dict(root=dict(SA.PRONE_ROOT), head=dict(pitch=72.0), armR=dict(SA.PRONE_ARMS['Right']),
               armL=dict(SA.PRONE_ARMS['Left']), legR=dict(SA.PRONE_LEGS['Right']), legL=dict(SA.PRONE_LEGS['Left']))
V_PRONE_BLESSE = V(V_PRONE, head=dict(pitch=55, yaw=-25), armL=dict(pitch=120, abd=-10, twist=60, elbow=120))


def _contamination():
    VPTS['brasG_haut'] = ('LeftLowerArm', (0.0, 0.25, 0.0))
    return Kill(
        'k_contamination', 'Monstre_Contamination', 'Victime contaminée', 2.8,
        monster=[
            K(0.0, **M(pel=dict(ty=-0.3))),
            K(0.3, **M(pel=dict(ty=-0.6, z=-0.7, y=-6), spine=dict(p=-6, y=-4), chest=dict(y=-4), jaw=dict(a=16),
                       finR=dict(c=-5, s=10), footR=dict(z=-0.9))),
            K(0.55, **M(pel=dict(ty=-0.4, z=-0.5, y=-4), spine=dict(p=-4, y=-3), chest=dict(y=-3), neck=dict(p=-6, y=-4),
                        head=dict(p=-6, y=-6), jaw=dict(a=30), finR=dict(c=55), footR=dict(z=-0.9))),
            K(0.72, **M(pel=dict(ty=-0.5, z=-0.5, y=-4), spine=dict(p=-5, y=-3), chest=dict(y=-3), neck=dict(p=-9, y=-4),
                        head=dict(p=-9, y=-6), jaw=dict(a=3), finR=dict(c=55), footR=dict(z=-0.9))),
            K(1.05, **M(pel=dict(ty=-0.4, z=-0.4, y=-14), spine=dict(p=-4, y=-8), chest=dict(y=-8), neck=dict(p=-6, y=-4),
                        head=dict(p=-6, y=-6), jaw=dict(a=8), armR=dict(sp=45, sr=40, el=15), finR=dict(c=55), footR=dict(z=-0.9))),
            K(1.35, **M(pel=dict(ty=-0.4, z=-0.3, y=12), spine=dict(p=-2, y=8), chest=dict(y=6), armR=dict(sp=35, sr=-50, el=25),
                        finR=dict(c=-10, s=14), jaw=dict(a=14), footR=dict(z=-0.6))),
            K(2.8, **M(pel=dict(ty=-0.2, z=0.3), neck=dict(p=-6, y=14), head=dict(p=-8, y=16), jaw=dict(a=8), footR=dict(z=-0.1))),
        ],
        victim=[K(0.0, **V_PEUR),
                K(0.35, **V(V_RECUL, armL=dict(pitch=95, abd=25, elbow=15))),
                K(0.72, root=dict(lean=-16), head=dict(pitch=30, roll=20), armR=dict(pitch=100, abd=40, elbow=80),
                  armL=dict(pitch=150, abd=20, elbow=10), legR=dict(pitch=25, knee=45), legL=dict(pitch=0, knee=25)),
                K(1.1, root=dict(lean=-10), head=dict(pitch=20), armR=dict(pitch=120, abd=50, elbow=60),
                  armL=dict(pitch=150, abd=25, elbow=10), legR=dict(pitch=30, knee=40), legL=dict(pitch=10, knee=20)),
                K(1.45, root=dict(lean=30, y=-0.5), head=dict(pitch=10), armR=dict(pitch=130, abd=50, elbow=30),
                  armL=dict(pitch=140, abd=40, elbow=20), legR=dict(pitch=10, knee=30), legL=dict(pitch=-10, knee=40)),
                K(1.8, **V_PRONE), K(2.2, **V_PRONE_BLESSE), K(2.8, **V_PRONE_BLESSE)],
        anchor=[K(0.0, ancre=dict()),
                K(0.3, ancre=dict(z=0.5, wiR=1.0)),
                K(0.55, ancre=dict(ty=0.8, z=1.0, wiR=1.0, wb=0.6)),
                K(0.72, ancre=dict(ty=1.0, z=1.1, wiR=1.0, wb=1.0)),
                K(0.98, ancre=dict(ty=1.0, z=1.1, wiR=1.0, wb=1.0, snap=1)),
                K(1.12, ancre=dict(ty=1.2, z=1.0, x=0.3, y=-10, wiR=1.0)),
                K(1.35, ancre=dict(ty=1.0, z=0.4, x=-2.0, y=-50, wiR=0.0)),
                K(1.8, ancre=dict(z=-0.8, x=-4.6, y=-75, sol=1.0)),
                K(2.8, ancre=dict(z=-0.8, x=-4.6, y=-75, sol=1.0))],
        ik={'R': ('brasG', 'wiR', (0.9, -1.0, 0.2))}, attach={'brasG_haut': ('bouche', 'wb')},
        over_m=lambda t: {'neck': {'y': shake(t, 0.75, 1.0, 5.0, 4.0)}, 'head': {'y': shake(t, 0.75, 1.0, 5.0, 5.0)}},
        over_v=lambda t: add(lutte(t, 81, 0.2, 1.3, 1.0, 6.0, ('armR', 'legR', 'legL')),
                             {'root': {'tilt': 6 * jit(t, 83, 1.2) * env(t, 1.9, 3.0)}}),
        markers=[(0.0, 'Camera', 'epaule_victime'), (0.25, 'Son', 'grognement'), (0.3, 'Son', 'saisie'),
                 (0.72, 'Morsure', 'bras'), (0.73, 'Son', 'morsure'), (0.74, 'Eclaboussure', 'bras'), (0.75, 'Infection', ''),
                 (0.76, 'Tremble', '0.5'), (1.35, 'Lacher', ''), (1.35, 'Camera', 'suivre'), (1.75, 'Son', 'chute_corps'),
                 (2.0, 'Son', 'grognement'), (2.6, 'Camera', 'retour')])


CONTAMINATION = _contamination()


KILLS = [MORSURE_COU, MORSURE_REPETEE, DEV_SAISIE, DEV_TRAINER, DEV_TOURNER, DEV_MANGER, ATTAQUE_VENTRE, TRAINEE_SAISIE,
         TRAINEE_TRAINER, EXTRACTION, FRENESIE, CONTAMINATION]
CLIPS = {}
VICTIM = {}


def _register():
    CLIPS.clear()
    VICTIM.clear()
    for k in KILLS:
        CLIPS[k.key] = A.Clip(k.key, k.name, k.length, k, loop=k.loop, priority=k.priority, label=k.label,
                              markers=k.markers, parts=list(A.ORDER))
        VICTIM[k.key] = k


_register()


def victim_world(key, t):
    return VICTIM[key].victim(t)
