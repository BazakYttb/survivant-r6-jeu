"""GIF animés des mises à mort et du déplacement (moteur d'aperçu rapide d'apercu_rapide.py : maillage allégé du
monstre, victime en volumes aux couleurs du survivant). Les phases d'une mise à mort sont enchaînées ; les boucles de
traînée et de repas sont jouées une fois. Le cadre suit le milieu entre le monstre et la victime. Le sol défile à la
vitesse du clip (marche, course, traînées : en jeu, c'est le HumanoidRootPart qui avance) et les traînées laissent une
trace de sang au sol.
usage : python gif_morts.py dossier_sortie [clé,clé...] [i/s] [largeur]"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import apercu_rapide as AR
import mon_anim as A
import mon_clips as C
import mon_morts as MM

SEQ = {
    'morsure_cou': ['k_cou'], 'morsure_repetee': ['k_repetee'],
    'devoration': ['k_dev_saisie', 'k_dev_trainer', 'k_dev_tourner', 'k_dev_manger'],
    'attaque_ventre': ['k_ventre'], 'trainee': ['k_trainee_saisie', 'k_trainee_trainer'],
    'extraction': ['k_extraction'], 'frenesie': ['k_frenesie'], 'contamination': ['k_contamination'],
    'deplacement': ['idle', 'walk', 'run', 'jump', 'fall', 'land', 'roar', 'sniff', 'attack'],
}
TITRES = {'morsure_cou': 'Morsure au cou', 'morsure_repetee': 'Morsure répétée', 'devoration': 'Dévoration',
          'attaque_ventre': 'Attaque au ventre', 'trainee': 'Traînée', 'extraction': 'Extraction (suggérée)',
          'frenesie': 'Frénésie', 'contamination': 'Victime contaminée', 'deplacement': 'Déplacement et gestes'}
VUES = {'morsure_repetee': (20, 14), 'deplacement': (65, 12)}     # (azimut, élévation) ; sinon trois quarts face
# vitesse du sol le long de Z dans le repère du HumanoidRootPart (marche : il avance vers -Z, le sol recule ;
# traînées : le corps est tourné de 180 degrés, le HumanoidRootPart recule)
SOL = {'walk': C.WALK.v, 'run': C.RUN.v, 'k_dev_trainer': -MM.DRAG.v, 'k_trainee_trainer': -MM.DRAG_VITE.v}
COUL = {'Torso': (88, 98, 52), 'RightUpperArm': (88, 98, 52), 'LeftUpperArm': (88, 98, 52),
        'RightLowerArm': (196, 150, 120), 'LeftLowerArm': (196, 150, 120), 'Head': (200, 155, 125),
        'RightUpperLeg': (60, 74, 110), 'LeftUpperLeg': (60, 74, 110), 'RightLowerLeg': (60, 74, 110),
        'LeftLowerLeg': (60, 74, 110)}
SANG = (92, 6, 8)


def police(taille):
    for nom in ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf', 'segoeui.ttf', 'Helvetica.ttc'):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            pass
    return ImageFont.load_default(size=taille)                  # (sans accents)


def render(P, vic, view, size, center, span, defil=0.0, trace=()):
    """apercu_rapide.render avec les couleurs du survivant pour la victime, un sol décalé de `defil` le long de Z et
    une trace de sang au sol (points (x, z) du repère du HumanoidRootPart)."""
    W = A.fk(P)
    az, el = AR.VIEWS[view] if isinstance(view, str) else view
    r, u, f = AR.camera(az, el)
    L = -f * 0.5 + u * 0.7 + r * 0.4
    L /= np.linalg.norm(L)
    tris, cols = [], []
    for p, (V, T) in AR.MESH.items():
        Vw = V @ W[p][:3, :3].T + W[p][:3, 3]
        tris.append(Vw[T])
        cols.append(np.repeat(np.array([[214, 196, 184]]), len(T), 0))
    if vic:
        for p, M in vic.items():
            V, T = AR.VBOX[p]
            Vw = V @ M[:3, :3].T + M[:3, 3]
            tris.append(Vw[T])
            cols.append(np.repeat(np.array([COUL.get(p, (90, 100, 60))]), len(T), 0))
    tri = np.concatenate(tris)
    col = np.concatenate(cols)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= (np.linalg.norm(n, axis=1) + 1e-12)[:, None]
    keep = (n @ f) < 0
    tri, col, n = tri[keep], col[keep], n[keep]
    shade = 0.32 + 0.68 * np.clip(n @ L, 0, 1)
    c = np.asarray(center, float)
    depth = (tri.mean(1) - c) @ f
    order = np.argsort(-depth)
    w, h = size
    sc = h / span

    def ecran(p):
        q = np.asarray(p, float) - c
        return (w / 2 + (q @ r) * sc, h / 2 - (q @ u) * sc)

    img = Image.new('RGB', size, (232, 230, 226))
    dr = ImageDraw.Draw(img)
    x0, z0 = c[0] // 2 * 2, c[2] // 2 * 2 + defil % 2.0
    for g in np.arange(-40, 41, 2.0):
        dr.line([ecran((g + x0, 0, -40 + c[2])), ecran((g + x0, 0, 40 + c[2]))], fill=(208, 206, 200))
        dr.line([ecran((-40 + c[0], 0, g + z0)), ecran((40 + c[0], 0, g + z0))], fill=(208, 206, 200))
    for i in range(len(trace) - 1):
        (xa, za), (xb, zb) = trace[i], trace[i + 1]
        d = np.array([xb - xa, zb - za])
        if np.linalg.norm(d) < 1e-6:
            continue
        nx, nz = np.array([-d[1], d[0]]) / np.linalg.norm(d) * (0.45 + 0.12 * np.sin(1.7 * i))
        dr.polygon([ecran((xa + nx, 0, za + nz)), ecran((xb + nx, 0, zb + nz)), ecran((xb - nx, 0, zb - nz)),
                    ecran((xa - nx, 0, za - nz))], fill=SANG)
    sx = w / 2 + ((tri - c) @ r) * sc
    sy = h / 2 - ((tri - c) @ u) * sc
    for i in order:
        cc = tuple(int(v) for v in np.clip(col[i] * shade[i], 0, 255))
        dr.polygon([(sx[i, 0], sy[i, 0]), (sx[i, 1], sy[i, 1]), (sx[i, 2], sy[i, 2])], fill=cc)
    return img


def gif(cle, out, fps=12, width=300, view=(-40, 14)):
    clips = dict(C.CLIPS)
    clips.update(MM.CLIPS)
    f1, f2 = police(max(11, width // 22)), police(max(10, width // 26))
    frames = []
    centre = None
    defil = 0.0
    trace = []                                                  # points (x, z) de la trace de sang
    for k in SEQ[cle]:
        clip = clips[k]
        libre = cle == 'deplacement' and clip.loop               # boucles du déplacement : 2 s au plus
        n = int(round(min(clip.length, 2.0) * fps)) if libre else max(2, int(round(clip.length * fps)))
        dt = 1.0 / fps if libre else clip.length / n
        vz = SOL.get(k, 0.0)
        for i in range(n + (0 if clip.loop else 1)):
            t = i * dt
            if i > 0 and vz:
                defil += vz * dt
                trace = [(x, z + vz * dt) for x, z in trace]     # la trace reste sur le sol, qui défile
            P = clip.fn(t)
            vic = None
            cen = np.array([0.0, 5.0, -1.5])
            if k in MM.CLIPS:
                vic = AR.victim_model(k, t, P)
                tv = vic['Torso'][:3, 3]
                cen = np.array([tv[0] * 0.5, 5.0, (tv[2] + 0.3) * 0.5])
                if vz:
                    trace.append((float(tv[0]), float(tv[2])))
            centre = cen if centre is None else centre * 0.85 + cen * 0.15
            im = render(P, vic, view, (width, int(width * 1.3)), centre, 15.5, defil, trace)
            d = ImageDraw.Draw(im)
            d.text((6, 4), TITRES[cle], fill=(30, 20, 20), font=f1)
            d.text((6, 6 + f1.size), '%s  %.2f s' % (clip.label or k, t), fill=(90, 80, 80), font=f2)
            frames.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True)
    return len(frames)


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    cles = sys.argv[2].split(',') if len(sys.argv) > 2 else list(SEQ)
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 300
    for c in cles:
        path = os.path.join(out, c + '.gif')
        n = gif(c, path, fps, width, VUES.get(c, (-40, 14)))
        print('%-16s %3d images  %.0f Ko' % (c, n, os.path.getsize(path) / 1024), flush=True)
