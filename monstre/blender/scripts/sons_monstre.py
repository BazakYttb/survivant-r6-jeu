"""Sons du monstre et des mises à mort, synthétisés (aucun enregistrement : libres de droits).
Sources (scie avec gigue, bruit rose / brun, impulsions), formants (filtres résonants), enveloppes, distorsion douce,
réverbération courte par convolution. Sortie : <dossier>/<nom>.ogg (Vorbis, 44,1 kHz, mono) et .wav si demandé.
usage : python sons_monstre.py dossier_sortie [--wav]"""
import os
import sys
import subprocess
import numpy as np
from scipy import signal

SR = 44100
RNG = np.random.default_rng(1666)


# ------------------------------------------------------------------------------------------------ briques
def t_(dur):
    return np.arange(int(dur * SR)) / SR


def noise(n):
    return RNG.standard_normal(n)


def pink(n):
    w = noise(n)
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, w) * 3.0


def brown(n):
    x = np.cumsum(noise(n))
    x = signal.lfilter([1, -1], [1, -0.995], x)
    return x / (np.abs(x).max() + 1e-9)


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype='bandpass', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='lowpass', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='highpass', fs=SR, output='sos'), x)


def reson(x, f, q):
    b, a = signal.iirpeak(f, q, fs=SR)
    return signal.lfilter(b, a, x)


def formants(x, fs_bw):
    return sum(g * reson(x, f, f / bw) for f, bw, g in fs_bw)


def env(n, a, d, s=0.0, r=None):
    """Attaque a, déclin d vers s ; r : relâchement final (secondes)."""
    e = np.ones(n)
    na, nd = int(a * SR), int(d * SR)
    if na:
        e[:na] = np.linspace(0, 1, na) ** 1.5
    if nd:
        e[na:na + nd] = 1 + (s - 1) * (1 - np.exp(-np.linspace(0, 5, len(e[na:na + nd]))))
    e[na + nd:] = s if (a or d) else 1
    if r:
        nr = int(r * SR)
        e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def decay(n, tau, delay=0.0):
    t = np.arange(n) / SR - delay
    return np.where(t >= 0, np.exp(-np.maximum(t, 0) / tau), 0.0)


def saw(f0_curve, jitter=0.0):
    """Dent de scie à fréquence variable (avec gigue) : source glottique grave."""
    f = f0_curve * (1 + jitter * lp(noise(len(f0_curve)), 30) * 3)
    ph = np.cumsum(f) / SR
    return 2 * (ph - np.floor(ph + 0.5))


def fry(n, rate=28.0, depth=0.8):
    """Modulation irrégulière (grain de la voix rauque)."""
    ph = np.cumsum(rate * (1 + 0.35 * lp(noise(n), 8) * 4)) / SR
    pulses = (0.5 + 0.5 * np.cos(2 * np.pi * ph)) ** 3
    return 1 - depth + depth * pulses


def drive(x, k):
    return np.tanh(k * x) / np.tanh(k)


def reverb(x, dur=0.8, wet=0.25, damp=3000):
    n = int(dur * SR)
    ir = noise(n) * np.exp(-np.arange(n) / SR / (dur / 5))
    ir = lp(ir, damp)
    ir /= np.abs(ir).sum() / 8
    y = signal.fftconvolve(x, ir)[:len(x) + n]
    out = np.zeros(len(y))
    out[:len(x)] = x
    return out * (1 - wet) + y * wet


def thump(dur, f0=80, f1=35, tau=0.12, click=0.3):
    t = t_(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.05)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / tau)
    c = lp(noise(len(t)), 2500) * np.exp(-t / 0.012) * click
    return s + c


def place(buf, x, at):
    i = int(at * SR)
    n = min(len(x), len(buf) - i)
    if n > 0:
        buf[i:i + n] += x[:n]
    return buf


def norm(x, peak=0.89):
    x = x - np.mean(x)
    return x / (np.abs(x).max() + 1e-9) * peak


def fade(x, a=0.005, r=0.02):
    na, nr = int(a * SR), int(r * SR)
    x = x.copy()
    if na:
        x[:na] *= np.linspace(0, 1, na)
    if nr:
        x[-nr:] *= np.linspace(1, 0, nr)
    return x


