"""Generate the Roblox Studio scripts from the build manifest, the rig and the animations.

    python make_lua.py [--manifest ../build/manifest.json]
                       [--template ../roblox/AnatomieR6_Setup.template.lua]
                       [--out ../roblox/AnatomieR6_Setup.lua] [--no-info]

1. AnatomieR6_Setup.lua (command bar: builds the jointed R6 rig and places the imported meshes).
   The line '--@@PARTS_TABLE@@' of the template becomes a Lua table literal built from
   build/manifest.json (name -> {region, cat, base, tris, info}):

    PARTS = {
        ["Head_Skull_Face"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="..."},
        ["RightLowerArm_Radius"] = {region="RightLowerArm", ...},
        ...
    }

   (keys sorted, colours rounded to 3 decimals; region = rig part the mesh is welded to). Never
   hardcodes part lists: whatever is in the manifest ends up in the script. The block
   '--@@RIG@@' ... '--@@/RIG@@' becomes rig_spec.lua_table() (10 parts, Motor6Ds, RightHand), so the
   template stays runnable on its own and the generated script always matches rig_spec.py.
2. SurvivantR6_Animate.client.lua (the in-game controller): '--@@CLIPS@@' -> clip metadata.
3. SurvivantR6_Animations.lua (command bar: animations, controller, StarterCharacter, editor):
   '--@@RIG@@' -> RIG, '--@@ANIMS@@' -> anim.export_luau_table(), and the long strings
   ANIMATE_SOURCE (the controller) and EDITOR_SOURCE (roblox/SurvivantEditeur.module.lua, installed
   as ServerStorage.SurvivantEditeur; its child module Donnees = {RIG, ANIMS} is written at install
   time from the same tables).
4. roblox/test/expected_anims.lua (values the offline tests check) and viewer/anims.json.
"""
import argparse
import json
import math
import os
import sys

import rig_spec

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ROBLOX = os.path.join(ROOT, 'roblox')
MARKER = '--@@PARTS_TABLE@@'
REGIONS = rig_spec.REGIONS
CATS = ('bone', 'tooth', 'cartilage', 'disc', 'ligament', 'organ', 'brain', 'eye', 'vessel',
        'nerve', 'muscle', 'gland', 'skin', 'gear')


def lua_str(s):
    """Lua/Luau double-quoted string literal (UTF-8 kept as is)."""
    out = ['"']
    for ch in str(s):
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif o < 32 or o == 127:
            out.append('\\%03d' % o)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def lua_num(x):
    v = round(float(x), 3)
    if v == 0:
        return '0'
    s = ('%.3f' % v).rstrip('0').rstrip('.')
    return s


def inject(text, name, content, keep_markers=False):
    """Replace the line '--@@NAME@@', or the block '--@@NAME@@' ... '--@@/NAME@@', by `content`
    (keep_markers: only the inside of the block, so the result is still a template)."""
    lines = text.split('\n')
    start = [i for i, l in enumerate(lines) if l.strip() == f'--@@{name}@@']
    end = [i for i, l in enumerate(lines) if l.strip() == f'--@@/{name}@@']
    if len(start) != 1 or len(end) > 1 or (end and end[0] < start[0]) or (keep_markers and not end):
        sys.exit(f'error: template must contain exactly one line --@@{name}@@ (optionally closed by --@@/{name}@@)')
    if keep_markers:
        lines[start[0] + 1:end[0]] = [content]
    else:
        lines[start[0]:(end[0] if end else start[0]) + 1] = [content]
    return '\n'.join(lines)


def replace_once(text, marker, content):
    if text.count(marker) != 1:
        sys.exit(f'error: template must contain {marker!r} exactly once (found {text.count(marker)})')
    return text.replace(marker, content)


