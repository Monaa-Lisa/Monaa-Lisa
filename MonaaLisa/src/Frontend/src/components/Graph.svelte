<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import Graph from 'graphology';
  import Sigma from 'sigma';
  import concaveman from 'concaveman';
  import type { Paper } from '$lib/types/paper';
  import { getClusterColor } from '../utils/clusterColors';
  import { getCategoryCountryName } from '../utils/categoryCountries';

  /**
   * array of papers to display in the graph.
   * passed from the parent component.
   */
  export let papers: Paper[] = [];
  export let selectedPaperId: string | null = null;

  //internal state variables for component management
  let container: HTMLDivElement | null = null;
  let hullCanvas: HTMLCanvasElement | null = null;
  let selectedPaper: Paper | null = null;
  let selectedNode: string | null = null;
  let renderer: Sigma | null = null;
  let graph: Graph | null = null;

  // Hulls state variable (promoted to top-level so listeners can access it)
  let hulls: any[] = [];

  //add cache for quick paper lookup
  let paperCache: Map<string, Paper> = new Map();
  //add debounce for hover
  let hoverTimeout: number | null = null;

  const dispatch = createEventDispatcher();
  const FALLBACK_NODE_COLOR = '#999999';

  function getPaperCoords(p: Paper): {x: number, y: number} {
    if (!p.tsne) return { x: 0, y: 0 };
    if (Array.isArray(p.tsne)) {
      return { x: p.tsne[0], y: p.tsne[1] };
    } else if ('x' in p.tsne) {
      return { x: p.tsne.x, y: p.tsne.y };
    } else if ('tsne1' in p.tsne) {
      return { x: p.tsne.tsne1, y: p.tsne.tsne2 };
    }
    return { x: 0, y: 0 };
  }

  function selectNodeById(nodeId: string) {
    if (!graph || !renderer || !graph.hasNode(nodeId)) return;

    const edgesToRemove = graph.edges();
    edgesToRemove.forEach((edge) => graph!.dropEdge(edge));

    graph.forEachNode((n) => {
      graph!.setNodeAttribute(n, 'color', 'rgba(0, 0, 0, 0.25)');
    });

    graph.setNodeAttribute(nodeId, 'color', '#00FF00');

    const paper = graph.getNodeAttribute(nodeId, 'paper') as Paper;
    selectedPaper = paper;

    const nodePosition = graph.getNodeAttributes(nodeId);
    const camera = renderer.getCamera();
    camera.animatedReset({
      x: nodePosition.x,
      y: nodePosition.y,
      ratio: 0.5,
      duration: 800
    } as any);

    selectedNode = nodeId;
    renderer.refresh();
    dispatch('nodeSelected', nodeId);
  }

  $: if (selectedPaperId && selectedPaperId !== selectedNode && graph && renderer) {
    selectNodeById(selectedPaperId);
  }

  function drawHulls(hullsToDraw: any[]) {
    if (!hullCanvas || !renderer) return;
    const ctx = hullCanvas.getContext('2d');
    if (!ctx) return;

    if (hullCanvas.width !== hullCanvas.offsetWidth || hullCanvas.height !== hullCanvas.offsetHeight) {
      hullCanvas.width = hullCanvas.offsetWidth;
      hullCanvas.height = hullCanvas.offsetHeight;
    }

    ctx.clearRect(0, 0, hullCanvas.width, hullCanvas.height);

    hullsToDraw.forEach(hull => {
      if (!hull.path || hull.path.length < 3) return;

      ctx.beginPath();
      hull.path.forEach((pt: [number, number], i: number) => {
        // Essential: map graph coordinates to current viewport coordinates (handles zoom/pan)
        const pos = renderer!.graphToViewport({x: pt[0], y: pt[1]});
        if (i === 0) ctx.moveTo(pos.x, pos.y);
        else ctx.lineTo(pos.x, pos.y);
      });
      ctx.closePath();
      ctx.fillStyle = hull.color;
      ctx.fill();
      ctx.strokeStyle = hull.strokeColor;
      ctx.lineWidth = 2;
      ctx.stroke();

      const center = renderer!.graphToViewport({x: hull.cx, y: hull.cy});
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 14px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = 'black';
      ctx.shadowBlur = 4;
      ctx.fillText(hull.label, center.x, center.y);
      ctx.shadowBlur = 0;
    });
  }

  onMount(() => {
    console.log("Graph Component Mounting...");
    graph = new Graph();
    const dataSource = papers.filter(p => !!p.entry_id);

    // Stub setup
    const inDegree = new Map<string, number>();
    dataSource.forEach(p => inDegree.set(p.entry_id!, 0));
    let maxIn = 0;

    const minSize = 1;
    const maxSize = 6;
    const sizeFor = (count: number) => {
      if (maxIn === 0) return minSize;
      const t = count / maxIn;
      return minSize + t * (maxSize - minSize);
    };

    const categoryPoints = new Map<string, {x: number, y: number}[]>();
    const papersByCategory = new Map<string, Paper[]>();
    const categoryCentroids = new Map<string, {x: number, y: number}>();

    dataSource.forEach(p => {
      const cat = p.category || 'Unknown';
      if (!papersByCategory.has(cat)) papersByCategory.set(cat, []);
      papersByCategory.get(cat)!.push(p);
    });

    papersByCategory.forEach((papers, cat) => {
      let sumX = 0, sumY = 0;
      papers.forEach(p => {
        const coords = getPaperCoords(p);
        sumX += coords.x;
        sumY += coords.y;
      });
      categoryCentroids.set(cat, { x: sumX / papers.length, y: sumY / papers.length });
    });

    const categories = Array.from(papersByCategory.keys()).sort();
    const territoryCenters = new Map<string, {x: number, y: number}>();
    const SPACING_FACTOR = 400;
    const ANGLE_INCREMENT = 137.5 * (Math.PI / 180);

    categories.forEach((cat, i) => {
      const r = SPACING_FACTOR * Math.sqrt(i + 1);
      const theta = i * ANGLE_INCREMENT;
      territoryCenters.set(cat, {
        x: r * Math.cos(theta),
        y: r * Math.sin(theta)
      });
    });

    dataSource.forEach(paper => {
      const entryId = paper.entry_id!;
      const cat = paper.category || 'Unknown';
      const centroid = categoryCentroids.get(cat) || {x: 0, y: 0};
      const territory = territoryCenters.get(cat) || {x: 0, y: 0};

      const LOCAL_SCALE = 20.0;
      const coords = getPaperCoords(paper);
      const localX = (coords.x - centroid.x) * LOCAL_SCALE;
      const localY = (coords.y - centroid.y) * LOCAL_SCALE;
      const finalX = territory.x + localX;
      const finalY = territory.y + localY;

      const inCitations = inDegree.get(entryId) || 0;
      const nodeSize = sizeFor(inCitations);
      const nodeColor = getClusterColor(paper.category, paper.cluster) ?? FALLBACK_NODE_COLOR;

      graph!.addNode(entryId, {
        x: finalX,
        y: finalY,
        size: nodeSize,
        label: paper.title,
        color: nodeColor,
        originalColor: nodeColor,
        paper: paper,
        inCitations
      });

      paperCache.set(entryId, paper);

      if (!categoryPoints.has(cat)) {
        categoryPoints.set(cat, []);
      }
      categoryPoints.get(cat)!.push({x: finalX, y: finalY});
    });

    if (container) {
      console.log("Initializing Sigma Renderer...");
      renderer = new Sigma(graph, container, {
        renderEdgeLabels: false,
        defaultNodeType: 'circle',
        defaultEdgeType: 'line',
        minCameraRatio: 0.001,
        maxCameraRatio: 100,
        renderLabels: false,
      });

      renderer.on('enterNode', ({ node }) => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        hoverTimeout = setTimeout(() => {
          selectedPaper = paperCache.get(node) || null;
        }, 200) as unknown as number;
      });

      renderer.on('leaveNode', () => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        selectedPaper = null;
      });

      renderer.on('clickNode', ({ node }) => {
        selectNodeById(node);
      });

      renderer.on('clickStage', () => {
        selectedNode = null;
        selectedPaper = null;
        graph!.forEachNode((n) => {
          const originalColor = graph!.getNodeAttribute(n, 'originalColor');
          graph!.setNodeAttribute(n, 'color', originalColor);
        });
        const edgesToRemove = graph!.edges();
        edgesToRemove.forEach((edge) => graph!.dropEdge(edge));
        renderer!.getCamera().animatedReset({ duration: 800 });
        renderer!.refresh();
        dispatch('nodeDeselected');
      });

      // Bind hull drawing to camera update
      const camera = renderer.getCamera();
      const hullDrawer = () => drawHulls(hulls); // Uses top-level `hulls` variable
      camera.on('updated', hullDrawer);

      const killRenderer = () => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        if (renderer) {
          renderer.getCamera().off('updated', hullDrawer);
          renderer.kill();
        }
        paperCache.clear();
      };

      // Compute Hulls
      try {
        console.log("Computing Hulls...");
        hulls = []; // Reset the top-level variable

        categoryPoints.forEach((points, cat) => {
          if (points.length < 3) return;

          const cx = points.reduce((sum, p) => sum + p.x, 0) / points.length;
          const cy = points.reduce((sum, p) => sum + p.y, 0) / points.length;

          const withDist = points.map(p => ({
            p,
            dist: (p.x - cx)**2 + (p.y - cy)**2
          }));
          withDist.sort((a, b) => a.dist - b.dist);
          const keepCount = Math.ceil(points.length * 0.98);

          if (keepCount < 3) return;

          const keptPoints = withDist.slice(0, keepCount).map(item => [item.p.x, item.p.y] as [number, number]);

          let hullPoints;
          if (typeof concaveman === 'function') {
            hullPoints = concaveman(keptPoints, 1.0);
          } else if ((concaveman as any).default) {
            hullPoints = (concaveman as any).default(keptPoints, 1.0);
          } else {
            console.warn("Concaveman not found or invalid type", concaveman);
            return;
          }

          const color = getClusterColor(cat, cat) || '#cccccc';

          hulls.push({
            path: hullPoints,
            color: color + '33',
            strokeColor: color + '66',
            label: getCategoryCountryName(cat),
            cx, cy
          });
        });

        console.log(`Generated ${hulls.length} hulls.`);

        // Initial draw
        setTimeout(() => drawHulls(hulls), 100);

      } catch (e) {
        console.error("Error generating hulls:", e);
      }

      return killRenderer;
    }
  });
</script>

<style>
  .graph-container {
    width: 100%;
    height: 600px;
    border: none;
    background-color: #1e1e27;
    position: relative;
  }

  canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
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
    z-index: 10;
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

<div class="graph-container" bind:this={container}>
  <canvas bind:this={hullCanvas}></canvas>
</div>

{#if selectedPaper}
  <div class="paper-details visible">
    <h3>{selectedPaper.title}</h3>
    <p><strong>authors:</strong> {selectedPaper.authors}</p>
    <p><strong>summary:</strong> {selectedPaper.summary}</p>
    <p><strong>published:</strong> {selectedPaper.published ? new Date(selectedPaper.published).toLocaleDateString() : 'Unbekannt'}</p>
  </div>
{/if}
