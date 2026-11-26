#!/usr/bin/env python3
"""Voice-over lines with Kokoro-82M (Apache-2.0), run locally through kokoro-onnx.

  python3 vo/make_vo.py <model-dir> [voice]     # model-dir holds kokoro-v1.0.onnx + voices-v1.0.bin

Writes vo/lines/NN.wav (24 kHz mono) and vo/lines.json (start time, text, length).
Each line has a slot on the cut; if a take runs long it is re-spoken faster (never time-stretched).
"""
import json, sys
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
# (start s, latest end s, text) — starts sit on picture beats in comp.html
LINES = [
    (0.10, 1.58, "One photo, every morning."),
    (1.75, 3.60, "Far from mom? Now you're right here."),
    (4.25, 5.75, "On her home screen, all day."),
    (6.15, 7.75, "Snap one. Send it. Done."),
    (8.30, 10.30, "Only the people you pick get to see it."),
    (11.35, 13.00, "Miles apart. Still close."),
    (13.60, 15.20, "They saw your morning."),
    (16.40, 18.30, "Bopli. Coming soon to iPhone."),
]

def main():
    mdir = Path(sys.argv[1]); voice = sys.argv[2] if len(sys.argv) > 2 else 'af_heart'
    k = Kokoro(str(mdir / 'kokoro-v1.0.onnx'), str(mdir / 'voices-v1.0.bin'))
    out = HERE / 'lines'; out.mkdir(exist_ok=True)
    meta = []
    for i, (t0, t1, text) in enumerate(LINES):
        speed = 1.0
        while True:
            x, sr = k.create(text, voice=voice, speed=speed, lang='en-us')
            x = np.asarray(x, dtype=np.float32)
            env = np.abs(x) > .01                      # trim silence the model pads around the take
            a, b = np.argmax(env), len(x) - np.argmax(env[::-1])
            x = x[max(0, a - int(.02 * sr)): b + int(.06 * sr)]
            if len(x) / sr <= (t1 - t0) or speed >= 1.15: break
            speed = round(speed + .05, 2)
        sf.write(out / f'{i:02d}.wav', x, sr)
        meta.append(dict(start=t0, slot_end=t1, text=text, length=round(len(x) / sr, 2), speed=speed, voice=voice))
        print(f'{t0:5.2f}  {len(x)/sr:4.2f}s / {t1-t0:4.2f}s  x{speed}  {text}')
    (HERE / 'lines.json').write_text(json.dumps(meta, indent=1))

if __name__ == '__main__':
    main()
