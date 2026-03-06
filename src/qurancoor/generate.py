#!/usr/bin/env python3
"""
Quran Word Coordinate Generator — v3 Fixed
============================================

CRITICAL FIX: The quran.com-images DB numbers waqf marks (ۖ ۗ etc.) as word
positions (e.g., 2:38:5 = ۖ), but the mushaf JSON skips them (2:38:5 = فإما).
This caused ALL word boxes after a waqf mark to shift by one position.

SOLUTION: Use mushaf JSON as the source of truth for word locations.
Match by ORDER within each line, not by DB position numbers.

Algorithm:
  1. For each line, get ALL glyphs from DB (words + markers + waqf)
  2. Compute proportional cuts for ALL glyphs (so markers get their space)
  3. Snap cuts to actual image gaps
  4. Collect only type=1 (word) cuts in ORDER
  5. Assign mushaf locations to those cuts by ORDER (1st word cut → 1st mushaf word)

USAGE:
  python3 generate_coords.py --build-db -q quran.com-images
  python3 generate_coords.py -b . -q quran.com-images -o output --page 7 --debug
  python3 generate_coords.py -b . -q quran.com-images -o output --all
"""

import json, os, sys, re, sqlite3, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("ERROR: pip install fonttools Pillow numpy")
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────────────────────

TEXT_LEFT, TEXT_RIGHT = 40, 880
INK_THRESH = 180
SNAP_RANGE = 30
MIN_WORD_RATIO = 0.25
MIN_WORD_PX = 15

DEFAULT_LINES_15 = [
    (23, 68, 0, 23), (112, 76, 91, 21), (203, 77, 188, 15),
    (295, 78, 280, 15), (394, 72, 373, 21), (481, 80, 466, 15),
    (580, 76, 561, 19), (674, 79, 656, 18), (767, 79, 753, 14),
    (864, 75, 846, 18), (956, 76, 939, 17), (1050, 78, 1032, 18),
    (1149, 74, 1128, 21), (1242, 74, 1223, 19), (1332, 79, 1316, 16),
]

DEFAULT_LINES_8 = [
    (175, 120, 150, 25), (320, 120, 295, 25), (465, 120, 440, 25),
    (610, 120, 585, 25), (755, 120, 730, 25), (900, 120, 875, 25),
    (1045, 120, 1020, 25), (1190, 120, 1165, 25),
]


# ─── DB Builder ──────────────────────────────────────────────────────────────

def build_sqlite_db(quran_images_dir, db_path='quran_glyphs.db'):
    sql_path = os.path.join(quran_images_dir, 'sql', '02-database.sql')
    if not os.path.exists(sql_path):
        print(f"ERROR: {sql_path} not found"); return False
    conn = sqlite3.connect(db_path); c = conn.cursor()
    for t in ['glyph', 'glyph_page_line', 'glyph_ayah']:
        c.execute(f'DROP TABLE IF EXISTS {t}')
    c.execute('CREATE TABLE glyph (glyph_id INTEGER PRIMARY KEY, font_file TEXT, glyph_code INTEGER, page_number INTEGER, glyph_type_id INTEGER, glyph_type_meta INTEGER, description TEXT)')
    c.execute('CREATE TABLE glyph_page_line (glyph_page_line_id INTEGER PRIMARY KEY, glyph_id INTEGER, page_number INTEGER, line_number INTEGER, position INTEGER, line_type TEXT)')
    c.execute('CREATE TABLE glyph_ayah (glyph_ayah_id INTEGER PRIMARY KEY, glyph_id INTEGER, sura_number INTEGER, ayah_number INTEGER, position INTEGER)')
    with open(sql_path, 'r') as f:
        content = f.read()
    def parse_inserts(table):
        rows = []
        for m in re.findall(rf"INSERT INTO `{table}` VALUES\s*(.+?);", content, re.S):
            for row in re.findall(r'\(([^)]+)\)', m):
                vals = []
                for v in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", row):
                    v = v.strip().strip("'")
                    if v == 'NULL': vals.append(None)
                    else:
                        try: vals.append(int(v))
                        except: vals.append(v)
                rows.append(vals)
        return rows
    for table, cols in [('glyph', 7), ('glyph_page_line', 6), ('glyph_ayah', 5)]:
        rows = parse_inserts(table)
        if rows:
            ph = ','.join(['?'] * cols)
            c.executemany(f'INSERT INTO {table} VALUES ({ph})', [r[:cols] for r in rows])
            print(f"  {table}: {len(rows)} rows")
    conn.commit()
    c.execute('CREATE INDEX IF NOT EXISTS idx_gpl_page ON glyph_page_line(page_number)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ga_glyph ON glyph_ayah(glyph_id)')
    conn.commit(); conn.close()
    print(f"  → {db_path}"); return True


