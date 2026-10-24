"""Animations du monstre (rig rigide de 37 pièces, rig_spec) : cinématique directe, IK des jambes, poses-clés,
courbes, échantillonnage, réduction des clés et export vers Roblox (Motor6D.Transform par pièce).

Repère Roblox du modèle au repos (studs) : X = droite du monstre, Y = haut, Z = arrière (il regarde vers -Z), sol à
Y = 0. Chaque Motor6D a des C0/C1 alignés sur ce repère au pivot de l'articulation (installateur Roblox), donc
Transform = rotation autour du pivot exprimée dans le repère (au repos) du parent, puis translation.

Conventions d'angles (degrés) :
  pitch (axe X) : + = membre vers l'avant (jambe, bras) ; tronc, cou, tête : - = penché vers l'avant / vers le bas
  yaw   (axe Y) : + = tourne vers SA gauche
  roll  (axe Z) : + = bascule vers SA gauche (le haut va vers -X) ; bras droit écarté = +, bras gauche écarté = -
Rotation d'une pose : R = Ry(yaw) . Rz(roll) . Rx(pitch).

Pièce supplémentaire « VictimeAncre » (joint VictimeAncre, parent HumanoidRootPart) : position de la victime pendant
une mise à mort (son HumanoidRootPart y est soudé) ; repos = 4 studs devant le monstre, au sol, tournée vers lui."""
import math
import numpy as np
from mon_skel import rig_spec, J, HAND, FINGERS, HEAD_C, FH, UH, SCALE, JAW_HINGE

RIG = rig_spec()                                       # pièce -> (parent, pivot, articulation)
PIV = {n: np.asarray(v[1], float) for n, v in RIG.items()}
PARENT = {n: v[0] for n, v in RIG.items()}
JOINT = {n: v[2] for n, v in RIG.items()}
HRP_C = np.asarray(J['Pelvis'], float)                 # centre du HumanoidRootPart (repère modèle)
HRP_SIZE = (2.4, 2.4, 1.6)
HIP_HEIGHT = float(HRP_C[1] - HRP_SIZE[1] / 2)         # Humanoid.HipHeight
# victime : son HumanoidRootPart est 3 studs au-dessus de son sol (rig du survivant), 4 studs devant le monstre
VICTIM_REST = np.array([0.0, 3.0, HRP_C[2] - 4.0])     # repère modèle
PIV['VictimeAncre'] = VICTIM_REST.copy()
PARENT['VictimeAncre'] = 'HumanoidRootPart'
JOINT['VictimeAncre'] = 'VictimeAncre'
PIECES = list(RIG.keys())


def _order():
    out, seen = [], {'HumanoidRootPart'}
    pending = PIECES + ['VictimeAncre']
    while pending:
        for n in list(pending):
            if PARENT[n] in seen:
                out.append(n); seen.add(n); pending.remove(n)
    return out


ORDER = _order()                                       # parents avant enfants
CHILDREN = {}
for _n in ORDER:
    CHILDREN.setdefault(PARENT[_n], []).append(_n)


# ------------------------------------------------------------------------------------------------ maths

def Rx(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(p=0.0, y=0.0, r=0.0):
    return Ry(y) @ Rz(r) @ Rx(p)


def axis_angle(axis, d):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    t = math.radians(d); c, s = math.cos(t), math.sin(t)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + s * K + (1 - c) * K @ K


def M4(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def T4(t):
    return M4(None, t)


def quat(R):
    """(x, y, z, w) d'une matrice de rotation."""
    m = R
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s; x = (m[2, 1] - m[1, 2]) / s; y = (m[0, 2] - m[2, 0]) / s; z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s; x = 0.25 * s; y = (m[0, 1] + m[1, 0]) / s; z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s; x = (m[0, 1] + m[1, 0]) / s; y = 0.25 * s; z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s; x = (m[0, 2] + m[2, 0]) / s; y = (m[1, 2] + m[2, 1]) / s; z = 0.25 * s
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q) * (1 if q[3] >= 0 else -1)


def angle_between(Ra, Rb):
    Rr = Ra.T @ Rb
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(Rr) - 1) / 2))))


# ------------------------------------------------------------------------------------------------ poses

class Pose(dict):
    """pièce -> (R 3x3, t 3) : Transform de son articulation. Pièces absentes = repos."""

    def get_rt(self, n):
        v = self.get(n)
        if v is None:
            return np.eye(3), np.zeros(3)
        return v


