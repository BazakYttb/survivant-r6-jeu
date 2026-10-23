"""Mappings from anatomical 'real' coordinates (cm) to R6 stud space.

Stud space is Blender space: X = character's left, Y = back, Z = up, ground at Z=0.
R6 boxes (studs): Torso x[-1,1] z[2,4]; Head centred (0,0,4.5) ~1.2 cube;
Left Arm x[1,2] z[2,4]; Right Arm x[-2,-1]; Left Leg x[0,1] z[0,2]; Right Leg x[-1,0].
Real coordinates: x = lateral (+left), y = posterior (+back), z = up (cm)
(limbs use u = lateral from limb axis, v = posterior, w = distance below the
proximal joint centre).
"""
import numpy as np


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


class HeadMap:
    region = 'Head'
    O = np.array([0.0, 0.02, 4.52])
    S = np.array([0.046 * 1.08, 0.046, 0.046])
    spc = 0.046

    def fwd(self, p):
        return self.O + np.asarray(p) * self.S

    def inv(self, q):
        return (np.asarray(q) - self.O) / self.S


class TorsoMap:
    region = 'Torso'
    sx, sy, sz, sz_low = 0.046, 0.040, 0.0335, 0.024
    spc = 0.040

    def __init__(self, girdle=False):
        self.girdle = girdle
        if girdle:
            xr = np.linspace(0, 40, 4001)
            xs = self.sx * xr + 0.32 * smoothstep(8, 17, xr)
            self._xr, self._xs = xr, xs

    def _fx(self, x):
        if not self.girdle:
            return self.sx * x
        return np.sign(x) * np.interp(np.abs(x), self._xr, self._xs)

    def _ix(self, X):
        if not self.girdle:
            return X / self.sx
        return np.sign(X) * np.interp(np.abs(X), self._xs, self._xr)

    def fwd(self, p):
        p = np.atleast_2d(p).astype(float)
        z = p[:, 2] - 91.0
        Z = 1.95 + np.where(z >= 0, self.sz * z, self.sz_low * z)
        return np.stack([self._fx(p[:, 0]), self.sy * p[:, 1], Z], 1)

    def inv(self, q):
        q = np.atleast_2d(q).astype(float)
        dz = q[:, 2] - 1.95
        z = 91.0 + np.where(dz >= 0, dz / self.sz, dz / self.sz_low)
        return np.stack([self._ix(q[:, 0]), q[:, 1] / self.sy, z], 1)


class ArmMap:
    sh = 0.031     # horizontal stud/cm
    sv = 0.0208    # vertical stud/cm
    spc = 0.028
    Z0 = 3.66
    W = [0, 32, 59, 80]
    XA = [1.20, 1.30, 1.47, 1.50]

    def __init__(self, side):
        self.s = side  # +1 left, -1 right
        self.region = 'LeftArm' if side > 0 else 'RightArm'

    def xaxis(self, w):
        return np.interp(w, self.W, self.XA)

    def fwd(self, p):
        p = np.atleast_2d(p).astype(float)
        u, v, w = p[:, 0], p[:, 1], p[:, 2]
        return np.stack([self.s * (self.xaxis(w) + self.sh * u), self.sh * v, self.Z0 - self.sv * w], 1)

    def inv(self, q):
        q = np.atleast_2d(q).astype(float)
        w = (self.Z0 - q[:, 2]) / self.sv
        u = (self.s * q[:, 0] - self.xaxis(w)) / self.sh
        return np.stack([u, q[:, 1] / self.sh, w], 1)


class LegMap:
    sx = 0.034
    sy = 0.029
    sv = 0.0214
    spc = 0.031
    Z0 = 1.95
    W = [0, 43.5, 91]
    XA = [0.42, 0.50, 0.50]
    WY = [0, 43.5, 82, 91]
    YA = [-0.10, 0.0, 0.10, 0.10]

    def __init__(self, side):
        self.s = side
        self.region = 'LeftLeg' if side > 0 else 'RightLeg'

    def fwd(self, p):
        p = np.atleast_2d(p).astype(float)
        u, v, w = p[:, 0], p[:, 1], p[:, 2]
        X = self.s * (np.interp(w, self.W, self.XA) + self.sx * u)
        Y = np.interp(w, self.WY, self.YA) + self.sy * v
        return np.stack([X, Y, self.Z0 - self.sv * w], 1)

    def inv(self, q):
        q = np.atleast_2d(q).astype(float)
        w = (self.Z0 - q[:, 2]) / self.sv
        u = (self.s * q[:, 0] - np.interp(w, self.W, self.XA)) / self.sx
        v = (q[:, 1] - np.interp(w, self.WY, self.YA)) / self.sy
        return np.stack([u, v, w], 1)


def stud_bbox(m, lo, hi, n=7):
    """Stud-space bbox of a cm-space box under mapping m."""
    g = np.stack(np.meshgrid(*[np.linspace(lo[i], hi[i], n) for i in range(3)], indexing='ij'), -1).reshape(-1, 3)
    s = m.fwd(g)
    return s.min(0), s.max(0)