# ------------------------------------------------------------------------------------------------ sons
def voix(dur, f0, formes, rage=1.0, souffle=0.4, fry_rate=28, drive_k=3.0):
    n = int(dur * SR)
    src = saw(f0, 0.02) * fry(n, fry_rate, 0.85)
    sub = saw(f0 * 0.5, 0.03) * 0.6
    nz = bp(noise(n), 250, 4000) * souffle
    v = formants(src + sub + nz * 0.6, formes) + 0.3 * bp(nz, 800, 3500)
    return drive(norm(v) * rage, drive_k)


def grognement():
    d = 1.7
    t = t_(d)
    f0 = 58 + 8 * np.sin(np.pi * t / d) - 6 * t / d
    v = voix(d, f0, [(380, 90, 1.0), (760, 140, 0.7), (2400, 300, 0.25)], souffle=0.5, fry_rate=24)
    return reverb(v * env(len(t), 0.18, 0.3, 0.8, 0.45), 0.6, 0.18)


def hurlement():
    d = 2.6
    t = t_(d)
    f0 = 85 + 70 * np.sin(np.clip(t / 1.4, 0, 1) * np.pi * 0.9) * (1 - 0.3 * t / d) + 6 * np.sin(2 * np.pi * 5.5 * t)
    v = voix(d, f0, [(700, 160, 1.0), (1150, 200, 0.8), (2600, 350, 0.45), (3600, 500, 0.2)], rage=1.6, souffle=0.9,
             fry_rate=36, drive_k=4.5)
    v += 0.35 * hp(noise(len(t)), 2000) * env(len(t), 0.2, 0.6, 0.3)
    return reverb(v * env(len(t), 0.25, 0.8, 0.85, 0.6), 1.4, 0.32, 2400)


def hurlement_court():
    d = 0.95
    t = t_(d)
    f0 = 130 + 60 * np.sin(np.pi * t / d)
    v = voix(d, f0, [(800, 180, 1.0), (1300, 220, 0.8), (2900, 400, 0.5)], rage=1.8, souffle=1.0, fry_rate=40,
             drive_k=5)
    return reverb(v * env(len(t), 0.04, 0.25, 0.7, 0.25), 0.8, 0.25)


def reniflement():
    d = 0.75
    out = np.zeros(int(d * SR))
    for k, at in enumerate((0.0, 0.17, 0.32)):
        n = int(0.11 * SR)
        x = bp(noise(n), 1200 + 300 * k, 6500) * np.sin(np.linspace(0, np.pi, n)) ** 1.5
        x += 0.4 * bp(noise(n), 300, 900) * np.sin(np.linspace(0, np.pi, n))
        place(out, x * (0.8 + 0.2 * k), at)
    return reverb(out, 0.3, 0.12)


def souffle():
    d = 2.0
    t = t_(d)
    x = bp(pink(len(t)), 180, 1400) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.2
    x += 0.25 * voix(d, 45 + 3 * np.sin(2 * np.pi * t), [(300, 80, 1.0), (650, 120, 0.4)], souffle=1.2, fry_rate=18) * \
        np.sin(np.pi * t / d) ** 2
    return reverb(x, 0.5, 0.15)


def pas_lourd():
    d = 0.7
    x = thump(d, 95, 32, 0.13, 0.25)
    t = t_(d)
    x += 0.25 * bp(noise(len(t)), 700, 2600) * decay(len(t), 0.02)
    x += 0.12 * bp(noise(len(t)), 2000, 6000) * decay(len(t), 0.05, 0.03) * (RNG.random(len(t)) < 0.02)
    return reverb(x, 0.4, 0.15)


def saisie():
    d = 0.45
    t = t_(d)
    x = 0.8 * bp(noise(len(t)), 500, 4200) * decay(len(t), 0.05)
    x += 0.6 * thump(d, 110, 50, 0.06, 0.1)
    x += 0.3 * bp(noise(len(t)), 1500, 5000) * decay(len(t), 0.12, 0.04) * (0.5 + 0.5 * np.sin(2 * np.pi * 37 * t))
    return x


def squelch(dur, f_hi=2200, f_lo=280, tau=0.09):
    """Bruit mouillé : filtre passe-bas résonant dont la fréquence chute."""
    n = int(dur * SR)
    x = noise(n)
    out = np.zeros(n)
    fc = f_lo + (f_hi - f_lo) * np.exp(-np.arange(n) / SR / tau)
    blk = 256
    zi = None
    for i in range(0, n, blk):
        b, a = signal.iirpeak(fc[i], 3.5, fs=SR)
        seg, zi = signal.lfilter(b, a, x[i:i + blk], zi=zi if zi is not None else signal.lfilter_zi(b, a) * 0)
        out[i:i + blk] = seg
    return out * decay(n, tau * 1.6) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * np.arange(n) / SR))


