#!/usr/bin/env python3
"""Lay recorded sound effects onto the cut. No music (it is added later in the edit), no synthesis.

  python3 mix_sfx.py sfx-track.wav

Sources: sfx/*.mp3, all CC0 recordings from Freesound (see sfx/CREDITS.md).
Every file is peak-normalised on load, then only trimmed, aligned, panned and levelled.
Event times match comp.html.
"""
import subprocess, sys, wave
from pathlib import Path
import numpy as np

SR, DUR = 48000, 18.84
N = int(SR * DUR)
HERE = Path(__file__).parent / 'sfx'
_cache = {}


def load(name, a=0.0, b=None, fo=0.0):
    key = (name, a, b, fo)
    if key not in _cache:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(HERE / f'{name}.mp3'), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
        x = x[int(a * SR): int(b * SR) if b else None].copy()
        x /= np.abs(x).max() + 1e-9                   # every source at the same peak, so gains below mean something
        f = min(len(x) // 4, int(.004 * SR))          # tiny fades so trims never click
        x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f)
        if fo:                                        # longer fade-out where a long tail was cut short
            g = min(len(x), int(fo * SR)); x[-g:] *= np.linspace(1, 0, g) ** 2
        env = np.sqrt(np.convolve(x ** 2, np.ones(240) / 240, 'same'))
        onset = int(np.argmax(env > env.max() * .3))
        peak = int(env.argmax())
        _cache[key] = (x, onset, peak)
    return _cache[key]


out = np.zeros((N, 2))


def at(t, name, gain_db=0.0, pan=0.0, a=0.0, b=None, align='onset', fo=0.0):
    """Place `name` so its onset (or its loudest point, align='peak') lands at time t."""
    x, onset, peak = load(name, a, b, fo)
    x = x * 10 ** (gain_db / 20)
    i = int(t * SR) - (peak if align == 'peak' else onset)
    if i < 0: x, i = x[-i:], 0
    x = x[: max(0, N - i)]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    out[i:i + len(x), 0] += x * l * 1.414
    out[i:i + len(x), 1] += x * r * 1.414


# real phone-keyboard taps, cut out of one recording and cycled so no two neighbours repeat
TAPS = [0.07, 0.195, 0.34, 0.56, 0.69, 0.805, 1.01, 1.14, 1.255, 1.46, 1.59, 1.705, 3.305, 3.43, 3.57, 3.795, 3.92, 4.04]
_k = [0]


def tap(t, gain_db=-6, pan=0.0):
    s = TAPS[_k[0] % len(TAPS)]; _k[0] += 7
    at(t, 'phone-typing', gain_db, pan, a=s - .012, b=s + .085)


POPS = ['pop', 'blop', 'plop']

