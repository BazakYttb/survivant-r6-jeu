"""Write ../LISTE_DES_PIECES.md from ../build/manifest.json (survivor outfit first, then the anatomy by body part
of the jointed R6 rig)."""
import json, os
import rig_spec as RS
HERE = os.path.dirname(os.path.abspath(__file__))
m = json.load(open(os.path.join(HERE, '..', 'build', 'manifest.json')))
REG = [(r, f'{RS.LABELS_FR[r]} ({r})') for r in RS.REGIONS]
CAT = {'bone': 'os', 'tooth': 'dents', 'cartilage': 'cartilage', 'disc': 'disque', 'ligament': 'ligament / tendon',
       'organ': 'organe', 'brain': 'cerveau', 'eye': 'œil', 'vessel': 'vaisseau', 'nerve': 'nerf', 'muscle': 'muscle',
       'gland': 'glande'}
OUTFIT = ('skin', 'gear')
anat = {k: v for k, v in m.items() if v['cat'] not in OUTFIT}
outfit = sorted((v for v in m.values() if v['cat'] in OUTFIT), key=lambda v: (v['cat'], v['name']))
tot = sum(v['tris'] for v in anat.values())
fmt = lambda n: f'{n:,}'.replace(',', ' ')
out = ['# Liste des pièces', '',
       f'{len(anat)} pièces anatomiques ({fmt(tot)} triangles, version Ultra) et {len(outfit)} pièces de tenue du '
       f'survivant, soit {len(m)} MeshParts. Chaque pièce est soudée à la pièce du rig R6 articulé indiquée '
       '(bras et jambes coupés au coude et au genou).', '']
REGLABEL = dict(REG)
out += [f'## Tenue du survivant — {len(outfit)} pièces, {fmt(sum(v["tris"] for v in outfit))} triangles', '',
        'Rangées dans le dossier `Anatomie_R6 > Peau`. Elles remplacent visuellement les blocs Roblox du rig '
        '(réglage `SKIN_MODE`), avec la transparence `SKIN_TRANSPARENCY` (0 = opaque). Les accessoires (bonnet, '
        'sac à dos) sont masqués en radiographie.', '',
        '| Pièce | Pièce du rig | Type | Triangles | Description |', '|---|---|---|---:|---|']
for v in outfit:
    kind = 'accessoire' if v['cat'] == 'gear' else 'tenue'
    out.append(f"| `{v['name']}` | {REGLABEL.get(v['region'], v['region'])} | {kind} | {v['tris']} | {v.get('info', '')} |")
out.append('')
for key, label in REG:
    items = sorted((v for v in anat.values() if v['region'] == key), key=lambda v: v['name'])
    out += [f'## {label} — {len(items)} pièces, {fmt(sum(v["tris"] for v in items))} triangles', '',
            '| Pièce | Catégorie | Triangles | Description |', '|---|---|---:|---|']
    for v in items:
        out.append(f"| `{v['name']}` | {CAT.get(v['cat'], v['cat'])} | {v['tris']} | {v.get('info', '')} |")
    out.append('')
open(os.path.join(HERE, '..', 'LISTE_DES_PIECES.md'), 'w').write('\n'.join(out))
print('written', len(anat), 'anatomy parts +', len(outfit), 'outfit parts')
