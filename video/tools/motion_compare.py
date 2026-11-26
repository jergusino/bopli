#!/usr/bin/env python3
"""Measure how things move in a reference video, and compare a remake against it.

  python3 video/tools/motion_compare.py --ref ref.mp4 [--ours ours.mp4] --out <folder> [--fps 20]

Per frame (dense optical flow, Farneback, on 480 px wide greyscale):
  speed     median flow length of the pixels that move, in % of frame width per second
  moving    share of pixels that move more than 0.4 px
  cam_*     the global move fitted to the flow: pan x/y (% width per s), zoom (%/s), rotation (deg/s)
Per move (a run of frames with speed above a floor):
  start, length, peak time, t80 (share of the move's length it takes to cover 80 % of its travel),
  shape: "snap" (t80 < .45, front-loaded), "s-curve" (.45-.7), "ramp-in" (> .7)

Output:
  flow.json           all numbers (ref and ours)
  flow.png            speed / zoom / pan curves, ref above ours, cuts marked
  moves.md            the move tables side by side, and a per-0.5 s pacing diff
  side-by-side.mp4    ref | ours, synced, with time and speed bars burned in
"""
import argparse, json, subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W = 480


def frames(path, fps):
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'fps={fps},scale={W}:-2', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
                            '-of', 'csv=p=0', str(path)], capture_output=True, text=True, check=True).stdout.split(',')
    w0, h0 = int(probe[0]), int(probe[1])
    H = int(round(W * h0 / w0 / 2) * 2)
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def flow_stats(vid, fps):
    gray = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in vid]
    H = gray[0].shape[0]
    ys, xs = np.mgrid[0:H:6, 0:W:6]
    pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
    rows = [dict(speed=0, moving=0, cam_x=0, cam_y=0, zoom=0, rot=0, cut=False)]
    for a, b in zip(gray, gray[1:]):
        d = np.abs(a.astype(np.int16) - b).mean()
        f = cv2.calcOpticalFlowFarneback(a, b, None, .5, 4, 21, 3, 7, 1.5, 0)
        mag = np.hypot(f[..., 0], f[..., 1])
        mv = mag > .4
        hist_a = np.histogram(a, 32, (0, 256))[0] / a.size
        hist_b = np.histogram(b, 32, (0, 256))[0] / b.size
        cut = bool(.5 * np.abs(hist_a - hist_b).sum() > .3 or (d > 40 and mag.mean() < 2))
        r = dict(speed=float(np.median(mag[mv])) if mv.mean() > .002 else 0.0, moving=float(mv.mean()), cut=cut,
                 cam_x=0.0, cam_y=0.0, zoom=0.0, rot=0.0, diff=float(d))
        if mv.mean() > .02 and not cut:
            s = f[pts[:, 1].astype(int), pts[:, 0].astype(int)]
            M, inl = cv2.estimateAffinePartial2D(pts, pts + s, method=cv2.RANSAC, ransacReprojThreshold=1.0)
            if M is not None and inl.mean() > .35:
                sc = float(np.hypot(M[0, 0], M[1, 0]))
                ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
                c = np.array([W / 2, H / 2])
                t = M[:, :2] @ c + M[:, 2] - c          # pan measured at frame centre
                r.update(cam_x=float(t[0]), cam_y=float(t[1]), zoom=sc - 1, rot=ang, cam_share=float(inl.mean()))
        rows.append(r)
    k = 100 * fps / W                                   # px/frame -> % width per second
    for r in rows:
        r['speed'] *= k; r['cam_x'] *= k; r['cam_y'] *= k
        r['zoom'] *= 100 * fps; r['rot'] *= fps
    return rows


def moves(rows, fps, floor=3.0):
    out, i, n = [], 1, len(rows)
    sp = np.array([0 if r['cut'] else r['speed'] * max(r['moving'], .02) ** .5 for r in rows])
    while i < n:
        if sp[i] > floor:
            j = i
            while j < n and sp[j] > floor * .6 and not rows[j]['cut']:
                j += 1
            seg = sp[i:j]
            if len(seg) >= 2:
                cum = np.cumsum(seg) / seg.sum()
                t80 = (np.searchsorted(cum, .8) + 1) / len(seg)
                shape = 'snap' if t80 < .45 else ('s-curve' if t80 <= .7 else 'ramp-in')
                out.append(dict(start=round(i / fps, 2), length=round(len(seg) / fps, 2),
                                peak=round((i + int(seg.argmax())) / fps, 2), peak_speed=round(float(seg.max()), 1),
                                t80=round(float(t80), 2), shape=shape,
                                zoom=round(float(np.mean([rows[k]['zoom'] for k in range(i, j)])), 1),
                                pan=round(float(np.mean([np.hypot(rows[k]['cam_x'], rows[k]['cam_y']) for k in range(i, j)])), 1)))
            i = j
        else:
            i += 1
    return out


