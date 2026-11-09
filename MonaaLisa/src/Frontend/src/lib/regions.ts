/**
 * Names for the regions of a paper map.
 *
 * The papers are grouped by their map position (k-means on the UMAP
 * coordinates), and every group is named after the term that sets its titles
 * apart from the rest of the map: the word or phrase that is frequent inside
 * the group and rare outside. This is only an annotation drawn on top of the
 * map, the positions themselves are not changed.
 */
export interface RegionInput {
    title: string;
    x: number;
    y: number;
}

export interface Region {
    /** Stable within one map, e.g. "graph neural networks" */
    id: string;
    label: string;
    /** Centre in map coordinates */
    x: number;
    y: number;
    /** Papers in the region */
    size: number;
}

const STOPWORDS = new Set(
    (
        "a an and are as at be by can do for from has have how in into is it its of on or our over some than that the " +
        "their there these this to under via we what when where which while who why with without " +
        // words that say nothing about the topic of a paper
        "using based towards toward approach approaches method methods new novel study studies analysis paper " +
        "application applications use case results problem problems some two one first non general improved " +
        "efficient simple large small high low fast better beyond more less part ii iii"
    ).split(" "),
);

interface Word {
    /** Lower case and singular, what is counted */
    key: string;
    /** As written in the title */
    raw: string;
}

/** "networks" -> "network", "galaxies" -> "galaxy", so singular and plural count as one term */
function singular(word: string): string {
    if (word.length > 4 && word.endsWith("ies")) return `${word.slice(0, -3)}y`;
    if (word.length > 3 && word.endsWith("s") && !/(ss|us|is)$/.test(word)) return word.slice(0, -1);
    return word;
}

/** Too vague to name a region alone, fine inside a phrase ("field theory", "deep learning") */
const WEAK_ALONE = new Set(
    (
        "theory deep model data system learning network random quantum image problem field time function structure " +
        "effect property state order wave dynamic space algorithm equation"
    ).split(" "),
);

function words(title: string): Word[] {
    return title
        .replace(/\$[^$]*\$/g, " ") // formulas
        .replace(/\\[a-zA-Z]+/g, " ") // LaTeX commands
        .replace(/[^a-zA-Z0-9\- ]+/g, " ")
        .split(/\s+/)
        .map((w) => w.replace(/^-+|-+$/g, ""))
        .filter((w) => w.length > 1 && !/^\d+$/.test(w))
        .map((raw) => ({ key: singular(raw.toLowerCase()), raw }));
}

/** Words and phrases of up to three words in a title, none starting or ending with a stopword */
function terms(list: Word[]): Map<string, string> {
    const stop = (w: Word) => STOPWORDS.has(w.key) || STOPWORDS.has(w.raw.toLowerCase());
    const found = new Map<string, string>();
    for (let i = 0; i < list.length; i++) {
        if (stop(list[i])) continue;
        for (let n = 1; n <= 3 && i + n <= list.length; n++) {
            if (stop(list[i + n - 1])) continue;
            const part = list.slice(i, i + n);
            found.set(part.map((w) => w.key).join(" "), part.map((w) => w.raw).join(" "));
        }
    }
    return found;
}

