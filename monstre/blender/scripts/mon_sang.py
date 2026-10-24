"""Sang sur la créature (elle vient de dévorer quelqu'un) : attributs par sommet des maillages HD, lus par la matière
de peau puis cuits dans les textures de jeu.

  Sang       quantité (0 propre, 1 couche épaisse)
  SangFrais  1 frais et mouillé (rouge sombre brillant), 0 séché (croûte brun-rouge mate)

Sources : gueule (lèvres, gencives, crocs), menton et gorge, mains et griffes imbibées, avant-bras, éclaboussures sur
le torse, les bras et les cuisses, pieds qui ont marché dans le sang. Les coulures descendent le long du maillage
(plus forte pente vers le bas, avec un peu de hasard) et finissent par une goutte. Repère Blender (z vers le haut)."""
import math
import zlib
import numpy as np
from scipy.spatial import cKDTree
from mon_common import to_blender, unit, smoothstep
from mon_skel import HEAD_C, FH, UH, XH, HAND, FINGERS, J, SCALE
from mon_body import lip_upper, head_radius, HM, jaw_point

K_SKIN, K_HEAD, K_TOOTH, K_GUM, K_NAIL = 0, 1, 2, 3, 4


def neighbors(T, n):
    """Listes de voisins (CSR) depuis les triangles."""
    E = np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    E = np.vstack([E, E[:, ::-1]])
    E = np.unique(E, axis=0)
    ptr = np.zeros(n + 1, np.int64)
    np.add.at(ptr, E[:, 0] + 1, 1)
    ptr = np.cumsum(ptr)
    return ptr, E[:, 1]


def descend(V, ptr, nbr, start, rng, length, jitter=0.35):
    """Coulure : de sommet en sommet vers le bas (pente la plus forte, un peu de hasard), jusqu'à `length` studs ou un
    creux. Renvoie la liste des positions."""
    path = [V[start]]
    i = start
    run = 0.0
    seen = {i}
    while run < length:
        nb = nbr[ptr[i]:ptr[i + 1]]
        if len(nb) == 0:
            break
        d = V[nb] - V[i]
        L = np.linalg.norm(d, axis=1) + 1e-9
        slope = d[:, 2] / L                                  # < 0 : descend
        score = slope + jitter * rng.uniform(-1, 1, len(nb)) * 0.3
        k = int(np.argmin(score))
        if slope[k] > -0.05 or nb[k] in seen:               # plat ou creux : la goutte s'arrête
            break
        i = int(nb[k])
        seen.add(i)
        run += float(L[k])
        path.append(V[i])
    return np.array(path)


def splat_paths(V, tree, paths, r0, out, val=1.0, rng=None):
    """Trace des coulures : profil gaussien autour de chaque point, plus large en haut, renflements irréguliers,
    goutte au bout (r0 : rayon moyen, chaque coulure varie de 0,7 à 1,4 fois)."""
    rng = rng or np.random.default_rng(3)
    for P in paths:
        n = len(P)
        if n < 2:
            continue
        t = np.linspace(0, 1, n)
        k = rng.uniform(0.7, 1.4)
        r = r0 * k * (1.0 - 0.4 * t) * (1.0 + 0.22 * np.sin(t * rng.uniform(8, 18) + rng.uniform(0, 6.3)))
        r[-min(3, n):] = r0 * k * 1.35                         # goutte
        idx = tree.query_ball_point(P, 2.2 * r)
        for k, ids in enumerate(idx):
            if not ids:
                continue
            ids = np.asarray(ids)
            d = np.linalg.norm(V[ids] - P[k], axis=1)
            w = val * np.exp(-(d / r[k]) ** 2 * 1.6)
            out[ids] = np.maximum(out[ids], w)


def blob(V, tree, c, r, out, val=1.0, rng=None, satellites=0):
    """Tache ronde (bord doux) et petites gouttes satellites autour."""
    ids = tree.query_ball_point(c, 2.0 * r)
    if ids:
        ids = np.asarray(ids)
        d = np.linalg.norm(V[ids] - c, axis=1)
        out[ids] = np.maximum(out[ids], val * np.exp(-(d / r) ** 2 * 1.4))
    for _ in range(satellites):
        dirn = unit(rng.normal(size=3))
        cc = c + dirn * r * rng.uniform(1.4, 3.2)
        rr = r * rng.uniform(0.12, 0.3)
        j = tree.query_ball_point(cc, 2.0 * rr)
        if j:
            j = np.asarray(j)
            d = np.linalg.norm(V[j] - cc, axis=1)
            out[j] = np.maximum(out[j], val * np.exp(-(d / rr) ** 2 * 1.4))


