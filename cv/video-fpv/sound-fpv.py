"""Sound design de la vidéo « Le drone FPV » : musique, effets et mixage avec la voix.

Tout est synthétisé, comme pour le CV vidéo :
  - musique : la mineur à 112 BPM, nappes, basse pompée, arpège en doubles croches, batterie,
    une intensité par chapitre ;
  - effets : moteurs brushless (vol en immersion, vol stationnaire, essai moteurs), pièces qui se
    posent, fils tirés, soudure, bips du contrôleur, clavier, déclencheurs photo, whooshs, impacts ;
  - réverbération par convolution, ducking par la voix, limiteur.

Usage : python sound-fpv.py sync-fpv.json sortie.wav
"""
import json
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
RNG = np.random.default_rng(7)


# ------------------------------------------------------------------ outils
def secs(n):
    return int(round(n * SR))


def tvec(dur):
    return np.arange(secs(dur)) / SR


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, min(f, SR * .45), 'low', fs=SR, output='sos'), x, axis=0)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, 'high', fs=SR, output='sos'), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, min(hi, SR * .45)], 'band', fs=SR, output='sos'), x, axis=0)


def svf_sweep(x, f0, f1, q=2.0, mode='bp', curve=1.0):
    """Filtre à variables d'état dont la fréquence glisse de f0 à f1 (balayage exponentiel)."""
    n = len(x)
    u = np.linspace(0, 1, n) ** curve
    f = f0 * (f1 / f0) ** u
    g = 2 * np.sin(np.pi * np.minimum(f, SR / 6) / SR)
    damp = 1.0 / q
    low = band = 0.0
    out = np.empty(n)
    for i in range(n):
        high = x[i] - low - damp * band
        band += g[i] * high
        low += g[i] * band
        out[i] = band if mode == 'bp' else (low if mode == 'lp' else high)
    return out


