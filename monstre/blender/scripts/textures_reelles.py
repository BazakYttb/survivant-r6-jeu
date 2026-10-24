"""Motifs de peau raccordables tirés d'un vrai scan de tête (« Infinite, 3D Head Scan » de Lee Perry-Smith,
Infinite-Realities, CC BY 3.0 ; fichiers distribués avec three.js : examples/models/gltf/LeePerrySmith/).

Zones de peau propre (crâne, cou, nuque : ni barbe, ni yeux, ni oreilles), passe-haut (on ne garde que le grain,
pas l'éclairage ni la forme du visage), puis raccord sans couture : mélange de l'image et de sa copie décalée d'une
demi-période avec une pondération qui conserve le contraste.

Sorties (dossier donné) :
  peau_couleur_1.png, peau_couleur_2.png  détail de couleur, rapport à la teinte locale, moyenne 0,5 (données)
  peau_relief_pores_1.png                 relief fin du cou (pores, ridules, plis), 16 bits, moyenne 0,5
  peau_relief_pores_2.png                 relief fin du crâne (pores), 16 bits, moyenne 0,5
  peau_brillance.png                      détail de brillance (carte spéculaire), moyenne 0,5

usage : python -I textures_reelles.py dossier_scan dossier_sortie"""
import sys
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def tileable(img):
    """Rend une image raccordable : mélange avec sa copie décalée d'une demi-période, poids en sin² (nuls aux
    bords de l'original), combinaison qui garde l'écart-type (pas d'adoucissement dans la zone de mélange)."""
    img = np.asarray(img, np.float64)
    H, W = img.shape[:2]
    wy = np.sin(np.pi * (np.arange(H) + 0.5) / H) ** 2
    wx = np.sin(np.pi * (np.arange(W) + 0.5) / W) ** 2
    w = np.outer(wy, wx)
    ws = np.roll(w, (H // 2, W // 2), axis=(0, 1))
    sh = np.roll(img, (H // 2, W // 2), axis=(0, 1))
    a = w / (w + ws)
    b = 1.0 - a
    k = 1.0 / np.sqrt(a * a + b * b)
    if img.ndim == 3:
        a, b, k = a[..., None], b[..., None], k[..., None]
    mean = img.mean(axis=(0, 1))
    return mean + ((img - mean) * a + (sh - mean) * b) * k


def highpass(img, sigma):
    """Passe-haut par division (couleur) : rapport à la moyenne locale floutée."""
    img = np.asarray(img, np.float64)
    blur = np.stack([ndi.gaussian_filter(img[..., c], sigma, mode='reflect') for c in range(img.shape[2])], -1)
    return img / np.maximum(blur, 1e-4)


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def save_gray16(arr01, path):
    a = np.clip(arr01, 0, 1)
    Image.fromarray((a * 65535 + 0.5).astype(np.uint16)).save(path)


def save_rgb8(arr01, path):
    Image.fromarray((np.clip(arr01, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    col = srgb_to_lin(np.asarray(Image.open(os.path.join(src, 'Map-COL.jpg')).convert('RGB'), np.float64) / 255.0)
    spec = np.asarray(Image.open(os.path.join(src, 'Map-SPEC.jpg')).convert('L'), np.float64) / 255.0
    disp = np.asarray(Image.open(os.path.join(src, 'Infinite-Level_02_Disp_NoSmoothUV-4096.jpg')).convert('L'),
                      np.float64) / 255.0
    info = []
    # couleur : zones propres de la carte 1024 px (crâne côté gauche, cou côté gauche, nuque côté droit)
    for name, boxes in (('peau_couleur_1', [(330, 30, 530, 230)]), ('peau_couleur_2', [(80, 540, 336, 796),
                                                                                     (700, 540, 956, 796)])):
        tiles = []
        for x0, y0, x1, y1 in boxes:
            r = highpass(col[y0:y1, x0:x1], 40.0)              # grain de couleur, sans l'éclairage
            tiles.append(r)
        r = np.mean(tiles, axis=0) if len(tiles) > 1 else tiles[0]
        r = tileable(r)
        r = r / r.mean(axis=(0, 1))                           # rapport moyen 1 par canal
        r = np.clip(r, 0.55, 1.45)
        img = np.stack([np.asarray(Image.fromarray((r[..., c] * 0.5 * 255).astype(np.float32)).resize(
            (512, 512), Image.BICUBIC)) / 255.0 for c in range(3)], -1)
        save_rgb8(img, os.path.join(out, name + '.png'))
        info.append('%s : écart-type du rapport %s' % (name, np.round(r.reshape(-1, 3).std(0), 3)))
    # relief fin : cou gauche et droit de la carte 4096 px (pores, ridules), moyenne des deux zones
    pores = []
    for x0, y0 in ((260, 2250), (3040, 2250)):
        p = disp[y0:y0 + 1024, x0:x0 + 1024]
        p = p - ndi.gaussian_filter(p, 30)                    # passe-haut : pas de forme du visage
        pores.append(p / p.std())
    p = tileable(pores[0] + pores[1][:, ::-1])                # côté droit retourné : même sens des plis
    p = 0.5 + p / (8.0 * p.std())
    save_gray16(p, os.path.join(out, 'peau_relief_pores_1.png'))
    info.append('pores 1 (cou) : 1024 px, moyenne %.3f, écart-type %.3f' % (p.mean(), p.std()))
    # deuxième relief : côté du crâne, au-dessus de l'oreille (autre grain, pour casser la répétition)
    q = disp[250:1150, 400:1300]
    q = q - ndi.gaussian_filter(q, 30)
    q = tileable(q / q.std())
    q = np.asarray(Image.fromarray(q.astype(np.float32)).resize((1024, 1024), Image.BICUBIC), np.float64)
    q = 0.5 + q / (8.0 * q.std())
    save_gray16(q, os.path.join(out, 'peau_relief_pores_2.png'))
    info.append('pores 2 (crâne) : 1024 px, moyenne %.3f, écart-type %.3f' % (q.mean(), q.std()))
    # brillance : carte spéculaire (pores sombres = peau mate), mêmes zones que la couleur
    sp = []
    for x0, y0, x1, y1 in ((110, 110, 366, 366), (80, 540, 336, 796), (700, 540, 956, 796)):
        s = spec[y0:y1, x0:x1]
        s = s - ndi.gaussian_filter(s, 40)
        sp.append(s / s.std())
    s = tileable(np.mean(sp, axis=0))
    s = 0.5 + s / (6.0 * s.std())
    img = np.asarray(Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8)).resize((512, 512), Image.BICUBIC))
    Image.fromarray(img).save(os.path.join(out, 'peau_brillance.png'))
    info.append('brillance : 512 px')
    # teinte moyenne de la peau propre (pour régler la palette)
    clean = np.concatenate([col[110:366, 110:366].reshape(-1, 3), col[540:796, 80:336].reshape(-1, 3),
                            col[540:796, 700:956].reshape(-1, 3)])
    m = clean.mean(0)
    info.append('teinte moyenne (linéaire) %s, sRGB %s' % (np.round(m, 3),
                np.round(np.where(m <= 0.0031308, m * 12.92, 1.055 * m ** (1 / 2.4) - 0.055), 3)))
    with open(os.path.join(out, 'LISEZMOI.txt'), 'w', encoding='utf-8') as fh:
        fh.write(__doc__ + '\n' + '\n'.join(info) + '\n')
    print('\n'.join(info))


if __name__ == '__main__':
    main()
