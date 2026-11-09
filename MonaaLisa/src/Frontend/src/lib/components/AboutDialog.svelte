<script lang="ts">
    import Dialog from "$lib/components/ui/Dialog.svelte";

    interface Props {
        open: boolean;
        onclose: () => void;
    }

    let { open, onclose }: Props = $props();
    let lang = $state<"en" | "de">("en");
</script>

<Dialog {open} {onclose} title="About Monaa-Lisa" width={560}>
    <p>
        Monaa-Lisa is a map of the arXiv literature. Papers are placed by the similarity of their content, so a
        region of the map is a topic, and every paper can be followed along its references, its citations and its
        related papers.
    </p>

    <h3>How the map is made</h3>
    <ol>
        <li>
            <strong>Metadata</strong> (title, abstract, authors, categories, dates) comes from arXiv. References, citations
            and related papers come from Semantic Scholar. Links between two arXiv papers are kept as edges; references
            and citations outside arXiv are only counted.
        </li>
        <li>
            <strong>Embedding.</strong> Title and abstract of every paper are embedded with SPECTER2 (768 dimensions), a
            model trained on citation links between scientific papers.
        </li>
        <li>
            <strong>Projection.</strong> The embedding is reduced with PCA to 128 dimensions and then with UMAP to the two
            map coordinates. PCA and UMAP were fitted once and are kept fixed, so a new paper is placed on the same map
            as the existing ones and positions do not change between visits.
        </li>
    </ol>

    <h3>Reading the views</h3>
    <ul>
        <li>
            <strong>Subjects and categories:</strong> the area of a circle follows the number of papers of the dataset
            in that category. A category counts every paper listed in it, cross listed ones included; a subject counts
            every paper once, by its primary category.
        </li>
        <li>
            <strong>Paper map:</strong> one point per paper at its UMAP position. Distances are meaningful locally
            (close points are similar), the axes have no meaning. Point size follows the citation count (on arXiv and
            elsewhere), colour the paper's primary category or its year of publication. A category map shows the most
            cited papers first; the number of papers can be raised in the header. It can be limited to a range of years, and the
            play button next to the years shows the papers on the map in the order they were published.
        </li>
        <li>
            <strong>Topic names</strong> on the paper map are an aid for reading it, not part of the method. The papers
            shown are grouped by their position (k-means), and each group is named after the word or phrase that is
            frequent in its titles and rare in the rest of the map. After zooming in, the papers in view are grouped and
            named again, so the names become more specific. The names change with the papers shown and can be
            switched off in the header.
        </li>
        <li>
            <strong>Citations:</strong> a chart of the selected paper's references and the papers citing it: year of
            publication on the x axis, citation count (log scale) on the y axis. References are mostly left of the
            selected paper, citations right of it. The most cited papers of each group are shown first, the number can
            be raised in the header. Only papers in the dataset are drawn, the counts outside arXiv are listed in the
            details.
        </li>
        <li>
            <strong>Similar:</strong> the papers nearest to the selected one, drawn at their own map positions with
            the papers of the open category in grey behind them. Nearest means the smallest cosine distance between
            the 128-dimensional embeddings. Where the embedding of a paper is not in the database, the nearest papers
            on the two-dimensional map are shown instead, and the view says so. That is a rough guide only: the map keeps
            topic areas well, but of the ten most similar papers in the embedding fewer than one on average is also
            among the ten nearest on the map (see analysis/README.md in the repository). The tab offers two more ways
            that use the citations instead of the text: <em>shared references</em> lists papers citing the same papers
            (bibliographic coupling), <em>cited together</em> lists papers that later work cites alongside this one
            (co-citation). Both need at least two links in common and are ordered by the number of common links
            relative to the lengths of the two lists.
        </li>
    </ul>

    <div class="lang" role="group" aria-label="Language of the credits">
        <button class:active={lang === "en"} onclick={() => (lang = "en")}>EN</button>
        <button class:active={lang === "de"} onclick={() => (lang = "de")}>DE</button>
    </div>

    {#if lang === "de"}
        <p>
            Entwickelt wurde das Projekt von Nico Bestek, Nick Wittkowski, Lenio Cabral-Rosario und Bastian Rosinski im
            Rahmen des Softwarepraktikums 2025 an der Hochschule Bochum unter der Betreuung von Prof. Dr. Christian
            Scheffer und Jonas Friemel.
        </p>
        <p>
            Ein ganz besonderer Dank gilt dabei Jonas Friemel, der uns das gesamte Jahr über als direkter Ansprechpartner
            intensiv betreut hat. Er stand uns jederzeit mit Rat und Tat zur Seite und half uns, auch in stressigen Phasen
            stets einen kühlen Kopf zu bewahren.
        </p>
    {:else}
        <p>
            The project was developed by Nico Bestek, Nick Wittkowski, Lenio Cabral-Rosario and Bastian Rosinski as part
            of the 2025 Software Project at Bochum University of Applied Sciences, supervised by Prof. Dr. Christian
            Scheffer and Jonas Friemel.
        </p>
        <p>
            Special thanks go to Jonas Friemel, who supported us closely throughout the year as our direct contact. He was
            always there with advice and help and kept us calm in stressful phases.
        </p>
    {/if}

    {#snippet footer()}
        <span class="license">Licensed under AGPL v3</span>
        <a class="source" href="https://github.com/Monaa-Lisa/Monaa-Lisa" target="_blank" rel="noopener noreferrer">
            Source code
        </a>
    {/snippet}
</Dialog>

<style>
    p {
        margin: 0 0 12px;
        line-height: 1.6;
    }
    h3 {
        margin: 16px 0 6px;
        color: var(--text);
        font-size: var(--text-sm);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    ol,
    ul {
        margin: 0 0 12px;
        padding-left: 20px;
        line-height: 1.6;
    }
    li {
        margin-bottom: 6px;
    }
    strong {
        color: var(--text);
        font-weight: 600;
    }
    .lang {
        display: inline-flex;
        margin: 8px 0 12px;
        padding: 2px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
    }
    .lang button {
        padding: 2px 10px;
        border: 0;
        border-radius: var(--radius-sm);
        background: none;
        color: var(--text-3);
        font-size: var(--text-xs);
        font-weight: 500;
        cursor: pointer;
    }
    .lang button.active {
        background: var(--surface-3);
        color: var(--text);
    }
    .license {
        margin-right: auto;
        align-self: center;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .source {
        font-size: var(--text-sm);
    }
</style>
