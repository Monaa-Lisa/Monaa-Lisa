<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';

  export let data: any;
  export let level: number;
  export let selectedPaper: any;

  const dispatch = createEventDispatcher();

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D;
  let width = 800;
  let height = 600;

  // --- ZOOM & PAN STATE ---
  let transform = { k: 1, x: 0, y: 0 }; // k=Zoomfaktor, x/y=Verschiebung
  let isDragging = false;
  let startDrag = { x: 0, y: 0 };

  // Konfiguration
  const ZOOM_THRESHOLD = 2.5; // Ab diesem Zoom-Level wird der Drilldown ausgelöst
  const MIN_ZOOM = 0.8;
  const MAX_ZOOM = 10;

  // Bounds (Daten-Bereich)
  let bounds = { minX: -1, maxX: 1, minY: -1, maxY: 1 };
  const PADDING = 40;

  onMount(() => {
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  });

  // Wenn neue Daten kommen (z.B. nach Drilldown), View resetten
  $: if (canvas && data) {
    calculateBounds();
    // Reset View bei Level-Wechsel, aber behalte Position, wenn wir tiefer gehen?
    // Fürs Erste: Reset, damit man das neue Level komplett sieht.
    resetView();
    render();
  }

  function resize() {
    if(!canvas) return;
    width = canvas.parentElement?.clientWidth || 800;
    height = canvas.parentElement?.clientHeight || 600;
    canvas.width = width;
    canvas.height = height;
    ctx = canvas.getContext('2d')!;
    render();
  }

  function resetView() {
    transform = { k: 1, x: 0, y: 0 };
  }

  function calculateBounds() {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    // Hilfsfunktion
    const update = (x: number, y: number) => {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    };

    if (level === 0 || level === 1) {
      const items = level === 0 ? data.categories : data.subcategories;
      if (items) {
        items.forEach((item: any) => {
          if (item.hull) item.hull.forEach(([x, y]: number[]) => update(x, y));
        });
      }
    } else {
        // Fallback für Level 2 (falls du das hier auch rendern willst)
        if(Array.isArray(data)) data.forEach((p:any) => update(p.x, p.y));
    }

    if (minX === Infinity) { minX = -1; maxX = 1; minY = -1; maxY = 1; }
    // Quadratische Bounds vermeiden Division durch Null
    if (maxX === minX) maxX += 0.1;
    if (maxY === minY) maxY += 0.1;

    bounds = { minX, maxX, minY, maxY };
  }

  // --- TRANSFORMATION ---
  // Wandelt Daten-Koordinaten in Screen-Koordinaten um (inkl. Zoom/Pan)
  function toScreen(x: number, y: number) {
    // 1. Normalisieren auf 0..1 (Basis-Koordinaten im Canvas)
    const normX = (x - bounds.minX) / (bounds.maxX - bounds.minX);
    const normY = (y - bounds.minY) / (bounds.maxY - bounds.minY);

    // 2. Auf Canvas-Größe projizieren (Y invertiert)
    const baseX = PADDING + normX * (width - 2 * PADDING);
    const baseY = height - (PADDING + normY * (height - 2 * PADDING));

    // 3. Zoom & Pan anwenden
    // Formel: screenX = baseX * k + transX
    const screenX = baseX * transform.k + transform.x;
    const screenY = baseY * transform.k + transform.y;

    return { x: screenX, y: screenY };
  }

  // Wandelt Screen-Mausposition zurück in Basis-Canvas-Koordinaten (für Zoom-Berechnung)
  // (Nicht Daten-Koordinaten, sondern "Pixel vor Zoom")
  function fromScreenToBase(screenX: number, screenY: number) {
      return {
          x: (screenX - transform.x) / transform.k,
          y: (screenY - transform.y) / transform.k
      };
  }

  // --- RENDERING ---
  function render() {
    if (!ctx) return;

    // Clear & Background
    ctx.fillStyle = "#f8f9fa";
    ctx.fillRect(0, 0, width, height);

    // Grid zeichnen (optional, hilft bei Zoom-Orientierung)
    drawGrid();

    if (level === 0 || level === 1) {
      const items = level === 0 ? data.categories : data.subcategories;
      if (items) items.forEach((item: any) => drawHull(item));
    }
  }

  function drawGrid() {
      ctx.strokeStyle = "rgba(0,0,0,0.05)";
      ctx.lineWidth = 1;
      const gridSize = 50 * transform.k;

      // Einfaches Grid basierend auf Offset
      const offsetX = transform.x % gridSize;
      const offsetY = transform.y % gridSize;

      ctx.beginPath();
      for(let x = offsetX; x < width; x += gridSize) { ctx.moveTo(x,0); ctx.lineTo(x,height); }
      for(let y = offsetY; y < height; y += gridSize) { ctx.moveTo(0,y); ctx.lineTo(width,y); }
      ctx.stroke();
  }

  function drawHull(item: any) {
    const color = level === 0 ? 'rgba(0, 100, 255, 0.15)' : 'rgba(0, 200, 100, 0.15)';
    const stroke = level === 0 ? '#0066cc' : '#009944';

    ctx.fillStyle = color;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2 * transform.k; // Linien werden dicker beim Reinzoomen? Oder konstant: 2
    // Besser konstant lassen:
    ctx.lineWidth = 2;

    ctx.beginPath();
    item.hull.forEach(([hx, hy]: number[], i: number) => {
      const { x, y } = toScreen(hx, hy);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Label
    if (item.name || item.id) {
        // Label Position berechnen
        const centerData = item.center ? item.center : item.hull[0];
        const pos = toScreen(centerData[0], centerData[1]);

        // Textgröße skaliert leicht mit, aber nicht linear
        const fontSize = Math.max(12, 10 * transform.k);

        ctx.fillStyle = '#333';
        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText(item.name || item.id, pos.x, pos.y);
    }
  }

  // --- INTERAKTION (Zoom & Pan & Drill) ---

  function handleWheel(e: WheelEvent) {
    e.preventDefault();

    const zoomIntensity = 0.1;
    const direction = e.deltaY > 0 ? -1 : 1; // Runter = Rauszoom, Hoch = Reinzoom
    const factor = 1 + direction * zoomIntensity;

    const mouseX = e.offsetX;
    const mouseY = e.offsetY;

    // Aktuelle "Welt"-Position unter der Maus merken
    const mouseBefore = fromScreenToBase(mouseX, mouseY);

    // Zoom anwenden
    let newK = transform.k * factor;
    newK = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newK));

    // Neue Verschiebung berechnen, damit Punkt unter der Maus stabil bleibt
    const newX = mouseX - mouseBefore.x * newK;
    const newY = mouseY - mouseBefore.y * newK;

    transform = { k: newK, x: newX, y: newY };

    // --- SEMANTIC ZOOM CHECK ---
    // Wenn wir tief genug drin sind, prüfen wir auf Drilldown
    if (transform.k > ZOOM_THRESHOLD && direction > 0) {
       checkZoomDrilldown(mouseX, mouseY);
    }

    render();
  }

  function handleMouseDown(e: MouseEvent) {
    isDragging = true;
    startDrag = { x: e.clientX - transform.x, y: e.clientY - transform.y };
  }

  function handleMouseMove(e: MouseEvent) {
    if (isDragging) {
      transform.x = e.clientX - startDrag.x;
      transform.y = e.clientY - startDrag.y;
      render();
    }
  }

  function handleMouseUp() {
    isDragging = false;
  }

  // Normaler Klick-Drilldown (als Alternative/Ergänzung)
  function handleClick(e: MouseEvent) {
     if (!isDragging) { // Nur wenn nicht gerade verschoben wurde
         checkZoomDrilldown(e.offsetX, e.offsetY, true);
     }
  }

  // Checkt, ob Drilldown nötig ist
  function checkZoomDrilldown(mx: number, my: number, forceClick = false) {
     const items = level === 0 ? data.categories : data.subcategories;
     if (!items) return;

     // Wir prüfen alle Hulls
     for (const item of items) {
         if (isPointInPoly(mx, my, item.hull)) {
             // Entweder Klickzwang ODER Zoom-Schwellenwert
             if (forceClick || transform.k > ZOOM_THRESHOLD) {
                 console.log("Drilldown Triggered:", item.id);
                 dispatch('drilldown', { id: item.id });
                 return; // Nur einer gleichzeitig
             }
         }
     }
  }

  // Point in Poly (angepasst an transformierte Koordinaten)
  function isPointInPoly(mx: number, my: number, hull: number[][]) {
    let inside = false;
    for (let i = 0, j = hull.length - 1; i < hull.length; j = i++) {
        // Hull-Punkte in Screen-Koordinaten umrechnen
        const pi = toScreen(hull[i][0], hull[i][1]);
        const pj = toScreen(hull[j][0], hull[j][1]);

        const xi = pi.x, yi = pi.y;
        const xj = pj.x, yj = pj.y;

        const intersect = ((yi > my) !== (yj > my)) && (mx < (xj - xi) * (my - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
  }

</script>

<canvas
  bind:this={canvas}
  on:wheel={handleWheel}
  on:mousedown={handleMouseDown}
  on:mousemove={handleMouseMove}
  on:mouseup={handleMouseUp}
  on:mouseleave={handleMouseUp}
  on:click={handleClick}
  style="display: block; width: 100%; height: 100%; cursor: grab;"
/>