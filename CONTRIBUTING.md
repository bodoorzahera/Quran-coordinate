# Contributing to Quran Word Coordinates

شكرًا لاهتمامك بالمساهمة! / Thank you for your interest in contributing!

This project is open source under the [MIT License](LICENSE). Contributions of all
kinds are welcome — code, documentation, data corrections, and ideas.

## Development setup

```bash
git clone https://github.com/bodoorzahera/Quran-coordinate.git
cd Quran-coordinate

# install the package in editable mode with all extras
pip install -e ".[all]"

# run the web viewer locally
qurancoor serve --images-dir ./images --port 8003
# open http://localhost:8003
```

The coordinate data and both SQLite databases (`quran_glyphs.db`, `word_freq.db`)
are committed to the repo, so the system runs immediately — **no build step is
required just to run it**.

## Project layout

| Path | Purpose |
|------|---------|
| `src/qurancoor/server.py` | FastAPI server — serves the API, the embedded UI, and page images |
| `src/qurancoor/__init__.py` | Python data API (`get_page`, `get_word`, `find_word_at`, …) |
| `src/qurancoor/generate.py` | Coordinate extraction pipeline (regenerate from source images) |
| `src/qurancoor/build_freq.py` | Builds `word_freq.db` from the mushaf JSON |
| `npm/` | JavaScript/TypeScript package (`quran-word-coords`) |
| `images/`, `mushaf/` | Page images and mushaf text/locations |
| `deploy.html`, `Features.html` | Deployment guide & feature/promo page |

See [`AI_AGENT_GUIDE.md`](AI_AGENT_GUIDE.md) for a deep dive into the architecture
and the coordinate-generation algorithm.

## Regenerating data (only if needed)

```bash
# rebuild the glyph database (needs the quran.com-images submodule)
qurancoor generate --build-db -q quran.com-images

# regenerate all page coordinates
qurancoor generate -b . -q quran.com-images -o output --all

# rebuild the word-frequency database
qurancoor build-freq --mushaf-dir ./mushaf --db word_freq.db
```

## Pull request guidelines

1. **Branch** from `master` (don't commit directly to `master`).
2. Keep changes focused — one logical change per PR.
3. Match the existing code style (the codebase favours compact, dependency-light code).
4. If you change the Python API, mirror it in the JS package (`npm/src/index.ts`) where applicable.
5. Update `README.md` / docs when behaviour or commands change.
6. Describe **what** and **why** in the PR description.

## Reporting issues

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For data/coordinate errors,
please include the page number and `sura:ayah:word` location.

## Code of Conduct

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
