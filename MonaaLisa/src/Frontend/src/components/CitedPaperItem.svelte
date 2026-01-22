<script lang="ts">
  import type { Paper } from '$lib/types/paper';
  import { getClusterColor } from '../utils/clusterColors';
  import { createEventDispatcher } from 'svelte';

  export let paper: Paper;
  export let confidence: number | null = null;
  export let variant: 'citation' | 'reference' | 'relation' = 'citation';

  const dispatch = createEventDispatcher<{ select: string }>();

  function handleSelect() {
    if (paper.entry_id) {
      dispatch('select', paper.entry_id);
    }
  }

  function getYear(dateStr: string | null | undefined): string {
    if (!dateStr) return '—';
    const year = new Date(dateStr).getFullYear();
    return isNaN(year) ? '—' : String(year);
  }

  function truncate(text: string | undefined, maxLen: number): string {
    if (!text) return '';
    return text.length > maxLen ? `${text.substring(0, maxLen)}...` : text;
  }
</script>

<div
  class="item {variant}-item"
  role="button"
  tabindex="0"
  on:click|stopPropagation={handleSelect}
  on:keydown|stopPropagation={(e) => e.key === 'Enter' && handleSelect()}
>
  <div class="cluster" style="background-color: {getClusterColor(paper.category, paper.cluster)}">
    {paper.cluster}
  </div>
  <div class="info">
    <h5>{paper.title}</h5>
    <p class="authors">{paper.authors}</p>
    <p class="summary">{truncate(paper.summary, 80)}</p>
    <div class="meta">
      <span class="date">{getYear(paper.published)}</span>
      {#if confidence !== null}
        <span class="confidence">Confidence: {(confidence * 100).toFixed(1)}%</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .item {
    padding: 0.5rem;
    background-color: #3a3a45;
    margin-bottom: 0.25rem;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .item:hover {
    background-color: #4a4a55;
  }

  .reference-item {
    border-left: 2px solid #1E90FF;
  }

  .relation-item {
    border-left: 2px solid #32CD32;
  }

  .cluster {
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

  .info {
    flex: 1;
    min-width: 0;
  }

  .info h5 {
    margin: 0 0 0.15rem 0;
    font-size: 12px;
    color: white;
    line-height: 1.2;
  }

  .authors {
    margin: 0 0 0.25rem 0;
    font-size: 10px;
    color: #999;
    font-style: italic;
  }

  .summary {
    margin: 0 0 0.25rem 0;
    font-size: 10px;
    color: #bbb;
    line-height: 1.3;
  }

  .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .date {
    font-size: 9px;
    color: #888;
  }

  .confidence {
    font-size: 9px;
    color: #32CD32;
    font-weight: bold;
  }
</style>

