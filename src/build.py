"""Build all anatomy meshes -> build/parts/<name>.npz + build/manifest.json
usage: python build.py [substring filters...] [-j N]"""
import sys, os, json, time, fnmatch
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'build', 'parts')


MODULES = ('head', 'torso_skel', 'torso_thorax', 'torso_abdomen', 'torso_vessels', 'arms', 'legs', 'survivor')


def load_parts():
    mods = []
    for m in MODULES:
        try:
            mods.append(__import__(m))
        except ModuleNotFoundError as e:
            if e.name == m:
                continue
            raise
    P = []
    for m in mods:
        P += m.parts()
    return P


def job(name):
    from parts import build_part
    P = {p.name: p for p in load_parts()}
    p = P[name]
    extra = {}
    try:
        if p.mesh is not None:          # analytic mesh with exact per-corner normals (cn)
            v, f, c, cn = p.mesh()
            v, f, c = v.astype(np.float32), f.astype(np.int32), np.clip(c, 0, 1).astype(np.float32)
            extra['cn'] = np.asarray(cn, np.float32)
            print(f'{p.name:40s} {len(f):6d} tris  analytic', flush=True)
        else:
            v, f, c = build_part(p)
        if p.cat not in ('skin', 'gear'):
            from skin import contain
            v = contain(v, p.mapping.region).astype(np.float32)
        if p.clip is not None:               # limb part crossing the elbow / knee: keep this segment's side
            from meshops import clip_plane
            v, f, c = clip_plane(v, f, c, p.clip[1], p.clip[0])
            v, f, c = v.astype(np.float32), f.astype(np.int32), c.astype(np.float32)
            extra.pop('cn', None)
            print(f'{p.name:40s} {len(f):6d} tris  clipped {p.clip[0]} z={p.clip[1]}', flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        return name, None
    np.savez_compressed(os.path.join(OUT, name + '.npz'), v=v, f=f, c=c, **extra)
    return name, dict(name=name, region=p.region, cat=p.cat, base=list(p.base), tris=int(len(f)), info=p.info)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    nj = 4
    if '-j' in args:
        i = args.index('-j'); nj = int(args[i + 1]); del args[i:i + 2]
    os.makedirs(OUT, exist_ok=True)
    P = load_parts()
    names = [p.name for p in P if not args or any(fnmatch.fnmatch(p.name, a) for a in args)]
    # biggest first for better load balancing
    order = sorted(names, key=lambda n: -[p.target for p in P if p.name == n][0])  # analytic parts are instant
    t0 = time.time()
    man_path = os.path.join(OUT, '..', 'manifest.json')
    results = {}
    with Pool(nj, maxtasksperchild=1) as pool:
        for name, meta in pool.imap_unordered(job, order):
            if meta:
                results[name] = meta
            else:
                print('FAILED', name)
    # several builds may run at once: update the manifest under an exclusive lock
    try:
        import fcntl
    except ImportError:                 # Windows: no flock (builds are not run concurrently there)
        fcntl = None
    with open(man_path + '.lock', 'w') as lk:
        if fcntl:
            fcntl.flock(lk, fcntl.LOCK_EX)
        man = json.load(open(man_path)) if os.path.exists(man_path) else {}
        man.update(results)
        man = {k: v for k, v in man.items() if os.path.exists(os.path.join(OUT, k + '.npz'))}
        tmp = man_path + '.tmp'
        json.dump(man, open(tmp, 'w'), indent=1)
        os.replace(tmp, man_path)
    tot = sum(m['tris'] for m in man.values())
    print(f'done {len(names)} parts in {time.time() - t0:.0f}s; manifest {len(man)} parts, {tot} tris')
