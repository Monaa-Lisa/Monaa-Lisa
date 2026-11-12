<!--
  ClusterGraph.svelte

  Draws the top-level and sub-level category "blob" clusters on an HTML canvas.
  Uses a particle system to fill cluster territories with glowing dots.
  Pan/zoom: click-drag to pan, scroll-wheel to zoom.
  Clicking a cluster dispatches the 'clusterClick' event with the cluster's id/name/color.
-->
<script lang="ts">
    import { onMount, createEventDispatcher } from "svelte";
    import type { ClusterNode } from "$lib/types/paper";
    import { EdgeAnimator } from "./edgeAnimation";
    // UMAP coordinate data for semantic layout
    import rawUmapLocs from "../utils/cluster-locations.json";
    const UMAP_LOCS: Record<string, { x: number; y: number }> = {
        ...(rawUmapLocs as any).top,
        ...(rawUmapLocs as any).sub,
    };

    /** Array of clusters to visualise. */
    export let clusters: ClusterNode[] = [];
    /** If set, subcategory colours are derived from this parent colour. */
    export let parentColor: string | null = null;

    let canvasEl: HTMLCanvasElement;
    let canvasW = 0;
    let canvasH = 0;
    let dpr = 1;
    let hoveredCluster: string | null = null;
    // ─── layout mode: 'default' = ellipse/phyllotaxis, 'semantic' = UMAP positions ─
    const LAYOUT_MODE_KEY = "monaalisa-layout-mode";
    let layoutMode: "default" | "semantic" =
        (typeof localStorage !== "undefined" &&
            (localStorage.getItem(LAYOUT_MODE_KEY) as
                | "default"
                | "semantic"
                | null)) ||
        "default";
    // tooltip visibility for the info (ⓘ) button
    let showLayoutInfo = false;

    const dispatch = createEventDispatcher();

    // ─── colour palette for top-level categories ──────────────────────
    const CATEGORY_COLORS: Record<string, string> = {
        physics: "#4361ee",
        computer_science: "#f72585",
        mathematics: "#4cc9f0",
        statistics: "#7209b7",
        electrical_engineering: "#ff7a18",
        quantitative_biology: "#2ec4b6",
        quantitative_finance: "#ffd166",
        economics: "#e71d36",
    };

    // ─── types ────────────────────────────────────────────────────────
    interface LayoutCluster extends ClusterNode {
        x: number;
        y: number;
        radius: number;
        color: string;
    }
    interface Transform {
        scale: number;
        offsetX: number;
        offsetY: number;
    }

    // ─── view state (pan / zoom) ──────────────────────────────────────
    let view: Transform = { scale: 1, offsetX: 0, offsetY: 0 };
    let initialView: Transform = { scale: 1, offsetX: 0, offsetY: 0 };

    // drag state
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartOffsetX = 0;
    let dragStartOffsetY = 0;

    // zoom animation
    let zoomAnim = {
        active: false,
        start: { scale: 1, offsetX: 0, offsetY: 0 } as Transform,
        end: { scale: 1, offsetX: 0, offsetY: 0 } as Transform,
        startTime: 0,
        duration: 700,
        callback: null as (() => void) | null,
    };

    // layout data
    let laid: LayoutCluster[] = [];
    let particles: Particle[] = [];
    let edgeAnimator: EdgeAnimator | null = null;
    let animFrameId = 0;

    // ─── colour helpers ───────────────────────────────────────────────
    function assignColor(c: ClusterNode, idx: number): string {
        if (parentColor) return shiftHue(parentColor, idx * 28);
        return CATEGORY_COLORS[c.id] ?? hslColor(idx, clusters.length);
    }

    function hslColor(i: number, total: number): string {
        const h = (i / Math.max(total, 1)) * 360;
        return `hsl(${h}, 65%, 55%)`;
    }

    function shiftHue(hex: string, deg: number): string {
        let r = parseInt(hex.slice(1, 3), 16) / 255;
        let g = parseInt(hex.slice(3, 5), 16) / 255;
        let b = parseInt(hex.slice(5, 7), 16) / 255;
        const max = Math.max(r, g, b),
            min = Math.min(r, g, b);
        let h = 0,
            s = 0;
        const l = (max + min) / 2;
        if (max !== min) {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
            else if (max === g) h = ((b - r) / d + 2) / 6;
            else h = ((r - g) / d + 4) / 6;
        }
        h = (((h + deg / 360) % 1) + 1) % 1;
        const sat = Math.min(s * 1.05, 1);
        const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat;
        const p = 2 * l - q;
        const h2r = (pp: number, qq: number, t: number) => {
            t = ((t % 1) + 1) % 1;
            if (t < 1 / 6) return pp + (qq - pp) * 6 * t;
            if (t < 0.5) return qq;
            if (t < 2 / 3) return pp + (qq - pp) * (2 / 3 - t) * 6;
            return pp;
        };
        const nr = Math.round(h2r(p, q, h + 1 / 3) * 255);
        const ng = Math.round(h2r(p, q, h) * 255);
        const nb = Math.round(h2r(p, q, h - 1 / 3) * 255);
        return (
            "#" +
            [nr, ng, nb].map((v) => v.toString(16).padStart(2, "0")).join("")
        );
    }

    function hexToRgb(hex: string): [number, number, number] {
        return [
            parseInt(hex.slice(1, 3), 16),
            parseInt(hex.slice(3, 5), 16),
            parseInt(hex.slice(5, 7), 16),
        ];
    }

    // ─── top-level category angles (degrees clockwise from top) ───────
    // physics at top, quant_finance next to economics,
    // statistics between economics and mathematics
    const CAT_ANGLES: Record<string, number> = {
        physics: 0,
        computer_science: 50,
        mathematics: 100,
        statistics: 148,
        economics: 196,
        quantitative_finance: 222,
        quantitative_biology: 275,
        electrical_engineering: 325,
    };

    // ─── layout ───────────────────────────────────────────────────────
    function computeLayout(): LayoutCluster[] {
        if (!clusters.length) return [];
        if (layoutMode === "semantic") return computeUmapLayout();
        return computeDefaultLayout();
    }

    /** Default ellipse (top-level) / phyllotaxis (sub-level) arrangement. */
    function computeDefaultLayout(): LayoutCluster[] {
        if (!clusters.length) return [];
        const sorted = [...clusters].sort((a, b) => b.count - a.count);
        const maxCount = sorted[0].count;
        const aspect = canvasW && canvasH ? canvasW / canvasH : 16 / 9;
        const sqA = Math.sqrt(Math.max(0.5, Math.min(aspect, 2.5)));

        if (!parentColor) {
            // Top-level: elliptical arrangement matching screen aspect ratio
            const Rx = 240 * sqA;
            const Ry = 240 / sqA;
            return sorted.map((c, i) => {
                const deg = CAT_ANGLES[c.id];
                let x: number, y: number;
                if (deg !== undefined) {
                    const rad = (deg * Math.PI) / 180;
                    x = Rx * Math.sin(rad);
                    y = -Ry * Math.cos(rad);
                } else {
                    const GA = Math.PI * (3 - Math.sqrt(5));
                    const r = 180 * Math.sqrt(i + 1);
                    x = r * Math.cos(i * GA) * sqA;
                    y = (r * Math.sin(i * GA)) / sqA;
                }
                return {
                    ...c,
                    x,
                    y,
                    radius: 55 + 110 * Math.sqrt(c.count / maxCount),
                    color: assignColor(c, i),
                };
            });
        } else {
            // Subcategory: tighter phyllotaxis with aspect correction
            const GA = Math.PI * (3 - Math.sqrt(5));
            const BASE =
                clusters.length <= 6 ? 150 : clusters.length <= 12 ? 110 : 90;
            return sorted.map((c, i) => {
                const r = BASE * Math.sqrt(i + 1);
                const theta = i * GA;
                return {
                    ...c,
                    x: r * Math.cos(theta) * sqA,
                    y: (r * Math.sin(theta)) / sqA,
                    radius: 40 + 95 * Math.sqrt(c.count / maxCount),
                    color: assignColor(c, i),
                };
            });
        }
    }

    /**
     * UMAP layout: positions clusters at their pre-computed semantic coordinates.
     * After placing them, a push-apart pass ensures no more than slight border overlap.
     */
    function computeUmapLayout(): LayoutCluster[] {
        if (!clusters.length) return [];
        const sorted = [...clusters].sort((a, b) => b.count - a.count);
        const maxCount = sorted[0].count;

        // Build mutable positioned array
        const placed: LayoutCluster[] = sorted.map((c, i) => {
            const pos = UMAP_LOCS[c.id];
            return {
                ...c,
                x: pos ? pos.x : (i - sorted.length / 2) * 80,
                y: pos ? pos.y : 0,
                radius: !parentColor
                    ? 55 + 110 * Math.sqrt(c.count / maxCount)
                    : 40 + 95 * Math.sqrt(c.count / maxCount),
                color: assignColor(c, i),
            };
        });

        // Push-apart: allow slight overlap at the circle border (10% overlap max)
        // Iterate several times so clusters cascade‐push each other.
        const MAX_OVERLAP_RATIO = 0.8; // allow touching up to 90% of sum of radii
        for (let iter = 0; iter < 60; iter++) {
            for (let i = 0; i < placed.length; i++) {
                for (let j = i + 1; j < placed.length; j++) {
                    const ci = placed[i];
                    const cj = placed[j];
                    const dx = cj.x - ci.x;
                    const dy = cj.y - ci.y;
                    const d = Math.sqrt(dx * dx + dy * dy) || 0.001;
                    const minD = (ci.radius + cj.radius) * MAX_OVERLAP_RATIO;
                    if (d < minD) {
                        const push = (minD - d) / 2;
                        const ux = (dx / d) * push;
                        const uy = (dy / d) * push;
                        ci.x -= ux;
                        ci.y -= uy;
                        cj.x += ux;
                        cj.y += uy;
                    }
                }
            }
        }

        return placed;
    }

    function computeInitialView(
        laid: LayoutCluster[],
        W: number,
        H: number,
    ): Transform {
        if (!laid.length) return { scale: 1, offsetX: W / 2, offsetY: H / 2 };
        const pad = 60;
        const xs = laid
            .map((c) => [c.x - c.radius - pad, c.x + c.radius + pad])
            .flat();
        const ys = laid
            .map((c) => [c.y - c.radius - pad, c.y + c.radius + pad])
            .flat();
        const minX = Math.min(...xs),
            maxX = Math.max(...xs);
        const minY = Math.min(...ys),
            maxY = Math.max(...ys);
        const scale = Math.min(W / (maxX - minX), H / (maxY - minY)) * 1.1;
        return {
            scale,
            offsetX: W / 2 - ((minX + maxX) / 2) * scale,
            offsetY: H / 2 - ((minY + maxY) / 2) * scale,
        };
    }

    // ─── coordinate transforms ────────────────────────────────────────
    function w2s(wx: number, wy: number): { x: number; y: number } {
        return {
            x: wx * view.scale + view.offsetX,
            y: wy * view.scale + view.offsetY,
        };
    }

    function s2w(sx: number, sy: number): { x: number; y: number } {
        return {
            x: (sx - view.offsetX) / view.scale,
            y: (sy - view.offsetY) / view.scale,
        };
    }

    // ─── deterministic particle generator ─────────────────────────────
    interface Particle {
        wx: number;
        wy: number;
        size: number;
        ci: number;
    }

    function generateParticles(laid: LayoutCluster[]): Particle[] {
        let seed = 12345;
        const rng = () => {
            seed = (seed * 16807) % 2147483647;
            return (seed - 1) / 2147483646;
        };
        const ps: Particle[] = [];
        laid.forEach((c, ci) => {
            const n = Math.max(100, Math.min(700, Math.sqrt(c.count) * 1.1));
            for (let i = 0; i < n; i++) {
                const a = rng() * Math.PI * 2;
                const r = Math.sqrt(rng()) * c.radius * 0.88;
                ps.push({
                    wx: c.x + Math.cos(a) * r,
                    wy: c.y + Math.sin(a) * r,
                    size: 0.8 + rng() * 2.0,
                    ci,
                });
            }
        });
        return ps;
    }

    // ─── rebuild layout (resets view) ─────────────────────────────────
    function rebuild(W: number, H: number) {
        laid = computeLayout();
        particles = generateParticles(laid);
        initialView = computeInitialView(laid, W, H);
        view = { ...initialView };
        if (edgeAnimator) {
            edgeAnimator.updateClusters(laid);
        } else {
            edgeAnimator = new EdgeAnimator(laid);
        }
    }

    // ─── animation helpers ────────────────────────────────────────────
    function lerp(a: number, b: number, t: number): number {
        return a + (b - a) * t;
    }
    function easeInOutCubic(t: number): number {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    // ─── rendering ────────────────────────────────────────────────────
    function draw() {
        if (!canvasEl) return;
        const ctx = canvasEl.getContext("2d");
        if (!ctx) return;

        // handle zoom animation
        if (zoomAnim.active) {
            const elapsed = Date.now() - zoomAnim.startTime;
            const t = Math.min(elapsed / zoomAnim.duration, 1);
            const e = easeInOutCubic(t);
            view = {
                scale: lerp(zoomAnim.start.scale, zoomAnim.end.scale, e),
                offsetX: lerp(zoomAnim.start.offsetX, zoomAnim.end.offsetX, e),
                offsetY: lerp(zoomAnim.start.offsetY, zoomAnim.end.offsetY, e),
            };
            if (t >= 1) {
                zoomAnim.active = false;
                if (zoomAnim.callback) {
                    const cb = zoomAnim.callback;
                    zoomAnim.callback = null;
                    cb();
                }
            }
        }

        // clear with DPR-aware transform
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = "#0F1020";
        ctx.fillRect(0, 0, canvasW, canvasH);
        if (!laid.length) return;

        // draw edges
        edgeAnimator?.update(Date.now());
        edgeAnimator?.draw(ctx, view);

        // ── territory glows (smooth radial gradients) ──
        laid.forEach((c) => {
            const s = w2s(c.x, c.y);
            const sr = c.radius * view.scale;
            const [r, g, b] = hexToRgb(c.color);
            const hov = hoveredCluster === c.id;

            // outer ambient glow
            const outerR = sr * 1.6;
            const outerGrad = ctx.createRadialGradient(
                s.x,
                s.y,
                0,
                s.x,
                s.y,
                outerR,
            );
            outerGrad.addColorStop(
                0,
                `rgba(${r},${g},${b},${hov ? 0.22 : 0.11})`,
            );
            outerGrad.addColorStop(
                0.5,
                `rgba(${r},${g},${b},${hov ? 0.1 : 0.05})`,
            );
            outerGrad.addColorStop(1, `rgba(${r},${g},${b},0)`);
            ctx.fillStyle = outerGrad;
            ctx.beginPath();
            ctx.arc(s.x, s.y, outerR, 0, Math.PI * 2);
            ctx.fill();

            // inner core glow
            const coreR = sr * 0.6;
            const coreGrad = ctx.createRadialGradient(
                s.x,
                s.y,
                0,
                s.x,
                s.y,
                coreR,
            );
            coreGrad.addColorStop(
                0,
                `rgba(${r},${g},${b},${hov ? 0.14 : 0.07})`,
            );
            coreGrad.addColorStop(1, `rgba(${r},${g},${b},0)`);
            ctx.fillStyle = coreGrad;
            ctx.beginPath();
            ctx.arc(s.x, s.y, coreR, 0, Math.PI * 2);
            ctx.fill();
        });

        // ── subtle territory ring borders ──
        laid.forEach((c) => {
            const s = w2s(c.x, c.y);
            const sr = c.radius * view.scale;
            const hov = hoveredCluster === c.id;
            ctx.strokeStyle = c.color + (hov ? "65" : "18");
            ctx.lineWidth = hov ? 1.5 : 0.8;
            ctx.beginPath();
            ctx.arc(s.x, s.y, sr * 0.92, 0, Math.PI * 2);
            ctx.stroke();
        });

        // ── particles ──
        const rgbCache = new Map<number, [number, number, number]>();
        particles.forEach((p) => {
            if (!rgbCache.has(p.ci))
                rgbCache.set(p.ci, hexToRgb(laid[p.ci].color));
            const [r, g, b] = rgbCache.get(p.ci)!;
            const hov = hoveredCluster === laid[p.ci].id;
            ctx.fillStyle = `rgba(${r},${g},${b},${hov ? 0.85 : 0.5})`;
            const s = w2s(p.wx, p.wy);
            const sz = Math.max(p.size * Math.sqrt(view.scale), 0.5);
            ctx.beginPath();
            ctx.arc(s.x, s.y, sz, 0, Math.PI * 2);
            ctx.fill();
        });

        // ── labels ──
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.shadowColor = "rgba(0,0,0,0.9)";
        ctx.shadowBlur = 8;

        const dimOthers = hoveredCluster !== null;

        // draw non-hovered labels first (possibly dimmed)
        ctx.globalAlpha = dimOthers ? 0.5 : 1.0;
        for (const c of laid) {
            if (c.id === hoveredCluster) continue;
            const s = w2s(c.x, c.y);
            const showFull = view.scale >= LABEL_FULL_SCALE;
            const label = showFull ? c.name : abbrevName(c.name);

            ctx.font = `bold ${18}px 'Segoe UI', system-ui, sans-serif`;
            ctx.fillStyle = "#e0e0e0";
            ctx.fillText(label, s.x, s.y - 14);

            if (showFull) {
                ctx.font = `13px 'Segoe UI', system-ui, sans-serif`;
                ctx.fillStyle = "#888888";
                ctx.fillText(fmtCount(c.count) + " papers", s.x, s.y + 14);
            }
        }

        // reset alpha and draw hovered label last so it's on top
        ctx.globalAlpha = 1.0;
        if (hoveredCluster) {
            const c = laid.find((x) => x.id === hoveredCluster);
            if (c) {
                const s = w2s(c.x, c.y);
                const showFull = view.scale >= LABEL_FULL_SCALE || true; // hover always shows full
                const label = c.name;

                ctx.font = `bold ${21}px 'Segoe UI', system-ui, sans-serif`;
                ctx.fillStyle = "#ffffff";
                ctx.fillText(label, s.x, s.y - 14);

                if (showFull) {
                    ctx.font = `15px 'Segoe UI', system-ui, sans-serif`;
                    ctx.fillStyle = "#cccccc";
                    ctx.fillText(fmtCount(c.count) + " papers", s.x, s.y + 14);
                }
            }
        }

        ctx.shadowBlur = 0;
    }

    function fmtCount(n: number): string {
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
        if (n >= 1_000) return Math.round(n / 1_000) + "K";
        return String(n);
    }

    // label display: show abbreviation when zoomed out, full name when zoomed in
    const LABEL_FULL_SCALE = 0.9; // >= show full name, < show abbreviation (tweakable)
    // zoom limits
    const MIN_SCALE = 0.38; // how far out the user can zoom (prevents zooming out too far)
    const MAX_SCALE = 20;
    // At this zoom level, check if a cluster fills the screen enough to auto-drill in
    const AUTO_DRILL_SCALE = 9.0;
    // Minimum fraction of shorter canvas edge that a cluster must fill to trigger auto-drill
    const AUTO_DRILL_FILL = 0.4;
    // Prevents auto-drill from firing multiple times
    let autoDrillPending = false;
    let autoDrillTimeout: ReturnType<typeof setTimeout> | null = null;

    function abbrevName(name: string): string {
        if (!name) return "";
        // normalize separators to spaces and split
        const parts = name.replace(/[_-]+/g, " ").trim().split(/\s+/);
        if (parts.length > 1) {
            // take first letter of up to 3 parts
            return parts
                .slice(0, 3)
                .map((p) => p[0]?.toUpperCase() ?? "")
                .join("");
        }
        // single word: take first 3 letters
        return name.slice(0, 3).toUpperCase();
    }

    // ─── hit-testing (Euclidean) ──────────────────────────────────────
    function hitTest(sx: number, sy: number): LayoutCluster | null {
        if (!laid.length) return null;
        const w = s2w(sx, sy);
        let minD = Infinity,
            best: LayoutCluster | null = null;
        for (const c of laid) {
            const dx = w.x - c.x,
                dy = w.y - c.y;
            const d = Math.sqrt(dx * dx + dy * dy) / c.radius;
            if (d < minD && d < 1.3) {
                minD = d;
                best = c;
            }
        }
        return best;
    }

    // ─── zoom animation ──────────────────────────────────────────────
    function animateZoomTo(target: LayoutCluster) {
        const targetScale = Math.min(canvasW, canvasH) / (target.radius * 3.5);
        zoomAnim = {
            active: true,
            start: { ...view },
            end: {
                scale: targetScale,
                offsetX: canvasW / 2 - target.x * targetScale,
                offsetY: canvasH / 2 - target.y * targetScale,
            },
            startTime: Date.now(),
            duration: 700,
            callback: () => {
                dispatch("clusterClick", {
                    id: target.id,
                    name: target.name,
                    color: target.color,
                });
            },
        };
    }

    function resetView() {
        zoomAnim = {
            active: true,
            start: { ...view },
            end: { ...initialView },
            startTime: Date.now(),
            duration: 500,
            callback: null,
        };
    }

    // ─── events: pan / zoom / hover ───────────────────────────────────
    function handleMouseDown(e: MouseEvent) {
        if (zoomAnim.active) return;
        e.preventDefault();
        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        dragStartOffsetX = view.offsetX;
        dragStartOffsetY = view.offsetY;
        canvasEl.style.cursor = "grabbing";
        window.addEventListener("mousemove", handleDragMove);
        window.addEventListener("mouseup", handleDragEnd);
    }

    function handleDragMove(e: MouseEvent) {
        view = {
            ...view,
            offsetX: dragStartOffsetX + (e.clientX - dragStartX),
            offsetY: dragStartOffsetY + (e.clientY - dragStartY),
        };
    }

    function handleDragEnd(e: MouseEvent) {
        window.removeEventListener("mousemove", handleDragMove);
        window.removeEventListener("mouseup", handleDragEnd);
        isDragging = false;
        const dx = Math.abs(e.clientX - dragStartX);
        const dy = Math.abs(e.clientY - dragStartY);
        // treat as click if movement was minimal
        if (dx < 4 && dy < 4) {
            const rect = canvasEl.getBoundingClientRect();
            const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
            if (hit) animateZoomTo(hit);
        }
        updateCursor(e);
    }

    function handleCanvasMouseMove(e: MouseEvent) {
        if (isDragging) return;
        const rect = canvasEl.getBoundingClientRect();
        const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
        const newId = hit?.id ?? null;
        if (newId !== hoveredCluster) {
            hoveredCluster = newId;
            canvasEl.style.cursor = hoveredCluster ? "pointer" : "grab";
        }
    }

    function handleWheel(e: WheelEvent) {
        e.preventDefault();
        if (zoomAnim.active) return;
        const rect = canvasEl.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const factor = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(
            MIN_SCALE,
            Math.min(view.scale * factor, MAX_SCALE),
        );
        const ratio = newScale / view.scale;
        view = {
            scale: newScale,
            offsetX: mx - (mx - view.offsetX) * ratio,
            offsetY: my - (my - view.offsetY) * ratio,
        };
        // Check whether the user has zoomed deep enough into a single cluster to auto-drill
        checkAutoDrill();
    }

    /**
     * If the user has zoomed in past AUTO_DRILL_SCALE and a cluster fills most of the
     * visible canvas, dispatch a clusterClick after a short debounce delay so the
     * user has time to see the zoom-in animation before the view transitions.
     */
    function checkAutoDrill() {
        if (view.scale < AUTO_DRILL_SCALE) {
            // Below threshold - cancel any pending drill
            if (autoDrillTimeout) {
                clearTimeout(autoDrillTimeout);
                autoDrillTimeout = null;
            }
            autoDrillPending = false;
            return;
        }
        if (autoDrillPending) return; // already scheduled
        // Find the cluster closest to the canvas centre
        const cx = canvasW / 2;
        const cy = canvasH / 2;
        const w = s2w(cx, cy);
        let best: LayoutCluster | null = null;
        let bestD = Infinity;
        for (const c of laid) {
            const dx = w.x - c.x;
            const dy = w.y - c.y;
            const d = Math.sqrt(dx * dx + dy * dy);
            if (d < bestD && d < c.radius * 1.5) {
                bestD = d;
                best = c;
            }
        }
        if (!best) return;
        const screenR = best.radius * view.scale;
        if (screenR > Math.min(canvasW, canvasH) * AUTO_DRILL_FILL) {
            autoDrillPending = true;
            autoDrillTimeout = setTimeout(() => {
                autoDrillPending = false;
                autoDrillTimeout = null;
                if (best)
                    dispatch("clusterClick", {
                        id: best.id,
                        name: best.name,
                        color: best.color,
                    });
            }, 450); // short delay so the zoom animation is visible before transition
        }
    }

    function handleMouseLeave() {
        if (!isDragging) {
            hoveredCluster = null;
            canvasEl.style.cursor = "grab";
        }
    }

    function updateCursor(e: MouseEvent) {
        const rect = canvasEl.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        if (mx >= 0 && mx < canvasW && my >= 0 && my < canvasH) {
            const hit = hitTest(mx, my);
            hoveredCluster = hit?.id ?? null;
            canvasEl.style.cursor = hit ? "pointer" : "grab";
        }
    }

    // ─── lifecycle ────────────────────────────────────────────────────
    onMount(() => {
        dpr = window.devicePixelRatio || 1;

        const resize = () => {
            const newW = canvasEl.offsetWidth;
            const newH = canvasEl.offsetHeight;
            canvasEl.width = newW * dpr;
            canvasEl.height = newH * dpr;

            if (laid.length && canvasW > 0) {
                // keep center stable on resize - don't reset user's pan/zoom
                view = {
                    ...view,
                    offsetX: view.offsetX + (newW - canvasW) / 2,
                    offsetY: view.offsetY + (newH - canvasH) / 2,
                };
                initialView = computeInitialView(laid, newW, newH);
            } else {
                rebuild(newW, newH);
            }
            canvasW = newW;
            canvasH = newH;
        };

        const ro = new ResizeObserver(resize);
        ro.observe(canvasEl);
        resize();
        canvasEl.style.cursor = "grab";

        // animation loop
        const animate = () => {
            draw();
            animFrameId = requestAnimationFrame(animate);
        };
        animFrameId = requestAnimationFrame(animate);

        return () => {
            ro.disconnect();
            cancelAnimationFrame(animFrameId);
            window.removeEventListener("mousemove", handleDragMove);
            window.removeEventListener("mouseup", handleDragEnd);
        };
    });

    // rebuild layout when clusters change (new view level)
    $: clustersChanged(clusters);
    function clustersChanged(_: ClusterNode[]) {
        if (!canvasEl || canvasW <= 0) return;
        rebuild(canvasW, canvasH);
    }

    /** Toggle between default and semantic (UMAP) layout; rebuilds and persists. */
    function setLayoutMode(mode: "default" | "semantic") {
        if (layoutMode === mode) return;
        layoutMode = mode;
        if (typeof localStorage !== "undefined")
            localStorage.setItem(LAYOUT_MODE_KEY, mode);
        if (canvasEl && canvasW > 0) rebuild(canvasW, canvasH);
    }
</script>

<svelte:window
    on:click={() => {
        if (showLayoutInfo) showLayoutInfo = false;
    }}
/>

<div class="cluster-container">
    <canvas
        bind:this={canvasEl}
        on:mousedown={handleMouseDown}
        on:mousemove={handleCanvasMouseMove}
        on:mouseleave={handleMouseLeave}
        on:wheel|preventDefault={handleWheel}
    ></canvas>
    <button class="reset-btn" on:click={resetView} title="Reset view"
        >&#x27F2;</button
    >

    <!-- Layout-mode toggle - bottom left, styled like the citation-graph tab buttons -->
    <div class="layout-controls">
        <div class="layout-toggle">
            <button
                class="layout-btn"
                class:active={layoutMode === "default"}
                on:click={() => setLayoutMode("default")}
                title="Default arrangement">Default</button
            >
            <button
                class="layout-btn"
                class:active={layoutMode === "semantic"}
                on:click={() => setLayoutMode("semantic")}
                title="Semantic arrangement based on UMAP coordinates"
                >Semantic</button
            >
        </div>
        <!-- info button -->
        <button
            class="layout-info-btn"
            class:active={showLayoutInfo}
            on:click|stopPropagation={() => (showLayoutInfo = !showLayoutInfo)}
            title="About these views"
            aria-label="Layout mode info">i</button
        >
    </div>
    {#if showLayoutInfo}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="layout-info-tooltip" on:click|stopPropagation>
            <button
                class="layout-info-close"
                on:click={() => (showLayoutInfo = false)}
                aria-label="Close">✕</button
            >
            <p>
                <strong>Semantic</strong><br />Displays the clusters as close as
                possible to their semantic similarity without ruining
                visibility.
            </p>
            <p>
                <strong>Default</strong><br />Positions the clusters in an
                aesthetically pleasing way, ignoring similarity.
            </p>
        </div>
    {/if}
</div>

<style>
    .cluster-container {
        width: 100%;
        height: 100%;
        position: relative;
        overflow: hidden;
    }
    canvas {
        width: 100%;
        height: 100%;
        display: block;
        background: var(--bg-primary, #0f1020);
    }
    .reset-btn {
        position: absolute;
        bottom: 16px;
        right: 16px;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        border: 1px solid var(--border-subtle, rgba(147, 51, 234, 0.18));
        background: var(--glass-bg, rgba(20, 22, 50, 0.55));
        backdrop-filter: blur(var(--glass-blur, 16px));
        color: var(--text-secondary, #a8a8c8);
        font-size: 20px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10;
        transition: all
            var(--transition-smooth, 0.3s cubic-bezier(0.4, 0, 0.2, 1));
        box-shadow: 0 0 10px rgba(147, 51, 234, 0.1);
    }
    .reset-btn:hover {
        background: rgba(147, 51, 234, 0.25);
        color: #fff;
        border-color: rgba(147, 51, 234, 0.4);
        box-shadow: 0 0 20px rgba(147, 51, 234, 0.3);
    }

    /* ── Layout-mode toggle (bottom-left, mirrors PaperDetailGraph tab-btn style) ── */
    .layout-controls {
        position: absolute;
        bottom: 16px;
        left: 16px;
        display: flex;
        align-items: center;
        gap: 6px;
        z-index: 10;
    }
    .layout-toggle {
        display: flex;
        gap: 2px;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
        padding: 3px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .layout-btn {
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        border-radius: 6px;
        padding: 5px 14px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    .layout-btn.active {
        /* Match .tab-btn.active from PaperDetailGraph */
        background: linear-gradient(
            135deg,
            rgba(147, 51, 234, 0.35),
            rgba(232, 57, 160, 0.25)
        );
        color: var(--text-primary, #f0f0f8);
        box-shadow: 0 0 12px rgba(147, 51, 234, 0.2);
    }
    .layout-btn:hover:not(.active) {
        background: rgba(255, 255, 255, 0.05);
        color: var(--text-secondary, #a8a8c8);
    }

    /* ── Info button ── */
    .layout-info-btn {
        width: 26px;
        height: 26px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(0, 0, 0, 0.3);
        color: var(--text-muted, #6b6b8d);
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        transition: all 0.15s ease;
        line-height: 1;
    }
    .layout-info-btn.active,
    .layout-info-btn:hover {
        background: rgba(147, 51, 234, 0.25);
        color: #e0e0f8;
        border-color: rgba(147, 51, 234, 0.4);
    }

    /* ── Info tooltip ── */
    .layout-info-tooltip {
        position: absolute;
        bottom: 56px;
        left: 16px;
        width: 260px;
        background: rgba(14, 16, 36, 0.96);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(147, 51, 234, 0.28);
        border-radius: 10px;
        padding: 14px 14px 12px;
        z-index: 20;
        box-shadow:
            0 4px 24px rgba(0, 0, 0, 0.45),
            0 0 16px rgba(147, 51, 234, 0.12);
        font-size: 12px;
        line-height: 1.55;
        color: var(--text-secondary, #a8a8c8);
    }
    .layout-info-tooltip p {
        margin: 0 0 8px;
    }
    .layout-info-tooltip p:last-child {
        margin-bottom: 0;
    }
    .layout-info-tooltip strong {
        color: var(--text-primary, #f0f0f8);
        font-weight: 600;
    }
    .layout-info-close {
        float: right;
        margin: -4px -4px 6px 8px;
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
        cursor: pointer;
        padding: 2px 4px;
        border-radius: 4px;
        line-height: 1;
    }
    .layout-info-close:hover {
        color: #e0e0f8;
        background: rgba(255, 255, 255, 0.06);
    }
</style>
