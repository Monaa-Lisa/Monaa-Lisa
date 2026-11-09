<script lang="ts">
    // Fonts are bundled with the app, so visitors' browsers do not contact
    // a font CDN (no third party requests, GDPR friendly).
    import "@fontsource/ibm-plex-sans/latin-400.css";
    import "@fontsource/ibm-plex-sans/latin-500.css";
    import "@fontsource/ibm-plex-sans/latin-600.css";
    // Design tokens and base styles
    import "../app.css";

    let { children } = $props();
</script>

{@render children()}
