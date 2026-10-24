"""Corps continu -> pièces du rig : chaque sommet va à l'os le plus proche (distance normalisée par l'épaisseur),
chaque pièce reçoit un manchon (peau des voisines près de la frontière, légèrement rentrée) qui comble le vide quand
l'articulation plie. Repère Blender pour les sommets (les os sont donnés en repère Roblox puis convertis)."""
import numpy as np
from mon_common import to_blender, unit
from mon_skel import J, HAND, FINGERS, HEAD_C, FH, UH, rig_spec, SCALE


def piece_segments():
    """{pièce: [(A, B, r)]} en repère Roblox ; r = épaisseur caractéristique (normalise la distance)."""
    S = {}
    Jp = J
    S['Pelvis'] = [(Jp['Pelvis'] + [0, -0.5, 0.05], Jp['SpineLow'], 0.6), (Jp['Pelvis'], Jp['Hip_R'] + [0.05, 0, 0], 0.45),
                   (Jp['Pelvis'], Jp['Hip_L'] + [-0.05, 0, 0], 0.45)]
    S['Abdomen'] = [(Jp['SpineLow'], Jp['SpineMid'], 0.6)]
    S['Chest'] = [(Jp['SpineMid'], Jp['SpineHigh'], 0.62)]
    neck_lo = Jp['NeckBase'] + (Jp['SpineHigh'] - Jp['NeckBase']) * 0.25       # le cou commence sous sa base
    S['UpperChest'] = [(Jp['SpineHigh'], neck_lo, 0.62),
                       (Jp['SpineHigh'] + [0, 0.25, 0], Jp['Shoulder_R'] + [-0.1, 0.05, 0], 0.42),
                       (Jp['SpineHigh'] + [0, 0.25, 0], Jp['Shoulder_L'] + [0.1, 0.05, 0], 0.42)]
    S['Neck'] = [(neck_lo, Jp['HeadJoint'] + FH * 0.05, 0.42)]
    S['Head'] = [(Jp['HeadJoint'] + FH * 0.3, HEAD_C + FH * 0.75 * SCALE, 0.65)]
    for side in ('R', 'L'):
        S['Thigh_' + side] = [(Jp['Hip_' + side], Jp['Knee_' + side], 0.36)]
        S['Shin_' + side] = [(Jp['Knee_' + side], Jp['Ankle_' + side], 0.24)]
        h = HAND[side]
        fwd = np.array([0.1 if side == 'R' else -0.1, 0, -1.0])
        S['Foot_' + side] = [(Jp['Ankle_' + side], np.array([Jp['Ankle_' + side][0], 0.1, Jp['Ankle_' + side][2]]) + unit(fwd) * 1.1, 0.2)]
        S['UpperArm_' + side] = [(Jp['Shoulder_' + side], Jp['Elbow_' + side], 0.26)]
        S['Forearm_' + side] = [(Jp['Elbow_' + side], Jp['Wrist_' + side], 0.2)]
        S['Hand_' + side] = [(h['wrist'], h['knuckles'], 0.16)]
        for name in FINGERS:
            for j, (a, b, d) in enumerate(h['fingers'][name]['segs']):
                S['%s%d_%s' % (name, j + 1, side)] = [(a, b, 0.07)]
    return S


def _seg_dist(P, A, B):
    AB = B - A
    L2 = max(AB @ AB, 1e-12)
    t = np.clip(((P - A) @ AB) / L2, 0.0, 1.0)
    Q = A[None] + t[:, None] * AB[None]
    return np.linalg.norm(P - Q, axis=1), Q


def assign(Vb, pieces, segs, chunk=400000):
    """Étiquette (indice dans pieces) et distance normalisée de chaque sommet (repère Blender)."""
    n = len(Vb)
    best = np.full(n, np.inf)
    lab = np.zeros(n, np.int32)
    second = np.full(n, np.inf)
    for i, name in enumerate(pieces):
        dmin = np.full(n, np.inf)
        for A, B, r in segs[name]:
            Ab, Bb = to_blender(np.asarray(A, float)), to_blender(np.asarray(B, float))
            for s0 in range(0, n, chunk):
                d, _ = _seg_dist(Vb[s0:s0 + chunk], Ab, Bb)
                dmin[s0:s0 + chunk] = np.minimum(dmin[s0:s0 + chunk], d / r)
        better = dmin < best
        second = np.where(better, best, np.minimum(second, dmin))
        lab = np.where(better, i, lab)
        best = np.where(better, dmin, best)
    return lab, best, second


