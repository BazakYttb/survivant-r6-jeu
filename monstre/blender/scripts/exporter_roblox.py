"""Paquet Roblox du monstre : données d'animation (MonstreDonnees.lua) et kit à insérer dans Studio (Monstre_Kit.rbxmx).

- Clips du monstre (déplacement, gestes, phases des mises à mort) et de la victime (rig du survivant, src/anim.py) :
  échantillonnés à 30 i/s, clés réduites piste par piste (interpolation nlerp, 0,5 degré / 5 mm ; doigts 0,8 degré),
  quantifiées (u16 ms, quaternion i16, translation i16 en mm) et encodées en base64 (format lu par MonstreAnim.lua).
- Rig (pivots, parents), points de la victime (sang), séquences de mises à mort.
- Monstre_Kit.rbxmx : dossier avec l'installateur, les modules et les scripts (sources de monstre/roblox/src).
- test/reference_poses.lua : poses de contrôle pour les tests hors ligne (décodage et interpolation en Luau).
usage : python exporter_roblox.py [dossier monstre/roblox]"""
import os
import sys
import math
import base64
import struct
import time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mon_anim as A
import mon_clips as C
import mon_morts as MM

from mon_common import src_survivant, dossier_monstre, chemin_proxy

sys.path.insert(0, src_survivant())
import anim as SA

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(dossier_monstre(), 'roblox')
SRC = os.path.join(OUT, 'src')
FPS = 30

MARKERS = {'REF_A': (0.0, 5.0, 0.0), 'REF_B': (0.0, 7.0, 0.0), 'REF_C': (1.5, 5.0, 0.0), 'REF_D': (0.0, 5.0, -1.0)}
GLOW = tuple(float(v) for v in A.HEAD_C + (A.FH * 0.42 - A.UH * 0.36) * A.SCALE * 0.98)

# sons des clips de déplacement et des gestes (marqueurs ajoutés ici)
EXTRA_MARKERS = {
    'idle': [(0.4, 'Son', 'souffle'), (2.4, 'Son', 'souffle')],
    'walk': [(0.02, 'Son', 'pas_lourd'), (C.WALK.T / 2 + 0.02, 'Son', 'pas_lourd')],
    'run': [(0.02, 'Son', 'pas_lourd'), (C.RUN.T / 2 + 0.02, 'Son', 'pas_lourd')],
    'land': [(0.05, 'Son', 'pas_lourd')],
    'sniff': [(0.5, 'Son', 'reniflement'), (1.5, 'Son', 'reniflement'), (2.5, 'Son', 'reniflement')],
    'jump': [(0.05, 'Son', 'grognement')],
}


def nlerp(qa, qb, u):
    if qa @ qb < 0:
        qb = -qb
    q = qa * (1 - u) + qb * u
    return q / np.linalg.norm(q)