/** How a term is written in a name: as in most titles, acronyms stay in capitals */
function spelling(forms: Map<string, number>): string {
    const lower = new Map<string, number>();
    const capitals = new Map<string, number>();
    for (const [form, count] of forms) {
        const key = form.toLowerCase();
        lower.set(key, (lower.get(key) ?? 0) + count);
        form.split(" ").forEach((w) => {
            if (w === w.toUpperCase() && /[A-Z]/.test(w)) {
                capitals.set(w.toLowerCase(), (capitals.get(w.toLowerCase()) ?? 0) + count);
            }
        });
    }
    const [best, total] = [...lower.entries()].sort((a, b) => b[1] - a[1])[0];
    const text = best
        .split(" ")
        .map((w) => ((capitals.get(w) ?? 0) > total * 0.6 ? w.toUpperCase() : w))
        .join(" ");
    return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Small deterministic random generator, the same map always gets the same regions */
function random(seed: number): () => number {
    let state = seed >>> 0 || 1;
    return () => {
        state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
        return state / 4294967296;
    };
}

/** k-means on the positions, returns the group index of every point */
function kMeans(points: RegionInput[], k: number): number[] {
    const next = random(points.length * 31 + k);
    // k-means++ start: every further centre is drawn far from the ones so far
    const centres = [points[Math.floor(next() * points.length)]].map((p) => ({ x: p.x, y: p.y }));
    const distance = points.map(() => Infinity);
    while (centres.length < k) {
        const last = centres[centres.length - 1];
        let sum = 0;
        points.forEach((p, i) => {
            distance[i] = Math.min(distance[i], (p.x - last.x) ** 2 + (p.y - last.y) ** 2);
            sum += distance[i];
        });
        let pick = next() * sum;
        let chosen = points.length - 1;
        for (let i = 0; i < points.length; i++) {
            pick -= distance[i];
            if (pick <= 0) {
                chosen = i;
                break;
            }
        }
        centres.push({ x: points[chosen].x, y: points[chosen].y });
    }

    const group = new Array<number>(points.length).fill(0);
    for (let round = 0; round < 25; round++) {
        let moved = false;
        points.forEach((p, i) => {
            let best = 0;
            let bestDistance = Infinity;
            centres.forEach((c, j) => {
                const d = (p.x - c.x) ** 2 + (p.y - c.y) ** 2;
                if (d < bestDistance) {
                    bestDistance = d;
                    best = j;
                }
            });
            if (group[i] !== best) {
                group[i] = best;
                moved = true;
            }
        });
        if (!moved) break;
        const sums = centres.map(() => ({ x: 0, y: 0, n: 0 }));
        points.forEach((p, i) => {
            sums[group[i]].x += p.x;
            sums[group[i]].y += p.y;
            sums[group[i]].n++;
        });
        sums.forEach((s, j) => {
            if (s.n) centres[j] = { x: s.x / s.n, y: s.y / s.n };
        });
    }
    return group;
}

/** Middle value, so a few far away papers do not pull a label off its region */
function median(values: number[]): number {
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
}

export function findRegions(papers: RegionInput[]): Region[] {
    const points = papers.filter((p) => p.x !== 0 || p.y !== 0);
    if (points.length < 60) return [];
    const k = Math.max(4, Math.min(12, Math.round(points.length / 110)));
    const group = kMeans(points, k);

    // in how many titles a term occurs, on the whole map and per group
    const everywhere = new Map<string, number>();
    const inGroup = Array.from({ length: k }, () => new Map<string, number>());
    const members = Array.from({ length: k }, () => [] as RegionInput[]);
    /** The ways a term is written in the titles */
    const forms = new Map<string, Map<string, number>>();
    points.forEach((p, i) => {
        members[group[i]].push(p);
        for (const [term, raw] of terms(words(p.title))) {
            everywhere.set(term, (everywhere.get(term) ?? 0) + 1);
            inGroup[group[i]].set(term, (inGroup[group[i]].get(term) ?? 0) + 1);
            const written = forms.get(term) ?? new Map<string, number>();
            written.set(raw, (written.get(raw) ?? 0) + 1);
            forms.set(term, written);
        }
    });

    const minSize = Math.max(8, points.length * 0.015);
    const candidates: { group: number; term: string; score: number }[] = [];
    inGroup.forEach((counts, g) => {
        const size = members[g].length;
        if (size < minSize) return;
        for (const [term, count] of counts) {
            const length = term.split(" ").length;
            // a single word has to be common in the group, a phrase is telling even when it is rarer
            if (count < Math.max(3, size * (length === 1 ? 0.05 : 0.025))) continue;
            if (length === 1 && WEAK_ALONE.has(term)) continue;
            const here = count / size;
            const overall = everywhere.get(term)! / points.length;
            if (here <= overall) continue;
            // frequent in the group and much more frequent than elsewhere; phrases say more than single words
            const score = here * Math.log(here / overall) * (length === 1 ? 1 : length === 2 ? 1.8 : 2.1);
            candidates.push({ group: g, term, score });
        }
    });

    // best terms first, every group gets one name and no two groups the same
    candidates.sort((a, b) => b.score - a.score);
    const named = new Map<number, string>();
    const used = new Set<string>();
    for (const { group: g, term } of candidates) {
        // a word that is already part of another name would only repeat it
        if (named.has(g) || used.has(term)) continue;
        named.set(g, term);
        used.add(term);
        term.split(" ").forEach((w) => used.add(w));
    }

    return [...named.entries()].map(([g, term]) => ({
        id: term,
        label: spelling(forms.get(term)!),
        x: median(members[g].map((p) => p.x)),
        y: median(members[g].map((p) => p.y)),
        size: members[g].length,
    }));
}
