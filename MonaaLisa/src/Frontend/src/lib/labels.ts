/**
 * Places the titles of a Sigma view. The titles are HTML elements drawn over
 * the canvas (see .node-label in app.css), which lets them sit left or right
 * of a point and fade with an ellipsis. Candidates are tried in order of
 * importance and a title is kept when its box on screen fits the stage and
 * does not overlap a title placed before. Zooming in frees room, so more
 * titles appear.
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
    place(ranked: LabelCandidate[]): PlacedLabel[];
}

/** Must match .node-label in app.css */
export const LABEL_FONT = '500 11px "IBM Plex Sans", system-ui, sans-serif';
export const LABEL_MAX_WIDTH = 320;
const LABEL_HEIGHT = 16;
const GAP = 5;

type Box = [number, number, number, number];

const overlaps = (a: Box, b: Box) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

export function createLabelPlacer(renderer: Sigma, maxLabels = 60): LabelPlacer {
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
        place(ranked) {
            const { width: stageWidth, height: stageHeight } = renderer.getDimensions();
            const boxes: Box[] = [];
            const placed: PlacedLabel[] = [];
            for (const [rank, { id, label }] of ranked.entries()) {
                if (placed.length >= maxLabels) break;
                const data = renderer.getNodeDisplayData(id);
                if (!data || data.hidden) continue;
                const p = renderer.framedGraphToViewport(data);
                if (p.x < 0 || p.y < 0 || p.x > stageWidth || p.y > stageHeight) continue;
                const size = renderer.scaleSize(data.size);
                const w = width(label);
                const half = LABEL_HEIGHT / 2;
                const right: Box = [p.x + size + GAP, p.y - half, p.x + size + GAP + w, p.y + half];
                const left: Box = [p.x - size - GAP - w, p.y - half, p.x - size - GAP, p.y + half];
                for (const box of [right, left]) {
                    // the first candidate (the selected paper) may run off the stage, the rest must fit
                    if (rank > 0 && (box[0] < 0 || box[2] > stageWidth)) continue;
                    if (boxes.some((b) => overlaps(b, box))) continue;
                    boxes.push(box);
                    placed.push({ id, label, x: box[0], y: p.y, width: w });
                    break;
                }
            }
            return placed;
        },
    };
}
