<script lang="ts">
  // Die Props müssen exakt zu dem passen, was du in +page.svelte übergibst
  export let selectedPaper: any = null; // Kann null sein
  export let currentLevel: number = 0;  // Muss definiert sein!
  export let onBack: () => void;
</script>

<div class="sidebar">
  <div class="header">
    <h2>Arxiv Map</h2>
    {#if currentLevel > 0}
      <button on:click={onBack} class="back-btn">
        ⬅ Ebene hoch ({currentLevel})
      </button>
    {/if}
  </div>

  <div class="content">
    {#if selectedPaper}
      <div class="paper-details">
        <h3>{selectedPaper.title}</h3>
        <p class="meta-id">ID: {selectedPaper.id}</p>

        <h4>Authors</h4>
        <div class="tags">
          {#each selectedPaper.authors as author}
            <span class="tag">{author}</span>
          {/each}
        </div>

        <div class="stats">
            <div><strong>Cites:</strong> {selectedPaper.cites?.length || 0}</div>
            <div><strong>Similar:</strong> {selectedPaper.similar?.length || 0}</div>
        </div>
      </div>

    {:else}
      <div class="placeholder">
        {#if currentLevel === 0}
          <p>ℹ️ Wähle eine <strong>Kategorie</strong> (blaue Cluster), um hineinzuzoomen.</p>
        {:else if currentLevel === 1}
          <p>ℹ️ Du bist in Level 1. Wähle eine <strong>Subcategory</strong> (grüne Cluster).</p>
        {:else if currentLevel === 2}
          <p>ℹ️ Du bist in Level 2. Klicke auf einen <strong>roten Punkt</strong>, um Paper-Details zu sehen.</p>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .sidebar {
    width: 320px;
    height: 100%;
    background: #f8f9fa;
    border-left: 1px solid #ddd;
    display: flex;
    flex-direction: column;
    font-family: sans-serif;
  }
  .header {
    padding: 1rem;
    background: #fff;
    border-bottom: 1px solid #eee;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  }
  .back-btn {
    margin-top: 0.5rem;
    padding: 0.4rem 0.8rem;
    cursor: pointer;
    background: #333;
    color: #fff;
    border: none;
    border-radius: 4px;
    font-size: 0.9rem;
  }
  .content {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
  }
  .paper-details h3 {
    margin-top: 0;
    font-size: 1.1rem;
    line-height: 1.4;
  }
  .meta-id {
    color: #666;
    font-size: 0.8rem;
    font-family: monospace;
    margin-bottom: 1rem;
  }
  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-bottom: 1rem;
  }
  .tag {
    background: #e9ecef;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
  }
  .stats {
    display: flex;
    gap: 1rem;
    font-size: 0.9rem;
    color: #444;
  }
  .placeholder {
    color: #777;
    text-align: center;
    margin-top: 2rem;
    line-height: 1.5;
  }
</style>