# S1 · "one photo evry mornig" -> corrected on black -> badge -> bloom
at(0.02, 'whoosh-air', -20, -.2, align='peak')
at(0.17, 'click-snap', -12, -.1)                                   # selection handles
for i in range(5): tap(.24 + i * .055, -6, -.2 + i * .05)
for i in range(11): tap(.53 + i * .041, -7 + (i % 2), .05 + i * .02)
at(1.03, 'low-hit', -10, b=.6, fo=.3)                                         # flip to dark
at(1.03, 'swoosh-tonal-dark', -16, 0, align='peak')
at(1.10, 'click-menu', -11)                                        # autocorrect
at(1.21, 'pop', -6, .45); at(1.23, 'blop', -14, .45)               # badge
at(1.58, 'whoosh-reverse', -6, align='peak')                       # bloom sucks into the dot
# S2 · tracker: boom in, ring steps, flip, "right here"
at(1.60, 'sub-boom', -1, b=.9, fo=.5)
at(1.62, 'whoosh-air-cut', -9, align='peak')
for k, tp in enumerate((1.86, 2.10, 2.36, 2.58)): at(tp, 'click-menu', -13 + k, (k % 2 - .5) * .4)
at(2.74, 'swoosh-tonal-bright', -12, 0, align='peak')               # glow
at(2.95, 'whoosh-mid', -8, .15, align='peak')                      # coin flips through edge-on
at(3.02, 'blip-hint', -8)
at(3.04, 'ping', -20, b=.8, fo=.5)
# S3 · photo burst: a real iPhone shutter on every cut
for k, tc in enumerate((3.60, 3.75, 3.90, 4.05)): at(tc, 'shutter-iphone', -1, (-.3, .3, -.15, .15)[k])
# S4 · circle draws, rings fly in, page collapses into the shutter button
at(4.22, 'swoosh-v', -9, -.2)
at(4.52, 'click-snap', -15)
at(4.72, 'sub-kick', -7)
at(4.86, 'whoosh-long', -4, 0, align='peak')
at(4.80, 'swoosh-tonal-bright', -10, .3, align='peak')
at(5.70, 'riser', -11, align='peak')
at(5.70, 'sub-kick', -4); at(5.70, 'click-mouse', -8)
# S5 · camera: viewfinder drops in, hand, title, tap-to-focus, shutter, collapse
at(5.95, 'whoosh-swipe', -10, -.2, align='peak')
at(6.20, 'whoosh-air', -15, .3, align='peak')
for i in range(9): tap(6.14 + i * .035, -13, .1)
at(6.85, 'click-mouse', -6); at(6.86, 'blip-hint', -16)
at(7.27, 'shutter-iphone', 0)
at(7.88, 'whoosh-reverse', -6, align='peak')
# S6 · canvas: land, drag, whip, info window, close-up, pull out, pops, darkening build
at(7.90, 'low-hit', -8, b=.6, fo=.3); at(7.95, 'whoosh-medium', -9, .3, align='peak')
at(7.99, 'click-mouse', -10, .4)
at(8.34, 'whip', -4, -.3, align='peak')
at(8.52, 'whoosh-swipe', -11, .5, align='peak'); at(8.60, 'plop', -13, .5)
at(8.90, 'whoosh-air-cut', -6, 0, align='peak')
at(8.95, 'sub-kick', -8); at(9.10, 'zoom-in', -9, 0, align='peak')
for i in range(10): at(8.98 + i * .055, POPS[i % 3], -13 + (i % 2) * 2, np.sin(i * 2.1) * .7)
at(9.32, 'swoosh-tonal-dark', -11, -.2, align='peak')
at(10.52, 'riser', -9, align='peak')
# S7 · the big word slams in
at(10.585, 'sub-boom', 0, b=1.0, fo=.5); at(10.585, 'bass-drop', -6, b=1.3, fo=.6)
at(10.62, 'whoosh-long', -7, .2, align='peak')
at(11.08, 'whoosh-reverse', -7, align='peak')
# S8 · "miles (❌) apar?" -> "still (🫶) close ↗"
at(11.10, 'low-hit', -8, b=.6, fo=.3); at(11.10, 'click-snap', -9)
for i in range(10): tap(11.12 + i * .05, -9, .3)
at(11.40, 'click-menu', -11)
at(11.59, 'pop', -6); at(11.64, 'whip', -13, .5, align='peak')
at(12.15, 'click-snap', -8, -.3); at(12.13, 'whoosh-air', -18, -.3, align='peak')
at(12.45, 'click-menu', -12); at(12.52, 'whoosh-swipe', -13, .5, align='peak')
at(12.55, 'click-snap', -8, .3); at(12.63, 'pop', -6)
# S9 · chat: bubble, send, reply, scroll, typing, zoom, select, delete, retype
at(13.08, 'swoosh-v', -11)
at(13.40, 'message-sent', -3, .4)
at(13.55, 'message-ding', -8, -.3)
at(14.00, 'whoosh-air', -17, align='peak')
for i in range(19): tap(14.10 + i * .05, -6 + (i % 3 == 0), -.1 + (i % 5) * .05)
at(14.82, 'zoom-in', -7, 0, align='peak'); at(14.80, 'whoosh-medium', -14, align='peak')
at(15.04, 'click-snap', -9); at(15.07, 'plop', -13, .4)
at(15.40, 'click-menu', -6)
for k in range(4): tap(15.43 + k * .1, -6)
# S10 · glitch out, spinner, wordmark
at(16.05, 'glitch', -2, b=.26, fo=.05); at(16.12, 'glitch-short', -5, b=.16, fo=.04)
at(16.26, 'sub-kick', -9)
at(17.20, 'ping', -9, b=1.6, fo=1.0); at(17.24, 'swoosh-tonal-bright', -16, 0, align='peak')

peak = np.abs(out).max()
out *= .5 / peak                                   # headroom; loudness set at mux
pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
dst = sys.argv[1] if len(sys.argv) > 1 else 'sfx-track.wav'
with wave.open(dst, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('wrote', dst)
