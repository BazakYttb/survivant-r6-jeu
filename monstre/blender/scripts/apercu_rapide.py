"""Aperçus rapides (sans Blender) : maillage allégé du monstre (dump_proxy.py) posé par pièce, victime en boîtes,
projection orthographique, rendu au peintre avec PIL. Sert à régler les poses ; les rendus finals passent par
apercu_anim.py (Cycles).
usage : python apercu_rapide.py sortie.png clé1,clé2 [images] [vues] [taille]"""
import os
import sys
import math
import numpy as np
from PIL import Image, ImageDraw
import mon_anim as A

from mon_common import src_survivant, chemin_proxy

sys.path.insert(0, src_survivant())
import rig_spec as RS

HERE = os.path.dirname(os.path.abspath(__file__))
_PX = np.load(chemin_proxy() or 'proxy.npz')                 # python dump_proxy.py -- Monstre.blend proxy.npz
MESH = {k[2:]: (_PX[k], _PX['T_' + k[2:]]) for k in _PX.files if k.startswith('V_')}


def _box(sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    V = np.array([[x, y, z] for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)], float)
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    T = []
    for a, b, c, d in F:
        T += [(a, b, c), (a, c, d)]
    T = np.array(T, int)
    # orienter vers l'extérieur
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    ctr = V[T].mean(1)
    flip = (n * ctr).sum(1) < 0
    T[flip] = T[flip][:, [0, 2, 1]]
    return V, T


VBOX = {p: _box(*(np.array(RS.SIZE[p], float) * 0.97)) for p in RS.PARTS}
VIEWS = {'profil': (90, 8), 'face': (0, 6), 'tq': (-40, 14), 'dessus': (-30, 60), 'dos': (180, 8), 'tqd': (45, 12)}


def camera(az, el):
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.sin(a) * math.cos(e), math.sin(e), -math.cos(a) * math.cos(e)])   # vers la caméra
    f = -d
    up = np.array([0.0, 1.0, 0.0])
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def render(P, victim=None, view='profil', size=(320, 420), center=(0, 5.5, -3), span=15.0, extra=()):
    """P : pose du monstre ; victim : {pièce: matrice 4x4 (repère modèle)} ou None ; extra : [(points Nx3, couleur)]."""
    W = A.fk(P)
    az, el = VIEWS[view] if isinstance(view, str) else view
    r, u, f = camera(az, el)
    L = -f * 0.5 + u * 0.7 + r * 0.4; L /= np.linalg.norm(L)
    polys = []
    for p, (V, T) in MESH.items():
        Vw = V @ W[p][:3, :3].T + W[p][:3, 3]
        polys.append((Vw[T], np.array([205, 190, 180])))
    if victim:
        for p, M in victim.items():
            V, T = VBOX[p]
            Vw = V @ M[:3, :3].T + M[:3, 3]
            col = np.array([95, 120, 70]) if p != 'Head' else np.array([200, 160, 130])
            polys.append((Vw[T], col))
    tri = np.concatenate([q[0] for q in polys])
    col = np.concatenate([np.repeat(q[1][None], len(q[0]), 0) for q in polys])
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nn = np.linalg.norm(n, axis=1) + 1e-12
    n = n / nn[:, None]
    keep = (n @ f) < 0                                   # faces tournées vers la caméra
    tri, col, n = tri[keep], col[keep], n[keep]
    shade = 0.3 + 0.7 * np.clip(n @ L, 0, 1)
    depth = (tri.mean(1) - np.asarray(center)) @ f
    order = np.argsort(-depth)
    w, h = size
    sc = h / span
    c = np.asarray(center, float)
    img = Image.new('RGB', size, (238, 238, 232))
    dr = ImageDraw.Draw(img)
    # sol : grille
    for g in np.arange(-20, 21, 2.0):
        for a0, a1 in (((g, 0, -20), (g, 0, 20)), ((-20, 0, g), (20, 0, g))):
            pa = np.array(a0) - c; pb = np.array(a1) - c
            dr.line([(w / 2 + (pa @ r) * sc, h / 2 - (pa @ u) * sc), (w / 2 + (pb @ r) * sc, h / 2 - (pb @ u) * sc)],
                    fill=(205, 205, 198))
    sx = w / 2 + ((tri - c) @ r) * sc
    sy = h / 2 - ((tri - c) @ u) * sc
    for i in order:
        cc = tuple(int(v) for v in np.clip(col[i] * shade[i], 0, 255))
        dr.polygon([(sx[i, 0], sy[i, 0]), (sx[i, 1], sy[i, 1]), (sx[i, 2], sy[i, 2])], fill=cc)
    for pts, cl in extra:
        for pnt in np.atleast_2d(pts):
            q = pnt - c
            x, y = w / 2 + (q @ r) * sc, h / 2 - (q @ u) * sc
            dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=cl)
    return img


def victim_model(clip_key, t, P):
    import mon_morts as MORTS
    k = MORTS.VICTIM[clip_key]
    wv = k.victim(t)
    R, tr = P.get_rt('VictimeAncre')
    F = MORTS.anchor_frame(R, tr)
    return {p: F @ wv[p] for p in RS.PARTS}


def sheet(out, keys, nfr=6, views=('profil', 'tq'), size=(240, 320), times=None):
    import mon_clips as C
    import mon_morts as MORTS
    clips = dict(C.CLIPS); clips.update(MORTS.CLIPS)
    rows = []
    for k in keys:
        clip = clips[k]
        ts = times or [clip.length * i / (nfr - (0 if clip.loop else 1)) for i in range(nfr)]
        for v in views:
            row = []
            for t in ts:
                P = clip.fn(t)
                vic = victim_model(k, t, P) if k in MORTS.CLIPS else None
                im = render(P, vic, v, size)
                ImageDraw.Draw(im).text((4, 4), '%s %.2fs %s' % (k, t, v), fill=(0, 0, 0))
                row.append(im)
            rows.append(row)
    w, h = size
    ncol = max(len(r) for r in rows)
    S = Image.new('RGB', (w * ncol, h * len(rows)), (255, 255, 255))
    for i, row in enumerate(rows):
        for j, im in enumerate(row):
            S.paste(im, (j * w, i * h))
    S.save(out)
    return out


if __name__ == '__main__':
    out = sys.argv[1]
    keys = sys.argv[2].split(',')
    nfr = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    views = sys.argv[4].split(',') if len(sys.argv) > 4 else ('profil', 'tq')
    sz = int(sys.argv[5]) if len(sys.argv) > 5 else 240
    print(sheet(out, keys, nfr, views, (sz, int(sz * 4 / 3))))
