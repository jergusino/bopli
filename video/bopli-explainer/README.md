# Bopli explainer video

An 18.8 s explainer for Bopli. It copies the beat structure, timing and transitions of a reference reel, with new copy, stock photos and sound effects.

- Output: 1440×1080 (4:3, same as the reference), 60 fps, motion blur from 240 fps renders averaged in fours.
- Audio: `out/bopli-explainer-v3-vo.mp4` has the reference reel's original audio, our sound effects and a voice-over, mastered to -14 LUFS. `out/bopli-explainer-v2.mp4` has the sound effects only. The SFX and VO stems are in `out/` as WAVs.
- The original audio belongs to the reference reel's creator. It is not stored in this repo on its own; only the v3 mix contains it.

## Files

| file | what |
|---|---|
| `comp.html` | The whole film as one HTML page. Every frame is a pure function of time: `window.__seek(t)`. Preview it with `comp.html?play` or `comp.html?t=8.4`. |
| `render.mjs` | Playwright renderer. `node render.mjs stills out.png 1.2,3.4` makes a contact sheet. `node render.mjs video out.mp4 60 4 4` renders the video (fps, workers, sub-frames for motion blur). |
| `mix_sfx.py` | Places the downloaded sound effects on the cut and writes the SFX stem. It only trims, pans and sets levels. Nothing is synthesised. |
| `mix_final.py` | Final mix: the reference's original audio (ducked under the voice), the SFX track and the voice-over, two-pass loudnorm to -14 LUFS / -1.5 dBTP. |
| `vo/` | `make_vo.py` speaks the script with Kokoro-82M (Apache-2.0, voice `af_heart`) through kokoro-onnx, fitting each line to its slot on the cut. `lines.json` has the script and timing; `lines/` the takes. |
| `photos/` | Unsplash stock photos (Unsplash License). Sources are in `photos/CREDITS.md`. |
| `sfx/` | Sound effects: recordings from [Freesound](https://freesound.org), all CC0. Titles, authors and links are in `sfx/CREDITS.md`. |
| `fonts/` | Inter, Instrument Serif, Caveat and Nunito (OFL, licences included). |
| `../tools/grab_reel.py` | Downloads a reference reel and analyses it: frames, contact sheets, motion energy, cuts, still stretches and audio hits. |
| `../tools/motion_compare.py` | Optical-flow comparison of the reference and a remake: speed, zoom and pan curves, a move table with easing shape (t80), pacing per 0.5 s, and a synced side-by-side video. |
| `../tools/freesound_fetch.py` | Searches Freesound for CC0 sounds only and downloads their HQ previews with credits. |

## Beat sheet (the reference's timing, Bopli copy)

| t (s) | beat |
|---|---|
| 0.0–1.6 | Handwritten *one*, iOS text selection on **photo**, typo "evry mornig" gets corrected on black, Bopli badge pops in, everything blooms into a white dot |
| 1.6–3.6 | Distance tracker: 820 km → 0 km "away from mom", the ring closes, the disc flips to a Bopli coin, "right here" |
| 3.6–4.2 | Four photo cuts, one every 0.15 s: sunrise, phone home screen, latte, camera lens |
| 4.2–5.7 | A line circle and fish outline draw on, text rings "all day, together." spin up, the frame folds into the shutter button |
| 5.7–7.9 | Camera "New Bopli": the viewfinder grows from a circle, a morning selfie gets "good morning ☀" written on it, the shutter fires |
| 7.9–10.55 | Canvas: the photo card gets dragged, an info window ("Seen by: Mom, Dad, Ema, Grandma"), a cluster of family photos with transform gizmos, then fade to dark |
| 10.55–11.1 | Giant wavy word "miles" |
| 11.1–13.1 | "miles (❌→✈️) apart ←" then "still (🫶) close ↗" |
| 13.1–16.05 | The line becomes a sent chat bubble, a reply "saw your morning..", typing "Bopli. Coming so on", then select, Delete and retype "soon" |
| 16.05–18.84 | Glitch to black, spinner, Bopli wordmark |

## Rebuild

```bash
node render.mjs video silent.mp4 60 4 4
python3 mix_sfx.py sfx-track.wav
ffmpeg -i silent.mp4 -i sfx-track.wav -af "volume=5dB" -c:v copy -c:a aac -b:a 256k -shortest out/bopli-explainer-v2.mp4
python3 vo/make_vo.py <folder with kokoro-v1.0.onnx + voices-v1.0.bin> af_heart
python3 mix_final.py --music reference.mp4 --sfx sfx-track.wav --out mix.wav
ffmpeg -i silent.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest out/bopli-explainer-v3-vo.mp4
```
