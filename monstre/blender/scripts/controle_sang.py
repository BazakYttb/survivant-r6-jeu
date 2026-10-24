"""Contrôle des images intégrées aux exports : aucune ne doit contenir de rouge sang (la modération de Roblox a refusé
une texture tachée de sang et averti le compte). Lit Monstre.glb et Monstre.fbx sans Blender (glTF binaire, FBX
binaire), extrait toutes les images intégrées et compte, pour chacune, les pixels « rouge sang » : en sRGB (valeurs
de l'image), R > 0,3, R > 2 G et R > 2 B. Compte aussi les pixels « rougeâtres » (critère plus large : R > 0,2,
R > 1,5 G, R > 1,5 B), pour voir la marge.

usage : python -I controle_sang.py dossier_export [--md tableau.md] [--seuil 0.0001] [--planche planche.jpg]
Code de sortie 1 si un export contient un gabarit SANG_* ou si une texture de couleur dépasse le seuil (proportion de
pixels rouge sang, 0,0001 = 0,01 % par défaut). --planche : toutes les textures de couleur du GLB sur une image (ce
que reçoit la modération de Roblox à l'import), pixels rouge sang entourés de magenta."""
import io
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw


def blood_stats(raw):
    """(largeur, hauteur, mode, proportion rouge sang, proportion rougeâtre, nombre de pixels rouge sang)."""
    im = Image.open(io.BytesIO(raw))
    im.load()
    w, h, mode = im.size[0], im.size[1], im.mode
    a = np.asarray(im.convert('RGB'), dtype=np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    blood = (r > 0.3) & (r > 2 * g) & (r > 2 * b)
    reddish = (r > 0.2) & (r > 1.5 * g) & (r > 1.5 * b)
    n = r.size
    return w, h, mode, blood.sum() / n, reddish.sum() / n, int(blood.sum())


def role_from_name(name):
    for key, role in (('Couleur', 'couleur'), ('Normale', 'normale'), ('Rugosite', 'rugosité')):
        if key in name:
            return role
    return '?'


# ---------------------------------------------------------------------------------------------------------- glTF

def glb_images(path):
    """[(nom, rôle, matières, octets)] des images d'un .glb."""
    data = open(path, 'rb').read()
    magic, _version, length = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF':
        raise ValueError('%s : pas un glTF binaire' % path)
    off, js, binc = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack_from('<I4s', data, off)
        off += 8
        if ctype == b'JSON':
            js = json.loads(data[off:off + clen])
        elif ctype == b'BIN\x00':
            binc = data[off:off + clen]
        off += clen
    roles, mats = {}, {}
    tex_img = [t.get('source') for t in js.get('textures', [])]
    for m in js.get('materials', []):
        pbr = m.get('pbrMetallicRoughness', {})
        for slot, role in ((pbr.get('baseColorTexture'), 'couleur'), (m.get('normalTexture'), 'normale'),
                           (pbr.get('metallicRoughnessTexture'), 'rugosité')):
            if slot is not None:
                i = tex_img[slot['index']]
                roles[i] = role
                mats.setdefault(i, []).append(m.get('name', '?'))
    out = []
    for i, im in enumerate(js.get('images', [])):
        bv = js['bufferViews'][im['bufferView']]
        o = bv.get('byteOffset', 0)
        name = im.get('name', 'image_%d' % i)
        out.append((name, roles.get(i, role_from_name(name)), mats.get(i, []), binc[o:o + bv['byteLength']]))
    nodes = [n.get('name', '') for n in js.get('nodes', [])]
    return out, nodes


# ----------------------------------------------------------------------------------------------------------- FBX

def _fbx_tree(data):
    """Arbre des noeuds d'un FBX binaire : [(nom, propriétés, enfants)]."""
    if not data.startswith(b'Kaydara FBX Binary'):
        raise ValueError('pas un FBX binaire')
    version = struct.unpack_from('<I', data, 23)[0]
    wide = version >= 7500
    head = struct.Struct('<QQQ' if wide else '<III')

    def node(off):
        end, nprops, _plen = head.unpack_from(data, off)
        off += head.size
        nlen = data[off]
        off += 1
        if end == 0:
            return None, off
        name = data[off:off + nlen].decode('ascii', 'replace')
        off += nlen
        props = []
        for _ in range(nprops):
            t = chr(data[off])
            off += 1
            if t in 'YCIFDL':
                fmt = {'Y': '<h', 'C': '<?', 'I': '<i', 'F': '<f', 'D': '<d', 'L': '<q'}[t]
                props.append(struct.unpack_from(fmt, data, off)[0])
                off += struct.calcsize(fmt)
            elif t in 'fdlib':
                _alen, _enc, clen = struct.unpack_from('<III', data, off)
                off += 12 + clen
                props.append(None)                      # tableaux : inutiles ici
            elif t in 'SR':
                ln = struct.unpack_from('<I', data, off)[0]
                off += 4
                props.append(data[off:off + ln])
                off += ln
            else:
                raise ValueError('type de propriété FBX inconnu %r' % t)
        children = []
        while off < end:
            ch, off = node(off)
            if ch is not None:
                children.append(ch)
        return (name, props, children), end

    nodes, off = [], 27
    while off < len(data):
        n, off = node(off)
        if n is None:
            break
        nodes.append(n)
    return nodes


def _fbx_name(b):
    return b.split(b'\x00\x01')[0].decode('utf-8', 'replace') if isinstance(b, bytes) else str(b)


def fbx_images(path):
    """[(nom, rôle, matières, octets)] des images intégrées (noeuds Video avec Content) d'un .fbx."""
    tree = _fbx_tree(open(path, 'rb').read())
    top = {n[0]: n for n in tree}
    objs = top['Objects'][2]
    videos, textures, materials, models = {}, {}, {}, []
    for name, props, ch in objs:
        if name == 'Video':
            kids = {c[0]: c[1] for c in ch}
            content = kids.get('Content', [b''])[0] or b''
            fname = (kids.get('RelativeFilename') or kids.get('Filename') or [b''])[0]
            videos[props[0]] = (_fbx_name(props[1]), os.path.basename(_fbx_name(fname).replace('\\', '/')), content)
        elif name == 'Texture':
            textures[props[0]] = _fbx_name(props[1])
        elif name == 'Material':
            materials[props[0]] = _fbx_name(props[1])
        elif name == 'Model':
            models.append(_fbx_name(props[1]))
    vid_tex, tex_mat = {}, {}
    for name, props, _ch in top.get('Connections', ('', [], []))[2]:
        if name != 'C':
            continue
        kind, child, parent = _fbx_name(props[0]), props[1], props[2]
        if child in videos and parent in textures:
            vid_tex.setdefault(child, []).append(parent)
        elif child in textures and parent in materials:
            slot = _fbx_name(props[3]) if kind == 'OP' and len(props) > 3 else ''
            tex_mat.setdefault(child, []).append((materials[parent], slot))
    slot_role = {'DiffuseColor': 'couleur', 'NormalMap': 'normale', 'Bump': 'normale'}
    out = []
    for vid, (vname, fname, content) in videos.items():
        if not content:
            continue
        mats, slots = [], set()
        for t in vid_tex.get(vid, []):
            for m, slot in tex_mat.get(t, []):
                mats.append(m)
                slots.add(slot)
        role = role_from_name(fname or vname)
        if role == '?' and len(slots) == 1:
            role = slot_role.get(slots.pop(), '?')
        out.append((fname or vname, role, sorted(set(mats)), content))
    return out, models


# ------------------------------------------------------------------------------------------------------- rapport

def contact_sheet(raws, path, cell=256, cols=8):
    """Planche des images [(nom, octets)] : vignettes de cell px, nom dessous ; pixels rouge sang entourés."""
    lab = 16
    rows_n = (len(raws) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows_n * (cell + lab)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for k, (name, raw) in enumerate(raws):
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        a = np.asarray(im, dtype=np.float32) / 255.0
        blood = (a[..., 0] > 0.3) & (a[..., 0] > 2 * a[..., 1]) & (a[..., 0] > 2 * a[..., 2])
        th = im.resize((cell, cell), Image.LANCZOS)
        x, y = (k % cols) * cell, (k // cols) * (cell + lab)
        sheet.paste(th, (x, y))
        if blood.any():
            ys, xs = np.nonzero(blood)
            sx, sy = cell / im.size[0], cell / im.size[1]
            for px, py in zip(xs[::max(1, len(xs) // 400)], ys[::max(1, len(ys) // 400)]):
                cx, cy = x + px * sx, y + py * sy
                dr.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), outline=(255, 0, 255))
        dr.text((x + 3, y + cell + 2), name.replace('_Couleur', ''), fill=(220, 220, 220))
    sheet.save(path, quality=90)


def check(folder, seuil=1e-4, sheet=None):
    rows, errs, listing = {}, [], {}
    for fn, reader in (('Monstre.glb', glb_images), ('Monstre.fbx', fbx_images)):
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            errs.append('%s absent' % fn)
            continue
        imgs, names = reader(path)
        sang = sorted(n for n in names if n.startswith('SANG_'))
        if sang:
            errs.append('%s : gabarits de sang présents (%s)' % (fn, ', '.join(sang)))
        listing[fn] = []
        if sheet and fn == 'Monstre.glb':
            contact_sheet(sorted((n, r) for n, ro, _m, r in imgs if ro == 'couleur'), sheet)
        for name, role, mats, raw in imgs:
            w, h, mode, pb, pr, nb = blood_stats(raw)
            base = re.sub(r'\.(png|jpe?g)$', '', name)
            listing[fn].append((base, role, w, h, mode, len(raw), mats, pb, pr, nb))
            rows.setdefault(base, {})[fn] = (role, w, h, pb, pr, nb)
            if role == 'couleur' and pb > seuil:
                errs.append('%s : %s a %.4f %% de pixels rouge sang' % (fn, base, 100 * pb))
        print('%s : %d images intégrées, %d gabarits SANG_*' % (fn, len(imgs), len(sang)))
    return rows, listing, errs


def markdown(rows, listing):
    L = []
    files = list(listing)
    L.append('| Texture de couleur | Taille | ' + ' | '.join('%s : rouge sang' % f for f in files)
             + ' | ' + ' | '.join('%s : rougeâtre' % f for f in files) + ' |')
    L.append('|---|---:|' + '---:|' * (2 * len(files)))
    for base in sorted(rows):
        r = rows[base]
        if not any(v[0] == 'couleur' for v in r.values()):
            continue
        size = next('%d px' % v[1] if v[1] == v[2] else '%d × %d' % (v[1], v[2]) for v in r.values())
        cells = []
        for f in files:
            v = r.get(f)
            cells.append('absente' if v is None else '%.4f %% (%d px)' % (100 * v[3], v[5]))
        for f in files:
            v = r.get(f)
            cells.append('absente' if v is None else '%.3f %%' % (100 * v[4]))
        L.append('| `%s` | %s | %s |' % (base, size, ' | '.join(cells)))
    L.append('')
    for f in files:
        roles = {}
        for it in listing[f]:
            roles[it[1]] = roles.get(it[1], 0) + 1
        others = [it for it in listing[f] if it[1] != 'couleur']
        worst = max((it[7] for it in others), default=0.0)
        L.append('- `%s` : %d images intégrées (%s) ; images de normale et de rugosité : %.4f %% de pixels rouge sang '
                 'au plus.' % (f, len(listing[f]), ', '.join('%d %s' % (n, k) for k, n in sorted(roles.items())),
                               100 * worst))
    L.append('')
    for f in files:
        L.append('<details><summary>Liste des %d images intégrées à <code>%s</code></summary>' % (len(listing[f]), f))
        L.append('')
        L.append('| Image | Rôle | Taille | Mode | Octets | Matière | Rouge sang |')
        L.append('|---|---|---:|---|---:|---|---:|')
        for base, role, w, h, mode, nbytes, mats, pb, _pr, _nb in sorted(listing[f]):
            L.append('| `%s` | %s | %d × %d | %s | %d | %s | %.4f %% |' % (base, role, w, h, mode, nbytes,
                                                                          ', '.join(mats) or '?', 100 * pb))
        L.append('')
        L.append('</details>')
        L.append('')
    return '\n'.join(L)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    folder, md, seuil, sheet = args[0], None, 1e-4, None
    if '--md' in args:
        md = args[args.index('--md') + 1]
    if '--seuil' in args:
        seuil = float(args[args.index('--seuil') + 1])
    if '--planche' in args:
        sheet = args[args.index('--planche') + 1]
    rows, listing, errs = check(folder, seuil, sheet)
    text = markdown(rows, listing)
    if md:
        with open(md, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    worst = {}
    for base, r in rows.items():
        for f, v in r.items():
            if v[0] == 'couleur':
                worst[f] = max(worst.get(f, (0.0, '')), (v[3], base))
    for f, (pb, base) in sorted(worst.items()):
        if pb > 0:
            print('  %s : texture de couleur la plus rouge : %s (%.4f %% de pixels rouge sang)' % (f, base, 100 * pb))
        else:
            print('  %s : aucun pixel rouge sang dans les textures de couleur' % f)
    for e in errs:
        print('  ERREUR', e)
    print('SANG', 'ABSENT' if not errs else 'PRESENT')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
