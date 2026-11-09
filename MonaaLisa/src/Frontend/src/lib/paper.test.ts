import { describe, expect, it } from "vitest";
import {
    authorList,
    categoryList,
    citationCount,
    parseCoordinates,
    primaryCategory,
    shortAuthors,
    toBibtex,
    toIdList,
    toPaper,
} from "./paper";

const raw = {
    id: 7,
    entry_id: "1412.6980",
    title: "Adam:  A Method for\n Stochastic Optimization",
    authors: "Diederik P. Kingma, Jimmy Ba",
    categories: "cs.LG stat.ML",
    published: "2014-12-22T00:00:00.000Z",
    tsne: { x: 1.5, y: -2, method: "umap" },
    arxiv_citation_count: 4004,
    non_arxiv_citation_count: 158527,
};

describe("toPaper", () => {
    it("normalises an API paper", () => {
        const paper = toPaper(raw)!;
        expect(paper.title).toBe("Adam: A Method for Stochastic Optimization");
        expect([paper.x, paper.y]).toEqual([1.5, -2]);
        expect(paper.citations).toEqual([]);
        expect(paper.abstract).toBe("");
    });

    it("drops entries without an id or a title", () => {
        expect(toPaper({ ...raw, entry_id: "" })).toBeNull();
        expect(toPaper({ ...raw, title: "" })).toBeNull();
    });
});

describe("parseCoordinates", () => {
    it("reads objects and JSON strings, and falls back to 0/0", () => {
        expect(parseCoordinates({ x: 1, y: 2 })).toEqual([1, 2]);
        expect(parseCoordinates('{"x": 3, "y": 4}')).toEqual([3, 4]);
        expect(parseCoordinates("not json")).toEqual([0, 0]);
        expect(parseCoordinates(null)).toEqual([0, 0]);
        expect(parseCoordinates({ x: "1", y: 2 })).toEqual([0, 0]);
    });
});

describe("toIdList", () => {
    it("accepts arrays of ids or objects and comma separated text", () => {
        expect(toIdList(["a", 5, { entry_id: "b" }, null])).toEqual(["a", "5", "b"]);
        expect(toIdList("a, b ,,c")).toEqual(["a", "b", "c"]);
        expect(toIdList(undefined)).toEqual([]);
    });
});

describe("categories and authors", () => {
    it("splits the category list", () => {
        expect(primaryCategory("cs.LG stat.ML")).toBe("cs.LG");
        expect(primaryCategory(null)).toBe("");
        expect(categoryList(" cs.LG  stat.ML ")).toEqual(["cs.LG", "stat.ML"]);
    });

    it("splits authors on commas and 'and', without affiliations", () => {
        expect(authorList("A. One (MIT), B. Two and C. Three")).toEqual(["A. One", "B. Two", "C. Three"]);
        expect(authorList("Alexander Sandberg")).toEqual(["Alexander Sandberg"]);
    });

    it("shortens long author lists", () => {
        expect(shortAuthors("A, B, C, D")).toBe("A, B, C et al.");
        expect(shortAuthors("A, B")).toBe("A, B");
    });
});

describe("citationCount", () => {
    it("adds the citations outside arXiv to the ones on arXiv", () => {
        expect(citationCount(toPaper(raw)!)).toBe(162531);
    });

    it("uses the longer of the stored count and the loaded list", () => {
        const paper = toPaper({ ...raw, arxiv_citation_count: 1, citations: ["a", "b", "c"], non_arxiv_citation_count: 0 })!;
        expect(citationCount(paper)).toBe(3);
    });
});

describe("toBibtex", () => {
    it("writes an arXiv @misc entry", () => {
        const bibtex = toBibtex(toPaper(raw)!);
        expect(bibtex).toContain("@misc{kingma2014adam,");
        expect(bibtex).toContain("author = {Diederik P. Kingma and Jimmy Ba}");
        expect(bibtex).toContain("eprint = {1412.6980}");
        expect(bibtex).toContain("primaryClass = {cs.LG}");
    });

    it("escapes LaTeX special characters", () => {
        expect(toBibtex(toPaper({ ...raw, title: "50% faster & cheaper_models" })!)).toContain(
            "title = {50\\% faster \\& cheaper\\_models}",
        );
    });
});
