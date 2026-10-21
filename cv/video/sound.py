"""Sound design du CV vidéo : musique, effets et mixage avec la voix.

Tout est synthétisé (aucun échantillon externe) :
  - musique : nappes en accords étendus, basse, arpège avec écho, kick / hats / snare doux,
    sections qui suivent les scènes ;
  - effets : whooshs à filtre balayé, impacts graves, montées, frappes tonales (cloche FM),
    verre pour les pastilles, drone spatialisé, déclencheur photo, grondement du relief ;
  - réverbération par convolution, ducking de la musique par la voix, limiteur.

Usage : python sound.py sync.json sortie.wav
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


def a2v(a):
    """Temps d'animation -> temps vidéo (inverse du WARP)."""
    for i in range(1, len(WARP)):
        if a <= WARP[i][1]:
            (v0, a0), (v1, a1) = WARP[i - 1], WARP[i]
            return v0 + (v1 - v0) * (a - a0) / (a1 - a0)
    return WARP[-1][0] + (a - WARP[-1][1])


SCENES = [w[0] for w in WARP[1:-1]]  # limites de scènes en temps vidéo

# ------------------------------------------------------------------ voix
voice = np.zeros((N, 2))
for v in CFG['voice']:
    a, sr = sf.read(v['file'], dtype='float64')
    if a.ndim > 1:
        a = a.mean(1)
    assert sr == SR
    seg = a[secs(v['from']):secs(v['to'])].copy()
    fade = secs(.08)
    seg[:fade] *= np.linspace(0, 1, fade)
    seg[-fade:] *= np.linspace(1, 0, fade)
    seg = hp(seg, 75, 2)
    place(voice, np.stack([seg, seg], 1), v['at'])
# niveau voix : crête vers -3 dBFS
voice *= 10 ** (-3 / 20) / (np.max(np.abs(voice)) + 1e-9)
# enveloppe de la voix pour le ducking
venv = np.abs(voice[:, 0])
win = secs(.04)
venv = np.convolve(venv, np.ones(win) / win, mode='same')
venv = venv / (np.percentile(venv[venv > 1e-4], 90) + 1e-9)
venv = np.clip(venv, 0, 1)
# attaque rapide / relâchement lent
duck = np.empty_like(venv)
g = 0.0
att, rel = 1 - np.exp(-1 / secs(.03)), 1 - np.exp(-1 / secs(.45))
step = 64
for i in range(0, len(venv), step):
    target = venv[i]
    g += (target - g) * (1 - (1 - (att if target > g else rel)) ** step)
    duck[i:i + step] = g
duck_gain = 1 - .72 * duck  # environ -11 dB sous la voix

# ------------------------------------------------------------------ musique
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
# I – vi – IV – V en accords étendus (ré majeur)
CHORDS = [
    [50, 57, 61, 64, 66, 69],   # Dmaj9
    [47, 54, 57, 61, 62, 66],   # Bm11
    [43, 50, 54, 57, 59, 62],   # Gmaj9
    [45, 52, 57, 59, 61, 64],   # A6/9
]
ROOTS = [38, 35, 31, 33]


def section(t):
    """Intensité des couches selon la scène (temps vidéo)."""
    s = SCENES
    if t < s[0]:
        return 'intro'
    if t < s[1]:
        return 'light'
    if t < s[2]:
        return 'break'
    if t < s[3]:
        return 'groove'
    if t < s[4]:
        return 'tension'
    if t < s[5]:
        return 'light2'
    if t < s[6]:
        return 'groove2'
    if t < CUE['fin']:
        return 'build'
    return 'outro'


music = np.zeros((N, 2))
pad_bus = np.zeros((N, 2))
nbars = int(np.ceil(DUR / BAR)) + 1

# nappes
for b in range(nbars):
    t0 = b * BAR
    if t0 > DUR:
        break
    ch = CHORDS[b % 4]
    sec = section(t0 + .1)
    if sec == 'tension':
        ch = [CHORDS[1], CHORDS[2]][b % 2]
    if sec == 'outro':
        ch = CHORDS[0]
    dur = BAR + 1.8
    t = tvec(dur)
    sig = np.zeros((len(t), 2))
    for j, m in enumerate(ch):
        for det, pn in [(-.07, -.6), (0, 0), (.07, .6)]:
            f = midi(m) * 2 ** (det / 12)
            vib = 1 + .0018 * np.sin(2 * np.pi * (.17 + j * .03) * t + j)
            w = saw_add(f * vib, t, nh=18, roll=1.5, phase=RNG.uniform(0, 6.28))
            sig += pan2(w * (.55 if j == 0 else .38), pn * (.4 + .1 * j))
    cut = {'intro': 900, 'light': 1500, 'break': 1100, 'groove': 2300, 'tension': 1200,
           'light2': 1700, 'groove2': 2500, 'build': 3200, 'outro': 2600}[sec]
    sig = lp(sig, cut, 2)
    e = env_adsr(len(t), 1.0, .3, .85, 1.8, sustain_len=BAR - 1.1)
    lvl = {'intro': .5, 'break': .62, 'tension': .55, 'build': .62, 'outro': .7}.get(sec, .5)
    place(pad_bus, sig * e[:, None] * lvl * .07, t0)
