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
 * One colour per subject, as slots of the categorical palette in app.css
 * (--series-1 ... --series-8, with their own steps for the dark theme). The
 * three large subjects take the three slots that stay apart for colour blind
 * readers in every pairing.
 */
const SUBJECT_SLOT: Record<string, number> = {
    physics: 1,
    computer_science: 2,
    mathematics: 3,
    electrical_engineering: 4,
    quantitative_finance: 5,
    quantitative_biology: 6,
    statistics: 7,
    economics: 8,
};

/** For everything without a subject, and for "other" on the maps */
export const DEFAULT_CATEGORY_COLOR = "var(--map-other)";

/**
 * Colour of a subject as a CSS value, usable in styles as it is. Canvases
 * resolve it with resolveColor() from lib/theme.ts.
 */
export function subjectColor(subjectId: string): string {
    const slot = SUBJECT_SLOT[subjectId];
    return slot ? `var(--series-${slot})` : DEFAULT_CATEGORY_COLOR;
}

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

/**
 * The subjects and categories come with the number of papers arXiv lists in
 * them (a snapshot in arxiv_cluster_data.json). `datasetCounts` replaces
 * these by the papers that are really in the dataset, once the backend has
 * counted them.
 */
export interface DatasetCounts {
    /** Papers listed in a category, cross listed ones included */
    papers: Map<string, number>;
    /** Papers with the category as their primary one */
    primary: Map<string, number>;
}

export function subjectList(counts: DatasetCounts | null = null): CategoryNode[] {
    return clusters
        .map((c) => ({
        id: c.id,
        name: c.name,
        // every paper has one primary category, so this counts each paper once
        count: counts ? c.children.reduce((sum, sub) => sum + (counts.primary.get(sub.id) ?? 0), 0) : c.total_count,
    }))
        .sort((a, b) => b.count - a.count);
}

export const subjects: CategoryNode[] = subjectList();

export function subjectName(subjectId: string): string {
    return clusters.find((c) => c.id === subjectId)?.name ?? subjectId;
}

export function subcategories(subjectId: string, counts: DatasetCounts | null = null): CategoryNode[] {
    const parent = clusters.find((c) => c.id === subjectId);
    return (parent?.children ?? [])
        .map((sub) => ({ id: sub.id, name: sub.name, count: counts ? (counts.papers.get(sub.id) ?? 0) : sub.value }))
        .sort((a, b) => b.count - a.count);
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
    return subjectColor(subjectOf(primaryCategory(categories)));
}

/** Compact count for labels: 1234 -> "1.2k", 2200822 -> "2.2M" */
export function formatCount(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 10_000) return `${Math.round(n / 1_000)}k`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
}
