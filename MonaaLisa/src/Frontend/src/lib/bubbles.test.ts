import { describe, expect, it } from "vitest";
import { packCircles } from "./bubbles";

const items = [
    { id: "a", n: 1000 },
    { id: "b", n: 250 },
    { id: "c", n: 250 },
    { id: "d", n: 10 },
    { id: "empty", n: 0 },
];

describe("packCircles", () => {
    const packed = packCircles(items, (i) => i.n);

    it("leaves out items without a value", () => {
        expect(packed.map((b) => b.item.id).sort()).toEqual(["a", "b", "c", "d"]);
    });

    it("never lets two circles overlap", () => {
        for (let i = 0; i < packed.length; i++) {
            for (let j = i + 1; j < packed.length; j++) {
                const distance = Math.hypot(packed[i].x - packed[j].x, packed[i].y - packed[j].y);
                expect(distance).toBeGreaterThanOrEqual(packed[i].r + packed[j].r);
            }
        }
    });

    it("gives a larger value a larger circle and equal values equal circles", () => {
        const r = Object.fromEntries(packed.map((b) => [b.item.id, b.r]));
        expect(r.a).toBeGreaterThan(r.b);
        expect(r.b).toBeCloseTo(r.c);
        expect(r.c).toBeGreaterThan(r.d);
    });

    it("keeps the smallest circle large enough for its name", () => {
        const r = Object.fromEntries(packed.map((b) => [b.item.id, b.r]));
        expect(r.d).toBeGreaterThan(r.a / 4);
    });

    it("returns nothing for nothing", () => {
        expect(packCircles([], () => 1)).toEqual([]);
    });
});
