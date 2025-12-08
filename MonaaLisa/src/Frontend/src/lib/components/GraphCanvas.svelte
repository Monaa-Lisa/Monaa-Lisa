<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import Graph from 'graphology';
  import Sigma from 'sigma';

  export let data: any[]; // Dein Array von Papers aus Level 2

  const dispatch = createEventDispatcher();
  let container: HTMLElement;
  let renderer: Sigma;

  // Wenn sich die Daten ändern (z.B. Drill-down in neue Subcategory), Graph neu bauen
  $: if (data && container) {
    initGraph();
  }

  function initGraph() {
    // 1. Alten Renderer killen, falls vorhanden
    if (renderer) renderer.kill();
    if (!data) return;

    // 2. Graphology Instanz erstellen
    const graph = new Graph();

    // 3. Daten hinzufügen
    // Achtung: Sigma braucht IDs als Strings und x/y idealerweise im Bereich 0-1 oder skaliert
    // Da deine Daten sehr klein sind (0.05), multiplizieren wir sie vllt. mal mit 1000 für Sigma
    const SCALING_FACTOR = 1000;

    data.forEach(paper => {
      // Node hinzufügen
      graph.addNode(paper.id, {
        label: paper.title,
        x: paper.x * SCALING_FACTOR,
        y: paper.y * SCALING_FACTOR,
        size: 5, // Punktgröße
        color: "#fa5a5a", // Rote Punkte
        // Wir können auch die ganzen Paper-Daten hier speichern für Click-Events
        paperData: paper
      });
    });

    // Edges hinzufügen (nur wenn beide Enden existieren)
    data.forEach(paper => {
        if(paper.cites) {
            paper.cites.forEach((targetId: string) => {
                if(graph.hasNode(targetId)) {
                    // Verhindert doppelte Kanten
                    if (!graph.hasEdge(paper.id, targetId)) {
                        graph.addEdge(paper.id, targetId, {
                            color: "#ccc",
                            size: 1
                        });
                    }
                }
            });
        }
    });

    // 4. Sigma Renderer starten (WebGL Canvas)
    renderer = new Sigma(graph, container, {
      minCameraRatio: 0.1,
      maxCameraRatio: 10,
    });

    // 5. Events binden
    renderer.on("clickNode", (event) => {
      // event.node ist die ID, event.attributes sind die Daten
      const paper = graph.getNodeAttribute(event.node, "paperData");
      dispatch('paperClick', paper);
    });

    // Optional: Hover Effekt
    renderer.on("enterNode", (event) => {
        document.body.style.cursor = "pointer";
    });
    renderer.on("leaveNode", () => {
        document.body.style.cursor = "default";
    });
  }

  onDestroy(() => {
    if (renderer) renderer.kill();
  });
</script>

<div bind:this={container} style="width: 100%; height: 100%;"></div>