# montée progressive au début
pad_bus[:secs(3.5)] *= np.linspace(0, 1, secs(3.5))[:, None] ** 1.6

# basse
bass = np.zeros((N, 2))
for b in range(nbars):
    t0 = b * BAR
    sec = section(t0 + .1)
    if t0 > DUR or sec in ('intro', 'break'):
        continue
    root = ROOTS[b % 4] if sec not in ('tension',) else [35, 31][b % 2]
    if sec == 'outro':
        root = 38
    f = midi(root)
    if sec in ('tension',):
        # pulsation en croches, tendue
        for k in range(8):
            tt = tvec(BEAT / 2)
            s = np.sin(2 * np.pi * f * tt) + .35 * np.sin(4 * np.pi * f * tt)
            s *= np.exp(-tt * 7) * (1 if k % 2 == 0 else .7)
            place(bass, pan2(lp(s, 260) * .16, 0), t0 + k * BEAT / 2)
    else:
        tt = tvec(BAR)
        s = np.sin(2 * np.pi * f * tt) + .3 * np.sin(4 * np.pi * f * tt) + .1 * np.sin(6 * np.pi * f * tt)
        s *= env_adsr(len(tt), .05, .4, .7, .5)
        place(bass, pan2(lp(s, 220) * .17, 0), t0)

# arpège pluck + écho ping-pong
arp = np.zeros((N, 2))
pattern = [0, 2, 3, 4, 5, 4, 3, 2]
for b in range(nbars):
    t0 = b * BAR
    sec = section(t0 + .1)
    if t0 > DUR or sec in ('intro', 'break', 'outro'):
        continue
    ch = CHORDS[b % 4] if sec != 'tension' else [CHORDS[1], CHORDS[2]][b % 2]
    step_len = BEAT / 2
    lvl = {'light': .5, 'light2': .55, 'tension': .45, 'groove': .7, 'groove2': .75, 'build': .8}[sec]
    for k in range(8):
        m = ch[pattern[k]] + 12
        tt = tvec(.5)
        f = midi(m)
        s = np.sin(2 * np.pi * f * tt) + .25 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 18) \
            + .12 * np.sin(2 * np.pi * 3 * f * tt) * np.exp(-tt * 25)
        s *= np.exp(-tt * 9) * (1 - np.exp(-tt * 400))
        place(arp, pan2(s * .045 * lvl, (-.35, .35)[k % 2]), t0 + k * step_len)
d = secs(BEAT * .75)
echo = np.zeros_like(arp)
echo[d:, 1] += arp[:-d, 0] * .45
echo[d:, 0] += arp[:-d, 1] * .45
echo[2 * d:] += arp[:-2 * d] * .22
arp = lp(arp + echo, 6500)

# batterie
drums = np.zeros((N, 2))


def kick(level=1.0):
    tt = tvec(.55)
    f = 46 + 110 * np.exp(-tt * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-tt * 6.5)
    s += hp(RNG.standard_normal(len(tt)), 3000) * np.exp(-tt * 300) * .15
    return pan2(np.tanh(s * 1.4) * .32 * level, 0)


def hat(level=1.0, open_=False):
    tt = tvec(.25)
    s = hp(RNG.standard_normal(len(tt)), 7500, 2) * np.exp(-tt * (18 if open_ else 55))
    return pan2(lp(s, 12000) * .022 * level, .25)


def snare(level=1.0):
    tt = tvec(.4)
    body = np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 22)
    noise = bp(RNG.standard_normal(len(tt)), 1500, 7000) * np.exp(-tt * 14)
    return pan2((body * .5 + noise * .6) * .09 * level, -.1)


for b in range(nbars):
    t0 = b * BAR
    sec = section(t0 + .1)
    if t0 > DUR:
        break
    for k in range(4):
        tb = t0 + k * BEAT
        s = section(tb)
        if s in ('groove', 'groove2'):
            place(drums, kick(), tb)
            if k in (1, 3):
                place(drums, snare(.9), tb)
            place(drums, hat(.8), tb + BEAT / 2)
            place(drums, hat(.45), tb + BEAT / 4 * 3)
        elif s in ('light', 'light2'):
            if k in (0, 2):
                place(drums, kick(.7), tb)
            place(drums, hat(.5), tb + BEAT / 2)
        elif s == 'build':
            place(drums, kick(.85), tb)
            place(drums, hat(.7), tb + BEAT / 2)
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


