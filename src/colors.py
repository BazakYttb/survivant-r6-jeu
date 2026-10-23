"""Procedural vertex colours (sRGB 0..1).  ctx keys:
pc (cm points), ps (stud points), n (stud normals), ao, cav, prm (tube params s01, phi) ."""
import numpy as np
from sdf import fbm, perlin, worley


def C(*rgb):
    return np.array(rgb, float)


def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a * (1 - t) + b * t


def shade(col, ctx, ao_k=0.45, cav_k=0.35, light=0.10):
    """Apply occlusion and cavity darkening, slight ridge highlight."""
    ao = ctx.get('ao', 1.0)
    cav = ctx.get('cav', 0.0)
    f = (1 - ao_k) + ao_k * ao
    f = f * (1 - cav_k * np.clip(cav, 0, 1)) * (1 + light * np.clip(-cav, 0, 1))
    return np.clip(col * f[:, None], 0, 1)


def _n(ctx, k='pc'):
    return ctx[k]


# ---------------------------------------------------------------- bone
BONE = C(0.89, 0.85, 0.75)
BONE_DARK = C(0.70, 0.62, 0.48)
BONE_WHITE = C(0.95, 0.93, 0.86)


def bone(ctx, tint=0.0, seed=0):
    p = ctx['pc']
    big = fbm(p * 0.18, 3, seed=seed)
    fine = perlin(p * 2.3, seed + 5)
    col = mix(BONE, BONE_DARK, np.clip(0.35 + 0.9 * big, 0, 1) * 0.45)
    col = mix(col, BONE_WHITE, np.clip(fine * 0.8, 0, 1) * 0.35)
    # tiny pores
    speck = np.clip((perlin(p * 7.0, seed + 9) - 0.42) * 6, 0, 1)
    col = mix(col, BONE_DARK * 0.85, speck * 0.35)
    if tint:
        col = mix(col, C(0.93, 0.88, 0.70), tint)
    return shade(col, ctx, 0.5, 0.55, 0.12)


def teeth(ctx):
    p = ctx['pc']
    col = mix(C(0.97, 0.95, 0.88), C(0.90, 0.85, 0.70), np.clip(fbm(p * 1.2, 2) * 0.8 + 0.3, 0, 1) * 0.5)
    return shade(col, ctx, 0.5, 0.5, 0.15)


def cartilage(ctx, seed=0):
    p = ctx['pc']
    base = C(0.80, 0.86, 0.90)
    col = mix(base, C(0.92, 0.94, 0.95), np.clip(fbm(p * 0.8, 2, seed=seed) + 0.4, 0, 1) * 0.5)
    col = mix(col, C(0.75, 0.80, 0.86), np.clip(perlin(p * 3.0, seed + 3), 0, 1) * 0.3)
    return shade(col, ctx, 0.35, 0.3, 0.15)


def disc(ctx):
    p = ctx['pc']
    col = mix(C(0.86, 0.88, 0.86), C(0.76, 0.80, 0.84), np.clip(perlin(p * 1.6) + 0.3, 0, 1) * 0.5)
    return shade(col, ctx, 0.4, 0.3)


def ligament(ctx, seed=0):
    prm = ctx.get('prm')
    p = ctx['pc']
    if prm is not None:
        stri = np.sin(prm[:, 1] * 9 + perlin(p * 0.7, seed) * 3) * 0.5 + 0.5
    else:
        stri = np.clip(perlin(p * np.array([3.0, 3.0, 0.6]), seed) + 0.5, 0, 1)
    col = mix(C(0.93, 0.91, 0.84), C(0.80, 0.77, 0.68), stri * 0.45)
    return shade(col, ctx, 0.4, 0.3, 0.2)


# ---------------------------------------------------------------- vessels / nerves
def artery(ctx, seed=0):
    p = ctx['pc']
    col = mix(C(0.74, 0.10, 0.09), C(0.55, 0.05, 0.06), np.clip(fbm(p * 0.6, 2, seed=seed) + 0.5, 0, 1) * 0.6)
    return shade(col, ctx, 0.35, 0.2, 0.25)


def vein(ctx, seed=0):
    p = ctx['pc']
    col = mix(C(0.22, 0.27, 0.58), C(0.14, 0.17, 0.40), np.clip(fbm(p * 0.6, 2, seed=seed) + 0.5, 0, 1) * 0.6)
    return shade(col, ctx, 0.35, 0.2, 0.25)


