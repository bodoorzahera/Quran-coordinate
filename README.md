# Quran Word Coordinates

Pixel-accurate word coordinates for every word in the Quran (Madani mushaf). Maps each of the **77,320 words** across **604 pages** to its exact bounding box on the page image.

## Install

### Python (full system)
```bash
pip install qurancoor              # Data API only
pip install qurancoor[serve]       # + web viewer/editor
pip install qurancoor[generate]    # + coordinate generation tools
pip install qurancoor[all]         # everything
```

### JavaScript / TypeScript
```bash
npm install quran-word-coords
```

## Quick Start

### Python API

```python
from qurancoor import get_page, get_word, find_word_at, get_ayah, scale_coords

# Get all word coordinates on page 7
coords = get_page(7)
# => {"2:38:1": {"h": {"x": 818, "y": 23, "w": 61, "h": 68}, ...}, ...}

# Get a specific word: Sura 2, Ayah 255 (Ayat Al-Kursi), Word 1
word = get_word(2, 255, 1)
print(word["h"])  # {"x": ..., "y": ..., "w": ..., "h": ...}

# Find which word is at pixel (820, 40) on page 7
location = find_word_at(7, 820, 40)
# => "2:38:1"

# Get all words in Al-Fatiha, Ayah 1
words = get_ayah(1, 1)

# Scale to a different display size
scaled = scale_coords(word["h"], target_width=1800, target_height=2874)
```

### CLI Commands

```bash
# Launch the web viewer (requires mushaf page images)
qurancoor serve --images-dir ./images --port 8003

# Generate coordinates from source images
qurancoor generate --build-db -q quran.com-images
qurancoor generate -b . -q quran.com-images -o output --all

# Build word frequency database
qurancoor build-freq --mushaf-dir ./mushaf --db word_freq.db
```

### JavaScript / TypeScript

```typescript
import { getPage, getWord, findWordAt, getAyah, scaleBox } from 'quran-word-coords';

const coords = getPage(7);
const word = getWord(2, 255, 1);
const location = findWordAt(7, 820, 40); // => "2:38:1"
const ayah = getAyah(1, 1);
const scaled = scaleBox(word!.h, 1800, 2874);
```

## API Reference

| Function | Python | npm | Description |
|----------|--------|-----|-------------|
| Get page coords | `get_page(7)` | `getPage(7)` | All word boxes on a page (1-604) |
| Get word coords | `get_word(2, 255, 1)` | `getWord(2, 255, 1)` | Specific word by sura:ayah:word |
| Hit-test | `find_word_at(7, 820, 40)` | `findWordAt(7, 820, 40)` | Which word is at (x,y)? |
| Get ayah words | `get_ayah(2, 255)` | `getAyah(2, 255)` | All words in an ayah |
| Scale coords | `scale_coords(box, w, h)` | `scaleBox(box, w, h)` | Adapt to different image sizes |
| Word count | `word_count(7)` | `wordCount(7)` | Number of words on a page |
| All locations | `all_locations(7)` | `allLocations(7)` | Sorted word keys on a page |
| Free memory | `clear_cache()` | `clearCache()` | Release cached data |

## Coordinate Format

Each word has up to 3 coordinate boxes, all in **pixels** relative to the page image (900 x 1437):

```json
{
  "2:38:1": {
    "h": { "x": 818, "y": 23, "w": 61, "h": 68 },
    "p": { "x": 818, "y": 0,  "w": 61, "h": 23 },
    "o": { "x": 0,   "y": 23, "w": 39, "h": 68 }
  }
}
```

| Box | Name | Purpose |
|-----|------|---------|
| `h` | Highlight | Tight bounding box around the word ink |
| `p` | Padding | Space above the text line (for tooltips/popovers) |
| `o` | Origin | Left margin area (for line markers) |

Key format: `"sura:ayah:word"` — e.g., `"2:38:1"` = Sura 2 (Al-Baqarah), Ayah 38, Word 1.

## Practical Use Cases

1. **Word-by-word highlighting** during audio recitation — map audio timestamps to word coordinates
2. **Tap-to-show tafsir** — hit-test user taps against word boxes on mushaf images
3. **Visual search results** — highlight found words directly on mushaf pages
4. **Tajweed overlay** — color-code words with tajweed rules at exact positions
5. **Qira'at (variant readings)** — mark words with reading differences
6. **Word frequency tools** — tap a word to see all its occurrences across the Quran

---

## How Word Positioning Works

The system achieves pixel-accurate coordinates through a 5-step pipeline:

### Step 1: Font Metric Analysis
Each page uses a dedicated QCF font (`QCF_P001.TTF` ... `QCF_P604.TTF`) where every word is a single glyph. The system extracts the **advance width** of each glyph from the font's `hmtx` table to determine proportional spacing.

### Step 2: Image Line Detection
Horizontal projection analysis on the grayscale page image identifies text line bands — consecutive rows with ink above a threshold. Standard pages have 15 lines; sura opening pages have 8.

### Step 3: Glyph Database Lookup
From `quran_glyphs.db` (built from [quran.com-images](https://github.com/quran/quran.com-images)), the system retrieves ALL glyphs on each line — words, ayah markers, and waqf marks. Non-word elements occupy physical space and must be accounted for.

### Step 4: Proportional Cutting with Gap Snapping

The core algorithm:

1. **Proportional cuts** from font advance widths give expected boundary positions
2. **Gap detection** scans actual image pixels for vertical whitespace columns
3. **Snap to gaps** aligns each cut to the nearest real gap using a scoring function:
   ```
   score = gap_width * 2.0 - distance_from_expected * 0.5
   ```
4. **Minimum width enforcement** prevents collapsed boxes (< 25% expected width)

### Step 5: Mushaf JSON Alignment

The quran.com-images database numbers waqf marks as word positions, but the mushaf JSON skips them — causing position misalignment. The system matches word boxes to mushaf words by **sequential order within each line**, not by position numbers, ensuring every word maps correctly.

---

## Repository Structure

```
qurancoor/
  pyproject.toml              # Python package config
  src/qurancoor/
    __init__.py               # Data API (get_page, get_word, etc.)
    cli.py                    # CLI entry point (qurancoor command)
    server.py                 # Web viewer/editor (FastAPI)
    generate.py               # Coordinate extraction pipeline
    build_freq.py             # Word frequency database builder
    data/                     # 604 coordinate JSON files (bundled)
  npm/                        # npm package
    package.json
    src/index.ts
    data/coords.json
  data/
    coords/                   # Alternative coordinate data
    pages/farsh/              # Qira'at variant readings
  quran.com-images/           # Submodule: fonts, SQL data
```

## Building from Source

Only needed if regenerating coordinates from mushaf images.

```bash
pip install qurancoor[all]

# Build glyph database
qurancoor generate --build-db -q quran.com-images

# Generate all page coordinates
qurancoor generate -b . -q quran.com-images -o output --all

# Build word frequency database
qurancoor build-freq --mushaf-dir ./mushaf --db word_freq.db

# Launch viewer
qurancoor serve --images-dir ./images --port 8003
```

## License

MIT. The mushaf images and quran.com-images data have their own licenses — see [quran.com-images](https://github.com/quran/quran.com-images).
