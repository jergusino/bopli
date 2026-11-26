#!/usr/bin/env python3
"""Download a reel (or take a local file) and break it down so its motion can be copied.

Usage:
  python3 video/tools/grab_reel.py --source <url-or-file> --out <folder> [--cookies cookies.txt] [--fps 10]

Output in <folder>:
  ref.mp4              the video (downloaded or copied)
  frames/              frames at --fps (JPEG)
  sheets/sheet-NN.png  contact sheets, one row per second, timestamps burned in
  energy.png           motion energy over time, cuts and audio hits marked
  audio.wav            mono 22.05 kHz audio
  analysis.json        numbers: duration, size, cuts, still stretches, shot lengths, audio hits
  analysis.md          the same, readable

Needs: yt-dlp (for URLs), ffmpeg/ffprobe, python3 with numpy + Pillow.
Instagram often blocks cloud and logged-out requests; pass --cookies (Netscape cookies.txt
exported from a logged-in browser) or download the file yourself and pass its path.
"""
import argparse, json, math, shutil, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def acquire(source, out, cookies):
    dst = out / "ref.mp4"
    p = Path(source).expanduser()
    if p.exists():
        shutil.copy(p, dst)
        return dst
    cmd = ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", str(dst), source]
    if cookies:
        cmd[1:1] = ["--cookies", cookies]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not dst.exists():
        sys.exit("download failed:\n" + (r.stderr or r.stdout)[-1500:] +
                 "\nTip: pass --cookies cookies.txt, or download the reel yourself and pass the file path.")
    return dst


def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    num, den = v.get("avg_frame_rate", "30/1").split("/")
    return {
        "duration": float(j["format"]["duration"]),
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": round(float(num) / float(den or 1), 3),
        "has_audio": any(s["codec_type"] == "audio" for s in j["streams"]),
    }


def extract_frames(path, out, fps):
    d = out / "frames"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale=360:-2", "-q:v", "3", str(d / "f%05d.jpg")])
    return sorted(d.glob("f*.jpg"))


def motion(frames):
    """Per-step energy (mean abs diff, 0-255) and colour-histogram distance for cut detection."""
    prev = prevh = None
    energy, hist = [0.0], [0.0]
    for f in frames:
        im = Image.open(f).convert("RGB").resize((96, 170))
        a = np.asarray(im, dtype=np.float32)
        h = np.concatenate([np.histogram(a[..., c], 32, (0, 256))[0] for c in range(3)]).astype(np.float32)
        h /= h.sum()
        if prev is not None:
            energy.append(float(np.abs(a - prev).mean()))
            hist.append(float(0.5 * np.abs(h - prevh).sum()))
        prev, prevh = a, h
    return np.array(energy[: len(frames)]), np.array(hist[: len(frames)])


def find_cuts(energy, hist, fps):
    cuts = []
    med = np.median(energy) + 1e-6
    for i in range(1, len(energy)):
        if hist[i] > 0.35 or (energy[i] > max(25, 6 * med) and hist[i] > 0.15):
            if not cuts or i - cuts[-1] > fps * 0.15:
                cuts.append(i)
    return [round(i / fps, 2) for i in cuts]


def still_stretches(energy, fps, thr=1.0, min_len=0.3):
    out, start = [], None
    for i, e in enumerate(list(energy) + [99]):
        if e < thr and start is None:
            start = i
        elif e >= thr and start is not None:
            if (i - start) / fps >= min_len:
                out.append([round(start / fps, 2), round(i / fps, 2)])
            start = None
    return out


def audio_hits(path, out):
    wav = out / "audio.wav"
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "22050", str(wav)])
    except subprocess.CalledProcessError:
        return [], None
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = 256
    n = len(x) // hop
    if n < 4:
        return [], None
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(1)) + 1e-9
    db = np.maximum(20 * np.log10(rms), -80)
    # onset strength: rise of the level over the next ~35 ms vs the last ~35 ms
    k = 3
    pad = np.pad(db, (k, k), mode="edge")
    flux = np.maximum(0, np.array([pad[i + k: i + 2 * k].max() - pad[i: i + k].mean() for i in range(n)]))
    thr = max(6.0, np.percentile(flux, 95))
    hits, last = [], -1
    for i in range(1, n - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1] - 1e-9 and db[i: i + 4].max() > -45:
            t = i * hop / sr
            if t - last > 0.08:
                hits.append({"t": round(t, 3), "db": round(float(db[min(n - 1, i + 3)]), 1)})
                last = t
    return hits, (np.arange(n) * hop / sr, db)