def build_table(manifest, with_info=True):
    lines = ['PARTS = {']
    warnings = []
    for name in sorted(manifest):
        e = manifest[name]
        region = e.get('region')
        cat = e.get('cat', 'bone')
        base = e.get('base') or [0.8, 0.8, 0.8]
        if region not in REGIONS:
            warnings.append(f'{name}: unknown region {region!r}')
        if rig_spec.region_of_name(name) != region:
            warnings.append(f'{name}: name does not match region {region!r} (rig_spec.region_of_name)')
        if cat not in CATS:
            warnings.append(f'{name}: unknown category {cat!r}')
        if not name.isascii() or ' ' in name:
            warnings.append(f'{name}: name must be ASCII without spaces')
        if len(base) != 3:
            warnings.append(f'{name}: base colour must have 3 components')
            base = (list(base) + [0.8, 0.8, 0.8])[:3]
        tris = e.get('tris')
        if isinstance(tris, int) and tris > 19000:
            warnings.append(f'{name}: {tris} triangles > 19000 (Roblox limit 20000)')
        col = ','.join(lua_num(min(max(float(c), 0.0), 1.0)) for c in base)
        fields = [f'region={lua_str(region)}', f'cat={lua_str(cat)}', f'color={{{col}}}']
        info = (e.get('info') or '').strip()
        if with_info and info:
            fields.append(f'info={lua_str(info)}')
        lines.append(f'\t[{lua_str(name)}] = {{{", ".join(fields)}}},')
    lines.append('}')
    return '\n'.join(lines), warnings


