/**
 * Packs circles whose area is proportional to a value into one compact
 * cluster. Greedy: circles are placed largest first, each one as close to the
 * centre as possible without overlapping a placed one. `aspect` stretches the
 * cluster horizontally so it fills a landscape view.
 */
export interface Bubble<T> {
    item: T;
    x: number;
    y: number;
    r: number;
}

export function packCircles<T>(items: T[], value: (item: T) => number, aspect = 1.4): Bubble<T>[] {
    const sorted = [...items].filter((i) => value(i) > 0).sort((a, b) => value(b) - value(a));
    if (!sorted.length) return [];
    const max = value(sorted[0]);
    // the smallest circle keeps a quarter of the largest radius, so its name still fits
    const radius = (item: T) => 0.26 + 0.74 * Math.sqrt(value(item) / max);
    const GAP = 0.05;
    const STEPS = 48;

    const placed: Bubble<T>[] = [];
    for (const item of sorted) {
        const r = radius(item);
        if (!placed.length) {
            placed.push({ item, x: 0, y: 0, r });
            continue;
        }
        let best: { x: number; y: number } | null = null;
        let bestScore = Infinity;
        for (const p of placed) {
            const d = p.r + r + GAP;
            for (let k = 0; k < STEPS; k++) {
                const a = (k / STEPS) * Math.PI * 2;
                const x = p.x + Math.cos(a) * d;
                const y = p.y + Math.sin(a) * d;
                const score = (x / aspect) ** 2 + y ** 2;
                if (score >= bestScore) continue;
                const free = placed.every((q) => Math.hypot(q.x - x, q.y - y) >= q.r + r + GAP - 1e-9);
                if (free) {
                    best = { x, y };
                    bestScore = score;
                }
            }
        }
        placed.push({ item, x: best?.x ?? 0, y: best?.y ?? 0, r });
    }
    return placed;
}
