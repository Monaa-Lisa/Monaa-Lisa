<!--
  MetricCards.svelte
  Row of 4 metric cards displaying the current navigation layers.
  In category view, they show the hierarchy path (e.g., "Computer Science" -> "cs.CG").
  Remaining cards show contextual stats.
-->
<script lang="ts">
  import type { ViewState } from '$lib/types/paper';

  export let view: ViewState;
  export let paperCount: number = 0;
  export let clusterCount: number = 0;
  /** arXiv citations count – provided after PaperDetailGraph fetches neighbourhood */
  export let arxivCitationCount: number | undefined = undefined;
  /** arXiv references (cited-by) count – provided after PaperDetailGraph fetches */
  export let arxivReferenceCount: number | undefined = undefined;

  interface Card {
    label: string;
    value: string;
    subValue?: string;
    icon: string;
    accent: string; /* gradient class */
  }

  $: cards = buildCards(view, paperCount, clusterCount, arxivCitationCount, arxivReferenceCount);

  function buildCards(
    v: ViewState,
    pCount: number,
    cCount: number,
    arxivCit?: number,
    arxivRef?: number,
  ): Card[] {
    if (v.level === 'top') {
      return [
        { label: 'View', value: 'All Categories', icon: '◎', accent: 'purple' },
        { label: 'Categories', value: String(cCount), icon: '⬡', accent: 'magenta' },
        { label: 'Depth', value: 'Top Level', icon: '◈', accent: 'cyan' },
        { label: 'Status', value: 'Exploring', icon: '◉', accent: 'blue' },
      ];
    }
    if (v.level === 'sub') {
      return [
        { label: 'Category', value: v.parentName, icon: '◎', accent: 'purple' },
        { label: 'Subcategories', value: String(cCount), icon: '⬡', accent: 'magenta' },
        { label: 'Depth', value: 'Level 2', icon: '◈', accent: 'cyan' },
        { label: 'Status', value: 'Navigating', icon: '◉', accent: 'blue' },
      ];
    }
    if (v.level === 'papers') {
      return [
        { label: 'Category', value: v.parentName, icon: '◎', accent: 'purple' },
        { label: 'Subcategory', value: v.categoryName, icon: '⬡', accent: 'magenta' },
        { label: 'Papers', value: String(pCount), icon: '◈', accent: 'cyan' },
        { label: 'Status', value: 'Viewing', icon: '◉', accent: 'blue' },
      ];
    }
    if (v.level === 'detail') {
      const citStr = arxivCit !== undefined ? String(arxivCit) : '…';
      const refStr = arxivRef !== undefined ? String(arxivRef) : '…';
      const nonArxivCit = v.paper.non_arxiv_citation_count ?? 0;
      const nonArxivRef = v.paper.non_arxiv_reference_count ?? 0;
      return [
        { label: 'Category', value: v.parentName, icon: '◎', accent: 'purple' },
        { label: 'Subcategory', value: v.categoryName, icon: '⬡', accent: 'magenta' },
        {
          label: 'Citations',
          value: citStr,
          subValue: nonArxivCit ? `+ ${nonArxivCit} non-arXiv` : undefined,
          icon: '◈',
          accent: 'cyan',
        },
        {
          label: 'References',
          value: refStr,
          subValue: nonArxivRef ? `+ ${nonArxivRef} non-arXiv` : undefined,
          icon: '◉',
          accent: 'blue',
        },
      ];
    }
    return [];
  }


</script>

<div class="metric-row">
  {#each cards as card}
    <div class="metric-card {card.accent}">
      <div class="card-glow"></div>
      <div class="card-content">
        <div class="card-header">
          <span class="card-icon">{card.icon}</span>
          <span class="card-label">{card.label}</span>
        </div>
        <div class="card-value" title={card.value}>{card.value}</div>
        {#if card.subValue}
          <div class="card-sub-value">{card.subValue}</div>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .metric-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    padding: 10px 16px;
    flex-shrink: 0;
  }

  .metric-card {
    position: relative;
    border-radius: var(--radius-md, 12px);
    overflow: hidden;
    background: var(--glass-bg, rgba(20, 22, 50, 0.55));
    backdrop-filter: blur(var(--glass-blur, 16px));
    border: 1px solid var(--glass-border, rgba(255,255,255,0.08));
    transition: all var(--transition-smooth, 0.3s cubic-bezier(0.4,0,0.2,1));
  }

  .metric-card:hover {
    transform: translateY(-1px);
  }

  /* top-edge accent line */
  .card-glow {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    opacity: 0.8;
  }

  /* ── Purple accent ── */
  .metric-card.purple .card-glow  { background: linear-gradient(90deg, #9333ea, rgba(147,51,234,0.2)); }
  .metric-card.purple .card-icon  { color: var(--accent-purple, #9333ea); }
  .metric-card.purple:hover {
    border-color: rgba(147, 51, 234, 0.35);
    box-shadow: 0 0 20px rgba(147, 51, 234, 0.15);
  }

  /* ── Magenta accent ── */
  .metric-card.magenta .card-glow { background: linear-gradient(90deg, #e839a0, rgba(232,57,160,0.2)); }
  .metric-card.magenta .card-icon { color: var(--accent-magenta, #e839a0); }
  .metric-card.magenta:hover {
    border-color: rgba(232, 57, 160, 0.35);
    box-shadow: 0 0 20px rgba(232, 57, 160, 0.15);
  }

  /* ── Cyan accent ── */
  .metric-card.cyan .card-glow    { background: linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2)); }
  .metric-card.cyan .card-icon    { color: var(--accent-cyan, #22d3ee); }
  .metric-card.cyan:hover {
    border-color: rgba(34, 211, 238, 0.35);
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.15);
  }

  /* ── Blue accent ── */
  .metric-card.blue .card-glow    { background: linear-gradient(90deg, #4a6cf7, rgba(74,108,247,0.2)); }
  .metric-card.blue .card-icon    { color: var(--accent-blue, #4a6cf7); }
  .metric-card.blue:hover {
    border-color: rgba(74, 108, 247, 0.35);
    box-shadow: 0 0 20px rgba(74, 108, 247, 0.15);
  }

  /* ── Card inner layout ── */
  .card-content {
    position: relative;
    padding: 10px 14px 12px;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }

  .card-icon {
    font-size: 12px;
    opacity: 0.7;
  }

  .card-label {
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted, #6b6b8d);
  }

  .card-value {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary, #f0f0f8);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.3;
  }

  .card-sub-value {
    font-size: 10px;
    color: var(--text-muted, #6b6b8d);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 768px) {
    .metric-row {
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      padding: 8px 12px;
    }
  }
</style>