def write_atomic(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--manifest', default=os.path.join(ROOT, 'build', 'manifest.json'))
    ap.add_argument('--template', default=os.path.join(ROBLOX, 'AnatomieR6_Setup.template.lua'))
    ap.add_argument('--out', default=os.path.join(ROBLOX, 'AnatomieR6_Setup.lua'))
    ap.add_argument('--no-info', action='store_true', help='omit the French descriptions (smaller script)')
    a = ap.parse_args(argv)

    with open(a.manifest, encoding='utf-8') as f:
        manifest = json.load(f)
    with open(a.template, encoding='utf-8') as f:
        template = f.read()
    # the template keeps a copy of RIG so that it runs on its own (offline tests): keep it in sync
    synced = inject(template, 'RIG', rig_spec.lua_table(), keep_markers=True)
    if synced != template:
        write_atomic(a.template, synced)
        template = synced
        print(f'{os.path.relpath(a.template)}: RIG block updated from rig_spec.py')

    table, warnings = build_table(manifest, with_info=not a.no_info)
    out = inject(template, 'PARTS_TABLE', table)
    out = inject(out, 'RIG', rig_spec.lua_table())
    write_atomic(a.out, out)

    regions = {}
    for e in manifest.values():
        regions[e.get('region')] = regions.get(e.get('region'), 0) + 1
    for w in warnings:
        print('warning:', w)
    print(f'{os.path.relpath(a.out)}: {len(manifest)} parts '
          f'({", ".join(f"{k} {v}" for k, v in sorted(regions.items(), key=lambda kv: str(kv[0])))}), '
          f'{len(out.encode("utf-8")) / 1024:.1f} KiB')


def clips_table():
    """Lua table of the clip metadata used by the Animate controller."""
    import anim
    lines = ['local CLIPS = {']
    for c in anim.CLIPS:
        fields = [f'name = {lua_str(c.name)}', f'length = {lua_num(c.length)}', f'loop = {str(c.loop).lower()}',
                  f'priority = {lua_str(c.priority)}']
        if c.speed is not None:
            fields.append(f'speed = {lua_num(c.speed)}')
        if tuple(c.parts) != tuple(rig_spec.PARTS):
            fields.append('partial = true')
        lines.append(f'\t{c.key} = {{ {", ".join(fields)} }},')
    lines.append('}')
    return '\n'.join(lines)


def long_string(text):
    level = 1
    while (']' + '=' * level + ']') in text:
        level += 1
    eq = '=' * level
    return f'[{eq}[\n{text}]{eq}]'


def make_anims():
    import anim
    with open(os.path.join(ROBLOX, 'SurvivantR6_Animate.client.template.lua'), encoding='utf-8') as f:
        ctl = f.read()
    ctl = inject(ctl, 'CLIPS', clips_table())
    write_atomic(os.path.join(ROBLOX, 'SurvivantR6_Animate.client.lua'), ctl)
    with open(os.path.join(ROBLOX, 'SurvivantEditeur.module.lua'), encoding='utf-8') as f:
        editor = f.read()
    with open(os.path.join(ROBLOX, 'SurvivantR6_Animations.template.lua'), encoding='utf-8') as f:
        inst = f.read()
    table, nkeys = anim.export_luau_table()
    inst = inject(inst, 'RIG', rig_spec.lua_table())
    inst = inject(inst, 'ANIMS', 'local ' + table)
    inst = replace_once(inst, '--@@ANIMATE_SOURCE@@', long_string(ctl))
    inst = replace_once(inst, '--@@EDITOR_SOURCE@@', long_string(editor))
    out = os.path.join(ROBLOX, 'SurvivantR6_Animations.lua')
    write_atomic(out, inst)
    print(f'{os.path.relpath(out)}: {len(anim.CLIPS)} animations, {nkeys} keyframes, '
          f'{len(inst.encode("utf-8")) / 1024:.1f} KiB')
    write_expected(anim)
    viewer = os.path.join(ROOT, 'viewer', 'anims.json')
    with open(viewer, 'w', encoding='utf-8') as f:
        f.write(anim.export_json())
    print(f'{os.path.relpath(viewer)}: {os.path.getsize(viewer) / 1024:.0f} KiB (web viewer)')


def rig_frame(part, T):
    """Motor6D.Transform -> pose in the parent part's axes (what SurvivantEditeur reads and writes):
    (12 CFrame components, [x, y, z, rx, ry, rz] with angles in degrees, CFrame.Angles order X, Y, Z)."""
    import numpy as np
    r = rig_spec.JOINT_DEFS[rig_spec.JOINT_OF[part]][3]
    R0 = np.asarray(r, float).reshape(3, 3)
    p = R0 @ T[:3, 3]
    R = R0 @ T[:3, :3] @ R0.T
    ry = math.asin(max(-1.0, min(1.0, R[0, 2])))
    rx = math.atan2(-R[1, 2], R[2, 2])
    rz = math.atan2(-R[0, 1], R[0, 0])
    return [*p, *R.ravel()], [*p, math.degrees(rx), math.degrees(ry), math.degrees(rz)]


def write_expected(anim):
    """roblox/test/expected_anims.lua: what the installer must build (rig, names, flags, key counts, sample
    poses as Motor6D.Transform and in the editor's parent-frame convention)."""
    nums = lambda vals: ', '.join('%.5f' % v for v in vals)
    lines = ['-- généré par src/make_lua.py : valeurs attendues pour les tests (rig et animations)',
             rig_spec.lua_table(), 'local CLIPS = {']
    for c in anim.CLIPS:
        times, frames = anim.reduce_keys(*anim.sample(c), parts=c.parts)
        full = tuple(c.parts) == tuple(rig_spec.PARTS)
        sample_parts = ('Torso', 'Head', 'RightLowerArm', 'LeftLowerLeg') if full else c.parts
        samples = []
        for k in sorted({0, len(times) // 2, len(times) - 1}):
            for part in sample_parts:
                T = frames[k][part]
                comps = [*T[:3, 3], *T[:3, :3].ravel()]
                rig12, deg = rig_frame(part, T)
                samples.append(f'{{ k = {k + 1}, part = {lua_str(part)}, t = {lua_num(times[k])}, cf = {{ {nums(comps)} }}, '
                               f'rig = {{ {nums(rig12)} }}, deg = {{ {nums(deg)} }} }}')
        speed = 'nil' if c.speed is None else lua_num(c.speed)
        plist = ', '.join(lua_str(p) for p in c.parts)
        lines.append(f'\t{{ key = {lua_str(c.key)}, name = {lua_str(c.name)}, label = {lua_str(c.label)}, '
                     f'loop = {str(c.loop).lower()}, priority = {lua_str(c.priority)}, length = {lua_num(c.length)}, '
                     f'speed = {speed}, nkeys = {len(times)}, parts = {{ {plist} }},\n\t\tsamples = {{\n\t\t\t'
                     + ',\n\t\t\t'.join(samples) + '\n\t\t} },')
    lines.append('}')
    lines.append('return { RIG = RIG, CLIPS = CLIPS }')
    write_atomic(os.path.join(ROBLOX, 'test', 'expected_anims.lua'), '\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
    make_anims()
