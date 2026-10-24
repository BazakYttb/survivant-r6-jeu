"""Textures de sang pour le jeu (posées au sol ou devant la caméra par les scripts Roblox) : flaque, éclaboussures,
traînée raccordable en longueur, éclaboussure d'écran avec coulures. Chaque décalque : couleur + opacité (PNG RGBA,
sRGB), rugosité, normale (relief du film de sang : ménisque au bord, croûte mince).

usage : python -I sang_decals.py dossier_sortie"""
import os
import sys
import math
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

THIN = np.array([0.42, 0.035, 0.03])        # sRGB : film mince, rouge
THICK = np.array([0.16, 0.008, 0.008])      # sRGB : couche épaisse, presque noire
DRY = np.array([0.24, 0.07, 0.05])          # sRGB : bord séché, brun


def periodic_noise(shape, rng, octaves=((4, 1.0), (9, 0.5), (19, 0.25)), px=True, py=True):
    """Bruit lisse (somme de sinus à fréquences entières : raccordable sur les bords périodiques)."""
    h, w = shape
    y = np.linspace(0, 1, h, endpoint=False)[:, None]
    x = np.linspace(0, 1, w, endpoint=False)[None, :]
    out = np.zeros(shape)
    for f, a in octaves:
        for _ in range(4):
            fx = rng.integers(1, f + 1) * (1 if px else rng.uniform(0.7, 1.3))
            fy = rng.integers(0, f + 1) * (1 if py else rng.uniform(0.7, 1.3))
            out += a * np.sin(2 * np.pi * (fx * x + fy * y) + rng.uniform(0, 2 * np.pi))
    return out / np.abs(out).max()


def angular_noise(th, rng, k=(3, 5, 8, 13), amp=(0.35, 0.22, 0.12, 0.07)):
    r = np.zeros_like(th)
    for kk, aa in zip(k, amp):
        r += aa * np.sin(kk * th + rng.uniform(0, 2 * np.pi))
    return r


def soft(x, w):
    """0 -> 1 doux sur une largeur w autour de 0 (x > 0 : intérieur)."""
    return np.clip(0.5 + x / w, 0, 1)


def splatter(N, rng, R0=0.32, spikes=14, drops=160):
    """Éclaboussure : tache centrale aux bords irréguliers, pointes rayonnantes terminées par une goutte, gouttelettes
    allongées dans le sens du jet. Renvoie l'épaisseur (0..1) sur une grille N x N, coordonnées [-1, 1]."""
    y, x = np.mgrid[-1:1:N * 1j, -1:1:N * 1j]
    rho = np.hypot(x, y)
    th = np.arctan2(y, x)
    px = 2.0 / N
    R = R0 * (1 + angular_noise(th, rng))
    thick = soft(R - rho, 3 * px) * np.clip(1.0 - (rho / (R + 1e-6)) ** 2 * 0.5, 0.3, 1)
    for _ in range(spikes):
        a = rng.uniform(-np.pi, np.pi)
        L = R0 * rng.uniform(0.5, 1.8)
        wdt = R0 * rng.uniform(0.06, 0.16)
        u = x * math.cos(a) + y * math.sin(a)
        v = -x * math.sin(a) + y * math.cos(a)
        r0 = R0 * (1 + float(angular_noise(np.array([a]), rng)[0])) * 0.8
        tt = (u - r0) / L
        half = wdt * (1 - np.clip(tt, 0, 1)) ** 1.3
        m = (tt > -0.1) & (tt < 1.0)
        spike = np.where(m, soft(half - np.abs(v), 2 * px), 0.0)
        thick = np.maximum(thick, spike * 0.75)
        # goutte au bout
        cx, cy = (r0 + L * 1.05) * math.cos(a), (r0 + L * 1.05) * math.sin(a)
        rd = wdt * rng.uniform(0.6, 1.2)
        thick = np.maximum(thick, 0.7 * soft(rd - np.hypot(x - cx, y - cy), 2 * px))
    for _ in range(drops):
        a = rng.uniform(-np.pi, np.pi)
        d = R0 * (1.1 + rng.exponential(0.9))
        if d > 0.95:
            continue
        cx, cy = d * math.cos(a), d * math.sin(a)
        rr = R0 * 0.09 * rng.pareto(2.5) * 0.4 + 2.5 * px
        rr = min(rr, R0 * 0.18)
        el = 1.0 + 2.5 * rng.uniform(0, 1) * min(1.0, d / R0 - 1)      # allongées loin du centre
        u = (x - cx) * math.cos(a) + (y - cy) * math.sin(a)
        v = -(x - cx) * math.sin(a) + (y - cy) * math.cos(a)
        e = np.hypot(u / el, v)
        thick = np.maximum(thick, rng.uniform(0.45, 0.8) * soft(rr - e, 2 * px))
    return np.clip(thick, 0, 1)