def env_adsr(n, a, d, s, r, sustain_len=None):
    a, d, r = secs(a), secs(d), secs(r)
    sl = n - a - d - r if sustain_len is None else secs(sustain_len)
    sl = max(sl, 0)
    e = np.concatenate([np.linspace(0, 1, a, endpoint=False), np.linspace(1, s, d, endpoint=False),
                        np.full(sl, s), np.linspace(s, 0, r)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def pan2(x, p):
    """Panoramique à puissance constante ; p de -1 (gauche) à 1 (droite), scalaire ou tableau."""
    p = np.clip(p, -1, 1)
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def place(bus, sig, t):
    i = secs(t)
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(len(bus), i + len(sig))
    if j > i:
        bus[i:j] += sig[:j - i]


def saw_add(f, t, nh=24, roll=1.25, phase=0.0):
    """Dent de scie additive, adoucie (pas d'aliasing)."""
    out = np.zeros_like(t)
    for k in range(1, nh + 1):
        if k * np.max(f) > SR * .42:
            break
        out += np.sin(2 * np.pi * k * f * t + phase * k) / k ** roll
    return out


def make_ir(rt=2.6, pre=.022, bright=5200, seed=3):
    r = np.random.default_rng(seed)
    n = secs(rt * 1.3)
    t = np.arange(n) / SR
    decay = np.exp(-6.91 * t / rt)
    ir = r.standard_normal((n, 2)) * decay[:, None]
    ir = lp(ir, bright, 1)
    # premières réflexions
    for d, g in [(.011, .55), (.017, .42), (.029, .33), (.041, .25)]:
        k = secs(d)
        ir[k, 0] += g
        ir[k + secs(.003), 1] += g * .9
    ir = np.concatenate([np.zeros((secs(pre), 2)), ir])
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


IR_HALL = make_ir(2.8, .025, 5000, 3)
IR_ROOM = make_ir(1.1, .012, 7000, 5)


def reverb(x, ir, wet):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    y = np.stack([fftconvolve(x[:, 0], ir[:, 0])[:len(x)], fftconvolve(x[:, 1], ir[:, 1])[:len(x)]], 1)
    return y * wet

# ------------------------------------------------------------------ chronologie
CFG = json.load(open(sys.argv[1]))
DUR = CFG['duration']
N = secs(DUR)
WARP = CFG['warp']
CUE = CFG['cues']
VW = [w[0] for w in WARP]
AW = [w[1] for w in WARP]


def a2v(a):
    """Temps d'animation -> temps vidéo."""
    return float(np.interp(a, AW, VW))


def v2a(v):
    return np.interp(v, VW, AW)


CH = VW[1:-1]          # débuts des chapitres 2 à 7 (temps vidéo)
CH_START = VW[:-1]


def chapter(t):
    return int(np.searchsorted(VW[1:], t, side='right')) + 1

# ------------------------------------------------------------------ voix
voice = np.zeros((N, 2))
for v in CFG['voice']:
    a, sr = sf.read(v['file'], dtype='float64')
    if a.ndim > 1:
        a = a.mean(1)
    assert sr == SR
    a = hp(a, 75, 2)
    place(voice, np.stack([a, a], 1), v['at'])
voice *= 10 ** (-3 / 20) / (np.max(np.abs(voice)) + 1e-9)
venv = np.abs(voice[:, 0])
win = secs(.04)
venv = np.convolve(venv, np.ones(win) / win, mode='same')
venv = venv / (np.percentile(venv[venv > 1e-4], 90) + 1e-9)
venv = np.clip(venv, 0, 1)
duck = np.empty_like(venv)
g = 0.0
att, rel = 1 - np.exp(-1 / secs(.03)), 1 - np.exp(-1 / secs(.45))
step = 64
for i in range(0, len(venv), step):
    target = venv[i]
    g += (target - g) * (1 - (1 - (att if target > g else rel)) ** step)
    duck[i:i + step] = g
duck_gain = 1 - .72 * duck

# ------------------------------------------------------------------ musique
# la mineur, 112 BPM : i – VI – III – VII en accords étendus, plus électronique que le CV
BPM = 112
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [
    [45, 52, 55, 59, 60, 64],   # Am9
    [41, 48, 52, 55, 57, 60],   # Fmaj9
    [40, 48, 52, 55, 59, 62],   # Cmaj9/E
    [43, 50, 55, 57, 59, 64],   # G6/9
]
ROOTS = [33, 29, 36, 31]
TOPO_V = CUE['topo']
FIN_V = CUE['fin']


def section(t):
    c = chapter(t)
    if c == 1:
        return 'intro' if t < CUE['c1d'] - .2 else 'lift'
    if c == 2:
        return 'build1'
    if c == 3:
        return 'digital'
    if c == 4:
        return 'drive'
    if c == 5:
        return 'groove' if t < TOPO_V else 'wide'
    if c == 6:
        return 'calm'
    return 'rise' if t < FIN_V else 'outro'


LVL = {  # pad, basse, arpège, batterie
    'intro': (.55, 0, 0, 0), 'lift': (.55, .7, .4, .4), 'build1': (.5, .8, .55, .6),
    'digital': (.45, .75, .9, .55), 'drive': (.5, .8, .8, .72), 'groove': (.5, .8, .75, .68),
    'wide': (.65, .8, .7, .6), 'calm': (.6, .5, .35, 0), 'rise': (.6, .8, .8, .68), 'outro': (.75, .6, 0, 0)}
CUT = {'intro': 800, 'lift': 1400, 'build1': 1600, 'digital': 1900, 'drive': 2600, 'groove': 2400,
       'wide': 3000, 'calm': 1300, 'rise': 2800, 'outro': 2200}

music = np.zeros((N, 2))
pad_bus = np.zeros((N, 2))
nbars = int(np.ceil(DUR / BAR)) + 1
for b in range(nbars):
    t0 = b * BAR
    if t0 > DUR:
        break
    sec = section(t0 + .1)
    ch = CHORDS[0] if sec == 'outro' else CHORDS[b % 4]
    dur = BAR + 1.8
    t = tvec(dur)
    sig = np.zeros((len(t), 2))
    for j, m in enumerate(ch):
        for det, pn in [(-.08, -.6), (0, 0), (.08, .6)]:
            f = midi(m) * 2 ** (det / 12)
            vib = 1 + .0018 * np.sin(2 * np.pi * (.19 + j * .03) * t + j)
            w = saw_add(f * vib, t, nh=18, roll=1.5, phase=RNG.uniform(0, 6.28))
            sig += pan2(w * (.55 if j == 0 else .38), pn * (.4 + .1 * j))
    sig = lp(sig, CUT[sec], 2)
    e = env_adsr(len(t), .9, .3, .85, 1.8, sustain_len=BAR - 1.0)
    place(pad_bus, sig * e[:, None] * LVL[sec][0] * .065, t0)
pad_bus[:secs(2.5)] *= np.linspace(0, 1, secs(2.5))[:, None] ** 1.4

# basse : croches avec « pompe » (sidechain) sur les sections rythmées
bass = np.zeros((N, 2))
for b in range(nbars):
    t0 = b * BAR
    if t0 > DUR:
        break
    f = midi(ROOTS[b % 4] if section(t0 + .1) != 'outro' else 33)
    for k in range(8):
        tb = t0 + k * BEAT / 2
        lv = LVL[section(tb)][1]
        if lv == 0:
            continue
        tt = tvec(BEAT / 2)
        s = np.sin(2 * np.pi * f * tt) + .35 * np.sin(4 * np.pi * f * tt) + .12 * saw_add(np.array([f * 2]), tt, nh=6)
        pump = (1 - np.exp(-tt * 38)) * np.exp(-tt * 3)
        place(bass, pan2(lp(s * pump, 300) * .15 * lv, 0), tb)

# arpège en doubles croches, écho ping-pong
arp = np.zeros((N, 2))
pattern = [0, 3, 4, 5, 4, 3, 2, 3, 0, 3, 4, 5, 4, 5, 3, 2]
for b in range(nbars):
    t0 = b * BAR
    if t0 > DUR:
        break
    ch = CHORDS[b % 4]
    for k in range(16):
        tb = t0 + k * BEAT / 4
        lv = LVL[section(tb)][2]
        if lv == 0:
            continue
        m = ch[pattern[k]] + 12
        tt = tvec(.35)
        f = midi(m)
        s = np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 20) \
            + .15 * np.sin(2 * np.pi * 3 * f * tt) * np.exp(-tt * 30)
        s *= np.exp(-tt * 13) * (1 - np.exp(-tt * 500)) * (1 if k % 4 == 0 else .7)
        place(arp, pan2(s * .032 * lv, (-.4, .4)[k % 2]), tb)
d = secs(BEAT * .75)
echo = np.zeros_like(arp)
echo[d:, 1] += arp[:-d, 0] * .4
echo[d:, 0] += arp[:-d, 1] * .4
echo[2 * d:] += arp[:-2 * d] * .18
arp = lp(arp + echo, 7000)

drums = np.zeros((N, 2))


def kick(level=1.0):
    tt = tvec(.5)
    f = 48 + 120 * np.exp(-tt * 30)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7)
    s += hp(RNG.standard_normal(len(tt)), 3000) * np.exp(-tt * 300) * .15
    return pan2(np.tanh(s * 1.5) * .32 * level, 0)