def nerve(ctx, seed=0):
    prm = ctx.get('prm')
    p = ctx['pc']
    if prm is not None:
        f = np.sin(prm[:, 1] * 7 + perlin(p * 0.5, seed) * 2) * 0.5 + 0.5
    else:
        f = np.clip(perlin(p * 2.0, seed) + 0.5, 0, 1)
    col = mix(C(0.97, 0.90, 0.58), C(0.86, 0.74, 0.38), f * 0.5)
    return shade(col, ctx, 0.35, 0.25, 0.2)


def spinal_cord(ctx):
    p = ctx['pc']
    col = mix(C(0.94, 0.90, 0.80), C(0.85, 0.76, 0.66), np.clip(perlin(p * 1.5) + 0.5, 0, 1) * 0.4)
    return shade(col, ctx, 0.35, 0.3)


# ---------------------------------------------------------------- organs
def muscle(ctx, base=C(0.58, 0.14, 0.12), seed=0):
    p = ctx['pc']
    f = np.clip(fbm(p * 0.9, 3, seed=seed) + 0.5, 0, 1)
    col = mix(base, base * 0.7, f * 0.6)
    return shade(col, ctx, 0.45, 0.4, 0.2)


def brain(ctx, groove, vessel_seed=11):
    p = ctx['pc']
    base = C(0.86, 0.71, 0.67)
    col = mix(base, C(0.76, 0.58, 0.55), np.clip(fbm(p * 0.35, 3) + 0.5, 0, 1) * 0.55)
    col = mix(col, C(0.48, 0.24, 0.24), np.clip(groove, 0, 1) * 0.9)
    # pial vessels: thin meandering red lines
    q = p * 0.33 + 0.8 * np.stack([fbm(p * 0.2, 2, seed=vessel_seed + k) for k in range(3)], 1)
    v1 = np.exp(-(perlin(q, vessel_seed + 1) / 0.035) ** 2)
    v2 = np.exp(-(perlin(q * 2.3, vessel_seed + 2) / 0.03) ** 2) * 0.6
    col = mix(col, C(0.60, 0.11, 0.12), np.clip(v1 + v2, 0, 1) * 0.85)
    return shade(col, ctx, 0.4, 0.45, 0.1)


def lung(ctx):
    p = ctx['pc']
    base = C(0.86, 0.57, 0.57)
    col = mix(base, C(0.72, 0.42, 0.45), np.clip(fbm(p * 0.5, 3) + 0.5, 0, 1) * 0.6)
    f1, f2 = worley(p * 0.9)
    lob = np.clip(1 - (f2 - f1) / 0.08, 0, 1)
    col = mix(col, C(0.55, 0.36, 0.40), lob * 0.45)
    spots = np.clip((perlin(p * 2.5, 4) - 0.35) * 5, 0, 1) * np.clip(fbm(p * 0.3, 2, seed=8) + 0.2, 0, 1)
    col = mix(col, C(0.25, 0.22, 0.24), spots * 0.75)
    return shade(col, ctx, 0.45, 0.35, 0.15)


def liver(ctx):
    p = ctx['pc']
    col = mix(C(0.50, 0.17, 0.11), C(0.38, 0.11, 0.08), np.clip(fbm(p * 0.6, 3) + 0.5, 0, 1) * 0.7)
    f1, f2 = worley(p * 1.6, 3)
    col = mix(col, C(0.33, 0.09, 0.07), np.clip(1 - (f2 - f1) / 0.06, 0, 1) * 0.25)
    return shade(col, ctx, 0.45, 0.35, 0.2)


def simple(base, var=0.15, freq=0.8, dark=0.7):
    base = np.asarray(base, float)

    def f(ctx):
        p = ctx['pc']
        col = mix(base, base * dark, np.clip(fbm(p * freq, 3) + 0.5, 0, 1) * var * 3)
        return shade(col, ctx, 0.45, 0.35, 0.15)
    return f


def lobulated(base, freq=1.4):
    base = np.asarray(base, float)

    def f(ctx):
        p = ctx['pc']
        f1, f2 = worley(p * freq, 5)
        col = mix(base, base * 0.72, np.clip(1 - (f2 - f1) / 0.12, 0, 1) * 0.7)
        col = mix(col, base * 1.08, np.clip(perlin(p * 0.7), 0, 1) * 0.4)
        return shade(np.clip(col, 0, 1), ctx, 0.45, 0.4, 0.15)
    return f
