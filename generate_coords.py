#!/usr/bin/env python3
"""
Quran Word Coordinate Generator — Hybrid QPC + Image Gap Snapping
=================================================================

Uses QPC font advance widths as proportional guide, then snaps word
boundaries to actual gaps in the page image. This handles the case where
page images are from a different rendering than the QPC V1 fonts.

Algorithm:
  1. Load glyph data from quran.com-images MySQL dump (→ SQLite)
  2. For each line, compute expected boundary positions from QPC advance widths
  3. Find all pixel-level gaps in the actual page image
  4. Snap each boundary to the nearest suitable gap (wider gaps preferred)
  5. Validate: no word should be narrower than 30% of its expected width

PREREQUISITES:
  git clone https://github.com/quran/quran.com-images.git
  pip install fonttools Pillow numpy --break-system-packages

USAGE:
  # First time: build SQLite DB from MySQL dump
  python3 generate_coords.py --build-db -q quran.com-images

  # Generate for one page with debug overlay
  python3 generate_coords.py -b . -q quran.com-images -o output --page 3 --debug

  # Batch all 604 pages
  python3 generate_coords.py -b . -q quran.com-images -o output
"""

import json, os, sys, re, sqlite3, argparse
import numpy as np
from PIL import Image, ImageDraw

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("ERROR: pip install fonttools Pillow numpy")
    sys.exit(1)

# ─── Configuration ───────────────────────────────────────────────────────────

TEXT_LEFT, TEXT_RIGHT = 40, 880
INK_THRESH = 180
SNAP_RANGE = 30
MIN_WORD_RATIO = 0.30
MAX_H_HEIGHT = 68
MAX_P_HEIGHT = 23

DEFAULT_LINES = [
    (23, 68, 0, 23), (112, 76, 91, 21), (203, 77, 188, 15),
    (295, 78, 280, 15), (394, 72, 373, 21), (481, 80, 466, 15),
    (580, 76, 561, 19), (674, 79, 656, 18), (767, 79, 753, 14),
    (864, 75, 846, 18), (956, 76, 939, 17), (1050, 78, 1032, 18),
    (1149, 74, 1128, 21), (1242, 74, 1223, 19), (1332, 79, 1316, 16),
]