def hat(level=1.0, open_=False):
    tt = tvec(.25)
    s = hp(RNG.standard_normal(len(tt)), 7500, 2) * np.exp(-tt * (16 if open_ else 60))
    return pan2(lp(s, 12000) * .02 * level, .25)


def clap(level=1.0):
    tt = tvec(.4)
    n = bp(RNG.standard_normal(len(tt)), 900, 6000)
    e = np.exp(-tt * 18) + .6 * np.exp(-np.abs(tt - .012) * 900) + .5 * np.exp(-np.abs(tt - .024) * 900)
    return pan2(n * e * .07 * level, -.1)


for b in range(nbars):
    t0 = b * BAR
    if t0 > DUR:
        break
    for k in range(4):
        tb = t0 + k * BEAT
        s = section(tb)
        lv = LVL[s][3]
        if lv == 0:
            continue
        if s in ('lift', 'build1', 'digital', 'wide'):
            if k in (0, 2) or s == 'build1':
                place(drums, kick(.75 * lv), tb)
            place(drums, hat(.6 * lv), tb + BEAT / 2)
            if s == 'digital':
                place(drums, hat(.3), tb + BEAT / 4 * 3)
        else:
            place(drums, kick(lv), tb)
            if k in (1, 3):
                place(drums, clap(lv), tb)
            place(drums, hat(.8 * lv), tb + BEAT / 2)
            place(drums, hat(.4 * lv), tb + BEAT / 4)
            place(drums, hat(.45 * lv), tb + BEAT / 4 * 3)
            if s == 'rise' and k == 3 and b % 2:
                place(drums, hat(.6, True), tb + BEAT / 2)
# pas de batterie pendant l'arrivée de chaque chapitre (respiration)
for t in CH:
    i0, i1 = secs(t - .3), secs(t + .9)
    drums[i0:i1] *= (1 - np.sin(np.linspace(0, np.pi, i1 - i0)) ** .5)[:, None]
music = pad_bus + bass + arp + drums

# ------------------------------------------------------------------ effets
sfx = np.zeros((N, 2))
send = np.zeros((N, 2))  # envoi vers la grande réverbération


def whoosh(tc, dur=1.1, up=True, level=1.0, pan_from=-.8, pan_to=.8):
    n = secs(dur)
    x = RNG.standard_normal(n)
    f0, f1 = (250, 5500) if up else (5000, 300)
    y = svf_sweep(x, f0, f1, q=1.6, curve=.8)
    y += .5 * svf_sweep(RNG.standard_normal(n), f0 * .6, f1 * .6, q=3)
    u = np.linspace(0, 1, n)
    e = np.sin(np.pi * u) ** 2.2
    y = lp(y * e, 8500, 2)
    y /= np.max(np.abs(y)) + 1e-9
    s = pan2(y * .2 * level, np.linspace(pan_from, pan_to, n))
    place(sfx, s, tc - dur / 2)
    place(send, s * .5, tc - dur / 2)


def impact(t, level=1.0, sub=58):
    tt = tvec(2.6)
    f = sub * .62 + sub * .5 * np.exp(-tt * 9)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.2)
    body = lp(RNG.standard_normal(len(tt)), 380) * np.exp(-tt * 9) * .9
    snap = bp(RNG.standard_normal(len(tt)), 1800, 6000) * np.exp(-tt * 90) * .14
    sig = np.tanh((s * .9 + body + snap) * 1.2) * .27 * level
    st = pan2(sig, 0)
    place(sfx, st, t)
    place(send, st * .9, t)


