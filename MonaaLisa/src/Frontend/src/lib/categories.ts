/**
 * arXiv category hierarchy used for the two subject levels, and the colours
 * of the eight subjects (shared by the treemaps, the paper map, the citation
 * views and the lists).
 */
import clusterData from "../utils/arxiv_cluster_data.json";
import { getSubcategoryName, getTopLevelCategory } from "../utils/arxivTaxonomy";
import type { CategoryNode } from "$lib/types/paper";
import { primaryCategory } from "$lib/paper";

interface ClusterEntry {
    id: string;
    name: string;
    total_count: number;
    children: { id: string; name: string; value: number }[];
}

const clusters = clusterData as ClusterEntry[];

/**
 * One colour per subject, a muted print palette (after Tableau 10) that
 * stays readable on white and on near-black.
 */
export const CATEGORY_COLORS: Record<string, string> = {
    physics: "#4e79a7",
    computer_science: "#e15759",
    mathematics: "#59a14f",
    statistics: "#b07aa1",
    electrical_engineering: "#f28e2b",
    quantitative_biology: "#76b7b2",
    quantitative_finance: "#c9a227",
    economics: "#9c755f",
};

export const DEFAULT_CATEGORY_COLOR = "#8c8c88";

/**
 * Category prefix used to search within a subject.
 * Physics has no common prefix (hep-th, astro-ph, ...), "physics." only
 * covers part of it.
 */
export const CATEGORY_PREFIX: Record<string, string> = {
    computer_science: "cs.",
    mathematics: "math.",
    statistics: "stat.",
    electrical_engineering: "eess.",
    quantitative_biology: "q-bio.",
    quantitative_finance: "q-fin.",
    economics: "econ.",
    physics: "physics.",
};

export const subjects: CategoryNode[] = clusters.map((c) => ({
    id: c.id,
    name: c.name,
    count: c.total_count,
}));

export function subjectName(subjectId: string): string {
    return clusters.find((c) => c.id === subjectId)?.name ?? subjectId;
}

export function subcategories(subjectId: string): CategoryNode[] {
    const parent = clusters.find((c) => c.id === subjectId);
    return (parent?.children ?? []).map((sub) => ({ id: sub.id, name: sub.name, count: sub.value }));
}

/** Subject a subcategory belongs to, e.g. "cs.LG" -> "computer_science". */
export function subjectOf(categoryId: string): string {
    const name = getTopLevelCategory(categoryId);
    return clusters.find((c) => c.name === name)?.id ?? "";
}

export function subcategoryName(categoryId: string): string {
    return getSubcategoryName(categoryId);
}

/**
 * Where a paper sits in the hierarchy, derived from its primary category,
 * e.g. cs.LG -> { categoryId: "cs.LG", categoryName: "Machine Learning", subjectId: "computer_science", subjectName: "Computer Science" }.
 */
export function paperContext(categories: string | null): {
    categoryId: string;
    categoryName: string;
    subjectId: string;
    subjectName: string;
} {
    const id = primaryCategory(categories);
    if (!id) return { categoryId: "", categoryName: "", subjectId: "", subjectName: "" };
    const subject = subjectOf(id);
    return {
        categoryId: id,
        categoryName: getSubcategoryName(id),
        subjectId: subject,
        subjectName: subject ? subjectName(subject) : "",
    };
}

/** Colour of the subject a paper belongs to (by its primary category). */
export function categoryColor(categories: string | null): string {
    return CATEGORY_COLORS[subjectOf(primaryCategory(categories))] ?? DEFAULT_CATEGORY_COLOR;
}

/** Compact count for labels: 1234 -> "1.2k", 2200822 -> "2.2M" */
export function formatCount(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 10_000) return `${Math.round(n / 1_000)}k`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
}
