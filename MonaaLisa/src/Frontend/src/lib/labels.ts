/**
 * Places the titles of a Sigma view. The titles are HTML elements drawn over
 * the canvas (see .node-label in app.css), which lets them sit left or right
 * of a point and fade with an ellipsis. Candidates are tried in order of
 * importance and a title is kept when its box on screen fits the stage,
 * keeps clear of the overlays (legend, zoom buttons) and does not touch a
 * title placed before. Zooming in frees room, so more titles appear.
 */
import type Sigma from "sigma";

export interface LabelCandidate {
    id: string;
    label: string;
}

export interface PlacedLabel {
    id: string;
    label: string;
    /** Left edge and vertical centre of the title box, in px inside the stage */
    x: number;
    y: number;
    width: number;
}

export interface LabelPlacer {
    /** `limit` lowers the number of titles for this call */
    place(ranked: LabelCandidate[], limit?: number): PlacedLabel[];
}

/** Must match .node-label in app.css */
export const LABEL_FONT = '500 11px "IBM Plex Sans", system-ui, sans-serif';
export const LABEL_MAX_WIDTH = 320;
const LABEL_HEIGHT = 16;
const GAP = 5;
/** Free space kept around every title, so the map does not turn into a wall of text */
const MARGIN_X = 6;
const MARGIN_Y = 3;
/** A title may cover at most this many other points, crowded spots stay readable */
const MAX_COVERED_POINTS = 1;
/** The selected paper's title is shortened rather than dropped, down to this width */
const MIN_PRIMARY_WIDTH = 90;

/** [left, top, right, bottom] in px inside the stage */
export type Box = [number, number, number, number];

const overlaps = (a: Box, b: Box) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

export function createLabelPlacer(renderer: Sigma, maxLabels = 60, obstacles: () => Box[] = () => []): LabelPlacer {
    const context = document.createElement("canvas").getContext("2d");
    const widths = new Map<string, number>();
    const width = (label: string) => {
        let w = widths.get(label);
        if (w === undefined) {
            if (context) {
                context.font = LABEL_FONT;
                w = context.measureText(label).width;
            } else {
                w = label.length * 6.2;
            }
            w = Math.min(Math.ceil(w) + 4, LABEL_MAX_WIDTH);
            widths.set(label, w);
        }
        return w;
    };

    return {
        place(ranked, limit = maxLabels) {
            const { width: stageWidth, height: stageHeight } = renderer.getDimensions();
            const blocked = obstacles();
            const taken: Box[] = [];

            // screen positions of all points, binned so a box only checks its neighbourhood
            const CELL = 32;
            const grid = new Map<string, [number, number][]>();
            renderer.getGraph().forEachNode((node) => {
                const d = renderer.getNodeDisplayData(node);
                if (!d || d.hidden) return;
                const v = renderer.framedGraphToViewport(d);
                if (v.x < 0 || v.y < 0 || v.x > stageWidth || v.y > stageHeight) return;
                const key = `${Math.floor(v.x / CELL)},${Math.floor(v.y / CELL)}`;
                const cell = grid.get(key);
                if (cell) cell.push([v.x, v.y]);
                else grid.set(key, [[v.x, v.y]]);
            });
            const covered = (b: Box) => {
                let n = 0;
                for (let cx = Math.floor(b[0] / CELL); cx <= Math.floor(b[2] / CELL); cx++) {
                    for (let cy = Math.floor(b[1] / CELL); cy <= Math.floor(b[3] / CELL); cy++) {
                        for (const [x, y] of grid.get(`${cx},${cy}`) ?? []) {
                            if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) n++;
                        }
                    }
                }
                return n;
            };
            const placed: PlacedLabel[] = [];
            const padded = (b: Box): Box => [b[0] - MARGIN_X, b[1] - MARGIN_Y, b[2] + MARGIN_X, b[3] + MARGIN_Y];
            const free = (box: Box) =>
                box[0] >= 0 &&
                box[2] <= stageWidth &&
                box[1] >= 0 &&
                box[3] <= stageHeight &&
                !blocked.some((b) => overlaps(b, box)) &&
                !taken.some((b) => overlaps(b, box));

            for (const [rank, { id, label }] of ranked.entries()) {
                if (placed.length >= limit) break;
                const data = renderer.getNodeDisplayData(id);
                if (!data || data.hidden) continue;
                const p = renderer.framedGraphToViewport(data);
                if (p.x < 0 || p.y < 0 || p.x > stageWidth || p.y > stageHeight) continue;
                const size = renderer.scaleSize(data.size);
                const half = LABEL_HEIGHT / 2;
                const box = (side: "left" | "right", w: number): Box =>
                    side === "right"
                        ? [p.x + size + GAP, p.y - half, p.x + size + GAP + w, p.y + half]
                        : [p.x - size - GAP - w, p.y - half, p.x - size - GAP, p.y + half];

                let w = width(label);
                let chosen: Box | null = null;
                for (const side of ["right", "left"] as const) {
                    const b = box(side, w);
                    if (free(b) && (rank === 0 || covered(b) <= MAX_COVERED_POINTS)) {
                        chosen = b;
                        break;
                    }
                }
                // the selected paper always gets its title, shortened to the wider side
                if (!chosen && rank === 0) {
                    // free room on both sides, up to the stage edge or an overlay on that line
                    const sameLine = blocked.filter((b) => b[1] < p.y + half && b[3] > p.y - half);
                    const rightEdge = Math.min(stageWidth, ...sameLine.filter((b) => b[0] > p.x).map((b) => b[0]));
                    const leftEdge = Math.max(0, ...sameLine.filter((b) => b[2] < p.x).map((b) => b[2]));
                    const roomRight = rightEdge - (p.x + size + GAP) - 4;
                    const roomLeft = p.x - size - GAP - leftEdge - 4;
                    const side = roomRight >= Math.min(w, roomLeft) ? "right" : "left";
                    w = Math.max(MIN_PRIMARY_WIDTH, Math.min(w, side === "right" ? roomRight : roomLeft));
                    chosen = box(side, w);
                }
                if (!chosen) continue;
                taken.push(padded(chosen));
                placed.push({ id, label, x: chosen[0], y: p.y, width: w });
            }
            return placed;
        },
    };
}

/**
 * Boxes of the overlays drawn over a map (legend, zoom buttons), relative to
 * the map's canvas element, so titles are not placed underneath them.
 */
export function overlayBoxes(canvas: HTMLElement, selector = ".legend, .zoom"): Box[] {
    const root = canvas.parentElement;
    if (!root) return [];
    const origin = canvas.getBoundingClientRect();
    return [...root.querySelectorAll<HTMLElement>(selector)].map((el) => {
        const r = el.getBoundingClientRect();
        return [r.left - origin.left - 4, r.top - origin.top - 4, r.right - origin.left + 4, r.bottom - origin.top + 4];
    });
}