def pool(N, rng):
    """Flaque : grande tache épaisse à lobes, quelques gouttes autour."""
    y, x = np.mgrid[-1:1:N * 1j, -1:1:N * 1j]
    th = np.arctan2(y, x)
    rho = np.hypot(x, y)
    px = 2.0 / N
    R = 0.62 * (1 + 0.6 * angular_noise(th, rng, k=(2, 3, 5, 9, 17), amp=(0.25, 0.2, 0.12, 0.06, 0.03)))
    thick = soft(R - rho, 4 * px) * (0.85 + 0.15 * np.clip(1 - rho / R, 0, 1))
    for _ in range(40):
        a = rng.uniform(-np.pi, np.pi)
        d = rng.uniform(0.7, 0.95)
        cx, cy = d * math.cos(a), d * math.sin(a)
        rr = rng.uniform(0.008, 0.03)
        thick = np.maximum(thick, 0.7 * soft(rr - np.hypot(x - cx, y - cy), 2 * px))
    return np.clip(thick, 0, 1)


def trail(H, W, rng):
    """Traînée raccordable en longueur (axe x) : bande irrégulière, stries parallèles (corps et doigts traînés),
    trous et gouttes. Coordonnées : x périodique, y dans [-1, 1]."""
    yy = np.linspace(-1, 1, H)[:, None]
    xx = np.linspace(0, 1, W, endpoint=False)[None, :]
    px = 2.0 / H
    n1 = periodic_noise((1, W), rng, octaves=((3, 1.0), (7, 0.5), (15, 0.25)), py=False)[0]
    n2 = periodic_noise((1, W), rng, octaves=((4, 1.0), (11, 0.4)), py=False)[0]
    center = 0.12 * n2[None, :]
    half = 0.55 + 0.18 * n1[None, :]
    band = soft(half - np.abs(yy - center), 4 * px)
    # stries : 7 lignes parallèles plus foncées / plus claires
    stri = np.zeros((H, W))
    for k in range(7):
        y0 = rng.uniform(-0.45, 0.45)
        w = rng.uniform(0.02, 0.07)
        nn = periodic_noise((1, W), rng, octaves=((5, 1.0), (13, 0.5)), py=False)[0]
        stri += rng.uniform(0.3, 0.7) * soft(w * (0.6 + 0.4 * nn[None, :]) - np.abs(yy - center - y0), 2 * px)
    holes = periodic_noise((H, W), rng, octaves=((6, 1.0), (14, 0.5), (29, 0.25)))
    thick = band * np.clip(0.55 + 0.35 * np.clip(stri, 0, 1) - 0.35 * np.clip(holes - 0.25, 0, 1), 0, 1)
    thick = np.where(holes > 0.62, thick * 0.25, thick)
    return np.clip(thick, 0, 1)


