"""Animations of the jointed R6 survivor (10 parts: elbows and knees), authored on a kinematic model of the
rig in rig_spec.py.

Every clip is a function of time returning the world pose (HumanoidRootPart frame) of the 10 body parts;
the Motor6D transforms Roblox needs (KeyframeSequence Pose.CFrame) follow from the joints' C0/C1.
Legs are 2-bone chains (thigh 0.95, shin 1.05 stud): planted boots are solved with analytic IK on the sole
edge that touches the ground (heel, then toe: a rigid boot rolls heel to toe), so feet never slide and the
knees bend naturally; swinging legs follow smooth angle curves that join the stance poses with matching
speeds. Arms bend at the elbow (forearm forward), legs at the knee (shin backward).

Roblox rig space: X = character's right, Y = up, Z = back (the character faces -Z).
HumanoidRootPart centre = origin, ground at Y = -3.
"""
import json
import numpy as np
import rig_spec as RS

GROUND = RS.GROUND
SIDES = {'Right': 1.0, 'Left': -1.0}
PARTS = RS.PARTS
UPPER_ARM = {s: s + 'UpperArm' for s in SIDES}
LOWER_ARM = {s: s + 'LowerArm' for s in SIDES}
UPPER_LEG = {s: s + 'UpperLeg' for s in SIDES}
LOWER_LEG = {s: s + 'LowerLeg' for s in SIDES}


# ----------------------------------------------------------------------------------------------
# math