def fk(pose):
    """Matrices monde (repère modèle) de chaque pièce ; HumanoidRootPart = identité (le modèle bouge par
    l'Humanoid)."""
    W = {'HumanoidRootPart': np.eye(4)}
    for n in ORDER:
        R, t = pose.get_rt(n)
        piv = PIV[n]
        W[n] = W[PARENT[n]] @ T4(piv) @ M4(R, t) @ T4(-piv)
    return W


def point(W, n, p):
    """Position monde d'un point p (repère modèle au repos) attaché à la pièce n."""
    return (W[n] @ np.append(np.asarray(p, float), 1.0))[:3]


# ------------------------------------------------------------------------------------------------ IK des jambes

SIDES = ('R', 'L')
SGN = {'R': 1.0, 'L': -1.0}
HIP = {s: PIV['Thigh_' + s] for s in SIDES}
KNEE = {s: PIV['Shin_' + s] for s in SIDES}
ANKLE = {s: PIV['Foot_' + s] for s in SIDES}
V1 = {s: KNEE[s] - HIP[s] for s in SIDES}
V2 = {s: ANKLE[s] - KNEE[s] for s in SIDES}
# points du pied (repère modèle au repos) pour le contact au sol : talon, plante, bouts des orteils
FOOT_PTS = {}
for _s in SIDES:
    _a = ANKLE[_s]
    _fwd = np.array([SGN[_s] * 0.1, 0, -1.0]); _fwd /= np.linalg.norm(_fwd)
    FOOT_PTS[_s] = np.array([[_a[0], 0.05, _a[2] + 0.25], [_a[0], 0.04, _a[2] - 0.35],
                             _a + _fwd * 0.9 + np.array([0, -0.8, 0]), _a + _fwd * 1.15 + np.array([0, -0.82, 0])])


def _rot2(v, th):
    c, s = math.cos(th), math.sin(th)
    return np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])


def _ang(v):
    return math.atan2(v[1], v[0])


def leg_ik(side, W_pelvis, target, foot_pitch_world=0.0, abd=0.0, foot_yaw_world=0.0):
    """Cuisse, tibia et pied pour mettre la cheville au point `target` (repère modèle), genou plié vers l'avant comme
    au repos. La jambe tourne d'abord autour de Y (annule le lacet du bassin : le plan de la jambe reste face à
    l'avant), puis d'un petit roulis (rattrape l'écart latéral), puis plie dans son plan (IK à deux segments).
    Le pied garde un pitch donné dans le monde (semelle à plat = 0). abd : écart latéral voulu en plus (degrés).
    Renvoie {pièce: (R, t)} et l'erreur de position restante."""
    Rp = W_pelvis[:3, :3]
    hip_w = (W_pelvis @ np.append(HIP[side], 1))[:3]
    # lacet du bassin dans le monde -> la cuisse le compense
    fwd = Rp @ np.array([0, 0, -1.0])
    psi = -math.degrees(math.atan2(-fwd[0], -fwd[2])) + foot_yaw_world
    x0 = V1[side][0] + V2[side][0]                              # décalage latéral de la jambe au repos
    alpha = SGN[side] * abd
    a = V1[side][1:]; b = V2[side][1:]
    L1, L2 = np.linalg.norm(a), np.linalg.norm(b)
    phi0 = _ang(b) - _ang(a)
    phi0 = (phi0 + math.pi) % (2 * math.pi) - math.pi
    for _ in range(4):                                         # roulis : la cheville tombe sur la bonne abscisse
        G = Rp @ Ry(psi) @ Rz(alpha)
        d = G.T @ (np.asarray(target, float) - hip_w)
        ex = d[0] - x0
        if abs(ex) < 1e-4:
            break
        alpha += math.degrees(math.atan2(ex, max(-d[1], 1e-3)))
    G = Rp @ Ry(psi) @ Rz(alpha)
    d = G.T @ (np.asarray(target, float) - hip_w)
    D = d[1:]
    dist = np.clip(np.linalg.norm(D), abs(L1 - L2) + 1e-3, L1 + L2 - 1e-4)
    cphi = (dist ** 2 - L1 ** 2 - L2 ** 2) / (2 * L1 * L2)
    phi = math.copysign(math.acos(np.clip(cphi, -1, 1)), phi0)
    th2 = phi - phi0
    c = a + _rot2(b, th2)
    th1 = _ang(D) - _ang(c)
    th1 = (th1 + math.pi) % (2 * math.pi) - math.pi
    p1, p2 = math.degrees(th1), math.degrees(th2)
    R_th = Ry(psi) @ Rz(alpha) @ Rx(p1)
    R_sh = Rx(p2)
    R_world_shin = Rp @ R_th @ R_sh
    R_ft = R_world_shin.T @ Ry(foot_yaw_world) @ Rx(foot_pitch_world)
    out = {'Thigh_' + side: (R_th, np.zeros(3)), 'Shin_' + side: (R_sh, np.zeros(3)), 'Foot_' + side: (R_ft, np.zeros(3))}
    return out, abs(np.linalg.norm(D) - dist) + abs(d[0] - x0)