def lip_curves():
    """Lèvre du haut, bord de la mâchoire, menton (repère Roblox -> Blender), points échantillonnés."""
    up = []
    for a in np.radians(np.linspace(-78, 78, 60)):
        dfx = np.array([[math.cos(a), math.sin(a) * 0.95, 0.0]])
        dfx[0, 2] = lip_upper(dfx[0, 0] * 0.9, dfx[0, 1] * 0.9) + 0.02
        dd = unit(dfx[0])
        rr = head_radius(dd[None])[0] * 0.95
        up.append(HEAD_C + (dd * rr) @ HM.T)
    lo = [jaw_point(t, 0.0) for t in np.linspace(-0.97, 0.97, 60)]
    chin = [jaw_point(t, w) for t in np.linspace(-0.8, 0.8, 30) for w in (0.55, 0.8, 1.0)]
    return to_blender(np.array(up)), to_blender(np.array(lo)), to_blender(np.array(chin))


def fingertips(side):
    h = HAND[side]
    return to_blender(np.array([h['fingers'][n]['segs'][-1][1] for n in FINGERS]))


def compute(V, T, kind, group, seed=7):
    """Champs Sang et SangFrais pour un maillage HD (V repère Blender, T triangles, kind attribut Mat par sommet,
    group : 'CORPS', 'MAIN_R', 'MAIN_L' ou 'MACHOIRE')."""
    rng = np.random.default_rng(seed + zlib.crc32(group.encode()) % 1000)
    n = len(V)
    tree = cKDTree(V)
    ptr, nbr = neighbors(T, n)
    S = np.zeros(n)                     # quantité
    F = np.zeros(n)                     # fraîcheur (pondérée par la quantité, normalisée à la fin)
    Wf = np.zeros(n)

    def add(field, fresh):
        """Ajoute une couche : quantité max, fraîcheur moyenne pondérée."""
        nonlocal S, F, Wf
        S = np.maximum(S, field)
        F += field * fresh
        Wf += field

    up, lo, chin = lip_curves()
    kind = np.rint(kind).astype(int)
    if group in ('CORPS', 'MACHOIRE'):
        # gueule : gencives, palais et crocs couverts, lèvres et pourtour
        mouth = np.vstack([up, lo])
        d, _ = cKDTree(mouth).query(V)
        coat = 1.0 - smoothstep(np.clip((d - 0.04) / 0.2, 0, 1))
        coat = np.where(np.isin(kind, (K_TOOTH, K_GUM)), np.maximum(coat, rng.uniform(0.75, 1.0, n)), coat)
        add(coat, 1.0)
        # menton et dessous de la mâchoire : couche plus légère
        d2, _ = cKDTree(chin).query(V)
        add(0.75 * (1.0 - smoothstep(np.clip((d2 - 0.03) / 0.22, 0, 1))), 0.8)
        # coulures depuis les lèvres et le menton
        seeds = np.vstack([lo[rng.choice(len(lo), 26)], up[rng.choice(len(up), 14)], chin[rng.choice(len(chin), 18)]])
        _, starts = tree.query(seeds)
        paths = [descend(V, ptr, nbr, int(s), rng, rng.uniform(0.25, 1.1)) for s in starts]
        F_paths = np.zeros(n)
        splat_paths(V, tree, paths, 0.024, F_paths, rng=rng)
        add(F_paths, 0.7)
    if group == 'CORPS':
        # gorge et cou, haut de la poitrine : coulures et éclaboussures
        neck = to_blender(np.array([J['NeckBase'] + np.array([0, -0.25, -0.35]), J['HeadJoint'] + np.array([0, -0.5, -0.1])]))
        cand = np.nonzero((np.linalg.norm(V - neck[0], axis=1) < 0.7) | (np.linalg.norm(V - neck[1], axis=1) < 0.6))[0]
        if len(cand):
            starts = rng.choice(cand, min(12, len(cand)), replace=False)
            paths = [descend(V, ptr, nbr, int(s), rng, rng.uniform(0.3, 1.2)) for s in starts]
            f = np.zeros(n); splat_paths(V, tree, paths, 0.022, f, rng=rng); add(f, 0.5)
        # éclaboussures sur l'avant du corps (torse, bras, cuisses ; pas sur le crâne), quelques coulures courtes
        hc = to_blender(HEAD_C)
        front = np.nonzero((V[:, 1] > np.percentile(V[:, 1], 40)) & (V[:, 2] > 2.0)
                           & (np.linalg.norm(V - hc, axis=1) > 1.4))[0]
        f = np.zeros(n)
        for c in V[rng.choice(front, 42, replace=False)]:
            blob(V, tree, c, rng.uniform(0.015, 0.04), f, rng.uniform(0.55, 0.95), rng, satellites=int(rng.integers(1, 5)))
        add(f, 0.2)
        starts = rng.choice(front, 16, replace=False)
        paths = [descend(V, ptr, nbr, int(s), rng, rng.uniform(0.1, 0.5)) for s in starts]
        f = np.zeros(n); splat_paths(V, tree, paths, 0.018, f, 0.8, rng=rng); add(f, 0.3)
        # avant-bras : traînées jusqu'aux poignets (les mains ont fouillé le corps)
        for side, s in (('R', 1.0), ('L', -1.0)):
            el, wr = to_blender(J['Elbow_' + side]), to_blender(J['Wrist_' + side])
            seg = wr - el
            tpar = np.clip(((V - el) @ seg) / (seg @ seg), 0, 1)
            near = np.linalg.norm(V - (el + tpar[:, None] * seg), axis=1) < 0.3
            amt = near * smoothstep(np.clip((tpar - 0.7) / 0.3, 0, 1)) * 0.4
            add(amt, 0.4)
            cand = np.nonzero(near & (tpar > 0.35))[0]
            if len(cand):
                starts = rng.choice(cand, min(9, len(cand)), replace=False)
                paths = [descend(V, ptr, nbr, int(i), rng, rng.uniform(0.3, 0.9)) for i in starts]
                f = np.zeros(n); splat_paths(V, tree, paths, 0.02, f, rng=rng); add(f, 0.55)
        # pieds : ont marché dans le sang (séché), plus fort en bas
        feet = (V[:, 2] < 0.45) & (np.abs(V[:, 0]) > 0.55)
        amt = feet * (1.0 - smoothstep(np.clip((V[:, 2] - 0.04) / 0.38, 0, 1))) * rng.uniform(0.55, 1.0, n)
        add(amt, 0.05)
    if group in ('MAIN_R', 'MAIN_L'):
        side = group[-1]
        tips = fingertips(side)
        wrist = to_blender(HAND[side]['wrist'])
        d_tip, _ = cKDTree(tips).query(V)
        # doigts et griffes imbibés, de plus en plus vers le bout ; paume et dos de la main tachés
        coat = 1.0 - smoothstep(np.clip((d_tip - 0.12) / 0.5, 0, 1))
        coat = np.where(kind == K_NAIL, np.maximum(coat, rng.uniform(0.35, 0.8, n)), coat)
        add(coat, 0.8)
        starts = rng.choice(n, 34, replace=False)
        paths = [descend(V, ptr, nbr, int(s), rng, rng.uniform(0.15, 0.7)) for s in starts]
        f = np.zeros(n); splat_paths(V, tree, paths, 0.018, f, rng=rng); add(f, 0.7)
        f = np.zeros(n)
        for c in V[rng.choice(n, 14, replace=False)]:
            blob(V, tree, c, rng.uniform(0.012, 0.03), f, rng.uniform(0.5, 0.9), rng, satellites=int(rng.integers(1, 4)))
        add(f, 0.3)
    fresh = np.where(Wf > 1e-6, F / np.maximum(Wf, 1e-6), 0.0)
    return np.clip(S, 0, 1).astype(np.float32), np.clip(fresh, 0, 1).astype(np.float32)


def apply_to_object(ob, group, seed=7):
    """Calcule et écrit les attributs Sang et SangFrais sur un objet HD de Blender."""
    import bpy
    import mon_blend as MB
    V, T, A = MB.mesh_arrays(ob.data)
    kind = A.get('Mat', np.zeros(len(V)))
    S, F = compute(V, T, kind, group, seed)
    me = ob.data
    for name, arr in (('Sang', S), ('SangFrais', F)):
        a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'POINT')
        a.data.foreach_set('value', arr)
    return float((S > 0.3).mean())
