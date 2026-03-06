# AI Agent Integration Guide — Quran Word Coordinates

This document is designed for AI agents, LLMs, and automated systems that need to understand and use this system's data programmatically.

## System Purpose

This system produces **pixel-accurate bounding boxes** for every word in the Quran, mapped to mushaf page images. The data links the textual address of each word (`sura:ayah:word`) to its exact visual position on the printed page.

## Data Access Quick Reference

### Primary Output: `output/page-NNN.json`

604 JSON files (page-001.json to page-604.json). Each contains:

```json
{
  "page": 7,
  "coords": {
    "2:38:1": {
      "h": { "x": 818, "y": 23, "w": 61, "h": 68 },
      "p": { "x": 818, "y": 0,  "w": 61, "h": 23 },
      "o": { "x": 0,   "y": 23, "w": 39, "h": 68 }
    },
    "2:38:2": { ... },
    "2:38:3": { ... }
  }
}
```

### Key Format: `"sura:ayah:word"`

- `"1:1:1"` = Al-Fatiha, Ayah 1, Word 1 (Bismillah)
- `"2:255:1"` = Al-Baqarah, Ayat Al-Kursi, Word 1
- `"114:6:3"` = An-Nas, last ayah, word 3

Words are numbered starting from 1, right-to-left as they appear in the mushaf.

### Coordinate Spaces

All values are **integer pixels** relative to the page image origin (top-left = 0,0). Standard image size: **900 x 1437 pixels**.

| Property | Purpose | Typical Use |
|----------|---------|-------------|
| `h` (highlight) | Tight bounding box around the word ink | Word highlighting, hit-testing, selection |
| `p` (padding) | Space above the text line | Tooltip/popover positioning |
| `o` (origin) | Left margin column | Line number indicators, ayah markers |

### Coordinate Properties

```
h.x  = left edge of word box (pixels from left of image)
h.y  = top edge of word box (pixels from top of image)
h.w  = width of word box in pixels
h.h  = height of word box in pixels
```

To get the right edge: `h.x + h.w`
To get the bottom edge: `h.y + h.h`
To get the center: `(h.x + h.w/2, h.y + h.h/2)`

## API Endpoints (when server.py is running)

| Endpoint | Method | Returns |
|----------|--------|---------|
| `GET /api/pages` | GET | `{"pages": [1, 2, 3, ..., 604]}` |
| `GET /api/page/{n}` | GET | Page coords + mushaf word text |
| `GET /api/image/{n}` | GET | Page image file (PNG) |
| `POST /api/page/{n}/save` | POST | Save edited coordinates |
| `GET /api/word-freq/page/{n}` | GET | Word frequencies for all words on page |
| `GET /api/word-freq/variants/{bare_id}` | GET | All tashkeel variants of a bare word |
| `GET /api/word-freq/occurrences/{voc_id}` | GET | All locations of a specific vocalized word |

### Example API Responses

**GET /api/page/7:**
```json
{
  "page": 7,
  "coords": {
    "2:38:1": { "h": {"x":818,"y":23,"w":61,"h":68}, "p": {...}, "o": {...} },
    ...
  },
  "mushaf": {
    "2:38:1": { "word": "فَإِمَّا", "line": 1 },
    "2:38:2": { "word": "يَأْتِيَنَّكُم", "line": 1 },
    ...
  }
}
```

**GET /api/word-freq/page/7:**
```json
{
  "freqs": {
    "2:38:1": { "bare": "فاما", "bare_count": 12, "bare_id": 45 },
    ...
  }
}
```

**GET /api/word-freq/variants/45:**
```json
{
  "bare": "فاما",
  "bare_id": 45,
  "variants": [
    { "voc_id": 101, "vocalized": "فَإِمَّا", "count": 8 },
    { "voc_id": 102, "vocalized": "فَأَمَّا", "count": 4 }
  ]
}
```

**GET /api/word-freq/occurrences/101:**
```json
{
  "vocalized": "فَإِمَّا",
  "voc_id": 101,
  "occurrences": [
    { "page": 7, "sura": 2, "ayah": 38, "word_pos": 1, "location": "2:38:1", "sura_name": "البقرة" },
    ...
  ]
}
```

## Database Schemas

### `quran_glyphs.db` (Glyph metadata from quran.com-images)

```sql
-- Every glyph (words, markers, waqf signs)
glyph(glyph_id, font_file, glyph_code, page_number, glyph_type_id, glyph_type_meta, description)
-- glyph_type_id: 1=word, 2=end-of-ayah marker, 3=sura header, 4=waqf mark

-- Line placement
glyph_page_line(glyph_page_line_id, glyph_id, page_number, line_number, position, line_type)
-- line_type: 'ayah' for text lines

-- Quranic address
glyph_ayah(glyph_ayah_id, glyph_id, sura_number, ayah_number, position)
```

### `word_freq.db` (Word frequency analysis)

```sql
word_bare(bare_id, bare, count)
-- bare = word stripped of all tashkeel, normalized (alef variants → ا, teh marbuta → ه, alef maqsura → ي)

word_vocalized(voc_id, bare_id, vocalized, count)
-- vocalized = word with full tashkeel as it appears in the mushaf

word_occurrence(occ_id, voc_id, page, sura, ayah, word_pos, location)
-- location = "sura:ayah:word_pos" string

sura_names(sura, name)
-- Arabic sura names, 1-114
```