def screen(N, rng):
    """Éclaboussure d'écran : deux ou trois impacts, coulures qui descendent (vers le bas de l'image)."""
    t = np.zeros((N, N))
    for k in range(3):
        sp = splatter(N // 2, rng, R0=rng.uniform(0.3, 0.45), spikes=10, drops=50)      # impact sur N/2 px
        x0 = int(rng.uniform(0.0, 0.5) * N)
        y0 = int(rng.uniform(0.0, 0.32) * N)
        t[y0:y0 + N // 2, x0:x0 + N // 2] = np.maximum(t[y0:y0 + N // 2, x0:x0 + N // 2], sp)
    # coulures : depuis les zones épaisses, vers le bas
    cols = rng.choice(np.nonzero(t.max(0) > 0.6)[0], 14, replace=False) if (t.max(0) > 0.6).sum() > 14 else []
    yy = np.arange(N)[:, None]
    xx = np.arange(N)[None, :]
    for c in cols:
        rows = np.nonzero(t[:, c] > 0.6)[0]
        if not len(rows):
            continue
        r0 = rows.max()
        L = int(rng.uniform(0.1, 0.45) * N)
        w0 = rng.uniform(3, 8)
        wob = np.cumsum(rng.normal(0, 0.6, L))
        for i in range(L):
            yi = r0 + i
            if yi >= N:
                break
            w = w0 * (1 - 0.6 * i / L)
            cx = c + wob[i]
            lo, hi = int(max(0, cx - w - 2)), int(min(N, cx + w + 3))
            seg = np.clip(1.0 - np.abs(np.arange(lo, hi) - cx) / max(w, 1), 0, 1)
            t[yi, lo:hi] = np.maximum(t[yi, lo:hi], 0.8 * seg)
        # goutte au bout
        yi = min(N - 1, r0 + L)
        cx = c + (wob[-1] if L else 0)
        d = np.hypot(yy - yi, xx - cx)
        t = np.maximum(t, 0.85 * np.clip(1.0 - d / (w0 * 1.4), 0, 1))
    return np.clip(t, 0, 1)


def finish(thick, rng, name, out, dry=0.0, tile=False):
    """Couleur, opacité, rugosité et normale depuis l'épaisseur (tile : raccordable en x, grain périodique)."""
    sm = ndi.gaussian_filter(thick, 1.0, mode='wrap' if tile else 'nearest')
    if tile:
        grain = periodic_noise(thick.shape, rng, octaves=((24, 1.0), (61, 0.6), (130, 0.3)))
    else:                               # grain irrégulier (pas de motif en grille)
        g = sum(ndi.gaussian_filter(rng.normal(size=thick.shape), s) * s for s in (1.5, 4.0, 10.0))
        grain = g / np.abs(g).max()
    k = np.clip(sm ** 0.7, 0, 1)[..., None]
    col = THIN[None, None] * (1 - k) + THICK[None, None] * k
    rim = np.clip(ndi.gaussian_filter((thick > 0.05).astype(float), 2.0) - ndi.gaussian_filter((thick > 0.05).astype(float), 6.0), 0, 1)
    col = col * (1 - 0.35 * rim[..., None]) + DRY[None, None] * (dry * np.clip(1 - k, 0, 1))
    col = col * (1 + 0.08 * grain[..., None])
    alpha = np.clip(soft(sm - 0.08, 0.1) * (0.55 + 0.45 * np.clip(sm * 1.6, 0, 1)), 0, 1)
    rgba = np.dstack([np.clip(col, 0, 1), alpha])
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(out, name + '_Couleur.png'))
    rough = np.clip(0.12 + 0.35 * (1 - k[..., 0]) + 0.25 * dry * (1 - k[..., 0]) + 0.05 * grain, 0.05, 1)
    Image.fromarray((rough * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, name + '_Rugosite.png'))
    hgt = ndi.gaussian_filter(sm, 1.5) * 6.0 + 0.05 * grain
    gy, gx = np.gradient(hgt)
    nrm = np.dstack([-gx, -gy, np.ones_like(gx)])
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    Image.fromarray(((nrm * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, name + '_Normale.png'))
    return float(alpha.mean())


def goutte(N, rng, out, name='SANG_Goutte'):
    """Goutte pour les particules (giclées) : disque sombre, bord doux, petit reflet."""
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1) * 2 - 1
    r = np.hypot(xx * 1.05, yy * 0.95)
    thick = np.clip(1.0 - r, 0, 1) ** 0.6
    alpha = np.clip((0.82 - r) / 0.16, 0, 1)
    k = thick[..., None]
    col = THIN[None, None] * (1 - k) + THICK[None, None] * k
    hl = np.exp(-((xx + 0.3) ** 2 + (yy + 0.35) ** 2) / 0.02)[..., None]
    col = np.clip(col + 0.35 * hl * np.array([1.0, 0.75, 0.75]), 0, 1)
    rgba = np.dstack([col, alpha])
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(out, name + '_Couleur.png'))
    Image.fromarray(np.full((N, N), int(0.1 * 255), np.uint8)).save(os.path.join(out, name + '_Rugosite.png'))
    Image.fromarray(np.dstack([np.full((N, N), 128, np.uint8)] * 2 + [np.full((N, N), 255, np.uint8)])).save(
        os.path.join(out, name + '_Normale.png'))
    return float(alpha.mean())


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(1666)
    info = []
    info.append(('SANG_Flaque', finish(pool(1024, rng), rng, 'SANG_Flaque', out, dry=0.2)))
    for i in range(1, 4):
        info.append(('SANG_Eclaboussure_%d' % i, finish(splatter(1024, rng, R0=rng.uniform(0.2, 0.3)), rng,
                                                        'SANG_Eclaboussure_%d' % i, out, dry=0.1)))
    info.append(('SANG_Trainee', finish(trail(256, 1024, rng), rng, 'SANG_Trainee', out, dry=0.35, tile=True)))
    info.append(('SANG_Ecran', finish(screen(1024, rng), rng, 'SANG_Ecran', out, dry=0.0)))
    info.append(('SANG_Goutte', goutte(128, rng, out)))
    for n, a in info:
        print('%-22s opacité moyenne %.2f' % (n, a))


if __name__ == '__main__':
    main()