def bell(f, level=1.0, dur=3.0):
    tt = tvec(dur)
    idx = 2.2 * np.exp(-tt * 3)
    mod = np.sin(2 * np.pi * f * 3.5 * tt) * idx
    s = np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt * 1.6)
    s += .3 * np.sin(2 * np.pi * f * 2.01 * tt) * np.exp(-tt * 3)
    return s * (1 - np.exp(-tt * 300)) * level


def reverse_swell(t_end, f, dur=.9, level=1.0):
    """Cloche inversée qui « aspire » vers le temps fort."""
    b = bell(f, 1, 2.2)
    wet = reverb(b, IR_HALL, 1.0)[:, 0] + b * .3
    r = wet[:secs(dur)][::-1]
    r *= np.linspace(0, 1, len(r)) ** 2
    s = pan2(r * .06 * level, 0)
    place(sfx, s, t_end - dur)


def tonal_hit(t, m, level=1.0):
    reverse_swell(t, midi(m), .7, level)
    impact(t, .55 * level, 62)
    b = bell(midi(m), .09 * level, 3.0)
    s = np.stack([b, np.roll(b, secs(.007))], 1)
    place(sfx, s, t)
    place(send, s * 1.2, t)


def riser(t0, t1, level=1.0):
    dur = t1 - t0
    n = secs(dur)
    y = svf_sweep(RNG.standard_normal(n), 400, 9000, q=2.2, curve=1.6)
    tt = np.arange(n) / SR
    f = 110 * 2 ** (2 * (tt / dur) ** 1.5)
    tone = (np.sin(2 * np.pi * np.cumsum(f) / SR) + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * .5)
    e = (tt / dur) ** 2.4
    y = lp(y, 9000, 2)
    y /= np.max(np.abs(y * e)) + 1e-9
    sig = (y * .2 + tone * .045) * e * level
    s = pan2(sig, np.sin(np.linspace(0, 6 * np.pi, n)) * .4)
    place(sfx, s, t0)
    place(send, s * .6, t0)


def glass(t, m, level=1.0, pan=0.0):
    tt = tvec(1.2)
    f = midi(m)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 5.5) + .45 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 9) \
        + .2 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 16)
    s *= (1 - np.exp(-tt * 900))
    click = hp(RNG.standard_normal(len(tt)), 4000) * np.exp(-tt * 400) * .25
    sig = pan2((s * .07 + click * .05) * level, pan)
    place(sfx, sig, t)
    place(send, sig * .9, t)


def soft_swoosh(t, dur=.6, level=1.0, pan=0.0):
    n = secs(dur)
    y = svf_sweep(RNG.standard_normal(n), 1800, 600, q=1.2)
    e = np.sin(np.pi * np.linspace(0, 1, n)) ** 3
    s = pan2(y * e * .07 * level, pan)
    place(sfx, s, t - dur * .45)
    place(send, s * .4, t - dur * .45)


def shutter(t, pan=0.0, level=1.0):
    tt = tvec(.12)
    c1 = bp(RNG.standard_normal(len(tt)), 2500, 9000) * np.exp(-tt * 260)
    c2 = np.roll(bp(RNG.standard_normal(len(tt)), 1500, 6000) * np.exp(-tt * 200), secs(.038))
    thump = np.sin(2 * np.pi * 180 * tt) * np.exp(-tt * 90) * .4
    s = pan2((c1 * .5 + c2 * .35 + thump) * .09 * level, pan)
    place(sfx, s, t)
    place(send, s * .25, t)


def sparkle(t, pan):
    tt = tvec(.08)
    f = RNG.uniform(3200, 6400)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 70)
    place(sfx, pan2(s * .012, pan), t)


def pluck(t, m, level=1.0, pan=0.0):
    tt = tvec(1.6)
    f = midi(m)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 4) + .5 * np.sin(2 * np.pi * 4 * f * tt) * np.exp(-tt * 14) \
        + .2 * np.sin(2 * np.pi * 10.2 * f * tt) * np.exp(-tt * 30)
    sig = pan2(s * (1 - np.exp(-tt * 600)) * .075 * level, pan)
    place(sfx, sig, t)
    place(send, sig * .8, t)


# ------------------------------------------------------------------ effets propres au FPV
bed = np.zeros((N, 2))  # sons continus (moteurs, vent) : baissés plus fort sous la voix
def clunk(t, level=1.0, pan=0.0, ring=1.0):
    """Pièce qui se pose : choc sourd + résonance métallique inharmonique + petit clic."""
    tt = tvec(1.0)
    thump = np.sin(2 * np.pi * (90 + 60 * np.exp(-tt * 40)) * tt) * np.exp(-tt * 22)
    met = sum(np.sin(2 * np.pi * f * tt + k) * np.exp(-tt * (14 + 6 * k)) * a
              for k, (f, a) in enumerate([(1230, .5), (1987, .35), (2871, .25), (4120, .15)]))
    click = hp(RNG.standard_normal(len(tt)), 3500) * np.exp(-tt * 500)
    s = pan2((thump * .55 + met * .12 * ring + click * .12) * .4 * level, pan)
    place(sfx, s, t)
    place(send, s * .35, t)