def sheets(frames, fps, out, per_row=None):
    d = out / "sheets"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    per_row = per_row or int(fps)
    rows_per_sheet = 6
    tw = 150
    th = int(tw * Image.open(frames[0]).height / Image.open(frames[0]).width)
    n_rows = math.ceil(len(frames) / per_row)
    paths = []
    for s in range(math.ceil(n_rows / rows_per_sheet)):
        rows = range(s * rows_per_sheet, min(n_rows, (s + 1) * rows_per_sheet))
        sheet = Image.new("RGB", (per_row * tw, len(rows) * (th + 16)), "white")
        dr = ImageDraw.Draw(sheet)
        for ri, r in enumerate(rows):
            for c in range(per_row):
                i = r * per_row + c
                if i >= len(frames):
                    break
                im = Image.open(frames[i]).resize((tw, th))
                sheet.paste(im, (c * tw, ri * (th + 16) + 16))
                dr.text((c * tw + 3, ri * (th + 16) + 2), f"{i / fps:.1f}s", fill="black")
        p = d / f"sheet-{s + 1:02d}.png"
        sheet.save(p)
        paths.append(p)
    return paths


def plot_energy(energy, fps, cuts, hits, audio, out):
    W, H = 1600, 360
    im = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(im)
    dur = len(energy) / fps
    X = lambda t: int(40 + (W - 60) * t / max(dur, 1e-6))
    top = max(energy.max(), 1)
    pts = [(X(i / fps), int(200 - 170 * e / top)) for i, e in enumerate(energy)]
    dr.line(pts, fill=(29, 124, 242), width=2)
    for c in cuts:
        dr.line([(X(c), 20), (X(c), 200)], fill=(234, 43, 43), width=1)
    if audio is not None:
        t, db = audio
        apts = [(X(tt), int(340 - 120 * (max(d, -60) + 60) / 60)) for tt, d in zip(t[::4], db[::4])]
        dr.line(apts, fill=(120, 120, 120), width=1)
    for h in hits:
        dr.ellipse([X(h["t"]) - 3, 215, X(h["t"]) + 3, 221], fill=(0, 0, 0))
    for s in range(int(dur) + 1):
        dr.text((X(s) - 4, 202), str(s), fill="black")
    dr.text((40, 4), "motion energy (blue) · cuts (red) · audio level (grey) · audio hits (dots)", fill="black")
    im.save(out / "energy.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cookies")
    ap.add_argument("--fps", type=float, default=10)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    ref = acquire(a.source, out, a.cookies)
    info = probe(ref)
    frames = extract_frames(ref, out, a.fps)
    energy, hist = motion(frames)
    cuts = find_cuts(energy, hist, a.fps)
    still = still_stretches(energy, a.fps)
    bounds = [0.0] + cuts + [round(info["duration"], 2)]
    shots = [round(b - a_, 2) for a_, b in zip(bounds, bounds[1:]) if b - a_ > 0.01]
    hits, audio = audio_hits(ref, out) if info["has_audio"] else ([], None)
    sheet_paths = sheets(frames, a.fps, out)
    plot_energy(energy, a.fps, cuts, hits, audio, out)

    still_total = sum(b - s for s, b in still)
    res = {
        **info,
        "source": a.source,
        "frames_fps": a.fps,
        "cuts": cuts,
        "shot_lengths": shots,
        "still_stretches": still,
        "still_share": round(still_total / info["duration"], 3),
        "energy_per_second": [round(float(energy[int(s * a.fps): int((s + 1) * a.fps)].mean()), 2)
                              for s in range(int(math.ceil(info["duration"])))
                              if energy[int(s * a.fps): int((s + 1) * a.fps)].size],
        "audio_hits": hits,
        "sheets": [str(p.relative_to(out)) for p in sheet_paths],
    }
    (out / "analysis.json").write_text(json.dumps(res, indent=2))
    md = [f"# Reel breakdown", "",
          f"- {info['width']}×{info['height']} · {info['fps']} fps · {info['duration']:.2f} s · audio: {info['has_audio']}",
          f"- cuts ({len(cuts)}): {', '.join(map(str, cuts)) or 'none'}",
          f"- shot lengths: {', '.join(map(str, shots))}",
          f"- still: {res['still_share'] * 100:.0f}% · stretches: {still}",
          f"- energy / s: {res['energy_per_second']}",
          f"- audio hits ({len(hits)}): {', '.join(str(h['t']) for h in hits)}",
          "", "Sheets: " + ", ".join(res["sheets"]) + " · energy.png"]
    (out / "analysis.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
