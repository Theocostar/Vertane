"""Construit sync-fpv.json : place les 7 voix et cale chaque animation sur la phrase qui en parle.

Les repères sont donnés en secondes à partir du début de la voix de chaque chapitre
(mesurés sur les fichiers voice/c1.wav ... c7.wav)."""
import json
import soundfile as sf

ANIM = [0, 24, 72, 130, 160, 210, 228, 252]   # limites des chapitres (temps d'animation)
LEAD = [.9, .7, .6, .6, .6, .6, .6]            # silence avant la voix
TAIL = [.5, 1.7, 1.2, 1.1, 1.4, 1.0, 4.6]      # temps après la voix (le dernier : carte finale)
CUES = [
    {'c1a': .6, 'c1b': 6.4, 'c1end': 12.9, 'c1c': 13.4, 'c1d': 19.1},
    {'p0': 4.9, 'p1': 9.0, 'p2': 13.8, 'p3': 19.1, 'p4': 27.7, 'p5': 30.85, 'p6': 35.75,
     'asm': 39.5, 'asm2': 42.3, 'asmEnd': 45.7},
    {'g0': 3.06, 'g1': 10.06, 'pp': 14.1, 'pi': 16.0, 'pd': 17.86, 'g2': 20.3, 'g3': 22.9, 'g4': 25.86,
     'g5': 31.67, 'far': 37.36, 'k1': 40.4, 'k2': 41.4, 'k3': 42.3, 'k4': 43.03, 'k5': 44.89, 'k6': 46.63,
     'py': 50.73},
    {'x0': 3.77, 'x1': 5.87, 'x2': 7.97, 'x3': 10.24, 'mode0': 12.75, 'mode1': 16.07, 'sim': 24.42},
    {'u0': 2.37, 'u1': 9.79, 'u2': 16.23, 'u3': 19.81, 'u4': 23.53, 'u5': 27.0, 'topo': 27.7,
     'tp0': 31.0, 'ortho': 35.0, 'cloud': 36.49, 'mesh': 37.4, 'use': 38.94},
    {'r0': 3.5, 'r1': 6.0, 'r2': 8.25, 'cert': 11.9},
    {'f1': .14, 'fq': 4.4, 'fin': 7.2},
]
voice, warp, cues, v = [], [[0, 0]], {}, 0.0
for i in range(7):
    d = sf.info(f'voice/c{i + 1}.wav').duration
    at = v + LEAD[i]
    voice.append({'file': f'voice/c{i + 1}.wav', 'at': round(at, 3)})
    for k, r in CUES[i].items():
        cues[k] = round(at + r, 3)
    v = at + d + TAIL[i]
    warp.append([round(v, 3), ANIM[i + 1]])
json.dump({'duration': round(v, 3), 'warp': warp, 'voice': voice, 'cues': cues},
          open('sync-fpv.json', 'w'), indent=1)
print('durée', round(v, 2), 's')
for (v0, a0), (v1, a1) in zip(warp, warp[1:]):
    print(f'{v0:7.2f}-{v1:7.2f}  vitesse anim {(a1 - a0) / (v1 - v0):.2f}')
