<script lang="ts">
    import Dialog from "$lib/components/ui/Dialog.svelte";

    interface Props {
        open: boolean;
        onclose: () => void;
    }

    let { open, onclose }: Props = $props();
    let lang = $state<"en" | "de">("en");
</script>

<Dialog {open} {onclose} title="About Monaa-Lisa" width={520}>
    <div class="lang" role="group" aria-label="Language">
        <button class:active={lang === "en"} onclick={() => (lang = "en")}>EN</button>
        <button class:active={lang === "de"} onclick={() => (lang = "de")}>DE</button>
    </div>

    {#if lang === "de"}
        <p>
            Monaa-Lisa ist eine Web-Anwendung zur hierarchischen Visualisierung von Open Access Literatur, die
            wissenschaftliche Recherchen intuitiver und strukturierter gestaltet. Entwickelt wurde das Projekt von Nico
            Bestek, Nick Wittkowski, Lenio Cabral-Rosario und Bastian Rosinski im Rahmen des Softwarepraktikums 2025 an der
            Hochschule Bochum unter der Betreuung von Prof. Dr. Christian Scheffer und Jonas Friemel.
        </p>
        <p>
            Ein ganz besonderer Dank gilt dabei Jonas Friemel, der uns das gesamte Jahr über als direkter Ansprechpartner
            intensiv betreut hat. Er stand uns jederzeit mit Rat und Tat zur Seite und half uns, auch in stressigen Phasen
            stets einen kühlen Kopf zu bewahren.
        </p>
    {:else}
        <p>
            Monaa-Lisa is a web application for the hierarchical visualization of Open Access literature, designed to make
            scientific research more intuitive and structured. The project was developed by Nico Bestek, Nick Wittkowski,
            Lenio Cabral-Rosario, and Bastian Rosinski as part of the 2025 Software Project at Bochum University of Applied
            Sciences under the supervision of Prof. Dr. Christian Scheffer and Jonas Friemel.
        </p>
        <p>
            Special thanks go to Jonas Friemel, who provided us with intensive support throughout the year as our direct
            contact person. He was always there to offer advice and assistance and helped us to keep a cool head even
            during stressful phases.
        </p>
    {/if}

    {#snippet footer()}
        <span class="license">Licensed under AGPL v3</span>
        <a class="source" href="https://github.com/Monaa-Lisa/Monaa-Lisa" target="_blank" rel="noopener noreferrer">
            <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path
                    d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
                />
            </svg>
            Source code
        </a>
    {/snippet}
</Dialog>

<style>
    p {
        margin: 0 0 12px;
        line-height: 1.6;
    }
    .lang {
        display: inline-flex;
        margin-bottom: 12px;
        padding: 2px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
    }
    .lang button {
        padding: 2px 10px;
        border: 0;
        border-radius: var(--radius-sm);
        background: none;
        color: var(--text-3);
        font-size: var(--text-xs);
        font-weight: 500;
        cursor: pointer;
    }
    .lang button.active {
        background: var(--surface-3);
        color: var(--text);
    }
    .license {
        margin-right: auto;
        align-self: center;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .source {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--text);
        font-size: var(--text-sm);
        text-decoration: none;
    }
    .source:hover {
        color: var(--accent);
    }
    .source :global(svg) {
        width: 16px;
        height: 16px;
    }
</style>