def reduce_track(times, Q, T, tol_deg, tol_pos):
    n = len(times) - 1
    keep = {0, n}

    def err(i, j, k):
        u = (times[k] - times[i]) / (times[j] - times[i])
        q = nlerp(Q[i], Q[j], u)
        d = min(1.0, abs(float(q @ Q[k])))
        ang = 2 * math.degrees(math.acos(d))
        return max(ang / tol_deg, np.linalg.norm(T[i] + (T[j] - T[i]) * u - T[k]) / tol_pos)

    stack = [(0, n)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        worst, wk = 0.0, None
        for k in range(i + 1, j):
            e = err(i, j, k)
            if e > worst:
                worst, wk = e, k
        if worst > 1.0:
            keep.add(wk)
            stack.append((i, wk))
            stack.append((wk, j))
    static = all(np.allclose(Q[k], Q[0], atol=2e-5) and np.allclose(T[k], T[0], atol=1e-5) for k in range(n + 1))
    return [0] if static else sorted(keep)


def quat_fix(qs):
    """Quaternions (x, y, z, w) rendus continus (pas de saut de signe entre échantillons voisins)."""
    out = [np.asarray(qs[0], float)]
    for q in qs[1:]:
        q = np.asarray(q, float)
        out.append(-q if q @ out[-1] < 0 else q)
    return out


def encode(times, Q, T, idx, hasT):
    b = bytearray()
    for k in idx:
        ms = int(round(times[k] * 1000))
        assert 0 <= ms < 65536
        q = Q[k]
        b += struct.pack('<Hhhhh', ms, *[int(round(max(-1.0, min(1.0, v)) * 32767)) for v in q])
        if hasT:
            b += struct.pack('<hhh', *[int(round(v * 1000)) for v in T[k]])
    return base64.b64encode(bytes(b)).decode('ascii')


def decode(s, hasT):
    raw = base64.b64decode(s)
    rec = 16 if hasT else 10
    out = []
    for o in range(0, len(raw), rec):
        ms, qx, qy, qz, qw = struct.unpack_from('<Hhhhh', raw, o)
        t = np.zeros(3)
        if hasT:
            t = np.array(struct.unpack_from('<hhh', raw, o + 10)) / 1000.0
        q = np.array([qx, qy, qz, qw], float)
        out.append((ms / 1000.0, q / np.linalg.norm(q), t))          # renormalisé comme dans MonstreAnim
    return out


def sample_eval(keys, t):
    """Même calcul que MonstreAnim.sampleTrack (Luau)."""
    T = [k[0] for k in keys]
    if t <= T[0] or len(keys) == 1:
        q, p = keys[0][1], keys[0][2]
        return q, p
    if t >= T[-1]:
        return keys[-1][1], keys[-1][2]
    i = int(np.searchsorted(T, t, side='right')) - 1
    u = (t - T[i]) / (T[i + 1] - T[i])
    qa, qb = keys[i][1], keys[i + 1][1]
    if qa @ qb < 0:
        qb = -qb
    q = qa + (qb - qa) * u
    q = q / np.linalg.norm(q)
    p = keys[i][2] + (keys[i + 1][2] - keys[i][2]) * u
    return q, p


def clip_tracks(length, loop, frame_fn, parts, tol_fn):
    """frame_fn(t) -> {piste: (R 3x3, t 3)}. Renvoie {piste: (chaîne, hasT)}, nb de clés, erreur max (degrés)."""
    n = max(2, int(round(length * FPS)))
    times = [round(length * i / n, 3) for i in range(n + 1)]          # instants au ms près (clés exactes)
    frames = [frame_fn(0.0 if (loop and i == n) else t) for i, t in enumerate(times)]
    tracks, nkeys, emax = {}, 0, 0.0
    for p in parts:
        Q = quat_fix([A.quat(f[p][0]) for f in frames])
        T = [np.asarray(f[p][1], float) for f in frames]
        hasT = max(float(np.abs(t).max()) for t in T) > 2e-4
        tol_deg, tol_pos = tol_fn(p)
        idx = reduce_track(times, Q, T, tol_deg, tol_pos)
        s = encode(times, Q, T, idx, hasT)
        keys = decode(s, hasT)
        for k, t in enumerate(times):                       # contrôle : erreur de toute la chaîne (réduction + quantification)
            q, pp = sample_eval(keys, t)
            d = min(1.0, abs(float(q @ (Q[k] / np.linalg.norm(Q[k])))))
            emax = max(emax, 2 * math.degrees(math.acos(d)))
            assert np.linalg.norm(pp - T[k]) < tol_pos + 0.003, (p, t)
        tracks[p] = (s, hasT)
        nkeys += len(idx)
    return tracks, nkeys, emax


def monster_frames(clip):
    def fn(t):
        P = clip.fn(t)
        return {p: P.get_rt(p) for p in A.ORDER}
    return fn


def victim_frames(fn_world):
    def fn(t):
        Tr = SA.transforms(fn_world(t))
        return {p: (M[:3, :3], M[:3, 3]) for p, M in Tr.items()}
    return fn


def tol_monstre(p):
    if any(p.startswith(f) for f in ('Index', 'Middle', 'Ring', 'Pinky', 'Thumb')):
        return 0.8, 0.005
    return 0.5, 0.005


def lua_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def fmt(v):
    return ('%.4f' % v).rstrip('0').rstrip('.') if abs(v) >= 5e-5 else '0'


SEQUENCES = [
    dict(key='morsure_cou', label='Morsure au cou', emoji='🩸', phases=[dict(clip='k_cou')], fin='mort'),
    dict(key='morsure_repetee', label='Morsure répétée', emoji='🦷', phases=[dict(clip='k_repetee')], fin='mort'),
    dict(key='devoration', label='Dévoration', emoji='👹',
         phases=[dict(clip='k_dev_saisie'), dict(clip='k_dev_trainer', trainer=True), dict(clip='k_dev_tourner'),
                 dict(clip='k_dev_manger', repas=True)],
         fin='mort', trainer=dict(vers='taniere', vitesse=MM.DRAG.v, distance=26)),
    dict(key='attaque_ventre', label='Attaque au ventre', emoji='💀', phases=[dict(clip='k_ventre')], fin='mort'),
    dict(key='trainee', label='Traînée', emoji='🩸',
         phases=[dict(clip='k_trainee_saisie'), dict(clip='k_trainee_trainer', trainer=True)],
         fin='mort', trainer=dict(vers='sortie', vitesse=MM.DRAG_VITE.v, distance=40)),
    dict(key='extraction', label='Extraction suggérée', emoji='🫀', phases=[dict(clip='k_extraction')], fin='mort'),
    dict(key='frenesie', label='Frénésie', emoji='🐺', phases=[dict(clip='k_frenesie')], fin='mort'),
    dict(key='contamination', label='Victime contaminée', emoji='☣️', phases=[dict(clip='k_contamination')],
         fin='infection'),
]


def lua_value(v, ind=''):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float, np.floating)):
        return fmt(float(v))
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, dict):
        items = ', '.join('%s = %s' % (k, lua_value(x, ind)) for k, x in v.items())
        return '{' + items + '}'
    if isinstance(v, (list, tuple)):
        return '{' + ', '.join(lua_value(x, ind) for x in v) + '}'
    raise TypeError(type(v))


