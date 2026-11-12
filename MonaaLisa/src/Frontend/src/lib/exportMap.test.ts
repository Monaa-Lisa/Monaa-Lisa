import { describe, expect, it } from "vitest";
import { papersToCsv, sceneToSvg, type MapScene } from "./exportMap";
import { toPaper } from "./paper";

const scene: MapScene = {
    width: 400,
    height: 300,
    title: "Machine Learning (cs.LG) · 2 papers <test>",
    points: [
        { x: 10.04, y: 20, r: 3, color: "#2a78d6" },
        { x: 30, y: 40, r: 5, color: "#eb6834" },
    ],
    lines: [{ x1: 10, y1: 20, x2: 30, y2: 40 }],
    titles: [{ x: 36, y: 40, text: "Attention & more", bold: true }],
    names: [{ x: 200, y: 150, text: "Neural networks" }],
    ring: { x: 30, y: 40, r: 9 },
    legend: [
        { color: "#2a78d6", label: "Machine Learning cs.LG 1" },
        { color: "#eb6834", label: "Statistics stat.ML 1" },
    ],
    colors: { background: "#ffffff", text: "#191c26", muted: "#464b5a", line: "#b3b7c4" },
};

describe("sceneToSvg", () => {
    const svg = sceneToSvg(scene);

    it("draws every point, line, ring, title and name", () => {
        expect(svg.match(/<circle /g)).toHaveLength(2 + 1 + 2); // points, ring, legend
        expect(svg.match(/<line /g)).toHaveLength(1);
        expect(svg).toContain('cx="10" cy="20" r="3" fill="#2a78d6"');
        expect(svg).toContain(">Neural networks</text>");
    });

    it("escapes text", () => {
        expect(svg).toContain("Attention &amp; more");
        expect(svg).toContain("2 papers &lt;test&gt;");
        expect(svg).not.toContain("<test>");
    });

    it("is one well formed svg with room for title and legend", () => {
        expect(svg.startsWith("<svg xmlns=")).toBe(true);
        expect(svg.match(/<svg /g)).toHaveLength(svg.match(/<\/svg>/g)!.length);
        const height = Number(svg.match(/height="(\d+)"/)![1]);
        expect(height).toBeGreaterThan(300 + 34);
    });

    it("wraps a long legend into rows", () => {
        const many = { ...scene, legend: Array.from({ length: 12 }, (_, i) => ({ color: "#000", label: `Category number ${i}` })) };
        const ys = new Set([...sceneToSvg(many).matchAll(/r="4.5" fill="#000"\/>\n<text x="[\d.]+" y="(\d+)"/g)].map((m) => m[1]));
        expect(ys.size).toBeGreaterThan(1);
    });
});

describe("papersToCsv", () => {
    const paper = toPaper({
        entry_id: "1412.6980",
        title: 'Adam: A "Method", for Optimization',
        authors: "Diederik P. Kingma, Jimmy Ba",
        categories: "cs.LG stat.ML",
        published: "2014-12-22T00:00:00.000Z",
        tsne: { x: 1.5, y: -2 },
        arxiv_citation_count: 4,
        non_arxiv_citation_count: 6,
    })!;

    it("writes a header and one quoted row per paper", () => {
        const lines = papersToCsv([paper]).split("\r\n");
        expect(lines[0]).toBe("arxiv_id,title,authors,year,primary_category,categories,citations,map_x,map_y,url");
        expect(lines[1]).toBe(
            '"1412.6980","Adam: A ""Method"", for Optimization","Diederik P. Kingma, Jimmy Ba","2014","cs.LG","cs.LG stat.ML","10","1.5","-2","https://arxiv.org/abs/1412.6980"',
        );
        expect(lines).toHaveLength(3);
    });
});
