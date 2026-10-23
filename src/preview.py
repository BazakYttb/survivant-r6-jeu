"""python preview.py out.png view [patterns...] [!exclude_pattern...] [--skin] [--skin-alpha 1.0] [--res 800x1000] [--samples 16] [--elev 8] [--azim A] [--persp]
--skin adds the R6 skin parts (Skin_*) to the selection; otherwise they are left out unless a pattern names them."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blend_lib as B

a = sys.argv[1:]
out, view = a[0], a[1]
opts = a[2:]
skin = '--skin' in opts
def opt(k, d):
    if k in opts:
        return opts[opts.index(k) + 1]
    return d
res = tuple(int(x) for x in opt('--res', '800x1000').split('x'))
samples = int(opt('--samples', '16'))
elev = float(opt('--elev', '8'))
azim = opt('--azim', None)
pats = [p for i, p in enumerate(opts) if not p.startswith('--') and (i == 0 or opts[i - 1] not in ('--res', '--samples', '--elev', '--azim', '--skin-alpha', '--view', '--exposure'))]
skin_alpha = float(opt('--skin-alpha', '1.0'))
B.reset()
man = B.manifest() if os.path.exists(os.path.join(B.BUILD, 'manifest.json')) else {}
excl = [p[1:] for p in pats if p.startswith('!')]
pats = [p for p in pats if not p.startswith('!')]
import fnmatch
names = [n for n in B.part_names(pats) if not any(fnmatch.fnmatch(n, e) for e in excl)]
if not any(p.startswith('Skin') for p in pats):
    names = [n for n in names if not n.startswith('Skin_')]
if skin:
    names += [n for n in B.part_names(['Skin_*']) if n not in names]
objs = [B.load_part(n, man, skin_alpha=skin_alpha) for n in names]
B.setup_render(res, samples, view=opt('--view', 'AgX'), exposure=float(opt('--exposure', '0')))
B.camera(objs, view, elev=elev, azim=None if azim is None else float(azim), ortho='--persp' not in opts)
B.render(os.path.abspath(out))
print('rendered', len(objs), 'objects')
