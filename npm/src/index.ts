import rawData from "../../data/coords.json";

/**
 * Bounding box in pixels relative to page image (900x1437).
 */
export interface Box {
  /** Left edge X coordinate */
  x: number;
  /** Top edge Y coordinate */
  y: number;
  /** Width in pixels */
  w: number;
  /** Height in pixels */
  h: number;
}

/**
 * Coordinate set for a word.
 * - h: highlight box (word bounding rectangle)
 * - p: padding box (above-line space for tooltips)
 * - o: origin box (left margin indicator area)
 */
export interface WordCoords {
  h: Box;
  p?: Box;
  o?: Box;
}

/**
 * All word coordinates on a page.
 * Keys are "sura:ayah:word" strings.
 */
export type PageCoords = Record<string, WordCoords>;

/**
 * Parsed word location.
 */
export interface WordLocation {
  sura: number;
  ayah: number;
  word: number;
}

// Internal cache
const cache: Map<number, PageCoords> = new Map();
const allData = rawData as unknown as Record<string, PageCoords>;

function loadAllData(): Record<string, PageCoords> {
  return allData;
}

/**
 * Parse a location string "sura:ayah:word" into its components.
 */
export function parseLocation(location: string): WordLocation {
  const parts = location.split(":");
  if (parts.length !== 3) throw new Error(`Invalid location: ${location}`);
  return {
    sura: parseInt(parts[0], 10),
    ayah: parseInt(parts[1], 10),
    word: parseInt(parts[2], 10),
  };
}

/**
 * Format a location from components to "sura:ayah:word" string.
 */
export function formatLocation(
  sura: number,
  ayah: number,
  word: number
): string {
  return `${sura}:${ayah}:${word}`;
}

/**
 * Get all word coordinates for a page (1-604).
 *
 * @example
 * ```ts
 * const coords = getPage(7);
 * // => { "2:38:1": { h: { x: 818, y: 23, w: 61, h: 68 }, ... }, ... }
 * ```
 */
export function getPage(page: number): PageCoords {
  if (page < 1 || page > 604) {
    throw new RangeError(`Page must be 1-604, got ${page}`);
  }
  if (cache.has(page)) return cache.get(page)!;
  const data = loadAllData();
  const coords = data[String(page)] || {};
  cache.set(page, coords);
  return coords;
}

/**
 * Get coordinates for a specific word.
 *
 * @example
 * ```ts
 * const box = getWord(2, 255, 1); // Al-Baqarah, Ayat Al-Kursi, word 1
 * console.log(box?.h); // { x: ..., y: ..., w: ..., h: ... }
 * ```
 */
export function getWord(
  sura: number,
  ayah: number,
  word: number,
  page?: number
): WordCoords | null {
  const key = formatLocation(sura, ayah, word);
  if (page !== undefined) {
    const coords = getPage(page);
    return coords[key] || null;
  }
  // Search all pages
  const data = loadAllData();
  for (const [, pageCoords] of Object.entries(data)) {
    if (key in pageCoords) return pageCoords[key];
  }
  return null;
}

/**
 * Find which word is at pixel position (x, y) on a page.
 *
 * @returns Location string "sura:ayah:word" or null
 *
 * @example
 * ```ts
 * const loc = findWordAt(7, 820, 40);
 * // => "2:38:1"
 * ```
 */
export function findWordAt(
  page: number,
  x: number,
  y: number
): string | null {
  const coords = getPage(page);
  for (const [location, coord] of Object.entries(coords)) {
    const box = coord.h;
    if (x >= box.x && x <= box.x + box.w && y >= box.y && y <= box.y + box.h) {
      return location;
    }
  }
  return null;
}

/**
 * Get coordinates for all words in an ayah.
 *
 * @example
 * ```ts
 * const words = getAyah(2, 255);
 * // => { "2:255:1": {...}, "2:255:2": {...}, ... }
 * ```
 */
export function getAyah(
  sura: number,
  ayah: number,
  page?: number
): PageCoords {
  const prefix = `${sura}:${ayah}:`;
  if (page !== undefined) {
    const coords = getPage(page);
    const result: PageCoords = {};
    for (const [k, v] of Object.entries(coords)) {
      if (k.startsWith(prefix)) result[k] = v;
    }
    return result;
  }
  // Search all pages
  const data = loadAllData();
  const result: PageCoords = {};
  for (const [, pageCoords] of Object.entries(data)) {
    for (const [k, v] of Object.entries(pageCoords)) {
      if (k.startsWith(prefix)) result[k] = v;
    }
  }
  return result;
}

/**
 * Get the number of words on a page.
 */
export function wordCount(page: number): number {
  return Object.keys(getPage(page)).length;
}

/**
 * Get all word location keys on a page, sorted.
 */
export function allLocations(page: number): string[] {
  return Object.keys(getPage(page)).sort();
}

/**
 * Scale a coordinate box to a different image size.
 *
 * @example
 * ```ts
 * const scaled = scaleBox(box, 1800, 2874); // 2x size
 * ```
 */
export function scaleBox(
  box: Box,
  targetWidth: number,
  targetHeight: number,
  sourceWidth: number = 900,
  sourceHeight: number = 1437
): Box {
  const sx = targetWidth / sourceWidth;
  const sy = targetHeight / sourceHeight;
  return {
    x: Math.round(box.x * sx),
    y: Math.round(box.y * sy),
    w: Math.round(box.w * sx),
    h: Math.round(box.h * sy),
  };
}

/**
 * Clear the internal page cache to free memory.
 */
export function clearCache(): void {
  cache.clear();
}
