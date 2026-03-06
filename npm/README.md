# quran-word-coords

Pixel-accurate word coordinates for every word in the Quran (Madani mushaf). Maps each of the 77,320 words to its exact bounding box on 604 page images (900x1437 px).

## Install

```bash
npm install quran-word-coords
```

## Usage

```typescript
import {
  getPage,
  getWord,
  findWordAt,
  getAyah,
  scaleBox,
} from "quran-word-coords";

// Get all word coordinates on page 7
const coords = getPage(7);
// => { "2:38:1": { h: { x: 818, y: 23, w: 61, h: 68 }, p: {...}, o: {...} }, ... }

// Get a specific word: Sura 2, Ayah 255 (Ayat Al-Kursi), Word 1
const word = getWord(2, 255, 1);
console.log(word?.h); // { x: ..., y: ..., w: ..., h: ... }

// Find which word was tapped at pixel (820, 40) on page 7
const location = findWordAt(7, 820, 40);
// => "2:38:1"

// Get all words in an ayah
const ayah = getAyah(1, 1); // Al-Fatiha, Ayah 1

// Scale coordinates to a different display size
const box = word!.h;
const scaled = scaleBox(box, 1800, 2874); // 2x display
```

## API

| Function | Description |
|----------|-------------|
| `getPage(page)` | Get all word coords on a page (1-604) |
| `getWord(sura, ayah, word, page?)` | Get coords for a specific word |
| `findWordAt(page, x, y)` | Hit-test: find word at pixel position |
| `getAyah(sura, ayah, page?)` | Get all words in an ayah |
| `wordCount(page)` | Number of words on a page |
| `allLocations(page)` | All word keys on a page, sorted |
| `scaleBox(box, w, h)` | Scale coords to different image size |
| `parseLocation(loc)` | Parse "2:255:1" into `{sura, ayah, word}` |
| `clearCache()` | Free memory |

## Coordinate Format

Each word has up to 3 coordinate boxes (all in pixels, origin = top-left of 900x1437 image):

| Box | Purpose |
|-----|---------|
| `h` | **Highlight** - tight bounding box around the word |
| `p` | **Padding** - space above the line (for tooltips) |
| `o` | **Origin** - left margin column (for markers) |

## Use Cases

- Word-by-word highlighting during audio recitation
- Tap-to-show tafsir/translation on mushaf images
- Visual search results on mushaf pages
- Tajweed color-coding overlay
- Accessibility features for Quran apps

## License

MIT
