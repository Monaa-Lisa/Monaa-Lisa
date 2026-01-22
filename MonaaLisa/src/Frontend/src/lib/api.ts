import { env as publicEnv } from '$env/dynamic/public';
import type { Paper, PaperCitation, PaperReference, Citation, Reference, Relation, PapersResponse } from '$lib/types/paper';

const API_BASE_URL = publicEnv.PUBLIC_API_BASE_URL || 'http://localhost:3000';

// Simple in-memory cache
const cache = new Map<string, Paper[]>();

export async function fetchPapers(limit = 5000, skip = 0): Promise<Paper[]> {
  const response = await fetch(`${API_BASE_URL}/papers?take=${limit}&skip=${skip}`);

  if (!response.ok) {
    throw new Error(`Backend request failed (${response.status})`);
  }

  console.log("fetchPapers", limit, skip)
  const payload = (await response.json()) as Partial<PapersResponse> | Paper[];
  console.log("payload", payload);
  const rawItems = Array.isArray(payload) ? payload : payload?.items ?? [];

  return rawItems
    .map((item, index, array) => normalizePaper(item as Paper, index, array.length))
    .filter((paper): paper is Paper => Boolean(paper));
}

export async function fetchCitingPapers(entryId: string): Promise<Paper[]> {
  const key = `citing:${entryId}`;
  if (cache.has(key)) return cache.get(key)!;

  const url = `${API_BASE_URL}/papers?citedBy=${encodeURIComponent(entryId)}&take=1000`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API request failed (${res.status})`);

  // Annahme: Backend liefert bereits Paper-Objekte in ähnlichem Format wie Frontend erwartet.
  // Falls Backend ein anderes Schema liefert, hier normalisieren.
  const payload = (await res.json()) as any;
  const items: any[] = Array.isArray(payload) ? payload : payload?.items ?? [];
  const papers: Paper[] = items.map((p: any) => {
    // Minimal-Normalisierung / Fallbacks — an Projekt-API anpassen
    return {
      ...p,
      entry_id: p.entry_id ?? String(p.id),
      title: p.title ?? 'Untitled',
      citations: Array.isArray(p.citations) ? p.citations.map(String) : [],
      tsne1: typeof p.tsne1 === 'number' ? p.tsne1 : (p.tsne?.[0] ?? 0),
      tsne2: typeof p.tsne2 === 'number' ? p.tsne2 : (p.tsne?.[1] ?? 0),
      authors: p.authors ?? '',
      summary: p.summary ?? '',
      category: p.category ?? (p.cluster ?? null),
      cluster: p.cluster ?? (p.category ?? 'U'),
      added: p.added ?? new Date().toISOString(),
      url: p.url ?? null,
      hash: p.hash ?? null,
      published: p.published ?? null,
      id: p.id ?? undefined
    } as Paper;
  });

  cache.set(key, papers);
  return papers;
}

export function clearCitationCache(entryId?: string) {
  if (entryId) cache.delete(`citing:${entryId}`);
  else cache.clear();
}

export async function fetchPaperCitations(entryId: string): Promise<PaperCitation[]> {
  const res = await fetch(`${API_BASE_URL}/paper-citations/paper/${encodeURIComponent(entryId)}`);
  if (!res.ok) throw new Error(`Failed to fetch paper citations: ${res.status}`);
  return res.json();
}

export async function fetchPaperReferences(entryId: string): Promise<PaperReference[]> {
  const res = await fetch(`${API_BASE_URL}/paper-references/paper/${encodeURIComponent(entryId)}`);
  if (!res.ok) throw new Error(`Failed to fetch paper references: ${res.status}`);
  return res.json();
}

export async function fetchExternalCitations(entryId: string): Promise<Citation[]> {
  const res = await fetch(`${API_BASE_URL}/citations/paper/${encodeURIComponent(entryId)}`);
  if (!res.ok) throw new Error(`Failed to fetch external citations: ${res.status}`);
  return res.json();
}

export async function fetchExternalReferences(entryId: string): Promise<Reference[]> {
  const res = await fetch(`${API_BASE_URL}/references/paper/${encodeURIComponent(entryId)}`);
  if (!res.ok) throw new Error(`Failed to fetch external references: ${res.status}`);
  return res.json();
}

/**
 * Fetches all relations for a given paper (both as source and target).
 */
export async function fetchRelationsForPaper(entryId: string): Promise<Relation[]> {
  const res = await fetch(`${API_BASE_URL}/relations/paper/${encodeURIComponent(entryId)}`);
  if (!res.ok) throw new Error(`Failed to fetch relations for paper: ${res.status}`);
  return res.json();
}

/**
 * Fetches relations where the given paper is the source.
 */
export async function fetchRelationsBySource(sourceId: string): Promise<Relation[]> {
  const res = await fetch(`${API_BASE_URL}/relations/source/${encodeURIComponent(sourceId)}`);
  if (!res.ok) throw new Error(`Failed to fetch relations by source: ${res.status}`);
  return res.json();
}

/**
 * Fetches relations where the given paper is the target.
 */
export async function fetchRelationsByTarget(targetId: string): Promise<Relation[]> {
  const res = await fetch(`${API_BASE_URL}/relations/target/${encodeURIComponent(targetId)}`);
  if (!res.ok) throw new Error(`Failed to fetch relations by target: ${res.status}`);
  return res.json();
}

/**
 * Fetches all relations with optional pagination.
 */
export async function fetchAllRelations(limit = 1000, skip = 0): Promise<Relation[]> {
  const res = await fetch(`${API_BASE_URL}/relations?take=${limit}&skip=${skip}`);
  if (!res.ok) throw new Error(`Failed to fetch all relations: ${res.status}`);
  return res.json();
}

function normalizePaper(raw: Paper, index: number, total: number): Paper | null {
  if (!raw || !raw.entry_id || !raw.title || raw.title === '[STUB] Pending Fetch') {
    return null;
  }
    console.log("normalizePaper", raw.entry_id)
  const anyRaw = raw as any;
  const summary = raw.summary ?? 'Keine Zusammenfassung vorhanden.';
  const authors = formatAuthors(raw.authors);
  const category = (raw.category ?? anyRaw.cluster) ?? null;
  const { tsne1, tsne2 } = deriveTsne(raw.tsne, index, total);

  return {
    id: Number(raw.id ?? index),
    entry_id: raw.entry_id,
    title: raw.title,
    authors: authors,
    summary: summary,
    published: raw.published,
    category: category,
    url: raw.url ?? "",
    tsne: [tsne1, tsne2],
    added: raw.added ?? new Date().toISOString(),
    cluster: category ?? 'U',
  };
}

function formatAuthors(authors: Paper['authors']): string {
  if (!authors) return '';
  if (Array.isArray(authors)) {
    return authors.join(', ');
  }
  return authors;
}


function deriveTsne(value: unknown, index: number, total: number) {
  const fallback = circlePosition(index, total);
  if (Array.isArray(value) && value.length >= 2) {
    const [x, y] = value;
    return {
      tsne1: typeof x === 'number' ? x : Number(x) || fallback.tsne1,
      tsne2: typeof y === 'number' ? y : Number(y) || fallback.tsne2,
    };
  }
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const x = obj.x ?? obj.tsne1 ?? obj[0];
    const y = obj.y ?? obj.tsne2 ?? obj[1];
    return {
      tsne1: typeof x === 'number' ? x : Number(x) || fallback.tsne1,
      tsne2: typeof y === 'number' ? y : Number(y) || fallback.tsne2,
    };
  }
  return fallback;
}

function circlePosition(index: number, total: number) {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2;
  const radius = 10;
  return {
    tsne1: Math.cos(angle) * radius,
    tsne2: Math.sin(angle) * radius,
  };
}