def build_sqlite_db(quran_images_dir, db_path='quran_glyphs.db'):
    sql_path = os.path.join(quran_images_dir, 'sql', '02-database.sql')
    if not os.path.exists(sql_path):
        print(f"ERROR: {sql_path} not found"); return False
    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS glyph (glyph_id INTEGER PRIMARY KEY, font_file TEXT, glyph_code INTEGER, page_number INTEGER, glyph_type_id INTEGER, glyph_type_meta INTEGER, description TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS glyph_page_line (glyph_page_line_id INTEGER PRIMARY KEY, glyph_id INTEGER, page_number INTEGER, line_number INTEGER, position INTEGER, line_type TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS glyph_ayah (glyph_ayah_id INTEGER PRIMARY KEY, glyph_id INTEGER, sura_number INTEGER, ayah_number INTEGER, position INTEGER)')
    with open(sql_path, 'r') as f: content = f.read()
    def parse_inserts(table):
        rows = []
        for match in re.findall(rf"INSERT INTO `{table}` VALUES\s*(.+?);", content, re.DOTALL):
            for m in re.finditer(r'\(([^)]+)\)', match):
                vals = []
                for v in m.group(1).split(','):
                    v = v.strip().strip("'")
                    if v == 'NULL': vals.append(None)
                    else:
                        try: vals.append(int(v))
                        except: vals.append(v)
                rows.append(tuple(vals))
        return rows
    for table, cols in [('glyph', 7), ('glyph_page_line', 6), ('glyph_ayah', 5)]:
        print(f"  {table}...", end='', flush=True)
        rows = parse_inserts(table)
        c.executemany(f'INSERT OR IGNORE INTO {table} VALUES ({",".join(["?"]*cols)})', rows)
        print(f" {len(rows)} rows")
    c.execute('CREATE INDEX IF NOT EXISTS i1 ON glyph_page_line(page_number)')
    c.execute('CREATE INDEX IF NOT EXISTS i2 ON glyph_ayah(sura_number,ayah_number)')
    c.execute('CREATE INDEX IF NOT EXISTS i3 ON glyph(page_number)')
    conn.commit(); conn.close()
    print(f"  ✓ {db_path}"); return True


_font_cache = {}
def get_font_advances(font_path):
    if font_path in _font_cache: return _font_cache[font_path]
    tt = TTFont(font_path); cmap = tt.getBestCmap(); hmtx = tt['hmtx']
    adv = {cp: hmtx.metrics[gn][0] for cp, gn in cmap.items() if gn in hmtx.metrics}
    tt.close(); _font_cache[font_path] = adv; return adv


def find_ink_extent(gray, y1, y2):
    strip = gray[y1:y2, TEXT_LEFT:TEXT_RIGHT]
    ci = np.sum(strip < INK_THRESH, axis=0); ic = np.where(ci > 0)[0]
    if len(ic) == 0: return TEXT_LEFT, TEXT_RIGHT, y1, y2
    ri = np.sum(strip < INK_THRESH, axis=1); ir = np.where(ri > 3)[0]
    return int(ic[0]+TEXT_LEFT), int(ic[-1]+TEXT_LEFT), int(ir[0]+y1) if len(ir) else y1, int(ir[-1]+y1+1) if len(ir) else y2


def find_all_gaps(gray, y1, y2, x1, x2):
    strip = gray[y1:y2, x1:x2]; ci = np.sum(strip < INK_THRESH, axis=0)
    gaps = []; ing = False; gs = 0
    for i in range(len(ci)):
        if ci[i] == 0:
            if not ing: gs = i; ing = True
        else:
            if ing:
                w = i - gs
                if w >= 2: gaps.append({'center': gs + w//2 + x1, 'width': w})
                ing = False
    return gaps


def compute_line_cuts(glyphs, font_adv, gray, y1, y2, ink_l, ink_r):
    n = len(glyphs); lw = ink_r - ink_l
    if lw <= 0 or n == 0: return None
    advs = [font_adv.get(g['code'], 500) for g in glyphs]
    total = sum(advs)
    if total == 0: return None
    expected_w = [int(a / total * lw) for a in advs]

    prop = [ink_r]; cum = 0
    for i in range(n - 1):
        cum += advs[i]; prop.append(ink_r - int(cum / total * lw))
    prop.append(ink_l)

    all_gaps = find_all_gaps(gray, y1, y2, ink_l, ink_r)
    used = set(); cuts = [prop[0]]

    for ci in range(1, n):
        target = prop[ci]; prev = cuts[-1]; exp_w = expected_w[ci - 1]
        best = None; best_score = -999
        for gi, g in enumerate(all_gaps):
            if gi in used: continue
            dist = abs(g['center'] - target)
            if dist > SNAP_RANGE: continue
            w_left = prev - g['center']
            if w_left < max(20, int(exp_w * MIN_WORD_RATIO)): continue
            score = g['width'] * 2.0 - dist * 0.5
            if score > best_score: best_score = score; best = (gi, g['center'])
        if best: used.add(best[0]); cuts.append(best[1])
        else: cuts.append(target)

    cuts.append(prop[-1])
    for _ in range(3):
        changed = False
        for i in range(n):
            w = cuts[i] - cuts[i+1]
            if w < max(20, int(expected_w[i] * MIN_WORD_RATIO)):
                cuts[i+1] = prop[i+1]; changed = True
        if not changed: break
    return cuts


def process_page(page_num, base_dir, fonts_dir, db_path, output_dir, debug=False):
    ps = f"page-{page_num:03d}"
    img_path = None
    for ext in ['png', 'jpg']:
        p = os.path.join(base_dir, 'images', f'{ps}.{ext}')
        if os.path.exists(p): img_path = p; break
    if not img_path: return None

    font_path = os.path.join(fonts_dir, f'QCF_P{page_num:03d}.TTF')
    if not os.path.exists(font_path): return None
    font_adv = get_font_advances(font_path)
    gray = np.array(Image.open(img_path).convert('L'))

    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute('''SELECT gpl.line_number, g.glyph_code, g.glyph_type_id,
        ga.sura_number, ga.ayah_number, ga.position
        FROM glyph_page_line gpl JOIN glyph g ON g.glyph_id=gpl.glyph_id
        LEFT JOIN glyph_ayah ga ON ga.glyph_id=gpl.glyph_id
        WHERE gpl.page_number=? AND gpl.line_type='ayah'
        ORDER BY gpl.line_number, gpl.position''', (page_num,))
    db_lines = {}
    for r in c.fetchall():
        ln = r[0]
        if ln not in db_lines: db_lines[ln] = []
        db_lines[ln].append({'code': r[1], 'tid': r[2], 'sura': r[3], 'ayah': r[4], 'wpos': r[5]})
    conn.close()
    if not db_lines: return None

    coords = {}; text_idx = 0
    for line_num in sorted(db_lines.keys()):
        if text_idx >= len(DEFAULT_LINES): break
        ty, th, gy, gh = DEFAULT_LINES[text_idx]; text_idx += 1
        glyphs = db_lines[line_num]
        y1, y2 = ty, min(ty + th, gray.shape[0])
        ink_l, ink_r, ink_top, ink_bot = find_ink_extent(gray, y1, y2)
        cuts = compute_line_cuts(glyphs, font_adv, gray, y1, y2, ink_l, ink_r)
        if cuts is None: continue
        actual_h = ink_bot - ink_top
        for i, g in enumerate(glyphs):
            xr, xl = cuts[i], cuts[i+1]
            if xl > xr: xl, xr = xr, xl
            w = max(xr - xl, 1)
            if g['tid'] == 1 and g['sura'] is not None:
                loc = f"{g['sura']}:{g['ayah']}:{g['wpos']}"
                h_h = min(actual_h, MAX_H_HEIGHT)
                coords[loc] = {
                    'h': {'x': xl, 'y': ink_top, 'w': w, 'h': h_h},
                    'p': {'x': xl, 'y': gy + max(0,(gh-min(gh,MAX_P_HEIGHT))//2), 'w': w, 'h': min(gh, MAX_P_HEIGHT)},
                    'o': {'x': 0, 'y': ink_top, 'w': 39, 'h': h_h},
                }

    result = {'page': page_num, 'coords': coords}
    with open(os.path.join(output_dir, f'{ps}.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if debug:
        img = Image.open(img_path).convert('RGBA')
        ov = Image.new('RGBA', img.size, (0,0,0,0)); draw = ImageDraw.Draw(ov)
        palette = [(255,50,50),(50,180,50),(50,50,255),(255,165,0),(160,32,240),(0,200,200),(200,50,120),(120,120,0)]
        for ci, (loc, layers) in enumerate(coords.items()):
            h = layers['h']; c = palette[ci % len(palette)]
            draw.rectangle([h['x'], h['y'], h['x']+h['w']-1, h['y']+h['h']-1],
                           fill=(*c, 30), outline=(*c, 200), width=2)
        Image.alpha_composite(img, ov).save(os.path.join(output_dir, f'debug-{ps}.png'))
    return result


def main():
    p = argparse.ArgumentParser(description='Quran Word Coordinates (QPC + Gap Snap)')
    p.add_argument('--base-dir', '-b', default='.')
    p.add_argument('--output-dir', '-o', default='output')
    p.add_argument('--quran-images-dir', '-q', default='quran.com-images')
    p.add_argument('--db', default='quran_glyphs.db')
    p.add_argument('--page', '-p', type=int)
    p.add_argument('--start', '-s', type=int, default=1)
    p.add_argument('--end', '-e', type=int, default=604)
    p.add_argument('--debug', '-d', action='store_true')
    p.add_argument('--build-db', action='store_true')
    args = p.parse_args()

    if args.build_db or not os.path.exists(args.db):
        print("Building SQLite database...")
        if not build_sqlite_db(args.quran_images_dir, args.db): sys.exit(1)

    fonts_dir = os.path.join(args.quran_images_dir, 'res', 'fonts')
    if not os.path.isdir(fonts_dir):
        print(f"ERROR: {fonts_dir} not found\n  git clone https://github.com/quran/quran.com-images.git"); sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    pages = [args.page] if args.page else list(range(args.start, args.end + 1))
    print(f"Processing {len(pages)} pages...")
    ok = fail = 0
    for i, pn in enumerate(pages):
        print(f"  [{i+1}/{len(pages)}] Page {pn}...", end='', flush=True)
        try:
            r = process_page(pn, args.base_dir, fonts_dir, args.db, args.output_dir, args.debug)
            if r: print(f" ✓ {len(r['coords'])} words"); ok += 1
            else: print(" skip"); fail += 1
        except Exception as e: print(f" ✗ {e}"); fail += 1
    print(f"\nDone: {ok} ok, {fail} skip → {args.output_dir}/")

if __name__ == '__main__':
    main()
