<script lang="ts">
  export let semanticObj: Record<string, any>;
  export let isExpanded: boolean = false;

  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{ toggle: void }>();

  function toggle() {
    dispatch('toggle');
  }

  function formatAuthors(authors: { name: string }[] | undefined): string {
    if (!authors || authors.length === 0) return 'Unknown';
    return authors.map(a => a.name).join(', ');
  }
</script>

<div
  class="item"
  role="button"
  tabindex="0"
  on:click|stopPropagation={toggle}
  on:keydown|stopPropagation={(e) => e.key === 'Enter' && toggle()}
>
  <div class="header">
    <span class="title">{semanticObj?.title || 'Unknown Title'}</span>
    <span class="year">{semanticObj?.year || '—'}</span>
    <span class="expand-icon">{isExpanded ? '▾' : '▸'}</span>
  </div>

  {#if isExpanded}
    <div class="details">
      <p><strong>Authors:</strong> {formatAuthors(semanticObj?.authors)}</p>

      {#if semanticObj?.abstract}
        <p class="abstract"><strong>Abstract:</strong> {semanticObj.abstract}</p>
      {/if}

      {#if semanticObj?.fieldsOfStudy?.length > 0}
        <p class="fields"><strong>Fields:</strong> {semanticObj.fieldsOfStudy.join(', ')}</p>
      {/if}

      {#if semanticObj?.venue}
        <p><strong>Venue:</strong> {semanticObj.venue}</p>
      {/if}

      <p>
        <strong>Citations:</strong> {semanticObj?.citationCount ?? '—'} |
        <strong>References:</strong> {semanticObj?.referenceCount ?? '—'}
      </p>

      {#if semanticObj?.url}
        <a class="link" href={semanticObj.url} target="_blank" rel="noopener noreferrer">
          🔗 View on Semantic Scholar
        </a>
      {/if}
    </div>
  {/if}
</div>

<style>
  .item {
    background-color: rgba(30, 30, 40, 0.6);
    border-radius: 4px;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    cursor: pointer;
    border-left: 2px solid #8B5CF6;
    transition: background-color 0.2s ease;
  }

  .item:hover {
    background-color: rgba(139, 92, 246, 0.2);
  }

  .header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .title {
    flex: 1;
    font-size: 11px;
    font-weight: bold;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .year {
    font-size: 10px;
    color: #888;
    flex-shrink: 0;
  }

  .expand-icon {
    font-size: 10px;
    color: #8B5CF6;
    flex-shrink: 0;
  }

  .details {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(139, 92, 246, 0.3);
  }

  .details p {
    font-size: 10px;
    color: #bbb;
    margin: 0.25rem 0;
    line-height: 1.4;
  }

  .details strong {
    color: #A78BFA;
  }

  .abstract {
    max-height: 100px;
    overflow-y: auto;
  }

  .fields {
    color: #8B5CF6 !important;
  }

  .link {
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

  .link:hover {
    background-color: rgba(139, 92, 246, 0.4);
    text-decoration: underline;
  }
</style>