def build_data():
    t0 = time.time()
    lines = ['-- MonstreDonnees (ModuleScript, ReplicatedStorage.Monstre) : généré par exporter_roblox.py, ne pas modifier',
             '-- à la main. Pistes : base64 de (u16 ms, i16 qx qy qz qw x 32767[, i16 x y z en mm]) ; voir MonstreAnim.',
             'local D = {}']
    # rig
    parts = []
    for n in A.ORDER:
        parts.append(dict(name=n, parent=A.PARENT[n], joint=A.JOINT[n], pivot=[float(v) for v in A.PIV[n]]))
    rig = dict(hrp=dict(center=[float(v) for v in A.HRP_C], size=list(A.HRP_SIZE), hipHeight=float(A.HIP_HEIGHT)),
               markers={k: list(v) for k, v in MARKERS.items()}, glow=list(GLOW), victimRest=[float(v) for v in A.VICTIM_REST])
    lines.append('D.rig = {')
    lines.append('\thrp = %s,' % lua_value(rig['hrp']))
    lines.append('\tmarkers = %s,' % lua_value(rig['markers']))
    lines.append('\tglow = %s,' % lua_value(rig['glow']))
    lines.append('\tvictimRest = %s,' % lua_value(rig['victimRest']))
    lines.append('\tparts = {')
    for p in parts:
        lines.append('\t\t%s,' % lua_value(p))
    lines.append('\t},')
    lines.append('}')
    # points de la victime
    lines.append('D.points = {')
    for k, (part, loc) in MM.VPTS.items():
        lines.append('\t%s = {%s, {%s}},' % (k, lua_str(part), ', '.join(fmt(v) for v in loc)))
    lines.append('}')
    # clips du monstre
    stats = []
    mclips = list(C.CLIPS.values()) + [MM.CLIPS[k.key] for k in MM.KILLS]
    lines.append('D.monstre = {}')
    total_m = 0
    for c in mclips:
        markers = sorted(list(c.markers) + EXTRA_MARKERS.get(c.key, []))
        tracks, nk, emax = clip_tracks(c.length, c.loop, monster_frames(c), A.ORDER, tol_monstre)
        total_m += nk
        stats.append((c.key, nk, emax))
        lines.append('D.monstre[%s] = {name = %s, label = %s, length = %s, loop = %s, priority = %s, speed = %s,' % (
            lua_str(c.key), lua_str(c.name), lua_str(c.label), fmt(c.length), 'true' if c.loop else 'false',
            lua_str(c.priority), 'nil' if c.speed is None else fmt(c.speed)))
        lines.append('\tmarkers = {%s},' % ', '.join('{%s, %s, %s}' % (fmt(t), lua_str(nm), lua_str(str(v)))
                                                   for t, nm, v in markers))
        lines.append('\ttrans = {%s},' % ', '.join('%s = true' % p for p, (s, h) in tracks.items() if h))
        lines.append('\ttracks = {')
        for p, (s, h) in tracks.items():
            lines.append('\t\t%s = %s,' % (p, lua_str(s)))
        lines.append('\t},')
        lines.append('}')
        print('monstre %-18s %5d clés  erreur max %.2f°' % (c.key, nk, emax), flush=True)
    # clips de la victime (rig du survivant)
    lines.append('D.victime = {}')
    total_v = 0
    vclips = [(k.key, k.vname, k.length, k.vloop, k.victim, k.label) for k in MM.KILLS]
    g = SA.CLIP['getup']
    vclips.append(('getup', 'Victime_SeRelever', g.length, False, g.fn, 'Se relever'))
    for key, name, length, loop, fn, label in vclips:
        tracks, nk, emax = clip_tracks(length, loop, victim_frames(fn), SA.PARTS, lambda p: (0.5, 0.005))
        total_v += nk
        stats.append(('v:' + key, nk, emax))
        lines.append('D.victime[%s] = {name = %s, label = %s, length = %s, loop = %s,' % (
            lua_str(key), lua_str(name), lua_str(label), fmt(length), 'true' if loop else 'false'))
        lines.append('\ttrans = {%s},' % ', '.join('%s = true' % p for p, (s, h) in tracks.items() if h))
        lines.append('\ttracks = {')
        for p, (s, h) in tracks.items():
            lines.append('\t\t%s = %s,' % (p, lua_str(s)))
        lines.append('\t},')
        lines.append('}')
        print('victime %-17s %5d clés  erreur max %.2f°' % (key, nk, emax), flush=True)
    # séquences
    lines.append('D.sequences = {')
    for s in SEQUENCES:
        lines.append('\t%s,' % lua_value(s))
    lines.append('}')
    lines.append('return D')
    txt = '\n'.join(lines) + '\n'
    print('données : %.0f Ko, %d clés monstre, %d clés victime, %.0f s' % (len(txt.encode()) / 1024, total_m, total_v,
                                                                           time.time() - t0))
    return txt, stats