# ─── Font ────────────────────────────────────────────────────────────────────

def get_font_advances(font_path):
    tt = TTFont(font_path)
    cmap = tt.getBestCmap(); hmtx = tt['hmtx']
    adv = {}
    for cp, gn in cmap.items():
        if gn in hmtx.metrics:
            adv[cp] = hmtx.metrics[gn][0]
    tt.close()
    return adv


# ─── Image Analysis ──────────────────────────────────────────────────────────

def detect_line_bands(gray, expected):
    h_proj = np.sum(gray < INK_THRESH, axis=1)
    thr = max(3, np.max(h_proj) * 0.05)
    in_t = False; bands = []; s = 0
    for y in range(len(h_proj)):
        if h_proj[y] >= thr:
            if not in_t: s = y; in_t = True
        else:
            if in_t and y - s > 15: bands.append((s, y)); in_t = False
    if in_t and len(h_proj) - s > 15: bands.append((s, len(h_proj)))
    return bands if len(bands) == expected else None


def find_ink_extent(gray, y1, y2):
    strip = gray[y1:y2, TEXT_LEFT:TEXT_RIGHT]
    ci = np.sum(strip < INK_THRESH, axis=0)
    ic = np.where(ci > 0)[0]
    if len(ic) == 0: return TEXT_LEFT, TEXT_RIGHT
    return int(ic[0] + TEXT_LEFT), int(ic[-1] + TEXT_LEFT + 1)


def find_ink_rows(gray, y1, y2):
    strip = gray[y1:y2, TEXT_LEFT:TEXT_RIGHT]
    ri = np.sum(strip < INK_THRESH, axis=1)
    ir = np.where(ri > 3)[0]
    if len(ir) == 0: return y1, y2
    return int(ir[0] + y1), int(ir[-1] + y1 + 1)