def split(V, T, A, pieces, segs, sleeve=0.5, inset=0.975, inset_dist=0.012):
    """Découpe un maillage continu (repère Blender) en pièces. Renvoie {pièce: (own, sleeve_hd, sleeve_lo)} où chaque
    élément est (V, T, A) ; le manchon jeu est rentré sous la peau : le long de la normale du corps continu
    (A['Normal'], de inset_dist) si elle est fournie (sûr aussi dans les plis), sinon vers l'os de la pièce."""
    lab, best, second = assign(V, pieces, segs)
    tl = lab[T]
    tri_lab = np.where(tl[:, 1] == tl[:, 2], tl[:, 1], tl[:, 0])
    out = {}
    for i, name in enumerate(pieces):
        own = tri_lab == i
        if not own.any():
            continue
        # distance normalisée à cette pièce pour tous les sommets (pour le manchon)
        dmin = np.full(len(V), np.inf)
        Qbest = np.zeros_like(V)
        for Aa, Bb, r in segs[name]:
            Ab, Bb2 = to_blender(np.asarray(Aa, float)), to_blender(np.asarray(Bb, float))
            d, Q = _seg_dist(V, Ab, Bb2)
            d = d / r
            m = d < dmin
            dmin = np.where(m, d, dmin)
            Qbest[m] = Q[m]
        excess = dmin - best                     # 0 sur la pièce, > 0 chez les voisines
        near = (excess[T] < sleeve).all(axis=1) & ~own
        def sub(mask, shrink=None):
            idx = np.nonzero(mask)[0]
            used = np.unique(T[idx])
            remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used))
            Vs = V[used].copy()
            if shrink is not None:
                if 'Normal' in A:
                    Vs = Vs - A['Normal'][used] * inset_dist
                else:
                    Vs = Qbest[used] + (Vs - Qbest[used]) * shrink
            return Vs, remap[T[idx]].astype(np.int32), {k: v[used] for k, v in A.items()}
        out[name] = (sub(own), sub(near) if near.any() else None, sub(near, inset) if near.any() else None)
    return out


def distances(Vb, pieces, segs, chunk=400000):
    """Distance normalisée de chaque sommet (repère Blender) à chaque pièce : tableau (n, len(pieces))."""
    n = len(Vb)
    D = np.full((n, len(pieces)), np.inf)
    for i, name in enumerate(pieces):
        for A, B, r in segs[name]:
            Ab, Bb = to_blender(np.asarray(A, float)), to_blender(np.asarray(B, float))
            for s0 in range(0, n, chunk):
                d, _ = _seg_dist(Vb[s0:s0 + chunk], Ab, Bb)
                D[s0:s0 + chunk, i] = np.minimum(D[s0:s0 + chunk, i], d / r)
    return D


