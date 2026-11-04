/**
 * arXiv category hierarchy used for the two cluster levels, and the colours
 * of the top-level categories (shared by the cluster maps and the paper map).
 */
import clusterData from "../utils/arxiv_cluster_data.json";
import { getSubcategoryName, getTopLevelCategory } from "../utils/arxivTaxonomy";
import type { ClusterNode } from "$lib/types/paper";
import { primaryCategory } from "$lib/paper";

interface ClusterEntry {
    id: string;
    name: string;
    total_count: number;
    children: { id: string; name: string; value: number }[];
}

const clusters = clusterData as ClusterEntry[];

/** Data colours of the top-level categories. */
export const CATEGORY_COLORS: Record<string, string> = {
    physics: "#4361ee",
    computer_science: "#f72585",
    mathematics: "#4cc9f0",
    statistics: "#7209b7",
    electrical_engineering: "#ff7a18",
    quantitative_biology: "#2ec4b6",
    quantitative_finance: "#ffd166",
    economics: "#e71d36",
};

export const DEFAULT_CATEGORY_COLOR = "#4a9eff";

/**
 * Category prefix used to load sample papers for a top-level category.
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

export const topClusters: ClusterNode[] = clusters.map((c) => ({
    id: c.id,
    name: c.name,
    count: c.total_count,
}));

export function subClusters(parentId: string): ClusterNode[] {
    const parent = clusters.find((c) => c.id === parentId);
    return (parent?.children ?? []).map((sub) => ({ id: sub.id, name: sub.name, count: sub.value }));
}

export function topClusterIdByName(name: string): string {
    return clusters.find((c) => c.name === name)?.id ?? "";
}

/**
 * Where a paper sits in the hierarchy, derived from its primary category,
 * e.g. cs.LG -> { categoryId: "cs.LG", categoryName: "Machine Learning", parentName: "Computer Science" }.
 */
export function paperContext(categories: string | null): {
    categoryId: string;
    categoryName: string;
    parentName: string;
} {
    const id = primaryCategory(categories);
    if (!id) return { categoryId: "", categoryName: "", parentName: "" };
    const subName = getSubcategoryName(id);
    const topName = getTopLevelCategory(id);
    return {
        categoryId: id,
        categoryName: subName !== id ? subName : id,
        parentName: topName !== "Other" ? topName : "",
    };
}
