#!/usr/bin/env python3
"""Final mix: the reference reel's original audio + our sound effects + the voice-over.

  python3 mix_final.py --music ref.mp4 --sfx sfx-track.wav --out mix.wav

- music: the reference's own track (same length and cut as the film), ducked under every VO line
- sfx:   mix_sfx.py output
- vo:    vo/lines/*.wav placed at the start times in vo/lines.json
Mastered with ffmpeg loudnorm to -14 LUFS, -1 dBTP (Instagram / TikTok level).
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np

SR, DUR = 48000, 18.84
N = int(SR * DUR)
HERE = Path(__file__).parent


def read(path, ch=2):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', str(ch), '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64).reshape(-1, ch)
    out = np.zeros((N, ch)); out[:min(N, len(x))] = x[:N]
    return out


def rms_db(x):
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--music', required=True); ap.add_argument('--sfx', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--music-db', type=float, default=-3.0, help='music level vs the VO')
    ap.add_argument('--sfx-db', type=float, default=-6.0, help='sfx level vs the VO')
    ap.add_argument('--duck-db', type=float, default=-9.0, help='music dip while a VO line plays')
    a = ap.parse_args()

    music, sfx = read(a.music), read(a.sfx)
    vo = np.zeros((N, 2)); active = np.zeros(N)
    for i, ln in enumerate(json.loads((HERE / 'vo' / 'lines.json').read_text())):
        x = read(HERE / 'vo' / 'lines' / f'{i:02d}.wav', 1)[:, 0]
        x = x[:np.max(np.nonzero(np.abs(x) > 1e-5)) + 1] if np.any(np.abs(x) > 1e-5) else x
        s = int(ln['start'] * SR); e = min(N, s + len(x))
        vo[s:e] += x[:e - s, None] * .707
        active[s:e] = 1

    # duck: attack 60 ms, release 300 ms, as a smoothed gain curve on the music only
    g = np.where(active > 0, 10 ** (a.duck_db / 20), 1.0)
    att, rel = 1 - np.exp(-1 / (.06 * SR)), 1 - np.exp(-1 / (.3 * SR))
    sm = np.empty(N); v = 1.0
    for i in range(N):                     # one-pole follower, faster when ducking than when recovering
        v += (g[i] - v) * (att if g[i] < v else rel); sm[i] = v
    # start each dip slightly before the word so the first syllable is clear
    lead = int(.05 * SR); sm = np.concatenate([sm[lead:], np.full(lead, sm[-1])])

    # levels relative to the voice (speech-active RMS)
    vo_ref = rms_db(vo[active > 0]) if active.any() else -20
    m = music * 10 ** ((vo_ref + a.music_db - rms_db(music)) / 20)
    f = sfx * 10 ** ((vo_ref + a.sfx_db - rms_db(sfx[np.abs(sfx).max(1) > 1e-3])) / 20)
    mix = m * sm[:, None] + f + vo
    bed = (m * sm[:, None] + f)[active > 0]
    print(f'voice over the bed while speaking: {rms_db(vo[active > 0]) - rms_db(bed):+.1f} dB')
    mix *= .5 / np.abs(mix).max()

    tmp = Path(a.out).with_suffix('.pre.wav')
    pcm = (np.clip(mix, -1, 1) * 32767).astype('<i2')
    import wave
    with wave.open(str(tmp), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    # two-pass loudnorm to -14 LUFS / -1 dBTP
    meas = subprocess.run(['ffmpeg', '-v', 'info', '-nostats', '-i', str(tmp), '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                          capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}"
          f":measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,aresample={SR}")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(tmp), '-af', af, '-ar', str(SR), str(a.out)], check=True)
    tmp.unlink()
    print('wrote', a.out)


if __name__ == '__main__':
    main()