# --- intro : souffle inversé puis impact doux sur l'apparition du nom
riser(0.0, .78, .6)
impact(.78, .7, 55)
reverse_swell(.78, midi(74), .8, 1.2)
place(send, pan2(bell(midi(74), .05, 3.5), 0), .78)
glass(2.55, 81, .8)                                   # pastille « Recherche d'alternance »

# --- transitions entre scènes
for i, tb in enumerate(SCENES):
    whoosh(tb + .05, 1.15, up=(i % 2 == 0), level=1.0, pan_from=(-.8, .8)[i % 2], pan_to=(.8, -.8)[i % 2])

# --- scène 2 : photo, titre, badges
soft_swoosh(4.75, .7, 1.0)
soft_swoosh(CUE['s2l1'], .5, .7, -.2)
soft_swoosh(CUE['s2l2'], .5, .7, .2)
for k, m in zip(['b1', 'b2', 'b3'], [78, 81, 85]):
    glass(CUE[k], m, 1.0, (-.3, 0, .3)[['b1', 'b2', 'b3'].index(k)])

# --- scène 3 : trois frappes tonales, la dernière plus forte
impact(SCENES[1] + .05, .8, 50)
tonal_hit(CUE['w1'], 66, .8)
tonal_hit(CUE['w2'], 69, .9)
tonal_hit(CUE['w3'], 74, 1.15)

# --- scène 4 : cartes
for k, m in zip(['c1', 'c2', 'c3'], [74, 78, 81]):
    glass(CUE[k] + .05, m, 1.0, (-.4, 0, .4)[['c1', 'c2', 'c3'].index(k)])
    soft_swoosh(CUE[k], .6, .8, (-.4, 0, .4)[['c1', 'c2', 'c3'].index(k)])

# --- scène 5 : drone, photos, relevé, relief
F0, F1 = 35.7, 41.7
rows, X0, X1, R = [-270, -135, 0, 135, 270], -540, 540, 67.5
segs = []
for i, y in enumerate(rows):
    dr = -1 if i % 2 else 1
    xa, xb = (X0, X1) if dr > 0 else (X1, X0)
    segs.append(('l', xa, xb, y))
    if i < len(rows) - 1:
        segs.append(('c', xb, y + R, dr))
lens = [abs(s[2] - s[1]) if s[0] == 'l' else np.pi * R for s in segs]
tot = sum(lens)


def path_at(u):
    dd = u * tot
    i = 0
    while i < len(segs) - 1 and dd > lens[i]:
        dd -= lens[i]
        i += 1
    s = segs[i]
    f = min(1, dd / lens[i])
    if s[0] == 'l':
        return s[1] + (s[2] - s[1]) * f, s[3]
    ang = -np.pi / 2 + f * np.pi
    return s[1] + s[3] * R * np.cos(ang), s[2] + R * np.sin(ang)


def ease_io(x):
    x = np.clip(x, 0, 1)
    return np.where(x < .5, 4 * x ** 3, 1 - (-2 * x + 2) ** 3 / 2)


# son du drone : 4 rotors légèrement désaccordés + souffle, spatialisé
v_on, v_off = a2v(35.2), a2v(42.7)
n = secs(v_off - v_on + .6)
tt = np.arange(n) / SR
anim_t = np.interp(tt + v_on, [w[0] for w in WARP], [w[1] for w in WARP])
u = ease_io((anim_t - F0) / (F1 - F0))
xs = np.array([path_at(q)[0] for q in u[::480]])
xs = np.interp(np.arange(n), np.arange(0, n, 480)[:len(xs)], xs)
vel = np.gradient(xs) * SR / 1000.0
climb = np.clip((anim_t - 41.7) / 1.0, 0, 1)
pitch = 1 + .018 * np.clip(vel, -1.5, 1.5) + .12 * climb
rot = np.zeros(n)
for k, base in enumerate([186, 192, 199, 205]):
    ph = 2 * np.pi * np.cumsum(base * pitch) / SR + k
    rot += saw_add(np.ones(1) * 1, ph / (2 * np.pi), nh=14, roll=1.1)
rot = lp(rot, 2600 * (1 - .6 * climb.mean()), 2)
air = bp(RNG.standard_normal(n), 250, 1400) * .6
blade = 1 + .25 * np.sin(2 * np.pi * 31 * tt)
dr_sig = (rot * .055 + air * .05) * blade
e = np.clip((anim_t - 35.2) / .6, 0, 1) * (1 - climb) ** 1.5
dr_sig *= e
pan = np.clip(xs / 600, -.85, .85)
st = pan2(dr_sig, pan)
place(sfx, st * .9, v_on)
place(send, st * .25, v_on)