def snap(t, level=1.0, pan=0.0):
    tt = tvec(.08)
    s = bp(RNG.standard_normal(len(tt)), 2000, 9000) * np.exp(-tt * 350) + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 200) * .4
    place(sfx, pan2(s * .08 * level, pan), t)


def tick(t, level=1.0, pan=0.0, f=3200):
    tt = tvec(.05)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 260) + hp(RNG.standard_normal(len(tt)), 6000) * np.exp(-tt * 600) * .3
    place(sfx, pan2(s * .05 * level, pan), t)


def blip(t, f, level=1.0, pan=0.0, dur=.09):
    tt = tvec(dur)
    s = np.sign(np.sin(2 * np.pi * f * tt)) * .5 + np.sin(2 * np.pi * f * tt)
    s = lp(s, 5000) * np.exp(-tt * 30) * (1 - np.exp(-tt * 2000))
    sig = pan2(s * .03 * level, pan)
    place(sfx, sig, t)
    place(send, sig * .5, t)


def zip_(t, dur=.9, level=1.0, pan=0.0):
    """Fil qui se tire : bruit filtré qui glisse vers l'aigu."""
    n = secs(dur)
    y = svf_sweep(RNG.standard_normal(n), 700, 3800, q=4, curve=.7)
    u = np.linspace(0, 1, n)
    e = np.sin(np.pi * u) ** 1.5 * (1 + .5 * np.sin(2 * np.pi * 38 * u * dur))
    y = y / (np.max(np.abs(y)) + 1e-9)
    s = pan2(y * e * .06 * level, np.linspace(pan - .25, pan + .25, n))
    place(sfx, s, t)


def sizzle(t, dur=1.1, level=1.0, pan=0.0):
    """Fer à souder sur l'étain : grésillement + crépitements + petit souffle de flux."""
    n = secs(dur + .4)
    tt = np.arange(n) / SR
    hiss = bp(RNG.standard_normal(n), 3000, 11000) * np.exp(-tt * 2.6)
    crack = np.zeros(n)
    for k in range(int(70 * dur)):
        i = int(RNG.uniform(0, secs(dur)) * RNG.uniform(.3, 1))
        L = int(RNG.uniform(40, 160))
        if i + L < n:
            crack[i:i + L] += RNG.standard_normal(L) * np.exp(-np.arange(L) / (L / 5)) * RNG.uniform(.2, 1)
    crack = hp(crack, 1800)
    puff = lp(RNG.standard_normal(n), 900) * np.exp(-((tt - .25) / .2) ** 2) * .5
    e = (1 - np.exp(-tt * 80))
    s = pan2(lp((hiss * .25 + crack * .5 + puff * .3) * e, 8000) * .12 * level, pan)
    place(sfx, s, t)
    place(send, s * .2, t)


def keys(t0, t1, rate=11.0, level=1.0):
    """Frappe au clavier pendant l'écriture du code."""
    t = t0
    while t < t1:
        tt = tvec(.06)
        s = bp(RNG.standard_normal(len(tt)), 1200, 7000) * np.exp(-tt * 380) + np.sin(2 * np.pi * RNG.uniform(260, 340) * tt) * np.exp(-tt * 160) * .5
        place(sfx, pan2(s * .045 * level * RNG.uniform(.6, 1.1), .35 + RNG.uniform(-.1, .1)), t)
        t += RNG.exponential(1 / rate) + .025


def rotor(t0, t1, rpm_curve, level=1.0, wind=0.0, pan_curve=None, fc=3200):
    """Quatre moteurs brushless : sifflement harmonique dont la hauteur suit les gaz,
    battement des pales, souffle des hélices et vent (vol)."""
    n = secs(t1 - t0)
    tt = np.arange(n) / SR
    r = np.clip(rpm_curve(tt + t0), 0, None)
    out = np.zeros(n)
    for k, det in enumerate([1.0, 1.013, .991, 1.022]):
        f = (90 + 260 * r) * det * (1 + .004 * np.sin(2 * np.pi * (.7 + .3 * k) * tt + k))
        ph = np.cumsum(f) / SR
        out += saw_add(np.ones(1), ph + k * .21, nh=12, roll=1.05)
    whine = lp(out, fc, 2) * np.clip(r, 0, 1.2)
    blade = 1 + .3 * np.sin(2 * np.pi * np.cumsum((90 + 260 * r) * 2) / SR)
    wash = bp(RNG.standard_normal(n), 200, 2200) * np.clip(r, 0, 1.3) ** 1.5 * blade
    sig = whine * .05 + wash * .045
    if wind:
        gust = 1 + .35 * np.sin(2 * np.pi * .23 * tt) + .2 * np.sin(2 * np.pi * .61 * tt + 1)
        sig += lp(hp(RNG.standard_normal(n), 120), 1600) * .12 * wind * gust
    pans = pan_curve(tt + t0) if pan_curve else 0
    s = pan2(sig * level, pans)
    f = secs(.25)
    s[:f] *= np.linspace(0, 1, f)[:, None]
    s[-f:] *= np.linspace(1, 0, f)[:, None]
    place(bed, s, t0)
    place(send, s * .12, t0)


