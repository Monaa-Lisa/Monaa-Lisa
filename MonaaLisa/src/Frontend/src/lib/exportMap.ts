/**
 * Saves what a map shows: as a figure (SVG for print, PNG for slides) and
 * the papers as a table (CSV). The figure is drawn again from the data, not
 * copied from the screen, so it is sharp at any size.
 */
import { citationCount, paperLinks, primaryCategory, publishedYear } from "$lib/paper";
import type { Paper } from "$lib/types/paper";

/** Everything on a map, in px inside a stage of `width` x `height` */
export interface MapScene {
    width: number;
    height: number;
    /** Line above the map, e.g. "Machine Learning (cs.LG) · 1,000 of 48,272 papers" */
    title: string;
    points: { x: number; y: number; r: number; color: string }[];
    lines: { x1: number; y1: number; x2: number; y2: number }[];
    /** Paper titles: left edge and vertical centre */
    titles: { x: number; y: number; text: string; bold?: boolean }[];
    /** Region names: centre */
    names: { x: number; y: number; text: string }[];
    /** Ring around the selected paper */
    ring: { x: number; y: number; r: number } | null;
    legend: { color: string; label: string }[];
    colors: { background: string; text: string; muted: string; line: string };
}

const FONT = '"IBM Plex Sans", "Helvetica Neue", Arial, sans-serif';
const HEAD = 34;
const FOOT = 30;

/** Width of a legend entry, estimated (the SVG has no way to measure text) */
const legendWidth = (label: string) => 22 + label.length * 6.1;

/** Legend entries in rows that fit the width */
function legendRows(scene: MapScene): { x: number; row: number; color: string; label: string }[] {
    const placed = [];
    let x = 12;
    let row = 0;
    for (const item of scene.legend) {
        const w = legendWidth(item.label);
        if (x + w > scene.width - 12 && x > 12) {
            x = 12;
            row++;
        }
        placed.push({ x, row, ...item });
        x += w + 10;
    }
    return placed;
}

const escapeXml = (text: string) =>
    text.replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c]!);
const n = (value: number) => Math.round(value * 10) / 10;

export function sceneToSvg(scene: MapScene): string {
    const legend = legendRows(scene);
    const rows = legend.length ? legend[legend.length - 1].row + 1 : 0;
    const total = HEAD + scene.height + (rows ? 10 + rows * 20 : 0) + (FOOT - 20);
    const { background, text, muted, line } = scene.colors;
    const halo = `stroke="${background}" stroke-width="3" stroke-linejoin="round" paint-order="stroke"`;
    const out: string[] = [
        `<svg xmlns="http://www.w3.org/2000/svg" width="${scene.width}" height="${total}" viewBox="0 0 ${scene.width} ${total}" font-family='${FONT}'>`,
        `<rect width="100%" height="100%" fill="${background}"/>`,
        `<text x="12" y="22" font-size="14" font-weight="600" fill="${text}">${escapeXml(scene.title)}</text>`,
        `<svg x="0" y="${HEAD}" width="${scene.width}" height="${scene.height}" viewBox="0 0 ${scene.width} ${scene.height}">`,
    ];
    for (const l of scene.lines) {
        out.push(`<line x1="${n(l.x1)}" y1="${n(l.y1)}" x2="${n(l.x2)}" y2="${n(l.y2)}" stroke="${line}" stroke-width="0.7"/>`);
    }
    for (const p of scene.points) {
        out.push(`<circle cx="${n(p.x)}" cy="${n(p.y)}" r="${n(p.r)}" fill="${p.color}"/>`);
    }
    if (scene.ring) {
        out.push(
            `<circle cx="${n(scene.ring.x)}" cy="${n(scene.ring.y)}" r="${n(scene.ring.r)}" fill="none" stroke="${text}" stroke-width="2"/>`,
        );
    }
    for (const t of scene.titles) {
        out.push(
            `<text x="${n(t.x + 2)}" y="${n(t.y)}" dominant-baseline="central" font-size="11" font-weight="${t.bold ? 600 : 500}" fill="${text}" ${halo}>${escapeXml(t.text)}</text>`,
        );
    }
    for (const t of scene.names) {
        out.push(
            `<text x="${n(t.x)}" y="${n(t.y)}" text-anchor="middle" dominant-baseline="central" font-size="14" font-weight="600" fill="${text}" ${halo} stroke-width="4">${escapeXml(t.text)}</text>`,
        );
    }
    out.push("</svg>");
    for (const item of legend) {
        const y = HEAD + scene.height + 20 + item.row * 20;
        out.push(
            `<circle cx="${item.x + 5}" cy="${y - 4}" r="4.5" fill="${item.color}"/>`,
            `<text x="${item.x + 15}" y="${y}" font-size="12" fill="${muted}">${escapeXml(item.label)}</text>`,
        );
    }
    out.push("</svg>");
    return out.join("\n");
}

