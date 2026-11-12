<script lang="ts">
    let showAboutModal = false;
    let lang = 'en'; // Standardmäßig auf Englisch
</script>

<div class="header">
    <div class="header-accent-line"></div>
    <div class="header-inner">
        <span class="header-logo">M-L</span>
        <h1 class="header-title">
            Monaa-Lisa <span class="header-divider">-</span>
            <span class="header-subtitle">Academic Paper Visualization</span>
        </h1>
        <button class="about-btn" on:click={() => (showAboutModal = true)}
            >About Us</button
        >
    </div>
</div>

{#if showAboutModal}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-backdrop" on:click={() => (showAboutModal = false)}>
        <div class="modal-content" on:click|stopPropagation>
            <button
                class="modal-close"
                on:click={() => (showAboutModal = false)}>×</button
            >
            <h2>About Us</h2>
            <div class="lang-switch">
                <button class:active={lang === 'de'} on:click={() => lang = 'de'}>DE</button>
                <button class:active={lang === 'en'} on:click={() => lang = 'en'}>EN</button>
            </div>
            <div class="content-area">
                {#if lang === 'de'}
                    <p>
                        MONAA-LISA ist eine Web-Anwendung zur hierarchischen Visualisierung von Open Access Literatur, die wissenschaftliche Recherchen
                intuitiver und strukturierter gestaltet. Entwickelt wurde das Projekt von Nico Bestek, Nick Wittkowski, Lenio Cabral-Rosario
                und Bastian Rosinski im Rahmen des Softwarepraktikums 2025 an der <strong>Hochschule Bochum</strong> unter der Betreuung von Prof. Dr. Christian
                Scheffer und Jonas Friemel.
                    </p>
                    <p>
                        Ein ganz besonderer Dank gilt dabei <strong>Jonas Friemel</strong>, der uns das gesamte Jahr über als direkter Ansprechpartner intensiv betreut hat. Er stand uns jederzeit mit Rat und Tat zur Seite und half uns, auch in stressigen Phasen stets einen kühlen Kopf zu bewahren.
                    </p>
                {:else}
                    <p>
                        MONAA-LISA is a web application for the hierarchical visualization of Open Access literature, designed to make scientific research more intuitive and structured. The project was developed by Nico Bestek, Nick Wittkowski, Lenio Cabral-Rosario, and Bastian Rosinski as part of the 2025 Software Project at <strong>Bochum University of Applied Sciences</strong> under the supervision of Prof. Dr. Christian Scheffer and Jonas Friemel.
                    </p>
                    <p>
                        Special thanks go to <strong>Jonas Friemel</strong>, who provided us with intensive support throughout the year as our direct contact person. He was always there to offer advice and assistance and helped us to keep a cool head even during stressful phases.
                    </p>
                {/if}
            </div>
            <hr class="modal-divider" />
            <div class="modal-footer-license">
                <p class="license-label">Licensed under AGPL v3</p>
                <a href="https://github.com/Monaa-Lisa/Monaa-Lisa" target="_blank" rel="noopener noreferrer" class="github-link">
                    <svg height="20" width="20" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                    </svg>
                    Source Code on GitHub
                </a>
            </div>
        </div>
    </div>
{/if}

<style>
    .header {
        position: relative;
        padding: 0;
        background: var(--bg-secondary, #141530);
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        z-index: 100;
        flex-shrink: 0;
        overflow: hidden;
    }

    .header-accent-line {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: var(
            --gradient-header,
            linear-gradient(90deg, #9333ea, #e839a0, #22d3ee)
        );
        opacity: 0.7;
    }

    .header-inner {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 10px 20px;
    }

    .header-logo {
        font-size: 14px;
        font-weight: 800;
        letter-spacing: 2px;
        color: var(--text-primary, #f0f0f8);
        padding: 4px 8px;
        border: 1.5px solid rgba(147, 51, 234, 0.5);
        border-radius: 4px;
        background: linear-gradient(
            135deg,
            rgba(147, 51, 234, 0.15),
            rgba(232, 57, 160, 0.1)
        );
        text-shadow: 0 0 8px rgba(147, 51, 234, 0.4);
        flex-shrink: 0;
    }

    .header-title {
        color: var(--text-primary, #f0f0f8);
        font-size: 15px;
        margin: 0;
        font-weight: 600;
        letter-spacing: 0.5px;
        white-space: nowrap;
    }

    .header-divider {
        color: var(--text-muted, #6b6b8d);
        margin: 0 2px;
        font-weight: 300;
    }

    .header-subtitle {
        color: var(--text-secondary, #a8a8c8);
        font-weight: 400;
    }

    .about-btn {
        margin-left: auto;
        background: var(--glass-bg, rgba(20, 22, 50, 0.55));
        border: 1px solid var(--border-subtle, rgba(147, 51, 234, 0.25));
        color: var(--text-secondary, #a8a8c8);
        border-radius: var(--radius-sm, 8px);
        padding: 5px 14px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .about-btn:hover {
        background: rgba(147, 51, 234, 0.2);
        border-color: rgba(147, 51, 234, 0.5);
        color: var(--text-primary, #f0f0f8);
    }

    .modal-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.6);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        backdrop-filter: blur(4px);
    }

    .modal-content {
        background: var(--bg-secondary, #141530);
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        border-radius: var(--radius-md, 12px);
        padding: 28px 36px;
        max-width: 640px;
        width: 92%;
        position: relative;
        color: var(--text-primary, #f0f0f8);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
        text-align: left;
    }
    .modal-content h2 {
        margin: 0 0 12px;
        font-size: 20px;
        font-weight: 700;
        color: var(--text-primary, #f0f0f8);
    }
    .modal-content p {
        margin: 0;
        font-size: 15px;
        line-height: 1.65;
        color: var(--text-secondary, #c1c1d6);
    }
    .modal-content p + p {
        margin-top: 12px;
    }
    .modal-content p:first-of-type {
        font-weight: 500;
    }
    .modal-content strong {
        color: var(--text-primary, #f0f0f8);
        font-weight: 700;
    }

    .modal-close {
        position: absolute;
        top: 12px;
        right: 14px;
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        font-size: 22px;
        cursor: pointer;
        line-height: 1;
        padding: 2px 6px;
        border-radius: 4px;
        transition: color 0.15s ease;
    }
    .modal-close:hover {
        color: var(--text-primary, #f0f0f8);
    }

    /* Container für die Lizenz-Sektion im Modal */
    .modal-footer-license {
        margin-top: 20px;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }

    /* Die Trennlinie über dem GitHub-Link */
    .modal-divider {
        width: 100%;
        border: none;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 5px;
    }

    /* Der Text "Licensed under AGPL v3" */
    .license-label {
        font-size: 12px;
        color: var(--text-secondary, #a8a8c8);
        opacity: 0.8;
    }

    /* Die optimierte GitHub-Link Klasse */
    .github-link {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 18px;
        background: rgba(147, 51, 234, 0.15); /* Dezentes Lila */
        border: 1px solid rgba(147, 51, 234, 0.4);
        border-radius: 8px;
        color: #ffffff; /* Weiß für maximalen Kontrast */
        text-decoration: none;
        font-size: 14px;
        font-weight: 600;
        transition: all 0.25s ease;
    }

    /* Hover-Effekt für Interaktivität */
    .github-link:hover {
        background: rgba(147, 51, 234, 0.3);
        border-color: #e839a0; /* Wechselt zu Pink beim Hover (passend zum Header-Gradient) */
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(147, 51, 234, 0.3);
    }

    /* Sorgt dafür, dass das Icon und Text perfekt auf einer Linie liegen */
    .github-link svg {
        flex-shrink: 0;
        fill: currentColor; /* Verwendet die Textfarbe (#ffffff) auch für das Icon */
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }

    .lang-switch {
        display: flex;
        padding: 3px;
        border-radius: 6px;
    }

    .lang-switch button {
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        font-size: 11px;
        font-weight: 700;
        padding: 4px 8px;
        cursor: pointer;
        border-radius: 4px;
        transition: all 0.2s ease;
    }

    .lang-switch button.active {
        background: rgba(147, 51, 234, 0.3);
        color: #fff;
    }

    .content-area {
        min-height: 180px; /* Verhindert das Springen des Modals beim Umschalten */
    }
</style>