def A(a):
    return a2v(a)


# --- transitions entre chapitres
for i, tb in enumerate(CH):
    whoosh(tb + .05, 1.15, up=(i % 2 == 0), level=.9, pan_from=(-.8, .8)[i % 2], pan_to=(.8, -.8)[i % 2])
    impact(tb + .35, .35, 52)

# ============ chapitre 1 : vol en immersion
c1end = CUE['c1end']


def fly_rpm(t):
    a = v2a(t)
    return .78 + .12 * np.sin(a * .8) + .08 * np.sin(a * 2.3 + 1)


def fly_pan(t):
    return .25 * np.sin(v2a(t) * .55)


rotor(0, c1end + 1.0, fly_rpm, level=.8, wind=.7, pan_curve=fly_pan, fc=3600)
riser(0, .6, .4)
impact(CUE['c1a'], .45, 50)
soft_swoosh(CUE['c1a'], .6, .8)
tonal_hit(CUE['c1b'], 69, .9)
whoosh(c1end + .35, 1.2, up=False, level=1.0)
impact(c1end + .8, .5, 48)
glass(a2v(v2a(CUE['c1c']) + .1), 81, .9, -.3)
soft_swoosh(CUE['c1c'] + .1, .5, .6, -.3)
glass(a2v(v2a(CUE['c1c']) + 1.2), 85, .9, .3)
soft_swoosh(a2v(v2a(CUE['c1c']) + 1.2), .5, .6, .3)
ws = v2a(CUE['c1d'])
riser(CUE['c1d'] - 1.6, CUE['c1d'] - .02, .8)
for i, m in enumerate([64, 69, 76]):
    tonal_hit(a2v(ws + i * .75), m, (.8, .9, 1.15)[i])
# plan studio : drone en vol stationnaire
rotor(CUE['c1d'] - .4, CH[0] + .3, lambda t: .45 + .03 * np.sin(t * 1.4), level=.4, fc=2400)

