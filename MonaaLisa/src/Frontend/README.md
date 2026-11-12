# Monaa-Lisa frontend

SvelteKit 2 / Svelte 5 app that shows the arXiv map. It only talks to the
NestJS backend (`PUBLIC_API_BASE_URL`, default `http://localhost:3000`).

## Layout

- `src/lib/components/App.svelte`: the frame (header, sidebar, map, details)
  and all navigation state. The current subject, category and paper are
  mirrored in the URL (`?category=cs.LG&paper=1206.5538`).
- `Sidebar.svelte`: search with filters, and the list of categories or papers
  of the current level.
- `BubbleMap.svelte` (+ `lib/bubbles.ts`): the subject and category levels
  as packed circles, circle area = papers on arXiv.
- `PaperMap.svelte`: the paper map of one category on Sigma.js, points at
  their UMAP position, size = citations, colour = primary category or year
  of publication. Titles are placed by `lib/labels.ts`, the names of the
  regions come from `lib/regions.ts` (k-means on the positions, each group
  named after the term typical for its titles).
- `CitationTimeline.svelte`: references and citations of one paper as a
  chart (year against citations), or the papers most similar to it at their
  map positions with the category map behind them.
- `PaperDetails.svelte`: metadata, links (arXiv, PDF, DOI, Semantic Scholar),
  BibTeX, abstract, and the reference / citation / related lists.
- `LibraryPanel.svelte` (+ `lib/library.svelte.ts`): saved and recently
  opened papers in localStorage, BibTeX export.
- `lib/exportMap.ts`: saves a paper map as a figure (SVG, PNG) and its papers
  as CSV. The figure is drawn again from the data, not copied from the screen.
- `lib/api.ts`: the only place that calls the backend. `lib/neighbourhood.ts`
  loads and caches everything around one paper.
- `lib/categories.ts`: the arXiv hierarchy and the subject colours.
  `src/app.css`: design tokens (light and dark) and base styles. The data
  colours (`--series-1` to `--series-8`, `--seq-1` to `--seq-5`) are checked
  for colour blind readers, keep that in mind before changing them.

## Commands

```sh
npm install
npm run dev        # http://localhost:5173
npm run check      # svelte-check
npm run build      # production build for `node build` (adapter-node)
```
