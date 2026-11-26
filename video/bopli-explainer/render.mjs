// Render comp.html frame by frame with Playwright.
//   node render.mjs stills <out.png> 0.5,1.2,3.0      contact sheet of chosen times
//   node render.mjs video  <out.mp4> [fps=60] [workers=4]
// Video mode renders at 2×fps and blends frame pairs (180° shutter motion blur), then encodes H.264.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }
const { chromium } = pw;
const here = path.dirname(fileURLToPath(import.meta.url));
const url = pathToFileURL(path.join(here, 'comp.html')).href;
const [mode, out, a3, a4] = process.argv.slice(2);

async function page(browser) {
  const p = await browser.newPage({ viewport: { width: 1440, height: 1080 }, deviceScaleFactor: 1 });
  p.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await p.goto(url);
  await p.evaluate(() => window.__ready);
  return p;
}
const run = (cmd, args, opts = {}) => new Promise((res, rej) => {
  const c = spawn(cmd, args, { stdio: ['pipe', 'inherit', 'inherit'], ...opts });
  c.on('exit', code => code ? rej(new Error(`${cmd} exited ${code}`)) : res());
  return c;
});

if (mode === 'stills') {
  const times = a3.split(',').map(Number);
  const b = await chromium.launch();
  const p = await page(b);
  const tmp = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), 'st-'));
  const files = [];
  for (const t of times) {
    await p.evaluate(t => window.__seek(t), t);
    const f = path.join(tmp, `${t.toFixed(3)}.png`);
    await p.screenshot({ path: f });
    files.push(f);
  }
  await b.close();
  const cols = Math.min(3, files.length);
  const rows = Math.ceil(files.length / cols);
  const filt = files.map((_, i) => `[${i}:v]scale=480:360,drawtext=text='${times[i].toFixed(2)}':x=8:y=8:fontsize=22:fontcolor=red:box=1:boxcolor=white@0.7[v${i}]`).join(';');
  const layout = files.map((_, i) => `${(i % cols) * 480}_${Math.floor(i / cols) * 360}`).join('|');
  const pad = Array.from({ length: rows * cols - files.length }, () => '');
  await run('ffmpeg', ['-v', 'error', '-y', ...files.flatMap(f => ['-i', f]), '-filter_complex',
    files.length > 1 ? `${filt};${files.map((_, i) => `[v${i}]`).join('')}xstack=inputs=${files.length}:layout=${layout}:fill=gray` : filt.replace('[v0]', ''), out]);
  fs.rmSync(tmp, { recursive: true });
  console.log('wrote', out);
} else if (mode === 'video') {
  const fps = +(a3 || 60), workers = +(a4 || 4), sub = 2, rfps = fps * sub;
  const browser = await chromium.launch();
  const dur = await (await page(browser)).evaluate(() => window.__dur);
  const N = Math.round(dur * rfps);
  const tmp = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), 'seg-'));
  const chunk = Math.ceil(N / workers);
  const t0 = Date.now();
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const a = w * chunk, b = Math.min(N, a + chunk);
    if (a >= b) return;
    const p = await page(browser);
    const seg = path.join(tmp, `seg${w}.mkv`);
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(rfps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'ffv1', seg], { stdio: ['pipe', 'inherit', 'inherit'] });
    const done = new Promise((res, rej) => ff.on('exit', c => c ? rej(new Error('ffmpeg seg ' + c)) : res()));
    for (let i = a; i < b; i++) {
      await p.evaluate(t => window.__seek(t), i / rfps);
      const buf = await p.screenshot({ type: 'jpeg', quality: 96 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (w === 0 && i % 60 === 0) console.log(`frame ${i}/${b} · ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await done; await p.close();
  }));
  await browser.close();
  const list = path.join(tmp, 'list.txt');
  fs.writeFileSync(list, Array.from({ length: workers }, (_, w) => `file 'seg${w}.mkv'`).filter((_, w) => w * chunk < N).join('\n'));
  await run('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list,
    '-vf', `tmix=frames=${sub}:weights=1 1,select=not(mod(n\\,${sub})),setpts=N/${fps}/TB`, '-r', String(fps),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', out]);
  fs.rmSync(tmp, { recursive: true });
  console.log(`wrote ${out} in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
