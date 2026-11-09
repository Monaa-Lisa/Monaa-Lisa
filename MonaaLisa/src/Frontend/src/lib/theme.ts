/**
 * Light / dark theme. The choice is stored in localStorage and applied as
 * data-theme on <html> (app.html does that before the first paint); without
 * a choice the system setting is used.
 * The canvases read their colours from the CSS tokens through `token()`.
 */
const KEY = "monaalisa_theme";

export type Theme = "light" | "dark";

function systemTheme(): Theme {
    return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function currentTheme(): Theme {
    const attr = document.documentElement.dataset.theme;
    return attr === "dark" || attr === "light" ? attr : systemTheme();
}

export function setTheme(theme: Theme) {
    document.documentElement.dataset.theme = theme;
    try {
        localStorage.setItem(KEY, theme);
    } catch {
        // not saved, still applied for this visit
    }
}

/** Value of a CSS custom property, e.g. token("--text"). */
export function token(name: string, fallback = ""): string {
    if (typeof document === "undefined") return fallback;
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/** Resolves a colour given as "var(--name)" to its current value, for the canvases. */
export function resolveColor(color: string, fallback = "#888888"): string {
    const m = color.match(/^var\((--[\w-]+)\)$/);
    return m ? token(m[1], fallback) : color;
}

/**
 * Calls `callback` whenever the theme changes (switch in the header or the
 * system setting). Returns a function that stops listening.
 */
export function onThemeChange(callback: () => void): () => void {
    const observer = new MutationObserver(callback);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const media = matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", callback);
    return () => {
        observer.disconnect();
        media.removeEventListener("change", callback);
    };
}

/** "#rrggbb" with an alpha in [0, 1] -> "rgba(r, g, b, a)" */
export function withAlpha(hex: string, alpha: number): string {
    const m = hex.match(/^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i);
    if (!m) return hex;
    return `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${alpha})`;
}