def Rx(a):
    a = np.radians(a); c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    a = np.radians(a); c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    a = np.radians(a); c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def M4(R=None, p=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if p is not None:
        M[:3, 3] = p
    return M


def T(p):
    return M4(p=p)


def inv4(M):
    R, p = M[:3, :3], M[:3, 3]
    return M4(R.T, -R.T @ p)


def quat(R):
    """Rotation matrix -> unit quaternion (x, y, z, w), w >= 0."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = np.array([0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s])
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = np.array([(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s])
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = np.array([(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s])
    q /= np.linalg.norm(q)
    return q if q[3] >= 0 else -q


def rot_angle(Ra, Rb):
    """Angle (degrees) between two rotations."""
    c = (np.trace(Ra.T @ Rb) - 1) / 2
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


def apply(W, P):
    return np.asarray(P, float) @ W[:3, :3].T + W[:3, 3]


# ----------------------------------------------------------------------------------------------
# rig (rig_spec.py)

REST = {n: RS.rest(n) for n in ('HumanoidRootPart',) + PARTS}
JOINTS = {}                                   # part1 -> (joint name, part0, C0, C1)
for _name, (_p0, _p1, _piv, _r) in RS.JOINT_DEFS.items():
    _C0, _C1 = RS.c0c1(_name)
    JOINTS[_p1] = (_name, _p0, _C0, _C1)

SH_PIV = {s: np.array([SIDES[s] * 1.2, 0.66, 0.0]) for s in SIDES}      # shoulder pivots (torso frame)
HIP_PIV = {s: np.array([SIDES[s] * 0.5, -1.0, 0.0]) for s in SIDES}     # hip pivots (torso frame)
ELBOW_LOCAL = np.array([0.0, -0.5, 0.0])                                 # elbow pivot in the upper arm frame
KNEE_LOCAL = np.array([0.0, -0.475, 0.0])                                # knee pivot in the upper leg frame
L_THIGH, L_SHIN = 0.95, 1.05                                             # hip -> knee, knee -> sole
L_FORE = 1.0                                                             # elbow -> fingertips
HEEL, TOE = 0.53, 0.59                    # sole edges behind / ahead of the shin axis (lower leg local z)


def transforms(world):
    """World poses (HRP frame) -> Motor6D.Transform per Part1 name."""
    W = dict(world); W['HumanoidRootPart'] = M4()
    return {p1: inv4(C0) @ inv4(W[p0]) @ W[p1] @ C1 for p1, (_, p0, C0, C1) in JOINTS.items()}


def world_from_transforms(Tr):
    """Inverse of transforms(): forward kinematics from Motor6D transforms."""
    W = {'HumanoidRootPart': M4()}
    for p1 in PARTS:
        _, p0, C0, C1 = JOINTS[p1]
        W[p1] = W[p0] @ C0 @ Tr[p1] @ inv4(C1)
    del W['HumanoidRootPart']
    return W


# ----------------------------------------------------------------------------------------------
# body proxies (part-local points) for ground contact and checks; limb ends near the elbows and knees
# are half cylinders (the outfit is hinged there)

def _box_pts(hx, hy, hz, n=3):
    g = [np.linspace(-1, 1, n)] * 3
    P = np.stack(np.meshgrid(*g, indexing='ij'), -1).reshape(-1, 3)
    P = P[np.abs(P).max(1) > 0.999]
    return P * np.array([hx, hy, hz])


def _semi(r, y0, below, hx, n=9):
    a = np.linspace(0, np.pi, n)
    sg = -1.0 if below else 1.0
    return np.array([(x, y0 + sg * r * np.sin(t), r * np.cos(t)) for x in (-hx, 0.0, hx) for t in a])


SOLE = np.stack(np.meshgrid(np.linspace(-0.50, 0.50, 3), [-0.525], np.linspace(-TOE, 0.51, 5), indexing='ij'),
                -1).reshape(-1, 3)
_cyl = [(0.69 * np.cos(a), y, 0.69 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)
        for y in (-0.45, 0.0, 0.45)]
PROXY = {'Torso': np.concatenate([_box_pts(1.03, 1.03, 0.56, 4), [(-0.62, 0.47, -0.645)]]),
         'Head': np.concatenate([np.array(_cyl), [(0, 0.69, 0), (0, -0.63, 0)]])}
for _s in SIDES:
    PROXY[UPPER_ARM[_s]] = np.concatenate([_box_pts(0.52, 0.5, 0.53, 3), _semi(0.524, -0.5, True, 0.5)])
    PROXY[LOWER_ARM[_s]] = np.concatenate([_box_pts(0.52, 0.5, 0.53, 3), _semi(0.524, 0.5, False, 0.5)])
    PROXY[UPPER_LEG[_s]] = np.concatenate([_box_pts(0.52, 0.475, 0.53, 3), _semi(0.53, -0.475, True, 0.5)])
    PROXY[LOWER_LEG[_s]] = np.concatenate([_box_pts(0.52, 0.525, 0.53, 3), _semi(0.53, 0.525, False, 0.5), SOLE])


def lowest(W, name):
    return float(apply(W, PROXY[name])[:, 1].min())


# ----------------------------------------------------------------------------------------------
# posing

def torso_world(root):
    R = Ry(root.get('yaw', 0)) @ Rx(-root.get('lean', 0)) @ Rz(-root.get('tilt', 0))
    return M4(R, (root.get('x', 0), root.get('y', 0), root.get('z', 0)))


def limb_rot(side, pitch=0.0, abd=0.0, twist=0.0):
    """Arm orientation in the torso frame: twist about the limb, pitch forward (+), then abduction outward (+)
    (Rz Rx: singular only when the arm points straight forward or back)."""
    s = SIDES[side]
    return Rz(s * abd) @ Rx(pitch) @ Ry(s * twist)


def leg_rot(side, pitch=0.0, abd=0.0, twist=0.0):
    """Leg orientation in the torso frame: twist about the thigh, abduction outward (+), then pitch forward (+)
    (Rx Rz: singular only at 90 degrees of abduction, so crouching and kneeling thighs stay well defined)."""
    s = SIDES[side]
    return Rx(pitch) @ Rz(s * abd) @ Ry(s * twist)


def arm_world(WT, side, pitch=0.0, abd=0.0, twist=0.0, elbow=0.0):
    piv = SH_PIV[side]
    Wu = WT @ T(piv) @ M4(limb_rot(side, pitch, abd, twist)) @ T(-piv) @ REST[UPPER_ARM[side]]
    Wl = Wu @ T(ELBOW_LOCAL) @ M4(Rx(elbow)) @ T(-ELBOW_LOCAL) @ T((0, -1.0, 0))
    return Wu, Wl


def leg_world(WT, side, pitch=0.0, abd=0.0, twist=0.0, knee=0.0, d=0.0):
    """d: the thigh slides up into the torso along its axis (hidden by the jacket), shortening the leg."""
    piv = HIP_PIV[side]
    Wu = WT @ T(piv) @ M4(leg_rot(side, pitch, abd, twist)) @ T((0, d, 0)) @ T(-piv) @ REST[UPPER_LEG[side]]
    Wl = Wu @ T(KNEE_LOCAL) @ M4(Rx(-knee)) @ T(-KNEE_LOCAL) @ T((0, -1.0, 0))
    return Wu, Wl


def head_world(WT, pitch=0.0, yaw=0.0, roll=0.0):
    piv = np.array([0.0, 1.0, 0.0])
    return WT @ T(piv) @ M4(Ry(yaw) @ Rx(pitch) @ Rz(roll)) @ T(-piv) @ REST['Head']


def _two_bone(qy, qz, L1, L2, alpha=0.0, sign=1.0):
    """Planar 2-bone IK from the root (origin) to (qy, qz) in the (up, back) plane. Angles from the downward
    vertical, positive forward (towards -z); alpha: angular offset of the end point from the second bone's axis.
    Of the two solutions, keeps the one whose joint angle sign * (a1 - a2) is >= 0 and smallest (knees bend
    forward, elbows backward... and a boot rolling on its toe keeps the straighter knee).
    Returns (a1, a2, reach_ok)."""
    D = max(np.hypot(qy, qz), 1e-6)
    aT = np.arctan2(-qz, -qy)
    cb = (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D)
    ok = -1.0 <= cb <= 1.0
    b = np.arccos(np.clip(cb, -1, 1))
    best = None
    for bend in (1.0, -1.0):
        a1 = aT + bend * b
        ky, kz = -L1 * np.cos(a1), -L1 * np.sin(a1)
        a2 = np.arctan2(-(qz - kz), -(qy - ky)) + alpha
        j = sign * (a1 - a2)
        j = (j + np.pi) % (2 * np.pi) - np.pi
        key = (j < -1e-3, abs(j))
        if best is None or key < best[0]:
            best = (key, a1, a2)
    return best[1], best[2], ok


def arm_ik(WT, side, target, elbow_up=False, twist=0.0):
    """Shoulder pitch / abduction and elbow flexion putting the fingertips (lower-arm local (0, -0.5, 0)) on
    `target` (rig space). The elbow bends forward (flexion), the upper arm keeps its lateral offset."""
    s = SIDES[side]
    piv = apply(WT, SH_PIV[side])
    v = WT[:3, :3].T @ (np.asarray(target, float) - piv)
    off = s * 0.3                                       # pivot -> elbow lateral offset (upper arm frame)
    R_ = np.hypot(v[0], v[1])
    ph0 = np.arctan2(v[1], v[0])
    a = np.arccos(np.clip(off / max(R_, 1e-6), -1, 1))
    cands = [ph0 + a, ph0 - a]
    th = min(cands, key=lambda t: abs((t + np.pi) % (2 * np.pi) - np.pi))
    q = Rz(-np.degrees(th)) @ v
    a_u, a_f, ok = _two_bone(q[1], q[2], 0.66, L_FORE, sign=-1.0)
    return dict(pitch=float(np.degrees(a_u)), abd=float(np.degrees(th) * s), twist=twist,
                elbow=float(np.degrees(a_f - a_u))), ok


def _frame(a, b):
    """Orthonormal frame (columns): a, then b made perpendicular to a, then a x b."""
    a = a / np.linalg.norm(a)
    b = b - (b @ a) * a
    b = b / np.linalg.norm(b)
    return np.column_stack([a, b, np.cross(a, b)])


def arm_world_pole(WT, side, target, pole):
    """Arm whose fingertips reach `target` (rig space) with the elbow turned towards `pole` (torso-frame direction).
    The shoulder rotation is built directly instead of through pitch / abduction angles (limb_rot), which are
    singular when the arm points straight forward: hands on a ladder stay smooth and the elbows keep pointing down.
    Returns ((upper arm, lower arm) world poses, reach_ok)."""
    s = SIDES[side]
    P = SH_PIV[side]
    v = WT[:3, :3].T @ (np.asarray(target, float) - apply(WT, P))      # shoulder pivot -> fingertips (torso frame)
    e0 = np.array([s * 0.3, -0.66, 0.0])                                # shoulder pivot -> elbow (upper arm frame)
    # |e0 + Rx(e) (0, -L_FORE, 0)|^2 = |e0|^2 + L_FORE^2 + 2 * 0.66 * L_FORE * cos(e)
    ce = (v @ v - e0 @ e0 - L_FORE ** 2) / (2 * 0.66 * L_FORE)
    ok = -1.0 <= ce <= 1.0
    elbow = float(np.degrees(np.arccos(np.clip(ce, -1.0, 1.0))))
    f = e0 + Rx(elbow) @ np.array([0.0, -L_FORE, 0.0])                 # fingertips in the upper arm frame
    R = _frame(v, np.asarray(pole, float) * np.array([s, 1.0, 1.0])) @ _frame(f, e0).T
    Wu = WT @ T(P) @ M4(R) @ T(-P) @ REST[UPPER_ARM[side]]
    Wl = Wu @ T(ELBOW_LOCAL) @ M4(Rx(elbow)) @ T(-ELBOW_LOCAL) @ T((0, -1.0, 0))
    return (Wu, Wl), ok


def _uvec(a):
    """Downward unit vector tilted forward by angle a (radians) in the (up, back) plane."""
    return np.array([-np.cos(a), -np.sin(a)])


def _angles_from_points(WT, side, H, K, A):
    """Torso-frame leg angles reproducing exactly the world points hip pivot H, knee pivot K and shin bottom
    centre A: the thigh direction gives pitch / abduction, its length the telescoping d = L_THIGH - |K - H|,
    and the shin direction gives the knee flexion and the thigh twist (which keeps the knee plane, hence
    the boot, aligned with where the foot is planted)."""
    s = SIDES[side]
    Rt = WT[:3, :3].T
    t = Rt @ (K - H)
    ell = np.linalg.norm(t)
    t = t / ell
    th = np.arcsin(np.clip(t[0], -1, 1))                          # abduction (thigh direction = Rx(p) Rz(th) (0,-1,0))
    pt = np.arctan2(-t[2], -t[1])                                  # pitch over the full circle
    sd = Rt @ (A - K)
    sd = sd / np.linalg.norm(sd)
    sl = (Rx(np.degrees(pt)) @ Rz(np.degrees(th))).T @ sd          # shin in the thigh frame (before twist)
    kn = np.arccos(np.clip(-sl[1], -1, 1))
    tw = np.arctan2(sl[0], sl[2]) if kn > 1e-4 else 0.0
    if abs(tw) > np.pi / 2:
        # the shin is a hair ahead of the thigh (knee just past straight, standing legs): atan2 would twist the
        # thigh by a half turn and point the boot backward; keep it forward with a tiny hyperextension instead
        tw -= np.copysign(np.pi, tw)
        kn = -kn
    return dict(pitch=float(np.degrees(pt)), abd=float(np.degrees(th) * s), twist=float(np.degrees(tw) * s),
                knee=float(np.degrees(kn)), d=float(L_THIGH - ell))


def _snap(WT, side, ang, want=GROUND):
    """Telescope the thigh so the lowest point of the boot is exactly at height `want` (d stays >= 0)."""
    for _ in range(3):
        Wu, Wl = leg_world(WT, side, **ang)
        err = lowest(Wl, LOWER_LEG[side]) - want
        ay = Wu[1, 1]
        if abs(err) < 1e-4 or ay < 0.2:
            break
        ang['d'] = max(0.0, ang['d'] - err / ay)
    return ang


def solve_rocker(WT, side, C, zs, knee):
    """Planted boot resting on its sole edge zs (+HEEL / -TOE) at ground point C (rig space), with the knee
    bent by about `knee` degrees. The boot stays in the vertical plane through C (pointing forward); its
    tilt is solved so the chain hip -> knee -> boot reaches C, and the thigh telescopes to fit.
    Returns (angles, boot tilt in degrees (+ = boot ahead of the knee, heel down), ok)."""
    H = apply(WT, HIP_PIV[side])
    k = np.radians(knee)
    h2 = np.array([H[1], H[2]])
    c2 = np.array([C[1], C[2]])

    def knee_pt(fs):
        A = c2 - zs * np.array([-np.sin(fs), np.cos(fs)])
        return A, A + L_SHIN * np.array([np.cos(fs), np.sin(fs)])

    def g(fs):
        _, K = knee_pt(fs)
        v = K - h2
        return (np.arctan2(-v[1], -v[0]) - (fs + k) + np.pi) % (2 * np.pi) - np.pi
    grid = np.radians(np.linspace(-80, 80, 161))
    vals = [g(x) for x in grid]
    root = None
    for i in range(len(grid) - 1):
        if vals[i] == 0 or (vals[i] * vals[i + 1] < 0 and abs(vals[i] - vals[i + 1]) < 1.0):
            a, b = grid[i], grid[i + 1]
            for _ in range(36):
                m = 0.5 * (a + b)
                if g(a) * g(m) <= 0:
                    b = m
                else:
                    a = m
            r = 0.5 * (a + b)
            ell = np.linalg.norm(knee_pt(r)[1] - h2)
            if 0.45 <= ell <= L_THIGH + 0.4 and (root is None or abs(r) < abs(root)):
                root = r
    found = root is not None
    if not found:
        root = 0.0
    A2, K2 = knee_pt(root)
    A = np.array([C[0], A2[0], A2[1]])
    K = np.array([C[0], K2[0], K2[1]])
    K[0] = A[0] + (H[0] - A[0]) * (K[1] - A[1]) / max(H[1] - A[1], 1e-3)
    ang = _angles_from_points(WT, side, H, K, A)
    ok = found and ang['d'] >= -1e-3
    ang['d'] = max(0.0, ang['d'])
    return _snap(WT, side, ang), (float(np.degrees(root)) if found else None), ok


def solve_rocker_ik(WT, side, C, zs):
    """Planted boot on its sole edge zs at ground point C, the knee solved by 2-bone IK (no telescoping):
    for deep-knee gaits (crouch walk). Returns (angles, boot tilt in degrees, ok)."""
    H = apply(WT, HIP_PIV[side])
    q = np.array([C[1] - H[1], C[2] - H[2]])
    a_t, a_s, ok = _two_bone(q[0], q[1], L_THIGH, np.hypot(L_SHIN, zs), alpha=np.arctan2(zs, L_SHIN), sign=1.0)
    K2 = np.array([H[1], H[2]]) + L_THIGH * _uvec(a_t)
    A2 = K2 + L_SHIN * _uvec(a_s)
    A = np.array([C[0], A2[0], A2[1]])
    K = np.array([C[0], K2[0], K2[1]])           # shin upright sideways: the boot sole stays level
    ang = _angles_from_points(WT, side, H, K, A)
    ang['d'] = max(0.0, ang['d'])
    return _snap(WT, side, ang), float(np.degrees(a_s)), ok


def solve_flat(WT, side, foot, upright=False):
    """Planted boot lying flat (shin vertical, boot pointing forward) with its sole centre at `foot`
    (rig space, y = ground). The shin leans sideways towards the hip, unless `upright`: then the knee is right
    above the boot and the sole stays level, as in the crouch walk (wide, deep stances, where the leaning shin
    rolled the boot onto its inner edge, which sank into the ground)."""
    H = apply(WT, HIP_PIV[side])
    A = np.array([foot[0], foot[1], foot[2]], float)
    K = A + np.array([0.0, L_SHIN, 0.0])
    if not upright:
        K[0] = A[0] + (H[0] - A[0]) * (K[1] - A[1]) / max(H[1] - A[1], 1e-3)
    ang = _angles_from_points(WT, side, H, K, A)
    ok = ang['d'] >= -1e-3
    ang['d'] = max(0.0, ang['d'])
    return _snap(WT, side, ang, foot[1]), ok


def build(root, head=None, arms=None, legs=None, ground='feet', clamp=True, clamp_all=False):
    """Pose the rig. arms[side]: dict(pitch, abd, twist, elbow) or dict(hand=(x, y, z)) (IK);
    legs[side]: dict(pitch, abd, twist, knee, d) or dict(foot=(x, y, z)) (boot flat on the ground there, shin vertical).
    ground='feet': the feet carry the body (clamp keeps the torso, head and arms above the ground);
    'body': the whole body rests on the ground (lowest point of all parts put on the ground)."""
    head = head or {}
    arms = arms or {}
    legs = legs or {}
    WT = torso_world(root)
    world = {'Torso': WT, 'Head': head_world(WT, **head)}
    for side in SIDES:
        a = dict(arms.get(side, {}))
        if 'hand' in a:
            ang, _ = arm_ik(WT, side, a.pop('hand'), twist=a.get('twist', 0.0))
            a = ang
        world[UPPER_ARM[side]], world[LOWER_ARM[side]] = arm_world(WT, side, **a)
    for side in SIDES:
        L = dict(legs.get(side, {}))
        if 'foot' in L:
            ang, _ = solve_flat(WT, side, L['foot'], L.get('upright', False))
        else:
            ang = {k: L.get(k, 0.0) for k in ('pitch', 'abd', 'twist', 'knee', 'd')}
        world[UPPER_LEG[side]], world[LOWER_LEG[side]] = leg_world(WT, side, **ang)
    if clamp:
        if ground == 'body':
            names = PARTS
        elif clamp_all:
            names = PARTS
        else:
            names = ('Torso', 'Head') + tuple(UPPER_ARM.values()) + tuple(LOWER_ARM.values())
        low = min(lowest(world[n], n) for n in names)
        if ground == 'body' or low < GROUND:
            lift = T((0, GROUND - low, 0))
            world = {k: lift @ v for k, v in world.items()}
    return world


# ----------------------------------------------------------------------------------------------
# curves

def _hermite(p0, p1, m0, m1, t):
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1


def cyc(phase, keys):
    """Periodic smooth curve (non-uniform Catmull-Rom) through (phase, value) keys, phase in [0, 1)."""
    ks = sorted(keys)
    P = np.array([k[0] for k in ks], float)
    V = np.array([k[1] for k in ks], float)
    n = len(ks)
    ph = phase % 1.0
    i = int(np.searchsorted(P, ph, side='right')) - 1
    Pi = P[i] if i >= 0 else P[-1] - 1.0
    i %= n
    j = (i + 1) % n
    Pj = P[j] if j > i else P[j] + 1.0
    if Pi > ph:
        Pi -= 1.0
    if Pj < ph:
        Pj += 1.0
    h = Pj - Pi

    def tangent(k):
        kp, kn = (k - 1) % n, (k + 1) % n
        pp = P[kp] if kp < k else P[kp] - 1.0
        pn = P[kn] if kn > k else P[kn] + 1.0
        return (V[kn] - V[kp]) / (pn - pp)
    t = (ph - Pi) / h
    return float(_hermite(V[i], V[j], tangent(i) * h, tangent(j) * h, t))


def curve(t, keys):
    """Non-periodic smooth curve through (time, value) keys, flat at both ends, monotone between keys
    (Fritsch-Carlson): no overshoot, so a limb never swings past its key poses."""
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


def window(ph, a, b, soft=0.04):
    """Smooth periodic window: 1 on [a, b], 0 outside, soft edges."""
    ph = ph % 1.0

    def sm(x):
        x = np.clip(x, 0, 1)
        return x * x * (3 - 2 * x)
    best = 0.0
    for off in (-1.0, 0.0, 1.0):
        x = ph + off
        best = max(best, sm((x - (a - soft)) / soft) * sm(((b + soft) - x) / soft))
    return best


def c(ph, amp, k=1.0, off=0.0):
    return amp * np.cos(2 * np.pi * (k * ph - off))


def s_(ph, amp, k=1.0, off=0.0):
    return amp * np.sin(2 * np.pi * (k * ph - off))


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------------------------------------
# clips

class Clip:
    def __init__(self, key, name, length, fn, loop=True, priority='Movement', fps=30, speed=None, label='',
                 ground='feet', parts=None):
        self.key, self.name, self.length, self.fn, self.loop = key, name, length, fn, loop
        self.priority, self.fps, self.speed, self.label, self.ground = priority, fps, speed, label, ground
        self.parts = tuple(parts) if parts else PARTS        # parts keyed in Roblox (partial clips: an overlay)

    def world(self, t):
        return self.fn(t)


# --- locomotion: planted, rolling boots, bending knees -------------------------------------------------
SWING_CLEAR = 0.05                        # minimum height of the swinging boot above the ground (mid-swing)
SWING_SLIDE = 0.3                         # max slide of the swinging thigh into the torso (the stance uses up to 0.4)


class Gait:
    """Cyclic locomotion whose boots never slide. During stance a sole edge rests on a ground point moving
    backward at exactly `v` studs/s (the speed the clip is made for, at playback rate 1): the boot rolls over
    its heel edge, then over its toe edge once the sole is flat (a rigid boot rolls heel to toe), the knee
    follows a natural flexion curve (knee_stance(p)) and the thigh telescopes a little inside the jacket so
    the chain fits exactly. During the swing the thigh angle follows a Hermite curve matching the stance
    angles and speeds at toe-off and heel strike, and the knee folds up to `knee_peak`.
    root(ph), arms(ph, root), head(ph, root) give the upper body for the cycle phase ph in [0, 1)."""

    def __init__(self, T_, v, duty, flat, root, arms, head, foot_x=0.55, knee_stance=(8.0, 10.0),
                 knee_peak=60.0, peak_at=0.38, mode='knee'):
        self.T, self.v, self.duty, self.flat, self.mode = T_, v, duty, flat, mode
        self.root_fn, self.arms_fn, self.head_fn = root, arms, head
        self.foot_x, self.knee_peak, self.peak_at = foot_x, knee_peak, peak_at
        self.k0, self.k1 = knee_stance
        self.travel = v * duty * T_
        self.y_off = 0.0
        self._tune()

    def root(self, ph):
        r = dict(self.root_fn(ph % 1.0))
        r['y'] = r.get('y', 0.0) + self.y_off
        return r

    def phase(self, ph, side):
        return (ph - (0.0 if side == 'Right' else 0.5)) % 1.0

    def knee_stance(self, p):
        return self.k0 + self.k1 * np.sin(np.pi * np.clip(p / self.duty, 0, 1))

    def contact(self, ph, side, p):
        """Stance at foot phase p (0 = heel strike): (leg angles, contact point, edge, ok)."""
        s = SIDES[side]
        WT_s = torso_world(self.root(ph - p))
        hz_s = apply(WT_s, HIP_PIV[side])[2]
        cz = hz_s - (self.flat * self.travel - HEEL) + self.v * self.T * p     # heel contact, moving with the ground
        WT = torso_world(self.root(ph))
        C = np.array([s * self.foot_x, GROUND, cz])
        kn = self.knee_stance(p)
        solve = (lambda C_, zs: solve_rocker(WT, side, C_, zs, kn)) if self.mode == 'knee' else \
            (lambda C_, zs: solve_rocker_ik(WT, side, C_, zs))
        ang, tilt, ok = solve(C, HEEL)
        edge = HEEL
        if tilt is None or tilt < 0:                        # sole flat (or heel out of reach): roll over the toe
            C = C - np.array([0, 0, HEEL + TOE])
            ang, tilt, ok = solve(C, -TOE)
            edge = -TOE
        return ang, C, edge, ok

    def leg(self, ph, side, WT):
        p = self.phase(ph, side)
        if p < self.duty:
            ang, C, edge, ok = self.contact(ph, side, p)
            return leg_world(WT, side, **ang), ang
        u = (p - self.duty) / (1 - self.duty)
        ang = self._swing(ph, side, p, u)
        us, slide, lift = self._lift_profile(side)
        dx, e = float(np.interp(u, us, slide)), float(np.interp(u, us, lift))
        ang = dict(ang, d=ang['d'] + dx, pitch=ang['pitch'] + e, knee=ang['knee'] + e)
        return leg_world(WT, side, **ang), ang

    def _lift_profile(self, side):
        """The boot has no ankle: as the shin swings forward the toe drops and would scrape through the floor
        before heel strike. To keep the sole SWING_CLEAR * sin(pi u) above the ground, the swinging thigh first
        slides into the torso (hidden by the jacket, as during the stance) by up to SWING_SLIDE, then the knee is
        lifted (hip and knee flexed by the same angle, so the boot keeps its tilt) for what is left: crouched
        gaits, whose thighs are too flat for the slide to raise the boot. Both corrections are solved on a grid
        over the swing, then widened and smoothed (they build up and settle gradually, never less than needed)
        and faded out at toe-off and heel strike. Returns (u grid, slide grid, lift grid in degrees), cached."""
        cache = self.__dict__.setdefault('_lift', {})
        if side in cache:
            return cache[side]
        n, w = 200, 0.08
        us = np.linspace(0.0, 1.0, n + 1)
        need_d, need_e = np.zeros(n + 1), np.zeros(n + 1)
        off = 0.0 if side == 'Right' else 0.5
        for i, u in enumerate(us):
            p = self.duty + u * (1 - self.duty)
            ph = (p + off) % 1.0
            WT = torso_world(self.root(ph))
            ang = self._swing(ph, side, p, u)
            want = GROUND + SWING_CLEAR * np.sin(np.pi * u)

            def low(dx, e):
                a = dict(ang, d=ang['d'] + dx, pitch=ang['pitch'] + e, knee=ang['knee'] + e)
                return lowest(leg_world(WT, side, **a)[1], LOWER_LEG[side])
            if low(0.0, 0.0) >= want:
                continue
            ay = leg_world(WT, side, **ang)[0][1, 1]          # how much the slide raises the boot
            dx = 0.0
            if ay > 0.5:
                for _ in range(4):
                    err = low(dx, 0.0) - want
                    if err >= -1e-4 or dx >= SWING_SLIDE:
                        break
                    dx = min(SWING_SLIDE, dx - err / ay)
            need_d[i] = dx
            if low(dx, 0.0) >= want - 1e-4:
                continue
            lo_e, hi_e = 0.0, 45.0
            for _ in range(30):
                m = 0.5 * (lo_e + hi_e)
                if low(dx, m) >= want:
                    hi_e = m
                else:
                    lo_e = m
            need_e[i] = hi_e
        k = int(round(w * n))
        tri = np.concatenate([np.arange(1, k + 1), np.arange(k + 1, 0, -1)]).astype(float)
        tri /= tri.sum()
        fade = smooth01(us / 0.12) * smooth01((1.0 - us) / 0.12)

        def smooth(need):
            wide = np.array([need[max(0, i - k):i + k + 1].max() for i in range(n + 1)])
            return np.convolve(np.pad(wide, k, mode='edge'), tri, mode='valid') * fade
        cache[side] = (us, smooth(need_d), smooth(need_e))
        return cache[side]

    def _swing(self, ph, side, p, u):
        """Swing leg angles (before the ground clearance lift)."""
        t_o, t_n, e = ph - (p - self.duty), ph + (1 - p), 1e-3
        a_o = self.contact(t_o, side, self.duty)[0]
        a_o2 = self.contact(t_o - e, side, self.duty - e)[0]
        a_n = self.contact(t_n, side, 0.0)[0]
        a_n2 = self.contact(t_n + e, side, e)[0]
        span = 1 - self.duty
        d_ = lambda k: ((a_o[k] - a_o2[k]) / e * span, (a_n2[k] - a_n[k]) / e * span)
        mo, mn = d_('pitch')
        pitch = _hermite(a_o['pitch'], a_n['pitch'], mo, mn, u)
        abd = a_o['abd'] + (a_n['abd'] - a_o['abd']) * smooth01(u)
        mko, mkn = d_('knee')
        pk = self.peak_at
        if u < pk:
            knee = _hermite(a_o['knee'], self.knee_peak, mko * pk, 0.0, u / pk)
        else:
            knee = _hermite(self.knee_peak, a_n['knee'], 0.0, mkn * (1 - pk), (u - pk) / (1 - pk))
        mdo, mdn = d_('d')
        dd = max(0.0, _hermite(a_o['d'], a_n['d'], mdo, mdn, u))
        return dict(pitch=pitch, abd=abd, twist=0.0, knee=max(0.0, knee), d=dd)

    def world(self, t):
        ph = (t / self.T) % 1.0
        root = self.root(ph)
        WT = torso_world(root)
        world = {'Torso': WT, 'Head': head_world(WT, **self.head_fn(ph, root))}
        arms = self.arms_fn(ph, root)
        for side in SIDES:
            world[UPPER_ARM[side]], world[LOWER_ARM[side]] = arm_world(WT, side, **arms[side])
        for side in SIDES:
            (world[UPPER_LEG[side]], world[LOWER_LEG[side]]), _ = self.leg(ph, side, WT)
        return world

    def _tune(self):
        """Lower the body until every planted leg reaches the ground (the thigh may only slide in, not out)."""
        for _ in range(12):
            worst = 0.0
            for ph in np.linspace(0, 1, 60, endpoint=False):
                for side in SIDES:
                    p = self.phase(ph, side)
                    if p < self.duty:
                        WT = torso_world(self.root(ph))
                        ang, C, edge, ok = self.contact(ph, side, p)
                        # residual: how far the boot misses the ground when the thigh is fully out
                        Wu, Wl = leg_world(WT, side, **ang)
                        worst = max(worst, lowest(Wl, LOWER_LEG[side]) - GROUND)
            if worst <= 2e-3:
                break
            self.y_off -= worst + 0.003


def _arms(ph, base, amp, abd, abd_amp, elbow, elbow_amp, lag, twist=0.0):
    """Arms swing against the legs (the left arm is forward at the right heel strike, ph = 0); the elbow
    bends more on the forward swing."""
    out = {}
    for side, off in (('Right', 0.5), ('Left', 0.0)):
        sw = c(ph, 1.0, off=off + lag)
        out[side] = dict(pitch=base + amp * sw, abd=abd - abd_amp * sw, twist=twist,
                         elbow=elbow + elbow_amp * max(0.0, sw) - 0.25 * elbow_amp * max(0.0, -sw))
    return out


# --- walk: 0.7 s cycle, 6 studs/s ----------------------------------------------------------------------
WALK_DUTY = 0.58
WALK = Gait(
    0.7, 6.0, WALK_DUTY, 0.45, knee_stance=(7.0, 11.0), knee_peak=62.0, peak_at=0.36,
    root=lambda ph: dict(x=c(ph, 0.045, off=WALK_DUTY / 2), y=-0.03 + c(ph, 0.035, 2, WALK_DUTY / 2), z=0.0,
                         lean=4.0 + c(ph, 1.0, 2, 0.1), tilt=s_(ph, 2.0), yaw=-c(ph, 4.5, off=0.03)),
    arms=lambda ph, r: _arms(ph, 5.0, 25.0, 6.0, 2.0, 16.0, 18.0, 0.035),
    head=lambda ph, r: dict(pitch=3.0 + c(ph, 1.0, 2, 0.2), yaw=-0.65 * r['yaw'], roll=-0.5 * r['tilt']))


def walk(t):
    return WALK.world(t)


# --- run: 0.56 s cycle with a flight phase, 16 studs/s ------------------------------------------------------
RUN_DUTY = 0.31
RUN = Gait(
    0.56, 16.0, RUN_DUTY, 0.40, knee_stance=(20.0, 22.0), knee_peak=112.0, peak_at=0.42,
    root=lambda ph: dict(x=c(ph, 0.035, off=RUN_DUTY / 2), y=-0.12 - c(ph, 0.09, 2, RUN_DUTY / 2), z=0.0,
                         lean=13.0 + c(ph, 2.0, 2, 0.2), tilt=s_(ph, 2.5), yaw=-c(ph, 9.0, off=0.02)),
    arms=lambda ph, r: _arms(ph, 12.0, 42.0, 10.0, 5.0, 82.0, 14.0, 0.03),
    head=lambda ph, r: dict(pitch=10.0 + c(ph, 1.5, 2), yaw=-0.7 * r['yaw'], roll=-0.6 * r['tilt']))


def run(t):
    return RUN.world(t)


# --- crouch walk: wide, low, 1.0 s cycle, 2.6 studs/s ---------------------------------------------------------
CW_DUTY = 0.62
CROUCH_WALK = Gait(
    1.0, 2.6, CW_DUTY, 0.45, foot_x=0.68, knee_peak=118.0, peak_at=0.42, mode='ik',
    root=lambda ph: dict(x=c(ph, 0.05, off=CW_DUTY / 2), y=-0.62 + c(ph, 0.025, 2, CW_DUTY / 2), z=0.06,
                         lean=24.0 + c(ph, 1.5, 2, 0.1), tilt=s_(ph, 3.0), yaw=-c(ph, 5.0, off=0.03)),
    arms=lambda ph, r: _arms(ph, 26.0, 10.0, 8.0, 2.0, 62.0, 6.0, 0.04),
    head=lambda ph, r: dict(pitch=21.0 + c(ph, 1.0, 2, 0.2), yaw=-0.7 * r['yaw'], roll=-0.5 * r['tilt']))


def crouch_walk(t):
    return CROUCH_WALK.world(t)


# --- idle: breathing, weight shift, looking around (feet planted, knees soft) ------------------------------------
STAND_FEET = {'Right': (0.56, GROUND, -0.14), 'Left': (-0.56, GROUND, -0.02)}   # both a bit ahead of the hips: soft
                                                                                 # knees, never hyperextended


def idle(t):
    L = 4.0
    ph, br = t / L, t / 2.0
    root = dict(x=s_(ph, 0.05), y=s_(br, 0.010, off=0.1) - 0.07 - 0.02 * (0.5 - 0.5 * np.cos(4 * np.pi * ph)),
                z=0.0, lean=2.0 + s_(br, 0.6, off=0.15), tilt=s_(ph, 1.3), yaw=s_(ph, 2.5, off=0.85))
    look = cyc(ph, [(0.0, 0), (0.22, 0), (0.33, 17), (0.50, 15), (0.60, 2), (0.74, -10), (0.86, -8), (0.96, 0)])
    head = dict(pitch=1.5 + s_(br, 1.0, off=0.35) + cyc(ph, [(0.0, 0), (0.33, -3), (0.6, 0), (0.8, 2)]),
                yaw=look - 0.6 * root['yaw'], roll=-0.5 * root['tilt'])
    arms = {side: dict(pitch=4 + s_(br, 1.4, off=0.25 + 0.05 * k) + s_(ph, 1.0, off=0.6),
                       abd=5.0 + s_(br, 0.9, off=0.2) + SIDES[side] * s_(ph, 0.8, off=0.62), twist=4.0,
                       elbow=13.0 + s_(br, 2.0, off=0.3 + 0.1 * k))
            for k, side in enumerate(SIDES)}
    legs = {s: dict(foot=f) for s, f in STAND_FEET.items()}
    return build(root, head, arms, legs)


# --- crouch idle: deep knee bend, alert ----------------------------------------------------------------------------
CROUCH_FEET = {'Right': (0.72, GROUND, -0.45), 'Left': (-0.66, GROUND, 0.25)}


def crouch_idle(t):
    L = 3.0
    ph, br = t / L, t / 1.5
    root = dict(x=s_(ph, 0.02), y=-0.86 + s_(br, 0.012), z=0.05, lean=26.0 + s_(br, 0.7, off=0.1),
                tilt=s_(ph, 0.8), yaw=s_(ph, 2.0, off=0.7))
    look = cyc(ph, [(0.0, 0), (0.25, -14), (0.50, -12), (0.70, 10), (0.88, 9)])
    head = dict(pitch=22 + s_(br, 0.8, off=0.3), yaw=look - 0.6 * root['yaw'], roll=-0.4 * root['tilt'])
    arms = {'Right': dict(pitch=34 + s_(br, 1.5, off=0.2), abd=8 + s_(br, 0.6), twist=6, elbow=58 + s_(br, 2.0)),
            'Left': dict(pitch=28 + s_(br, 1.5, off=0.25), abd=10 + s_(br, 0.6), twist=6, elbow=50 + s_(br, 2.0, off=0.2))}
    # the wide front (right) boot keeps its sole level, its knee right above it (leaning towards the hip, the shin
    # rolled it onto its inner edge, 0.08 stud into the ground); the folded back leg keeps its toes forward
    legs = {s: dict(foot=f, upright=(s == 'Right')) for s, f in CROUCH_FEET.items()}
    return build(root, head, arms, legs)


# --- prone ("allongé"): chest on the ground, forearms flat in front, head up ------------------------------------
PRONE_ROOT = dict(x=0.0, y=-2.45, z=0.35, lean=86.0)
PRONE_ARMS = {'Right': dict(pitch=152.7, abd=-37.0, twist=92.2, elbow=79.8),      # forearms flat, hands in front
              'Left': dict(pitch=152.7, abd=-37.0, twist=92.2, elbow=79.8)}
PRONE_LEGS = {'Right': dict(pitch=-4.0, abd=7.0, twist=4.0, knee=10.0),
              'Left': dict(pitch=-4.0, abd=11.0, twist=-3.0, knee=6.0)}


def prone_idle(t):
    L = 4.0
    ph, br = t / L, t / 2.5
    root = dict(PRONE_ROOT, y=PRONE_ROOT['y'] + s_(br, 0.008), lean=PRONE_ROOT['lean'] + s_(br, 0.5),
                tilt=s_(ph, 1.0, off=0.3), yaw=s_(ph, 1.5, off=0.6))
    look = cyc(ph, [(0.0, 0), (0.3, 14), (0.55, 12), (0.75, -8), (0.9, -6)])
    head = dict(pitch=72 + s_(br, 1.0, off=0.3) + cyc(ph, [(0.0, 0), (0.3, -3), (0.6, 0)]),
                yaw=look - 0.5 * root['yaw'], roll=-0.5 * root['tilt'])
    arms = {side: dict(a, pitch=a['pitch'] + s_(br, 0.6, off=0.1 * k), elbow=a['elbow'] + s_(ph, 2.0, off=0.3 * k))
            for k, (side, a) in enumerate(PRONE_ARMS.items())}
    legs = {'Right': dict(PRONE_LEGS['Right'], abd=PRONE_LEGS['Right']['abd'] + s_(ph, 1.5, off=0.2),
                          knee=PRONE_LEGS['Right']['knee'] + s_(ph, 3.0)),
            'Left': dict(PRONE_LEGS['Left'], abd=PRONE_LEGS['Left']['abd'] + s_(ph, 1.5, off=0.7),
                         knee=PRONE_LEGS['Left']['knee'] - s_(ph, 3.0))}
    return build(root, head, arms, legs, ground='body')


# --- crawl ("ramper", army crawl): forearm planted and pulled back while the arm sweeps to the side, then lifted
# and brought forward; the opposite knee draws up and pushes. Arm keys (pitch, abd, twist, elbow) were solved
# offline so the elbow and forearm rest on the ground and follow it during the pull.
CRAWL_ARM_KEYS = [(0.0000, (154.6, -24.7, 82.6, 59.7)),
                  (0.0357, (154.2, -24.6, 83.1, 61.6)),
                  (0.0714, (154.0, -24.9, 84.0, 63.7)),
                  (0.1071, (153.9, -25.6, 85.3, 66.3)),
                  (0.1429, (153.9, -27.3, 87.1, 69.8)),
                  (0.1786, (154.1, -30.2, 89.5, 74.8)),
                  (0.2143, (154.6, -34.3, 92.6, 81.1)),
                  (0.2500, (155.4, -39.8, 96.2, 88.8)),
                  (0.2857, (156.5, -46.5, 100.0, 97.4)),
                  (0.3214, (157.9, -54.3, 104.0, 106.5)),
                  (0.3571, (159.4, -63.2, 108.0, 115.8)),
                  (0.3929, (160.8, -73.2, 112.2, 125.0)),
                  (0.4286, (161.8, -84.2, 116.8, 133.9)),
                  (0.4643, (165.5, -92.2, 119.4, 139.5)),
                  (0.5000, (172.3, -90.9, 113.3, 137.7)),
                  (0.5357, (177.1, -86.8, 105.9, 132.4)),
                  (0.5714, (179.8, -81.9, 100.8, 125.5)),
                  (0.6071, (181.0, -76.8, 97.3, 118.1)),
                  (0.6429, (181.4, -71.7, 95.0, 110.7)),
                  (0.6786, (181.0, -66.9, 93.4, 103.7)),
                  (0.7143, (180.2, -62.3, 92.4, 97.5)),
                  (0.7500, (178.8, -58.1, 91.7, 92.1)),
                  (0.7857, (176.8, -53.9, 91.4, 87.3)),
                  (0.8214, (174.2, -49.7, 91.1, 83.0)),
                  (0.8571, (170.9, -45.4, 90.7, 78.8)),
                  (0.8929, (166.8, -40.6, 89.8, 74.4)),
                  (0.9286, (162.1, -35.4, 88.0, 69.5)),
                  (0.9643, (157.0, -29.7, 84.9, 64.3))]
CRAWL_T = 1.4


def crawl(t):
    ph = t / CRAWL_T
    root = dict(x=s_(ph, 0.04), y=PRONE_ROOT['y'] + 0.02 * (0.5 + 0.5 * np.cos(4 * np.pi * (ph - 0.15))),
                z=PRONE_ROOT['z'] + s_(ph, 0.04, 2, 0.1), lean=PRONE_ROOT['lean'], tilt=s_(ph, 6.0, off=0.05),
                yaw=s_(ph, 4.0, off=0.1))
    arms, legs = {}, {}
    for side, off in (('Right', 0.0), ('Left', 0.5)):
        p = ph - off
        vals = [cyc(p, [(k, a[i]) for k, a in CRAWL_ARM_KEYS]) for i in range(4)]
        arms[side] = dict(pitch=vals[0], abd=vals[1], twist=vals[2], elbow=vals[3])
    for side, off in (('Left', 0.0), ('Right', 0.5)):     # contralateral: left knee draws up with the right arm pull
        p = ph - off
        # frog leg: the thigh turns out (twist) so the knee folds flat along the ground, the inner side of the boot down
        legs[side] = dict(pitch=cyc(p, [(0.0, -5), (0.25, -3), (0.45, -1), (0.7, -3), (0.88, -6)]),
                          abd=cyc(p, [(0.0, 8), (0.25, 24), (0.45, 36), (0.7, 20), (0.88, 8)]),
                          twist=cyc(p, [(0.0, 6), (0.22, 62), (0.45, 84), (0.7, 58), (0.9, 8)]),
                          knee=cyc(p, [(0.0, 8), (0.25, 48), (0.45, 84), (0.7, 40), (0.88, 10)]))
    head = dict(pitch=70 + c(ph, 1.0, 2), yaw=-0.8 * root['yaw'], roll=-0.7 * root['tilt'])
    return build(root, head, arms, legs, ground='body')


# --- jump / fall / land ------------------------------------------------------------------------------------------
def jump(t):
    k = lambda keys: curve(t, keys)
    root = dict(y=k([(0, -0.05), (0.12, 0.04), (0.5, 0.04)]), lean=k([(0, 8), (0.14, -4), (0.5, -2)]),
                yaw=k([(0, 0), (0.2, -4), (0.5, -3)]))
    # arms swing up into a V above the shoulders (arm raised: a negative abduction takes the hand outward)
    arms = {'Right': dict(pitch=k([(0, -24), (0.16, 152), (0.5, 146)]), abd=k([(0, 8), (0.16, -20), (0.5, -18)]),
                          elbow=k([(0, 20), (0.16, 14), (0.5, 18)])),
            'Left': dict(pitch=k([(0, -28), (0.16, 134), (0.5, 128)]), abd=k([(0, 8), (0.16, -24), (0.5, -22)]),
                         elbow=k([(0, 22), (0.16, 22), (0.5, 26)]))}
    legs = {'Right': dict(pitch=k([(0, -6), (0.15, 58), (0.5, 50)]), knee=k([(0, 8), (0.15, 96), (0.5, 84)]),
                          abd=3.0),
            'Left': dict(pitch=k([(0, -14), (0.15, 18), (0.5, 14)]), knee=k([(0, 18), (0.15, 72), (0.5, 64)]),
                         abd=3.0)}
    head = dict(pitch=k([(0, -4), (0.15, 6), (0.5, 4)]))
    return build(root, head, arms, legs, clamp=False)


def fall(t):
    ph = t / 0.9
    root = dict(y=0.04, lean=-3 + c(ph, 1.0), tilt=s_(ph, 1.5), yaw=s_(ph, 2.0, off=0.2))
    # arms flung up and out, the forearms bent upward (twist), flailing out of phase
    arms = {side: dict(pitch=12 + c(ph, 8.0, off=0.5 * k + 0.1), abd=112 + s_(ph, 10.0, off=0.5 * k), twist=-58,
                       elbow=36 + c(ph, 12.0, off=0.5 * k + 0.3))
            for k, side in enumerate(SIDES)}
    legs = {'Right': dict(pitch=24 + c(ph, 7.0), knee=40 + c(ph, 8.0, off=0.2), abd=4.0),
            'Left': dict(pitch=-4 - c(ph, 7.0), knee=30 - c(ph, 8.0, off=0.2), abd=4.0)}
    head = dict(pitch=-8 + c(ph, 1.5, off=0.3), yaw=-0.5 * root['yaw'])
    return build(root, head, arms, legs, clamp=False)


LAND_FEET = {'Right': (0.56, GROUND, -0.22), 'Left': (-0.56, GROUND, 0.02)}


def land(t):
    k = lambda keys: curve(t, keys)
    dip = k([(0, -0.02), (0.09, -0.62), (0.22, -0.42), (0.42, -0.07)])
    root = dict(y=dip, lean=k([(0, 2), (0.09, 16), (0.22, 11), (0.42, 3)]))
    # the arms come down from the fall pose (up and out) for balance as the knees absorb the impact
    arms = {side: dict(pitch=k([(0, 14), (0.1, 30), (0.42, 5)]), abd=k([(0, 96), (0.1, 30), (0.42, 6)]),
                       twist=k([(0, -48), (0.1, -10), (0.42, 0)]), elbow=k([(0, 36), (0.1, 30), (0.42, 14)]))
            for side in SIDES}
    legs = {s: dict(foot=f) for s, f in LAND_FEET.items()}
    head = dict(pitch=k([(0, -6), (0.09, 8), (0.42, 2)]))
    return build(root, head, arms, legs)


# --- climb: hands and boots on the rungs of a ladder in front, moving down at the climbing speed -------------------
CLIMB_T, CLIMB_V = 0.45, 5.0              # cycle (s) and climbing speed (studs/s) the clip is made for
CLIMB_Z = -0.95                           # ladder plane in front of the body (rig z)
CLIMB_RUNG = CLIMB_V * CLIMB_T / 2        # rung spacing: a hand grabs a new rung every half cycle
CLIMB_HAND_Y, CLIMB_FOOT_Y = 1.75, -1.78  # fingertips / boot ball when a rung is grabbed (rungs at +0.15 / -0.07)
CLIMB_ELBOW = (0.55, -1.0, 0.2)           # the elbows point down, out and a little back (right side, x mirrored)


def solve_rung(WT, side, C):
    """Boot resting on a rung by the ball of the foot at C (rig space): 2-bone IK, knee forward, no telescoping."""
    H = apply(WT, HIP_PIV[side])
    zs = -TOE + 0.18                                  # ball of the foot, a little behind the toe edge
    q = np.array([C[1] - H[1], C[2] - H[2]])
    a_t, a_s, ok = _two_bone(q[0], q[1], L_THIGH, np.hypot(L_SHIN, zs), alpha=np.arctan2(zs, L_SHIN), sign=1.0)
    K2 = np.array([H[1], H[2]]) + L_THIGH * _uvec(a_t)
    A2 = K2 + L_SHIN * _uvec(a_s)
    ang = _angles_from_points(WT, side, H, np.array([C[0], K2[0], K2[1]]), np.array([C[0], A2[0], A2[1]]))
    ang['d'] = max(0.0, ang['d'])
    return ang, ok


def rung_path(p, duty, y_hi, z, back, x):
    """Hand / boot contact over a climbing cycle: on its rung (moving down at CLIMB_V relative to the body) for
    p < duty, then off the ladder (pulled back by `back`) up to the next rung, leaving and arriving at rung speed."""
    travel = CLIMB_V * duty * CLIMB_T
    if p < duty:
        return np.array([x, y_hi - travel * p / duty, z])
    u = (p - duty) / (1 - duty)
    m = -CLIMB_V * (1 - duty) * CLIMB_T
    return np.array([x, _hermite(y_hi - travel, y_hi, m, m, u), z + back * np.sin(np.pi * u)])


def climb(t):
    ph = t / CLIMB_T
    root = dict(x=s_(ph, 0.03), y=-0.05 + c(ph, 0.04, 2), lean=5.0 + c(ph, 1.0, 2), tilt=s_(ph, 2.0))
    WT = torso_world(root)
    legs = {}
    hands = {side: rung_path((ph - off) % 1.0, 0.6, CLIMB_HAND_Y, CLIMB_Z, 0.35, SIDES[side] * 0.92)
             for side, off in (('Right', 0.0), ('Left', 0.5))}           # right hand with the left boot
    # each boot lands on a rung (3 rungs below the hands' one) slightly after the opposite hand
    f_off = (CLIMB_HAND_Y + 0.15 - 3 * CLIMB_RUNG - (CLIMB_FOOT_Y - 0.07)) / CLIMB_V / CLIMB_T
    for side, off in (('Left', f_off), ('Right', f_off + 0.5)):
        C = rung_path((ph - off) % 1.0, 0.45, CLIMB_FOOT_Y, CLIMB_Z, 0.32, SIDES[side] * 0.52)
        legs[side] = solve_rung(WT, side, C)[0]
    head = dict(pitch=-10 + c(ph, 1.5, 2), yaw=-0.5 * s_(ph, 2.0))
    world = build(root, head, None, legs, clamp=False)
    for side, hand in hands.items():          # hands on the rungs, elbows down (no pitch / abduction singularity)
        (world[UPPER_ARM[side]], world[LOWER_ARM[side]]), _ = arm_world_pole(WT, side, hand, CLIMB_ELBOW)
    return world


# --- sit: thighs on the seat, shins down, hands on the knees ----------------------------------------------------------
# Roblox's SeatWeld puts the HumanoidRootPart centre 0.5 stud above the seat top for this rig (R15 humanoid, measured
# in Studio: C0 (0, 0.5, 0), C1 (0, -0.5, 0)); the hips would be 0.5 below it and the thighs inside the seat. The body
# is lifted 1 stud so the hips are 0.5 above the seat top and the thighs (1 stud thick) rest on it.
SEAT_LIFT = 1.0


def sit(t):
    ph = t / 3.0
    br = t / 1.5
    root = dict(y=SEAT_LIFT + s_(br, 0.008), lean=3.0 + s_(br, 0.5), yaw=s_(ph, 1.5))
    arms = {side: dict(pitch=36 + s_(br, 1.0, off=0.2 * k), abd=10.0, twist=6.0, elbow=44 + s_(br, 1.5))
            for k, side in enumerate(SIDES)}
    legs = {side: dict(pitch=88.0, abd=6.0, knee=90.0) for side in SIDES}
    head = dict(pitch=2 + s_(br, 0.8), yaw=cyc(ph, [(0.0, 0), (0.3, 12), (0.6, -8)]))
    return build(root, head, arms, legs, clamp=False)


# --- tool held in the right hand (overlay on the right arm only) --------------------------------------------------------
def tool(t):
    br = t / 2.0
    W = idle(t)
    WT = W['Torso']
    W[UPPER_ARM['Right']], W[LOWER_ARM['Right']] = arm_world(WT, 'Right', pitch=72 + s_(br, 1.2), abd=4.0, twist=8.0,
                                                             elbow=22 + s_(br, 1.5, off=0.2))
    return W


# --- stance transitions: splines through key poses (angles), feet planted at key poses by IK ------------------------------
def _desc(root, head, arms, legs, ground='feet'):
    """Pose descriptor with IK limbs converted to angles at that key pose."""
    WT = torso_world(root)
    out_l, out_a = {}, {}
    for side, L in legs.items():
        if 'foot' in L:
            ang, _ = solve_flat(WT, side, L['foot'], L.get('upright', False))
            out_l[side] = ang
        else:
            out_l[side] = {k: L.get(k, 0.0) for k in ('pitch', 'abd', 'twist', 'knee', 'd')}
    for side, a in arms.items():
        if 'hand' in a:
            ang, _ = arm_ik(WT, side, a['hand'], twist=a.get('twist', 0.0))
            out_a[side] = ang
        else:
            out_a[side] = {k: a.get(k, 0.0) for k in ('pitch', 'abd', 'twist', 'elbow')}
    return dict(root=dict(root), head=dict(head), arms=out_a, legs=out_l)


def keyed(t, keys, ground='feet'):
    times = [k[0] for k in keys]
    descs = [k[1] for k in keys]

    def field(get):
        return curve(t, [(tk, get(d)) for tk, d in zip(times, descs)])
    root = {f: field(lambda d, f=f: d['root'].get(f, 0.0)) for f in ('x', 'y', 'z', 'lean', 'tilt', 'yaw')}
    head = {f: field(lambda d, f=f: d['head'].get(f, 0.0)) for f in ('pitch', 'yaw', 'roll')}
    arms = {side: {f: field(lambda d, f=f, side=side: d['arms'][side].get(f, 0.0))
                   for f in ('pitch', 'abd', 'twist', 'elbow')} for side in SIDES}
    legs = {side: {f: field(lambda d, f=f, side=side: d['legs'][side].get(f, 0.0))
                   for f in ('pitch', 'abd', 'twist', 'knee', 'd')} for side in SIDES}
    return build(root, head, arms, legs, ground=ground, clamp_all=True)


D_STAND = _desc(dict(y=-0.07, lean=2.0), dict(pitch=1.5),
                {s: dict(pitch=4, abd=5, twist=4, elbow=13) for s in SIDES},
                {s: dict(foot=f) for s, f in STAND_FEET.items()})
D_PRONE = _desc(PRONE_ROOT, dict(pitch=72.0), PRONE_ARMS, PRONE_LEGS)
D_KNEEL = _desc(dict(y=-1.0, z=0.05, lean=12.0), dict(pitch=14.0),
                {s: dict(pitch=36, abd=10, twist=4, elbow=40) for s in SIDES},
                {'Right': dict(pitch=-18.0, abd=6.0, knee=112.0),       # right knee down on the ground
                 'Left': dict(foot=(-0.6, GROUND, -0.95))})            # left foot planted ahead
D_HANDS = _desc(dict(y=-1.55, z=0.0, lean=52.0), dict(pitch=40.0),
                {'Right': dict(hand=(1.25, GROUND, -1.85), twist=10), 'Left': dict(hand=(-1.25, GROUND, -1.85), twist=10)},
                {'Right': dict(pitch=34.0, abd=8.0, knee=120.0), 'Left': dict(pitch=40.0, abd=10.0, knee=125.0)})
D_LOWER = _desc(dict(y=-2.2, z=0.2, lean=76.0), dict(pitch=62.0),
                {s: dict(pitch=128, abd=24, twist=-30, elbow=96) for s in SIDES},
                {'Right': dict(pitch=-2.0, abd=7.0, knee=40.0), 'Left': dict(pitch=-2.0, abd=10.0, knee=36.0)})
D_PUSH = _desc(dict(y=-1.75, z=0.25, lean=70.0), dict(pitch=50.0),
               {'Right': dict(hand=(1.3, GROUND, -1.25)), 'Left': dict(hand=(-1.3, GROUND, -1.25))},
               {'Right': dict(pitch=-2.0, abd=7.0, knee=12.0), 'Left': dict(pitch=-2.0, abd=10.0, knee=10.0)})
D_KNEES = _desc(dict(y=-1.45, z=0.1, lean=46.0), dict(pitch=34.0),
                {'Right': dict(hand=(1.2, GROUND, -1.55)), 'Left': dict(hand=(-1.2, GROUND, -1.55))},
                {'Right': dict(pitch=46.0, abd=8.0, knee=118.0), 'Left': dict(pitch=58.0, abd=9.0, knee=125.0)})
D_RISE = _desc(dict(y=-0.62, z=0.0, lean=18.0), dict(pitch=10.0),
               {s: dict(pitch=24, abd=8, twist=5, elbow=30) for s in SIDES},
               {'Right': dict(foot=(0.58, GROUND, -0.25)), 'Left': dict(foot=(-0.58, GROUND, 0.3))})


def lie_down(t):
    return keyed(t, [(0.0, D_STAND), (0.24, D_KNEEL), (0.46, D_HANDS), (0.70, D_LOWER), (0.95, D_PRONE)])


def get_up(t):
    return keyed(t, [(0.0, D_PRONE), (0.26, D_PUSH), (0.55, D_KNEES), (0.85, D_RISE), (1.15, D_STAND)])


CLIPS = [
    Clip('idle', 'Survivant_Repos', 4.0, idle, priority='Idle', fps=20, label='Repos'),
    Clip('walk', 'Survivant_Marche', WALK.T, walk, speed=WALK.v, label='Marche'),
    Clip('run', 'Survivant_Course', RUN.T, run, speed=RUN.v, label='Course'),
    Clip('crouch', 'Survivant_Accroupi', 3.0, crouch_idle, priority='Idle', fps=20, label='Accroupi'),
    Clip('crouchwalk', 'Survivant_MarcheAccroupie', CROUCH_WALK.T, crouch_walk, speed=CROUCH_WALK.v,
         label='Marche accroupie'),
    Clip('prone', 'Survivant_Allonge', 4.0, prone_idle, priority='Idle', fps=20, label='Allongé', ground='body'),
    Clip('crawl', 'Survivant_Ramper', CRAWL_T, crawl, speed=1.0, label='Ramper', ground='body'),
    Clip('jump', 'Survivant_Saut', 0.5, jump, loop=False, priority='Action', label='Saut'),
    Clip('fall', 'Survivant_Chute', 0.9, fall, priority='Action', label='Chute'),
    Clip('land', 'Survivant_Atterrissage', 0.42, land, loop=False, priority='Action', label='Atterrissage'),
    Clip('liedown', 'Survivant_SAllonger', 0.95, lie_down, loop=False, priority='Action', label="S'allonger"),
    Clip('getup', 'Survivant_SeRelever', 1.15, get_up, loop=False, priority='Action', label='Se relever'),
    Clip('climb', 'Survivant_Grimper', CLIMB_T, climb, speed=CLIMB_V, label='Grimper'),
    Clip('sit', 'Survivant_Assis', 3.0, sit, priority='Core', fps=20, label='Assis'),
    Clip('tool', 'Survivant_Outil', 4.0, tool, priority='Action', fps=20, label='Outil en main',
         parts=('RightUpperArm', 'RightLowerArm')),
]
CLIP = {c_.key: c_ for c_ in CLIPS}


# ----------------------------------------------------------------------------------------------
# sampling, keyframe reduction, checks

def sample(clip):
    n = max(2, int(round(clip.length * clip.fps)))
    times = np.linspace(0, clip.length, n + 1)
    frames = []
    for t in times:
        tt = 0.0 if (clip.loop and t >= clip.length - 1e-9) else t        # loops end exactly on the first pose
        frames.append(transforms(clip.world(tt)))
    return times, frames


def _interp(Ta, Tb, a):
    """Linear position + slerp rotation between two transforms (what Roblox does between keyframes)."""
    qa, qb = quat(Ta[:3, :3]), quat(Tb[:3, :3])
    if qa @ qb < 0:
        qb = -qb
    d = np.clip(qa @ qb, -1, 1)
    th = np.arccos(d)
    if th < 1e-6:
        q = qa
    else:
        q = (np.sin((1 - a) * th) * qa + np.sin(a * th) * qb) / np.sin(th)
    x, y, z, w = q / np.linalg.norm(q)
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    return M4(R, (1 - a) * Ta[:3, 3] + a * Tb[:3, 3])


def reduce_keys(times, frames, tol_deg=0.45, tol_pos=0.005, parts=PARTS):
    """Keep the keyframes needed so linear interpolation stays within tolerance (all joints together)."""
    keep = {0, len(times) - 1}

    def err(i, j, k):
        a = (times[k] - times[i]) / (times[j] - times[i])
        e = 0.0
        for name in parts:
            Ti = _interp(frames[i][name], frames[j][name], a)
            Tk = frames[k][name]
            e = max(e, rot_angle(Ti[:3, :3], Tk[:3, :3]) / tol_deg, np.linalg.norm(Ti[:3, 3] - Tk[:3, 3]) / tol_pos)
        return e

    def rec(i, j):
        if j - i < 2:
            return
        worst, wk = 0.0, None
        for k in range(i + 1, j):
            e = err(i, j, k)
            if e > worst:
                worst, wk = e, k
        if worst > 1.0:
            keep.add(wk)
            rec(i, wk)
            rec(wk, j)
    rec(0, len(times) - 1)
    idx = sorted(keep)
    return [times[i] for i in idx], [frames[i] for i in idx]


def check(clip, n=None):
    """Lowest point above the ground of every part over the clip: {part: (min, max)}."""
    n = n or int(clip.length * 60)
    lows = {p: [] for p in PARTS}
    for t in np.linspace(0, clip.length, n, endpoint=False):
        W = clip.world(t)
        for p in PARTS:
            lows[p].append(lowest(W[p], p) - GROUND)
    return {p: (float(np.min(v)), float(np.max(v))) for p, v in lows.items()}


# ----------------------------------------------------------------------------------------------
# exports

def export_luau_table(clips=CLIPS, digits=3):
    """Lua table literal:
    ANIMS = { {key=, name=, label=, length=, loop=, priority=, speed=, parts={...}, keys={ {t, {pose...}}, ... } }, ... }
    `parts` lists the keyed body parts (all of rig_spec.PARTS, or a subset for an overlay clip) and each
    pose is {x, y, z, qx, qy, qz, qw} (Motor6D.Transform of that part's joint) in the order of `parts`."""
    lines = ['ANIMS = {']
    fmt = lambda v: ('%.*f' % (digits, v)).rstrip('0').rstrip('.') if abs(v) >= 0.5 * 10 ** -digits else '0'
    total = 0
    for clip in clips:
        times, frames = sample(clip)
        times, frames = reduce_keys(times, frames, parts=clip.parts)
        total += len(times)
        sp = 'nil' if clip.speed is None else fmt(clip.speed)
        plist = ', '.join(f'"{p}"' for p in clip.parts)
        lines.append(f'\t{{key="{clip.key}", name="{clip.name}", label="{clip.label}", length={fmt(clip.length)}, '
                     f'loop={str(clip.loop).lower()}, priority="{clip.priority}", speed={sp}, parts={{{plist}}}, keys={{')
        for t, fr in zip(times, frames):
            poses = []
            for p in clip.parts:
                Tm = fr[p]
                q = quat(Tm[:3, :3])
                poses.append('{' + ','.join(fmt(v) for v in (*Tm[:3, 3], *q)) + '}')
            lines.append(f'\t\t{{{fmt(t)},{{{",".join(poses)}}}}},')
        lines.append('\t}},')
    lines.append('}')
    return '\n'.join(lines), total


def export_json(clips=CLIPS, fps=30):
    """World poses for the web viewer (Roblox rig space): per clip, frames every `dt` seconds (loops: n frames,
    the next one is the first again; one-shots: n + 1 frames ending on the last pose), each frame a
    [x, y, z, qx, qy, qz, qw] per part of PARTS. `rest` gives each part's rest position."""
    out = {'parts': list(PARTS), 'rest': {p: [float(v) for v in REST[p][:3, 3]] for p in PARTS}, 'clips': []}
    for clip in clips:
        n = max(2, int(round(clip.length * fps)))
        dt = clip.length / n
        frames = []
        for i in range(n + (0 if clip.loop else 1)):
            W = clip.world(i * dt)
            frames.append([[round(float(v), 4) for v in (*W[p][:3, 3], *quat(W[p][:3, :3]))] for p in PARTS])
        out['clips'].append(dict(key=clip.key, name=clip.name, label=clip.label, length=clip.length, loop=clip.loop,
                                 speed=clip.speed, ground=clip.ground, dt=dt, frames=frames))
    return json.dumps(out, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    short = {'Torso': 'T', 'Head': 'H', 'RightUpperArm': 'RUA', 'RightLowerArm': 'RLA', 'LeftUpperArm': 'LUA',
             'LeftLowerArm': 'LLA', 'RightUpperLeg': 'RUL', 'RightLowerLeg': 'RLL', 'LeftUpperLeg': 'LUL',
             'LeftLowerLeg': 'LLL'}
    for clip in CLIPS:
        rep = check(clip)
        print(f'{clip.key:11s} ' + ' '.join(f'{short[p]} {lo:+.2f}' for p, (lo, hi) in rep.items()))
    txt, total = export_luau_table()
    print('luau table', round(len(txt) / 1024, 1), 'KiB,', total, 'keyframes')
