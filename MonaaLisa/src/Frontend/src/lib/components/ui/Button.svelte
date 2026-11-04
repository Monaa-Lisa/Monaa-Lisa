<!--
  Button with three looks:
  - primary: the one main action in a place
  - secondary: normal actions (bordered)
  - ghost: quiet actions in toolbars and lists
  Pass `icon` for a square icon-only button and always give it a `label`.
-->
<script lang="ts">
    import type { Snippet } from "svelte";
    import type { HTMLButtonAttributes } from "svelte/elements";

    interface Props extends HTMLButtonAttributes {
        variant?: "primary" | "secondary" | "ghost" | "danger";
        size?: "sm" | "md";
        icon?: boolean;
        /** Accessible name, required for icon-only buttons */
        label?: string;
        pressed?: boolean;
        children?: Snippet;
    }

    let {
        variant = "secondary",
        size = "md",
        icon = false,
        label,
        pressed,
        children,
        type = "button",
        ...rest
    }: Props = $props();
</script>

<button
    {type}
    class="btn {variant} {size}"
    class:icon
    aria-label={label}
    title={icon ? label : rest.title}
    aria-pressed={pressed}
    {...rest}
>
    {@render children?.()}
</button>

<style>
    .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        height: 30px;
        padding: 0 10px;
        border: 1px solid transparent;
        border-radius: var(--radius);
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1;
        white-space: nowrap;
        cursor: pointer;
        transition:
            background var(--duration) var(--ease),
            border-color var(--duration) var(--ease),
            color var(--duration) var(--ease);
    }
    .btn.sm {
        height: 26px;
        padding: 0 8px;
        font-size: var(--text-xs);
    }
    .btn.icon {
        width: 30px;
        padding: 0;
    }
    .btn.icon.sm {
        width: 26px;
    }
    .btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
    .btn :global(svg) {
        width: 15px;
        height: 15px;
        flex-shrink: 0;
    }

    .primary {
        background: var(--accent);
        border-color: var(--accent);
        color: var(--accent-fg);
    }
    .primary:hover:not(:disabled) {
        background: var(--accent-hover);
        border-color: var(--accent-hover);
    }

    .secondary {
        background: var(--surface);
        border-color: var(--border-strong);
        color: var(--text);
    }
    .secondary:hover:not(:disabled) {
        background: var(--surface-2);
        border-color: var(--text-3);
    }

    .ghost {
        background: transparent;
        color: var(--text-2);
    }
    .ghost:hover:not(:disabled),
    .ghost[aria-pressed="true"] {
        background: var(--surface-2);
        color: var(--text);
    }

    .danger {
        background: var(--danger-soft);
        color: var(--danger);
    }
    .danger:hover:not(:disabled) {
        background: var(--danger);
        color: #fff;
    }
</style>
