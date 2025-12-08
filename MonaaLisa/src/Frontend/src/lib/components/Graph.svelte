<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { onMount } from 'svelte';
  import Graph from 'graphology';
  import Sigma from 'sigma';
  import type { Paper } from '$lib/types/paper';
  import { clusterColors as clusterCol } from '../../utils/clusterColors';

  /**
   * array of papers to display in the graph.
   * passed from the parent component.
   * @type {Paper[]}
   */
  export let papers: Paper[] = [];

  /**
   * id of the currently selected paper
   * used for external selection control
   * @type {string | null}
   */
  export let selectedPaperId: string | null = null;

  /**
   * flag to use dummy data for showcasing.
   * when true, uses dummypapers instead of the papers prop.
   * set to true for demo, false for real data.
   * @type {boolean}
   
  export let useDummyData: boolean = true;

  // DEMO-ONLY: easy-to-remove organic layout pass to make dummy clusters look organic (no FA2).
  // Remove by deleting this export and the block labeled "DEMO-ONLY ORGANIC LAYOUT" below.
  export let organicDemoLayout: boolean = true;

  // DEMO-ONLY: global compression factor (0..1). Lower brings clusters closer together.
  // Remove by deleting this export and the block labeled "DEMO-ONLY GLOBAL COMPRESSION" below.
  export let demoClusterCompression: number = 0.45;
*/
  //internal state variables for component management
  let container: HTMLDivElement | null = null;
  let selectedPaper: Paper | null = null;
  let selectedNode: string | null = null;
  let renderer: Sigma | null = null;
  let graph: Graph | null = null;

  //add cache for quick paper lookup
  let paperCache: Map<string, Paper> = new Map();

  //add debounce for hover
  let hoverTimeout: number | null = null;

  const dispatch = createEventDispatcher();

  //cluster color mapping for visual grouping
  //todo: figure out if we even need this later on or if cluster colors are static instead of dynamic
  /*const clusterCol: Record<string, string> = {
    A: '#CC6666',
    B: '#66B2B2',
    C: '#9966CC',
    D: '#CC66B2',
    E: '#6699CC',
    F: '#FF4500',
    G: '#00CED1',
  };*/

  /**
   * selects and highlights a node in the graph, updating visuals and connections.
   * clears edges, resets colors, highlights related nodes, adds edges, and zooms.
   * @param {string} nodeId - the id of the node to select.
   */
  function selectNodeById(nodeId: string) {
    if (!graph || !renderer || !graph.hasNode(nodeId)) return;

    //clear all edges to reset the view
    const edgesToRemove = graph!.edges();
    edgesToRemove.forEach((edge: string) => {
      graph!.dropEdge(edge);
    });

    //set all nodes to a semi-transparent black to help focus on selections
    graph!.forEachNode((n: string) => {
      graph!.setNodeAttribute(n, 'color', 'rgba(0, 0, 0, 0.25)');
    });

    //highlight selected node in green
    graph.setNodeAttribute(nodeId, 'color', '#00FF00');

    //retrieve paper data and collect only direct citations (no related or citing papers)
    const paper = (graph.getNodeAttributes(nodeId) as any).paper as Paper;
    selectedPaper = paper;
    const relatedNodes = new Set<string>(paper.citations);

    //highlight related nodes in yellow
    relatedNodes.forEach(relatedId => {
      if (graph!.hasNode(relatedId)) {
        graph!.setNodeAttribute(relatedId, 'color', '#FFFF00');
      }
    });

    //add edges only for citations
    //edges to cited papers
    paper.citations.forEach(citedId => {
      if (graph!.hasNode(citedId)) {
        graph!.addEdge(nodeId, citedId, {
          color: '#FFFFFF',
          size: 1.5
        });
      }
    });

    // *** FIXED ZOOM - CORRECT SIGMA.JS API ***
    const nodePosition = graph.getNodeAttributes(nodeId) as any;
    console.log('Zooming to node:', nodeId, 'Position:', nodePosition.x, nodePosition.y);
    
    const camera = renderer.getCamera();
    // TypeScript's AnimateOptions may not include x/y directly depending on the sigma types;
    // cast to any to allow passing x/y while keeping runtime behavior unchanged.
    camera.animatedReset({
      x: nodePosition.x,
      y: nodePosition.y,
      ratio: 0.5,  // Zoom in closer (smaller ratio = more zoomed)
      duration: 800
    } as any);

    selectedNode = nodeId;
    renderer.refresh();

    // *** CRITICAL: EMIT EVENT TO SIDEBAR ***
    dispatch('nodeSelected', nodeId);
    console.log('EMITTED nodeSelected:', nodeId);
  }

  //react to prop changes: update selection when selectedpaperid changes
  $: if (selectedPaperId && selectedPaperId !== selectedNode && graph && renderer) {
    console.log('Graph reacting to sidebar selection:', selectedPaperId);
    selectNodeById(selectedPaperId);
  }

  onMount(() => {
    //initialize graphology graph for data storage
    graph = new Graph();

    // no more dummy data :D
    const dataSource = papers;

    // compute inbound citation counts (times a paper is cited by others)
    const inDegree = new Map<string, number>();
    dataSource.forEach(p => inDegree.set(p.entry_id, 0));
    dataSource.forEach(p => {
      p.citations.forEach(cid => {
        if (inDegree.has(cid)) inDegree.set(cid, (inDegree.get(cid) || 0) + 1);
      });
    });
    let maxIn = 0;
    inDegree.forEach(v => { if (v > maxIn) maxIn = v; });
    const minSize = 1;
    const maxSize = 6;
    const sizeFor = (count: number) => {
      if (maxIn === 0) return minSize;
      const t = count / maxIn;
      return minSize + t * (maxSize - minSize);
    };

    //populate graph with nodes from the selected data source
    dataSource.forEach(paper => {
      
      const scaleFactor = 0.5; //adjust as needed for better spacing
      const scaledX = paper.tsne1 * scaleFactor;
      const scaledY = paper.tsne2 * scaleFactor;

      const inCitations = inDegree.get(paper.entry_id) || 0;
      const nodeSize = sizeFor(inCitations);

      graph!.addNode(paper.entry_id, {
        x: scaledX,
        y: scaledY,
        size: nodeSize,
        label: paper.title,
        color: clusterCol[paper.cluster] || '#999999',
        originalColor: clusterCol[paper.cluster] || '#999999',
        paper: paper,
        inCitations // extra attribute for debugging/inspection
      });

      //cache paper for fast lookup
      paperCache.set(paper.entry_id, paper);
    });

    //initialize sigma renderer for visualization
    if (container) {
      renderer = new Sigma(graph, container, {
        renderEdgeLabels: false,
        defaultNodeType: 'circle',
        defaultEdgeType: 'line',
        minCameraRatio: 0.1,
        maxCameraRatio: 10,
        //labels disabled for clarity; use sidebar/search instead
        renderLabels: false,
      });

      //handle node hover: show paper details with debounce
      renderer.on('enterNode', ({ node }: { node: string }) => {
        //clear previous timeout
        if (hoverTimeout) clearTimeout(hoverTimeout);
        
        //debounce: delay setting selectedPaper by 100ms
        hoverTimeout = setTimeout(() => {
          selectedPaper = paperCache.get(node) || null;
        }, 200) as unknown as number;
      });

      renderer.on('leaveNode', () => {
        //clear timeout and hide details
        if (hoverTimeout) clearTimeout(hoverTimeout);
        selectedPaper = null;
      });

      // *** FIXED CLICK HANDLER - NO DUPLICATE DISPATCH ***
      renderer.on('clickNode', ({ node }: { node: string }) => {
        console.log('🖱️ CLICKED NODE:', node);
        selectNodeById(node); // This emits the event internally
      });

      //handle stage click: deselect and reset view
      renderer.on('clickStage', () => {
        selectedNode = null;
        selectedPaper = null;

        //restore original node colors
        graph!.forEachNode((n: string) => {
          const originalColor = (graph!.getNodeAttributes(n) as any).originalColor;
          graph!.setNodeAttribute(n, 'color', originalColor);
        });

        //remove all edges
        const edgesToRemove = graph!.edges();
        edgesToRemove.forEach((edge: string) => {
          graph!.dropEdge(edge);
        });

        renderer!.getCamera().animatedReset({ duration: 800 });
        renderer!.refresh();

        dispatch('nodeDeselected');
        console.log('EMITTED nodeDeselected');
      });

      //cleanup: destroy renderer and clear cache on unmount
      return () => {
        if (renderer) renderer.kill();
        paperCache.clear();
      };
    }
  });
</script>

<style>
  .graph-container {
    width: 100%;
    height: 600px;
    border: none;
    background-color: #1e1e27;
  }

  .paper-details {
    position: absolute;
    top: 10px;
    right: 10px;
    background: rgba(255, 255, 255, 0.95);
    padding: 15px;
    border: 1px solid #34495e;
    border-radius: 8px;
    max-width: 300px;
    display: none;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    font-size: 14px;
  }

  .paper-details.visible {
    display: block;
  }

  .paper-details h3 {
    margin: 0 0 10px 0;
    color: #2c3e50;
    font-size: 16px;
  }

  .paper-details p {
    margin: 5px 0;
    color: #34495e;
  }
</style>

<div class="graph-container" bind:this={container}></div>

{#if selectedPaper}
  <div class="paper-details visible">
    <h3>{selectedPaper.title}</h3>
    <p><strong>authors:</strong> {selectedPaper.authors}</p>
    <p><strong>summary:</strong> {selectedPaper.summary}</p>
    <p><strong>published:</strong> {selectedPaper.published ? new Date(selectedPaper.published).toLocaleDateString() : 'Unbekannt'}</p>
    <p><strong>citations:</strong> {selectedPaper.citations.length}</p>
  </div>
{/if}