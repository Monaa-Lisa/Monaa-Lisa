<!--
  GraphLayout.svelte

  This is the main "shell" component that renders everything.
  It works like a state machine with 4 view levels:
    1. top      - shows top-level subject clusters (Physics, CS, Math, ...)
    2. sub      - shows subcategory clusters inside a top-level subject
    3. papers   - shows individual paper nodes via Sigma.js (Graph.svelte)
    4. detail   - shows a paper's citation/reference graph (PaperDetailGraph.svelte)

  The `view` variable holds the current level plus whatever context that level needs.
  Navigation always pushes forward (top → sub → papers → detail) or uses breadcrumbs to go back.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import ClusterGraph from "./ClusterGraph.svelte";
    import Graph from "./Graph.svelte";
    import PaperDetailGraph from "./PaperDetailGraph.svelte";
    import LoadingSpinner from "./LoadingSpinner.svelte";
    import Header from "./Header.svelte";
    import Sidebar from "./Sidebar.svelte";
    import PaperSidebar from "./PaperSidebar.svelte";
    import MetricCards from "./MetricCards.svelte";
    import Dashboard from "./Dashboard.svelte";
    import type {
        ApiPaper,
        Paper,
        PapersResponse,
        ClusterNode,
        ViewState,
        PaperSession,
    } from "$lib/types/paper";
    import { env as publicEnv } from "$env/dynamic/public";
    import clusterData from "../utils/arxiv_cluster_data.json";
    import {
        SUBCATEGORY_TO_TOPLEVEL,
        getSubcategoryName,
        getTopLevelCategory,
    } from "../utils/arxivTaxonomy";

    const API_BASE_URL =
        publicEnv.PUBLIC_API_BASE_URL || "http://localhost:3000";

    // ─── paper / node limits────────────────────────
    // Defaults kept at 1000 for faster initial load; 2500 added as a middle
    // ground. Values >= 10000 and "All" show a confirmation modal because
    // they can cause severe slowdowns or browser crashes.
    let paperLimit = 1000;
    let nodeLimit = 1000;
    const LIMIT_OPTIONS = [
        { value: 100, label: "100" },
        { value: 500, label: "500" },
        { value: 1000, label: "1000" },
        { value: 2500, label: "2500" },
        { value: 5000, label: "5000" },
        { value: 10000, label: "10000" },
        { value: 0, label: "All" },
    ];
    // Threshold above which the user must confirm before the value is applied.
    const LARGE_LIMIT_THRESHOLD = 10000;
    const SIDEBAR_SAMPLE = 50; // papers shown in sidebar at cluster levels

    // ─── large-load confirmation modal ─────────────
    // Shows when the user picks 10000 or "All". Confirm is locked behind a
    // 5-second countdown so the warning text is actually read.
    let confirmModalOpen = false; // whether the modal is visible
    let confirmCountdown = 5; // seconds remaining before Confirm unlocks
    let confirmTimer: ReturnType<typeof setInterval> | null = null;
    // The value the user attempted to select (held until confirmed/cancelled).
    let pendingLimit: number | null = null;
    // Which selector triggered the modal: 'paper' or 'node'.
    let pendingLimitTarget: "paper" | "node" = "paper";
    // Last confirmed safe values - restored on cancel.
    let prevPaperLimit = paperLimit;
    let prevNodeLimit = nodeLimit;

    /** Open the modal for a dangerously large limit selection. */
    function openLimitConfirm(target: "paper" | "node", attempted: number) {
        pendingLimitTarget = target;
        pendingLimit = attempted;
        confirmCountdown = 5;
        confirmModalOpen = true;
        // Kick off the 1-second tick.
        if (confirmTimer) clearInterval(confirmTimer);
        confirmTimer = setInterval(() => {
            confirmCountdown -= 1;
            if (confirmCountdown <= 0) {
                clearInterval(confirmTimer!);
                confirmTimer = null;
            }
        }, 1000);
    }

    /** User confirmed - apply the pending value and close. */
    function applyLimitConfirm() {
        if (pendingLimit === null) return;
        if (pendingLimitTarget === "paper") {
            paperLimit = pendingLimit;
            prevPaperLimit = pendingLimit;
            if (view.level === "papers") loadPapers(view.categoryId);
        } else {
            nodeLimit = pendingLimit;
            prevNodeLimit = pendingLimit;
        }
        closeLimitConfirm();
    }

    /** User cancelled - revert the select back to the previous safe value. */
    function cancelLimitConfirm() {
        // Revert binding so the <select> shows the old value again.
        if (pendingLimitTarget === "paper") paperLimit = prevPaperLimit;
        else nodeLimit = prevNodeLimit;
        closeLimitConfirm();
    }

    function closeLimitConfirm() {
        confirmModalOpen = false;
        pendingLimit = null;
        if (confirmTimer) {
            clearInterval(confirmTimer);
            confirmTimer = null;
        }
    }

    /**
     * Called by the Papers <select> on:change.
     * Intercepts large values and shows the modal instead of applying them.
     */
    function handlePaperLimitChange(e: Event) {
        const attempted = Number((e.target as HTMLSelectElement).value);
        if (attempted === 10000 || attempted === 0) {
            // Immediately revert binding so the select still shows the old value.
            paperLimit = prevPaperLimit;
            openLimitConfirm("paper", attempted);
        } else {
            // Safe value - apply and track.
            prevPaperLimit = attempted;
            if (view.level === "papers") loadPapers(view.categoryId);
        }
    }

    /**
     * Called by the Nodes <select> on:change.
     * Same guard as handlePaperLimitChange but for the detail view node cap.
     */
    function handleNodeLimitChange(e: Event) {
        const attempted = Number((e.target as HTMLSelectElement).value);
        if (attempted === 10000 || attempted === 0) {
            nodeLimit = prevNodeLimit;
            openLimitConfirm("node", attempted);
        } else {
            prevNodeLimit = attempted;
        }
    }
    const MAX_HISTORY = 5;
    const HISTORY_KEY = "monaalisa_paper_sessions_v1";

    // ─── navigation state ─────────────────────────────────────────────
    let view: ViewState = { level: "top" };
    /** View to return to when pressing back from detail */
    let previousView: ViewState = { level: "top" };

    // paper data (only loaded at papers/detail level)
    let papers: Paper[] = [];
    // sample papers for sidebar in cluster views (top / sub)
    let sidebarSamplePapers: Paper[] = [];

    let sidebarOpen = false;
    let selectedPaperId: string | null = null;
    let loading = false;
    let error: string | null = null;

    // ─── author highlight state ────────────────────────────────────
    let authorHighlight: string = "";

    /** Full paper objects from the sidebar's latest search.
     *  Passed to Graph.svelte so it can highlight matching nodes and inject
     *  any missing ones.  Cleared on every view-level navigation. */
    let searchHighlightPapers: Paper[] = [];

    function handleAuthorHighlightFromSidebar(e: CustomEvent<string>) {
        authorHighlight = e.detail;
    }

    /** Receive search results from Sidebar and forward them to the Graph. */
    function handleSearchHighlightFromSidebar(e: CustomEvent<Paper[]>) {
        searchHighlightPapers = e.detail;
    }

    // ─── dashboard ────────────────────────────────────────────────────
    let dashboardOpen = false;
    let dashboardRef: Dashboard;
    /** Incremented whenever favorites change forces re-evaluation of isFavorite */
    let favoritesVersion = 0;

    // ─── group picker modal ───────────────────────────────────────────
    let groupPickerOpen = false;
    let groupPickerPaper: Paper | null = null;
    let groupPickerSelectedIds: string[] = [];
    let groupPickerNewGroupName = "";

    function openDashboard() {
        dashboardOpen = true;
    }
    function closeDashboard() {
        dashboardOpen = false;
    }

    function handleFavoritePaper(e: CustomEvent<Paper>) {
        const paper = e.detail;
        if (dashboardRef && dashboardRef.isFavorite(paper.entry_id)) {
            dashboardRef.removeFavoriteById(paper.entry_id);
            favoritesVersion += 1;
        } else {
            groupPickerPaper = paper;
            groupPickerSelectedIds = [];
            groupPickerNewGroupName = "";
            groupPickerOpen = true;
        }
    }

    function confirmGroupPicker() {
        if (!groupPickerPaper || !dashboardRef) return;
        dashboardRef.addFavoriteWithGroups(
            groupPickerPaper,
            groupPickerSelectedIds,
            groupPickerNewGroupName.trim() || null,
        );
        favoritesVersion += 1;
        groupPickerOpen = false;
        groupPickerPaper = null;
        groupPickerSelectedIds = [];
        groupPickerNewGroupName = "";
    }

    function cancelGroupPicker() {
        groupPickerOpen = false;
        groupPickerPaper = null;
    }

    // colour of the current parent category (passed to subcategory + papers)
    let currentCategoryColor: string = "#4a9eff";

    // ─── arXiv neighbourhood counts (from PaperDetailGraph) ──────────
    let arxivCitationCount: number | undefined = undefined;
    let arxivReferenceCount: number | undefined = undefined;

    // ─── paper browsing history (localStorage) ────────────────────────
    let sessions: PaperSession[] = loadSessions();

    function loadSessions(): PaperSession[] {
        try {
            const raw =
                typeof localStorage !== "undefined"
                    ? localStorage.getItem(HISTORY_KEY)
                    : null;
            return raw ? JSON.parse(raw) : [];
        } catch {
            return [];
        }
    }

    function saveSessions(list: PaperSession[]) {
        try {
            if (typeof localStorage !== "undefined") {
                localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
            }
        } catch {}
    }

    function addSession(paper: Paper) {
        const newSession: PaperSession = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            mainPaper: {
                entry_id: paper.entry_id,
                title: paper.title,
                authors: paper.authors,
            },
            startedAt: Date.now(),
        };
        sessions = [
            newSession,
            ...sessions.filter((s) => s.mainPaper.entry_id !== paper.entry_id),
        ].slice(0, MAX_HISTORY);
        saveSessions(sessions);
        return newSession.id;
    }

    function deleteSessionById(sessionId: string) {
        sessions = sessions.filter((s) => s.id !== sessionId);
        saveSessions(sessions);
    }

    // ─── category prefix for sub-level sidebar loading ────────────────
    const CLUSTER_CAT_PREFIX: Record<string, string> = {
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
     * Given a paper's primary category (e.g. "cs.AI"), derive the full
     * ViewState detail fields so breadcrumbs show the proper hierarchy.
     */
    function resolveDetailContext(paper: Paper): {
        categoryId: string;
        categoryName: string;
        parentName: string;
    } {
        const firstCat =
            (paper.categories ?? "").trim().split(/[\s,]+/)[0] ?? "";
        if (!firstCat)
            return { categoryId: "", categoryName: "", parentName: "" };
        // subcategory name e.g. "Artificial Intelligence"
        const subName = getSubcategoryName(firstCat);
        // top-level name e.g. "Computer Science"
        const topName = getTopLevelCategory(firstCat);
        return {
            categoryId: firstCat,
            categoryName: subName !== firstCat ? subName : firstCat,
            parentName: topName !== "Other" ? topName : "",
        };
    }

    // reactive cluster count for metric cards
    $: currentClusterCount = (() => {
        if (view.level === "top") return topClusters.length;
        if (view.level === "sub") return getSubclusters(view.parentId).length;
        return 0;
    })();

    // ─── top-level cluster data from static JSON ──────────────────────
    const CATEGORY_COLORS: Record<string, string> = {
        physics: "#4361ee",
        computer_science: "#f72585",
        mathematics: "#4cc9f0",
        statistics: "#7209b7",
        electrical_engineering: "#ff7a18",
        quantitative_biology: "#2ec4b6",
        quantitative_finance: "#ffd166",
        economics: "#e71d36",
    };

    const topClusters: ClusterNode[] = clusterData.map((cat: any) => ({
        id: cat.id,
        name: cat.name,
        count: cat.total_count,
    }));

    function getSubclusters(parentId: string): ClusterNode[] {
        const parent = clusterData.find((c: any) => c.id === parentId);
        return (parent?.children ?? []).map((sub: any) => ({
            id: sub.id,
            name: sub.name,
            count: sub.value,
        }));
    }

    // ─── breadcrumbs ──────────────────────────────────────────────────
    interface Crumb {
        label: string;
        action: () => void;
    }

    $: breadcrumbs = buildCrumbs(view);

    function buildCrumbs(v: ViewState): Crumb[] {
        const crumbs: Crumb[] = [
            {
                label: "All Categories",
                action: () => {
                    view = { level: "top" };
                    papers = [];
                    error = null;
                },
            },
        ];

        if (v.level === "sub" || v.level === "papers" || v.level === "detail") {
            const pName = v.parentName;
            if (!pName) return crumbs; // avoid empty/clickable-but-empty crumbs
            const pId = v.level === "sub" ? v.parentId : "";
            crumbs.push({
                label: pName,
                action: () => {
                    const pid =
                        clusterData.find((c: any) => c.name === pName)?.id ??
                        "";
                    if (!pid) return; // guard: no matching cluster, don't crash
                    view = { level: "sub", parentName: pName, parentId: pid };
                    papers = [];
                    error = null;
                    loadSamplePapers("sub", pid);
                },
            });
        }

        if (v.level === "papers" || v.level === "detail") {
            const cId = v.categoryId;
            const cName = v.categoryName;
            const pName = v.parentName;
            if (!cId && !cName) return crumbs; // guard: empty category context
            crumbs.push({
                label: cName || cId,
                action: () => {
                    if (!cId) return;
                    view = {
                        level: "papers",
                        categoryId: cId,
                        categoryName: cName,
                        parentName: pName,
                    };
                    loadPapers(cId);
                },
            });
        }

        if (v.level === "detail") {
            crumbs.push({ label: v.paper.title, action: () => {} });
        }

        return crumbs;
    }

    function truncate(s: string, n: number): string {
        return s.length > n ? s.slice(0, n) + "…" : s;
    }

    // ─── navigation handlers ──────────────────────────────────────────
    function handleTopClusterClick(
        e: CustomEvent<{ id: string; name: string; color: string }>,
    ) {
        // User clicked a top-level blob - drill into its subcategories with a fade transition
        drillDown(() => {
            currentCategoryColor = e.detail.color;
            authorHighlight = "";
            view = {
                level: "sub",
                parentName: e.detail.name,
                parentId: e.detail.id,
            };
            papers = [];
            error = null;
            loadSamplePapers("sub", e.detail.id);
        });
    }

    function handleSubClusterClick(
        e: CustomEvent<{ id: string; name: string; color: string }>,
    ) {
        if (view.level !== "sub") return;
        // Capture the current parentName before the async transition
        const parentName = view.parentName;
        // User clicked a subcategory blob - load papers and switch to graph view with fade
        drillDown(() => {
            currentCategoryColor = e.detail.color;
            authorHighlight = "";
            searchHighlightPapers = []; // clear stale highlights on navigation
            view = {
                level: "papers",
                categoryId: e.detail.id,
                categoryName: e.detail.name,
                parentName,
            };
            loadPapers(e.detail.id);
        });
    }

    // Called when the user clicks a node in the Sigma scatter graph.
    // Records a session entry and transitions to the detail view with a fade.
    function handlePaperSelected(e: CustomEvent<Paper>) {
        if (view.level !== "papers") return;
        const paper = e.detail;
        // Capture context now - view may mutate before the drillDown callback runs
        const categoryId = view.categoryId;
        const categoryName = view.categoryName;
        const parentName = view.parentName;
        arxivCitationCount = undefined;
        arxivReferenceCount = undefined;
        authorHighlight = "";
        searchHighlightPapers = []; // clear on detail entry
        previousView = view;
        addSession(paper);
        drillDown(() => {
            view = {
                level: "detail",
                paper,
                categoryId,
                categoryName,
                parentName,
            };
            if (dashboardRef) dashboardRef.addToHistory(paper);
        });
    }

    function handleDetailBack() {
        if (view.level !== "detail") return;
        arxivCitationCount = undefined;
        arxivReferenceCount = undefined;
        authorHighlight = ""; // clear highlights on view change
        searchHighlightPapers = []; // clear search highlights on back
        // Return to wherever we came from (papers, sub, or top)
        view = previousView;
    }

    function handleSidebarSelect(e: CustomEvent<Paper>) {
        const paper = e.detail;
        arxivCitationCount = undefined;
        arxivReferenceCount = undefined;
        previousView = view;
        addSession(paper);
        // Always derive proper category hierarchy from the paper itself
        const ctx = resolveDetailContext(paper);
        const catId =
            ctx.categoryId ||
            (view.level === "papers" || view.level === "detail"
                ? view.categoryId
                : "");
        const catName =
            ctx.categoryName ||
            (view.level === "papers" || view.level === "detail"
                ? view.categoryName
                : "");
        const parName =
            ctx.parentName ||
            (view.level !== "top" ? ((view as any).parentName ?? "") : "");
        view = {
            level: "detail",
            paper,
            categoryId: catId,
            categoryName: catName,
            parentName: parName,
        };
        if (dashboardRef) dashboardRef.addToHistory(paper);
    }

    /** Called when PaperDetailGraph emits navigate (click on a graph node) */
    function handleGraphNavigate(e: CustomEvent<Paper>) {
        if (view.level !== "detail") return;
        const paper = e.detail;
        arxivCitationCount = undefined;
        arxivReferenceCount = undefined;
        previousView = view;
        addSession(paper);
        view = {
            level: "detail",
            paper,
            categoryId: view.categoryId,
            categoryName: view.categoryName,
            parentName: view.parentName,
        };
        if (dashboardRef) dashboardRef.addToHistory(paper);
    }

    /** Called when PaperSidebar emits navigate (click on a citation/reference) */
    function handlePaperSidebarNavigate(e: CustomEvent<Paper>) {
        if (view.level !== "detail") return;
        const paper = e.detail;
        arxivCitationCount = undefined;
        arxivReferenceCount = undefined;
        previousView = view;
        view = {
            level: "detail",
            paper,
            categoryId: view.categoryId,
            categoryName: view.categoryName,
            parentName: view.parentName,
        };
        if (dashboardRef) dashboardRef.addToHistory(paper);
    }

    function handleToggleSidebar() {
        sidebarOpen = !sidebarOpen;
    }

    function handleNodeDeselected() {
        selectedPaperId = null;
    }

    function handleNeighbourhoodLoaded(
        e: CustomEvent<{ citationCount: number; referenceCount: number }>,
    ) {
        arxivCitationCount = e.detail.citationCount;
        arxivReferenceCount = e.detail.referenceCount;
    }

    function handleDeleteSession(e: CustomEvent<string>) {
        deleteSessionById(e.detail);
    }

    async function handleRestoreSession(e: CustomEvent<PaperSession>) {
        const session = e.detail;
        // Try to find the paper in the currently loaded set first (fast path)
        let paper: Paper | null =
            papers.find((p) => p.entry_id === session.mainPaper.entry_id) ??
            sidebarSamplePapers.find(
                (p) => p.entry_id === session.mainPaper.entry_id,
            ) ??
            null;

        if (!paper) {
            // Try dedicated single-paper endpoint
            try {
                const res = await fetch(
                    `${API_BASE_URL}/papers/${encodeURIComponent(session.mainPaper.entry_id)}`,
                );
                if (res.ok) {
                    const raw: ApiPaper = await res.json();
                    paper = normalizePaper(raw, 0, 1);
                }
            } catch {
                /* fall through */
            }
        }

        if (!paper) {
            // Fall back to title search
            try {
                const res = await fetch(
                    `${API_BASE_URL}/papers?search=${encodeURIComponent(session.mainPaper.title.slice(0, 80))}&take=10`,
                );
                if (res.ok) {
                    const payload = await res.json();
                    const rawItems: ApiPaper[] = Array.isArray(payload)
                        ? payload
                        : (payload?.items ?? []);
                    const found = rawItems.find(
                        (p) => p.entry_id === session.mainPaper.entry_id,
                    );
                    if (found) paper = normalizePaper(found, 0, 1);
                }
            } catch {
                /* ignore */
            }
        }

        if (paper) {
            arxivCitationCount = undefined;
            arxivReferenceCount = undefined;
            previousView = view;
            // Always derive proper category hierarchy from the paper itself
            const ctx = resolveDetailContext(paper);
            const catId =
                ctx.categoryId ||
                (view.level === "papers" ? view.categoryId : "");
            const catName =
                ctx.categoryName ||
                (view.level === "papers" ? view.categoryName : "");
            const parName =
                ctx.parentName ||
                (view.level === "papers" ? view.parentName : "");
            view = {
                level: "detail",
                paper,
                categoryId: catId,
                categoryName: catName,
                parentName: parName,
            };
            if (dashboardRef) dashboardRef.addToHistory(paper);
        }
    }

    // ─── data loading ─────────────────────────────────────────────────
    // Fetches papers for a specific subcategory from the NestJS backend.
    // Papers are stored in the `papers` array which Graph.svelte reads reactively.
    async function loadPapers(categoryId: string) {
        loading = true;
        error = null;
        papers = [];
        // Clear stale search highlights whenever a new category is loaded.
        searchHighlightPapers = [];
        try {
            // Build URL: filter by category, apply optional cap, sort by citation count
            const url = `${API_BASE_URL}/papers?categories=${encodeURIComponent(categoryId)}${paperLimit > 0 ? `&take=${paperLimit}` : ""}&skip=0&sort=citations`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Backend ${response.status}`);

            const payload = (await response.json()) as
                | Partial<PapersResponse>
                | ApiPaper[];
            const rawItems = Array.isArray(payload)
                ? payload
                : (payload?.items ?? []);

            papers = rawItems
                .map((item, i, a) =>
                    normalizePaper(item as ApiPaper, i, a.length),
                )
                .filter((p): p is Paper => Boolean(p));

            // sidebar shows all the loaded papers in papers-level view
            sidebarSamplePapers = papers;

            if (!papers.length)
                error = "Keine Papers für diese Kategorie gefunden.";
        } catch (err) {
            error = err instanceof Error ? err.message : "Fehler beim Laden.";
            papers = [];
        } finally {
            loading = false;
        }
    }

    /**
     * Load a sample of papers for the sidebar in top / sub cluster views.
     * @param level  'top' or 'sub'
     * @param parentId  cluster id (for sub level); unused at top level
     */
    async function loadSamplePapers(level: "top" | "sub", parentId?: string) {
        try {
            let categoryParam = "";
            if (parentId) {
                const prefix = CLUSTER_CAT_PREFIX[parentId] ?? "";
                categoryParam = prefix
                    ? `&categories=${encodeURIComponent(prefix)}`
                    : "";
            }
            const url = `${API_BASE_URL}/papers?take=${SIDEBAR_SAMPLE}&skip=0&sort=citations${categoryParam}`;
            const res = await fetch(url);
            if (!res.ok) return;
            const payload = (await res.json()) as
                | Partial<PapersResponse>
                | ApiPaper[];
            const rawItems = Array.isArray(payload)
                ? payload
                : (payload?.items ?? []);
            sidebarSamplePapers = rawItems
                .map((item, i, a) =>
                    normalizePaper(item as ApiPaper, i, a.length),
                )
                .filter((p): p is Paper => Boolean(p));
        } catch {
            sidebarSamplePapers = [];
        }
    }

    // ─── paper normalisation (carried over) ───────────────────────────
    function parseTsne(tsne: unknown): [number, number] {
        if (!tsne) return [0, 0];
        let obj: any = tsne;
        if (typeof obj === "string") {
            try {
                obj = JSON.parse(obj);
            } catch {
                return [0, 0];
            }
        }
        if (
            obj &&
            typeof obj === "object" &&
            typeof obj.x === "number" &&
            typeof obj.y === "number"
        ) {
            return [obj.x, obj.y];
        }
        return [0, 0];
    }

    function normalizePaper(
        raw: ApiPaper,
        index: number,
        total: number,
    ): Paper | null {
        if (!raw?.entry_id || !raw?.title) return null;
        const [t1, t2] = parseTsne(raw.tsne);
        console.log(`Normalized paper ${raw.entry_id} (${index + 1}/${total}) with t-SNE (${t1.toFixed(2)}, ${t2.toFixed(2)})`);
        return {
            id: Number(raw.id ?? index),
            entry_id: raw.entry_id,
            title: raw.title,
            authors: formatAuthors(raw.authors),
            abstract: raw.abstract ?? "",
            published: raw.published ?? null,
            categories: raw.categories ?? null,
            url: raw.url ?? null,
            citations: deriveStringArray(raw.citations),
            references: deriveStringArray(raw.references),
            non_arxiv_citation_count: raw.non_arxiv_citation_count ?? 0,
            non_arxiv_reference_count: raw.non_arxiv_reference_count ?? 0,
            tsne1: t1,
            tsne2: t2,
            cluster: raw.categories ?? "U",
        };
    }

    function formatAuthors(a: ApiPaper["authors"]): string {
        if (!a) return "";
        return Array.isArray(a) ? a.join(", ") : a;
    }

    function deriveStringArray(value: unknown): string[] {
        if (!value) return [];
        if (Array.isArray(value)) {
            return value
                .map((item) => {
                    if (typeof item === "string") return item;
                    if (typeof item === "number") return item.toString();
                    if (item && typeof item === "object" && "entry_id" in item)
                        return (item as any).entry_id ?? "";
                    return "";
                })
                .filter(Boolean);
        }
        if (typeof value === "string")
            return value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean);
        return [];
    }

    // ─── load initial sample papers for top-level sidebar ────────────  // sidebar label: human-readable name for the current view level
    $: sidebarLabel = (() => {
        if (view.level === "top") return "ArXiv";
        if (view.level === "sub") return view.parentName;
        if (view.level === "papers") return view.categoryName;
        if (view.level === "detail")
            return view.categoryName || view.parentName || "Paper";
        return "ArXiv";
    })();
    onMount(() => {
        // Don't load papers at top level by default
    });

    // ─── drill-down transition ─────────────────────────────────────────────
    // Whether the full-screen fade overlay is visible (true during transitions)
    let drillTransitioning = false;
    // true while the overlay is fading back OUT (fade-in of the new view)
    let drillFadingIn = false;

    /**
     * Execute a view-change with a smooth fade-out / fade-in overlay.
     * The callback fires after the fade-out completes so the new view is
     * never seen mid-transition.
     */
    function drillDown(callback: () => void) {
        drillTransitioning = true;
        drillFadingIn = false;
        // Wait for fade-out to finish, then do view change and fade back in
        setTimeout(() => {
            callback();
            drillFadingIn = true;
            setTimeout(() => {
                drillTransitioning = false;
                drillFadingIn = false;
            }, 450);
        }, 320);
    }
</script>

<!-- main app container -->
<div class="app-container">
    <!-- Full-screen fade overlay for drill-down transitions -->
    {#if drillTransitioning}
        <div
            class="drill-overlay"
            class:drill-fade-out={!drillFadingIn}
            class:drill-fade-in={drillFadingIn}
        ></div>
    {/if}
    <!-- Dashboard slide-in panel -->
    <Dashboard
        bind:this={dashboardRef}
        isOpen={dashboardOpen}
        on:close={closeDashboard}
        on:navigate={(e) => {
            // Navigate to a paper from the dashboard
            const item = e.detail;
            const paper: Paper = {
                id: 0,
                entry_id: item.entry_id,
                title: item.title,
                authors: item.authors,
                abstract: "",
                published: item.published,
                categories: item.categories,
                url: null,
                citations: [],
                references: [],
                non_arxiv_citation_count: 0,
                non_arxiv_reference_count: 0,
                tsne1: 0,
                tsne2: 0,
                cluster: item.categories ?? "U",
            };
            previousView = view;
            const ctx = resolveDetailContext(paper);
            view = {
                level: "detail",
                paper,
                categoryId: ctx.categoryId,
                categoryName: ctx.categoryName,
                parentName: ctx.parentName,
            };
            dashboardOpen = false;
        }}
    />

    <Header />

    <!-- metric cards row -->
    <MetricCards
        {view}
        paperCount={papers.length}
        clusterCount={currentClusterCount}
        {arxivCitationCount}
        {arxivReferenceCount}
    />

    <!-- breadcrumb bar -->
    <nav class="breadcrumbs">
        <button
            class="db-toggle-btn"
            class:db-btn-disabled={dashboardOpen}
            on:click={openDashboard}
            disabled={dashboardOpen}
            title="Open Dashboard"
        >
            &#9776; Dashboard
        </button>
        <span class="crumb-sep-line"></span>
        {#each breadcrumbs as crumb, i}
            {#if i > 0}<span class="sep">›</span>{/if}
            {#if i < breadcrumbs.length - 1}
                <button class="crumb" on:click={crumb.action}
                    >{crumb.label}</button
                >
            {:else}
                <!-- Last crumb: full paper title (truncated to keep breadcrumb manageable) -->
                <span class="crumb current" title={crumb.label}>
                    {crumb.label.length > 80
                        ? crumb.label.slice(0, 80) + "…"
                        : crumb.label}
                </span>
            {/if}
        {/each}
        <div class="limit-select-wrapper">
            {#if view.level === "papers"}
                <span class="limit-label">Papers:</span>
                <!-- on:change intercepted - large values go through the modal -->
                <select
                    class="limit-select"
                    bind:value={paperLimit}
                    on:change={handlePaperLimitChange}
                >
                    {#each LIMIT_OPTIONS as opt}
                        <option value={opt.value}
                            >{opt.label}{opt.value === 0
                                ? " (uncapped)"
                                : ""}</option
                        >
                    {/each}
                </select>
            {:else if view.level === "detail"}
                <span class="limit-label">Nodes:</span>
                <!-- on:change intercepted - large values go through the modal -->
                <select
                    class="limit-select"
                    bind:value={nodeLimit}
                    on:change={handleNodeLimitChange}
                >
                    {#each LIMIT_OPTIONS as opt}
                        <option value={opt.value}>{opt.label}</option>
                    {/each}
                </select>
            {/if}
        </div>
    </nav>

    <!-- Large-load confirmation modal
         Triggered when the user selects 10 000 or "All" papers/nodes.
         The Confirm button is intentionally locked for 5 seconds so the
         warning text has time to be read before the destructive action fires. -->
    {#if confirmModalOpen}
        <div class="confirm-modal-backdrop" role="presentation">
            <div
                class="confirm-modal"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-modal-title"
            >
                <h3 id="confirm-modal-title" class="confirm-modal-title">
                    ⚠ Large Dataset Warning
                </h3>
                <p class="confirm-modal-body">
                    Displaying more than 5 000 papers at once will significantly
                    increase loading times and may impact performance or
                    <strong>crash your browser</strong>. Are you sure you want
                    to continue?
                </p>
                <div class="confirm-modal-buttons">
                    <button
                        class="confirm-btn confirm-btn-cancel"
                        on:click={cancelLimitConfirm}
                    >
                        Cancel
                    </button>
                    <button
                        class="confirm-btn confirm-btn-ok"
                        disabled={confirmCountdown > 0}
                        on:click={applyLimitConfirm}
                    >
                        {#if confirmCountdown > 0}
                            Confirm ({confirmCountdown})
                        {:else}
                            Confirm
                        {/if}
                    </button>
                </div>
            </div>
        </div>
    {/if}

    <div class="main-content">
        <!-- ── graph panel (central area) ── -->
        <div class="graph-panel">
            <!-- ── TOP-LEVEL CLUSTERS ── -->
            {#if view.level === "top"}
                <ClusterGraph
                    clusters={topClusters}
                    parentColor={null}
                    on:clusterClick={handleTopClusterClick}
                />

                <!-- ── SUBCATEGORY CLUSTERS ── -->
            {:else if view.level === "sub"}
                <ClusterGraph
                    clusters={getSubclusters(view.parentId)}
                    parentColor={CATEGORY_COLORS[view.parentId] ?? "#4a9eff"}
                    on:clusterClick={handleSubClusterClick}
                />

                <!-- ── PAPERS VIEW ── -->
            {:else if view.level === "papers"}
                {#if loading}
                    <div class="status-card">
                        <LoadingSpinner size={60} />
                        <p>Fetching Papers for {view.categoryName}…</p>
                    </div>
                {:else if error}
                    <div class="status-card error">
                        <p>{error}</p>
                        <button on:click={() => loadPapers(view.categoryId)}
                            >Erneut versuchen</button
                        >
                    </div>
                {:else}
                    <Graph
                        {papers}
                        {selectedPaperId}
                        categoryColor={currentCategoryColor}
                        {authorHighlight}
                        {searchHighlightPapers}
                        apiBaseUrl={API_BASE_URL}
                        categoryId={view.categoryId}
                        on:paperSelected={handlePaperSelected}
                        on:nodeDeselected={handleNodeDeselected}
                    />
                {/if}

                <!-- ── PAPER DETAIL VIEW ── -->
            {:else if view.level === "detail"}
                {#key `${view.paper.entry_id}_${nodeLimit}`}
                    <PaperDetailGraph
                        paper={view.paper}
                        apiBaseUrl={API_BASE_URL}
                        {nodeLimit}
                        {authorHighlight}
                        isFavoriteCheck={(entryId) =>
                            favoritesVersion >= 0 && dashboardRef
                                ? dashboardRef.isFavorite(entryId)
                                : false}
                        on:back={handleDetailBack}
                        on:neighbourhoodLoaded={handleNeighbourhoodLoaded}
                        on:navigate={handleGraphNavigate}
                        on:favorite={handleFavoritePaper}
                    />
                {/key}
            {/if}
        </div>

        <!-- ── right sidebar panel ── -->
        {#if view.level === "detail"}
            <!-- Paper sidebar with citations, references, history -->
            {#key view.paper.entry_id}
                <PaperSidebar
                    paper={view.paper}
                    apiBaseUrl={API_BASE_URL}
                    isOpen={sidebarOpen}
                    {dashboardOpen}
                    isFavorite={favoritesVersion >= 0 && dashboardRef
                        ? dashboardRef.isFavorite(view.paper.entry_id)
                        : false}
                    on:toggle={handleToggleSidebar}
                    on:navigate={handlePaperSidebarNavigate}
                    on:favorite={handleFavoritePaper}
                    on:authorHighlight={handleAuthorHighlightFromSidebar}
                />
            {/key}
        {:else}
            <!-- Category sidebar with paper list -->
            <Sidebar
                papers={view.level === "papers" ? papers : sidebarSamplePapers}
                isOpen={sidebarOpen}
                {dashboardOpen}
                {selectedPaperId}
                categoryFilter={view.level === "papers" ||
                view.level === "detail"
                    ? view.categoryId
                    : view.level === "sub"
                      ? (CLUSTER_CAT_PREFIX[(view as any).parentId] ?? "")
                      : ""}
                categoryLabel={sidebarLabel}
                apiBaseUrl={API_BASE_URL}
                on:toggle={handleToggleSidebar}
                on:selectPaper={handleSidebarSelect}
                on:authorHighlight={handleAuthorHighlightFromSidebar}
                on:searchHighlight={handleSearchHighlightFromSidebar}
            />
        {/if}
    </div>
</div>

{#if groupPickerOpen && groupPickerPaper}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
        class="picker-overlay"
        on:click|self={cancelGroupPicker}
        role="dialog"
        aria-modal="true"
    >
        <div class="picker-modal">
            <h3 class="picker-heading">Add to Favorites</h3>
            <p class="picker-paper-title">
                {truncate(groupPickerPaper.title, 90)}
            </p>

            {#if dashboardRef && dashboardRef.getGroups().length > 0}
                <p class="picker-section-label">Add to group(s):</p>
                <div class="picker-groups">
                    {#each dashboardRef.getGroups() as group (group.id)}
                        <label class="picker-group-item">
                            <input
                                type="checkbox"
                                value={group.id}
                                checked={groupPickerSelectedIds.includes(
                                    group.id,
                                )}
                                on:change={(e) => {
                                    if (
                                        (e.target as HTMLInputElement).checked
                                    ) {
                                        groupPickerSelectedIds = [
                                            ...groupPickerSelectedIds,
                                            group.id,
                                        ];
                                    } else {
                                        groupPickerSelectedIds =
                                            groupPickerSelectedIds.filter(
                                                (id) => id !== group.id,
                                            );
                                    }
                                }}
                            />
                            {group.name}
                        </label>
                    {/each}
                </div>
            {/if}

            <p class="picker-section-label">Or create a new group:</p>
            <div class="picker-new-group">
                <input
                    type="text"
                    class="picker-group-input"
                    placeholder="New group name (optional)"
                    bind:value={groupPickerNewGroupName}
                    on:keydown={(e) => {
                        if (e.key === "Enter") confirmGroupPicker();
                    }}
                />
            </div>

            <div class="picker-actions">
                <button class="picker-cancel" on:click={cancelGroupPicker}
                    >Cancel</button
                >
                <button class="picker-confirm" on:click={confirmGroupPicker}
                    >★ Add to Favorites</button
                >
            </div>
        </div>
    </div>
{/if}

<style>
    .app-container {
        width: 100vw;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background-color: var(--bg-primary, #0f1020);
        color: var(--text-primary, #f0f0f8);
        overflow: hidden;
    }

    /* ── Drill-down transition overlay ── */
    .drill-overlay {
        position: fixed;
        inset: 0;
        z-index: 9990;
        background: var(--bg-primary, #0f1020);
        pointer-events: none;
    }
    .drill-fade-out {
        animation: drillFadeOut 320ms ease-in forwards;
    }
    .drill-fade-in {
        animation: drillFadeIn 450ms ease-out forwards;
    }
    @keyframes drillFadeOut {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }
    @keyframes drillFadeIn {
        from {
            opacity: 1;
        }
        to {
            opacity: 0;
        }
    }

    .breadcrumbs {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 5px 16px;
        background: var(--bg-secondary, #141530);
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        font-size: 12px;
        flex-shrink: 0;
    }

    .limit-select-wrapper {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
    }
    .limit-label {
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        white-space: nowrap;
    }
    .limit-select {
        background: rgba(20, 22, 50, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: var(--text-secondary, #a8a8c8);
        font-size: 11px;
        padding: 3px 8px;
        border-radius: var(--radius-sm, 8px);
        cursor: pointer;
        outline: none;
        transition: border-color 0.15s ease;
    }
    .limit-select:hover,
    .limit-select:focus {
        border-color: rgba(147, 51, 234, 0.4);
        color: var(--text-primary, #f0f0f8);
    }
    .limit-select option {
        background: #141530;
        color: #f0f0f8;
    }

    /* ── Large-load confirmation modal── */
    .confirm-modal-backdrop {
        position: fixed;
        inset: 0;
        z-index: 10100;
        background: rgba(0, 0, 0, 0.55);
        display: flex;
        align-items: center;
        justify-content: center;
        backdrop-filter: blur(3px);
    }
    .confirm-modal {
        width: 420px;
        max-width: calc(100vw - 40px);
        background: var(--bg-secondary, #0e1024);
        border: 1px solid rgba(147, 51, 234, 0.28);
        border-radius: 12px;
        padding: 24px 24px 20px;
        box-shadow:
            0 16px 48px rgba(0, 0, 0, 0.6),
            0 0 24px rgba(147, 51, 234, 0.1);
        display: flex;
        flex-direction: column;
        gap: 14px;
    }
    .confirm-modal-title {
        margin: 0;
        font-size: 15px;
        font-weight: 700;
        color: #ffd166;
    }
    .confirm-modal-body {
        margin: 0;
        font-size: 13px;
        line-height: 1.55;
        color: var(--text-secondary, #a8a8c8);
    }
    .confirm-modal-body strong {
        color: #ff6b6b;
    }
    .confirm-modal-buttons {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }
    .confirm-btn {
        padding: 7px 16px;
        border-radius: 8px;
        border: none;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .confirm-btn-cancel {
        background: rgba(255, 255, 255, 0.05);
        color: var(--text-secondary, #a8a8c8);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .confirm-btn-cancel:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-primary, #f0f0f8);
    }
    .confirm-btn-ok {
        background: linear-gradient(
            135deg,
            rgba(147, 51, 234, 0.9),
            rgba(232, 57, 160, 0.8)
        );
        color: #fff;
    }
    .confirm-btn-ok:hover:not(:disabled) {
        filter: brightness(1.15);
    }
    .confirm-btn-ok:disabled {
        opacity: 0.55;
        cursor: not-allowed;
        filter: grayscale(0.2);
    }

    .db-toggle-btn {
        background: none;
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: var(--text-secondary, #a8a8c8);
        font-size: 11px;
        padding: 3px 10px;
        border-radius: var(--radius-sm, 8px);
        cursor: pointer;
        transition: all 0.15s ease;
        flex-shrink: 0;
        white-space: nowrap;
    }
    .db-toggle-btn:hover {
        background: rgba(147, 51, 234, 0.15);
        color: var(--text-primary, #f0f0f8);
        border-color: rgba(147, 51, 234, 0.35);
    }

    /* Dashboard is open: blur and disable the toggle button so the user
       cannot open a second dashboard while one is already active. */
    .db-toggle-btn.db-btn-disabled {
        filter: blur(1.5px);
        opacity: 0.4;
        pointer-events: none;
        cursor: not-allowed;
    }

    .crumb-sep-line {
        width: 1px;
        height: 14px;
        background: var(--glass-border, rgba(255, 255, 255, 0.12));
        flex-shrink: 0;
        margin: 0 4px;
    }

    .sep {
        color: var(--text-muted, #6b6b8d);
        margin: 0 2px;
    }

    .crumb {
        background: none;
        border: none;
        color: var(--accent-cyan, #22d3ee);
        cursor: pointer;
        padding: 2px 6px;
        border-radius: var(--radius-sm, 8px);
        font-size: 12px;
        transition: all var(--transition-fast, 0.15s ease);
    }
    .crumb:hover {
        background: rgba(34, 211, 238, 0.12);
        color: #fff;
    }
    .crumb.current {
        color: var(--text-primary, #f0f0f8);
        cursor: default;
    }

    .main-content {
        flex: 1;
        position: relative;
        display: flex;
        overflow: hidden;
    }

    .graph-panel {
        flex: 1;
        position: relative;
        display: flex;
        overflow: hidden;
        border-radius: var(--radius-md, 12px);
        margin: 0 4px 4px 4px;
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        background: var(--bg-primary, #0f1020);
    }

    :global(.graph-wrapper),
    :global(.cluster-canvas),
    :global(.cluster-container),
    :global(.detail-wrapper) {
        width: 100% !important;
        height: 100% !important;
    }

    .status-card {
        margin: auto;
        padding: 3rem 2rem;
        border-radius: var(--radius-lg, 16px);
        border: 1px solid var(--border-subtle, rgba(147, 51, 234, 0.18));
        background: var(--glass-bg, rgba(20, 22, 50, 0.55));
        backdrop-filter: blur(var(--glass-blur, 16px));
        color: var(--text-primary, #f0f0f8);
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2rem;
        min-width: 320px;
        box-shadow: var(--shadow-glow-sm);
    }

    .status-card.error {
        border-color: rgba(245, 101, 101, 0.4);
        box-shadow: 0 0 20px rgba(245, 101, 101, 0.15);
    }

    .status-card button {
        align-self: center;
        background: linear-gradient(
            135deg,
            var(--accent-purple),
            var(--accent-magenta)
        );
        border: none;
        border-radius: 999px;
        color: white;
        cursor: pointer;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all var(--transition-smooth);
        box-shadow: 0 0 15px rgba(147, 51, 234, 0.3);
    }

    .status-card button:hover {
        transform: translateY(-1px);
        box-shadow: 0 0 25px rgba(147, 51, 234, 0.5);
    }

    /* ── group picker modal ── */
    .picker-overlay {
        position: fixed;
        inset: 0;
        z-index: 500;
        background: rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(3px);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .picker-modal {
        background: var(--bg-secondary, #141530);
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.12));
        border-radius: 14px;
        padding: 22px 24px;
        width: 360px;
        max-width: 94vw;
        box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
        display: flex;
        flex-direction: column;
        gap: 14px;
    }

    .picker-heading {
        margin: 0;
        font-size: 15px;
        font-weight: 700;
        color: var(--text-primary, #f0f0f8);
    }

    .picker-paper-title {
        margin: 0;
        font-size: 12px;
        color: var(--text-secondary, #a8a8c8);
        line-height: 1.5;
    }

    .picker-section-label {
        margin: 0;
        font-size: 11px;
        font-weight: 600;
        color: var(--text-muted, #6b6b8d);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .picker-groups {
        display: flex;
        flex-direction: column;
        gap: 6px;
        max-height: 180px;
        overflow-y: auto;
        scrollbar-width: thin;
    }

    .picker-group-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: var(--text-primary, #f0f0f8);
        cursor: pointer;
        padding: 4px 6px;
        border-radius: 6px;
        transition: background 0.12s;
    }
    .picker-group-item:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .picker-new-group {
    }

    .picker-group-input {
        width: 100%;
        box-sizing: border-box;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        color: var(--text-primary, #f0f0f8);
        font-size: 12px;
        padding: 6px 10px;
        border-radius: 8px;
        outline: none;
        transition: border-color 0.15s;
    }
    .picker-group-input:focus {
        border-color: var(--accent-cyan, #22d3ee);
    }

    .picker-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        margin-top: 4px;
    }

    .picker-cancel {
        background: none;
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
        padding: 6px 14px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .picker-cancel:hover {
        background: rgba(255, 255, 255, 0.06);
        color: var(--text-primary, #f0f0f8);
    }

    .picker-confirm {
        /* Matches the active tab-btn colour scheme from PaperDetailGraph */
        background: linear-gradient(
            135deg,
            rgba(147, 51, 234, 0.35),
            rgba(232, 57, 160, 0.25)
        );
        border: 1px solid rgba(147, 51, 234, 0.35);
        color: var(--text-primary, #f0f0f8);
        font-size: 12px;
        font-weight: 600;
        padding: 6px 16px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.15s;
        box-shadow: 0 0 12px rgba(147, 51, 234, 0.2);
    }
    .picker-confirm:hover {
        background: linear-gradient(
            135deg,
            rgba(147, 51, 234, 0.55),
            rgba(232, 57, 160, 0.45)
        );
        box-shadow: 0 0 20px rgba(147, 51, 234, 0.4);
        transform: translateY(-1px);
    }
</style>