# ------------------------------------------------------------------------------------------------ doigts et mains

def finger_curl(side, amount, spread=0.0, thumb=None):
    """Flexion des doigts (degrés par phalange, + = vers la paume), écart (degrés), pouce (sinon comme les doigts)."""
    h = HAND[side]
    out = {}
    for name in FINGERS:
        f = h['fingers'][name]
        ax = f['axis']
        k = (thumb if (name == 'Thumb' and thumb is not None) else amount)
        for j in range(len(f['segs'])):
            n = '%s%d_%s' % (name, j + 1, side)
            R = axis_angle(ax, k * (1.0 if j == 0 else 1.15))
            if j == 0 and spread and name != 'Thumb':
                i = FINGERS.index(name) - 1.5
                R = axis_angle(h['N'], SGN[side] * spread * i * 0.5) @ R
            out[n] = (R, np.zeros(3))
    return out


def finger_axis_sign_check():
    """Vérifie que +curl referme bien les doigts vers la paume (bout des doigts vers N de la paume)."""
    h = HAND['R']
    f = h['fingers']['Middle']
    a, b, d = f['segs'][-1]
    P = Pose(finger_curl('R', 30))
    W = fk(P)
    tip0 = b
    tip1 = point(W, 'Middle2_R', b)
    return float((tip1 - tip0) @ h['N'])


# ------------------------------------------------------------------------------------------------ courbes

def _hermite(p0, p1, m0, m1, t):
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1


def curve(t, keys):
    """Courbe lisse non périodique (Fritsch-Carlson, sans dépassement) par des clés (temps, valeur)."""
    ks = sorted(keys)
    Tk = np.array([k[0] for k in ks], float)
    V = np.array([k[1] for k in ks], float)
    if t <= Tk[0]:
        return float(V[0])
    if t >= Tk[-1]:
        return float(V[-1])
    n = len(Tk)
    dk = np.diff(V) / np.diff(Tk)
    m = np.zeros(n)
    for k in range(1, n - 1):
        if dk[k - 1] * dk[k] > 0:
            w1 = 2 * (Tk[k + 1] - Tk[k]) + (Tk[k] - Tk[k - 1])
            w2 = (Tk[k + 1] - Tk[k]) + 2 * (Tk[k] - Tk[k - 1])
            m[k] = (w1 + w2) / (w1 / dk[k - 1] + w2 / dk[k])
    i = int(np.searchsorted(Tk, t, side='right')) - 1
    h = Tk[i + 1] - Tk[i]
    return float(_hermite(V[i], V[i + 1], m[i] * h, m[i + 1] * h, (t - Tk[i]) / h))


def cyc(ph, keys):
    """Courbe périodique (phase 0..1) par des clés (phase, valeur), Catmull-Rom."""
    ks = sorted(keys)
    P = np.array([k[0] for k in ks] + [ks[0][0] + 1.0])
    V = np.array([k[1] for k in ks] + [ks[0][1]])
    ph = ph % 1.0
    if ph < P[0]:
        ph += 1.0
    i = int(np.searchsorted(P, ph, side='right')) - 1
    i = min(i, len(P) - 2)
    n = len(ks)

    def val(k):
        return V[k % n] if k >= 0 else V[(k % n)]

    def tang(k):
        kp, kn = (k - 1) % n, (k + 1) % n
        pp = P[k % n] - ((P[k % n] - P[kp]) % 1.0 or 1.0)
        pn = P[k % n] + ((P[kn] - P[k % n]) % 1.0 or 1.0)
        return (V[kn] - V[kp]) / (pn - pp)
    h = P[i + 1] - P[i]
    t = (ph - P[i]) / h
    return float(_hermite(V[i], V[i + 1], tang(i) * h, tang((i + 1) % n) * h, t))


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return float(x * x * (3 - 2 * x))


