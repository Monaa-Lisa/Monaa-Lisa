/**
 * Picks which nodes of a Sigma view carry their title. Sigma itself only
 * avoids overlaps for labels it chooses, not for forced ones, so the choice
 * is made here: candidates are tried in order of importance and a title is
 * kept when its box on screen does not overlap a title placed before.
 * Zooming in frees room, so more titles appear.
 */
import type Sigma from "sigma";

export interface LabelCandidate {
    id: string;
    label: string;
}

export interface LabelPlacer {
    place(ranked: LabelCandidate[]): Set<string>;
}

export function createLabelPlacer(renderer: Sigma, font: string, maxLabels = 40): LabelPlacer {
    const context = document.createElement("canvas").getContext("2d");
    const widths = new Map<string, number>();
    const width = (label: string) => {
        let w = widths.get(label);
        if (w === undefined) {
            if (context) {
                context.font = font;
                w = context.measureText(label).width;
            } else {
                w = label.length * 6.2;
            }
            widths.set(label, w);
        }
        return w;
    };

    return {
        place(ranked) {
            const { width: stageWidth, height: stageHeight } = renderer.getDimensions();
            const boxes: [number, number, number, number][] = [];
            const chosen = new Set<string>();
            for (const [rank, { id, label }] of ranked.entries()) {
                if (chosen.size >= maxLabels) break;
                const data = renderer.getNodeDisplayData(id);
                if (!data || data.hidden) continue;
                const p = renderer.framedGraphToViewport(data);
                if (p.x < 0 || p.y < 0 || p.x > stageWidth || p.y > stageHeight) continue;
                const size = renderer.scaleSize(data.size);
                // sigma draws the label to the right of the node, vertically centred
                const w = width(label);
                const box: [number, number, number, number] = [p.x - size - 2, p.y - 9, p.x + size + 6 + w, p.y + 9];
                // a title may run off the right edge a little, the first one (the selected paper) always shows
                if (rank > 0 && box[2] > stageWidth + 0.4 * w) continue;
                if (boxes.some((b) => b[0] < box[2] && box[0] < b[2] && b[1] < box[3] && box[1] < b[3])) continue;
                boxes.push(box);
                chosen.add(id);
            }
            return chosen;
        },
    };
}

export function sameSet(a: Set<string>, b: Set<string>): boolean {
    if (a.size !== b.size) return false;
    for (const value of a) if (!b.has(value)) return false;
    return true;
}