def reference_poses():
    """Poses de contrôle (calcul Python sur les clés décodées) pour test/test_monstre.lua."""
    import re
    src = open(os.path.join(SRC, 'MonstreDonnees.lua'), encoding='utf-8').read()
    out = ['-- poses de contrôle (exporter_roblox.py) : {rig, clip, t, piste, qx, qy, qz, qw, x, y, z}', 'return {']
    cases = [('monstre', 'walk', 0.37), ('monstre', 'k_cou', 1.234), ('monstre', 'k_dev_trainer', 2.9),
             ('monstre', 'k_frenesie', 1.01), ('victime', 'k_cou', 1.5), ('victime', 'getup', 0.61)]
    for rig, key, t in cases:
        m = re.search(r'D\.%s\["%s"\] = \{.*?\n\ttrans = \{(.*?)\},\n\ttracks = \{\n(.*?)\n\t\},' % (rig, key), src, re.S)
        trans = set(x.split(' =')[0].strip() for x in m.group(1).split(',') if x.strip())
        for line in m.group(2).split('\n'):
            p, s = line.strip().rstrip(',').split(' = ')
            keys = decode(s.strip('"'), p in trans)
            q, pp = sample_eval(keys, t)
            out.append('\t{%s, %s, %s, %s, %s},' % (lua_str(rig), lua_str(key), fmt(t), lua_str(p),
                                                    ', '.join('%.6f' % v for v in (*q, *pp))))
    out.append('}')
    return '\n'.join(out) + '\n'


