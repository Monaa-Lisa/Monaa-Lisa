import { describe, expect, it } from "vitest";
import { findRegions, type RegionInput } from "./regions";

/** `count` papers around a centre, titles built from a pattern */
function cluster(count: number, cx: number, cy: number, title: (i: number) => string): RegionInput[] {
    return Array.from({ length: count }, (_, i) => ({
        title: title(i),
        // a small deterministic spread around the centre
        x: cx + Math.sin(i * 12.9898) * 0.4,
        y: cy + Math.cos(i * 78.233) * 0.4,
    }));
}

// every group shares one phrase, the rest of the titles varies as it does in real data
const rest = ["for molecules", "at scale", "revisited", "with attention", "under noise", "in practice", "a survey"];
const titled = (phrase: string) => (i: number) =>
    i % 2 ? `${phrase} ${rest[i % rest.length]}` : `${rest[(i + 3) % rest.length]}: ${phrase}`;

const map = [
    ...cluster(120, 0, 0, titled("Graph neural networks")),
    ...cluster(120, 10, 0, titled("Reinforcement Learning")),
    ...cluster(120, 0, 10, titled("Lattice QCD")),
    ...cluster(120, 10, 10, titled("Black holes")),
];

describe("findRegions", () => {
    const regions = findRegions(map);
    const names = regions.map((r) => r.label).sort();

    it("names every group after the phrase typical for its titles", () => {
        expect(names).toHaveLength(4);
        expect(names.some((n) => /graph neural network/i.test(n))).toBe(true);
        expect(names.some((n) => /reinforcement learning/i.test(n))).toBe(true);
        expect(names.some((n) => /black hole/i.test(n))).toBe(true);
    });

    it("keeps acronyms in capitals", () => {
        expect(names.some((n) => n.includes("QCD"))).toBe(true);
        expect(names.some((n) => n.includes("Qcd"))).toBe(false);
    });

    it("puts a name at the centre of its group", () => {
        const black = regions.find((r) => /black hole/i.test(r.label))!;
        expect(black.x).toBeGreaterThan(9);
        expect(black.x).toBeLessThan(11);
        expect(black.y).toBeGreaterThan(9);
        expect(black.size).toBe(120);
    });

    it("gives the same names for the same papers", () => {
        expect(
            findRegions(map)
                .map((r) => r.label)
                .sort(),
        ).toEqual(names);
    });

    it("has no names for a handful of papers or papers without a position", () => {
        expect(findRegions(map.slice(0, 20))).toEqual([]);
        expect(findRegions(map.map((p) => ({ ...p, x: 0, y: 0 })))).toEqual([]);
    });

    it("never uses a filler word as a name", () => {
        const vague = cluster(200, 0, 0, (i) => `A new approach using the method ${i}`);
        for (const region of findRegions(vague)) {
            expect(region.label.toLowerCase()).not.toMatch(/^(new|approach|method|using)$/);
        }
    });
});