# déclencheurs photo + étincelles de points
shot_t = np.arange(F0 + .15, F1, .3)
for a in shot_t:
    uu = float(ease_io((a - F0) / (F1 - F0)))
    x, _ = path_at(uu)
    shutter(a2v(a), x / 700, .9)
for k in range(140):
    a = RNG.uniform(F0 + .2, 42.3)
    uu = float(ease_io((min(a, F1) - F0) / (F1 - F0)))
    x, _ = path_at(uu)
    sparkle(a2v(a), x / 650 + RNG.uniform(-.2, .2))
# changements d'étape (pastille en verre)
glass(a2v(37.4), 81, .6, .7)
glass(a2v(42.0), 85, .7, .7)
# relief qui se soulève : grondement + montée + floraison
r0, r1 = a2v(41.8), a2v(44.6)
riser(r0 - 1.3, r0 + .05, .7)
n = secs(r1 - r0 + 2.5)
tt = np.arange(n) / SR
rum = lp(RNG.standard_normal(n), 140, 2) * 2.2 + np.sin(2 * np.pi * 38 * tt) * .6
crack = np.zeros(n)
for k in range(220):
    i = int(RNG.uniform(0, secs(r1 - r0)))
    crack[i:i + 200] += RNG.standard_normal(200) * np.exp(-np.arange(200) / 30) * RNG.uniform(.2, 1)
crack = bp(crack, 400, 3500)
shape = np.clip(tt / (r1 - r0), 0, 1) ** 1.3 * np.exp(-np.clip(tt - (r1 - r0), 0, None) * 1.6)
s = pan2((rum * .16 + crack * .05) * shape, 0)
place(sfx, s, r0)
place(send, s * .4, r0)
impact(r0 + .05, .75, 48)
reverse_swell(r1, midi(69), 1.0, .9)
place(send, pan2(bell(midi(69), .045, 3.5), .2), r1)

# --- scène 6 : frise
for k, m in zip(['n0', 'n1', 'n2', 'n3'], [62, 66, 69, 74]):
    pluck(CUE[k] + .02, m, 1.0 if k != 'n3' else 1.3, (-.6, -.2, .2, .6)[int(k[1])])
    soft_swoosh(CUE[k] - .25, .9, .5, (-.6, -.2, .2, .6)[int(k[1])])
glass(CUE['n3'] + .15, 86, .8, .6)

# --- scène 7 : pastilles (les principales plus présentes)
HI = {0, 4, 5, 11, 13}
scale = [74, 76, 78, 81, 83, 86, 88, 90]
for i in range(14):
    t = CUE['ch%d' % i]
    m = scale[i % len(scale)]
    glass(t, m, 1.1 if i in HI else .55, ((i * 37) % 9 - 4) / 6)
    if i in HI:
        pluck(t, m - 24, .6, ((i * 37) % 9 - 4) / 6)

# --- scène 8 : montée, qualités, carte finale
riser(CUE['q0'] - 1.7, CUE['q0'] - .02, 1.0)
for k, m, lv in zip(['q0', 'q1', 'q2', 'q3'], [62, 66, 69, 74], [.8, .85, .9, 1.05]):
    tonal_hit(CUE[k], m, lv)
whoosh(CUE['qout'] + .3, 1.0, up=False, level=.8)
impact(CUE['fin'] + .1, 1.0, 50)
place(send, pan2(bell(midi(62), .06, 4.0) + bell(midi(69), .04, 4.0), 0), CUE['fin'] + .1)
reverse_swell(CUE['fh2'], midi(78), .9, 1.0)
glass(CUE['fh2'] + .02, 86, .9)
glass(CUE['fh2'] + .2, 90, .6, .4)

# ------------------------------------------------------------------ mixage
music_wet = reverb(music * .6, IR_HALL, .28)
fx_wet = reverb(send, IR_HALL, .55) + reverb(sfx * .3, IR_ROOM, .25)
music_mix = (music + music_wet) * duck_gain[:, None]
fx_mix = sfx + fx_wet
# légère compression des effets sous la voix aussi (moins forte)
fx_mix *= (1 - .35 * duck)[:, None]

mix = voice + music_mix * .62 + fx_mix * .9
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
sf.write(sys.argv[2].replace('.wav', '-musique.wav'), (music_mix * .62).astype(np.float32), SR, subtype='FLOAT')
sf.write(sys.argv[2].replace('.wav', '-effets.wav'), (fx_mix * .9).astype(np.float32), SR, subtype='FLOAT')
print('ok', DUR, 's', 'crête', float(np.max(np.abs(mix))))
