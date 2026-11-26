#!/usr/bin/env python3
"""Lay the downloaded sound effects onto the cut. No music (added later in the edit), no synthesis.

  python3 mix_sfx.py sfx-track.wav

Sources: sfx/*.ogg — uisfx (CC0, see sfx/LICENSE-uisfx-audio.txt) and
"Holga shuttersound.ogg" from Wikimedia Commons (public domain).
Event times match comp.html. This script only trims, pans and sets levels.
"""
import subprocess, sys, wave
from pathlib import Path
import numpy as np

SR, DUR = 48000, 18.84
N = int(SR * DUR)
HERE = Path(__file__).parent / 'sfx'
_cache = {}


def load(name, a=0.0, b=None):
    key = (name, a, b)
    if key not in _cache:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(HERE / f'{name}.ogg'), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
        x = x[int(a * SR): int(b * SR) if b else None].copy()
        f = min(len(x), int(.006 * SR))            # tiny fades so trims never click
        x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f)
        _cache[key] = x
    return _cache[key]


out = np.zeros((N, 2))


def at(t, name, gain_db=0.0, pan=0.0, a=0.0, b=None, lead=0.0):
    """Place `name` so its attack lands at time t (lead = seconds of pre-roll in the file)."""
    x = load(name, a, b) * 10 ** (gain_db / 20)
    i = int((t - lead) * SR)
    if i < 0: x, i = x[-i:], 0
    x = x[: max(0, N - i)]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    out[i:i + len(x), 0] += x * l * 1.414
    out[i:i + len(x), 1] += x * r * 1.414


TYPE, WHOOSH, WHOOSH2 = 'mechanical-typing', 'cinematic-swipe', 'soft-swipe'
SHUTTER_CLICK = dict(name='camera-holga-shutter', a=0.37, b=0.62)
SHUTTER_FULL = dict(name='camera-holga-shutter', a=0.37, b=1.0)

# S1 · typing "one photo evry mornig" -> fix -> badge -> bloom
at(0.00, WHOOSH2, -14, -.2, lead=.024)                       # handwritten "one"
at(0.18, 'glass-select', -9, -.1)                             # selection handles
for i in range(5): at(.24 + i * .055, TYPE, -4, -.2 + i * .05)
for i in range(11): at(.53 + i * .041, TYPE, -5 + (i % 2), .05 + i * .02)
at(1.00, 'soft-collapse', -10)                                # flip to dark
at(1.20, 'glass-badge', -8, .45)                              # badge pops in
at(1.46, WHOOSH, -8, 0, lead=.026)                            # bloom into the dot
# S2 · tracker countdown -> coin flip -> "right here"
at(1.60, 'cinematic-drop', -9)
for k, tp in enumerate((1.62, 1.86, 2.10, 2.36, 2.58, 2.78)): at(tp, 'glass-progress-step', -12 + k, (k % 2 - .5) * .4)
at(2.72, 'mechanical-snap', -6)
at(2.80, WHOOSH2, -8, .2, lead=.024)
at(3.00, 'glass-success', -7)
# S3 · photo burst: real shutter on every cut
for k, tc in enumerate((3.60, 3.75, 3.90, 4.05)): at(tc, **SHUTTER_CLICK, gain_db=-2, pan=(-.3, .3, -.15, .15)[k], lead=.011)
# S4 · circle draws, rings spin up, frame folds into the shutter button
at(4.20, 'cinematic-expand', -9, -.2)
for i in range(14): at(4.72 + i * .035, TYPE, -13, np.sin(i) * .6)
at(5.24, 'cinematic-collapse', -7)
at(5.70, 'mechanical-press', -5)
# S5 · camera
at(5.78, 'cinematic-open', -10)
at(6.08, WHOOSH2, -10, -.4, lead=.024)
for i in range(9): at(6.14 + i * .035, TYPE, -9, .1)
at(6.30, WHOOSH2, -17, -.2, lead=.024); at(6.88, WHOOSH2, -17, .2, lead=.024)
at(7.20, 'dreamy-reaction', -12, .3)
at(7.27, **SHUTTER_FULL, gain_db=0, lead=.011)
at(7.78, WHOOSH, -10, 0, lead=.026)
# S6 · canvas: drag, zoom, whip, info window, cluster pops, darkening build
at(7.90, WHOOSH, -9, .3, lead=.026)
at(7.98, 'mechanical-drag-start', -9, .4)
at(8.27, 'minimal-collapse', -10)
at(8.33, WHOOSH, -6, -.3, lead=.026)
at(8.43, 'glass-open', -10, .5)
at(8.86, WHOOSH2, -8, 0, lead=.024)
for i in range(10): at(8.98 + i * .055, 'rubber-snap', -12, np.sin(i * 2.1) * .7)
at(9.05, 'scifi-scanning', -12); at(9.75, 'scifi-scanning', -9)
# S7 · big word impact
at(10.55, 'cinematic-drop', -2)
at(10.60, WHOOSH, -7, .3, lead=.026)
at(11.02, WHOOSH2, -10, 0, lead=.024)
# S8 · "miles (❌) apar?" -> "still (🫶) close ↗"
at(11.10, 'mechanical-press', -6)
for i in range(10): at(11.12 + i * .05, TYPE, -6, .3)
at(11.42, 'minimal-deselect', -10)
at(11.58, 'dreamy-reaction', -8)
at(11.62, WHOOSH2, -11, .5, lead=.024)
at(12.15, 'mechanical-toggle-on', -8, -.3)
at(12.45, 'minimal-deselect', -11)
at(12.50, WHOOSH2, -11, .5, lead=.024)
at(12.55, 'mechanical-toggle-on', -8, .3)
at(12.62, 'dreamy-reaction', -8)
# S9 · chat: send, receive, typing, select, delete, retype
at(13.04, 'soft-collapse', -10)
at(13.38, 'glass-send', -6, .4)
at(13.54, 'glass-receive', -7, -.3)
for i in range(19): at(14.10 + i * .05, TYPE, -6 + (i % 3 == 0), -.1 + (i % 5) * .05)
at(14.74, 'cinematic-expand', -10)
at(15.04, 'glass-select', -8)
at(15.06, 'soft-open', -12, .5)
at(15.40, 'minimal-delete', -6)
for k in range(4): at(15.43 + k * .1, TYPE, -6)
# S10 · glitch out, spinner, wordmark
at(16.05, 'scifi-error', -4); at(16.13, 'scifi-disconnect', -6)
at(17.20, 'dreamy-complete', -8)

peak = np.abs(out).max()
out *= .5 / peak                                   # headroom; loudness set at mux
pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
dst = sys.argv[1] if len(sys.argv) > 1 else 'sfx-track.wav'
with wave.open(dst, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('wrote', dst)