def clics(dur, n, f_lo=1500, f_hi=6500, spread=0.06, start=0.0):
    out = np.zeros(int(dur * SR))
    for _ in range(n):
        at = start + RNG.random() * spread
        m = int(0.012 * SR)
        imp = noise(m) * np.exp(-np.arange(m) / SR / 0.002)
        f = RNG.uniform(f_lo, f_hi)
        place(out, reson(imp, f, 6) * RNG.uniform(0.5, 1.0), at)
    return out


def morsure():
    d = 0.8
    x = 1.2 * clics(d, 7, 1800, 7000, 0.05)
    x += 0.9 * squelch(d, 2400, 300, 0.1)
    x += 0.5 * thump(d, 120, 45, 0.07, 0.1)
    x += place(np.zeros(int(d * SR)), 0.5 * squelch(0.4, 1600, 250, 0.06), 0.12)
    return reverb(x, 0.35, 0.12)


def dechirure():
    d = 1.1
    n = int(d * SR)
    out = np.zeros(n)
    t = 0.0
    while t < d - 0.03:
        g = int(RNG.uniform(0.004, 0.016) * SR)
        x = bp(noise(g), RNG.uniform(700, 1500), RNG.uniform(3500, 7000)) * np.hanning(g) * RNG.uniform(0.4, 1.0)
        place(out, x, t)
        dens = 0.5 + 2.5 * np.sin(np.pi * t / d)
        t += RNG.uniform(0.002, 0.02) / dens
    out = out * env(n, 0.05, 0.3, 0.8, 0.25)
    out += 0.6 * squelch(d, 1800, 260, 0.25)
    return reverb(out, 0.4, 0.15)


def craquement():
    d = 0.6
    x = 1.4 * clics(d, 4, 900, 4500, 0.025)
    t = t_(d)
    imp = np.zeros(len(t))
    imp[int(0.004 * SR)] = 1.0
    x += 2.5 * reson(imp, 1450, 12) * decay(len(t), 0.05)
    x += 0.5 * thump(d, 100, 45, 0.06, 0.2)
    return reverb(x, 0.3, 0.1)


def mastication():
    d = 2.52                                    # boucle : 6 temps de 0,42 s
    out = np.zeros(int(d * SR))
    for k in range(6):
        at = k * 0.42
        place(out, 0.8 * squelch(0.3, RNG.uniform(1400, 2600), RNG.uniform(220, 360), RNG.uniform(0.05, 0.09)), at + 0.02)
        if k % 2 == 1:
            place(out, 0.6 * clics(0.2, 3, 2000, 6000, 0.03), at + 0.1)
        place(out, 0.25 * thump(0.2, 90, 50, 0.05, 0.0), at)
    out += 0.15 * bp(brown(len(out)), 80, 400)
    return reverb(fade(out, 0.002, 0.004), 0.3, 0.1)


def impact():
    d = 0.6
    t = t_(d)
    x = 1.2 * thump(d, 85, 30, 0.14, 0.5)
    x += 0.6 * bp(noise(len(t)), 600, 3000) * decay(len(t), 0.03)
    x += 0.4 * squelch(d, 1600, 250, 0.05)
    return reverb(x, 0.4, 0.15)


def chute_corps():
    d = 1.1
    out = np.zeros(int(d * SR))
    place(out, 1.0 * thump(0.6, 75, 30, 0.14, 0.4), 0.0)
    place(out, 0.55 * thump(0.5, 95, 40, 0.09, 0.3), 0.16)
    place(out, 0.35 * thump(0.4, 120, 50, 0.06, 0.3), 0.29)
    n = len(out)
    out += 0.18 * bp(noise(n), 900, 4500) * decay(n, 0.25, 0.02)
    return reverb(out, 0.5, 0.18)