def split_smooth(V, T, A, pieces, segs, sleeve=0.5, inset_dist=0.012, t_clamp=0.06, parents=None):
    """Comme split, mais la frontière entre deux pièces suit la courbe où leurs distances normalisées sont égales :
    les triangles qui la traversent sont recoupés (nouveaux sommets partagés par les deux pièces), la coupe est une
    courbe régulière et non un zigzag le long des arêtes. parents = {pièce: parent} : le manchon d'une pièce ne prend
    rien chez ses enfants (chaque enfant fournit le sien), une seule épaisseur par jointure.
    Renvoie {pièce: (own, None, sleeve_lo)}."""
    D = distances(V, pieces, segs)
    lab = D.argmin(1)
    keys = list(A.keys())
    extraV, extraA = [], {k: [] for k in keys}
    nV = len(V)
    edge_pt = {}

    def new_vertex(p, attrs):
        extraV.append(p)
        for k in keys:
            extraA[k].append(attrs[k])
        return nV + len(extraV) - 1

    def interp(a, b, t):
        out = {}
        for k in keys:
            v = A[k][a] * (1 - t) + A[k][b] * t
            if k == 'Normal':
                v = v / max(np.linalg.norm(v), 1e-12)
            out[k] = v
        return out

    def edge_point(a, b):
        key = (a, b) if a < b else (b, a)
        if key in edge_pt:
            return edge_pt[key]
        i, j = lab[a], lab[b]
        ga, gb = D[a, i] - D[a, j], D[b, i] - D[b, j]
        t = ga / (ga - gb) if ga != gb else 0.5
        t = min(max(t, t_clamp), 1 - t_clamp)
        idx = new_vertex(V[a] * (1 - t) + V[b] * t, interp(a, b, t))
        edge_pt[key] = idx
        return idx

    tl = lab[T]
    mixed = ~((tl[:, 0] == tl[:, 1]) & (tl[:, 1] == tl[:, 2]))
    out_T = [T[~mixed]]
    out_L = [tl[~mixed, 0]]
    sub_T, sub_L = [], []
    for f in np.nonzero(mixed)[0]:
        vs = [int(x) for x in T[f]]
        ls = [int(x) for x in tl[f]]
        if len(set(ls)) == 3:
            P = [edge_point(vs[k], vs[(k + 1) % 3]) for k in range(3)]          # P[k] sur l'arête k -> k+1
            q_attrs = {}
            for k in keys:
                v = (A[k][vs[0]] + A[k][vs[1]] + A[k][vs[2]]) / 3.0
                if k == 'Normal':
                    v = v / max(np.linalg.norm(v), 1e-12)
                q_attrs[k] = v
            q = new_vertex(V[vs].mean(0), q_attrs)
            for k in range(3):
                poly = [P[(k + 2) % 3], vs[k], P[k], q]                          # entrée, sommet, sortie, centre
                sub_T += [(poly[1], poly[2], poly[3]), (poly[1], poly[3], poly[0])]
                sub_L += [ls[k], ls[k]]
            continue
        poly = {}
        for k in range(3):
            u, w = vs[k], vs[(k + 1) % 3]
            poly.setdefault(ls[k], []).append(u)
            if ls[k] != ls[(k + 1) % 3]:
                p = edge_point(u, w)
                poly[ls[k]].append(p)
                poly.setdefault(ls[(k + 1) % 3], []).append(p)
        for l, pl in poly.items():
            for k in range(1, len(pl) - 1):
                sub_T.append((pl[0], pl[k], pl[k + 1]))
                sub_L.append(l)
    if sub_T:
        out_T.append(np.array(sub_T, np.int64))
        out_L.append(np.array(sub_L, np.int64))
    V2 = np.vstack([V] + ([np.array(extraV)] if extraV else []))
    A2 = {k: np.concatenate([A[k]] + ([np.array(extraA[k], dtype=A[k].dtype)] if extraV else [])) for k in keys}
    T2 = np.vstack(out_T).astype(np.int64)
    L2 = np.concatenate(out_L)
    D2 = np.vstack([D, distances(np.array(extraV), pieces, segs)]) if extraV else D
    best = D2.min(1)
    res = {}
    for i, name in enumerate(pieces):
        own = L2 == i
        if not own.any():
            continue
        excess = D2[:, i] - best
        near = (excess[T2] < sleeve).all(axis=1) & ~own
        if parents:
            kids = [k for k, nm in enumerate(pieces) if parents.get(nm) == name]
            if kids:
                near &= ~np.isin(L2, kids)

        def sub(mask, inset=False):
            idx = np.nonzero(mask)[0]
            used = np.unique(T2[idx])
            remap = -np.ones(len(V2), np.int64)
            remap[used] = np.arange(len(used))
            Vs = V2[used].copy()
            if inset:
                Vs = Vs - A2['Normal'][used] * inset_dist
            return Vs, remap[T2[idx]].astype(np.int32), {k: v[used] for k, v in A2.items()}
        res[name] = (sub(own), None, sub(near, True) if near.any() else None)
    return res