class Track:
    """Pistes d'une pose-clé à l'autre : chaque canal (pièce, composante) suit une courbe par ses clés.
    keys : liste (temps, {pièce: dict(p=, y=, r=, x=, ty=, z=)}) ; les canaux absents d'une clé gardent la valeur
    interpolée des autres clés."""

    def __init__(self, keys):
        self.ch = {}
        for t, d in keys:
            for piece, v in d.items():
                for k, val in v.items():
                    self.ch.setdefault((piece, k), []).append((t, float(val)))

    def at(self, t):
        vals = {}
        for (piece, k), ks in self.ch.items():
            vals.setdefault(piece, {})[k] = curve(t, ks) if len(ks) > 1 else ks[0][1]
        return vals


def pose_from(vals):
    """{pièce: dict(p, y, r, x, ty, z)} -> Pose."""
    P = Pose()
    for piece, v in vals.items():
        P[piece] = (euler(v.get('p', 0.0), v.get('y', 0.0), v.get('r', 0.0)),
                    np.array([v.get('x', 0.0), v.get('ty', 0.0), v.get('z', 0.0)]))
    return P


def merge(*poses):
    """Compose des poses : pour une même pièce, rotations multipliées (dans l'ordre), translations additionnées."""
    out = Pose()
    for P in poses:
        for n, (R, t) in P.items():
            if n in out:
                R0, t0 = out[n]
                out[n] = (R0 @ R, t0 + t)
            else:
                out[n] = (R, t)
    return out


# ------------------------------------------------------------------------------------------------ clips

class Clip:
    """fn(t) -> Pose. markers : [(temps, nom, valeur)] (KeyframeMarker de Roblox)."""

    def __init__(self, key, name, length, fn, loop=True, priority='Movement', speed=None, label='', markers=(),
                 parts=None, fps=30):
        self.key, self.name, self.length, self.fn, self.loop = key, name, length, fn, loop
        self.priority, self.speed, self.label, self.markers, self.fps = priority, speed, label, list(markers), fps
        self.parts = list(parts) if parts else [n for n in ORDER if n != 'VictimeAncre']


def sample(clip):
    n = max(2, int(round(clip.length * clip.fps)))
    times = [clip.length * i / n for i in range(n + 1)]
    return times, [clip.fn(t) for t in times]


def reduce_keys(times, poses, parts, tol_deg=0.4, tol_pos=0.004):
    """Retire les clés que l'interpolation linéaire (slerp) entre voisines reproduit à la tolérance près."""
    keep = [0]
    i = 0
    n = len(times)
    while i < n - 1:
        j = i + 1
        while j + 1 < n:
            ok = True
            for k in range(i + 1, j + 1):
                u = (times[k] - times[i]) / (times[j + 1] - times[i])
                for p in parts:
                    Ra, ta = poses[i].get_rt(p)
                    Rb, tb = poses[j + 1].get_rt(p)
                    Rk, tk = poses[k].get_rt(p)
                    if np.linalg.norm(ta + (tb - ta) * u - tk) > tol_pos:
                        ok = False; break
                    qa, qb = quat(Ra), quat(Rb)
                    if qa @ qb < 0:
                        qb = -qb
                    q = qa * (1 - u) + qb * u; q /= np.linalg.norm(q)
                    w, x, y, z = q[3], q[0], q[1], q[2]
                    Ri = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                                   [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                                   [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
                    if angle_between(Ri, Rk) > tol_deg:
                        ok = False; break
                if not ok:
                    break
            if not ok:
                break
            j += 1
        keep.append(j)
        i = j
    return [times[k] for k in keep], [poses[k] for k in keep]


def export_lua(clips, var='ANIMS', digits=4):
    """Table Luau : {key, name, label, length, loop, priority, speed, parts, keys={{t,{pose...}}}, markers}.
    pose = {x, y, z, qx, qy, qz, qw} (Motor6D.Transform), dans l'ordre de parts."""
    fmt = lambda v: (('%.*f' % (digits, v)).rstrip('0').rstrip('.') if abs(v) >= 0.5 * 10 ** -digits else '0')
    lines = ['%s = {' % var]
    total = 0
    for c in clips:
        times, poses = sample(c)
        times, poses = reduce_keys(times, poses, c.parts)
        total += len(times)
        sp = 'nil' if c.speed is None else fmt(c.speed)
        pl = ', '.join('"%s"' % p for p in c.parts)
        mk = ', '.join('{%s, "%s", "%s"}' % (fmt(t), nm, val) for t, nm, val in c.markers)
        lines.append('\t{key="%s", name="%s", label="%s", length=%s, loop=%s, priority="%s", speed=%s, parts={%s}, '
                     'markers={%s}, keys={' % (c.key, c.name, c.label, fmt(c.length), str(c.loop).lower(),
                                               c.priority, sp, pl, mk))
        for t, P in zip(times, poses):
            items = []
            for p in c.parts:
                R, tr = P.get_rt(p)
                q = quat(R)
                items.append('{' + ','.join(fmt(v) for v in (*tr, *q)) + '}')
            lines.append('\t\t{%s,{%s}},' % (fmt(t), ','.join(items)))
        lines.append('\t}},')
    lines.append('}')
    return '\n'.join(lines), total


def rig_lua():
    """Table Luau RIG : pièces dans l'ordre de la hiérarchie, parent, pivot, articulation."""
    fmt = lambda v: ('%.4f' % v).rstrip('0').rstrip('.')
    lines = ['RIG = {', '\thrp = {center={%s}, size={%s}, hipHeight=%s},' % (
        ', '.join(fmt(v) for v in HRP_C), ', '.join(fmt(v) for v in HRP_SIZE), fmt(HIP_HEIGHT)), '\tparts = {']
    for n in ORDER:
        lines.append('\t\t{name="%s", parent="%s", joint="%s", pivot={%s}},' % (
            n, PARENT[n], JOINT[n], ', '.join(fmt(v) for v in PIV[n])))
    lines += ['\t},', '}']
    return '\n'.join(lines)


# ------------------------------------------------------------------------------------------------ IK des bras

def _rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else axis_angle(np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0]), 180)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def slerp_R(Ra, Rb, w):
    qa, qb = quat(Ra), quat(Rb)
    if qa @ qb < 0:
        qb = -qb
    q = qa * (1 - w) + qb * w
    q /= np.linalg.norm(q)
    x, y, z, ww = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * ww), 2 * (x * z + y * ww)],
                     [2 * (x * y + z * ww), 1 - 2 * (x * x + z * z), 2 * (y * z - x * ww)],
                     [2 * (x * z - y * ww), 2 * (y * z + x * ww), 1 - 2 * (x * x + y * y)]])


