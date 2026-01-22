<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import type { Paper } from '$lib/types/paper';
  import { getClusterColor } from '../utils/clusterColors';
  import { paperConnections, citationsWithPapers, referencesWithPapers, relationsWithPapers } from '$lib/stores/paperConnections';

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

  $: dataSource = papers;

  // UI state
  let query = '';
  let focusSelected = false; // if true, only the selected paper is shown
  let expandedCitations = new Set<string>();
  let expandedExternal = new Set<string>(); // track which papers have external section expanded
  let expandedExternalItems = new Set<string>(); // track which external items are expanded (by paperId)
  let localSelected: Paper | null = null; // local selected for immediate display

  // *** BULLETPROOF REACTIVE - WAITS FOR DATA ***
  $: {
    if (selectedPaperId && dataSource && dataSource.length > 0) {
      const foundPaper = dataSource.find((p) => p.entry_id === selectedPaperId);
      
      localSelected = foundPaper || null;
      focusSelected = true;
      isOpen = true; // FORCE OPEN SIDEBAR

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
    if (!q) return dataSource;
    return dataSource.filter((p) => {
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

  function formatExternalAuthors(authors: { name: string }[] | undefined): string {
    if (!authors || authors.length === 0) return 'Unknown';
    return authors.map(a => a.name).join(', ');
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
    const target = dataSource.find((p) => p.entry_id === citedId);
    if (target) selectPaper(target);
  }

  //badges next to the papers in the sidebar
  //colors by cluster identifiers (falls back to grey when missing)
  //todo: remove when backend provides cluster colors or make dynamic
  /*const clusterColors: Record<string, string> = {
    A: '#CC6666',
    B: '#66B2B2',
    C: '#9966CC',
    D: '#CC66B2',
    E: '#6699CC',
    F: '#FF4500',
    G: '#00CED1',
  };*/
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
                    {#each $citationsWithPapers as conn}
                      {#if conn.paper}
                        <div
                          class="cited-paper-item"
                          role="button"
                          tabindex="0"
                          on:click|stopPropagation={() => selectCitedPaper(conn.entry_id)}
                          on:keydown|stopPropagation={(e) => e.key === 'Enter' && selectCitedPaper(conn.entry_id)}
                        >
                          <div class="cited-paper-cluster" style="background-color: {getClusterColor(conn.paper.category, conn.paper.cluster)}">
                            {conn.paper.cluster}
                          </div>
                          <div class="cited-paper-info">
                            <h5>{conn.paper.title}</h5>
                            <p class="cited-paper-authors">{conn.paper.authors}</p>
                            <p class="cited-paper-summary">
                              {conn.paper.summary && conn.paper.summary.length > 80
                                ? `${conn.paper.summary.substring(0, 80)}...`
                                : conn.paper.summary ?? ''}
                            </p>
                            <span class="cited-paper-date">{conn.paper.published ? new Date(conn.paper.published).getFullYear() : '—'}</span>
                          </div>
                        </div>
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if $referencesWithPapers.length > 0}
                  <div class="connection-section">
                    <span class="connection-label reference-label">📤 References:</span>
                    {#each $referencesWithPapers as conn}
                      {#if conn.paper}
                        <div
                          class="cited-paper-item reference-item"
                          role="button"
                          tabindex="0"
                          on:click|stopPropagation={() => selectCitedPaper(conn.entry_id)}
                          on:keydown|stopPropagation={(e) => e.key === 'Enter' && selectCitedPaper(conn.entry_id)}
                        >
                          <div class="cited-paper-cluster" style="background-color: {getClusterColor(conn.paper.category, conn.paper.cluster)}">
                            {conn.paper.cluster}
                          </div>
                          <div class="cited-paper-info">
                            <h5>{conn.paper.title}</h5>
                            <p class="cited-paper-authors">{conn.paper.authors}</p>
                            <p class="cited-paper-summary">
                              {conn.paper.summary && conn.paper.summary.length > 80
                                ? `${conn.paper.summary.substring(0, 80)}...`
                                : conn.paper.summary ?? ''}
                            </p>
                            <span class="cited-paper-date">{conn.paper.published ? new Date(conn.paper.published).getFullYear() : '—'}</span>
                          </div>
                        </div>
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if $relationsWithPapers.length > 0}
                  <div class="connection-section">
                    <span class="connection-label relation-label">🔗 Relations:</span>
                    {#each [...$relationsWithPapers].sort((a, b) => (b.raw?.confidence ?? 0) - (a.raw?.confidence ?? 0)) as conn}
                      {#if conn.paper}
                        <div
                          class="cited-paper-item relation-item"
                          role="button"
                          tabindex="0"
                          on:click|stopPropagation={() => selectCitedPaper(conn.entry_id)}
                          on:keydown|stopPropagation={(e) => e.key === 'Enter' && selectCitedPaper(conn.entry_id)}
                        >
                          <div class="cited-paper-cluster" style="background-color: {getClusterColor(conn.paper.category, conn.paper.cluster)}">
                            {conn.paper.cluster}
                          </div>
                          <div class="cited-paper-info">
                            <h5>{conn.paper.title}</h5>
                            <p class="cited-paper-authors">{conn.paper.authors}</p>
                            <p class="cited-paper-summary">
                              {conn.paper.summary && conn.paper.summary.length > 80
                                ? `${conn.paper.summary.substring(0, 80)}...`
                                : conn.paper.summary ?? ''}
                            </p>
                            <div class="cited-paper-meta">
                              <span class="cited-paper-date">{conn.paper.published ? new Date(conn.paper.published).getFullYear() : '—'}</span>
                              <span class="relation-confidence">Confidence: {((conn.raw?.confidence ?? 0) * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                        </div>
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
                          {#each $paperConnections.externalCitations as ext}
                            {@const sem = ext.semanticscholar_obj}
                            {@const itemId = `ext-cit-${sem?.paperId || ext.id}`}
                            <div
                              class="external-paper-item"
                              role="button"
                              tabindex="0"
                              on:click|stopPropagation={() => toggleExternalItem(itemId)}
                              on:keydown|stopPropagation={(e) => e.key === 'Enter' && toggleExternalItem(itemId)}
                            >
                              <div class="external-paper-header">
                                <span class="external-paper-title">{sem?.title || 'Unknown Title'}</span>
                                <span class="external-paper-year">{sem?.year || '—'}</span>
                                <span class="external-expand-icon">{expandedExternalItems.has(itemId) ? '▾' : '▸'}</span>
                              </div>
                              {#if expandedExternalItems.has(itemId)}
                                <div class="external-paper-details">
                                  <p class="external-paper-authors">
                                    <strong>Authors:</strong> {formatExternalAuthors(sem?.authors)}
                                  </p>
                                  {#if sem?.abstract}
                                    <p class="external-paper-abstract">
                                      <strong>Abstract:</strong> {sem.abstract}
                                    </p>
                                  {/if}
                                  {#if sem?.fieldsOfStudy?.length > 0}
                                    <p class="external-paper-fields">
                                      <strong>Fields:</strong> {sem.fieldsOfStudy.join(', ')}
                                    </p>
                                  {/if}
                                  {#if sem?.venue}
                                    <p class="external-paper-venue">
                                      <strong>Venue:</strong> {sem.venue}
                                    </p>
                                  {/if}
                                  <p class="external-paper-stats">
                                    <strong>Citations:</strong> {sem?.citationCount ?? '—'} | <strong>References:</strong> {sem?.referenceCount ?? '—'}
                                  </p>
                                  {#if sem?.url}
                                    <a class="external-paper-link" href={sem.url} target="_blank" rel="noopener noreferrer">
                                      🔗 View on Semantic Scholar
                                    </a>
                                  {/if}
                                </div>
                              {/if}
                            </div>
                          {/each}
                        </div>
                      {/if}

                      {#if $paperConnections.externalReferences.length > 0}
                        <div class="connection-section">
                          <span class="connection-label external-reference-label">📤 External References:</span>
                          {#each $paperConnections.externalReferences as ext}
                            {@const sem = ext.semanticscholar_obj}
                            {@const itemId = `ext-ref-${sem?.paperId || ext.id}`}
                            <div
                              class="external-paper-item"
                              role="button"
                              tabindex="0"
                              on:click|stopPropagation={() => toggleExternalItem(itemId)}
                              on:keydown|stopPropagation={(e) => e.key === 'Enter' && toggleExternalItem(itemId)}
                            >
                              <div class="external-paper-header">
                                <span class="external-paper-title">{sem?.title || 'Unknown Title'}</span>
                                <span class="external-paper-year">{sem?.year || '—'}</span>
                                <span class="external-expand-icon">{expandedExternalItems.has(itemId) ? '▾' : '▸'}</span>
                              </div>
                              {#if expandedExternalItems.has(itemId)}
                                <div class="external-paper-details">
                                  <p class="external-paper-authors">
                                    <strong>Authors:</strong> {formatExternalAuthors(sem?.authors)}
                                  </p>
                                  {#if sem?.abstract}
                                    <p class="external-paper-abstract">
                                      <strong>Abstract:</strong> {sem.abstract}
                                    </p>
                                  {/if}
                                  {#if sem?.fieldsOfStudy?.length > 0}
                                    <p class="external-paper-fields">
                                      <strong>Fields:</strong> {sem.fieldsOfStudy.join(', ')}
                                    </p>
                                  {/if}
                                  {#if sem?.venue}
                                    <p class="external-paper-venue">
                                      <strong>Venue:</strong> {sem.venue}
                                    </p>
                                  {/if}
                                  <p class="external-paper-stats">
                                    <strong>Citations:</strong> {sem?.citationCount ?? '—'} | <strong>References:</strong> {sem?.referenceCount ?? '—'}
                                  </p>
                                  {#if sem?.url}
                                    <a class="external-paper-link" href={sem.url} target="_blank" rel="noopener noreferrer">
                                      🔗 View on Semantic Scholar
                                    </a>
                                  {/if}
                                </div>
                              {/if}
                            </div>
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

  .cited-paper-item {
    padding: 0.5rem;
    background-color: #3a3a45;
    margin-bottom: 0.25rem;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .cited-paper-item:hover {
    background-color: #4a4a55;
  }

  .cited-paper-item.cited-paper-missing {
    flex-direction: column;
    gap: 0.25rem;
    opacity: 0.6;
  }

  .cited-paper-cluster {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 10px;
    flex-shrink: 0;
  }

  .cited-paper-info {
    flex: 1;
    min-width: 0;
  }

  .cited-paper-item h5 {
    margin: 0 0 0.15rem 0;
    font-size: 12px;
    color: white;
    line-height: 1.2;
  }

  .cited-paper-authors {
    margin: 0 0 0.25rem 0;
    font-size: 10px;
    color: #999;
    font-style: italic;
  }

  .cited-paper-summary {
    margin: 0 0 0.25rem 0;
    font-size: 10px;
    color: #bbb;
    line-height: 1.3;
  }

  .cited-paper-date {
    font-size: 9px;
    color: #888;
  }

  .missing-paper-id {
    font-size: 10px;
    color: #999;
    font-family: monospace;
  }

  .missing-paper-note {
    font-size: 9px;
    color: #666;
    font-style: italic;
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

  .reference-item {
    border-left: 2px solid #1E90FF;
  }

  .relation-label {
    color: #32CD32;
    background-color: rgba(50, 205, 50, 0.15);
  }

  .relation-item {
    border-left: 2px solid #32CD32;
  }

  .cited-paper-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .relation-confidence {
    font-size: 9px;
    color: #32CD32;
    font-weight: bold;
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

  .external-paper-item {
    background-color: rgba(30, 30, 40, 0.6);
    border-radius: 4px;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    cursor: pointer;
    border-left: 2px solid #8B5CF6;
    transition: background-color 0.2s ease;
  }

  .external-paper-item:hover {
    background-color: rgba(139, 92, 246, 0.2);
  }

  .external-paper-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .external-paper-title {
    flex: 1;
    font-size: 11px;
    font-weight: bold;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .external-paper-year {
    font-size: 10px;
    color: #888;
    flex-shrink: 0;
  }

  .external-expand-icon {
    font-size: 10px;
    color: #8B5CF6;
    flex-shrink: 0;
  }

  .external-paper-details {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(139, 92, 246, 0.3);
  }

  .external-paper-details p {
    font-size: 10px;
    color: #bbb;
    margin: 0.25rem 0;
    line-height: 1.4;
  }

  .external-paper-details strong {
    color: #A78BFA;
  }

  .external-paper-authors {
    color: #ccc !important;
  }

  .external-paper-abstract {
    max-height: 100px;
    overflow-y: auto;
  }

  .external-paper-fields {
    color: #8B5CF6 !important;
  }

  .external-paper-link {
    display: inline-block;
    margin-top: 0.5rem;
    font-size: 10px;
    color: #8B5CF6;
    text-decoration: none;
    padding: 0.25rem 0.5rem;
    background-color: rgba(139, 92, 246, 0.2);
    border-radius: 3px;
    transition: background-color 0.2s ease;
  }

  .external-paper-link:hover {
    background-color: rgba(139, 92, 246, 0.4);
    text-decoration: underline;
  }
</style>