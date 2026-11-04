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
    import { RotateCcw } from "@lucide/svelte";
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
        ctx.fillStyle = "#0c0c0e"; // --bg
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

            ctx.font = `600 16px 'IBM Plex Sans', system-ui, sans-serif`;
            ctx.fillStyle = "#ededf0";
            ctx.fillText(label, s.x, s.y - 14);

            if (showFull) {
                ctx.font = `12px 'IBM Plex Mono', ui-monospace, monospace`;
                ctx.fillStyle = "#8a8a94";
                ctx.fillText(fmtCount(c.count) + " papers", s.x, s.y + 14);
            }
        }

        // reset alpha and draw hovered label last so it's on top
        ctx.globalAlpha = 1.0;
        if (hoveredCluster) {
            const c = laid.find((x) => x.id === hoveredCluster);
            if (c) {
                const s = w2s(c.x, c.y);
                const label = c.name;

                ctx.font = `600 18px 'IBM Plex Sans', system-ui, sans-serif`;
                ctx.fillStyle = "#ffffff";
                ctx.fillText(label, s.x, s.y - 14);

                // the hovered cluster always shows its paper count
                ctx.font = `13px 'IBM Plex Mono', ui-monospace, monospace`;
                ctx.fillStyle = "#a6a6b0";
                ctx.fillText(fmtCount(c.count) + " papers", s.x, s.y + 14);
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


<div class="cluster-container">
    <canvas
        bind:this={canvasEl}
        on:mousedown={handleMouseDown}
        on:mousemove={handleCanvasMouseMove}
        on:mouseleave={handleMouseLeave}
        on:wheel|preventDefault={handleWheel}
    ></canvas>
    <div class="map-controls card">
        <div class="segmented" role="group" aria-label="Arrangement">
            <button
                class:active={layoutMode === "default"}
                aria-pressed={layoutMode === "default"}
                on:click={() => setLayoutMode("default")}
                title="Arranged for readability, positions do not carry meaning">Clear</button
            >
            <button
                class:active={layoutMode === "semantic"}
                aria-pressed={layoutMode === "semantic"}
                on:click={() => setLayoutMode("semantic")}
                title="Arranged by topic similarity: related fields sit close together">By similarity</button
            >
        </div>
        <span class="sep" aria-hidden="true"></span>
        <button class="icon-btn" on:click={resetView} title="Reset view" aria-label="Reset view">
            <RotateCcw size={16} />
        </button>
    </div>
</div>

<style>
    .cluster-container {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: var(--bg);
    }
    canvas {
        display: block;
        width: 100%;
        height: 100%;
        cursor: grab;
    }
    canvas:active {
        cursor: grabbing;
    }

    .map-controls {
        position: absolute;
        right: 12px;
        bottom: 12px;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 3px;
    }
    .segmented {
        display: flex;
        gap: 2px;
    }
    .segmented button,
    .icon-btn {
        height: 28px;
        padding: 0 12px;
        border: 0;
        border-radius: var(--radius);
        background: none;
        color: var(--text-3);
        font-size: var(--text-xs);
        font-weight: 500;
        cursor: pointer;
    }
    .segmented button:hover,
    .icon-btn:hover {
        color: var(--text);
    }
    .segmented button.active {
        background: var(--surface-3);
        color: var(--text);
    }
    .icon-btn {
        display: grid;
        place-items: center;
        width: 28px;
        padding: 0;
    }
    .sep {
        width: 1px;
        height: 16px;
        background: var(--border);
    }
</style>