SHOULDER = {s: PIV['UpperArm_' + s] for s in SIDES}
ELBOW = {s: PIV['Forearm_' + s] for s in SIDES}
WRIST = {s: PIV['Hand_' + s] for s in SIDES}
PALM = {s: HAND[s]['wrist'] + HAND[s]['D'] * 0.35 + HAND[s]['N'] * 0.08 for s in SIDES}


def arm_ik(side, W, target, pole=(0.0, -1.0, 0.6)):
    """Épaule (rotation complète) et coude (flexion autour de X) pour mettre la paume au point `target` (repère
    modèle) ; le coude part vers `pole` (direction monde, par défaut vers le bas et l'arrière). Main et doigts gardent
    leurs rotations. W : matrices monde de la pose (le parent de l'épaule, UpperChest, doit y être à jour)."""
    Wp = W['UpperChest']
    Rp = Wp[:3, :3]
    S = (Wp @ np.append(SHOULDER[side], 1))[:3]
    u0 = ELBOW[side] - SHOULDER[side]
    f0 = PALM[side] - ELBOW[side]
    tgt = Rp.T @ (np.asarray(target, float) - S)                     # repère du parent (au repos)
    d = np.clip(np.linalg.norm(tgt), 0.3, np.linalg.norm(u0) + np.linalg.norm(f0) - 1e-3)
    lo, hi = 0.0, 170.0                                               # flexion du coude : |u0 + Rx(th) f0| = d
    for _ in range(50):
        mid = (lo + hi) / 2
        if np.linalg.norm(u0 + Rx(mid) @ f0) > d:
            lo = mid
        else:
            hi = mid
    th = (lo + hi) / 2
    v_rest = u0 + Rx(th) @ f0
    R1 = _rot_between(v_rest, tgt)
    # torsion autour de l'axe épaule-cible : coude vers le pôle
    axis = tgt / np.linalg.norm(tgt)
    e = R1 @ u0
    pl = Rp.T @ np.asarray(pole, float)
    e_p = e - (e @ axis) * axis
    p_p = pl - (pl @ axis) * axis
    if np.linalg.norm(e_p) > 1e-6 and np.linalg.norm(p_p) > 1e-6:
        ang = math.degrees(math.atan2(np.cross(e_p, p_p) @ axis, e_p @ p_p))
        R1 = axis_angle(axis, ang) @ R1
    return {'UpperArm_' + side: (R1, np.zeros(3)), 'Forearm_' + side: (Rx(th), np.zeros(3))}