# ------------------------------------------------------------------------------------------------ kit .rbxmx
_ref = [0]


def _referent():
    _ref[0] += 1
    return 'RBX%032X' % _ref[0]


def _cdata(s):
    return '<![CDATA[' + s.replace(']]>', ']]]]><![CDATA[>') + ']]>'


def item(cls, name, source=None, disabled=None, children=(), attrs=None):
    props = ['<string name="Name">%s</string>' % name]
    if source is not None:
        props.append('<ProtectedString name="Source">%s</ProtectedString>' % _cdata(source))
    if disabled is not None:
        props.append('<bool name="Disabled">%s</bool>' % ('true' if disabled else 'false'))
    body = ''.join('<Item class="%s" referent="%s"><Properties>%s</Properties>%s</Item>' % c for c in [])
    kids = ''.join(children)
    return '<Item class="%s" referent="%s"><Properties>%s</Properties>%s</Item>' % (cls, _referent(), ''.join(props), kids)


def build_kit():
    def src(name):
        return open(os.path.join(SRC, name), encoding='utf-8').read()
    kids = [
        item('ModuleScript', 'Installateur', src('Installateur.lua')),
        item('ModuleScript', 'MonstreAnim', src('MonstreAnim.lua')),
        item('ModuleScript', 'MonstreConfig', src('MonstreConfig.lua')),
        item('ModuleScript', 'MonstreDonnees', src('MonstreDonnees.lua')),
        item('ModuleScript', 'MonstreOutils', src('MonstreOutils.lua')),
        item('Script', 'MonstreServeur', src('MonstreServeur.server.lua'), disabled=True),
        item('LocalScript', 'MonstreClient', src('MonstreClient.client.lua')),
    ]
    kit = item('Folder', 'Monstre_Kit', children=kids)
    return ('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
            '<External>null</External><External>nil</External>' + kit + '</roblox>\n')


# ------------------------------------------------------------------------------------------------ données de test
def qmat(q):
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def decoded_clip(src, rig, key):
    import re
    m = re.search(r'D\.%s\["%s"\] = \{.*?\n\ttrans = \{(.*?)\},\n\ttracks = \{\n(.*?)\n\t\},' % (rig, key), src, re.S)
    trans = set(x.split(' =')[0].strip() for x in m.group(1).split(',') if x.strip())
    out = {}
    for line in m.group(2).split('\n'):
        p, s_ = line.strip().rstrip(',').split(' = ')
        out[p] = decode(s_.strip('"'), p in trans)
    return out


