<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import type { Paper } from '$lib/types/paper';
  import { getClusterColor } from '../utils/clusterColors';
  import { paperConnections, citationsWithPapers, referencesWithPapers, relationsWithPapers } from '$lib/stores/paperConnections';
  import CitedPaperItem from './CitedPaperItem.svelte';
  import ExternalPaperItem from './ExternalPaperItem.svelte';

  /**
   * array of papers to display.
   * passed from the parent.
   * @type {Paper[]}
   */
  export let papers: Paper[] = [];

  /**
   * control for sidebar visibility.
   * @type {boolean}
   */
  export let isOpen: boolean = false;

  /**
   * currently selected paper id.
   * @type {string | null}
   */
  export let selectedPaperId: string | null = null;

  const dispatch = createEventDispatcher();

  // UI state
  let query = '';
  let focusSelected = false; // if true, only the selected paper is shown
  let expandedCitations = new Set<string>();
  let expandedExternal = new Set<string>(); // track which papers have external section expanded
  let expandedExternalItems = new Set<string>(); // track which external items are expanded (by paperId)
  let localSelected: Paper | null = null; // local selected for immediate display

  // *** BULLETPROOF REACTIVE - WAITS FOR DATA ***
  $: {
    if (selectedPaperId && papers && papers.length > 0) {
      const foundPaper = papers.find((p) => p.entry_id === selectedPaperId);

      localSelected = foundPaper || null;
      focusSelected = true;
      isOpen = true;

      tick().then(() => {
        const el = document.querySelector(`[data-paper-id="${selectedPaperId}"]`) as HTMLElement | null;
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    } else {
      localSelected = null;
      focusSelected = false;
    }
  }

  // Search/filter
  function normalize(s: string | undefined | null) {
    return (s ?? '').toLowerCase();
  }

  $: filteredList = (() => {
    const q = normalize(query).trim();
    if (!q) return papers;
    return papers.filter((p) => {
      const inTitle = normalize(p.title).includes(q);
      const authorsStr = Array.isArray(p.authors) ? p.authors.join(' ') : p.authors;
      const inAuthors = normalize(authorsStr).includes(q);
      const inSummary = normalize(p.summary).includes(q);
      return inTitle || inAuthors || inSummary;
    });
  })();

  function sortSelectedFirst(list: Paper[]) {
    if (!localSelected) return list;
    const selId = localSelected.entry_id;
    return list.slice().sort((a, b) => {
      if (a.entry_id === selId && b.entry_id !== selId) return -1;
      if (b.entry_id === selId && a.entry_id !== selId) return 1;
      return 0;
    });
  }

  // Displayed list:
  // - If focusing selected, show only that one (on any selection)
  // - Else show filtered list, with selected (if any) at top
  $: displayedPapers =
    focusSelected && localSelected ? [localSelected] : sortSelectedFirst(filteredList);

  // Handlers
  function onSearchInput(e: Event) {
    const val = (e.currentTarget as HTMLInputElement).value;
    query = val;
    if (val.trim()) {
      // Searching shows relevant papers; do not force single-selected view
      focusSelected = false;
    }
  }

  function clearSearch() {
    query = '';
  }


  function getPublishedYear(dateStr: string | null | undefined): number {
    if (!dateStr) return 0;
    const year = new Date(dateStr).getFullYear();
    return isNaN(year) ? 0 : year;
  }

  function sortByPublishedYear<T extends { paper?: { published?: string | null } }>(items: T[]): T[] {
    return [...items].sort((a, b) => getPublishedYear(b.paper?.published) - getPublishedYear(a.paper?.published));
  }

  function sortExternalByYear<T extends { semanticscholar_obj: { year?: number } }>(items: T[]): T[] {
    return [...items].sort((a, b) => (b.semanticscholar_obj?.year ?? 0) - (a.semanticscholar_obj?.year ?? 0));
  }

  function showAll() {
    focusSelected = false;
    localSelected = null;
  }

  function toggleSidebar() {
    dispatch('toggle');
  }

  function toggleCitations(paperEntryId: string) {
    if (expandedCitations.has(paperEntryId)) {
      expandedCitations.delete(paperEntryId);
    } else {
      expandedCitations.add(paperEntryId);
    }
    expandedCitations = new Set(expandedCitations); // trigger reactivity
  }

  function toggleExternal(paperEntryId: string) {
    if (expandedExternal.has(paperEntryId)) {
      expandedExternal.delete(paperEntryId);
    } else {
      expandedExternal.add(paperEntryId);
    }
    expandedExternal = new Set(expandedExternal); // trigger reactivity
  }

  function toggleExternalItem(itemId: string) {
    if (expandedExternalItems.has(itemId)) {
      expandedExternalItems.delete(itemId);
    } else {
      expandedExternalItems.add(itemId);
    }
    expandedExternalItems = new Set(expandedExternalItems); // trigger reactivity
  }

  function selectPaper(paper: Paper) {
    // Selecting a paper focuses it and collapses view to that paper
    localSelected = paper;
    focusSelected = true;
    query = '';
    dispatch('selectPaper', paper);
    // Scroll to the selected paper
    tick().then(() => {
      const el = document.querySelector(
        `[data-paper-id="${paper.entry_id}"]`
      ) as HTMLElement | null;
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  function selectCitedPaper(citedId: string) {
    const target = papers.find((p) => p.entry_id === citedId);
    if (target) selectPaper(target);
  }
</script>

<!-- sidebar toggle button -->
<button class="sidebar-toggle" class:open={isOpen} on:click={toggleSidebar}>
  <span class="toggle-icon">{isOpen ? '→' : '←'}</span>
</button>

<!-- expandable sidebar -->
<div class="sidebar" class:open={isOpen}>
  <div class="sidebar-header">
    <h3>Academic Papers</h3>
    <button class="close-btn" on:click={toggleSidebar}>×</button>
  </div>

  <div class="sidebar-tools">
    <div class="search">
      <input
        type="text"
        placeholder="Search title or authors..."
        value={query}
        on:input={onSearchInput}
      />
      {#if query}
        <button class="clear" on:click={clearSearch}>✕</button>
      {/if}
    </div>

    {#if focusSelected || query}
      <button class="show-all" on:click={showAll}>Show all</button>
    {/if}
  </div>
  
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="sidebar-content" on:click={() => dispatch('deselect')}>
    {#if displayedPapers.length === 0}
      <div class="empty">No papers found.</div>
    {:else}
      {#each displayedPapers as paper (paper.entry_id)}
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div
          class="paper-item" 
          class:selected={selectedPaperId === paper.entry_id}
          data-paper-id={paper.entry_id}
          on:click|stopPropagation={() => selectPaper(paper)}
        >
          <div class="paper-cluster" style="background-color: {getClusterColor(paper.category, paper.cluster)}">
            {paper.cluster}
          </div>
          <div class="paper-info">
            <h4>{paper.title}</h4>
            <p class="paper-authors">{paper.authors}</p>
            <p class="paper-summary">
              {(paper.summary ?? '').length > 100
                ? `${(paper.summary ?? '').substring(0, 100)}...`
                : paper.summary ?? ''}
            </p>
            <div class="paper-meta">
              {#if selectedPaperId === paper.entry_id}
                <button
                  class="citations"
                  on:click|stopPropagation={() => paper.entry_id && toggleCitations(paper.entry_id)}
                >
                  {#if $paperConnections.loading}
                    Loading...
                  {:else}
                    Citations ({$citationsWithPapers.length}) / Refs ({$referencesWithPapers.length}) / Rel ({$relationsWithPapers.length}) {paper.entry_id && expandedCitations.has(paper.entry_id) ? '▾' : '▸'}
                  {/if}
                </button>
              {/if}
              <span class="date">{paper.published ? new Date(paper.published).getFullYear() : '—'}</span>
            </div>

            {#if selectedPaperId === paper.entry_id && paper.entry_id && expandedCitations.has(paper.entry_id)}
              <div class="cited-papers">
                {#if $citationsWithPapers.length > 0}
                  <div class="connection-section">
                    <span class="connection-label citation-label">📥 Cited by this paper:</span>
                    {#each sortByPublishedYear($citationsWithPapers) as conn}
                      {#if conn.paper}
                        <CitedPaperItem
                          paper={conn.paper}
                          variant="citation"
                          on:select={(e) => selectCitedPaper(e.detail)}
                        />
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if $referencesWithPapers.length > 0}
                  <div class="connection-section">
                    <span class="connection-label reference-label">📤 References:</span>
                    {#each sortByPublishedYear($referencesWithPapers) as conn}
                      {#if conn.paper}
                        <CitedPaperItem
                          paper={conn.paper}
                          variant="reference"
                          on:select={(e) => selectCitedPaper(e.detail)}
                        />
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if $relationsWithPapers.length > 0}
                  <div class="connection-section">
                    <span class="connection-label relation-label">🔗 Relations:</span>
                    {#each [...$relationsWithPapers].sort((a, b) => (b.raw?.confidence ?? 0) - (a.raw?.confidence ?? 0)) as conn}
                      {#if conn.paper}
                        <CitedPaperItem
                          paper={conn.paper}
                          variant="relation"
                          confidence={conn.raw?.confidence ?? null}
                          on:select={(e) => selectCitedPaper(e.detail)}
                        />
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if $citationsWithPapers.length === 0 && $referencesWithPapers.length === 0 && $relationsWithPapers.length === 0 && !$paperConnections.loading}
                  <p class="no-connections">No connections found in current dataset</p>
                {/if}

                <!-- External Section -->
                <div class="external-section-wrapper">
                  <button
                    class="external-toggle-btn"
                    on:click|stopPropagation={() => paper.entry_id && toggleExternal(paper.entry_id)}
                  >
                    {#if $paperConnections.loading}
                      Loading...
                    {:else}
                      🌐 External ({$paperConnections.externalCitations.length + $paperConnections.externalReferences.length}) {paper.entry_id && expandedExternal.has(paper.entry_id) ? '▾' : '▸'}
                    {/if}
                  </button>

                  {#if paper.entry_id && expandedExternal.has(paper.entry_id)}
                    <div class="external-papers">
                      {#if $paperConnections.externalCitations.length > 0}
                        <div class="connection-section">
                          <span class="connection-label external-citation-label">📥 External Citations:</span>
                          {#each sortExternalByYear($paperConnections.externalCitations) as ext}
                            {@const itemId = `ext-cit-${ext.semanticscholar_obj?.paperId || ext.id}`}
                            <ExternalPaperItem
                              semanticObj={ext.semanticscholar_obj}
                              isExpanded={expandedExternalItems.has(itemId)}
                              on:toggle={() => toggleExternalItem(itemId)}
                            />
                          {/each}
                        </div>
                      {/if}

                      {#if $paperConnections.externalReferences.length > 0}
                        <div class="connection-section">
                          <span class="connection-label external-reference-label">📤 External References:</span>
                          {#each sortExternalByYear($paperConnections.externalReferences) as ext}
                            {@const itemId = `ext-ref-${ext.semanticscholar_obj?.paperId || ext.id}`}
                            <ExternalPaperItem
                              semanticObj={ext.semanticscholar_obj}
                              isExpanded={expandedExternalItems.has(itemId)}
                              on:toggle={() => toggleExternalItem(itemId)}
                            />
                          {/each}
                        </div>
                      {/if}

                      {#if $paperConnections.externalCitations.length === 0 && $paperConnections.externalReferences.length === 0 && !$paperConnections.loading}
                        <p class="no-connections">No external connections found</p>
                      {/if}
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .sidebar-toggle {
    position: absolute;
    right: -5px;
    top: 50%;
    transform: translateY(-50%);
    background-color: #4a9eff;
    border: none;
    border-radius: 50% 0 0 50%;
    width: 40px;
    height: 60px;
    color: white;
    cursor: pointer;
    z-index: 200;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .sidebar-toggle:hover {
    background-color: #357abd;
  }

  .sidebar-toggle.open {
    right: 350px;
    border-radius: 0 50% 50% 0;
  }

  .toggle-icon {
    font-size: 18px;
    font-weight: bold;
  }

  .sidebar {
    position: absolute;
    right: -370px;
    top: 0;
    width: 370px;
    height: 100%;
    background-color: #2a2a35;
    border-left: 1px solid #3a3a45;
    transition: right 0.3s ease;
    z-index: 150;
    display: flex;
    flex-direction: column;
  }

  .sidebar.open {
    right: 0;
  }

  .sidebar-header {
    padding: 1rem;
    border-bottom: 1px solid #3a3a45;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .sidebar-header h3 {
    margin: 0;
    color: white;
    font-size: 18px;
  }

  .close-btn {
    background: none;
    border: none;
    color: #999;
    font-size: 24px;
    cursor: pointer;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    color: white;
  }

  .sidebar-tools {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #3a3a45;
    flex-wrap: nowrap; /* Prevents the button from wrapping underneath the search bar */
  }

  .search {
    flex: 1;
    position: relative;
  }

  .search input {
    width: 100%;
    max-width: 200px; /* Limits the search bar width to prevent it from getting too big */
    padding: 0.5rem 2rem 0.5rem 0.5rem;
    border: 1px solid #3a3a45;
    border-radius: 4px;
    background: #1f1f29;
    color: #e6e6e6;
    outline: none;
  }

  .search .clear {
    position: absolute;
    right: 4px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: #bbb;
    cursor: pointer;
    padding: 0 6px;
    height: 100%;
  }

  .show-all {
    flex-shrink: 0; /* Prevents the button from shrinking and getting cut off */
    background: #44495d;
    color: #e6e6e6;
    border: 1px solid #3a3a45;
    border-radius: 4px;
    padding: 0.45rem 0.6rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .show-all:hover {
    background: #50566e;
  }

  .sidebar-content {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }

  .empty {
    color: #bbb;
    padding: 1rem;
    font-size: 14px;
  }

  .paper-item {
    padding: 1rem;
    border-bottom: 1px solid #3a3a45;
    cursor: pointer;
    transition: background-color 0.2s;
    display: flex;
    gap: 0.75rem;
  }

  .paper-item:hover {
    background-color: #3a3a45;
  }

  .paper-item.selected {
    background-color: #4a9eff20;
    border-left: 3px solid #4a9eff;
  }

  .paper-cluster {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 12px;
    flex-shrink: 0;
  }

  .paper-info {
    flex: 1;
    min-width: 0;
  }

  .paper-info h4 {
    margin: 0 0 0.5rem 0;
    font-size: 14px;
    color: white;
    line-height: 1.3;
    word-wrap: break-word;
  }

  .paper-authors {
    margin: 0 0 0.5rem 0;
    font-size: 12px;
    color: #999;
    font-style: italic;
  }

  .paper-summary {
    margin: 0 0 0.5rem 0;
    font-size: 12px;
    color: #ccc;
    line-height: 1.4;
  }

  .paper-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #999;
  }

  .citations {
    cursor: pointer;
    color: #4a9eff;
    background: none;
    border: none;
    padding: 0;
    text-decoration: underline;
  }

  .cited-papers {
    margin-top: 0.5rem;
    padding-left: 0.75rem;
    border-left: 2px solid #4a9eff;
  }


  .connection-section {
    margin-bottom: 0.75rem;
  }

  .connection-label {
    display: block;
    font-size: 11px;
    font-weight: bold;
    margin-bottom: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
  }

  .citation-label {
    color: #FFD700;
    background-color: rgba(255, 215, 0, 0.15);
  }

  .reference-label {
    color: #1E90FF;
    background-color: rgba(30, 144, 255, 0.15);
  }

  .relation-label {
    color: #32CD32;
    background-color: rgba(50, 205, 50, 0.15);
  }


  .no-connections {
    color: #888;
    font-size: 11px;
    font-style: italic;
    padding: 0.5rem;
  }

  /* External papers styles */
  .external-section-wrapper {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid rgba(139, 92, 246, 0.3);
  }

  .external-toggle-btn {
    width: 100%;
    padding: 0.5rem;
    background-color: #8B5CF6;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    transition: background-color 0.2s ease;
    text-align: left;
  }

  .external-toggle-btn:hover {
    background-color: #7C3AED;
  }


  .external-papers {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background-color: rgba(139, 92, 246, 0.1);
    border-radius: 4px;
    border-left: 2px solid #8B5CF6;
  }

  .external-citation-label {
    color: #A78BFA;
    background-color: rgba(167, 139, 250, 0.15);
  }

  .external-reference-label {
    color: #C4B5FD;
    background-color: rgba(196, 181, 253, 0.15);
  }
</style>