/** Draws the scene on a canvas, `scale` times the size on screen */
export function sceneToCanvas(scene: MapScene, scale = 3): HTMLCanvasElement {
    const legend = legendRows(scene);
    const rows = legend.length ? legend[legend.length - 1].row + 1 : 0;
    const total = HEAD + scene.height + (rows ? 10 + rows * 20 : 0) + (FOOT - 20);
    const canvas = document.createElement("canvas");
    canvas.width = scene.width * scale;
    canvas.height = total * scale;
    const c = canvas.getContext("2d")!;
    const { background, text, muted, line } = scene.colors;
    c.scale(scale, scale);
    c.fillStyle = background;
    c.fillRect(0, 0, scene.width, total);
    c.fillStyle = text;
    c.font = `600 14px ${FONT}`;
    c.fillText(scene.title, 12, 22);

    c.save();
    c.translate(0, HEAD);
    c.beginPath();
    c.rect(0, 0, scene.width, scene.height);
    c.clip();
    c.strokeStyle = line;
    c.lineWidth = 0.7;
    for (const l of scene.lines) {
        c.beginPath();
        c.moveTo(l.x1, l.y1);
        c.lineTo(l.x2, l.y2);
        c.stroke();
    }
    for (const p of scene.points) {
        c.fillStyle = p.color;
        c.beginPath();
        c.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        c.fill();
    }
    if (scene.ring) {
        c.strokeStyle = text;
        c.lineWidth = 2;
        c.beginPath();
        c.arc(scene.ring.x, scene.ring.y, scene.ring.r, 0, Math.PI * 2);
        c.stroke();
    }
    c.lineJoin = "round";
    c.textBaseline = "middle";
    const write = (label: string, x: number, y: number, halo: number) => {
        c.strokeStyle = background;
        c.lineWidth = halo;
        c.strokeText(label, x, y);
        c.fillStyle = text;
        c.fillText(label, x, y);
    };
    for (const t of scene.titles) {
        c.font = `${t.bold ? 600 : 500} 11px ${FONT}`;
        write(t.text, t.x + 2, t.y, 3);
    }
    c.textAlign = "center";
    c.font = `600 14px ${FONT}`;
    for (const t of scene.names) write(t.text, t.x, t.y, 4);
    c.restore();

    c.textAlign = "left";
    c.textBaseline = "alphabetic";
    c.font = `400 12px ${FONT}`;
    for (const item of legend) {
        const y = HEAD + scene.height + 20 + item.row * 20;
        c.fillStyle = item.color;
        c.beginPath();
        c.arc(item.x + 5, y - 4, 4.5, 0, Math.PI * 2);
        c.fill();
        c.fillStyle = muted;
        c.fillText(item.label, item.x + 15, y);
    }
    return canvas;
}

/** The papers as CSV (RFC 4180: quoted fields, quotes doubled, CRLF) */
export function papersToCsv(papers: Paper[]): string {
    const quote = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`;
    const rows = papers.map((p) =>
        [
            p.entry_id,
            p.title,
            p.authors,
            publishedYear(p.published),
            primaryCategory(p.categories),
            p.categories ?? "",
            citationCount(p),
            p.x,
            p.y,
            paperLinks(p).arxiv,
        ]
            .map(quote)
            .join(","),
    );
    const head = "arxiv_id,title,authors,year,primary_category,categories,citations,map_x,map_y,url";
    return [head, ...rows].join("\r\n") + "\r\n";
}

/** Hands a file to the browser's download */
export function download(name: string, content: Blob | string, type = "text/plain") {
    const blob = typeof content === "string" ? new Blob([content], { type: `${type};charset=utf-8` }) : content;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
