# Quran Word Coordinates System

A precision system that maps every word in the Quran to its exact pixel coordinates on mushaf page images. The output is a set of JSON files containing bounding boxes for each word, enabling any application to know exactly where every word appears on each page.

## What This System Produces

For each of the 604 pages of the Quran, it generates a JSON file like this:

```json
{
  "page": 7,
  "coords": {
    "2:38:1": {
      "h": { "x": 818, "y": 23, "w": 61, "h": 68 },
      "p": { "x": 818, "y": 0,  "w": 61, "h": 23 },
      "o": { "x": 0,   "y": 23, "w": 39, "h": 68 }
    }
  }
}
```

- **Key** `"2:38:1"` = Sura 2, Ayah 38, Word 1
- **`h`** = Highlight box (the word's bounding rectangle on the page image)
- **`p`** = Padding box (space above the line, useful for popovers/tooltips)
- **`o`** = Origin box (left margin area, useful for line markers)

## How Word Positioning Works

The system achieves pixel-accurate word coordinates through a multi-step pipeline:

### Step 1: Font Metric Analysis
Each page of the Quran uses a dedicated QCF (Quran Complex Font) where every word is a single glyph. The system reads the font file (`QCF_P001.TTF` ... `QCF_P604.TTF`) and extracts the **advance width** of each glyph from the `hmtx` table. These widths tell us the proportional space each word should occupy.

### Step 2: Image Line Detection
The system analyzes the grayscale page image using horizontal projection (summing dark pixels per row). Consecutive rows with ink above a threshold form "bands" — these are the text lines. It expects 15 lines for standard pages or 8 lines for pages with larger text (like Sura openings).

### Step 3: Glyph Database Lookup
From the `quran_glyphs.db` database (built from [quran.com-images](https://github.com/quran/quran.com-images) SQL data), the system gets every glyph on each line — not just words, but also **ayah markers** (circle numbers) and **waqf marks** (pause signs like `ۖ ۗ ۘ`). This is critical because these non-word glyphs occupy physical space on the line.

### Step 4: Proportional Cutting with Gap Snapping

This is the core algorithm:

1. **Proportional cuts**: Using font advance widths, calculate where each glyph boundary *should* fall. For example, if a line has 3 glyphs with widths 600, 400, 200, the cuts are at 50%, 83% from the right edge.

2. **Gap detection**: Scan the actual image pixels in the line band to find all vertical gaps (columns with zero ink). These are the real spaces between words.

3. **Snap to gaps**: Each proportional cut point is snapped to the nearest real image gap within a tolerance range (30px for standard pages, 54px for large-text pages). The snapping uses a scoring function that favors wider gaps and penalizes distance from the expected position:
   ```
   score = gap_width * 2.0 - distance * 0.5
   ```
   For gaps adjacent to markers (ayah numbers, waqf), the width bonus increases to 3.0 and the search range extends by 15px.

4. **Minimum width enforcement**: After snapping, any word box narrower than 25% of its expected width is reset to the proportional position to prevent collapsed boxes.

### Step 5: Mushaf JSON Alignment (The Critical Fix)

The quran.com-images database numbers waqf marks as word positions (e.g., `2:38:5` = a waqf mark), but the mushaf JSON source of truth skips them (so `2:38:5` = the actual next word). This mismatch would shift every word after a waqf mark by one position.

**Solution**: The system computes cut boxes for ALL glyphs (words + markers + waqf) to give every element its proper space, then extracts only the word-type boxes (type=1) in order, and matches them 1:1 with mushaf JSON words by **sequential order**, not by database position numbers.

### Accuracy Result

This approach produces coordinates that precisely frame each word in the mushaf image. The debug mode (`--debug`) generates overlay images where you can visually verify every word box.

## Project Structure

```
qurancoor/
  generate_coords.py    # Word coordinate extraction pipeline
  build_word_freq.py    # Word frequency database builder
  server.py             # Web viewer/editor (FastAPI)
  quran.com-images/     # Submodule: fonts, SQL data (github.com/quran/quran.com-images)
  images/               # Mushaf page images (page-001.png ... page-604.png)
  mushaf/               # Mushaf JSON files with word text and locations
  output/               # Generated coordinate JSON files (page-001.json ... page-604.json)
  data/
    coords/             # Alternative coordinate data
    pages/farsh/        # Qira'at (variant readings) data per page
```

## Quick Start

### Prerequisites

```bash
pip install numpy Pillow fonttools fastapi uvicorn
```

You also need:
- Page images in `images/` (900x1437 PNG files of the Madani mushaf)
- The `quran.com-images` submodule (for fonts and glyph database)
- Mushaf JSON files in `mushaf/` (word text with sura:ayah:word locations)

### 1. Build the Glyph Database

```bash
python3 generate_coords.py --build-db -q quran.com-images
```

This parses the SQL from `quran.com-images/sql/02-database.sql` and creates `quran_glyphs.db`.

### 2. Generate Word Coordinates

```bash
# Single page with debug overlay
python3 generate_coords.py -b . -q quran.com-images -o output --page 7 --debug

# All 604 pages
python3 generate_coords.py -b . -q quran.com-images -o output --all
```

### 3. Build Word Frequency Database (Optional)

```bash
python3 build_word_freq.py --mushaf-dir ./mushaf --db word_freq.db
```

Creates `word_freq.db` with word frequencies, tashkeel variants, and occurrence locations.

### 4. Launch the Viewer/Editor

```bash
python3 server.py --images-dir ./images --json-dir ./output --mushaf-dir ./mushaf --port 8003
```

Open `http://localhost:8003` to browse pages, see word boxes overlaid on the mushaf, edit coordinates, and explore word frequencies.

## Practical Use Cases

### 1. Word-by-Word Highlighting During Recitation
Use the `h` (highlight) coordinates to highlight each word as audio plays. Map audio timestamps to `sura:ayah:word` locations, then draw a colored rectangle at the exact pixel position.

### 2. Tap-to-Show-Tafsir on Mobile
Use hit-testing against the coordinate boxes. When a user taps coordinates (x, y) on the page image, find which word's `h` box contains that point, get the `sura:ayah:word` key, and display the relevant tafsir or translation.

### 3. Word Frequency & Linguistic Analysis
Combine coordinates with `word_freq.db` to build interactive tools: tap a word to see how many times it appears in the Quran, view all tashkeel variants of the same root, and navigate to every occurrence.

### 4. Qira'at (Variant Readings) Overlay
The `data/pages/farsh/` files contain variant readings per word. Use coordinates to overlay reading differences directly on the mushaf image, showing which words have Qira'at variations.

### 5. Accessibility & Search
Map search results (e.g., "find all instances of a word") to exact visual locations. Scroll to the page and zoom to the word with precise coordinates.

### 6. Educational Tajweed Highlighting
Use word boxes to overlay tajweed color-coding rules on specific words or letters, with coordinates ensuring exact alignment with the mushaf image.

## Output JSON Format Reference

Each `output/page-NNN.json`:

| Field | Description |
|-------|-------------|
| `page` | Page number (1-604) |
| `coords` | Object mapping `"sura:ayah:word"` to coordinate sets |
| `coords[key].h` | **Highlight box** — word bounding rectangle `{x, y, w, h}` in pixels |
| `coords[key].p` | **Padding box** — above-line space for tooltips `{x, y, w, h}` |
| `coords[key].o` | **Origin box** — left margin indicator area `{x, y, w, h}` |

All coordinates are in pixels relative to the page image's top-left corner (0, 0).

## Word Frequency Database Schema (`word_freq.db`)

| Table | Description |
|-------|-------------|
| `word_bare` | Unique words without tashkeel, with total count |
| `word_vocalized` | Unique words with tashkeel, linked to bare form |
| `word_occurrence` | Every word instance: page, sura, ayah, position, location |
| `sura_names` | Sura number to Arabic name mapping |

## License

Open source. The mushaf images and quran.com-images data have their own licenses — please refer to [quran.com-images](https://github.com/quran/quran.com-images) for details.
