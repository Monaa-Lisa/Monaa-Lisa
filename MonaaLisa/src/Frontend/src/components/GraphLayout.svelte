<script lang="ts">
  import { onMount } from 'svelte';
  import Graph from './Graph.svelte';
  import Header from './Header.svelte';
  import Sidebar from './Sidebar.svelte';
  import type { Paper } from '$lib/types/paper';
  import { fetchPapers } from '$lib/api';

  const DEFAULT_LIMIT = 5000;

  let papers: Paper[] = [];
  let sidebarOpen = false;
  let selectedPaperId: string | null = null;
  let loading = true;
  let error: string | null = null;

  onMount(() => {
    void loadPapers();
  });

  // loads Papers from the Backend API
  async function loadPapers() {
    loading = true;
    error = null;
    try {
      papers = await fetchPapers(DEFAULT_LIMIT);

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