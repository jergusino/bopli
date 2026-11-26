#!/usr/bin/env python3
"""Search Freesound for CC0 sounds and download their HQ previews (no API key needed).

  python3 video/tools/freesound_fetch.py --out <folder> --top 8 "whoosh" "sub boom" ...

Only sounds licensed Creative Commons 0 are fetched (the search is filtered on it, and each
result's licence is checked again). Per query: <folder>/<query-slug>/<id>-<title-slug>.mp3
and one meta.json with title, author, duration, downloads and the sound's page.
"""
import argparse, html, json, re, time, urllib.parse, urllib.request
from pathlib import Path

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) sfx-fetch'}
BLOCK = re.compile(r'<div class="bw-search__result".*?(?=<div class="bw-search__result"|\Z)', re.S)


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40]


def search(q, top):
    url = 'https://freesound.org/search/?' + urllib.parse.urlencode(
        {'q': q, 'f': 'license:"Creative Commons 0"', 's': 'Downloads (most first)', 'g': '0'})
    page = get(url).decode('utf-8', 'replace')
    out = []
    for b in BLOCK.findall(page):
        a = lambda k: (m.group(1) if (m := re.search(rf'data-{k}="([^"]*)"', b)) else '')
        if 'License: Creative Commons 0' not in b or not a('sound-id'):
            continue
        out.append(dict(id=int(a('sound-id')), title=html.unescape(a('title')), user=a('username'),
                        duration=float(a('duration') or 0), downloads=int(a('num-downloads') or 0),
                        preview=a('mp3').replace('-lq.mp3', '-hq.mp3'),
                        page=f"https://freesound.org/people/{a('username')}/sounds/{a('sound-id')}/", license='CC0'))
        if len(out) >= top:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--max-dur', type=float, default=8.0)
    ap.add_argument('queries', nargs='+')
    a = ap.parse_args()
    root = Path(a.out)
    for q in a.queries:
        d = root / slug(q); d.mkdir(parents=True, exist_ok=True)
        res = [r for r in search(q, a.top * 2) if r['duration'] <= a.max_dur][: a.top]
        for r in res:
            f = d / f"{r['id']}-{slug(r['title'])}.mp3"
            if not f.exists():
                f.write_bytes(get(r['preview']))
            r['file'] = f.name
        (d / 'meta.json').write_text(json.dumps(res, indent=1))
        print(f'{q}: {len(res)}  ' + ' | '.join(f"{r['title'][:28]} ({r['duration']:.1f}s)" for r in res))


if __name__ == '__main__':
    main()
