<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import Graph from 'graphology';
  import Sigma from 'sigma';
  import concaveman from 'concaveman';
  import type { Paper, Hull } from '$lib/types/paper';
  import { paperConnections } from '$lib/stores/paperConnections';
  import { getClusterColor } from '../utils/clusterColors';
  import { getCategoryCountryName } from '../utils/categoryCountries';

  export let papers: Paper[] = [];
  export let selectedPaperId: string | null = null;

  let container: HTMLDivElement | null = null;
  let hullCanvas: HTMLCanvasElement | null = null;
  let selectedPaper: Paper | null = null;
  let selectedNode: string | null = null;
  let renderer: Sigma | null = null;
  let graph: Graph | null = null;
  let pulseFrameId: number | null = null;
  let hulls: Hull[] = [];
  let hoverTimeout: ReturnType<typeof setTimeout> | null = null;

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

  function stopPulsing() {
    if (pulseFrameId) {
      cancelAnimationFrame(pulseFrameId);
      pulseFrameId = null;
    }
  }

  function startPulsing() {
    stopPulsing();
    const start = Date.now();

    const tick = () => {
      if (!graph || !renderer) return;

      const elapsed = Date.now() - start;
      const intensity = (Math.sin(elapsed / 300) + 1) / 2; // Slower, smoother pulse

      // Get zoom ratio to scale edges
      const cameraRatio = renderer.getCamera().getState().ratio;
      // Scale factor: grows when zoomed out, shrinks when zoomed in (clamped)
      const zoomScale = Math.max(0.3, Math.sqrt(Math.min(cameraRatio, 2)));

      let hasEdges = false;
      graph.forEachEdge((edge, attrs) => {
        hasEdges = true;

        // High dynamic range for alpha: 0.2 (dim) to 0.9 (bright)
        const alpha = 0.2 + (0.7 * intensity);
        // Dynamic thickness: 4 (base) to 8 (peak)
        const baseSize = 4 + (4 * intensity);

        if (attrs.isOutline) {
          graph!.setEdgeAttribute(edge, 'color', `rgba(0, 0, 0, ${alpha})`);
          graph!.setEdgeAttribute(edge, 'size', (baseSize + 5) * zoomScale);
        } else {
          const baseColor = attrs.baseColor || '0, 255, 255';
          graph!.setEdgeAttribute(edge, 'color', `rgba(${baseColor}, ${alpha})`);
          graph!.setEdgeAttribute(edge, 'size', baseSize * zoomScale);
        }
      });

      if (hasEdges) {
        renderer.refresh();
        pulseFrameId = requestAnimationFrame(tick);
      }
    };

    pulseFrameId = requestAnimationFrame(tick);
  }

  onDestroy(() => {
    stopPulsing();
  });

  async function selectNodeById(nodeId: string) {
    if (!graph || !renderer || !graph.hasNode(nodeId)) return;

    stopPulsing();
    resetVisuals();

    // Dim all nodes for focus mode
    graph.forEachNode((n) => {
      graph!.setNodeAttribute(n, 'color', 'rgba(0, 0, 0, 0.25)');
    });

    graph.setNodeAttribute(nodeId, 'color', '#00FF00');

    selectedPaper = graph.getNodeAttribute(nodeId, 'paper') as Paper;

    // Refresh renderer first to ensure node attributes (color) are updated visually
    selectedNode = nodeId;
    renderer.refresh();
    dispatch('nodeSelected', nodeId);

    // Get the actual displayed position from the renderer (safest source of truth for coordinates)
    const displayData = renderer.getNodeDisplayData(nodeId);

    if (displayData) {
        const camera = renderer.getCamera();
        const currentRatio = camera.getState().ratio;

        camera.animate(
          {
            x: displayData.x,
            y: displayData.y,
            ratio: Math.min(currentRatio, 0.15)
          },
          {
            duration: 800,
            easing: 'cubicInOut'
          }
        );
    } else {
        console.warn("Could not get display data for node:", nodeId);
    }

    try {
      // Use the store to fetch connections (shared with Sidebar)
      const { citations, references, relations } = await paperConnections.fetchConnections(nodeId);


      const processConnections = (items: { entry_id: string; paper?: Paper; type: string; raw?: any }[], type: string) => {
        const isCitation = type === 'citation';
        const isRelation = type === 'relation';
        // Citation: Yellow/Gold, Reference: Blue, Relation: Green
        const baseColor = isCitation ? '255, 215, 0' : (isRelation ? '50, 205, 50' : '30, 144, 255');
        const nodeColor = isCitation ? '#FFD700' : (isRelation ? '#32CD32' : '#1E90FF');

        items.forEach((item) => {
          const targetId = item.entry_id;

          if (graph?.hasNode(targetId) && targetId !== nodeId) {
             // avoid duplicate edges
             if (!graph?.hasEdge(nodeId, targetId) && !graph?.hasEdge(targetId, nodeId)) {
                // Add outline edge first
                graph?.addEdge(nodeId, targetId, {
                  size: 8,
                  color: '#000000',
                  type: 'line',
                  isOutline: true
                });

                // Add main edge with custom styling attributes
                graph?.addEdge(nodeId, targetId, {
                  size: 6, // Thicker base size for easier clicking
                  color: `rgba(${baseColor}, 1)`,
                  type: 'line',
                  baseColor: baseColor // used by startPulsing
                });

                // Highlight target node
                graph?.setNodeAttribute(targetId, 'color', nodeColor);
                // Make connected nodes slightly larger
                const currentSize = graph?.getNodeAttribute(targetId, 'size');
                if (typeof currentSize === 'number') {
                    graph?.setNodeAttribute(targetId, 'originalSize', currentSize);
                    graph?.setNodeAttribute(targetId, 'size', currentSize * 1.5);
                }
             }
          }
        });
      };

      processConnections(citations, 'citation');
      processConnections(references, 'reference');
      processConnections(relations, 'relation');

      if (graph.edges().length > 0) {
        startPulsing();
      }

    } catch (err) {
      console.error("Fehler beim Laden der Verbindungen:", err);
    }
  }

  /* --- Morphological Helper Functions --- */

  /**
   * Vergrössert die Menge von Punkten ausgehen vom Zentrum eines Polygons
   */
  function inflateAroundCenter(
    points: [number, number][],
    cx: number,
    cy: number,
    factor: number
  ) {
    return points.map(([x, y]) => {
      const dx = x - cx;
      const dy = y - cy;
      return [cx + dx * factor, cy + dy * factor] as [number, number];
    });
  }

  /**
   * Berechnet einen Skalierungsfaktor, damit die Hülle (Hull) alle Punkte
   * inklusive eines Sicherheitsabstands (Padding) umschließt.
   */
  function inflateToContainPadding(
    hull: [number, number][],
    points: { x: number; y: number }[],
    cx: number,
    cy: number,
    padding: number,
    maxFactor = 1.6
  ) {
    const maxPointR = Math.max(...points.map(p => Math.hypot(p.x - cx, p.y - cy)));
    const maxHullR  = Math.max(...hull.map(([x,y]) => Math.hypot(x - cx, y - cy))) || 1;

    const targetR = maxPointR + padding;
    const rawFactor = targetR / maxHullR;
    const factor = Math.min(Math.max(1, rawFactor), maxFactor);

    return inflateAroundCenter(hull, cx, cy, factor);
  }

  function clusterSpread(points: {x:number;y:number}[], cx:number, cy:number) {
    const meanSq = points.reduce((s, p) => s + (p.x - cx)**2 + (p.y - cy)**2, 0) / points.length;
    return Math.sqrt(meanSq);
  }

  /**
   * Chaikin Algorithmus um Ecken "abzurunden"
   */
  function chaikinSmooth(points: [number, number][], iterations = 2) {
    let pts = points;
    for (let k = 0; k < iterations; k++) {
      const res: [number, number][] = [];
      for (let i = 0; i < pts.length; i++) {
        const p0 = pts[i];
        const p1 = pts[(i + 1) % pts.length];
        // Q
        res.push([0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]]);
        // R
        res.push([0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]]);
      }
      pts = res;
    }
    return pts;
  }

  /* ------------------------------------- */

  function resetVisuals() {
    if (!graph) return;

    // Drop temporary edges
    graph.forEachEdge(edge => graph!.dropEdge(edge));

    // Reset nodes to original state
    graph.forEachNode(n => {
      const originalColor = graph!.getNodeAttribute(n, 'originalColor');
      if (originalColor) graph!.setNodeAttribute(n, 'color', originalColor);

      const originalSize = graph!.getNodeAttribute(n, 'originalSize');
      if (originalSize) {
        graph!.setNodeAttribute(n, 'size', originalSize);
        graph!.removeNodeAttribute(n, 'originalSize');
      }
    });
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
    graph = new Graph({ multi: true });
    const dataSource = papers.filter(p => !!p.entry_id);

    // Initialize the paper connections store with papers lookup
    paperConnections.setPapersLookup(dataSource);

    // Stub setup
    const inDegree = new Map<string, number>();
    dataSource.forEach(p => inDegree.set(p.entry_id!, 0));
    let maxIn = 0;

    const minSize = 3;  // Increased from 1 for better visibility/clicking
    const maxSize = 12; // Increased from 6 for better visibility/clicking
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


      if (!categoryPoints.has(cat)) {
        categoryPoints.set(cat, []);
      }
      categoryPoints.get(cat)!.push({x: finalX, y: finalY});
    });

    if (container) {
      renderer = new Sigma(graph, container, {
        renderEdgeLabels: false,
        defaultNodeType: 'circle',
        defaultEdgeType: 'line',
        minCameraRatio: 0.001,
        maxCameraRatio: 100,
        renderLabels: false,
        enableEdgeEvents: true,
        doubleClickZoomingRatio: 1,
      });

      renderer.on('enterNode', ({ node }) => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        hoverTimeout = setTimeout(() => {
          selectedPaper = graph?.getNodeAttribute(node, 'paper') as Paper || null;
        }, 200);
      });

      renderer.on('leaveNode', () => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        selectedPaper = null;
      });

      renderer.on('clickNode', ({ node }) => {
        selectNodeById(node);
      });

      renderer.on('clickEdge', ({ edge }) => {
        if (!graph) return;
        const [source, target] = graph.extremities(edge);
        if (selectedNode === source) {
            selectNodeById(target);
        } else {
            selectNodeById(source);
        }
      });

      // Native dblclick listener for reliable double-click detection on background
      const handleDoubleClick = () => {
        stopPulsing();
        selectedNode = null;
        selectedPaper = null;
        resetVisuals();

        // Just zoom out from current position, don't change x/y
        const camera = renderer!.getCamera();
        const currentState = camera.getState();
        camera.animate(
          { x: currentState.x, y: currentState.y, ratio: Math.min(currentState.ratio * 3, 1.5) },
          { duration: 500, easing: 'cubicInOut' }
        );

        renderer!.refresh();
        dispatch('nodeDeselected');
      };

      container.addEventListener('dblclick', handleDoubleClick);

      renderer.on('clickStage', () => {
        stopPulsing();
        selectedNode = null;
        selectedPaper = null;
        resetVisuals();
        renderer!.refresh();
        dispatch('nodeDeselected');
      });

      // Bind hull drawing to camera update
      const camera = renderer.getCamera();
      const hullDrawer = () => drawHulls(hulls); // Uses top-level `hulls` variable
      camera.on('updated', hullDrawer);

      const killRenderer = () => {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        container?.removeEventListener('dblclick', handleDoubleClick);
        if (renderer) {
          renderer.getCamera().off('updated', hullDrawer);
          renderer.kill();
        }
      };

      // Compute Hulls
      try {
        hulls = [];

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

          // 1) glätten
          let smoothHull = chaikinSmooth(hullPoints as [number, number][], 2);

          // 2) Padding dynamisch aus Spread (statt minOffset=35)
          const spread = clusterSpread(points, cx, cy);
          const padding = Math.max(20, spread * 0.35);

          // 3) aufblasen bis alle Punkte + padding "radial" reinpassen (mit cap)
          smoothHull = inflateToContainPadding(
            smoothHull,
            points,
            cx, cy,
            padding,
            1.6
          );

          const color = getClusterColor(cat, cat) || '#cccccc';

          hulls.push({
            path: smoothHull,
            color: color + '33',
            strokeColor: color + '66',
            label: getCategoryCountryName(cat),
            cx, cy
          });
        });


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