## Mushaf JSON Format (`mushaf/page-NNN.json`)

```json
{
  "lines": [
    {
      "type": "text",
      "line": 1,
      "words": [
        { "location": "2:38:1", "word": "فَإِمَّا" },
        { "location": "2:38:2", "word": "يَأْتِيَنَّكُم" }
      ]
    }
  ]
}
```

## How Word Position Accuracy Is Achieved

The system solves a non-trivial problem: mapping logical word positions to pixel coordinates on a rendered image. Here is why naive approaches fail and what this system does instead:

### Problem 1: Non-Uniform Spacing
Arabic text has variable spacing. Words with tall letters (لا, ك) take different space than short ones (من). Simple equal-division of the line would misalign most words.

**Solution**: Read the actual font advance widths from QCF TTF files. Each page has its own font, so every glyph's proportional width is known exactly.

### Problem 2: Invisible Elements Occupy Space
Ayah end markers (circled numbers) and waqf/pause signs take physical space on the line but are not "words." If you only count words, the remaining words shift out of position.

**Solution**: Compute proportional cuts for ALL glyphs (words + markers + waqf), giving each element its space. Then extract only word-type boxes.

### Problem 3: Database vs. Mushaf Position Mismatch
The quran.com-images database assigns position numbers to waqf marks (e.g., position 5 = a waqf sign), but the mushaf JSON skips them (position 5 = the next actual word). Matching by position number causes every subsequent word to be offset.

**Solution**: Match word boxes to mushaf words by **sequential order within each line**, not by position numbers. The system:
1. Gets all glyphs from the database (words + markers + waqf) in line order
2. Computes pixel boundaries for all of them
3. Filters to only word-type (type=1) boundaries, in order
4. Pairs them 1:1 with mushaf JSON words, in order

### Problem 4: Font Metrics vs. Rendered Pixels
Font advance widths give proportional positions, but actual rendering may differ due to kerning, ligatures, and rasterization. Proportional cuts alone can split through the middle of a letter.

**Solution**: The "gap snapping" algorithm. After computing proportional cut positions, scan the actual image pixels for vertical gaps (columns with zero ink). Snap each cut to the nearest real gap, scoring candidates by:
```
score = gap_width * weight - distance_from_expected * 0.5
```
This ensures cuts always fall in actual whitespace between words, never through a letter.

## Integration Patterns

### Pattern 1: Static File Consumption
Read `output/page-NNN.json` files directly. No server needed.
```python
import json
with open("output/page-007.json") as f:
    data = json.load(f)
for location, coord in data["coords"].items():
    box = coord["h"]
    print(f"{location}: x={box['x']}, y={box['y']}, w={box['w']}, h={box['h']}")
```

### Pattern 2: Hit-Testing (Which Word Was Clicked?)
```python
def find_word_at(coords, click_x, click_y):
    for location, coord in coords.items():
        box = coord["h"]
        if (box["x"] <= click_x <= box["x"] + box["w"] and
            box["y"] <= click_y <= box["y"] + box["h"]):
            return location
    return None
```

### Pattern 3: Scale Coordinates to Any Display Size
The coordinates are for 900x1437 images. To scale:
```python
def scale_box(box, display_width, display_height):
    sx = display_width / 900
    sy = display_height / 1437
    return {
        "x": int(box["x"] * sx),
        "y": int(box["y"] * sy),
        "w": int(box["w"] * sx),
        "h": int(box["h"] * sy),
    }
```

### Pattern 4: Find All Coordinates for an Ayah
```python
def get_ayah_words(coords, sura, ayah):
    prefix = f"{sura}:{ayah}:"
    return {k: v for k, v in coords.items() if k.startswith(prefix)}
```

### Pattern 5: Cross-Page Word Search via API
```python
import requests
# 1. Get bare word ID from any page
freqs = requests.get("http://localhost:8003/api/word-freq/page/7").json()["freqs"]
bare_id = freqs["2:38:1"]["bare_id"]

# 2. Get all tashkeel variants
variants = requests.get(f"http://localhost:8003/api/word-freq/variants/{bare_id}").json()

# 3. Get all occurrences of a variant
for v in variants["variants"]:
    occs = requests.get(f"http://localhost:8003/api/word-freq/occurrences/{v['voc_id']}").json()
    for o in occs["occurrences"]:
        print(f"Page {o['page']}: {o['sura_name']} {o['ayah']}:{o['word_pos']}")
```

## File Dependencies

```
generate_coords.py
  READS:  images/page-NNN.png, quran.com-images/res/fonts/QCF_PNNN.TTF, quran_glyphs.db, mushaf/page-NNN.json
  WRITES: output/page-NNN.json

build_word_freq.py
  READS:  mushaf/page-NNN.json
  WRITES: word_freq.db

server.py
  READS:  output/page-NNN.json, images/page-NNN.png, mushaf/page-NNN.json, word_freq.db
  SERVES: Web UI + REST API
```

## Rebuilding Everything from Scratch

```bash
# 1. Clone quran.com-images (if not present)
git submodule update --init

# 2. Build glyph database
python3 generate_coords.py --build-db -q quran.com-images

# 3. Generate all coordinates
python3 generate_coords.py -b . -q quran.com-images -o output --all

# 4. Build word frequency database
python3 build_word_freq.py --mushaf-dir ./mushaf --db word_freq.db

# 5. Launch viewer
python3 server.py --port 8003
```