def trainer():
    d = 3.0                                     # boucle (fondu enchaîné des bords)
    n = int(d * SR)
    t = t_(d)
    x = bp(pink(n), 140, 1600) * (0.6 + 0.4 * np.abs(lp(noise(n), 3) * 20).clip(0, 1))
    x *= 0.65 + 0.35 * np.sin(2 * np.pi * t / 1.5 + 0.3) ** 2      # au rythme des pas (traîner : 1,5 s)
    for _ in range(6):
        at = RNG.uniform(0.1, d - 0.4)
        m = int(RNG.uniform(0.08, 0.25) * SR)
        place(x, 0.5 * bp(noise(m), 1200, 5000) * np.hanning(m), at)
    k = int(0.25 * SR)
    x[:k] = x[:k] * np.linspace(0, 1, k) + x[-k:] * np.linspace(1, 0, k)
    return x[:n - k]


def cri_victime():
    d = 1.3
    t = t_(d)
    f0 = 300 + 60 * np.sin(np.pi * np.clip(t / 0.5, 0, 1)) - 50 * t + 8 * np.sin(2 * np.pi * 6 * t)
    src = saw(f0, 0.01) * (0.9 + 0.1 * fry(len(t), 60, 0.5))
    v = formants(src + 0.3 * bp(noise(len(t)), 400, 5000), [(820, 120, 1.0), (1250, 150, 0.7), (2800, 300, 0.4),
                                                           (3500, 400, 0.25)])
    v = drive(norm(v), 2.0) * env(len(t), 0.06, 0.4, 0.75, 0.5)
    v = lp(v, 5000)
    return reverb(v, 0.9, 0.3)


def eclaboussure():
    d = 0.5
    t = t_(d)
    x = 1.0 * squelch(d, 2600, 400, 0.04)
    x += 0.7 * bp(noise(len(t)), 400, 3200) * decay(len(t), 0.03)
    x += 0.5 * clics(d, 10, 3000, 9000, 0.25, 0.04)
    return reverb(x, 0.3, 0.1)


def battement():
    d = 0.75
    out = np.zeros(int(d * SR))
    place(out, 1.0 * thump(0.25, 62, 38, 0.06, 0.0), 0.0)
    place(out, 0.7 * thump(0.25, 58, 36, 0.07, 0.0), 0.24)
    return lp(out, 300, 4)


def toux():
    d = 0.8
    out = np.zeros(int(d * SR))
    for at, g in ((0.0, 1.0), (0.3, 0.75)):
        n = int(0.22 * SR)
        tt = np.arange(n) / SR
        src = bp(noise(n), 200, 5000) + 0.4 * saw(np.full(n, 140.0), 0.02)
        v = formants(src, [(500, 120, 1.0), (1500, 200, 0.6), (2500, 300, 0.3)])
        v = norm(v) * np.exp(-tt / 0.07) * np.clip(tt / 0.008, 0, 1) * g
        place(out, v, at)
    return reverb(lp(out, 6000), 0.4, 0.15)


def acouphene():
    d = 3.2
    t = t_(d)
    x = np.sin(2 * np.pi * 6200 * t) * 0.6 + np.sin(2 * np.pi * 6230 * t) * 0.3
    x *= env(len(t), 0.05, 0.4, 0.6, 1.8)
    x += 0.05 * hp(noise(len(t)), 5000) * env(len(t), 0.05, 0.4, 0.4, 1.8)
    return x


SONS = {'grognement': grognement, 'hurlement': hurlement, 'hurlement_court': hurlement_court,
        'reniflement': reniflement, 'souffle': souffle, 'pas_lourd': pas_lourd, 'saisie': saisie, 'morsure': morsure,
        'dechirure': dechirure, 'craquement': craquement, 'mastication': mastication, 'impact': impact,
        'chute_corps': chute_corps, 'trainer': trainer, 'cri_victime': cri_victime, 'eclaboussure': eclaboussure,
        'battement': battement, 'toux': toux, 'acouphene': acouphene}


def ecrire_wav(path, x):
    from scipy.io import wavfile
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))


def main():
    out = sys.argv[1]
    garder_wav = '--wav' in sys.argv
    os.makedirs(out, exist_ok=True)
    for nom, fn in SONS.items():
        x = norm(fade(fn()), 0.89)
        wav = os.path.join(out, nom + '.wav')
        ecrire_wav(wav, x)
        ogg = os.path.join(out, nom + '.ogg')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '6', ogg], check=True)
        if not garder_wav:
            os.remove(wav)
        print('%-16s %.2f s  %5.1f Ko' % (nom, len(x) / SR, os.path.getsize(ogg) / 1024))


if __name__ == '__main__':
    main()