def find_all_gaps(gray, y1, y2, xl, xr):
    strip = gray[y1:y2, xl:xr]
    ci = np.sum(strip < INK_THRESH, axis=0)
    gaps = []; ing = False; gs = 0
    for i in range(len(ci)):
        if ci[i] == 0:
            if not ing: gs = i; ing = True
        else:
            if ing:
                w = i - gs
                if w >= 2: gaps.append({'center': gs + w//2 + xl, 'width': w})
                ing = False
    if ing:
        w = len(ci) - gs
        if w >= 2: gaps.append({'center': gs + w//2 + xl, 'width': w})
    return gaps


# ─── Core: Compute cuts for ALL glyphs ──────────────────────────────────────

def compute_all_cuts(all_glyphs, font_adv, gray, y1, y2, ink_l, ink_r, snap_range):
    n = len(all_glyphs)
    lw = ink_r - ink_l
    if lw <= 0 or n == 0: return None

    advs = [font_adv.get(g['code'], 500) for g in all_glyphs]
    total = sum(advs)
    if total == 0: return None

    # Proportional positions for ALL glyphs
    prop = [ink_r]
    cum = 0
    for i in range(n - 1):
        cum += advs[i]
        prop.append(ink_r - int(cum / total * lw))
    prop.append(ink_l)

    all_gaps = find_all_gaps(gray, y1, y2, ink_l, ink_r)
    used = set()
    cuts = [prop[0]]

    for ci in range(1, n):
        target = prop[ci]
        prev = cuts[-1]
        exp_w = int(advs[ci-1] / total * lw)

        adj_marker = (all_glyphs[ci-1].get('tid') in (2, 3, 4) or all_glyphs[ci].get('tid') in (2, 3, 4))
        sr = snap_range + 15 if adj_marker else snap_range

        best = None; best_score = -999
        for gi, g in enumerate(all_gaps):
            if gi in used: continue
            dist = abs(g['center'] - target)
            if dist > sr: continue
            w_left = prev - g['center']
            min_w = max(MIN_WORD_PX, int(exp_w * MIN_WORD_RATIO))
            if w_left < min_w: continue
            w_bonus = 3.0 if adj_marker else 2.0
            score = g['width'] * w_bonus - dist * 0.5
            if score > best_score: best_score = score; best = (gi, g['center'])

        if best: used.add(best[0]); cuts.append(best[1])
        else: cuts.append(target)

    cuts.append(prop[-1])

    # Fix narrow
    for _ in range(3):
        changed = False
        for i in range(n):
            w = cuts[i] - cuts[i+1]
            min_w = max(MIN_WORD_PX, int(advs[i] / total * lw * MIN_WORD_RATIO))
            if w < min_w: cuts[i+1] = prop[i+1]; changed = True
        if not changed: break

    return cuts


# ─── Page Processor ──────────────────────────────────────────────────────────

def process_page(page_num, base_dir, quran_images_dir, db_path, output_dir, mushaf_dir, debug=False):
    # Load image
    img_path = None
    for ext in ['png', 'jpg', 'jpeg', 'webp']:
        p = os.path.join(base_dir, 'images', f'page-{page_num:03d}.{ext}')
        if os.path.exists(p): img_path = p; break
    if not img_path: return None

    gray = np.array(Image.open(img_path).convert('L'))
    page_h, page_w = gray.shape

    # Load font
    font_path = os.path.join(quran_images_dir, 'res', 'fonts', f'QCF_P{page_num:03d}.TTF')
    if not os.path.exists(font_path): return None
    font_adv = get_font_advances(font_path)

    # Load DB glyphs
    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute('''
        SELECT gpl.line_number, gpl.position,
               g.glyph_code, g.glyph_type_id,
               ga.sura_number, ga.ayah_number, ga.position as word_pos
        FROM glyph_page_line gpl
        JOIN glyph g ON g.glyph_id = gpl.glyph_id
        LEFT JOIN glyph_ayah ga ON ga.glyph_id = gpl.glyph_id
        WHERE gpl.page_number = ? AND gpl.line_type = 'ayah'
        ORDER BY gpl.line_number, gpl.position
    ''', (page_num,))

    db_lines = {}
    for r in c.fetchall():
        ln = r[0]
        if ln not in db_lines: db_lines[ln] = []
        db_lines[ln].append({
            'pos': r[1], 'code': r[2], 'tid': r[3],
            'sura': r[4], 'ayah': r[5], 'word_pos': r[6]
        })
    conn.close()
    if not db_lines: return None

    total_db_lines = len(db_lines)

    # Layout
    if total_db_lines <= 8:
        default_layout = DEFAULT_LINES_8[:total_db_lines]
        snap_range = int(SNAP_RANGE * 1.8)
    else:
        default_layout = DEFAULT_LINES_15[:total_db_lines]
        snap_range = SNAP_RANGE

    detected = detect_line_bands(gray, total_db_lines)
    if detected:
        layout = []
        for i, (y1, y2) in enumerate(detected):
            gy = detected[i-1][1] if i > 0 else 0
            gh = y1 - gy
            layout.append((y1, y2-y1, gy, gh))
    else:
        layout = default_layout

    # ═══════════════════════════════════════════════════════════════
    # Load mushaf JSON — THIS is the source of truth for locations
    # ═══════════════════════════════════════════════════════════════
    mushaf_lines = []  # list of lists of {location, word}
    mushaf_path = os.path.join(mushaf_dir, f'page-{page_num:03d}.json')
    if os.path.exists(mushaf_path):
        with open(mushaf_path, 'r', encoding='utf-8') as f:
            mdata = json.load(f)
        for line in mdata.get('lines', []):
            if line.get('type') == 'text':
                words = []
                for w in line.get('words', []):
                    loc = w.get('location', '')
                    if loc:
                        words.append({'location': loc, 'word': w.get('word', '')})
                mushaf_lines.append(words)

    # Process each line
    coords = {}
    line_nums = sorted(db_lines.keys())

    for li, line_num in enumerate(line_nums):
        if li >= len(layout): break

        ty, th, gy, gh = layout[li]
        all_glyphs = db_lines[line_num]
        y1, y2 = ty, min(ty + th, page_h)

        ink_l, ink_r = find_ink_extent(gray, y1, y2)
        ink_top, ink_bot = find_ink_rows(gray, y1, y2)

        # Compute cuts for ALL glyphs (words + markers + waqf)
        cuts = compute_all_cuts(all_glyphs, font_adv, gray, y1, y2, ink_l, ink_r, snap_range)
        if cuts is None: continue

        # ═══════════════════════════════════════════════════════════
        # Extract word boxes (tid=1 only) in ORDER
        # ═══════════════════════════════════════════════════════════
        word_boxes = []
        for i, g in enumerate(all_glyphs):
            if g.get('tid') == 1:
                x_left = cuts[i + 1]
                x_right = cuts[i]
                w = x_right - x_left
                if w >= 5:
                    word_boxes.append({'x': x_left, 'w': w})

        # ═══════════════════════════════════════════════════════════
        # Match with mushaf words BY ORDER (not by DB location!)
        # ═══════════════════════════════════════════════════════════
        mushaf_words = mushaf_lines[li] if li < len(mushaf_lines) else []

        actual_h = min(ink_bot - ink_top, 68)

        if len(word_boxes) == len(mushaf_words):
            # Perfect match — assign by order
            for wi, mw in enumerate(mushaf_words):
                box = word_boxes[wi]
                coords[mw['location']] = {
                    'h': {'x': box['x'], 'y': ink_top, 'w': box['w'], 'h': actual_h},
                    'p': {'x': box['x'], 'y': gy + max(0, (gh - 23)//2), 'w': box['w'], 'h': min(gh, 23)},
                    'o': {'x': 0, 'y': ink_top, 'w': 39, 'h': actual_h},
                }
        elif len(word_boxes) > 0 and len(mushaf_words) > 0:
            # Mismatch — try best effort: assign min(boxes, words) by order
            count = min(len(word_boxes), len(mushaf_words))
            for wi in range(count):
                mw = mushaf_words[wi]
                box = word_boxes[wi]
                coords[mw['location']] = {
                    'h': {'x': box['x'], 'y': ink_top, 'w': box['w'], 'h': actual_h},
                    'p': {'x': box['x'], 'y': gy + max(0, (gh - 23)//2), 'w': box['w'], 'h': min(gh, 23)},
                    'o': {'x': 0, 'y': ink_top, 'w': 39, 'h': actual_h},
                }
            if len(word_boxes) != len(mushaf_words):
                print(f"    ⚠ Line {line_num}: {len(word_boxes)} boxes vs {len(mushaf_words)} mushaf words")

    # Save
    os.makedirs(output_dir, exist_ok=True)
    result = {'page': page_num, 'coords': coords}
    with open(os.path.join(output_dir, f'page-{page_num:03d}.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if debug:
        gen_debug(img_path, coords, output_dir, page_num)

    return result


def gen_debug(img_path, coords, output_dir, page_num):
    img = Image.open(img_path).convert('RGBA')
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    COLORS = [(233,69,96),(59,130,246),(234,179,8),(34,197,94),(168,85,247),(249,115,22),(6,182,212),(236,72,153)]
    for i, (loc, v) in enumerate(sorted(coords.items())):
        h = v['h']; c = COLORS[i % len(COLORS)]
        draw.rectangle([h['x'], h['y'], h['x']+h['w'], h['y']+h['h']], fill=(*c, 35), outline=(*c, 200), width=1)
        # Word number label
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except: font = ImageFont.load_default()
        draw.text((h['x']+h['w']//2, h['y']-2), loc.split(':')[-1], fill=(*c, 220), font=font, anchor='mb')
    out = Image.alpha_composite(img, ov)
    out.save(os.path.join(output_dir, f'debug-page-{page_num:03d}.png'))


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Quran Word Coordinates v3')
    parser.add_argument('-b', '--base-dir', default='.')
    parser.add_argument('-q', '--quran-images-dir', default='quran.com-images')
    parser.add_argument('--db', default='quran_glyphs.db')
    parser.add_argument('-o', '--output-dir', default='output')
    parser.add_argument('-m', '--mushaf-dir', default=None)
    parser.add_argument('--page', type=int, action='append')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--build-db', action='store_true')
    args = parser.parse_args()

    mushaf_dir = args.mushaf_dir or os.path.join(args.base_dir, 'mushaf')

    if args.build_db:
        print("Building SQLite database...")
        if not build_sqlite_db(args.quran_images_dir, args.db): sys.exit(1)
        print("Done!")
        if not args.page and not args.all: return

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found. Run with --build-db first."); sys.exit(1)

    if args.page: pages = args.page
    elif args.all: pages = list(range(1, 605))
    else:
        pages = []
        img_dir = os.path.join(args.base_dir, 'images')
        if os.path.isdir(img_dir):
            for f in sorted(os.listdir(img_dir)):
                if f.startswith('page-') and f.split('.')[-1] in ('png','jpg','jpeg','webp'):
                    try: pages.append(int(f.replace('page-','').split('.')[0]))
                    except: pass

    if not pages: print("No pages. Use --page N or --all"); return

    print(f"Processing {len(pages)} pages...")
    ok = fail = skip = 0
    for i, pn in enumerate(pages):
        print(f"  [{i+1}/{len(pages)}] Page {pn}...", end='', flush=True)
        try:
            r = process_page(pn, args.base_dir, args.quran_images_dir, args.db, args.output_dir, mushaf_dir, args.debug)
            if r: wc = len(r.get('coords', {})); print(f" ✓ {wc} words"); ok += 1
            else: print(" skip"); skip += 1
        except Exception as e:
            print(f" ✗ {e}"); import traceback; traceback.print_exc(); fail += 1

    print(f"\nDone: {ok} ok, {skip} skip, {fail} fail → {args.output_dir}/")


if __name__ == '__main__':
    main()