def test_fixtures():
    src = open(os.path.join(SRC, 'MonstreDonnees.lua'), encoding='utf-8').read()
    px = np.load(chemin_proxy())
    L = ['-- données de test (exporter_roblox.py) : import simulé du monstre, rig du survivant, positions attendues', 'return {']
    L.append('\tmonstre = {')
    for n in A.PIECES:
        V = px['V_' + n]
        lo, hi = V.min(0), V.max(0)
        c, sz = (lo + hi) / 2, np.maximum(hi - lo, 0.05)
        L.append('\t\t{name = "MON_%s_1", center = {%s}, size = {%s}},' % (n, ', '.join(fmt(v) for v in c), ', '.join(fmt(v) for v in sz)))
    L.append('\t},')
    L.append('\tmarqueurs = {%s},' % ', '.join('%s = {%s}' % (k, ', '.join(fmt(x) for x in v)) for k, v in MARKERS.items()))
    L.append('\tglow = {%s},' % ', '.join(fmt(v) for v in GLOW))
    import rig_spec as RS
    L.append('\tsurvivant = {')
    L.append('\t\tparts = {')
    for n in ('HumanoidRootPart',) + RS.PARTS:
        L.append('\t\t\t{name = "%s", center = {%s}, size = {%s}},' % (n, ', '.join(fmt(v) for v in RS.CENTER[n]), ', '.join(fmt(v) for v in RS.SIZE[n])))
    L.append('\t\t},')
    L.append('\t\tjoints = {')
    for name, (p0, p1, piv, r) in RS.JOINT_DEFS.items():
        C0, C1 = RS.c0c1(name)
        cf = lambda M: ', '.join(fmt(v) for v in (*M[:3, 3], *M[:3, :3].reshape(-1)))
        L.append('\t\t\t{name = "%s", part0 = "%s", part1 = "%s", C0 = {%s}, C1 = {%s}},' % (name, p0, p1, cf(C0), cf(C1)))
    L.append('\t\t},')
    L.append('\t},')
    L.append('\tattendus = {')
    cases = [('k_cou', 0.0), ('k_cou', 1.234), ('k_repetee', 2.51), ('k_dev_trainer', 1.1), ('k_ventre', 0.8),
             ('k_extraction', 2.0), ('k_contamination', 2.7), ('walk', 0.5)]
    for key, t in cases:
        mon = decoded_clip(src, 'monstre', key)
        P = A.Pose()
        for n, keys in mon.items():
            q, p = sample_eval(keys, t)
            P[n] = (qmat(q), p)
        W = A.fk(P)
        pts = {n: A.point(W, n, A.PIV[n]) for n in ('Head', 'Hand_R', 'Foot_L', 'Jaw', 'Index2_R')}
        row = '\t\t{clip = "%s", t = %s, monstre = {%s}' % (key, fmt(t), ', '.join('%s = {%s}' % (n, ', '.join('%.5f' % v for v in x)) for n, x in pts.items()))
        if key in MM.CLIPS:
            vic = decoded_clip(src, 'victime', key)
            Tr = {}
            for n, keys in vic.items():
                q, p = sample_eval(keys, t)
                Tr[n] = A.M4(qmat(q), p)
            Wv = SA.world_from_transforms(Tr)
            R_a, t_a = P.get_rt('VictimeAncre')
            F = MM.anchor_frame(R_a, t_a)
            vp = {n: (F @ Wv[n])[:3, 3] for n in ('Torso', 'Head', 'RightLowerLeg', 'LeftLowerArm')}
            vp['HumanoidRootPart'] = F[:3, 3]
            row += ', victime = {%s}' % ', '.join('%s = {%s}' % (n, ', '.join('%.5f' % v for v in x)) for n, x in vp.items())
        L.append(row + '},')
    L.append('\t},')
    L.append('}')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    os.makedirs(SRC, exist_ok=True)
    txt, stats = build_data()
    with open(os.path.join(SRC, 'MonstreDonnees.lua'), 'w', encoding='utf-8') as f:
        f.write(txt)
    os.makedirs(os.path.join(OUT, 'test'), exist_ok=True)
    with open(os.path.join(OUT, 'test', 'reference_poses.lua'), 'w', encoding='utf-8') as f:
        f.write(reference_poses())
    if chemin_proxy():                          # données de test (maillage allégé requis, sinon on garde les anciennes)
        with open(os.path.join(OUT, 'test', 'fixtures.lua'), 'w', encoding='utf-8') as f:
            f.write(test_fixtures())
    else:
        print('proxy.npz absent : test/fixtures.lua non régénéré (python dump_proxy.py -- Monstre.blend proxy.npz)')
    kit = build_kit()
    with open(os.path.join(OUT, 'Monstre_Kit.rbxmx'), 'w', encoding='utf-8') as f:
        f.write(kit)
    print('kit : %.0f Ko' % (len(kit.encode()) / 1024))
    print('erreur max (réduction + quantification) : %.2f°' % max(e for _, _, e in stats))
