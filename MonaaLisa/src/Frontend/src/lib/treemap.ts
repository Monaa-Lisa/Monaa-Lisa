/**
 * Squarified treemap layout (Bruls, Huizing, van Wijk 2000): fills a
 * rectangle with tiles whose area is proportional to a value, keeping the
 * tiles close to square so labels fit.
 */
export interface Tile<T> {
    item: T;
    x: number;
    y: number;
    width: number;
    height: number;
}

interface Row<T> {
    items: { item: T; area: number }[];
    area: number;
}

function worstRatio<T>(row: Row<T>, side: number): number {
    if (!row.items.length || side === 0) return Infinity;
    const areas = row.items.map((r) => r.area);
    const max = Math.max(...areas);
    const min = Math.min(...areas);
    const s2 = row.area * row.area;
    const w2 = side * side;
    return Math.max((w2 * max) / s2, s2 / (w2 * min));
}

export function squarify<T>(
    items: T[],
    value: (item: T) => number,
    width: number,
    height: number,
): Tile<T>[] {
    const sorted = [...items].filter((i) => value(i) > 0).sort((a, b) => value(b) - value(a));
    const total = sorted.reduce((sum, i) => sum + value(i), 0);
    if (!sorted.length || total <= 0 || width <= 0 || height <= 0) return [];

    const scale = (width * height) / total;
    const tiles: Tile<T>[] = [];
    let x = 0;
    let y = 0;
    let w = width;
    let h = height;
    let row: Row<T> = { items: [], area: 0 };

    const layoutRow = () => {
        const horizontal = w >= h; // a row runs along the shorter side
        const side = horizontal ? h : w;
        const thickness = row.area / side;
        let offset = 0;
        for (const { item, area } of row.items) {
            const length = area / thickness;
            tiles.push(
                horizontal
                    ? { item, x, y: y + offset, width: thickness, height: length }
                    : { item, x: x + offset, y, width: length, height: thickness },
            );
            offset += length;
        }
        if (horizontal) {
            x += thickness;
            w -= thickness;
        } else {
            y += thickness;
            h -= thickness;
        }
        row = { items: [], area: 0 };
    };

    for (const item of sorted) {
        const area = value(item) * scale;
        const side = Math.min(w, h);
        const candidate: Row<T> = { items: [...row.items, { item, area }], area: row.area + area };
        if (!row.items.length || worstRatio(candidate, side) <= worstRatio(row, side)) {
            row = candidate;
        } else {
            layoutRow();
            row = { items: [{ item, area }], area };
        }
    }
    if (row.items.length) layoutRow();
    return tiles;
}
