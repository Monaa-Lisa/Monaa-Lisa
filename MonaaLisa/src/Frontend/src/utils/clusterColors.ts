/**
 * Curated palettes per arXiv category. Extend this object as new categories go live.
 * Each palette intentionally mixes warm/cool hues to keep dense clusters visually separable.
 */
const categoryPalettes: Record<string, string[]> = {
  'cs.CG': ['#ff7a18', '#ffd166', '#4cc9f0', '#4361ee', '#7209b7', '#f72585'],
  'math.DG': ['#2ec4b6', '#ff9f1c', '#e71d36', '#9b5de5', '#00bbf9', '#3a86ff'],
};

const defaultPalette = ['#00a6fb', '#f87575', '#ffc857', '#41ead4', '#b388eb', '#6eeb83'];
const DEFAULT_CATEGORY_KEY = '__default__';

const paletteCache = new Map<string, string[]>();

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

function getPalette(category?: string | null): string[] {
  const key = category ?? DEFAULT_CATEGORY_KEY;
  if (!paletteCache.has(key)) {
    paletteCache.set(key, categoryPalettes[category ?? ''] ?? defaultPalette);
  }
  return paletteCache.get(key)!;
}

export function getClusterColor(category?: string | null, cluster?: string | null): string {
  const palette = getPalette(category);
  const label = (cluster ?? category ?? 'unclustered').toLowerCase();
  const idx = Math.abs(hashString(label)) % palette.length;
  return palette[idx];
}

export function getCategoryPalette(category?: string | null): string[] {
  return [...getPalette(category)];
}