"""
qurancoor - Pixel-accurate word coordinates for every word in the Quran.

Usage:
    from qurancoor import get_page, get_word, get_ayah, find_word_at

    # Get all word coordinates on page 7
    coords = get_page(7)
    # => {"2:38:1": {"h": {"x": 818, "y": 23, "w": 61, "h": 68}, ...}, ...}

    # Get coordinates for a specific word
    box = get_word(2, 255, 1)  # Al-Baqarah, Ayat Al-Kursi, word 1
    # => {"h": {"x": ..., "y": ..., "w": ..., "h": ...}, "p": {...}, "o": {...}}

    # Find which word is at a pixel position
    location = find_word_at(7, 820, 40)
    # => "2:38:1"

    # Get all words in an ayah
    words = get_ayah(2, 255)
    # => {"2:255:1": {...}, "2:255:2": {...}, ...}
"""

__version__ = "1.0.0"

import json
import os
from typing import Dict, List, Optional, Tuple

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_cache: Dict[int, dict] = {}

# Page ranges for each sura (sura -> (start_page, end_page))
# Precomputed from coordinate data
_sura_pages: Optional[Dict[int, Tuple[int, int]]] = None


def _load_page(page: int) -> dict:
    if page in _cache:
        return _cache[page]
    path = os.path.join(_DATA_DIR, f"page-{page:03d}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    coords = data.get("coords", {})
    _cache[page] = coords
    return coords


def get_page(page: int) -> dict:
    """Get all word coordinates for a page (1-604).

    Returns:
        Dict mapping "sura:ayah:word" to coordinate sets.
        Each coordinate set has:
        - "h": highlight box {"x", "y", "w", "h"} (word bounding rectangle)
        - "p": padding box (above-line space for tooltips)
        - "o": origin box (left margin area)
    """
    if not 1 <= page <= 604:
        raise ValueError(f"Page must be 1-604, got {page}")
    return _load_page(page)


def get_word(sura: int, ayah: int, word: int, page: Optional[int] = None) -> Optional[dict]:
    """Get coordinates for a specific word.

    Args:
        sura: Sura number (1-114)
        ayah: Ayah number
        word: Word position (1-based)
        page: Page number (optional, searches if not provided)

    Returns:
        Coordinate set {"h": {...}, "p": {...}, "o": {...}} or None
    """
    key = f"{sura}:{ayah}:{word}"
    if page is not None:
        coords = _load_page(page)
        return coords.get(key)
    # Search all pages
    for p in range(1, 605):
        coords = _load_page(p)
        if key in coords:
            return coords[key]
    return None


def find_word_at(page: int, x: int, y: int) -> Optional[str]:
    """Find which word is at pixel position (x, y) on a page.

    Args:
        page: Page number (1-604)
        x: X coordinate in pixels (relative to page image)
        y: Y coordinate in pixels (relative to page image)

    Returns:
        Location string "sura:ayah:word" or None
    """
    coords = _load_page(page)
    for location, coord in coords.items():
        box = coord.get("h", coord)
        if (box["x"] <= x <= box["x"] + box["w"] and
                box["y"] <= y <= box["y"] + box["h"]):
            return location
    return None


def get_ayah(sura: int, ayah: int, page: Optional[int] = None) -> dict:
    """Get coordinates for all words in an ayah.

    Args:
        sura: Sura number (1-114)
        ayah: Ayah number
        page: Page number (optional, searches if not provided)

    Returns:
        Dict mapping "sura:ayah:word" to coordinate sets
    """
    prefix = f"{sura}:{ayah}:"
    if page is not None:
        coords = _load_page(page)
        return {k: v for k, v in coords.items() if k.startswith(prefix)}
    # Search all pages
    result = {}
    for p in range(1, 605):
        coords = _load_page(p)
        for k, v in coords.items():
            if k.startswith(prefix):
                result[k] = v
        if result and not any(k.startswith(prefix) for k in coords):
            break  # Past this ayah's pages
    return result


def get_sura_pages(sura: int) -> List[int]:
    """Get all page numbers that contain words from a sura.

    Args:
        sura: Sura number (1-114)

    Returns:
        Sorted list of page numbers
    """
    prefix = f"{sura}:"
    pages = []
    for p in range(1, 605):
        coords = _load_page(p)
        if any(k.startswith(prefix) for k in coords):
            pages.append(p)
    return pages


def word_count(page: int) -> int:
    """Get the number of words on a page."""
    return len(_load_page(page))


def all_locations(page: int) -> List[str]:
    """Get all word location keys on a page, sorted."""
    return sorted(_load_page(page).keys())


def scale_coords(box: dict, target_width: int, target_height: int,
                 source_width: int = 900, source_height: int = 1437) -> dict:
    """Scale a coordinate box to a different image size.

    Args:
        box: Coordinate box {"x", "y", "w", "h"}
        target_width: Target image width in pixels
        target_height: Target image height in pixels
        source_width: Source image width (default 900)
        source_height: Source image height (default 1437)

    Returns:
        Scaled coordinate box {"x", "y", "w", "h"}
    """
    sx = target_width / source_width
    sy = target_height / source_height
    return {
        "x": round(box["x"] * sx),
        "y": round(box["y"] * sy),
        "w": round(box["w"] * sx),
        "h": round(box["h"] * sy),
    }


def clear_cache():
    """Clear the internal page cache to free memory."""
    _cache.clear()
