<script lang="ts">
  import { onMount } from 'svelte';
  import Graph from './Graph.svelte';
  import Header from './Header.svelte';
  import Sidebar from './Sidebar.svelte';
  import type { ApiPaper, Paper, PapersResponse } from '$lib/types/paper';
  import { env as publicEnv } from '$env/dynamic/public';

  const API_BASE_URL = publicEnv.PUBLIC_API_BASE_URL || 'http://localhost:3000';
  const DEFAULT_LIMIT = 500;

  let papers: Paper[] = [];
  let sidebarOpen = false;
  let selectedPaperId: string | null = null;
  let loading = true;
  let error: string | null = null;

  onMount(() => {
    void loadPapers();
  });

  // lädt Papers vom Backend
  async function loadPapers() {
    loading = true;
    error = null;
    try {
      const response = await fetch(
        `${API_BASE_URL}/papers?take=${DEFAULT_LIMIT}&skip=0`,
      );
      if (!response.ok) {
        throw new Error(`Backend request failed (${response.status})`);
      }

      const payload = (await response.json()) as Partial<PapersResponse> | ApiPaper[];
      const rawItems = Array.isArray(payload) ? payload : payload?.items ?? [];

      papers = rawItems
        .map((item, index, array) => normalizePaper(item as ApiPaper, index, array.length))
        .filter((paper): paper is Paper => Boolean(paper));

      selectedPaperId = null;
      sidebarOpen = false;

      if (!papers.length) {
        error = 'Es wurden keine Papers gefunden.';
      }
    } catch (err) {
      error =
        err instanceof Error
          ? err.message
          : 'Unbekannter Fehler beim Laden der Papers.';
      papers = [];
    } finally {
      loading = false;
    }
  }

  // normalisiert rohes Paper-Objekt vom Backend in internes Paper-Format
  function normalizePaper(raw: ApiPaper, index: number, total: number): Paper | null {
    if (!raw || !raw.entry_id || !raw.title) {
      return null;
    }

    const summary = raw.summary ?? 'Keine Zusammenfassung vorhanden.';
    const authors = formatAuthors(raw.authors);
    const citations = deriveStringArray(raw.citations);
    const category = (raw.category ?? (raw as { cluster?: string | null }).cluster) ?? null;
    const { tsne1, tsne2 } = deriveTsne(raw.tsne, index, total);

    return {
      id: Number(raw.id ?? index),
      entry_id: raw.entry_id,
      title: raw.title,
      authors,
      summary,
      published: raw.published,
      category,
      url: raw.url ?? null,
      hash: raw.hash,
      citations,
      tsne1,
      tsne2,
      added: raw.added ?? new Date().toISOString(),
      cluster: category ?? 'U',
    };
  }

  // formatiert Autorenliste als String
  function formatAuthors(authors: ApiPaper['authors']): string {
    if (!authors) return '';
    if (Array.isArray(authors)) {
      return authors.join(', ');
    }
    return authors;
  }

  // wandelt verschiedene Formate von Zitationsangaben in ein String-Array um
  function deriveStringArray(value: unknown): string[] {
    if (!value) return [];
    if (Array.isArray(value)) {
      return value
        .map((item) => {
          if (typeof item === 'string') return item;
          if (typeof item === 'number') return item.toString();
          if (item && typeof item === 'object' && 'entry_id' in item) {
            const candidate = (item as { entry_id?: string }).entry_id;
            return candidate ?? '';
          }
          return '';
        })
        .filter(Boolean);
    }
    if (typeof value === 'string') {
      return value
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean);
    }
    if (typeof value === 'object') {
      return Object.values(value as Record<string, unknown>)
        .map((val) => {
          if (typeof val === 'string') return val;
          if (typeof val === 'number') return val.toString();
          return '';
        })
        .filter(Boolean);
    }
    return [];
  }

  // holt tSNE Koordinaten aus verschiedenen möglichen Formaten
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

  // fallback methode falls keine tSNE Koordinaten vorhanden sind - verteilt Punkte im Kreis
  function circlePosition(index: number, total: number) {
    const angle = (index / Math.max(total, 1)) * Math.PI * 2;
    const radius = 10;
    return {
      tsne1: Math.cos(angle) * radius,
      tsne2: Math.sin(angle) * radius,
    };
  }

  function handleToggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }

  //handling of paper selection from sidebar - update graph
  function handleSelectPaper(event: CustomEvent<Paper>) {
    const paper = event.detail;
    selectedPaperId = paper.entry_id;
    sidebarOpen = true;
    console.log('selected paper from sidebar:', paper);

  }

  //handling for node selection from graph - update sidebar
  function handleNodeSelected(event: CustomEvent<string>) {
    selectedPaperId = event.detail;
    sidebarOpen = true;
    console.log('selected paper from graph:', event.detail);
  }

  //handling node deselection from graph - clear sidebar selection
  function handleNodeDeselected() {
    selectedPaperId = null;
  }
</script>

<!-- main app container -->
<div class="app-container">
<!-- search component at top -->
<Header />

  <div class="main-content">
  <!-- graph visualization component with selection binding -->

    {#if loading}
      <div class="status-card">
        <p>Lade Papers...</p>
      </div>
    {:else if error}
      <div class="status-card error">
        <p>{error}</p>
        <button on:click={loadPapers}>Erneut versuchen</button>
      </div>
    {:else}
      <Graph
        {papers}
        {selectedPaperId}
        on:nodeSelected={handleNodeSelected}
        on:nodeDeselected={handleNodeDeselected}
      />

     <!-- sidebar component for the paper list -->
      <Sidebar
        papers={papers}
        isOpen={sidebarOpen}
        {selectedPaperId}
        on:toggle={handleToggleSidebar}
        on:selectPaper={handleSelectPaper}
      />
    {/if}
  </div>
</div>

<style>
  .app-container {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background-color: #1e1e27;
    color: white;
    overflow: hidden;
  }

  .main-content {
    flex: 1;
    position: relative;
    display: flex;
  }

  :global(.graph-container) {
    width: 100% !important;
    height: 100% !important;
  }

  .status-card {
    margin: auto;
    padding: 2rem;
    border-radius: 1rem;
    border: 1px solid #27313a;
    background-color: #232b32;
    color: #e0e6ed;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-width: 320px;
  }

  .status-card.error {
    border-color: #f56565;
  }

  .status-card button {
    align-self: center;
    background: #4a9eff;
    border: none;
    border-radius: 999px;
    color: white;
    cursor: pointer;
    padding: 0.5rem 1.5rem;
    font-weight: 600;
  }
</style>