# ============ chapitre 2 : construire
soft_swoosh(A(24.4), .7, .9)
PT = [v2a(CUE[k]) for k in ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6']]
ASM = v2a(CUE['asm'])
AEND = v2a(CUE['asmEnd'])
for i, k in enumerate(['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6']):
    glass(CUE[k] + .02, [74, 76, 79, 81, 83, 86, 88][i], .55, -.5)          # case cochée dans la liste
clunk(A(PT[0] + 1.1), 1.2, 0, .7)                                          # châssis carbone
soft_swoosh(A(PT[0] + .6), .9, .7)
for i in range(4):
    clunk(A(PT[1] + i * .25 + .75), .7, (-.6, .6, -.3, .3)[i], 1.3)          # moteurs
clunk(A(PT[2] + .7), .8, 0)                                                # ESC
snap(A(PT[2] + 1.1), .8, .4)                                               # condensateur
clunk(A(PT[3] + .7), .7, 0, .8)                                            # contrôleur de vol
for k in range(6):                                                         # gyroscope qui pulse
    a = PT[3] + 1.2 + k * (2 * np.pi / 6)
    if a < PT[4]:
        blip(A(a), 1760, .5, .1)
clunk(A(PT[4] + .7), .6, .2, 1.2)                                          # récepteur
clunk(A(PT[5] + .7), .6, -.3, 1.2)                                         # caméra
clunk(A(PT[5] + 1.3), .6, .3, 1.2)                                         # émetteur vidéo
for k in range(5):
    blip(A(PT[5] + 1.4 + k * .35), 2350 + k * 120, .35, .4, .06)           # ondes vidéo
clunk(A(PT[6] - .9 + .75), .7, 0, .9)                                      # plaque du dessus
clunk(A(PT[6] + .95), 1.1, 0, .4)                                          # batterie
for i in range(4):
    snap(A(ASM - 1.6 + i * .15 + .75), .7, (-.5, .5, -.2, .2)[i])          # hélices
# câblage et soudure
soft_swoosh(A(ASM + .8), .7, .8)
whoosh(A(ASM + .45), .9, up=True, level=.45)                               # batterie retirée
for i in range(12):
    t0 = ASM + 1.1 + i * .38
    zip_(A(t0), a2v(t0 + .9) - a2v(t0), .55, ((i % 3) - 1) * .4)
    sizzle(A(t0 + .95), a2v(t0 + 2.05) - a2v(t0 + .95), .75, ((i % 3) - 1) * .3)
soft_swoosh(CUE['asm2'], .7, .8)
whoosh(A(AEND + .5), .9, up=False, level=.45)                              # batterie remise
clunk(A(AEND + 1.0), 1.0, 0, .5)
# essai moteurs
rotor(A(AEND + .5), CH[1] + .4, lambda t: np.clip((v2a(t) - (AEND + .6)) / 1.4, 0, 1) ** 1.4 * .6,
      level=.75, fc=3000)
for k in range(3):
    blip(A(AEND + .2 + k * .14), (1568, 1976, 2349)[k], .6, 0, .1)        # bips d'armement

# ============ chapitre 3 : programmer
soft_swoosh(A(72.6), .9, .8)
PG = [v2a(CUE[k]) for k in ['g0', 'g1', 'g2', 'g3', 'g4', 'g5']]
for i, a in enumerate(PG):
    glass(A(a), (76, 79, 81, 83, 86, 88)[i], .7, -.4)
    soft_swoosh(A(a), .45, .5, .2)
# écriture du micrologiciel : flux de données puis carillon
t = PG[0] + .4
while t < PG[1] - 1:
    blip(A(t), RNG.choice([1320, 1480, 1760, 1980]), .32, .3, .05)
    t += .11
for k, m in enumerate([76, 81, 88]):
    pluck(A(PG[1] - 1) + k * .12, m, .7, .3)
# curseurs PID
for k in ['pp', 'pi', 'pd']:
    a0 = v2a(CUE[k])
    for j in range(9):
        tick(A(a0 + j * 1.2 / 9), .7, .3, 2600 + j * 90)
    blip(A(a0 + 1.25), 2093, .4, .3)
# filtres, rates : petit balayage
soft_swoosh(A(PG[2] + 1.5), 1.4, .6)
soft_swoosh(A(PG[3] + 1.6), 1.6, .6)
for i in range(4):
    tick(A(PG[4] + .6 + i * .5), .9, .2, 3400)                             # éléments OSD
for k in range(10):
    blip(A(PG[5] + .6 + k * .22), RNG.choice([880, 1175, 1320]), .25, -.2, .05)  # boîte noire
FAR = v2a(CUE['far'])
whoosh(A(FAR + .35), 1.0, up=True, level=.7)
impact(A(FAR + .6), .55, 50)
for i, k in enumerate(['k1', 'k2', 'k3', 'k4', 'k5', 'k6']):
    glass(CUE[k], (74, 78, 81, 83, 86, 90)[i], .75, (-.5, -.3, -.1, .1, .3, .5)[i])
PY = v2a(CUE['py'])
whoosh(A(PY), .9, up=False, level=.5)
glass(A(PY + .3), 86, .8)
keys(A(PY + 1), A(130 - .8), 10.0, .9)

# ============ chapitre 4 : piloter
soft_swoosh(A(130.8), .8, .8)
AX = [v2a(CUE[k]) for k in ['x0', 'x1', 'x2', 'x3']]
M0, M1, SIM = v2a(CUE['mode0']), v2a(CUE['mode1']), v2a(CUE['sim'])


def hover_rpm(t):
    a = v2a(t)
    r = .5 + .03 * np.sin(a * .5)
    u = np.clip((a - (AX[0] + .2)) / 1.8, 0, 1)
    r = r + .25 * np.sin(u * np.pi * 2) * ((u > 0) & (u < 1))          # gaz
    for x in AX[1:]:
        u = np.clip((a - (x + .2)) / 1.8, 0, 1)
        r = r + .08 * np.sin(u * np.pi) * ((u > 0) & (u < 1))
    u = np.clip((a - (M1 + 1)) / 1.6, 0, 1)
    r = r + .35 * np.sin(u * np.pi) * ((u > 0) & (u < 1))               # tonneau en acro
    return r


rotor(A(131.2), A(SIM + .2), hover_rpm, level=.55, fc=2800)
for i, a in enumerate(AX):
    glass(A(a), (74, 78, 81, 85)[i], .7, (-.4, -.15, .15, .4)[i])
    soft_swoosh(A(a + 1.0), 1.1, .7, (-.5, .5, .5, -.5)[i])
glass(A(M0), 79, .7, .3)
glass(A(M1), 86, .9, .3)
whoosh(A(M1 + 1.8), 1.6, up=True, level=.75, pan_from=-.9, pan_to=.9)    # tonneau
for i, (k, m) in enumerate([(.1, 69), (1.4, 74), (2.6, 81)]):
    pluck(A(SIM + k), m, .9, (-.4, 0, .4)[i])
    soft_swoosh(A(SIM + k), .5, .5, (-.4, 0, .4)[i])

# ============ chapitre 5 : possibilités
soft_swoosh(A(160.4), .8, .8)
for i, k in enumerate(['u0', 'u1', 'u2', 'u3', 'u4', 'u5']):
    soft_swoosh(CUE[k] + .1, .7, .8, (-.5, 0, .5, -.5, 0, .5)[i])
    glass(CUE[k] + .15, (74, 76, 79, 81, 83, 88)[i], .7 if i < 5 else 1.0, (-.5, 0, .5, -.5, 0, .5)[i])
TOPO = v2a(CUE['topo'])
riser(A(TOPO + 1) - 1.8, A(TOPO + 1), .9)
impact(A(TOPO + 1), .8, 48)
reverse_swell(A(TOPO + 1.2), midi(69), .9, 1.0)
place(send, pan2(bell(midi(69), .05, 4.0), 0), A(TOPO + 1.2))
tp0, tp1, tp2, tp3 = [v2a(CUE[k]) for k in ['tp0', 'ortho', 'cloud', 'mesh']]
t = tp0
while t < tp1 - .1:                                                        # survol photo
    shutter(A(t), RNG.uniform(-.5, .5), .8)
    t += .32
for k, a in enumerate([tp1, tp2, tp3]):
    glass(A(a), (81, 85, 88)[k], .8, .5)
for k in range(90):                                                        # points du nuage
    sparkle(A(RNG.uniform(tp2, tp3 + .8)), RNG.uniform(-.7, .7))
tonal_hit(A(tp3), 76, .6)
USE = v2a(CUE['use'])
for i in range(3):
    pluck(A(USE + i * 1.6), (69, 74, 76)[i], .9, (-.4, 0, .4)[i])

# ============ chapitre 6 : règles
soft_swoosh(A(210.4), .8, .8)
for i, k in enumerate(['r0', 'r1', 'r2']):
    soft_swoosh(CUE[k] + .1, .8, .7, (-.5, 0, .5)[i])
    pluck(CUE[k] + .12, (62, 66, 69)[i], 1.0, (-.5, 0, .5)[i])
reverse_swell(CUE['cert'] + .05, midi(81), .8, 1.0)
glass(CUE['cert'] + .05, 86, 1.0)
place(send, pan2(bell(midi(81), .04, 3.5), 0), CUE['cert'] + .05)

# ============ chapitre 7 : conclusion
W0 = v2a(CUE['f1'])
for i, m in enumerate([62, 66, 69]):
    tonal_hit(A(W0 + i * .8), m, (.75, .85, .95)[i])
Q0 = v2a(CUE['fq'])
riser(A(Q0) - 1.4, A(Q0) - .02, .7)
for i, m in enumerate([69, 74, 81]):
    tonal_hit(A(Q0 + i * .8), m, (.8, .9, 1.1)[i])
FN = v2a(CUE['fin'])
whoosh(A(FN - .3), 1.0, up=False, level=.7)
impact(A(FN), 1.0, 46)
place(send, pan2(bell(midi(57), .06, 4.5) + bell(midi(64), .04, 4.5), 0), A(FN))
for i in range(3):
    glass(A(FN + 1.2 + i * .25), (81, 85, 88)[i], .5, (-.3, 0, .3)[i])


# ------------------------------------------------------------------ mixage
music_wet = reverb(music * .6, IR_HALL, .28)
fx_wet = reverb(send, IR_HALL, .55) + reverb(sfx * .3, IR_ROOM, .25)
music_mix = (music + music_wet) * duck_gain[:, None]
fx_mix = sfx + fx_wet
# légère compression des effets sous la voix aussi (moins forte)
fx_mix *= 1.25 * (1 - .35 * duck)[:, None]
fx_mix += (bed + reverb(bed * .4, IR_ROOM, .2)) * (1 - .6 * duck)[:, None]

mix = voice + music_mix * .7 + fx_mix * .9
# fondu de fin
fo = secs(2.2)
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
# limiteur simple
# crête sur une fenêtre [i, i + 5 ms] : le gain baisse avant que la crête arrive
look = secs(.005)
peak = np.max(np.abs(mix), axis=1)
blk = 32
nb = int(np.ceil(N / blk))
pk = np.pad(peak, (0, nb * blk - N)).reshape(nb, blk).max(1)
k = int(np.ceil(look / blk))
pk_ahead = np.array([pk[i:i + k + 1].max() for i in range(nb)])
thr = 10 ** (-1.0 / 20)
gain = np.minimum(1, thr / (pk_ahead + 1e-9))
g = np.empty(nb)
cur = 1.0
rel = 1 - np.exp(-blk / secs(.12))
for i in range(nb):
    cur = gain[i] if gain[i] < cur else cur + (gain[i] - cur) * rel
    g[i] = cur
mix *= np.repeat(g, blk)[:N, None]
mix = np.clip(mix, -thr, thr)
sf.write(sys.argv[2], mix.astype(np.float32), SR, subtype='FLOAT')
# pistes séparées pour contrôle
sf.write(sys.argv[2].replace('.wav', '-musique.wav'), (music_mix * .7).astype(np.float32), SR, subtype='FLOAT')
sf.write(sys.argv[2].replace('.wav', '-effets.wav'), (fx_mix * .9).astype(np.float32), SR, subtype='FLOAT')
print('ok', DUR, 's', 'crête', float(np.max(np.abs(mix))))