def plot(series, fps, path):
    Wp, Hp = 1800, 220 * len(series)
    im = Image.new('RGB', (Wp, Hp), 'white'); dr = ImageDraw.Draw(im)
    dur = max(len(r) for _, r in series) / fps
    X = lambda t: int(50 + (Wp - 70) * t / dur)
    for k, (name, rows) in enumerate(series):
        y0 = k * 220
        dr.text((50, y0 + 4), f'{name}: speed (blue, %W/s) · zoom (green, %/s) · pan (orange, %W/s) · cuts (red)', fill='black')
        top = 120
        Y = lambda v: int(y0 + 200 - 170 * min(abs(v), top) / top)
        for key, col in (('speed', (29, 124, 242)), ('zoom', (40, 170, 70)), ('pan', (240, 140, 20))):
            vals = [np.hypot(r['cam_x'], r['cam_y']) if key == 'pan' else r[key] for r in rows]
            dr.line([(X(i / fps), Y(v)) for i, v in enumerate(vals)], fill=col, width=2)
        for i, r in enumerate(rows):
            if r['cut']:
                dr.line([(X(i / fps), y0 + 25), (X(i / fps), y0 + 200)], fill=(230, 40, 40))
        for s in range(int(dur) + 1):
            dr.line([(X(s), y0 + 200), (X(s), y0 + 206)], fill='black'); dr.text((X(s) - 4, y0 + 207), str(s), fill='black')
    im.save(path)


def side_by_side(ref, ours, rs, os_, fps, path):
    n = min(len(ref), len(ours))
    H = ref.shape[1]
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{2 * W}x{H + 40}',
                          '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', str(path)],
                         stdin=subprocess.PIPE)
    for i in range(n):
        o = ours[i]
        if o.shape[0] != H:
            o = cv2.resize(o, (W, H))
        canvas = Image.new('RGB', (2 * W, H + 40), 'white')
        canvas.paste(Image.fromarray(ref[i]), (0, 0)); canvas.paste(Image.fromarray(o), (W, 0))
        dr = ImageDraw.Draw(canvas)
        for k, r in enumerate((rs[i], os_[i])):
            x0 = k * W
            dr.rectangle([x0 + 60, H + 12, x0 + 60 + min(400, int(r['speed'] * 3)), H + 28], fill=(29, 124, 242))
            dr.text((x0 + 6, H + 14), ('ref ' if k == 0 else 'ours ') + f'{r["speed"]:.0f}', fill='black')
        dr.text((W - 30, H + 14), f'{i / fps:5.2f}s', fill='red')
        p.stdin.write(canvas.tobytes())
    p.stdin.close(); p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', required=True); ap.add_argument('--ours'); ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=float, default=20)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ref = frames(a.ref, a.fps); rs = flow_stats(ref, a.fps); rm = moves(rs, a.fps)
    res = dict(fps=a.fps, ref=dict(rows=rs, moves=rm))
    series = [('ref', rs)]
    if a.ours:
        ours = frames(a.ours, a.fps); os_ = flow_stats(ours, a.fps); om = moves(os_, a.fps)
        res['ours'] = dict(rows=os_, moves=om); series.append(('ours', os_))
        side_by_side(ref, ours, rs, os_, a.fps, out / 'side-by-side.mp4')
    (out / 'flow.json').write_text(json.dumps(res))
    plot(series, a.fps, out / 'flow.png')
    md = ['# Moves', '']
    for name in ('ref', 'ours'):
        if name not in res:
            continue
        md += [f'## {name}', '', '| start | len | peak | peak speed | t80 | shape | zoom | pan |', '|---|---|---|---|---|---|---|---|']
        md += [f"| {m['start']} | {m['length']} | {m['peak']} | {m['peak_speed']} | {m['t80']} | {m['shape']} | {m['zoom']} | {m['pan']} |"
               for m in res[name]['moves']]
        md.append('')
    if 'ours' in res:
        md += ['## Pacing per 0.5 s (mean speed × moving share)', '', '| t | ref | ours | ref cuts | ours cuts |', '|---|---|---|---|---|']
        step = int(a.fps / 2)
        for s in range(0, min(len(rs), len(res['ours']['rows'])), step):
            f = lambda rows: np.mean([r['speed'] * r['moving'] for r in rows[s:s + step]])
            c = lambda rows: sum(r['cut'] for r in rows[s:s + step])
            md.append(f"| {s / a.fps:.1f} | {f(rs):.1f} | {f(res['ours']['rows']):.1f} | {c(rs)} | {c(res['ours']['rows'])} |")
    (out / 'moves.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
