"""Build the downloadable .zip packs and their base64 chunks for the web page.

    python make_packs.py

Outputs:
  ../dist/Survivant_R6_Roblox.zip   light FBX + Roblox scripts (setup, tools, animations + editor) + docs
                                    (CLAUDE.md: how a Claude session on the user's computer edits the character
                                    in Roblox Studio through Studio's MCP server)
  ../dist/Survivant_R6_Ultra.zip    full-resolution FBX + the same scripts and docs
  ../dist/Survivant_R6_Blender.zip  animated Blender scene (jointed R6 armature, one action per animation) + docs
  ../viewer/dl/<pack>.<sha8>.<i>.txt  each zip as base64 chunks (artifact pages serve text files); the name
                                      carries the zip's hash so a new build never overwrites a published chunk
  ../viewer/dl/packs.json           file name, size, SHA-256 and chunk list per pack
  ../viewer/anatomie_glb.txt        base64 of ../viewer/anatomie.glb (3D view)
"""
import base64
import glob
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DL = os.path.join(ROOT, 'viewer', 'dl')
CHUNK = 9_000_000          # raw bytes per chunk -> 12 MB of base64 text (artifact text files: 16 MB max)

DOCS = [('INSTALLATION_RAPIDE.txt', 'INSTALLATION_RAPIDE.txt'),
        ('README.md', 'README.md'),
        ('CLAUDE.md', 'CLAUDE.md'),
        ('LISTE_DES_PIECES.md', 'LISTE_DES_PIECES.md')]
SCRIPTS = [('roblox/AnatomieR6_Setup.lua', 'AnatomieR6_Setup.lua'),
           ('roblox/SurvivantR6_Animations.lua', 'SurvivantR6_Animations.lua'),
           ('roblox/AnatomieR6_Outils.lua', 'AnatomieR6_Outils.lua')]


def tri_label(n):
    return f'{n / 1e6:.1f} M'.replace('.', ',') if n >= 1e6 else f'{round(n / 1000)} k'


def packs():
    info = json.load(open(os.path.join(ROOT, 'dist', 'export_info.json')))
    import anim
    n = len(anim.CLIPS)
    return {
        'roblox': dict(file='Survivant_R6_Roblox.zip',
                       files=[('dist/Anatomie_R6_Leger.fbx', 'Anatomie_R6_Leger.fbx')] + SCRIPTS + DOCS,
                       sub=f'FBX léger ({tri_label(info["triangles_light"])} triangles) + scripts + {n} animations'),
        'ultra': dict(file='Survivant_R6_Ultra.zip',
                      files=[('dist/Anatomie_R6_Ultra.fbx', 'Anatomie_R6_Ultra.fbx')] + SCRIPTS + DOCS,
                      sub=f'FBX complet ({tri_label(info["triangles"])} triangles) + scripts + {n} animations'),
        'blender': dict(file='Survivant_R6_Blender.zip',
                        files=[('dist/Survivant_R6_Anime.blend', 'Survivant_R6_Anime.blend')] + DOCS,
                        sub=f'Scène .blend animée : armature R6 articulée, {n} actions'),
    }


def build_zip(path, folder, files):
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, arc in files:
            z.write(os.path.join(ROOT, src), f'{folder}/{arc}')
    os.replace(tmp, path)


def main():
    os.makedirs(DL, exist_ok=True)
    for old in glob.glob(os.path.join(DL, '*.txt')):
        os.remove(old)
    index = {}
    for key, p in packs().items():
        zpath = os.path.join(ROOT, 'dist', p['file'])
        build_zip(zpath, p['file'][:-4], p['files'])
        data = open(zpath, 'rb').read()
        sha = hashlib.sha256(data).hexdigest()
        parts, sizes = [], []
        for i in range(0, len(data), CHUNK):
            txt = base64.b64encode(data[i:i + CHUNK])
            name = f'{key}.{sha[:8]}.{i // CHUNK}.txt'
            open(os.path.join(DL, name), 'wb').write(txt)
            parts.append('dl/' + name)
            sizes.append(len(txt))
        index[key] = dict(file=p['file'], sub=p['sub'], bytes=len(data), sha256=sha, parts=parts, sizes=sizes)
        print(f'{p["file"]}: {len(data) / 1e6:.1f} MB, {len(parts)} chunks ({sum(sizes) / 1e6:.1f} MB of text)')
    json.dump(index, open(os.path.join(DL, 'packs.json'), 'w'), ensure_ascii=False, indent=1)
    glb = open(os.path.join(ROOT, 'viewer', 'anatomie.glb'), 'rb').read()
    open(os.path.join(ROOT, 'viewer', 'anatomie_glb.txt'), 'wb').write(base64.b64encode(glb))
    print(f'anatomie_glb.txt: {len(glb) * 4 / 3 / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
