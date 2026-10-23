"""Re-target the limb anatomy to the jointed rig: every arm / leg part goes to its upper or lower segment
(rig_spec.LIMBS), and the parts that cross the elbow or knee (vessels, nerves, ligaments, tendons) are built
once per segment and clipped at the joint plane (the cut is capped)."""
import copy
import rig_spec as RS


def segment(parts, plan, labels):
    """plan[base name] = 'upper' | 'lower' | 'split'; labels = (upper label, lower label) for split parts."""
    out = []
    for p in parts:
        limb, base = p.name.split('_', 1)
        upper, lower, z = RS.LIMBS[limb]
        how = plan[base]
        if how in ('upper', 'lower'):
            reg = upper if how == 'upper' else lower
            p.name, p.region = f'{reg}_{base}', reg
            out.append(p)
            continue
        for reg, keep, lab in ((upper, 'above', labels[0]), (lower, 'below', labels[1])):
            q = copy.copy(p)
            q.name, q.region, q.clip = f'{reg}_{base}', reg, (keep, z)
            q.info = f'{p.info} - partie {lab}'
            out.append(q)
    return out
