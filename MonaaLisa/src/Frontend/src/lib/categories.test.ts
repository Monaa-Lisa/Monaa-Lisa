import { describe, expect, it } from "vitest";
import { paperContext, subcategories, subjectList, subjectOf, type DatasetCounts } from "./categories";

describe("arXiv hierarchy", () => {
    it("knows the subject of a category", () => {
        expect(subjectOf("cs.LG")).toBe("computer_science");
        expect(subjectOf("hep-th")).toBe("physics");
        expect(subjectOf("stat.ML")).toBe("statistics");
        expect(subjectOf("not-a-category")).toBe("");
    });

    it("places a paper by its primary category", () => {
        expect(paperContext("cs.LG stat.ML")).toEqual({
            categoryId: "cs.LG",
            categoryName: "Machine Learning",
            subjectId: "computer_science",
            subjectName: "Computer Science",
        });
        expect(paperContext(null).categoryId).toBe("");
    });
});

describe("dataset counts", () => {
    const counts: DatasetCounts = {
        papers: new Map([
            ["cs.LG", 50],
            ["cs.CV", 80],
            ["hep-th", 30],
        ]),
        primary: new Map([
            ["cs.LG", 20],
            ["cs.CV", 70],
            ["hep-th", 30],
        ]),
    };

    it("counts a subject by the primary categories, every paper once", () => {
        const subjects = subjectList(counts);
        expect(subjects.find((s) => s.id === "computer_science")!.count).toBe(90);
        expect(subjects.find((s) => s.id === "physics")!.count).toBe(30);
        expect(subjects[0].id).toBe("computer_science");
    });

    it("counts a category with its cross listed papers, largest first", () => {
        const cs = subcategories("computer_science", counts);
        expect(cs.slice(0, 2)).toEqual([
            { id: "cs.CV", name: "Computer Vision and Pattern Recognition", count: 80 },
            { id: "cs.LG", name: "Machine Learning", count: 50 },
        ]);
        expect(cs.at(-1)!.count).toBe(0);
    });

    it("falls back to the arXiv totals without counts", () => {
        expect(subjectList().every((s) => s.count > 1000)).toBe(true);
    });
});
